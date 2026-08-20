# Web UI: selectable graph time range, and the session-average line the API already ships

The four charts the bundled frontend draws are locked to a five-minute window,
and the second line on each speed chart is a client-side moving average standing
in for a figure the daemon already sends. `GET /api/v0/stats/graphs/{graph}` has
accepted `?interval=N` and reported a `session` object since #987 (issue #981),
and the Web UI passes neither and reads neither — the range that parameter
exists to control is still a compile-time constant in `stats.js`, and the
session totals go straight into the bin. The desktop client has had a graph
scale and a session-average line for as long as it has had graphs; the Web UI is
the only one of the two that cannot answer "was this stalled an hour ago?" or
"is this faster or slower than the session so far?".

**No server change and no EC protocol change.** Everything below is frontend
work against an endpoint that already does what is needed.

**Two independent pieces, one issue** because they touch the same three files
and the same `series` descriptors: sections A–F are the range selector,
sections G–H are the session-average line. Either can land first.

## Current state

| Piece | Location |
|---|---|
| Poll cadence, fetch width, SMA window | `src/webapi/static/js/views/stats.js:15-18` — `GRAPH_POLL_MS = 2000`, `TREE_EVERY = 3`, `GRAPH_WIDTH = 300`, `SMA_WINDOW = 50` |
| The three Statistics charts | `src/webapi/static/js/views/stats.js:23-32` — `GRAPHS`, each with a `series` descriptor |
| Client-side moving average (to be deleted) | `src/webapi/static/js/views/stats.js:35-44` — `sma()` |
| Graph fetch — no `interval` sent, `session` discarded | `src/webapi/static/js/views/stats.js:60-74` — `loadGraph` |
| Poll loop | `src/webapi/static/js/views/stats.js:89-98` — `refresh`, `setInterval(refresh, GRAPH_POLL_MS)` |
| Statistics grid render (no toolbar) | `src/webapi/static/js/views/stats.js:106-119` |
| Kad chart constants and descriptor | `src/webapi/static/js/views/networks.js:23-26` |
| Kad fetch + poll loop | `src/webapi/static/js/views/networks.js:244-256` |
| Kad panel toolbar (a control could join it) | `src/webapi/static/js/views/networks.js:268-276` |
| Kad chart render (`bare`, single series) | `src/webapi/static/js/views/networks.js:276` |
| Chart renderer, N series | `src/webapi/static/js/charts.js:101` — `draw(cv, g, [xs, ...series], hover)` |
| Legend — rendered only above one series | `src/webapi/static/js/charts.js:77,86-91` |
| Time-axis formatters (hour:minute only) | `src/webapi/static/js/charts.js:16-19` |
| X-axis labels — 4 evenly spaced | `src/webapi/static/js/charts.js:170-178` |
| Hover readout — adds seconds | `src/webapi/static/js/charts.js:203-214` |
| Chart CSS — legend, bare card | `src/webapi/static/css/app.css:527-538`, `:644` |
| Toolbar CSS | `src/webapi/static/css/app.css:211` |
| Persistent client-side prefs | `src/webapi/static/js/store.js:33-46` — `loadPref` / `savePref`, `"amule."`-prefixed localStorage |
| Hash router — one view mounted at a time | `src/webapi/static/js/app.js:369-390` — `RouteView` lazy-imports the single active route |
| API handler (already complete) | `src/webapi/Api.cpp:6131` — `HandleStatsGraph`; `interval` parse at `:6163-6182`, cache at `:6186`, `width` tail at `:6223-6235`, `interval_seconds` / `max_points` at `:6246-6252`, `session` at `:6276-6286` |
| Validated TTL cache | `src/webapi/TtlCache.h:71-88` — `GetOrFetch` with a predicate |
| Docs | `docs/api/REFERENCE.md:2252` — `/stats/graphs/{graph}` |

Desktop reference, for what the lines are supposed to mean:

| Piece | Location |
|---|---|
| Three lines per rate graph — *Current*, *Running average*, *Session average* | `src/StatisticsDlg.cpp:145-150` |
| Same three on the Kad graph | `src/KadDlg.cpp:107-109` |
| Three lines on Connections — *Active connections / downloads / uploads*, no average | `src/StatisticsDlg.cpp:151-153` |
| How each line is computed | `src/Statistics.cpp` — `CStatistics::ComputeAverages`; session average is `kValueRun / phr->sTimestamp` **per point** |
| How amulegui reconstructs the per-point totals from the session tags | `src/amule-remote-gui.cpp:4228-4300` |
| Desktop's scale request | `src/amule-remote-gui.cpp:4122-4168` — `CStatGraphRem::DoRequery` |

