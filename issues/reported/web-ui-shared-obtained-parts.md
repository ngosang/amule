# Web UI: add the "Obtained Parts" availability bar to shared files

## Summary

The Shared Files table in the desktop GUI has 14 columns
(`CSharedFilesCtrl::CSharedFilesCtrl`, `src/SharedFilesCtrl.cpp:104-120`). The
Web UI and the `/api/v0` shared endpoints behind it cover 13 of them. The one
gap is **Obtained Parts** — the per-part availability bar
(`src/SharedFilesCtrl.cpp:112`).

`GET /api/v0/shared/{hash}` already reports `part_count` (how many ~9.28 MB
parts the file has), but nothing reports the state of each part, so the Web UI
has no way to draw the bar. The equivalent bar for downloads
(`progress.parts` on `GET /api/v0/downloads/{hash}`) is already implemented and
rendered.

The underlying data is already on the wire between `amuled` and `amuleapi`. It
is decoded for partfiles and silently dropped for complete shared files. This
issue is about finishing that path and rendering it.

`/api/v0` is experimental and has no external consumers, so breaking changes
would be acceptable; none are needed here — the change is purely additive.

## What the desktop shows

`CSharedFilesCtrl::GetItemBarFill` (`src/SharedFilesCtrl.cpp:450-500`) fills
the column:

- While the file is being hashed (`GetHashingProgress() > 0`): a two-tone bar —
  hashed prefix green, pending remainder yellow.
- Otherwise: one span per part, coloured **purely by how many sources have that
  part** — `m_SrcpartFrequency` for partfiles, `m_AvailPartFrequency` for
  complete known files. Zero sources → red; one or more → blue, darkening as
  the source count rises (`210 - 22 * (count - 1)`, clamped at 0).

Note the semantics: unlike the Downloads bar, this bar is **not** about local
completeness. A complete shared file is 100 % local by definition; what the
column shows is how well each part is replicated across the network — i.e.
which parts of your share nobody else has (red = you are the only source).
Parity means an availability bar, not a progress bar.

## Where the data already is

| Layer | State |
|---|---|
| `amuled` → EC, complete shared files | **Present.** `CKnownFile_Encoder::Encode` (`src/ExternalConn.cpp:3366-3385`) RLE-encodes the availability vector into `EC_TAG_PARTFILE_PART_STATUS` on every `EC_TAG_KNOWNFILE` tag, on both the `EC_OP_GET_SHARED_FILES` path (`ExternalConn.cpp:1805-1822`) and the `EC_OP_GET_UPDATE` path amuleapi actually uses (`ExternalConn.cpp:2013-2017`). |
| `amuled` → EC, shared partfiles | **Present.** `CPartFile_Encoder::Encode` (`ExternalConn.cpp:3247`) calls the base encoder first, so `EC_TAG_PARTFILE` carries the same tag. |
| `amuleapi` refresher, partfiles | **Decoded.** `DecodeRleBlobsForPartFile` (`src/webapi/Refresher.cpp:1064-1087`) fills `FileSnapshot::download::decoded_part_sources` (`src/webapi/State.h:200-208`). |
| `amuleapi` refresher, complete shared files | **Dropped.** `ApplyGetUpdateToShared` (`src/webapi/Refresher.cpp:1162`) never looks at `EC_TAG_PARTFILE_PART_STATUS` on the `EC_TAG_KNOWNFILE` tags it walks. |
| `/api/v0` shared JSON | **Missing.** `WriteSharedDetailObject` (`src/webapi/Api.cpp:2525-2562`) emits `part_count` only. |
| Web UI | **Missing.** `src/webapi/static/js/views/shared-detail.js:122` prints the part count as a number; the header comment of that file records the absence explicitly. |

So for a **shared partfile** the availability vector is already in the snapshot
(the downloads walker decoded it into `download.decoded_part_sources`). For a
**complete shared file** — the overwhelming majority of a typical share — it
arrives on every tick and is thrown away.

## Proposed change

### 1. Daemon side (`src/webapi/`)

