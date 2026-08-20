# Web UI: multi-tab search — one tab per search, like amuleGUI

## Summary

`amuleapi` runs **several concurrent searches**, each addressed by its own
`search_id`, and both search SSE events carry the id they belong to. The bundled
Web UI ignores all of it: `src/webapi/static/js/views/search.js` keeps **one**
result map, calls the search endpoints with no id, disables the *Search* button
while a search runs, and renders a single hardcoded tab
(`views/search.js:299-300`). The SSE layer throws the routing information away
before the view even sees it — `search_result_added` and `search_progress` are
written to two global store keys, so the last frame from any search overwrites
whatever was there (`js/events.js:171-176`).

The practical result: starting a second search wipes the first one's results
from the screen, a browse of a peer's shared files cannot be shown at all, and
a search another client started (amuleGUI, the monolithic GUI, a second browser)
is invisible.

This issue replaces that with the desktop's model: **one tab per search**, all
of them live at once, closable individually, plus the actions the per-search API
exposes (stop, free, Kad *Extend*, peer browse). The existing single-search code
path is removed outright — there is no "current search" to fall back to.

Web UI only: everything lives under `src/webapi/static/` (HTML, CSS, JS, i18n,
images). No C++ and no `docs/` changes. Commits carry `web-ui` in the title, per
this repo's convention (`feat(web-ui): …`).

## API surface this consumes

This is the search surface `amuleapi` exposes. Every call names its search in
the path; there is no unaddressed variant and no implicit "current search". If
one of the routes or fields below is missing when this work starts, it is
blocked on the backend — **do not re-introduce a client-side fallback to an
unaddressed call.**

| Call | Purpose |
|---|---|
| `GET /api/v0/search` | every search amuled holds — `{search_id, query, kind, state}`, plus `client_ecid` on a `kind:"browse"` entry. Includes searches this browser never started. |
| `POST /api/v0/search` | start one. Body `{query, type, file_type, extension, min_avail, min_size, max_size}`; `type` is `local`/`global`/`kad`. → `202 {ok, search_id, query}` |
| `GET /api/v0/search/{id}/results` | that search's results + `progress {state, kind, percent}` + `query`. Accepts `limit`/`offset`/`sort`/`order`. `404` when the id is unknown or freed. |
| `POST /api/v0/search/{id}/stop` | stop it, keep its results |
| `POST /api/v0/search/{id}/more` | widen a **running Kad** search (the desktop's *Extend*). `400` for any other kind or a finished search. |
| `DELETE /api/v0/search/{id}` | stop **and** free it; later reads `404` |
| `POST /api/v0/search/results/{hash}/download` | queue a hit. Body `{category, ecid}` — `ecid` picks one grouped `children[]` alternative filename. Search-agnostic: addressed by hash, not by search. |
| `GET`/`POST /api/v0/search/results/{hash}/comments` | Kad ratings/comments for one hit. Also search-agnostic. |
| `POST /api/v0/clients/{ecid}/shared_files` | browse a peer's share ("View files"). → `202 {ok, search_id}`; results arrive through the search machinery with `kind:"browse"`. ADMIN-only. |

Result fields (identical on the list and on `search_result_added`): `hash`,
`name`, `size`, `sources {total, complete}`, `already_have`, `rating`, `status`,
`type`, `children[]`, `comments[]`, `kad_comment_search_running`, `media` (only
for locally-known hits), and `directory` — the remote folder, present only on
**browse** results.

SSE, on the `search` channel, both carrying `search_id`:

- `search_result_added` — one new parent result; payload is byte-for-byte a
  results-list entry with `search_id` prepended.
- `search_progress` — `{search_id, state, percent, results, kind}`; `state` is
  `running` or `finished`, and the `finished` frame is the completion signal.
- `search_closed` — `{search_id}`; that search was freed (by this or any other
  client) and is gone. Not the same as `finished`.

## Current state

| Piece | Location |
|---|---|
| The whole search view, single-search | `src/webapi/static/js/views/search.js` (347 lines) |
| One result map for everything | `views/search.js:65-77` (`resultsMap`, `flush`, `scheduleSync`) |
| Unaddressed calls | `views/search.js:86` (`api.get("search/results")`), `:163` (`api.post("search/stop")`) |
| *Search* disabled while running | `views/search.js:291` (`disabled=${searching}`) |
| The hardcoded single tab | `views/search.js:299-300` |
| SSE routing thrown away | `js/events.js:164-176` — two global keys, `search:result` / `search:progress` |
| Result fields the view never reads | `views/search.js` — `comments[]`, `kad_comment_search_running` and `children[]` are not referenced anywhere |
| The comments list to extract and share | `views/download-detail.js:240-296` (`DownloadComments`) |
| Tab strip component | `js/components.js:136-149` (`Tabs`: `tabs[{key,label,badge}]`, `active`, `onSelect`, `extra`) — no close affordance |
| Tab CSS | `css/app.css:602-622` (`.tabs`, `.tab`, `.tab-badge`), mobile overflow rule at `:828` |
| Table plumbing | `js/table.js:67-105` (`useTablePrefs`), `:131` (`VirtualTable`), `:37` (`sortRows`), `:107` (`ColumnPicker`) |
| Per-tab prefs idiom to copy | `views/clients.js:45-50` — `key=${…}` remounts the table so `useTablePrefs` re-reads its storage key |
| Store (module-level pub/sub, survives view unmount) | `js/store.js:11-31`, hook `js/dom.js:25-30` (`useStore`) |
| Live-data teardown on logout / dead session | `js/app.js:59`, `:184` (`data.stop()`), `js/events.js:56-74` |
| Peer table, where "View files" belongs | `views/client-table.js:40-88` (columns), `:147` (`ClientTable`), rows keyed by the peer's own EC handle (`client_ecid` on today's client object) |
| i18n | `static/i18n/en.json:150-191,502-503,526-533` (`search_*`), `es.json`; checker `node src/webapi/tools/check-i18n.mjs` |

