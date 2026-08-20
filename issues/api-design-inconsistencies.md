# amuleapi: design inconsistencies still open on the v0 surface

## Summary

The sixteen inconsistencies the first pass over `/api/v0/` turned up are all
resolved (the `/events` verb rejection, the categories envelope, trailing
slashes and empty captures, the two meanings of `limit`, the search envelope,
the four priority converters, `{ecid}` doubling as an address, the shadowed
capture routes, the three bulk-mutation conventions, the missing member `GET` on
categories, the four unknown-value spellings, the unauthenticated update state,
the hard-coded rate limiter, the three query-validation policies, the cold-start
`409`, and the missing health endpoint). This file is what a second pass found —
eight places where two endpoints still answer the same kind of question in two
different ways.

None of these is a bug: each answer is defensible where it stands, and the cost
is paid by the client, which has to learn the rule twice. Defects that produce a
*wrong* answer live in
[`api-protocol-and-correctness-bugs.md`](api-protocol-and-correctness-bugs.md);
pure renames live in
[`api-field-names-and-units.md`](api-field-names-and-units.md), which also
carries the R1–R12 rules this file argues against.

Verified against the source at commit `c80a7627a` and, where observable, a live
`amuleapi` on `127.0.0.1:4713`. Line numbers are from that tree; the function
names are the durable reference.

---

## 1. Omitted-vs-null is settled in the documentation and unsettled in the code

`docs/api/REFERENCE.md:287` now states the rule:

> A field whose value is not known is `null`, not a sentinel. […] A key is
> **omitted** only where absence itself is the meaning.

The download and shared objects follow it — `remaining_time`,
`last_seen_complete`, `last_upload` and `shared_since` all emit `null`. The rest
of the surface has not caught up:

| Where | What is omitted | Api.cpp |
|---|---|---|
| `/clients`, `/clients/{ecid}`, both per-file client routes, `client_*` SSE | `part_progress_percent`, when it is not computable | `:2954`, `EventDiff.cpp:268` |
| `/known_clients` | **eleven** keys behind **seven** guards — `name`; `ip`+`port`+`kad_port`; `country_code`; `software`+`version`; `source_origin`; `obfuscation`; `first_seen`+`sessions` | `:3021-3073` |
| `/downloads/{hash}`, `/shared/{hash}`, search results | `media`, omitted wholesale | `SearchJson.cpp:66` and the two file writers |
| `/shared/{hash}` | `parts`, when no availability data has been decoded | `:3195` |
| `/chats` | `last_message`, when the session has none | `:5730` |
| `/search` | `client_ecid`, `started_at`, `result_count`, per entry | `:7722` |
| `/stats/tree`, `/stats/graphs` | `key`, `label_value`, `token`, `extra`, `ratio`, and the graphs' `active_uploads` / `active_downloads` | `:7106`, `:7143` |
| four `SimpleConnControlOp` routes | `message`, when the daemon sent no string | shared helper |

Every one has a defensible local reason, and the reason is written down at each
site: "the daemon did not report this" has to stay distinguishable from "zero".
`null` satisfies all of them, at the cost of a few bytes, and it is what the
document now promises.

The one genuine exception is
`GET /…/{hash}/clients?include_parts=true` → `parts`: the caller opted in, so
the key's absence is the answer to a question they did not ask.

**Fix.** Apply the documented rule to the writers above. `WriteIntOrNull` and
its siblings already exist; `media` needs a `null` branch rather than a skipped
object.

---

## 2. `GET /categories` can return a `priority` that `PATCH /categories/{index}` refuses

The read path formats the priority with the shared `PriorityName`
(`Refresher.cpp:2580` → `:377`), which can return any of the six file
levels — including `very_low` and `release`. The write path validates against
`FilePriorityToCode(name, kPrioCategory)` (`Api.cpp:3710`), whose category
domain admits only `low` / `normal` / `high` / `auto`.

So a category whose stored priority is `very_low` or `release` reads back a
value that cannot be sent again: the ordinary read-modify-write round trip
(`GET`, change the name, `PATCH` the whole object back) answers `400` naming a
field the client never touched.

**How reachable is it?** Barely, and this is the reason the section is short.
The desktop's category priority control offers only *Don't change* / Low /
Normal / High / Auto (`muuli_wdr.cpp`, the `IDC_PRIOCOMBO` choice list), and
`CDownloadQueue::SetCatPrio` (`DownloadQueue.cpp:1237`) applies whatever it is
given as a *download* priority — the same domain the API accepts. So no ordinary
path puts one of the two extra values into a category; a hand-edited
`amule.conf`, or a category written by some other client, is what it would take.

The asymmetry itself is deliberate on the *download* side and documented there:
the `.part.met` loader clamps anything outside low/normal/high back to normal on
restart. Categories inherit the download set for the same reason. What is not
deliberate is that the read side, which shares `PriorityName` with downloads and
shared files, can name two levels the write side refuses.