## What the API already gives us

| Parameter | Range | Default | Effect |
|---|---|---|---|
| `interval` | `1`–`3600` | `1` | Seconds between samples. Passed straight to amuled as `EC_TAG_STATSGRAPH_SCALE`, so it changes **how far back the window reaches**. |
| `width` | `1`–`1800` | full window | Tails the reply to the last N samples. Applied after the fetch; it does **not** change the span each sample covers. |

Response fields that matter here:

- `interval_seconds` — the interval actually applied. `t` / `t_unix` are spaced
  by it, so the reconstructed time axis is correct for any interval.
- `max_points` — how many points this daemon can answer with before it starts
  repeating records. The server truncates every series to it.
- `session.download_bytes` / `session.upload_bytes` — session totals in **bytes**
  (1 KiB granularity; amuled truncates before sending).
- `session.kad_node_seconds` — `Σ(Kad node count per second)`, i.e. node·seconds.
  Not a transfer figure and meaningless except as a numerator.
- `session.duration_seconds` — daemon uptime at the newest point. `0` when the
  daemon does not report it. This is the divisor that turns the three figures
  above into the averages they exist for.

Out-of-range or non-numeric `interval` is `400 bad_request`. The presets below
are fixed values, so the frontend never needs to validate.

## How far the daemon can actually reach

amuled keeps `nHistRanges = 7` ranges of `GetPointsPerRange() = 1800` records
(`src/Statistics.cpp:246`, `src/Statistics.h:534`), each range at twice the
spacing of the one before, recorded at 1 Hz:

| Range | Record spacing | Span | Cumulative reach |
|---|---|---|---|
| 0 | 1 s | 30 min | 30 min |
| 1 | 2 s | 1 h | 1.5 h |
| 2 | 4 s | 2 h | 3.5 h |
| 3 | 8 s | 4 h | 7.5 h |
| 4 | 16 s | 8 h | 15.5 h |
| 5 | 32 s | 16 h | 31.5 h |
| 6 | 64 s | 32 h | 63.5 h |

So roughly **63.5 hours are retained**, of which only the newest 30 minutes are
at 1 s resolution — which is exactly the window the UI shows today. Everything
older than half an hour is already on disk and simply never asked for.

Measured against a live daemon (uptime ~23 min at the time):

```
interval=1    points=1404   max_points=1800
interval=12   points=118    max_points=1800
interval=288  points=6      max_points=1800
```

A daemon younger than the requested window returns fewer points rather than an
error, and the chart draws what arrives. No special handling is needed.

### Record repeats

Asking for points closer together than the records in the range being read
makes amuled hand back the same record repeatedly, which the caller cannot
detect (no timestamps on the wire). The rule is simply
**`interval` ≥ the record spacing at the far edge of the window**. Every preset
proposed below satisfies it by a wide margin, and `max_points` truncation
remains the backstop. Keep the property in mind if the preset list changes.

## Requested change

### A. One shared time-range selector

A `<select>` offering fixed presets. `interval` is derived from the preset and
the existing `GRAPH_WIDTH = 300`:

| Preset | `interval` | Window (300 samples) | Deepest range touched |
|---|---|---|---|
| 5 minutes (default) | `1` | 5 min | 0 (1 s) |
| 1 hour | `12` | 1 h | 1 (2 s) |
| 6 hours | `72` | 6 h | 3 (8 s) |
| 24 hours | `288` | 24 h | 5 (32 s) |

Stop at 24 h. The retained history caps a 300-sample window at
`228600 / 300 = 762 s` of interval (~63 h), and a preset near that ceiling would
show mostly empty axis on any daemon that has not been up for three days.

**The selector must be global, not per chart.** `m_stats_graphs_cache`
(`src/webapi/Api.cpp:6186`) is a single unkeyed entry: one EC round trip serves
all four graph names, and an entry fetched at a different interval counts as a
miss. Three charts on one interval cost one EC round trip per TTL — the burst is
single-flighted through the cache mutex, so the second and third requests read
the value the first stored. Three charts on three intervals would evict each
other on every tick and cost three round trips instead.

The Statistics view and the Networks/Kad tab are separate hash routes and only
one is mounted at a time (`src/webapi/static/js/app.js:369-390`), so they cannot
thrash each other. They should still read the **same** persisted preference, so
switching tabs does not silently switch the range back to 5 minutes.

### B. The poll cadence has to follow the interval

