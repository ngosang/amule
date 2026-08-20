# Searching by media metadata is not implemented: the code is `#if 0`, while aMule already publishes the tags and already answers such searches for others

## Summary

aMule 3.1 extracts media metadata from shared files, publishes it to ed2k and to
Kad, and its Kad node correctly matches metadata search terms *for other clients*.
The one thing its own users cannot do is search by it. There is no minimum length,
minimum bitrate, codec, title, album or artist filter anywhere — not in the GUI,
not over EC, not in the REST API.

The code for it exists and is compiled out. Three blocks in
`CSearchList::CreateSearchData()` are wrapped in `#if 0` behind a TODO
(`src/SearchList.cpp:1564-1614`, `:1651-1694`, `:1733-1763`):

```cpp
// #warning TODO - I keep this here, ready if we ever allow such searches...
#if 0
		if (complete > 0){
			if (++iParameterCount < parametercount) {
				target.WriteBooleanAND();
			}
			target.WriteMetaDataSearchParam(FT_COMPLETE_SOURCES, ED2K_SEARCH_OP_GREATER, complete);
		}
```

The scaffolding is stale enough that flipping the `#if 0` would not compile:
`complete`, `minBitrate`, `minLength`, `codec`, `title`, `album` and `artist` are
not declared anywhere in the function, and `CSearchParams`
(`src/SearchList.h:86-101`) has no fields for them — it carries only
`searchString`, `strKeyword`, `typeText`, `extension`, `minSize`, `maxSize` and
`availability`.

## The asymmetry this creates

Everything except the query side is already in place.

- **We publish the data.** `CKnownFile::CreateOfferedFilePacket()`
  (`src/KnownFile.cpp:1396-1405`) sends length, bitrate and codec to the server and
  to peers, and `CSearch::PreparePacketForTags()`
  (`src/kademlia/kademlia/Search.cpp:1497-1530`) publishes to Kad.
- **We answer other people's metadata searches.** `CKeyEntry::SearchTermsMatch()`
  (`src/kademlia/kademlia/Entry.cpp:214-350`) implements the string `MetaTag` case
  and the full set of comparisons — `OpGreaterEqual`, `OpLessEqual`, `OpGreater`,
  `OpLess`, `OpEqual`, `OpNotEqual` — resolving integers through
  `CEntry::GetIntTagValue()` (`src/kademlia/kademlia/Entry.cpp:80-97`), which
  matches on `IsInt()` and therefore copes with any integer width.
- **We display the data.** Length, Bitrate and Codec are real columns of the
  search results list (`src/SearchListCtrl.cpp:149-166`), with their own sort
  comparators.

So an aMule node indexes and serves metadata queries it cannot make.

## eMule has it, and is a usable reference

eMule implements the whole feature, and its shape is worth copying because it
avoids a trap aMule's dead code walks into.

**The parameters exist as first-class search fields** (`SearchParams.h:56-78`):

```cpp
	UINT uComplete;
	CString strCodec;
	ULONG ulMinBitrate;
	ULONG ulMinLength;
	CString strTitle;
	CString strAlbum;
	CString strArtist;
```

They are rows of the search dialog's option grid, declared alongside the size and
availability rows that aMule already has (`SearchParamsWnd.h:8-21`):

```cpp
typedef enum EOptsRows
{
	orMinSize,
	orMaxSize,
	orAvailability,
	orCompleteSources,
	orExtension,
	orCodec,
	orBitrate,
	orLength,
	orTitle,
	orAlbum,
	orArtist
};
```

They are read back with validation and caps — bitrate clamped to 1000000, length
to 24 h (`SearchParamsWnd.cpp:1056-1125`) — and emitted in `GetSearchPacket()`
(`SearchResultsWnd.cpp:1095-1111`):

```cpp
	if (pParams->ulMinBitrate > 0)
		AddAndAttr(FT_MEDIA_BITRATE, ED2K_SEARCH_OP_GREATER_EQUAL, pParams->ulMinBitrate);

	if (pParams->ulMinLength > 0)
		AddAndAttr(FT_MEDIA_LENGTH, ED2K_SEARCH_OP_GREATER_EQUAL, pParams->ulMinLength);

	if (!pParams->strCodec.IsEmpty())
		AddAndAttr(FT_MEDIA_CODEC, pParams->strCodec);

	if (!pParams->strTitle.IsEmpty())
		AddAndAttr(FT_MEDIA_TITLE, pParams->strTitle);

	if (!pParams->strAlbum.IsEmpty())
		AddAndAttr(FT_MEDIA_ALBUM, pParams->strAlbum);

	if (!pParams->strArtist.IsEmpty())
		AddAndAttr(FT_MEDIA_ARTIST, pParams->strArtist);
```

Three details differ from aMule's dead code and matter:

1. **eMule uses the numeric tag ids** (`FT_MEDIA_*`) for both ed2k and Kad. The
   dead aMule code uses the ed2k *string* names for ed2k
   (`FT_ED2K_MEDIA_LENGTH` is `"length"`, `src/include/tags/FileTags.h:138-143`)
   and the one-character forms for Kad. The one-character form and the numeric id
   serialise to the same bytes, so the Kad half agrees; the ed2k half does not.
2. **eMule compares with `ED2K_SEARCH_OP_GREATER_EQUAL`**, the dead code with
   `ED2K_SEARCH_OP_GREATER`.
3. **eMule builds an expression tree instead of counting parameters**
   (`SearchResultsWnd.cpp:994-1006`):

```cpp
static void AddAndAttr(UINT uTag, UINT uOpr, uint64 ullVal)
{
	s_SearchExpr2.m_aExpr.InsertAt(0, CSearchAttr(uTag, uOpr, ullVal));
	if (s_SearchExpr2.m_aExpr.GetCount() > 1)
		s_SearchExpr2.m_aExpr.InsertAt(0, CSearchAttr(SEARCHOPTOK_AND));
}
```

Each attribute inserts its own `AND` as it is added, and the finished tree is
walked once to emit the packet. Nothing has to know the total in advance.

## The trap in the current aMule structure

aMule emits the boolean operators from a count computed *before* the parameters
are written:

```cpp
	// src/SearchList.cpp:1439-1449
	unsigned int parametercount = 0;
	if (!params.typeText.IsEmpty())
		++parametercount;
	if (params.minSize > 0)
		++parametercount;
	if (params.maxSize > 0)
		++parametercount;
	if (params.availability > 0)
		++parametercount;
	if (!params.extension.IsEmpty())
		++parametercount;
```

plus `parametercount += _SearchExpr.m_aExpr.GetCount();` (`:1499`). That count is
correct today precisely *because* the media parameters are compiled out. Every
disabled block still contains `if (++iParameterCount < parametercount)`, so
enabling them without extending the count would emit fewer `AND` operators than
there are parameters, producing a malformed search expression — and tripping the
function's own `wxASSERT(iParameterCount == parametercount)` (`:1618`) in debug
builds.

Adding the media parameters to the pre-count would work, but it keeps an
invariant that has to hold between one counting site and two writing branches
150 lines below it. Adopting eMule's incremental tree removes the invariant
instead of extending it.

## Requested change

1. Add the fields to `CSearchParams` (`src/SearchList.h:86-101`): minimum length,
   minimum bitrate, codec, title, album, artist. Complete sources is the same
   mechanism and is disabled alongside them; include it or drop the dead block.
2. Replace the `parametercount` scheme in `CSearchList::CreateSearchData()` with an
   incrementally built expression, in the shape of eMule's `AddAndAttr()`, and
   delete the three `#if 0` blocks rather than reviving them in place.
3. Emit the terms with the numeric tag ids and `ED2K_SEARCH_OP_GREATER_EQUAL`, as
   eMule does, for both ed2k and Kad.
4. Expose the fields in the GUI search panel, alongside the existing extension /
   size / availability filters.
5. Carry them over EC. `CEC_Search_Tag`
   (`src/libs/ec/cpp/ECSpecialTags.h:715-730`) currently transports name, type,
   file type, extension, availability, min size and max size; it needs the new
   ones so amulegui and amuleapi can drive a metadata search against a remote
   daemon.
6. Accept them in the REST search endpoint, whose body is today `query`, `type`,
   `file_type`, `extension`, `min_size`, `max_size`, `min_avail`
   (`src/webapi/Api.cpp:9724-9731`, documented at
   `docs/api/REFERENCE.md:2442-2460`), and document the additions there.
7. Validate the inputs the way eMule does: reject unparseable values, and accept a
   length as `h:mm:ss` as well as in seconds.

## Acceptance criteria

- A search with a minimum length, minimum bitrate, codec, title, album or artist
  filter returns only matching results, on both ed2k and Kad.
- The same search can be issued from aMule, from amulegui against a remote daemon,
  and from the REST API.
- A search with no metadata filter produces the exact same packet it produces
  today.
- A search combining a metadata filter with an `OR` / `NOT` expression produces a
  well-formed expression, and the debug assertion on the parameter count either
  holds or no longer exists.
- Invalid input (an unparseable bitrate, a malformed length) is reported to the
  user rather than silently dropped or sent as zero.

## Out of scope

- Maximum length / maximum bitrate filters: eMule offers only minimums, and the
  protocol operators would allow both, but this request is for parity first.
- How the metadata is extracted from local files, and how it is published.

---

Line references checked against aMule `55b0b60db` and the eMule source in
`/home/kizar/Downloads/emule-code`.
