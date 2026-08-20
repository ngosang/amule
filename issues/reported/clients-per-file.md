# Clients of a file: per-file routes (`/downloads/{hash}/clients`, `/shared/{hash}/clients`), the per-source part bar, and A4AF rows

## Summary

The desktop GUI has two per-file peer panels and `/api/v0` has no route for
either of them:

- **Downloads → bottom panel “File sources”** (`src/SourceListCtrl.cpp:36-47`):
  every source of the selected partfile, including the **A4AF** rows (sources
  parked on another file), each with a per-part bar showing *which chunks that
  peer has*.
- **Shared files → bottom panel “Peers”** (`src/SharedFilePeersListCtrl.cpp:29-40`):
  every peer transferring, or queued, for the selected shared file.

`amuleapi` exposes only a global peer list, `GET /api/v0/clients`. There is no
“clients of this file” resource, so a client has to pull the **whole** peer list
and cross-reference `download_file_hash` / `upload_file_hash` itself — which is
exactly what the bundled Web UI does today
(`src/webapi/static/js/views/client-table.js:172-186`), with the consequences
that comment already admits: A4AF and other non-transferring sources “never show
up here”.

Three things are missing, and **none of them needs a core change or an EC
protocol change** — every tag involved is already defined and already on the
wire at the detail level `amuleapi` already subscribes to
(`EC_DETAIL_INC_UPDATE`, `src/webapi/RefresherTick.cpp:102`):

1. **No per-file client route.** Rendering one file’s panel costs the
   entire `/clients` payload — every upload-queue waiter on the node — and the
   join has to be re-done in every client.
2. **The per-source part bar does not exist in the API.** The core sends
   `EC_TAG_CLIENT_PART_STATUS` (the peer’s chunk bitmap for the file we pull
   from it), `EC_TAG_CLIENT_UPLOAD_PART_STATUS`,
   `EC_TAG_CLIENT_NEXT_REQUESTED_PART` and
   `EC_TAG_CLIENT_LAST_DOWNLOADING_PART` (`src/ECSpecialCoreTags.cpp:458-483`).
   `src/webapi/Refresher.cpp` decodes **none** of the four. All the API offers is
   the scalar count `available_parts` plus a `part_progress_percent` that is
   computed **only** on the single-peer detail endpoint
   (`src/webapi/Api.cpp:4534-4548`).
3. **A4AF sources cannot be listed.** `GET /downloads/{hash}/a4af` returns bare
   ECIDs (`src/webapi/Api.cpp:3289-3301`) and an A4AF peer has neither
   `download_file_hash` nor `upload_file_hash` pointing at this file, so no
   client-side join can produce those rows.

Plus a fourth, smaller one found while mapping the columns: **four fields the
panels need are detail-only.** `WriteClientObject` emits only
`WriteClientBaseFields`, so the list object — and the SSE `client_added` /
`client_updated` payload built from the same field set
(`src/webapi/EventDiff.cpp:183-210`) — has no `source_origin`,
`view_shared_disabled`, `available_parts` or `mod_version`. Those live in
`WriteClientDetailObject` only (`src/webapi/Api.cpp:2409-2456`), which means the
desktop’s **Origin** and **Shares File List** columns are unrenderable from a
list read.

`/api/v0/` is experimental with no external consumers, so field additions and
shape changes land in place rather than waiting for a `v1`.

## Parity target: the desktop columns

### Downloads → “File sources” (`src/SourceListCtrl.cpp:36-47`)

| Desktop column | API field today | Status |
|---|---|---|
| User Name | `client_name` | ok |
| Downloaded | `xfer.down_total` | ok |
| Speed | `download_speed_bps` | ok |
| Uploaded | `xfer.up_total` | ok |
| **Available Parts** (per-part bar) | `available_parts` (a count) | **missing** — no bitmap |
| Version | `software` + `software_version` | ok |
| Download Status | `download_state`, `remote_queue_rank` | ok |
| **Origin** | `source_origin` | **detail-only** |
| Local File Name | — (resolve `download_file_hash`) | ok, see note |
| Remote File Name | `download_file_name` | ok |
| **Shares File List** | `view_shared_disabled` | **detail-only** |
| **A4AF rows** | — | **missing** |

