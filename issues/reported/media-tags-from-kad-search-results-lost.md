# Bug: the media metadata of a Kad search result never reaches the file — the codec is parsed and thrown away, and length / bitrate are dropped when the download starts

## Summary

A file found through a Kad keyword search loses its media metadata on the way to
the download, in two independent ways, both inside
`CSearch::ProcessResultKeyword()`.

**1. The codec is read off the wire and discarded.** Kad result tags arrive with
string names — `CFileDataIO::ReadTag()` reads the name with `ReadString()` and
never folds a one-character name into a `NameID` (`src/SafeFile.cpp:390-397`),
unlike the ed2k-side `CTag` constructor — which is why the handler matches on
`tag->GetName()`. It declares a local for the codec
(`src/kademlia/kademlia/Search.cpp:1198`) and fills it while walking those tags
(`:1234-1235`):

```cpp
		} else if (tag->GetName() == TAG_MEDIA_CODEC) {
			codec = tag->GetStr();
```

and then never mentions it again. The tag list it builds for the search result
(`:1267-1289`) carries the file format, artist, album, title, length, bitrate and
availability — but no codec:

```cpp
	if (!title.IsEmpty()) {
		taglist.push_back(new CTagString(TAG_MEDIA_TITLE, title));
	}
	if (length) {
		taglist.push_back(new CTagVarInt(TAG_MEDIA_LENGTH, length));
	}
	if (bitrate) {
		taglist.push_back(new CTagVarInt(TAG_MEDIA_BITRATE, bitrate));
	}
```

`codec` occurs exactly twice in the whole file — the declaration and that
assignment. Being a `wxString` rather than a scalar, the assignment is a call with
side effects, so `-Wunused-but-set-variable` does not fire and nothing flags it.
A result that came only from Kad therefore shows an empty Codec column, and the
value never reaches the download either.

**2. Length and bitrate arrive as `uint8`/`uint16`, and the download inherit path
only accepts `uint32`.** The two `CTagVarInt` calls above use no forced bit size,
so the type is chosen from the value (`src/Tag.h:180-196`):

```cpp
	void SizedInit(uint64 value, uint8 forced_bits)
	{
		if (forced_bits) {
			// The bitsize was forced.
			Init(value, forced_bits);
		} else {
			m_uVal = value;
			if (value <= 0xFF) {
				m_uType = TAGTYPE_UINT8;
			} else if (value <= 0xFFFF) {
				m_uType = TAGTYPE_UINT16;
			} else if (value <= 0xFFFFFFFF) {
				m_uType = TAGTYPE_UINT32;
			} else {
				m_uType = TAGTYPE_UINT64;
			}
		}
	}
```

while the inherit table in `CPartFile::CPartFile(CSearchFile *)` matches on an
exact type (`src/PartFile.cpp:184-189`):

```cpp
				{ FT_MEDIA_LENGTH, 3 },
				{ FT_MEDIA_BITRATE, 3 },
				{ FT_MEDIA_CODEC, 2 } };
			for (unsigned int t = 0; t < itemsof(_aMetaTags); ++t) {
				if (pTag.GetType() == _aMetaTags[t].nType &&
					pTag.GetNameID() == _aMetaTags[t].nID) {
```

`TAGTYPE_UINT32` is `0x03`, `TAGTYPE_UINT16` is `0x08` and `TAGTYPE_UINT8` is
`0x09` (`src/include/tags/TagTypes.h:32-39`), so the comparison fails for every
value narrow enough to be compressed — which is all of them in practice:

| Value | Type built | Matches the `== 3` check? |
|---|---|---|
| `length=202` (a song) | `TAGTYPE_UINT8` | no |
| `length=2603` (an episode) | `TAGTYPE_UINT16` | no |
| `bitrate=128` | `TAGTYPE_UINT8` | no |
| `bitrate=1500` | `TAGTYPE_UINT16` | no |
| `length > 65535` (over 18 h) | `TAGTYPE_UINT32` | yes |

The ed2k path does not have this problem, because its publisher forces the width
(`src/KnownFile.cpp:1397` and `:1400`):

