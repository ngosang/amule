# amuleapi: expose the IP-filter Reload / Update actions, which EC has carried for years

## Summary

The desktop Preferences → Security → IP-Filtering page has two buttons that act
on the **core**, and neither has any surface in `/api/v0/`:

| Desktop button | What it does |
|---|---|
| **Reload List** | Re-reads `ipfilter.dat` + `ipfilter_static.dat` from the core's config directory into the live filter |
| **Update now** | Downloads `ipfilter.dat` from the configured URL, swaps it in, then reloads |

Every *setting* on that page is already mapped — `security.ipfilter_clients`,
`ipfilter_servers`, `ipfilter_auto_update`, `ipfilter_update_url`,
`ipfilter_block_below_access_level`, `ipfilter_include_lan_ips`,
`reject_spoofed_source_ips`, `use_system_ipfilter`
(`src/webapi/PrefsSchema.cpp:184-196`). Only the two *actions* are missing, so an
API client can configure an update URL it can never trigger, and can never make
the daemon pick up an `ipfilter.dat` dropped into its config directory.

This needs **no protocol work**: both operations have been EC opcodes for years
(`EC_OP_IPFILTER_RELOAD` = `0x2B`, `EC_OP_IPFILTER_UPDATE` = `0x51`,
`src/libs/ec/abstracts/ECCodes.abstract:96,143`), the core handles them
(`src/ExternalConn.cpp:3836-3849`), and `amulegui` already drives them remotely
(`src/amule-remote-gui.cpp:1961-1973`). `amuleapi` just never grew the two
routes.

