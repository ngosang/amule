# Bug: media metadata never runs when `ffprobe_path` is empty — the core does no auto-detection at all

## Summary

`files.ffprobe_path` is documented, in two places, as optional because the core
falls back to auto-detection:

- `docs/api/REFERENCE.md:1759` — "`ffprobe_path` is a **daemon-side** path — an
  empty string means the daemon auto-detects the binary."
- `src/webapi/static/i18n/en.json:700` — the web UI labels the field
  "Path to ffprobe (empty = auto-detect)".
- `src/Preferences.cpp:1667-1672` — the preference's own comment: "Path default
  is empty — populated on demand by `MediaProbe::AutoDetectPath()`".

**None of that happens.** The core never calls `AutoDetectPath()`. The only
caller in the entire tree is the desktop Preferences **Detect** button
(`src/PrefsUnifiedDlg.cpp:2175-2190`), and the scheduling path gives up the
moment the preference is empty:

```cpp
// src/SharedFileList.cpp:697-700
const wxString &ffprobePath = thePrefs::GetMediaMetadataFFProbePath();
if (ffprobePath.IsEmpty()) {
    return;
}
```

So on any deployment without a desktop GUI — `amuled` + `amuleapi`, which is
precisely what the REST surface exists for — an operator enables
`files.media_metadata_enabled`, leaves the documented-as-optional path empty, and
gets **silent nothing**: no probe, no metadata, no error, no log line, and no
field anywhere reporting that the feature is inert. There is also no way for that
operator to learn a working path, since the machine that would have to be
searched is the daemon's.

Two supporting defects fall out of the same area and are fixed alongside:

- `MediaProbe::CanRun()` (`src/MediaProbe.cpp:73-84`) spawns
  `ffprobe -version` through `wxExecute(..., wxEXEC_SYNC)` with **no timeout**. A
  wedged binary hangs its caller forever — today that means the desktop
  Preferences dialog freezing on a **Detect** click.
- On `amulegui`, **Detect probes the wrong machine**: it runs detection in the
  GUI process and pushes the result to a daemon that may be on another host with
  an entirely different filesystem.

The work is staged so the bug fix stands alone and ships first; the later steps
give the detection a home in the core and make it reachable from every client.

## Reproducing

On a host that has `ffmpeg` installed, with no desktop GUI involved:

```sh
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"files":{"media_metadata_enabled":true,"ffprobe_path":""}}' \
  "http://$HOST/api/v0/preferences"

curl -s -X POST -H "Authorization: Bearer $TOKEN" "http://$HOST/api/v0/shared/reload"
curl -s -H "Authorization: Bearer $TOKEN" "http://$HOST/api/v0/shared/$HASH_OF_A_VIDEO" | jq .media
```

Expected, per the reference: the file acquires Length / Bitrate / Codec, visible
as the `media` object and advertised to peers in search results.

Actual: `media` is absent, forever. Nothing is logged even with the
`logMediaProbe` debug category enabled, because the code returns before reaching
any logging.

## Root cause

| Piece | Location |
|---|---|
| Detection routine, never called by the core | `src/MediaProbe.cpp:125-146` — `AutoDetectPath()`: tries bare `ffprobe` on `$PATH`, then a per-platform well-known list; returns `""` when nothing runs |
| Its only caller in the tree | `src/PrefsUnifiedDlg.cpp:2175-2190` — the desktop **Detect** button, which fills the text field and nothing else |
| Where the empty path dead-ends | `src/SharedFileList.cpp:697-700` |
| The preference | `src/Preferences.cpp:1676-1677`, accessors `src/Preferences.h:850-851` |
| Unbounded child process | `src/MediaProbe.cpp:73-84` (`CanRun()`) |
| Bounded child process, already written and used by the per-file probe | `src/MediaProbe.cpp:211-215` — `RunBoundedFFProbe(exe, argv, timeoutMs, keepRunning, stdoutLines)` |
| The worker that already isolates ffprobe from the core | `src/MediaProbeThread.cpp:66-77` (`QueueProbe`), `:79-119` (`Entry`) |

---

## Step 1 — Fix the bug: make the core detect (core only)

This step alone closes the bug and changes no protocol and no API shape.

1. **Bound the detection probe.** Route `MediaProbe::CanRun()` through the
   existing `RunBoundedFFProbe()` with a wall-clock bound (a few seconds is ample
   for `-version`), keeping its return contract (`true` ⇔ exit code 0). This is
   what makes detection safe to call from anywhere, and it also removes the
   desktop **Detect** button's ability to freeze the UI on a wedged binary.