The bar is not decoration: it is the only place a user sees *why* a source is
useless (it has only chunks we already hold). The desktop renders five states
per part — peer lacks it / peer has it and we need it / peer has it and we have
it / currently downloading / next requested — in `CSourceBarRenderer`
(`src/SourceListCtrl.cpp:50-80`), and swaps the whole cell for an
`A4AF: <filename>` badge on an A4AF row.

Note on the two name columns, which are easy to mix up
(`src/GenericClientListCtrl.cpp:751-768`): **Local File Name** is the
*partfile's own* name (`GetRequestFile()->GetFileName()`), which the API only
exposes indirectly — resolve `download_file_hash` against the downloads list; on
a per-file route it is the file being viewed, so it costs nothing there.
**Remote File Name** is the name the peer advertises
(`EC_TAG_CLIENT_REMOTE_FILENAME` → `download_file_name`), and the desktop
deliberately blanks it to `[Unknown]` on an A4AF row — the advertised name
belongs to the other file. A client rendering A4AF rows should do the same.

### Shared files → “Peers” (`src/SharedFilePeersListCtrl.cpp:29-40`)

Same set from the upload side: User Name, Downloaded, Download Speed, Uploaded,
Upload Speed, **Available Parts**, Version, Upload Status, Download Status,
**Origin**, Local File Name, **Shares File List**. `upload_speed_bps`,
`queue_waiting_position` and `upload_state` are already on the list object; the
three bold ones have the same gaps as above.

The bar differs between the two panels, and the API has to carry both inputs:
Sources draws the five-state bar from the peer's `part_status`
(`CSourceBarRenderer`), Peers draws a plain **two-state** bar from
`GetUpPartCount()` / `IsUpPartAvailable()` — i.e.
`EC_TAG_CLIENT_UPLOAD_PART_STATUS` — with no A4AF branch
(`src/GenericClientListCtrl.cpp:919-940`, and the renderer note at
`src/GenericClientListCtrl.h:241-245`).

## Proposed implementation

### 1. Decode the four part tags in the refresher

`src/webapi/Refresher.cpp` (client decoder, around `:930-945` where
`EC_TAG_CLIENT_AVAILABLE_PARTS` is already read), storing into
`webapi::ClientSnapshot` (`src/webapi/State.h:380-387`):

| New field | Source tag | Notes |
|---|---|---|
| `part_status` (`std::vector<bool>`) | `EC_TAG_CLIENT_PART_STATUS` | chunks the peer has of the file **we download from it** |
| `upload_part_status` | `EC_TAG_CLIENT_UPLOAD_PART_STATUS` | chunks the peer has of the file **it downloads from us** |
| `next_requested_part` | `EC_TAG_CLIENT_NEXT_REQUESTED_PART` | index, or absent |
| `last_downloading_part` | `EC_TAG_CLIENT_LAST_DOWNLOADING_PART` | index, or absent |

Wire details that will bite if missed:

- **An empty `PART_STATUS` tag means “full source”**, not “no data”
  (`src/ECSpecialCoreTags.cpp:461-464`; the GUI’s counterpart is
  `src/amule-remote-gui.cpp:2823-2831`). Length 0 → all bits true.
- The payload is a raw `BitVector` buffer: bit `i` is
  `buffer[i / 8] & (1 << (i & 7))` — **LSB-first inside each byte**
  (`src/BitVector.h:52-60`, `src/OtherFunctions.cpp:1684`).
- The core only sends the tag when `partStatus.size() == pfile->GetPartCount()`,
  so a decoded bitmap whose length disagrees with the file’s part count must be
  dropped, not padded.
- These are *tagmap* fields: absent means unchanged, not zero — same convention
  the rest of the decoder already follows.

### 2. Two new routes, one sub-resource name

```
GET /api/v0/downloads/{hash}/clients
GET /api/v0/shared/{hash}/clients
```

**Same name on both sides, deliberately.** Both return the same object (the
`/clients` list row) out of the same cache (`m_clients`), selected by hash;
the relation to the file is a **field**, not a path. Calling one `sources` and
the other `peers` would also make the path lie: a partfile in download almost
always has peers pulling completed chunks *from* us, so a `…/sources` route
would be full of rows that are not sources. The existing comment at
`src/webapi/State.h:259` already shows the confusion — it describes filtering by
`upload_file_hash` (the upload direction) under the name *sources*.

