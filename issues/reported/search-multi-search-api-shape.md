# amuleapi: address every search by id in the path, and close the remaining multi-search gaps

## Summary

`amuleapi` already runs **several concurrent searches**: `POST /api/v0/search`
returns a daemon-allocated `search_id`, `m_state` keeps one slot per search
(`src/webapi/State.h:1348`), the refresher polls each active one independently
(`src/webapi/RefresherTick.cpp:181-290`), and both SSE events carry the
`search_id` they belong to (`src/webapi/EventDiff.cpp:567-688`). What the REST
surface still carries is the **single-search shape it grew out of**: the id is an
optional query/body parameter, and when it is omitted the request silently
resolves to a per-session "current search" — the most recently started one.

That default is the last piece of single-search thinking in the API, and it is
now pure liability:

- It duplicates every addressed path with an unaddressed one that means
  something different depending on which client asked and when.
- `POST /search/stop` with no body **and** no current search sends
  `EC_OP_SEARCH_STOP` with no `EC_TAG_SEARCH_ID` at all
  (`src/webapi/Api.cpp:8361-8370`) — the daemon then decides what "stop" means.
- It costs real state and real code: `m_current_search_id`, `ResolveSearchId()`,
  `CurrentSearchId()`, the `search_id: 0` sentinel, `ParseSearchIdParam`, and a
  duplicated "never evict the current search" carve-out in two functions.

On top of that, several things a multi-search consumer genuinely needs are
missing, all of them either already on the EC wire or already implemented and
merely undocumented:

- The Kad **"More results"** action has no route at all.
- A **browse** entry drops the peer it is listing (`EC_TAG_CLIENT`) and every
  browse result drops the shared folder it lives in
  (`EC_TAG_SEARCHFILE_DIRECTORY`) — the desktop's *Directories* column.
- A search's own **query string** is not on its results envelope.
- The results of a **finished** search are frozen forever, which silently breaks
  the Kad comments flow for search hits.
- The **`related::` keyword search** works over REST today and is documented
  nowhere.

This issue does all of it in one pass: move the id into the path, delete the
"current search" concept, and fill the gaps. `/api/v0/` is experimental and has
no consumers outside this repository, so the shape changes land in place rather
than waiting for a `v1`.

## Current state

| Piece | Location |
|---|---|
| Route table | `src/webapi/Api.cpp:1060-1125` |
| `GET /search` (list, direct `EC_OP_SEARCH_LIST` roundtrip) | `src/webapi/Api.cpp:5751-5791` |
| `POST /search` (start) | `src/webapi/Api.cpp:8135-8305` |
| `GET /search/results` (`?search_id=`) | `src/webapi/Api.cpp:5615-5715` |
| `POST /search/stop` (body `search_id` + `close`) | `src/webapi/Api.cpp:8311-8402` |
| `POST /search/results/{hash}/download` | `src/webapi/Api.cpp:8404-8510` |
| `GET`/`POST /search/results/{hash}/comments` | `src/webapi/Api.cpp:8517-8625` |
| Optional-id parsing | `src/webapi/Api.cpp:5142-5165` (`SearchIdParam` / `ParseSearchIdParam`) |
| Cross-client discovery on a cache miss | `src/webapi/Api.cpp:5720-5741` (`DiscoverSearchIfHeldByCore`) |
| Per-search slots, "current" pointer, 64-slot cap | `src/webapi/State.h:648-660`, `:1345-1363` |
| `ResolveSearchId` / `CurrentSearchId` / eviction carve-out | `src/webapi/State.cpp:122-152`, `:155-158`, `:194-265`, `:273-289` |
| Refresher: poll each **active** search | `src/webapi/RefresherTick.cpp:196-290` |
| Lifecycle → `active`/`complete`/`percent` | `src/webapi/Refresher.cpp:2076-2099` (`AdvanceSearchProgress`) |
| Per-search SSE diffing | `src/webapi/EventDiff.cpp:567-688`, `src/webapi/EventDiff.h:76-88` |
| Result → JSON, and the fields read off the wire | `src/webapi/Api.cpp:5311-5400` (`WriteSearchObject`), `src/webapi/Refresher.cpp:1930-2045` (`ApplySearchFull`), `src/webapi/State.h:553-617` |
| Docs | `docs/api/REFERENCE.md:95-102` (index), `:221` (sort table), `:2052-2219` (Search section), `:1110-1133` (peer browse); `docs/api/EVENTS.md:35-43`, `:161`, `:423-469` |
| Tests | `unittests/curl-tests/amuleapi/19-search.sh` (82 hits), `07-read-stats-and-search-results.sh:174`, `10-refresher-lazy-ondemand.sh:192`, `20-etag-conditional-get.sh:247,257`, `22-sse-diff-emission.sh:267`, `26-rfc-followup-endpoints.sh:459` |

