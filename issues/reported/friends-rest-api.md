# Expose the friends list over REST (`/api/v0/friends`): list, add, remove, friend slot

## Summary

The desktop client's **Messages → Friends** panel is the only major GUI surface
that `amuleapi` does not cover at all. A REST/web client can *see* whether a
connected peer happens to be a friend (`is_friend` on `GET /clients/{ecid}`)
but cannot list the friends list, add to it, remove from it, or grant a friend
slot.

Everything needed is **already on the wire**. The daemon ships the complete
friends list inside the same `EC_OP_GET_UPDATE` response `amuleapi` already
issues once per second — and `RefresherTick` explicitly *drops* it. The
mutations (`add` / `remove` / `friend slot` / `browse`) are all branches of the
single `EC_OP_FRIEND` opcode, which `amuleapi` already sends for the "View
Files" browse.

So this is REST-layer plumbing plus **one small core-side addition**: the
friend-slot flag is currently not serialized into the friend tag, so no EC
client (amulegui included — its context-menu checkbox is permanently unchecked)
can read it back.

## Current state

| Piece | Location |
|---|---|
| Friend tag serializer (5 sub-tags) | `src/ECSpecialCoreTags.cpp:593-602` — `CEC_Friend_Tag` |
| Friends appended to every `GET_UPDATE` reply | `src/ExternalConn.cpp:2064-2073` |
| Mutation handler (`add` / `remove` / `friendslot` / `shared`) | `src/ExternalConn.cpp:2428-2540` — `Get_EC_Response_Friend` |
| Opcode dispatch | `src/ExternalConn.cpp:3829` — `case EC_OP_FRIEND` |
| Core list model | `src/FriendList.cpp`, `src/Friend.cpp` |
| amuleapi drops the friends container | `src/webapi/RefresherTick.cpp:93-97` — *"The response also carries `EC_TAG_CLIENT` … and `EC_TAG_FRIEND` containers, both of which we ignore"* |
| amuleapi already sends `EC_OP_FRIEND` (browse only) | `src/webapi/Api.cpp:8095-8100` |
| Reference client-side usage | `src/amule-remote-gui.cpp:3186-3330` — `CFriendListRem` |

## EC protocol reference

Opcode `EC_OP_FRIEND = 0x57`. Tags (`src/libs/ec/abstracts/ECCodes.abstract:426-434`):

| Tag | Id | Direction | Meaning |
|---|---|---|---|
| `EC_TAG_FRIEND` | `0x0800` | both | Container; **tag value is the friend's ECID** |
| `EC_TAG_FRIEND_NAME` | `0x0801` | reply / add | Display name |
| `EC_TAG_FRIEND_HASH` | `0x0802` | reply / add | MD4 user hash (may be empty) |
| `EC_TAG_FRIEND_IP` | `0x0803` | reply / add | uint32 IPv4, same byte order as `EC_TAG_CLIENT_USER_IP` |
| `EC_TAG_FRIEND_PORT` | `0x0804` | reply / add | uint16 TCP port |
| `EC_TAG_FRIEND_CLIENT` | `0x0805` | reply | ECID of the linked live peer, `0` when offline |
| `EC_TAG_FRIEND_ADD` | `0x0806` | request | Sub-tag `EC_TAG_CLIENT` (by peer ECID) **or** the 4-tuple hash/ip/port/name |
| `EC_TAG_FRIEND_REMOVE` | `0x0807` | request | Sub-tag `EC_TAG_FRIEND` (friend ECID) |
| `EC_TAG_FRIEND_FRIENDSLOT` | `0x0808` | request | Tag value = new bool; sub-tag `EC_TAG_FRIEND` |
| `EC_TAG_FRIEND_SHARED` | `0x0809` | request | Browse; sub-tag `EC_TAG_FRIEND` or `EC_TAG_CLIENT` |

All mutations answer `EC_OP_NOOP` on success and `EC_OP_FAILED` + `EC_TAG_STRING`
on failure. `REMOVE` is deliberately **idempotent** (`ExternalConn.cpp:2454-2467`):
removing an unknown ECID still answers `NOOP`.

