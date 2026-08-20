# Make the shared-files reload asynchronous: it freezes the GUI and stalls the amuleapi EC lane

## Summary

`CSharedFileList::Reload()` walks every configured share root synchronously on
the caller's thread. Two callers make that a user-visible defect:

1. **The GUI "Reload" button** (`CSharedFilesWnd::OnBtnReloadShared`) calls the
   no-callback overload, so the whole walk runs on the main thread without
   pumping events. The window is frozen — no repaint, no progress, no
   indication anything is happening — for as long as the scan takes. On a large
   tree, or shares on NFS/CIFS/sshfs/a spun-down disk, that is seconds to
   minutes, long enough for the window manager to grey the window out as "not
   responding".

2. **The EC opcode `EC_OP_SHAREDFILES_RELOAD`** runs the walk *inline in the EC
   request handler* and only sends its reply afterwards. Every EC client
   inherits the stall, and `amuleapi` — whose entire EC lane is a single
   serialised worker — degrades badly: the HTTP request hangs, the refresher
   loop stops ticking, other endpoints start returning `503 ec_unavailable`,
   and a long enough walk can make `amuleapi` deliberately terminate itself.
   The endpoint even answers `202 Accepted`, which promises exactly the
   asynchronous behaviour it does not implement.

The fix is two independent, small changes: give the GUI button the
progress-and-yield path that already exists, and make the EC handler *schedule*
the reload instead of performing it.

## Current state

| Piece | Location |
|---|---|
| The walk itself | `src/SharedFileList.cpp:1051` — `Reload(ReloadYieldCb)` |
| No-callback overload | `src/SharedFileList.cpp:1046` — `Reload()` → `Reload(nullptr)` |
| Re-entrancy guard | `src/SharedFileList.cpp:1057` — `reloading` flag |
| Directory walk + yield hook | `src/SharedFileList.cpp:383` `FindSharedFiles`, `:520` `AddFilesFromDirectory` (yields every 256 files) |
| GUI button handler | `src/SharedFilesWnd.cpp:263` — `OnBtnReloadShared` |
| Working progress+yield precedent | `src/PrefsUnifiedDlg.cpp:3084-3097` — `wxProgressDialog` + `reloadYield` lambda |
| EC handler (reload op) | `src/ExternalConn.cpp:3662` — `theApp->sharedfiles->Reload(); response = new CECPacket(EC_OP_NOOP);` |
| EC handler (set shared dirs, same defect) | `src/ExternalConn.cpp:1741` — inline `Reload()` before returning the response |
| Once-per-second core hook | `src/SharedFileList.cpp:1379` — `CSharedFileList::Process()`, called from `src/amule.cpp:1996` |
| amuleapi endpoint | `src/webapi/Api.cpp:7634` — `HandleSharedReload` → `SimpleConnControlOp(..., EC_OP_SHAREDFILES_RELOAD, 202)` |
| amuleapi EC lane | `src/webapi/EcService.h:73` — single worker, FIFO queue, `max_depth = 8`, full queue → `nullptr` → `503` |
| amuleapi self-exit on EC blackout | `src/webapi/App.cpp:539` + `:575` — `kEcFailExitAfter = 300` failed ticks (~5 min) |
| Other EC senders that inherit the stall | `src/TextClient.cpp:350` (amulecmd), `src/webserver/src/WebServer.cpp:445` (amuleweb), `src/amule-remote-gui.cpp:1985` (amulegui — fire-and-forget, so unaffected) |

### Why the walk is slow

Per file it is a `FileExists()`, a name-filter check, a `GetModificationTime()`
+ `GetFileSize()` stat pair, and an indexed `FindKnownFile()` lookup
(`AddPathToShares`, `src/SharedFileList.cpp:580`). Cheap per file, but it is
*per file over the whole share tree*, and each one is a filesystem round trip.
Hashing of newly discovered files is **not** part of the stall — those are
queued as `CHashingTask`s and run on `CThreadScheduler` afterwards
(`src/SharedFileList.cpp:444`).

