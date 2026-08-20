# Full chat parity over EC and REST: list, read, receive and send peer/friend messages

## Summary

Chatting with a friend works only in the **monolithic** aMule today. Over EC the
feature is half-built, and that blocks both remote clients:

- **Receiving** is a one-way relay: `amuled` buffers incoming peer messages in a
  per-connection queue and hands them out, destructively, on
  `EC_OP_GET_CHAT_MESSAGES`. There is no history, no session list, and each EC
  client sees only what arrived while it was connected.
- **Sending does not exist over EC at all.** `CChatSelector::SendMessage`
  carries a literal `// #warning EC needed here.` (`src/ChatSelector.cpp:241`)
  and the whole send path is `#ifndef CLIENT_GUI`, which is why amulegui ships
  with a permanently disabled compose box (`src/ChatWnd.cpp:217-228`).
- `amuleapi` does not even advertise the chat capability, so it gets nothing.

**Goal:** a remote client — amulegui over EC, or any REST client through
`amuleapi` — can **list** chat sessions, **read** their history, **receive** new
messages and **send** messages to a friend or any peer, exactly as the local
GUI can.

Getting there needs the chat model to move **into the core**, as a small session
store both builds feed. Today the transcript exists only inside the monolithic
GUI's notebook tabs, so there is nothing for EC to serve and no way for two
clients to agree on what was said. With the store in place, the local GUI,
amulegui and `amuleapi` are three views of the same conversation — which also
removes the "message sent from amulegui is invisible to amuleapi" split-brain
that a client-side-only design would bake in.

## Scope

1. **Core** — a chat session store, fed at the two existing choke points.
2. **EC** — new ops to list sessions, read history, send and close, plus a
   capability tag. Backward compatible: the legacy drain keeps working untouched.
3. **amulegui** — consume the store; enable the compose box.
4. **amuleapi** — REST endpoints + two new event types on the single SSE stream.

## Current state

| Piece | Location |
|---|---|
| Inbound choke point (one call, both builds) | `src/BaseClient.cpp:3011` — `Notify_ChatProcessMsg(GUI_ID(...), name + "\|" + message)` |
| Outbound choke point | `src/ClientList.cpp:811-828` — `CClientList::SendChatMessage(gui_id, text)` → `CUpDownClient::SendChatMessage` (`src/BaseClient.cpp:2601+`) |
| Message filter (applies before either) | `src/BaseClient.cpp:3015+` — `CUpDownClient::IsMessageFiltered` |
| Relay hook into EC | `src/GuiEvents.cpp:765-780` — `ChatProcessMsg` → `ExternalConn::QueueChatMessage` |
| Per-connection queue (cap 100, oldest dropped) | `src/ExternalConn.cpp:451-461` |
| Fan-out to chat-capable connections | `src/ExternalConn.cpp:1067+` |
| Destructive drain handler | `src/ExternalConn.cpp:4117-4130` — `case EC_OP_GET_CHAT_MESSAGES` |
| Capability `EC_TAG_CAN_CHAT` (`0x0016`) advertise / echo / read | `src/libs/ec/cpp/RemoteConnect.cpp:148-151`, `src/ExternalConn.cpp:1455-1459`, `RemoteConnect.cpp:788-793` (accessor `RemoteConnect.h:332`) |
| amulegui: receive-only consumer | `src/amule-remote-gui.cpp:467` (poll), `:1309-1324` (`CChatMsgHandlerRem::HandlePacket`) |
| amulegui: send disabled | `src/ChatSelector.cpp:215-252`, `src/ChatWnd.cpp:217-228` |
| Local session model (GUI-only, not shared) | `src/ChatSelector.cpp` — `CChatSession` notebook pages |
| amuleapi never advertises chat | `src/webapi/App.cpp:404-410`; `src/ExternalConnector.cpp:458-461` has no `SetCanChat` |

### Wire shape of the legacy drain (stays supported, unchanged)

`EC_OP_GET_CHAT_MESSAGES` (`0x5B`, **no tags**) → `EC_OP_CHAT_MESSAGES` (`0x5C`)
with one `EC_TAG_CHAT` per buffered message: tag value is the string
`"<peer name>|<message text>"`, sub-tag `EC_TAG_CHAT_CLIENT_ID` (`0x0901`) is
the sender's **GUI_ID**, a uint64 packed as `(ip << 16) | port`
(`src/OtherFunctions.h:328-331`), the IP in the same byte order as
`EC_TAG_CLIENT_USER_IP`.

