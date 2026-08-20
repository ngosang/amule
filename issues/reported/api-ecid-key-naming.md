# Give EC handles one key name across the API: `client_ecid` → `ecid`, `client_name` → `name`

## Summary

`amuleapi` exposes the same kind of value — an **ECID**, the short-lived handle
`amuled` assigns to an object over the External Connection protocol — under two
different key names depending on which endpoint you ask:

| Endpoint | Key |
|---|---|
| `GET /api/v0/servers` | `ecid` |
| `GET /api/v0/search/results` → `children[]` | `ecid` |
| `POST /api/v0/search/results/{hash}/download` (body) | `ecid` |
| `GET /api/v0/clients`, `GET /api/v0/clients/{ecid}` | **`client_ecid`** |
| SSE `client_removed` | **`client_ecid`** |

The URL segment is `{ecid}` in every route that takes one
(`/servers/{ecid}`, `/clients/{ecid}`, `/clients/{ecid}/shared_files`), so the
client object is the odd one out against the API's own paths as well as against
its sibling collections.

The same object carries a second redundant self-prefix: **`client_name`** inside
a client object, where every other collection spells its display name `name`
(`/servers[].name`, `/downloads[].name`, `/shared[].name`,
`/search/results[].name`).

The API has in fact already made this choice once, in the one place it had to:
both `GET /clients` and `GET /known_clients` accept **`sort=name`**
(`src/webapi/Api.cpp:3025-3028`, `:4468-4471`), because `sort=client_name` would
have been absurd. So a consumer today sorts by `name` and then reads the value
out of `client_name`.

This issue picks one rule, applies it, and writes it down so future collections
do not have to re-litigate it. `/api/v0/` is experimental and has no consumers
outside this repository yet, so the rename lands in place rather than waiting
for a `v1`.

## The rule

> **An object names its own EC handle `ecid`. A reference to a *different*
> kind of object's handle carries the owner as a prefix (`client_ecid`,
> `server_ecid`, …), and an array of foreign handles says so in its key name.**

This is the ordinary REST convention — a resource's own identifier is not
prefixed with its own type, foreign keys are — and it keeps the prefix
meaningful: seeing `client_ecid` inside, say, a friend or a transfer object
immediately tells you it points *out* of that object, which is exactly the case
where a reader needs the hint.

## Current state

| Piece | Location |
|---|---|
| Client object writer (`client_ecid`, `client_name`) | `src/webapi/Api.cpp:2231-2235` — `WriteClientBaseFields`, shared by `GET /clients` and `GET /clients/{ecid}` |
| Known-client object writer (`client_name`) | `src/webapi/Api.cpp:2354-2361` — `WriteKnownClientObject` |
| Server object writer (`ecid`) | `src/webapi/Api.cpp:4258` — `WriteServerObject` |
| Search children writer (`ecid`) | `src/webapi/Api.cpp:5364` |
| Server mutation replies (`ecid`) | `src/webapi/Api.cpp:4686`, `:4738`, `:4977` |
| A4AF source array (bare ints, no key naming) | `src/webapi/Api.cpp:3294-3299` — `GET /downloads/{hash}/a4af` |
| SSE client payloads | `src/webapi/EventDiff.cpp:187` (`ToJson(const ClientSnapshot&)`), `:402` (`RemovedEcidPayload`) |
| Route captures (already `{ecid}` everywhere) | `src/webapi/Api.cpp:791-818` (clients), `:884-918` (servers) |
| Docs | `docs/api/REFERENCE.md` — 8 × `client_ecid`, 4 × `client_name`; `docs/api/EVENTS.md` — 3 × `client_ecid`, 1 × `client_name` |
| Bundled web UI (**breaks if not updated in the same change**) | `static/js/views/client-table.js:50,51,105,165,185`, `static/js/views/clients.js:37` |
| curl tests referencing the keys | `unittests/curl-tests/amuleapi/10-refresher-lazy-ondemand.sh`, `26-rfc-followup-endpoints.sh`, `33-known-clients.sh` |

## Requested change

### `GET /api/v0/clients` and `GET /api/v0/clients/{ecid}`

```diff
 {
-  "client_ecid": 4382,
-  "client_name": "AnonymousPeer",
+  "ecid": 4382,
+  "name": "AnonymousPeer",
   "user_hash": "1f2e3a...",
   "ip": "203.0.113.42",
   "…": "…"
 }
```

Nothing else in the object moves. The detail endpoint shares the same writer, so
it inherits the change.

### `GET /api/v0/known_clients`

```diff
 {
   "user_hash": "a1b2c3d4e5060e708090a0b0c0d06f00",
-  "client_name": "example-peer",
+  "name": "example-peer",
   "…": "…"
 }
```

Note this collection is keyed by `user_hash`, not by an ECID — it has no `ecid`
field and gains none. Only the name is renamed, so the two client collections
spell their display name the same way. Its `sort=name` parameter already uses
the short spelling and is unaffected.

### SSE `client_added` / `client_updated` / `client_removed`