It also matches how the state is actually keyed: a downloading partfile with
≥1 completed chunk is in **both** collections at once (`is_downloading` and
`is_shared`, `src/webapi/State.h:53-65`), so for such a hash both routes exist
and, by design here, **return the same body**. They differ only in the 404 check
— `is_downloading` vs `is_shared` — which is what makes each a legitimate
sub-resource of its collection. One handler, parameterized by which flag it
requires; the desktop's split panels are two client-side filters over one
response, not two server shapes.

Both authenticated like `/clients` (read access, not ADMIN), both `GET`/`HEAD`
only, both list-shaped: the usual envelope plus `snapshot_at`, and the shared
`ListParams` handling so `limit` / `offset` / `sort` / `order` work as on
`/clients` (`src/webapi/Api.cpp:3021-3034`). `404` when the hash is not a
download / not a shared file.

Both patterns must be matched **before** the bare `/downloads/{hash}`
(`src/webapi/Api.cpp:1203`) and `/shared/{hash}` (`:979`) patterns in
`CApiDispatcher::DispatchToHandler`, which accept any single segment — the same
ordering the existing `/downloads/{hash}/filenames`, `/downloads/{hash}/a4af` and
`/shared/{hash}/verify` blocks already rely on.

Not to be confused with the existing `GET /downloads/{hash}/filenames`
(`src/webapi/Api.cpp:1166`, handler `:3243-3283`), which returns *aggregate*
`{name, count}` pairs across sources, not one row per source. It stays as it is.

Each entry is the **client list object** (so a client reuses one row renderer
everywhere) plus:

| Extra key | Meaning |
|---|---|
| `role` | live transfer relation **with this file**: `"source"` (serves it to us, including queued), `"peer"` (pulls it from us), `"both"`, `"none"` |
| `a4af` | `true` on a source parked on another file — the desktop’s A4AF row |
| `part_progress_percent` | already-defined field, now computed here too |
| `parts` | the peer’s bitmap — **only** when `?include_parts=true` |

`role` and `a4af` are separate because they are orthogonal: a pure A4AF row is
`role: "none"`, `a4af: true`, but the same peer can be parked on another file
*and* be downloading this one from us (`role: "peer"`, `a4af: true`). Collapsing
A4AF into a fourth `role` value would make that row unrepresentable.

No `?role=` filter for now: the caller already has the rows in hand and a
one-line filter is cheaper than a server-side parameter. Add it if a client
reports needing it.

`parts` is opt-in and off by default for the same reason the downloads *list*
omits the file's own part array while `GET /downloads/{hash}` always includes it
(`src/webapi/Api.cpp:3089-3097`): a multi-TiB file is 100K+ entries — here, per
peer, times every source. Keep the bitmaps out of the SSE payload entirely.

Shape for `parts`: the compact form, an array of booleans (or a `"0110…"`
string) of exactly `part_count` entries, **not** a per-part object. The file’s
own five-state view is already available from `GET /downloads/{hash}` (its
`progress.parts[]` carries `state` + `sources`,
`src/webapi/Api.cpp:2051-2088`), so a client draws the desktop’s five states by
combining that array with this peer’s bitmap and the two part indices. Duplicating
the file-side state per source would multiply the payload for information the
client already holds.

Which bitmap a row carries follows its `role`: `part_status` for a source (the
file we pull from the peer), `upload_part_status` for a peer (the file it pulls
from us). A `role: "both"` row has both, and the route serving a hash that is
both a download and a shared file must not mix them up — the two tags describe
different files whenever the peer is downloading one file from us and serving us
another.

**`GET /downloads/{hash}/a4af` should be retired at the same time.** Once
these rows carry an `a4af` flag, its only other payload — `a4af_auto` — is
already on the download detail object (`src/webapi/Api.cpp:2220-2221`), so the
GET adds nothing but a second read surface for the same data. Keep the `POST` on
that path: the swap actions (`swap_this`, `swap_this_auto`, `swap_others`) have
no replacement here, and this issue is read-only otherwise. Its reply body keeps
using `WriteA4afObject`, so retiring the `GET` does not delete the serializer —
and it stays the "did it work?" signal for the per-source swap proposed in
[client-swap-to-another-file.md](client-swap-to-another-file.md).

