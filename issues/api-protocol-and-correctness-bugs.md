# amuleapi: protocol and correctness bugs still open on the v0 surface

## Summary

The thirteen defects the first pass over `/api/v0/` turned up are all fixed
(`HEAD` bodies on error responses, the bracketed `server_ip`, the silent close
on an oversize request, the `comments_updated` payload, the `log`/`logs`
channel, the error catalog, the stats-graph comment, the two static-asset
ETags, unverified search `media`, the `304` served for changed content, the
missing `Allow` header, the CORS method list). This file is what a second pass
found — ten defects that are *not* naming, and so do not belong in
[`api-field-names-and-units.md`](api-field-names-and-units.md).

Each one is a client getting a wrong answer, an undecodable one, or one that
contradicts the documentation. None needs an EC protocol change; §4 and §5 are
the two that reach into `src/` proper rather than `src/webapi`.

Grouped by kind:

- **A value that cannot be read back correctly** (§1, §9) — a gate that exists
  but is never applied, and an undocumented sentinel.
- **Type asymmetry** (§2) — one key, a string on the way in and a number on the
  way out.
- **Silent truncation and wrap** (§4, §5) — two preference families where the
  value a client writes is not the value the daemon stores, with nothing said.
- **Code and documentation disagree** (§3, §6).
- **Actions that do not survive a retry** (§7).
- **A filter and a cap that mean the opposite of what they look like**
  (§8, §10).

Verified against the source and, where observable, a live `amuleapi` on
`127.0.0.1:4713`, at commit `c80a7627a`. Line numbers are from that tree; the
function names are the durable reference.

---

## 1. `available_parts` is emitted unconditionally, so "tag absent" reads as "zero parts"

`ClientSnapshot` carries a flag whose only purpose is to gate this field
(`src/webapi/State.h:433`):

```cpp
bool has_available_parts = false;  // false => tag absent, omit the field
```

The refresher sets it when the EC tag arrives (`Refresher.cpp:1086`). Nothing
reads it. `WriteClientBaseFields` emits the value regardless
(`src/webapi/Api.cpp:2946`):

```cpp
w.Key("available_parts");
w.ValueInt(static_cast<int64_t>(c.available_parts));
```

So a peer that never reported how many parts it holds is indistinguishable from
one that reported holding none — and "none" is a meaningful answer here, since
it is what a fresh source looks like before its part map arrives.

Because the field lives in the *base* writer, the defect ships on five
surfaces: `GET /clients`, `GET /clients/{ecid}`,
`GET /downloads/{hash}/clients`, `GET /shared/{hash}/clients`, and the
`client_*` SSE payload (`EventDiff.cpp:259`). One guard fixes all five.

**Fix.** Emit `null` when `has_available_parts` is false — matching what
`remaining_time`, `last_upload` and `shared_since` already do since the
unknown-value pass. `WriteIntOrNull(w, "available_parts", c.has_available_parts,
c.available_parts)` is the whole change, plus the matching branch in
`EventDiff.cpp` (and its `Equal` predicate, or the field never updates).

**Test.** A curl case asserting the key is present and `null` for a peer with no
part map.

---

## 2. `POST /api/v0/kad/bootstrap` takes `ip` as a string and echoes it as a number

The handler accepts either spelling (`Api.cpp:8755-8773`):

```cpp
const auto it = obj.find("ip");
if (it->second.is<std::string>()) {
        if (!ParseIpv4Dotted(s, ip_he)) { … }        // "1.2.3.4"
} else {
        ip_he = static_cast<std::uint32_t>(v);        // 16909060
}
```

and answers with the host-order integer, whichever form came in
(`Api.cpp:8815`):

```cpp
w.Key("ip");
w.ValueInt(static_cast<int64_t>(ip_he));
```

One key, two types on the two sides of the same request. A client that posts
`{"ip": "1.2.3.4"}` and stores the reply now holds `{"ip": 16909060}`, which it
cannot post back without converting, and which no other endpoint on the surface
would produce — every other IP is a dotted quad (`Uint32toStringIP`,
`FormatClientIpv4`).

**Fix.** Echo the dotted quad. `Uint32toStringIP(ip_he)` is already in the file
and is what the peer and server rows use.

