# amuleapi: naming cleanup of the REST surface — landed, and what is left

## Summary

The one-pass naming cleanup this document specified — the ~137 renames across
every route, JSON key, query parameter, preference key and SSE payload on
`/api/v0/`, held against rules R1–R12 — has landed, and the rules now live in the
contract (`REFERENCE.md:456`). This document keeps only the naming items still
open: a few keys and enum values the sweep missed, one abbreviated unit, and the
`/api/v1/` cut.

Verified against the source at commit `cd7441c72`. The items below are the only
naming work left.

---

## 1. `upload_state` / `download_state` enum values leak raw eMule tokens (R8, R1)

The keys were renamed, but their *values* were not. `ClientUploadStateName`
(`Refresher.cpp:689`) and `ClientDownloadStateName` (`Refresher.cpp:715`) — whose
strings ship as `client.upload_state` / `download_state` (`Api.cpp:3043-3046`,
and the SSE `client_*` payload) — return a set of tokens that are the `US_*` /
`DS_*` C++ enum identifiers lowercased with the words run together: not
snake_case (R1) and implementation vocabulary (R8). The single-word states in
the same two switches are clean (`connected`, `downloading`, `queued`,
`pending`), and every *other* multi-word state enum on the surface is properly
snake_cased — the download `status`'s `insufficient_disk` (`Refresher.cpp:363`),
the ident state's `id_needed` (`:759`) — so these run-together compounds are the
miss:

| current | proposed |
|---|---|
| `waitcallback` | `waiting_callback` |
| `waitcallbackkad` | `waiting_callback_kad` |
| `reqhashset` | `requesting_hashset` |
| `noneededparts` | `no_needed_parts` |
| `toomanyconns` | `too_many_connections` |
| `toomanyconnskad` | `too_many_connections_kad` |
| `lowtolowip` | `low_to_low_ip` |
| `remotequeuefull` | `remote_queue_full` |
| `onqueue` | `queued` |

`onqueue` also collides with `US_ONUPLOADQUEUE`, which already returns `queued`
(`Refresher.cpp:691`) — the same "on the queue" state spelled two ways (R6), so
the two should collapse to one. These are enum *values*, so the fix moves with a
`REFERENCE.md` enum-list update and any Web UI switch on these strings.

## 2. `GET /search/results/{hash}/comments` returns `count`, its twin returns `total`

The comments-collection rename (`count` → `total`, so every collection says
`total`) reached the download side but missed the identical search side.
`HandleDownloadComments` emits `w.Key("total")` (`Api.cpp:4681`) and the
`comments_updated` SSE payload matches (`EventDiff.cpp:158`), but
`HandleSearchComments` — the same comment set for a search result — still emits
`w.Key("count")` (`Api.cpp:11578`). `w.Key("count")` is the *only* occurrence on
the whole serializer surface; every other "how many in this response" is `total`.

**Fix.** `count` → `total` on `HandleSearchComments`, and the `REFERENCE.md` line
for that endpoint.

## 3. Two `queue.*` counts miss the `_count` convention (R5)

The `/status` `queue` object (also the `status_changed` SSE) carries two counts
that the original pass reviewed as compliant but that do not follow R5:

| current | proposed | why |
|---|---|---|
| `queue.upload_clients_waiting` | `queue.waiting_upload_client_count` | `Api.cpp:2728` — a count of queued upload clients, no `_count`; the identical concept elsewhere is `uploading_client_count` (`:3312`) and `upload_queue_count` (`:3373`) |
| `queue.download_sources_total` | `queue.download_source_count` | `Api.cpp:2730` — `_total` is reserved for the pagination envelope and for a count *inside an object that names the thing* (`sources.total`); `queue` names neither, so the exception does not apply |

## 4. Preference `files.min_free_space_mb` carries an abbreviated unit (R2)

`PrefsSchema.cpp:178`. R2 spells units out (`_bytes`, `_seconds`, `_minutes`);
`_mb` is an abbreviation, and it sits beside `files.file_buffer_bytes`
(`:267`) which does spell it out. Settle on `min_free_space_megabytes` (spelled
out), or convert at the boundary and name it `min_free_space_bytes`.

## 5. `_kbps` is the lone short rate token left on a spelled-out surface

Every rate is spelled out (`speed_bytes_per_second`,
`bitrate_kilobits_per_second`) — except three preference bandwidth limits, which
kept the short `_kbps`: `connection.max_download_kbps`, `max_upload_kbps` and
`upload_slot_min_kbps` (`PrefsSchema.cpp:137`, `:139`, `:154`; `REFERENCE.md:2260-2262`).
The reason is real — a bandwidth limit is what the user types and the desktop
shows, and both are KiB/s, so the value must not be converted to bytes — but the
*spelling* is now the one abbreviation R2 otherwise forbids, and `REFERENCE.md`
does not document it as a deliberate exception.

**Decision, not a mechanical fix.** Either spell them out
(`_kibibytes_per_second`, the honest unit and ugly), or keep `_kbps` and add one
line to the R2 note naming these three as the documented KiB/s exception. The
second is smaller and is what the code already does; it just is not written down.

## 6. The `/api/v1/` prefix flip is a milestone, not a pending rename

The old plan ended by flipping the prefix to `/api/v1/` in a final commit, to
honour a documented v0 freeze. That framing is obsolete: `REFERENCE.md:5` now
states `/api/v0/` is **not frozen** — names are corrected in place — and
`/api/v1/` is cut later, "once the surface has settled and been exercised end to
end." So the flip is no longer a rename waiting to land; it is the act of cutting
v1: every `/api/v0/` path literal in `Api.cpp` moves to `/api/v1/`, `GET /version`
reports `api_version: "v1"` (today it still emits `"v0"`, `Api.cpp:2085`), and
the Web UI base path, the curl tests and the docs follow. Nothing blocks it; it
waits on the judgement that the surface has settled.

## 7. Cosmetic: `/version/check` uses two prefixes for its two error codes

`POST /version/check` can answer `409 update_check_unavailable` (`Api.cpp:5071`)
or `429 version_check_throttled` (`Api.cpp:5092`) — the same endpoint,
`update_`/`version_` disagreeing on the prefix for the same concept. Both are
otherwise rule-compliant, and `version_check_throttled` is deliberately distinct
from the auth limiter's `rate_limited` (comment at `Api.cpp:5087`). Pick one
prefix if the two are ever touched again; not worth a commit on its own.

---

## Scope

Four small renames, one decision, one milestone, one cosmetic note. §1 (enum
values) and §2 (`count → total`) are the missed copies of renames that otherwise
landed — the highest value, because a client switching on `upload_state` or
reading a comment count gets a token the rest of the surface does not use. §3 and
§4 are R5/R2 misses left in earlier "keep" buckets. §5 is a one-line
documentation decision (or a two-key rename). §6 is not work until v1 is cut; it
is recorded so the flip is not forgotten. §7 is cosmetic.

The three error codes `GET /shared/{hash}/content` added (`path_unavailable`,
`ec_content_unreachable`, `ec_content_mismatch`) are already in the
`REFERENCE.md` catalog and are snake_case and rule-compliant — no naming work,
noted only because the earlier "the catalog lists every code" count moved.