---

## Part 1 — Core chat session store

New core component (compiled into **both** `amule` and `amuled`; no GUI
dependency), e.g. `src/ChatSessionStore.{h,cpp}`, owned by `CamuleApp`.

**Model**

- Sessions keyed by **GUI_ID** (uint64). Per session: peer name, ip, port, the
  linked live client ECID (0 when offline), the friend ECID when the peer is in
  the friends list, and a ring of messages.
- Per message: `id` (uint32, **monotonic across the whole store**, never reused
  within a process), `direction` (in / out), `timestamp` (unix seconds), `text`.
- A store-wide `last_msg_id`, so a client can resume with one cursor rather than
  one per session.
- Bounded: **200 messages per session, 50 sessions**, oldest evicted first.
  Plain constants — no new preference and no EC prefs work until someone asks
  for one.
- In-memory only. The daemon does not persist chat today and this issue does not
  add that; document it.

**Feeding it** — two calls, both already single choke points:

- Inbound: in `CUpDownClient::ProcessChatMessage`, right where
  `Notify_ChatProcessMsg` fires (`src/BaseClient.cpp:3011`) — **after** the
  message filter and the spam/captcha branches, so the store holds exactly what
  the user is meant to see.
- Outbound: in `CClientList::SendChatMessage` (`src/ClientList.cpp:811-828`),
  recording the message whether or not the peer is connected yet — the core
  queues it for a connecting client (`src/BaseClient.cpp:2614-2625`) and the
  desktop optimistically shows it, so the store should too.

**Removal must be a notification, not a silent drop.** Mirror
`MuleNotify::Search_Removed` (`src/GuiEvents.cpp:711-716`,
`src/SearchList.cpp:322`): when a session leaves the store, the core raises
`Notify_Chat_SessionRemoved(gui_id)` and the monolithic GUI closes that tab
through the `CChatWnd::EndSession(uint64)` that already exists
(`src/ChatWnd.cpp:260-263`). Without it, a session closed from the web leaves a
tab open on a transcript that no longer exists anywhere — the exact failure the
search code refuses to allow (`src/amule-remote-gui.cpp:3562-3575`).

**And the monolithic GUI's own close must reach the store.** Today closing a
chat tab is a bare notebook `DeletePage` (`src/ChatWnd.cpp:121-124`,
`:159-162`) that touches nothing in the core — unlike a search tab, which goes
through `CSearchDlg::OnSearchClosing`. Add the same wiring: an
`EVT_MULENOTEBOOK_PAGE_CLOSING` handler on `CChatWnd` that removes the session
from the store, with the reentrancy guard `CSearchDlg` already needs
(`src/SearchDlg.cpp:792-812` — the store's removal notify routes straight back
into `EndSession` → `DeletePage`).

Without both halves the three clients disagree about what "closed" means: the
web close would destroy core state the local GUI still shows, and the local
close would leave a session the web still lists. With them, all three converge
on one core operation exactly as search tabs do.

Rendering `CChatSelector`'s **content** from the store (rather than from its own
`CChatSession` text buffers) stays an optional follow-up — the close/notify
wiring above is what is required.

---

## Part 2 — EC protocol extension

### New opcodes and tags

`src/libs/ec/abstracts/ECCodes.abstract` (last used opcode is `0x62`, last used
capability tag `0x0026`):

```
EC_OP_GET_CHAT_SESSIONS             0x63
EC_OP_CHAT_SESSIONS                 0x64
EC_OP_CHAT_SEND                     0x65
EC_OP_CHAT_CLOSE_SESSION            0x66

EC_TAG_CAN_CHAT_SESSIONS            0x0027

    EC_TAG_CHAT_SESSION             0x0902   # container; value = GUI_ID (uint64)
    EC_TAG_CHAT_MESSAGE             0x0903   # container; value = message text
    EC_TAG_CHAT_MSG_ID              0x0904   # uint32 monotonic id / cursor
    EC_TAG_CHAT_DIRECTION           0x0905   # uint8: 0 = incoming, 1 = outgoing
    EC_TAG_CHAT_TIMESTAMP           0x0906   # uint32 unix seconds
    EC_TAG_CHAT_PEER_NAME           0x0907   # string
```

