# Bug: embedded cover art is advertised as the file's codec — an MP3 with artwork publishes `mjpeg`

## Summary

`MediaProbe::Probe()` picks the first **video** stream ffprobe reports and
publishes its codec as `FT_MEDIA_CODEC`. ffprobe exposes embedded cover art as a
video stream, so for an audio file with artwork that stream is the *only* video
stream and it always wins: the file is advertised as `mjpeg` (or `png`) instead
of `mp3`, `flac`, `aac`…

The tag is not cosmetic. It goes out on the wire to every peer
(`src/KnownFile.cpp:1402-1404`, in the tag list built for search answers and
publishing), and back into our own clients through
`EC_TAG_KNOWNFILE_MEDIA_CODEC` (`src/ECSpecialCoreTags.cpp:361`), where it fills
the Codec column of the search and shared-files lists and the file-detail dialog.

This is not an edge case. On a plain music folder, **7 of 9 MP3s** were affected:

```
$ for f in *.mp3; do printf '%s\n  ' "$f"; ffprobe -v error \
      -show_entries 'stream=codec_name,codec_type:stream_disposition=attached_pic' \
      -of csv=p=0 "$f" | paste -sd' '; done
01. Taylor Swift - The Fate of Ophelia.mp3
  mp3,audio,0 mjpeg,video,1
45 Harry Styles - Watermelon Sugar.mp3
  mp3,audio,0 mjpeg,video,1
Harry Belafonte - Somewhere Over The Rainbow-What A Wonderful World.mp3
  mp3,audio,0
Taylor Swift - Anti-Hero.mp3
  mp3,audio,0 mjpeg,video,1
Taylor Swift - Love Story.mp3
  mp3,audio,0
Taylor Swift - Shake It Off.mp3
  mp3,audio,0 mjpeg,video,1
```

The third field is `attached_pic`: a `1` on the `mjpeg` stream is the cover.

Length and bitrate are correct — they come from the `format` section, not from
the streams. Only the codec is wrong.

## Reproducing

Any MP3 with an ID3v2 `APIC` frame (i.e. almost any MP3 from a tagged library).
With media metadata enabled and the file shared:

```
$ ffprobe -v error -show_entries 'format=duration,bit_rate:stream=codec_name,codec_type' \
      -of default=nk=0:nw=1 'Taylor Swift - Anti-Hero.mp3'
codec_name=mp3
codec_type=audio
codec_name=mjpeg
codec_type=video
duration=202.379400
bit_rate=325052
```

The second stream is the cover art. aMule logs a successful probe, and its codec
is the one persisted and published:

```
 2026-08-22 19:39:01: Extracting media metadata with ffprobe: /downloads/incoming/m.mp3
$ strings ~/.aMule/known.met | grep -x mjpeg
mjpeg
```

Expected `mp3`, got `mjpeg`.

## Root cause

Two places, both in `src/MediaProbe.cpp`.

**1. The probe never asks for the flag that identifies cover art** (line 492):

```cpp
argv.Add(wxT("format=duration,bit_rate:stream=codec_name,codec_type"));
```

FFmpeg marks these streams with `AV_DISPOSITION_ATTACHED_PIC`, which ffprobe
exports as the `attached_pic` field of its `stream_disposition` section. Nothing
else in ffprobe's output distinguishes a 600×600 JPEG thumbnail from a real
video track: both are `codec_type=video`.

That flag is a reliable signal rather than a per-demuxer convention. In the whole
of libavformat it has exactly two origins, and both set it unconditionally. Every
cover-art path goes through the shared helper `ff_add_attached_pic()`, called
from the three shared tag parsers (`id3v2.c`, `flac_picture.c`, `apetag.c`) and
from the `asf`, `matroska`, `mov` and `wtv` demuxers:

```c
// libavformat/demux_utils.c:129
st->disposition         |= AV_DISPOSITION_ATTACHED_PIC;
st->codecpar->codec_type = AVMEDIA_TYPE_VIDEO;
```

and the MOV demuxer sets it directly in one further place, for timed-thumbnail
tracks (`libavformat/mov.c:9702`), which are not cover art but are equally not
the file's video content.

