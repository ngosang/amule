# `GET /api/v0/status`: expose the counters and identity it drops, and settle its field names

## Summary

`GET /api/v0/status` (and its `status_changed` SSE twin) is the API's headline
view of the node. Three things are wrong with it today, all in the same handler
and all fixable from the data `amuleapi` already receives once per tick:

1. **Counters that arrive and get dropped.** The refresher asks `amuled` for
   stats at `EC_DETAIL_FULL`, and that response carries the **protocol overhead
   rates** and the **free disk space** for the Temp and Incoming directories.
   `StatusSnapshot` reads none of them — `RefresherTick.cpp` even says so in a
   comment. The desktop shows the overhead in the status bar (*Show overhead
   bandwidth*) and the disk figures under the Downloads and Shared Files lists,
   with a warning when the queue needs more room than is left.
2. **Our own eD2k identity is missing.** The desktop *Networks → ED2K Info*
   panel shows five rows; the API covers three. Missing: the numeric **ID** and
   the public **IP:Port** a HighID gives you. The id already rides
   `EC_TAG_CONNSTATE` — `amuleapi` even calls into that tag object today for
   `HasLowID()`, which is *derived from the id it then throws away*.
3. **Three field names do not survive a second reading**, and one of them
   reports an alarming value in a state where it means nothing.

**No core change, no EC protocol change, no extra round-trip.** `/api/v0/` is
experimental and has no consumers outside this repository yet, so the renames
land in place rather than waiting for a `v1`.

## Parity table — desktop *ED2K Info* panel

Every row `CServerWnd::UpdateED2KInfo` (`src/ServerWnd.cpp:249-289`) can render:

| Desktop row | API today | Verdict |
|---|---|---|
| `eD2k Status:` — *Connected* / *Not Connected* | `ed2k.state` | covered |
| `IP:Port` — our public address + local TCP port (HighID), or the literal word *Server* (LowID) | — | **missing** → `ed2k.public_ip`, paired with `preferences.connection.tcp_port` |
| `ID` — the numeric id | — | **missing** → `ed2k.id` |
| `Connection Type:` — *LowID* / *HighID* | `ed2k.low_id` | covered, but reports `true` while disconnected — fixed below |
| `Connected since:` | `ed2k.connected_since` | covered |

With the fields below, the whole panel is reproducible from `GET /api/v0/status`
plus `GET /api/v0/preferences`. The rest of the Networks → eD2k page — the server
list and its actions, the *Server Info* and *aMule Log* panes — is served by
other endpoints and is out of scope here.

## Current state

