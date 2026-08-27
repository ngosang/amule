#!/usr/bin/env python3
"""Generate issues/API_INVENTORY.md from the scanned facts.

Inputs (all produced from src/webapi by the sibling scripts):
  facts.json  — per-function errors / params / body fields / response shapes
  routes.json — the route table lifted out of DispatchToHandler
  prefs.json  — the PrefsSchema.cpp data table

Everything mechanical (error tables, response skeletons, sort keys, the
preferences table) is rendered from those files, so a stale hand-written
line cannot survive a regeneration. The prose annotations live in EP below.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "facts.json")))
R = json.load(open(os.path.join(HERE, "routes.json")))
P = json.load(open(os.path.join(HERE, "prefs.json")))
FUN, SHAPE = F["funcs"], F["shapes"]

sys.path.insert(0, HERE)
import apiscan

# Full function index across every file the doc references, used to rewrite the
# hand-written `File.cpp:NNN` refs to wherever those functions live *now*.
ALLIDX = apiscan.index(["Api.cpp", "App.cpp", "HttpServer.cpp", "SearchJson.cpp",
                        "EventDiff.cpp", "StaticFs.cpp", "EventBus.cpp"])

REPO = os.path.dirname(os.path.dirname(HERE))
COMMIT = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
DIRTY = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "src/webapi"],
                       capture_output=True, text=True).stdout.strip()
TREE = (f"commit `{COMMIT}` plus the uncommitted `src/webapi` changes in the "
        f"working tree" if DIRTY else f"commit `{COMMIT}`")

out = []
def w(s=""):
    out.append(s)

def loc(fn):
    """`src/webapi/Api.cpp:1234-1300` for a function name."""
    if fn not in FUN:
        return "?"
    return ", ".join(f"`src/webapi/{l}`" for l in FUN[fn]["loc"])

def esc(s):
    return s.replace("|", "\\|")

def json_block(shape, title="Response body"):
    w(f"**{title}**")
    w()
    w("```json")
    w(json.dumps(shape, indent=2))
    w("```")
    w()

def csp(s):
    """Inline code span that survives a message containing backticks."""
    if "`" in s:
        return "<code>" + s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</code>"
    return f"`{s}`"


def err_table(rows):
    if not rows:
        return
    w("| Status | `code` | `message` |")
    w("|---|---|---|")
    for st, c, msg in rows:
        m = csp(esc(msg))
        if msg.endswith(".c_str()") or msg.endswith("_err") or msg.endswith("_msg") \
                or msg.startswith("("):
            m = f"*(relayed at runtime: {csp(esc(msg))})*"
        w(f"| {st} | `{c}` | {m} |")
    w()


def bulk_table(handlers):
    rows, seen = [], set()
    for h in handlers:
        for b in FUN.get(h, {}).get("bulk_errors", []):
            k = tuple(str(x) for x in b)
            if k not in seen:
                seen.add(k); rows.append(b)
    if not rows:
        return
    w("**Per-item errors** (inside `results[]`)")
    w()
    w("| `http` | `code` | `message` |")
    w("|---|---|---|")
    for st, c, msg in rows:
        m = csp(esc(str(msg)))
        if str(msg).endswith(("_err", "_msg", ".c_str()")):
            m = f"*(relayed at runtime: {csp(esc(str(msg)))})*"
        w(f"| {st} | `{c}` | {m} |")
    w()


def collect_errors(handlers):
    """Merged, de-duplicated error rows for a list of function names."""
    seen, rows = set(), []
    for h in handlers:
        for e in FUN.get(h, {}).get("errors", []):
            k = tuple(e)
            if k not in seen:
                seen.add(k); rows.append(e)
    rows.sort(key=lambda e: (e[0], e[1], e[2]))
    return rows

# ===================================================================
# Front matter and the cross-cutting behaviour every endpoint inherits
# ===================================================================
w(f"""# amuleapi — REST endpoint inventory (extracted from source)

