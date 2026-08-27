# amuleapi: one-pass naming cleanup of the whole REST surface (paths, query params, JSON keys)

## Summary

`/api/v0/` grew endpoint by endpoint, and the names grew with it. A full
inventory of the surface — every route in `src/webapi/Api.cpp`, every key written
by the `Write*Object` serializers, every preference row in
`src/webapi/PrefsSchema.cpp`, every SSE payload in `src/webapi/EventDiff.cpp` —
turns up a consistent set of problems:

- **Numbers without units.** `size`, `size_done`, `last_upload`,
  `download_active_time` and `lost_to_corruption` are bytes, bytes, a unix
  timestamp, seconds and bytes. Nothing in the names says so, and `saved_by_ich`
  sitting between two of them is a count of *packets*.
- **Booleans that do not read as booleans**, and one field that looks like a
  boolean but is a counter: `uploading` on `GET /shared` is *the number of clients
  currently downloading that file*.
- **The same concept under different names** on neighbouring endpoints:
  `xfer.up_total` / `total_uploaded`, `count` / `total`, `exp` / `expires_at`,
  `kind` / `type`, `obfuscation` / `obfuscation_status`.
- **Internal vocabulary in the public contract:** `xfer`, `met_file`,
  `partmet_id`, `mmap`, `secident`, `core_tweaks`, `ip2country`, `raw`, `enum`.
- **Fields nobody can decode without reading C++:** `dl_up_modifier`,
  `saved_by_ich`, `upnp_tcp_port`, `start_next_paused`, `hashing_progress`
  (a part *count*, not a percentage).
- **Three words for the remote party:** `client`, `peer` and `source`, used
  interchangeably in keys, paths, enum values and prose.

`/api/v0/` is experimental and has no consumers outside this repository — the
Web UI in `src/webapi/static` and the curl tests in
`unittests/curl-tests/amuleapi` are the only callers — so this is the moment to
fix the names in place, in one pass, before anything external depends on them.

Written against commit `c80a7627a` and re-verified against `43c1dad16`. The
inline `File.cpp:NNN` references are from the original tree and have drifted a
little since; the **writer/serializer function names are the durable reference**
(and `issues/inventory/API_INVENTORY.md`, regenerated at `43c1dad16`, carries
the current line for each). This file absorbed an earlier, narrower write-up
that covered only the units and the duplicate names (§1's `_bytes` / `_seconds`
/ `_at` suffixes, the `bps` question in R2, `uploading`, `hashing_progress`,
`xfer`, `count`/`total`, `exp`/`expires_at`, and the internal vocabulary now
handled by R8) — everything it argued is below.

**Bugs and design defects are tracked separately.** This file is names only.
What is *wrong* rather than badly spelled is in
[`api-protocol-and-correctness-bugs.md`](api-protocol-and-correctness-bugs.md),
and what is merely inconsistent is in
[`api-design-inconsistencies.md`](api-design-inconsistencies.md). The three
files share one pass: the renames below rewrite the same serializers those two
ask to change, so landing them apart touches every writer twice.

The tables below list only the renames still open. Everything the earlier passes
resolved — the omitted-vs-null convention, the bulk/list envelopes, the
collection-action paths, the error-code catalog, and the handful of renames that
did land (`firewalled_tcp`, `lan_mode`, the three `core_tweaks.*_minutes`,
`?status=`) — is gone from here.

This issue is **naming only**. No new data is read from the daemon and no EC
change is required; every rename is a key string in a serializer, a parser
branch, a JS property and a doc line.

**The result ships as `/api/v1/`.** `docs/api/REFERENCE.md:5` promises that
*"`/api/v0/` is frozen against any backwards-incompatible change"*, and this
issue is one giant backwards-incompatible change. Rather than break that
promise, honour it by demotion: every rename lands under `/api/v0/` while the
surface is still unpublished, and the **final commit of the staging sequence
renames the prefix to `/api/v1/`** — routes, docs, Web UI base path, curl
tests — and deletes v0. No alias, no coexistence: v0 never existed as a stable
surface, and v1 is born already clean. Anything else (v0+v1 side by side, or
breaking v0 in place and still calling it v0) contradicts the documented
policy.

## Naming rules to adopt

Write these down in `docs/api/REFERENCE.md` so the next endpoint does not have to
re-litigate them.

