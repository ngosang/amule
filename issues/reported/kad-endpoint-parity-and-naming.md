# `GET /api/v0/kad`: reach parity with the desktop "Kad Info" panel, and disambiguate `ip`

## Summary

The desktop client's **Networks → Kad Info** panel is the reference view of Kad
state, and `GET /api/v0/kad` is meant to be its REST equivalent — the docs
describe it as "the Kad subtree from `/status`, plus the detail fields the status
rollup omits". Walking the panel row by row, two rows have no equivalent, and one
field that *is* there is named ambiguously:

- **Kademlia client ID** — the node's own 128-bit DHT id. Not exposed anywhere in
  the API, on any endpoint.
- **Connected since** — exposed as `kad.connected_since` on `GET /api/v0/status`
  but **absent from `GET /api/v0/kad`**, the endpoint a client goes to for Kad
  detail. Today the endpoint's own opening sentence is therefore not true.
- **`ip`** — our externally-visible address, under a key that says nothing about
  whose address it is, in a payload that also carries `buddy.ip`, which is
  somebody else's.

All three are `amuleapi`-side: the Kad id already rides the `EC_TAG_CONNSTATE`
tag inside the `EC_OP_STAT_REQ` response the refresher fetches every tick, and
the timestamp is already parsed into the status snapshot. **No core change, no EC
protocol change, no extra round-trip.** `/api/v0/` is experimental and has no
consumers outside this repository yet, so the rename lands in place rather than
waiting for a `v1`.

## Parity table

Every row `CServerWnd::UpdateKadInfo` (`src/ServerWnd.cpp:291-388`) can render:

| Desktop row | API today | Verdict |
|---|---|---|
| `Kademlia Status:` — *Running* / *Running in LAN mode* / *Not running* | `state` (`disabled`/`connecting`/`connected`) + `in_lan_mode` | covered |
| `Kademlia client ID:` — 32 hex chars | — | **missing** → `node_id` |
| `Status:` — *Connected* / *Disconnected* | `state` | covered |
| `Connected since:` | `/status` `kad.connected_since` only | **missing here** → `connected_since` |
| `Connection State:` — *OK* / *Firewalled — open TCP port N* | `firewalled`; the port is `preferences.connection.tcp_port` | covered (message composed client-side) |
| `UDP Connection State:` — *OK* / *Firewalled — open UDP port N* | `firewalled_udp`; port from `preferences.connection.udp_port` | covered |
| `Firewalled state:` — *No buddy* / *Connecting to buddy* / *Connected to buddy at IP:Port* | `buddy.{status,ip,port}` (`no_buddy`/`connecting`/`connected`) | covered |
| `IP address:` | `ip` | covered, but **renamed** to `public_ip` below |
| `Indexed sources / keywords / notes / load` | `indexed.{sources,keywords,notes,load}` | covered |
| `Average Users:` / `Average Files:` | `network.{users,files}` | covered |

The rest of the Networks → Kad page is already covered too — the node counter and
graph (`network.nodes`, `GET /stats/graphs/kad`), *Bootstrap from node*
(`POST /kad/bootstrap`) and *Update nodes from URL* (`POST /kad/update`) — so
this issue is scoped to the info panel.

## Current state

