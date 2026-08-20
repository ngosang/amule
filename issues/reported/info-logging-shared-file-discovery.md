# Info-level logging for shared-file discovery: hashing, ffprobe, watcher changes and new-file counts

## Summary

When aMule discovers and hashes new shared files, or shells out to `ffprobe` to
extract media metadata, **a release build says nothing at all**. Not "filtered
out by the log settings" — the trace statements are compiled out of the binary
entirely. A user who shares a large directory, or who has just configured
`ffprobe` in the preferences, sees an idle-looking client that is in fact busy
reading every file on disk and spawning a child process per media file, with no
way to tell what it is working on.

Add distinct **info-level** log lines, each carrying the file's full path:

1. one when a file starts being hashed,
2. one when `ffprobe` is executed on a file, and
3. one when the directory watcher attaches or detaches an already-known file,
   which is the auto-discovery case that does no hashing and would otherwise
   still be completely silent, and
4. one summary line per discovery pass saying how many **new** files were found,
   printed only when that count is above zero, and printed for both discovery
   routes — the "Reload" button's bulk walk and the watcher's auto-discovery.

## Current state

Every per-file trace on these paths is `AddDebugLogLineN`, and that macro is
`do {} while(false)` unless the build defines `__DEBUG__`:

```cpp
// src/Logger.h:455
#ifdef __DEBUG__
#define AddDebugLogLineN(type, string) \
	if (theLogger.IsEnabled(type)) \
	theLogger.AddLogLine(__TFILE__, __LINE__, false, type, string)
#else
#define AddDebugLogLineN(type, string) \
	do { \
	} while (false)
#endif
```

`__DEBUG__` is only defined for a debug configuration
(`cmake/options.cmake:254` — `add_compile_definitions($<$<CONFIG:DEBUG>:__DEBUG__>)`),
so in the builds users actually run these lines do not exist. Even in a debug
build they need *two* further opt-ins: the `VerboseDebug` preference
(`src/Preferences.cpp:1315`, default `false`) and the specific category, which
starts disabled (`src/Logger.h:139` — `m_enabled(false)`).

The traces that exist today, all `AddDebugLogLineN`:

| Trace | Category | Location |
|---|---|---|
| `Found shared file: %s` | `logKnownFiles` | `src/SharedFileList.cpp:591` |
| `Hashing new unknown shared file '%s'` (logged when the task is **queued**, not when it runs) | `logKnownFiles` | `src/SharedFileList.cpp:641` |
| `Starting to create MD4 and AICH hash for file: %s` (the actual hashing) | `logHasher` | `src/ThreadTasks.cpp:126-136` |
| `MediaProbe: queueing %s (ffprobe=%s)` | `logMediaProbe` | `src/SharedFileList.cpp:732` |
| `MediaProbe: probing %s` (the actual `ffprobe` execution) | `logMediaProbe` | `src/MediaProbe.cpp:436` |
| `Media metadata: %s -> length=%us bitrate=%ukbps codec=%s` | `logMediaProbe` | `src/amule.cpp:2317` |
| `Safe adding file to sharedlist: %s` | `logKnownFiles` | `src/amule.cpp:2214-2215` |

What a release build *does* print while scanning shares (all info level):

* `Adding file %s to shares` — partfiles only (`src/SharedFileList.cpp:407`).
* `Shared directory not found, skipping: %s` /
  `No shareable files found in directory: %s` — per directory.
* `Found %i known shared files, %i unknown` — one summary line at the end
  (`src/SharedFileList.cpp:464`).
* `Excluded %i files from sharing by filter` — one summary line.

So: nothing per hashed file, and nothing whatsoever about `ffprobe`. The
`ffprobe` case is the worse of the two, because it is a feature the user
explicitly turns on and points at a binary
(`Preferences → media metadata`, `src/Preferences.cpp:1675-1677`, off by
default) and then gets zero feedback that it is being used, that the binary
works, or which file is being probed.

## Requested change

Two new info lines. Both must include the **full path** (directory + filename),
not just the basename, and both must be plain `AddLogLineN` (not
`AddDebugLogLine*`) so they appear in a stock release build with no debug
settings enabled.

### 1. Hashing

In `CHashingTask::Entry()` (`src/ThreadTasks.cpp:82`), after the open /
length / size guards and immediately before the existing `m_toHash` branch at
`src/ThreadTasks.cpp:126`:

```cpp
AddLogLineN(CFormat(_("Hashing file: %s")) % fullPath);
```

* `fullPath` is already computed at `src/ThreadTasks.cpp:86`
  (`m_path.JoinPaths(m_filename)`) and the surrounding debug lines already
  format a `CPath` directly with `%s`, which yields its printable form.
* Placing it *after* the guards means files that are skipped (unreadable,
  zero-size, larger than the maximum) do not claim to have been hashed; those
  cases already log their own critical debug lines.
* This one insertion point covers every hashing path — newly discovered shared
  files, completion hashing of finished downloads, and AICH-only re-hashes —
  because they all construct a `CHashingTask`. That is intentional: each of
  those is real disk work worth one line. Pick wording that is honest for all
  three (hence `Hashing file:` rather than `Hashing new shared file:`).
* **Distinguish the AICH-only case, because it fires for files that were
  discovered long ago.** `CSharedFileList::CheckAICHHashes`
  (`src/SharedFileList.cpp:1769`) queues a `CHashingTask(file)` for every
  already-shared, already-known file whose AICH master hash is missing from
  `known2_64.met` (`src/SharedFileList.cpp:1798`), and that runs at startup on
  every launch (`FindSharedFiles` schedules `CAICHSyncTask(true)` whenever the
  scan found no new files). Normally it queues nothing; but after a
  `known2_64.met` loss, prune or format change it re-reads the **entire
  library** from disk — today completely silently, for minutes or hours. That
  work deserves a line, but it must not claim the file was just discovered.
  `CHashingTask::Entry()` already branches on exactly the three cases
  (`src/ThreadTasks.cpp:126-136`), so emit the info line inside those existing
  branches with wording matched to each: MD4 (with or without AICH) →
  `_("Hashing file: %s")`; AICH-only →
  `_("Rebuilding AICH hashset for file: %s")`. No extra branching needed, just
  two msgids instead of one.
* Do **not** log at the discovery/queue site (`src/SharedFileList.cpp:641`)
  instead: hashing tasks run serially on `CThreadScheduler` well after the
  directory walk finishes, so a queue-time line tells the user nothing about
  what is happening *now*, which is the whole point.

### 2. ffprobe

In `MediaProbe::Probe()` (`src/MediaProbe.cpp:406`), replace the debug line at
`src/MediaProbe.cpp:436` — after the empty-`ffprobePath` guard and the `argv`
construction, immediately before `RunBoundedFFProbe` — with:

```cpp
AddLogLineN(CFormat(_("Extracting media metadata with ffprobe: %s")) % file);
```

* This is the exact point at which a child process is about to be spawned, so
  the line fires once per actual `ffprobe` execution — not once per queued job
  (`src/SharedFileList.cpp:732` already covers queueing at debug level and can
  stay as it is).
* Drop the now-redundant `MediaProbe: probing %s` debug line at the same spot.
* Keep the outcome trace (`Media metadata: ... -> length=... bitrate=... codec=...`,
  `src/amule.cpp:2317`) at debug level. The request here is one line per
  execution; whether to also promote the *result* line is a separate judgement
  call and should not be bundled in without deciding it explicitly.

### 3. Auto-discovered files (directory watcher)

The two lines above already cover a file that the watcher picks up and that has
to be **hashed** — `CSharedDirWatcher` routes CREATE events through
`CSharedFileList::NotifyPathAdded` (`src/SharedFileList.cpp:881`), which calls
the same `AddPathToShares` the bulk walk uses and feeds the resulting
`CHashingTask` to `CThreadScheduler` (`src/SharedFileList.cpp:911-919`). So a
genuinely new file dropped into a shared directory gets its `Hashing file: ...`
line, and then its ffprobe line once it completes.

There is a gap, though: a file the watcher attaches that is **already in
`known.met`** — moved or renamed into a shared directory, or a file coming back
after being moved out — takes the `kAddPathKnown` branch. Nothing is hashed,
nothing is probed, and the only trace is a debug line. The file silently becomes
shared and gets published to peers with no info-level record at all. Unlike the
bulk walk, the watcher path has no end-of-scan summary line to account for it
either.