## Requested change

### 1. Move search state out of the view

The view unmounts whenever the user navigates to another section, so tab state
cannot live in component state. Add **`static/js/searches.js`**: a module-level
registry keyed by `search_id`, publishing through the existing `store` (no
second pub/sub mechanism).

Per open search: `{id, query, kind, state, percent, count, results: Map(hash → result)}`
plus its own UI state — `selection`, `filter`, `filterHave`, `rowCat`, and the
last-seeded flag.

Publish on two granularities so a burst of results on a background tab never
re-renders the table:

- `store.set("searches", [...])` — the light tab-strip list (`id`, `query`,
  `kind`, `state`, `percent`, `count`), coalesced on a trailing ~1 s timer, the
  same throttle `views/search.js:70-77` uses today.
- `store.set("search:" + id, resultsArray)` — the heavy array, published **only
  for the active tab**. Background tabs accumulate into their `Map` and update
  their count; switching to one publishes its array once.

Prefer the `results` count from the last `search_progress` frame for the badge
when there is one (it is the backend's own map size and may legitimately run
ahead of the upserts we have seen), else the local map size.

Also export `reset()`, dropping every tab, and call it from both places that
already tear the live layer down: `js/app.js:59` (dead session) and `:184`
(logout). On the SSE `resync` event, re-seed instead of dropping.

### 2. Demux the SSE events by `search_id`

In `js/events.js:171-176`, key the store writes by id and stop clobbering:

```js
es.addEventListener("search_result_added", (ev) => {
  try { const p = JSON.parse(ev.data); store.set("search:" + p.search_id + ":result", p); } catch (_) {}
});
```

…and the same for `search_progress`, plus a new listener for `search_closed`.
`searches.js` subscribes once per open id and routes into that tab; a frame for
an id it does not know triggers adoption (§7).

### 3. Tab strip

Extend the shared `Tabs` component (`js/components.js:136`) with an optional
`onClose(key)`: when present, each tab renders a close button (`×`, with an
`aria-label`, `title`, and `stopPropagation` so it does not also select the
tab). Existing callers pass nothing and are unaffected.

- Keys: `Tabs` compares `tab.key === active` with `===`
  (`js/components.js:141-143`), so stringify the id once (`String(search_id)`)
  and use that everywhere — a numeric id against a string active key silently
  selects nothing.