2. **Add a cached resolver.** `MediaProbe::DetectedPath(bool redetect = false)` —
   `AutoDetectPath()` memoised once per process (`std::call_once`, with
   `redetect` forcing a fresh run and replacing the cache), returning `""` when
   nothing was found. Detection describes the machine, not the user's choice, so
   it is derived at runtime and never persisted to the config file.
3. **Stop dead-ending on the empty preference.** In
   `src/SharedFileList.cpp:697-700`, drop the early return and enqueue the job
   with whatever the preference holds, empty or not.
4. **Resolve on the worker.** In `CMediaProbeThread::Entry()`
   (`src/MediaProbeThread.cpp:100-113`), use
   `job.ffprobePath.IsEmpty() ? MediaProbe::DetectedPath() : job.ffprobePath` and
   skip the job when that is still empty. The first media file in a share pays
   one bounded detection, off the main thread; every later job reads the cache.
   This keeps the worker's stated invariant intact — it resolves against
   `MediaProbe`'s own cache, never `thePrefs`.
5. **Log the outcome once**, under the existing `logMediaProbe` category: which
   binary was auto-detected, or that none was found and extraction stays off.
   The feature's failure mode being completely silent is how this went unnoticed.

After this step `docs/api/REFERENCE.md:1759` and the web UI's field label become
accurate as written — they need re-reading to confirm, not editing.

---

## Step 2 — Give the detection an EC surface

With the core owning detection, expose it so remote clients can ask *the machine
that matters* what it found. Additive, no `EC_CURRENT_PROTOCOL_VERSION` bump —
unknown opcodes and tags are already handled (an old daemon answers an unknown
opcode with `EC_OP_FAILED`, `src/ExternalConn.cpp:4251-4258`), and the capability
tag below means a new client never has to send one blindly.

| New code | Value | Purpose |
|---|---|---|
| `EC_OP_FFPROBE_DETECT` | `0x63` | Request. No tags — it always means "run detection now". First free opcode after `EC_OP_CLIENT_HISTORY` = `0x62`. |
| `EC_OP_FFPROBE_PATH` | `0x64` | Reply. Carries `EC_TAG_FFPROBE_DETECTED_PATH`. |
| `EC_TAG_FFPROBE_DETECTED_PATH` | `0x2100` | string — the binary detection found, `""` when none was found. First free number after the `EC_TAG_SHAREDDIR` block (`ECCodes.abstract:662-665`). |
| `EC_TAG_CAN_FFPROBE_DETECT` | `0x0027` | Capability echoed in `AUTH_OK`, first free after `EC_TAG_CAN_CLIENT_HISTORY` = `0x0026`. |

- Handle the request in `src/ExternalConn.cpp` next to the other single-shot ops:
  call `MediaProbe::DetectedPath(/*redetect=*/true)` and answer with the path.
  Guard the handler `#ifndef CLIENT_GUI`, as the other core-only handlers are.
- Advertise the capability alongside the existing ones
  (`src/ExternalConn.cpp:1454` for the emit side,
  `src/libs/ec/cpp/RemoteConnect.cpp:769` and `RemoteConnect.h:216` for the
  client-side accessor).
- The op **has no side effects**: it detects and reports, and never writes
  `files.ffprobe_path`. Persisting is the caller's decision, because the two
  callers want different things — the desktop dialog fills its text field and
  only commits when the user presses OK, while a REST call has no OK button and
  stores immediately (step 4). Keeping the op pure is what lets both behave
  correctly without a second opcode or a "persist" flag.
- A detection is a bounded subprocess on the EC handler thread; step 1's bound is
  the precondition that makes that acceptable.
- The fresh result also replaces the core's memoised value, so the empty-preference
  fallback from step 1 immediately uses whatever was just found.

---

## Step 3 — `amulegui`: ask the core instead of probing the GUI host

`PrefsUnifiedDlg::OnButtonMediaMetaDetect()` (`src/PrefsUnifiedDlg.cpp:2175-2190`)
currently searches the machine the GUI runs on, which for a remote session is the
wrong filesystem entirely — it can offer a path that does not exist on the
daemon, or report "not found" while the daemon has ffmpeg installed.

- Monolithic build: keep calling `MediaProbe::DetectedPath(/*redetect=*/true)`
  directly — same core routine, now shared.
- `CLIENT_GUI` build: send `EC_OP_FFPROBE_DETECT` and fill the text field from
  the reply. Keep the existing "not found" message box for an empty reply,
  reworded to say the **core's** machine has no ffprobe.
