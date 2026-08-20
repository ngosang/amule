# Bug: the completion re-probe cannot clear a field, so unverified metadata from a search result survives as our own

## Summary

A download inherits the media metadata its source advertised, as a preview while
the file is incomplete (`src/PartFile.cpp:172-186`, issue #280). On completion the
file is re-probed, and the intent is explicit
(`src/SharedFileList.cpp:884-887`):

> Force it (bypassing the already-has-FT_MEDIA gate) so the authoritative local
> probe overwrites any metadata inherited from the search result, which is only
> a during-download preview.

The overwrite is conditional, though (`src/amule.cpp:2312-2320`):

```cpp
if (evt.GetLengthSeconds()) {
	file->AddTagUnique(CTagInt32(FT_MEDIA_LENGTH, evt.GetLengthSeconds()));
}
if (evt.GetBitrateKbps()) {
	file->AddTagUnique(CTagInt32(FT_MEDIA_BITRATE, evt.GetBitrateKbps()));
}
if (!evt.GetCodec().IsEmpty()) {
	file->AddTagUnique(CTagString(FT_MEDIA_CODEC, evt.GetCodec()));
}
```

A field the local probe could not determine is not written, so the inherited
value stays. For any such field the promise above is not kept: the peer's
number survives, and from that point aMule publishes it to ed2k and Kad as its
own verified metadata.

## Reproducing

Download a file whose search hit advertises all three fields — say
`length=180, bitrate=1500, codec=h264` — and that probes locally to a codec and
nothing else. A raw elementary stream does exactly that, and `.h264` and `.hevc`
are both in the probed extension list:

```
$ ffprobe -v error -show_entries 'format=duration,bit_rate:stream=codec_name,codec_type' \
      -of default=nk=0:nw=1 raw.h264
codec_name=h264
codec_type=video
duration=N/A
bit_rate=N/A
```

On completion the probe returns the codec only. `FT_MEDIA_CODEC` is replaced;
`FT_MEDIA_LENGTH` and `FT_MEDIA_BITRATE` keep the values the source claimed. The
same happens to any single field a probe cannot determine — the codec of a
container ffprobe cannot identify, the duration of a truncated capture.
The file now advertises numbers nobody verified, and nothing in the UI or the
API distinguishes them from probed ones.

The degenerate case is the same code path with the feature turned off: a
completed download keeps its inherited tags forever, because
`MaybeScheduleMediaProbe()` returns at the first line
(`src/SharedFileList.cpp:772`) and no probe ever contradicts them.

## Root cause

`AddTagUnique` can only add or replace, so "the probe found nothing for this
field" and "the probe was not run" are indistinguishable at the call site. The
nonzero guards were written to avoid attaching meaningless `0` tags — correct in
itself, but on a re-probe the alternative to a `0` tag is not "no tag", it is
"the previous, unverified tag".

## Requested change

Distinguish "probed and found nothing" from "not probed", on the re-probe path
specifically:

1. When a probe **succeeds**, make its result authoritative for all three fields:
   attach the ones it found and *remove* the tags for the ones it did not,
   instead of leaving whatever was there. `CAbstractFile` has `AddTagUnique()`
   (`src/KnownFile.h:144`) but no removal counterpart, so this needs a small
   `RemoveTag(uint8 id)` beside it. The wire behaviour does not change: the
   publishers already skip absent tags (`src/KnownFile.cpp:1396-1405`).
2. Keep the current behaviour when the probe **fails** (`Probe()` returned false):
   an unreadable file should not wipe a preview that is at least plausible.
3. Consider marking inherited-but-unverified metadata as such, so a file whose
   values came from a peer can be told apart from one that was actually probed.
   That is a design question, not a prerequisite: (1) alone fixes the stated
   contract.

## Acceptance criteria

- A completed download whose local probe returns fewer fields than the search
  hit advertised ends up with only the locally probed fields.
- A completed download whose probe fails entirely keeps its inherited preview.
- Re-probing a file twice with the same content is idempotent.
- No `0`-valued or empty media tag is ever attached or published.

## Out of scope

- Whether inheriting media metadata from search results is a good idea at all;
  it is deliberate (#280) and useful while downloading.
- Which fields the probe extracts, and how it picks the codec. This report is
  about what happens to the values once a re-probe returns them.

---

Line references checked against aMule `55b0b60db`; ffprobe output produced with
ffprobe 8.0.
