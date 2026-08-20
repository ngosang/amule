# Web UI: API endpoints the bundled Web UI never calls

## Summary

`amuleapi` exposes **55 distinct route patterns** under `/api/v0` — counting
`/search/{id}/{action}` once, though it dispatches three actions (plus two
retired paths answered with a pointer to their replacement, the SSE stream at
`/api/v0/events`, the country flags and the static fallthrough). The Web UI in
`src/webapi/static/` consumes most of them, but **19 route+method combinations
across 13 paths are never called from any `.js` file**, and a further set of
**query parameters and body fields is silently ignored** even on the endpoints
the UI does use.

This document is an inventory, not a plan: what is unused, and what it would
buy the UI. `amuleweb` is deprecated and was not considered.

Method: every route in `CApiDispatcher::DispatchToHandler`
(`src/webapi/Api.cpp:757-1553`) cross-referenced against every
`api.get/post/patch/del` call site under `src/webapi/static/js/`. All API
traffic goes through `js/api.js` (`fetch` at `api.js:83`); the only other
network calls in the frontend are the SSE `EventSource` (`events.js:133`) and
the i18n bundle fetch (`i18n.js:36`), so the grep is exhaustive.

## Unused endpoints

### 1. `/api/v0/shared/directories` — all four methods

| Method | Handler | Admin | What it does |
|---|---|---|---|
| `GET` | `Api.cpp:8956` | no | the configured share roots — explicit + recursive, each flagged |
| `PUT` | `Api.cpp:9005` | yes | replace the whole set |
| `POST` | `Api.cpp:9055` | yes | add one directory |
| `DELETE ?path=` | `Api.cpp:9111` | yes | remove one directory |

The largest gap, and worse than "no UI at all": the Web UI *does* offer a share
list, through the wrong door. `views/preferences.js:101` renders the
`directories.shared` preference (`PrefsSchema.cpp:146`,
`EC_TAG_DIRECTORIES_SHARED`) as a textarea under Directories → Shared. That
preference is not the share configuration — it is the **derived union**
`shareddir_list`, and writing it through `PATCH /preferences` is lossy:

- **The recursive flag is lost.** The two intent lists are
  `shareddir_explicit_list` and `shareddir_recursive_list`
  (`ExternalConn.cpp:1645-1652`); the union flattens both into one flat list of
  paths with nothing marking which root was recursive.
- **Nothing is persisted.** The prefs apply path
  (`ECSpecialMuleTags.cpp:845-848`) clears and refills `shareddir_list` in
  memory and stops there — no `SaveSharedFolders()`, no update of the two
  intent files.
- **Nothing rescans.** The same block only calls `RequestReload()` when the
  *exclusion filter* changed (`ECSpecialMuleTags.cpp:885-887`); a changed share
  list triggers no re-walk.
- **The edit gets reverted.** `CPreferences::ReloadSharedFolders`
  (`Preferences.cpp:2627`) reconciles against `shareddir.dat` and rewrites all
  three files from the *intent* lists, which the prefs path never touched.
- **No validation.** Paths are pushed unchecked, so a typo becomes a silently
  dead share.