## Required core-side change (small)

`CEC_Friend_Tag` (`src/ECSpecialCoreTags.cpp:593-602`) does not serialize the
friend-slot flag, so `CFriend::HasFriendSlot()` is permanently `false` on every
EC client. Add it to the reply, reusing the existing tag id:

```cpp
AddTag(EC_TAG_FRIEND_FRIENDSLOT, Friend->HasFriendSlot(), valuemap);
```

Optionally (nice to have, can be deferred without blocking the endpoints) add
two new sub-tags for the two persisted timestamps `CFriend` already keeps and
writes to `emfriends.met` but never transmits — `m_dwLastSeen` and
`m_dwLastChatted` (`src/Friend.cpp:126-135`):

```
EC_TAG_FRIEND_LAST_SEEN     0x080A
EC_TAG_FRIEND_LAST_CHATTED  0x080B
```

All three are **optional sub-tags**: an `amuleapi` built against a newer core
talking to an older `amuled` must degrade gracefully — `friend_slot` reads
`false`, the timestamps are omitted from the JSON. This is the same rule
`is_friend` / `dl_up_modifier` already follow on `GET /clients/{ecid}`.

## Requested change — REST surface

### Resource key

`{ecid}` — the friend's `EC_TAG_FRIEND` id, matching how `EC_OP_FRIEND`'s
`REMOVE` / `FRIENDSLOT` / `SHARED` branches address a friend. Like every other
ECID it is **not stable across an `amuled` restart**; document `user_hash` as
the durable reference, exactly as `GET /clients/{ecid}` already does.

### The friend object

```json
{
  "friend_ecid":  12,
  "name":         "alice",
  "user_hash":    "a1b2c3d4e5060e708090a0b0c0d06f00",
  "ip":           "203.0.113.42",
  "port":         4662,
  "client_ecid":  4382,
  "online":       true,
  "friend_slot":  false
}
```

| Field | Type | Notes |
|---|---|---|
| `friend_ecid` | int | The resource key. |
| `name` | string | `"?"` when the core has no name for the record. |
| `user_hash` | string | 32-char lowercase MD4, or `""` for a friend added by IP:port only (the core supports both — see `CFriendList::FindFriend`, `src/FriendList.cpp:149-174`). |
| `ip` | string | Dotted quad. Render with the existing `FormatClientIpv4()` (`src/webapi/Refresher.cpp:706-722`) — `EC_TAG_FRIEND_IP` has the same encoding as `EC_TAG_CLIENT_USER_IP`. `""` for a zero IP. |
| `port` | int | |
| `client_ecid` | int | Live peer this friend is currently linked to; `0` when offline. Joins against `GET /clients`. |
| `online` | bool | Convenience: `client_ecid != 0`. This is exactly what the desktop list colours green/red. |
| `friend_slot` | bool | Needs the core change above. `false` against an older daemon. |
| `last_seen` / `last_chatted` | int | Unix seconds. **Omitted** when the daemon does not send them (optional core change above). |

---

### `GET /api/v0/friends`

**Auth:** `GUEST`