| Piece | Location |
|---|---|
| Core emits the Kad id | `src/ECSpecialCoreTags.cpp:202` — `CEC_ConnState_Tag`, guarded by `Kademlia::CKademlia::IsRunning()` |
| Core emits the timestamp | `src/ECSpecialCoreTags.cpp:204-206` — `EC_TAG_KAD_CONNECTED_SINCE`, only while connected |
| Core emits our external address | `src/ExternalConn.cpp:1641` — `EC_TAG_STATS_KAD_IP_ADDRESS`, only while Kad is connected |
| libec accessors | `src/libs/ec/cpp/ECSpecialTags.h:321` — `GetKadID(CUInt128&)`; `:332-335` — `GetKadConnectedSince(uint32&)` |
| Reference consumer (proves the wire works) | `src/amule-remote-gui.cpp:1741` — `tag->GetKadID(theApp->m_kadID)`, which fills the desktop row in `amulegui` |
| `amuleapi` Kad parse | `src/webapi/Refresher.cpp:1378-1435` — `ParseKadFromPacket`, fed the whole `EC_OP_STAT_REQ` response; the address at `:1419`, the buddy's at `:1428` |
| `amuleapi` status parse (already reads the timestamp) | `src/webapi/Refresher.cpp:200-206` — `conn->GetKadConnectedSince()` into `StatusSnapshot::kad_connected_since` |
| Snapshot struct | `src/webapi/State.h:424-443` — `KadSnapshot` (no id, no timestamp) |
| REST emit | `src/webapi/Api.cpp:5060-5119` — `HandleKad`, reading `m_state.Kad()` only; ours at `:5085`, the buddy's at `:5111` |
| Value source (core) | `Kademlia::CKademlia::GetKadID()`; persisted in `preferencesKad.dat` (`src/kademlia/kademlia/Prefs.cpp:114,132`) |
| Docs | `docs/api/REFERENCE.md` — the `GET /api/v0/kad` section |
| Bundled web UI (**breaks if the rename ships without it**) | `static/js/views/networks.js:418` — the "your IP" tile reads `d.ip` |
| Test | `unittests/curl-tests/amuleapi/05-read-servers-kad-categories-prefs.sh:119` — `.ip \| type` |

## EC protocol reference

No protocol change. Both missing values are already transmitted, as sub-tags of
`EC_TAG_CONNSTATE` (`0x0005`) in the `EC_OP_STAT_REQ` reply:

| Tag | Id | Type | Notes |
|---|---|---|---|
| `EC_TAG_KAD_ID` | `0x0010` | `EC_TAGTYPE_UINT128` | Present only while Kad is **running** (not merely connected). |
| `EC_TAG_KAD_CONNECTED_SINCE` | `0x0019` | uint32 | Unix seconds; present only while Kad is **connected**. |

Semantics worth documenting:

- The Kad id is **persistent**: the daemon generates it randomly on first run and
  stores it in `preferencesKad.dat`, so it survives restarts. That makes it
  unlike every other identifier the API hands out for the local node — the
  session-scoped ECIDs, and the server-assigned eD2k id. Worth one sentence in
  the docs, because it is the only stable self-identity a consumer can key on.
- It is a DHT routing key, not a credential — publishing it over a read
  (`GUEST`) endpoint is the same exposure the desktop panel already gives, and
  every Kad contact we talk to learns it anyway.

## Implementation note: amuleapi does not link `CUInt128` yet

`GetKadID()` yields a `Kademlia::CUInt128`, and reading it pulls `ECUInt128.o`
out of `libec`, which in turn needs `src/kademlia/utils/UInt128.cpp` — a file the
`amuleapi` target does not compile. Today nothing in `amuleapi` touches a
`UINT128` tag, so the object is never pulled and the link succeeds; the moment
this field is added it will fail with undefined references to
`CUInt128::CUInt128(const uint8_t*)` / `ToByteArray` / `ToHexString`.

The fix is the one `amulegui` already applies for the same reason
(`src/CMakeLists.txt:574`): add the source to the target.

```diff
 add_executable (amuleapi
 	${CMAKE_SOURCE_DIR}/src/ExternalConnector.cpp
+	${CMAKE_SOURCE_DIR}/src/kademlia/utils/UInt128.cpp
 	${CMAKE_SOURCE_DIR}/src/OtherFunctions.cpp
```

Do **not** work around it by reading the tag's raw bytes: `CECTag::GetTagData()`
asserts the tag is `EC_TAGTYPE_CUSTOM`, so that path trips an `EC_ASSERT` in a
debug build.

## Requested change

### `GET /api/v0/kad`