### What breaks in amuleapi today, step by step

`POST /api/v0/shared/reload` → `HandleSharedReload` → `SendRecvSerialized` →
`CEcService` worker → amuled runs the full walk → reply. Meanwhile:

* The HTTP session thread is blocked in `Submit(...).get()`.
* The refresher tick (1/s) and every other EC-backed endpoint queue behind the
  in-flight roundtrip; once 8 are queued, further submissions get `nullptr`
  immediately → **`503 ec_unavailable` across the API**.
* SSE emission stops (it runs in the refresher loop), so client state freezes.
* `App.cpp:591`'s `WARN refresher tick took N ms` fires.
* Once ticks start failing on the full queue, the EC-blackout counter climbs:
  `WARN` at 30 consecutive failures, and at 300 (~5 min) `amuleapi` exits on
  purpose so a supervisor restarts the pair.

There is no timeout that bounds this. `EcService.h:62` says the wait is
"bounded by the EC read timeout", but nothing calls `SetTimeout` on the EC
socket, and TCP keepalive (`src/libs/ec/cpp/ECMuleSocket.cpp:60`, 30 s idle /
10 s / 3 probes) never fires because amuled is *alive and busy* — the kernel
keeps ACKing. The real bound is "however long the walk takes".

## Requested change

### Part A — GUI button: progress dialog + yield

Rewrite `CSharedFilesWnd::OnBtnReloadShared` (`src/SharedFilesWnd.cpp:263`) to
use the cancellable-progress overload that already exists, mirroring
`src/PrefsUnifiedDlg.cpp:3084-3097`:

```cpp
void CSharedFilesWnd::OnBtnReloadShared(wxCommandEvent &WXUNUSED(evt))
{
#ifndef CLIENT_GUI
    wxProgressDialog progress(_("Reloading shared files"),
        _("Scanning shared directories..."),
        100, this, wxPD_APP_MODAL | wxPD_AUTO_HIDE);
    auto reloadYield = [&progress](size_t filesScanned) -> bool {
        progress.Pulse(CFormat(_("Reloading shared files: %u files scanned"))
            % static_cast<unsigned>(filesScanned));
        return true;   // see "no cancel button" below
    };
    theApp->sharedfiles->Reload(reloadYield);
    progress.Update(100);
    SelectionUpdated();
#else
    // amulegui: CSharedFilesRem::Reload only posts EC_OP_SHAREDFILES_RELOAD
    // and returns, so there is nothing local to show progress for.
    theApp->sharedfiles->Reload();
#endif
}
```

Notes for the implementer:

* `Reload(std::function<bool(size_t)>)` compiles in **both** builds — the
  remote GUI already has a shim at `src/amule-remote-gui.h:600` that ignores
  the callback. The `#ifndef CLIENT_GUI` above is only to avoid a
  create-and-immediately-destroy dialog flash in amulegui.
* `_("Reloading shared files: %u files scanned")` is an **existing** msgid
  (`src/PrefsUnifiedDlg.cpp:3086`) — reuse it verbatim so no new translation is
  needed for the per-tick text.
* **No cancel button on purpose.** `FindSharedFiles` clears `m_Files_map` before
  it starts walking (`src/SharedFileList.cpp:398`), so an aborted walk leaves a
  partially populated share list with nothing to roll back to. The preferences
  dialog can offer cancel only because it re-runs the walk against the previous
  directory list on abort (`src/PrefsUnifiedDlg.cpp:3111`); the button has no
  such prior state. If a cancel button is wanted later it needs a real rollback
  story, so leave `wxPD_CAN_ABORT` off and always return `true` from the yield.
* This keeps the walk on the main thread — it does not move it to a worker. The
  point is that the event loop is pumped every 256 files, so the window
  repaints, stays draggable and shows progress.

### Part B — core: schedule the reload instead of running it in the EC handler

1. Add a deferred-reload request to `CSharedFileList` (`src/SharedFileList.h`):