**Test.** A curl case asserting `POST {"ip":"1.2.3.4","port":4672}` answers
`"ip":"1.2.3.4"`.

---

## 3. `DELETE /api/v0/logs/*` answers `204`; the reference documents `{"ok": true}`

`docs/api/REFERENCE.md:2404`:

> `DELETE /api/v0/logs/serverinfo` clears the buffer and returns `{ "ok": true }`.

and `REFERENCE.md:2386` shows the same body for `DELETE /api/v0/logs/amule`.

The daemon returns `204 No Content` with an empty body, on both log routes:

```
$ curl -s -o /dev/null -w '%{http_code}\n' -X DELETE …/api/v0/logs/serverinfo
204
```

A client written from the document parses the empty body as JSON and fails on a
call that succeeded.

**Fix.** The `204` is the right answer — a pure action with nothing to report.
Correct both places in the reference instead of the code.

---

## 4. `online_signature.update_frequency_seconds` accepts values the core cannot hold

The preference schema declares a `uint32` with the full range
(`src/webapi/PrefsSchema.cpp:229`):

```cpp
PREF_U32("online_signature", "update_frequency_seconds", EC_TAG_ONLINESIG_UPDATE,
         0xFFFFFFFFu, PrefAccess::ReadWrite, online_signature.update_frequency_seconds),
```

The core member behind it is 16 bits (`src/Preferences.h:1202`,
`static uint16 s_OSUpdate;`, written through `SetOSUpdate(uint16)` at `:738`).
Anything above 65535 wraps: a client that sets 86400 (daily) gets 20864
(≈ 5.8 hours) and is told nothing — the `PATCH` succeeds and the subsequent
`GET` reports the wrapped value.

**Fix.** Cap the schema row at `65535u`, so an out-of-range value is the `400`
every other numeric parameter already answers. The one-line alternative — widen
the core member — is an ABI change to `amule.conf` handling for a setting whose
useful range is minutes.

**Test.** A curl case asserting `PATCH {"online_signature":
{"update_frequency_seconds": 86400}}` is a `400`.

---

## 5. The three `core_tweaks.*_ms` preferences silently truncate to whole minutes

The API names and accepts milliseconds (`PrefsSchema.cpp:234`, `:237`, `:238`):
`kad_reask_ms`, `source_reask_ms`, `server_keepalive_timeout_ms`. The core
stores **minutes** (`src/Preferences.h:374-384`):

```cpp
static uint64 GetServerKeepAliveTimeout() { return s_dwServerKeepAliveTimeoutMins * 60000; }
static void SetServerKeepAliveTimeout(uint64 val) { s_dwServerKeepAliveTimeoutMins = val / 60000; }
```

So the write path integer-divides by 60000. A client that sets
`kad_reask_ms: 90000` (90 s) reads back `60000`; one that sets `30000` reads
back `0`. The value is accepted, the response is a success, and the number
changes underneath. Nothing in the schema, the response or the reference says
the field is quantised.

**Fix.** Two options, both without an EC change:

1. Convert at the API boundary — `GET` divides the EC value by 60000, `PATCH`
   multiplies by 60000 — and rename the fields to `_minutes` (the rename is
   tracked in [`api-field-names-and-units.md`](api-field-names-and-units.md)
   §1.9). A client that writes `2` then reads `2`, which is the point.
2. Keep milliseconds and document the quantisation, rejecting a value that is
   not a whole number of minutes rather than truncating it.

Option 1 is the honest one: the field cannot express what its name promises.

---

## 6. The synthesized category 0 serves fabricated values that contradict the reference

When amuled reports no index-0 category, `CategoriesWithDefault`
(`src/webapi/Api.cpp:5625`) inserts one:

```cpp
webapi::CategorySnapshot d;
d.index = 0;
d.priority_code = 0;   // PR_LOW (matches amuled default)
d.priority = "low";
cats.insert(cats.begin(), std::move(d));
```

`name`, `path` and `comment` are left default-constructed, so the row goes out
as `{"index":0,"name":"","path":"","comment":"","color":0,"priority":"low"}`.
The reference documents that same row as
(`docs/api/REFERENCE.md:1978-1985`):

```json
{ "index": 0, "name": "All", "path": "/home/user/aMule/Incoming",
  "comment": "", "color": 0, "priority": "normal" }
```

