# `GET /api/v0/servers`: expose the soft/hard file limits and the TCP/UDP capability flags

## Summary

The desktop server list has 16 columns; `GET /api/v0/servers` covers 12 of them.
The four missing ones are **Soft Files**, **Hard Files**, **TCP Flags** and
**UDP Flags**.

All four are **already on the wire**. `CEC_Server_Tag` serializes them from both
of its constructors, libec already exposes typed accessors for them, and the
`EC_OP_GET_UPDATE` response `amuleapi`'s refresher parses once per tick carries
them alongside the fields it already reads. `MergeServerTag` simply does not
look at them.

So this is a pure `amuleapi`-side change: read four tags that already arrive,
carry them in the snapshot, emit them. **No core change, no EC protocol change,
no extra round-trip.**

Beyond column parity, one of these fields is functionally load-bearing: the
`related_search` TCP flag is what the desktop gates its *"Search related files
(eD2k, local server)"* action on (`CServer::GetRelatedSearchSupport()`,
`src/Server.h:159`). Without it a REST client cannot tell whether a
`related::<hash>` local search will work against the currently connected server.

Since the server object is being edited anyway, this issue also folds in **one
rename of an existing field** — see [Naming review](#naming-review). `/api/v0/`
is experimental and has no consumers yet, so renames land in place rather than
waiting for a `v1`.

## Current state

| Piece | Location |
|---|---|
| Core emits all four (detail-level ctor) | `src/ECSpecialCoreTags.cpp:102-121` — `CEC_Server_Tag(const CServer *, EC_DETAIL_LEVEL)` |
| Core emits all four (valuemap ctor, the one `GET_UPDATE` uses) | `src/ECSpecialCoreTags.cpp:150-154` |
| Typed accessors already in libec | `src/libs/ec/cpp/ECSpecialTags.h:287-303` — `GetSoftFiles()` / `GetHardFiles()` / `GetTCPFlags()` / `GetUDPFlags()` |
| `amuleapi` server parse (does not read them) | `src/webapi/Refresher.cpp:1497-1610` — `MergeServerTag`; `files` is read at `:1592-1596` |
| Refresher entry point | `src/webapi/Refresher.cpp:1615` — `ApplyGetUpdateToServers`, fed by the `EC_OP_GET_UPDATE` roundtrip at `src/webapi/RefresherTick.cpp:102` |
| Snapshot struct | `src/webapi/State.h:399-418` — `ServerSnapshot` |
| REST emit | `src/webapi/Api.cpp:4252-4288` — `WriteServerObject` |
| List handler + sort comparators | `src/webapi/Api.cpp:4310-4338` — `HandleServers` |
| SSE payload | `src/webapi/EventDiff.cpp:167-181` — `ToJson(const ServerSnapshot &)` |
| SSE change detection | `src/webapi/EventDiff.cpp:307-314` — `Equal(const ServerSnapshot&, const ServerSnapshot&)` |
| Desktop columns (reference rendering) | `src/ServerListCtrl.cpp:104-111` (columns), `:294-303` (soft/hard), `:341-394` (flag letters), `:130-131` (flag columns hidden by default) |

## EC protocol reference

No protocol change. All four tags exist and are already transmitted:

| Tag | Id | Type | Source |
|---|---|---|---|
| `EC_TAG_SERVER_FILES_SOFT` | `0x050F` | uint32 | `CServer::GetSoftFiles()` |
| `EC_TAG_SERVER_FILES_HARD` | `0x0510` | uint32 | `CServer::GetHardFiles()` |
| `EC_TAG_SERVER_TCP_FLAGS` | `0x0511` | uint32 | `CServer::GetTCPFlags()` |
| `EC_TAG_SERVER_UDP_FLAGS` | `0x0512` | uint32 | `CServer::GetUDPFlags()` |

Defined in `src/libs/ec/abstracts/ECCodes.abstract:342-345`.

Semantics to preserve:

- **Soft / hard limits** are the per-user publishing limits the server
  advertises: below the soft limit a client may publish every file, between
  soft and hard only its rarest, above the hard limit nothing. They arrive only
  once a UDP status reply has come back, so **`0` means "the server has not told
  us"**, not "the limit is zero" — the desktop renders that as a blank cell
  (`src/ServerListCtrl.cpp:290-303`), exactly as it does for Users and Files.
- **Flags** are bitmasks of the eD2k wire capabilities the server announced.
  `0` likewise means "nothing announced yet".
- Both constructors of `CEC_Server_Tag` emit the tags, so both the initial list
  and the incremental updates carry them — no risk of a permanently blank field
  after the first tick.

Flag bit definitions, `include/protocol/ed2k/Client2Server/TCP.h:70-76`:

| Bit | Constant | JSON key | Meaning | Desktop letter |
|---|---|---|---|---|
| `0x0001` | `SRV_TCPFLG_COMPRESSION` | `compression` | zlib-compressed packets | `c` |
| `0x0008` | `SRV_TCPFLG_NEWTAGS` | `new_tags` | compact tag encoding | `n` |
| `0x0010` | `SRV_TCPFLG_UNICODE` | `unicode` | Unicode strings | `u` |
| `0x0040` | `SRV_TCPFLG_RELATEDSEARCH` | `related_search` | related-files search | `r` |
| `0x0080` | `SRV_TCPFLG_TYPETAGINTEGER` | `type_tag_integer` | integer file-type tags | `t` |
| `0x0100` | `SRV_TCPFLG_LARGEFILES` | `large_files` | files > 4 GiB | `l` |
| `0x0400` | `SRV_TCPFLG_TCPOBFUSCATION` | `tcp_obfuscation` | TCP protocol obfuscation | `o` |

And `include/protocol/ed2k/Client2Server/UDP.h:51-58`:

| Bit | Constant | JSON key | Meaning | Desktop letter |
|---|---|---|---|---|
| `0x0001` | `SRV_UDPFLG_EXT_GETSOURCES` | `get_sources` | extended GetSources request | `g` |
| `0x0002` | `SRV_UDPFLG_EXT_GETFILES` | `get_files` | extended GetFiles request | `f` |
| `0x0008` | `SRV_UDPFLG_NEWTAGS` | `new_tags` | compact tag encoding | `n` |
| `0x0010` | `SRV_UDPFLG_UNICODE` | `unicode` | Unicode strings | `u` |
| `0x0020` | `SRV_UDPFLG_EXT_GETSOURCES2` | `get_sources_v2` | GetSources v2 | `G` |
| `0x0100` | `SRV_UDPFLG_LARGEFILES` | `large_files` | files > 4 GiB | `l` |
| `0x0200` | `SRV_UDPFLG_UDPOBFUSCATION` | `udp_obfuscation` | UDP obfuscation | `o` |
| `0x0400` | `SRV_UDPFLG_TCPOBFUSCATION` | `tcp_obfuscation` | TCP obfuscation (announced over UDP) | `O` |

## Requested change

### `GET /api/v0/servers`

Four new fields on the server object, one existing field renamed:

```json
{
  "servers": [
    {
      "ecid": 1,
      "name": "eMule Server",
      "description": "Public server",
      "version": "17.15",
      "address": "203.0.113.5:4242",
      "country_code": "de",
      "port": 4242,
      "users": 312000,
      "max_users": 500000,
      "files": 75000000,
      "soft_file_limit": 1000,
      "hard_file_limit": 5000,
      "priority": "normal",
      "ping_ms": 42,
      "failed_count": 0,
      "static": false,
      "tcp_flags": {
        "bitmask": 1497,
        "compression": true,
        "new_tags": true,
        "unicode": true,
        "related_search": true,
        "type_tag_integer": true,
        "large_files": true,
        "tcp_obfuscation": true
      },
      "udp_flags": {
        "bitmask": 1851,
        "get_sources": true,
        "get_files": true,
        "new_tags": true,
        "unicode": true,
        "get_sources_v2": true,
        "large_files": true,
        "udp_obfuscation": true,
        "tcp_obfuscation": true
      }
    }
  ],
  "total": 1, "offset": 0, "limit": 1
}
```

| Field | Type | Meaning |
|---|---|---|
| `soft_file_limit` | int | **New.** Per-user *soft* publishing limit the server advertises. `0` = not reported yet (render blank, not "0"). |
| `hard_file_limit` | int | **New.** Per-user *hard* publishing limit. `0` = not reported yet. |
| `tcp_flags` | object | **New.** Decoded TCP capability bits, plus `bitmask`. |
| `udp_flags` | object | **New.** Decoded UDP capability bits, plus `bitmask`. |
| `failed_count` | int | **Renamed** from `failed`. Consecutive failed connection attempts. |

**Why decoded objects rather than bare integers.** It is the rule the rest of
this API already follows — `GET /clients` states that "the daemon decodes
amuled's internal enums server-side so consumers never need the lookup tables",
and every peer state field ships as a token, not a code. A bare
`tcp_flags: 1497` would force every consumer to carry a copy of two `#define`
blocks out of the aMule tree. `bitmask` is kept alongside for the diagnostic use
case and for bits a future server announces that this build does not name yet.

Every boolean is always present (`false` when the bit is clear or nothing has
been announced), so consumers never branch on key existence. `Auth: GUEST`,
unchanged. The query parameters are unchanged (`limit` / `offset` / `sort` /
`order`, see the naming review below); there is no request body.

### SSE `server_added` / `server_updated`

`ToJson(const ServerSnapshot &)` emits the same four new fields and the renamed
`failed_count` — the event payload and the REST object are documented as
identical — and `Equal(const ServerSnapshot&, …)` compares the four, so a server
that announces its capabilities after the first UDP reply produces a
`server_updated`.

## Naming review

Every field and parameter this endpoint exposes, reviewed while the object is
open. `/servers` is `GET`-only here, so the surface is the query parameters plus
the server object.

### Renamed

| Before | After | Why |
|---|---|---|
| `failed` | `failed_count` | `"failed": 0` reads as a boolean that happens to be serialized as a number — a consumer skimming the object would take it for "did the last connection fail?". It is a *counter* of consecutive failures, so the name has to say so. Not read by the bundled web UI, so the rename is free. |

### Named deliberately (new fields, rejecting the obvious first choice)

| Obvious name | Chosen | Why |
|---|---|---|
| `soft_files` / `hard_files` | `soft_file_limit` / `hard_file_limit` | Sitting next to the existing `files` (the count of files the server indexes), `soft_files` / `hard_files` read as *subsets of that count* — "how many of those files are soft?". They are neither counts nor subsets: they are per-user publishing **limits**. The `_limit` suffix removes the whole misreading. |
| `raw` | `bitmask` | Inside a flags object, `raw` says "unprocessed" without saying *of what*; the API also already uses `raw` in `GET /stats/tree` for something different (a node's untranslated string value). `bitmask` names the thing exactly and tells the consumer it can be AND-ed. |
| `obfuscation` (in `tcp_flags`) | `tcp_obfuscation` | `udp_flags` legitimately carries **both** a UDP-obfuscation and a TCP-obfuscation bit. If the TCP object called its bit `obfuscation` while the UDP object had `obfuscation` + `tcp_obfuscation`, the same key would mean different things in the two objects. Spelling out the transport in both keeps each key meaning exactly one wire constant. |
| `obfuscation` (in `udp_flags`) | `udp_obfuscation` | Same reason, other side. |
| `get_sources2` | `get_sources_v2` | `2` glued to the name reads like a count. `_v2` is unambiguously a protocol revision. |

### Reviewed, keeping the current name

| Field / param | Verdict |
|---|---|
| `ecid` | Jargon, but documented, and it is the URL key for `/servers/{ecid}`; the docs already explain that it is not stable across a daemon restart. |
| `name`, `description`, `version`, `country_code`, `port`, `users`, `max_users`, `priority`, `static` | Self-explanatory and matching the desktop column names. |
| `files` | Ambiguous only next to the *old* `soft_files` / `hard_files` spelling; with `_limit` on those, `files` unambiguously reads as "files indexed by this server". |
| `address` | Redundant with `port` on its face, but it is the exact string the alternate route form takes (`/servers/{ip}:{port}/connect`), so it earns its place. |
| `ping_ms` | Unit in the name — the pattern to keep. |
| `new_tags`, `type_tag_integer` | Opaque unless you know eD2k, but they are faithful to the wire constants and any "friendlier" rewording would be just as opaque while breaking the mapping. The bit table above is what carries the meaning; these are diagnostics the desktop hides by default. |
| `sort=name\|users\|ping\|files` | `ping` (not `ping_ms`) looks inconsistent, but it matches the convention the other list endpoints already use — `GET /downloads` sorts on `speed` for the field `speed_bps`. Sort keys drop unit suffixes; leave it. |
| `limit`, `offset`, `order` | Standard, shared across every list endpoint. |

## Implementation checklist

**amuleapi (`src/webapi/`)**
- [ ] `State.h` — add `soft_file_limit`, `hard_file_limit`, `tcp_flags`,
      `udp_flags` (`std::uint32_t`, default `0`) to `ServerSnapshot`, with a
      comment recording that `0` means "not announced"; rename `failed` →
      `failed_count`.
- [ ] `Refresher.cpp` — read the four tags in `MergeServerTag` using the same
      `AssignIfExist` pattern the neighbouring fields use, so a tag suppressed
      by `CValueMap` on an unchanged tick leaves the cached value intact.
- [ ] `Api.cpp` — a small `WriteServerFlags(CJsonWriter&, const char *key,
      std::uint32_t bits, const FlagBit *table, size_t n)` helper plus two static
      bit tables; call it twice from `WriteServerObject`, emit the two `_limit`
      fields next to `files`, and rename the `failed` key.
- [ ] `EventDiff.cpp` — mirror the four fields in `ToJson(const ServerSnapshot&)`,
      rename the `failed` key there too, and add the four to
      `Equal(const ServerSnapshot&, …)`.

**Docs**
- [ ] `docs/api/REFERENCE.md` — `GET /api/v0/servers`: extend the sample body,
      document the `0` = "not reported" sentinel for the two limits, table out
      both flag objects with the meaning of each bit, and rename `failed`.
- [ ] `docs/api/EVENTS.md` — `server_added` / `server_updated`: same fields in
      the payload sample.

**Tests**
- [ ] `unittests/tests/RefresherTest.cpp` — a fixture server tag carrying the
      four tags asserts they reach `ServerSnapshot`; a tag without them asserts
      the cached values survive (the `CValueMap` suppression path).
- [ ] `unittests/tests/EventDiffTest.cpp` — a tick where only `tcp_flags`
      changes fires exactly one `server_updated`.
- [ ] `unittests/curl-tests/amuleapi/05-read-servers-kad-categories-prefs.sh` —
      assert the new keys exist, that `tcp_flags` is an object with a numeric
      `bitmask`, and update any assertion on the old `failed` key.

**Web UI (`src/webapi/static`) — optional follow-up, can ship separately**
- [ ] Optional soft/hard limit columns in the servers table
      (`static/js/views/networks.js:170-185`), blank on `0`, plus i18n keys.
      The flag objects are diagnostics — the desktop hides those two columns by
      default and the web UI can simply not show them.

## Acceptance criteria

- [ ] `GET /api/v0/servers` returns `soft_file_limit`, `hard_file_limit`,
      `tcp_flags` and `udp_flags` for every server, with no extra EC round-trip
      per request.
- [ ] For a server the desktop shows values for, the API's limits match the
      desktop Soft/Hard Files columns, and the decoded flag booleans match the
      letters the desktop renders (`c n u r t l o` / `g f n u G l o O`).
- [ ] A freshly added server that has not answered a UDP status request yet
      reports `0` / all-`false`, and flips to real values — emitting one
      `server_updated` — once it replies.
- [ ] Against an `amuled` old enough not to send the tags, `/servers` still
      answers `200` with the zero/false defaults.
- [ ] The server object exposes `failed_count`, and the old `failed` key appears
      nowhere in the codebase, the docs or the tests.
- [ ] `docs/api/REFERENCE.md` documents every named bit, so a consumer never has
      to read the aMule headers.

## Out of scope

- New `sort=` keys for the added fields: nobody has asked, and the existing
  comparator set covers the columns people sort by.
- The `ecid` vs `client_ecid` inconsistency between this endpoint and
  `GET /clients` — both name the same kind of short-lived EC handle under
  different keys. This endpoint already uses the shorter spelling, so settling it
  is work on the *other* side and does not belong in this diff.
- Any change to how the desktop renders these columns.
- Exposing capability *derivations* such as `CServer::SupportsObfuscationTCP()`
  as their own booleans — with the bits decoded, a consumer can compute those.