| Piece | Location |
|---|---|
| Core emits the overhead + free-space tags | `src/ExternalConn.cpp:1573-1589` — `Get_EC_Response_StatRequest`, in the `EC_DETAIL_FULL` / `EC_DETAIL_INC_UPDATE` branch |
| Core emits the eD2k id | `src/ECSpecialCoreTags.cpp:184` — `CEC_ConnState_Tag`, when connected; `:196` sends `0xffffffff` while connecting |
| Overhead sources | `theStats::GetUpOverheadRate()` / `GetDownOverheadRate()` — `src/Statistics.cpp:326-327` (`CPreciseRateCounter`, 5 s window) |
| Free-space sources | `theStats::GetTempFreeSpace()` / `GetIncomingFreeSpace()` — `src/Statistics.h:463,468`; plain atomic reads, published every 10 s by `CFreeSpaceThread` (`src/FreeSpaceThread.cpp:42`), so a stats poll never touches the filesystem |
| eD2k id source | `CamuleApp::GetED2KID()` → `serverconnect->GetClientID()` — `src/amule.cpp:3110-3113` |
| libec accessors | `src/libs/ec/cpp/ECSpecialTags.h:312-314` — `GetEd2kId()`, `GetClientId()`, `HasLowID()` |
| `amuleapi` already requests `EC_DETAIL_FULL` | `src/webapi/RefresherTick.cpp:67` — the comment at `:57-66` explicitly lists the unused tags |
| Status parse | `src/webapi/Refresher.cpp:174-252` — `ParseStatusFromPacket`; `HasLowID()` at `:187`, speeds at `:212-217` |
| Snapshot struct | `src/webapi/State.h:936-999` — `StatusSnapshot`; `ed2k_lowid` at `:962`, speeds at `:975-976`, the two `queue` fields at `:979-980` |
| REST emit | `src/webapi/Api.cpp:1934-2004` — `HandleStatus` (`ed2k` object at `:1934`, `speeds` + `queue` at `:1991-2004`) |
| Peer-side counterpart | `src/webapi/Api.cpp:2415` — `high_id` on `GET /clients/{ecid}`, next to `user_id_hybrid` at `:2413` |
| Existing dotted-quad helpers (**both file-local**, see the note below) | `src/webapi/Refresher.cpp:709-722` — `FormatClientIpv4`; `:1337` — `IPv4ToDotted` |
| SSE payload | `src/webapi/EventDiff.cpp:219-242` — `ToJsonStatusEvent` (`low_id` at `:225`, `speeds` at `:235-236`, `queue` at `:237-239`) |
| SSE change detection | `src/webapi/EventDiff.cpp:331-339` — `Equal(const StatusSnapshot&, const StatusSnapshot&)` |
| Desktop consumers (reference) | status bar in `src/amuleDlg.cpp` (overhead); `src/DownloadListCtrl.cpp:1186-1205` (temp free space + low-space warning); `src/SharedFilesCtrl.cpp:1127` (incoming free space); `CamuleDlg::SetFreeSpaceLabel`, `src/amuleDlg.cpp:695-720`; `src/ServerWnd.cpp:249-289` (ED2K Info) |
| Docs | `docs/api/REFERENCE.md` — `GET /api/v0/status`, and `GET /clients/{ecid}` for `high_id`; `docs/api/EVENTS.md:385-410` — `status_changed` |
| Bundled web UI (**breaks if not updated in the same change**) | `static/js/app.js:309,311`; `static/js/views/networks.js:383` — both read `ed2k.low_id` |
| Tests | `unittests/tests/RefresherTest.cpp`, `unittests/tests/EventDiffTest.cpp`; `unittests/curl-tests/amuleapi/03-read-status.sh`, `26-rfc-followup-endpoints.sh` |

## EC protocol reference

No protocol change. Every value below is already on the wire:

| Tag | Id | Type | Notes |
|---|---|---|---|
| `EC_TAG_STATS_UP_OVERHEAD` | `0x0204` | uint32 | Current upload overhead, **bytes/second** |
| `EC_TAG_STATS_DOWN_OVERHEAD` | `0x0205` | uint32 | Current download overhead, **bytes/second** |
| `EC_TAG_STATS_TEMP_FREE_SPACE` | `0x021C` | uint64 | Free bytes on the filesystem holding the part files |
| `EC_TAG_STATS_INCOMING_FREE_SPACE` | `0x021D` | uint64 | Free bytes where finished downloads land |
| `EC_TAG_ED2K_ID` | `0x0006` | uint32 | Sub-tag of `EC_TAG_CONNSTATE` (`0x0005`). Present only while connected; `0xffffffff` while a connect is in flight |

Defined in `src/libs/ec/abstracts/ECCodes.abstract:190,234-235,258-259`.

Properties the implementation must respect:

- **Detail-level gated.** The core only adds the stats extras at
  `EC_DETAIL_FULL` / `EC_DETAIL_INC_UPDATE` (`ExternalConn.cpp:1567-1589`).
  `amuleapi` already asks for `EC_DETAIL_FULL` — but do not "optimise" that
  request down to `EC_DETAIL_CMD` afterwards, or these tags (and the log channel)
  disappear.
- **Overhead is *not* part of the main rates.** `GetUploadRate()` and
  `GetOverheadRate()` are separate counters; the desktop renders the overhead as
  an additional figure in parentheses, not a subset. The API fields are likewise
  **additive** to `speeds.{download,upload}_bps`.
