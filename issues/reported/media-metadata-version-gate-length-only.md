# Bug: a probed file with no duration is advertised to ed2k but invisible to Kad, EC and the Web UI — and re-probed on every start

## Summary

`CKnownFile::GetMetaDataVer()` is not a stored flag. It is derived from one tag:

```cpp
// src/KnownFile.cpp:142-151
uint32 CKnownFile::GetMetaDataVer() const
{
	// Derived from tag presence, no separate m_uMetaDataVer field.
	// FT_MEDIA_LENGTH is the only tag MediaProbe populates
	// unconditionally on a successful probe (bitrate and codec are
	// best-effort per format), so nonzero length is the reliable
	// "we've probed this and have data worth publishing" signal.
	// Kad's publisher (Search.cpp:1422) uses this exact gate.
	return GetIntTagValue(FT_MEDIA_LENGTH) > 0 ? 1 : 0;
}
```

The premise stated in that comment is what fails. `MediaProbe::Probe()` does not
populate `FT_MEDIA_LENGTH` unconditionally on success: it succeeds on duration
**or** codec (`src/MediaProbe.cpp:576`:
`if (!got_duration && !got_codec) return false;`), and `amule.cpp:2312-2320`
attaches whichever fields came back. A file that yields a codec but no duration
therefore ends up with `FT_MEDIA_CODEC` attached and `GetMetaDataVer() == 0`,
which puts four consumers in disagreement about whether the file has metadata:

| Consumer | Gate | Result for a codec-only file |
|---|---|---|
| ed2k publish (`src/KnownFile.cpp:1391-1405`) | none, per-tag `if` | **advertises `codec` to every peer** |
| Kad publish (`src/kademlia/kademlia/Search.cpp:1498`) | `GetMetaDataVer() > 0` | publishes nothing |
| EC → amulegui / Web UI (`src/ECSpecialCoreTags.cpp:358`) | `GetMetaDataVer() != 0` | sends nothing, API reports `has_media:false` |
| File detail dialog (`src/FileDetailDialog.cpp:260`) | `GetMetaDataVer() != 0` | shows N/A |

The same tag is good enough to advertise to strangers and not good enough to
show to the person who owns the file.

There is a second consequence. The "don't probe twice" gate uses the same
signal:

```cpp
// src/SharedFileList.cpp:797
if (!bForceReprobe && pFile->GetIntTagValue(FT_MEDIA_LENGTH) > 0) {
```

so these files never look probed. Every startup rescan re-runs ffprobe on all of
them, forever, for a result that is already known and will be discarded again.
The waste is silent: a rescan queues more than one job, which puts the worker in
bulk mode (`src/MediaProbeThread.cpp:107`), so the per-file log line is suppressed
and the re-probes show up only as an inflated count in the one summary line.

## Reproducing

`.h264` and `.hevc` are both in `ED2KFT_VIDEO`, so raw elementary streams are
scheduled for probing. Any of them reproduces it:

```
$ ffprobe -v error -show_entries 'format=duration,bit_rate:stream=codec_name,codec_type' \
      -of default=nk=0:nw=1 raw.h264
codec_name=h264
codec_type=video
duration=N/A
bit_rate=N/A
$ echo $?
0
```

`ParseSeconds("N/A")` fails, so `FT_MEDIA_LENGTH` is never attached; the codec is.
Share such a file and: peers see `h264` in the search hit, the Web UI shows no
media block, and the log repeats the extraction line on every restart.

The same shape occurs for any container where ffprobe cannot determine a
duration — truncated files, some transport streams, captures without an index.

## Root cause

`GetMetaDataVer()` was defined as a proxy for "we have probed this file", using
the field the probe was assumed to always return. `Probe()` does not guarantee
that field, and the ed2k publisher never adopted the proxy in the first place.

## Requested change

Make one definition of "this file has media metadata" and use it everywhere.

1. Derive `GetMetaDataVer()` from the presence of **any** `FT_MEDIA_*` tag, not
   from `FT_MEDIA_LENGTH` alone. The comment in `src/KnownFile.h:375-381` and the
   one at `src/ECSpecialCoreTags.cpp:354-357` describe the intent correctly
   already; only the implementation is narrower than the intent.
2. Use `GetMetaDataVer()` for the "already probed" gate in
   `src/SharedFileList.cpp:797` instead of re-testing `FT_MEDIA_LENGTH`, so a
   codec-only file is probed once and then left alone.
3. Leave the ed2k publisher's per-tag `if` checks as they are: they already emit
   only the fields that exist, which is the correct wire behaviour. After (1)
   the other three consumers agree with it.

A stored flag would work too, but a derived one keeps the "no separate
`m_uMetaDataVer` field" property the current code was written for.

## Acceptance criteria

- A shared `raw.h264` (codec, no duration) shows its codec in the Web UI, the
  file detail dialog and amulegui, and is published to Kad.
- The same file is probed once and not re-probed on the next start; the
  `Extracting media metadata with ffprobe` line appears once, not per restart.
- A file that yields no metadata at all is still never marked as having any.
- A file with length but no codec keeps behaving exactly as today.

## Out of scope

- Whether raw elementary streams should be probed at all: they are legitimately
  in the audio/video extension list and the probe does return useful data.
- Which fields the probe extracts, and how accurate they are. This report is only
  about the four consumers disagreeing on whether a probed file counts as having
  metadata.

---

Line references checked against aMule `55b0b60db`; ffprobe output produced with
ffprobe 8.0.