- Hide or disable the button when the daemon does not advertise
  `EC_TAG_CAN_FFPROBE_DETECT`, the way the Clients window hides its "Known" tab
  against a daemon without the client-history capability
  (`src/ClientsWnd.cpp:110`).
- Either way the button only fills the field; the value is stored when the user
  presses OK, exactly as today. Cancel still discards it.

---

## Step 4 — `amuleapi`: `POST /api/v0/ffprobe/detect`

**Auth:** `ADMIN` — it spawns a process on the core and writes a preference. No
body.

The REST equivalent of the desktop **Detect** button: run detection on the core
and **store the result in `files.ffprobe_path`**. A REST call has no OK button to
commit against, so detect-and-store is one action here; the caller reads the
stored value back from `GET /api/v0/preferences` like any other setting.

```sh
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://$HOST/api/v0/ffprobe/detect"
```

```json
{ "ok": true, "found": true, "ffprobe_path": "/usr/bin/ffprobe" }
```

Implemented as two EC round trips inside the one request: `EC_OP_FFPROBE_DETECT`,
then — only when something was found — a `EC_OP_SET_PREFERENCES` carrying
`EC_TAG_FILES_MEDIA_FFPROBE_PATH`, reusing the packing the preferences PATCH
handler already does (`src/webapi/Api.cpp:6280-6505`), followed by the same
inline `RefresherTick` so the value is visible immediately.

Two rules worth pinning down:

- **Nothing found ⇒ nothing written.** The response is
  `{ "ok": true, "found": false, "ffprobe_path": "<unchanged>" }` and the
  preference keeps whatever it held. Overwriting a working hand-configured path
  with `""` because detection failed to recognise it — a container wrapper, an
  unusual prefix — would be destructive, and detection failing is not evidence
  that the configured binary is bad.
- **Found ⇒ overwrite.** An explicit detect replaces any previously configured
  path, which is what the desktop button does to its text field.

Because step 1 already makes an empty `ffprobe_path` work, this endpoint is never
required to get metadata flowing — it is for operators who want the path pinned,
visible in `GET /preferences`, and stable across an ffmpeg reinstall that moves
the binary.

**Response:** `200 OK` with the body above.

**Errors:** `403 forbidden` (guest), `405 method_not_allowed`,
`503 ec_unsupported` (daemon does not advertise `EC_TAG_CAN_FFPROBE_DETECT` — the
op is never sent blindly, mirroring how `GET /api/v0/known_clients` gates on the
client-history capability), `503 ec_unavailable`, `400 amuled_rejected`.

### Why there is no `GET /api/v0/ffprobe`

An earlier draft paired this with a read endpoint reporting configured / detected
/ effective paths. It is not worth its own resource: the configured path is
already on `GET /api/v0/preferences`, and once detect writes there, that single
field answers "which binary will run" without a second place to keep in sync.
Nothing else in the API grows a shadow copy of a preference, and this should not
be the first.

`GET`/`PATCH /api/v0/preferences` keep exactly the shape they have today —
`files.ffprobe_path` simply gains a second way to be written.

---

## Implementation checklist

**Step 1 — core (`src/`)**
- [ ] `MediaProbe.cpp` — bound `CanRun()` via `RunBoundedFFProbe()`.
- [ ] `MediaProbe.h` / `MediaProbe.cpp` — add the memoised
      `MediaProbe::DetectedPath(bool redetect = false)`.
- [ ] `SharedFileList.cpp:697-700` — remove the empty-path early return.
- [ ] `MediaProbeThread.cpp` — resolve an empty `job.ffprobePath` through
      `MediaProbe::DetectedPath()`; skip the job when it is still empty.
- [ ] One `logMediaProbe` line recording the auto-detected binary or its absence.
- [ ] Verify all four combinations: {ffmpeg installed, not installed} ×
      {`ffprobe_path` empty, explicitly set}. Empty + installed must produce
      `media` on `GET /api/v0/shared/{hash}`; empty + not installed must stay off
      and say so once in the log; an explicit path must keep overriding detection
      exactly as today.

**Step 2 — EC (`src/libs/ec/`, `src/ExternalConn.cpp`)**
- [ ] `ECCodes.abstract` — `EC_OP_FFPROBE_DETECT` `0x63`,
      `EC_OP_FFPROBE_PATH` `0x64`, `EC_TAG_FFPROBE_DETECTED_PATH` `0x2100`,
      `EC_TAG_CAN_FFPROBE_DETECT` `0x0027`, each with the usual `##` comment
      noting that legacy peers skip them.