One small core fix rides along: **an IP-filter update does not persist the URL it
was given**, unlike its two siblings. Both `EC_OP_SERVER_UPDATE_FROM_URL`
(`src/ExternalConn.cpp:3804`) and `EC_OP_KAD_UPDATE_FROM_URL`
(`src/ExternalConn.cpp:4179`) write the URL back into the preferences before
starting the download, so "update from this URL" and "remember this URL" are one
action for `server.met` and `nodes.dat`. `CIPFilter::Update()` keeps it in a
member only (`src/IPFilter.cpp:479-492`), so an operator who updates from a URL
finds `security.ipfilter_update_url` unchanged afterwards and the next
auto-update at startup silently uses the old one. See
[Persist the URL](#persist-the-url-core).

`/api/v0/` is experimental and has no consumers outside this repository, so the
routes land directly rather than waiting for a `v1`.

## Current state

| Piece | Location |
|---|---|
| EC opcodes | `src/libs/ec/abstracts/ECCodes.abstract:96` (`EC_OP_IPFILTER_RELOAD`), `:143` (`EC_OP_IPFILTER_UPDATE`) |
| Core handlers | `src/ExternalConn.cpp:3836-3849` — both reply `EC_OP_NOOP`; `UPDATE` reads the URL from the packet's first tag and falls back to `thePrefs::IPFilterURL()` when it is empty |
| Core implementation | `src/IPFilter.cpp:406-409` (`Reload()` → `CThreadScheduler` task), `:479-492` (`Update()` → `CHTTPDownloadThread`), `:494-522` (`DownloadFinished()` → swap + reload) |
| The two siblings that *do* persist their URL | `src/ExternalConn.cpp:3804` (`thePrefs::SetEd2kServersUrl`), `:4179` (`thePrefs::SetKadNodesUrl`) |
| The preference the IP filter fails to write | `src/Preferences.h:688-689` (`IPFilterURL()` / `SetIPFilterURL()`); startup auto-update reads it at `src/IPFilter.cpp:554` |
| Remote-GUI client (the shape to copy) | `src/amule-remote-gui.cpp:1961-1973` — `Reload()` sends the bare op; `Update()` sends `CECTag(EC_TAG_STRING, url)` |
| Desktop buttons | `src/PrefsUnifiedDlg.cpp:2231-2239`; widgets `IDC_IPFRELOAD` / `IDC_IPFILTERUPDATE` (`src/muuli_wdr.cpp:2884`) |
| Nearest existing routes to copy | `POST /api/v0/shared/reload` (`src/webapi/Api.cpp:7634-7647`), `POST /api/v0/kad/update` (`:6672-6726`), helper `SimpleConnControlOp` (`:6514`) |
| Configured URL in the API's own snapshot | `src/webapi/State.h:829` (`security.ipfilter_update_url`) |

## Requested change

### `POST /api/v0/ipfilter/reload`

**Auth:** `ADMIN`. No body.

Sends `EC_OP_IPFILTER_RELOAD`. The core queues a `CIPFilterTask` and keeps the
current filter live until the new one finishes loading, so this is asynchronous.

```sh
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://$HOST/api/v0/ipfilter/reload"
```

**Response:** `202 Accepted` → `{ "ok": true }`

**Errors:** `400 amuled_rejected`, `403 forbidden` (guest), `405 method_not_allowed`,
`503 ec_unavailable`.

### `POST /api/v0/ipfilter/update`

**Auth:** `ADMIN`.

**Body (optional):** `{ "ipfilter_url": "http://example.com/ipfilter.dat" }`

- When `ipfilter_url` is present it must be a non-empty `http://` or `https://`
  string — the same scheme gate `POST /kad/update` and `POST /servers/update`
  apply, because the core hands the string straight to the HTTP downloader and a
  bad scheme would otherwise fail asynchronously with nowhere to report it.
- When it is **absent**, the configured `security.ipfilter_update_url` is used.
  amuleapi resolves that itself from its own preferences snapshot
  (`src/webapi/State.h:829`) and sends the resolved value, so the behaviour does
  not depend on which amuled build answers. If both are empty, reject with
  `400 bad_request` ("no ipfilter URL configured") rather than sending a request
  the core turns into a silent no-op (`CIPFilter::Update()` returns immediately
  on an empty URL).

An explicit `ipfilter_url` is **persisted** into `security.ipfilter_update_url`,
so a subsequent `GET /preferences` reflects it and the next auto-update at
startup uses it — the same side effect `POST /servers/update` and
`POST /kad/update` already have. That persistence belongs in the core, not here;
see [Persist the URL](#persist-the-url-core) below.

Always send the URL as `CECTag(EC_TAG_STRING, url)`, matching
`CIPFilterRem::Update()`.

```sh
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"ipfilter_url":"http://upd.emule-security.org/ipfilter.zip"}' \
  "http://$HOST/api/v0/ipfilter/update"
```

**Response:** `202 Accepted` → `{ "ok": true, "ipfilter_url": "..." }` — echoing
the effective URL, so a caller that omitted it learns which one ran.

**Errors:** `400 bad_request` (non-string / empty / non-http(s) `ipfilter_url`,
or no URL available at all), `400 amuled_rejected`, `403 forbidden`,
`405 method_not_allowed`, `503 ec_unavailable`.

## Persist the URL (core)

"Update from this URL" and "remember this URL" are one action for the other two
list downloads, and should be for this one too:

| Operation | Persists the URL it was handed |
|---|---|
| `EC_OP_SERVER_UPDATE_FROM_URL` | yes — `thePrefs::SetEd2kServersUrl(url)`, `src/ExternalConn.cpp:3804` |
| `EC_OP_KAD_UPDATE_FROM_URL` | yes — `thePrefs::SetKadNodesUrl(url)`, `src/ExternalConn.cpp:4179` |
| `EC_OP_IPFILTER_UPDATE` | **no** |

The consequence is not cosmetic: `security.ipfilter_auto_update` re-downloads
from `thePrefs::IPFilterURL()` at every startup (`src/IPFilter.cpp:554`), so a
URL used for a manual update is forgotten and the old one silently comes back on
the next run.

Put the write in **`CIPFilter::Update()`** (`src/IPFilter.cpp:479`) rather than in
the EC handler, because unlike the server and Kad cases that one function is the
single funnel for every caller — the EC op, the desktop **Update now** button
(`src/PrefsUnifiedDlg.cpp:2236-2239`, which passes the text field's current value
straight in) and the startup auto-update. One line there makes all three
consistent; the startup path writes back the value it just read, which is a
no-op.

Two deliberate non-changes:

- **No `Notify_*` for the widget.** The server and Kad handlers pair their write
  with `Notify_ServersURLChanged` / `Notify_NodesURLChanged`
  (`src/GuiEvents.cpp:212-224`) because those text boxes live on the always-present
  Networks tab. The IP-filter URL box (`IDC_IPFILTERURL`) exists only while the
  modal Preferences dialog is open, and that dialog loads its values from the
  preferences each time it opens, so there is nothing to refresh.
- **The dialog-open race is pre-existing.** If Preferences is open when a REST
  client updates the URL, pressing OK writes the dialog's older value back. That
  is true of every EC-settable preference today and is out of scope here.

## Reading the outcome

Both operations report only through the core's log, exactly like
`POST /shared/{hash}/verify` does. Document the lines a caller can watch for on
`GET /api/v0/logs/amule` or the `log` SSE channel — they are gettext-translated
at the daemon's locale and carry no correlation id, so they are human-readable
output and not a machine-parseable contract:

- `Loading IP filters 'ipfilter.dat' and 'ipfilter_static.dat'.` (`src/IPFilter.cpp:108`)
- `IP filter is ready` (`:537`)
- `Successfully updated ipfilter.dat` (`:509`)
- `Failed to download ipfilter.dat from <url>` (`:516`)

## Why two endpoints and not two preference triggers

`ip2country` exposes its refresh as a write-only `update_now` preference
(`src/webapi/PrefsSchema.cpp:256`), and copying that here would be the wrong
call: it works for GeoIP only because EC genuinely carries that refresh **as a
preference tag** (`EC_TAG_IP2COUNTRY_UPDATE_NOW`, handled in
`src/ECSpecialMuleTags.cpp:1017-1025`). The IP filter's two operations are
standalone opcodes that already exist; wrapping them in new preference tags would
add protocol surface duplicating protocol we already have, and would make a
`PATCH /preferences` silently start a network download. Dedicated `POST` routes
also match every other action the API exposes — `/shared/reload`,
`/servers/update`, `/kad/update`, `/kad/bootstrap`, `/version/check`.

## Implementation checklist

**Core (`src/`)**
- [ ] `IPFilter.cpp:479` — `CIPFilter::Update()` writes
      `thePrefs::SetIPFilterURL(strURL)` before starting the download, so the EC
      op, the desktop button and the startup auto-update all agree on the stored
      URL.
- [ ] No EC change: the opcodes and the preference tag
      (`EC_TAG_IPFILTER_UPDATE_URL`) both already exist.

**amuleapi (`src/webapi/`)**
- [ ] `Api.h` / `Api.cpp` — `HandleIpfilterReload` and `HandleIpfilterUpdate`,
      plus their route entries in the dispatch chain (alongside the other action
      routes, e.g. after the `/kad/bootstrap` block at `Api.cpp:953-961`), with
      `405` for any verb other than `POST`.
- [ ] `Api.cpp` — reload can reuse
      `SimpleConnControlOp(m_app, m_state, EC_OP_IPFILTER_RELOAD, 202)` verbatim;
      update follows `HandleKadUpdateFromUrl` (`:6672`), including its
      persistence semantics, plus the "fall back to the configured URL, else
      `400`" resolution.
- [ ] No preference-schema change: `security.ipfilter_update_url` is already
      mapped (`src/webapi/PrefsSchema.cpp:189`), so the persisted value shows up
      on the next `GET /preferences` with no further work.

**Docs (`docs/api/`)**
- [ ] `REFERENCE.md` — a new **IP filter** section with both endpoints, and the
      two index entries under a new heading next to **Logs** / **Network control**.
- [ ] `REFERENCE.md` — state that `POST /ipfilter/update` persists the URL into
      `security.ipfilter_update_url`, and that the outcome of both operations is
      only observable in the amule log.
- [ ] `REFERENCE.md` — while there: `POST /api/v0/servers/update` persists
      `servers.update_url` (`src/ExternalConn.cpp:3804`) and the reference never
      says so, unlike the `POST /kad/update` entry which documents its
      persistence. Add the sentence so all three read alike.

**Web UI (`src/webapi/static`) — same change, not a follow-up**
- [ ] `views/preferences.js` — attach an action button to the existing
      `ipfilter_update_url` text field, exactly like the `servers/update` and
      `kad/update` rows at `:113-116` and `:126-129`:
      `action: { path: "ipfilter/update", body: "ipfilter_url", titleKey: …, toastKey: … }`.
- [ ] `views/preferences.js` — extend `runAction` (`:485-490`) and its renderer
      (`:472-479`) to support a **bodyless** action (an action with no `body` key:
      no URL required, `api.post(path)` with no payload), and add the Reload
      button to the `prefs_group_ipfilter` group with it. This is the only new UI
      machinery needed.
- [ ] `i18n/en.json` + `i18n/es.json` — `prefs_action_ipfilter_reload`,
      `prefs_action_ipfilter_reload_toast`, `prefs_action_ipfilter_update`,
      `prefs_action_ipfilter_update_toast`; `node src/webapi/tools/check-i18n.mjs`
      passes.

**Tests (`unittests/curl-tests/amuleapi/`)**
- [ ] New `34-ipfilter-actions.sh`: `POST /ipfilter/reload` → `202`;
      `POST /ipfilter/update` with an explicit URL → `202` echoing it; with no
      body and a configured URL → `202` echoing the configured one; with no body
      and no configured URL → `400`; an `ftp://` URL → `400`; a guest token →
      `403`; `GET` → `405`. Plus: after an update with an explicit URL,
      `GET /preferences` reports it as `security.ipfilter_update_url`.

## Acceptance criteria

- [ ] An `amuled` + `amuleapi` deployment can reload and update its IP filter over
      REST, with no GUI process anywhere, and read the outcome from
      `GET /api/v0/logs/amule`.
- [ ] `POST /api/v0/ipfilter/update` with no body uses
      `security.ipfilter_update_url` and echoes it; with no body and no configured
      URL it fails loudly with `400` instead of doing nothing.
- [ ] `POST /api/v0/ipfilter/update` with an explicit URL leaves that URL in
      `security.ipfilter_update_url`, so the next `GET /preferences` shows it and
      the next startup auto-update uses it — the same behaviour
      `POST /servers/update` and `POST /kad/update` already have.
- [ ] The desktop **Update now** button and `amulegui` store the URL too: they go
      through the same `CIPFilter::Update()`.
- [ ] Both routes reject guests with `403` and non-`POST` verbs with `405`.
- [ ] The bundled web UI's Security page has working Reload and Update buttons in
      both locales.

## Out of scope

- A `GET /api/v0/ipfilter` status resource (loaded range count, ready flag).
  `CIPFilter::BanCount()` is not carried over EC at all, so it would need new
  protocol surface; the stats tree's filtered-client / filtered-server counters
  already answer "is it doing anything".
- Editing `ipfilter.dat` / `ipfilter_static.dat` content through the API.
- Any change to the IP-filter *settings*, which are already exposed on
  `GET`/`PATCH /api/v0/preferences`.