`PUT /shared/directories` is the correct door and does all five things right
(`Get_EC_Response_SetSharedDirs`, `ExternalConn.cpp:1739-1792`): it validates
each path server-side (the browser cannot stat the daemon's filesystem),
reports the rejects individually with a reason while still applying the ones
that passed (`EC_TAG_SHAREDDIR_REJECTED` + a numeric code, mapped to
`not_found` / `not_readable` at `Api.cpp:8941`), sets both intent lists,
refreshes the union so the next reconcile does not trim the new roots, calls
`SaveSharedFolders()` and then `RequestReload()` — the rescan is deferred to
the next `Process()` tick, so the reply means "accepted and saved", not
"rescanned".

`views/shared.js` lists the *files* the roots expanded into and offers no way
to see or edit the roots themselves.

**Would enable:** a "Shared directories" panel — list roots, mark them
recursive, add/remove, see per-path rejections — in Preferences or as a pane of
the Shared view. The `directories.shared` textarea should be **removed** in the
same change: it is a footgun, not a fallback.

### 2. `/api/v0/friends` — the whole friends surface, five methods

| Route | Method | Handler | Admin |
|---|---|---|---|
| `/friends` | `GET` | `Api.cpp:5684` | no |
| `/friends` | `POST` | `Api.cpp:5708` | yes |
| `/friends/{ecid}` | `PATCH` | `Api.cpp:5919` | yes |
| `/friends/{ecid}` | `DELETE` | `Api.cpp:5866` | yes |
| `/friends/{ecid}/shared_files` | `POST` | `Api.cpp:9610` | yes |

The frontend contains no occurrence of the word "friend" outside the
`friend_slot` status icon (`client-table.js:136`) and two unrelated preference
labels — no view, no nav entry, no i18n keys.

The surface is complete and cheap:

- `GET /friends` is served straight from the refresher snapshot (the friends
  list rides along with every `GET_UPDATE`, so it costs no EC roundtrip) and
  supports `?limit/offset/sort/order` with `name` and `online` comparators.
- Rows carry `ecid`, `name`, `user_hash`, `ip`, `port`, `client_ecid`,
  `online`, `friend_slot` (`Api.cpp:5016`) — joinable against `/clients` via
  `client_ecid`.
- `POST /friends` accepts either `{client_ecid}` (befriend a live peer) or
  `{ip, port, user_hash}` (add offline).
- `PATCH /friends/{ecid}` takes `{friend_slot: bool}` — the reserved upload
  slot, which only one friend can hold.
- **Live deltas already exist**: `EventDiff.cpp:695` publishes
  `friend_added`/`friend_updated`/`friend_removed`, and `friends` is a valid
  SSE channel (`Api.cpp:10418`). A Friends view could register with
  `data.register()` exactly like Downloads/Clients and need no polling.
- `POST /friends/{ecid}/shared_files` is the *more capable* browse of the two:
  a friend record carries a stored `ip:port`, so the daemon can build a client
  for it and browse a friend who is **not currently connected** — which
  `/clients/{ecid}/shared_files` cannot do (`Api.cpp:9616-9621`).

**Would enable:** the desktop's Friends list, with the live event stream it
already publishes into the void today.

### 3. `/api/v0/chats` and the two message-send aliases — the whole chat surface

| Route | Method | Handler | Admin |
|---|---|---|---|
| `/chats` | `GET` | `Api.cpp:5390` | no |
| `/chats/{peer}/messages` | `GET` | `Api.cpp:5425` | no |
| `/chats/{peer}/messages` | `POST` | `Api.cpp:5582` | yes |
| `/chats/{peer}` | `DELETE` | `Api.cpp:5640` | yes |
| `/friends/{ecid}/messages` | `POST` | `Api.cpp:5602` | yes |
| `/clients/{ecid}/messages` | `POST` | `Api.cpp:5621` | yes |

Peer keys are `<ip>:<port>`. Every route answers `503 ec_unsupported` when the
connected amuled does not serve chat (`m_app.IsServerChatActive()`), so a
consumer must handle that and hide the UI.

- `GET /chats` is served from the refresher snapshot, most-recently-active
  first, and supports `?limit/offset/sort/order` (`last_message_at`, `name`).
- `GET /chats/{peer}/messages` takes `?since_id=` — a monotonic cursor that
  never duplicates and never skips — and `?limit=`, which means the *last* n.
  It returns `total` and `last_msg_id` alongside the window.
- The three `POST` forms all take `{text}` (≤1024 bytes) and answer **202**:
  the core acknowledges it queued the message on the peer connection, not that
  the peer received it. `POST /chats/{peer}/messages` also *starts* a session
  for an unknown peer — no 404. `POST /friends/{ecid}/messages` is the form
  that reaches an **offline** friend, via the friend's stored `ip:port`.
- **Live deltas already exist**: `EventDiff.cpp:577,582` publish `chat_message`
  and `chat_session_closed`, on the `chats` channel (`Api.cpp:10428`). The
  `chat_message` payload carries the full message plus `peer`, `ip`, `port`,
  `name`, `client_ecid` and `friend_ecid`, so a chat window needs no polling at
  all.

The frontend has no `chats` call site and no chat view; the only chat-adjacent
strings are two message-filter preference labels.

**Would enable:** the desktop's Messages window — session list, per-peer
transcript, send, close — driven entirely by the SSE stream, plus "send a
message" actions on the Clients table and a future Friends view.

### 4. `GET /api/v0/downloads/{hash}/clients` and `GET /api/v0/shared/{hash}/clients`

Both served by `HandleFileClients` (`Api.cpp:3602`). The peers of one file, as
`/clients` rows plus three things the UI cannot compute:

- `role` — `"source"` / `"peer"` / `"both"` / `"none"`.
- `a4af` — **whether the row is an A4AF source of this file**, resolved against
  `file.download.a4af_sources` (`Api.cpp:3640-3655`). A pure A4AF peer has
  neither `download_file_hash` nor `upload_file_hash` equal to this hash.
- `?include_parts=true` — the per-row part bitmap for this file, direction-aware
  (download map for a source, upload map for a peer; a pure A4AF row has none).

The `FileClients` component (`client-table.js:191-206`) reimplements a strict
subset in the browser: it filters the global live `clients` store on
`download_file_hash === hash || upload_file_hash === hash`
(`client-table.js:196`). So the Clients tab of both detail panels
**silently omits every A4AF-only source**, and has no `role` column and no part
bitmaps.

**Would enable:** the A4AF rows in the Clients tab — which is also the
replacement for the retired `GET /downloads/{hash}/a4af`, so the A4AF action
buttons (`download-detail.js:63`) stop acting on something the user cannot see.
Note this is a one-shot fetch, not an SSE-backed store, so it needs its own
refresh cadence — or a hybrid that keeps the live store and fetches this
endpoint only for the `a4af`/`role`/`parts` overlay.

### 5. `GET /api/v0/known_clients` — the credit store

Handler `Api.cpp:5253`. Every peer the daemon has ever exchanged data with,
keyed by `user_hash`, carrying stored history rather than live transfer state:
`total_uploaded`, `total_downloaded`, `first_seen`, `last_seen`, `sessions`,
`name`, `ip`/`port`/`kad_port`, `country_code`, `software`/`version`,
`source_origin`, `obfuscation`, plus `online` to correlate with `/clients` by
`user_hash`. Answers `503 ec_unsupported` unless
`IsServerClientHistoryActive()` — the request is never sent blind, because a
daemon predating `EC_OP_GET_CLIENT_HISTORY` asserts instead of answering
(`Api.cpp:5259-5266`). Fetched once per process and then maintained by the
refresher. Supports `?limit/offset/sort/order`.

`views/clients.js` only shows live connections (the live `clients` store), so
this data is unreachable from the web.

**Would enable:** a "Known clients" tab mirroring the desktop's credit list —
who you have uploaded to / downloaded from historically, and the credit
standing that drives queue priority.

### 6. `GET /api/v0/clients/{ecid}` — single-peer detail

Handler `Api.cpp:5361`, writer `Api.cpp:2800`. A superset of the list row: the
full base field set plus eight detail-only fields — `user_id_hybrid`,
`high_id`, `server_ip`, `server_port`, `server_name`, `kad_port`, `is_friend`,
`dl_up_modifier`. `404` when the ecid is not in the current snapshot.

None of those eight appear anywhere in the frontend for a client:
`user_id_hybrid`, `kad_port`, `is_friend` and `dl_up_modifier` have no
occurrence at all, and every `high_id` / `server_ip` / `server_port` /
`server_name` hit (`app.js:312-314`, `networks.js:175-181,455,470`,
`searches.js:350-351`) reads the **`/status` ed2k object**, not a peer.
`client-table.js:136` shows `friend_slot` (the reserved upload
slot) but never `is_friend` (friends-list membership) — they are
different fields, and the one the UI cannot show is the one that says "this
peer is on my friends list".

**Would enable:** a detail panel on click in the Clients table, matching the
existing `download-detail.js` / `shared-detail.js` pattern.

## Ignored parameters on endpoints that *are* used

Not unused routes, but unused capability.

| Parameter | Endpoints | Status in the UI |
|---|---|---|
| `?limit` `?offset` `?sort` `?order` | **nine** list endpoints — `/downloads`, `/clients`, `/shared`, `/servers`, `/known_clients`, `/chats`, `/friends`, `/search/{id}/results`, `/downloads\|shared/{hash}/clients` — via `ParseListParams`, `Api.cpp:2999` | Never sent. See the note below: this is **not** a simple "wire it up". |
| `?filter=uploads\|downloads\|active` | `GET /clients` (`Api.cpp:3707`) | Never sent; `views/clients.js:34-35` filters client-side over the full live store. Same SSE constraint as pagination. Note the server's definition is stricter than the UI's: it tests `upload_state == "uploading"` / `download_state == "downloading"`, whereas `clients.js` uses the broader `isDown`/`isUp` predicates — so the two would not agree. |
| `?include_parts=true` | `/downloads\|shared/{hash}/clients` (`Api.cpp:3626`) | Moot — the endpoint itself is unused (see §4). |
| `?since_id=` `?limit=` | `GET /chats/{peer}/messages` (`Api.cpp:5452-5474`) | Moot — the endpoint itself is unused (see §3). |
| `?max_client_versions=N` | `GET /stats/tree` (`Api.cpp:6821`) | Never sent (`stats.js:78`), so the client-version breakdown of the stats tree stays at its default cap. |
| `?interval=N` | `GET /stats/graphs/{graph}` (`Api.cpp:6927`) | Never sent — `stats.js:62` and `networks.js:291` pass only `?width=`. Already tracked in `issues/issue-webui-graph-interval.md`, which also covers the discarded `session` object. |
| `?tail=N` | `GET /logs/serverinfo` (`ParseTailParam`, `Api.cpp:6555`; used at `7404`) | Never sent (`networks.js:380`) — the whole server-info log is transferred every refresh. It *is* sent on `/logs/amule` (`networks.js:347`). |
| `?channels=` | `GET /api/v0/events` (SSE, `Api.cpp:10344`) | Never sent: the UI subscribes to the whole bus (`events.js:133`) and compensates with a 500 ms publish throttle (`events.js:116-120`). But it already consumes **eight** of the nine channels — `downloads`/`servers`/`shared`/`clients` as resource deltas (`events.js:205-207`), plus `status_changed`, `log_appended`, the three `search_*` events and `comments_updated` (`events.js:156-191`) — so filtering would only drop `friends` and `chats`, both of which are idle until those views exist. A per-view filter (subscribe to the active tab's channels only) is the version that would actually pay; a static filter buys almost nothing. |
| `category` (body) | `POST /downloads` (`Api.cpp:4277`, field parsed at `4338`) | Never sent by the add-link bar (`app.js:164`, which sends only `{links}` or `{ed2k_link}`), so a link added there always lands in the default category. It *is* sent on `POST /search/results/{hash}/download` (`search.js:185-192`). |
| `client_ecid` (body) | `POST /downloads/{hash}/a4af` (`Api.cpp:4042-4064`) | Never sent (`download-detail.js:63` sends only `{action}`). It narrows `swap_this` from "every A4AF source of this file" to one source — which the UI could not offer anyway, since it cannot list the A4AF sources (see §4). |
| `?type=bearer` | `POST /auth/login` | Not used, correctly — the browser uses the session cookie; the bearer token is for external clients. |
| address-keyed aliases `/servers/{ip:port}` | `PATCH` / `DELETE` / `connect` | The UI always has the ECID. Not a gap. |

### Why server-side pagination is not a quick win

For the four list endpoints the UI reads through the live-data layer
(`/downloads`, `/shared`, `/clients`, `/servers` — and a future `/friends` or
`/chats`), sending `?limit/?offset` is not enough.

`events.js` seeds each collection once from its list endpoint (`seed()`,
`events.js:77`) and then applies SSE deltas to the resulting `Map`
**unconditionally** — `m.set(id, payload)` on `_added`/`_updated`,
`m.delete(id)` on `_removed` (`events.js:202-221`). Nothing scopes a delta to
the seeded window. Seed page 1 and the store immediately starts accumulating
rows from outside it as they update, so the client ends up holding an arbitrary
partial set that is neither the window it asked for nor the whole collection —
and `total` no longer describes what is in the store.

Making this work means either paginating the SSE contract too (a server
change), or switching the paginated views off the live layer onto explicit
fetch-per-page with their own refresh (losing live updates). Server-side
windowing is fully implemented and correct (`limit` capped at 500, stable sort
before slice, `total`/`offset`/`limit` on every response) — the blocker is on
the frontend's data model, and that is the actual work item.

Three of the nine are unaffected and could take the parameters today:
`/known_clients` and `/downloads|shared/{hash}/clients` are one-shot fetches
with no delta stream, and `/chats` has deltas but no seeded collection.
`/search/{id}/results` is polled per tab (`searches.js:106`), so it is nearly
as free.

### The SSE channel list is longer than the source says

Worth recording while `?channels=` is on the table, because a filter is only
safe if the channel names are right.

The prefix→channel mapping (`Api.cpp:10397-10429`) names nine channels:
`downloads`, `shared`, `servers`, `clients`, `friends`, `status`, `logs`,
`search`, `chats`. Two problems:

- **The doc-comment above it (`Api.cpp:10344-10356`) still lists only six**,
  omitting `friends`, `search` and `chats`.
- **A tenth channel exists by accident.** `comments_updated`
  (`EventDiff.cpp:663,672`) matches no branch of the mapping, so it falls
  through to `return prefix` and its channel is literally `comments`. That
  happens to read correctly only because the event is named in the plural;
  renaming it to `comment_updated` would silently move it to a `comment`
  channel and break any `?channels=comments` subscriber. The UI consumes this
  event (`events.js:189`), so it is a channel in practice, not a curiosity.

## Full route inventory

Every route in the dispatcher, in dispatch order. ✔ = called by the Web UI.

| Route | Methods | Used |
|---|---|---|
| `/api/v0/version` | GET | ✔ `app.js:117`, `about.js:22,28` |
| `/api/v0/version/check` | POST | ✔ `about.js:39` |
| `/api/v0/auth/login` | POST | ✔ `api.js:132` |
| `/api/v0/auth/logout` | POST | ✔ `api.js:137` |
| `/api/v0/auth/session` | GET | ✔ `api.js:138` |
| `/api/v0/auth/passwords` | GET / PATCH | ✔ `preferences.js:318,344` |
| `/api/v0/status` | GET | ✔ `events.js:125` (poll fallback; live via SSE `status_changed`) |
| `/api/v0/downloads` | GET | ✔ `downloads.js:47` (`?include_completed=1`) |
| | POST | ✔ `app.js:164` |
| | PATCH (bulk) | ✔ `downloads.js:119,123` |
| | DELETE (bulk) | ✔ `downloads.js:116` |
| `/api/v0/downloads/clear_completed` | POST | ✔ `downloads.js:127,130` |
| `/api/v0/clients` | GET | ✔ `client-table.js:119`, `clients.js` (live store) |
| `/api/v0/known_clients` | GET | ✘ **unused** |
| `/api/v0/clients/{ecid}` | GET | ✘ **unused** |
| `/api/v0/clients/{ecid}/shared_files` | POST | ✔ `searches.js:323` |
| `/api/v0/shared` | GET | ✔ `shared.js:39` |
| | PATCH (bulk) | ✔ `shared.js:65` |
| `/api/v0/shared/reload` | POST | ✔ `shared.js:103` |
| `/api/v0/shared/directories` | GET / PUT / POST / DELETE | ✘ **unused (all four)** |
| `/api/v0/servers` | GET | ✔ `networks.js:140`, `searches.js:348` |
| | POST | ✔ `networks.js:166` |
| `/api/v0/friends` | GET / POST | ✘ **unused (both)** |
| `/api/v0/friends/{ecid}/shared_files` | POST | ✘ **unused** |
| `/api/v0/friends/{ecid}` | PATCH / DELETE | ✘ **unused (both)** |
| `/api/v0/chats` | GET | ✘ **unused** |
| `/api/v0/chats/{peer}/messages` | GET / POST | ✘ **unused (both)** |
| `/api/v0/chats/{peer}` | DELETE | ✘ **unused** |
| `/api/v0/friends/{ecid}/messages` | POST | ✘ **unused** |
| `/api/v0/clients/{ecid}/messages` | POST | ✘ **unused** |
| `/api/v0/servers/update` | POST | ✔ `preferences.js:117` |
| `/api/v0/servers/{ecid}/connect` | POST | ✔ `networks.js:152` |
| `/api/v0/servers/{ecid}` | PATCH | ✔ `networks.js:170` |
| | DELETE | ✔ `networks.js:157` |
| `/api/v0/kad` | GET | ✔ `networks.js:488` |
| `/api/v0/networks/connect` | POST | ✔ `networks.js:113` |
| `/api/v0/networks/disconnect` | POST | ✔ `networks.js:113` |
| `/api/v0/kad/update` | POST | ✔ `preferences.js:130` |
| `/api/v0/kad/bootstrap` | POST | ✔ `networks.js:307` |
| `/api/v0/ipfilter/reload` | POST | ✔ `preferences.js:176` |
| `/api/v0/ipfilter/update` | POST | ✔ `preferences.js:180` |
| `/api/v0/shared/{hash}/verify` | POST | ✔ `shared-detail.js:77`, `shared.js:93` (bulk) |
| `/api/v0/shared/{hash}/clients` | GET | ✘ **unused** |
| `/api/v0/shared/{hash}` | GET | ✔ `shared-detail.js:53` |
| | PATCH | ✔ `shared.js:57` (priority), `components.js:217,259` (comment/rating, name) |
| `/api/v0/categories` | GET | ✔ `categories.js:29`, `downloads.js:43`, `search.js:51` |
| | POST | ✔ `categories.js:53` |
| `/api/v0/categories/{index}` | PATCH | ✔ `categories.js:52` |
| | DELETE | ✔ `categories.js:59` |
| `/api/v0/preferences` | GET / PATCH | ✔ `preferences.js:405,559`, `networks.js:444` — all 125 `PrefsSchema.cpp` rows are covered, across all 13 schema categories, plus the bespoke `remote_controls.webserver.guest_password` (`Api.cpp:7950-7975`, not a schema row) |
| `/api/v0/logs/amule` | GET | ✔ `networks.js:347` (`?tail=`) |
| | DELETE | ✔ `networks.js:355` |
| `/api/v0/logs/serverinfo` | GET | ✔ `networks.js:380` (no `?tail=`) |
| | DELETE | ✔ `networks.js:388` |
| `/api/v0/stats/tree` | GET | ✔ `stats.js:78` |
| `/api/v0/search` | GET | ✔ `searches.js:134` |
| | POST | ✔ `searches.js:304` (also `related::`) |
| `/api/v0/search/results/{hash}/download` | POST | ✔ `search.js:199,208` |
| `/api/v0/search/results/{hash}/comments` | GET | ✔ `search.js:376` |
| | POST (Kad notes lookup) | ✔ `search.js:391` |
| `/api/v0/search/results` | — | retired stub → `GET /search/{id}/results` |
| `/api/v0/search/stop` | — | retired stub → `POST /search/{id}/stop` |
| `/api/v0/search/{id}` | DELETE | ✔ `searches.js:391,403` |
| `/api/v0/search/{id}/results` | GET | ✔ `searches.js:106` |
| `/api/v0/search/{id}/stop` | POST | ✔ `searches.js:364` |
| `/api/v0/search/{id}/more` | POST | ✔ `searches.js:380` |
| `/api/v0/stats/graphs/{graph}` | GET | ✔ `stats.js:62` (`download`, `upload`, `connections`), `networks.js:291` (`kad`) — all four graph names |
| `/api/v0/downloads/{hash}/comments` | GET | ✔ `download-detail.js:230` |
| | POST (Kad notes lookup) | ✔ `download-detail.js:245` |
| `/api/v0/downloads/{hash}/filenames` | GET | ✔ `download-detail.js:274` |
| `/api/v0/downloads/{hash}/a4af` | POST | ✔ `download-detail.js:63` (`swap_this`, `swap_others`, `swap_this_auto`) |
| `/api/v0/downloads/{hash}/clients` | GET | ✘ **unused** |
| `/api/v0/downloads/{hash}` | GET | ✔ `download-detail.js:35` |
| | PATCH | ✔ `downloads.js:85-88,284`, `download-detail.js:285`, `components.js:217,259` |
| | DELETE | ✔ `downloads.js:93` |
| `/api/v0/events` (SSE, `App.cpp:484`) | GET | ✔ `events.js:133` |
| `/flags/{code}.png` | GET | ✔ `components.js:36` |
| static fallthrough | GET | ✔ the shell itself |

`GET /downloads/{hash}/a4af` was retired and answers `405`
(`Api.cpp:1471-1485`); A4AF sources are rows of `GET /downloads/{hash}/clients`
instead, and `a4af_auto` rides the download detail object. The `POST` half
stays.

`HEAD` is accepted wherever `GET` is and is never issued by the UI; it is not
counted as a gap.

## Suggested priority

1. **`/shared/directories`** — not merely a missing feature: the Web UI
   currently exposes an *incorrect* share editor via the `directories.shared`
   preference, which loses the recursive flag, validates nothing, persists
   nothing and gets reverted by the next reconcile. Replace it with this route.
2. **`GET /downloads/{hash}/clients`** — the A4AF swap buttons already ship in
   `download-detail.js`, acting on sources the user cannot see. This is the
   route that shows them, and it also brings `role` and part bitmaps.
3. **`/friends` (five methods)** — a whole desktop feature missing, with its
   SSE deltas already being published and dropped on the floor.
4. **`/chats` (six routes)** — the other whole desktop feature missing, also
   with its SSE deltas already published and dropped. Bigger than Friends (a
   transcript view, not a table) and gated on `IsServerChatActive()`, so it
   needs a capability check the other views don't.
5. **`GET /clients/{ecid}` + `GET /known_clients`** — peer detail panel and the
   credit list.
6. **Small ignored parameters** — `?tail` on `/logs/serverinfo`,
   `?max_client_versions` on `/stats/tree`, `category` on `POST /downloads`.
   Each is a one-line change. (`?interval` on the graphs is tracked separately
   in `issues/issue-webui-graph-interval.md`.)
7. **`?channels=` on the SSE stream** — a traffic/wakeup optimisation, no new
   feature, and a small one: the UI already consumes eight of the nine
   channels, so only a *per-view* filter would pay. Low priority.
8. **Server-side pagination** — genuinely useful at scale, but it is a
   live-data-layer redesign, not a parameter to start sending. See the note
   above.