FFmpeg uses exactly the same test for its own “real video streams” selector: the
`V` stream specifier is plain `AVMEDIA_TYPE_VIDEO` plus “not attached_pic”, and
nothing else (`libavformat/avformat.c:472` and `:480`).

**2. The selection takes the first video stream unconditionally**
(lines 537-570):

```cpp
// Codec selection: the first video track's codec, else the first audio
// track's. Subtitle / data streams (e.g. a leading subrip track in an
// mkv) never win, so we don't advertise "subrip" as a file's codec.
...
} else if (key == wxT("codec_type")) {
        if (value == wxT("video") && videoCodec.IsEmpty()) {
                videoCodec = pendingCodec;
        } else if (value == wxT("audio") && audioCodec.IsEmpty()) {
                audioCodec = pendingCodec;
        }
```

The comment shows the intent — subtitle and data streams were deliberately
excluded — but attached pictures were not considered, and they are the one
non-content stream that claims `codec_type=video`.

## Scope

Only files whose extension maps to `ED2KFT_AUDIO` or `ED2KFT_VIDEO` are probed
at all (`src/SharedFileList.cpp:783`), so the blast radius is that list
intersected with the FFmpeg demuxers that can create an attached picture.

Every FFmpeg demuxer that calls `ff_add_attached_pic()` (checked against
FFmpeg n8.0):

| Source of the picture | Demuxer | aMule extensions reached |
|---|---|---|
| ID3v2 `APIC`, generic path (`libavformat/demux.c:323-330`, gated to the `mp3`, `aac`, `tta` and `wav` demuxers) | mp3, aac, wav | `.mp3` `.mp2` `.mpa` `.m1a` `.m2a` `.aac` `.wav` |
| ID3v2 `APIC`, per-demuxer | aiffdec, dsfdec | `.aif` `.aifc` `.aiff` `.dsf` |
| FLAC `PICTURE` / `METADATA_BLOCK_PICTURE` | flacdec, oggparsevorbis | `.flac` `.ogg` `.oga` `.opus` |
| APE tag cover | ape, mpc, mpc8, wvdec, aacdec | `.ape` `.mpc` `.mpp` `.wv` |
| MOV `covr` atom | mov | `.mp4` `.m4a` `.m4b` `.mov` `.m4v` `.qt` `.3gp` `.3g2` `.3gpp` `.3gp2` `.f4v` `.hdmov` `.movie` |
| Matroska attachment with an image MIME type (`libavformat/matroskadec.c:3406-3416`) | matroska, webm | `.mkv` `.mka` `.webm` `.weba` |
| ASF `WM/Picture` attribute (`libavformat/asf.c:146` → `asf_read_picture()` → `:106`) | asf | `.wma` `.wmv` `.asf` `.wm` `.dvr-ms` |

(Extensions the demuxer declares itself, plus the ones it opens by content
probing — FFmpeg does not need the extension to match.)

The two cases behave differently:

- **Audio files: always wrong.** The cover is the only video stream, so it is
  always the one picked. Every tagged music file in a shared library is affected.
- **Video files: not affected in practice, but only by accident.** In every file
  tested the attached picture was reported *after* the real streams, so the video
  codec wins — including one MP4 where the cover was deliberately muxed as the
  first stream, which the MOV demuxer still reported last. The selection
  therefore depends on where each demuxer happens to place the picture, which is
  not something the format guarantees or that ffprobe documents. The fix removes
  the dependency; it does not change today's result for video.

## Requested change

Ask ffprobe for the flag and skip the streams that carry it.

**1.** Extend the entry list (`src/MediaProbe.cpp:492`):

```cpp
argv.Add(wxT("format=duration,bit_rate:stream=codec_name,codec_type:stream_disposition=attached_pic"));
```

With `-of default=nk=0:nw=1` the subsection field is printed after that stream's
own fields, with an uppercase `DISPOSITION:` prefix:

```
codec_name=mp3
codec_type=audio
DISPOSITION:attached_pic=0
codec_name=mjpeg
codec_type=video
DISPOSITION:attached_pic=1
duration=202.379400
bit_rate=325052
```