**Fix.** Proportionate to how rare it is: **document the asymmetry** in the
reference's [Priority levels](#priority-levels) section — the category read
domain is the six-value file set, the write domain is four — and leave the code
alone.

Clamping on read was the tempting answer and is worse: the API would report
`high` for a category the daemon holds as `release`, and the client's write-back
would then persist that lie. Widening the write domain is worse too — the value
would survive one session and be clamped to normal by the partfile loader on the
next restart, which is the silent rewrite the download path refuses `very_low`
and `release` to avoid. Between two ways of quietly changing a user's setting
and one sentence in a document, the sentence wins.

---

## 3. `POST /api/v0/downloads` accepts two spellings of one input

The body parser takes both (`Api.cpp:4754-4768`):

```
{"ed2k_link": "ed2k://|file|…|/"}          // singular
{"links": ["ed2k://|file|…|/", …]}         // array
```

Two names for the same input, on the one endpoint that already answers with the
bulk `results` envelope for a single item. A client reading the reference has to
be told which to use, and every future field that varies by arity inherits the
question.

**Fix.** `links` only — `links: ["…"]` covers the single case, and the response
is already an array of per-item results either way. This is the same collapse
the three `*/update` endpoints need for their `servers_url` / `nodes_url` /
`ipfilter_url` spellings.

---

## 4. `include_completed` is a boolean over a three-state axis

`GET /downloads?include_completed=` answers "active only" (default) and
"active plus completed". There is no way to ask for *completed only*, which is
the third state the collection actually has and the one a "Finished" tab needs.

The parameter also names the mechanism rather than the axis: a client reading
`include_completed=false` cannot tell whether the excluded rows are hidden or
absent.

**Fix.** `status=active` (default) / `status=all` / `status=completed`, with
`400` on anything else. The validation half already landed — an unparseable
value is a `400`, not a silent false — so what is left is the axis. `status` is
also the key the download object already reports, so the filter and the field
agree (R7 in the naming document).

---

## 5. Fourteen mutation-response shapes, and a `PATCH` that answers with less than its `GET`

Fourteen distinct `{ok, …}` shapes across the surface — `{ok}`,
`{ok, message}`, `{ok, ecid}`, `{ok, hash}`, `{ok, hash, category}`,
`{ok, address}`, `{ok, index}`, `{ok, name, index?}`, `{ok, ip, port}`,
`{ok, peer}`, `{ok, peer, message{…}}`, `{ok, search_id}`,
`{ok, search_id, query}`, `{ok, <servers_url|nodes_url|ipfilter_url>}` — plus
the full mutated object, the bulk `results` envelope and `204 No Content`.
**22 response bodies carry a constant `"ok": true`**, which the status code
already said. (The per-item `ok` inside `results[]` is the one that is real
data.)

Underneath that, the single-resource mutations disagree with their own reads.
Measured live:

| Route | Keys returned | `GET` on the same URL |
|---|---|---|
| `PATCH /downloads/{hash}` (`Api.cpp:5184`) | 15 | 32 |
| `PATCH /shared/{hash}` (`Api.cpp:8925`) | 16 | 27 |
| `PATCH /servers/{ecid}` | `{ok, ecid}` | the full server object |
| `PATCH /friends/{ecid}` | the friend object | the friend object |

So a client that PATCHes and stores the response has a *different* object than
one that PATCHes and re-GETs — silently missing the `progress.parts` array and
sixteen other keys. `PATCH /friends/{ecid}` is the one that gets it right and is
the model to copy.

Creations are a third convention: `POST /servers` answers `{ok, address}` with
no id at all, `POST /categories` answers `{ok, name, index?}` and drops `index`
when the post-create rescan misses it, `POST /friends` answers with the friend
object — or a bare `{ok: true}` when the new friend has not surfaced in the
snapshot yet.

**Fix.** One rule, three cases:

- A mutation that changes a resource returns **the resource, in the shape `GET`
  on that URL returns**.
- A creation returns the created resource plus a `Location` header.
- A pure action with nothing to report returns `202`/`204` with **no body**, and
  every constant `"ok": true` goes.

---

## 6. Two single-valued `status` enums, on a key that means something else everywhere

Three endpoints answer with a one-value enum under `status`:

| Route | Body | Api.cpp |
|---|---|---|
| `POST /downloads/{hash}/comments` | `{"status": "kad_search_started"}` | `:4396` |
| `POST /search/results/{hash}/comments` | `{"status": "kad_search_started"}` | `:10794` |
| `POST /version/check` | `{"status": "started"}` | `:4735` |

A field that can only hold one value carries no information, and `status` on
every other object on this surface is a *transfer* state (`downloading`,
`paused`, `hashing`, …). A client switching on `status` has to know which kind
of object it is holding first.

**Fix.** `202 Accepted` with no body on all three — the status code is the
"started" these are trying to say. The two comment routes are one shape written
twice, so they move together.

---

## 7. `FileTypeToken` and `SearchTypeToken` are the same function, twice