- **HighID vs LowID.** An id `>= HIGHEST_LOWID_ED2K_KAD` (`16777216`,
  `src/NetworkFunctions.h:122`) is a HighID, and then the id **is our public
  IPv4** packed into a uint32; below that is a LowID, an arbitrary small number
  the server picked for a firewalled client. That is exactly what
  `CEC_ConnState_Tag::HasLowID()` tests.
- **Byte order.** The id packs the address LSB-first, the same layout
  `EC_TAG_CLIENT_USER_IP` uses, so `FormatClientIpv4()` renders it correctly
  as-is — matching `Uint32toStringIP()` in the desktop
  (`src/NetworkFunctions.h:36-39`).
- **Two sentinels never reach the JSON**: `0xffffffff` for "connecting, no id
  yet", and the free-space one below.

## Implementation note 1: the free-space sentinel is `-1` cast through uint64

`theStats::GetTempFreeSpace()` returns a **signed** `sint64` whose
`FREE_SPACE_UNKNOWN` value is `-1` (`src/Statistics.h:68`) — the state before
`CFreeSpaceThread` has published its first sample, and the state an unreachable
mount (a NAS holding Temp or Incoming, say) leaves behind permanently. The EC
serializer casts it straight to `uint64` (`ExternalConn.cpp:1587-1589`), so
**the wire carries `0xFFFFFFFFFFFFFFFF`**.

Storing that in an unsigned snapshot field and emitting it would put
`18446744073709551615` in the JSON — read by any consumer as "17 exabytes free",
the exact opposite of the truth. The desktop is careful here: it hides the label
entirely rather than printing `0 bytes`, because "0" would read as a full disk
(`CamuleDlg::SetFreeSpaceLabel`, `src/amuleDlg.cpp:702-712`).

The decode is free as long as the field is signed — `static_cast<std::int64_t>`
on the tag's `GetInt()` turns `0xFFFFFFFFFFFFFFFF` back into `-1`:

```cpp
if (const CECTag *t = resp->GetTagByName(EC_TAG_STATS_TEMP_FREE_SPACE)) {
    out.temp_free_bytes = static_cast<std::int64_t>(t->GetInt());  // -1 == unknown
}
```

and the handler emits `null` for any negative value. `null` is already this
API's idiom for "the daemon cannot answer that" — `GET /api/v0/version` uses it
for `update.update_available`, and `CJsonWriter::ValueNull()` exists for it.

## Implementation note 2: format the address in the refresher, not the handler

The obvious shape for `public_ip` — emit the raw id into `StatusSnapshot` and
render the dotted quad in `HandleStatus` — does not compile. Both existing IPv4
formatters live in **anonymous namespaces inside `Refresher.cpp`**
(`FormatClientIpv4` in the block spanning `:358-1057`, `IPv4ToDotted` in
`:1314-1350`), so neither is visible from `Api.cpp`, and neither is declared in
`Refresher.h`.

Do not export one to work around it. Every other address the API serves is
already **stored pre-formatted as a string in the snapshot** —
`StatusSnapshot::server_ip`, `KadSnapshot::ip`, `KadSnapshot::buddy_ip`,
`ClientSnapshot::ip` — so the consistent move is to format in
`ParseStatusFromPacket`, where the helpers already are, and have the handler emit
a plain string. The HighID test lives there too, next to the code that already
computes `HasLowID()`.

## Requested change

### `GET /api/v0/status`

```diff
 {
   "ec_connected": true,
   "ed2k": {
     "state": "connected",
-    "low_id": false,
+    "high_id": true,
+    "id": 1234567890,
+    "public_ip": "210.2.150.73",
     "connected_since": 1751000000,
     "server_name": "eMule Server",
     "server_ip": "203.0.113.5",
     "server_port": 4242,
     "network": { "users": 312000, "files": 75000000 }
   },
   "kad": { "…": "…" },
   "speeds": {
     "download_bps": 4500000,
     "upload_bps": 50000,
+    "download_overhead_bps": 8700,
+    "upload_overhead_bps": 1100
   },
+  "disk": {
+    "temp_free_bytes": 48318382080,
+    "incoming_free_bytes": 48318382080
+  },
   "queue": {
-    "upload_queue_length": 12,
-    "total_source_count": 1843
+    "upload_clients_waiting": 12,
+    "download_sources_total": 1843
   }
 }
```