Add one info line in the `NotifyPathAdded` switch (`src/SharedFileList.cpp:911`),
in the `kAddPathKnown` case only:

```cpp
case kAddPathKnown:
    AddLogLineN(CFormat(_("Now sharing file: %s")) % fullPath);
    break;
```

(`fullPath` is `NotifyPathAdded`'s own `wxString` parameter, already the
complete path — nothing to join.)

Do **not** put this line inside `AddPathToShares` itself: that function is
shared with the bulk directory walk, where the already-known case is the
overwhelming majority of entries — one line per file there would bury everything
else under thousands of "nothing happened" lines on every rescan. The watcher
path is different in kind: it is an *event*, it fires at unpredictable times, its
volume is bounded by real filesystem activity rather than by tree size, and there
is no summary line covering it.

For the same reason, log the symmetric case — a shared file disappearing behind
the user's back is at least as interesting as one appearing:

* `CSharedFileList::NotifyPathRemoved` (`src/SharedFileList.cpp:929`), which
  currently only writes `Watcher: detaching deleted file '%s' from shares` at
  debug level: add
  `AddLogLineN(CFormat(_("Stopped sharing removed file: %s")) % fullPath);`
* `CSharedFileList::NotifyDirRemoved` (`src/SharedFileList.cpp:953`) detaches a
  whole subtree at once and already has the count in hand
  (`victims.size()`, `src/SharedFileList.cpp:986`): one summary info line there
  rather than one line per file, e.g.
  `_("Stopped sharing %u files under removed directory: %s")`.

`NotifyPathModified` needs nothing extra: a real size/mtime change re-hashes the
file, so it is already covered by the hashing line.

### 4. Summary line: how many new files were discovered

There should be a single info line reporting **how many new files a discovery
pass found**, printed only when that count is greater than zero, and it must
appear for both discovery routes — the bulk walk behind the "Reload" button and
the directory watcher's auto-discovery.

Today only the bulk walk reports anything, and it does so awkwardly
(`src/SharedFileList.cpp:450-467`):

```cpp
if (addedFiles == 0) {
    AddLogLineN(CFormat(wxPLURAL("Found %i known shared file",
        "Found %i known shared files", GetCount())) % GetCount());
    CThreadScheduler::AddTask(new CAICHSyncTask(true));
} else {
    AddLogLineN(CFormat(wxPLURAL("Found %i known shared file, %i unknown",
        "Found %i known shared files, %i unknown", GetCount())) % GetCount() % addedFiles);
}
```

so the new-file count only exists as a suffix on a different message, in one of
two mutually exclusive variants, and the watcher path prints nothing at all.

**Count once, at the one place discovery is decided.** `AddPathToShares`
(`src/SharedFileList.cpp:580`) is the single function both routes go through,
and its `kAddPathQueued` branch (`src/SharedFileList.cpp:641`) *is* the
definition of "a new file was discovered". Add a counter there and flush it from
the once-per-second `CSharedFileList::Process()` tick
(`src/SharedFileList.cpp:1379`, driven by `CamuleApp::OnCoreTimer`,
`src/amule.cpp:1996`):

```cpp
// in the kAddPathQueued branch of AddPathToShares, next to the existing
// hashTasks.push_back(...)
++m_discoveredNewFiles;

// at the top of CSharedFileList::Process()
if (m_discoveredNewFiles) {
    AddLogLineN(CFormat(wxPLURAL("Discovered %u new shared file",
        "Discovered %u new shared files", m_discoveredNewFiles)) % m_discoveredNewFiles);
    m_discoveredNewFiles = 0;
}
```

Why this placement rather than tallying in the callers:

* It covers **every** discovery route with no plumbing: the bulk walk
  (`AddFilesFromDirectory`), the watcher's CREATE handling
  (`CSharedFileList::NotifyPathAdded`, `src/SharedFileList.cpp:881`), the
  watcher's rename handling (`src/SharedDirWatcher.cpp:705`), the walk of a
  newly appeared shared subdirectory (`src/SharedDirWatcher.cpp:506` —
  recursive, so a per-caller tally would need a counter threaded through the
  recursion), and the MODIFY-treated-as-add path
  (`src/SharedFileList.cpp:1017`).
* No signature changes. `NotifyPathAdded` stays `void`; `SharedDirWatcher.cpp`
  is not touched at all.