**2.** The disposition now arrives *after* `codec_type`, so the codec can no
longer be committed on the `codec_type` line. Buffer the stream and flush it when
the next one starts — `codec_name` is always the first field of a stream:

```cpp
	wxString videoCodec, audioCodec;
	wxString pendingCodec, pendingType;
	bool pendingAttachedPic = false;

	// Commit the buffered stream. Cover art (ID3 APIC, FLAC PICTURE, MOV covr,
	// Matroska image attachments, ...) is reported by ffprobe as a regular
	// video stream and would otherwise be advertised as the file's codec: an
	// MP3 with artwork would publish "mjpeg" instead of "mp3".
	auto flushStream = [&]() {
		if (!pendingCodec.IsEmpty() && !pendingAttachedPic) {
			if (pendingType == wxT("video") && videoCodec.IsEmpty()) {
				videoCodec = pendingCodec;
			} else if (pendingType == wxT("audio") && audioCodec.IsEmpty()) {
				audioCodec = pendingCodec;
			}
		}
		pendingCodec.clear();
		pendingType.clear();
		pendingAttachedPic = false;
	};

	for (const wxString &line : stdout_lines) {
		...
		} else if (key == wxT("codec_name")) {
			flushStream();
			pendingCodec = value;
		} else if (key == wxT("codec_type")) {
			pendingType = value;
		} else if (key == wxT("DISPOSITION:attached_pic")) {
			pendingAttachedPic = (value == wxT("1"));
		}
	}
	flushStream();
```

Flushing on the *next* `codec_name` rather than on the disposition line is
deliberate: a stream that never gets a `DISPOSITION:attached_pic` line is still
counted, as a non-attached stream, instead of being dropped silently.

The comment block at lines 479-487 documents the field order and has to be
updated with it.

### Why not `-select_streams V`

The uppercase `V` specifier means exactly "video streams that are not attached
pictures", which would solve it without any parsing change — but it selects
*only* video, and the probe needs the audio stream too for audio-only files.
That would mean two ffprobe executions per file instead of one.

### The `-show_entries` compatibility question

Worth knowing before merging, because the two halves behave differently.

An unknown **section** name is fatal — ffprobe refuses the option and exits
non-zero, which `Probe()` reports as a failed probe:

```
$ ffprobe -show_entries 'format=duration:bogus_section=x' file.wav
No match for section 'bogus_section'
Failed to set value 'format=duration:bogus_section=x' for option 'show_entries': Invalid argument
$ echo $?
1
```

An unknown **field** inside a known section is silently ignored:

```
$ ffprobe -v error -show_entries 'stream=codec_name:stream_disposition=attached_pic,bogus_field' \
      -of default=nk=0:nw=1 a.mp3
codec_name=mp3
DISPOSITION:attached_pic=0
codec_name=mjpeg
DISPOSITION:attached_pic=1
$ echo $?
0
```

So the only compatibility question is the `stream_disposition` section name
itself. It is unconditional in `fftools/ffprobe.c:314`
(`.unique_name = "stream_disposition"`), and the ffprobe path is user-configurable
(*Preferences → Files → Path to ffprobe*), so it is worth confirming against the
oldest ffprobe the project intends to support.

### Why `attached_pic` alone, and not the other dispositions

`timed_thumbnails` needs no separate check: the MOV demuxer always sets it
*together* with `AV_DISPOSITION_ATTACHED_PIC` (`libavformat/mov.c:9702`), so those
tracks are already skipped. `still_image` is not cover art at all — the MPEG-TS
demuxer sets it from the video stream descriptor (`libavformat/mpegts.c:1849`) for
a stream that really is the file's video content, and FFmpeg's own `V` specifier
does not exclude it either.

## Verification

Files built with FFmpeg 7.1, each carrying an embedded cover, probed with the
proposed entry list and run through both the current and the proposed selection:

| File | Streams reported (`codec/type`, `PIC` = attached_pic) | Current | With the fix |
|---|---|---|---|
| `a.mp3` (ID3v2 APIC) | `mp3/a` `mjpeg/v/PIC` | `mjpeg` | **`mp3`** |
| `a.flac` (PICTURE block) | `flac/a` `mjpeg/v/PIC` | `mjpeg` | **`flac`** |
| `a.m4a` (MOV `covr`) | `aac/a` `mjpeg/v/PIC` | `mjpeg` | **`aac`** |
| `a.ogg` (METADATA_BLOCK_PICTURE) | `vorbis/a` `mjpeg/v/PIC` | `mjpeg` | **`vorbis`** |
| `a.opus` (METADATA_BLOCK_PICTURE) | `opus/a` `mjpeg/v/PIC` | `mjpeg` | **`opus`** |
| `a.aiff` (ID3v2 APIC) | `pcm_s16be/a` `mjpeg/v/PIC` | `mjpeg` | **`pcm_s16be`** |
| `a.mka` (image attachment) | `vorbis/a` `mjpeg/v/PIC` | `mjpeg` | **`vorbis`** |
| real-world tagged MP3 | `mp3/a` `mjpeg/v/PIC` | `mjpeg` | **`mp3`** |
| `v_cover_last.mp4` | `h264/v` `aac/a` `mjpeg/v/PIC` | `h264` | `h264` |
| `v_cover_first.mp4` (cover muxed as stream 0) | `h264/v` `aac/a` `mjpeg/v/PIC` | `h264` | `h264` |
| `v_attach.mkv` (image attachment) | `h264/v` `aac/a` `mjpeg/v/PIC` | `h264` | `h264` |

Note the `v_cover_first.mp4` row: the cover was muxed as the *first* stream and
the MOV demuxer still reported it last, which is the ordering behaviour described
under Scope.

ASF is the one row that could not be produced as a file: FFmpeg has no muxer for
the `WM/Picture` attribute, so a generated `.wma` gets a real JPEG *video track*
instead of cover art. The demuxer side is unambiguous in the source
(`asf.c:146` → `asf_read_picture()` → `ff_add_attached_pic()` at `asf.c:106`), and
that helper is the same choke point as every other format above.

### Known limitation

An image muxed as a **genuine video track**, with no `attached_pic` flag, stays
indistinguishable from real video and is still reported as the file's codec:

```
$ ffprobe -v error -show_entries 'stream=codec_name,codec_type:stream_disposition=attached_pic' \
      -of csv=p=0 v_fakecover2.mkv
mjpeg,video,0
h264,video,0
aac,audio,0
```

The first stream is a single-frame JPEG muxed as an ordinary video track: no
`attached_pic`, so nothing tells it apart from the real `h264` track.

No disposition-based fix can catch that, and neither can FFmpeg's own `V`
specifier. It is also not how cover art is stored by any tagger — the file above
had to be built by hand with `-c:v mjpeg`; Matroska uses attachments and MP4 uses
the `covr` atom, both of which the fix handles. Distinguishing it would need a
heuristic (single-frame tracks, `nb_frames=1`, duration far below the file's),
which is out of proportion to the case.

## Acceptance criteria

- An MP3 with an embedded `APIC` cover publishes `mp3`, not `mjpeg`.
- A FLAC with a `PICTURE` block publishes `flac`; an M4A with a `covr` atom
  publishes `aac`.
- An MP4 with h264 video and aac audio still publishes `h264`.
- An MKV carrying a `png` image attachment still publishes the real video codec,
  whatever position the attachment holds in the stream list.
- Length and bitrate are unchanged in all of the above.
- A stream whose `DISPOSITION:attached_pic` line is missing is still considered
  for codec selection.

## Out of scope

- Preferring video over audio in general is correct and stays as it is; only
  attached pictures are excluded.
- Existing shared files keep the codec already stored in `known.met`. Whether the
  fix should force a re-probe of files whose stored codec is an image codec
  (`mjpeg`, `png`, `bmp`, `gif`, `webp`) is a separate decision — without it, a
  library tagged by the current code stays wrong until each file is re-added.

---

Line references checked against aMule `55b0b60db` and FFmpeg `n8.0`; the probe
outputs were produced with ffprobe 8.0 and the test files with FFmpeg 7.1.