| Field | Type | Meaning |
|---|---|---|
| `ed2k.id` | int | **New.** Our eD2k id as assigned by the connected server. `0` when not connected, and `0` while connecting (the `0xffffffff` sentinel is normalized away). `>= 16777216` is a HighID. |
| `ed2k.public_ip` | string | **New.** Our public IPv4, dotted quad, derived from `id` when it is a HighID. `""` for a LowID or while disconnected, because a LowID carries no address. |
| `ed2k.high_id` | bool | **Renamed + flipped** from `low_id`. `true` when our id is a HighID. `false` for a LowID **and** whenever we are not connected — gate on `ed2k.state == "connected"` before treating it as a firewall verdict. |
| `speeds.download_overhead_bps` | int | **New.** Protocol/control-traffic overhead currently being received, bytes/second. **Additive** to `download_bps`, not part of it. |
| `speeds.upload_overhead_bps` | int | **New.** Same for the sending direction. |
| `disk.temp_free_bytes` | int \| null | **New.** Free bytes on the filesystem holding the part files. `null` when the daemon has no figure — first seconds after startup, or a directory it cannot stat. |
| `disk.incoming_free_bytes` | int \| null | **New.** Free bytes where finished downloads land. Same `null` rule. |
| `queue.upload_clients_waiting` | int | **Renamed** from `upload_queue_length`. Peers queued for an upload slot. |
| `queue.download_sources_total` | int | **Renamed** from `total_source_count`. Sources known across every file in the download queue. |

Two caveats the docs should carry: the two disk figures are **equal whenever
Temp and Incoming share a filesystem** (the default layout — correct, not a bug),
and `incoming_free_bytes` describes the **default category's** incoming directory
(`src/Statistics.h:465-467`), so a category pointed at another filesystem is not
covered and the daemon reports no per-category figure.

The overhead fields are always present, `0` when the daemon reports nothing.
`Auth: GUEST`, unchanged. `/status` takes no query parameters and no request
body; that is unchanged too.

A consumer reproduces the desktop's low-space warning by comparing
`disk.temp_free_bytes` against the bytes still to write across the queue
(`size - size_done` summed over `GET /downloads`), which is what
`CDownloadListCtrl` does (`src/DownloadListCtrl.cpp:1186-1205`), or against the
`files.min_free_space_mb` preference when `files.stop_on_low_disk_space` is on.

### `GET /api/v0/clients/{ecid}` — docs only

The peer-side `high_id` keeps its name and semantics; it is already the target
spelling. Its documentation should gain the same explicit `16777216` threshold
sentence, so both ends of the API are documented against the same number instead
of one saying "id ≥ `0x1000000`" and the other saying nothing.

### SSE `status_changed`

`ToJsonStatusEvent` emits every field above with the same names, and
`Equal(const StatusSnapshot&, …)` compares the new values (`ed2k_id`, the two
overhead rates, the two disk figures; `public_ip` is derived from the id, so
comparing the id is sufficient).

Event-rate impact is negligible. The overhead rates move on essentially every
tick while transfers run, but so do `download_bps` / `upload_bps`, already in
that comparison — no new wakeups. The disk figures are resampled only every 10 s
(`src/FreeSpaceThread.cpp:42`), so at worst they add one `status_changed` per
10 s, and only when the number moved. On a fully idle daemon nothing new fires.

## Naming review

Every field this endpoint returns, reviewed while the handler is open. `/status`
has no query parameters and no request body, so the response object is the whole
surface.

### Renamed