**a. Store the vector on the shared side of the snapshot.**
Add to `FileSnapshot::SharedSide` in `src/webapi/State.h:212`:

```cpp
// Per-part source availability for the shared "Obtained Parts" bar,
// decoded from EC_TAG_PARTFILE_PART_STATUS on the EC_TAG_KNOWNFILE
// tag. Sized to ceil(size / PARTSIZE) once a decode has landed.
std::vector<std::uint16_t> decoded_part_sources;
```

For a file that is also downloading, prefer the already-decoded
`download.decoded_part_sources` when this one is empty — both come from the
same server-side encoder, so there is no reason to decode twice.

Clear it in `ClearSharedRoleKeepPriority` (`Refresher.cpp:1094`) like the rest
of the shared session state.

**b. Decode it in the shared walker.**
`ApplyGetUpdateToShared` needs its own stateful decoder map, mirroring
`m_partfile_rle` (`src/webapi/App.h:181`, accessor at `App.h:126`) and its
plumbing in `RefresherTick.cpp:100-137`:

- `RLE_Data` diffs are **XOR deltas against the previously decoded buffer** (see
  the warning on `RLE_Data::ResetDecoder`, `src/RLE.h:105-112`). A decoder that
  skips packets desyncs permanently and paints garbage, so the state must be
  created and fed from the first `EC_TAG_KNOWNFILE` tag onwards — never lazily
  on first UI request.
- Evict the entry on `EC_TAG_FILE_REMOVED` and on the shared-role-off
  transition, exactly as the downloads walker does
  (`Refresher.cpp:1129-1135`, `RefresherTick.cpp:120-128`).
- Reset it on reconnect, wherever `m_partfile_rle` is already reset.
- **Edge case worth an explicit test:** when a partfile completes, `amuled`
  destroys its `CPartFile_Encoder` and builds a fresh `CKnownFile_Encoder` for
  the same ECID (`CFileEncoderMap::UpdateEncoders`,
  `ExternalConn.cpp:310-386`). The daemon's diff baseline restarts empty, so
  amuleapi must reset its decoder state for that ECID at the same moment — i.e.
  when the tag kind for an ECID flips from `EC_TAG_PARTFILE` to
  `EC_TAG_KNOWNFILE`. Without this, the first post-completion bar is garbage.

**c. Emit it on the detail endpoint.**
`WriteSharedDetailObject` gains, next to `part_count`:

```json
"parts": [ { "sources": 4 }, { "sources": 0 }, { "sources": 12 } ]
```

- One entry per part, in file order; `parts.length == part_count`.
- Omit the key entirely when no decode has landed yet (the UI then renders
  nothing, as it does today) rather than emitting an all-zero array — "no data
  yet" and "no sources for any part" must stay distinguishable.
- `sources` is the raw `uint16` source count — not a colour, not a percentage.
  Colour mapping is the client's job.
- Do **not** copy the Downloads shape (`{state, sources}`,
  `WriteProgressParts`, `Api.cpp:2051-2088`): its `state` encodes local
  completeness, which is meaningless for a share and would invite a wrong
  renderer.

Keep this **detail-only**. `GET /api/v0/shared` (the list) and the
`shared_updated` SSE payload (`ToJsonSharedEvent`,
`src/webapi/EventDiff.cpp:146-163`) must not carry it, for the same reason the
downloads list omits `progress.parts` (`Api.cpp:2963-2966`): a 100 GB file has
~10 800 parts, and multiplying that across a five-figure share on every SSE
tick is not viable. Consequently `EqualShared` (`EventDiff.cpp:292-305`) must
**not** be extended with the new field either — doing so would make every
source-count fluctuation emit a `shared_updated` event for every file.

**d. Hashing progress: out of scope, and here is why.**
The desktop's yellow/green hashing bar cannot be reproduced today:
`EC_TAG_PARTFILE_HASHED_PART_COUNT` is added only by the partfile tag
constructor (`src/ECSpecialCoreTags.cpp:236`), not by
`CEC_SharedFile_Tag`, so a complete known file being re-hashed exposes no
hashing progress over EC at all. Surfacing it would mean a new tag on the
shared tag constructor — a daemon change outside `src/webapi/` — and belongs in
its own issue. The availability bar is the substance of this one.

