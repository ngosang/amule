# amuleapi — REST endpoint inventory (extracted from source)

Generated from `src/webapi` at commit `c80a7627a` by the scripts described in
[How this document was produced](#how-this-document-was-produced). Every route,
query parameter, body field, response key and error below was lifted out of the
C++ sources — `src/webapi/Api.cpp`, `App.cpp`, `HttpServer.cpp`,
`SearchJson.cpp`, `PrefsSchema.cpp` — and not from `docs/api/REFERENCE.md`,
which is known to drift.

**91 endpoint sections** over **61 route blocks** in `DispatchToHandler`, plus the SSE, static-file, country-flag and CORS-preflight paths that live outside it.

## Contents

1. [Transport, routing and shared behaviour](#1-transport-routing-and-shared-behaviour)
2. [Authentication and authorization](#2-authentication-and-authorization)
3. [Shared envelopes](#3-shared-envelopes)
4. [Error catalog](#4-error-catalog)
5. [Endpoints](#5-endpoints)
    - [System](#system)
        - [GET, HEAD /api/v0/health](#get-head-apiv0health)
        - [GET, HEAD /api/v0/version](#get-head-apiv0version)
        - [POST /api/v0/version/check](#post-apiv0versioncheck)
    - [Authentication](#authentication)
        - [POST /api/v0/auth/login](#post-apiv0authlogin)
        - [POST /api/v0/auth/logout](#post-apiv0authlogout)
        - [GET, HEAD /api/v0/auth/session](#get-head-apiv0authsession)
        - [GET, HEAD /api/v0/auth/passwords](#get-head-apiv0authpasswords)
        - [PATCH /api/v0/auth/passwords](#patch-apiv0authpasswords)
    - [Status and networks](#status-and-networks)
        - [GET, HEAD /api/v0/status](#get-head-apiv0status)
        - [GET, HEAD /api/v0/kad](#get-head-apiv0kad)
        - [POST /api/v0/networks/connect](#post-apiv0networksconnect)
        - [POST /api/v0/networks/disconnect](#post-apiv0networksdisconnect)
        - [POST /api/v0/kad/bootstrap](#post-apiv0kadbootstrap)
        - [POST /api/v0/kad/update](#post-apiv0kadupdate)
        - [POST /api/v0/ipfilter/reload](#post-apiv0ipfilterreload)
        - [POST /api/v0/ipfilter/update](#post-apiv0ipfilterupdate)
    - [Downloads](#downloads)
        - [GET, HEAD /api/v0/downloads](#get-head-apiv0downloads)
        - [POST /api/v0/downloads](#post-apiv0downloads)
        - [PATCH /api/v0/downloads](#patch-apiv0downloads)
        - [DELETE /api/v0/downloads](#delete-apiv0downloads)
        - [POST /api/v0/downloads_clear_completed](#post-apiv0downloads_clear_completed)
        - [GET, HEAD /api/v0/downloads/{hash}](#get-head-apiv0downloadshash)
        - [PATCH /api/v0/downloads/{hash}](#patch-apiv0downloadshash)
        - [DELETE /api/v0/downloads/{hash}](#delete-apiv0downloadshash)
        - [GET, HEAD /api/v0/downloads/{hash}/comments](#get-head-apiv0downloadshashcomments)
        - [POST /api/v0/downloads/{hash}/comments](#post-apiv0downloadshashcomments)
        - [GET, HEAD /api/v0/downloads/{hash}/filenames](#get-head-apiv0downloadshashfilenames)
        - [GET, HEAD /api/v0/downloads/{hash}/clients](#get-head-apiv0downloadshashclients)
        - [POST /api/v0/downloads/{hash}/a4af](#post-apiv0downloadshasha4af)
    - [Clients (peers)](#clients-peers)
        - [GET, HEAD /api/v0/clients](#get-head-apiv0clients)
        - [GET, HEAD /api/v0/clients/{ecid}](#get-head-apiv0clientsecid)
        - [POST /api/v0/clients/{ecid}/shared_files](#post-apiv0clientsecidshared_files)
        - [POST /api/v0/clients/{ecid}/messages](#post-apiv0clientsecidmessages)
    - [Known clients (credit store)](#known-clients-credit-store)
        - [GET, HEAD /api/v0/known_clients](#get-head-apiv0known_clients)
    - [Shared files](#shared-files)
        - [GET, HEAD /api/v0/shared](#get-head-apiv0shared)
        - [PATCH /api/v0/shared](#patch-apiv0shared)
        - [POST /api/v0/shared_reload](#post-apiv0shared_reload)
        - [POST /api/v0/shared/media/refresh](#post-apiv0sharedmediarefresh)
        - [GET, HEAD /api/v0/share_directories](#get-head-apiv0share_directories)
        - [PUT /api/v0/share_directories](#put-apiv0share_directories)
        - [POST /api/v0/share_directories](#post-apiv0share_directories)
        - [DELETE /api/v0/share_directories](#delete-apiv0share_directories)
        - [GET, HEAD /api/v0/shared/{hash}](#get-head-apiv0sharedhash)
        - [PATCH /api/v0/shared/{hash}](#patch-apiv0sharedhash)
        - [POST /api/v0/shared/{hash}/verify](#post-apiv0sharedhashverify)
        - [POST /api/v0/shared/{hash}/media/refresh](#post-apiv0sharedhashmediarefresh)
        - [GET, HEAD /api/v0/shared/{hash}/clients](#get-head-apiv0sharedhashclients)
    - [Servers (ed2k server list)](#servers-ed2k-server-list)
        - [GET, HEAD /api/v0/servers](#get-head-apiv0servers)
        - [POST /api/v0/servers](#post-apiv0servers)
        - [POST /api/v0/servers_update](#post-apiv0servers_update)
        - [POST /api/v0/servers/{ecid}/connect](#post-apiv0serversecidconnect)
        - [POST /api/v0/servers/by-address/{address}/connect](#post-apiv0serversby-addressaddressconnect)
        - [PATCH /api/v0/servers/{ecid}](#patch-apiv0serversecid)
        - [DELETE /api/v0/servers/{ecid}](#delete-apiv0serversecid)
        - [PATCH, DELETE /api/v0/servers/by-address/{address}](#patch-delete-apiv0serversby-addressaddress)
    - [Friends](#friends)
        - [GET, HEAD /api/v0/friends](#get-head-apiv0friends)
        - [POST /api/v0/friends](#post-apiv0friends)
        - [PATCH /api/v0/friends/{ecid}](#patch-apiv0friendsecid)
        - [DELETE /api/v0/friends/{ecid}](#delete-apiv0friendsecid)
        - [POST /api/v0/friends/{ecid}/shared_files](#post-apiv0friendsecidshared_files)
        - [POST /api/v0/friends/{ecid}/messages](#post-apiv0friendsecidmessages)
    - [Chat](#chat)
        - [GET, HEAD /api/v0/chats](#get-head-apiv0chats)
        - [GET, HEAD /api/v0/chats/{peer}/messages](#get-head-apiv0chatspeermessages)
        - [POST /api/v0/chats/{peer}/messages](#post-apiv0chatspeermessages)
        - [DELETE /api/v0/chats/{peer}](#delete-apiv0chatspeer)
    - [Categories](#categories)
        - [GET, HEAD /api/v0/categories](#get-head-apiv0categories)
        - [POST /api/v0/categories](#post-apiv0categories)
        - [GET, HEAD /api/v0/categories/{index}](#get-head-apiv0categoriesindex)
        - [PATCH /api/v0/categories/{index}](#patch-apiv0categoriesindex)
        - [DELETE /api/v0/categories/{index}](#delete-apiv0categoriesindex)
    - [Preferences](#preferences)
        - [GET, HEAD /api/v0/preferences](#get-head-apiv0preferences)
        - [PATCH /api/v0/preferences](#patch-apiv0preferences)
    - [Logs](#logs)
        - [GET, HEAD /api/v0/logs/amule](#get-head-apiv0logsamule)
        - [DELETE /api/v0/logs/amule](#delete-apiv0logsamule)
        - [GET, HEAD /api/v0/logs/serverinfo](#get-head-apiv0logsserverinfo)
        - [DELETE /api/v0/logs/serverinfo](#delete-apiv0logsserverinfo)
    - [Statistics](#statistics)
        - [GET, HEAD /api/v0/stats/tree](#get-head-apiv0statstree)
        - [GET, HEAD /api/v0/stats/graphs/{graph}](#get-head-apiv0statsgraphsgraph)
    - [Search](#search)
        - [GET, HEAD /api/v0/search](#get-head-apiv0search)
        - [POST /api/v0/search](#post-apiv0search)
        - [GET, HEAD /api/v0/search/{id}/results](#get-head-apiv0searchidresults)
        - [POST /api/v0/search/{id}/stop](#post-apiv0searchidstop)
        - [POST /api/v0/search/{id}/more](#post-apiv0searchidmore)
        - [DELETE /api/v0/search/{id}](#delete-apiv0searchid)
        - [POST /api/v0/search/results/{hash}/download](#post-apiv0searchresultshashdownload)
        - [GET, HEAD /api/v0/search/results/{hash}/comments](#get-head-apiv0searchresultshashcomments)
        - [POST /api/v0/search/results/{hash}/comments](#post-apiv0searchresultshashcomments)
    - [Server-sent events](#server-sent-events)
        - [GET, HEAD /api/v0/events](#get-head-apiv0events)
    - [Static assets and country flags](#static-assets-and-country-flags)
        - [GET, HEAD /flags/{code}.png](#get-head-flagscodepng)
        - [GET, HEAD /{any non-/api/ path}](#get-head-any-non-api-path)
        - [OPTIONS <any path>](#options-any-path)
6. [Appendix A — preferences field table](#appendix-a--preferences-field-table)
7. [Appendix B — SSE event catalog](#appendix-b--sse-event-catalog)
8. [Appendix C — retired and shadowed paths](#appendix-c--retired-and-shadowed-paths)
9. [Appendix D — sortable fields per list endpoint](#appendix-d--sortable-fields-per-list-endpoint)
10. [How this document was produced](#how-this-document-was-produced)

---

## 1. Transport, routing and shared behaviour

| Item | Value | Source |
|---|---|---|
| Base URL | `http://<bind_address>:<port>` — `BindAddress` / `Port` in `amuleapi.conf`, overridable with `--bind-address` / `--http-port` | `TextShell`, `App.cpp` |
| API prefix | `/api/v0` — `api_version` is the literal `"v0"` | `HandleVersion`, `Api.cpp` |
| Content type | `application/json` on every API response except `/flags/*.png` (`image/png`) and static files | `Api.cpp` |
| HTTP version | HTTP/1.1, Boost.Beast, one `std::thread` for the io_context plus a worker pool for handlers | `HttpServer.cpp` |
| Request body limit | 1 MiB — over-size requests answer `413 payload_too_large`, then close | `HttpServer.cpp` (`body_limit`) |
| Request header limit | 16 KiB — over-size headers answer `431 headers_too_large`, then close | `HttpServer.cpp` (`header_limit`, `kMaxHeaderBytes`) |
| Read timeout | 10 s to finish sending the request → `408 request_timeout`, then close; a 20 s stream backstop behind it. Both disarmed once a handler starts, and for SSE | `HttpServer.cpp` (`m_request_timer`, `expires_after`) |
| Response compression | gzip when the client sends `Accept-Encoding: gzip`, the body is ≥ 256 B and its type is not already compressed. The `ETag` carries a coding suffix so the two representations validate apart | `HttpServer.cpp` (`WillCompressBody`) |
| Authenticated responses | `Cache-Control: private` + `Vary: Cookie`, stamped on every response whose caller presented a token or the session cookie (a handler that set its own `Cache-Control` is left alone) | `Api.cpp` (`Dispatch`) |
| Concurrent SSE sessions | 32; the 33rd gets `503 sessions_exhausted` + `Retry-After: 10` | `HttpServer.cpp` (`kMaxConcurrentStreamingSessions`) |
| Unhandled handler exception | `500` with code **`internal`** (note: handlers' own 500s use `internal_error`) | `HttpServer.cpp` (session dispatch `catch`) |

### Dispatch order

1. **SSE divert.** The streaming resolver runs *before* everything else: a
   `GET`/`HEAD` whose path (query stripped) is exactly `/api/v0/events` is
   handed to `PreflightEvents` + `DispatchEvents` and never reaches the
   normal dispatcher. A trailing slash (`/api/v0/events/`) does **not** match.
   (the `streaming_resolver` lambda in `App.cpp`)
2. **CORS preflight.** `OPTIONS` carrying `Access-Control-Request-Method`
   returns `204` with the CORS bundle, before auth and before routing.
   `OPTIONS` *without* that header falls through to normal routing and ends
   in that route's `405` (or `404`). See `CApiDispatcher::Dispatch`.
3. **Path validation.** `web_api_path::LooksMalicious(path)` rejects NUL,
   `%00`, `..` and `%2e%2e` with `400 bad_request`
   (`path contains a traversal/injection token`).
4. **Trailing-slash normalisation.** A path under `/api/` has one trailing
   slash stripped (`web_api_path::StripTrailingSlash`), so `/api/v0/status/`
   and `/api/v0/status` are the same resource. Deliberately confined to the
   API prefix: outside it a trailing slash means a directory.
5. **Route match**, in the literal source order of `DispatchToHandler`
   Literal paths are compared with `==`; captured
   paths go through `web_api_path::ParsePattern` / `Match`, which is
   *opaque-segment*: a capture matches any single segment, including an
   empty one and including `ip:port`.
6. **`/flags/` prefix** (outside `/api/v0`) → `ServeCountryFlag`.
7. **Static fallthrough**: any `GET`/`HEAD` whose path does not start with
   `/api/` → `ServeStaticFile`.
8. **`404 not_found` / `no such endpoint`** otherwise.

Routing consequences worth knowing:

- Literal routes are matched before the capture patterns that would shadow
  them, so a file hash literally equal to `media`, or a search id literally
  equal to `results`, is unreachable (see
  [Appendix C](#appendix-c--retired-and-shadowed-paths)). The collection
  actions that used to do this to `{hash}` / `{ecid}` — clear-completed,
  share reload, the share roots, the server-list update — have their own
  top-level paths now and shadow nothing.
- A server is addressed by ECID (`/servers/{ecid}`) or by `<ip>:<port>`
  (`/servers/by-address/{address}`), on separate paths. The address form is
  matched first, so `by-address` is not reachable as an `{ecid}`. The
  by-address handlers resolve the address to an ECID and delegate to the
  ECID-keyed ones.
- Captures accept an empty segment (`/api/v0/clients/` matches
  `/api/v0/clients/{ecid}` with `ecid == ""`), so the *handler* produces the
  rejection, not the router.
- A trailing slash under `/api/` is stripped before matching (step 4), so
  `/api/v0/status/` reaches the same handler as `/api/v0/status`.
- `HEAD` is routed exactly like `GET` and the body is stripped afterwards on
  **any** status, so an erroring `HEAD` carries no content. `Content-Length`
  still describes the body the equivalent `GET` would return, because the
  transport is what withholds the bytes.

### ETag / conditional GET

`Dispatch` post-processes every `GET`/`HEAD` that returns `200` with a
non-empty body **and no `ETag` of its own**: it stamps `ETag:
"<md5-of-body>"` and turns a matching `If-None-Match` into `304` with an
empty body, no `Content-Type`, and the `ETag` preserved. Mutations and error
responses are passed through untouched.

The hash is memoized per `(target, snapshot revision)`, cache capped at
`kEtagCacheCapacity` entries, and the memo is **opt-in per target**
(`MemoizableTarget` — `/downloads` and `/shared`, the only bodies where
skipping an MD5 is worth anything). The key is a revision counter bumped by
every writer, not a wall-clock stamp, and the revision is sampled both before
and after the handler runs: a body produced across a write is not attributable
to a revision and is simply not memoized. Everything else hashes per request.

A validator names one *representation*, so the coding is part of it: when the
transport would gzip the body, the ETag carries a coding suffix, and
`If-None-Match` is compared against the suffixed form. A client holding the
gzip bytes and one holding the identity bytes therefore validate separately.

`ServeStaticFile` computes its own mtime+size ETag and answers its own `304`
(through the same `If-None-Match` grammar — `*`, comma-separated lists, weak
`W/"…"` validators — and a case-insensitive header lookup). The outer layer
steps aside whenever a handler set an `ETag`, so a static asset hands out one
validator, the same for `GET` and `HEAD`.

### CORS

Controlled by `AllowCORS` / `CORSOrigins` in `amuleapi.conf`
(`ResolveCorsOrigin` and `ApplyCorsHeaders`, `Api.cpp`).
When enabled, every response (including 4xx/5xx) carries `Vary: Origin`,
plus — for an accepted origin — `Access-Control-Allow-Origin`,
`Access-Control-Allow-Credentials: true` and
`Access-Control-Expose-Headers: ETag`. A rejected origin still receives the
real response; the *browser* is what blocks it. Preflights add
`Access-Control-Allow-Methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS`,
`Access-Control-Allow-Headers: Authorization, Content-Type, If-None-Match,
Last-Event-ID` and `Access-Control-Max-Age: 86400`.

There is **no CSRF token**: the cookie's `SameSite=Strict` is the defence.

---

## 2. Authentication and authorization

Auth is not middleware — it is the first three to eight lines of each
handler, in a fixed order:

```cpp
auto a = Authenticate(req);                        // 401 / 429
if (!a.ok) return a.rejection;
if (auto rej = RequireAdmin(a)) return *rej;       // 403 — mutations
if (auto r = RequireSnapshot(m_state)) return *r;  // 503 — state readers
```

| Level | Meaning | How it is decided |
|---|---|---|
| `NONE` | reachable unauthenticated | handler calls neither gate |
| `GUEST` | any valid token (guest **or** admin) | `Authenticate(req)` only |
| `ADMIN` | admin token required | `Authenticate(req)` + `RequireAdmin(a)` |

Token transport (`AuthenticateRequest`, `Api.cpp:186`):
`Authorization: Bearer <jwt>` takes precedence over the
`amuleapi_token` cookie (`kSessionCookieName`). The cookie is
issued with `; HttpOnly; SameSite=Strict; Path=/api/v0; Max-Age=<lifetime>`
— no `Secure` (amuleapi serves plain HTTP by design). Tokens are HS256 JWTs
(`src/libwebcommon/Jwt.*`); a token issued before the last credential change
is rejected (`credentials changed; please sign in again`), as is one whose
`jti` is in the revocation set.

Two independent per-IP rate limiters:

| Limiter | Scope | Window / failures / lockout | Source |
|---|---|---|---|
| `m_rateLimiter` | `POST /auth/login` password failures | `[Auth] Login*` config keys | `CApiDispatcher` ctor |
| `m_authRateLimiter` | every generic `401` (bad/missing/revoked token) on any authenticated route, incl. logout and SSE preflight | 60 s / 30 failures / 300 s lockout (hard-coded) | `CApiDispatcher` ctor |

Both answer `429 rate_limited` with a `Retry-After` header.

`RequireSnapshot` (`Api.cpp:276`) answers `503 ec_unavailable` until the
first EC snapshot from `amuled` has been received; it guards every handler
that reads cached daemon state.

---

## 3. Shared envelopes

### Error envelope

Produced by `ErrorResponse` (`Api.cpp:143`) — signature `ErrorResponse(status, code, message)`:

```json
{ "error": { "code": "bad_request", "message": "…" } }
```

### List envelope and pagination

Every list endpoint goes through `ListResponse` / `ListResponseFromPtrsUnlocked`
(`ListResponse` / `ListResponseFromPtrsUnlocked`, `Api.cpp`) and answers:

```json
{ "<plural_key>": [ … ], "total": 0, "offset": 0, "limit": 0 }
```

`total` is the pre-slice count; `limit` echoes the requested limit, or the
number of returned rows when no `limit` was sent. `WritePageMeta`,

Shared query parameters (`ParseListParams`, `Api.cpp:3420`) on those
endpoints:

| Param | Type | Rules |
|---|---|---|
| `limit` | integer | ≤ 9 digits, clamped to **500**; bad value → `400` `` `limit` must be a non-negative integer`` |
| `offset` | integer | ≤ 9 digits; bad value → `400` `` `offset` must be a non-negative integer`` |
| `sort` | string | must be one of the endpoint's sortable fields ([Appendix D](#appendix-d--sortable-fields-per-list-endpoint)); unknown → `400` ``unknown `sort` field for this endpoint`` |
| `order` | `asc` \| `desc` | anything else → `400` `` `order` must be "asc" or "desc"`` |

Sorting is a stable sort over the whole set, then the window is sliced.

### Bulk mutation envelope

Four routes answer with a per-item result list (`BulkResultsResponse`,
`Api.cpp:4606`): `POST /downloads`, `PATCH /downloads`, `DELETE /downloads` and
`PATCH /shared`. Other multi-item mutations have their own shapes —
`POST /downloads_clear_completed` answers `{ok, cleared, cleared_hashes}` and the
`/share_directories` writes answer `{ok, rejected[]}`.

```json
{ "results": [ { "id": "<hash|link>", "ok": true },
               { "id": "…", "ok": false,
                 "error": { "code": "not_found", "message": "…" } } ] }
```

Aggregate HTTP status: all items OK → the route's success status; every item
`503` → `503`; any other mixture → **`207 Multi-Status`**. `hashes` arrays are
parsed by `ParseBulkHashes` (`Api.cpp:4652`): 1–500 entries, each a 32-char
hex string.

### Mutation flow

Every mutating handler follows the same seven steps (comment at
`Api.cpp`): authenticate → require admin → parse the JSON body →
send the EC packet through `SendRecvSerialized` → `EC_OP_NOOP` means success
and `EC_OP_FAILED` carries `amuled`'s rejection (surfaced as
`400 amuled_rejected`) → run a `RefresherTick` inline so the response
reflects post-mutation state → return the updated resource, `201`, or `204`.

---

## 4. Error catalog

Every `(status, code)` pair emitted anywhere in `Api.cpp`, counted over all
handlers, plus the pairs produced below the dispatcher by the HTTP layer.

| Status | `code` | Distinct messages | Meaning |
|---|---|---|---|
| 400 | `amuled_rejected` | 30 | `amuled` refused the EC mutation (`EC_OP_FAILED`); its message is relayed |
| 400 | `bad_request` | 165 | malformed path, query, body or field value |
| 401 | `invalid_credentials` | 1 | login password matched no configured role |
| 401 | `unauthorized` | 6 | missing / invalid / expired / revoked token |
| 403 | `forbidden` | 1 | `RequireAdmin` — admin role required |
| 403 | `invalid_credentials` | 1 | `current_password` did not match on a password change |
| 404 | `not_found` | 40 | no such route, file, peer, server, category or search |
| 405 | `method_not_allowed` | 1 | the path exists, the method does not; the response carries an `Allow` header (`MethodNotAllowed`, one site, one message per route) |
| 409 | `completed_use_clear_completed` | 1 | delete attempted on a completed download |
| 409 | `conflict` | 2 | state conflict (A4AF loop, gated preference) |
| 409 | `kad_more_exhausted` | 1 | `/search/{id}/more` on a Kad search with nothing left |
| 409 | `not_completed` | 1 | single clear-completed on a file that is not completed |
| 409 | `not_shared` | 1 | comment/rating attempted on a non-shared file |
| 409 | `partfile_unsupported` | 2 | verify attempted on a partfile |
| 409 | `update_check_unavailable` | 1 | version check disabled or unavailable |
| 429 | `rate_limited` | 4 | per-IP auth / login failure lockout (`Retry-After`) |
| 429 | `update_check_throttled` | 1 | version check asked for again too soon |
| 500 | `internal_error` | 10 | hash decode / serialization failure inside a handler |
| 502 | `amuled_rejected` | 4 | the daemon answered but the reply was unusable (no `search_id` for a search/browse, shared-directory apply refused) |
| 502 | `bad_gateway` | 1 | unparseable EC payload from `amuled` |
| 503 | `ec_unavailable` | 45 | no first EC snapshot yet, or the EC roundtrip failed |
| 503 | `ec_unsupported` | 8 | the connected `amuled` is too old for this feature |
| 503 | `login_disabled` | 1 | no admin/guest password configured |

Produced by the HTTP layer, below the dispatcher:

| Status | `code` | When | Source |
|---|---|---|---|
| 500 | `internal` | a handler threw | `HttpServer.cpp`, session dispatch `catch` |
| 503 | `sessions_exhausted` | 33rd concurrent SSE session; `Retry-After: 10` | `HttpServer.cpp`, `WriteCapRefusal` |
| — | — | body > 1 MiB, headers > 16 KiB, or a 10 s read timeout: the connection is closed with no response | `HttpServer.cpp` |

Bulk per-item `error.code` values (inside `results[]`, not the envelope):
`ec_unavailable`, `amuled_rejected`, `not_found`, `internal_error`,
`completed_use_clear_completed`.

---

## 5. Endpoints

Every route the server answers, in resource order. `Auth` is the level the
handler enforces (see [§2](#2-authentication-and-authorization)); the shared
`401` / `403` / `429` rows are not repeated per endpoint.

### System

#### `GET, HEAD /api/v0/health`

Liveness / readiness probe. Answers `200` as long as the HTTP server is up, whatever the state of the EC link.

| | |
|---|---|
| Handler | `HandleHealth` — `src/webapi/Api.cpp:1935-1951` |
| Auth | **NONE** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "status": "string",
  "ec_connected": "bool",
  "snapshot": "bool"
}
```

**Notes**

- `status` is the constant `"ok"` — reaching the handler at all is what it reports. Readiness is `ec_connected` (EC link up) and `snapshot` (a first daemon snapshot has landed): both true is when the state-reading endpoints stop answering `503 ec_unavailable`.
- Takes no auth gate and no snapshot gate, so it is usable from a container/orchestrator probe that holds no token.
- `GET /api/v0/version` used to be pressed into this role; this route owns it now.

#### `GET, HEAD /api/v0/version`

Daemon and API version, plus — for an authenticated caller — the daemon's new-version check state.

| | |
|---|---|
| Handler | `HandleVersion` — `src/webapi/Api.cpp:1953-2035` |
| Auth | **NONE for the identity fields, GUEST for `update`** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "name": "string",
  "api_version": "string",
  "amule_version": "string",
  "daemon_version": "string",
  "update": {
    "check_enabled": "bool",
    "checked": "bool",
    "latest_version": "string",
    "update_available": "bool",
    "last_checked": "int|null"
  }
}
```

**Notes**

- Auth is **optional**, which is why the handler does not call `Authenticate` unconditionally: version negotiation has to work before anyone holds a token. A request with no credential is the documented unauthenticated use and is not counted against the generic 401 limiter; a credential that *is* presented and rejected still counts.
- `update` is emitted **only** when the caller authenticated — whether this daemon runs an outdated build is not something an anonymous caller on a reachable interface should learn. Clients must treat the key as optional.
- Inside `update`: `latest_version` / `update_available` / `last_checked` reflect what the daemon last learned, and are null until a check has completed; `check_enabled` mirrors the `general.check_new_version` preference and the daemon's own capability.
- `amule_version` is the aMule version string, `daemon_version` the connected `amuled`'s.

#### `POST /api/v0/version/check`

Ask the daemon to run its new-version check now. Asynchronous: the result lands on a later `GET /api/v0/version`.

| | |
|---|---|
| Handler | `HandleVersionCheck` — `src/webapi/Api.cpp:4682-4739` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"status": "started"}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 409 | `update_check_unavailable` | `version check is disabled or unavailable on the connected daemon` |
| 429 | `update_check_throttled` | `version check was throttled by the daemon; try again shortly` |
| 503 | `ec_unavailable` | `EC roundtrip failed for version check` |

**Notes**

- Gated on the daemon reporting the check as available *and* `general.check_new_version` being on; otherwise `409 update_check_unavailable`.
- The daemon's own throttle surfaces as `429 update_check_throttled`; the daemon's localized message is deliberately not relayed.

### Authentication

#### `POST /api/v0/auth/login`

Exchange a password for a session. The response always sets the `amuleapi_token` cookie; the JWT is only echoed in the body for bearer clients.

| | |
|---|---|
| Handler | `HandleLogin` — `src/webapi/Api.cpp:2037-2120` |
| Auth | **NONE** |
| Success | `200 OK` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `type` | `bearer` | Opt into the bearer shape (also triggered by `Accept: application/jwt`). `BeginSession`, `Api.cpp:2128` |

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `password` | string | yes | Plain password; matched against the admin record first, then the guest record. |

**Response body** — cookie shape (default), plus `token` and `jti` when the
bearer shape was requested:

```json
{
  "token": "string (bearer only)",
  "role": "admin | guest",
  "expires_at": "ISO-8601 UTC string",
  "expires_at_unix": "int",
  "jti": "string (bearer only)"
}
```

Headers: `Set-Cookie: amuleapi_token=<jwt>; HttpOnly; SameSite=Strict; Path=/api/v0; Max-Age=<lifetime>`.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | `body must be JSON object {"password": "..."}` |
| 400 | `bad_request` | <code>missing or non-string `password` field</code> |
| 401 | `invalid_credentials` | `password does not match any configured role` |
| 429 | `rate_limited` | `too many failed attempts; retry later` |
| 503 | `login_disabled` | <code>amuleapi has no admin/guest password configured; set one via `amuleapi --set-admin-pass=&lt;plain&gt;`</code> |

**Notes**

- Password failures are counted by the dedicated login limiter (`[Auth] Login*` config); a lockout answers `429 rate_limited` with `Retry-After`. A *misconfiguration* (`no password configured at all`) answers `503 login_disabled` and does **not** count as a failure.
- The comparison runs over the MD5 of the plain password, then the stored PBKDF2 record; a record predating the current KDF cost is upgraded in place on a successful login.

#### `POST /api/v0/auth/logout`

Revoke the calling session's `jti` and clear the cookie.

| | |
|---|---|
| Handler | `HandleLogout` — `src/webapi/Api.cpp:2179-2267` |
| Auth | **NONE** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{ "ok": true }
```

Headers: a `Set-Cookie` that expires `amuleapi_token`.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 401 | `unauthorized` | `invalid or expired token` |
| 401 | `unauthorized` | `missing bearer token or session cookie` |
| 429 | `rate_limited` | `too many failed auth attempts; retry later` |

**Notes**

- Deliberately soft: it extracts the bearer/cookie token itself instead of calling `Authenticate`, and an already-revoked or expired token still gets `200` — logging out twice is not an error.
- Repeated `401`s here still feed the generic per-IP auth limiter.

#### `GET, HEAD /api/v0/auth/session`

Describe the calling token: role, `jti`, and expiry.

| | |
|---|---|
| Handler | `HandleSession` — `src/webapi/Api.cpp:2279-2306` |
| Auth | **GUEST** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "role": "string",
  "jti": "string",
  "exp": "string",
  "exp_unix": "int"
}
```

#### `GET, HEAD /api/v0/auth/passwords`

Whether an admin password is set and whether the guest role is enabled. No password material is ever returned.

| | |
|---|---|
| Handler | `HandleAuthPasswords` — `src/webapi/Api.cpp:2311-2332` |
| Auth | **ADMIN** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "admin_set": "bool",
  "guest_enabled": "bool"
}
```

#### `PATCH /api/v0/auth/passwords`

Change the admin and/or guest password, or enable/disable the guest role.

| | |
|---|---|
| Handler | `HandleAuthPasswordsPatch` — `src/webapi/Api.cpp:2344-2480` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `current_password` | string | yes | Must be the current **admin** password. |
| `admin_password` | string | no | New admin password. Cannot be empty — the admin role cannot be removed. |
| `guest_password` | string | no | New guest password. Setting it implies `guest_enabled: true` unless `guest_enabled` says otherwise. |
| `guest_enabled` | bool | no | Enable/disable the guest role. |

**Response body** — the post-change state plus a freshly issued session
for the caller (the same fields `POST /auth/login` returns):

```json
{
  "admin_set": "bool",
  "guest_enabled": "bool",
  "other_sessions_revoked": true,
  "role": "admin",
  "expires_at": "ISO-8601 UTC string",
  "expires_at_unix": "int"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`admin_password` cannot be empty; the admin role cannot be removed</code> |
| 400 | `bad_request` | <code>`current_password` is required</code> |
| 400 | `bad_request` | <code>`guest_enabled` must be a boolean</code> |
| 400 | `bad_request` | <code>`guest_password` cannot be set together with `guest_enabled: false`</code> |
| 400 | `bad_request` | `body must be a JSON object` |
| 400 | `bad_request` | `nothing to change` |
| 400 | `bad_request` | `password fields must be strings` |
| 403 | `invalid_credentials` | <code>`current_password` is not the admin password</code> |
| 429 | `rate_limited` | `too many failed attempts; retry later` |
| 500 | `internal_error` | *(relayed at runtime: `apply_err.c_str()`)* |

**Notes**

- Writing the credential file invalidates every token issued before it. The caller is re-issued in the same response, so the operator who changed the password stays signed in and everybody else is signed out.
- A wrong `current_password` is `403 invalid_credentials` and counts against the login rate limiter.
- `guest_password` together with `guest_enabled: false` is rejected rather than guessed at; a body that changes nothing is `400 nothing to change`.
- The credential store lives outside `/preferences`: sending `remote_controls.amuleapi` passwords there is rejected on purpose.

### Status and networks

#### `GET, HEAD /api/v0/status`

The dashboard rollup: ed2k/Kad connection state, transfer counters, queue sizes, and the daemon/EC health flags. Same nested shape the `status_changed` SSE event carries.

| | |
|---|---|
| Handler | `HandleStatus` — `src/webapi/Api.cpp:2482-2624` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "ec_connected": "bool",
  "ed2k": {
    "state": "string",
    "high_id": "bool",
    "id": "int",
    "public_ip": "string",
    "connected_since": "int",
    "server_name": "string",
    "server_ip": "string",
    "server_port": "int",
    "network": {
      "users": "int",
      "files": "int"
    }
  },
  "kad": {
    "state": "string",
    "firewalled": "bool",
    "connected_since": "int",
    "network": {
      "users": "int",
      "files": "int",
      "nodes": "int"
    }
  },
  "speeds": {
    "download_bps": "int",
    "upload_bps": "int",
    "download_overhead_bps": "int",
    "upload_overhead_bps": "int"
  },
  "disk": {
    "temp_free_bytes": "int | null",
    "incoming_free_bytes": "int | null"
  },
  "queue": {
    "upload_clients_waiting": "int",
    "download_sources_total": "int"
  }
}
```

**Notes**

- Built from one `Dashboard()` acquisition, so every counter in the response is from the same snapshot.
- The `kad.network` sub-object is byte-identical to the one on `GET /api/v0/kad` — one writer, `WriteKadNetworkObject`, `Api.cpp:664`.
- `disk.*_free_bytes` is `null` (not `-1`, not `0`) when the daemon could not determine free space.
- `ed2k.public_ip` is an empty string until a high ID is obtained.

#### `GET, HEAD /api/v0/kad`

Kademlia state: node id, firewall status, bucket/contact counters and the network rollup.

| | |
|---|---|
| Handler | `HandleKad` — `src/webapi/Api.cpp:6978-7046` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "state": "string",
  "node_id": "string",
  "firewalled": "bool",
  "firewalled_udp": "bool",
  "in_lan_mode": "bool",
  "connected_since": "int",
  "public_ip": "string",
  "network": {
    "users": "int",
    "files": "int",
    "nodes": "int"
  },
  "indexed": {
    "sources": "int",
    "keywords": "int",
    "notes": "int",
    "load": "int"
  },
  "buddy": {
    "status": "string",
    "ip": "string",
    "port": "int"
  }
}
```

#### `POST /api/v0/networks/connect`

Connect ed2k, Kad, or both.

| | |
|---|---|
| Handler | `HandleNetworksConnect` — `src/webapi/Api.cpp:8545-8588` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "message": "…"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `network` | `ed2k` \| `kad` \| `both` | no | Default `both`. `ed2k` → `EC_OP_SERVER_CONNECT`, `kad` → `EC_OP_KAD_START`, `both` → `EC_OP_CONNECT`. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>"`network` must be one of \"ed2k\", \"kad\", \"both\</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |

**Notes**

- The body is optional — an empty body means `both`.
- `/api/v0/kad/connect` and `/api/v0/kad/disconnect` were retired in favour of this route with `{"network":"kad"}`.

#### `POST /api/v0/networks/disconnect`

Disconnect ed2k, Kad, or both.

| | |
|---|---|
| Handler | `HandleNetworksDisconnect` — `src/webapi/Api.cpp:8590-8635` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "message": "…"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `network` | `ed2k` \| `kad` \| `both` | no | Default `both`. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>"`network` must be one of \"ed2k\", \"kad\", \"both\</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |

#### `POST /api/v0/kad/bootstrap`

Bootstrap Kad from one known contact.

| | |
|---|---|
| Handler | `HandleKadBootstrap` — `src/webapi/Api.cpp:8735-8822` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "ip": <uint32>, "port": <int>}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `ip` | string \| number | yes | Dotted-quad IPv4, or a host-order uint32. |
| `port` | number | yes | 0–65535. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`ip` must be a dotted-quad IPv4 address or a host-order uint32</code> |
| 400 | `bad_request` | <code>`ip` must be a string or number</code> |
| 400 | `bad_request` | <code>`ip` uint32 out of range</code> |
| 400 | `bad_request` | <code>`port` must be in [0, 65535]</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required field `ip` is missing</code> |
| 400 | `bad_request` | <code>required numeric field `port` is missing</code> |
| 503 | `ec_unavailable` | `EC roundtrip failed for KAD_BOOTSTRAP_FROM_IP` |

#### `POST /api/v0/kad/update`

Tell the daemon to fetch `nodes.dat` from a URL.

| | |
|---|---|
| Handler | `HandleKadUpdateFromUrl` — `src/webapi/Api.cpp:8655-8675` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "nodes_url": "<effective url>"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `nodes_url` | string | no | `http://` or `https://` URL. When omitted, the configured `kademlia.nodes_url` preference is used; if no preference snapshot exists yet, that fallback is a `503`. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `("required string field " + field + " is missing").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must be a string").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must be an http:// or https:// URL").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must not be empty").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " was omitted and no URL is configured").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |
| 503 | `ec_unavailable` | `amuleapi has not received its first EC snapshot yet` |

**Notes**

- `amuled` persists the URL into the matching preference itself, so this route does not also PATCH `/preferences`.
- Shares `ResolveFetchUrl` / `UrlFetchOp` with `POST /servers_update` and `POST /ipfilter/update`.

#### `POST /api/v0/ipfilter/reload`

Reload the IP filter from disk (the Security page's *Reload List*).

| | |
|---|---|
| Handler | `HandleIpfilterReload` — `src/webapi/Api.cpp:8686-8694` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "message": "…"}` |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |

#### `POST /api/v0/ipfilter/update`

Fetch an IP-filter list from a URL (the Security page's *Update now*).

| | |
|---|---|
| Handler | `HandleIpfilterUpdate` — `src/webapi/Api.cpp:8707-8733` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "ipfilter_url": "<effective url>"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `ipfilter_url` | string | no | `http://` or `https://` URL; falls back to the `security.ipfilter_update_url` preference when omitted. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `("required string field " + field + " is missing").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must be a string").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must be an http:// or https:// URL").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must not be empty").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " was omitted and no URL is configured").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |
| 503 | `ec_unavailable` | `amuleapi has not received its first EC snapshot yet` |

### Downloads

#### `GET, HEAD /api/v0/downloads`

The transfer queue. Completed entries are filtered out by default.

| | |
|---|---|
| Handler | `HandleDownloads` — `src/webapi/Api.cpp:3886-3966` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `include_completed` | `1` \| `true` \| `yes` | Include entries whose `status` is `completed` (they live in the daemon's *awaiting clear* list). Any other value means false. |
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `name`, `progress`, `size`, `speed`, `status`. |

**Request body**: none.

**Response body**

```json
{
  "downloads": [
    {
      "hash": "string",
      "name": "string",
      "ed2k_link": "string",
      "size": "int",
      "size_done": "int",
      "size_xfer": "int",
      "speed_bps": "int",
      "status": "string",
      "priority": "string",
      "priority_auto": "bool",
      "category": "int",
      "sources": {
        "total": "int",
        "not_current": "int",
        "transferring": "int",
        "a4af": "int"
      },
      "progress": {
        "percent": "number"
      },
      "kad_comment_search_running": "bool",
      "hashing_progress": "int"
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Notes**

- List rows omit `progress.parts` and the detail-only fields; read `GET /api/v0/downloads/{hash}` for those.
- `hashing_progress` and `kad_comment_search_running` *are* on the list row — deliberately, so a client can render a hashing indicator without a per-file roundtrip.

#### `POST /api/v0/downloads`

Add one or more ed2k links.

| | |
|---|---|
| Handler | `HandleDownloadAdd` — `src/webapi/Api.cpp:4741-4875` |
| Auth | **ADMIN** |
| Success | `202 Accepted` (bulk envelope; `207` on a mixed result, `503` when every item failed) |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `ed2k_link` | string | either | A single `ed2k://` link. |
| `links` | array of strings | either | Several `ed2k://` links. Mutually exclusive with `ed2k_link`; at least one entry. |
| `category` | number | no | Category index, 0–255. Default 0. |

**Response body** — the [bulk envelope](#bulk-mutation-envelope); `id` is
the submitted link.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`category` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`category` must be in [0, 255]</code> |
| 400 | `bad_request` | <code>`ed2k_link` must be a string</code> |
| 400 | `bad_request` | <code>`links` must be an array of ed2k://strings</code> |
| 400 | `bad_request` | <code>`links` must contain at least one entry</code> |
| 400 | `bad_request` | <code>every entry in `links` must be a string</code> |
| 400 | `bad_request` | `every link must start with ed2k://` |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required field missing: send `ed2k_link` (string) or `links` (array of strings)</code> |
| 400 | `bad_request` | <code>send either `ed2k_link` (single) or `links` (array), not both</code> |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 503 | `ec_unavailable` | `EC roundtrip failed for ADD_LINK` |
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg`)* |

**Notes**

- The partfile is allocated and hashed asynchronously by `amuled`, so a just-added link may take one or two refresher ticks to appear in `GET /downloads`.

#### `PATCH /api/v0/downloads`

Apply the same status / priority / category change to many downloads.

| | |
|---|---|
| Handler | `HandleDownloadsBulkPatch` — `src/webapi/Api.cpp:8940-9071` |
| Auth | **ADMIN** |
| Success | `200 OK` (bulk envelope; `207` mixed, `503` all-failed) |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `hashes` | array of strings | yes | 1–500 lowercase 32-char hex MD4 hashes. |
| `status` | `paused` \| `resumed` \| `stopped` | no | At least one of `status`, `priority`, `category` is required. |
| `priority` | `low` \| `normal` \| `high` \| `auto` | no | Download priorities only — `very_low` and `release` are upload-side levels and are rejected here. |
| `category` | number | no | 0–255. |

**Response body** — the [bulk envelope](#bulk-mutation-envelope); `id` is
the hash.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>"`status` must be one of \"paused\", \"resumed\" or \"stopped\</code> |
| 400 | `bad_request` | *(relayed at runtime: `FilePriorityAccepted(kPrioDownload).c_str()`)* |
| 400 | `bad_request` | <code>`category` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`category` must be in [0, 255]</code> |
| 400 | `bad_request` | <code>`hashes` entries must be strings</code> |
| 400 | `bad_request` | <code>`hashes` may contain at most 500 entries</code> |
| 400 | `bad_request` | <code>`hashes` must be an array of 32-char hex strings</code> |
| 400 | `bad_request` | <code>`hashes` must contain at least one entry</code> |
| 400 | `bad_request` | <code>`priority` must be a wire-string enum</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>request body must include at least one of `status`, `priority`, or `category`</code> |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no download with that hash` |
| 500 | `internal_error` | `failed to decode partfile hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed` |
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err`)* |

**Notes**

- The patch is validated once for the whole batch: a malformed field is a `400` for the entire request, while per-hash problems (unknown hash, daemon rejection) come back per item.
- Ops are applied in a fixed order — status, then priority, then category — regardless of JSON key order.

#### `DELETE /api/v0/downloads`

Cancel and remove many active downloads.

| | |
|---|---|
| Handler | `HandleDownloadsBulkDelete` — `src/webapi/Api.cpp:9073-9138` |
| Auth | **ADMIN** |
| Success | `200 OK` (bulk envelope) |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `hashes` | array of strings | yes | 1–500 hex MD4 hashes. |

**Response body** — the [bulk envelope](#bulk-mutation-envelope).

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`hashes` entries must be strings</code> |
| 400 | `bad_request` | <code>`hashes` may contain at most 500 entries</code> |
| 400 | `bad_request` | <code>`hashes` must be an array of 32-char hex strings</code> |
| 400 | `bad_request` | <code>`hashes` must contain at least one entry</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no download with that hash` |
| 409 | `completed_use_clear_completed` | `DELETE only removes active downloads; use POST /downloads_clear_completed to clear a completed entry` |
| 500 | `internal_error` | `failed to decode partfile hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for DELETE` |
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err`)* |

**Notes**

- A `completed` entry is refused per item with `409 completed_use_clear_completed` — use `POST /api/v0/downloads_clear_completed` for those.

#### `POST /api/v0/downloads_clear_completed`

Acknowledge completed downloads so the daemon drops them from its *awaiting clear* staging list. Does **not** delete anything from disk.

| | |
|---|---|
| Handler | `HandleDownloadsClearCompleted` — `src/webapi/Api.cpp:5263-5382` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `hash` | string | no | Clear one entry. Omit the body (or the field) to clear every completed entry in one EC roundtrip. |

**Response body**

```json
{ "ok": true, "cleared": "int", "cleared_hashes": ["string"] }
```

An empty completed list is a `200` with `cleared: 0`, so a no-op stays
distinguishable from a daemon rejection.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`hash` must be a string</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 404 | `not_found` | `no download with that hash` |
| 409 | `not_completed` | `target download exists but is not in the completed staging list (status != "completed"). To remove an active partfile, use DELETE /downloads/{hash}.` |
| 503 | `ec_unavailable` | `EC roundtrip failed for CLEAR_COMPLETED` |

**Notes**

- Unknown body keys are ignored on purpose, so adding a flag later cannot break older clients.
- A top-level path, not `/downloads/clear_completed`: an action on the collection is not a member of it, and the old spelling shadowed the `{hash}` capture.

#### `GET, HEAD /api/v0/downloads/{hash}`

One download, with the per-part bitmap and every detail-only field.

| | |
|---|---|
| Handler | `HandleDownloadDetail` — `src/webapi/Api.cpp:4237-4270` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. Case-insensitive — canonicalised to lowercase by `LowerHexKey`, `Api.cpp:290`. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "hash": "string",
  "name": "string",
  "ed2k_link": "string",
  "size": "int",
  "size_done": "int",
  "size_xfer": "int",
  "speed_bps": "int",
  "status": "string",
  "priority": "string",
  "priority_auto": "bool",
  "category": "int",
  "sources": {
    "total": "int",
    "not_current": "int",
    "transferring": "int",
    "a4af": "int"
  },
  "progress": {
    "percent": "number",
    "parts": [
      {
        "state": "complete | incomplete | missing",
        "sources": "int"
      }
    ]
  },
  "kad_comment_search_running": "bool",
  "hashing_progress": "int",
  "last_seen_complete": "int|null",
  "last_changed": "int",
  "download_active_time": "int",
  "available_part_count": "int",
  "part_count": "int",
  "remaining_time": "int|null",
  "lost_to_corruption": "int",
  "gained_by_compression": "int",
  "saved_by_ich": "int",
  "aich_hash": "string",
  "met_file": "string",
  "path": "string",
  "partmet_id": "int",
  "queued_count": "int",
  "comment": "string",
  "rating": "int",
  "a4af_auto": "bool",
  "media": {
    "length_s": "int",
    "bitrate": "int",
    "codec": "string",
    "artist": "string",
    "album": "string",
    "title": "string"
  }
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no download with that hash` |

**Notes**

- `remaining_time` is `-1` when the file is not moving (`speed_bps == 0`).
- `media` is present only for a file `ffprobe` has produced metadata for.
- `parts[].state` is `complete` / `incomplete` / `missing`; the array is empty for a zero-byte file.
- Unlike `GET /downloads`, this endpoint answers for a completed download too.

#### `PATCH /api/v0/downloads/{hash}`

Change one download: pause/resume/stop, priority, category, comment+rating, or rename.

| | |
|---|---|
| Handler | `HandleDownloadPatch` — `src/webapi/Api.cpp:5007-5187` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | `paused` \| `resumed` \| `stopped` | no |  |
| `priority` | `low` \| `normal` \| `high` \| `auto` | no | Download priorities only — `very_low` and `release` are upload-side levels and are rejected here (`FilePriorityToCode`, `Api.cpp:3710`, domain `kPrioDownload`). |
| `category` | number | no | 0–255. |
| `comment` | string | with `rating` | ≤ 50 characters. Only settable on a file that is *shared* (a partfile with at least one complete chunk). |
| `rating` | number | with `comment` | Integer 0–5. |
| `name` | string | no | Rename; must be non-empty and contain no path separators. |

**Response body**

```json
{
  "hash": "string",
  "name": "string",
  "ed2k_link": "string",
  "size": "int",
  "size_done": "int",
  "size_xfer": "int",
  "speed_bps": "int",
  "status": "string",
  "priority": "string",
  "priority_auto": "bool",
  "category": "int",
  "sources": {
    "total": "int",
    "not_current": "int",
    "transferring": "int",
    "a4af": "int"
  },
  "progress": {
    "percent": "number"
  },
  "kad_comment_search_running": "bool",
  "hashing_progress": "int"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>"`status` must be one of \"paused\", \"resumed\" or \"stopped\</code> |
| 400 | `bad_request` | *(relayed at runtime: `FilePriorityAccepted(kPrioDownload).c_str()`)* |
| 400 | `bad_request` | <code>`category` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`category` must be in [0, 255]</code> |
| 400 | `bad_request` | <code>`comment` and `rating` must be set together</code> |
| 400 | `bad_request` | <code>`comment` exceeds 50 characters</code> |
| 400 | `bad_request` | <code>`comment` must be a string</code> |
| 400 | `bad_request` | <code>`name` must be a string</code> |
| 400 | `bad_request` | <code>`name` must not be empty</code> |
| 400 | `bad_request` | <code>`name` must not contain path separators</code> |
| 400 | `bad_request` | <code>`priority` must be a wire-string enum</code> |
| 400 | `bad_request` | <code>`rating` must be an integer in [0, 5]</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>request body must include at least one of `status`, `priority`, `category`, `comment`+`rating`, or `name`</code> |
| 404 | `not_found` | `no download with that hash` |
| 409 | `not_shared` | `comment and rating can only be set on a shared file` |
| 500 | `internal_error` | `failed to decode file hash` |
| 500 | `internal_error` | `failed to decode partfile hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed` |
| 503 | `ec_unavailable` | `EC roundtrip failed for RENAME_FILE` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SET_COMMENT` |

**Notes**

- At least one field is required; a body that changes nothing is a `400`.
- Fields are applied in a fixed order (status, priority, category, comment+rating, name), each as its own EC mutation — a later failure leaves the earlier ones applied.
- The response is the list-shaped object (no `parts`, no detail fields), re-read after an inline refresher tick.

#### `DELETE /api/v0/downloads/{hash}`

Cancel and remove one active download (partfile deleted by the daemon).

| | |
|---|---|
| Handler | `HandleDownloadDelete` — `src/webapi/Api.cpp:5189-5261` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{ "ok": true, "hash": "string" }
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no download with that hash` |
| 409 | `completed_use_clear_completed` | `DELETE only removes active downloads (deletes .part/.met files from disk). Use POST /downloads_clear_completed with optional {"hash":"..."} body to clear a completed entry's post-completion notification — the file in the Incoming directory ` |
| 500 | `internal_error` | `failed to decode partfile hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for DELETE` |

**Notes**

- A `completed` entry is refused with `409 completed_use_clear_completed`: the only EC op that touches the completed staging list is `EC_OP_CLEAR_COMPLETED`, and it does not delete the file from `Incoming`.

#### `GET, HEAD /api/v0/downloads/{hash}/comments`

Comments and ratings reported by the file's sources, plus any Kad notes retrieved so far.

| | |
|---|---|
| Handler | `HandleDownloadComments` — `src/webapi/Api.cpp:4302-4346` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "count": "int",
  "kad_comment_search_running": "bool",
  "comments": [
    {
      "username": "string",
      "filename": "string",
      "rating": "int",
      "comment": "string"
    }
  ]
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no download with that hash` |

**Notes**

- `kad_comment_search_running` is true while an on-demand Kad NOTES lookup is in flight — poll until it flips back to false.

#### `POST /api/v0/downloads/{hash}/comments`

Trigger an on-demand Kad NOTES lookup for this file.

| | |
|---|---|
| Handler | `HandleDownloadCommentsKadSearch` — `src/webapi/Api.cpp:4352-4400` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"status": "kad_search_started"}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 404 | `not_found` | `no download with that hash` |
| 500 | `internal_error` | `failed to decode file hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SEARCH_KAD_NOTES` |

**Notes**

- Admin-only even though it reads: it drives an unbounded Kad lookup on the daemon (~45 s).
- Results appear on a subsequent `GET` of the same path.

#### `GET, HEAD /api/v0/downloads/{hash}/filenames`

The filenames this file's sources report, with how many sources use each — the desktop's *Filenames* tab.

| | |
|---|---|
| Handler | `HandleDownloadFilenames` — `src/webapi/Api.cpp:4402-4436` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "filenames": [
    {
      "name": "string",
      "count": "int"
    }
  ]
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no download with that hash` |

#### `GET, HEAD /api/v0/downloads/{hash}/clients`

The peers related to this download: sources, peers pulling it from us, and A4AF sources.

| | |
|---|---|
| Handler | `HandleFileClients` — `src/webapi/Api.cpp:4056-4130` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of a **download**. |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `include_parts` | `true` \| `false` | Include each peer's per-part bitmap for this file. Anything else is a `400`. Default `false`. |
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. |

**Request body**: none.

**Response body**

```json
{
  "clients": [
    {
      "ecid": "int",
      "name": "string",
      "user_hash": "string",
      "ip": "string",
      "port": "int",
      "country_code": "string",
      "software": "string",
      "software_version": "string",
      "os_info": "string",
      "upload_state": "string",
      "download_state": "string",
      "ident_state": "string",
      "download_file_name": "string",
      "upload_file_name": "string",
      "upload_file_hash": "string",
      "download_file_hash": "string",
      "xfer": {
        "up_session": "int",
        "down_session": "int",
        "up_total": "int",
        "down_total": "int"
      },
      "upload_speed_bps": "int",
      "download_speed_bps": "int",
      "queue_waiting_position": "int",
      "remote_queue_rank": "int",
      "score": "int",
      "obfuscation_status": "string",
      "friend_slot": "bool",
      "source_origin": "string",
      "available_parts": "int",
      "mod_version": "string",
      "view_shared_disabled": "bool",
      "part_progress_percent": "number",
      "role": "string",
      "a4af": "bool",
      "parts": [
        "bool"
      ]
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `require_downloading ? "no download with that hash" : "no shared file with that hash"` |

**Notes**

- Same handler as `GET /api/v0/shared/{hash}/clients`, with `require_downloading = true` — the hash must name a download here and a shared file there.
- `role` is `source` / `peer` / `both` / `none`, and `a4af` marks a row that is an A4AF source of this file.
- Which bitmap a row carries follows its direction: the download bitmap for a source, the upload bitmap for a peer; a pure A4AF row has none.
- Sortable fields come from `ClientComparators` (`Api.cpp:3350`), so they match `GET /clients`: `name`, `software`.

#### `POST /api/v0/downloads/{hash}/a4af`

Swap A4AF (*asked for another file*) sources between this file and its siblings.

| | |
|---|---|
| Handler | `HandleDownloadA4afAction` — `src/webapi/Api.cpp:4463-4565` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `action` | `swap_this` \| `swap_this_auto` \| `swap_others` | yes | `swap_this` pulls A4AF sources onto this file; `swap_this_auto` does it and leaves auto-A4AF on; `swap_others` pushes them away. |
| `client_ecid` | number | no | Narrow `swap_this` to one named source (the desktop's per-peer *Swap to this file*). Only valid with `swap_this`; the ECID must be a current A4AF source of this file. |

**Response body**

```json
{
  "a4af_auto": "bool",
  "source_ecids": [
    "int"
  ]
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`action` must be one of swap_this, swap_this_auto, swap_others</code> |
| 400 | `bad_request` | <code>`client_ecid` is only valid with action `swap_this`</code> |
| 400 | `bad_request` | <code>`client_ecid` must be a non-negative integer</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>request body must include a string `action`</code> |
| 404 | `not_found` | `no client with that ECID in the current snapshot` |
| 404 | `not_found` | `no download with that hash` |
| 409 | `conflict` | `that client is not an A4AF source of this download` |
| 500 | `internal_error` | `failed to decode partfile hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for A4AF swap` |

**Notes**

- The `GET` half of this path was retired: read `a4af_auto` from the download detail object and the A4AF rows from `GET /downloads/{hash}/clients`. A `GET` here answers `405`.

### Clients (peers)

#### `GET, HEAD /api/v0/clients`

Every peer the daemon currently knows: upload slots, queue waiters and download sources, in one collection.

| | |
|---|---|
| Handler | `HandleClients` — `src/webapi/Api.cpp:4132-4193` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `filter` | `uploads` \| `downloads` \| `active` | `uploads` = peers with `upload_state == "uploading"`; `downloads` = peers with `download_state == "downloading"`; `active` = the union. Any other value is a `400`. Absent = every peer. |
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. |

**Request body**: none.

**Response body**

```json
{
  "clients": [
    {
      "ecid": "int",
      "name": "string",
      "user_hash": "string",
      "ip": "string",
      "port": "int",
      "country_code": "string",
      "software": "string",
      "software_version": "string",
      "os_info": "string",
      "upload_state": "string",
      "download_state": "string",
      "ident_state": "string",
      "download_file_name": "string",
      "upload_file_name": "string",
      "upload_file_hash": "string",
      "download_file_hash": "string",
      "xfer": {
        "up_session": "int",
        "down_session": "int",
        "up_total": "int",
        "down_total": "int"
      },
      "upload_speed_bps": "int",
      "download_speed_bps": "int",
      "queue_waiting_position": "int",
      "remote_queue_rank": "int",
      "score": "int",
      "obfuscation_status": "string",
      "friend_slot": "bool",
      "source_origin": "string",
      "available_parts": "int",
      "mod_version": "string",
      "view_shared_disabled": "bool",
      "part_progress_percent": "number"
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>"`filter` must be one of \"uploads\", \"downloads\", \"active\</code> |

**Notes**

- `/api/v0/uploads` was retired in favour of this route — consumers filter client-side (or with `?filter=uploads`).
- `part_progress_percent` is computed per row before serialization, so the list, the per-file rows, the detail object and the SSE `client_*` payloads all carry it.

#### `GET, HEAD /api/v0/clients/{ecid}`

One peer, with the ed2k-identity and server fields the list row omits.

| | |
|---|---|
| Handler | `HandleClientDetail` — `src/webapi/Api.cpp:5882-5908` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | EC connection id (`uint32`), unique per live connection. An empty or non-numeric segment is a `400`. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "ecid": "int",
  "name": "string",
  "user_hash": "string",
  "ip": "string",
  "port": "int",
  "country_code": "string",
  "software": "string",
  "software_version": "string",
  "os_info": "string",
  "upload_state": "string",
  "download_state": "string",
  "ident_state": "string",
  "download_file_name": "string",
  "upload_file_name": "string",
  "upload_file_hash": "string",
  "download_file_hash": "string",
  "xfer": {
    "up_session": "int",
    "down_session": "int",
    "up_total": "int",
    "down_total": "int"
  },
  "upload_speed_bps": "int",
  "download_speed_bps": "int",
  "queue_waiting_position": "int",
  "remote_queue_rank": "int",
  "score": "int",
  "obfuscation_status": "string",
  "friend_slot": "bool",
  "source_origin": "string",
  "available_parts": "int",
  "mod_version": "string",
  "view_shared_disabled": "bool",
  "part_progress_percent": "number",
  "user_id_hybrid": "uint",
  "high_id": "bool",
  "server_ip": "string",
  "server_port": "int",
  "server_name": "string",
  "kad_port": "int",
  "is_friend": "bool",
  "dl_up_modifier": "number"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no client with that ECID in the current snapshot` |

**Notes**

- Detail-only keys, on top of the list row: `user_id_hybrid`, `high_id`, `server_ip`, `server_port`, `server_name`, `kad_port`, `is_friend`, `dl_up_modifier`.
- ECIDs are per-connection and are not stable across daemon restarts.

#### `POST /api/v0/clients/{ecid}/shared_files`

Browse (*View Files*) a peer's share. Starts an asynchronous browse and returns the `search_id` its results will arrive under.

| | |
|---|---|
| Handler | `HandleClientBrowse` — `src/webapi/Api.cpp:10132-10136` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "search_id": <int>}` |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | EC connection id of a connected peer. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 502 | `amuled_rejected` | `daemon did not return a search_id for browse` |
| 503 | `ec_unavailable` | `EC roundtrip failed for browse` |

**Notes**

- Delegates to the shared `HandleBrowse` (`Api.cpp:10150`), which is where the auth gate and the EC exchange live — `HandleClientBrowse` itself is a two-line wrapper.
- Read the listing with `GET /api/v0/search/{search_id}/results`; the search's `kind` is `browse` and its `query` is the peer's name.
- A peer that refuses the browse comes back as `404` carrying the daemon's reason; a daemon that starts no browse at all is a `502`.

#### `POST /api/v0/clients/{ecid}/messages`

Send a chat message to a connected peer, addressed by ECID instead of `<ip>:<port>`.

| | |
|---|---|
| Handler | `HandleClientMessageSend` — `src/webapi/Api.cpp:6137-6153` |
| Auth | **ADMIN** |
| Success | `202 Accepted` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | EC connection id of a connected peer. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | Non-empty, ≤ 1024 bytes. |

**Response body**

```json
{ "ok": true, "peer": "<ip>:<port>",
  "message": { "id": "int", "direction": "out", "text": "string", "timestamp": "int" } }
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`text` exceeds 1024 bytes</code> |
| 400 | `bad_request` | <code>`text` must be a non-empty string</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required string field `text` is missing</code> |
| 404 | `not_found` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed for chat send` |
| 503 | `ec_unsupported` | `the connected amuled does not serve chat sessions` |

**Notes**

- Only reaches a peer the daemon has a live connection to. Use `POST /api/v0/friends/{ecid}/messages` to reach an offline friend.

### Known clients (credit store)

#### `GET, HEAD /api/v0/known_clients`

The daemon's credit store: every peer it has ever exchanged data with, keyed by user hash, with stored totals rather than live transfer state.

| | |
|---|---|
| Handler | `HandleKnownClients` — `src/webapi/Api.cpp:5774-5880` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `first_seen`, `last_seen`, `name`, `sessions`, `software`, `total_downloaded`, `total_uploaded`. |

**Request body**: none.

**Response body**

```json
{
  "known_clients": [
    {
      "user_hash": "string",
      "name": "string",
      "ip": "string",
      "port": "int",
      "kad_port": "int",
      "country_code": "string",
      "software": "string",
      "version": "string",
      "source_origin": "string",
      "obfuscation": "string",
      "total_uploaded": "uint",
      "total_downloaded": "uint",
      "last_seen": "uint",
      "first_seen": "uint",
      "sessions": "uint",
      "online": "bool"
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 502 | `bad_gateway` | `the core answered the history request with an unknown reply` |
| 503 | `ec_unavailable` | `the EC connection is unavailable` |
| 503 | `ec_unsupported` | `the connected amuled does not serve the client history` |

**Notes**

- A separate resource rather than a sub-path of `/clients`: these rows outlive the connection that would have issued an ECID.
- Matched before `/clients/{ecid}`, which would otherwise capture the segment.
- `503 ec_unsupported` when the connected `amuled` predates the EC op; `502 bad_gateway` when its payload cannot be decoded.

### Shared files

#### `GET, HEAD /api/v0/shared`

Every file the daemon is sharing, with upload counters.

| | |
|---|---|
| Handler | `HandleSharedList` — `src/webapi/Api.cpp:4195-4235` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `name`, `size`. |

**Request body**: none.

**Response body**

```json
{
  "shared": [
    {
      "hash": "string",
      "name": "string",
      "ed2k_link": "string",
      "size": "int",
      "priority": "string",
      "priority_auto": "bool",
      "complete_sources": "int",
      "xfer": {
        "session": "int",
        "total": "int"
      },
      "requests": {
        "session": "int",
        "total": "int"
      },
      "accepts": {
        "session": "int",
        "total": "int"
      },
      "upload_speed_bps": "int",
      "uploading": "int",
      "last_upload": "int|null",
      "shared_since": "int|null",
      "hashing_progress": "int",
      "media": {
        "length_s": "int",
        "bitrate": "int",
        "codec": "string",
        "artist": "string",
        "album": "string",
        "title": "string"
      }
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Notes**

- `uploading` is a **count of peers currently downloading this file**, not a boolean.
- `hashing_progress` is a part *count* (parts hashed so far by a Verify Local Data or an AICH rebuild), not a percentage; `0` when idle.

#### `PATCH /api/v0/shared`

Set the upload priority of many shared files at once.

| | |
|---|---|
| Handler | `HandleSharedBulkPatch` — `src/webapi/Api.cpp:9140-9206` |
| Auth | **ADMIN** |
| Success | `200 OK` (bulk envelope; `207` mixed, `503` all-failed) |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `hashes` | array of strings | yes | 1–500 hex MD4 hashes. |
| `priority` | `very_low` \| `low` \| `normal` \| `high` \| `release` \| `auto` | yes |  |

**Response body** — the [bulk envelope](#bulk-mutation-envelope).

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | *(relayed at runtime: `FilePriorityAccepted(kPrioShared).c_str()`)* |
| 400 | `bad_request` | <code>`hashes` entries must be strings</code> |
| 400 | `bad_request` | <code>`hashes` may contain at most 500 entries</code> |
| 400 | `bad_request` | <code>`hashes` must be an array of 32-char hex strings</code> |
| 400 | `bad_request` | <code>`hashes` must contain at least one entry</code> |
| 400 | `bad_request` | <code>`priority` must be a wire-string enum</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>request body must include `priority`</code> |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no shared file with that hash` |
| 500 | `internal_error` | `failed to decode file hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SHARED_SET_PRIO` |
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err`)* |

#### `POST /api/v0/shared_reload`

Ask the daemon to re-walk every configured share root.

| | |
|---|---|
| Handler | `HandleSharedReload` — `src/webapi/Api.cpp:9683-9712` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "message": "…"}` |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |

**Notes**

- Literally *accepted*: `amuled` schedules the walk and answers immediately (it starts on its next `Process()` tick). Repeated calls while a walk is pending coalesce into one.
- Completion is observable through `GET /api/v0/logs/amule` (or the `log_appended` SSE event) and the `shared_added` / `shared_removed` events — not through this response.

#### `POST /api/v0/shared/media/refresh`

Re-probe **every** shared file's media metadata, replacing what is stored.

| | |
|---|---|
| Handler | `HandleSharedMediaRefresh` — `src/webapi/Api.cpp:9640-9648` |
| Auth | **ADMIN** |
| Success | `202 Accepted` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{ "ok": true, "scope": "string", "queued": "int" }
```

`202`, not `200`: `amuled` queues the probes on its media-probe worker and
answers immediately, so nothing has been re-extracted yet. `queued` counts the
files accepted for probing — ones the scheduler dropped (not audio/video, an
incomplete download, missing on disk) are not counted.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed for media refresh` |
| 503 | `ec_unsupported` | `the connected amuled does not implement media metadata refresh` |

**Notes**

- The only way to correct metadata that is *wrong* rather than missing: the normal scheduler skips any file that already carries a media tag.
- Each probe **replaces** every media field, clearing one the new probe no longer finds. Nothing else about a file is touched and it is not re-hashed.
- One file at a time on the daemon's media-probe worker; shutting down mid-refresh is clean. Progress is observable through `GET /api/v0/logs/amule` and the `shared_updated` SSE events.
- A literal route matched before `/shared/{hash}`, so a file whose hash is literally `media` is unreachable.
- `503 ec_unsupported` when the connected `amuled` predates the EC op.

#### `GET, HEAD /api/v0/share_directories`

The configured share roots (as opposed to the files they produced).

| | |
|---|---|
| Handler | `HandleSharedDirectories` — `src/webapi/Api.cpp:9379-9420` |
| Auth | **GUEST** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "directories": [
    {
      "path": "string",
      "recursive": "bool"
    }
  ]
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 502 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `no reply from amuled` |

**Notes**

- Its own top-level path: the roots are configuration, not members of the `/shared` file collection, and the old `/shared/directories` spelling sat one segment away from being read as a file hash.

#### `PUT /api/v0/share_directories`

Replace the whole share-root list in one shot.

| | |
|---|---|
| Handler | `HandleSharedDirectoriesPut` — `src/webapi/Api.cpp:9428-9473` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `directories` | array of objects | yes | Each entry: `path` (non-empty string) and optional `recursive` (bool, default `false`). |

**Response body**

```json
{ "ok": true, "rejected": [ { "path": "string", "reason": "string" } ] }
```

`rejected` carries the roots `amuled` declined (missing, unreadable, …); the
apply itself still succeeds for the rest.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`directories` must be an array</code> |
| 400 | `bad_request` | <code>`recursive` must be a boolean</code> |
| 400 | `bad_request` | `each directory must be an object` |
| 400 | `bad_request` | <code>each directory needs a non-empty `path`</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 502 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `no reply from amuled` |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 403 | `not_readable` | `amuled cannot read that path` |
| 404 | `not_found` | `no such directory` |

#### `POST /api/v0/share_directories`

Add one share root, or update the `recursive` flag of an existing one.

| | |
|---|---|
| Handler | `HandleSharedDirectoriesAdd` — `src/webapi/Api.cpp:9478-9528` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | string | yes | Non-empty. Compared verbatim against the existing roots — POSIX and Windows spellings are both accepted as-is. |
| `recursive` | bool | no | Default `false`. |

**Response body** — same `{ "ok", "rejected" }` shape as the `PUT`.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`path` must be a non-empty string</code> |
| 400 | `bad_request` | <code>`recursive` must be a boolean</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 502 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | *(relayed at runtime: `ec_err.c_str()`)* |
| 503 | `ec_unavailable` | `no reply from amuled` |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 403 | `not_readable` | `amuled cannot read that path` |
| 404 | `not_found` | `no such directory` |

**Notes**

- Read-modify-write under a process-wide mutex: the current list is fetched from the daemon, edited, and applied whole.

#### `DELETE /api/v0/share_directories`

Remove one share root.

| | |
|---|---|
| Handler | `HandleSharedDirectoriesDelete` — `src/webapi/Api.cpp:9534-9572` |
| Auth | **ADMIN** |
| Success | `200 OK` |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `path` | string | **Required.** The root to remove, matched exactly. Unknown path → `404 not_found`. |

**Request body**: none.

**Response body** — same `{ "ok", "rejected" }` shape as the `PUT`.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`path` query parameter is required</code> |
| 404 | `not_found` | `no such shared directory` |
| 502 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | *(relayed at runtime: `ec_err.c_str()`)* |
| 503 | `ec_unavailable` | `no reply from amuled` |

**Per-item errors** (inside `results[]`)

| `http` | `code` | `message` |
|---|---|---|
| 403 | `not_readable` | `amuled cannot read that path` |
| 404 | `not_found` | `no such directory` |

**Notes**

- The target is a query parameter, not a body field, so the request carries no body.

#### `GET, HEAD /api/v0/shared/{hash}`

One shared file, with the per-part source-availability array and the detail-only fields.

| | |
|---|---|
| Handler | `HandleSharedDetail` — `src/webapi/Api.cpp:4272-4300` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4, case-insensitive. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "hash": "string",
  "name": "string",
  "ed2k_link": "string",
  "size": "int",
  "priority": "string",
  "priority_auto": "bool",
  "complete_sources": "int",
  "xfer": {
    "session": "int",
    "total": "int"
  },
  "requests": {
    "session": "int",
    "total": "int"
  },
  "accepts": {
    "session": "int",
    "total": "int"
  },
  "upload_speed_bps": "int",
  "uploading": "int",
  "last_upload": "int|null",
  "shared_since": "int|null",
  "hashing_progress": "int",
  "file_type": "string",
  "share_ratio": "number",
  "path": "string",
  "incomplete": "bool",
  "complete_sources_range": {
    "low": "int",
    "high": "int"
  },
  "aich_hash": "string",
  "part_count": "int",
  "parts": [
    {
      "sources": "int"
    }
  ],
  "queued_count": "int",
  "comment": "string",
  "rating": "int",
  "media": {
    "length_s": "int",
    "bitrate": "int",
    "codec": "string",
    "artist": "string",
    "album": "string",
    "title": "string"
  }
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no shared file with that hash` |

**Notes**

- Detail-only, on top of the list row: `file_type`, `share_ratio`, `path`, `incomplete`, `complete_sources_range`, `aich_hash`, `part_count`, `parts`, `queued_count`, `comment`, `rating`, `media`.
- `parts[]` is `{sources}` per part — deliberately *not* the downloads `state` shape, which would invite rendering it as progress. The key is omitted entirely when nothing has been decoded yet, so *no data* stays distinguishable from *no sources anywhere*.
- `path` is the file's real directory; for a shared partfile that is the temp directory, flagged by `incomplete`.

#### `PATCH /api/v0/shared/{hash}`

Set a shared file's upload priority, and/or its comment and rating.

| | |
|---|---|
| Handler | `HandleSharedPatch` — `src/webapi/Api.cpp:8830-8928` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `priority` | `very_low` \| `low` \| `normal` \| `high` \| `release` \| `auto` | no |  |
| `comment` | string | with `rating` | ≤ 50 characters. |
| `rating` | number | with `comment` | Integer 0–5. |

**Response body**

```json
{
  "hash": "string",
  "name": "string",
  "ed2k_link": "string",
  "size": "int",
  "priority": "string",
  "priority_auto": "bool",
  "complete_sources": "int",
  "xfer": {
    "session": "int",
    "total": "int"
  },
  "requests": {
    "session": "int",
    "total": "int"
  },
  "accepts": {
    "session": "int",
    "total": "int"
  },
  "upload_speed_bps": "int",
  "uploading": "int",
  "last_upload": "int|null",
  "shared_since": "int|null",
  "hashing_progress": "int",
  "media": {
    "length_s": "int",
    "bitrate": "int",
    "codec": "string",
    "artist": "string",
    "album": "string",
    "title": "string"
  }
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `FilePriorityAccepted(kPrioShared).c_str()`)* |
| 400 | `bad_request` | <code>`comment` and `rating` must be set together</code> |
| 400 | `bad_request` | <code>`comment` exceeds 50 characters</code> |
| 400 | `bad_request` | <code>`comment` must be a string</code> |
| 400 | `bad_request` | <code>`priority` must be a wire-string enum</code> |
| 400 | `bad_request` | <code>`rating` must be an integer in [0, 5]</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>request body must include `priority`, `comment`+`rating`, or `name`</code> |
| 404 | `not_found` | `no shared file with that hash` |
| 409 | `not_shared` | `comment and rating can only be set on a shared file` |
| 500 | `internal_error` | `failed to decode file hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SET_COMMENT` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SHARED_SET_PRIO` |

**Notes**

- At least one of `priority` or `comment`+`rating` is required.

#### `POST /api/v0/shared/{hash}/verify`

Re-hash a completed shared file against its on-disk data.

| | |
|---|---|
| Handler | `HandleSharedVerify` — `src/webapi/Api.cpp:9208-9271` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of a completed shared file. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no shared file with that hash` |
| 409 | `partfile_unsupported` | `verify local data is not supported on a partfile` |
| 500 | `internal_error` | `failed to decode file hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for VERIFY_LOCAL_DATA` |

**Notes**

- A partfile is refused with `409 partfile_unsupported`: the daemon's hashing task bails out on `IsPartFile()` but still answers `NOOP`, which would tell the caller the re-hash had been accepted.
- Progress is observable as `hashing_progress` on the file's rows.

#### `POST /api/v0/shared/{hash}/media/refresh`

Re-probe one shared file's media metadata.

| | |
|---|---|
| Handler | `HandleSharedMediaRefreshOne` — `src/webapi/Api.cpp:9650-9681` |
| Auth | **ADMIN** |
| Success | `202 Accepted` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of a shared file. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{ "ok": true, "scope": "string", "queued": "int" }
```

`202`, not `200`: `amuled` queues the probes on its media-probe worker and
answers immediately, so nothing has been re-extracted yet. `queued` counts the
files accepted for probing — ones the scheduler dropped (not audio/video, an
incomplete download, missing on disk) are not counted.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no shared file with that hash` |
| 409 | `partfile_unsupported` | `media metadata cannot be extracted from an incomplete download` |
| 500 | `internal_error` | `failed to decode file hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for media refresh` |
| 503 | `ec_unsupported` | `the connected amuled does not implement media metadata refresh` |

**Notes**

- Same semantics as the all-files form, scoped to one hash; `scope` reads `file` rather than `all`.
- An incomplete partfile is refused with `409 partfile_unsupported` rather than accepted and silently dropped by the daemon's scheduler: there is no complete file to read.
- Unknown hash → `404 not_found`.

#### `GET, HEAD /api/v0/shared/{hash}/clients`

The peers related to this shared file.

| | |
|---|---|
| Handler | `HandleFileClients` — `src/webapi/Api.cpp:4056-4130` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of a **shared** file. |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `include_parts` | `true` \| `false` | Include each peer's per-part bitmap. Default `false`. |
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. |

**Request body**: none.

**Response body**

```json
{
  "clients": [
    {
      "ecid": "int",
      "name": "string",
      "user_hash": "string",
      "ip": "string",
      "port": "int",
      "country_code": "string",
      "software": "string",
      "software_version": "string",
      "os_info": "string",
      "upload_state": "string",
      "download_state": "string",
      "ident_state": "string",
      "download_file_name": "string",
      "upload_file_name": "string",
      "upload_file_hash": "string",
      "download_file_hash": "string",
      "xfer": {
        "up_session": "int",
        "down_session": "int",
        "up_total": "int",
        "down_total": "int"
      },
      "upload_speed_bps": "int",
      "download_speed_bps": "int",
      "queue_waiting_position": "int",
      "remote_queue_rank": "int",
      "score": "int",
      "obfuscation_status": "string",
      "friend_slot": "bool",
      "source_origin": "string",
      "available_parts": "int",
      "mod_version": "string",
      "view_shared_disabled": "bool",
      "part_progress_percent": "number",
      "role": "string",
      "a4af": "bool",
      "parts": [
        "bool"
      ]
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `require_downloading ? "no download with that hash" : "no shared file with that hash"` |

**Notes**

- Same handler as `GET /api/v0/downloads/{hash}/clients` with `require_downloading = false`.
- `parts` here is an array of booleans (one per part), present only when `include_parts=true` *and* the row actually has a bitmap for this file.

### Servers (ed2k server list)

#### `GET, HEAD /api/v0/servers`

The ed2k server list, with per-server capability flags.

| | |
|---|---|
| Handler | `HandleServers` — `src/webapi/Api.cpp:5503-5531` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `files`, `name`, `ping`, `users`. |

**Request body**: none.

**Response body**

```json
{
  "servers": [
    {
      "ecid": "int",
      "name": "string",
      "description": "string",
      "version": "string",
      "address": "string",
      "country_code": "string",
      "port": "int",
      "users": "int",
      "max_users": "int",
      "files": "int",
      "soft_file_limit": "int",
      "hard_file_limit": "int",
      "priority": "string",
      "ping_ms": "int",
      "failed_count": "int",
      "static": "bool",
      "tcp_flags": {
        "bitmask": "uint",
        "compression": "bool",
        "new_tags": "bool",
        "unicode": "bool",
        "related_search": "bool",
        "type_tag_integer": "bool",
        "large_files": "bool",
        "tcp_obfuscation": "bool"
      },
      "udp_flags": {
        "bitmask": "uint",
        "get_sources": "bool",
        "get_files": "bool",
        "new_tags": "bool",
        "unicode": "bool",
        "get_sources_v2": "bool",
        "large_files": "bool",
        "udp_obfuscation": "bool",
        "tcp_obfuscation": "bool"
      }
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Notes**

- `tcp_flags` / `udp_flags` are decoded capability objects — a `bitmask` plus one boolean per wire bit. The names come from one table shared by the REST writer and the SSE payload (`ServerFlagNames.h:98`, `117`).
- `soft_file_limit` / `hard_file_limit` are the server's advertised limits; `ping_ms` and `failed_count` are the daemon's own counters, relayed verbatim.

#### `POST /api/v0/servers`

Add a server by address.

| | |
|---|---|
| Handler | `HandleServerAdd` — `src/webapi/Api.cpp:6500-6573` |
| Auth | **ADMIN** |
| Success | `201 Created` — `{"ok": true, "address": "host:port"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `address` | string | yes | `host:port`. The colon must be present and not at either end. |
| `name` | string | no | Display name; omitted means the daemon uses whatever the server announces. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`address` must be in "host:port" form</code> |
| 400 | `bad_request` | <code>`name` must be a string</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required string field `address` is missing ("host:port")</code> |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_ADD` |

#### `POST /api/v0/servers_update`

Tell the daemon to fetch `server.met` from a URL.

| | |
|---|---|
| Handler | `HandleServerUpdateFromUrl` — `src/webapi/Api.cpp:6679-6701` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "servers_url": "<effective url>"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `servers_url` | string | yes | `http://` or `https://` URL. Required — unlike the Kad and IP-filter variants there is no configured fallback. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `("required string field " + field + " is missing").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must be a string").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must be an http:// or https:// URL").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " must not be empty").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `(field + " was omitted and no URL is configured").c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |
| 503 | `ec_unavailable` | `amuleapi has not received its first EC snapshot yet` |

**Notes**

- A top-level path: updating the list is an action on the collection, and `/servers/update` shadowed a server whose ECID was `update`.

#### `POST /api/v0/servers/{ecid}/connect`

Connect to one server.

| | |
|---|---|
| Handler | `HandleServerConnect` — `src/webapi/Api.cpp:6575-6628` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "ecid": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | The server's EC id. To address a server by `<ip>:<port>` use `/servers/by-address/{address}/connect`. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no server with that ECID in the current snapshot` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_CONNECT` |

#### `POST /api/v0/servers/by-address/{address}/connect`

Connect to one server, addressed by `<ip>:<port>` instead of by ECID.

| | |
|---|---|
| Handler | `HandleServerConnectByAddress` — `src/webapi/Api.cpp:6795-6813` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "ecid": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `address` | `<ip>:<port>`, matched against the server list. Unknown address → `404 not_found`. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | `0.0.0.0 is not a server address` |
| 400 | `bad_request` | `malformed ip:port selector: expected a dotted quad and a port in 1..65535` |
| 404 | `not_found` | `no server matches that ip:port` |
| 404 | `not_found` | `no server with that ECID in the current snapshot` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_CONNECT` |

**Notes**

- Its own path rather than a `<ip>:<port>` value in the `{ecid}` capture. One capture with two identity domains, disambiguated by sniffing for a colon, is a dispatch rule invisible from outside — and it forecloses ever accepting an IPv6 literal, which is all colons. The handler resolves the address to an ECID and delegates to the ECID-keyed one, so the response is identical.

#### `PATCH /api/v0/servers/{ecid}`

Set a server's priority and/or its static flag.

| | |
|---|---|
| Handler | `HandleServerPatch` — `src/webapi/Api.cpp:6826-6917` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "ecid": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | Server EC id. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `priority` | `low` \| `normal` \| `high` | no |  |
| `static` | bool | no |  |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`priority` must be a string</code> |
| 400 | `bad_request` | <code>`priority` must be one of low, normal, high</code> |
| 400 | `bad_request` | <code>`static` must be a bool</code> |
| 400 | `bad_request` | <code>body must include at least one of `priority`, `static`</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 404 | `not_found` | `no server with that ECID in the current snapshot` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_SET_STATIC_PRIO` |

**Notes**

- At least one of the two fields is required.
- Note the priority vocabulary differs from files: servers have three levels, no `auto`.

#### `DELETE /api/v0/servers/{ecid}`

Remove one server from the list.

| | |
|---|---|
| Handler | `HandleServerDelete` — `src/webapi/Api.cpp:6630-6677` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "ecid": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | Server EC id. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no server with that ECID in the current snapshot` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_REMOVE` |

#### `PATCH, DELETE /api/v0/servers/by-address/{address}`

The `PATCH` and `DELETE` above, addressed by `<ip>:<port>` instead of by ECID. Same bodies, same responses.

| | |
|---|---|
| Handler | `HandleServerPatchByAddress` — `src/webapi/Api.cpp:6920-6936` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "ecid": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `address` | `<ip>:<port>`. Unknown address → `404 not_found`. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `priority` | `low` \| `normal` \| `high` | no | `PATCH` only. |
| `static` | bool | no | `PATCH` only. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | `0.0.0.0 is not a server address` |
| 400 | `bad_request` | <code>`priority` must be a string</code> |
| 400 | `bad_request` | <code>`priority` must be one of low, normal, high</code> |
| 400 | `bad_request` | <code>`static` must be a bool</code> |
| 400 | `bad_request` | <code>body must include at least one of `priority`, `static`</code> |
| 400 | `bad_request` | `malformed ip:port selector: expected a dotted quad and a port in 1..65535` |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 404 | `not_found` | `no server matches that ip:port` |
| 404 | `not_found` | `no server with that ECID in the current snapshot` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_REMOVE` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SERVER_SET_STATIC_PRIO` |

**Notes**

- Its own path rather than a `<ip>:<port>` value in the `{ecid}` capture. One capture with two identity domains, disambiguated by sniffing for a colon, is a dispatch rule invisible from outside — and it forecloses ever accepting an IPv6 literal, which is all colons. The handler resolves the address to an ECID and delegates to the ECID-keyed one, so the response is identical.

### Friends

#### `GET, HEAD /api/v0/friends`

The friend list — daemon-side records, not per-connection rows like `/clients`.

| | |
|---|---|
| Handler | `HandleFriends` — `src/webapi/Api.cpp:6199-6221` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `name`, `online`. |

**Request body**: none.

**Response body**

```json
{
  "friends": [
    {
      "ecid": "int",
      "name": "string",
      "user_hash": "string",
      "ip": "string",
      "port": "int",
      "client_ecid": "int",
      "online": "bool",
      "friend_slot": "bool"
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Notes**

- `ecid` identifies the *friend record*; `client_ecid` is the live connection when the friend is online (0 otherwise).

#### `POST /api/v0/friends`

Add a friend, either from a live connection or from raw contact details.

| | |
|---|---|
| Handler | `HandleFriendAdd` — `src/webapi/Api.cpp:6223-6379` |
| Auth | **ADMIN** |
| Success | `201 Created` — the created friend object |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `client_ecid` | number | either | ECID of a currently connected peer. |
| `ip` | string | either | Dotted-quad IPv4 (manual form). |
| `port` | number | either | TCP port (manual form). |
| `user_hash` | string | no | 32-char hex user hash (manual form). |
| `name` | string | no | Display name (manual form). |

**Response body**

```json
{
  "ecid": "int",
  "name": "string",
  "user_hash": "string",
  "ip": "string",
  "port": "int",
  "client_ecid": "int",
  "online": "bool",
  "friend_slot": "bool"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`client_ecid` and the ip/port/user_hash form are mutually exclusive</code> |
| 400 | `bad_request` | <code>`client_ecid` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`ip` must be a non-zero dotted IPv4 address</code> |
| 400 | `bad_request` | <code>`name` must be a string</code> |
| 400 | `bad_request` | <code>`port` must be in 1..65535</code> |
| 400 | `bad_request` | <code>`user_hash` must be 32 hexadecimal characters</code> |
| 400 | `bad_request` | <code>`user_hash` must be a string</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required integer field `port` is missing</code> |
| 400 | `bad_request` | <code>required string field `ip` is missing</code> |
| 404 | `not_found` | <code>no connected client with that `client_ecid`</code> |
| 503 | `ec_unavailable` | `EC roundtrip failed for FRIEND add` |

**Notes**

- `client_ecid` and the `ip`/`port`/`user_hash`/`name` form are mutually exclusive — sending both is a `400`.

#### `PATCH /api/v0/friends/{ecid}`

Grant or revoke this friend's reserved upload slot.

| | |
|---|---|
| Handler | `HandleFriendPatch` — `src/webapi/Api.cpp:6433-6498` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | Friend record EC id. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `friend_slot` | bool | yes |  |

**Response body**

```json
{
  "ecid": "int",
  "name": "string",
  "user_hash": "string",
  "ip": "string",
  "port": "int",
  "client_ecid": "int",
  "online": "bool",
  "friend_slot": "bool"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required boolean field `friend_slot` is missing</code> |
| 404 | `not_found` | `friend disappeared while setting the slot` |
| 404 | `not_found` | `no friend with that ecid` |
| 503 | `ec_unavailable` | `EC roundtrip failed for FRIEND slot` |

#### `DELETE /api/v0/friends/{ecid}`

Remove a friend.

| | |
|---|---|
| Handler | `HandleFriendRemove` — `src/webapi/Api.cpp:6381-6431` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "ecid": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | Friend record EC id. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no friend with that ecid` |
| 503 | `ec_unavailable` | `EC roundtrip failed for FRIEND remove` |

#### `POST /api/v0/friends/{ecid}/shared_files`

Browse a friend's share.

| | |
|---|---|
| Handler | `HandleFriendBrowse` — `src/webapi/Api.cpp:10138-10142` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "search_id": <int>}` |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | Friend record EC id. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 502 | `amuled_rejected` | `daemon did not return a search_id for browse` |
| 503 | `ec_unavailable` | `EC roundtrip failed for browse` |

**Notes**

- Same delegation as the client form: the work is in `HandleBrowse` (`Api.cpp:10150`), addressed by `EC_TAG_FRIEND` instead of `EC_TAG_CLIENT`. This is the form that can reach a friend whose connection is not currently live.
- The started search has `kind: "browse"` and the friend's name as its `query`.

#### `POST /api/v0/friends/{ecid}/messages`

Send a chat message to a friend, addressed by friend ECID.

| | |
|---|---|
| Handler | `HandleFriendMessageSend` — `src/webapi/Api.cpp:6119-6135` |
| Auth | **ADMIN** |
| Success | `202 Accepted` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `ecid` | Friend record EC id. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | Non-empty, ≤ 1024 bytes. |

**Response body** — same shape as the other send forms:

```json
{ "ok": true, "peer": "<ip>:<port>",
  "message": { "id": "int", "direction": "out", "text": "string", "timestamp": "int" } }
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`text` exceeds 1024 bytes</code> |
| 400 | `bad_request` | <code>`text` must be a non-empty string</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required string field `text` is missing</code> |
| 404 | `not_found` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed for chat send` |
| 503 | `ec_unsupported` | `the connected amuled does not serve chat sessions` |

**Notes**

- This is the form that reaches an **offline** friend — the daemon opens the connection.

### Chat

#### `GET, HEAD /api/v0/chats`

Open conversations, newest activity first when sorted.

| | |
|---|---|
| Handler | `HandleChats` — `src/webapi/Api.cpp:5910-5943` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `last_message_at`, `name`. |

**Request body**: none.

**Response body**

```json
{
  "chats": [
    {
      "peer": "string",
      "ip": "string",
      "port": "int",
      "name": "string",
      "client_ecid": "int",
      "friend_ecid": "int",
      "online": "bool",
      "message_count": "int",
      "last_msg_id": "int",
      "last_message_at": "int",
      "last_message": {
        "id": "int",
        "direction": "string",
        "text": "string",
        "timestamp": "int"
      }
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 503 | `ec_unsupported` | `the connected amuled does not serve chat sessions` |

**Notes**

- `peer` is the `<ip>:<port>` key every other chat route takes.
- `last_message` is the most recent message inline, so a list render needs no per-chat roundtrip.

#### `GET, HEAD /api/v0/chats/{peer}/messages`

One conversation's messages, with a polling cursor.

| | |
|---|---|
| Handler | `HandleChatMessages` — `src/webapi/Api.cpp:5945-6024` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `peer` | `<ip>:<port>`. A malformed key is a `400`. |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `since_id` | integer | Return only messages with `id` greater than this. Ids are monotonic per daemon process, so a poller never duplicates or skips; they reset when the daemon restarts (which also empties the store). |
| `limit` | integer | Keep only the **last** *n* of the selected window — *show me the tail of this conversation*. |

**Request body**: none.

**Response body**

```json
{
  "peer": "string",
  "messages": [
    {
      "id": "int",
      "direction": "string",
      "text": "string",
      "timestamp": "int"
    }
  ],
  "total": "int",
  "last_msg_id": "int"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>path `{peer}` must be `&lt;ip&gt;:&lt;port&gt;`</code> |
| 404 | `not_found` | `no chat session with that peer` |
| 503 | `ec_unsupported` | `the connected amuled does not serve chat sessions` |

**Notes**

- `total` is the conversation's full message count, `last_msg_id` the newest id — both independent of the window returned.
- `503 ec_unsupported` when the connected `amuled` does not serve chat sessions.
- This endpoint does **not** use the shared list envelope: no `offset`, no `sort`.

#### `POST /api/v0/chats/{peer}/messages`

Send a message into a conversation, addressed by `<ip>:<port>`.

| | |
|---|---|
| Handler | `HandleChatSend` — `src/webapi/Api.cpp:6099-6117` |
| Auth | **ADMIN** |
| Success | `202 Accepted` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `peer` | `<ip>:<port>`. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | Non-empty, ≤ 1024 bytes. |

**Response body**

```json
{ "ok": true, "peer": "<ip>:<port>",
  "message": { "id": "int", "direction": "out", "text": "string", "timestamp": "int" } }
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>`text` exceeds 1024 bytes</code> |
| 400 | `bad_request` | <code>`text` must be a non-empty string</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>path `{peer}` must be `&lt;ip&gt;:&lt;port&gt;`</code> |
| 400 | `bad_request` | <code>required string field `text` is missing</code> |
| 404 | `not_found` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed for chat send` |
| 503 | `ec_unsupported` | `the connected amuled does not serve chat sessions` |

#### `DELETE /api/v0/chats/{peer}`

Close a conversation and drop its stored messages.

| | |
|---|---|
| Handler | `HandleChatClose` — `src/webapi/Api.cpp:6155-6197` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "peer": "<ip>:<port>"}` |

**Path parameters**

| Name | Description |
|---|---|
| `peer` | `<ip>:<port>`. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>path `{peer}` must be `&lt;ip&gt;:&lt;port&gt;`</code> |
| 404 | `not_found` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed for chat close` |
| 503 | `ec_unsupported` | `the connected amuled does not serve chat sessions` |

**Notes**

- Publishes `chat_session_closed` to SSE subscribers.

### Categories

#### `GET, HEAD /api/v0/categories`

The download categories. Index 0 is the daemon's built-in *all* category.

| | |
|---|---|
| Handler | `HandleCategories` — `src/webapi/Api.cpp:6956-6976` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. |

**Request body**: none.

**Response body**

```json
{
  "categories": [
    {
      "index": "int",
      "name": "string",
      "path": "string",
      "comment": "string",
      "color": "int",
      "priority": "string"
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Notes**

- `color` is a packed RGB integer; `priority` is `low` / `normal` / `high` / `auto` — the category vocabulary, which has no `very_low` or `release`.
- Index 0 is synthesised when the daemon omits it (it suppresses the whole block until a custom category exists), so clients always see at least the default row.
- Takes the shared list params like every other list endpoint; `sort` accepts `index` and `name` (`CategoryComparators()`).

#### `POST /api/v0/categories`

Create a category.

| | |
|---|---|
| Handler | `HandleCategoryCreate` — `src/webapi/Api.cpp:9844-9913` |
| Auth | **ADMIN** |
| Success | `201 Created` — `{"ok": true, "name": "…", "index": <int>}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Non-empty. |
| `path` | string | no | Incoming directory for this category. |
| `comment` | string | no |  |
| `color` | number | no | uint32 packed RGB. |
| `priority` | `low` \| `normal` \| `high` \| `auto` | no |  |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `FilePriorityAccepted(kPrioCategory).c_str()`)* |
| 400 | `bad_request` | <code>`color` must be a uint32</code> |
| 400 | `bad_request` | <code>`color` out of range</code> |
| 400 | `bad_request` | <code>`priority` must be a wire-string enum</code> |
| 400 | `bad_request` | `category field must be a string` |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required string field `name` is missing</code> |
| 503 | `ec_unavailable` | `EC roundtrip failed for CREATE_CATEGORY` |

**Notes**

- `index` is resolved after an inline refresher tick by matching the created name, and is omitted if the new row has not surfaced yet.

#### `GET, HEAD /api/v0/categories/{index}`

One category.

| | |
|---|---|
| Handler | `HandleCategoryOne` — `src/webapi/Api.cpp:9919-9955` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `index` | uint8, 0–255. Non-numeric or out of range → `400`; a valid index with no category → `404 not_found`. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "index": "int",
  "name": "string",
  "path": "string",
  "comment": "string",
  "color": "int",
  "priority": "string"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `bad_request` | <code>path `{index}` must be a uint8 in [0, 255]</code> |
| 404 | `not_found` | `no category with that index` |

**Notes**

- Selected out of the same set the collection lists, synthetic default (index 0) included, so the two routes cannot disagree about which categories exist.

#### `PATCH /api/v0/categories/{index}`

Update a category. Unsent fields keep their current value.

| | |
|---|---|
| Handler | `HandleCategoryUpdate` — `src/webapi/Api.cpp:9957-10026` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `index` | uint8, 0–255. Non-numeric or out of range → `400`. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | no |  |
| `path` | string | no |  |
| `comment` | string | no |  |
| `color` | number | no |  |
| `priority` | `low` \| `normal` \| `high` \| `auto` | no |  |

**Response body**

```json
{
  "index": "int",
  "name": "string",
  "path": "string",
  "comment": "string",
  "color": "int",
  "priority": "string"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | *(relayed at runtime: `FilePriorityAccepted(kPrioCategory).c_str()`)* |
| 400 | `bad_request` | <code>`color` must be a uint32</code> |
| 400 | `bad_request` | <code>`color` out of range</code> |
| 400 | `bad_request` | <code>`priority` must be a wire-string enum</code> |
| 400 | `bad_request` | `category field must be a string` |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>path `{index}` must be a uint8 in [0, 255]</code> |
| 404 | `not_found` | `no category with that index` |
| 503 | `ec_unavailable` | `EC roundtrip failed for UPDATE_CATEGORY` |

#### `DELETE /api/v0/categories/{index}`

Delete a category.

| | |
|---|---|
| Handler | `HandleCategoryDelete` — `src/webapi/Api.cpp:10028-10107` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true, "index": <int>}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `index` | uint8, 0–255. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | `cannot delete the default (index=0) category` |
| 400 | `bad_request` | <code>path `{index}` must be a uint8 in [0, 255]</code> |
| 404 | `not_found` | `no category with that index` |
| 503 | `ec_unavailable` | `EC roundtrip failed for DELETE_CATEGORY` |

**Notes**

- Categories are positional: deleting one shifts every higher index down by one. The cached downloads are re-mapped in the same operation (files in the deleted category fall back to 0), so `GET /downloads` does not report stale indices for a tick.

### Preferences

#### `GET, HEAD /api/v0/preferences`

Every preference the daemon exposes, nested by category. Table-driven: the categories, keys, types and access levels all come from the schema in `src/webapi/PrefsSchema.cpp` — see [Appendix A](#appendix-a--preferences-field-table) for the full list.

| | |
|---|---|
| Handler | `HandlePreferences` — `src/webapi/Api.cpp:8034-8050` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Query parameters**: none.

**Request body**: none.

**Response body** — one object per category:

```json
{
  "general": { "…": "…" },
  "connection": { "…": "…" },
  "directories": { "…": "…" },
  "files": { "…": "…" },
  "servers": { "…": "…" },
  "security": { "…": "…" },
  "message_filter": { "…": "…" },
  "remote_controls": { "webserver": { "…": "…" }, "amuleapi": { "…": "…" } },
  "online_signature": { "…": "…" },
  "core_tweaks": { "…": "…" },
  "kademlia": { "…": "…" },
  "ip2country": { "…": "…" }
}
```

`WriteOnly` rows (passwords, triggers) are never emitted; `Rejected` rows never
appear either.

**Notes**

- `remote_controls` is the only two-level category: `webserver` and `amuleapi` are separate JSON sub-objects that pack into the same EC group.
- Read-only rows (capabilities, live status such as `connection.upnp_available`) are emitted but silently ignored on PATCH.

#### `PATCH /api/v0/preferences`

Apply a partial preferences update. The body mirrors the GET shape: one optional sub-object per category, containing only the keys to change.

| | |
|---|---|
| Handler | `HandlePreferencesPatch` — `src/webapi/Api.cpp:8262-8487` |
| Auth | **ADMIN** |
| Success | `200 OK` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

One optional object per category, e.g.

```json
{ "connection": { "max_download_kbps": 2048 },
  "files": { "add_new_files_paused": true } }
```

Field-level rules come from the schema (Appendix A): `Uint16` / `Uint32` rows
have an inclusive `max`, `Enum` rows accept only their listed names,
`StringArray` rows take an array of strings, and a row with a `gated_by`
capability answers `409 conflict` when that capability is false.

**Response body** — the full `GET /api/v0/preferences` object, re-read
after an inline refresher tick, so a consumer can confirm what actually landed
without a follow-up `GET`.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | `amuleapi passwords are managed through PATCH /auth/passwords, not through /preferences` |
| 400 | `bad_request` | *(relayed at runtime: `err.c_str()`)* |
| 400 | `bad_request` | `guest_enabled must be a bool` |
| 400 | `bad_request` | `guest_password must be a string` |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | `request body did not include any known pref fields` |
| 409 | `conflict` | `this daemon was built without support for that option` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SET_PREFERENCES` |

**Notes**

- Sent in one `EC_OP_SET_PREFERENCES` at `EC_DETAIL_FULL` — the detail level the daemon requires before it honours boolean tags.
- A body with no recognised field at all is a `400`; unknown keys inside a known category are ignored.
- `remote_controls.amuleapi` passwords are explicitly **rejected** here — they live behind `PATCH /api/v0/auth/passwords`.
- `remote_controls.webserver.guest_enabled` + `guest_password` share one EC tag, so their packing is hand-written rather than table-driven (`PrefAccess::Bespoke`).
- `core_tweaks.kad_reask_ms`, `source_reask_ms` and `server_keepalive_timeout_ms` are milliseconds on the wire, exactly as the daemon stores them — no unit conversion happens in this layer.

### Logs

#### `GET, HEAD /api/v0/logs/amule`

The daemon log as amuleapi has mirrored it (append-only, in-process cache).

| | |
|---|---|
| Handler | `HandleLogAmule` — `src/webapi/Api.cpp:7774-7814` |
| Auth | **GUEST** |
| Success | `200 OK` |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `tail` | integer | Return only the last *n* lines. `0`, absent, negative or non-numeric means everything; capped at 100 000. |

**Request body**: none.

**Response body**

```json
{
  "lines": [
    "string"
  ],
  "total_cached": "int",
  "returned": "int"
}
```

**Notes**

- `total_cached` is what the mirror holds, `returned` what this response carried — enough for a client to know what it missed.
- New lines also arrive as the `log_appended` SSE event.

#### `DELETE /api/v0/logs/amule`

Reset the daemon log.

| | |
|---|---|
| Handler | `HandleLogAmuleReset` — `src/webapi/Api.cpp:7816-7848` |
| Auth | **ADMIN** |
| Success | `204 No Content` |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |

**Notes**

- Also drops the in-process mirror, so the next `GET` starts empty and no spurious `log_appended` fires.

#### `GET, HEAD /api/v0/logs/serverinfo`

The server-info log — one accumulated text blob, fetched from the daemon lazily with a 1 s TTL.

| | |
|---|---|
| Handler | `HandleLogServerinfo` — `src/webapi/Api.cpp:7850-7910` |
| Auth | **GUEST** |
| Success | `200 OK` |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `tail` | integer | Keep only the last *n* lines, sliced at line boundaries from the end so the first line is always whole. |

**Request body**: none.

**Response body**

```json
{
  "text": "string",
  "total_bytes": "int",
  "returned_bytes": "int"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 503 | `ec_unavailable` | `EC fetch failed for server info; amuled may be disconnected` |

**Notes**

- `total_bytes` / `returned_bytes` let a client decide whether to re-poll with a smaller `?tail=`.

#### `DELETE /api/v0/logs/serverinfo`

Clear the server-info log.

| | |
|---|---|
| Handler | `HandleLogServerinfoReset` — `src/webapi/Api.cpp:7912-7940` |
| Auth | **ADMIN** |
| Success | `204 No Content` |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed` |

**Notes**

- Invalidates the 1 s lazy cache so the next `GET` re-fetches instead of returning stale text.

### Statistics

#### `GET, HEAD /api/v0/stats/tree`

The daemon's statistics tree (the desktop's *Statistics* page), as nested nodes.

| | |
|---|---|
| Handler | `HandleStatsTree` — `src/webapi/Api.cpp:7301-7377` |
| Auth | **GUEST** |
| Success | `200 OK` |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `max_client_versions` | integer 0–255 | Cap how many per-software version rows the daemon serializes (`EC_TAG_STATTREE_CAPPING`). `0` (default) is unlimited. Only the version lists are affected. Out of range → `400`. |

**Request body**: none.

**Response body**

```json
{
  "nodes": [
    {
      "key": "string (omitted when empty)",
      "label_value": "string (omitted when empty)",
      "label": "string",
      "values": [
        {
          "type": "string",
          "value": "uint | number | string (per the node's value kind)",
          "token": "string (only for enum-ish values)",
          "extra": "{ \u2026 same value object, recursively }"
        }
      ],
      "ratio": {
        "session": "number (optional)",
        "total": "number (optional)"
      },
      "children": [
        "{ \u2026 same node object, recursively }"
      ]
    }
  ]
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 503 | `ec_unavailable` | `EC fetch failed for stats tree; amuled may be disconnected` |

**Notes**

- Fetched lazily with a 1 s TTL that coalesces concurrent readers; the cache is unkeyed, so a request at a different cap counts as a miss.
- `values[].value` is a uint, a double or a string depending on what the daemon sent for that node; `token` and `extra` appear only when non-empty, and `key` / `label_value` are omitted when empty.
- `ratio` is present only when the node carries a session and/or total ratio; `children` is always present (empty array on a leaf).
- `503 ec_unavailable` when the EC fetch fails.

#### `GET, HEAD /api/v0/stats/graphs/{graph}`

One time series plus the session totals.

| | |
|---|---|
| Handler | `HandleStatsGraph` — `src/webapi/Api.cpp:7379-7530` |
| Auth | **GUEST** |
| Success | `200 OK` |

**Path parameters**

| Name | Description |
|---|---|
| `graph` | `download_speed` \| `upload_speed` \| `connections` \| `kad_nodes`. Anything else → `404 not_found`, validated **before** any EC roundtrip. |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `interval` | integer 1–3600 | Seconds between samples (`EC_TAG_STATSGRAPH_SCALE`). Default `1`. Rejected rather than clamped. |
| `width` | integer | Return only the last *n* points. `0`/absent means everything; capped at 1800. Applied after the fetch, so one cached bundle answers every `(graph, width)` combination. |

**Request body**: none.

**Response body**

```json
{
  "graph": "string",
  "unit": "bytes_per_second | count",
  "interval_seconds": "int",
  "max_points": "int",
  "points": [
    {
      "t": "ISO-8601 UTC string",
      "t_unix": "int",
      "value": "int",
      "active_downloads": "int (connections graph only)",
      "active_uploads": "int (connections graph only)"
    }
  ],
  "session": {
    "download_bytes": "int",
    "upload_bytes": "int",
    "kad_node_seconds": "int",
    "duration_seconds": "int"
  }
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `unknown graph; expected one of: download_speed, upload_speed, connections, kad_nodes` |
| 503 | `ec_unavailable` | `EC fetch failed for stats graphs; amuled may be disconnected` |

**Notes**

- One EC roundtrip serves all four graphs, so the 1 s lazy cache is shared across graph names — but it is keyed on nothing, so a request at a different `interval` is a miss.
- `points` is never longer than `max_points`; timestamps are anchored backwards from the fetch wall-clock.
- `active_downloads` / `active_uploads` appear only on the `connections` graph, and only when the daemon sent the second data blob.

### Search

#### `GET, HEAD /api/v0/search`

Every search the daemon currently holds — including ones started by another client or restored from disk.

| | |
|---|---|
| Handler | `HandleSearchList` — `src/webapi/Api.cpp:7722-7772` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`); shared list params (`limit`/`offset`/`sort`/`order`) |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. |

**Request body**: none.

**Response body**

```json
{
  "searches": [
    {
      "search_id": "int",
      "query": "string",
      "kind": "string",
      "state": "string",
      "client_ecid": "int",
      "started_at": "int",
      "result_count": "int"
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint"
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 503 | `ec_unavailable` | `EC roundtrip failed for SEARCH_LIST` |

**Notes**

- Fetched live over EC (`EC_OP_SEARCH_LIST`), not from the refresher cache.
- `client_ecid` appears only on a browse entry (whose share is being listed); `started_at` only for searches *this* amuleapi started; `result_count` only when the daemon reports it. All three are omitted rather than zeroed, so *unknown* stays distinguishable from *none*.
- `kind` is `local` / `global` / `kad` / `browse`; `state` is the daemon's lifecycle state.
- Carries the standard list envelope: the rows are fetched whole over EC, then sorted and sliced like any other list endpoint.

#### `POST /api/v0/search`

Start a search. The daemon allocates the `search_id` everything else is addressed by.

| | |
|---|---|
| Handler | `HandleSearchStart` — `src/webapi/Api.cpp:10236-10410` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "search_id": <int>, "query": "…"}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Non-empty. |
| `type` | `local` \| `global` \| `kad` | no | Default `global`. |
| `file_type` | string | no | aMule file-type label. |
| `extension` | string | no | e.g. `mkv`. |
| `min_size` | number | no | Bytes, ≥ 0. Default 0. |
| `max_size` | number | no | Bytes, ≥ 0. Default 0 = no cap. |
| `min_avail` | number | no | uint32. Default 0. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>"`type` must be one of \"local\", \"global\", \"kad\</code> |
| 400 | `bad_request` | <code>`extension` must be a string</code> |
| 400 | `bad_request` | <code>`file_type` must be a string</code> |
| 400 | `bad_request` | <code>`max_size` must be &gt;= 0</code> |
| 400 | `bad_request` | <code>`max_size` must be a non-negative integer (bytes; 0 = no cap)</code> |
| 400 | `bad_request` | <code>`min_avail` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`min_avail` out of range</code> |
| 400 | `bad_request` | <code>`min_size` must be &gt;= 0</code> |
| 400 | `bad_request` | <code>`min_size` must be a non-negative integer (bytes)</code> |
| 400 | `bad_request` | <code>`query` must be non-empty</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 400 | `bad_request` | <code>required string field `query` is missing</code> |
| 502 | `amuled_rejected` | `daemon did not return a search_id for SEARCH_START` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SEARCH_START` |

**Notes**

- A reply carrying no `search_id` is reported as `502 amuled_rejected` — without an id the caller has nothing to address.
- The refresher starts polling this id for results and progress, so SSE `search_result_added` / `search_progress` fire on the same deltas a poller would see.

#### `GET, HEAD /api/v0/search/{id}/results`

One search's results, with its progress rolled into the same envelope.

| | |
|---|---|
| Handler | `HandleSearchResults` — `src/webapi/Api.cpp:7532-7635` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | shared list params (`limit`/`offset`/`sort`/`order`) |

**Path parameters**

| Name | Description |
|---|---|
| `id` | Positive decimal `search_id`. `0`, non-numeric or overflowing → `400` (`kBadSearchIdMessage`, `kBadSearchIdMessage`). An id naming no live search → `404`. |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting. `sort` accepts: `directory`, `name`, `rating`, `size`, `sources`. |

**Request body**: none.

**Response body**

```json
{
  "results": [
    {
      "hash": "string",
      "name": "string",
      "size": "int",
      "sources": {
        "total": "int",
        "complete": "int"
      },
      "already_have": "bool",
      "rating": "int",
      "status": "string",
      "type": "string",
      "directory": "string",
      "media": {
        "length_s": "int",
        "bitrate": "int",
        "codec": "string",
        "artist": "string",
        "album": "string",
        "title": "string"
      },
      "children": [
        {
          "ecid": "int",
          "name": "string",
          "hash": "string",
          "sources": {
            "total": "int",
            "complete": "int"
          },
          "directory": "string"
        }
      ],
      "kad_comment_search_running": "bool",
      "comments": [
        {
          "username": "string",
          "filename": "string",
          "rating": "int",
          "comment": "string"
        }
      ]
    }
  ],
  "total": "uint",
  "offset": "uint",
  "limit": "uint",
  "search_id": "int",
  "query": "string",
  "progress": {
    "state": "idle | running | finished",
    "kind": "string",
    "percent": "int"
  }
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no search with that search_id (never started, freed or expired)` |

**Notes**

- Keeps its own envelope (the `progress` object rides alongside `results`) but reuses the shared window + page-meta helpers, so `limit`/`offset`/`sort`/`order` behave exactly as elsewhere.
- A finished search is refreshed on read (coalesced by a short TTL), because the refresher stops polling it.
- `results[].children` is always present (empty when the hit was seen under a single name); each child's `ecid` is what `POST /search/results/{hash}/download` takes to pick that filename.
- `media` is present only when the daemon reported probed metadata.
- `progress` mirrors the `search_progress` SSE event field-for-field.
- For a browse, `query` is the peer's name and `results[].directory` is populated — hence the `directory` sort key.
- `results`, `stop` and `more` are dispatched from one `/search/{id}/{action}` block in `DispatchToHandler`; any other action is a `404` `unknown search action (expected results, stop or more)`.

#### `POST /api/v0/search/{id}/stop`

Stop a running search but keep its results readable.

| | |
|---|---|
| Handler | `HandleSearchStop` — `src/webapi/Api.cpp:10464-10479` |
| Auth | **ADMIN** |
| Success | `200 OK` — `{"ok": true}` |

**Path parameters**

| Name | Description |
|---|---|
| `id` | Positive decimal `search_id`. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no search with that search_id (never started, freed or expired)` |
| 503 | `ec_unavailable` | `EC roundtrip failed for the search operation` |

**Notes**

- Siblings are untouched — the daemon is addressed with this id only.

#### `POST /api/v0/search/{id}/more`

Ask a running **Kad** search to widen its result frontier (the desktop's *More* button).

| | |
|---|---|
| Handler | `HandleSearchMore` — `src/webapi/Api.cpp:10503-10551` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true}` |

**Path parameters**

| Name | Description |
|---|---|
| `id` | Positive decimal `search_id`. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`more` applies to Kad searches only</code> |
| 400 | `bad_request` | <code>`more` applies to a running search; this one has finished</code> |
| 404 | `not_found` | `no search with that search_id (never started, freed or expired)` |
| 409 | `kad_more_exhausted` | `this Kad search cannot be widened any further (reask budget spent, or the search is in its final seconds)` |
| 503 | `ec_unavailable` | `EC roundtrip failed for the search operation` |

**Notes**

- Rejected with `400` for a non-Kad search and for a search that has already finished — mirroring the desktop button, which is greyed out in both cases.
- `409 kad_more_exhausted` when the daemon reports the search can no longer be widened (reask budget spent, or inside the ~20 s stopping window). A daemon too old to report gets today's `202`.

#### `DELETE /api/v0/search/{id}`

Stop **and** free a search: the daemon drops it and the local slot goes away.

| | |
|---|---|
| Handler | `HandleSearchClose` — `src/webapi/Api.cpp:10481-10501` |
| Auth | **ADMIN** |
| Success | `204 No Content` |

**Path parameters**

| Name | Description |
|---|---|
| `id` | Positive decimal `search_id`. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 404 | `not_found` | `no search with that search_id (never started, freed or expired)` |
| 503 | `ec_unavailable` | `EC roundtrip failed for the search operation` |

**Notes**

- After this, `GET /search/{id}/results` is a `404` and subscribers see `search_closed`.
- The `{id}` segment is validated *before* the method check, so `PATCH /api/v0/search/abc` is a `400`, not a `405`.

#### `POST /api/v0/search/results/{hash}/download`

Download one search result.

| | |
|---|---|
| Handler | `HandleSearchDownload` — `src/webapi/Api.cpp:10553-10658` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"ok": true, "hash": "…", "category": <int>}` |
| Gates | JSON object body, nesting ≤ 32 (`400 bad_request`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of the result, case-insensitive. |

**Query parameters**: none.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `category` | number | no | 0–255, default 0. |
| `ecid` | number | no | Pick one grouped child (from a result's `children[].ecid`) so the file downloads under that filename. Omitted means the parent hit. |

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err_msg.c_str()`)* |
| 400 | `bad_request` | <code>`category` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`category` must be in [0, 255]</code> |
| 400 | `bad_request` | <code>`ecid` must be a non-negative integer</code> |
| 400 | `bad_request` | <code>`ecid` out of range</code> |
| 400 | `bad_request` | <code>`{hash}` must be a 32-char hex MD4</code> |
| 400 | `bad_request` | *(relayed at runtime: `parse_err.c_str()`)* |
| 503 | `ec_unavailable` | `EC roundtrip failed for DOWNLOAD_SEARCH_RESULT` |

**Notes**

- The body is entirely optional — a bare POST downloads under the default category.
- The daemon looks the hash up in its own search list; an unknown hash comes back as `400 amuled_rejected`.
- Matched before `/search/{id}`, so the literal `results` segment is reserved.

#### `GET, HEAD /api/v0/search/results/{hash}/comments`

Kad community ratings/comments retrieved for one search result.

| | |
|---|---|
| Handler | `HandleSearchComments` — `src/webapi/Api.cpp:10663-10727` |
| Auth | **GUEST** |
| Success | `200 OK` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of the result. |

**Query parameters**: none.

**Request body**: none.

**Response body**

```json
{
  "count": "int",
  "kad_comment_search_running": "bool",
  "comments": [
    {
      "username": "string",
      "filename": "string",
      "rating": "int",
      "comment": "string"
    }
  ]
}
```

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no search result with that hash` |

**Notes**

- `kad_comment_search_running` is true while a lookup started by the `POST` form is still in flight.

#### `POST /api/v0/search/results/{hash}/comments`

Trigger a Kad NOTES lookup for one search result.

| | |
|---|---|
| Handler | `HandleSearchCommentsKadSearch` — `src/webapi/Api.cpp:10733-10798` |
| Auth | **ADMIN** |
| Success | `202 Accepted` — `{"status": "kad_search_started"}` |
| Gates | first EC snapshot (`503 ec_unavailable`) |

**Path parameters**

| Name | Description |
|---|---|
| `hash` | 32-char hex MD4 of the result. |

**Query parameters**: none.

**Request body**: none.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 400 | `amuled_rejected` | *(relayed at runtime: `ec_err.c_str()`)* |
| 400 | `bad_request` | <code>`{hash}` must be a 32-char hex MD4</code> |
| 404 | `not_found` | `no search result with that hash` |
| 503 | `ec_unavailable` | `EC roundtrip failed for SEARCH_KAD_NOTES` |

### Server-sent events

#### `GET, HEAD /api/v0/events`

The push channel: one long-lived `text/event-stream` carrying every state change the refresher diffs. Diverted by the streaming resolver before the normal dispatcher ever runs.

| | |
|---|---|
| Handler | `DispatchEvents` — `src/webapi/Api.cpp:10876-11176` |
| Auth | **GUEST** |
| Success | `200 OK`, `Content-Type: text/event-stream` |

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `channels` | comma-separated list | Deliver only these channels: `downloads`, `shared`, `servers`, `clients`, `friends`, `status`, `logs`, `search`, `chats`, `comments`. Unknown names are ignored (forward compatibility); at most 32 unique tokens are kept. The synthetic `resync` event is always delivered. |

**Request body**: none.

**Response headers**: `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, plus the CORS bundle. Chunked transfer encoding.

**Frame format**

```
event: <name>
id: <monotonic uint64>
data: <single-line JSON>

```

The stream opens with `: connected`, and emits `: keepalive` whenever nothing
has been written for 15 s (wall-clock driven, so a busy bus behind a
`?channels=` filter still keeps the connection warm).

**Notes**

- Auth runs in `PreflightEvents` on the I/O thread, **before** a worker thread is spawned and before the 32-slot budget is claimed, so an unauthenticated peer gets an ordinary `401`/`429` and cannot hold a slot.
- The 33rd concurrent stream is refused by the HTTP layer with `503 sessions_exhausted` + `Retry-After: 10`.
- Reconnect: send `Last-Event-ID`. An id newer than the bus (daemon restarted) or older than its oldest retained event (gap) produces a `resync` frame carrying `{reason, since_id, newest_id}` — `restart` or `gap` — after which the client is expected to invalidate and re-GET the REST collections. Gaps are also detected mid-stream, not only at connect.
- The cursor advances over filtered-out events too, so a reconnect never re-delivers them; replay is id-based, not channel-based.
- Guest tokens are accepted: SSE is a read-only push.
- The path must match exactly — `/api/v0/events/` is **not** diverted and ends up a `404`. A non-GET/HEAD method is not diverted either, and since no route matches it, also `404` (there is no `405` here).
- No ETag layer and no `OPTIONS` short-circuit apply to this route.
- See [Appendix B](#appendix-b--sse-event-catalog) for the event names.

### Static assets and country flags

#### `GET, HEAD /flags/{code}.png`

A country flag PNG, for `<img src>` in a UI. Outside `/api/v0` on purpose, and unauthenticated.

| | |
|---|---|
| Handler | `ServeCountryFlag` — `src/webapi/Api.cpp:1863-1918` |
| Auth | **NONE** |
| Success | `200 OK` |

**Path parameters**

| Name | Description |
|---|---|
| `code` | Exactly two lowercase ASCII letters, or the literal `unknown`. Anything else → `404 not_found` / `no such flag`. |

**Query parameters**: none.

**Request body**: none.

**Response**: `image/png` bytes, `Cache-Control: public, max-age=86400`.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no such flag` |

**Notes**

- Matched as a path **prefix** (`/flags/`), before the static-file fallthrough, so the response is identical with or without a configured `StaticRoot`.
- Missing artwork answers the same opaque `404` as a bad code, so the icon set is not enumerable.

#### `GET, HEAD /{any non-/api/ path}`

The bundled Web UI. Any safe-method request whose path does not start with `/api/` falls through to the static root.

| | |
|---|---|
| Handler | `ServeStaticFile` — `src/webapi/Api.cpp:1716-1861` |
| Auth | **NONE** |
| Success | `200 OK` |

**Query parameters**: none.

**Request body**: none.

**Response**: the file's bytes with a content type derived from its
extension (`StaticContentType`), an mtime+size `ETag`, and its own `304` branch.

**Errors** (beyond the shared auth/rate-limit ones)

| Status | `code` | `message` |
|---|---|---|
| 404 | `not_found` | `no such endpoint` |
| 404 | `not_found` | `no such file` |

**Notes**

- Root comes from `StaticRoot` in `amuleapi.conf`, else `ResolveDefaultStaticDir()`; resolved once via `std::call_once`. An empty root answers `404 no such endpoint`.
- `/` and the empty path serve `index.html`.
- Containment is enforced by `webapi::ResolveWithinRoot` (`StaticFs.cpp`) — `realpath`/`_fullpath` plus a prefix and separator check, so a symlink out of the root is refused.
- SPA fallback: an unresolved path **without** a `.` re-serves `index.html`; a path with an extension is a `404 no such file`.
- The mtime+size `ETag` is the one clients see: the outer ETag layer steps aside whenever a handler set its own, so `GET` and `HEAD` on an asset report the same validator. The `If-None-Match` lookup is case-insensitive and takes `*`, a comma-separated list and weak `W/"…"` validators, and the token carries a coding suffix when the response would be gzipped.

#### `OPTIONS <any path>`

Not a route: `CApiDispatcher::Dispatch` answers any
`OPTIONS` carrying `Access-Control-Request-Method` with **`204 No Content`**
and the CORS preflight bundle, before authentication and before routing.

| | |
|---|---|
| Auth | **NONE** |
| Success | `204 No Content`, no body, no `Content-Type` |

Headers on an accepted origin: `Access-Control-Allow-Origin`,
`Access-Control-Allow-Credentials: true`,
`Access-Control-Allow-Methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS`,
`Access-Control-Allow-Headers: Authorization, Content-Type, If-None-Match, Last-Event-ID`,
`Access-Control-Max-Age: 86400`. A rejected origin gets `204` + `Vary: Origin` only.

An `OPTIONS` **without** `Access-Control-Request-Method` is not special-cased:
it falls into normal routing and ends in that route's `405` (or `404`).

---

## Appendix A — preferences field table

All 125 rows of the schema table in `src/webapi/PrefsSchema.cpp`,
in source order. This *is* the contract of `GET`/`PATCH /api/v0/preferences`:
the emitter and the patch walker both drive off this table.

Access levels: **ReadWrite** (emitted, applied) · **ReadOnly** (emitted, silently ignored on PATCH) · **WriteOnly** (never emitted, applied) · **Rejected** (never emitted, `400` if sent) · **Bespoke** (emitted, PATCH hand-written).

| Category | Key | JSON type | Access | Constraint / values | Notes |
|---|---|---|---|---|---|
| `general` | `check_new_version` | bool | ReadWrite |  |  |
| `general` | `local_host_name` | string | ReadOnly |  |  |
| `general` | `nickname` | string | ReadWrite |  |  |
| `general` | `user_hash` | string (md4 hex) | ReadOnly |  |  |
| `connection` | `autoconnect` | bool | ReadWrite |  |  |
| `connection` | `bind_address` | string | ReadWrite |  |  |
| `connection` | `bind_interface` | string | ReadWrite |  |  |
| `connection` | `extended_udp_port_enabled` | bool | ReadWrite |  | API value is the negation of the EC value |
| `connection` | `max_connections` | number (uint32) | ReadWrite | max `65535` |  |
| `connection` | `max_download_kbps` | number (uint32) | ReadWrite | max `1000000000` |  |
| `connection` | `max_sources_per_file` | number (uint32) | ReadWrite | max `65535` |  |
| `connection` | `max_upload_kbps` | number (uint32) | ReadWrite | max `1000000000` |  |
| `connection` | `network_ed2k` | bool | ReadWrite |  |  |
| `connection` | `network_kad` | bool | ReadWrite |  |  |
| `connection` | `proxy_auth` | bool | ReadWrite |  |  |
| `connection` | `proxy_enabled` | bool | ReadWrite |  |  |
| `connection` | `proxy_host` | string | ReadWrite |  |  |
| `connection` | `proxy_port` | number (uint16) | ReadWrite | max `65535` |  |
| `connection` | `proxy_type` | string (enum) | ReadWrite | `socks5`, `socks4`, `http`, `socks4a` |  |
| `connection` | `proxy_user` | string | ReadWrite |  |  |
| `connection` | `reconnect` | bool | ReadWrite |  |  |
| `connection` | `tcp_port` | number (uint16) | ReadWrite | max `65535` |  |
| `connection` | `udp_port` | number (uint16) | ReadWrite | max `65535` |  |
| `connection` | `upload_slot_kbps` | number (uint32) | ReadWrite | max `65535` |  |
| `connection` | `upnp_available` | bool | ReadOnly |  | tag read from another EC group |
| `connection` | `upnp_enabled` | bool | ReadWrite |  |  |
| `connection` | `upnp_tcp_port` | number (uint16) | ReadWrite | max `65535` |  |
| `connection` | `proxy_password` | string (write-only) | WriteOnly |  |  |
| `directories` | `auto_rescan` | bool | ReadWrite |  |  |
| `directories` | `exclude_patterns` | string | ReadWrite |  |  |
| `directories` | `exclude_patterns_use_regex` | bool | ReadWrite |  |  |
| `directories` | `follow_symlinks` | bool | ReadWrite |  |  |
| `directories` | `incoming` | string | ReadWrite |  |  |
| `directories` | `share_hidden` | bool | ReadWrite |  |  |
| `directories` | `shared` | array of strings | ReadWrite |  |  |
| `directories` | `temp` | string | ReadWrite |  |  |
| `files` | `add_new_downloads_paused` | bool | ReadWrite |  |  |
| `files` | `aich_trust_every_hash` | bool | ReadWrite |  |  |
| `files` | `create_sparse_files` | bool | ReadWrite |  | API value is the negation of the EC value |
| `files` | `endgame_enabled` | bool | ReadWrite |  |  |
| `files` | `ffprobe_path` | string | ReadWrite |  |  |
| `files` | `ich_enabled` | bool | ReadWrite |  |  |
| `files` | `media_metadata_enabled` | bool | ReadWrite |  |  |
| `files` | `min_free_space_mb` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `files` | `mmap_enabled` | bool | ReadWrite |  | gated by `mmap_supported` (else `409 conflict`) |
| `files` | `mmap_supported` | bool | ReadOnly |  |  |
| `files` | `new_downloads_auto_priority` | bool | ReadWrite |  |  |
| `files` | `new_shared_files_auto_priority` | bool | ReadWrite |  |  |
| `files` | `preallocate_full_file_size` | bool | ReadWrite |  |  |
| `files` | `prioritize_first_last_chunks` | bool | ReadWrite |  |  |
| `files` | `save_source_seeds_for_rare_files` | bool | ReadWrite |  |  |
| `files` | `start_next_alphabetical` | bool | ReadWrite |  |  |
| `files` | `start_next_paused` | bool | ReadWrite |  |  |
| `files` | `start_next_same_category` | bool | ReadWrite |  |  |
| `files` | `stop_on_low_disk_space` | bool | ReadWrite |  |  |
| `servers` | `auto_update` | bool | ReadWrite |  |  |
| `servers` | `autoconnect_static_servers_only` | bool | ReadWrite |  |  |
| `servers` | `dead_server_retries` | number (uint32) | ReadWrite | max `65535` |  |
| `servers` | `manual_servers_high_priority` | bool | ReadWrite |  |  |
| `servers` | `remove_dead` | bool | ReadWrite |  |  |
| `servers` | `safe_connect` | bool | ReadWrite |  |  |
| `servers` | `smart_id_check` | bool | ReadWrite |  |  |
| `servers` | `update_list_from_client` | bool | ReadWrite |  |  |
| `servers` | `update_list_from_server` | bool | ReadWrite |  |  |
| `servers` | `update_url` | string | ReadWrite |  |  |
| `servers` | `use_priority_system` | bool | ReadWrite |  |  |
| `security` | `ipfilter_auto_update` | bool | ReadWrite |  |  |
| `security` | `ipfilter_block_below_access_level` | number (uint32) | ReadWrite | max `255` |  |
| `security` | `ipfilter_clients` | bool | ReadWrite |  |  |
| `security` | `ipfilter_include_lan_ips` | bool | ReadWrite |  |  |
| `security` | `ipfilter_servers` | bool | ReadWrite |  |  |
| `security` | `ipfilter_update_url` | string | ReadWrite |  |  |
| `security` | `obfuscation_enabled` | bool | ReadWrite |  |  |
| `security` | `obfuscation_requested` | bool | ReadWrite |  |  |
| `security` | `obfuscation_required` | bool | ReadWrite |  |  |
| `security` | `reject_spoofed_source_ips` | bool | ReadWrite |  |  |
| `security` | `shared_files_visibility` | string (enum) | ReadWrite | `everybody`, `friends`, `nobody` |  |
| `security` | `use_secident` | bool | ReadWrite |  |  |
| `security` | `use_system_ipfilter` | bool | ReadWrite |  |  |
| `message_filter` | `accept_from_friends_only` | bool | ReadWrite |  |  |
| `message_filter` | `accept_from_known_clients_only` | bool | ReadWrite |  |  |
| `message_filter` | `by_keyword` | bool | ReadWrite |  |  |
| `message_filter` | `comment_keywords` | string | ReadWrite |  |  |
| `message_filter` | `enabled` | bool | ReadWrite |  |  |
| `message_filter` | `filter_all_messages` | bool | ReadWrite |  |  |
| `message_filter` | `filter_comments` | bool | ReadWrite |  |  |
| `message_filter` | `keywords` | string | ReadWrite |  |  |
| `message_filter` | `show_in_log` | bool | ReadWrite |  |  |
| `remote_controls.webserver` | `enabled` | bool | ReadWrite |  |  |
| `remote_controls.webserver` | `guest_enabled` | bool | Bespoke |  |  |
| `remote_controls.webserver` | `port` | number (uint32) | ReadWrite | max `65535` |  |
| `remote_controls.webserver` | `refresh_seconds` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `remote_controls.webserver` | `template` | string | ReadWrite |  |  |
| `remote_controls.webserver` | `use_gzip` | bool | ReadWrite |  |  |
| `remote_controls.webserver` | `password` | string (write-only, md4 hex) | WriteOnly |  |  |
| `remote_controls.amuleapi` | `bind_address` | string | ReadWrite |  |  |
| `remote_controls.amuleapi` | `enabled` | bool | ReadWrite |  |  |
| `remote_controls.amuleapi` | `port` | number (uint32) | ReadWrite | max `65535` |  |
| `remote_controls.amuleapi` | `password` | — | Rejected |  |  |
| `remote_controls.amuleapi` | `guest_password` | — | Rejected |  |  |
| `remote_controls.amuleapi` | `guest_enabled` | — | Rejected |  |  |
| `online_signature` | `directory` | string | ReadWrite |  |  |
| `online_signature` | `enabled` | bool | ReadWrite |  |  |
| `online_signature` | `update_frequency_seconds` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `file_buffer_bytes` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `kad_max_source_searches` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `kad_reask_ms` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `max_new_connections_per_5s` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `max_upload_queue_clients` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `server_keepalive_timeout_ms` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `source_reask_ms` | number (uint32) | ReadWrite | max `0xFFFFFFFF` |  |
| `core_tweaks` | `verbose_logging` | bool | ReadWrite |  |  |
| `kademlia` | `update_url` | string | ReadWrite |  |  |
| `ip2country` | `auto_update` | bool | ReadWrite |  |  |
| `ip2country` | `custom_url` | string | ReadWrite |  |  |
| `ip2country` | `db_loaded` | bool | ReadOnly |  |  |
| `ip2country` | `db_path` | string | ReadOnly |  |  |
| `ip2country` | `download_in_progress` | bool | ReadOnly |  |  |
| `ip2country` | `enabled` | bool | ReadWrite |  |  |
| `ip2country` | `last_update_result` | string | ReadOnly |  |  |
| `ip2country` | `loaded_source` | string | ReadOnly |  |  |
| `ip2country` | `maxmind_license` | string | ReadWrite |  |  |
| `ip2country` | `source` | string (enum) | ReadWrite | `dbip`, `maxmind`, `custom` |  |
| `ip2country` | `supported` | bool | ReadOnly |  |  |
| `ip2country` | `update_now` | bool (write-only trigger) | WriteOnly |  |  |

EC group per category (`kCategories`, `PrefsSchema.cpp`):

| Category | EC group tag |
|---|---|
| `general` | `EC_TAG_PREFS_GENERAL` |
| `connection` | `EC_TAG_PREFS_CONNECTIONS` |
| `directories` | `EC_TAG_PREFS_DIRECTORIES` |
| `files` | `EC_TAG_PREFS_FILES` |
| `servers` | `EC_TAG_PREFS_SERVERS` |
| `security` | `EC_TAG_PREFS_SECURITY` |
| `message_filter` | `EC_TAG_PREFS_MESSAGEFILTER` |
| `remote_controls.webserver` | `EC_TAG_PREFS_REMOTECTRL` |
| `remote_controls.amuleapi` | `EC_TAG_PREFS_REMOTECTRL` |
| `online_signature` | `EC_TAG_PREFS_ONLINESIG` |
| `core_tweaks` | `EC_TAG_PREFS_CORETWEAKS` |
| `kademlia` | `EC_TAG_PREFS_KADEMLIA` |
| `ip2country` | `EC_TAG_PREFS_IP2COUNTRY` |

---

## Appendix B — SSE event catalog

Names are what `event:` carries on `GET /api/v0/events`; the channel is the
prefix before the first `_`, mapped by the resolver in `DispatchEvents`
(`DispatchEvents`). Publishers: `EventDiff.cpp` (`EmitDiffsAndUpdate`,
`PublishChatEvents`) and the SSE handler itself for `resync`.

| Event | Channel (`?channels=`) | Payload | Source |
|---|---|---|---|
| `download_added` / `download_updated` | `downloads` | the `/downloads` list object | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `download_removed` | `downloads` | `{"hash": "…"}` | `EventDiff.cpp` |
| `shared_added` / `shared_updated` | `shared` | the `/shared` list object | `EventDiff.cpp` |
| `shared_removed` | `shared` | `{"hash": "…"}` | `EventDiff.cpp` |
| `comments_updated` | `comments` | the file's comment set | `EventDiff.cpp` |
| `server_added` / `server_updated` / `server_removed` | `servers` | server object / `{"ecid": N}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `client_added` / `client_updated` / `client_removed` | `clients` | client object / `{"ecid": N}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `friend_added` / `friend_updated` / `friend_removed` | `friends` | friend object / `{"ecid": N}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `status_changed` | `status` | the nested `GET /status` envelope | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `log_appended` | `logs` | the appended log lines | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `search_result_added` | `search` | one search result (same writer as `GET /search/{id}/results`) | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `search_progress` | `search` | `{search_id, state, kind, percent, result_count}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `search_closed` | `search` | `{search_id}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `chat_message` | `chats` | one chat message object | `PublishChatEvents`, `EventDiff.cpp` |
| `chat_session_closed` | `chats` | `{"peer": "<ip>:<port>"}` | `PublishChatEvents`, `EventDiff.cpp` |
| `resync` | *(always delivered)* | `{"reason": "gap" \| "restart", "since_id": N, "newest_id": N}` | `DispatchEvents`, `Api.cpp` |

`search_result_added` and `GET /search/{id}/results` share one serializer
(`webapi::WriteSearchResultFields`, `src/webapi/SearchJson.cpp`), so a row is
byte-identical whether it arrives by poll or by push.

---

## Appendix C — retired and shadowed paths

**Answered explicitly, for any method** (so the replacement can be named):

| Path | Status | Message |
|---|---|---|
| `/api/v0/search/results` | 404 `not_found` | `retired: results are addressed per search at GET /search/{id}/results` |
| `/api/v0/search/stop` | 404 `not_found` | `retired: use POST /search/{id}/stop, or DELETE /search/{id} to also free it` |

**Retired with no stub** — these are plain `404 no such endpoint`:

| Path | Replacement |
|---|---|
| `/api/v0/uploads` | `GET /api/v0/clients` (filter by `upload_state`, or `?filter=uploads`) |
| `/api/v0/kad/connect` | `POST /api/v0/networks/connect` with `{"network":"kad"}` |
| `/api/v0/kad/disconnect` | `POST /api/v0/networks/disconnect` with `{"network":"kad"}` |

**Retired in place** — the path still exists, the verb does not:

| Route | Behaviour |
|---|---|
| `GET /api/v0/downloads/{hash}/a4af` | `405` — read `a4af_auto` on the download detail object and the A4AF rows from `GET /downloads/{hash}/clients` |

**Shadowed captures.** A literal route is always matched before the capture
pattern that would otherwise swallow it, so these segment values are
unreachable as a `{hash}` / `{ecid}` / `{id}`:

| Capture | Unreachable values |
|---|---|
| `/shared/{hash}` | `media` (`POST /shared/media/refresh` is matched first) |
| `/servers/{ecid}` | `by-address` (the address-keyed routes are matched first) |
| `/search/{id}` | `results` (`/search/results/{hash}/…` is matched first) |
| `/clients/{ecid}` | `known_clients` is a sibling route matched earlier |

The collection actions that used to shadow `{hash}` / `{ecid}` were moved to
their own top-level paths and no longer do:

| Old path | Now |
|---|---|
| `POST /api/v0/downloads/clear_completed` | `POST /api/v0/downloads_clear_completed` |
| `POST /api/v0/shared/reload` | `POST /api/v0/shared_reload` |
| `/api/v0/shared/directories` (`GET`/`PUT`/`POST`/`DELETE`) | `/api/v0/share_directories` |
| `POST /api/v0/servers/update` | `POST /api/v0/servers_update` |
| `/api/v0/servers/{ecid}` with an `<ip>:<port>` capture | `/api/v0/servers/by-address/{address}` |

---

## Appendix D — sortable fields per list endpoint

`?sort=` is validated against the endpoint's comparator table; an unknown
value is `400` `` unknown `sort` field for this endpoint ``. Endpoints not
listed here take no `sort` at all.

| Endpoint | `sort` values | Comparator table |
|---|---|---|
| `GET /api/v0/downloads` | `name`, `progress`, `size`, `speed`, `status` | inline `kComps` in `HandleDownloads` |
| `GET /api/v0/clients` | `name`, `software` | `ClientComparators()` |
| `GET /api/v0/downloads/{hash}/clients` | `name`, `software` | `FileClientComparators()` — built from `ClientComparators()` |
| `GET /api/v0/shared/{hash}/clients` | `name`, `software` | same as above |
| `GET /api/v0/known_clients` | `first_seen`, `last_seen`, `name`, `sessions`, `software`, `total_downloaded`, `total_uploaded` | inline `kComps` in `HandleKnownClients` |
| `GET /api/v0/shared` | `name`, `size` | inline `kComps` in `HandleSharedList` |
| `GET /api/v0/servers` | `files`, `name`, `ping`, `users` | inline `kComps` in `HandleServers` |
| `GET /api/v0/friends` | `name`, `online` | inline `kComps` in `HandleFriends` |
| `GET /api/v0/chats` | `last_message_at`, `name` | inline `kComps` in `HandleChats` |
| `GET /api/v0/search/{id}/results` | `directory`, `name`, `rating`, `size`, `sources` | inline `kComps` in `HandleSearchResults` |
| `GET /api/v0/search` | `search_id`, `query`, `started_at`, `result_count` | `SearchListComparators()` |
| `GET /api/v0/categories` | `index`, `name` | `CategoryComparators()` |

Range and type validation for `limit` / `offset` and for the endpoint-specific
query parameters lives in the shared `ParseUintParam` / `ParseBoolParam`
helpers, so those `400 bad_request` rejections are not listed in the
per-endpoint error tables; the accepted range is stated in each parameter
table instead.

---

## How this document was produced

Five scripts in this directory (`issues/inventory/`) read `src/webapi` and emit
the mechanical parts of this file, so a regeneration cannot keep a stale
hand-written line:

```sh
cd issues/inventory
python3 scan.py facts.json && python3 routes.py routes.json \
  && python3 prefs.py prefs.json && python3 gendoc.py
```

| Script | What it extracts |
|---|---|
| `apiscan.py` | slices a C++ file into top-level function definitions. Comments and string-literal *contents* are blanked before brace counting, so a `{` inside a comment or a JSON literal cannot desync the depth tracking. |
| `routes.py` | the route table straight out of `CApiDispatcher::DispatchToHandler`: every `path == "…"` literal, every `ParsePattern("…")`, the methods compared against, the handler called, and the `405`/`404` texts. |
| `scan.py` | per function: every `ErrorResponse(...)` / `BadRequestPtr(...)` / `BulkErr(...)` (parsed with a paren- and quote-aware scanner, not a regex, so a `;` or `,` inside a message is safe), every `qmap.find("…")` query key, every `obj.find("…")` body field, the `ListComparators` sort keys, the auth/admin/snapshot gates, and a JSON response skeleton folded from the ordered `CJsonWriter` calls (recursing into the `Write*` helpers each handler invokes). |
| `prefs.py` | all 125 rows of the `PrefsSchema.cpp` data table — category, key, type, access, bounds, enum values, gates. |

`gendoc.py` joins that data with the per-endpoint prose and renders this file. It
also re-anchors every `File.cpp:NNN` reference in the prose to the function's
current line, and fails loudly if a route block in `DispatchToHandler` or a
`Handle*` function is not documented here.

Two limits worth knowing when reading the response skeletons:

- The fold walks writer calls linearly, so a key emitted inside an `if` shows up
  as if it were always present. Conditional keys are called out in the per-
  endpoint **Notes** (`media`, `parts`, the detail-only blocks, the omitted
  search-list fields).
- Types are the `CJsonWriter` method used (`ValueInt` → `int`,
  `ValueUInt` → `uint`, `ValueDouble` → `number`, `ValueRaw` → a pre-serialized
  fragment), not a JSON-Schema type.

Every `GET` route in this file was additionally executed against a running
`amuleapi` and the response compared against the extracted skeleton — all of them
except `GET /api/v0/chats/{peer}/messages`, which needs a live conversation with
a peer. That is how
the `/stats/graphs/{graph}` names in this document are `download_speed`,
`upload_speed`, `connections`, `kad_nodes` — a stale comment in `DispatchToHandler`
still calls them `download`/`upload`/`connections`/`kad`, and
`docs/api/REFERENCE.md` inherits other drift of the same kind.