`Api.cpp:3182` and `Refresher.cpp:2361` are identical, character for character:

```cpp
const wxString desc =
        GetFiletypeByName(CPath(wxString::FromUTF8(name.c_str())), /*translated=*/false);
std::string s(desc.utf8_str());
std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
});
return s;
```

They feed `file_type` on `/shared/{hash}` and `type` on a search result — two
key names for one enum, which is the naming half of the problem and is tracked
in the naming document. The code half is here: two copies means a change to the
token set can land in one and not the other, and nothing in either file says the
other exists.

**Fix.** One function. `Refresher.h`, `OtherFunctions.h` and `State.h` are already included by both translation units, so there is somewhere obvious to put it.

---

## 8. `GET /preferences` does not say which of its 125 fields you are allowed to write

The payload is flat: 125 keys under 13 categories, all looking alike. Four
different things are mixed in it, and nothing in the response distinguishes
them.

| Kind | Example | On `PATCH` |
|---|---|---|
| settable | `files.mmap_enabled` | applied |
| read-only status | `files.mmap_supported`, `connection.upnp_available`, six `ip2country.*` | swallowed |
| write-only | three rows | applied, never echoed |
| refused | `remote_controls.amuleapi.{password,guest_password,guest_enabled}` | `400` |

The schema knows all four — `PrefAccess` (`PrefsSchema.h:72`) has exactly these
levels, `ReadWrite` / `ReadOnly` / `WriteOnly` / `Rejected` / `Bespoke` — and
none of it reaches the client, in the payload or in the reference.

**The error message makes it worse rather than better.** Patching a read-only
row on its own:

```
$ curl -X PATCH -d '{"files":{"mmap_supported":false}}' …/api/v0/preferences
{"error":{"code":"bad_request","message":"request body did not include any known pref fields"}}
```

`mmap_supported` *is* a known pref field — the same endpoint emitted it in the
`GET` a moment earlier. The daemon is answering "no such field" to a field it
publishes, because the writable-field scan skips `ReadOnly` and `Bespoke` rows
(`Api.cpp:8347`) and the "nothing matched" branch cannot tell an unknown key
from a skipped one.

**And the same key behaves differently depending on its company:**

```
$ curl -X PATCH -d '{"files":{"mmap_supported":false,"mmap_enabled":false}}' …
200
```

Sent alone it is an error; sent alongside a writable field it is silently
dropped and the request succeeds. That matters because the read-modify-write
round trip — `GET` the object, flip one value, `PATCH` it back — is the obvious
way to use this endpoint, and it necessarily sends the read-only rows back. It
works today by accident, through the swallow path.

**Two rows also break the schema's own bookkeeping**, in opposite directions:

- `remote_controls.amuleapi.{password,guest_password,guest_enabled}` are three
  `PREF_REJECT` rows (`PrefsSchema.cpp:222-224`) that exist *only* to be
  refused. They never appear on `GET`, so a client can discover them only by
  sending one. Their rejection message is good — *"amuleapi passwords are
  managed through PATCH /auth/passwords, not through /preferences"* — which is
  precisely the sentence the reference should be carrying up front instead of
  making a client find it by trial.
- `remote_controls.webserver.guest_password` is the mirror image: it *is*
  writable, through the hand-written `Bespoke` branch that packs it with
  `guest_enabled` into one EC tag (`Api.cpp:8409`), but it appears in no schema
  table and in no `GET` response. It is invisible to anything generated from the
  schema, this repo's own inventory included.

**Fix.** Three parts, none of them large:

1. An explicit `access` column in the reference's preference table, filled from
   `PrefAccess`, so a client can see before it writes. The data already exists;
   only the documentation is missing.
2. Make the read-only rejection truthful: a body naming *only* non-writable
   fields should say which ones and why (`\`files.mmap_supported\` is read-only`),
   not "no known pref fields". Keep swallowing them when they arrive alongside a
   writable field, so read-modify-write keeps working, and say *that* in the
   reference too.
3. List the three `amuleapi.*` rows in the reference with their real behaviour
   and their existing message, and give `webserver.guest_password` the schema
   row it never had.

Explicitly **not** a `status` sub-object per category: it would separate the
read-only rows cleanly, but it also breaks the 1:1 mapping between a JSON
category and a desktop preferences tab, which is what keeps a 125-field payload
navigable.

---

## Scope

Eight independent changes. §2, §7 and §8 are contained and can land as-is — one
is documentation only, one a deduplication, the third documentation plus one
schema row and a truthful error message. §3, §4 and §6 change a request or
response shape, and §1 and §5 change one broadly; all five belong in the same pass as the renames in
[`api-field-names-and-units.md`](api-field-names-and-units.md), for the same
reason that issue gives: `/api/v0/` has no consumers outside this repository
today, and every one of these is a breaking change that gets more expensive the
longer it waits.

§1 is the one worth doing as a single sweep rather than piecemeal: a rule that
half the surface follows is harder for a client to work with than one nothing
follows, because there is no way to tell which half you are holding.