```diff
 {
   "state": "connected",
+  "node_id": "8f3a1c07d94b2e5a6018bb4c7f209d3e",
   "firewalled": false,
   "firewalled_udp": false,
   "in_lan_mode": false,
+  "connected_since": 1751000000,
-  "ip": "203.0.113.5",
+  "public_ip": "203.0.113.5",
   "network": { "users": 5400000, "files": 1400000000, "nodes": 2400 },
   "indexed": { "sources": 12000, "keywords": 8500, "notes": 0, "load": 14 },
   "buddy": { "status": "connected", "ip": "203.0.113.9", "port": 4672 }
 }
```

| Field | Type | Meaning |
|---|---|---|
| `node_id` | string | **New.** Our own Kademlia node id — 32 lowercase hex characters. `""` when Kad is not running. Persisted by the daemon, so it is stable across restarts. |
| `connected_since` | int | **New here.** Unix seconds of the most recent Kad connect; `0` when not connected. Same value `GET /api/v0/status` reports as `kad.connected_since` — gate on `state` rather than trusting a `0`. |
| `public_ip` | string | **Renamed** from `ip`. Our externally-visible IPv4 as Kad discovered it from remote contacts. `""` when Kad is not connected — the daemon only sends the tag while connected, so the empty string is "not known", not "no address". Distinct from `preferences.connection.bind_address`, the local interface the daemon binds to. |

`buddy.ip` is **unchanged**: it is nested under the object that says whose
address it is, which is exactly the disambiguation the top-level field was
missing.

`Auth: GUEST`, unchanged. `/kad` takes no query parameters and no request body;
that is unchanged too. `/status` keeps its current `kad` rollup unchanged —
`node_id` is detail-view material, and `/status` deliberately carries only the
headline fields.

## Naming review

Every field this endpoint returns, reviewed while the handler is open. `/kad` is
`GET`-only with no query parameters, so the response object is the whole surface.

### Renamed

| Before | After | Why |
|---|---|---|
| `ip` | `public_ip` | Every other `ip` in the API belongs to a remote party — `/clients[].ip`, `/known_clients[].ip`, `/status.ed2k.server_ip`, and `buddy.ip` **in this same payload**. This one field is the only self-referential address and its name does not say so. There is a second ambiguity underneath: the API already exposes a *different* "our own address", `preferences.connection.bind_address`, the local interface the daemon binds to. "Our IP" is genuinely two things here; this one is specifically the address the outside world sees. |

### Named deliberately (new field, rejecting the obvious first choice)

| Obvious name | Chosen | Why |
|---|---|---|
| `id` | `node_id` | It sits next to `network.nodes`, so "our id in that node population" reads immediately, and *node id* is the standard DHT term for exactly this value. A bare `id` in a status payload also invites reading it as a resource key, which it is not. |

**Lowercase** hex rather than the desktop's uppercase, because every other hex
identifier this API emits is lowercase (`user_hash`, the MD4 file hashes) and a
consumer comparing them should not have to case-fold.

### Reviewed, keeping the current name

| Field | Verdict |
|---|---|
| `state` | Three-state enum shared with `/status`'s `ed2k.state` / `kad.state`. |
| `firewalled`, `firewalled_udp` | Positive-sense, transport spelled out, consistent with each other. |
| `in_lan_mode` | Says exactly what it is. |
| `network.{users,files,nodes}` | Mirrors `/status`'s `ed2k.network.*`. |
| `indexed.{sources,keywords,notes,load}` | The daemon's own vocabulary for the Kad store, and the desktop's row labels. |
| `buddy.{status,ip,port}` | Nested under the owner, which is what makes the bare `ip` fine *there*. |

## Implementation checklist

**amuleapi (`src/webapi/`)**
- [ ] `CMakeLists.txt` — add `${CMAKE_SOURCE_DIR}/src/kademlia/utils/UInt128.cpp`
      to the `amuleapi` target (see the implementation note).
- [ ] `State.h` — add `std::string node_id;` to `KadSnapshot`, documenting the
      empty-when-not-running rule and that the value is persistent; optionally
      rename `KadSnapshot::ip` → `public_ip` to match the JSON (internal, but it
      keeps the field readable next to `buddy_ip`).