| Before | After | Why |
|---|---|---|
| `ed2k.low_id` | `ed2k.high_id` | Two reasons. **Consistency:** `GET /clients/{ecid}` already reports a peer's as `high_id`, so today the same question is answered with opposite polarity depending on whose identity it is, and any shared client-side helper has to invert one. **Honesty:** the negative spelling degrades badly in the third state — `HasLowID()` is `GetEd2kId() < 16777216` and the absent tag reads as `0`, so `/status` currently reports `low_id: true` whenever we are **not connected at all**, which renders as a firewall diagnosis for a daemon that simply has no id yet. `high_id: false` reads correctly in both LowID and disconnected. It is also the direction the API already leans: `docs/api/REFERENCE.md` documents "`connection.extended_udp_port_enabled` is positive-sense", where the underlying EC tag is the negative `EC_TAG_CONN_UDP_DISABLE`. |
| `queue.upload_queue_length` | `queue.upload_clients_waiting` | Stutters against its own parent (`queue.…queue…`), and "length" hides *what* is queued. It counts **peers**, not bytes or files — the desktop calls them queued clients. |
| `queue.total_source_count` | `queue.download_sources_total` | "Total … count" of what? Nothing in the name ties it to downloads, and it is the odd one out in an object called `queue`. The new name says which side it belongs to and echoes the per-file `sources.total` vocabulary `GET /downloads` already uses. |

**Considered and rejected** for the polarity: a three-state enum
(`id_type: "high" | "low" | "unknown"`). It models the disconnected case
honestly, but costs every consumer a string comparison for what is binary in the
only state where it means anything, and the peer side genuinely has no third
state. A documented boolean beside `state` carries the same information.

The two `queue` keys are not read by the bundled web UI (`grep
upload_queue_length src/webapi/static` is empty), so those renames cost nothing
beyond this endpoint, its SSE payload and the docs. Optionally align the C++
snapshot fields too (`ul_queue_len`, `total_src_count`, `ed2k_lowid`) — internal,
so a readability call rather than a contract one.

### Named deliberately (new fields, rejecting the obvious first choice)

| Obvious name | Chosen | Why |
|---|---|---|
| `ed2k.client_id` | `ed2k.id` | It is the eD2k term of art (`serverconnect->GetClientID()`), but in *this* API `client` means **a remote peer** everywhere else — the `/clients` collection, the `/clients/{ecid}` detail route, the `client_added` / `client_updated` / `client_removed` events, and the peer object's own field names. `status.ed2k.client_id` would be the single place where `client_` points at ourselves. Inside an object called `ed2k`, a bare `id` is unambiguous and reads naturally next to `high_id`, which qualifies it. Also rejected: `ed2k_id` (stutters as `ed2k.ed2k_id`) and `user_id` (collides with the peer-side `user_hash` / `user_id_hybrid`). |
| `ed2k.ip` | `ed2k.public_ip` | The same object already carries `server_ip`. A bare `ip` there is a coin flip between "our address" and "the server's address" — and the value is specifically the address the *network* sees us at, the interesting distinction from a bind address or a LAN address. |
| flat `temp_free_bytes` | a `disk` object | `/status` groups by concern — `ed2k`, `kad`, `speeds`, `queue` — and disk is a third concern. It also leaves room for a future figure without another top-level key. |
| `temp_free` | `temp_free_bytes` | Unit in the name, matching `speeds.*_bps` here and `total_bytes` / `session.download_bytes` elsewhere. Without it a reader has to guess bytes vs MiB — and the related preference, `files.min_free_space_mb`, is in **MiB**, so the ambiguity is real. The two keys are named after the directories the daemon's own preferences call `directories.temp` and `directories.incoming`, so the join is obvious. |

### Reviewed, keeping the current name

| Field | Verdict |
|---|---|
| `ec_connected` | "EC" is jargon, but it is *this project's* jargon and it is used consistently: the `ec_unavailable` error code every endpoint can return names the same thing. Renaming here alone would break that pairing. |
| `state` | Three-state enum (`connected` / `connecting` / `disconnected`), shared shape with `kad.state`. |
| `connected_since` | Unix seconds, consistent with every other timestamp in the API (`last_seen`, `shared_since`, `last_upload` — none carry a `_unix` suffix). |
| `server_name`, `server_ip`, `server_port` | Prefixed, unambiguous, and the prefix is what lets `public_ip` sit beside them without confusion. |
| `speeds.download_bps` / `upload_bps` | Direction + unit in the name; the new overhead fields deliberately copy the pattern. |
| `network.users`, `network.files` | Mirrors `kad.network.{users,files,nodes}`. |