`GRAPH_POLL_MS` is a fixed 2000 ms. At `interval=288` a new sample appears every
288 s, so polling every 2 s is 144× redundant — and it is a full refetch of the
window each time, not an incremental one.

Scale it with the interval and cap it so the chart still feels live, e.g.:

```js
const pollMs = Math.min(30000, Math.max(2000, interval * 1000));
```

The stats tree poll (`TREE_EVERY = 3`) is counted in graph ticks. It must not
inherit the slowdown — at 24 h the tree would refresh every 90 s. Decouple it,
or recompute `TREE_EVERY` from `pollMs` so it keeps landing roughly every 6 s.

### C. The time axis needs the date at long ranges

`clockHM` (`src/webapi/static/js/charts.js:16`) formats hour:minute only. On a
24 h window the four x-axis labels can read `11:46 … 11:46` across two different
days, and the hover readout adding **seconds** (`clockHMS`) is noise when the
samples are 288 s apart.

Switch the formatter based on the span the chart is drawing:

- window ≤ ~2 h — today's behaviour (`HH:MM`, hover adds seconds)
- window > ~2 h — drop the seconds from the hover readout
- window crossing a day boundary — include day/month in the axis labels

The chart already knows the span: `xs[xs.length - 1] - xs[0]`. Prefer deriving
it there over threading the interval into `draw()`.

### D. Persistence

Store the choice with the existing helpers rather than inventing a mechanism:

```js
loadPref("stats.graphRange", 1)   // -> interval in seconds
savePref("stats.graphRange", interval)
```

`store.js:33-46` already guards every access, so a disabled or full
localStorage degrades to the fallback instead of throwing. This is a local view
preference like theme and language — it does **not** belong on the Preferences
page, which edits amuled's own settings over the API.

### E. Where the control goes

- **Statistics view** — the grid at `stats.js:106-119` has no toolbar; add a
  `.toolbar` row above it (the class already exists,
  `src/webapi/static/css/app.css:211` — `display:flex; gap:6px; align-items:center`).
- **Networks/Kad** — the panel already renders a `.toolbar` row
  (`networks.js:268-275`) with a `.spacer` before the connect button; the
  selector fits to the left of that spacer.

Use the established markup: `<select class="input input-sm">`, as in
`views/search.js:215` and the language picker at `app.js:242-253`.

### F. Clear stale data on change

`graphData` holds arrays fetched at the previous interval. Reset it when the
selection changes — in **both** views (`stats.js:47`, `networks.js:241`) —
otherwise the chart draws the old samples against the new time spacing for one
frame, a visibly wrong axis.

### G. Draw the daemon's session average, and delete the client-side SMA

Every graph response already carries the session figures. The average is one
division, per graph:

| Graph | Second series | Unit |
|---|---|---|
| `download_speed` | `session.download_bytes / session.duration_seconds` | bytes/s |
| `upload_speed` | `session.upload_bytes / session.duration_seconds` | bytes/s |
| `kad_nodes` | `session.kad_node_seconds / session.duration_seconds` | nodes |
| `connections` | none — the desktop draws none either (`src/StatisticsDlg.cpp:151-153`) | — |

It is **one value per response**, not one per point, so it is drawn as a flat
line across the window: `new Array(ys.length).fill(avg)` as the second series.
No change to `charts.js` is needed — it already takes `[xs, ...series]`, gives
every series after the first a thinner stroke and no fill, and puts each one in
the legend with `g.fmt()` applied to its last sample, which for a constant array
is the average itself.

**Guard: `duration_seconds === 0`.** Old daemons do not send
`EC_TAG_STATSGRAPH_SESSION_TIMESPAN` and the field is then `0`. Omit the series
entirely rather than dividing — the same "absent, not zero" rule the connections
graph already follows for `active_*`, and `charts.js:86` then hides the legend
because there is only one series left.

**Delete `sma()` (`stats.js:35-44`) and `SMA_WINDOW` (`:18`).** The connections
chart already stopped calling it; after this nothing does.

Two things worth stating plainly before someone re-adds it:

- **What is lost.** The desktop plots *three* lines — Current, Running average,
  Session average (`src/StatisticsDlg.cpp:145-150`, `src/KadDlg.cpp:107-109`) —
  and this drops the middle one. It is not a parity regression, because the
  web SMA was never that quantity: the desktop's running average is an
  `average_minutes`-wide `CPreciseRateCounter` (`CStatistics::ComputeAverages`),
  while `sma()` smooths whatever happens to be on screen. What goes away is a
  decorative approximation; what replaces it is an exact figure from the daemon.
  If the real running average is ever wanted, it needs a new EC-side series, not
  a client-side filter.
