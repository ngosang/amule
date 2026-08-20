# Bug: Artist / Album / Title never reach anything — they are never extracted, and the one path that does carry them dead-ends in the part file

## Summary

aMule defines six media tags (`src/include/tags/FileTags.h:74-79`):

```c
#define FT_MEDIA_ARTIST 0xD0    // <string>
#define FT_MEDIA_ALBUM 0xD1     // <string>
#define FT_MEDIA_TITLE 0xD2     // <string>
#define FT_MEDIA_LENGTH 0xD3    // <uint32> !!!
#define FT_MEDIA_BITRATE 0xD4   // <uint32>
#define FT_MEDIA_CODEC 0xD5     // <string>
```

Everything that displays or transports them handles all six. The code that
produces them handles three. `Artist`, `Album` and `Title` are empty on every
locally shared file, always, whatever the file contains — and the REST reference
documents them as if they were not (`docs/api/REFERENCE.md:746`):

> \| `artist` / `album` / `title` \| string \| Tag metadata; `""` when the file carries none. \|

Two independent defects produce that:

**1. Nothing extracts them.** `MediaInfo` (`src/MediaProbe.h:37-48`) has exactly
three fields, the probe asks ffprobe for exactly those
(`src/MediaProbe.cpp:492`), and `amule.cpp:2312-2320` attaches exactly those.
Nothing in the core ever writes `FT_MEDIA_ARTIST`, `_ALBUM` or `_TITLE` onto a
file. The only code in the tree that writes those three tags at all is
`src/amule-remote-gui.cpp:3110-3116`, where amulegui rebuilds on its proxy object
whatever the daemon sent it over EC — which, for a locally shared file, is always
empty.

**2. The one path that does carry them stores them where nothing can read
them.** A download inherits media metadata from its search hit through two
branches, one per tag encoding. The string-named branch
(`src/PartFile.cpp:125-135`) inherits all six:

```cpp
} _aMetaTags[] = { { FT_ED2K_MEDIA_ARTIST, 2 },
	{ FT_ED2K_MEDIA_ALBUM, 2 },
	{ FT_ED2K_MEDIA_TITLE, 2 },
	{ FT_ED2K_MEDIA_LENGTH, 2 },
	{ FT_ED2K_MEDIA_BITRATE, 3 },
	{ FT_ED2K_MEDIA_CODEC, 2 } };
```

Those `FT_ED2K_MEDIA_*` constants are the ed2k string names — `"Artist"`,
`"Album"`, `"Title"`, `"length"`, `"bitrate"`, `"codec"`
(`src/include/tags/FileTags.h:138-143`) — not the numeric IDs, and note that
`"length"` is declared as a string there while `FT_MEDIA_LENGTH` is a `uint32`.
The branch pushes each tag into `m_taglist` **under its string name**. The numeric-ID
branch right below it (`src/PartFile.cpp:172-186`) inherits three:

```cpp
} _aMetaTags[] = { { FT_FILETYPE, 2 },
	{ FT_FILEFORMAT, 2 },
	// ... comment omitted ...
	{ FT_MEDIA_LENGTH, 3 },
	{ FT_MEDIA_BITRATE, 3 },
	{ FT_MEDIA_CODEC, 2 } };
```

Every media consumer in the tree looks tags up by **numeric ID**, and the lookup
matches on the ID only:

```cpp
// src/KnownFile.cpp:232-241
const wxString &CAbstractFile::GetStrTagValue(uint8 tagname) const
{
	ArrayOfCTag::const_iterator it = m_taglist.begin();
	for (; it != m_taglist.end(); ++it) {
		if ((*it).GetNameID() == tagname && (*it).IsStr()) {
			return (*it).GetStr();
		}
	}
	return EmptyString;
}
```

A by-name overload exists (`src/KnownFile.cpp:243-252`) and no media consumer
calls it. So everything the first branch inherits is stored in the part file,
written to disk, carried for the lifetime of the download — and read by nobody.

## Who handles what

