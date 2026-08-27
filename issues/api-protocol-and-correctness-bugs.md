# amuleapi: protocol and correctness bugs still open on the v0 surface

## Summary

Currently open on `/api/v0/`: two SSE-behaviour defects, a wide swathe of
reference documentation that has drifted from the code (~20 sites), and two stale
code comments. None is a code bug in the request path — each is a client, coding
to the stream or the reference, getting an answer the daemon does not give, or a
comment that lies about the code beside it. None is naming, so none belongs in
[`api-field-names-and-units.md`](api-field-names-and-units.md).

Grouped by kind:

- **SSE disagrees with REST / its own docs** (§1, §2) — one field emitted with
  the wrong type on the stream, and an event class that never pushes the updates
  it documents.
- **The reference has drifted from the code** (§3) — ~20 places where
  `REFERENCE.md` or `EVENTS.md` states a shape, enum, error code, event or worked
  example the code does not produce, several of them contradicting the reference's
  own rules or its sibling document.
- **A code comment contradicts its code** (§4) — two stale comments in
  `src/webapi/Api.cpp`, comment-only edits, not client-visible.

Verified against the source and, where observable, a live `amuleapi` on
`127.0.0.1:4713`, at commit `43c1dad16`. Line numbers are from that tree; the
function names are the durable reference.

---

## 1. The shared SSE payload emits `last_upload` / `shared_since` as raw `0`; REST emits `null`

The REST writer for a shared file routes both timestamps through
`WriteIntOrNull`, emitting `null` when the value is `0`
(`src/webapi/Api.cpp:3215-3220`), and the comment beside it says why:

```cpp
// `last_upload` / `shared_since` are unix seconds, null when unknown --
// never uploaded, or a known.met entry that predates the field. They were 0,
// which reads as 1970 rather than "no idea".
WriteIntOrNull(w, "last_upload",  f.shared.last_upload  != 0, …);
WriteIntOrNull(w, "shared_since", f.shared.shared_since != 0, …);
```

The SSE writer two functions over does **not** guard them
(`src/webapi/EventDiff.cpp:179-180`):

```cpp
<< ",\"last_upload\":"  << f.shared.last_upload
<< ",\"shared_since\":" << f.shared.shared_since
```

So a file that has never uploaded (`last_upload == 0` — the common case) or
carries an old `known.met` (`shared_since == 0`) is pushed over SSE as
`last_upload: 0` / `shared_since: 0` but read over REST as `null`. This is the
routine case, not an edge one.

The contradiction is documented twice against the code:
`EVENTS.md:265` promises the `shared_added` / `shared_updated` payloads are
byte-for-byte identical to the matching REST list-item shape, and
`REFERENCE.md:1482` documents both fields as `null` when unknown. A client that
hydrates from REST and live-updates from SSE holds a `null` that flips to `0`
the first tick the file changes, and a renderer that treats the number as a
timestamp draws 1970-01-01.

`available_parts` and `remote_queue_rank` had exactly this shape and were fixed
on both surfaces; this pair is the one the SSE side of that pass missed.

**Fix.** Emit `null` for `0` in the SSE writer too — route both through
`WriteIntOrNull`, or mirror its guard inline. The `Equal` predicate at
`EventDiff.cpp:424-425` already compares the raw values and needs no change.

**Test.** An SSE curl case asserting a never-uploaded file arrives with
`last_upload: null`, matching its `GET /shared/{hash}`.

---

## 2. `search_result_added` is add-only, so a hit's mutating fields never update over SSE

The search channel emits `search_result_added` only the first time an ECID
appears in the results map (`src/webapi/EventDiff.cpp:934-935`, "per new ECID"),
and there is no `search_result_updated`. But `WriteSearchResultFields`
(`SearchJson.cpp:36-138`) serializes fields that change over a result's life:
`sources.total` / `sources.complete` grow as sources are found,
`already_have` / `status` change when the file starts downloading,
`children[]` grows as the same hash is seen under new names, and
`kad_comment_search_running` + `comments[]` change when a Kad NOTES lookup
lands.

`EVENTS.md:265` tells a client that a `*_updated` event "get[s] the full new
state and never need[s] to re-GET." For the search channel that promise does not
hold: only brand-new hits and the search's own `search_progress` (percent) ever
push. A subscriber that builds a results view purely from the stream freezes
each hit's source counts, download status, comment set and alternate-name list
at first-seen.

This is partly by design — `search_progress` is the intended re-poll cue — but
the surface documents a push contract it does not keep for this one channel, and
a client cannot tell from the payload that these rows are add-only.