The added/updated payloads mirror the REST object, so they follow it. The
removed payload changes key:

```diff
-{ "client_ecid": 4382 }
+{ "ecid": 4382 }
```

which also makes it identical in shape to `server_removed`, its sibling for the
other ECID-keyed collection.

### `GET /api/v0/downloads/{hash}/a4af`

The array holds **foreign** handles (client ECIDs) under a key that does not say
so, which is the one place the rule above has something to say beyond the
prefix question:

```diff
-{ "a4af_auto": false, "sources": [ 1234, 5678 ] }
+{ "a4af_auto": false, "source_ecids": [ 1234, 5678 ] }
```

The values are unchanged; the key now states what the integers are, so a reader
does not have to reach for the prose to learn they join against `/clients`. Not
read by the bundled web UI.

### Unchanged, deliberately

| Key | Why it stays |
|---|---|
| `/servers[].ecid`, search `children[].ecid`, the `ecid` field in the `POST /search/results/{hash}/download` body | Already the target spelling. |
| `{ecid}` path segments | Already uniform across every route. |
| `ecid` in the server mutation replies (`{"ok": true, "ecid": 1}`) | The reply identifies the server the request addressed; already correct. |
| `user_hash` | A different identity with different lifetime guarantees (stable across daemon restarts). Nothing here touches it, and the docs' advice to prefer it for durable references stands. |
| `/downloads[].hash`, `/shared[].hash` | Hash-keyed collections, unrelated to ECIDs. |

## Why not the other direction

Prefixing everything instead (`server_ecid`, `result_ecid`, …) would also be
consistent, and it is the wrong trade: it makes every object repeat its own type
in its own field names, it forces the same repetition on every future
collection, and it leaves the prefix carrying no information — at which point a
reader can no longer tell a self-handle from a foreign one, which is the only
distinction worth encoding.

## Implementation checklist

**amuleapi (`src/webapi/`)**
- [ ] `Api.cpp` — `WriteClientBaseFields`: `client_ecid` → `ecid`,
      `client_name` → `name`.
- [ ] `Api.cpp` — `WriteKnownClientObject`: `client_name` → `name`.
- [ ] `Api.cpp` — `GET /downloads/{hash}/a4af`: `sources` → `source_ecids`.
- [ ] `EventDiff.cpp` — `ToJson(const ClientSnapshot&)` and the client
      `RemovedEcidPayload` overload; the latter can then share the servers'
      `{"ecid": N}` shape instead of having its own.

**Docs**
- [ ] `docs/api/REFERENCE.md` — `GET /clients`, `GET /clients/{ecid}`,
      `GET /known_clients`, `GET/POST /downloads/{hash}/a4af`: rename in the
      samples and the field tables, including the cross-references in the prose
      ("joinable against `GET /clients`'s …").
- [ ] `docs/api/EVENTS.md` — the three `client_*` events.
- [ ] `docs/api/REFERENCE.md` — add the rule to the response-model section, so
      the next collection inherits it instead of choosing again.

**Web UI (`src/webapi/static`) — REQUIRED in the same change, not a follow-up**

The bundled frontend reads both keys; shipping the API rename without it leaves
the Clients view blank and its SSE row-keying broken.
- [ ] `views/client-table.js` — the name column (`:50-51`), the store
      registration `id: "client_ecid"` (`:105`), the `rowKey` (`:165`) and the
      text filter (`:185`).
- [ ] `views/clients.js:37` — the text filter.
- [ ] No i18n changes: the visible strings are unaffected.

**Tests**
- [ ] `unittests/curl-tests/amuleapi/10-refresher-lazy-ondemand.sh`,
      `26-rfc-followup-endpoints.sh`, `33-known-clients.sh` — update the jq
      paths.
- [ ] `unittests/tests/EventDiffTest.cpp` — any assertion on the client payload
      keys.
- [ ] Add one assertion that no response body anywhere still emits
      `client_ecid` / `client_name`, so the rename cannot half-land.

## Acceptance criteria

- [ ] Every ECID-carrying object names its own handle `ecid`; `client_ecid`
      appears nowhere in `src/`, `docs/`, `unittests/` or `static/`.
- [ ] Every collection names its display name `name`; `client_name` appears
      nowhere in the same set.
- [ ] `client_removed` and `server_removed` carry byte-identical payload shapes.
- [ ] `GET /downloads/{hash}/a4af` returns `source_ecids`, and the docs no longer
      need prose to explain what the integers are.
- [ ] The bundled web UI's Clients view (list, sorting, filtering, live SSE
      updates and the detail drawer) works exactly as before the rename.
- [ ] `docs/api/REFERENCE.md` states the self-handle-vs-foreign-handle rule once,
      in the shared response-model section.

## Out of scope

- Replacing ECIDs with a stable identifier. They are `amuled`'s own per-process
  handles and are documented as not surviving a daemon restart; that trade-off
  is deliberate and unchanged here.
- Renaming `user_hash`, or changing which field a detail route is keyed by.
- Any change to the values themselves, to route paths, or to pagination and
  sorting parameters.