`EC_TAG_CHAT` (`0x0900`) and `EC_TAG_CHAT_CLIENT_ID` (`0x0901`) keep their
current meaning; the new tags are siblings under the same `0x09xx` block.

### `EC_OP_GET_CHAT_SESSIONS` → `EC_OP_CHAT_SESSIONS`

The per-tick workhorse: **one roundtrip returns the session list and every
message newer than the client's cursor**, so an idle connection costs one small
packet and a busy one needs no follow-up query.

**Request:** optional `EC_TAG_CHAT_MSG_ID` — the highest message id the client
already holds. Absent or `0` means "everything you still have".

**Reply:** top-level `EC_TAG_CHAT_MSG_ID` = the store's current `last_msg_id`
(so the client can advance its cursor even when nothing came back), then one
`EC_TAG_CHAT_SESSION` per session:

| Sub-tag | Meaning |
|---|---|
| *(tag value)* | GUI_ID |
| `EC_TAG_CHAT_PEER_NAME` | Peer display name |
| `EC_TAG_CLIENT` | Linked live peer ECID; omitted when offline |
| `EC_TAG_FRIEND` | Friend ECID; omitted when the peer is not a friend |
| `EC_TAG_CHAT_MSG_ID` | This session's highest message id |
| `EC_TAG_CHAT_MESSAGE` × N | Only messages with `id >` the request cursor |

Each `EC_TAG_CHAT_MESSAGE` carries the text as its tag value plus
`EC_TAG_CHAT_MSG_ID`, `EC_TAG_CHAT_DIRECTION` and `EC_TAG_CHAT_TIMESTAMP`.

A session with no new messages is still listed (with no `EC_TAG_CHAT_MESSAGE`
children) so a client that connected late learns the session exists.

### `EC_OP_GET_CHAT_MESSAGES` — extended, backward compatible

Keep the opcode; branch on the tags present:

- **no tags** → the legacy destructive drain of the per-connection queue.
  Byte-for-byte unchanged, so today's amulegui keeps working against a new
  daemon.
- **with `EC_TAG_CHAT_CLIENT_ID`** (+ optional `EC_TAG_CHAT_MSG_ID` cursor) →
  a **non-destructive** read of that one session's history from the store,
  answered with the `EC_OP_CHAT_SESSIONS` shape above (a single session
  container). This is what backfills a conversation the client is opening for
  the first time.

### `EC_OP_CHAT_SEND`

| Tag | Required | Meaning |
|---|---|---|
| `EC_TAG_CHAT` | yes | Tag value = message text (UTF-8, non-empty) |
| `EC_TAG_CHAT_CLIENT_ID` | one of the three | Target GUI_ID — the id incoming messages arrive with, so replying needs no lookup |
| `EC_TAG_CLIENT` | " | Target by live peer ECID; the daemon derives the GUI_ID via `GUI_ID(client->GetIP(), client->GetUserPort())` |
| `EC_TAG_FRIEND` | " | **Target by friend ECID** — resolves through `CFriendList::FindFriend` to the friend's stored IP:port, so an *offline* friend is reachable, exactly like `CFriendList::StartChatSession` |

Implementation is thin: resolve the target to a GUI_ID, call
`theApp->clientlist->SendChatMessage(gui_id, text)` — which already builds a
`CUpDownClient` from the ip/port when none exists (`src/ClientList.cpp:817-826`)
— and let the store record it via the outbound hook.

**Reply:** `EC_OP_NOOP` with `EC_TAG_CHAT_CLIENT_ID` (the resolved GUI_ID) and
`EC_TAG_CHAT_MSG_ID` (the id the store assigned), so the sender can correlate
without waiting for the next poll. `EC_OP_FAILED` + `EC_TAG_STRING` on an
unknown target or empty text.

Note the semantics the desktop already has: a `false` return from
`CUpDownClient::SendChatMessage` means *queued while connecting*, not *failed* —
so it must not become an `EC_OP_FAILED`.

### `EC_OP_CHAT_CLOSE_SESSION`

`EC_TAG_CHAT_CLIENT_ID` → drop the session from the store and call
`CClientList::SetChatState(gui_id, MS_NONE)` (`src/ClientList.cpp:830-836`).
Reply `EC_OP_NOOP`.