* The one-second tick **coalesces**, which is exactly what is wanted: dropping
  50 files into a shared directory produces one `Discovered 50 new shared files`
  line, not 50. A single-file event produces `Discovered 1 new shared file`.
* A plain `unsigned` member is enough — every increment and the flush run on the
  main thread (the bulk walk, the wx filesystem-watcher event handler, and the
  core timer are all the main thread). No atomic, no mutex.

Then simplify the block quoted above: always print
`Found %i known shared file(s)` (dropping the two-argument variant and its
plural pair entirely, since the count now has its own line), and keep the
`CThreadScheduler::AddTask(new CAICHSyncTask(true))` call on the
`addedFiles == 0` branch exactly where it is — that scheduling condition is
unrelated to logging and must not change. Removing the `%i unknown` variant also
retires a msgid whose plural form was selected on `GetCount()` rather than on
the count it was pluralising.

One acceptable inaccuracy to be aware of rather than engineer around: the
counter counts files whose `CHashingTask` was *created*, whereas the existing
`addedFiles` counts tasks the scheduler *accepted*
(`CThreadScheduler::AddTask` can decline, e.g. during shutdown). Counting at
discovery is the correct semantic for "discovered N new files", and threading
the scheduler's verdict back to the counter is not worth it.

### 5. Startup must stay quiet when nothing changed

A hard requirement on all of the above: **starting aMule with an unchanged
share tree must not produce any per-file line.** A user with 20 000 shared
files, none of them new, must see the same handful of startup lines as today.
With the placements specified above that falls out for free, but it must be
verified, because the startup path touches every one of them:

| Startup step | Lines emitted for files already discovered on a previous run |
|---|---|
| `sharedfiles->Reload(...)` (`src/amule.cpp:1057` GUI, `:1112` daemon) | none — an already-known file takes the `kAddPathKnown` branch: no `CHashingTask`, so no hashing line, and no discovery-count increment |
| Per-partfile share add | the pre-existing `Adding file %s to shares` line, unchanged |
| End of the walk | `Found N known shared files`, and **no** `Discovered ...` line, because the count is zero |
| `CAICHSyncTask` → `CheckAICHHashes` | none, as long as every file's AICH master hash is present in `known2_64.met` (the normal case) |
| Media probe | none, as long as every audio/video file already carries `FT_MEDIA_LENGTH` |
| Watcher `Enable()` → `ColdDiscoverSubdirs()` (`src/SharedDirWatcher.cpp:525`) | none — it walks for unknown *subdirectories*, not files, and the startup `Reload` already ran before the watcher is enabled |
| Watcher steady state | none — `NotifyPathAdded` short-circuits on the path index for anything already shared (`src/SharedFileList.cpp:894-898`) |

Two cases where a *previously discovered* file legitimately does produce a line,
because real work is genuinely happening. Both must be called out in review so
they are not mistaken for the requirement being broken:

1. **First start after enabling media metadata.** Every already-shared
   audio/video file without `FT_MEDIA_LENGTH` gets probed, so it gets one
   ffprobe line. That is a one-time retrofit burst: once the tags are stored in
   `known.met`, subsequent startups are silent.
2. **A file `ffprobe` cannot read** (a non-media file with a media extension, a
   truncated download, a codec `ffprobe` fails on) never gets tags, so the
   `FT_MEDIA_LENGTH == 0` gate re-queues it on every startup and reload. It is
   re-probed today too — the new line only makes long-standing behaviour
   visible. Adding a negative-cache marker so a failed probe is not retried
   forever is a real improvement but a separate change; do not fold it in here.

### 6. Fix the misleading startup line from cold subdir discovery

While auditing what startup prints, one existing line is actively wrong.
`ColdDiscoverSubdirs()` reuses the watcher's dropped-events fallback flag to
request a resync when it finds subdirectories that appeared while aMule was off
(`src/SharedDirWatcher.cpp:610`). `FlushPendingEvents` then logs, at **critical**
level:

```
Shared-dir watcher: events dropped by backend, forcing a full shared-files reload to resync
```

(`src/SharedDirWatcher.cpp:655-660`). In the cold-discovery case no backend
dropped anything — new directories simply appeared while the client was not
running — and the user is told, in red, about a watcher failure that did not
happen. It also means a second full share walk right after startup, so the
startup log shows two `Found N known shared files` summaries with no explanation
for the second one.