`a4af` rows come from `f.download.a4af_sources`
(`src/webapi/State.h:196-197`) — already decoded, currently only reachable as
bare ECIDs through `/downloads/{hash}/a4af`. Resolve each ECID against the
client snapshot and emit it as a normal row with `a4af: true`; an ECID that no
longer resolves is skipped. They exist only on the download side: the A4AF
relation is stored in the download sub-block, so `/shared/{hash}/clients` on a
completed file never produces one.

### 3. Promote the four detail-only fields to the list object

Move `source_origin`, `available_parts`, `view_shared_disabled` and
`mod_version` from `WriteClientDetailObject` into `WriteClientBaseFields`
(base: `src/webapi/Api.cpp:2230-2298`, detail: `:2409-2456`), and compute `part_progress_percent` for list
rows too — the calculation at `src/webapi/Api.cpp:4537-4548` should move into a
helper both paths call, instead of living inside `HandleClientDetail`.

**Do not forget `EventDiff`.** Every promoted field must be added to *both*
`ToJson(const ClientSnapshot &)` (`src/webapi/EventDiff.cpp:183-210`) **and**
`Equal(const ClientSnapshot &, …)` (`:315-330`). A field added to `ToJson` but
not to `Equal` is silently frozen after the first frame: the differ decides
nothing changed and never emits `client_updated`.

### 4. Web UI

Web UI work lives entirely under `src/webapi/static/` and commits carry
`web-ui` in the title (`feat(web-ui): …`).

- `views/client-table.js`: drop the client-side hash join in `FileClients`
  (`:172-186`) and read `…/{hash}/clients` instead; add the three missing columns —
  **Available Parts** (a per-part bar component, matching the five desktop
  states, gated to a plain `n / total` text when the bar is off), **Origin**
  (`source_origin`), **Shares File List** (`view_shared_disabled`).
- Render A4AF rows visibly distinct (the desktop shows `A4AF: <filename>` in
  the bar cell) so a user can tell a parked source from a dead one.
- `views/download-detail.js` (`:98-106`) and `views/shared-detail.js`
  (`:76-84`): keep the existing “Clients” tab, now fed by the per-file route;
  request `include_parts=true` only while that tab is open.
- New i18n keys in every `static/i18n/*.json`.

### 5. Housekeeping

The comment at `src/webapi/State.h:255-260` names a `/downloads/{hash}/sources`
route that never existed and describes it filtering by `upload_file_hash` (the
upload direction). Update it to the two `…/clients` routes while touching this
code.

## Acceptance criteria

- [ ] `GET /downloads/{hash}/clients` lists transferring sources **and** A4AF
      sources for that partfile, with `role` and `a4af` set, and returns `404`
      for an unknown hash — or for a hash that is shared but not downloading.
- [ ] `GET /shared/{hash}/clients` lists uploading and queued peers for a shared
      file, `404` for an unknown hash — or for a partfile with no completed
      chunk (`is_shared` false).
- [ ] For a partfile that is both downloading and shared, the two routes return
      the same body, and every row's `role` says which direction it is.
- [ ] Both accept `limit` / `offset` / `sort` / `order` with the same semantics
      as `/clients`.
- [ ] `?include_parts=true` returns a bitmap of exactly `part_count` entries per
      peer; omitting it returns no `parts` key at all.
- [ ] A peer the core reports as a full source (empty `PART_STATUS` tag) comes
      back as all-true, not as an empty or absent bitmap.
- [ ] `source_origin`, `available_parts`, `view_shared_disabled`, `mod_version`
      and `part_progress_percent` are present on `GET /clients` rows and on the
      `client_added` / `client_updated` SSE payloads, and a change to any of them
      alone triggers a `client_updated` event.
- [ ] No `parts` array in any SSE payload.
- [ ] The Downloads and Shared Files detail panels render every desktop column
      from the tables above, including the per-part bar and A4AF rows, and no
      longer fetch the global `/clients` list to build the per-file table.
- [ ] `GET /downloads/{hash}/a4af` is gone (or, if kept, documented as
      redundant); its `POST` still works unchanged.
- [ ] `docs/` API reference updated for the two routes, the promoted fields and
      the retired route.

## Out of scope

- Any change to the EC protocol or to `src/` outside `src/webapi/` — everything
  above reads tags the core already sends.
- `amuleweb` (deprecated).
- Per-source actions (ban, add-to-friends, swap A4AF for one specific source);
  this issue is the read surface only.