Two of the four values disagree, and a UI that renders the category picker from
this shows a nameless entry where the document promises "All". (On a daemon
that *does* report category 0 — the common case — the real values come through
and the divergence is invisible, which is why it has survived.)

**Fix.** Either fill the synthesized row with the values the reference
promises — `name: "All"`, `path` from `directories.incoming`,
`priority: "normal"` — or document what it actually emits. The first matches
what a client expects "the category every download without a category belongs
to" to look like.

**Test.** A curl case is awkward here (it needs a daemon that omits the row); a
unit test over `CategoriesWithDefault` is the natural home.

---

## 7. `swap_this_auto` is a toggle, so retrying the request undoes it

`POST /api/v0/downloads/{hash}/a4af` takes three actions
(`src/webapi/Api.cpp:4494`); `swap_this_auto` maps to
`EC_OP_PARTFILE_SWAP_A4AF_THIS_AUTO`, which the core implements as
(`src/GuiEvents.cpp:869`):

```cpp
file->SetA4AFAuto(!file->IsA4AFAuto());
```

A flip, not a set. The API exposes no way to request a *value*: a client that
wants "auto on" has to read `a4af_auto`, compare, and conditionally POST — and
if the response is lost to a timeout and it retries, the flag ends up back where
it started. Two identical requests are not the same as one, on an endpoint whose
two sibling actions are ordinary commands.

**Fix.** Move the flag to where a value can be set:
`PATCH /downloads/{hash} {"a4af_auto": true}`, reading and writing the same key
the download object already reports. The `swap_this_auto` action can stay as a
deprecated alias or go; the other two A4AF actions are genuine commands and stay
where they are.

**Test.** A curl case asserting that setting the flag twice leaves it set.

---

## 8. `?channels=` with an empty value turns filtering off instead of selecting nothing

`GET /api/v0/events` builds its channel filter only when the parameter has a
value (`src/webapi/Api.cpp:10951`):

```cpp
const auto it = qmap.find("channels");
if (it != qmap.end() && !it->second.empty()) {
        channels_set = true;
        …
}
```

So `?channels=` — which a client produces the moment it joins an empty selection
list, the single most common way to end up with one — subscribes to **every**
channel rather than none. A UI with all its event categories unchecked receives
the full firehose.

Note that "all channels" already has its own well-defined spelling: **omit the
parameter**. `EVENTS.md:169` says so — "By default every channel is delivered" —
and that stays true, so the three cases a client needs are

| Request | Meaning |
|---|---|
| no `channels` parameter | every channel (the default, unchanged) |
| `?channels=downloads,status` | those two |
| `?channels=` | today: every channel. That is the bug. |

**Fix.** Reject it: `400 bad_request`. The surface already adopted the rule —
`REFERENCE.md:217`, "an empty value (`?limit=`) is a `400`, not an omission" —
and this is the parameter that would otherwise be its exception.

The tempting alternative, reading the empty string as the empty set, is worse
here even though it is the tidier set semantics. Because there is already a way
to say "everything", the empty string does not have to carry a meaning, so
giving it one buys nothing and costs the rule a per-parameter carve-out. And on
SSE specifically the failure mode is bad: a stream that opens, heartbeats, and
delivers nothing forever is indistinguishable from a broken one, so a client
that built that URL by accident — which is the whole reason this defect matters —
gets a debugging session instead of an error message. A client that genuinely
has nothing selected should not be holding a stream open at all.

**Test.** An SSE curl case asserting `?channels=` answers `400`, and one
asserting the parameter's absence still delivers every channel.

---

## 9. `remote_queue_rank` carries an undocumented `65535` sentinel

The core substitutes a magic value when the peer's queue is full
(`src/ECSpecialCoreTags.cpp:474-475`):

```cpp
EC_TAG_CLIENT_REMOTE_QUEUE_RANK,
client->IsRemoteQueueFull() ? (uint16)0xffff : client->GetRemoteQueueRank(),
```

amuleapi relays it verbatim (`Api.cpp:2931`). The reference shows the field as
an ordinary number (`REFERENCE.md:1147`, `:1224`, both `"remote_queue_rank": 0`)
and never mentions the sentinel, so a client renders "position 65535 in the
queue" for what means "that queue is full".