Distinguish the two reasons for the resync (an extra flag, or a small enum
instead of the bool at `src/SharedDirWatcher.cpp:99`) and log accordingly:

* dropped events → keep the existing critical line;
* cold-discovered subdirectories → an info line naming what happened, e.g.
  `_("Shared-dir watcher: %u new subdirectory(ies) found since last run, rescanning shares")`.

### Message wording

The messages must be clearly distinguishable from each other at a glance — that
is the point of having separate lines. Suggested msgids (all new, all wrapped in
`_()` since they are user-visible):

* `_("Hashing file: %s")`
* `_("Rebuilding AICH hashset for file: %s")`
* `_("Extracting media metadata with ffprobe: %s")`
* `_("Now sharing file: %s")`
* `_("Stopped sharing removed file: %s")`
* `_("Stopped sharing %u files under removed directory: %s")`
* `wxPLURAL("Discovered %u new shared file", "Discovered %u new shared files", n)`

## Implementation notes

**Thread safety is already handled.** Both call sites run off the main thread —
`CHashingTask::Entry()` on `CThreadScheduler`, `MediaProbe::Probe()` on the
dedicated `CMediaProbeThread` — and `CLogger::AddLogLine` detects that and posts
a `CLoggingEvent` instead of touching the GUI directly
(`src/Logger.cpp:156-163`). There is precedent for logging user-visible lines
from a worker thread: `src/LibSocketAsio.cpp:2072` logs
`_("Asio thread %d started")` from an Asio pool thread.

**Use `AddLogLineN`, not `AddLogLineNS`.** The `...NS` variant also writes to
stdout (`src/Logger.h:465`). A first-run scan of a large library would then dump
tens of thousands of lines onto amuled's console/journal. `AddLogLineN` reaches
the logfile, the GUI log pane, and every EC/API log consumer, which is what is
wanted here.

**Volume.** One line per file actually hashed and one per `ffprobe` execution.
On a first-run scan of a 20 000-file media library that is up to 20 000 of each
— but strictly proportional to work genuinely being done (a full file read; a
spawned process), never timer-driven, and it stops when the work stops. Note
that the lines also flow to log consumers: the GUI log pane, `amulecmd`'s log
tail, `GET /api/v0/logs/amule`, and the `log_appended` SSE event
(`docs/api/EVENTS.md:413`), so a big scan will push older lines out of the log
buffer faster than before. That is the expected cost of the feature.

**What deliberately stays unlogged.** Files that the *bulk share walk* finds and
recognises from `known.met` do no work — `AddPathToShares` returns
`kAddPathKnown` after a couple of `stat` calls (`src/SharedFileList.cpp:580`).
Those are the overwhelming majority of entries on every rescan after the first
one, and logging them at info level would bury the lines that matter under
thousands of "nothing happened" lines. Leave that path at debug level, and note
that the bulk walk already accounts for them in its
`Found %i known shared files, %i unknown` summary. The watcher's incremental
add of an already-known file is the case that *is* logged, for the reasons given
above.

## Acceptance criteria

* [ ] In a **release** build, with `VerboseDebug` off and no debug categories
      enabled, adding a directory of new files to the shares produces one info
      log line per file as it is hashed, each showing the file's full path.
* [ ] With media metadata enabled and a valid `ffprobe` path, one distinct info
      log line appears per `ffprobe` execution, showing the file's full path,
      and it is visibly different from the hashing line.
* [ ] The `ffprobe` line appears once per probe, and does not appear for files
      that were only queued and then skipped (already-tagged files, in-progress
      partfiles, files that vanished before the probe ran).
* [ ] No hashing line appears for files that are skipped as unreadable,
      zero-size, or over the maximum size.
* [ ] Dropping a brand-new file into a shared directory while aMule is running
      (auto-discovery via the directory watcher, `AutoRescanSharedDirs` on by
      default) produces the hashing line, and then the ffprobe line if it is an
      audio/video file — no share reload required.
* [ ] Moving a file aMule already knows into a shared directory produces one
      `Now sharing file: <full path>` line, even though nothing is hashed.
