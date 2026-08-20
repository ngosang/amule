# Once a shared file has been probed its media metadata can never be re-extracted

## Summary

Once a shared file carries a length, nothing can make aMule read it again. The
scheduler skips anything that already has one (`src/SharedFileList.cpp:797`):

```cpp
if (!bForceReprobe && pFile->GetIntTagValue(FT_MEDIA_LENGTH) > 0) {
	AddDebugLogLineN(logMediaProbe,
		CFormat(wxT("MediaProbe: skip (already has metadata) %s")) % pFile->GetFileName());
	return;
}
```

and the only caller that passes `bForceReprobe = true` is the download-completion
path (`src/SharedFileList.cpp:887`). Nothing else in the tree can force a probe:
the **Reload** button walks the share tree and re-adds every file, but each one
takes the branch above and is skipped, because reloading the *share* is not the
same operation as re-reading a *file*.

The consequence is that whatever was extracted the first time is permanent:

- a bug in the extraction leaves every already-probed file wrong forever, and
  fixing the bug in a later release fixes nothing for existing users;
- a newer aMule that extracts more fields cannot backfill them;
- installing a better ffprobe, or pointing the preference at a different one,
  changes nothing for files already seen;
- a file edited in place — retagged, remuxed, replaced — keeps the old values.

The only workaround is deleting `known.met`, which is not a workaround anyone
should be asked to use. That file is where `CKnownFile::WriteToFile()` stores the
**ed2k part hash list** and the AICH master hash, so deleting it re-hashes the
entire library from scratch, which on a large share is hours of disk I/O — and it
also carries the per-file all-time transferred bytes, requests and accepted
requests (`src/KnownFile.cpp:717-732`) plus the rest of each file's tag list, all
of which are lost with it.

## Requested change

A **Refresh media metadata** action, distinct from Reload, that re-extracts the
metadata of every shared file without disturbing anything else about it.

### Behaviour

- **Re-extract, do not rebuild.** Every media field is read again and the stored
  values replaced — including *clearing* a field the new probe no longer finds,
  so a refresh can correct a wrong value in both directions. Nothing else about
  the file is touched: statistics, comment, rating, upload priority, AICH hash
  set, share state, part/complete status and per-client credits all survive
  untouched. The file is not re-hashed; its ed2k hash is unchanged and it never
  leaves the share.
- **Asynchronous.** The action returns immediately and the work happens in the
  background. The user can keep using aMule, and downloads and uploads are
  unaffected.
- **Confirmed first.** Before anything is queued the user is asked to confirm,
  with a warning that the operation can take a long time and, ideally, the number
  of files that will be probed.
- **Interruptible and safe to leave running.** Shutting aMule down mid-refresh
  must be clean; the files not yet reached simply keep their previous values.
- **Reportable.** The user must be able to tell that a refresh is in progress and
  roughly how far along it is.

### Where it must be available

- **aMule and amulegui** — an entry in the shared-files view, next to but clearly
  separate from Reload, with the confirmation dialog. It must work from amulegui
  against a remote daemon, which means an EC opcode, not a GUI-local loop.
- **amuleapi** — a REST endpoint so headless deployments have it at all, e.g.
  `POST /api/v0/shared/media/refresh`, ADMIN-only, returning how many files were
  queued. A single-file variant (`POST /api/v0/shared/{hash}/media/refresh`) is
  the natural companion and is cheap once the bulk path exists — it is also the
  quickest way for a user to test a fix on one file.

## Implementation notes

Most of the machinery is already in place; what is missing is the entry point.

- **Forcing is already supported.** `MaybeScheduleMediaProbe(pFile, /*bForceReprobe=*/true)`
  already bypasses the "already has metadata" gate. A core method that iterates
  the shared list and calls it per file is the whole scheduling side.
- **But the force flag also bypasses the partfile guard**
  (`src/SharedFileList.cpp:792-796`), which exists because an in-progress download
  has no complete file to read — it is on disk as `<hash>.part`. That guard is
  currently safe to bypass only because the one existing caller fires exactly when
  a download has just completed. A refresh that walks the whole shared list must
  not inherit that: it has to skip part files itself, or the bypass has to become
  a separate flag from the metadata gate.
- **The worker is already asynchronous, queued and throttled.**
  `CMediaProbeThread` (`src/MediaProbeThread.cpp:79-160`) holds an unbounded job
  list, drains it one probe at a time on its own thread, bounds each probe with a
  30 s timeout, checks its run flag between jobs so shutdown is prompt, and
  marshals each result to the main thread. Queueing ten thousand jobs needs no
  new plumbing.
- **Bulk logging already exists.** A drain of more than one file switches to a
  single summary line for the whole batch (`src/MediaProbeThread.cpp:107`,
  `:141-158`), so a full refresh will not produce one log line per file.
- **Overwrite semantics need attention.** The apply step
  (`src/amule.cpp:2312-2320`) only writes a tag when the new value is non-zero or
  non-empty, so today a re-probe cannot clear a field that the previous probe had
  filled. `CAbstractFile` has `AddTagUnique()` (`src/KnownFile.h:144`) but no
  removal counterpart, so a small `RemoveTag(uint8 id)` is needed for the
  "replace, including clearing" requirement above.
- **Progress needs one new signal.** The worker reports only at the end of a
  drain. Exposing the pending job count — over EC for amulegui and in the REST
  response or a status field for amuleapi — is enough for a "refreshing, N left"
  indication.
- **Cost, for the confirmation wording.** On a real share, probing costs about
  13 ms per file (3.5 GB across 16 files took 218 ms, warm cache): a 10 000-file
  library is on the order of two minutes of background work. Slow media — network
  mounts, spun-down disks — is where the warning earns its place.

## Acceptance criteria

- Triggering the action from aMule, amulegui and the REST endpoint re-probes every
  shared audio/video file, including files that already had metadata.
- The action asks for confirmation before queueing anything, and cancelling
  queues nothing.
- After a refresh, a file whose content changed reports the new values, and a
  file whose probe now returns fewer fields no longer reports the stale ones.
- After a refresh, every file keeps its all-time transferred / requested /
  accepted counters, comment, rating, upload priority and AICH hash set, and no
  file is re-hashed or unshared.
- The UI stays responsive during the refresh and downloads/uploads are unaffected.
- Shutting down mid-refresh loses no data and produces no error.
- Reload keeps its current meaning and does **not** re-probe.

## Out of scope

- Re-hashing file content: that is a different, far more expensive operation.
- Automatically re-probing on file mtime change — worth considering separately,
  but this request is about an explicit, user-triggered action.
- Which fields the probe extracts and how accurate they are.

---

Line references checked against aMule `55b0b60db`. Timings measured with
ffprobe 8.0 on a local share.