Relevant core facts, all already in place — **no core or EC changes are needed
by this issue**:

- The daemon allocates a globally-unique id per `EC_OP_SEARCH_START` and
  addresses results / progress / stop / more by `EC_TAG_SEARCH_ID`.
- `EC_OP_SEARCH_LIST` enumerates every search the core holds regardless of who
  started it, and **browse ("View Files") tabs are included**, carrying the peer
  as `EC_TAG_CLIENT` (`src/ExternalConn.cpp:2866-2890`;
  `src/SearchList.cpp:1225-1234` registers a browse under the peer's name).
- Searches are persisted across restarts (`MAX_STORED_SEARCHES = 20`,
  `src/SearchList.h:459`), so `GET /search` can list searches from a previous
  daemon run. EC-started searches also ride a 20-entry LRU
  (`src/ExternalConn.cpp:2554`); an evicted one comes back as
  `EC_TAG_SEARCH_EXPIRED`, which the refresher already retires as finished.
- `EC_OP_SEARCH_REQUEST_MORE = 0x5F`
  (`src/libs/ec/abstracts/ECCodes.abstract:171`) is handled per id at
  `src/ExternalConn.cpp:3101-3119`.

## Requested change — part 1: the routes

Every search-scoped operation takes the id in the path. Nothing resolves to an
implicit search.

| Verb + path | Replaces | Notes |
|---|---|---|
| `GET /api/v0/search` | unchanged | list every search the daemon holds |
| `POST /api/v0/search` | unchanged | start one → `202` + `search_id` |
| `GET /api/v0/search/{id}/results` | `GET /search/results?search_id=` | id **required** |
| `POST /api/v0/search/{id}/stop` | `POST /search/stop` | stop, keep results |
| `POST /api/v0/search/{id}/more` | — (**new**) | widen a running Kad search |
| `DELETE /api/v0/search/{id}` | `POST /search/stop {"close":true}` | stop **and** free |
| `POST /api/v0/search/results/{hash}/download` | unchanged | |
| `GET`/`POST /api/v0/search/results/{hash}/comments` | unchanged | |

Retired outright: `GET /api/v0/search/results` and `POST /api/v0/search/stop`,
including their `search_id` query/body parameters and the `search_id: 0`
sentinel.

The two `{hash}` routes stay exactly where they are. They are **deliberately
search-agnostic**: the daemon resolves a download by hash against its whole
search list, and a Kad note fetched for a hash is fanned out to every result
carrying it, which is why the lookup walks all slots
(`src/webapi/State.cpp:181-192`). Nesting them under `{id}` would advertise a
scoping that does not exist.

**Routing requirements** (`src/webapi/Api.cpp:1060-1125`):

- `{id}` must be validated as a non-negative decimal integer; `0` and
  non-numeric segments are `400 bad_request`, never a fallback.
- The literal `/api/v0/search/results/{hash}/…` patterns must be matched
  **before** the `{id}` patterns. They cannot collide (different segment
  counts, and `{id}` is numeric) but the order makes that independent of the
  matcher's internals.
- `HEAD` keeps working wherever `GET` does (`GET /search`,
  `GET /search/{id}/results`, `GET /search/results/{hash}/comments`), as the
  current handlers already allow — the ETag/conditional-GET path depends on it.
- `405` for any other verb on each path, with the message naming the allowed
  ones, as the current handlers do.

### `GET /api/v0/search/{id}/results`

**Auth:** `GUEST`, unchanged from `GET /search/results` today
(`src/webapi/Api.cpp:5617-5619` — reading results is not an admin action; only
starting, stopping, freeing and widening a search are). Same response body as today, plus `query` (see part 2), and
still accepting `limit` / `offset` / `sort` (`name`, `size`, `sources`,
`rating`) / `order`. Keep `search_id` in the body even though it is now in the
path — clients key their tabs on it and it costs nothing.

Keep the existing on-miss discovery: an id this process never started is looked
up once via `EC_OP_SEARCH_LIST` and, if the daemon holds it, seeded as a live
slot before answering (`src/webapi/Api.cpp:5635-5648`). This is what lets a UI
adopt a search started by `amulegui`, the monolithic GUI, or a previous
`amuleapi` run.

```sh
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://$HOST/api/v0/search/42/results?sort=sources&order=desc&limit=50"
```

**Errors:** `400 bad_request` (bad `{id}`), `404 not_found` (no such search —
never started, freed, or expired), `405`, `503 ec_unavailable`.

### `POST /api/v0/search/{id}/stop`

**Auth:** `ADMIN`. No body. Sends `EC_OP_SEARCH_STOP` with
`EC_TAG_SEARCH_ID`, always. Results stay readable; siblings untouched.

**Response:** `200` → `{ "ok": true }`.
**Errors:** `400`, `404`, `405`, `503`.

### `DELETE /api/v0/search/{id}`

**Auth:** `ADMIN`. Sends `EC_OP_SEARCH_STOP` with `EC_TAG_SEARCH_ID` +
`EC_TAG_SEARCH_CLOSE`, then drops the local slot (`CState::CloseSearch`).
Afterwards `GET /api/v0/search/{id}/results` is a `404`.

**Response:** `204 No Content`.
**Errors:** `400`, `404`, `405`, `503`.

### `POST /api/v0/search/{id}/more` (new)

**Auth:** `ADMIN`. No body. This is the desktop **"More"** button
(`src/SearchDlg.cpp:1251-1277`): it re-asks already-queried Kad peers for a
wider result frontier (`KADEMLIA_FIND_VALUE_MORE`), capped at
`KADEMLIA_FIND_VALUE_MORE_REASKS` = 4 per search
(`src/kademlia/kademlia/Defines.h:60`).

Send `EC_OP_SEARCH_REQUEST_MORE` with `EC_TAG_SEARCH_ID`, mirroring
`CSearchListRem::RequestMoreResults` (`src/amule-remote-gui.cpp:3442-3457`).
The daemon replies with a plain ack (`EC_OP_MISC_DATA`) and logs the real
outcome itself, so this is fire-and-forget: `202 Accepted` → `{ "ok": true }`.

Kad-only, like the desktop button. amuleapi knows the kind from the slot, so
reject a non-Kad target with `400 bad_request` ("`more` applies to Kad searches
only") instead of forwarding a request the core turns into a silent no-op
(`CSearchManager::RequestMoreResults` returns false for a non-Kad id,
`src/SearchList.cpp:1253-1261`). A **finished** Kad search is also rejected with
`400` — the desktop greys the button out once the lifecycle completes
(`src/amule-remote-gui.cpp:3435-3440`).

```sh
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://$HOST/api/v0/search/42/more"
```

**Errors:** `400 bad_request` (bad `{id}`, non-Kad kind, or already finished),
`400 amuled_rejected`, `403 forbidden` (guest), `404 not_found`, `405`,
`503 ec_unavailable`.

## Requested change — part 2: the missing data

### `query` on a search's own envelope

A slot records only the search *kind* today (`MarkSearchStarted(id, kind)`), so
`GET /search/{id}/results` cannot say what was searched for, and a client that
adopted an id has to cross-reference `GET /search` for the string. Store the
query in `SearchSlot` and emit it:

- `POST /search` already has it — pass it into `MarkSearchStarted`.
- `DiscoverSearchIfHeldByCore` (`src/webapi/Api.cpp:5720-5741`) already reads
  the matching `EC_OP_SEARCH_LIST` entry — take `EC_TAG_SEARCH_NAME` from it and
  pass it into `MarkSearchDiscovered`.
- Add `"query": "..."` beside `search_id` in the results envelope (empty string
  when unknown, which can only happen for a slot seeded before its name was
  observed).

### `client_ecid` on a browse entry in `GET /api/v0/search`

`EC_OP_SEARCH_LIST` carries `EC_TAG_CLIENT` — the browsed peer's ecid — for
every browse entry (`src/ExternalConn.cpp:2876-2882`), and `HandleSearchList`
drops it (`src/webapi/Api.cpp:5766-5789`). A consumer therefore sees
`"kind": "browse"` with no way to tell **whose** share it is, which is exactly
what `amulegui` needs that tag for when it rebuilds a browse tab
(`src/amule-remote-gui.cpp:3736-3750`). For a browse, `query` is the peer's
name, not a query string — say so in the docs.

Emit `client_ecid` on entries that carry the tag, and omit it otherwise. The
`client_` prefix is deliberate and follows the API's own convention: an object
names *its own* EC handle without a type prefix (here `search_id`), while a
reference to a **different** kind of object carries the owner as a prefix
(`client_ecid`, `server_ecid`). So this key keeps its prefix regardless of what a
client object ends up calling its own handle:

```json
{
  "searches": [
    { "search_id": 42, "query": "ubuntu desktop iso", "kind": "global", "state": "finished" },
    { "search_id": 43, "query": "debian",             "kind": "kad",    "state": "running"  },
    { "search_id": 44, "query": "SomePeerNick", "kind": "browse", "state": "running", "client_ecid": 621 }
  ]
}
```

### `directory` on a browse result

A browse result carries the **shared folder it lives in** on the wire:
`EC_TAG_SEARCHFILE_DIRECTORY` (`0x0714`), emitted by the core for exactly the
results filed from a peer's shared-file list and for nothing else
(`src/ECSpecialCoreTags.cpp:548-558`), with a typed accessor already in libec
(`src/libs/ec/cpp/ECSpecialTags.h:700-705`, `CEC_SearchFile_Tag::GetBrowseSource`).
`ApplySearchFull` never reads it (`src/webapi/Refresher.cpp:1930-2067`), so
`webapi::SearchResult` has no field for it (`src/webapi/State.h:553-617`) and the
API cannot answer "which folder of this peer's share is this file in" — the
desktop's **Directories** column (`src/SearchListCtrl.cpp:168-172`), which is the
one browse-only column in that list.

- Add `directory` to `webapi::SearchResult` and read the tag in
  `ApplySearchFull`.
- Emit `"directory": "..."` on the result object, and on `children[]` entries for
  the same reason: the tag is per-result, and two copies of one file sitting in
  different folders of the same share get grouped under one parent, each showing
  its own folder exactly as it does on the desktop
  (`src/SearchListModel.cpp:307`).
- Omit it (or send `""`) for ordinary server/Kad hits, which never carry it —
  same rule the media object already follows.
- Add `directory` to the accepted `sort` keys for
  `GET /search/{id}/results` (`src/webapi/Api.cpp:5659-5680`), so a browse
  listing can be read folder by folder; the desktop sorts on it too
  (`src/SearchListCtrl.cpp:474`).

The two sibling tags `EC_TAG_SEARCHFILE_CLIENT_ID` / `_CLIENT_PORT` stay
unexposed: they identify the browsed peer, which the search itself already
identifies via the `client_ecid` above.

### Document the `related::` keyword search (docs only)

The desktop's **"Search related files (eD2k, local server)"** context-menu action
needs no endpoint and no opcode — the GUI just composes a magic keyword and
starts an ordinary local search (`src/SearchListCtrl.cpp:940-968`):

```sh
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"related::8b54a3c2...::0a1b2c3d...","type":"local"}' \
  "http://$HOST/api/v0/search"
```

So the feature already works over REST today and nobody knows, because
`docs/api/REFERENCE.md` never mentions it. Document it in the Search section:
the `related::` prefix, `::`-separated 32-char MD4 hashes (one or more, the
desktop passes every selected result), `type: "local"` — it is answered by the
connected ed2k server, so a server that does not implement related search simply
returns no hits, and it is not a Kad or global search.

### Finished searches must stop being frozen snapshots

`AdvanceSearchProgress` clears `active` when the daemon reports the search
finished (`src/webapi/Refresher.cpp:2080-2083`), and the refresher only walks
`ActiveSearchIds()` (`src/webapi/RefresherTick.cpp:197`). So once a search
finishes, its cached results never change again. Two user-visible consequences:

1. **The Kad comments flow for search hits is broken in the common case.**
   `POST /search/results/{hash}/comments` starts an asynchronous Kad NOTES
   lookup (up to ~45 s) whose results reach the API only through the
   per-search result poll. Started against a finished search — which is when a
   user actually reads a result list — `kad_comment_search_running` never turns
   on or off and `comments` stays empty forever.
2. A result downloaded from a finished search keeps reporting `status: "new"`
   and `already_have: false`, because those fields only refresh on a poll.

Fix: refresh a **non-active** slot on demand, coalesced by a short TTL, on the
paths that read its results. Add a per-slot timestamp to `SearchSlot` and a
helper such as `RefreshSearchIfStale(search_id)` that, when the slot is inactive
and its stamp is older than ~1 s, does one `EC_OP_SEARCH_RESULTS`
`EC_DETAIL_FULL` fetch (with the `EC_TAG_SEARCH_PARENT` grouping flag) and feeds
it through the existing `ApplySearchFull` (`src/webapi/Refresher.cpp:1930`) via
`CState::MutateSearch`. Call it from:

- `GET /api/v0/search/{id}/results`
- `GET`/`POST /api/v0/search/results/{hash}/comments` — these locate the result
  by hash across all slots, so have `FindSearchResultByHash` also report the
  owning `search_id` and refresh that slot before reading.

An active slot needs nothing: the tick already refreshes it every second. A
stamped TTL keeps a polling client from turning each GET into an EC roundtrip,
and matches the coalescing the other lazily-fetched endpoints use
(`src/webapi/TtlCache.h`). Anything genuinely new that the on-demand fetch pulls
in is picked up by the next diff pass as an ordinary `search_result_added`.

Note for the docs: refresh-on-read is the **only** mechanism for a finished
search, and there is deliberately no event to wait for — `comments_updated` is
emitted from the downloads diff loop only (`src/webapi/EventDiff.cpp:515-524`)
and never for a search hit. A client that starts a Kad notes lookup on a search
result therefore polls `GET /search/results/{hash}/comments` (or the results
list) while `kad_comment_search_running` is true. Say so where that flag is
documented, so nobody waits on a stream frame that will never come.

### `search_closed` SSE event

When a slot disappears — `DELETE /api/v0/search/{id}` from another client, the
64-slot cap evicting an old finished search, or an EC reset — subscribers get no
signal at all; the diff pass silently prunes its baseline at the end of the
search block in `src/webapi/EventDiff.cpp`. A consumer holding a tab per search
only finds out by getting a `404` on its next read, and with SSE live it may
never read again.

Emit `search_closed` from that existing prune loop, on the `search` channel:

```json
{ "search_id": 42 }
```

Note in the docs what it does **not** mean: a search the daemon evicted from its
own LRU is retired as `finished` and kept locally for late reads
(`src/webapi/RefresherTick.cpp:274-286`), so that case is a terminal
`search_progress`, not a `search_closed`.

## What gets deleted

- `m_current_search_id` and `ResolveSearchId()` (`src/webapi/State.h:1352`,
  `:1363`) — every read/write path takes a concrete id.
- `CState::CurrentSearchId()` (`src/webapi/State.h:1195`,
  `src/webapi/State.cpp:155-158`) and both call sites
  (`src/webapi/Api.cpp:5649`, `:8361`).
- The `search_id: 0` sentinel and `SearchIdParam` / `ParseSearchIdParam`
  (`src/webapi/Api.cpp:5142-5165`).
- The "never evict the current search" carve-out, duplicated in
  `MarkSearchStarted` and `MarkSearchDiscovered`
  (`src/webapi/State.cpp:213-227`, `:250-264`) — with no current pointer the
  rule is simply "evict the oldest slot that is not active".
- The `m_current_search_id` reset in `CloseSearch` and in the state reset
  (`src/webapi/State.cpp:281-289`, `:610`).
- The no-body / no-id branch of `POST /search/stop`, which sent
  `EC_OP_SEARCH_STOP` with no `EC_TAG_SEARCH_ID`
  (`src/webapi/Api.cpp:8361-8370`).
- Every doc paragraph explaining what "the current search" is
  (`docs/api/REFERENCE.md:2081`, `:2107-2111`, `:2165-2173`).

`MarkSearchStarted` and `MarkSearchDiscovered` otherwise keep their distinct
jobs — the first resets a slot and bumps its generation, the second seeds a slot
for a search this process did not start — but neither has a "current" side
effect any more.

## Implementation checklist

**amuleapi (`src/webapi/`)**
- [ ] `Api.cpp:1060-1125` — new route table: `/search`, `/search/{id}/results`,
      `/search/{id}/stop`, `/search/{id}/more`, `DELETE /search/{id}`, with the
      two literal `/search/results/{hash}/…` patterns matched first and numeric
      `{id}` validation.
- [ ] `Api.h` / `Api.cpp` — `HandleSearchResults`, `HandleSearchStop` take a
      resolved `search_id`; add `HandleSearchClose` and `HandleSearchMore`;
      delete `SearchIdParam` / `ParseSearchIdParam`.
- [ ] `Api.cpp` — `HandleSearchList` emits `client_ecid` when the entry carries
      `EC_TAG_CLIENT`.
- [ ] `Api.cpp` — results envelope gains `query`; `DiscoverSearchIfHeldByCore`
      forwards `EC_TAG_SEARCH_NAME`.
- [ ] `Refresher.cpp:1930-2067` / `State.h:553-617` / `Api.cpp:5311-5400` —
      `SearchResult` gains `directory`, read from `EC_TAG_SEARCHFILE_DIRECTORY`;
      `WriteSearchObject` emits it on the result and on each `children[]` entry.
- [ ] `Api.cpp:5659-5680` — `directory` added to the `sort` comparators for
      `GET /search/{id}/results`.
- [ ] `EventDiff.cpp` — `directory` added to the `search_result_added` payload
      (result and `children[]`), which must stay byte-for-byte identical to a
      results-list entry.
- [ ] `State.h` / `State.cpp` — `SearchSlot` gains `query` and a
      last-fetch stamp; `MarkSearchStarted` / `MarkSearchDiscovered` take the
      query; `FindSearchResultByHash` reports the owning id; delete
      `CurrentSearchId` / `ResolveSearchId` / `m_current_search_id` and simplify
      the eviction loops.
- [ ] `Api.cpp` (or a small helper shared with `RefresherTick.cpp`) —
      `RefreshSearchIfStale(search_id)` for inactive slots, wired into the
      results GET and both comments handlers.
- [ ] `EventDiff.cpp` / `EventDiff.h` — publish `search_closed` from the prune
      loop that already computes vanished ids.
- [ ] No core, EC or preference changes.

**Docs (`docs/api/`)**
- [ ] `REFERENCE.md:95-102` — index entries for the new paths, `/search/{id}/more`
      added, `/search/results` and `/search/stop` removed.
- [ ] `REFERENCE.md:221` — sort table row renamed to `GET /search/{id}/results`.
- [ ] `REFERENCE.md:2052-2219` — rewrite the Search section against the new
      shape: no "current search" anywhere, `query`, `client_ecid` and
      `directory` documented (the last two browse-only), `more` documented with
      its Kad-only + running-only constraints, `DELETE` replacing `close`.
- [ ] `REFERENCE.md:2052-2219` — a short **Related-files search** paragraph:
      `POST /search` with `type: "local"` and a
      `related::<md4>[::<md4>…]` query, answered by the connected ed2k server,
      no dedicated endpoint and no Kad/global equivalent.
- [ ] `REFERENCE.md:221` — `directory` added to the `GET /search/{id}/results`
      sort keys.
- [ ] `REFERENCE.md:1110-1133` — the peer-browse section points at
      `GET /search/{id}/results`, and notes that a browse also appears in
      `GET /search` with `kind: "browse"` and `client_ecid`.
- [ ] `REFERENCE.md` — document that the results of a finished search are
      refreshed on read, so a Kad comments lookup started after a search
      completes does surface.
- [ ] **Link sweep.** Renaming the sections renames their anchors, and a stale
      in-doc link is a silent dead end: repoint every reference to
      `#get-apiv0searchresults` (5 in `REFERENCE.md` — the index at `:98` plus
      `:2060`, `:2071`, `:2194`, and the sort table — and one in `EVENTS.md:447`)
      and to `#post-apiv0searchstop` (`:99`, `:2071`). Any endpoint whose docs
      tell the caller to poll a `search_id` it just returned — today
      `POST /clients/{ecid}/shared_files` — must point at
      `GET /search/{id}/results`; grep the docs for `search_id=` afterwards and
      expect no hits.
- [ ] `EVENTS.md:35-43`, `:161`, `:423-469` — add `search_closed` to the event
      list and the `search` channel section, and state what it is not.
- [ ] `EVENTS.md:447` — `search_result_added` gains `directory` in its
      field description, keeping the "byte-for-byte identical to a
      `/search/{id}/results` entry" claim true.

**Tests (`unittests/curl-tests/amuleapi/`)**
- [ ] `19-search.sh` — port all 82 references; drop the "no-id resolves to the
      current search" assertions (`:166-180`); add: `GET /search/results` → `404`
      (route gone), `POST /search/stop` → `404`, `{id}` = `0`/`abc` → `400`,
      `GET /search/{unknown}/results` → `404`, `DELETE /search/{id}` → `204`
      followed by `404` on its results, two concurrent searches each reading only
      their own hits, `POST /search/{id}/more` → `202` on a running Kad search and
      `400` on a global one, and `query` present on the results envelope.
- [ ] `07-read-stats-and-search-results.sh:174`,
      `10-refresher-lazy-ondemand.sh:192`,
      `20-etag-conditional-get.sh:247,257`, `22-sse-diff-emission.sh:267`,
      `26-rfc-followup-endpoints.sh:459` — updated to the new paths.
- [ ] A browse case: `POST /clients/{ecid}/shared_files`, then
      `GET /search/{id}/results` reporting `directory` on the returned files and
      `GET /search` reporting that id with `kind: "browse"` and its
      `client_ecid` (skipped when no peer is connected, like the existing
      peer-dependent assertions), plus `sort=directory` accepted.
- [ ] A comments-after-completion case: start a local search, wait for
      `finished`, `POST /search/results/{hash}/comments`, then poll
      `GET /search/results/{hash}/comments` and observe
      `kad_comment_search_running` flip on and back off (skipped when Kad is
      down, like the existing Kad-dependent assertions).

**Bundled web UI (`src/webapi/static/`) — keep it working, do not redesign it**

The shipped UI is the API's only consumer and it calls two of the retired paths:
`api.get("search/results")` (`static/js/views/search.js:86`) and
`api.post("search/stop")` (`:163`). The multi-tab redesign is a separate piece of
work, but this change must not ship a broken UI:
- [ ] `views/search.js` — keep the `search_id` returned by `POST /search`
      (`:152`) in component state and use `search/{id}/results` and
      `search/{id}/stop`; on mount, adopt the newest entry from `GET /search`
      instead of relying on the removed implicit default.
- [ ] `events.js:171-175` — the SSE handlers already receive `search_id`;
      ignoring frames for other ids is enough here (they currently overwrite one
      shared store key regardless of which search they belong to).

## Acceptance criteria

- [ ] No endpoint resolves to an implicit search: every search-scoped call names
      its id in the path, and `grep -rn "current_search\|ResolveSearchId\|CurrentSearchId" src/webapi`
      comes back empty.
- [ ] `GET /api/v0/search/results` and `POST /api/v0/search/stop` are gone
      (`404`), and `{id}` of `0` or a non-numeric segment is a `400`, never a
      fallback to some other search.
- [ ] Two searches started back to back can be read, stopped, and freed
      independently, in either order, with no interference; `DELETE` on one
      leaves the other readable.
- [ ] A search started by `amulegui` or the monolithic GUI is listed by
      `GET /api/v0/search`, readable at `GET /api/v0/search/{id}/results`,
      stoppable and freeable — including a browse entry, which reports
      `kind: "browse"` and the browsed peer's `client_ecid`.
- [ ] `POST /api/v0/search/{id}/more` widens a running Kad search (the daemon
      logs the reask) and returns `400` for a global/local search, a finished
      search, and an unknown id.
- [ ] After a search finishes: `POST /search/results/{hash}/comments` followed by
      polling `GET /search/results/{hash}/comments` shows
      `kad_comment_search_running` going `true` → `false` and any retrieved notes
      appearing, and a result downloaded from that search reports
      `status: "downloaded"` / `already_have: true` on the next read.
- [ ] A browse listing reports each file's remote folder in `directory`, and an
      ordinary server/Kad hit does not carry the field at all.
- [ ] Freeing a search delivers a `search_closed` event carrying its `search_id`
      to every SSE subscriber, while a search the daemon evicted from its own LRU
      still delivers a terminal `search_progress` with `state: "finished"`.
- [ ] Idle cost is unchanged: with no active search, a tick issues no
      search-related EC roundtrip, and reading a finished search's results
      repeatedly does not issue one per request.
- [ ] A reader of `docs/api/REFERENCE.md` alone can fire a related-files search
      without looking at the desktop source.
- [ ] `docs/api/REFERENCE.md` and `docs/api/EVENTS.md` describe only the new
      shape, and the whole `unittests/curl-tests/amuleapi/` suite passes against
      a live `amuled` + `amuleapi`.

## Out of scope

- The multi-tab Web UI itself. This issue only keeps the bundled UI functional
  on the new paths.
- Adding a result count or `percent` to `GET /api/v0/search` entries. A client
  restoring one view per search fetches each search's results anyway, which
  carries both, and the list endpoint is a single direct EC roundtrip that would
  otherwise have to be merged with local slot state.
- A `search_result_updated` / `search_result_removed` event pair. Results are
  add-only within a search, and the fields that do change on an existing hit
  (`status`, `already_have`, `comments`) are covered here by the on-read refresh.
- Moving `/search/results/{hash}/download` or
  `/search/results/{hash}/comments` under `{id}`: both are search-agnostic by
  design.
- Server-side per-search result filtering beyond the existing
  `limit`/`offset`/`sort`/`order`.
- A **destination-category parameter on `POST /search`**, mirroring the desktop
  search panel's *Category* dropdown (`ID_AUTOCATASSIGN`, `src/muuli_wdr.cpp:256-261`).
  That control is not a search parameter: `CSearchParams` has no category field
  (`src/SearchList.h:83-102`), nothing about it reaches the core with the query,
  and the only reader is `CSearchListCtrl::DownloadSelected`
  (`src/SearchListCtrl.cpp:1027-1036`), which uses it as the default category for
  the *download* call. `POST /search/results/{hash}/download` already takes
  `category`, so remembering a per-search default is a client-side concern.
- A **bulk "close every search"** route, the equivalent of the desktop's *Clear
  Search Results* button (`src/SearchDlg.cpp:1330-1339`: stop, then
  `DeleteAllPages()`, whose per-page handler calls
  `StopSearchById(id, /*close=*/true)`, `src/SearchDlg.cpp:813-824`). That is
  exactly one `DELETE /api/v0/search/{id}` per open search, and a bulk form would
  save no EC work at all — the core still needs one `EC_OP_SEARCH_STOP` per
  search — over a set the daemon caps at 20. The desktop's neighbouring *Reset
  Fields* button (`src/SearchDlg.cpp:1533-1551`) only clears form widgets and has
  no API surface by definition.
- Exposing `EC_TAG_SEARCHFILE_CLIENT_ID` / `_CLIENT_PORT` on a browse result.
  The browsed peer is already identified once per search by `client_ecid`.
- Any change to how `POST /api/v0/clients/{ecid}/shared_files` starts a browse.
  It already returns a `search_id` that this surface addresses like any other.