* [ ] Deleting or moving a shared file out produces one
      `Stopped sharing removed file: <full path>` line; removing a whole shared
      subdirectory produces a single summary line with the file count, not one
      line per file.
* [ ] A bulk share reload still does **not** emit a per-file line for files it
      recognises from `known.met`.
* [ ] Copying 50 new files into a shared directory at once produces a single
      `Discovered 50 new shared files` line, not 50 lines.
* [ ] Reloading shares after adding new files on disk produces the same
      `Discovered N new shared files` line as the watcher route, with identical
      wording.
* [ ] A discovery pass that finds no new files produces **no** discovery-count
      line at all — neither `Discovered 0 new shared files` nor an empty
      variant.
* [ ] The `Found N known shared files` summary still appears on every bulk
      reload, and the AICH sync task is still scheduled under exactly the same
      condition as before the change.
* [ ] Both lines are visible in the GUI log pane, in the logfile, and through
      `GET /api/v0/logs/amule` / the `log_appended` SSE event.
* [ ] Both strings are wrapped in `_()` and appear in the regenerated
      `po/amule.pot`.
* [ ] Neither line is printed to stdout.
* [ ] Restarting aMule with an unchanged share tree, whose files are all
      already hashed, AICH-complete and media-tagged, produces **no** per-file
      line at all: no hashing line, no AICH line, no ffprobe line, no
      `Now sharing file` line and no `Discovered ...` line.
* [ ] Deleting `known2_64.met` and restarting produces
      `Rebuilding AICH hashset for file: <full path>` lines — not
      `Hashing file:` lines, which would wrongly suggest the files were newly
      discovered.
* [ ] Starting with new subdirectories added under a recursive share root while
      aMule was off no longer logs a critical "events dropped by backend" line,
      and the reason for the extra share rescan is stated in the log.

## Files to touch

* `src/ThreadTasks.cpp` — the hashing line in `CHashingTask::Entry()`.
* `src/MediaProbe.cpp` — the `ffprobe` line, replacing the debug trace at the
  same point.
* `src/SharedFileList.cpp` — the watcher lines in `NotifyPathAdded`
  (`kAddPathKnown` case), `NotifyPathRemoved` and `NotifyDirRemoved`; the
  discovery counter in `AddPathToShares`, its flush in `Process()`, and the
  simplification of the `FindSharedFiles` summary block.
* `src/SharedFileList.h` — the `m_discoveredNewFiles` member.
* `src/SharedDirWatcher.cpp` / `src/SharedDirWatcher.h` — distinguishing the
  cold-discovery resync from the dropped-events resync.
* `po/amule.pot` — regenerated so the two new msgids reach translators.

## Manual test notes

1. Release build. Copy a handful of fresh files (including at least one `.mp3`
   and one `.mp4`) into a shared directory.
2. With media metadata **disabled**, trigger a share rescan: expect exactly one
   `Hashing file: /full/path/...` line per new file, and no ffprobe lines.
3. Enable media metadata, point it at a valid `ffprobe` binary (the Detect
   button in preferences works), and rescan: expect one
   `Extracting media metadata with ffprobe: /full/path/...` line per audio/video
   file that does not already carry metadata.
4. Rescan again with no changes: expect neither line — everything is already
   known and already tagged.
5. Leave aMule running and, from a shell, copy a new media file into a shared
   directory: within a couple of seconds the watcher must produce the hashing
   line and then the ffprobe line, with no user action.
6. `mv` a file aMule already knows from one shared directory to another: expect a
   single `Now sharing file: ...` line for the destination and a
   `Stopped sharing removed file: ...` line for the source.
7. `rm -r` a shared subdirectory: expect one summary line naming the directory
   and the number of files detached.
8. Copy a batch of ~50 new files into a shared directory in one go: expect a
   single `Discovered 50 new shared files` line, followed by the per-file
   hashing lines as the scheduler works through them.
9. Add new files on disk while aMule is stopped, then start it (or press
   Reload): expect `Found N known shared files` and the same
   `Discovered M new shared files` line.
10. Restart with nothing changed on disk: the log must contain no per-file
    lines at all.
11. Delete `known2_64.met` and restart: expect AICH-rebuild lines, not
    hashing lines.
12. Confirm the same lines arrive over the API: `GET /api/v0/logs/amule` and an
    open SSE stream receiving `log_appended`.