**Fix.** Either re-fire `search_result_added` (or add a `search_result_updated`)
when a tracked result's serialized fields change, matching the download and
shared channels; or state in `EVENTS.md` that search rows are add-only and a
`search_progress` frame is the signal to re-GET the results.

**Test.** An SSE case asserting that a result whose `sources.total` grows either
pushes a fresh frame or is documented as requiring a re-GET.

---

## 3. `REFERENCE.md` and `EVENTS.md` have drifted from the code in ~20 places

The reference carries drift the second-pass fixes never swept out of the
per-endpoint prose and worked examples. Three causes: the omitted-vs-null pass
made keys always-present that the sections still call "omitted"; the
mutation-response collapse changed bodies the sections still show; and several
enum, error-code and example lists were never reconciled with the writers. None
is a code bug — each is a client, coding to the document, getting an answer the
daemon does not give.

### 3a. "Omitted" keys that the code always emits as `null`

`REFERENCE.md:352` already states the rule — a null-capable field is *always
present*, `null` when unknown — yet these per-endpoint sections still tell a
client the key is absent, so a client testing `"key" in obj` gets a false
positive every time:

| Key / object | Doc claims "omitted/absent" | Code always emits `null` |
|---|---|---|
| `media` on `GET /downloads/{hash}` | `REFERENCE.md:867`, `:871-873` | `WriteMediaIfPresent`, `Api.cpp:2798` |
| `media` on `GET /shared`, `/shared/{hash}` | `:1490`, `:1520` | same helper |
| `media` on a search result | `:2794` (and `EVENTS.md:591` says `null`, contradicting it) | `SearchJson.cpp:69` |
| `last_message` on `GET /chats` | `:2989` | `WriteChatObject`, `Api.cpp:5948` |
| `label_value` on a `/stats/tree` node | `:2535` | `WriteStringOrNull`, `Api.cpp:7305` |
| `token` on a `/stats/tree` value | `:2548` ("absent") | `WriteStringOrNull`, `Api.cpp:7274` |

Separately, `EVENTS.md:325` shows the `shared_added` / `shared_updated` payload
with **no `media` key**, but `ToJsonSharedEvent` always emits it
(`EventDiff.cpp:190`) and `EqualShared` compares it, so a re-extraction fires a
`shared_updated` — which `REFERENCE.md:1492` documents and `EVENTS.md` omits.

### 3b. Enum/token lists that do not match what the writer emits

| Field | Doc lists | Code emits |
|---|---|---|
| `progress.parts[].state` | `transferring` / `complete` / `empty` / `corrupt` (`:849`, `:987`) | `complete` / `incomplete` / `missing` (`WriteProgressParts`, `Api.cpp:2708`) — only `complete` overlaps |
| download `status` | eight values (`:820`) | eleven — the doc omits `erroneous`, `insufficient_disk`, `unknown` (`DownloadStatusName`, `Refresher.cpp:360-368`) |

A client switching on the documented `parts[].state` renders nothing for the two
states that actually occur; one switching on `status` mishandles a partfile that
errors or fills the disk.

### 3c. A documented SSE event that is never emitted

`REFERENCE.md:1327` says the browse "emits a `search_finished` SSE event". No
such event exists — the emitters are `search_result_added` / `search_progress` /
`search_closed` (`EventDiff.cpp:948`, `:969`, `:991`), and both
`EventDiff.cpp:904` and `EVENTS.md:595` say in as many words there is **no**
`search_finished`; completion is the terminal `search_progress` with
`"state": "finished"`. A client waiting for `search_finished` waits forever, and
the two docs contradict each other.

### 3d. Wrong or missing error codes

| Endpoint | Doc | Code |
|---|---|---|
| browse (`POST /clients/{ecid}/shared_files`) | `502 bad_gateway` (`:1360`) | `502 amuled_rejected` (`Api.cpp:10350`) |
| `DELETE /categories/0` | `400 amuled_rejected` (`:2117`) | `400 bad_request`, rejected locally (`Api.cpp:10211`) |
| `PATCH /preferences` | table omits it (`:2298`) | `409 conflict` on an unsupported option (`Api.cpp:8542`) |
| `PATCH /shared/{hash}` | table omits it (`:1758`) | `404 not_found` for an unknown hash (`Api.cpp:9024`) |
| `POST /servers/{ecid}/connect` | table omits it (`:1882`) | `400 amuled_rejected` (`Api.cpp:6751`) |
| `POST /networks/{connect,disconnect}` | tables omit it (`:2314`, `:2324`) | `400 amuled_rejected` (`Api.cpp:8684`) |
| error catalog (`:3073`) | omits `not_readable` | per-item `403 not_readable` from `/share_directories` (`Api.cpp:9548`) |