## Implementation checklist

**amuleapi (`src/webapi/`)**
- [ ] `State.h` — in `StatusSnapshot`: add `std::uint32_t ed2k_id = 0;`,
      `std::string ed2k_public_ip;`, `std::uint64_t download_overhead_bps = 0;`
      and `upload_overhead_bps = 0;`, plus `std::int64_t temp_free_bytes = -1;`
      and `incoming_free_bytes = -1;` (**signed**, `-1` = unknown — note 1);
      rename `ed2k_lowid` → `ed2k_high_id`. Comment the additive overhead
      semantics and the false-while-disconnected rule.
- [ ] `Refresher.cpp` — in `ParseStatusFromPacket`: set `ed2k_high_id` from
      `conn->IsConnectedED2K() && !conn->HasLowID()`; inside the existing
      `IsConnectedED2K()` block read `conn->GetEd2kId()` (skipping the
      `0xffffffff` sentinel) and, for a HighID, store `FormatClientIpv4(id)` into
      `ed2k_public_ip` (note 2); read the four stats tags with the existing
      `if (const CECTag *t = resp->GetTagByName(...))` pattern, casting the
      free-space ones through `std::int64_t`.
- [ ] `RefresherTick.cpp:57-66` — update the comment: these tags are no longer
      "harmless overhead", they are consumed.
- [ ] `Api.cpp` — `HandleStatus`: emit `id`, `public_ip` and `high_id` in the
      `ed2k` object; the two overhead keys in `speeds`; the new `disk` object
      (`ValueNull()` for a negative figure); rename the two `queue` keys.
- [ ] `EventDiff.cpp` — mirror all of it in `ToJsonStatusEvent` (JSON `null`
      there too, not `-1`), and compare the new fields in
      `Equal(const StatusSnapshot&, const StatusSnapshot&)`.

**Docs**
- [ ] `docs/api/REFERENCE.md` — `GET /api/v0/status`: extend the sample; document
      the id and the HighID threshold, `public_ip`, the renamed `high_id` and its
      "only meaningful when connected" caveat, the additive overhead semantics,
      the `null` disk sentinel, the equal-when-same-filesystem note and the
      default-category caveat, and the two renamed `queue` keys.
- [ ] `docs/api/REFERENCE.md` — `GET /api/v0/clients/{ecid}`: state the same
      `16777216` threshold for the peer-side `high_id`.