Closing is **global**: the session goes away for every client. That is not a
compromise forced by the shared store — it is the semantic search tabs already
have, and the one this project deliberately settled on:

| Client | Closing a search tab does | Where |
|---|---|---|
| monolithic aMule | `theApp->searchlist->RemoveResults(id)` — frees the core bucket in-process | `src/SearchDlg.cpp:792-840` |
| amulegui | `EC_OP_SEARCH_STOP` + `EC_TAG_SEARCH_CLOSE` → the daemon runs the same `RemoveResults(id)` and forgets the id | `src/amule-remote-gui.cpp:3406-3430`, `src/ExternalConn.cpp:3077-3089` |
| amuleapi | `POST /search/stop {"close":true}` → the same tag | `src/webapi/Api.cpp:8319-8375` |

There is no per-client view of a search anywhere in the codebase: one client's
close destroys core state, and the other clients are **told** rather than left
holding a stale tab. The reasoning is spelled out at
`src/amule-remote-gui.cpp:3562-3575` — a tab for a search the daemon no longer
has "can only mislead", and acting on one of its results would silently do
nothing.

Chat must propagate the same way, and the session-list op gives it for free:
`EC_OP_CHAT_SESSIONS` reports the daemon's **whole** set, so a session a client
is tracking that is missing from the reply was closed elsewhere — exactly the
rule the union-progress path already uses for searches
(`src/amule-remote-gui.cpp:3620-3637`). No expiry tag needed.

### Capability handshake — do not skip it

A client must never send an unknown opcode: it lands in `ProcessRequest2`'s
unknown-opcode branch, which **asserts** before it can answer `EC_OP_FAILED`.
Follow the `EC_TAG_CAN_CLIENT_HISTORY` precedent exactly — the client advertises
`EC_TAG_CAN_CHAT_SESSIONS`, the daemon echoes it unconditionally, the client
exposes `ServerSupportsChatSessions()` and gates all four new ops on it.

One tag covers the whole set: list, history, send and close ship together.
`EC_TAG_CAN_CHAT` stays what it is — a request for the legacy relay — and a
client that advertises `EC_TAG_CAN_CHAT_SESSIONS` should **not** also advertise
it, so the daemon skips queueing to that connection and the client reads
everything from the store instead of receiving each message twice.

---

## Part 3 — amulegui

- Advertise `EC_TAG_CAN_CHAT_SESSIONS` (`src/amule-remote-gui.cpp:621-625`,
  `:755-756`) and, when the daemon echoes it, replace the drain poll
  (`:467`) with `EC_OP_GET_CHAT_SESSIONS` + cursor. Keep the old drain as the
  fallback path for an older daemon (receive-only, exactly as today).
- Populate `CChatSelector` tabs from the session list, so a session that already
  existed before amulegui connected shows up with its history — today a
  reconnect starts from nothing. Replay history through `StartSession()` +
  direct `AddText()`, **not** through `CChatWnd::ProcessMessage`, which sets the
  new-message blink (`src/ChatWnd.cpp:189-193`): a reconnect must not light the
  Messages toolbar button up for messages the user already read. Only messages
  arriving after the cursor the client connected with should blink.
- Close a tab whose session is **absent from the session list**, without sending
  a close of its own — the session was closed by another client. Mirror
  `CSearchDlg::CloseSearchTab` and the union-progress reconciliation at
  `src/amule-remote-gui.cpp:3620-3637`, including the "snapshot the tracked set
  first" detail (closing a tab mutates the set you are iterating).
- Send `EC_OP_CHAT_CLOSE_SESSION` when the **user** closes a tab, the way
  `OnSearchClosing` sends `EC_TAG_SEARCH_CLOSE` — and skip it on the
  closed-elsewhere path above, the same guard `m_expiringSearchID` provides for
  searches (`src/SearchDlg.cpp:818-825`).
- Route `CChatSelector::SendMessage` through `EC_OP_CHAT_SEND` and drop the
  `#ifndef CLIENT_GUI` guard, and drop the `CLIENT_GUI` branch of
  `CChatWnd::CheckNewButtonsState` so the compose box and Send button enable.
  This removes the `// #warning EC needed here.` at `src/ChatSelector.cpp:241`.
