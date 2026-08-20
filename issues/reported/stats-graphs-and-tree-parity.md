# `/stats/graphs` and `/stats/tree`: connections triplet, sample interval, client-version cap, and a units/naming fix

## Summary

The desktop **Statistics** tab and `GET /api/v0/stats/*` are fed by the same two
EC operations, but the REST side hardcodes every knob the protocol offers, drops
one of the two data tags the daemon sends, and mislabels part of what it does
return. Everything below is fixable **without a core change and without an EC
protocol change** — every tag involved already exists and is already on the wire.

1. **The connections graph is one line where the desktop draws three.** amuled
   ships a second tag, `EC_TAG_STATSGRAPH_DATA_CONN`, carrying per-point
   *active uploads* and *active downloads* alongside the total connection count
   that the endpoint already returns. `amuleapi` parses the response, sees the
   tag, and deliberately skips it (`src/webapi/Refresher.cpp:1875-1879`: *"not in
   StatsGraphs surface yet. Skipping until a concrete client asks"*). This is
   that ask. The bytes are already paid for — they ride in the same response.

2. **The sample interval is nailed to 1 second.** The handler always sends
   `EC_TAG_STATSGRAPH_SCALE = 1` and always reports `interval_seconds: 1`. At
   1 Hz sampling and the 1800-record window it asks for, that caps every graph
   at **30 minutes of history**, with no way to trade resolution for reach.
   `?width=N` does not help — it only tails the same 30-minute window. The
   desktop asks for the scale it is going to plot at
   (`src/amule-remote-gui.cpp:4134-4142`), which is how it can show hours.

3. **The stat tree is always uncapped.** `EC_TAG_STATTREE_CAPPING` limits how
   many per-software *version* rows the daemon serializes; `amuleapi` hardcodes
   `0`, which the core reads as *unlimited* (`src/StatTree.cpp:201` —
   `max_children - 1` underflows a `uint32_t`). On a long-lived node that is
   hundreds of rows a dashboard showing a top-10 never wanted.

4. **Three things it reports are wrong, and several names cannot be mapped to
   their content.** Found while reviewing the surface for this change:

   - `session.download_bytes` / `session.upload_bytes` are **kibibytes**, not
     bytes — the daemon divides by 1024 when it records the sample
     (`src/Statistics.cpp:406-407`) and nothing multiplies it back. Every
     consumer reading these as bytes is off by a factor of 1024.
   - `session.kad_bytes` is **not bytes and not a transfer figure at all**. It
     is `s_kadNodesTotal`, a per-second running sum of the Kad *node count*
     (`src/Statistics.cpp:415-416`) whose only use is dividing it by the session
     length to get the average node count (`src/amule-remote-gui.cpp:4226`). The
     name describes something that does not exist.
   - The **time axis can be silently wrong**. The daemon answers a request for
     more points than a resolution range holds by repeating records, and says so
     through `EC_TAG_STATSGRAPH_DEPTH` — which `amuleapi` ignores while
     reconstructing timestamps at a fixed spacing. Against a daemon whose ranges
     hold `560` records rather than `1800`, the left two thirds of every graph
     are drawn time-compressed with no way for the caller to notice.
   - `unit: "bps"` labels a **bytes**-per-second value with the notation that
     universally means bits per second.
   - `/stats/graphs/kad` names a network where its three siblings name a
     quantity; the series is a node count.
   - `/stats/tree` leaks two EC-internal type tokens (`istring`, `ishort`) that
     both mean "a plain integer", names a value's identity `raw`, and keys a
     field `enum` — a reserved word in most languages a client is written in.

   `/api/v0/` is experimental and has no consumers yet, so these land in place
   rather than waiting for a `v1`. Full audit in [Naming review](#naming-review).

## Current state

| Piece | Location |
|---|---|
| Graph handler, hardcoded EC request | `src/webapi/Api.cpp:5504-5613` — `HandleStatsGraph`; `SCALE=1` / `WIDTH=1800` at `:5533-5535` |
| Graph-name validation + `unit` mapping | `src/webapi/Api.cpp:5511-5525` |
| Point serialization (reconstructs timestamps at `interval` spacing) | `src/webapi/Api.cpp:5283-5309` — `WritePointArray` |
| `?width=N` parse (client-side tail, clamped to 1800) | `src/webapi/Api.cpp:5564-5580` |
| Graph parse — reads `DATA`, **skips** `DATA_CONN` and `DEPTH` | `src/webapi/Refresher.cpp:1850-1889` — `ParseGraphsFromPacket`; the skip is `:1875-1879` |
| Snapshot struct (four series, `interval_seconds = 1` literal) | `src/webapi/State.h:520-547` — `StatsGraphs` |
| Tree handler, hardcoded capping | `src/webapi/Api.cpp:5451-5499` — `HandleStatsTree`; `CAPPING=0` at `:5464` |
| Tree node serialization (`key` / `raw` / `label` / `values` / `enum` / `extra` / `ratio`) | `src/webapi/Api.cpp:5233-5281` — `WriteStatsNode` |
| Tree parse + value-type token mapping | `src/webapi/Refresher.cpp:1676-1807` — `ECStatValueTypeName`, `ParseStatsTreeFromPacket` |
| Tree value struct | `src/webapi/State.h:460-510` — `StatsTreeValue`, `StatsTreeNode` |
| The two 1 s TTL caches (unkeyed, single-flight) | `src/webapi/Api.h:324-328`, `src/webapi/TtlCache.h` |
| Core: graph request/response | `src/ExternalConn.cpp:3387-3445` — `GetStatsGraphs` |
| Core: history walk, both data blobs, session tags | `src/Statistics.cpp:569-668` — `CStatistics::GetHistoryForGui`; `connData` at `:625-626`, session values at `:654-658` |
| Core: what a history record holds, and in which units | `src/Statistics.cpp:405-416` — `RecordHistory` |
| Core: history is recorded at 1 Hz | `src/amule.cpp:1970-1979` |
| Core: records per resolution range | `src/Statistics.h:534` — `GetPointsPerRange()` → `1800` |
| Core: tree request | `src/ExternalConn.cpp:4137-4148` |
| Core: how capping is applied | `src/StatTree.cpp:189-215` — `CreateECTag`; flag set at `src/Statistics.cpp:1160,1167` |
| Core: what each `EC_VALUE_*` type is attached to | `src/StatTree.cpp:265-300` (simple), `:333-350` (counters), `:376-384` (UL/DL), `:410-418` (packets) |
| Desktop reference — 3-line connections scope | `src/StatisticsDlg.cpp:71` (`GRAPH_CONN`), series order at `src/Statistics.cpp:473-475` |
| Desktop reference — scale/width/depth request | `src/amule-remote-gui.cpp:4113-4192` — `CStatGraphRem::DoRequery` / `HandlePacket` |
| Desktop reference — session averages from the session tags | `src/amule-remote-gui.cpp:4216-4226` |
| Desktop reference — version cap | `src/amule-remote-gui.cpp:4081-4082`, pref default `0` at `src/Preferences.cpp:1562` |
| Docs | `docs/api/REFERENCE.md:92-93` (index), `:1936` (`/stats/tree`), `:2023` (`/stats/graphs/{graph}`) |
| Curl smoke test | `unittests/curl-tests/amuleapi/07-read-stats-and-search-results.sh:137-171` |
| Frontend consumers (graph names are hardcoded) | `src/webapi/static/js/views/stats.js:20-25,54`; `src/webapi/static/js/views/networks.js:247` |

## EC protocol reference

No protocol change. Every tag below already exists and is already exchanged.

### Request tags — `EC_OP_GET_STATSGRAPHS`

| Tag | Id | Type | Meaning | What amuleapi sends today |
|---|---|---|---|---|
| `EC_TAG_STATSGRAPH_SCALE` | `0x1B02` | uint16 | Seconds between returned points. The daemon walks its history backwards taking the newest record at or before each `now - n*scale` mark. | Always `1` |
| `EC_TAG_STATSGRAPH_WIDTH` | `0x1B01` | uint16 | Maximum number of points in the reply. | Always `1800` |
| `EC_TAG_STATSGRAPH_LAST` | `0x1B03` | double | Lower bound (daemon **uptime** seconds, not wall-clock) so a reply carries only points newer than the ones the caller already drew. Optional. | Not sent — the API refetches the whole window each time |

Both `SCALE` and `WIDTH` are mandatory in practice: `GetHistoryForGui` returns
zero points when either is `0`, and the daemon answers `EC_OP_FAILED` with
*"No points for graph."*.

### Response tags — `EC_OP_STATSGRAPHS`

| Tag | Id | Payload | Status |
|---|---|---|---|
| `EC_TAG_STATSGRAPH_DATA` | `0x1B04` | `N × 4` uint32, network byte order, interleaved: `[0]` download B/s, `[1]` upload B/s, `[2]` active connections, `[3]` Kad nodes | Parsed |
| `EC_TAG_STATSGRAPH_DATA_CONN` | `0x1B0A` | `N × 2` uint32, same encoding and same `N`, interleaved: `[0]` active uploads, `[1]` active downloads | **Ignored** |
| `EC_TAG_STATSGRAPH_SESSION_DL` | `0x1B0B` | uint64 — session bytes received **÷ 1024**, i.e. KiB | Parsed, mislabelled as bytes |
| `EC_TAG_STATSGRAPH_SESSION_UL` | `0x1B0C` | uint64 — session bytes sent **÷ 1024**, i.e. KiB | Parsed, mislabelled as bytes |
| `EC_TAG_STATSGRAPH_SESSION_KAD` | `0x1B0D` | uint64 — running sum of the per-second Kad node count (node·seconds) | Parsed, mislabelled as bytes |
| `EC_TAG_STATSGRAPH_SESSION_TIMESPAN` | `0x1B0E` | double — daemon uptime in seconds at the newest point | **Ignored** |
| `EC_TAG_STATSGRAPH_DEPTH` | `0x1B14` | uint16 — records the daemon holds per resolution range (`1800` in current builds, `560` in older ones) | **Ignored** |

Semantics that have to survive the change:

- **The two data blobs are point-aligned.** `GetHistoryForGui` fills `graphData`
  and `connData` in the same loop over the same records
  (`src/Statistics.cpp:617-632`), so index *i* of one is index *i* of the other,
  oldest first. A reply carrying `DATA` but not `DATA_CONN` can only come from an
  amuled predating the tag — treat the two extra series as absent, not as zeros
  mixed into real data.

- **What the three connection counters count** (`src/Statistics.cpp:410-412`,
  stat-tree keys at `src/Statistics.cpp:989-1007`):

  | Record field | Source | Stat-tree key | Desktop line |
  |---|---|---|---|
  | `cntConnections` | `GetActiveConnections()` — open peer sockets | `active_connections` | "Active connections (1:1)" |
  | `cntDownloads` | `GetDownloadingSources()` — peers we are pulling from | `active_downloads` | "Active downloads" |
  | `cntUploads` | `GetActiveUploadsCount()` — peers we are pushing to | `active_uploads` | "Active uploads" |

- **The three session tags are only meaningful next to the timespan.** The
  desktop divides each by `SESSION_TIMESPAN` to get the session-average line it
  plots on each graph (`src/amule-remote-gui.cpp:4224-4226`). `SESSION_DL` /
  `SESSION_UL` are additionally *scaled*: `RecordHistory` stores
  `GetSessionReceivedBytes() / 1024.0` and `GetSessionSentBytes() / 1024.0`, so
  both tags are KiB, truncated to whole KiB by the `uint64` cast at
  `src/Statistics.cpp:655-656`.
  `SESSION_KAD` is not a transfer quantity in any unit — it is the time-integral
  of the node count, and `SESSION_KAD ÷ TIMESPAN` is the only thing it is for.

- **`DEPTH` is a repeat guard, not a nicety.** The daemon keeps
  `nHistRanges = 7` ranges of `GetPointsPerRange()` records each, every range at
  twice the spacing of the one before. Ask for more points than a range holds and
  the walk hands back the *same record repeated* rather than an error — and since
  no timestamps travel on the wire, the caller cannot tell. `amuleapi`
  reconstructs the time axis by stepping backwards at `interval_seconds`
  (`WritePointArray`), so those repeats are drawn as distinct samples and the
  left of the plot is silently time-compressed. Against an amuled built with the
  old `560`, today's fixed `WIDTH=1800` hits this on every request once the
  daemon has been up longer than its finest range — a young daemon is safe only
  because the walk stops when it reaches the unused preallocated records. The
  desktop handles it by clamping its request to the reported depth
  (`src/amule-remote-gui.cpp:4182-4192`).

### Request tag — `EC_OP_GET_STATSTREE`

| Tag | Id | Type | Meaning |
|---|---|---|---|
| `EC_TAG_STATTREE_CAPPING` | `0x1B05` | uint8 | Maximum children serialized for nodes flagged `stCapChildren` — the per-software **version** rows. `0` = unlimited. |

Only the version lists are capped (`src/Statistics.cpp:1167`); the OS breakdown
and every fixed skeleton node are unaffected. It is a plain per-request
parameter, so two callers can ask for different caps against the same daemon.

### `EC_VALUE_*` types and what they are attached to

| Code | Id | Attached to | What it actually is |
|---|---|---|---|
| `EC_VALUE_INTEGER` | `0x00` | **never emitted.** It is the value both parsers assume when a value carries no `EC_TAG_STAT_VALUE_TYPE` sub-tag (`src/webapi/Refresher.cpp:1706`, `src/libs/ec/cpp/ECSpecialTags.cpp:99`), which several nodes rely on — `CStatTreeItemCounterMax` (Active connections), `Reconnects`, `TotalClients`, `PeakConnections` | plain integer |
| `EC_VALUE_ISTRING` | `0x01` | `CStatTreeItemCounterTmpl` in non-byte display mode (`src/StatTree.cpp:339`) | plain integer; the code differs only in that the **desktop** renders it with `CastItoIShort` ("12.5k") |
| `EC_VALUE_BYTES` | `0x02` | byte counters | raw bytes |
| `EC_VALUE_ISHORT` | `0x03` | packet counts beside a byte total (`src/StatTree.cpp:415,453`) | plain integer; same abbreviated desktop rendering |
| `EC_VALUE_TIME` | `0x04` | uptime / durations | raw seconds |
| `EC_VALUE_SPEED` | `0x05` | rate counters | raw bytes per second |
| `EC_VALUE_STRING` | `0x06` | ratios, "Never", "Not available" | opaque English string |
| `EC_VALUE_DOUBLE` | `0x07` | percentages, ratios | raw double |

`ISTRING` and `ISHORT` carry **no information a REST client can act on** — the
distinction is which wx formatter the desktop calls. The API's own docs already
group all three under "plain count", and `integer` is already the token an
untyped value resolves to, so collapsing onto it adds no new vocabulary.

The nested sub-value the API exposes as `extra` is not one thing. It is whatever
the desktop prints in parentheses, and it has three distinct meanings:

| Node kind | Primary value | Nested value |
|---|---|---|
| `CStatTreeItemCounterTmpl` with `stShowPercent` (`src/StatTree.cpp:340-347`) | count | **percentage of parent** (`double`) |
| `CStatTreeItemPackets` / `PacketTotals` (`src/StatTree.cpp:410-418`, `:446-455`) | bytes | **packet count** |
| `CStatTreeItemUlDlCounter` (`src/StatTree.cpp:376-384`) | session bytes | **all-time total bytes** |

The current documentation describes only the third case ("the parenthetical
`(total …)`"), which is why a client written against the docs mis-renders the
other two.

## Requested change

### A. `GET /api/v0/stats/graphs/{graph}` — three series on the connections graph

```json
{
  "graph": "connections",
  "unit": "count",
  "interval_seconds": 1,
  "max_points": 1800,
  "points": [
    { "t": "2026-06-14T09:40:00Z", "t_unix": 1781430000, "value": 42, "active_downloads": 7, "active_uploads": 4 },
    { "t": "2026-06-14T09:40:01Z", "t_unix": 1781430001, "value": 44, "active_downloads": 8, "active_uploads": 4 }
  ],
  "session": {
    "download_bytes": 12400000000,
    "upload_bytes": 980000000,
    "kad_node_seconds": 5400000,
    "duration_seconds": 86400
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `value` | int | Unchanged. Active peer connections at that point. |
| `active_downloads` | int | **New, `connections` graph only.** Peers we were downloading from. |
| `active_uploads` | int | **New, `connections` graph only.** Peers we were uploading to. |

`download_speed`, `upload_speed` and `kad_nodes` keep exactly the point shape
they have today — the two extra keys appear only where there is a second data
blob behind them. When the connected amuled predates
`EC_TAG_STATSGRAPH_DATA_CONN`, the keys are **omitted** rather than emitted as
`0`, so a consumer can tell "the daemon does not report this" from "nothing was
transferring".

### B. `?interval=N` on `GET /api/v0/stats/graphs/{graph}`

One new query parameter on all four graphs, defaulting to today's behaviour,
shown here beside the existing one it is easily confused with:

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `interval` | int, `1`–`3600` | `1` | Seconds between points. Passed straight through as `EC_TAG_STATSGRAPH_SCALE`. |
| `width` | int, `1`–`1800` | full window | Unchanged — tails the result to the last N points, applied after the fetch. |

Two new response fields:

| Field | Type | Meaning |
|---|---|---|
| `interval_seconds` | int | **Changed from a literal `1`** to the interval actually applied. It is what `t` / `t_unix` are spaced by, so a caller asking for `interval=10` gets an axis that is right. |
| `max_points` | int | **New.** How many points this daemon can answer with before it starts repeating records — `EC_TAG_STATSGRAPH_DEPTH`, defaulting to `1800` when the tag is absent. `points` is never longer than this. |

`interval=0` or a non-numeric value is `400 bad_request` (`0` makes the daemon
answer `EC_OP_FAILED`, which would surface as a confusing empty graph). Above
`3600` is `400` too: the daemon's seven ranges hold about 63 hours in total
(`1800 × (1+2+4+…+64) s`), so at one sample an hour all but ~63 points run off
the start of the session and come back empty — and `SCALE` is a uint16 on the
wire, so there is a hard ceiling regardless.

Two deliberate non-changes:

- **`width` stays a post-fetch tail.** The EC request keeps asking for the full
  window regardless of `width`, so one cached bundle still serves every
  `(graph, width)` combination. Pushing `width` into the EC request would make
  the cache key three-dimensional to save a few kilobytes of loopback traffic.
- **The reply is still fetched whole every second.** `EC_TAG_STATSGRAPH_LAST`
  incremental fetching is a real optimization and is out of scope here.

**Caching.** The single-flight `CTtlCache` is unkeyed and currently shares one
entry across all four graph names, which is only sound because the EC request is
a constant. Store the interval the bundle was fetched at inside `StatsGraphs`
and treat a mismatch as a miss: a caller with a fixed interval (every real one)
keeps today's single-round-trip-per-second behaviour, and two callers alternating
intervals each pay one EC round trip. Rejected the alternative of a
`map<interval, cache>` — an unbounded cache keyed by a caller-supplied value, for
a case nobody has.

**Server-side clamp.** After parsing, truncate every series to the last
`max_points` samples. This is what removes the silently-stretched axis against a
daemon with shallower ranges, and it is a no-op on current builds where the
request width and the depth are both 1800.

### C. `?max_client_versions=N` on `GET /api/v0/stats/tree`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `max_client_versions` | int, `0`–`255` | `0` (unlimited) | Maximum per-software version rows the daemon serializes. Passed as `EC_TAG_STATTREE_CAPPING`. |

The response shape does not change. Out-of-range or non-numeric is
`400 bad_request`. Same caching resolution as above: keep the value the tree was
fetched at next to it and treat a mismatch as a miss. The default stays `0`, so a
caller that never passes the parameter sees today's tree and today's cache
behaviour.

### D. Correctness fixes to what `session` reports

| Field | Today | After |
|---|---|---|
| `session.download_bytes` | the KiB figure from `EC_TAG_STATSGRAPH_SESSION_DL`, emitted unscaled under a `_bytes` name | multiplied by 1024, so the name is true. Granularity stays 1 KiB — the daemon truncates before sending. |
| `session.upload_bytes` | same defect | same fix |
| `session.kad_bytes` | `EC_TAG_STATSGRAPH_SESSION_KAD` under a name describing a quantity that does not exist | **renamed** `session.kad_node_seconds`: the time-integral of the Kad node count. Divide by `duration_seconds` for the session-average node count. |
| `session.duration_seconds` | — | **new**, from the currently-ignored `EC_TAG_STATSGRAPH_SESSION_TIMESPAN`. Daemon uptime in seconds at the newest point. Without it the other three are underivable, which is why the desktop reads it. `0` when the daemon does not send it. |

With `duration_seconds` present a client can draw the session-average line the
desktop draws on the three graphs that have one: divide `download_bytes`,
`upload_bytes` or `kad_node_seconds` by `duration_seconds`, instead of
approximating it. The connections graph has no session-average line, on the
desktop or here.

### E. Renames (see [Naming review](#naming-review) for the reasoning)

**`GET /api/v0/stats/graphs/{graph}`**

| Before | After |
|---|---|
| `/stats/graphs/download` | `/stats/graphs/download_speed` |
| `/stats/graphs/upload` | `/stats/graphs/upload_speed` |
| `/stats/graphs/kad` | `/stats/graphs/kad_nodes` |
| `/stats/graphs/connections` | unchanged |
| `unit: "bps"` | `unit: "bytes_per_second"` |
| `unit: "count"` | unchanged |

The `404 not_found` message listing the valid names is updated with them.

**`GET /api/v0/stats/tree`**

| Before | After |
|---|---|
| `raw` | `label_value` |
| `values[].enum` | `values[].token` |
| `values[].type: "istring"` | `values[].type: "integer"` |
| `values[].type: "ishort"` | `values[].type: "integer"` |

`extra` keeps its name; what changes is the documentation, which currently
describes one of its three meanings as though it were the only one.

## Naming review

Every parameter and field these two endpoints expose, reviewed while they are
open — not just the ones this change adds.

### Renamed

| Before | After | Why |
|---|---|---|
| `{graph}` = `kad` | `kad_nodes` | Alone among the four it names a *network* rather than the quantity plotted, and the Kad tab has several plottable quantities (nodes, users, indexed keywords). The series is the node count, and `unit: "count"` does not disambiguate it. |
| `{graph}` = `download` / `upload` | `download_speed` / `upload_speed` | Plural-less `download` next to a `connections` graph reads as "number of downloads" — the exact quantity the *connections* graph carries as `active_downloads`. Renaming these two makes all four names describe what is on the y-axis: `download_speed`, `upload_speed`, `connections`, `kad_nodes`. |
| `unit: "bps"` | `unit: "bytes_per_second"` | The values are bytes per second; `bps` is bits per second everywhere else in networking, so the current token invites an 8× error. Spelling it out also removes any question for a consumer that never reads the prose. (The `*_bps` *field* suffix used elsewhere in the API is a separate, established convention and is out of scope here — this is a self-describing `unit` token, whose whole job is to be unambiguous on its own.) |
| `session.kad_bytes` | `session.kad_node_seconds` | Not bytes, and not any kind of transfer. It is `Σ(node count per second)`; the unit really is node·seconds. A consumer summing it into a traffic total — the obvious thing to do with a `_bytes` field — produces nonsense. |
| `raw` | `label_value` | For a row whose label *is* data ("v0.70b: %s"), this carries the datum ("v0.70b"). `raw` says "unprocessed" without saying of what — and it sits next to `values[]`, which is where a reader would expect a "raw value" to be, so it actively points at the wrong field. `label_value` says exactly what it is: the value the label is built around. |
| `values[].enum` | `values[].token` | `enum` is a reserved word in C++, C#, Java, Rust, PHP and Swift, so a generated client cannot name the field after the key. `token` matches the internal field name (`enum_token`, `src/webapi/State.h:487`) and reads correctly beside `type` and `value`. Rejected `sentinel` — accurate about *why* the field exists, unhelpful about what a consumer does with it. |
| `values[].type: "istring"` / `"ishort"` | `"integer"` | Both are `EC_VALUE_*` names for "an integer the desktop renders abbreviated". They leak core internals, they are indistinguishable to a REST client, and the docs already lump them with `integer`. Collapsing three tokens into one removes a lookup nobody could act on. Purely an API-layer mapping change; the EC codes are untouched. |

### Named deliberately (new fields, rejecting the obvious first choice)

| Obvious name | Chosen | Why |
|---|---|---|
| `scale` | `interval` | `scale` is the EC tag's name and it is wrong for a public API: a "scale" reads as a multiplier applied to the *values*, which is what the desktop's separate "graph scale" preference actually is. This sets the **time between samples**, and the response field it drives is already `interval_seconds`. |
| `interval_seconds` (as the query param) | `interval` | Query parameters in this API drop the unit suffix their response field carries — the same convention that has `sort=speed` addressing `speed_bps`. |
| `depth` | `max_points` | `depth` is the EC tag's word and means nothing outside the daemon's ring-buffer implementation. A consumer wants one fact: how many points it can ask for. `max_points` says that, and pairs with `width`. |
| `uploads` / `downloads` | `active_uploads` / `active_downloads` | Bare `uploads` next to a connection count reads as a cumulative session counter. `active_` marks it instantaneous and matches the keys the same three numbers already carry in `GET /stats/tree` (`active_uploads`, `active_downloads`, `active_connections`) and the desktop's own line labels. |
| `capping` | `max_client_versions` | The wire name says neither what is capped nor by how much. It caps one specific thing; the desktop preference driving the identical tag is "Number of Client Versions shown". |
| `session_seconds` / `uptime_seconds` | `session.duration_seconds` | `uptime` would be a second, subtly different thing from the `uptime` node already in `/stats/tree` (which counts from process start, not from the oldest retained sample). Inside the `session` object, `duration_seconds` is unambiguous. |

### Reviewed, keeping the current name

| Field / param | Verdict |
|---|---|
| `value` | Renaming it to `connections` on that one graph would break the property that makes the four graphs interchangeable for a generic charting client: every point has a `value`. The two extra keys sit beside it, they do not replace it. |
| `width` | Names the caller's intent — how many samples wide the chart is — which is a different question from how far apart they are. Documented, and the pairing with the new `max_points` reads naturally. |
| `points[].t` / `t_unix` | Terse, but `t_unix` is self-evident and `t` beside it clearly reads as the other spelling of the same instant. This is also the array that repeats up to 1800 times, so the key length is the one place in this payload where it costs something real. |
| `graph`, `unit`, `points`, `session`, `interval_seconds` | Say what they hold. `session` is a container of session-to-date figures, all four now correctly named and united. |
| `session.download_bytes` / `upload_bytes` | Correct names for what the fields will hold **after** the ×1024 fix; the defect is the value, not the name. |
| `extra` | Renaming it to `secondary` would convey nothing new, and no accurate name exists for a field that is a percentage, a packet count or an all-time total depending on the node. It is `type`-tagged; what it needs is documentation of all three cases, not a new name. |
| `nodes`, `children`, `label`, `key` | Standard tree vocabulary, already documented. `key` is explicitly the stable machine id and `label` explicitly the English template. |
| `values[].type: bytes / speed / time / double / string / integer` | Each names a real distinction a client acts on when formatting. |
| `ratio.session` / `ratio.total` | Documented as download-per-upload doubles; the object name plus the docs carry the direction, and no shorter name does. |

## Implementation checklist

**amuleapi (`src/webapi/`)**
- [ ] `State.h` — `StatsGraphs`: add `active_uploads` / `active_downloads`
      (`std::vector<std::uint32_t>`, empty = daemon did not report), `max_points`
      (default `1800`), `session_duration_seconds`, rename
      `session_kad_bytes` → `session_kad_node_seconds`, and make
      `interval_seconds` a fetched value rather than a literal.
- [ ] `Refresher.cpp` `ParseGraphsFromPacket` — unpack
      `EC_TAG_STATSGRAPH_DATA_CONN` with the existing `UnpackInterleavedUint32`
      helper at `num_channels = 2`; read `EC_TAG_STATSGRAPH_DEPTH` and
      `EC_TAG_STATSGRAPH_SESSION_TIMESPAN`; multiply `SESSION_DL` / `SESSION_UL`
      by 1024 with a comment recording that the daemon divides at
      `Statistics.cpp:406-407`; truncate all six series to `max_points`; replace
      the "skipping until a concrete client asks" comment.
- [ ] `Refresher.cpp` `ECStatValueTypeName` — map `EC_VALUE_ISTRING` and
      `EC_VALUE_ISHORT` to `"integer"`.
- [ ] `State.h:467` — the `StatsTreeValue::extra` comment repeats the docs'
      mistake ("the parenthetical `(total …)`"). Correct it to the three cases
      so the next reader does not inherit it.
- [ ] `Api.cpp` `HandleStatsGraph` — rename the three graph path tokens and the
      `unit` value; parse and validate `interval`; send it as
      `EC_TAG_STATSGRAPH_SCALE`; report `interval_seconds` and `max_points`; emit
      the renamed/new `session` fields; pass the two extra series to
      `WritePointArray` for the `connections` graph only.
- [ ] `Api.cpp` `WritePointArray` — accept two optional parallel series and emit
      `active_downloads` / `active_uploads` when present, keeping the
      tail-and-timestamp logic in one place rather than forking a second writer.
- [ ] `Api.cpp` `WriteStatsNode` — emit `label_value` instead of `raw` and
      `token` instead of `enum`.
- [ ] `Api.cpp` `HandleStatsTree` — parse and validate `max_client_versions`,
      send it as `EC_TAG_STATTREE_CAPPING`.
- [ ] Both handlers — carry the fetch parameter (interval / cap) inside the
      cached value and treat a mismatch as a cache miss.

**Docs**
- [ ] `docs/api/REFERENCE.md:2023` — `/stats/graphs/{graph}`: new graph names,
      `interval`, `max_points`, the two new point fields (omitted, not zeroed, on
      an older daemon), the `width`-tails / `interval`-refetches distinction, the
      `unit` token, the corrected `session` object with the 1 KiB granularity
      note and the "divide by `duration_seconds`" recipe, and the `400` cases.
- [ ] `docs/api/REFERENCE.md:1936` — `/stats/tree`: `max_client_versions` and
      that `0` means unlimited; `raw` → `label_value`; `enum` → `token`; drop
      `istring` / `ishort` from the type table; replace the `extra` description
      with all three cases (percentage of parent / packet count / all-time
      total).
- [ ] `docs/api/REFERENCE.md:92-93` — index entries listing the graph names.
- [ ] `docs/api/REFERENCE.md:2039-2040` — while rewriting the sample: its two
      points pair `2026-06-19T11:00:00Z` / `2026-06-19T11:00:10Z` with epochs
      `1781430000` / `1781430010`, which are actually `2026-06-14T09:40:00Z` and
      `:10Z`. A reader checking the two representations against each other finds
      them inconsistent; use a pair that matches.

**Tests**
- [ ] `unittests/tests/RefresherTest.cpp` — a fixture `EC_OP_STATSGRAPHS` packet
      with both blobs asserts the six series come out point-aligned and
      big-endian-decoded; one with `DATA` only asserts the two extra series stay
      empty; one whose `DEPTH` is below the point count asserts the truncation;
      one asserts `SESSION_DL` is scaled by 1024 and `TIMESPAN` lands in
      `session_duration_seconds`.
- [ ] `unittests/curl-tests/amuleapi/07-read-stats-and-search-results.sh` —
      the four current graph names answer `200` and the three retired ones
      (`download`, `upload`, `kad`) `404`;
      `interval_seconds` echoes a requested `?interval=5`; `max_points` is a
      positive number and `points` never exceeds it; `?interval=0` and
      `?interval=99999` are `400`; `/stats/graphs/connections` points carry
      `active_downloads` / `active_uploads` and the other three graphs do not;
      `session` carries `kad_node_seconds` and `duration_seconds` and no
      `kad_bytes`; `/stats/tree` nodes never report type `istring` / `ishort` and
      never carry an `enum` or `raw` key; `/stats/tree?max_client_versions=1` is
      `200` with no `client_versions` container holding more than one child;
      `?max_client_versions=999` is `400`.

**Web UI (`src/webapi/static`)** — required, not optional: the bundled frontend
reads three of the keys this change renames, so it breaks without these edits.
- [ ] `js/views/stats.js:20-25,54` — the `GRAPHS` array's `name` fields
      (`download_speed`, `upload_speed`, `connections`).
- [ ] `js/views/networks.js:247` — the Kad graph URL (`kad_nodes`).
- [ ] `js/views/stats.js:127-133` — the dynamic version/OS row head reads
      `node.raw`; switch it to `node.label_value` (and the comment above it).
- [ ] `js/views/stats.js:148` — `v.enum ? tEnum(v.enum) : …` reads the renamed
      key; switch it to `v.token`. The `default:` branch comment at `:149` still
      lists `integer/istring/ishort`; drop the two retired tokens.
- [ ] Optional follow-up, can ship separately: `js/charts.js` draws at most two
      series (`[xs, ys, avgYs]`, header comment lines 6-7). Generalize it to N
      named series with a legend entry each, then plot the connections card the
      way the desktop does — active connections, active downloads, active uploads
      — dropping the client-side SMA that currently stands in for a second line
      there. New i18n keys in `static/i18n/*.json`, verified with
      `node src/webapi/tools/check-i18n.mjs`.

## Acceptance criteria

- [ ] Against a daemon that sends `EC_TAG_STATSGRAPH_DATA_CONN`,
      `GET /api/v0/stats/graphs/connections` returns `active_downloads` and
      `active_uploads` on every point, and the values match the desktop's Active
      downloads / Active uploads lines for the same instant.
- [ ] Those two keys are absent — not `0` — when the connected amuled does not
      send `EC_TAG_STATSGRAPH_DATA_CONN`, and the endpoint still answers `200`.
- [ ] `GET /api/v0/stats/graphs/download_speed?interval=10` reports
      `interval_seconds: 10`, and consecutive `t_unix` values differ by 10.
- [ ] With no `interval`, the point series is identical to today's.
- [ ] `points` never exceeds `max_points`, on a daemon reporting `560` as well as
      one reporting `1800`.
- [ ] `?interval=0`, `?interval=3601`, `?interval=abc` and
      `?max_client_versions=256` are all `400 bad_request`.
- [ ] `GET /api/v0/stats/tree?max_client_versions=5` returns at most five version
      rows per software, and the fixed skeleton nodes and the OS breakdown are
      untouched.
- [ ] `session.download_bytes` matches the **primary** value of the
      `download_data` node of `GET /api/v0/stats/tree` — the session figure, in
      raw bytes; that node's nested value is the all-time total — to within
      1 KiB, and likewise `upload_bytes` against `upload_data`. This is the check
      that proves the ×1024 fix landed.
- [ ] `session.kad_node_seconds ÷ session.duration_seconds` matches, within
      rounding, the session-average Kad node count the desktop plots, and
      `kad_bytes` appears nowhere in the codebase, the docs or the tests.
- [ ] `/stats/graphs/download`, `/upload` and `/kad` return `404 not_found`, and
      the error message lists the four current names.
- [ ] No `/stats/tree` response contains `raw`, `enum`, `istring` or `ishort`,
      and — with the frontend edits above applied — the bundled web UI renders
      the tree, the version/OS rows and the "Never" sentinel exactly as before.
- [ ] Against an amuled with none of `EC_TAG_STATSGRAPH_DATA_CONN`,
      `EC_TAG_STATSGRAPH_DEPTH` or `EC_TAG_STATSGRAPH_SESSION_TIMESPAN`, both
      endpoints answer `200` with the documented fallbacks.
- [ ] `docs/api/REFERENCE.md` documents every new and renamed parameter and
      field, and the three meanings of `extra`.

## Out of scope

- Incremental graph fetching via `EC_TAG_STATSGRAPH_LAST`. The API refetches the
  whole window every second and that is fine at these sizes; making it
  incremental means holding a per-interval ring in `amuleapi` and is separate
  work.
- Real per-point timestamps on the wire. `EC_TAG_STATSGRAPH_LAST` is measured in
  daemon *uptime* seconds, not wall-clock, so it cannot replace the backwards
  reconstruction in `WritePointArray` without a new tag — i.e. a protocol change.
- The `*_bps` field-name convention used by `/status`, `/downloads`, `/shared`
  and `/clients`. It is established across the API and consistent within itself;
  only the self-describing `unit` token on this endpoint is changed here.
- The desktop's graph *value* scales (`EC_TAG_CONN_DL_CAP` / `_UL_CAP`) and the
  Statistics preference page in general — display preferences, not data, and they
  belong with the preferences surface.
- An SSE channel for graph points. These endpoints are polled by design.
- Any change to how the desktop client requests or draws these graphs, or to the
  `EC_VALUE_*` codes themselves.