| Stage | length / bitrate / codec | artist / album / title |
|---|---|---|
| Local extraction (`MediaProbe`) | ✔ | **✘ never** |
| Inherit from a hit, numeric IDs (`src/PartFile.cpp:172-186`) | ✔ | **✘ not in the list** |
| Inherit from a hit, string names (`src/PartFile.cpp:125-135`) | stored unreadable | **stored unreadable** |
| Publish to **ed2k** (`src/KnownFile.cpp:1396-1405`) | ✔ | **✘ only three pushed** |
| Publish to **Kad** (`src/kademlia/kademlia/Search.cpp:1498-1520`) | ✔ | ✔ all six in `_aMetaTags[]` |
| EC → amulegui / Web UI (`src/ECSpecialCoreTags.cpp:359-364`, `:566-587`) | ✔ | ✔ |
| Remote GUI rebuild (`src/amule-remote-gui.cpp:3101-3117`) | ✔ | ✔ |
| File detail dialog (`src/FileDetailDialog.cpp:261-269`) | ✔ | ✔ three labels, permanently blank |
| REST API `media.artist` / `.album` / `.title` | ✔ | ✔ permanently `""` |

aMule *consumes* six and *produces* three: it will display an Artist that a peer
advertises, while its own shared files advertise none.

## Reproducing

**Extraction.** Share a tagged MP3, enable media metadata, wait for the probe,
then read it back:

```sh
curl -s -H "Authorization: Bearer $TOKEN" "http://$HOST/api/v0/shared/$HASH" | jq .media
```

`length_s`, `bitrate` and `codec` are filled. `artist`, `album` and `title` are
`""`, and stay `""` no matter what the file carries.

**Inheritance.** Start a download from an ed2k hit that carries the named tags
and enable the `logPartFile` category. The branch traces what it stored:

```
CPartFile::CPartFile(CSearchFile*): added tag "Artist"="…"
```

The same file, through the REST API or the file detail dialog: `media.artist` is
`""`, the Artist label is blank.

## What ffprobe can give, and the four things that make it non-trivial

All three fields come back for every container tested — mp3, flac, m4a, ogg,
opus, mka, wma — using a build configured with `--disable-everything` plus
demuxers and parsers. But a plain `format_tags=artist,title,album` is wrong in
four measurable ways.

**1. Ogg and Opus keep the tags on the stream, everyone else on the format.**
Vorbis comments belong to the logical stream, so `format_tags` alone loses them
and `stream_tags` alone loses everything else:

```
real.mp3    FORMAT[ TAG:album=… TAG:artist=… TAG:title=… ]  STREAM[ ]
a.flac      FORMAT[ TAG:artist=… TAG:title=… TAG:album=… ]  STREAM[ ]
a.m4a       FORMAT[ TAG:title=… TAG:artist=… TAG:album=… ]  STREAM[ ]
a.ogg       FORMAT[ ]                                       STREAM[ TAG:artist=… TAG:title=… TAG:album=… ]
a.opus      FORMAT[ ]                                       STREAM[ TAG:artist=… TAG:title=… TAG:album=… ]
a.mka       FORMAT[ TAG:title=… TAG:ARTIST=… TAG:ALBUM=… ]  STREAM[ ]
a.wma       FORMAT[ TAG:artist=… TAG:title=… TAG:album=… ]  STREAM[ ]
```

**2. Stream tags on a multi-track video are track labels, not song metadata.**
On a real MKV with German and Spanish audio plus several subtitle tracks:

```
$ ffprobe -v error -show_entries 'stream=codec_name:stream_tags=title,language' \
      -of default=nk=0:nw=1 film.mkv
codec_name=h264
codec_name=eac3
TAG:language=ger
TAG:title=Deutsch
codec_name=eac3
TAG:language=spa
TAG:title=Español (España)
...
```

Merging stream tags blindly would publish `Title=Deutsch` to every peer. Stream
tags may only be read from the audio stream whose codec was selected, and only
when the format section carried nothing.

**3. Matroska emits the keys upper-case.** In the table above, `a.mka` returns
`TAG:ARTIST` and `TAG:ALBUM` but `TAG:title` — three keys, two cases, one file.
ffprobe matches the requested names case-insensitively but prints the container's
own case, so the parser has to compare case-insensitively.

