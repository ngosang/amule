# amuleapi: protocol and correctness bugs still open on the v0 surface

## Summary

One code bug remains — a field emitted as `null` over REST but as `""` over SSE,
so a client hydrating from one and updating from the other watches the value
flip. The rest is a thin residue of documentation and comments: two reference
lines that name an error code the binary does not emit, one that describes a
graph-point key the writer dropped, and one stale request-body comment.

Verified against the source and the current `docs/api/REFERENCE.md` /
`EVENTS.md` at commit `cd7441c72`. The function names are the durable reference;
the line numbers below are from this tree.

---

## 1. `friend.ip` is `null` over REST but `""` over SSE

The REST friend serializer null-guards the address; the SSE one does not, so the
same friend arrives with two different values on the two transports:

- REST `WriteFriendObject` (`Api.cpp:5908`): `WriteStringOrNull(w, "ip",
  !f.ip.empty(), f.ip)` → `"ip": null` when the friend has no address.
- SSE `ToJson(const FriendSnapshot&)` (`EventDiff.cpp:272`):
  `<< ",\"ip\":\"" << EscJson(f.ip) << "\""` → always a string, so `"ip": ""` for
  the same friend.

A friend added by `user_hash` or address only, or one the daemon has not
resolved, keeps `f.ip == ""` — `MergeFriendTag` writes `f.ip` only when the EC
`IP` tag is present (`Refresher.cpp:1881-1884`). A subscriber hydrates its list
from `GET /friends` and holds `"ip": null`; the next refresher tick that touches
that friend fires `friend_updated` — `Equal(FriendSnapshot)` compares
`a.ip == b.ip` (`EventDiff.cpp:513`), so any change to the row re-emits it —
carrying `"ip": ""`. The cached value flips `null → ""` with no real data
change, breaking a client that treats `null` as "no address"
(`ip == null ? "—" : ip`).

This is exactly the REST/SSE divergence the resolved shared-file
`last_upload`/`shared_since` bug was, one serializer over. The sibling
`ToJson(const ClientSnapshot&)` documents the intended contract in as many words
(`EventDiff.cpp:288-290`: `country_code` is "null, not '', … the REST row this
event promises key parity with emits null here"); the friend serializer just
does not honour it for `ip`.

**Fix.** Mirror the REST guard in the SSE writer — `f.ip.empty() ? "null" :
"\"" + EscJson(f.ip) + "\""`, the same shape the `client_ecid` field beside it
already uses (`EventDiff.cpp:273`). No `Equal` change: it already compares the
raw value.

**Test.** An SSE case asserting a `user_hash`-only friend arrives with
`ip: null`, matching its `GET /friends` row.

## 2. `REFERENCE.md` names a `409 conflict` code the binary never emits

The `conflict` error code was split during the code-catalog rename into
`option_not_supported` and `not_a4af_source`, and `grep` finds no `conflict`
anywhere in `src/webapi`. Two per-endpoint **Errors** lines were rewritten from
the pre-rename name and still carry it, so a client switching on `error.code` for
either `409` never matches:

| Reference line | Doc says | Code emits |
|---|---|---|
| `REFERENCE.md:2423` (`PATCH /preferences`) | `409 conflict` | `409 option_not_supported` (`Api.cpp:8826`) — the build lacks the option |
| `REFERENCE.md:1068` (`PATCH /downloads/{hash}/a4af`) | `409 conflict` | `409 not_a4af_source` (`Api.cpp:4895`) — that client is not an A4AF source |

Both codes are correct in the catalog itself (`REFERENCE.md:3256`, `:3257`) and
in the same `/preferences` section's prose (`:2361`); only these two summary
lines are stale. Doc-only fix: replace `conflict` with the two real codes.

## 3. `REFERENCE.md` documents a graph-point `t` (ISO-8601) key the writer dropped

`REFERENCE.md:2810` says each `/stats/graphs/{graph}` point carries `t`
(ISO-8601 UTC), `at` (unix seconds) and `value`. The ISO twin was dropped in the
R3 pass: `WritePointArray` (`Api.cpp:7593`) emits only `at` and `value` (plus
the paired-series keys), no `t`. A client reading `point.t` gets `undefined`.
Doc-only fix: drop `t` from that sentence, leaving `at` and `value`.

## 4. A stale request-body comment names three keys the parser no longer accepts

`Api.cpp:11128-11131` documents the `POST /search` body as:

```cpp
//    "min_size":   uint64 bytes (optional, default 0),
//    "max_size":   uint64 bytes (optional, default 0 = no cap),
//    "min_avail":  uint32 (optional, default 0) }
```

The parser further down in the same handler reads `min_size_bytes`,
`max_size_bytes` and `min_source_count` (`Api.cpp:11187-11225`) — the names the
R2/R8 rename gave these fields. The C++ variables are still `min_size` /
`min_avail` (fine), but the comment purports to describe the JSON request shape
and names three keys the handler now rejects, which `CLAUDE.local.md` forbids a
comment from doing. One-comment edit; because it is a `.cpp`, run clang-format 18
afterward.

---

## Scope

One code fix and three documentation/comment edits. §1 is the only client-visible
defect — a one-line SSE guard mirroring REST, the same additive fix the resolved
shared-timestamp bug took, and the one worth landing first. §2 and §3 are
`docs/api/` edits (three lines a client coding against the reference gets wrong);
§4 is a comment-only edit. The durable guard against §2/§3 recurring is the one
the resolved reference-drift pass already named: generate the per-endpoint error
lists and worked examples from the serializers, the way `issues/inventory/`
already derives the shapes and the error catalog.