Standard [list envelope](../../docs/api/REFERENCE.md#list-pagination-and-sorting)
under the `friends` key, with `limit` / `offset` / `sort` / `order`.
Sortable fields: `name`, `online`.

```json
{ "friends": [ { … }, { … } ], "total": 7, "offset": 0, "limit": 7 }
```

Served straight from the refresher snapshot — **no extra EC roundtrip**, the
data already arrives with every tick.

**Errors:** `503 ec_unavailable`.

---

### `POST /api/v0/friends`

**Auth:** `ADMIN`

Two mutually exclusive body forms, mirroring the two `EC_TAG_FRIEND_ADD` shapes.

**Form A — promote a connected peer** (the desktop "Add to Friends" context item):

```json
{ "client_ecid": 4382 }
```

**Form B — add manually** (the desktop *Add a Friend* dialog, `src/AddFriend.cpp:48-80`):

```json
{ "ip": "203.0.113.42", "port": 4662, "name": "alice", "user_hash": "a1b2…" }
```

Validation must match the dialog: `ip` and `port` are **required** and must be
non-zero; `user_hash` is optional but must be 32 hex chars when present; `name`
is optional and defaults to the `ip` string. Note the EC handler requires all
four tags to be *present* (`ExternalConn.cpp:2442-2452`) — send an empty hash
and the defaulted name rather than omitting the tags.

Sending both `client_ecid` and any Form-B field is `400 bad_request`.

**Response:** `201 Created` → the new friend object.

The add is applied synchronously by the daemon but the new record only reaches
`amuleapi` on the next `GET_UPDATE`. Either call `RefresherTick()` inline
before responding (the pattern every mutation handler already uses — e.g.
`src/webapi/Api.cpp:3397`) and return the real object, or return
`202 Accepted` + `{"ok": true}`. Prefer the former for consistency with
`POST /servers` / `POST /categories`.

**Errors:** `400 bad_request` (malformed body, both forms, invalid hash, zero
ip/port), `404 not_found` (`client_ecid` names no live peer), `400 amuled_rejected`,
`503 ec_unavailable`.

---

### `DELETE /api/v0/friends/{ecid}`

**Auth:** `ADMIN`

```json
{ "ok": true, "friend_ecid": 12 }
```

`200 OK`. The EC op is idempotent, but the REST layer should still answer
`404 not_found` when the ECID is absent from the current snapshot — a typo must
be visible, same rule as `DELETE /shared/directories`.

Side effect worth documenting: removing a friend that currently holds the
friend slot clears it (`CFriendList::RemoveFriend`, `src/FriendList.cpp:81-97`).

**Errors:** `404 not_found`, `400 amuled_rejected`, `503 ec_unavailable`.

---

### `PATCH /api/v0/friends/{ecid}`

**Auth:** `ADMIN`

**Body:** `{ "friend_slot": true }` — the only mutable field today. A body with
no recognized field is `400 bad_request`.

**Response:** `200 OK` → the updated friend object.

**Document the exclusivity:** only one friend can hold the slot at a time.
Setting it on one friend clears every other friend's flag
(`CFriendList::SetFriendSlot`, `src/FriendList.cpp:227-251`), so a single PATCH
can produce **two** `friend_updated` SSE events — the new holder and the
previous one. Clients must not assume the response body is the only thing that
changed.

**Errors:** `400 bad_request`, `404 not_found`, `400 amuled_rejected`, `503 ec_unavailable`.

---

### `POST /api/v0/friends/{ecid}/shared_files`

**Auth:** `ADMIN`

Browse a friend's shared files — the friend-addressed twin of the existing
[`POST /clients/{ecid}/shared_files`](../../docs/api/REFERENCE.md#post-apiv0clientsecidshared_files),
and the reason it matters: a friend record carries a stored IP:port, so the
daemon can browse a friend that is **not currently connected** by building a
client from it (`CFriendList::RequestSharedFileList`, `src/FriendList.cpp:203+`).
The clients endpoint can only reach live peers.

Same EC op, same tag, different sub-tag: `EC_TAG_FRIEND_SHARED` carrying
`EC_TAG_FRIEND` instead of `EC_TAG_CLIENT`. The existing handler at
`src/webapi/Api.cpp:8090-8130` needs only the sub-tag swapped, and the reply
parsing (`EC_TAG_SEARCH_ID` / the `EC_OP_FAILED` + `EC_TAG_SEARCH_REF` failure
shape) is identical.

**Response:** `202 Accepted` → `{ "ok": true, "search_id": 17 }`, then poll
`GET /search/results?search_id=17`.

**Errors:** `403 forbidden` (guest), `404 not_found`, `502 bad_gateway`
(daemon returned no `search_id`), `503 ec_unavailable`.

## SSE events

`amuleapi` serves **one** SSE stream (`GET /api/v0/events`) carrying every event
type. Three new types:

| Event | Payload |
|---|---|
| `friend_added` | the friend object |
| `friend_updated` | the friend object |
| `friend_removed` | `{ "friend_ecid": 12 }` |

`friend_updated` must fire on any observable change, including the
online→offline transition (`client_ecid` going to `0`), which is what drives the
desktop list's connected indicator.

> **Channel filter.** No change needed to the SSE machinery. The prefix mapper
> (`src/webapi/Api.cpp:8756-8783`) ends in `return prefix`, so `friend_*`
> resolves to a `friend` channel on its own; a subscriber that sends no
> `?channels=` — which is every client today, including the bundled web UI —
> receives everything regardless. Add one line, `if (prefix == "friend") return
> "friends";`, only if you want the token to read plural like `downloads` /
> `clients`.

## Implementation checklist

**Core (`src/`)**
- [ ] `ECSpecialCoreTags.cpp` — serialize `EC_TAG_FRIEND_FRIENDSLOT` in `CEC_Friend_Tag`; optionally add `EC_TAG_FRIEND_LAST_SEEN` / `_LAST_CHATTED` to `ECCodes.abstract` and emit them.
- [ ] `ECSpecialTags.h` — accessor(s) for the new sub-tag(s) alongside the existing `Name()` / `UserHash()` / `IP()` / `Port()` / `Client()`.
- [ ] Optional cleanup: `CFriendListRem::ProcessItemUpdate` (`amule-remote-gui.cpp:3214`) can then read the flag, fixing amulegui's permanently-unchecked "Establish Friend Slot" item.

**amuleapi (`src/webapi/`)**
- [ ] `State.h` — `FriendSnapshot` struct + an ECID-keyed `std::map` in `CState`, with `Friends()` / `MutateFriends()` accessors mirroring the servers map.
- [ ] `Refresher.{h,cpp}` — `ApplyGetUpdateToFriends(resp, cache)` walker, called from the existing `GET_UPDATE` block in `RefresherTick.cpp:100-165`. Replace the "we ignore" comment while you are there.
- [ ] `EventDiff.{h,cpp}` — add friends to `LastSeenSnapshot` and emit the three events.
- [ ] `Api.cpp` — route table entries for `/api/v0/friends`, `/api/v0/friends/{ecid}`, `/api/v0/friends/{ecid}/shared_files`; `WriteFriendObject()`; the four handlers.
- [ ] `Api.cpp` — factor the browse helper at `:8090-8130` so both the client and friend routes share it.

**Docs**
- [ ] `docs/api/REFERENCE.md` — index entries + a `### Friends` section.
- [ ] `docs/api/EVENTS.md` — the three new event types in the catalog.

**Web UI (`src/webapi/static`) — optional follow-up, can ship separately**
- [ ] A Friends view (list + add/remove + friend slot + "View Files"), plus i18n keys in `static/i18n/*.json`.

## Acceptance criteria

- [ ] `GET /friends` lists what the desktop Friends panel lists, with no extra EC roundtrip per request.
- [ ] A friend added via `POST /friends` (either form) appears in the desktop GUI's list and survives an `amuled` restart (it is persisted to `emfriends.met`).
- [ ] `PATCH … {"friend_slot":true}` is reflected in the desktop context menu's checkbox, and setting it on a second friend clears the first.
- [ ] Removing a friend that is currently connected clears the live client's slot and `GET /clients/{ecid}` then reports `is_friend: false`.
- [ ] Browsing an **offline** friend returns a `search_id` and the results arrive under it.
- [ ] Against an `amuled` that predates the new sub-tags, every endpoint still works and `friend_slot` reads `false`.
- [ ] Unit tests for the new walker in `unittests/`, following the existing `ApplyGetUpdateTo*` tests.

## Out of scope

- `GET /api/v0/friends/{ecid}` — the list is small and carries every field; add it only if a client reports needing it.
- Chat / messaging — tracked separately (see the chat issue); this issue only covers the friends **list**.
- Persisting a friend's chat history.