- [ ] `ExternalConn.cpp` — request handler (`#ifndef CLIENT_GUI`) calling
      `MediaProbe::DetectedPath(true)`, with **no** preference write, and the
      capability advertisement next to the existing ones at `:1454`.
- [ ] `RemoteConnect.cpp` / `RemoteConnect.h` — parse and expose the capability
      flag, following the `EC_TAG_CAN_CLIENT_HISTORY` accessor at
      `RemoteConnect.h:216`.
- [ ] No `EC_CURRENT_PROTOCOL_VERSION` change.

**Step 3 — desktop GUI (`src/`)**
- [ ] `PrefsUnifiedDlg.cpp:2175-2190` — monolithic path calls
      `MediaProbe::DetectedPath(true)`; `CLIENT_GUI` path round-trips
      `EC_OP_FFPROBE_DETECT`. Both only fill the field; OK still commits and
      Cancel still discards.
- [ ] Hide or disable the **Detect** button when the capability is absent.
- [ ] Reword the "not found" message so it names the core's machine, not "your"
      machine; add the string to the translation catalogue.

**Step 4 — amuleapi (`src/webapi/`) + docs**
- [ ] `App.h` / `App.cpp` — record the `EC_TAG_CAN_FFPROBE_DETECT` capability at
      login, as `:99` already does for client history.
- [ ] `Api.h` / `Api.cpp` — `HandleFfprobeDetect` (`POST /ffprobe/detect`), its
      route entry and `405` handling; detect, then persist
      `EC_TAG_FILES_MEDIA_FFPROBE_PATH` through the existing SET_PREFERENCES
      packing only when a path was found, then the usual inline `RefresherTick`.
- [ ] `docs/api/REFERENCE.md` — a new **ffprobe** section for the endpoint plus
      its index entry; note that it writes `files.ffprobe_path` and that a failed
      detection leaves it untouched. Confirm the existing `files.ffprobe_path`
      sentence at `:1759` is now accurate and point it at the endpoint.

**Tests**
- [ ] `unittests/curl-tests/amuleapi/` — new script: `POST /ffprobe/detect`
      returns `{ok, found, ffprobe_path}`; on a runner with ffmpeg installed the
      path afterwards equals `files.ffprobe_path` from `GET /preferences`; on one
      without it, `found` is `false` and a previously configured path is
      unchanged; guest → `403`; `GET` → `405`.
- [ ] The four-way manual matrix from step 1, re-run on a daemon + `amulegui`
      pair to confirm the GUI's Detect reports the **daemon's** binary.

## Acceptance criteria

- [ ] With `files.media_metadata_enabled: true` and `files.ffprobe_path: ""` on a
      host that has ffmpeg installed, shared audio/video files acquire
      length/bitrate/codec — the documented "empty = auto-detect" behaviour is
      real for the first time, on `amuled` as well as on the monolithic build.
- [ ] With no ffmpeg installed, that same configuration logs one line saying so
      and otherwise behaves exactly as before: no repeated spawn attempts, no
      per-file noise.
- [ ] A hung or missing `ffprobe` cannot block daemon startup, the shared-file
      scan, an EC request, or the desktop Preferences dialog for longer than the
      detection timeout.
- [ ] `POST /api/v0/ffprobe/detect` picks up an ffmpeg installed after the daemon
      started, without a restart, and the path it reports is what
      `GET /api/v0/preferences` returns as `files.ffprobe_path` immediately
      afterwards.
- [ ] `POST /api/v0/ffprobe/detect` on a host with no ffmpeg answers
      `found: false` and leaves an already-configured `files.ffprobe_path`
      untouched.
- [ ] `amulegui`'s **Detect** button fills the field with a path that exists on
      the **daemon's** machine, and is hidden against a daemon that does not
      advertise the capability.
- [ ] `GET`/`PATCH /api/v0/preferences` return the same field set as before this
      issue.

## Out of scope

- Wiring the new endpoint into the bundled web UI
  (`src/webapi/static`). It is consumable by any client, and the Files
  preferences page needs no change for the bug fix itself — an empty
  `ffprobe_path` simply works now.
- Persisting the **automatic** detection result. The memoised value from step 1
  describes the machine and is re-derived every run; only an explicit
  `POST /ffprobe/detect` (or the desktop button plus OK) writes a path into the
  config, because that is a user decision to pin one.
- Any change to how `ffprobe` is invoked for actual metadata extraction, to the
  per-file probe timeout, or to the `media` fields on the file endpoints.
- Detecting anything other than `ffprobe` (e.g. a bundled or containerised
  ffmpeg wrapper); the well-known-path list in `src/MediaProbe.cpp:86-121` is
  unchanged here.