- [ ] `Refresher.cpp` — in `ParseKadFromPacket`, reach the `EC_TAG_CONNSTATE`
      tag at the packet root, call `GetKadID()`, and store
      `ToHexString().Lower()`. Leave the field empty when the sub-tag is absent
      (Kad not running) rather than emitting a zero id.
- [ ] `Api.cpp` — `HandleKad`: emit `node_id`, rename `ip` → `public_ip`, and
      emit `connected_since` by switching the single-snapshot read to
      `m_state.Dashboard()` so the handler can reach the already-parsed
      `StatusSnapshot::kad_connected_since` under one lock. (Parsing the
      timestamp a second time into `KadSnapshot` also works, but duplicates state
      for no gain.)

**Docs**
- [ ] `docs/api/REFERENCE.md` — `GET /api/v0/kad`: all three fields in the sample
      and a field table; state that `node_id` is persistent across restarts and
      lowercase hex, that `connected_since` is the same value `/status` reports,
      and — in one sentence — how `public_ip` differs from
      `connection.bind_address`.
- [ ] `docs/api/REFERENCE.md` — while there, make the endpoint's opening sentence
      true again: it claims to be the status subtree "plus the detail fields the
      status rollup omits", which only holds once `connected_since` is present.

**Web UI (`src/webapi/static`) — the rename half is REQUIRED in the same change**
- [ ] `views/networks.js:418` — the "your IP" tile reads `d.ip`; it would
      silently fall back to its `"—"` placeholder otherwise. No i18n change: the
      visible label is unaffected.
- [ ] *(optional follow-up)* add `node_id` and `connected_since` to the Kad tile
      grid (`:410-425`) plus their i18n keys, so the web view finally matches the
      desktop panel row for row.

**Tests**
- [ ] `unittests/tests/RefresherTest.cpp` — a connstate fixture carrying
      `EC_TAG_KAD_ID` lands the lowercase hex string; one without it leaves
      `node_id` empty.
- [ ] `unittests/curl-tests/amuleapi/05-read-servers-kad-categories-prefs.sh` —
      update the `.ip` path to `.public_ip`, assert `buddy.ip` still exists so the
      rename does not sweep the nested field, and assert `node_id` is a string
      matching `^[0-9a-f]{32}$` while Kad runs and `connected_since` a number.

## Acceptance criteria

- [ ] With Kad running, `GET /api/v0/kad` returns a 32-character lowercase-hex
      `node_id` equal (case-insensitively) to the *Kademlia client ID* row of the
      desktop panel for the same daemon.
- [ ] The same `node_id` comes back after restarting `amuled`, demonstrating it
      is the persisted identity and not a per-session handle.
- [ ] With Kad stopped, `node_id` is `""` and the endpoint still answers `200`.
- [ ] `connected_since` equals `GET /api/v0/status`'s `kad.connected_since` in
      the same tick, and is `0` when not connected.
- [ ] The endpoint returns `public_ip`; no response body anywhere emits a bare
      top-level `ip` for an address that belongs to us, and `buddy.ip` is
      untouched and still populated when a buddy is connected.
- [ ] `amuleapi` links cleanly on a **fresh** build tree (the `CUInt128`
      dependency is a link-time failure, so it will not show up in an incremental
      build of an already-configured tree).
- [ ] The web UI's Kad "your IP" tile shows the address exactly as before.
- [ ] A consumer can render every row of the desktop Kad Info panel from
      `GET /api/v0/kad` plus `GET /api/v0/preferences` alone.

## Out of scope

- Exposing the Kad id on `GET /api/v0/status`: it is detail-view material and
  `/status` is deliberately a headline rollup.
- Any Kad *action* (bootstrap, node-list update, start/stop) — all already have
  endpoints.
- Exposing the Kad routing table or contact list: the desktop does not show them
  either, and they are not on the wire.
- `preferences.connection.bind_address` / `bind_interface`: correctly named for
  what they are, and out of this payload.
- The daemon-side wording of the firewalled messages: the API ships the booleans
  and the ports, and the sentence is the consumer's to compose and translate.