```cpp
// Ask for a full shared-files reload to run from the next Process() tick
// instead of inline in the caller. Callers on the core event loop (EC
// request handlers, the directory watcher's dropped-events fallback) use
// this so they can answer immediately instead of blocking for the whole
// walk. Repeat requests before the tick coalesce into one walk.
void RequestReload() { m_reloadPending = true; }
```

with a `bool m_reloadPending = false;` member. A plain `bool` is sufficient —
every setter and the reader run on the core event loop; do not add an atomic
or a mutex for it (and if a caller off the main thread ever needs it, that
caller is the thing to fix).

2. Drain it at the top of `CSharedFileList::Process()`
   (`src/SharedFileList.cpp:1379`), which `CamuleApp::OnCoreTimer` already
   calls once per second (`src/amule.cpp:1996`):

```cpp
void CSharedFileList::Process()
{
    if (m_reloadPending && !reloading) {
        m_reloadPending = false;
        Reload();
    }
    Publish();
    ...
}
```

The `reloading` guard means a request arriving while a walk is in progress
keeps the flag set and runs afterwards, rather than being dropped or nesting.

3. Swap both inline EC callers over:

* `src/ExternalConn.cpp:3662` (`EC_OP_SHAREDFILES_RELOAD`):
  `theApp->sharedfiles->RequestReload();` then reply `EC_OP_NOOP` immediately.
* `src/ExternalConn.cpp:1741` (`EC_OP_SET_SHARED_DIRS`): the directory lists are
  still written and `SaveSharedFolders()` still runs synchronously — only the
  `Reload()` call becomes `RequestReload()`. The response therefore now means
  "directories accepted and persisted, rescan scheduled".

4. Promote the reload's start line from debug to info so clients that no longer
   block on the call can still see the walk begin. `src/SharedFileList.cpp:1064`
   is currently `AddDebugLogLineN(logKnownFiles, "Reload shared files")`, which
   is compiled out entirely in release builds; make it
   `AddLogLineN(_("Reloading shared files..."))`. The end-of-walk summary
   (`"Found %i known shared files, %i unknown"`, `src/SharedFileList.cpp:464`)
   is already an info line, so start and end become a matched pair.

### Part C — amuleapi endpoint and docs

* `HandleSharedReload` (`src/webapi/Api.cpp:7634`) keeps returning **202**,
  which is now truthful. Update its comment — the claim that the call is
  "synchronous on amuled's side but ... completes in well under a second" is
  exactly the assumption that fails on the trees where it matters.
* `SimpleConnControlOp` runs `RefresherTick(...)` inline after the op
  (`src/webapi/Api.cpp:6543`). For this endpoint that tick now snapshots state
  from *before* the walk, so it buys nothing; it is harmless (a few EC
  roundtrips) and shared with the connect/disconnect endpoints, so leaving it
  alone is fine. If you prefer to skip it, do so without changing behaviour for
  the other callers of that helper.
* `docs/api/REFERENCE.md:1280` (`POST /api/v0/shared/reload`): document that
  `202` means *accepted and scheduled*, that the walk starts within about a
  second and runs asynchronously, that repeated calls while a reload is pending
  or running coalesce into one walk, and that completion is observable through
  the amule log (`GET /api/v0/logs/amule`, `log_appended` SSE) and the
  `shared_added` / `shared_removed` SSE events rather than the response.
  `POST /api/v0/shared/{hash}/verify` is already documented in exactly this
  "accepted, outcome observed in the log" shape — match it.
* `PUT /api/v0/shared/directories` (backed by `EC_OP_SET_SHARED_DIRS`): document
  that the rescan is now scheduled rather than completed before the response
  returns. `/api/v0/` is experimental and unused by third parties, so this
  behavioural change needs no compatibility shim.
* No frontend change is needed: `src/webapi/static/js/views/shared.js:70`
  already fires the POST, shows a "reloading" toast and refreshes on a timer —
  i.e. it already assumes the asynchronous semantics.