**Fix.** Emit `null` for `0xffff` (the surface's established spelling for "no
value") and say so, or keep the number and document it. `null` is better: a
client sorting peers by queue position otherwise buries the full ones at the
bottom of the list as if they were merely very far back.

---

## 10. `limit` caps the request that asks and not the one that doesn't

Two defects, one cause. `ParseListParams` (`src/webapi/Api.cpp:3426`) validates
`limit` against 0–500 **only when the parameter is present**:

```cpp
if (qmap.count("limit")) {
        if (auto r = ParseUintParam(qmap, "limit", 0, 500, v))
                return r;
        out.has_limit = true;
        …
}
```

so an omitted `limit` is not a default — it is *unbounded*. Measured on
`/shared`:

| Request | Rows | `limit` in the envelope |
|---|---|---|
| *(no `limit`)* | **all of them** | 28 |
| `limit=500` | 28 | 500 |
| `limit=501` | `400 bad_request` | — |
| `limit=0` | 0 | 0 |

**The cap protects nothing.** The only way to receive more than 500 rows is to
not ask for a limit at all, so the explicit path is capped and the implicit one
is not — backwards from what a cap is for. And the only client that exists never
sends the parameter: `grep -r 'limit=' src/webapi/static/js` returns nothing, so
every list request the Web UI makes today is unbounded. On a 50 000-file share
that is a multi-megabyte body the ETag memo exists to avoid re-hashing — the
memo is treating a symptom whose cause is here.

**Second, the envelope reports a `limit` the caller never chose**
(`WritePageMeta`, `Api.cpp:3507`):

```cpp
w.Key("limit");
w.ValueUInt(params.has_limit ? params.limit : returned);
```

A client that round-trips the envelope — reads `{total, offset, limit}`, keeps
it as its paging state, and sends it back, which is what the envelope
invites — has just pinned its page size to however many rows happened to come
back the first time.

**Fix.** One rule, stated once in `REFERENCE.md`'s
[List pagination](#list-pagination-and-sorting) section and applied by
`ParseListParams` to all eleven list handlers:

> `limit` defaults to **100** and is capped at 500. Omitting it selects the
> first 100 items, not all of them.

Uniform rather than per-endpoint: a per-collection default would be a table for
a client to look up before it can predict a response, and the collections here
are not different enough to earn one. It goes in `ParseListParams`, which every
list handler already calls, so it is one initialiser and no per-handler work.

The echo then becomes well-defined by construction — `limit` always reports the
window actually applied — which is the second defect above, fixed for free.

Two of the nine collections already exceed the default on a modest install
(`/downloads` at 293 and `/known_clients` at 166 on the development daemon this
was measured against), so this is not a theoretical bound.

**How does a client then ask for everything?** It does not, and that is the
point — it pages, with `offset`, until `offset + limit >= total`. `total` is
already there to say when to stop. The three spellings that might look like an
escape hatch are all worse:

- `limit=0` is taken: it means *zero rows*, and it has to keep meaning that.
- A very large number cannot work while the cap stands, and removing the cap to
  allow it puts back exactly the unbounded response this fixes.
- `limit=all` puts a string sentinel in a numeric parameter, which is the shape
  of thing the surface's own query-validation rule (`REFERENCE.md:211`) exists
  to keep out.

If an escape hatch is ever genuinely needed, **raise the cap** — one number in
one place — rather than invent a spelling for its absence.

**The bootstrap sweep has to be documented as a paging loop.** This is the part
of the change that is not code. `EVENTS.md:13-25` specifies the ordering — open
`/events` first and buffer, `GET` the collections, then load-drain-flip in one
synchronous turn — and step 2 is written as a single `GET` per collection.
Windowed, that `GET` covers 100 of 293 downloads, and the stream then delivers
`download_updated` for the other 193: events for rows the client never fetched.
Step 2 becomes a sweep, and `EVENTS.md` has to say so:

```js
// Step 2, per collection: page to completion before the flip.
// `sort=hash` is the identity order this change has to add — see below.
async function sweep(path, key) {
  const rows = [];
  for (let offset = 0; ; offset += 100) {
    const page = await get(`${path}?limit=100&offset=${offset}&sort=hash`);
    rows.push(...page[key]);
    if (offset + page.limit >= page.total) break;
  }
  return rows;
}
```

Three rules go with it, and the third needs a comparator that does not exist
yet:

- **The whole sweep happens inside step 2**, before the drain and flip. Events
  arriving mid-sweep are buffered, as they already are, so a row that is added
  or removed while the sweep runs is corrected when the buffer replays. That is
  why the existing "open the stream first" ordering is what makes paging safe at
  all — without it, paging would widen the window in which an event is lost from
  one request to N.
- **A `resync` frame mid-sweep restarts the sweep**, same as it already
  invalidates a single-`GET` bootstrap.
- **Page on a sort key that does not move under live data.** The API sorts the
  whole set and then slices, so between two page requests a row whose sort key
  changed can move from a page not yet fetched to one already fetched, and be
  skipped. A *duplicate* is harmless — the store is keyed by id — but a skipped
  row is invisible until something happens to it, and if nothing does, it is
  missing for the life of the session. Sorting by `speed`, `progress` or
  `sources` during a sweep is therefore unsafe by construction. The hazard does
  not exist today, because today there is only ever one request.

  **This needs a sort key the surface does not have.** Only `/categories`
  (`index`) and `/search` (`search_id`) can be ordered by identity right now;
  `sort=hash`, `sort=ecid` and `sort=user_hash` are all
  `400 unknown \`sort\` field for this endpoint`. So the change carries one
  more comparator row per table — `hash` for `/downloads`, `/shared` and
  `/search/{id}/results`, `ecid` for `/clients`, `/servers`, `/friends` and the
  two per-file client routes, `user_hash` for `/known_clients` — each a
  three-line lambda beside the ones already there, and each spelled exactly like
  the response key it orders by, as R7 in
  [`api-field-names-and-units.md`](api-field-names-and-units.md) requires. Then
  the default sweep order is stated once in `EVENTS.md` and a client does not
  have to reason about it.

**It breaks the current contract, and that is accepted.** Changing what an
omitted parameter means is backwards-incompatible, and `REFERENCE.md:5` promises
`/api/v0/` is frozen against exactly that. The promise is honoured by demotion
rather than by deferral, the same way the renames are: `/api/v0/` has no
consumers outside this repository, so the change lands **in place, now**, and
ships as `/api/v1/` when the prefix flips in the final commit of the staging
sequence in
[`api-field-names-and-units.md`](api-field-names-and-units.md). No alias, no
coexistence.

**One ordering constraint remains, and it is not about versions.** The Web UI
does not page — `grep -r 'limit=' src/webapi/static/js` is empty — so the day
the default lands its download list shows 100 of 293 rows. The sweep above has
to go into the Web UI in the same commit as the default, not after it, or the
tree is left with a UI that silently truncates.

The echo half is neither breaking nor blocked: reporting the window actually
applied is additive and can land on its own at any time.

**Test.** Curl cases asserting that an omitted `limit` returns at most 100 and
reports `limit: 100`, that `offset` walks the whole collection in
`ceil(total / limit)` requests with no row repeated or skipped, and that
`limit=0` still returns zero rows.

---

## Scope

Ten independent fixes, none needing an EC protocol change. §4, §5, §6, §7 and §9
touch behaviour a client can observe today; §1, §2 and §10 change a response
shape additively (a number becomes `null`, or a string); §3 is a documentation
correction only.

Worth doing first: **§5** and **§4**, because a value the daemon silently
rewrites is worse than one it rejects; then **§8**, which hands a UI the
opposite of what it asked for; then **§7**, the only one where a retry does
damage. §1 and §9 are the same shape of defect — a value a client cannot tell
apart from a real one — and are cheapest landed together with the unknown-value
convention already documented in `REFERENCE.md`.

**§10 splits across versions.** Its echo half is a one-liner and additive, so it
can land on v0 now. The half that matters — a default `limit` of 100, so the cap
applies to the requests that currently bypass it — changes what an omitted
parameter means, which `REFERENCE.md:5` reserves for `/api/v1/`; it also
truncates the Web UI's lists until the UI learns to page. It belongs in the v1
pass staged by
[`api-field-names-and-units.md`](api-field-names-and-units.md), with the Web UI
work in the same commit.