### 2. Web UI (`src/webapi/static/`)

**a. Make the bar reusable.** `PiecesBar` and `PiecesLegend` currently live
private inside `views/download-detail.js:350-437`. Move them to
`components.js` and add an availability mode. The canvas drawing, DPR handling,
resize/theme observers and CSS-var lookups are all reusable as-is; only the
per-part fill rule differs:

- Downloads mode (existing, unchanged): `complete` → `--ok`, `missing` →
  `--bad`, `incomplete` → `--piece-avail-lo` … `--piece-avail` faded by source
  count.
- Availability mode (new): `sources === 0` → `--bad`; otherwise
  `--piece-avail-lo` … `--piece-avail` faded by source count, reusing the same
  `AVAIL_FULL` normalisation (`download-detail.js:26`) so the two bars read
  consistently.

No new CSS variables are needed — `--ok`, `--bad`, `--piece-avail` and
`--piece-avail-lo` are already defined for light and dark themes in
`static/css/`.

**b. Render it in the shared detail panel.** In `views/shared-detail.js`, add
the bar plus a short legend to the sharing section (or as its own section next
to the identity block), fed by `s.parts`. Render nothing when `s.parts` is
absent. Keep the existing `shared_detail_parts` numeric row — the count is
still useful and the bar does not replace it.

**c. Keep it live.** The panel already re-fetches `GET shared/{hash}` on every
live tick of the shared store (`shared-detail.js:47-56`, ETag-cached), so the
bar re-draws from the new payload with no new polling.

**d. i18n.** Add the new keys to **both** `static/i18n/en.json` and
`static/i18n/es.json`:

- a label for the bar, matching the desktop wording ("Obtained Parts");
- legend labels for "available" / "no sources", and a tooltip explaining that
  the blue shade encodes the number of sources and that red parts are parts no
  other peer has.

Reuse the existing `downloads_detail_avail_*` strings where they already say
the right thing instead of duplicating them.

### Out of scope (and why)

A **per-row bar in the Shared table** is deliberately not part of this. It
would require `parts` in the list response and in every `shared_updated`
event — the payload blow-up described above. The Web UI's Downloads view takes
the same line: a percentage `ProgressBar` in the table
(`views/downloads.js:159-161`), the detailed chunk map in the detail panel
only. If a list column is wanted later it needs its own design (e.g. an opt-in
`?include=parts` with a low `limit` cap) and its own issue.

## Acceptance criteria

1. `GET /api/v0/shared/{hash}` returns a `parts` array of length `part_count`
   for a complete shared file, with plausible `sources` values that change as
   peers come and go.
2. The same holds for a shared partfile (a download with at least one complete
   chunk), where the values match `progress.parts[].sources` from
   `GET /api/v0/downloads/{hash}` for the same file.
3. `parts` is absent — not empty, not all-zero — before the first successful
   decode.
4. `GET /api/v0/shared` and the `shared_updated` SSE events are unchanged from
   before the patch, and the `shared_updated` event rate does not increase.
5. A file that completes while the shared detail panel is open on it shows a
   correct bar immediately afterwards (no garbage from a stale RLE baseline).
6. The panel draws the bar, with a legend, in both light and dark themes; it
   re-draws on theme switch and on resize.
7. Guest (non-admin) sessions see the bar too — read-only data, no new
   permission implications.

## Testing notes

- `curl -s localhost:4713/api/v0/shared/<hash> | jq '.part_count, (.parts|length), (.parts|map(.sources)|unique)'`
  on both a complete share and a shared partfile.
- Compare against the desktop GUI's Obtained Parts column for the same file:
  the red/blue pattern should match part for part.
- Force the completion transition: let a small download finish while the shared
  detail panel is open on it, and confirm the bar stays coherent.
- A share containing a large file (thousands of parts), to confirm the canvas
  renderer degrades into a continuous band rather than becoming slow.