- [ ] `docs/api/EVENTS.md` — `status_changed`: the same keys in its payload
      sample, and its prose ("Fires when any field anywhere in the envelope
      changes — … headline speeds, queue length, or `ec_connected`") which now
      also covers the overhead rates and the disk figures.

**Web UI (`src/webapi/static`) — the `high_id` half is REQUIRED in the same change**

Both call sites read `ed2k.low_id` and would silently invert the badge.
- [ ] `static/js/app.js:309,311` — the header connection badge (`e2Cls`, label).
- [ ] `static/js/views/networks.js:383` — the eD2k connection-type row.
- [ ] No i18n changes for that: both the `..._low_id` and `..._high_id` strings
      already exist in `static/i18n/*.json`; only the branch that picks between
      them flips.

**Web UI — optional follow-up, can ship separately**
- [ ] Overhead in parentheses next to the header speeds
      (`static/js/app.js:364-365`), behind a toggle mirroring the desktop
      preference.
- [ ] Free-space figures under the Downloads and Shared lists, hidden when
      `null`, warning-coloured when the queue needs more than is left.
- [ ] An eD2k info block in the Networks view mirroring the desktop panel
      (status / IP:Port / ID / connection type / connected since). Plus i18n keys
      for all three.

**Tests**
- [ ] `unittests/tests/RefresherTest.cpp` — a HighID connstate lands the id and
      the dotted quad and sets `ed2k_high_id`; a `0xffffffff` connstate leaves
      the id `0`; a disconnected connstate leaves id `0`, `public_ip` empty and
      `ed2k_high_id` false; a packet with all four stats tags lands them; one
      without leaves overhead `0` and disk `-1`; **a packet carrying
      `0xFFFFFFFFFFFFFFFF` reads back as `-1`, not a huge positive number**.
- [ ] `unittests/tests/EventDiffTest.cpp` — a LowID→HighID tick fires exactly one
      `status_changed` carrying the new id; a tick where only the overhead moves
      fires exactly one; an unknown disk figure serialises as `null`.
- [ ] `unittests/curl-tests/amuleapi/03-read-status.sh` and
      `26-rfc-followup-endpoints.sh` — assert the new keys, that
      `disk.temp_free_bytes` is a number or null, that `public_ip` is non-empty
      exactly when `high_id` is true and the state is `connected`, and update the
      old `low_id` / `queue` paths.

## Acceptance criteria

- [ ] With a HighID connection, `ed2k.id` equals the **ID** row of the desktop
      ED2K Info panel for the same daemon, and `ed2k.public_ip` the address half
      of that panel's `IP:Port` row.
- [ ] With a LowID connection, `id` is the small server-assigned number,
      `public_ip` is `""`, and `high_id` is `false`. **Disconnected → `id` is `0`,
      `public_ip` is `""`, `high_id` is `false`**, where the old field reported
      the alarming `low_id: true`. The `0xffffffff` connecting sentinel never
      appears in a response.
- [ ] A HighID peer reports `high_id: true` on `/clients/{ecid}`: the same value
      means the same thing on both ends of the API.
- [ ] With traffic running, the overhead values are non-zero and in the same
      ballpark as the desktop status bar's parenthesised figures.
- [ ] `disk.temp_free_bytes` matches the figure under the desktop Downloads list
      (within one 10 s sampling window) and `disk.incoming_free_bytes` the one
      under the Shared Files list. A Temp directory that cannot be stat'ed reports
      `null` — **never** `18446744073709551615` and never `0`.
- [ ] Against an `amuled` old enough not to send the stats tags, `/status` still
      answers `200`, the overhead fields read `0` and the disk fields `null`.
- [ ] `low_id`, `upload_queue_length` and `total_source_count` appear nowhere in
      `src/`, `docs/`, `unittests/` or `static/`.
- [ ] A `status_changed` SSE frame carries exactly the same keys as the REST body.
- [ ] The web UI's header badge and the Networks eD2k row still show LowID /
      HighID correctly (not inverted) in all three states.
- [ ] A consumer can render every row of the desktop ED2K Info panel from
      `GET /api/v0/status` plus `GET /api/v0/preferences` alone.

## Out of scope

- `EC_TAG_CLIENT_ID` (`CamuleApp::GetID()`, the Kad-preferring effective id).
  A different value with different semantics; expose it under its own name if a
  consumer asks, rather than conflating it with the server-assigned id.
- `EC_TAG_STATS_BANNED_COUNT`, `EC_TAG_STATS_TOTAL_SENT_BYTES` /
  `_TOTAL_RECEIVED_BYTES` and `EC_TAG_STATS_SHARED_FILE_COUNT` — also unparsed,
  but they belong to different UI surfaces and should be argued on their own.
- Per-category free space: the daemon only publishes the Temp and default
  Incoming figures, so more would mean new core work.
- Cumulative overhead *totals* and the per-packet-class breakdown: already served
  in aggregated form by `GET /api/v0/stats/tree`.
- The Kad-side status subtree, which has its own endpoint.
- Restructuring `/status` (e.g. folding `server_name` / `server_ip` /
  `server_port` into a nested `server` object). Those names are already
  unambiguous; a reshape would be churn for its own sake.