Generated from `src/webapi` at {TREE} by the scripts described in
[How this document was produced](#how-this-document-was-produced). Every route,
query parameter, body field, response key and error below was lifted out of the
C++ sources — `src/webapi/Api.cpp`, `App.cpp`, `HttpServer.cpp`,
`SearchJson.cpp`, `PrefsSchema.cpp` — and not from `docs/api/REFERENCE.md`,
which is known to drift.

<!--COUNTS-->
""")

w("""## Contents

1. [Transport, routing and shared behaviour](#1-transport-routing-and-shared-behaviour)
2. [Authentication and authorization](#2-authentication-and-authorization)
3. [Shared envelopes](#3-shared-envelopes)
4. [Error catalog](#4-error-catalog)
5. [Endpoints](#5-endpoints)
<!--ENDPOINT-INDEX-->
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

Token transport (`AuthenticateRequest`, `Api.cpp:144-212`):
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

`RequireSnapshot` (`Api.cpp:234`) answers `503 ec_unavailable` until the
first EC snapshot from `amuled` has been received; it guards every handler
that reads cached daemon state.

---

## 3. Shared envelopes

### Error envelope

Produced by `ErrorResponse` (`Api.cpp:114`) — signature `ErrorResponse(status, code, message)`:

```json
{ "error": { "code": "bad_request", "message": "…" } }
```

### List envelope and pagination

Every list endpoint goes through `ListResponse` / `ListResponseFromPtrsUnlocked`
(`ListResponse` / `ListResponseFromPtrsUnlocked`, `Api.cpp`) and answers:

```json
{ "<plural_key>": [ … ], "total": 0, "offset": 0, "limit": 0 }
```

`total` is the pre-slice count; `limit` always echoes the effective page size —
the requested `limit`, or the default 100 when none was sent. `WritePageMeta`,

Shared query parameters (`ParseListParams`, `Api.cpp:2999`) on those
endpoints:

| Param | Type | Rules |
|---|---|---|
| `limit` | integer | 0–1000000000; default **100** when absent (out-of-range is rejected, not clamped); bad value → `400` `` `limit` must be an integer between 0 and 1000000000`` |
| `offset` | integer | 0–1000000000; bad value → `400` `` `offset` must be an integer between 0 and 1000000000`` |
| `after` | string | Keyset anchor: return rows after this value of the identity `sort` column. Ascending only — rejected with `order=desc`; needs a `sort` field that identifies a row, else `400`. |
| `sort` | string | must be one of the endpoint's sortable fields ([Appendix D](#appendix-d--sortable-fields-per-list-endpoint)); unknown → `400` ``unknown `sort` field for this endpoint`` |
| `order` | `asc` \\| `desc` | anything else → `400` `` `order` must be "asc" or "desc"`` |

Sorting is a stable sort over the whole set, then the window is sliced.

### Bulk mutation envelope

Five routes answer with a per-item result list (`BulkResultsResponse`,
`Api.cpp:4153`): `POST /downloads`, `PATCH /downloads`, `DELETE /downloads`,
`PATCH /shared` and `POST /downloads_clear_completed` (one `{id, ok}` per cleared
hash). The `/share_directories` writes have their own shape: they answer with the
applied root list, `{directories: [{path, recursive}]}`.

```json
{ "results": [ { "id": "<hash|link>", "ok": true },
               { "id": "…", "ok": false,
                 "error": { "code": "not_found", "message": "…" } } ] }
```

Aggregate HTTP status: all items OK → the route's success status; every item
`503` → `503`; any other mixture → **`207 Multi-Status`**. `hashes` arrays are
parsed by `ParseBulkHashes` (`Api.cpp:4200`): 1–500 entries, each a 32-char
hex string.

### Mutation flow

Every mutating handler follows the same seven steps (comment at
`Api.cpp`): authenticate → require admin → parse the JSON body →
send the EC packet through `SendRecvSerialized` → `EC_OP_NOOP` means success
and `EC_OP_FAILED` carries `amuled`'s rejection (surfaced as
`400 amuled_rejected`) → run a `RefresherTick` inline so the response
reflects post-mutation state → return the updated resource, `201`, or `204`.

---
""")

# ===================================================================
# Section 4 — error catalog, aggregated over every handler
# ===================================================================
w("## 4. Error catalog")
w()
w("Every `(status, code)` pair emitted anywhere in `Api.cpp`, counted over all")
w("handlers, plus the pairs produced below the dispatcher by the HTTP layer.")
w()
from collections import Counter
pairs = Counter()
for n, v in FUN.items():
    for st, code, _ in v["errors"]:
        pairs[(st, code)] += 1
w("| Status | `code` | Distinct messages | Meaning |")
w("|---|---|---|---|")
MEANING = {
    (400, "bad_request"): "malformed path, query, body or field value",
    (400, "amuled_rejected"): "`amuled` refused the EC mutation (`EC_OP_FAILED`); its message is relayed",
    (405, "method_not_allowed"): "the path exists, the method does not; the response carries an `Allow` header (`MethodNotAllowed`, one site, one message per route)",
    (401, "unauthorized"): "missing / invalid / expired / revoked token",
    (401, "invalid_credentials"): "login password matched no configured role",
    (403, "forbidden"): "`RequireAdmin` — admin role required",
    (403, "invalid_credentials"): "`current_password` did not match on a password change",
    (404, "not_found"): "no such route, file, peer, server, category or search",
    (409, "conflict"): "state conflict (A4AF loop, gated preference)",
    (409, "not_shared"): "comment/rating attempted on a non-shared file",
    (409, "not_completed"): "single clear-completed on a file that is not completed",
    (409, "completed_use_clear_completed"): "delete attempted on a completed download",
    (409, "partfile_unsupported"): "verify attempted on a partfile",
    (409, "kad_more_exhausted"): "`/search/{id}/more` on a Kad search with nothing left",
    (409, "update_check_unavailable"): "version check disabled or unavailable",
    (429, "rate_limited"): "per-IP auth / login failure lockout (`Retry-After`)",
    (429, "update_check_throttled"): "version check asked for again too soon",
    (500, "internal_error"): "hash decode / serialization failure inside a handler",
    (502, "amuled_rejected"): "the daemon answered but the reply was unusable (no `search_id` for a search/browse, shared-directory apply refused)",
    (502, "bad_gateway"): "unparseable EC payload from `amuled`",
    (503, "ec_unavailable"): "no first EC snapshot yet, or the EC roundtrip failed",
    (503, "ec_unsupported"): "the connected `amuled` is too old for this feature",
    (503, "login_disabled"): "no admin/guest password configured",
}
for (st, ecode), cnt in sorted(pairs.items()):
    w(f"| {st} | `{ecode}` | {cnt} | {MEANING.get((st, ecode), '')} |")
w()
w("Produced by the HTTP layer, below the dispatcher:")
w()
w("| Status | `code` | When | Source |")
w("|---|---|---|---|")
w("| 500 | `internal` | a handler threw | `HttpServer.cpp`, session dispatch `catch` |")
w("| 503 | `sessions_exhausted` | 33rd concurrent SSE session; `Retry-After: 10` | `HttpServer.cpp`, `WriteCapRefusal` |")
w("| — | — | body > 1 MiB, headers > 16 KiB, or a 10 s read timeout: the connection is closed with no response | `HttpServer.cpp` |")
w()
w("Bulk per-item `error.code` values (inside `results[]`, not the envelope):")
w("`ec_unavailable`, `amuled_rejected`, `not_found`, `internal_error`,")
w("`completed_use_clear_completed`.")
w()
w("---")
w()

# ===================================================================
# Section 5 — endpoints
# ===================================================================
LIST_Q = {"limit", "offset", "sort", "order"}
BY_ADDRESS_NOTE = (
    "Its own path rather than a `<ip>:<port>` value in the `{ecid}` capture. "
    "One capture with two identity domains, disambiguated by sniffing for a "
    "colon, is a dispatch rule invisible from outside — and it forecloses ever "
    "accepting an IPv6 literal, which is all colons. The handler resolves the "
    "address to an ECID and delegates to the ECID-keyed one, so the response is "
    "identical.")
COVERED = set()

def role_of(handler, override=None):
    if override:
        return override
    v = FUN.get(handler, {})
    return "ADMIN" if v.get("admin") else ("GUEST" if v.get("auth") else "NONE")

def ep(method, path, handler, summary, *, auth=None, success="`200 OK`",
       path_params=(), query=(), body=None, resp=None, errors_from=(),
       notes=(), list_env=None, shape_from=None, no_auto_errors=False):
    """Render one endpoint section."""
    COVERED.add(handler)
    for h in errors_from:
        COVERED.add(h)
    w(f"#### `{method} {path}`")
    w()
    w(summary)
    w()
    hs = [handler] + list(errors_from)
    v = FUN.get(handler, {})
    gates = []
    # `ListResponse` runs the first-snapshot gate itself, so a list handler
    # enforces it without naming it in its own body.
    if v.get("snapshot_gate") or "ListResponse" in v.get("calls", []):
        gates.append("first EC snapshot (`503 ec_unavailable`)")
    if v.get("json_body") or any(FUN.get(h, {}).get("json_body") for h in errors_from):
        gates.append("JSON object body, nesting ≤ 32 (`400 bad_request`)")
    if v.get("list_params"):
        gates.append("shared list params (`limit`/`offset`/`sort`/`order`)")
    w("| | |")
    w("|---|---|")
    w(f"| Handler | `{handler}` — {loc(handler)} |")
    w(f"| Auth | **{role_of(handler, auth)}** |")
    w(f"| Success | {success} |")
    if gates:
        w(f"| Gates | {'; '.join(gates)} |")
    w()
    if path_params:
        w("**Path parameters**")
        w()
        w("| Name | Description |")
        w("|---|---|")
        for n, d in path_params:
            w(f"| `{n}` | {d} |")
        w()
    auto_q = sorted(set(v.get("query", [])) - LIST_Q)
    if query or auto_q or v.get("list_params"):
        w("**Query parameters**")
        w()
        w("| Name | Type | Description |")
        w("|---|---|---|")
        for n, t, d in query:
            w(f"| `{n}` | {t} | {d} |")
        documented = {n for n, _, _ in query}
        for n in auto_q:
            if n not in documented:
                w(f"| `{n}` | — | *(undocumented — found in source)* |")
        if v.get("list_params"):
            sk = v.get("sort_keys") or []
            extra = f" `sort` accepts: {', '.join('`' + s + '`' for s in sk)}." if sk else ""
            w(f"| `limit`, `offset`, `sort`, `order` | see [list envelope](#list-envelope-and-pagination) | Standard pagination/sorting.{extra} |")
        w()
    else:
        w("**Query parameters**: none.")
        w()
    if body is None:
        w("**Request body**: none.")
        w()
    else:
        w("**Request body**")
        w()
        if isinstance(body, str):
            w(body)
        else:
            w("| Field | Type | Required | Description |")
            w("|---|---|---|---|")
            for f_ in body:
                w("| `%s` | %s | %s | %s |" % f_)
        w()
        found = set(v.get("body_fields", []))
        for h in errors_from:
            found |= set(FUN.get(h, {}).get("body_fields", []))
        if not isinstance(body, str):
            documented = {f_[0].split('.')[0].strip('`') for f_ in body}
            missing = sorted(x for x in found if x not in documented)
            if missing:
                w(f"*Fields seen in source but not described above: {', '.join('`' + m + '`' for m in missing)}.*")
                w()
    if resp is not None:
        if isinstance(resp, str):
            w(resp)
            w()
        else:
            json_block(resp)
    elif shape_from or list_env:
        if list_env:
            key, writer = list_env
            shape = {key: [SHAPE.get(writer, {})], "total": "uint", "offset": "uint", "limit": "uint"}
        else:
            shape = SHAPE.get(shape_from, {})
        json_block(shape)
    rows = [] if no_auto_errors else collect_errors(hs)
    if rows:
        w("**Errors** (beyond the shared auth/rate-limit ones)")
        w()
        err_table(rows)
    bulk_table(hs)
    if notes:
        w("**Notes**")
        w()
        for n in notes:
            w(f"- {n}")
        w()

def group(title):
    w(f"### {title}")
    w()

w("## 5. Endpoints")
w()
w("Every route the server answers, in resource order. `Auth` is the level the")
w("handler enforces (see [§2](#2-authentication-and-authorization)); the shared")
w("`401` / `403` / `429` rows are not repeated per endpoint.")
w()

# ------------------------------------------------------------------ System
group("System")

ep("GET, HEAD", "/api/v0/health", "HandleHealth",
   "Liveness / readiness probe. Answers `200` as long as the HTTP server is "
   "up, whatever the state of the EC link.",
   auth="NONE",
   shape_from="HandleHealth",
   notes=["`status` is the constant `\"ok\"` — reaching the handler at all is "
          "what it reports. Readiness is `ec_connected` (EC link up) and "
          "`snapshot` (a first daemon snapshot has landed): both true is when "
          "the state-reading endpoints stop answering `503 ec_unavailable`.",
          "Takes no auth gate and no snapshot gate, so it is usable from a "
          "container/orchestrator probe that holds no token.",
          "`GET /api/v0/version` used to be pressed into this role; this route "
          "owns it now."])

ep("GET, HEAD", "/api/v0/version", "HandleVersion",
   "Daemon and API version, plus — for an authenticated caller — the daemon's "
   "new-version check state.",
   auth="NONE for the identity fields, GUEST for `update`",
   shape_from="HandleVersion",
   notes=[
       "Auth is **optional**, which is why the handler does not call "
       "`Authenticate` unconditionally: version negotiation has to work before "
       "anyone holds a token. A request with no credential is the documented "
       "unauthenticated use and is not counted against the generic 401 "
       "limiter; a credential that *is* presented and rejected still counts.",
       "`update` is emitted **only** when the caller authenticated — whether "
       "this daemon runs an outdated build is not something an anonymous "
       "caller on a reachable interface should learn. Clients must treat the "
       "key as optional.",
       "Inside `update`: `latest_version` / `update_available` / `last_checked` "
       "reflect what the daemon last learned, and are null until a check has "
       "completed; `check_enabled` mirrors the `general.check_new_version` "
       "preference and the daemon's own capability.",
       "`amule_version` is the aMule version string, `daemon_version` the "
       "connected `amuled`'s.",
   ])

ep("POST", "/api/v0/version/check", "HandleVersionCheck",
   "Ask the daemon to run its new-version check now. Asynchronous: the result "
   "lands on a later `GET /api/v0/version`.",
   success="`202 Accepted` — no body",
   notes=["Gated on the daemon reporting the check as available *and* "
          "`general.check_new_version` being on; otherwise `409 update_check_unavailable`.",
          "The daemon's own throttle surfaces as `429 update_check_throttled`; the "
          "daemon's localized message is deliberately not relayed."])

# ------------------------------------------------------------------ Auth
group("Authentication")

ep("POST", "/api/v0/auth/login", "HandleLogin",
   "Exchange a password for a session. The response always sets the "
   "`amuleapi_token` cookie; the JWT is only echoed in the body for bearer clients.",
   query=[("type", "`bearer`", "Opt into the bearer shape (also triggered by "
           "`Accept: application/jwt`). `BeginSession`, `Api.cpp:1836`")],
   body=[("password", "string", "yes", "Plain password; matched against the admin "
          "record first, then the guest record.")],
   resp="""**Response body** — cookie shape (default), plus `token` and `jti` when the
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

Headers: `Set-Cookie: amuleapi_token=<jwt>; HttpOnly; SameSite=Strict; Path=/api/v0; Max-Age=<lifetime>`.""",
   errors_from=["ParseJsonObjectBody"],
   notes=["Password failures are counted by the dedicated login limiter "
          "(`[Auth] Login*` config); a lockout answers `429 rate_limited` with "
          "`Retry-After`. A *misconfiguration* (`no password configured at all`) "
          "answers `503 login_disabled` and does **not** count as a failure.",
          "The comparison runs over the MD5 of the plain password, then the "
          "stored PBKDF2 record; a record predating the current KDF cost is "
          "upgraded in place on a successful login."])

ep("POST", "/api/v0/auth/logout", "HandleLogout",
   "Revoke the calling session's `jti` and clear the cookie.",
   success="`204 No Content`",
   resp="""**Response body**: none.

Headers: a `Set-Cookie` that expires `amuleapi_token`.""",
   notes=["Deliberately soft: it extracts the bearer/cookie token itself instead "
          "of calling `Authenticate`, and an already-revoked or expired token "
          "still gets `204` — logging out twice is not an error.",
          "Repeated `401`s here still feed the generic per-IP auth limiter."])

ep("GET, HEAD", "/api/v0/auth/session", "HandleSession",
   "Describe the calling token: role, `jti`, and expiry.",
   shape_from="HandleSession")

ep("GET, HEAD", "/api/v0/auth/passwords", "HandleAuthPasswords",
   "Whether an admin password is set and whether the guest role is enabled. "
   "No password material is ever returned.",
   shape_from="HandleAuthPasswords")

ep("PATCH", "/api/v0/auth/passwords", "HandleAuthPasswordsPatch",
   "Change the admin and/or guest password, or enable/disable the guest role.",
   body=[("current_password", "string", "yes", "Must be the current **admin** password."),
         ("admin_password", "string", "no", "New admin password. Cannot be empty — "
          "the admin role cannot be removed."),
         ("guest_password", "string", "no", "New guest password. Setting it implies "
          "`guest_enabled: true` unless `guest_enabled` says otherwise."),
         ("guest_enabled", "bool", "no", "Enable/disable the guest role.")],
   resp="""**Response body** — the post-change state plus a freshly issued session
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
```""",
   errors_from=["ParseJsonObjectBody"],
   notes=["Writing the credential file invalidates every token issued before it. "
          "The caller is re-issued in the same response, so the operator who "
          "changed the password stays signed in and everybody else is signed out.",
          "A wrong `current_password` is `403 invalid_credentials` and counts "
          "against the login rate limiter.",
          "`guest_password` together with `guest_enabled: false` is rejected "
          "rather than guessed at; a body that changes nothing is `400 nothing to change`.",
          "The credential store lives outside `/preferences`: sending "
          "`remote_controls.amuleapi` passwords there is rejected on purpose."])

# ------------------------------------------------------------------ Status
group("Status and networks")

STATUS = dict(SHAPE["HandleStatus"])
STATUS["disk"] = {"temp_free_bytes": "int | null", "incoming_free_bytes": "int | null"}

ep("GET, HEAD", "/api/v0/status", "HandleStatus",
   "The dashboard rollup: ed2k/Kad connection state, transfer counters, queue "
   "sizes, and the daemon/EC health flags. Same nested shape the `status_changed` "
   "SSE event carries.",
   resp=STATUS,
   notes=["Built from one `Dashboard()` acquisition, so every counter in the "
          "response is from the same snapshot.",
          "The `kad.network` sub-object is byte-identical to the one on "
          "`GET /api/v0/kad` — one writer, `WriteKadNetworkObject`, `Api.cpp:619`.",
          "`disk.*_free_bytes` is `null` (not `-1`, not `0`) when the daemon could "
          "not determine free space.",
          "`ed2k.public_ip` is an empty string until a high ID is obtained."])

ep("GET, HEAD", "/api/v0/kad", "HandleKad",
   "Kademlia state: node id, firewall status, bucket/contact counters and the "
   "network rollup.",
   shape_from="HandleKad")

ep("POST", "/api/v0/networks/connect", "HandleNetworksConnect",
   "Connect ed2k, Kad, or both.",
   success="`202 Accepted` — `{\"message\": \"…\"}` (the daemon's status message, "
   "omitted when it returns none)",
   body=[("network", "`ed2k` \\| `kad` \\| `both`", "no", "Default `both`. "
          "`ed2k` → `EC_OP_SERVER_CONNECT`, `kad` → `EC_OP_KAD_START`, "
          "`both` → `EC_OP_CONNECT`.")],
   errors_from=["SimpleConnControlOp", "ParseJsonObjectBody"],
   notes=["The body is optional — an empty body means `both`.",
          "`/api/v0/kad/connect` and `/api/v0/kad/disconnect` were retired in "
          "favour of this route with `{\"network\":\"kad\"}`."])

ep("POST", "/api/v0/networks/disconnect", "HandleNetworksDisconnect",
   "Disconnect ed2k, Kad, or both.",
   success="`200 OK` — `{\"message\": \"…\"}` (the daemon's status message, "
   "omitted when empty)",
   body=[("network", "`ed2k` \\| `kad` \\| `both`", "no", "Default `both`.")],
   errors_from=["SimpleConnControlOp", "ParseJsonObjectBody"])

ep("POST", "/api/v0/kad/bootstrap", "HandleKadBootstrap",
   "Bootstrap Kad from one known contact.",
   success="`202 Accepted` — `{\"ip\": \"<dotted-quad>\", \"port\": <int>}` "
   "(echoes the parsed contact)",
   body=[("ip", "string \\| number", "yes", "Dotted-quad IPv4, or a host-order uint32."),
         ("port", "number", "yes", "0–65535.")],
   errors_from=["ParseJsonObjectBody"])

ep("POST", "/api/v0/kad/update", "HandleKadUpdateFromUrl",
   "Tell the daemon to fetch `nodes.dat` from a URL.",
   success="`202 Accepted` — no body",
   body=[("nodes_url", "string", "no", "`http://` or `https://` URL. When omitted, "
          "the configured `kademlia.nodes_url` preference is used; if no "
          "preference snapshot exists yet, that fallback is a `503`.")],
   errors_from=["ResolveFetchUrl", "UrlFetchOp"],
   notes=["`amuled` persists the URL into the matching preference itself, so this "
          "route does not also PATCH `/preferences`.",
          "Shares `ResolveFetchUrl` / `UrlFetchOp` with `POST /servers_update` and "
          "`POST /ipfilter/update`."])

ep("POST", "/api/v0/ipfilter/reload", "HandleIpfilterReload",
   "Reload the IP filter from disk (the Security page's *Reload List*).",
   success="`202 Accepted` — `{\"message\": \"…\"}` (the daemon's status message, "
   "omitted when empty)",
   errors_from=["SimpleConnControlOp"])

ep("POST", "/api/v0/ipfilter/update", "HandleIpfilterUpdate",
   "Fetch an IP-filter list from a URL (the Security page's *Update now*).",
   success="`202 Accepted` — no body",
   body=[("ipfilter_url", "string", "no", "`http://` or `https://` URL; falls back "
          "to the `security.ipfilter_update_url` preference when omitted.")],
   errors_from=["ResolveFetchUrl", "UrlFetchOp"])

# ------------------------------------------------------------------ Downloads
group("Downloads")

DL_DETAIL_ONLY = ["last_seen_complete", "last_changed", "download_active_time",
                  "available_part_count", "part_count", "remaining_time",
                  "lost_to_corruption", "gained_by_compression", "saved_by_ich",
                  "aich_hash", "met_file", "path", "partmet_id", "queued_count",
                  "comment", "rating", "a4af_auto", "media"]
DL_FULL = dict(SHAPE["WriteDownloadObject"])
DL_FULL["progress"] = {"percent": "number",
                       "parts": [{"state": "complete | incomplete | missing", "sources": "int"}]}
DL_LIST = {k: v for k, v in DL_FULL.items() if k not in DL_DETAIL_ONLY}
DL_LIST["progress"] = {"percent": "number"}

ep("GET, HEAD", "/api/v0/downloads", "HandleDownloads",
   "The transfer queue. Completed entries are filtered out by default.",
   query=[("status", "`active` \\| `all` \\| `completed`", "Which part of the queue "
           "to list. `active` (default) hides completed entries; `completed` shows "
           "only those (they live in the daemon's *awaiting clear* list); `all` "
           "shows both. Any other value is a `400`. The retired `include_completed` "
           "flag is rejected with a `400` naming this replacement.")],
   resp={"downloads": [DL_LIST], "total": "uint", "offset": "uint", "limit": "uint"},
   notes=["List rows omit `progress.parts` and the detail-only fields; read "
          "`GET /api/v0/downloads/{hash}` for those.",
          "`hashing_progress` and `kad_comment_search_running` *are* on the list "
          "row — deliberately, so a client can render a hashing indicator without "
          "a per-file roundtrip."])

ep("POST", "/api/v0/downloads", "HandleDownloadAdd",
   "Add one or more ed2k links.",
   success="`202 Accepted` (bulk envelope; `207` on a mixed result, `503` when every item failed)",
   body=[("links", "array of strings", "yes", "One or more `ed2k://` links; at "
          "least one entry. A single link is `{\"links\": [\"ed2k://...\"]}` — the "
          "old singular `ed2k_link` is rejected with a `400`."),
         ("category", "number", "no", "Category index, 0–255. Default 0.")],
   resp="""**Response body** — the [bulk envelope](#bulk-mutation-envelope); `id` is
the submitted link.""",
   errors_from=["ParseJsonObjectBody"],
   notes=["The partfile is allocated and hashed asynchronously by `amuled`, so a "
          "just-added link may take one or two refresher ticks to appear in "
          "`GET /downloads`."])

ep("PATCH", "/api/v0/downloads", "HandleDownloadsBulkPatch",
   "Apply the same status / priority / category change to many downloads.",
   success="`200 OK` (bulk envelope; `207` mixed, `503` all-failed)",
   body=[("hashes", "array of strings", "yes", "1–500 lowercase 32-char hex MD4 hashes."),
         ("status", "`paused` \\| `resumed` \\| `stopped`", "no", "At least one of "
          "`status`, `priority`, `category` is required."),
         ("priority", "`low` \\| `normal` \\| `high` \\| `auto`", "no", "Download priorities only — "
          "`very_low` and `release` are upload-side levels and are rejected here."),
         ("category", "number", "no", "0–255.")],
   resp="""**Response body** — the [bulk envelope](#bulk-mutation-envelope); `id` is
the hash.""",
   errors_from=["ParseBulkHashes", "ParseJsonObjectBody"],
   notes=["The patch is validated once for the whole batch: a malformed field is a "
          "`400` for the entire request, while per-hash problems (unknown hash, "
          "daemon rejection) come back per item.",
          "Ops are applied in a fixed order — status, then priority, then category "
          "— regardless of JSON key order."])

ep("DELETE", "/api/v0/downloads", "HandleDownloadsBulkDelete",
   "Cancel and remove many active downloads.",
   success="`200 OK` (bulk envelope)",
   body=[("hashes", "array of strings", "yes", "1–500 hex MD4 hashes.")],
   resp="""**Response body** — the [bulk envelope](#bulk-mutation-envelope).""",
   errors_from=["ParseBulkHashes", "ParseJsonObjectBody"],
   notes=["A `completed` entry is refused per item with "
          "`409 completed_use_clear_completed` — use "
          "`POST /api/v0/downloads_clear_completed` for those."])

ep("POST", "/api/v0/downloads_clear_completed", "HandleDownloadsClearCompleted",
   "Acknowledge completed downloads so the daemon drops them from its "
   "*awaiting clear* staging list. Does **not** delete anything from disk.",
   body=[("hash", "string", "no", "Clear one entry. Omit the body (or the field) to "
          "clear every completed entry in one EC roundtrip.")],
   resp="""**Response body** — the [bulk envelope](#bulk-mutation-envelope); `id` is
the cleared hash. An empty completed list is a `200` with an empty `results`
array, so a no-op stays distinguishable from a daemon rejection.""",
   errors_from=["ParseJsonObjectBody"],
   notes=["Unknown body keys are ignored on purpose, so adding a flag later cannot "
          "break older clients.",
          "A top-level path, not `/downloads/clear_completed`: an action on the "
          "collection is not a member of it, and the old spelling shadowed the "
          "`{hash}` capture."])

ep("GET, HEAD", "/api/v0/downloads/{hash}", "HandleDownloadDetail",
   "One download, with the per-part bitmap and every detail-only field.",
   path_params=[("hash", "32-char hex MD4. Case-insensitive — canonicalised to "
                 "lowercase by `LowerHexKey`, `Api.cpp:246`.")],
   resp=DL_FULL,
   notes=["`remaining_time` is `-1` when the file is not moving (`speed_bps == 0`).",
          "`media` is present only for a file `ffprobe` has produced metadata for.",
          "`parts[].state` is `complete` / `incomplete` / `missing`; the array is "
          "empty for a zero-byte file.",
          "Unlike `GET /downloads`, this endpoint answers for a completed download too."])

ep("PATCH", "/api/v0/downloads/{hash}", "HandleDownloadPatch",
   "Change one download: pause/resume/stop, priority, category, comment+rating, "
   "or rename.",
   path_params=[("hash", "32-char hex MD4.")],
   body=[("status", "`paused` \\| `resumed` \\| `stopped`", "no", ""),
         ("priority", "`low` \\| `normal` \\| `high` \\| `auto`", "no", "Download priorities only — "
          "`very_low` and `release` are upload-side levels and are rejected here "
          "(`FilePriorityToCode`, `Api.cpp:3710`, domain `kPrioDownload`)."),
         ("category", "number", "no", "0–255."),
         ("comment", "string", "with `rating`", "≤ 50 characters. Only settable on a "
          "file that is *shared* (a partfile with at least one complete chunk)."),
         ("rating", "number", "with `comment`", "Integer 0–5."),
         ("name", "string", "no", "Rename; must be non-empty and contain no path separators.")],
   resp=DL_LIST,
   errors_from=["TrySetCommentRating", "TryRename", "ParseJsonObjectBody"],
   notes=["At least one field is required; a body that changes nothing is a `400`.",
          "Fields are applied in a fixed order (status, priority, category, "
          "comment+rating, name), each as its own EC mutation — a later failure "
          "leaves the earlier ones applied.",
          "The response is the list-shaped object (no `parts`, no detail fields), "
          "re-read after an inline refresher tick."])

ep("DELETE", "/api/v0/downloads/{hash}", "HandleDownloadDelete",
   "Cancel and remove one active download (partfile deleted by the daemon).",
   success="`204 No Content`",
   path_params=[("hash", "32-char hex MD4.")],
   resp="""**Response body**: none.""",
   notes=["A `completed` entry is refused with `409 completed_use_clear_completed`: "
          "the only EC op that touches the completed staging list is "
          "`EC_OP_CLEAR_COMPLETED`, and it does not delete the file from `Incoming`."])

ep("GET, HEAD", "/api/v0/downloads/{hash}/comments", "HandleDownloadComments",
   "Comments and ratings reported by the file's sources, plus any Kad notes "
   "retrieved so far.",
   path_params=[("hash", "32-char hex MD4.")],
   shape_from="HandleDownloadComments",
   notes=["`kad_comment_search_running` is true while an on-demand Kad NOTES "
          "lookup is in flight — poll until it flips back to false."])

ep("POST", "/api/v0/downloads/{hash}/comments", "HandleDownloadCommentsKadSearch",
   "Trigger an on-demand Kad NOTES lookup for this file.",
   success="`202 Accepted` — no body",
   path_params=[("hash", "32-char hex MD4.")],
   notes=["Admin-only even though it reads: it drives an unbounded Kad lookup on "
          "the daemon (~45 s).",
          "Results appear on a subsequent `GET` of the same path."])

ep("GET, HEAD", "/api/v0/downloads/{hash}/filenames", "HandleDownloadFilenames",
   "The filenames this file's sources report, with how many sources use each — "
   "the desktop's *Filenames* tab.",
   path_params=[("hash", "32-char hex MD4.")],
   shape_from="HandleDownloadFilenames")

ep("GET, HEAD", "/api/v0/downloads/{hash}/clients", "HandleFileClients",
   "The peers related to this download: sources, peers pulling it from us, and "
   "A4AF sources.",
   path_params=[("hash", "32-char hex MD4 of a **download**.")],
   query=[("include_parts", "`true` \\| `false`", "Include each peer's per-part "
           "bitmap for this file. Anything else is a `400`. Default `false`.")],
   list_env=("clients", "WriteFileClientRow"),
   notes=["Same handler as `GET /api/v0/shared/{hash}/clients`, with "
          "`require_downloading = true` — the hash must name a download here and a "
          "shared file there.",
          "`role` is `source` / `peer` / `both` / `none`, and `a4af` marks a row "
          "that is an A4AF source of this file.",
          "Which bitmap a row carries follows its direction: the download bitmap "
          "for a source, the upload bitmap for a peer; a pure A4AF row has none.",
          "Sortable fields come from `ClientComparators` (`Api.cpp:2975`), so they "
          "match `GET /clients`: `name`, `software`."])

ep("POST", "/api/v0/downloads/{hash}/a4af", "HandleDownloadA4afAction",
   "Swap A4AF (*asked for another file*) sources between this file and its "
   "siblings.",
   path_params=[("hash", "32-char hex MD4.")],
   body=[("action", "`swap_this` \\| `swap_this_auto` \\| `swap_others`", "yes",
          "`swap_this` pulls A4AF sources onto this file; `swap_this_auto` does it "
          "and leaves auto-A4AF on; `swap_others` pushes them away."),
         ("client_ecid", "number", "no", "Narrow `swap_this` to one named source "
          "(the desktop's per-peer *Swap to this file*). Only valid with "
          "`swap_this`; the ECID must be a current A4AF source of this file.")],
   shape_from="WriteA4afObject",
   errors_from=["ParseJsonObjectBody"],
   notes=["The `GET` half of this path was retired: read `a4af_auto` from the "
          "download detail object and the A4AF rows from "
          "`GET /downloads/{hash}/clients`. A `GET` here answers `405`."])

# ------------------------------------------------------------------ Clients
group("Clients (peers)")

ep("GET, HEAD", "/api/v0/clients", "HandleClients",
   "Every peer the daemon currently knows: upload slots, queue waiters and "
   "download sources, in one collection.",
   query=[("filter", "`uploads` \\| `downloads` \\| `active`", "`uploads` = peers "
           "with `upload_state == \"uploading\"`; `downloads` = peers with "
           "`download_state == \"downloading\"`; `active` = the union. Any other "
           "value is a `400`. Absent = every peer.")],
   list_env=("clients", "WriteClientObject"),
   notes=["`/api/v0/uploads` was retired in favour of this route — consumers "
          "filter client-side (or with `?filter=uploads`).",
          "`part_progress_percent` is computed per row before serialization, so "
          "the list, the per-file rows, the detail object and the SSE "
          "`client_*` payloads all carry it."])

ep("GET, HEAD", "/api/v0/clients/{ecid}", "HandleClientDetail",
   "One peer, with the ed2k-identity and server fields the list row omits.",
   path_params=[("ecid", "EC connection id (`uint32`), unique per live connection. "
                 "An empty or non-numeric segment is a `400`.")],
   shape_from="WriteClientDetailObject",
   notes=["Detail-only keys, on top of the list row: `user_id_hybrid`, `high_id`, "
          "`server_ip`, `server_port`, `server_name`, `kad_port`, `is_friend`, "
          "`dl_up_modifier`.",
          "ECIDs are per-connection and are not stable across daemon restarts."])

ep("POST", "/api/v0/clients/{ecid}/shared_files", "HandleClientBrowse",
   "Browse (*View Files*) a peer's share. Starts an asynchronous browse and "
   "returns the `search_id` its results will arrive under.",
   auth="ADMIN", success="`202 Accepted` — the created search's list row (same "
   "shape as `GET /search` rows); `Location: /api/v0/search/{search_id}`",
   path_params=[("ecid", "EC connection id of a connected peer.")],
   errors_from=["HandleBrowse"],
   notes=["Delegates to the shared `HandleBrowse` (`Api.cpp:9638`), which is where "
          "the auth gate and the EC exchange live — `HandleClientBrowse` itself is "
          "a two-line wrapper.",
          "Read the listing with `GET /api/v0/search/{search_id}/results`; the "
          "search's `kind` is `browse` and its `query` is the peer's name.",
          "A peer that refuses the browse comes back as `404` carrying the "
          "daemon's reason; a daemon that starts no browse at all is a `502`."])

ep("POST", "/api/v0/clients/{ecid}/messages", "HandleClientMessageSend",
   "Send a chat message to a connected peer, addressed by ECID instead of "
   "`<ip>:<port>`.",
   success="`202 Accepted`",
   path_params=[("ecid", "EC connection id of a connected peer.")],
   body=[("text", "string", "yes", "Non-empty, ≤ 1024 bytes.")],
   errors_from=["SendChatMessageTo"],
   resp="""**Response body**

```json
{ "peer": "<ip>:<port>",
  "message": { "id": "int", "direction": "out", "text": "string" } }
```""",
   notes=["Only reaches a peer the daemon has a live connection to. Use "
          "`POST /api/v0/friends/{ecid}/messages` to reach an offline friend."])

group("Known clients (credit store)")

ep("GET, HEAD", "/api/v0/known_clients", "HandleKnownClients",
   "The daemon's credit store: every peer it has ever exchanged data with, keyed "
   "by user hash, with stored totals rather than live transfer state.",
   list_env=("known_clients", "WriteKnownClientObject"),
   notes=["A separate resource rather than a sub-path of `/clients`: these rows "
          "outlive the connection that would have issued an ECID.",
          "Matched before `/clients/{ecid}`, which would otherwise capture the "
          "segment.",
          "`503 ec_unsupported` when the connected `amuled` predates the EC op; "
          "`502 bad_gateway` when its payload cannot be decoded."])

# ------------------------------------------------------------------ Shared
group("Shared files")

ep("GET, HEAD", "/api/v0/shared", "HandleSharedList",
   "Every file the daemon is sharing, with upload counters.",
   list_env=("shared", "WriteSharedObject"),
   notes=["`uploading` is a **count of peers currently downloading this file**, "
          "not a boolean.",
          "`hashing_progress` is a part *count* (parts hashed so far by a Verify "
          "Local Data or an AICH rebuild), not a percentage; `0` when idle."])

ep("PATCH", "/api/v0/shared", "HandleSharedBulkPatch",
   "Set the upload priority of many shared files at once.",
   success="`200 OK` (bulk envelope; `207` mixed, `503` all-failed)",
   body=[("hashes", "array of strings", "yes", "1–500 hex MD4 hashes."),
         ("priority", "`very_low` \\| `low` \\| `normal` \\| `high` \\| `release` \\| `auto`", "yes", "")],
   resp="""**Response body** — the [bulk envelope](#bulk-mutation-envelope).""",
   errors_from=["ParseBulkHashes", "ParseJsonObjectBody"])

ep("POST", "/api/v0/shared_reload", "HandleSharedReload",
   "Ask the daemon to re-walk every configured share root.",
   success="`202 Accepted` — `{\"message\": \"…\"}` (the daemon's status message, "
   "omitted when empty)",
   errors_from=["SimpleConnControlOp"],
   notes=["Literally *accepted*: `amuled` schedules the walk and answers "
          "immediately (it starts on its next `Process()` tick). Repeated calls "
          "while a walk is pending coalesce into one.",
          "Completion is observable through `GET /api/v0/logs/amule` (or the "
          "`log_appended` SSE event) and the `shared_added` / `shared_removed` "
          "events — not through this response."])

ep("POST", "/api/v0/shared/media/refresh", "HandleSharedMediaRefresh",
   "Re-probe **every** shared file's media metadata, replacing what is stored.",
   success="`202 Accepted`",
   resp="""**Response body**

```json
{ "scope": "string", "queued": "int" }
```

`202`, not `200`: `amuled` queues the probes on its media-probe worker and
answers immediately, so nothing has been re-extracted yet. `queued` counts the
files accepted for probing — ones the scheduler dropped (not audio/video, an
incomplete download, missing on disk) are not counted.""",
   errors_from=["SendMediaRefresh"],
   notes=["The only way to correct metadata that is *wrong* rather than missing: "
          "the normal scheduler skips any file that already carries a media tag.",
          "Each probe **replaces** every media field, clearing one the new probe "
          "no longer finds. Nothing else about a file is touched and it is not "
          "re-hashed.",
          "One file at a time on the daemon's media-probe worker; shutting down "
          "mid-refresh is clean. Progress is observable through "
          "`GET /api/v0/logs/amule` and the `shared_updated` SSE events.",
          "A literal route matched before `/shared/{hash}`, so a file whose hash "
          "is literally `media` is unreachable.",
          "`503 ec_unsupported` when the connected `amuled` predates the EC op."])

ep("GET, HEAD", "/api/v0/share_directories", "HandleSharedDirectories",
   "The configured share roots (as opposed to the files they produced).",
   shape_from="HandleSharedDirectories",
   notes=["Its own top-level path: the roots are configuration, not members of "
          "the `/shared` file collection, and the old `/shared/directories` "
          "spelling sat one segment away from being read as a file hash."])

ep("PUT", "/api/v0/share_directories", "HandleSharedDirectoriesPut",
   "Replace the whole share-root list in one shot.",
   body=[("directories", "array of objects", "yes", "Each entry: `path` "
          "(non-empty string) and optional `recursive` (bool, default `false`).")],
   resp="""**Response body**

```json
{ "directories": [ { "path": "string", "recursive": "bool" } ] }
```

The applied share-root list, re-read from the daemon after the write.""",
   errors_from=["ApplySharedDirs", "ParseJsonObjectBody"])

ep("POST", "/api/v0/share_directories", "HandleSharedDirectoriesAdd",
   "Add one share root, or update the `recursive` flag of an existing one.",
   body=[("path", "string", "yes", "Non-empty. Compared verbatim against the "
          "existing roots — POSIX and Windows spellings are both accepted as-is."),
         ("recursive", "bool", "no", "Default `false`.")],
   resp="""**Response body** — same `{ "directories": [...] }` shape as the `PUT`.""",
   errors_from=["ApplySharedDirs", "ParseJsonObjectBody"],
   notes=["Read-modify-write under a process-wide mutex: the current list is "
          "fetched from the daemon, edited, and applied whole."])

ep("DELETE", "/api/v0/share_directories", "HandleSharedDirectoriesDelete",
   "Remove one share root.",
   query=[("path", "string", "**Required.** The root to remove, matched exactly. "
           "Unknown path → `404 not_found`.")],
   resp="""**Response body** — same `{ "directories": [...] }` shape as the `PUT`.""",
   errors_from=["ApplySharedDirs"],
   notes=["The target is a query parameter, not a body field, so the request "
          "carries no body."])

SH_LIST = SHAPE["WriteSharedObject"]
SH_FULL = SHAPE["WriteSharedDetailObject"]

ep("GET, HEAD", "/api/v0/shared/{hash}", "HandleSharedDetail",
   "One shared file, with the per-part source-availability array and the "
   "detail-only fields.",
   path_params=[("hash", "32-char hex MD4, case-insensitive.")],
   resp=SH_FULL,
   notes=["Detail-only, on top of the list row: `file_type`, `share_ratio`, "
          "`path`, `incomplete`, `complete_sources_range`, `aich_hash`, "
          "`part_count`, `parts`, `queued_count`, `comment`, `rating`, `media`.",
          "`parts[]` is `{sources}` per part — deliberately *not* the downloads "
          "`state` shape, which would invite rendering it as progress. The key is "
          "omitted entirely when nothing has been decoded yet, so *no data* stays "
          "distinguishable from *no sources anywhere*.",
          "`path` is the file's real directory; for a shared partfile that is the "
          "temp directory, flagged by `incomplete`."])

ep("PATCH", "/api/v0/shared/{hash}", "HandleSharedPatch",
   "Set a shared file's upload priority, and/or its comment and rating.",
   path_params=[("hash", "32-char hex MD4.")],
   body=[("priority", "`very_low` \\| `low` \\| `normal` \\| `high` \\| `release` \\| `auto`", "no", ""),
         ("comment", "string", "with `rating`", "≤ 50 characters."),
         ("rating", "number", "with `comment`", "Integer 0–5.")],
   resp=SH_LIST,
   errors_from=["TrySetCommentRating", "ParseJsonObjectBody"],
   notes=["At least one of `priority` or `comment`+`rating` is required."])

ep("POST", "/api/v0/shared/{hash}/verify", "HandleSharedVerify",
   "Re-hash a completed shared file against its on-disk data.",
   success="`202 Accepted` — no body",
   path_params=[("hash", "32-char hex MD4 of a completed shared file.")],
   notes=["A partfile is refused with `409 partfile_unsupported`: the daemon's "
          "hashing task bails out on `IsPartFile()` but still answers `NOOP`, "
          "which would tell the caller the re-hash had been accepted.",
          "Progress is observable as `hashing_progress` on the file's rows."])

ep("POST", "/api/v0/shared/{hash}/media/refresh", "HandleSharedMediaRefreshOne",
   "Re-probe one shared file's media metadata.",
   success="`202 Accepted`",
   path_params=[("hash", "32-char hex MD4 of a shared file.")],
   resp="""**Response body**

```json
{ "scope": "string", "queued": "int" }
```

`202`, not `200`: `amuled` queues the probes on its media-probe worker and
answers immediately, so nothing has been re-extracted yet. `queued` counts the
files accepted for probing — ones the scheduler dropped (not audio/video, an
incomplete download, missing on disk) are not counted.""",
   errors_from=["SendMediaRefresh"],
   notes=["Same semantics as the all-files form, scoped to one hash; `scope` "
          "reads `file` rather than `all`.",
          "An incomplete partfile is refused with `409 partfile_unsupported` "
          "rather than accepted and silently dropped by the daemon's scheduler: "
          "there is no complete file to read.",
          "Unknown hash → `404 not_found`."])

ep("GET, HEAD", "/api/v0/shared/{hash}/clients", "HandleFileClients",
   "The peers related to this shared file.",
   path_params=[("hash", "32-char hex MD4 of a **shared** file.")],
   query=[("include_parts", "`true` \\| `false`", "Include each peer's per-part "
           "bitmap. Default `false`.")],
   list_env=("clients", "WriteFileClientRow"),
   notes=["Same handler as `GET /api/v0/downloads/{hash}/clients` with "
          "`require_downloading = false`.",
          "`parts` here is an array of booleans (one per part), present only when "
          "`include_parts=true` *and* the row actually has a bitmap for this file."])

# ------------------------------------------------------------------ Servers
group("Servers (ed2k server list)")

SRV = dict(SHAPE["WriteServerObject"])
SRV["tcp_flags"] = {"bitmask": "uint", "compression": "bool", "new_tags": "bool",
                    "unicode": "bool", "related_search": "bool",
                    "type_tag_integer": "bool", "large_files": "bool",
                    "tcp_obfuscation": "bool"}
SRV["udp_flags"] = {"bitmask": "uint", "get_sources": "bool", "get_files": "bool",
                    "new_tags": "bool", "unicode": "bool", "get_sources_v2": "bool",
                    "large_files": "bool", "udp_obfuscation": "bool",
                    "tcp_obfuscation": "bool"}

ep("GET, HEAD", "/api/v0/servers", "HandleServers",
   "The ed2k server list, with per-server capability flags.",
   resp={"servers": [SRV], "total": "uint", "offset": "uint", "limit": "uint"},
   notes=["`tcp_flags` / `udp_flags` are decoded capability objects — a `bitmask` "
          "plus one boolean per wire bit. The names come from one table shared by "
          "the REST writer and the SSE payload (`ServerFlagNames.h:98`, `117`).",
          "`soft_file_limit` / `hard_file_limit` are the server's advertised "
          "limits; `ping_ms` and `failed_count` are the daemon's own counters, "
          "relayed verbatim."])

ep("POST", "/api/v0/servers", "HandleServerAdd",
   "Add a server by address.",
   success="`202 Accepted` — no body",
   body=[("address", "string", "yes", "`host:port`. The colon must be present and "
          "not at either end."),
         ("name", "string", "no", "Display name; omitted means the daemon uses "
          "whatever the server announces.")],
   errors_from=["ParseJsonObjectBody"])

ep("POST", "/api/v0/servers_update", "HandleServerUpdateFromUrl",
   "Tell the daemon to fetch `server.met` from a URL.",
   success="`202 Accepted` — no body",
   body=[("servers_url", "string", "yes", "`http://` or `https://` URL. Required — "
          "unlike the Kad and IP-filter variants there is no configured fallback.")],
   errors_from=["ResolveFetchUrl", "UrlFetchOp"],
   notes=["A top-level path: updating the list is an action on the collection, "
          "and `/servers/update` shadowed a server whose ECID was `update`."])

ep("POST", "/api/v0/servers/{ecid}/connect", "HandleServerConnect",
   "Connect to one server.",
   success="`202 Accepted` — no body",
   path_params=[("ecid", "The server's EC id. To address a server by "
                 "`<ip>:<port>` use `/servers/by-address/{address}/connect`.")])

ep("POST", "/api/v0/servers/by-address/{address}/connect",
   "HandleServerConnectByAddress",
   "Connect to one server, addressed by `<ip>:<port>` instead of by ECID.",
   success="`202 Accepted` — no body",
   path_params=[("address", "`<ip>:<port>`, matched against the server list. "
                 "Unknown address → `404 not_found`.")],
   errors_from=["ResolveServerEcid", "HandleServerConnect"],
   notes=[BY_ADDRESS_NOTE])

ep("PATCH", "/api/v0/servers/{ecid}", "HandleServerPatch",
   "Set a server's priority and/or its static flag.",
   success="`200 OK` — the full server object (same shape as `GET /servers` rows)",
   path_params=[("ecid", "Server EC id.")],
   body=[("priority", "`low` \\| `normal` \\| `high`", "no", ""),
         ("static", "bool", "no", "")],
   errors_from=["ParseJsonObjectBody"],
   notes=["At least one of the two fields is required.",
          "Note the priority vocabulary differs from files: servers have three "
          "levels, no `auto`."])

ep("DELETE", "/api/v0/servers/{ecid}", "HandleServerDelete",
   "Remove one server from the list.",
   success="`204 No Content`",
   path_params=[("ecid", "Server EC id.")])

ep("PATCH, DELETE", "/api/v0/servers/by-address/{address}",
   "HandleServerPatchByAddress",
   "The `PATCH` and `DELETE` above, addressed by `<ip>:<port>` instead of by "
   "ECID. Same bodies, same responses.",
   success="`PATCH` → `200 OK` — the full server object; "
   "`DELETE` → `204 No Content`",
   path_params=[("address", "`<ip>:<port>`. Unknown address → `404 not_found`.")],
   body=[("priority", "`low` \\| `normal` \\| `high`", "no", "`PATCH` only."),
         ("static", "bool", "no", "`PATCH` only.")],
   errors_from=["HandleServerDeleteByAddress", "ResolveServerEcid",
                "ParseJsonObjectBody", "HandleServerPatch", "HandleServerDelete"],
   notes=[BY_ADDRESS_NOTE])

# ------------------------------------------------------------------ Friends
group("Friends")

ep("GET, HEAD", "/api/v0/friends", "HandleFriends",
   "The friend list — daemon-side records, not per-connection rows like "
   "`/clients`.",
   list_env=("friends", "WriteFriendObject"),
   notes=["`ecid` identifies the *friend record*; `client_ecid` is the live "
          "connection when the friend is online (0 otherwise)."])

ep("POST", "/api/v0/friends", "HandleFriendAdd",
   "Add a friend, either from a live connection or from raw contact details.",
   success="`202 Accepted` — no body",
   body=[("client_ecid", "number", "either", "ECID of a currently connected peer."),
         ("ip", "string", "either", "Dotted-quad IPv4 (manual form)."),
         ("port", "number", "either", "TCP port (manual form)."),
         ("user_hash", "string", "no", "32-char hex user hash (manual form)."),
         ("name", "string", "no", "Display name (manual form).")],
   errors_from=["ParseJsonObjectBody"],
   notes=["`client_ecid` and the `ip`/`port`/`user_hash`/`name` form are mutually "
          "exclusive — sending both is a `400`."])

ep("PATCH", "/api/v0/friends/{ecid}", "HandleFriendPatch",
   "Grant or revoke this friend's reserved upload slot.",
   path_params=[("ecid", "Friend record EC id.")],
   body=[("friend_slot", "bool", "yes", "")],
   shape_from="WriteFriendObject",
   errors_from=["ParseJsonObjectBody"])

ep("DELETE", "/api/v0/friends/{ecid}", "HandleFriendRemove",
   "Remove a friend.",
   success="`204 No Content`",
   path_params=[("ecid", "Friend record EC id.")])

ep("POST", "/api/v0/friends/{ecid}/shared_files", "HandleFriendBrowse",
   "Browse a friend's share.",
   auth="ADMIN", success="`202 Accepted` — the created search's list row (same "
   "shape as `GET /search` rows); `Location: /api/v0/search/{search_id}`",
   path_params=[("ecid", "Friend record EC id.")],
   errors_from=["HandleBrowse"],
   notes=["Same delegation as the client form: the work is in `HandleBrowse` "
          "(`Api.cpp:9638`), addressed by `EC_TAG_FRIEND` instead of "
          "`EC_TAG_CLIENT`. This is the form that can reach a friend whose "
          "connection is not currently live.",
          "The started search has `kind: \"browse\"` and the friend's name as its "
          "`query`."])

ep("POST", "/api/v0/friends/{ecid}/messages", "HandleFriendMessageSend",
   "Send a chat message to a friend, addressed by friend ECID.",
   success="`202 Accepted`",
   path_params=[("ecid", "Friend record EC id.")],
   body=[("text", "string", "yes", "Non-empty, ≤ 1024 bytes.")],
   errors_from=["SendChatMessageTo"],
   resp="""**Response body** — same shape as the other send forms:

```json
{ "peer": "<ip>:<port>",
  "message": { "id": "int", "direction": "out", "text": "string" } }
```""",
   notes=["This is the form that reaches an **offline** friend — the daemon opens "
          "the connection."])

# ------------------------------------------------------------------ Chats
group("Chat")

ep("GET, HEAD", "/api/v0/chats", "HandleChats",
   "Open conversations, newest activity first when sorted.",
   list_env=("chats", "WriteChatObject"),
   notes=["`peer` is the `<ip>:<port>` key every other chat route takes.",
          "`last_message` is the most recent message inline, so a list render "
          "needs no per-chat roundtrip."])

ep("GET, HEAD", "/api/v0/chats/{peer}/messages", "HandleChatMessages",
   "One conversation's messages, with a polling cursor.",
   path_params=[("peer", "`<ip>:<port>`. A malformed key is a `400`.")],
   query=[("since_id", "integer", "Return only messages with `id` greater than "
           "this. Ids are monotonic per daemon process, so a poller never "
           "duplicates or skips; they reset when the daemon restarts (which also "
           "empties the store)."),
          ("limit", "integer", "Keep only the **last** *n* of the selected window "
           "— *show me the tail of this conversation*.")],
   shape_from="HandleChatMessages",
   notes=["`total` is the conversation's full message count, `last_msg_id` the "
          "newest id — both independent of the window returned.",
          "`503 ec_unsupported` when the connected `amuled` does not serve chat "
          "sessions.",
          "This endpoint does **not** use the shared list envelope: no `offset`, "
          "no `sort`."])

ep("POST", "/api/v0/chats/{peer}/messages", "HandleChatSend",
   "Send a message into a conversation, addressed by `<ip>:<port>`.",
   success="`202 Accepted`",
   path_params=[("peer", "`<ip>:<port>`.")],
   body=[("text", "string", "yes", "Non-empty, ≤ 1024 bytes.")],
   errors_from=["SendChatMessageTo"],
   resp="""**Response body**

```json
{ "peer": "<ip>:<port>",
  "message": { "id": "int", "direction": "out", "text": "string" } }
```""")

ep("DELETE", "/api/v0/chats/{peer}", "HandleChatClose",
   "Close a conversation and drop its stored messages.",
   success="`204 No Content`",
   path_params=[("peer", "`<ip>:<port>`.")],
   notes=["Publishes `chat_session_closed` to SSE subscribers."])

# ------------------------------------------------------------------ Categories
group("Categories")

ep("GET, HEAD", "/api/v0/categories", "HandleCategories",
   "The download categories. Index 0 is the daemon's built-in *all* category.",
   list_env=("categories", "WriteCategoryObject"),
   notes=["`color` is a packed RGB integer; `priority` is `low` / `normal` / "
          "`high` / `auto` — the category vocabulary, which has no `very_low` or "
          "`release`.",
          "Index 0 is synthesised when the daemon omits it (it suppresses the "
          "whole block until a custom category exists), so clients always see at "
          "least the default row.",
          "Takes the shared list params like every other list endpoint; `sort` "
          "accepts `index` and `name` (`CategoryComparators()`)."])

ep("POST", "/api/v0/categories", "HandleCategoryCreate",
   "Create a category.",
   success="`202 Accepted` — no body",
   body=[("name", "string", "yes", "Non-empty."),
         ("path", "string", "no", "Incoming directory for this category."),
         ("comment", "string", "no", ""),
         ("color", "number", "no", "uint32 packed RGB."),
         ("priority", "`low` \\| `normal` \\| `high` \\| `auto`", "no", "")],
   errors_from=["ParseCategoryFields", "ParseJsonObjectBody"],
   notes=["`index` is resolved after an inline refresher tick by matching the "
          "created name, and is omitted if the new row has not surfaced yet."])

ep("GET, HEAD", "/api/v0/categories/{index}", "HandleCategoryOne",
   "One category.",
   path_params=[("index", "uint8, 0–255. Non-numeric or out of range → `400`; "
                 "a valid index with no category → `404 not_found`.")],
   shape_from="WriteCategoryObject",
   notes=["Selected out of the same set the collection lists, synthetic default "
          "(index 0) included, so the two routes cannot disagree about which "
          "categories exist."])

ep("PATCH", "/api/v0/categories/{index}", "HandleCategoryUpdate",
   "Update a category. Unsent fields keep their current value.",
   path_params=[("index", "uint8, 0–255. Non-numeric or out of range → `400`.")],
   body=[("name", "string", "no", ""),
         ("path", "string", "no", ""),
         ("comment", "string", "no", ""),
         ("color", "number", "no", ""),
         ("priority", "`low` \\| `normal` \\| `high` \\| `auto`", "no", "")],
   shape_from="WriteCategoryObject",
   errors_from=["ParseCategoryFields", "ParseJsonObjectBody"])

ep("DELETE", "/api/v0/categories/{index}", "HandleCategoryDelete",
   "Delete a category.",
   success="`204 No Content`",
   path_params=[("index", "uint8, 0–255.")],
   notes=["Categories are positional: deleting one shifts every higher index down "
          "by one. The cached downloads are re-mapped in the same operation "
          "(files in the deleted category fall back to 0), so `GET /downloads` "
          "does not report stale indices for a tick."])

# ------------------------------------------------------------------ Preferences
group("Preferences")

ep("GET, HEAD", "/api/v0/preferences", "HandlePreferences",
   "Every preference the daemon exposes, nested by category. Table-driven: the "
   "categories, keys, types and access levels all come from the schema in "
   "`src/webapi/PrefsSchema.cpp` — see "
   "[Appendix A](#appendix-a--preferences-field-table) for the full list.",
   resp="""**Response body** — one object per category:

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
appear either.""",
   notes=["`remote_controls` is the only two-level category: `webserver` and "
          "`amuleapi` are separate JSON sub-objects that pack into the same EC "
          "group.",
          "Read-only rows (capabilities, live status such as "
          "`connection.upnp_available`) are emitted but silently ignored on PATCH."])

ep("PATCH", "/api/v0/preferences", "HandlePreferencesPatch",
   "Apply a partial preferences update. The body mirrors the GET shape: one "
   "optional sub-object per category, containing only the keys to change.",
   body="""One optional object per category, e.g.

```json
{ "connection": { "max_download_kbps": 2048 },
  "files": { "add_new_files_paused": true } }
```

Field-level rules come from the schema (Appendix A): `Uint16` / `Uint32` rows
have an inclusive `max`, `Enum` rows accept only their listed names,
`StringArray` rows take an array of strings, and a row with a `gated_by`
capability answers `409 conflict` when that capability is false.""",
   resp="""**Response body** — the full `GET /api/v0/preferences` object, re-read
after an inline refresher tick, so a consumer can confirm what actually landed
without a follow-up `GET`.""",
   errors_from=["ParseJsonObjectBody"],
   notes=["Sent in one `EC_OP_SET_PREFERENCES` at `EC_DETAIL_FULL` — the detail "
          "level the daemon requires before it honours boolean tags.",
          "A body with no recognised field at all is a `400`; unknown keys inside "
          "a known category are ignored.",
          "`remote_controls.amuleapi` passwords are explicitly **rejected** here — "
          "they live behind `PATCH /api/v0/auth/passwords`.",
          "`remote_controls.webserver.guest_enabled` + `guest_password` share one "
          "EC tag, so their packing is hand-written rather than table-driven "
          "(`PrefAccess::Bespoke`).",
          "`core_tweaks.kad_reask_ms`, `source_reask_ms` and "
          "`server_keepalive_timeout_ms` are milliseconds on the wire, exactly as "
          "the daemon stores them — no unit conversion happens in this layer."])

# ------------------------------------------------------------------ Logs
group("Logs")

ep("GET, HEAD", "/api/v0/logs/amule", "HandleLogAmule",
   "The daemon log as amuleapi has mirrored it (append-only, in-process cache).",
   query=[("tail", "integer", "Return only the last *n* lines. `0`, absent, "
           "negative or non-numeric means everything; capped at 100 000.")],
   shape_from="HandleLogAmule",
   notes=["`total_cached` is what the mirror holds, `returned` what this response "
          "carried — enough for a client to know what it missed.",
          "New lines also arrive as the `log_appended` SSE event."])

ep("DELETE", "/api/v0/logs/amule", "HandleLogAmuleReset",
   "Reset the daemon log.",
   success="`204 No Content`",
   notes=["Also drops the in-process mirror, so the next `GET` starts empty and no "
          "spurious `log_appended` fires."])

ep("GET, HEAD", "/api/v0/logs/serverinfo", "HandleLogServerinfo",
   "The server-info log — one accumulated text blob, fetched from the daemon "
   "lazily with a 1 s TTL.",
   query=[("tail", "integer", "Keep only the last *n* lines, sliced at line "
           "boundaries from the end so the first line is always whole.")],
   shape_from="HandleLogServerinfo",
   notes=["`total_bytes` / `returned_bytes` let a client decide whether to re-poll "
          "with a smaller `?tail=`."])

ep("DELETE", "/api/v0/logs/serverinfo", "HandleLogServerinfoReset",
   "Clear the server-info log.",
   success="`204 No Content`",
   notes=["Invalidates the 1 s lazy cache so the next `GET` re-fetches instead of "
          "returning stale text."])

# ------------------------------------------------------------------ Stats
group("Statistics")

ep("GET, HEAD", "/api/v0/stats/tree", "HandleStatsTree",
   "The daemon's statistics tree (the desktop's *Statistics* page), as nested "
   "nodes.",
   query=[("max_client_versions", "integer 0–255", "Cap how many per-software "
           "version rows the daemon serializes (`EC_TAG_STATTREE_CAPPING`). `0` "
           "(default) is unlimited. Only the version lists are affected. Out of "
           "range → `400`.")],
   resp={"nodes": [{
       "key": "string (omitted when empty)",
       "label_value": "string (omitted when empty)",
       "label": "string",
       "values": [{"type": "string",
                   "value": "uint | number | string (per the node's value kind)",
                   "token": "string (only for enum-ish values)",
                   "extra": "{ … same value object, recursively }"}],
       "ratio": {"session": "number (optional)", "total": "number (optional)"},
       "children": ["{ … same node object, recursively }"]}]},
   notes=["Fetched lazily with a 1 s TTL that coalesces concurrent readers; the "
          "cache is unkeyed, so a request at a different cap counts as a miss.",
          "`values[].value` is a uint, a double or a string depending on what the "
          "daemon sent for that node; `token` and `extra` appear only when "
          "non-empty, and `key` / `label_value` are omitted when empty.",
          "`ratio` is present only when the node carries a session and/or total "
          "ratio; `children` is always present (empty array on a leaf).",
          "`503 ec_unavailable` when the EC fetch fails."])

ep("GET, HEAD", "/api/v0/stats/graphs/{graph}", "HandleStatsGraph",
   "One time series plus the session totals.",
   path_params=[("graph", "`download_speed` \\| `upload_speed` \\| `connections` \\| "
                 "`kad_nodes`. Anything else → `404 not_found`, validated **before** "
                 "any EC roundtrip.")],
   query=[("interval", "integer 1–3600", "Seconds between samples "
           "(`EC_TAG_STATSGRAPH_SCALE`). Default `1`. Rejected rather than clamped."),
          ("width", "integer", "Return only the last *n* points. `0`/absent means "
           "everything; capped at 1800. Applied after the fetch, so one cached "
           "bundle answers every `(graph, width)` combination.")],
   resp={"graph": "string", "unit": "bytes_per_second | count",
         "interval_seconds": "int", "max_points": "int",
         "points": [{"t": "ISO-8601 UTC string", "t_unix": "int", "value": "int",
                     "active_downloads": "int (connections graph only)",
                     "active_uploads": "int (connections graph only)"}],
         "session": {"download_bytes": "int", "upload_bytes": "int",
                     "kad_node_seconds": "int", "duration_seconds": "int"}},
   notes=["One EC roundtrip serves all four graphs, so the 1 s lazy cache is "
          "shared across graph names — but it is keyed on nothing, so a request at "
          "a different `interval` is a miss.",
          "`points` is never longer than `max_points`; timestamps are anchored "
          "backwards from the fetch wall-clock.",
          "`active_downloads` / `active_uploads` appear only on the `connections` "
          "graph, and only when the daemon sent the second data blob."])

# ------------------------------------------------------------------ Search
group("Search")

ep("GET, HEAD", "/api/v0/search", "HandleSearchList",
   "Every search the daemon currently holds — including ones started by another "
   "client or restored from disk.",
   list_env=("searches", "WriteSearchListRow"),
   notes=["Fetched live over EC (`EC_OP_SEARCH_LIST`), not from the refresher cache.",
          "`client_ecid` appears only on a browse entry (whose share is being "
          "listed); `started_at` only for searches *this* amuleapi started; "
          "`result_count` only when the daemon reports it. All three are omitted "
          "rather than zeroed, so *unknown* stays distinguishable from *none*.",
          "`kind` is `local` / `global` / `kad` / `browse`; `state` is the "
          "daemon's lifecycle state.",
          "Carries the standard list envelope: the rows are fetched whole over "
          "EC, then sorted and sliced like any other list endpoint."])

ep("POST", "/api/v0/search", "HandleSearchStart",
   "Start a search. The daemon allocates the `search_id` everything else is "
   "addressed by.",
   success="`202 Accepted` — the created search's list row (same shape as "
   "`GET /search` rows); `Location: /api/v0/search/{search_id}`",
   body=[("query", "string", "yes", "Non-empty."),
         ("type", "`local` \\| `global` \\| `kad`", "no", "Default `global`."),
         ("file_type", "string", "no", "aMule file-type label."),
         ("extension", "string", "no", "e.g. `mkv`."),
         ("min_size", "number", "no", "Bytes, ≥ 0. Default 0."),
         ("max_size", "number", "no", "Bytes, ≥ 0. Default 0 = no cap."),
         ("min_avail", "number", "no", "uint32. Default 0.")],
   errors_from=["ParseJsonObjectBody"],
   notes=["A reply carrying no `search_id` is reported as `502 amuled_rejected` — "
          "without an id the caller has nothing to address.",
          "The refresher starts polling this id for results and progress, so SSE "
          "`search_result_added` / `search_progress` fire on the same deltas a "
          "poller would see."])

ep("GET, HEAD", "/api/v0/search/{id}/results", "HandleSearchResults",
   "One search's results, with its progress rolled into the same envelope.",
   path_params=[("id", "Positive decimal `search_id`. `0`, non-numeric or "
                 "overflowing → `400` (`" + "kBadSearchIdMessage" + "`, "
                 "`kBadSearchIdMessage`). An id naming no live search → `404`.")],
   resp={"results": [SHAPE["WriteSearchObject"]],
         "total": "uint", "offset": "uint", "limit": "uint",
         "search_id": "int", "query": "string",
         "progress": {"state": "idle | running | finished", "kind": "string",
                      "percent": "int"}},
   errors_from=["RequireSearch"],
   notes=["Keeps its own envelope (the `progress` object rides alongside "
          "`results`) but reuses the shared window + page-meta helpers, so "
          "`limit`/`offset`/`sort`/`order` behave exactly as elsewhere.",
          "A finished search is refreshed on read (coalesced by a short TTL), "
          "because the refresher stops polling it.",
          "`results[].children` is always present (empty when the hit was seen "
          "under a single name); each child's `ecid` is what "
          "`POST /search/results/{hash}/download` takes to pick that filename.",
          "`media` is present only when the daemon reported probed metadata.",
          "`progress` mirrors the `search_progress` SSE event field-for-field.",
          "For a browse, `query` is the peer's name and `results[].directory` is "
          "populated — hence the `directory` sort key.",
          "`results`, `stop` and `more` are dispatched from one "
          "`/search/{id}/{action}` block in `DispatchToHandler`; any other action is a "
          "`404` `unknown search action (expected results, stop or more)`."])

ep("POST", "/api/v0/search/{id}/stop", "HandleSearchStop",
   "Stop a running search but keep its results readable.",
   success="`204 No Content`",
   path_params=[("id", "Positive decimal `search_id`.")],
   errors_from=["RequireSearch", "SendSearchOp"],
   notes=["Siblings are untouched — the daemon is addressed with this id only."])

ep("POST", "/api/v0/search/{id}/more", "HandleSearchMore",
   "Ask a running **Kad** search to widen its result frontier (the desktop's "
   "*More* button).",
   success="`202 Accepted` — no body",
   path_params=[("id", "Positive decimal `search_id`.")],
   errors_from=["RequireSearch", "SendSearchOp"],
   notes=["Rejected with `400` for a non-Kad search and for a search that has "
          "already finished — mirroring the desktop button, which is greyed out in "
          "both cases.",
          "`409 kad_more_exhausted` when the daemon reports the search can no "
          "longer be widened (reask budget spent, or inside the ~20 s stopping "
          "window). A daemon too old to report gets today's `202`."])

ep("DELETE", "/api/v0/search/{id}", "HandleSearchClose",
   "Stop **and** free a search: the daemon drops it and the local slot goes away.",
   success="`204 No Content`",
   path_params=[("id", "Positive decimal `search_id`.")],
   errors_from=["RequireSearch", "SendSearchOp"],
   notes=["After this, `GET /search/{id}/results` is a `404` and subscribers see "
          "`search_closed`.",
          "The `{id}` segment is validated *before* the method check, so "
          "`PATCH /api/v0/search/abc` is a `400`, not a `405`."])

ep("POST", "/api/v0/search/results/{hash}/download", "HandleSearchDownload",
   "Download one search result.",
   success="`202 Accepted` — no body",
   path_params=[("hash", "32-char hex MD4 of the result, case-insensitive.")],
   body=[("category", "number", "no", "0–255, default 0."),
         ("ecid", "number", "no", "Pick one grouped child (from a result's "
          "`children[].ecid`) so the file downloads under that filename. Omitted "
          "means the parent hit.")],
   errors_from=["ParseJsonObjectBody"],
   notes=["The body is entirely optional — a bare POST downloads under the default "
          "category.",
          "The daemon looks the hash up in its own search list; an unknown hash "
          "comes back as `400 amuled_rejected`.",
          "Matched before `/search/{id}`, so the literal `results` segment is "
          "reserved."])

ep("GET, HEAD", "/api/v0/search/results/{hash}/comments", "HandleSearchComments",
   "Kad community ratings/comments retrieved for one search result.",
   path_params=[("hash", "32-char hex MD4 of the result.")],
   shape_from="HandleSearchComments",
   notes=["`kad_comment_search_running` is true while a lookup started by the "
          "`POST` form is still in flight."])

ep("POST", "/api/v0/search/results/{hash}/comments", "HandleSearchCommentsKadSearch",
   "Trigger a Kad NOTES lookup for one search result.",
   success="`202 Accepted` — no body",
   path_params=[("hash", "32-char hex MD4 of the result.")])

# ------------------------------------------------------------------ Events
group("Server-sent events")

ep("GET, HEAD", "/api/v0/events", "DispatchEvents",
   "The push channel: one long-lived `text/event-stream` carrying every state "
   "change the refresher diffs. Diverted by the streaming resolver before the "
   "normal dispatcher ever runs.",
   auth="GUEST",
   success="`200 OK`, `Content-Type: text/event-stream`",
   query=[("channels", "comma-separated list", "Deliver only these channels: "
           "`downloads`, `shared`, `servers`, `clients`, `friends`, `status`, "
           "`logs`, `search`, `chats`, `comments`. Unknown names are ignored "
           "(forward compatibility); at most 32 unique tokens are kept. The "
           "synthetic `resync` event is always delivered.")],
   errors_from=["PreflightEvents"],
   resp="""**Response headers**: `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, plus the CORS bundle. Chunked transfer encoding.

**Frame format**

```
event: <name>
id: <monotonic uint64>
data: <single-line JSON>

```

The stream opens with `: connected`, and emits `: keepalive` whenever nothing
has been written for 15 s (wall-clock driven, so a busy bus behind a
`?channels=` filter still keeps the connection warm).""",
   notes=["Auth runs in `PreflightEvents` on the I/O thread, **before** a worker "
          "thread is spawned and before the 32-slot budget is claimed, so an "
          "unauthenticated peer gets an ordinary `401`/`429` and cannot hold a slot.",
          "The 33rd concurrent stream is refused by the HTTP layer with "
          "`503 sessions_exhausted` + `Retry-After: 10`.",
          "Reconnect: send `Last-Event-ID`. An id newer than the bus (daemon "
          "restarted) or older than its oldest retained event (gap) produces a "
          "`resync` frame carrying `{reason, since_id, newest_id}` — `restart` or "
          "`gap` — after which the client is expected to invalidate and re-GET the "
          "REST collections. Gaps are also detected mid-stream, not only at connect.",
          "The cursor advances over filtered-out events too, so a reconnect never "
          "re-delivers them; replay is id-based, not channel-based.",
          "Guest tokens are accepted: SSE is a read-only push.",
          "The path must match exactly — `/api/v0/events/` is **not** diverted "
          "and ends up a `404`. A non-GET/HEAD method is not diverted either, and "
          "since no route matches it, also `404` (there is no `405` here).",
          "No ETag layer and no `OPTIONS` short-circuit apply to this route.",
          "See [Appendix B](#appendix-b--sse-event-catalog) for the event names."])

# ------------------------------------------------------------------ Non-API
group("Static assets and country flags")

ep("GET, HEAD", "/flags/{code}.png", "ServeCountryFlag",
   "A country flag PNG, for `<img src>` in a UI. Outside `/api/v0` on purpose, "
   "and unauthenticated.",
   auth="NONE",
   path_params=[("code", "Exactly two lowercase ASCII letters, or the literal "
                 "`unknown`. Anything else → `404 not_found` / `no such flag`.")],
   resp="""**Response**: `image/png` bytes, `Cache-Control: public, max-age=86400`.""",
   notes=["Matched as a path **prefix** (`/flags/`), before the static-file "
          "fallthrough, so the response is identical with or without a configured "
          "`StaticRoot`.",
          "Missing artwork answers the same opaque `404` as a bad code, so the "
          "icon set is not enumerable."])

ep("GET, HEAD", "/{any non-/api/ path}", "ServeStaticFile",
   "The bundled Web UI. Any safe-method request whose path does not start with "
   "`/api/` falls through to the static root.",
   auth="NONE",
   resp="""**Response**: the file's bytes with a content type derived from its
extension (`StaticContentType`), an mtime+size `ETag`, and its own `304` branch.""",
   notes=["Root comes from `StaticRoot` in `amuleapi.conf`, else "
          "`ResolveDefaultStaticDir()`; resolved once via `std::call_once`. An "
          "empty root answers `404 no such endpoint`.",
          "`/` and the empty path serve `index.html`.",
          "Containment is enforced by `webapi::ResolveWithinRoot` "
          "(`StaticFs.cpp`) — `realpath`/`_fullpath` plus a prefix and "
          "separator check, so a symlink out of the root is refused.",
          "SPA fallback: an unresolved path **without** a `.` re-serves "
          "`index.html`; a path with an extension is a `404 no such file`.",
          "The mtime+size `ETag` is the one clients see: the outer ETag layer "
          "steps aside whenever a handler set its own, so `GET` and `HEAD` on an "
          "asset report the same validator. The `If-None-Match` lookup is "
          "case-insensitive and takes `*`, a comma-separated list and weak "
          "`W/\"…\"` validators, and the token carries a coding suffix when the "
          "response would be gzipped."])

w("#### `OPTIONS <any path>`")
w()
w("Not a route: `CApiDispatcher::Dispatch` answers any")
w("`OPTIONS` carrying `Access-Control-Request-Method` with **`204 No Content`**")
w("and the CORS preflight bundle, before authentication and before routing.")
w()
w("| | |")
w("|---|---|")
w("| Auth | **NONE** |")
w("| Success | `204 No Content`, no body, no `Content-Type` |")
w()
w("Headers on an accepted origin: `Access-Control-Allow-Origin`,")
w("`Access-Control-Allow-Credentials: true`,")
w("`Access-Control-Allow-Methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS`,")
w("`Access-Control-Allow-Headers: Authorization, Content-Type, If-None-Match, Last-Event-ID`,")
w("`Access-Control-Max-Age: 86400`. A rejected origin gets `204` + `Vary: Origin` only.")
w()
w("An `OPTIONS` **without** `Access-Control-Request-Method` is not special-cased:")
w("it falls into normal routing and ends in that route's `405` (or `404`).")
w()
w("---")
w()

# ===================================================================
# Appendix A — preferences table (generated from PrefsSchema.cpp)
# ===================================================================
w("## Appendix A — preferences field table")
w()
w(f"All {len(P['rows'])} rows of the schema table in `src/webapi/PrefsSchema.cpp`,")
w("in source order. This *is* the contract of `GET`/`PATCH /api/v0/preferences`:")
w("the emitter and the patch walker both drive off this table.")
w()
w("Access levels: **ReadWrite** (emitted, applied) · **ReadOnly** (emitted, "
  "silently ignored on PATCH) · **WriteOnly** (never emitted, applied) · "
  "**Rejected** (never emitted, `400` if sent) · **Bespoke** (emitted, PATCH "
  "hand-written).")
w()
w("| Category | Key | JSON type | Access | Constraint / values | Notes |")
w("|---|---|---|---|---|---|")
for r in P["rows"]:
    constraint = ""
    if r["max"]:
        constraint = f"max `{r['max']}`"
    elif r["enum"]:
        constraint = ", ".join(f"`{e}`" for e in r["enum"])
    notes = []
    if r["invert"]:
        notes.append("API value is the negation of the EC value")
    if r["gate"]:
        notes.append(f"gated by `{r['gate']}` (else `409 conflict`)")
    if r["macro"] == "BOOL_INGROUP":
        notes.append("tag read from another EC group")
    w(f"| `{r['category']}` | `{r['key']}` | {r['type']} | {r['access']} | "
      f"{constraint} | {'; '.join(notes)} |")
w()
w("EC group per category (`kCategories`, `PrefsSchema.cpp`):")
w()
w("| Category | EC group tag |")
w("|---|---|")
for name, tag in P["categories"]:
    w(f"| `{name}` | `{tag}` |")
w()
w("---")
w()

# ===================================================================
# Appendix B — SSE events
# ===================================================================
w("""## Appendix B — SSE event catalog

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
| `search_progress` | `search` | `{search_id, state, kind, percent, results}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `search_closed` | `search` | `{search_id}` | `EmitDiffsAndUpdate`, `EventDiff.cpp` |
| `chat_message` | `chats` | one chat message object | `PublishChatEvents`, `EventDiff.cpp` |
| `chat_session_closed` | `chats` | `{"peer": "<ip>:<port>"}` | `PublishChatEvents`, `EventDiff.cpp` |
| `resync` | *(always delivered)* | `{"reason": "gap" \\| "restart", "since_id": N, "newest_id": N}` | `DispatchEvents`, `Api.cpp` |

`search_result_added` and `GET /search/{id}/results` share one serializer
(`webapi::WriteSearchResultFields`, `src/webapi/SearchJson.cpp`), so a row is
byte-identical whether it arrives by poll or by push.

---
""")

# ===================================================================
# Appendix C — retired / shadowed
# ===================================================================
w("""## Appendix C — retired and shadowed paths

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
""")

# ===================================================================
# Appendix D — sortable fields
# ===================================================================
w("## Appendix D — sortable fields per list endpoint")
w()
w("`?sort=` is validated against the endpoint's comparator table; an unknown")
w("value is `400` `` unknown `sort` field for this endpoint ``. Endpoints not")
w("listed here take no `sort` at all.")
w()
w("| Endpoint | `sort` values | Comparator table |")
w("|---|---|---|")
SORTS = [
    ("GET /api/v0/downloads", "HandleDownloads", "inline `kComps` in `HandleDownloads`"),
    ("GET /api/v0/clients", None, "`ClientComparators()`"),
    ("GET /api/v0/downloads/{hash}/clients", None, "`FileClientComparators()` — built from `ClientComparators()`"),
    ("GET /api/v0/shared/{hash}/clients", None, "same as above"),
    ("GET /api/v0/known_clients", "HandleKnownClients", "inline `kComps` in `HandleKnownClients`"),
    ("GET /api/v0/shared", "HandleSharedList", "inline `kComps` in `HandleSharedList`"),
    ("GET /api/v0/servers", "HandleServers", "inline `kComps` in `HandleServers`"),
    ("GET /api/v0/friends", "HandleFriends", "inline `kComps` in `HandleFriends`"),
    ("GET /api/v0/chats", "HandleChats", "inline `kComps` in `HandleChats`"),
    ("GET /api/v0/search/{id}/results", "HandleSearchResults", "inline `kComps` in `HandleSearchResults`"),
    ("GET /api/v0/search", None, "`SearchListComparators()`",
     ["search_id", "query", "started_at", "result_count"]),
    ("GET /api/v0/categories", None, "`CategoryComparators()`", ["index", "name"]),
]
for row in SORTS:
    label, handler, table = row[:3]
    keys = row[3] if len(row) > 3 else (FUN[handler]["sort_keys"] if handler
                                       else ["name", "software"])
    w(f"| `{label}` | {', '.join('`' + k + '`' for k in keys)} | {table} |")
w()
w("Range and type validation for `limit` / `offset` and for the endpoint-specific")
w("query parameters lives in the shared `ParseUintParam` / `ParseBoolParam`")
w("helpers, so those `400 bad_request` rejections are not listed in the")
w("per-endpoint error tables; the accepted range is stated in each parameter")
w("table instead.")
w()
w("---")
w()

# ===================================================================
# How this was produced + self-checks
# ===================================================================
w(f"""## How this document was produced

Five scripts in this directory (`issues/inventory/`) read `src/webapi` and emit
the mechanical parts of this file, so a regeneration cannot keep a stale
hand-written line:

```sh
cd issues/inventory
python3 scan.py facts.json && python3 routes.py routes.json \\
  && python3 prefs.py prefs.json && python3 gendoc.py
```

| Script | What it extracts |
|---|---|
| `apiscan.py` | slices a C++ file into top-level function definitions. Comments and string-literal *contents* are blanked before brace counting, so a `{{` inside a comment or a JSON literal cannot desync the depth tracking. |
| `routes.py` | the route table straight out of `CApiDispatcher::DispatchToHandler`: every `path == "…"` literal, every `ParsePattern("…")`, the methods compared against, the handler called, and the `405`/`404` texts. |
| `scan.py` | per function: every `ErrorResponse(...)` / `BadRequestPtr(...)` / `BulkErr(...)` (parsed with a paren- and quote-aware scanner, not a regex, so a `;` or `,` inside a message is safe), every `qmap.find("…")` query key, every `obj.find("…")` body field, the `ListComparators` sort keys, the auth/admin/snapshot gates, and a JSON response skeleton folded from the ordered `CJsonWriter` calls (recursing into the `Write*` helpers each handler invokes). |
| `prefs.py` | all {len(P['rows'])} rows of the `PrefsSchema.cpp` data table — category, key, type, access, bounds, enum values, gates. |

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
except `GET /api/v0/chats/{{peer}}/messages`, which needs a live conversation with
a peer. That is how
the `/stats/graphs/{{graph}}` names in this document are `download_speed`,
`upload_speed`, `connections`, `kad_nodes` — a stale comment in `DispatchToHandler`
still calls them `download`/`upload`/`connections`/`kad`, and
`docs/api/REFERENCE.md` inherits other drift of the same kind.
""")

# ---- self-checks ---------------------------------------------------
def anchor(h):
    t = h.lstrip("#").strip().replace("`", "")
    keep = []
    for ch in t.lower():
        if ch.isalnum() or ch in " -_":
            keep.append(ch)
        elif ch == "\u2014":
            keep.append("-")
    return "".join(keep).strip().replace(" ", "-")


# Build the endpoint index from the headings actually emitted.
idx, in_ep = [], False
n_groups = n_eps = 0
for line in out:
    if line.startswith("## 5. Endpoints"):
        in_ep = True; continue
    if in_ep and line.startswith("## ") and not line.startswith("## 5."):
        in_ep = False
    if not in_ep:
        continue
    if line.startswith("### "):
        n_groups += 1
        idx.append(f"    - [{line[4:].strip()}](#{anchor(line)})")
    elif line.startswith("#### "):
        n_eps += 1
        idx.append(f"        - [{line[5:].strip().strip('`')}](#{anchor(line)})")
n_routes = sum(1 for b in R if b["kind"] != "prefix")
counts = (f"**{n_eps} endpoint sections** over **{n_routes} route blocks** in "
          f"`DispatchToHandler`, plus the SSE, static-file, country-flag and "
          f"CORS-preflight paths that live outside it.")
doc = "\n".join(out)
doc = doc.replace("<!--COUNTS-->", counts)
doc = doc.replace("<!--ENDPOINT-INDEX-->", "\n".join(idx))

# Rewrite `Name`, `File.cpp:NNN` / `Name` (`File.cpp:NNN`) refs to the function's
# current line, so an edit upstream cannot leave a stale pointer behind.
REF = re.compile(r'`([A-Za-z_]\w*)`(\s*\(|,\s+|\s+in\s+)`'
                 r'(Api\.cpp|App\.cpp|HttpServer\.cpp|SearchJson\.cpp|EventDiff\.cpp|StaticFs\.cpp)'
                 r':(\d+(?:-\d+)?)`')


def _fix(m):
    name, sep, f, _old = m.groups()
    occ = [e for e in ALLIDX.get(name, []) if e["file"] == f]
    if not occ:
        return m.group(0)
    return f"`{name}`{sep}`{f}:{occ[0]['start']}`"


unresolved = []
spans = []


def _fix2(m):
    name, sep, f, _old = m.groups()
    occ = [e for e in ALLIDX.get(name, []) if e["file"] == f]
    if not occ:
        unresolved.append(m.group(0))
        return m.group(0)
    return f"`{name}`{sep}`{f}:{occ[0]['start']}`"


for m in REF.finditer(doc):
    spans.append(m.span())
doc, n_fixed = REF.subn(_fix2, doc)

TOKEN = re.compile(r'`(?:Api|App|HttpServer|SearchJson|EventDiff|StaticFs)\.cpp:[0-9][0-9-]*`')
anchored = set()
for m in REF.finditer(doc):
    anchored.add(m.group(3) + ":" + m.group(4))
stale = sorted({m.group(0) for m in TOKEN.finditer(doc)
                if m.group(0).strip("`") not in anchored})

problems = []
# A single dispatcher block can serve several documented routes.
ROUTE_ALIASES = {
    "/api/v0/search/{id}/{action}": ["/api/v0/search/{id}/results",
                                     "/api/v0/search/{id}/stop",
                                     "/api/v0/search/{id}/more"],
}
for b in R:
    if b["kind"] == "prefix":
        continue
    wanted = ROUTE_ALIASES.get(b["path"], [b["path"]])
    for x in wanted:
        if x not in doc:
            problems.append(f"route not documented: {x} (block {b['path']})")
DELEGATORS = {"HandleBrowse", "DispatchToHandler", "Dispatch"}
for n in FUN:
    if n.startswith("Handle") and n not in COVERED and n not in DELEGATORS:
        problems.append(f"handler not documented: {n}")
for n in ("DispatchEvents", "PreflightEvents", "ServeStaticFile", "ServeCountryFlag"):
    if n not in COVERED:
        problems.append(f"handler not documented: {n}")

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "API_INVENTORY.md")
    open(dest, "w").write(doc.rstrip() + "\n")
    print(f"wrote {dest}: {len(doc.splitlines())} lines")
    print(f"rewrote {n_fixed} source refs from the live index; "
          f"{len(unresolved)} unresolved")
    if stale:
        print(f"refs NOT anchored to an indexed function ({len(stale)}):")
        for x in stale:
            print("   ", x)
    if problems:
        print("PROBLEMS:")
        for p_ in problems:
            print("  -", p_)
        sys.exit(1)
    print("coverage: every route block and every handler is documented")
