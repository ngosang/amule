# Media metadata extraction should be enabled by default

## Summary

`/MediaMetadata/Enabled` defaults to `false` (`src/Preferences.cpp:1676-1677`):

```cpp
/**
 * Media metadata extraction (issue #140). Off by default so an
 * upgrade doesn't kick off a background probe of every shared
 * file until the user opts in. ...
 */
NewCfgItem(IDC_MEDIAMETA_ENABLED,
	(new Cfg_Bool("/MediaMetadata/Enabled", s_MediaMetadataEnabled, false)));
```

The caution made sense while the feature was new. Now that the cost is
measurable it looks disproportionate, and the default has a side effect the
reasoning did not account for: **the feature exists almost entirely for other
people's benefit**, and a default-off feature that benefits somebody else is one
that nearly nobody enables.

The extracted tags are advertised in search answers and published to Kad
(`src/KnownFile.cpp:1396-1405`, `src/kademlia/kademlia/Search.cpp:1498-1520`).
They are what fills the Length / Bitrate / Codec columns for the peer searching
the network. With the feature off, an aMule share is a hole in that data for
everyone else, while locally it only costs the owner a detail dialog showing
N/A for files they already have.

It is also undiscoverable where it matters most. On a headless deployment —
`amuled` plus `amuleapi`, which is what the REST surface exists for — there is no
dialog to stumble across the checkbox in. The operator has to already know the
preference exists to go looking for it.

## The cost, measured

A probe reads the container header and index, not the file. Timings for a real
share, using an ffprobe built with `--disable-everything` plus demuxers and
parsers, warm page cache, and the entry list the probe itself uses
(`format=duration,bit_rate:stream=codec_name,codec_type`):

Five of the sixteen files measured:

| File | Size | Probe |
|---|---|---|
| `Taylor Swift - Love Story.mp3` | 8 MB | 3.9 ms |
| `Mr.Robot 3x07 …mkv` | 437 MB | 3.7 ms |
| `Banksters 1x03 …mkv` | 1023 MB | 8.7 ms |
| `Harry Hole s01e04.mp4` | 160 MB | 23.4 ms |
| `Harry Potter 1 …avi` | 1401 MB | 52.7 ms |

16 files, 3.5 GB of media: **218 ms total, 13.6 ms average**. Size barely
correlates — the 1 GB MKV costs less than a 160 MB MP4 — because what is read is
the header and, for AVI, the index at the end.

Extrapolated to a 10 000-file media library, that is roughly **two minutes of
one background thread, once**, because:

- probes run on a dedicated worker, one at a time
  (`src/MediaProbeThread.cpp:111-139`), never on the hashing or completion paths;
- each is bounded by a 30 s timeout and cancelled on shutdown
  (`kProbeTimeoutMs`, `src/MediaProbeThread.cpp:40`);
- a file that yields a duration is never probed again — the scheduler skips
  anything that already carries one (`src/SharedFileList.cpp:797`), so for
  practically the whole library this is a one-time cost, not a per-start one;
- the log does not explode: a batch larger than one file switches to bulk mode
  and emits a single summary line for the whole drain
  (`src/MediaProbeThread.cpp:107`, `:141-158`).

## It degrades safely when ffmpeg is absent

Enabling by default does not require ffprobe to exist. When detection finds
nothing, the worker drops every job (`src/MediaProbeThread.cpp:121-125`):

```cpp
const wxString exe =
	job.ffprobePath.IsEmpty() ? MediaProbe::DetectedPath() : job.ffprobePath;
if (exe.IsEmpty()) {
	continue;
}
```

and `DetectedPath()` has already logged the one line that explains it. Detection
is memoised for the life of the process, so the cost on a machine without ffmpeg
is one failed lookup — an `ffprobe -version` spawn that fails immediately, plus a
stat of each well-known path — followed by a queue walk and a single log line. It
is not paid per file, and not paid again once it has answered.

## Requested change

1. Flip the default to `true` in `src/Preferences.cpp:1676-1677` and update the
   comment above it.
2. Leave the checkbox and everything downstream unchanged; this is a default,
   not a removal of the choice.

Note what this does and does not touch on upgrade. `Cfg_Bool::LoadFromFile()`
is `cfg->Read(GetKey(), &m_value, m_default)` (`src/Preferences.cpp:632`), so the
default only applies when the key is absent from `amule.conf`:

- a configuration written by a version that already had the key keeps whatever
  it says, including an explicit opt-out — nobody who turned it off gets it
  turned back on;
- a configuration older than the key, and every new configuration, gets it on.

That is the desired behaviour, but it means the change reaches existing
installations only when their config predates the setting; it is worth deciding
explicitly whether that is enough or whether a one-time migration is wanted.

## Acceptance criteria

- A fresh configuration has media metadata extraction enabled and probes shared
  audio/video files on first scan.
- An existing configuration with the key set to `0` still starts with the feature
  off.
- On a machine with no ffprobe, startup logs the single "no ffprobe binary found"
  line and nothing else changes: no repeated detection, no per-file errors.
- A library scan with the feature on emits one summary line, not one line per
  file.
- The checkbox still turns the feature off, and no further probes are scheduled
  once it is off.

## Out of scope

- Auto-detecting or bundling ffprobe.
- Which fields the probe extracts and how accurate they are.
- Re-probing files that were already probed.

---

Line references checked against aMule `55b0b60db`. Timings measured with
ffprobe 8.0 on a local share.