- **Flat, not a trend.** The desktop's session-average line moves: it is
  `kValueRun / phr->sTimestamp` evaluated *at each point*. The REST response
  carries the totals only as of the newest point, so reproducing the trend means
  integrating the per-point rates backwards to reconstruct the cumulative series
  — which is exactly what amulegui does (`src/amule-remote-gui.cpp:4228-4300`),
  including the documented trap that integrating from the wrong end puts a few
  percent of error over a divisor of a few seconds and flips the line's sign
  near the session start. Out of scope. A flat reference line answers the same
  question ("is the current rate above or below the session so far?") with no
  error term.

Two consequences to accept:

- **Shared y scale.** `draw()` scales the axis to the maximum across all series
  (`charts.js:123`), so a mostly-idle 24 h window with a high session average
  will squash the current line. That is the same behaviour as the desktop's
  shared axis and is the point of drawing them together.
- **Independent of the range selector.** The session figures do not depend on
  `interval`; the flat line is identical at 5 minutes and at 24 hours. Sections
  A–F and G–H do not interact.

### H. The Kad chart gets the same treatment

`KAD_GRAPH` (`networks.js:25-26`) has one series today and therefore no legend.
Adding the session average makes it two, so the card gains a legend row and the
first series needs a proper label: it currently reuses `networks_kad_nodes`,
which is also the card title — as a legend entry it should be
`common_legend_current`, matching the other charts and the desktop.

Check the layout: `.chart-bare` is `padding: 0`
(`src/webapi/static/css/app.css:535`) and `.net-split .chart-bare` is
`flex: 1 1 auto; min-height: 0` (`:644`). The legend is a sibling block below
the canvas host, so it claims its own row inside a flex item that was sized for
a canvas only — verify the Kad pane does not clip it at small heights.

## Deliberate non-changes

- **`?max_client_versions` stays unexposed.** The other parameter #981 added is
  not worth a control. Measured on a live node: the full tree is **9,539 bytes /
  75 nodes / 3 version rows**, and `?max_client_versions=10` returns a
  byte-identical body. On a long-lived node it would be hundreds of rows, but
  they sit under a collapsed container the user never opens, and "how many
  client version rows do you want?" is a preference nobody will ever touch. If
  the 6-second tree poll ever becomes a bandwidth problem, send a fixed cap from
  the frontend — one query parameter, no UI.
- **`max_points` is read by nobody, and that is correct here.** Its use would be
  deriving the deepest offerable range at runtime; the presets are fixed and
  stop at 24 h, well inside what every daemon retains, and the server truncates
  to `max_points` regardless. It becomes relevant only if the preset list is
  ever computed instead of written down.
- **`interval_seconds` is not verified against what was requested.** The presets
  are always in range, so the echo can only ever match. The axis is built from
  each point's own `t_unix`, not from this field, so it would be correct even if
  they diverged.
- **`session.download_bytes` / `upload_bytes` stay unused as totals.** After G
  they are read only as the numerator of the average. The same totals already
  appear in the tree (`upload_data` / `download_data`, session figure primary,
  all-time in `extra`), and duplicating them in the chart card buys nothing.
- **`GRAPH_WIDTH` stays 300.** It is the sample count, roughly the chart's pixel
  width. The range selector changes `interval`, not `width`; raising `width`
  would draw more samples than there are pixels.
- **No server change.** `interval` is validated, clamped and cached server-side
  already, `max_points` is reported, the `session` object is complete, and the
  reconstructed timestamps are spaced by the interval actually applied.

## Implementation checklist

**Web UI (`src/webapi/static`) — range selector (A–F)**
- [ ] `js/views/stats.js` — read the persisted interval, append `&interval=N`
      in `loadGraph`, derive the poll cadence from it, keep the tree poll near
      6 s, reset `graphData` on change, and render the selector in a new
      toolbar row above the grid.
- [ ] `js/views/networks.js` — same persisted interval on the Kad chart, same
      poll derivation, reset `graphData` on change, selector in the existing
      panel toolbar.
- [ ] A shared helper for the preset list and the load/save pair, so the two
      views cannot drift. Keep it small — a `RANGES` array plus two functions.
- [ ] `js/charts.js` — pick the axis and hover formatters from the span the
      data covers, adding day/month when the window crosses a day.

**Web UI — session average (G–H)**
- [ ] `js/views/stats.js` — build the flat average series for `download_speed`
      and `upload_speed` from `r.session`, omit it when `duration_seconds` is
      `0`, and relabel the second entry of each `series` descriptor.