- Wire "Send message" on the peer and friend context menus
  (`src/ClientContextActions.cpp:60`, `src/FriendListCtrl.cpp:190`) to the same
  path.

**End-to-end test for the whole issue:** hold a two-way conversation from
amulegui with a friend, then open `amuleapi` and see the same transcript.

---

## Part 4 — amuleapi REST surface

### Handshake and polling

- Add `m_canChatSessions` to `CaMuleExternalConnector` (mirroring
  `m_canMultiSearch`, `src/ExternalConnector.h:284`) and set it on the EC client
  next to `SetCanMultiSearch` (`src/ExternalConnector.cpp:461`); enable it in
  `CamuleapiApp` beside `m_canMultiSearch = true` (`src/webapi/App.cpp:410`).
- Expose `IsServerChatSessionsActive()` on the app, mirroring the existing
  `IsServerClientHistoryActive()` used at `src/webapi/Api.cpp:4413`.
- Add one `EC_OP_GET_CHAT_SESSIONS` roundtrip to `RefresherTick`
  (`src/webapi/RefresherTick.cpp`), **gated on the capability** and skipped
  entirely otherwise, carrying the cursor from the previous tick. Mirror the
  sessions into `CState`; the tick is 1 s (`src/webapi/App.cpp:526`).
- Every endpoint below answers `503 ec_unsupported` when the connected `amuled`
  lacks the capability — the same shape `/known_clients` already uses.

### Conversation key

`{peer}` = `"<ip>:<port>"`, the readable form of the GUI_ID the wire already
uses (e.g. `203.0.113.42:4662`). Stable across peer reconnects, unlike an ECID,
needs no invented identifier, and converts straight back to the GUI_ID the EC
ops want. The handler must validate the shape and reject anything else with
`400 bad_request`.

---

### `GET /api/v0/chats`

**Auth:** `GUEST`

```json
{
  "chats": [
    {
      "peer":            "203.0.113.42:4662",
      "ip":              "203.0.113.42",
      "port":            4662,
      "name":            "alice",
      "client_ecid":     4382,
      "friend_ecid":     12,
      "online":          true,
      "message_count":   14,
      "last_msg_id":     91,
      "last_message_at": 1786652714,
      "last_message":    { "id": 91, "direction": "in", "text": "thanks!", "timestamp": 1786652714 }
    }
  ],
  "total": 1, "offset": 0, "limit": 1
}
```

- `name` — from `EC_TAG_CHAT_PEER_NAME`; falls back to `"IP: <ip> Port: <port>"`
  exactly as the desktop does when the core has no name
  (`src/ChatSelector.cpp:191-196`).
- `client_ecid` / `friend_ecid` — `0` when the peer is offline / not a friend.
  Join against `GET /clients` and `GET /friends`.