## What this fixes, and what it does not

Fixed:

* The GUI window no longer freezes; the user sees files-scanned progress.
* Every EC client (`amuleapi`, `amulecmd`, `amuleweb`) gets an immediate reply.
  The reload request no longer occupies the `CEcService` in-flight slot for the
  duration of the walk, so it can no longer be the request that fills the
  8-deep queue and turns the whole API into a `503` wall.
* `202 Accepted` becomes an accurate description of the endpoint.

Deliberately **not** fixed here, and worth stating in the issue so nobody
expects it: the walk still occupies amuled's event loop while it runs, so EC
requests issued *during* the walk still wait for it to finish. That means a
pathological tree can still starve the lane for minutes.

Do **not** try to paper over that by pumping the event loop from the deferred
walk's yield callback. `FindSharedFiles` clears `m_Files_map` up front, so
during the walk the share list is transiently empty and then partially filled;
answering `EC_OP_GET_SHARED_FILES` from that state would make the diff engine
emit thousands of spurious `shared_removed` events followed by thousands of
`shared_added` ones. The current blocking behaviour is what protects clients
from ever observing a half-populated list. Making the walk genuinely
concurrency-safe requires an incremental scan that diffs against the live map
instead of clearing it (or a worker thread that collects `(path, mtime, size)`
tuples and hands batches to the main thread) — a separate, larger change.

## Acceptance criteria

* [ ] Clicking "Reload" in the shared-files pane shows a progress dialog with a
      live files-scanned count; the window stays responsive and repaints
      throughout, and the dialog closes when the walk ends.
* [ ] The same click in `amulegui` (remote) behaves as before — one EC packet,
      no dialog flash.
* [ ] `POST /api/v0/shared/reload` returns `202` in roughly the time of one EC
      round trip regardless of share-tree size, and the walk then runs.
* [ ] While that walk runs, no `503 ec_unavailable` is caused by the reload
      request itself sitting in the EC service's in-flight slot.
* [ ] `PUT /api/v0/shared/directories` returns without waiting for the rescan;
      the new roots are persisted before the response.
* [ ] Two `POST /api/v0/shared/reload` calls in quick succession result in one
      walk, not two.
* [ ] A release build logs `Reloading shared files...` when the walk starts and
      the existing `Found N known shared files, M unknown` line when it ends,
      with no debug categories enabled.
* [ ] `amulecmd`'s reload command and amuleweb's reload return immediately.

## Files to touch

* `src/SharedFilesWnd.cpp` — progress dialog + yield in `OnBtnReloadShared`.
* `src/SharedFileList.h` / `src/SharedFileList.cpp` — `RequestReload()`,
  `m_reloadPending`, the drain in `Process()`, info-level start line.
* `src/ExternalConn.cpp` — the two inline `Reload()` calls (`:1741`, `:3662`).
* `src/webapi/Api.cpp` — `HandleSharedReload` comment.
* `docs/api/REFERENCE.md` — `POST /shared/reload` and
  `PUT /shared/directories` semantics.
* `unittests/curl-tests/amuleapi/` — new script in the existing numbering
  scheme, modelled on `30-shared-verify.sh` (which already tests an
  accepted-not-completed `202` endpoint): assert `POST /shared/reload` returns
  `202 {"ok":true}` promptly, that a second immediate call also returns `202`,
  and that a `GET /shared` shortly afterwards still serves a coherent list.

## Manual test notes

Point a share root at a deliberately slow or large tree (a few tens of
thousands of files, or a network mount) so the walk takes several seconds:

1. Monolithic GUI: click Reload — window must stay responsive and show
   progress.
2. `amuled` + `amuleapi`: `time curl -X POST .../shared/reload` must return
   immediately; in parallel, poll `GET /api/v0/status` and confirm the API is
   not returning `503` because of the reload request itself; confirm
   `GET /api/v0/logs/amule` shows the start line and then the summary line.
3. `amulecmd`'s reload command must return to the prompt at once.
