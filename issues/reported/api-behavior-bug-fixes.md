# amuleapi: three behaviour bugs in the REST layer

## Summary

An audit of the amuleapi REST surface turned up three bugs that are about
**behaviour** — what the server *does*, not what its JSON looks like. They are
small, independent fixes in `src/webapi/Api.cpp`, each with its own test.

## The bugs

### 1. Missing `RequireAdmin` on the two comment-lookup POSTs

`POST /downloads/{hash}/comments` and `POST /search/results/{hash}/comments`
are the only mutating POSTs outside `/auth` without an admin check, and both
trigger an unbounded Kad NOTES lookup on the daemon
(`EC_OP_SHARED_FILE_SEARCH_KAD_NOTES`) — a guest session can make the daemon do
real network work.

The two handlers are `HandleDownloadCommentsKadSearch` and
`HandleSearchCommentsKadSearch`. Both already do `Authenticate` and
`HasFirstSnapshot()`; what is missing in each is the exact chain every other
mutation uses right after `Authenticate` (see `HandleDownloadAdd` for the
pattern):

```cpp
if (auto rej = RequireAdmin(a))
    return *rej;
```

**The fix is to gate them.** Documenting a guest exemption instead is only an
option if someone actively argues for guest-triggered Kad lookups — the default
is that mutations are admin-only.

### 2. Missing `HasFirstSnapshot()` guard on `POST /downloads`

`HandleDownloadAdd` is the only downloads handler without the guard — it does
`Authenticate` + `RequireAdmin` and goes straight to body parsing, so it
returns `202` before the first EC snapshot while every sibling (see
`HandleDownloadPatch`, immediately below it in the file) returns `503`. Add
the same block the siblings use, verbatim:

```cpp
if (!m_state.HasFirstSnapshot()) {
    return ErrorResponse(
        503, "ec_unavailable", "amuleapi has not received its first EC snapshot yet");
}
```

### 3. `ResolveServerEcidByAddress` conflates three outcomes into one sentinel

`ResolveServerEcidByAddress` returns a `std::uint32_t` where `0` means "not
found" — but it also returns `0` when the `ip:port` string is **syntactically
invalid** (no `:`, empty halves, non-numeric or out-of-range port). Its three
callers (the `/servers/{ip:port}` connect, delete and patch paths) all do
`if (ecid == 0) return 404`, which has two consequences:

- a server that legitimately holds ECID 0 can never be addressed by `ip:port`;
- a malformed `ip:port` answers `404 not_found` when it should answer
  `400 bad_request`.

Redesign the signature to make the three outcomes explicit — e.g. an enum
result (`Ok` / `BadInput` / `NotFound`) plus an out-param, or
`std::optional<std::uint32_t>` with a separate parse step — and map them to
`400` / `404` in the callers. No caller may compare the ECID against a magic
value.

## Acceptance criteria

- [ ] Both comment POSTs answer `403` for a guest session, with a curl test for
      each.
- [ ] `POST /downloads` before the first snapshot answers `503 ec_unavailable`,
      same as its siblings, with a curl test.
- [ ] A malformed `ip:port` selector on the `/servers/{ip:port}` routes answers
      `400 bad_request`; an unknown but well-formed one answers `404 not_found`
      — one curl test per case.
- [ ] No caller of `ResolveServerEcidByAddress` treats ECID `0` as "not found".
- [ ] Existing curl suite and C++ unit tests still pass.