- Standard [list envelope](../../docs/api/REFERENCE.md#list-pagination-and-sorting);
  sortable on `last_message_at`, `name`.

Served from the refresher snapshot — no extra EC roundtrip per request.

**Errors:** `503 ec_unsupported`, `503 ec_unavailable`.

---

### `GET /api/v0/chats/{peer}/messages`

**Auth:** `GUEST`

**Query:** `since_id=N` (only messages with `id > N`), `limit=N` (last N,
capped at the store's per-session retention).

```json
{
  "peer": "203.0.113.42:4662",
  "messages": [
    { "id": 90, "direction": "out", "text": "hi",      "timestamp": 1786652700 },
    { "id": 91, "direction": "in",  "text": "thanks!", "timestamp": 1786652714 }
  ],
  "total": 14,
  "last_msg_id": 91
}
```

`direction` is `"in"` (from the peer) or `"out"` (sent by us — from **any**
client: this API, amulegui, or the local GUI). `timestamp` is stamped by the
core when the message was received or sent.

`id` is monotonic per `amuled` process, so `since_id` is a safe polling cursor;
it resets when the daemon restarts, which also empties the store.

**Errors:** `404 not_found` (no such session), `400 bad_request` (malformed
`{peer}` or query), `503 ec_unsupported`, `503 ec_unavailable`.

---

### `POST /api/v0/chats/{peer}/messages`

**Auth:** `ADMIN`

**Body:** `{ "text": "hello" }` — non-empty, capped by the handler (suggest
1024 chars).

Sends `EC_OP_CHAT_SEND` with the GUI_ID decoded from `{peer}`; the core creates
the session if it does not exist, so this doubles as "start a chat with this
address".

**Response:** `202 Accepted` → the created message object (with the `id` the
core assigned).

`202`, not `200`: the core acknowledges that it queued the message on the peer
connection, not that the peer received it. An unreachable peer is not an error
here — the desktop behaves the same, optimistically printing
`*** Connecting to Client ***`.

**Errors:** `400 bad_request`, `400 amuled_rejected`, `503 ec_unsupported`,
`503 ec_unavailable`.

---

### `POST /api/v0/friends/{ecid}/messages`

**Auth:** `ADMIN`

Message a friend by friend ECID — the primary path, and the one that reaches an
**offline** friend through their stored IP:port. Sends `EC_OP_CHAT_SEND` with
`EC_TAG_FRIEND`.

**Body:** `{ "text": "hello" }`
**Response:** `202 Accepted` → `{ "ok": true, "peer": "203.0.113.42:4662", "message": { … } }`
so the caller learns the conversation key to read back.

**Errors:** `404 not_found` (no friend with that ECID), plus the set above.

> Pairs with the [friends issue](friends-rest-api.md), which adds
> `GET /api/v0/friends`. If the two land in either order, this endpoint only
> needs the friend ECID to exist on the daemon — it does not depend on the
> friends REST collection.

---

### `POST /api/v0/clients/{ecid}/messages`

**Auth:** `ADMIN`

The peer-addressed form, for the desktop's "Send message" context item on a peer
row — a caller holding an ECID should not have to compose an `ip:port` key.
Sends `EC_OP_CHAT_SEND` with `EC_TAG_CLIENT`. Same body and response as above.

**Errors:** `404 not_found` (no live peer with that ECID), plus the set above.

---

### `DELETE /api/v0/chats/{peer}`

**Auth:** `ADMIN`

Closes the session — `EC_OP_CHAT_CLOSE_SESSION`. Drops it from the core store
and resets the peer's chat state.

**Response:** `200 OK` → `{ "ok": true, "peer": "…" }`

Closing is **global**, matching how a search tab closes from any client (see
[`EC_OP_CHAT_CLOSE_SESSION`](#ec_op_chat_close_session)): a connected amulegui
drops the tab on its next poll. Say so on the endpoint.

**Errors:** `404 not_found`, `400 bad_request`, `503 ec_unsupported`,
`503 ec_unavailable`.

---

## SSE events

`amuleapi` serves **one** SSE stream (`GET /api/v0/events`) carrying every event
type. Two new types:

| Event | Payload |
|---|---|
| `chat_message` | `{ "peer": "203.0.113.42:4662", "ip": "…", "port": 4662, "name": "alice", "client_ecid": 4382, "friend_ecid": 12, "message": { "id": 91, "direction": "in", "text": "thanks!", "timestamp": 1786652714 } }` |
| `chat_session_closed` | `{ "peer": "203.0.113.42:4662" }` |

One event per message, **inbound and outbound alike** — an outbound one is how a
second UI tab, or a message the user sent from amulegui, reaches every other
viewer. A session that did not exist is implied by the first message carrying
its `peer`; no separate "session started" event.

> **Channel filter.** No change needed to the SSE machinery. The prefix mapper
> (`src/webapi/Api.cpp:8756-8783`) ends in `return prefix`, so `chat_*` resolves
> to a `chat` channel on its own; a subscriber that sends no `?channels=` —
> which is every client today, including the bundled web UI — receives
> everything regardless. Add one line, `if (prefix == "chat") return "chats";`,
> only if you want the token to read plural like `downloads` / `clients`.

---

## Implementation checklist

**Core (`src/`)**
- [ ] `ChatSessionStore.{h,cpp}` — the store, its caps and the monotonic id counter; owned by `CamuleApp`, built in both targets.
- [ ] `BaseClient.cpp:3011` — record the inbound message in the store (after the filter / spam branches).
- [ ] `ClientList.cpp:811-828` — record the outbound message in the store.
- [ ] `GuiEvents.{h,cpp}` — `Notify_Chat_SessionRemoved(gui_id)` → `CChatWnd::EndSession`, mirroring `Notify_Search_Removed`.
- [ ] `ChatWnd.{h,cpp}` — an `EVT_MULENOTEBOOK_PAGE_CLOSING` handler that removes the session from the store, plus the reentrancy guard against the notify routing back in.
- [ ] `libs/ec/abstracts/ECCodes.abstract` — the four opcodes, the capability tag and the six `0x09xx` tags.
- [ ] `libs/ec/cpp/RemoteConnect.{h,cpp}` — advertise `EC_TAG_CAN_CHAT_SESSIONS`, read the echo, add `ServerSupportsChatSessions()` and `SetCanChatSessions()`.
- [ ] `ExternalConn.cpp` — echo the capability next to `EC_TAG_CAN_CHAT` (`:1455`); handlers for the four ops; the tagged branch of `EC_OP_GET_CHAT_MESSAGES`; skip `QueueChatMessage` for sessions-capable connections.
- [ ] `ECSpecialTags.{h,cpp}` — a `CEC_ChatSession_Tag` / `CEC_ChatMessage_Tag` pair so both clients share one parser.

**amulegui (`src/`)**
- [ ] `amule-remote-gui.{h,cpp}` — advertise the capability, poll `EC_OP_GET_CHAT_SESSIONS` with a cursor, keep the legacy drain as fallback.
- [ ] `ChatSelector.cpp` / `ChatWnd.cpp` — build tabs from the session list, send via `EC_OP_CHAT_SEND`, enable the compose box.

**amuleapi (`src/webapi/`)**
- [ ] `ExternalConnector.{h,cpp}` + `App.{h,cpp}` — `m_canChatSessions`, `IsServerChatSessionsActive()`.
- [ ] `State.h` — session + message snapshot structs and the cursor.
- [ ] `RefresherTick.cpp` — the gated `EC_OP_GET_CHAT_SESSIONS` roundtrip.
- [ ] `EventDiff.{h,cpp}` — publish `chat_message` per new message and `chat_session_closed`.
- [ ] `Api.cpp` — the six routes, the writers, and the `503 ec_unsupported` gate.

**Docs**
- [ ] `docs/api/REFERENCE.md` — index entries + a `### Chat` section.
- [ ] `docs/api/EVENTS.md` — the two new event types in the catalog.
- [ ] `docs/EC_Protocol.md` — the new opcodes, tags and capability.

**Web UI (`src/webapi/static`) — optional follow-up, can ship separately**
- [ ] A Messages view (session list + transcript + compose), i18n keys in `static/i18n/*.json`.

## Acceptance criteria

- [ ] A message sent by a remote peer appears in `GET /api/v0/chats`, in a connected amulegui, and in the monolithic GUI — all three with the same text and sender.
- [ ] `POST /api/v0/friends/{ecid}/messages` reaches the friend, including when the friend was **not** connected when the call was made.
- [ ] A message sent from amulegui shows up in `GET /api/v0/chats/{peer}/messages` with `direction: "out"`, and vice versa.
- [ ] An amulegui that connects **after** a conversation started sees its history, not an empty tab.
- [ ] amulegui's compose box is enabled and sends successfully; the `// #warning EC needed here.` is gone.
- [ ] `since_id` polling never returns a duplicate and never skips a message.
- [ ] Retention caps are enforced (201st message in a session evicts the oldest; 51st session evicts the least recently active).
- [ ] Closing a session from `amuleapi` makes a connected amulegui drop the tab on its next poll, and vice versa — neither sends a redundant close back.
- [ ] Closing a session from the monolithic GUI removes it from `GET /api/v0/chats`; closing it from the web closes the monolithic GUI's tab. No client is left showing a session the core no longer has.
- [ ] Reconnecting amulegui rebuilds its tabs with their history and does **not** flash the new-message blink for it.
- [ ] Against an `amuled` **without** `EC_TAG_CAN_CHAT_SESSIONS`: every REST chat endpoint answers `503 ec_unsupported`, amulegui falls back to the legacy receive-only drain, and **no** unknown opcode ever goes on the wire — verified against a debug build, where an unknown opcode asserts.
- [ ] An old amulegui (advertising only `EC_TAG_CAN_CHAT`) against a **new** daemon keeps receiving messages exactly as before.

## Out of scope

- **Chat captcha** (`CCaptchaDialog` / `CCaptchaGenerator`). The whole anti-spam captcha path is `#ifndef AMULE_DAEMON` (`src/BaseClient.cpp:2846-2850`); the daemon relies on the message filter alone, so there is nothing to expose. The filter itself is already configurable through `preferences.message_filter`.
- Persisting chat history to disk across an `amuled` restart — deliberately deferred; see [Follow-up: on-disk chat history](#follow-up-on-disk-chat-history) at the end of this issue.
- Relaying the transcript's connect/disconnect notices (`ChatConnResult`, `src/GuiEvents.cpp:752-758`), which are `#ifndef AMULE_DAEMON` and would need their own relay.
- Refactoring the monolithic GUI's `CChatSelector` to render its transcript from the store. It must *feed* the store and take part in open/close (see Part 1), but its existing text buffers can keep painting the tab.

---

## Follow-up: on-disk chat history

**Not part of this issue.** The store above is in-memory, so an `amuled`
restart empties every conversation — the same behaviour the monolithic GUI has
today, where the transcript dies with the notebook page. Persisting it is a
clean, self-contained follow-up once the store exists, and it needs **no EC
change at all**: the ops already serve whatever the store holds, so history
simply survives a restart from every client's point of view.

Sketched here so the store is not designed in a way that makes it awkward
later.

### Format and location

Follow the house pattern for small persisted lists — `emfriends.met`
(`src/FriendList.cpp:99-147`): `${config_dir}/chats.met`, a `MET_HEADER` byte,
a `uint32` record count, then one record per session written through
`CFileDataIO` (GUI_ID, peer name, ip, port, then its message count and each
message's id / direction / timestamp / text). `CFriend::LoadFromFile` /
`WriteToFile` (`src/Friend.cpp:126-170`) is the shape to copy, tag-based
extension included, so a future field does not invalidate the file.

### Save policy

`CFriendList::SaveList()` rewrites the whole file on every mutation, which is
fine for a list that changes a few times a day. Chat is not that: a busy
conversation would rewrite the file per message. Use a **dirty flag plus a
debounced flush** (say, at most one write every 30 s), and an unconditional
flush on clean shutdown, from the same place the friend list is saved.

### The message-id counter must persist too

This is the detail worth deciding now. `id` is monotonic per process, and
clients hold it as a resume cursor (`since_id` over REST,
`EC_TAG_CHAT_MSG_ID` over EC). If history is restored but the counter restarts
at 1, a client reconnecting with cursor `91` either never sees new messages or
sees ids it already has. So **persist `last_msg_id`** alongside the sessions and
continue from it.

The alternative — keep per-process ids and make clients resync after a daemon
restart — is more machinery for less: the SSE stream already has a `resync`
frame, but nothing equivalent exists on the EC side, so amulegui would need one
invented for it. Persisting a `uint32` is cheaper than that.

### Privacy

Chat logs on disk are the most sensitive thing aMule would write. Two things
this must not skip:

- Create the file `0600`, the way `amuleapi-passwords` and
  `amuleapi-jwt-secret` already are.
- A preference to turn persistence off, defaulting to **off** — logging
  someone's private messages to disk should be opted into, not discovered.
  This is the one protocol-adjacent bit: making it togglable from amulegui and
  the REST API means an `EC_TAG_PREFS_*` tag under `EC_TAG_PREFS_FILES` (or a
  small new group) plus a `preferences` field, in the same shape as every other
  pref in `src/webapi/PrefsSchema.cpp`. Note it is distinct from the existing
  `ShowMessagesInLog` (`src/Preferences.h:774`), which only echoes incoming
  messages into the aMule log.

### Retention

The in-memory caps (200 messages per session, 50 sessions) apply to what is
written, so the file stays bounded without a second policy. If a user ever
wants a real archive, that is a separate feature — an append-only log per peer,
not a rewrite of this snapshot file.

### Acceptance criteria (for the follow-up)

- [ ] Conversations and their history survive an `amuled` restart when
      persistence is enabled.
- [ ] A client reconnecting after a restart with an old cursor receives exactly
      the messages it missed — no gap, no duplicates.
- [ ] With persistence disabled (the default) nothing is written, and an
      existing `chats.met` is left untouched rather than truncated.
- [ ] The file is `0600` and a corrupt or truncated file is handled like a
      corrupt `emfriends.met`: logged and skipped, never fatal.