- Label: the search's `query`, truncated (~24 chars) with the full string in
  `title`. A browse tab shows the peer's name, which is what `query` carries for
  `kind:"browse"`.
- Badge: the result count.
- A running search gets a `.tab.running` marker; the active tab's live
  `Searching… N%` text stays in the toolbar where it is today
  (`search_searching_fmt`).
- The strip must be `flex-wrap: nowrap` with `overflow-x: auto` on **all**
  widths, not just mobile (`css/app.css:828`): 20 wrapped tabs would eat the
  results area.
- Closing a tab: `DELETE /api/v0/search/{id}`, then drop it locally and activate
  a neighbour. A `404` is success — someone else already freed it.

### 4. Starting searches

The form on top keeps every field it has (query, type, file type, extension,
min availability, min/max size with unit) and every start opens a **new tab**
which becomes active:

- Remove `disabled=${searching}` from the *Search* button
  (`views/search.js:291`). Concurrent searches are the whole point; the only
  gate left is a non-empty query.
- Keep the query in the box after starting, so refining and re-running is one
  edit — each run is a new tab.
- On `202`, create the tab from `{search_id, query}` + the requested `type` as
  its kind, seed it `running` at 0 %, and let SSE fill it.

### 5. Per-tab toolbar

Acting on the **active** tab only:

| Control | Behaviour |
|---|---|
| *Stop* | `POST /search/{id}/stop`; enabled only while that tab is `running` |
| *Extend* | `POST /search/{id}/more`; **shown/enabled only when the active tab is a running Kad search**, mirroring the desktop button. A `400` is a toast, not a thrown error. |
| *Update results* | `GET /search/{id}/results`, authoritative replace of that tab's map |
| *Download* + category select | unchanged (`search/results/{hash}/download`), but reading the active tab's own selection |
| *Close tab* | as in §3 |
| *Close all* | one `DELETE` per open tab, in parallel, then clear the strip (the desktop's *Clear Search Results*) |

Table column prefs stay shared per tab **kind**, using the existing pattern from
`views/clients.js:45-50`: `useTablePrefs("search", …)` for query tabs and
`useTablePrefs("search-browse", …)` for browse tabs, with `key=` on the table so
switching between the two kinds remounts it. Selection, text filter, have/not-have
filter and per-row category live per tab, in the registry (§1) — switching tabs
and coming back must restore them.

### 6. Browse tabs ("View files")

`POST /api/v0/clients/{ecid}/shared_files` has never been called by the Web UI.
With tabs it fits exactly as it does on the desktop, where a browse is a tab in
the same notebook:

- `views/client-table.js` — add an `actions` column
  (`cls: "row-actions admin-only"`, like `views/search.js:246`) with a single
  *View files* icon button per peer, using the peer's own EC handle from the row
  — the field the peer table already keys rows by, whatever it is called at
  implementation time. The column
  rides the shared peer table, so it also appears in the detail panels' Clients
  tab, which is fine — it targets a peer, not a file.
- On `202`, open a tab from the returned `search_id` labelled with the peer's
  name, then navigate to `#/search` so the user lands on the tab that just
  opened. Keep that step generic — "open a browse tab for this `search_id` with
  this label" — so any future browse entry point (a friends list, say) reuses it
  instead of growing a second code path. Show a toast explaining the browse is asynchronous (a LowID peer needs
  a callback; a denied or unreachable peer finishes with zero files).
- A browse tab differs only in defaults: `directory` visible, `sources` /
  `rating` / `status` hidden, sorted by `directory` then `name`.

### 7. Adopting searches this browser did not start

On first mount (and whenever the registry is empty), `GET /api/v0/search` and
open a tab for every entry, using its `query`, `kind` and `state`. Fetch a tab's
results **lazily**, on first activation — adopting 20 searches must not fire 20
requests.

The same path handles a live surprise: a `search_progress` or
`search_result_added` frame for an unknown id means another client just started
a search. Re-run `GET /api/v0/search` (debounced, at most once every few
seconds) and add whatever is new. This is what amuleGUI does, and it is what
makes two browsers on the same daemon coherent.

`search_closed` for an open tab removes it, with a toast if it was the active
one. It is not `finished`: a finished search keeps its tab and its results.

A `404` on a tab's own `GET /search/{id}/results` means the same thing the hard
way — that search is gone from the daemon (freed elsewhere, or aged out of the
bounded set it keeps). Drop the tab with a toast; never retry the id.

### 8. Freshness and cost

- **SSE is the normal path** and its listeners are global (`js/events.js`), so
  tabs stay current even while the user is on another section. On returning to
  the view, render what the registry already holds — re-seed only the active tab,
  and only when SSE is not live.
- **Fallback polling** (`data.isLive()` false) belongs in the registry, not the
  view, and must not fan out: poll the active tab every 1.5 s and any other
  `running` tab every 5 s. Finished background tabs are not polled at all.
- Stop every timer when the view unmounts and when `reset()` runs.

### 9. The `directory` column

Add a `directory` column to the results table: `sortVal` on the string, hidden
by default for query tabs (which never carry it) and visible for browse tabs.
Sorting stays client-side through `sortRows`, like every other column here.

### 10. Community ratings/comments for a result

`GET /search/results/{hash}/comments` and its `POST` trigger, and every
result's own `comments[]` / `kad_comment_search_running`, have **no consumer in
the Web UI at all** — `views/search.js` never mentions either field. The desktop
has *Show all comments* per result (`src/SearchListCtrl.cpp:920-929`), which
opens the same dialog the download list uses, with a *Get from Kad* button. Add
the equivalent:

- A per-row action (icon button in the actions cell) opening a small panel or
  dialog for that hit: the comment count, a *Get from Kad* button
  (`POST /search/results/{hash}/comments`), and the list.
- No own-comment editor here, unlike the download panel: amuled only accepts a
  comment/rating on a *shared* file, and a search hit is not one.
- Extract the comments **list** markup out of `views/download-detail.js:240-296`
  (`DownloadComments`) into a shared component in `js/components.js` — next to
  the `CommentEditor` that already lives there — and use it from both. Same
  `comments_col_*` / `comments_none` / `comments_get_kad` keys, same
  `ratingLabel`; no new strings for the list itself.
- **Poll, do not wait for an event.** `comments_updated` is emitted only for
  downloads (`src/webapi/EventDiff.cpp:515-524`); a search hit's notes reach the
  API on read, so poll `GET /search/results/{hash}/comments` every ~2 s while
  `kad_comment_search_running` is `true`, and stop as soon as it clears. Cap the
  poll (the daemon's Kad lookup lives ~45 s) so a stuck flag cannot poll for
  ever.

### 11. Grouped results: alternative filenames

Every result carries `children[]` — the same file (same hash and size) advertised
by other peers under **different filenames**, each child with its own `ecid`,
`sources` and (on a browse) `directory`. The UI ignores the array, so a hit
advertised under five names looks like one row and always downloads under the
aggregated name.

Full expand/collapse tree rows are out of scope (`VirtualTable` is a flat
virtualised list, `js/table.js:131`). The functional gap is smaller than that:
being able to pick which advertised name to download.

- Show the count when `children.length > 0` — a badge on the name cell, with the
  alternative names in its `title`.
- In the row's download action, let the user pick one of the names; passing that
  child's `ecid` in the download body queues the file under it. The parent (no
  `ecid`) stays the default.

## Implementation checklist

**New**
- [ ] `static/js/searches.js` — the registry: open / close / adopt / reset,
      per-tab UI state, throttled publishes, the fallback poll schedule.

**Changed**
- [ ] `static/js/views/search.js` — rewritten around the registry: tab strip,
      per-tab table, per-tab toolbar, no `resultsMap`, no `search/results` or
      `search/stop` call, no `disabled=${searching}`, `directory` column,
      *Extend* button.
- [ ] `static/js/events.js:164-176` — per-`search_id` store keys; add the
      `search_closed` listener.
- [ ] `static/js/components.js:136-149` — optional `onClose` on `Tabs`.
- [ ] `static/js/views/client-table.js` — *View files* action column
      (admin-only) calling `clients/{ecid}/shared_files`.
- [ ] `static/js/components.js` — extract the comments list out of
      `views/download-detail.js:240-296` into a shared component, and use it
      from both the download detail panel and the new search-result comments
      panel.
- [ ] `static/js/app.js:59,184` — `searches.reset()` alongside `data.stop()`.
- [ ] `static/css/app.css:602-622,828` — `.tab-close`, non-wrapping scrollable
      strip at every width, `.tab.running` marker.
- [ ] `static/i18n/en.json` + `es.json` — new keys (tab close, close all,
      extend, view files, browse-started toast, adopted-search toast, directory
      column, search-freed toast, show-comments action, alternative-filenames
      badge); `node src/webapi/tools/check-i18n.mjs` passes. The comments list
      itself reuses the existing `comments_*` keys.

**Not touched**
- [ ] No C++, no `docs/`, no new dependency: no build step, no bundler, no
      runtime npm/CDN — the whole change is hand-written ES modules under
      `static/`, like the rest of this frontend.

## Acceptance criteria

- [ ] Three searches started back to back give three tabs, each keeping its own
      results, progress, selection and filters; switching between them loses
      nothing and starting a fourth disturbs none of them.
- [ ] Every search-scoped request carries its tab's id; nothing in
      `static/` calls `search/results` or `search/stop` any more
      (`grep -rn 'search/results\"\|search/stop' src/webapi/static` finds only
      the `results/{hash}/…` per-hit routes).
- [ ] Closing a tab frees that search on the daemon and leaves the others
      running; *Close all* clears the strip and frees all of them.
- [ ] *Extend* appears only for a running Kad tab, and widening it visibly adds
      results to that tab.
- [ ] *View files* on a peer opens a browse tab that fills as the peer answers,
      showing each file's remote folder, and reports honestly when the peer
      denies or never answers (tab finishes with zero files).
- [ ] A search started in amuleGUI (or a second browser) appears as a tab —
      both on page load and while the page is already open — and can be read,
      stopped and freed from there; freeing it in one browser makes its tab
      disappear from the other.
- [ ] A Kad search streaming hundreds of results into a **background** tab
      leaves the active tab's table smooth (no re-render per result), while the
      background tab's badge keeps counting up.
- [ ] A result's comments can be opened from a search tab, *Get from Kad*
      starts the lookup, and the retrieved notes appear without a reload —
      including on a search that already finished, which is the normal case.
- [ ] A result advertised under several filenames shows how many, and can be
      downloaded under a chosen one (the queued file carries that name).
- [ ] With SSE blocked, tabs still advance through the fallback poll, and no
      more than the active tab plus running tabs are polled.
- [ ] Reloading the page restores the tabs from the daemon, not from
      localStorage.
- [ ] Logging out and back in leaves no stale tab, no orphan timer and no
      request against the dead session.
- [ ] Guest sessions see results and can read comments but get no start / stop /
      extend / download / view-files controls (existing `admin-only` gate).
- [ ] Both locales complete, `check-i18n.mjs` clean, and no console errors in
      light and dark themes at desktop and mobile widths.

## Out of scope

- A persistent **search history** dropdown for the query box (the desktop's
  `CSearchHistory` and its *Clear Search History* button). It is a
  localStorage-only feature with no API involvement, worth doing on its own.
- A **"Search related files"** row action. The query is trivial to compose
  (`type: "local"`, `query: "related::<md4>…"`), but it only works against an
  ed2k server that advertises the related-search capability, and the API does not
  surface that capability today — a button that silently returns zero hits is
  worse than no button. Once the connected server's capability flags are
  readable, gating it is a one-liner and this becomes worth doing.
- Persisting tabs in `localStorage`. The daemon is the source of truth and lists
  its searches on request; a second cache would only be able to disagree with it.
- Per-tab column layouts. Prefs stay shared per tab kind (query vs browse).
- Expandable tree rows for grouped results (the desktop's *Expand all* /
  *Collapse all*). `VirtualTable` is a flat virtualised list; picking an
  alternative filename covers what the grouping is actually for.
- *Copy eD2k link* on a search result, and the desktop's "get stats for this
  file" web lookup.
- Server-side paging of results. The virtual table already handles the volumes
  involved (Kad caps a keyword search at 300 hits).
- Any change to the download queue, categories or preferences views.