- [ ] `js/views/stats.js` — delete `sma()` and `SMA_WINDOW`.
- [ ] `js/views/networks.js` — same average series on the Kad chart from
      `kad_node_seconds`, and relabel `KAD_GRAPH.series[0]` to
      `common_legend_current`.
- [ ] `css/app.css` — only if the Kad pane clips its new legend row.

**i18n**
- [ ] `static/i18n/en.json` + `es.json` — add the keys below, drop the now-unused
      `common_legend_running_avg`, verified with
      `node src/webapi/tools/check-i18n.mjs`.

**Docs**
- [ ] `docs/api/REFERENCE.md:2252` — no API change, but the `interval` row can
      gain a one-line note that the bundled UI exposes it as a range selector.

**Tests**
- [ ] `unittests/curl-tests/amuleapi/07-read-stats-and-search-results.sh`
      already covers `?interval=`, its `400`s, and the presence of the four
      `session` fields. Add an assertion that two consecutive `t_unix` values
      differ by exactly the requested interval for a preset other than 1.

## i18n keys

Following the existing `common_legend_` / `stats_` prefixes:

```
common_legend_session_avg   "Session average"      "Media de la sesión"
stats_graph_range           "Time range"           "Rango temporal"
stats_graph_range_5m        "5 minutes"            "5 minutos"
stats_graph_range_1h        "1 hour"               "1 hora"
stats_graph_range_6h        "6 hours"              "6 horas"
stats_graph_range_24h       "24 hours"             "24 horas"
```

Removed: `common_legend_running_avg` (both dictionaries) — its only two call
sites go away with `sma()`.

`"Session average"` and `"Current"` are the desktop's own strings
(`wxTRANSLATE` at `src/StatisticsDlg.cpp:145-147`), so the wx catalogs already
carry translations to copy from rather than invent.

## Acceptance criteria

**Range selector**
- [ ] Selecting "1 hour" makes every chart in the Statistics view request
      `?interval=12`, and consecutive `t_unix` values in the response differ
      by 12.
- [ ] With three charts on the same interval, one tick costs **one** EC round
      trip — the cache is not evicted between them.
- [ ] The selection survives a reload and is the same on the Statistics view
      and the Networks/Kad chart.
- [ ] At "24 hours" the poll cadence is at most one request per chart every
      30 s, and the stats tree still refreshes roughly every 6 s.
- [ ] At "24 hours" the x-axis labels are unambiguous across the day boundary,
      and the hover readout no longer shows seconds.
- [ ] Against a daemon whose uptime is shorter than the selected range, the
      chart draws the points that exist and does not error.
- [ ] Changing the selection never draws the previous interval's samples on the
      new axis, in either view.

**Session average**
- [ ] `download_speed` and `upload_speed` each draw a flat second line whose
      legend value equals `session.download_bytes / session.duration_seconds`
      (resp. `upload_bytes`) from the same response, formatted as a speed.
- [ ] The Kad chart draws a flat second line at
      `session.kad_node_seconds / session.duration_seconds` and shows a legend
      with *Current* and *Session average*.
- [ ] The connections chart still draws exactly its three daemon series and no
      average.
- [ ] Against a daemon reporting `duration_seconds: 0`, every chart falls back
      to a single line with no legend and no `NaN`/`Infinity` reaches the
      canvas.
- [ ] `sma`, `SMA_WINDOW` and `common_legend_running_avg` appear nowhere in
      `src/webapi/static`.
- [ ] The line values match the desktop's *Session average* for the same
      instant, within the 1 KiB truncation amuled applies to the byte counters.

**Both**
- [ ] `node src/webapi/tools/check-i18n.mjs` is clean, and no new string is
      hardcoded in English.

## Out of scope

- Exposing `max_client_versions` in the UI (see *Deliberate non-changes*).
- A free-text interval input. The presets cover the useful range; an arbitrary
  value invites the `400` path and the record-repeat rule for no benefit.
- Reconstructing the per-point session-average **trend** the desktop draws. It
  needs the cumulative totals integrated backwards from the newest point, with
  the error-direction handling at `src/amule-remote-gui.cpp:4240-4300`; a flat
  reference line is what this issue asks for.
- Restoring a running-average line. Doing it properly means a new series from
  amuled, not a client-side filter over the visible window.
- Incremental graph fetching via `EC_TAG_STATSGRAPH_LAST`. The endpoint refetches
  the whole window by design; making it incremental is separate work and is
  already listed as out of scope in #981.
- Any change to `GRAPH_WIDTH`, to the chart renderer's series handling, or to
  the desktop client's own graph scale.