(`GET /search/{id}/results` also lists a `503 ec_unavailable` it cannot emit,
`:2812` — the cache path never returns 503. Minor.)

### 3e. Response shapes and worked examples the writer contradicts

| Endpoint | Doc shows | Code produces |
|---|---|---|
| `GET /categories` top example | category 0 as `"All"` / `"normal"` (`:2046`) | `"Default"` / `"low"` (`Api.cpp:5814`) — the section's own detail example at `:2064` already agrees with the code |
| browse `202` body | `client_ecid: <ecid>` (`:1344`) | `client_ecid: null` — the row is built without setting it (`Api.cpp:10391`) |
| `POST`/`PUT`/`DELETE /share_directories` | `{ok, rejected}`, failures as flat `{code, message}` / "`reason`" (`:1647`, `:1670`, `:1692`) | the bulk envelope `{results:[{id, ok, error:{code, message}}]}` (`Api.cpp:4788`) |
| `POST /servers_update` | `servers_url` optional, falls back to a preference (`:1935`) | `servers_url` is required; omitting it is a `400` (`Api.cpp:6828`) — unlike `/ipfilter/update`, which does have the fallback |
| `POST /chats/{peer}/messages` | the store-assigned timestamp is readable in the reply (`:3033`) | the reply carries only `id` / `direction` / `text` (`Api.cpp:6257`) |
| `POST /networks/{connect,disconnect}` | no body (`:2312`, `:2322`) | a `{message}` body from the daemon (`Api.cpp:8706`) |
| `/stats/tree` value/node examples | omit `token` / `extra` / `label_value` (`:2554-2606`) | those keys are always present (as `null`), per `:352` |

**Fix.** All documentation, no code: reconcile each site with the writer. The
systemic ones (3a, and the examples in 3e) are the residue of the
omitted-vs-null and mutation-response passes not reaching the per-endpoint prose;
the durable guard against the next drift is to generate the worked examples from
the serializers, the way `issues/inventory/` already derives the shapes.

---

## 4. Two code comments contradict the code they describe

Neither is client-visible — both are stale comments in `src/webapi/Api.cpp` that
a fix changed the code beneath without updating. They belong here because
`CLAUDE.local.md` requires a comment not to contradict the code it describes, and
a reader trusting either is misled.

### 4a. `SimpleConnControlOp` still documents the dropped `ok` field

`Api.cpp:8671-8674`:

```cpp
// ... return a standard
// `{ok: true, message?: "..."}` response. Used by every connection-
// control endpoint where the EC op is parameterless.
```

The mutation-response pass dropped `ok`; the helper now emits `{message?}` only
(`Api.cpp:8706-8718`, whose own inline comment reads "`ok` dropped"). Fix the
header comment to `{message?: "..."}`.

### 4b. The download-`PATCH` priority comment lists two values the handler rejects

`Api.cpp:5248`:

```cpp
// priority: "very_low"|"low"|"normal"|"high"|"release"|"auto"
```

Two lines below, the write goes through
`FilePriorityToCode(…, kPrioDownload, …)` (`Api.cpp:5257`), and the
`kPrioDownload` domain admits only `low` / `normal` / `high` / `auto` —
`very_low` and `release` are `kPrioShared`-only (`Api.cpp:3825`, `:3829`) and
refused on a download by design (rationale at `Api.cpp:3801`). So the comment
names two levels a `400` rejects. Drop `very_low` and `release` from it (or mark
them "upload-side only").

Both are one-line comment edits; because they touch a `.cpp`, run clang-format 18
on the file afterward, per `CLAUDE.local.md`.

---

## Scope

Two code-behaviour fixes, one documentation sweep and two comment corrections,
none needing an EC change. §1 changes an SSE value from a number to `null` to
match REST — the same additive change the second pass made for `available_parts`
and `remote_queue_rank`, and the cheapest to land. §2 is the one design choice:
either the search channel pushes updates like its siblings, or `EVENTS.md`
documents that it does not — the second is smaller and honest if the add-only
model stays. §3 is entirely in `docs/`; the omit-vs-null (3a) and example (3e)
rows are the ones a client is most likely to code against and get wrong, so they
are the first to fix. §4 is two one-line comment edits, safe to land anytime.
