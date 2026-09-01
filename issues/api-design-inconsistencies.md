# amuleapi: design inconsistencies still open on the v0 surface

## Summary

Two design inconsistencies are open on `/api/v0/` — places where the surface
answers the same question in two different ways. Neither is a bug: each answer is
decodable where it stands, and the cost is paid by the client, which has to learn
the rule twice.

Defects that produce a *wrong* answer live in
[`api-protocol-and-correctness-bugs.md`](api-protocol-and-correctness-bugs.md)
(including the SSE-side `""`/`null` split on `friend.ip`, which is decodable but
*flips* over the stream); pure renames live in
[`api-field-names-and-units.md`](api-field-names-and-units.md).

Verified against the source at commit `cd7441c72` and, where observable, a live
`amuleapi` on `127.0.0.1:4713`. The function names are the durable reference.

---

## 1. Four address fields emit a `0` / `""` sentinel where the surface uses `null`

The R10 pass that spelled "no value" as `null` — never `0` or `""` — reached
most of the surface (`REFERENCE.md:359`, `:471`) but left four address fields
emitting the old sentinel. Each has a sibling in the same or an adjacent object
that uses `null`, so a client normalising "no address" has to special-case them:

| field | emits | site | the `null` sibling it disagrees with |
|---|---|---|---|
| `friend.port` | raw `0` | `WriteFriendObject`, `Api.cpp:5909-5910` | `friend.ip` just above and `friend.client_ecid` just below (`:5908`, `:5916`) |
| `kad.public_ip` | `""` | `HandleKad`, `Api.cpp:7415-7416` | `kad.buddy.ip` in the same object (`WriteIntOrNull`/`WriteStringOrNull`, `:7431`) |
| `ed2k.public_ip` | `""` | `HandleStatus`, `Api.cpp:2651-2652` | `known_client.ip`, `friend.ip` (`:3194`, `:5908`) |
| `ed2k.server_ip` | `""` | `HandleStatus`, `Api.cpp:2658-2659` | same |

`WriteKnownClientObject` shows the settled form: it nulls `port` and `kad_port`
together via `WriteIntOrNull` (`Api.cpp:3195-3196`), and `REFERENCE.md:359` lists
both among the keys that emit `null`. `friend.port` is the one field on the
friend row the R10 pass reached for `ip` and `client_ecid` but not for `port`;
the three public/server IPs are string fields whose `""` was kept as "not
connected / not running" (the ed2k pair commented "0 / empty while disconnected"
at `Api.cpp:2645`) — the same "a UI can render it blank" justification R10
already answers with `null`.

Nothing is *undecodable* — a `0` port and an `""` IP both read as "absent" — so
this is a coherence cost, not a bug (the same reason `client_ecid` lived here
before it was nulled). But the surface-wide rule is `null`, and these four are
the exceptions a client has to learn per field.

**Fix.** Route all four through the `WriteIntOrNull` / `WriteStringOrNull` guard
their siblings already use, keyed off the emptiness / not-connected test each
already has. And fix `REFERENCE.md:2080`, which still says `friend.ip` is `""`
for a zero address — the code already emits `null` there (`Api.cpp:5908`); the
line predates the R10 rewrite of that serializer.

## 2. `POST /geoip/update` returns a `{}` body; its three sibling fetch routes return none

Four routes trigger a background fetch and answer `202`. They split on whether
the `202` carries a body:

- `POST /geoip/update` → `202` with `Content-Type: application/json` and an empty
  `{}` body (`HandleGeoipUpdate`, `Api.cpp:9250-9255`).
- `POST /kad/update`, `POST /ipfilter/update`, `POST /servers_update` → `202`
  with `content_type` cleared and **no** body (`UrlFetchOp`, `Api.cpp:4111-4116`).

The geoip handler's own comment claims "202, like the three sibling fetch routes"
(`Api.cpp:9246`), but those three emit nothing while it emits `{}`. The reference
response model puts URL fetches in the "`202 Accepted`, no body" bucket
(`REFERENCE.md:225`) and does not list geoip among the `{message}` exceptions
(`:232`). A client that parses the body of these interchangeable routes gets an
object from one and an empty body from three, so it must branch on the endpoint.

**Fix.** Drop the `{}` — clear `content_type` and return no body, matching the
three URL-fetch routes (the family geoip actually belongs to). One-liner at the
geoip call site, plus its now-accurate comment.

---

## Scope

Two changes, both small. §1 is a `null` alignment across four address fields
(three of them commented-deliberate, so the fix is also a decision to hold the
surface to its own R10 rule) plus one stale `REFERENCE.md` line. §2 drops an
empty body to match three sibling routes.

Considered and left as documented-deliberate: server `soft_file_limit` /
`hard_file_limit` emit a raw `0` for "not reported yet" (`Api.cpp:5840-5843`),
which the reference already documents as intentional; unlike §1's fields they
have no `null` sibling beside them to disagree with, so a client cannot mistake
the convention within that object.

Neither §1 nor §2 is urgent: `/api/v0/` has no consumers outside this
repository, and both are coherence warts that are cheap to fix now and get
slightly more expensive with every client that learns to special-case them.