**4. The current output format cannot attribute a tag line.** With
`-of default=nk=0:nw=1` — what `src/MediaProbe.cpp:494` uses — every line is bare
`key=value`, so a `TAG:` line can only be assigned to the format section or to a
given stream by position, and that argument breaks on a file with no
`duration` / `bit_rate` line. Dropping `nw=1` makes ffprobe delimit the sections
and the attribution becomes explicit:

```
[STREAM]
codec_name=vorbis
codec_type=audio
TAG:artist=…
[/STREAM]
[FORMAT]
duration=5.000000
[/FORMAT]
```

## Requested change

**Extract them:**

1. Add `artist`, `album` and `title` to `MediaInfo` (`src/MediaProbe.h:37`) and to
   the event that carries the probe result to the main thread.
2. Extend the entry list (`src/MediaProbe.cpp:492`) with
   `format_tags=artist,title,album` and `stream_tags=artist,title,album`, and drop
   `nw=1` from `-of` so sections are delimited. Prefer the format-level values;
   fall back to the selected audio stream's tags only when the format section had
   none. Compare keys case-insensitively.
3. Attach the three tags in `amule.cpp:2312-2320` alongside the existing ones,
   keeping the existing rule that an empty string is not attached.

**Stop losing the inherited ones:**

4. In the string-named branch (`src/PartFile.cpp:125-135`), convert to the
   canonical numeric tag before pushing: `"Artist"` → `CTagString(FT_MEDIA_ARTIST, …)`,
   `"Album"` → `FT_MEDIA_ALBUM`, `"Title"` → `FT_MEDIA_TITLE`, `"codec"` →
   `FT_MEDIA_CODEC`, `"bitrate"` → `CTagInt32(FT_MEDIA_BITRATE, …)`.
5. Parse `"length"` (`h:mm:ss` / `m:ss`) into seconds and store it as
   `CTagInt32(FT_MEDIA_LENGTH, …)`; `FT_MEDIA_LENGTH` is a `uint32` everywhere
   else. Keep the existing `"0: 0"` / `"0:0"` rejection (`src/PartFile.cpp:145-150`)
   and drop anything else that does not parse rather than storing it raw.
6. Add `FT_MEDIA_ARTIST`, `_ALBUM` and `_TITLE` to the numeric-ID inherit list
   (`src/PartFile.cpp:172-186`), so both branches converge on the same six. Note
   that once (4) normalises the names to IDs the two branches can produce the
   same tag twice for a hit that carries both encodings — today they cannot
   collide because the keys differ — so the push needs `AddTagUnique()`
   semantics rather than a bare `m_taglist.push_back()`.

   If these inherited tags are instead considered too untrustworthy to read,
   delete the string-named branch outright. What should not stay is the current
   middle ground, where it stores data no code can reach.

**Publish them:**

7. Add the three IDs to the ed2k publish list (`src/KnownFile.cpp:1396-1405`),
   the only publisher that still sends three of the six. Kad already
   sends all six and needs no change.

## Acceptance criteria

- A shared MP3 / FLAC / M4A / OGG / OPUS / MKA / WMA carrying tags reports its
  artist, album and title through the REST API, the file detail dialog and
  amulegui.
- A multi-track MKV does **not** report an audio track label (`Deutsch`,
  `English`) as its title.
- A Matroska file whose keys are upper-case is read correctly.
- A file with no tags reports `""` for the three and publishes no tag for them.
- A download started from a hit carrying the string-named tags shows those values
  while it downloads, with `"length"` in `h:mm:ss` form displayed as a duration
  and a malformed `"length"` dropped rather than stored.
- ed2k and Kad publish the same set of media tags for the same file.

## Out of scope

- Additional tags such as `date`, `genre` or `track`: the ed2k protocol has no
  tag IDs for them.
- Whether ed2k servers still relay the string-named form in practice: the branch
  exists, and it should either feed something usable or not exist.

---

Line references checked against aMule `55b0b60db`. ffprobe outputs produced with
ffprobe 8.0; test files built with FFmpeg 7.1.