```cpp
		tags.push_back(new CTagVarInt(FT_MEDIA_LENGTH, len, 32));
```

so the same file found through an ed2k server keeps its length and bitrate on
download, and the same file found through Kad does not.

## Why length and bitrate still show in the search list

Unlike the codec, they do reach the `CSearchFile`, and nothing on the display path
cares about the integer width. The tag keeps its numeric id across the hand-off:
the name is the one-character form of the id (`TAG_MEDIA_LENGTH` is `wxT("\xD3")`,
`src/include/tags/FileTags.h:110-115`), `CFileDataIO::WriteString()` encodes it as
Latin-1 so it stays a single byte (`src/SafeFile.cpp:313-331`), and `CTag`'s wire
constructor turns a one-byte name back into a `NameID` (`src/Tag.cpp:89-101`).
`CSearchFile` then keeps it through the catch-all in its tag loop
(`src/SearchFile.cpp:104-105`):

```cpp
		default:
			AddTagUnique(tag);
```

and reads go through `CAbstractFile::GetIntTagValue()`
(`src/KnownFile.cpp:209-218`), which accepts any integer width:

```cpp
		if (((*it).GetNameID() == tagname) && (*it).IsInt()) {
```

That is what makes this easy to miss: the length and bitrate are on screen a
second before they are discarded.

## What the user sees

- **Codec:** empty for every Kad search result, and absent from the download.
- **Length and bitrate:** correct in the search list, gone as soon as the download
  starts. With media metadata extraction enabled they reappear at completion, when
  the local probe fills them in; with it disabled they are lost for good, even
  though the network had supplied them.

## Root cause

Two separate slips in the same function, plus one design assumption that only
holds for ed2k:

- the codec branch fills a local that the tag-list builder was never taught to
  read;
- `_aMetaTags` matches an exact `(id, type)` pair, which is a fine way to validate
  a tag when the writer controls the width — as the ed2k publisher does — but the
  Kad path deliberately compresses, so the width at the receiver is a property of
  the value, not of the field.

## Requested change

1. Push the codec into the tag list in `CSearch::ProcessResultKeyword()`
   (`src/kademlia/kademlia/Search.cpp:1267-1289`), next to the other media tags:
   `if (!codec.IsEmpty()) taglist.push_back(new CTagString(TAG_MEDIA_CODEC, codec));`
2. In the inherit table (`src/PartFile.cpp:184-189`), accept any integer type for
   `FT_MEDIA_LENGTH` and `FT_MEDIA_BITRATE` — `pTag.IsInt()` instead of
   `pTag.GetType() == 3` — keeping the string check for `FT_MEDIA_CODEC` and the
   existing "skip zero / skip empty" rules.
3. Apply the same relaxation to the Kad re-publish lookup
   (`src/kademlia/kademlia/Search.cpp:1509-1511`), which asks `GetTag(id, 3)`.
   That one is safe today only because everything reaching a `CKnownFile` locally
   is a `CTagInt32`; it would silently stop publishing the moment a narrower tag
   got stored, which is exactly what (2) makes possible.
4. Do not "fix" (2) by forcing 32 bits on the Kad side. The narrow types are built
   locally by the receiving client, so nothing about the wire format needs to
   change; Kad payloads are size-sensitive, and a receiver that understands only
   one width would still be wrong.

## Acceptance criteria

- A Kad search result whose publisher advertised a codec shows that codec in the
  search list, and the download started from it carries it.
- A Kad search result's length and bitrate survive into the download, for values
  of any magnitude — a three-minute song (`uint8`) as much as a long film
  (`uint16`).
- The same file found through an ed2k server behaves identically.
- A zero-valued or empty media tag is still skipped.
- After completion, a local probe still overrides whatever was inherited.

## Out of scope

- Whether inherited metadata should be trusted at all: this report is only about
  it being lost for reasons unrelated to trust.
- Which fields the probe extracts locally, and how accurate they are.

---

Line references checked against aMule `55b0b60db`. Verified by reading the full
path from the Kad result handler to the part file; not observed on a live Kad
network.
