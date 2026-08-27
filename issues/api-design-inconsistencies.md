# amuleapi: design inconsistencies still open on the v0 surface

## Summary

Two design inconsistencies are currently open on `/api/v0/` — two places where
the surface answers the same kind of question in two different ways. Neither is a
bug: each answer is defensible where it stands, and the cost is paid by the
client, which has to learn the rule twice.

Defects that produce a *wrong* answer live in
[`api-protocol-and-correctness-bugs.md`](api-protocol-and-correctness-bugs.md);
pure renames live in
[`api-field-names-and-units.md`](api-field-names-and-units.md), which also
carries the R1–R12 rules this file argues against.

Verified against the source at commit `43c1dad16` and, where observable, a live
`amuleapi` on `127.0.0.1:4713`. Line numbers are from that tree; the function
names are the durable reference.

---

## 1. `client_ecid` is `null` on one endpoint and a `0` sentinel on two others

The unknown-value convention the second pass adopted is now documented in full
(`REFERENCE.md:346-356`):

> `null` means "no value", an absent key means "not reported", and neither is
> ever spelled `0` or `-1`.

The four keys that legitimately stay omitted are enumerated in the same place
(`started_at` and `result_count` on `/search`, the `key` on a stats node, and
`parts` behind `?include_parts=true`), so the three-state rule is written down
and a client can rely on it.

Two writers do not follow it. `client_ecid` — the live connection's ECID, if any
— is emitted as `null` when there is none on a `/search` row (`WriteIntOrNull`,
`Api.cpp:3392`), but as `0` on `/friends` (`Api.cpp:5675-5678`) and on `/chats`
(`client_ecid` and `friend_ecid`, `Api.cpp:5932-5937`), where `0` is the
"not connected" / "not a friend" sentinel. That is precisely the `0`-for-"no
value" the documented rule says the surface does not use, and it is the common
case: a friend is usually offline.

The `online` flag beside these fields disambiguates, so nothing is *undecodable*
— this is a coherence cost, not a bug. But a client normalising "no live
connection" across the surface has to special-case per endpoint, and the naive
`GET /clients/${friend.client_ecid}` it invites hits `/clients/0` → `404`.

**Fix.** Emit `client_ecid` / `friend_ecid` as `null` when there is no
connection, matching `/search` and the rule the reference already states (R10 in
the naming document). The `online` flag stays as the human-readable form. It
rewrites the same two writers as the renames in
[`api-field-names-and-units.md`](api-field-names-and-units.md), so it rides that
pass.

**One documentation nit on the same axis.** A statistics node also omits `ratio`
when the daemon reported neither component (`Api.cpp:7316`), but the list of
deliberately-omitted keys at `REFERENCE.md:356` names only the node's `key`, not
`ratio`. Add `ratio` to that list, or emit `null` — one word either way.

---

## 2. `POST /networks/connect` answers `202`, `POST /networks/disconnect` answers `200`

Both routes are thin wrappers over the same helper, `SimpleConnControlOp`
(`Api.cpp:8675`): same request shape, same inline `RefresherTick`, same
daemon-supplied `{message}` body. They disagree only on the success code —
connect passes `202` (`Api.cpp:8762`), disconnect passes `200`
(`Api.cpp:8807`) — and the reference codifies the split (`REFERENCE.md:2312`
vs `:2322`).

Nothing observable justifies the difference. Both merely hand the request to the
daemon over EC and return; disconnect is no more "completed" at return time than
connect is. The surface's other `SimpleConnControlOp` callers — `/shared_reload`
and `/ipfilter/reload` — both answer `202`, so `200` on disconnect is the lone
exception. A client wrapping connection control has to special-case the two
codes for no reason it can see.

**Fix.** Make both `202` — the code that says "handed to the daemon, not yet
observed to have taken effect", which is what both do. `202` is already what
three of the four `SimpleConnControlOp` routes return, so this is one argument
changed at the disconnect call site, plus the reference line.

---

## Scope

Two changes, both small. §2 is a one-argument fix plus a doc line. §1 is a
one-key-each `null` alignment for `client_ecid` / `friend_ecid` (plus a
one-word `REFERENCE.md` nit for `ratio`); the `null` half rides the same R10
pass as the renames in
[`api-field-names-and-units.md`](api-field-names-and-units.md), since it rewrites
the same two writers.

Neither is urgent: `/api/v0/` has no consumers outside this repository, and both
are the kind of coherence wart that is cheap to fix now and gets slightly more
expensive with every client that learns to work around it.