| # | Rule |
|---|---|
| **R1** | `snake_case` for every path segment, query parameter and JSON key. The only violation today is the path `/logs/serverinfo`. |
| **R2** | **Units live in the name.** `_bytes`, `_bps` (**bytes** per second), `_kbps` (**1024 bytes** per second — the unit the daemon itself stores), `_seconds`, `_minutes`, `_ms`, `_percent` (always 0–100). A bare number is only acceptable when it is a dimensionless count. The one genuine bit rate on the surface — the media bitrate ffprobe reports — is `_kbits`, because `ParseBitrateKbps` (`MediaProbe.cpp:434-450`) divides ffprobe's bits/second by **1000** and so cannot borrow either byte spelling. `_bps` goes against networking convention, where `bps` is bits, so the reference must carry a literal numeric example beside the definition (`speed_bps: 524288` is 512 KiB/s), not just the sentence; **if it does not, this rule has failed and the long spelling wins.** `b` is a byte and `k` is 1024, throughout, and both halves of that are stated in the same sentence as the example. An IEC-style `_kibps` was tried and reverted: it mixes a loose local convention (`b` = byte, which is not SI) with a strict standard one (`i` = 1024) inside one token, and `kibps` is not IEC notation for anything either — the correct IEC spelling is `KiB/s`. Either the whole token is a documented local convention or none of it is. The error it would have prevented is also small: a client assuming `k` = 1000 sets a bandwidth *limit* 2.4% off, which is invisible in practice, unlike the 8× a mis-read `_bps` puts on a displayed speed. **Two alternatives were considered and rejected.** *Spell it out* — `speed_bytes_per_second` — is unambiguous but buys nothing the numeric example does not, at 13 more characters on the most-read key in the API. *Convert the values to bits* so `bps` means what a network engineer expects does not survive contact with the payload: `GET /downloads/{hash}` returns `size` and `size_done` in bytes beside `speed_bps`, and `(size - size_done) / speed` is the object's most natural computation, so a bit-valued rate would make two adjacent, identical-looking fields differ by 8× with nothing on screen to say so — a worse trap than a name, because a name is visible. Every other quantity on the surface is bytes (`total_uploaded`, `lost_to_corruption`, `session.download_bytes`, and `/stats/graphs`' `unit: "bytes_per_second"`, whose points match `status.speeds.download_bps` value for value), so the rate would be the lone exception. |
| **R3** | **Timestamps are integer unix seconds and end in `_at`.** One representation, not two: drop the parallel ISO-8601 twins (`expires_at` + `expires_at_unix` → a single `expires_at`). Formatting is a client concern, exactly as the reference already says about numbers. |
| **R4** | **Booleans read as predicates:** `is_*`, `has_*`, `can_*`, `*_enabled`, `*_supported`. Never a bare adjective (`static`, `failed`), never a bare verb (`uploading`, `reconnect`), and never a field that holds a count. |
| **R5** | **Counts end in `_count`** — except inside an object that already names the thing being counted, where the parent carries it (`sources.total`, `sources.transferring`). The pagination envelope keeps `total` for "matching items before the window". |
| **R6** | **One concept, one key, everywhere.** The same quantity must not be `xfer.up_total` on one resource and `total_uploaded` on the next. |
| **R7** | **A `sort` value *is* the response key it orders by**, spelled identically, dotted for nested keys: `sort=speed_bps`, `sort=ping_ms`, `sort=size_bytes`, `sort=sources.total`. No stripped suffixes, no per-endpoint mapping table to keep in sync, and a field rename can never orphan a sort value. |
| **R8** | **No implementation vocabulary in public names.** EC tag names, C++ member names, aMule config-file section names and on-disk format details (`.met`) stay internal. Protocol terms that aMule's own UI shows the user — `ed2k`, `kad`, `a4af`, `ich`, `aich`, `ecid`, `mmap` — stay, and get one expansion in the reference. |
| **R9** | **A writable field accepts the values the same field returns.** Where a write is really a command (`status: "resumed"`), it belongs in a differently-named key (`action`), not in the read field's name. |
| **R10** | **Always emit the key.** Unknown/absent values are `null`, not "field omitted" — a client should never have to distinguish "absent" from "zero" by probing. |
| **R11** | **Group by quantity, not by scope.** A sub-object earns its place when it groups *different* quantities (`sources`, `progress`, `media`). One quantity split by time window does not: the window belongs in the key (`uploaded_bytes_session` / `uploaded_bytes_total`), not in a wrapper (`xfer.session`). This is why `sources.total` stays nested below while `xfer`, `requests` and `accepts` are flattened. |
| **R12** | **One word for the remote party: `client`.** The API says `client` everywhere — `/clients`, `client_ecid`, `client_added`, `…/{hash}/clients`, `/clients/{ecid}/messages`. **`peer` is not used at all**, in a key, a path or an enum value. **`source` is not a synonym for it**: a source is a client *in a role with respect to one file* — one that can serve that file to us — so it survives only where that relation is what is being counted or described (`sources.total`, `complete_source_count`, `source_origin`, `source_ecids`). Renaming those to `clients.*` would make them lie: a file's clients include the ones downloading **from** us, which its sources do not. The rule governs the **contract** — keys, paths, enum values — and the reference prose that explains it; Web UI labels are free to mirror the desktop's wording, where the Shared Files panel is called *Peers*. |

## 1. Renames

### 1.1 Downloads — `GET /downloads`, `GET /downloads/{hash}`

`WriteDownloadObject`, `Api.cpp:2752`. The list-level keys ship
unchanged in the `download_added` / `download_updated` SSE payloads
(`ToJsonDownloadEvent`, `EventDiff.cpp:109`).

| current | new | why |
|---|---|---|
| `size` | `size_bytes` | R2 |
| `size_done` | `completed_bytes` | R2. `done` vs `xfer` is a real distinction the names hide: this one is `GetCompletedSize()` (`PartFile.h:565`) — file size minus gaps, i.e. **bytes of the file present on disk**. Do *not* call it `downloaded_bytes`; that reads as the wire figure, which is the other field |
| `size_xfer` | `transferred_bytes` | R2/R8 — `xfer` is not a word. This is `GetTransferred()` (`PartFile.h:195`), **bytes received over the wire**; it differs from `completed_bytes` by exactly the compression gain and the corruption loss the two fields below report (`PartFile.cpp:796-801`). The reference should say so |
| `sources.not_current` | `sources.unavailable` | it counts sources that are neither queued, downloading nor connected; "not current" is a double negative for "not usable right now" |
| `sources.total` / `sources.transferring` / `sources.a4af` | *(keep)* | R5 — the parent object already says what is being counted |
| `progress.percent` | *(keep)* | but document the 0–100 range explicitly |
| `progress.parts[].state: "incomplete"` | `"pending"` | it means "we lack it, a source has it" |
| `progress.parts[].state: "missing"` | `"unavailable"` | it means "we lack it and no source has it" |
| `priority_auto` | `is_priority_auto` | R4 |
| `a4af_auto` | `is_a4af_auto` | R4 |
| `category` | `category_index` | a bare integer named after a string-ish concept; it is the index into `GET /categories` |
| `hashing_progress` | `hashed_part_count` | **the current name lies** — it is a part count, not a percentage: `EC_TAG_PARTFILE_HASHED_PART_COUNT` (`Refresher.cpp:587`), and `State.h:166` comments "parts hashed so far; 0 = idle". On the list as well as the detail object, so the SSE payload moves with it. **Emit `parts_total_count` beside it on the list rows too** (today `part_count` is detail-only): a rising integer with no total next to it is not renderable, and a progress bar fed it directly shows 3% for three parts of a hundred and 300% for three hundred of a thousand |
| `last_seen_complete` | `last_seen_complete_at` | R3 |
| `last_changed` | `last_received_at` | R3, **and the current name is wrong** — it is `EC_TAG_PARTFILE_LAST_RECV` (`Refresher.cpp:574`), the last time data arrived |
| `download_active_time` | `active_seconds` | R2 |
| `remaining_time` | `eta_seconds` | R2. It is already `null` when there is no ETA, so only the name moves |
| `available_part_count` / `part_count` | `parts_available_count` / `parts_total_count` | R5, and the pairing is currently invisible — `parts_available_count` is the parts at least one source can serve |
| `lost_to_corruption` | `lost_to_corruption_bytes` | R2 |
| `gained_by_compression` | `gained_by_compression_bytes` | R2 |
| `saved_by_ich` | `ich_recovered_packet_count` | R2/R5 — the unit differs from its two byte-valued neighbours: `CPartFile::TotalPacketsSavedDueToICH()` (`PartFile.h:266`) counts **packets**, incremented per recovered block at `PartFile.cpp:3793`. `ich` itself stays (R8 — the desktop UI shows the user "I.C.H.", `muuli_wdr.cpp:687`, `muuli_wdr.cpp:1735`); it gets its one expansion (Intelligent Corruption Handling) in the reference |
| `met_file` | `part_file_name` | R8 — and the key is wrong twice over: the value is the **`.part`** basename, not the `.met` one, and both are on-disk format details. The alternative — **dropping both**, since they describe the daemon's private temp layout — does not survive contact with the only consumer: the Web UI renders this one in the download-detail stats (`views/download-detail.js:154`), so it stays and gets an honest name |
| `partmet_id` | *(drop)* | R8, and nothing reads it — `met_file` is the only one of the pair the Web UI displays, and the index is just the numeric part of that filename. Rename it to `part_file_index` only if a consumer turns up |
| `path` | `directory` | it is always a directory; `path` invites "full path to the file" |
| `queued_count` | `upload_queue_count` | count of clients queued to download this file *from us* |
| `comment` / `rating` | `my_comment` / `my_rating` | they collide with `comments[].comment` / `.rating`, which are *other clients'* |
| `media.length_s` | `media.duration_seconds` | R2; `length` also collides with the file's byte size |
| `media.bitrate` | `media.bitrate_kbits` | R2 — the unit exists nowhere in the code, and this one really is kilo**bits**: `ParseBitrateKbps` (`MediaProbe.cpp:434-450`) divides ffprobe's bits/second by **1000**, so it cannot borrow the API's `_kbps` = KiB/s spelling |
| `kad_comment_search_running` | `is_kad_comment_lookup_running` | R4; "search" here is a Kad *notes* lookup, not a file search. **Three writers carry this key**, not one: the download object, `GET /downloads/{hash}/comments` (`Api.cpp:4302`) and the search result (`SearchJson.cpp:115`). A rename that misses one leaves the Web UI polling a key that stopped existing |
| `hash`, `name`, `ed2k_link`, `status`, `priority`, `speed_bps`, `aich_hash` | *(keep)* | reviewed: rule-compliant. `aich` stays under R8 — the desktop shows the user "AICH info" in the shared-files context menu (`SharedFilesCtrl.cpp:209`) — and `aich_hash: ""` before the hashset exists is the one R10 fix on this set |
| `media.codec` / `.artist` / `.album` / `.title` | *(keep)* | reviewed: rule-compliant; only the two unit-bearing members of `media` move |

Sub-resources of a download:

| endpoint | current | new |
|---|---|---|
| `GET .../comments` | `count` | `total` (R6 — every other collection says `total`). The `comments_updated` SSE payload carries the same key (`EventDiff.cpp:142`) and moves with it |
| `GET .../filenames` | `filenames[].name` | `filenames[].filename`, and `filenames[].count` → `filenames[].source_count` |
| `POST .../a4af` reply (`WriteA4afObject`, `Api.cpp:4448`) | `a4af_auto` | `is_a4af_auto` (R4) — the same flag as on the download detail object, so it moves with it. `source_ecids` beside it is already right |
| `POST .../a4af` | `action` values `swap_this`, `swap_others` | keep the values. `swap_this_auto` has **already** been moved out (it is now rejected here; the flag is set idempotently via `PATCH /downloads/{hash} {"a4af_auto": …}`) — the remaining rename is only `a4af_auto` → `is_a4af_auto` on that PATCH, tracked above |

Write side:

| current | new | why |
|---|---|---|
| `PATCH /downloads` and `PATCH /downloads/{hash}` body `status` (`paused`/`resumed`/`stopped`) | `action` (`pause`/`resume`/`stop`) | R9 — `resumed` is never a value `status` returns, and the read enum has 11 values the write side rejects: `DownloadStatusName` (`Refresher.cpp:314`) returns `completed`, `completing`, `stopped`, `downloading`, `waiting`, `hashing`, `erroneous`, `insufficient_disk`, `paused`, `allocating`, `unknown` |
| `category` in every body that carries one — `POST /downloads`, both `PATCH` forms, `POST /search/results/{hash}/download` | `category_index` | R6 with the read side |

### 1.2 Clients — `GET /clients`, `GET /clients/{ecid}`, `GET /known_clients`, `GET /downloads/{hash}/clients`, `GET /shared/{hash}/clients`

`WriteClientBaseFields` (`Api.cpp:2879`), `WriteClientObject` (`Api.cpp:2961`),
`WriteKnownClientObject` (`Api.cpp:3021`), `WriteClientDetailObject` (`Api.cpp:3077`),
`WriteFileClientRow` (`Api.cpp:3998`). The base fields ship in the `client_*` SSE
payloads too (`ToJson(const ClientSnapshot&)`, `EventDiff.cpp:231`) — and note
`Equal` at `EventDiff.cpp:430` has to move with them, since a field in one but not the other
never updates.

| current | new | why |
|---|---|---|
| `xfer.up_session` | `uploaded_bytes_session` | R2/R6/R8/R11 — flatten the `xfer` object; the same key name means a 4-field up/down pair here and an upload-only pair on `/shared` |
| `xfer.down_session` | `downloaded_bytes_session` | |
| `xfer.up_total` | `uploaded_bytes_total` | |
| `xfer.down_total` | `downloaded_bytes_total` | |
| `known_clients.total_uploaded` / `total_downloaded` | `uploaded_bytes_total` / `downloaded_bytes_total` | R6 — same quantity as above, different name today |
| `queue_waiting_position` | `upload_queue_position` | it is this client's place in **our** upload queue — same `upload_*` prefix as `upload_state` and the renamed `upload_queue_score`, so the side is readable without pronouns |
| `remote_queue_rank` | `remote_queue_position` | the mirror image — our place in **their** queue; `rank` and `position` were two words for one thing. (The `0xffff`-full-queue sentinel already emits `null` via `WriteIntOrNull`; only the rename is left.) |
| `score` | `upload_queue_score` | score of what, on which side |
| `dl_up_modifier` | `credit_ratio` | unguessable abbreviation; it is the credit-system modifier applied to this client (`CUpDownClient::GetScoreRatio()`, `State.h:477`), which the desktop labels "DL/UP modifier". `credit_ratio_modifier` was the other candidate; `credit_ratio` wins on R5 — it is a ratio, not a count of modifiers |
| `friend_slot` | `has_friend_slot` | R4, and it is easy to misread as `is_friend` |
| `view_shared_disabled` | `can_browse_shared_files` **(inverted)** | R4 — a negated boolean forces `disabled == false` at every call site |
| `high_id` | `is_high_id` | R4 |
| `user_id_hybrid` | `ed2k_user_id` | R8 — "hybrid" is an eDonkey-encoding detail |
| `obfuscation_status` (clients) / `obfuscation` (known_clients) | `obfuscation_state` on both | R6; `_state` matches the sibling `upload_state` / `download_state` / `ident_state` |
| `mod_version` | `client_mod_name` | it is the client's mod string, not a version |
| `os_info` | `reported_os` | untrusted, client-reported, frequently empty — the name should not promise more |
| `available_parts` | `parts_offered_count` | R5; deliberately *not* `parts_available_count` — that name belongs to the download object, where it means "parts any source can serve"; this one is the parts **this** client holds |
| `part_progress_percent` | *(keep)* | reviewed: rule-compliant |
| `version` (known_clients) | `software_version` | R6 — `/clients` calls the identical value `software_version` |
| `online` (known_clients) | `is_online` | R4 |
| `sessions` (known_clients) | `session_count` | R5 |
| `first_seen` / `last_seen` | `first_seen_at` / `last_seen_at` | R3 |
| `is_friend`, `user_hash`, `server_ip`, `server_port`, `server_name`, `kad_port`, `country_code`, `software`, `upload_state`, `download_state`, `ident_state`, `source_origin`, `upload_speed_bps`, `download_speed_bps`, the four `*_file_name` / `*_file_hash` keys | *(keep)* | reviewed: rule-compliant |
| `country_code: ""` | `null` when unresolved | R10, same as on `/servers` |

The two per-file client routes add three keys to the same object:

| current | new | why |
|---|---|---|
| `a4af` (bool) | `is_a4af` | R4 — a bare acronym holding a boolean, beside `role`, which is a string |
| `role` values `source` / `peer` / `both` / `none` | `downloading_from` / `uploading_to` / `both` / `none` | R12 — `peer` as a role value is the **only contract-level `peer` left outside `/chats`** (`Api.cpp:3975`, documented at `REFERENCE.md:836`), and paired against `source` it is not even the same axis (one names a relation to the file, the other the entity). Naming both roles by direction says exactly what the row is: we pull this file from that client, or it pulls it from us |
| `parts` (array of bool, behind `?include_parts=true`) | *(keep)* | reviewed: the caller opted into it, so its absence is an answer, not a missing value |

`GET /known_clients` also has to stop omitting **eleven** keys behind **seven**
`if` guards (`name`; `ip`+`port`+`kad_port`; `country_code`;
`software`+`version`; `source_origin`; `obfuscation`; `first_seen`+`sessions`)
when their value is empty or zero (R10, `Api.cpp:3021-3073`) — a client currently
cannot tell "this client never reported an IP" from "this build forgot the
field".

### 1.3 Shared files — `GET /shared`, `GET /shared/{hash}`

`WriteSharedBaseFields` (`Api.cpp:3105`), `WriteSharedObject` (`Api.cpp:3163`),
`WriteSharedDetailObject` (`Api.cpp:3195`), `WriteSharedAvailabilityParts` (`Api.cpp:2708`).
The base fields ship in the `shared_*` SSE payloads (`ToJsonSharedEvent`,
`EventDiff.cpp:163`).

| current | new | why |
|---|---|---|
| `size` | `size_bytes` | R2 |
| `xfer.session` / `xfer.total` | `uploaded_bytes_session` / `uploaded_bytes_total` | R2/R6/R8/R11 |
| `requests.session` / `requests.total` | `request_count_session` / `request_count_total` | R5/R11 |
| `accepts.session` / `accepts.total` | `accepted_request_count_session` / `accepted_request_count_total` | R5/R11 — `accepts` is a verb doing duty as a plural noun |
| **`uploading`** | **`uploading_client_count`** | **the single worst name on the surface**: it reads as a boolean and holds an integer. R12 — clients, not peers |
| `complete_sources` | `complete_source_count` | R5. Note the same quantity is `sources.complete` on a search result (`SearchJson.cpp`) — R6 tolerates the divergence only because the search object nests a whole `sources` group and this one does not; the reference has to say so, or it reads as drift |
| `complete_sources_range.low` / `.high` | `complete_source_count_min` / `_max`, **flattened** — the wrapper object earns nothing once the keys say `min`/`max` | R6 with the above |
| `last_upload` | `last_upload_at` | R3 |
| `shared_since` | `shared_since_at` | R3 |
| `hashing_progress` | `hashed_part_count` | R6 — the same rename as on the download object; here it is fed through `SharedHashingProgress()` so a shared partfile reads correctly, and it is a list-level field, so the SSE payload moves with it |
| `priority_auto` | `is_priority_auto` | R4 |
| `share_ratio` | `upload_ratio` | it is `uploaded_bytes_total / size_bytes`; "share ratio" reads as a BitTorrent seed ratio |
| `part_count` | `parts_total_count` | R6 — the download object's identical field is renamed the same way |
| `parts` (detail; `[{sources}]`) | *(keep the placement and the shape)* — but **emit `null`** instead of omitting the key when no availability data has been decoded yet (R10) | the divergence from the download side is correct: `progress` is meaningless for a complete share, and the download's `{state, sources}` encodes *local* completeness, which would invite a renderer that lies about a shared file. Two shapes because they answer two questions. `null` still keeps "no data yet" distinguishable from "no sources for any part" |
| `path` | `directory` | R6 with the download object — it is the same value for the same file, and it is always a directory |
| `incomplete` | `is_incomplete` | R4 |
| `queued_count` | `upload_queue_count` | R6 with the download object |
| `comment` / `rating` | `my_comment` / `my_rating` | R6 with the download object |
| `media.length_s` / `media.bitrate` | `media.duration_seconds` / `media.bitrate_kbits` | R2 |
| `file_type` | *(keep the key)* | but normalise the values: they are `GetFiletypeDesc()`'s untranslated **UI labels** (`OtherFunctions.cpp:217-274`), lowercased — `videos`, `audio`, `archives`, `cd-images`, `pictures`, `texts`, `programs`, `any`. Three problems in one enum: plurals where the token names one file's type, a hyphen where every other enum token is snake_case, and `any` meaning *unknown*. Settle on `video`, `audio`, `archive`, `cd_image`, `picture`, `text`, `program`, `unknown` |

`/share_directories`:

| current | new | why |
|---|---|---|
| `directories[].recursive` | `directories[].is_recursive` | R4 |
| `directories[].path` | *(keep)* | a share **root** is a configured path, not the directory a file lives in; the two `path` → `directory` renames above are about a file's location. Say this in the reference so the divergence reads as a decision |
| `DELETE /share_directories?path=` | body `{"path": …}` | a query-string selector on a collection URL (`Api.cpp:9534`): forgetting it reads as "delete every share root". A body on `DELETE` is already the house style — `DELETE /downloads` takes `{"hashes": [...]}` |
| `rejected[].reason` values `not_readable` / `not_found` | *(keep)* | clear |

### 1.4 Servers — `GET /servers` and mutations

`WriteServerObject`, `Api.cpp:5403`. Same keys in the `server_*` SSE
payloads (`EventDiff.cpp:197`).

| current | new | why |
|---|---|---|
| `users` / `max_users` | `user_count` / `max_user_count` | R5. They are self-explanatory in isolation, but the cost of keeping them is that they become the exception once `/shared` reports `complete_source_count`, `/clients` `session_count` and `/downloads` `upload_queue_count`: a consumer can no longer tell from a key whether a bare plural is a count or a list |
| `files` | `file_count` | R5, same reasoning — and it disambiguates against the rest of the API, not just against its `soft_file_limit` / `hard_file_limit` neighbours |
| `static` | `is_static` | R4, plus: `static` is a reserved word in C++, Java, C# and TypeScript-adjacent codegen, so any generated client has to mangle it |
| `address` (string `"ip:port"`) with no `ip` | add `ip`, keep `address` and `port` | the `ip:port` URL form needs the IP, so every client re-parses `address` today |
| `country_code: ""` | `null` when unresolved | R10 |
| `soft_file_limit`, `hard_file_limit`, `failed_count`, `ping_ms`, `ecid`, `priority`, `description`, `version` | *(keep)* | reviewed: rule-compliant. `0` on the two limits means "not reported yet", which the reference already documents |
| `tcp_flags.*`, `udp_flags.*` (bare booleans: `compression`, `unicode`, `large_files`, `new_tags`, `type_tag_integer`, …) | *(keep)* | R4's parent-qualifies carve-out, the same one R5 grants `sources.total`: the object is called `tcp_flags`, so every member reads as a flag without an `is_`/`supports_` prefix. Do **not** prefix them one at a time. Shared table at `ServerFlagNames.h`, so REST and SSE cannot drift |
| `POST /servers_update` body `servers_url`, `POST /kad/update` body `nodes_url`, `POST /ipfilter/update` body `ipfilter_url` | `url` on all three | R6 — three `*/update` endpoints, three spellings of "the URL to fetch the list from", each repeating a noun the path already carries. All three go through one handler with a per-endpoint `spec.field` (`Api.cpp:3788`), so this is one line per spec |

### 1.5 Categories

`WriteCategoryObject`, `Api.cpp:5455`.

| current | new | why |
|---|---|---|
| `index` | *(keep the key)* | but document loudly that it is **positional and renumbered on delete** — `DELETE /categories/{index}` already has to shift every download's category to compensate |
| `path` | `save_path` | ambiguous next to `directories.incoming`; it is where finished files in this category land |
| `color` (bare uint32) | `color` as `"#rrggbb"` | a 24-bit value delivered as a decimal integer, with the code accepting the full uint32 range |
| synthesized index-0 row | give it real values | when the daemon sends no index-0 category the handler fabricates one with `name: ""`, `path: ""`, `color: 0`, `priority: "low"` and serves it as if it were real (`CategoriesWithDefault`, `Api.cpp:5625`); the docs claim `"All"` / `"normal"` (`REFERENCE.md:1845-1850`) |
| `priority` write enum | accept what the read enum returns | R9 — reads can return `very_low` and `release`, writes reject them (documented at `REFERENCE.md:1874`) |

### 1.6 Search

`WriteSearchResultFields` (`SearchJson.cpp:36`) — shared by
`GET /search/{id}/results` and the `search_result_added` SSE payload, so these
renames land once; `HandleSearchList` (`Api.cpp:7722`) hand-writes the
`searches[]` object; `HandleSearchResults` writes the `progress` object.

| current | new | why |
|---|---|---|
| `searches[].search_id` | `id` | the id is in the path (`/search/{id}/results`), so the object is prefixing its own key with its own type — the same rule that turned `client_ecid` into `ecid` on the client object. References *from elsewhere* (the SSE payloads, `search_result_added.search_id`, the `search_id` echoed in the results envelope) keep the prefix: they point out of the object |
| `POST /search` body `type` vs `searches[].kind` / `progress.kind` | `type` everywhere | R6 — one concept, two names |
| `POST /search` body `min_size` / `max_size` | `min_size_bytes` / `max_size_bytes` | R2 |
| `POST /search` body `min_avail` | `min_source_count` | R8 — "availability" in the desktop's Extended Parameters row is a minimum source count |
| `POST /search` body `file_type`, `extension` | *(keep)* | reviewed: rule-compliant |
| `results[].size` | `size_bytes` | R2 |
| `results[].sources.total` / `.complete` | *(keep)* | R5/R6 — same shape as the download object's `sources` |
| `results[].already_have` | `is_already_downloaded` | R4 |
| `results[].type` | `file_type` | R6 — `POST /search`'s own body already spells this filter `file_type` (`Api.cpp:10292`), so the rename aligns request and response rather than inventing a name. `/shared/{hash}` derives its `file_type` from the *same* call (`GetFiletypeByName(name, translated=false)`, lowercased), so these are one enum under two key names; next to a `media` object a bare `type` also reads as a MIME type. The two key names already draw from one shared token function (`FileTypeToken`, `Refresher.cpp`); only the two spellings differ |
| `results[].rating` | *(keep)* | but document `0` = *unrated*, not "rated zero" |
| `results[].comments[].username` / `.filename` / `.rating` / `.comment` | *(keep)* | reviewed: rule-compliant, and the identical object ships on `GET /downloads/{hash}/comments` and in the `comments_updated` SSE payload — three copies of one shape, so any change to it moves in all three |
| `searches[].query`, `searches[].state`, `searches[].client_ecid`, `searches[].result_count` | *(keep)* | reviewed: rule-compliant; only `search_id` and `kind` move, above |
| `results[].directory` | *(keep)* | reviewed: rule-compliant, and already the `sort` key |
| `results[].media.length_s` / `.bitrate` | `.duration_seconds` / `.bitrate_kbits` | R2 |
| `results[].children[]` | `results[].alternate_names[]` | `children` is tree vocabulary for what the code calls same-hash/same-size hits advertised under different filenames (`State.h:873-875`) — there is no hierarchy, only one file seen under several names. Each entry's `hash` is by construction the parent's, so it can go |
| `results[].kad_comment_search_running` | `is_kad_comment_lookup_running` | R4/R6 — see §1.1, three writers |
| `progress.percent` | *(keep)* | 0–100, document it |
| `search_progress` SSE `results` | `result_count` | R5/R6 — a plural key holding an integer, while `results` is an array everywhere else, and `GET /search` already calls the same number `result_count` |

### 1.7 Friends and chats

`WriteFriendObject` (`Api.cpp:5475`, SSE at `EventDiff.cpp:197`),
`WriteChatObject` (`Api.cpp:5730`), `WriteChatMessageObject` (`Api.cpp:5714`),
`ChatMessageJson` / `PublishChatEvents` (`EventDiff.cpp:605`, `EventDiff.cpp:612`).

| endpoint | current | new | why |
|---|---|---|---|
| `/friends` | `online` | `is_online` | R4/R6 — `/known_clients` and `/chats` get the same rename |
| `/friends` | `friend_slot` | `has_friend_slot` | R4/R6 — same field, same rename as on the client object |
| `/friends` | `ip: ""`, `client_ecid: 0` | `null` | R10 — same sentinel cleanup as `/servers` and `/clients` |
| `/chats`, `/chats/{peer}`, `/chats/{peer}/messages` | the `peer` key and the `{peer}` path segment | `client_address`, `/chats/{client_address}` | R12 — `peer` is the third word for the thing the API calls a client, and it is the *address* form of it (it has to be: a chat can address a client that is offline and has no ECID). `client_ecid` sits beside it for the online case. Six sites carry the key: the chat object (`Api.cpp:5733`), the messages envelope (`Api.cpp:6007`), the send reply (`Api.cpp:6080`), the close reply (`Api.cpp:6189`), and the `chat_message` / `chat_session_closed` SSE payloads (`EventDiff.cpp:629`, `EventDiff.cpp:635`) |
| `/chats` | `last_msg_id` | `last_message_id` | R6 — the same object spells it out twice over (`message_count`, `last_message_at`, `last_message`); only the id is abbreviated. The messages envelope carries the same key |
| `/chats/{…}/messages` | query `since_id` | `since_message_id` | same concept as above; `id` alone does not say of what |
| `/chats` | `messages[].timestamp`, `chat_message` SSE `message.timestamp` | `sent_at` | R3 — every other time in the API is `_at`, and "timestamp" names the type, not the event |
| `/chats` | `online` | `is_online` | R4/R6 |
| `/chats` | `client_ecid: 0`, `friend_ecid: 0` | `null` when offline / not a friend | R10 |
| `/chats` | `last_message` (omitted when the session has none), `last_message_at: 0` | always emit; `null` when there is no message | R10 |
| `/chats` | `direction` (`in`/`out`), `message_count`, `name`, `ip`, `port` | *(keep)* | reviewed: rule-compliant |

### 1.8 Status, Kad and stats

`GET /status` (`Api.cpp:2482`ff, SSE at `EventDiff.cpp:293`), `GET /kad`
(`Api.cpp:6978`ff, `WriteKadNetworkObject` at `Api.cpp:664`), `GET /stats/tree` and
`GET /stats/graphs/{graph}` (`WriteStatsValue` `Api.cpp:7106`, `WriteStatsNode` `Api.cpp:7143`,
`WritePointArray` `Api.cpp:7202`).

| current | new | why |
|---|---|---|
| `ed2k.connected_since`, `kad.connected_since` (both on `/status` and on `/kad`) | `connected_since_at` | R3 |
| `ed2k.high_id` | `ed2k.is_high_id` | R4/R6 — the client object's `high_id` becomes `is_high_id` in §1.2; this is the same predicate about ourselves |
| `ed2k.network.users` / `.files`, `kad.network.users` / `.files` / `.nodes` | `user_count` / `file_count` / `node_count` | R5/R6 — `network` names the scope, not the thing counted, so the carve-out does not apply, and `/servers` reports the same two quantities as `user_count` / `file_count`. One helper (`WriteKadNetworkObject`) serves `/status` and `/kad`, so the Kad triplet is one edit |
| `kad.indexed.load` | `kad.indexed.load_percent` | R2 — a 0–100 value with no unit in the name. The word `load` is the daemon's and the desktop's, which the suffix preserves |
| `kad.buddy.status` | `kad.buddy.state` | every other connection enum in the API (`ed2k.state`, `kad.state`, the top-level `state` on the same object) is `state` |
| `kad.indexed.{sources,keywords,notes}`, `kad.node_id`, `kad.public_ip`, `kad.buddy.{ip,port}`, `speeds.*`, `disk.*`, `queue.*`, `ec_connected` | *(keep)* | reviewed: rule-compliant. `indexed.*` is the daemon's and the desktop panel's vocabulary |
| `/stats/graphs` `unit: "bytes_per_second"` | `unit: "bps"` | R2/R6 — `_bps` **is** this API's word for bytes per second, written down once in the reference, and the token should match the `speed_bps` / `upload_speed_bps` fields it describes. `unit: "count"` on the other two graphs is already right |
| `/stats/graphs` `points[].t` + `points[].t_unix` | `points[].at` (unix seconds, ISO twin dropped) | R3. Dropping the twin also removes a key and its ~22-byte value from every point in an array that can run to `max_points`, and `at` is shorter than `t_unix` |
| `/stats/graphs` `graph` (echoes the requested graph name, `Api.cpp:7483`), `interval_seconds`, `max_points`, `active_downloads`, `active_uploads`, `session.download_bytes` / `.upload_bytes` / `.kad_node_seconds` / `.duration_seconds`, `?width=N`, `?interval=N` | *(keep)* | reviewed: rule-compliant. `width` is how many samples the caller wants, `max_points` how many the daemon can give — two different questions, and the pair reads correctly. The `session` object is R11-correct: four *different* quantities under one scope |
| `/stats/tree` `label`, `label_value`, `token`, `values[]`, `values[].type`, `values[].value`, `values[].extra`, `ratio.session` / `.total`, `children`, `?max_client_versions=N` | *(keep)* | reviewed: rule-compliant, and `children` here is a real tree, unlike the search result's. `max_client_versions` is a cap like `limit`, not a reported count, so R5 does not apply |

### 1.9 Preferences — `GET`/`PATCH /preferences`

This is the largest naming surface: **13 categories, 125 fields**
(`PrefsSchema.cpp`), most of them transliterations of `amule.conf` keys or of EC
tag names.

**Category renames**

| current | new | why |
|---|---|---|
| `core_tweaks` | `advanced` | `core_tweaks` is EC-group/internal vocabulary (there is no such `amule.conf` section); "core" means nothing to an API consumer, `verbose_logging` inside it is not a tweak, and the desktop tab holding these settings is literally called **"Advanced"** (`PrefsUnifiedDlg.cpp:384`) |
| `ip2country` | `geoip` | the rest of the API says GeoIP (`country_code`, `/flags/{code}.png`) |
| `kademlia` | `kad` | everything else in the API says `kad`; this category exists only because EC has a group for it and holds exactly one field |

**Units and silent quantisation** (rename only). The three
`core_tweaks.*_minutes` fields already carry the honest unit and convert at the
boundary; what they still need is the **category** rename (`core_tweaks` →
`advanced`, below) and, for one, the `kad_reask` → `kad_source_reask`
disambiguation. Everywhere else, where the daemon quantises, say so in the
reference.

| current | new | note |
|---|---|---|
| `connection.max_download_kbps` / `max_upload_kbps` | *(keep)* | R2 — `_kbps` is KiB/s and stays that way, defined once in the reference alongside `_bps`. **Not** converted to bytes at the boundary either, though it would work (the core stores KiB/s in `s_maxdownload` and `PATCH /preferences` echoes the whole object, so a rounding would be visible rather than silent): a bandwidth limit is what the user types and what the desktop shows, and both are KiB/s, so bytes would force the UI to divide to render it and make `1000000` read back as `999424` |
| `connection.upload_slot_kbps` | `upload_slot_min_kbps` | the unit spelling stays; the fix here is that it is the *minimum bandwidth allotted per slot*, not "a slot's speed" |
| `core_tweaks.kad_reask_minutes` | `advanced.kad_source_reask_minutes` | category rename, plus the `kad_source_reask` disambiguation |
| `core_tweaks.source_reask_minutes` | `advanced.source_reask_minutes` | category rename |
| `core_tweaks.server_keepalive_timeout_minutes` | `advanced.server_keepalive_timeout_minutes` | category rename |
| `core_tweaks.max_new_connections_per_5s` | `advanced.max_new_connections_per_5_seconds` | R1/R2 — `5s` glued into an identifier |
| `core_tweaks.file_buffer_bytes` | *(keep the name)* | document the 15000-byte quantisation (`Preferences.h:426-427`: `100000` becomes `90000`) |
| `core_tweaks.max_upload_queue_clients` | *(keep)* | document the step of 100 (`Preferences.h:428-429`) |
| `core_tweaks.kad_max_source_searches` | `advanced.kad_max_concurrent_source_searches` | it is a concurrency cap, not a lifetime total |
| `security.ipfilter_block_below_access_level` | `security.ipfilter_min_access_level` | document the 0–255 scale |

**Unexplained internals**

| current | new |
|---|---|
| `files.ich_enabled` | *(keep)* — the desktop UI shows the user "I.C.H." (`muuli_wdr.cpp:1735`), so `ich` is R8 protocol vocabulary like `aich` |
| `files.aich_trust_every_hash` | `files.trust_unverified_aich_hashes` |
| `files.mmap_enabled` / `mmap_supported` | *(keep)* — the desktop shows the user *"Use MMAP: memory-mapped file access"* (`muuli_wdr.cpp:2098`), so `mmap` is R8 UI-shown vocabulary like `ich`; the reference expands it once |
| `files.endgame_enabled` | `files.endgame_mode_enabled` |
| `files.save_source_seeds_for_rare_files` | `files.save_sources_for_rare_files` |
| `files.start_next_paused` / `start_next_alphabetical` / `start_next_same_category` | `files.on_finished_start_next_paused` / `_alphabetically` / `_in_same_category` — today nothing says *when* they apply |
| `security.use_secident` | `security.secure_identification_enabled` |
| `security.obfuscation_enabled` | `security.protocol_obfuscation_enabled` (note the field maps to `EC_TAG_SECURITY_OBFUSCATION_SUPPORTED`, `PrefsSchema.cpp:190` — a misleading alias worth a comment) |
| `security.use_system_ipfilter` | `security.system_ipfilter_enabled` |
| `servers.auto_update` | `servers.update_list_at_startup` — it maps to `SetAutoServerlist` (`ECSpecialMuleTags.cpp:780`) and collides conceptually with `update_list_from_server` / `_from_client` and with `POST /servers_update` |
| `servers.safe_connect` | `servers.safe_server_connect_enabled` |
| `servers.smart_id_check` | `servers.smart_lowid_check_enabled` — the desktop says *"Use smart LowID check on connect"* (`muuli_wdr.cpp:1640`); it is not "checking the server's id", so the rename must keep *smart LowID*, and R4 adds the predicate suffix |
| `servers.use_priority_system` | `servers.server_priority_system_enabled` |
| `servers.remove_dead` | `servers.remove_dead_servers` |
| `servers.dead_server_retries` | `servers.dead_server_retry_count` |
| `general.check_new_version` | `general.version_check_enabled` |
| `general.local_host_name` | `general.daemon_host_name` — "local" relative to whom? |
| `connection.reconnect` | `connection.reconnect_on_connection_loss` |
| `connection.network_ed2k` / `network_kad` | `connection.ed2k_enabled` / `kad_enabled` (R4) |
| `connection.upnp_available` | `connection.upnp_supported` (R6 with `mmap_supported`, `geoip.supported`) |
| `connection.upnp_tcp_port` | `connection.upnp_control_point_port` — it is **not** the forwarded port (`amule.cpp`: `new CUPnPControlPoint(GetUPnPTCPPort())`); this is the most misreadable field in the payload. The Web UI label keeps saying "UPnP TCP Port", matching the desktop, or the user will not find the setting |
| `connection.max_connections` / `max_sources_per_file` | `max_connection_count` / `max_sources_per_file_count` (R5) |
| `directories.incoming` / `temp` | `directories.incoming_path` / `temp_path` |
| `directories.shared` | `directories.shared_paths` — only this one is an array, and nothing in the names says which |
| `directories.exclude_patterns` | *(keep)* — the single string holds **several** `'|'`-separated wildcards (or one regex when `exclude_patterns_use_regex` is set — `Preferences.h:809` stores the single string, and the desktop's own tooltip spells the format out at `muuli_wdr.cpp:1875`); the plural describes the content, and the singular would orphan the `_use_regex` sibling |
| `directories.auto_rescan` | `directories.rescan_on_startup` |
| `message_filter.by_keyword` | `message_filter.filter_by_keyword` (R4) |
| `message_filter.show_in_log` | `message_filter.log_filtered_messages` |
| `remote_controls.webserver.template` | `template_name` — reserved word in several client languages; the C++ member is already `template_name` (`PrefsSchema.cpp:214`) |
| `remote_controls.webserver.use_gzip` | `gzip_enabled` (R6 — the same payload mixes `use_*` and `*_enabled`) |
| `geoip.last_update_result` | `geoip.last_update_status` + a documented value set (it is a free-form string today) |
| `geoip.update_now` | move it out: it is an **action** modelled as a write-only boolean → `POST /geoip/update`, matching `POST /servers_update` and `POST /kad/update` |

**Bare-adjective boolean preferences.** R4 also catches roughly two dozen rows
the table above does not name individually — `connection.autoconnect`,
`connection.proxy_enabled`'s siblings `proxy_auth`, `directories.follow_symlinks`
/ `share_hidden`, `files.create_sparse_files` / `preallocate_full_file_size` /
`prioritize_first_last_chunks` / `add_new_downloads_paused` /
`new_downloads_auto_priority` / `new_shared_files_auto_priority` /
`stop_on_low_disk_space`, `security.ipfilter_clients` / `ipfilter_servers` /
`ipfilter_include_lan_ips` / `ipfilter_auto_update` / `obfuscation_requested` /
`obfuscation_required` / `reject_spoofed_source_ips`,
`servers.autoconnect_static_servers_only` / `manual_servers_high_priority` /
`update_list_from_server` / `update_list_from_client`,
`message_filter.accept_from_friends_only` / `accept_from_known_clients_only` /
`filter_all_messages` / `filter_comments`, `geoip.auto_update`. Decide once and
state it in the reference: either every boolean preference takes a predicate form
(`*_enabled` for a switch, `is_*`/`has_*` otherwise), or preferences are exempt
because each row mirrors a desktop checkbox label. **Recommended: exempt them**,
and confine R4 in this category to the rows above, where the name is wrong for a
reason other than its grammar. Renaming two dozen switches whose current names
already read as the checkbox they toggle buys nothing and doubles the diff.

**Four "where do I fetch this list from" URLs, four shapes** — `servers.update_url`,
`kademlia.update_url`, `security.ipfilter_update_url`, `ip2country.custom_url`.
Settle on `<thing>_update_url`, with the `<thing>_` prefix only where the category
holds more than one such URL. Three are already right; only
`ip2country.custom_url` moves, to `geoip.custom_update_url`.

**Read-only / write-only / gated fields.** The access-level documentation gap —
which rows are settable, which are read-only status, the three phantom
`remote_controls.amuleapi.*` rows and the schema-less `webserver.guest_password`
— has **landed** as a documentation fix: `REFERENCE.md` now carries the access
levels and a truthful read-only rejection message (on the resolved list in
[`api-design-inconsistencies.md`](api-design-inconsistencies.md)). The renames
above rely on that distinction being visible, because several of them
(`upnp_supported`, `geoip.supported`, `mmap_supported`) only read correctly once
a client can see which rows are status and which are settings.

### 1.10 Endpoints added after the audit

Three routes landed after the inventory above was taken, so their keys were
never held against R1–R12. Reviewed here.

`GET /health` (`HandleHealth`, `Api.cpp:1935`):

| current | new | why |
|---|---|---|
| `status` | *(keep)* | the constant `"ok"`; it is the liveness answer, and a probe reading the status code does not need it to say more |
| `ec_connected` | `is_ec_connected` | R4 — a bare past participle holding a boolean. The identical key on `GET /status` moves with it (§1.8 marks it *(keep)*; this supersedes that row — one concept, one spelling, R6) |
| `snapshot` | `has_snapshot` | R4, and the bare noun reads as *the snapshot itself*, which is what a caller might reasonably expect the key to contain. It is "a first refresher tick has landed" |

`POST /shared/media/refresh` and `POST /shared/{hash}/media/refresh`
(`SendMediaRefresh`, `Api.cpp:9585`):

| current | new | why |
|---|---|---|
| `queued` | `queued_file_count` | R5 — a bare past participle holding an integer, the same defect as `uploading` on `/shared` |
| `scope` (`"all"` / `"file"`) | *(keep)* | it distinguishes the two routes' answers in one shape, which is worth a key |

### 1.11 Auth, version and logs

| current | new | why |
|---|---|---|
| `/logs/serverinfo` | `/logs/server_info` | R1 — the only non-snake_case path segment in the API |
| `/logs/amule` `lines` (the array itself, `Api.cpp:7799`) | *(keep)* |
| `/logs/amule` `total_cached` | `total_lines` | R6 — the sibling endpoint says `total_bytes`; "cached" describes amuleapi's mirror, not the answer |
| `/logs/amule` `returned` | `returned_lines` | R6 |
| `/logs/server_info` `text`, `total_bytes`, `returned_bytes` | *(keep)* | they are the model the two renames above copy: this endpoint ships one text blob, so its counters are bytes, and `/logs/amule` ships an array, so its counters are lines |
| `version.name` | `service` | "name" of what? It is the constant `"amuleapi"` |
| `version.amule_version` | `amuleapi_version` | **actively misleading** — it is the `VERSION` the *amuleapi binary* was built from, which need not match the aMule daemon it is talking to; `daemon_version` beside it is that one |
| `version.api_version: "v0"` | `"v1"` | a *value* naming the API version. The final prefix-flip commit has to change it, or the endpoint reports `v0` from under `/api/v1/` |
| `version.update.update_available` | `update.is_available` | R4, stutters inside its own object |
| `version.update.checked` | `update.has_been_checked` | R4 |
| `version.update.last_checked` | `update.last_checked_at` | R3 |
| `version.update.latest_version: ""` | `null` before a check completes | R10 — its two siblings on the same object already emit `null` (`Api.cpp:2018`) |
| `version.update.check_enabled` | *(keep)* | reviewed: rule-compliant |
| `auth/session` `exp` / `exp_unix` | `expires_at` (unix int) | R3/R6 — `/auth/login` returns the same value as `expires_at`, and `exp` is raw JWT-claim jargon |
| `auth/login` `expires_at` (ISO) + `expires_at_unix` | one `expires_at` (unix int) | R3 |
| `jti` | `session_id` | R8 — a JWT internal in the public contract. Also **always emit it on login**: today it appears only in the bearer shape (`Api.cpp:2174`), so it is absent from every cookie-auth response while `/auth/session` returns it unconditionally |
| `auth/passwords` `admin_set` | `admin_password_set` | R6 with its sibling |
| `auth/passwords` `guest_enabled` | `guest_access_enabled` (read and write) | R6 |
| `auth/passwords` `other_sessions_revoked` | drop | always `true` |
| `?type=bearer` | `?include_token=true` | "type" of what. `Accept: application/jwt` (`Api.cpp:2147`) selects the same shape — say in the reference that the header form survives the rename unchanged, or retire it in the same pass |

### 1.12 Error codes

The binary emits **27** distinct codes. The catalog in
`docs/api/REFERENCE.md:2949` now lists **26** of them — the completeness gap is
closed; the missing one is `not_readable`, a per-item code inside the
`/share_directories` bulk envelope, documented with its endpoint rather than in
the catalog. What is left is the naming.

| current | new | why |
|---|---|---|
| `internal` (`HttpServer.cpp:662`) | `internal_error` | two codes for one condition; a client matching one misses the other. This one is a raw JSON literal, so it does not grep like the rest |
| `completed_use_clear_completed` | `download_completed` | an *instruction* embedded in a machine-readable code; the hint belongs in `message` |
| `conflict` | **split it**: `option_not_supported` (`Api.cpp:8373` — the build lacks the preference) and `not_a4af_source` (`Api.cpp:4530` — that client is not an A4AF source of this file) | `conflict` just restates the HTTP status, and one code carries two unrelated meanings on two endpoints |
| `sessions_exhausted` (`HttpServer.cpp:698`, also a raw literal) | `too_many_streams` | unique style, and "sessions" here means SSE streams, not logins |
| `update_check_throttled` | `rate_limited` | two codes for one concept at the same status (429) |
| `bad_gateway` (`/known_clients`) | `amuled_response_invalid` | HTTP status name used as a code |
| `ec_unavailable`, `ec_unsupported`, `amuled_rejected`, `kad_more_exhausted`, `partfile_unsupported`, `login_disabled`, `not_shared`, `not_completed`, `update_check_unavailable` | *(keep)* | R8 — project vocabulary, used consistently |

The catalog itself is now complete — it lists every code the binary emits, both
two-status codes included — so only the renames above are left.

## 2. Query parameters

Names only — the query-parameter renames still open.

| endpoint | current | new / fix |
|---|---|---|
| every list endpoint | `sort=size` / `progress` / `speed` / `ping` / `users` / `files` / `sessions` / `total_uploaded` / `total_downloaded` / `first_seen` / `last_seen` / `sources` / `online` | R7: each becomes the response key it orders by, after that key's own rename — `size_bytes`, `progress.percent`, `speed_bps`, `ping_ms`, `user_count`, `file_count`, `session_count`, `uploaded_bytes_total`, `downloaded_bytes_total`, `first_seen_at`, `last_seen_at`, `sources.total`, `is_online`. `sort=name`, `status`, `software`, `rating`, `directory`, `last_message_at` are already the key and do not move |
| `GET /clients` | `filter=uploads` / `downloads` / `active` | `activity=uploading` / `downloading` / `active` — "filter" names the mechanism, not the axis, and the values are plural nouns for what are client states |
| `POST /auth/login`, `PATCH /auth/passwords` | `type=bearer` | `include_token=true` |

## 3. Applying the renames

**R10 (omitted-vs-null)** is the rule the renames below assume: always emit the
key, `null` for an unknown value. It is documented in `REFERENCE.md` and holds
across the surface; the one writer that still emits a `0` sentinel where the rule
wants `null` (`client_ecid` / `friend_ecid` on `/friends` and `/chats`) is
tracked in
[`api-design-inconsistencies.md`](api-design-inconsistencies.md) §1.

**SSE payloads.** `EventDiff.cpp` shares the REST serializers for exactly two
payloads — the search result (`WriteSearchResultFields`, `SearchJson.cpp:36`) and
the server capability objects (`ServerTcpFlagsJson` / `ServerUdpFlagsJson`) — and
hand-builds **everything else** as a literal `ostringstream` chain. So every key
renamed above except those exists a second time as a string literal there and has
to be renamed twice, in `ToJson*` **and** in the matching `Equal*` predicate.

## 4. Files to touch

| Area | Files |
|---|---|
| Serializers and handlers | `src/webapi/Api.cpp` (all `Write*Object` helpers and every handler's body parser), `src/webapi/SearchJson.cpp` |
| Snapshot structs (rename members to match, so the JSON key and the field name stay greppable) | `src/webapi/State.h`, `src/webapi/State.cpp`, `src/webapi/Refresher.cpp`, `src/webapi/RefresherTick.cpp` |
| SSE payloads and channel routing | `src/webapi/EventDiff.cpp` (both `ToJson*` and `Equal*`), `src/webapi/EventBus.cpp` |
| Preference schema (keys, categories, access markers) | `src/webapi/PrefsSchema.cpp`, `src/webapi/PrefsSchema.h` |
| Web UI (the only consumer) | `src/webapi/static/js/*.js`, `src/webapi/static/js/views/*.js`, and the preference labels in `src/webapi/static/i18n/{en,es}.json` |
| Docs | `docs/api/REFERENCE.md` (add the rules section; the versioning paragraph at `:5` and the Backward-compatibility section at `:2982` change with the final prefix-flip commit; and sweep the **101** remaining occurrences of "peer" — starting with the `Clients (peers)` index heading at `:44` and the section heading at `:1103`, and the per-file `role` table at `:912` — into "client", per R12), `docs/api/EVENTS.md` (**12** more), `docs/QUICKSTART-AMULEAPI.md` (1) |
| Tests | the **41** scripts in `unittests/curl-tests/amuleapi/` (plus `run-all.sh`), plus `unittests/tests/{RefresherTest,StateTest,EventDiffTest,ChatSessionStoreTest,CredentialsTest}.cpp` |

### Size of the change, and how to stage it

Measured over the **137** renamed keys distinctive enough to grep for
unambiguously (`name`, `size`, `total`, `type`, `status` and friends are
excluded — they collide with ordinary JS and C++), counting only uses in key
position (`"key"`, `.key`, a jq path), so an English word that happens to match
does not inflate the number:

| Where | How many of the 137 appear |
|---|---|
| Bundled Web UI (`static/js`, excluding `vendor/`) | **109**, across 19 of the 27 JS files |
| curl test suite | **79**, across 33 of the 41 scripts |
| C++ unit tests | **56**, across 9 of the 43 files |

So this is not a serializer-only change, and a big-bang commit would be
unreviewable. Stage it **one resource at a time** — downloads, then clients,
then shared, then servers, then categories, then friends/chats, then
status/kad/stats, then preferences, then search, then the post-audit routes,
then auth/version/logs — and
make each commit carry, together: the `Api.cpp` serializer, the `EventDiff.cpp`
payload and its `Equal`, the snapshot struct, the Web UI reads, the curl test,
and the doc section. Every commit then leaves the tree working; none of them
leaves the UI reading a key the API stopped emitting.

## 5. Acceptance criteria

- [ ] Every key listed in §1 is renamed in the serializer, in the snapshot
      struct, in the SSE payload, in the Web UI and in the docs — `grep` for the
      old key name outside `src/libs/ec` (EC tag names are untouched) and outside
      `issues/` returns nothing.
- [ ] `docs/api/REFERENCE.md` opens with the R1–R12 rules and states the unit
      conventions (`_bps` = bytes/second, `_kbps` = KiB/s, `_at` = unix seconds,
      `_percent` = 0–100) once, in one place.
- [ ] Every `sort` value is spelled exactly like the response key it orders by
      (R7), so the reference needs no per-endpoint mapping table.
- [ ] `internal` no longer exists as a code distinct from `internal_error`, and
      the reference catalog still lists every code the binary can emit.
- [ ] Grepping for `peer` across `docs/api` and `src/webapi` returns nothing that
      is part of the contract — no key, path segment or enum value, and no
      reference prose describing one (R12). Web UI labels may keep the desktop's
      wording.
- [ ] The final commit flips the prefix: the API answers only under `/api/v1/`,
      `GET /version` reports `api_version: "v1"`, and `grep` for `/api/v0/`
      outside `issues/` returns nothing — no alias, no coexisting v0.
- [ ] The curl test suite passes with the renamed contract, and the Web UI works
      end to end against it (downloads, shared, clients, servers, categories,
      preferences, search, logs, SSE).
