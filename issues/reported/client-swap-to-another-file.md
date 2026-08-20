# amuleapi: expose per-source "Swap to this file" (`EC_OP_CLIENT_SWAP_TO_ANOTHER_FILE`), the last A4AF action the REST API is missing

## Summary

The GUI's peer context menu offers **Swap to this file**: in a download's source
list, take *one* A4AF source — a peer that holds this file but is currently
serving another — and force it onto this file right now. `amuleapi` cannot do
this. It exposes only the three **file-wide** A4AF actions
(`swap_this` / `swap_this_auto` / `swap_others` on
`POST /api/v0/downloads/{hash}/a4af`), which operate on *every* source of a file
at once. There is no way to move a single source.

The daemon has supported the per-source action for years:
`EC_OP_CLIENT_SWAP_TO_ANOTHER_FILE` (`0x54`) is fully implemented in
`amuled` and is what amulegui already sends. Nothing new is needed in the core
protocol — this is REST-layer plumbing, plus one small (recommended, optional)
core fix so the caller can tell whether the swap actually happened.

With this in, `amuleapi` covers the complete peer context menu, closing the last
gap that is not already tracked by
[friends](reported/friends-rest-api.md) (Add/Remove Friend, Friend Slot) and
[chat](reported/chat-rest-api.md) (Send message).

## Current state

| Piece | Location |
|---|---|
| GUI menu entry (`MP_CHANGE2FILE`) | `src/ClientContextActions.cpp:61`; enabled only for A4AF rows, `:63-64` |
| GUI action → core call | `src/GenericClientListCtrl.cpp:546-557` — `OnSwapSource`, passes the **owner file** as target |
| Core implementation | `src/DownloadClient.cpp:1522-1639` — `CUpDownClient::SwapToAnotherFile(bIgnoreNoNeeded, ignoreSuspensions, bRemoveCompletely, toFile)` |
| EC opcode | `src/libs/ec/abstracts/ECCodes.abstract:149` — `EC_OP_CLIENT_SWAP_TO_ANOTHER_FILE 0x54` |
| EC handler (daemon side) | `src/ExternalConn.cpp:3714-3723` |
| amulegui sender (reference client) | `src/amule-remote-gui.cpp:3990-4002` |
| File-wide A4AF actions in core | `src/GuiEvents.cpp:846-869` — `PartFile_Swap_A4AF`, `_Auto`, `_Others` |
| File-wide A4AF ops over EC | `src/ExternalConn.cpp:2253-2261`, `:3651-3653` |
| **amuleapi: A4AF routes** | `src/webapi/Api.cpp:1179-1196` |
| **amuleapi: A4AF read handler** | `src/webapi/Api.cpp:3304` — `HandleDownloadA4af`, serializer `WriteA4afObject` at `:3289` |
| **amuleapi: A4AF action handler** | `src/webapi/Api.cpp:3334` — `HandleDownloadA4afAction` (the three file-wide actions) |
| A4AF source list in the snapshot | `src/webapi/State.h:196-197` — `download.a4af_auto`, `download.a4af_sources` (client ECIDs); filled by `src/webapi/Refresher.cpp:597-609` |
| Client lookup by ECID | `src/webapi/Api.cpp:4385` — `FindClientByEcid` (file-local anonymous namespace, declared *after* the A4AF handlers) |
| Existing docs | `docs/api/REFERENCE.md:782-819` |

### What the core action actually does

`SwapToAnotherFile(true, false, false, toFile)` — exactly the argument set both
the GUI (`GenericClientListCtrl.cpp:555`) and the EC handler
(`ExternalConn.cpp:3720`) use:

1. Returns **false** immediately if the peer has no request file, or if it is in
   `DS_DOWNLOADING` (aMule refuses to swap away a source that is actively
   sending data).
2. Looks `toFile` up in the peer's own `m_A4AF_list`. If the peer is not an A4AF
   source *of that file*, there is no target and the call returns **false**.
3. Otherwise: removes the peer from its current request file, adds it as an A4AF
   source there, removes it from the target's A4AF list, makes the target the new
   request file, resets download state, and fires the usual
   `Notify_SourceCtrl*` notifications.

So the action is inherently a **(source, file)** pair, and it is best-effort:
several ordinary conditions make it a no-op.

## EC protocol reference

Request — `EC_OP_CLIENT_SWAP_TO_ANOTHER_FILE` (`0x54`), two flat tags:

| Tag | Value |
|---|---|
| `EC_TAG_CLIENT` (`0x0600`) | the peer's **ECID** (uint32) |
| `EC_TAG_PARTFILE` (`0x0300`) | the target partfile's **MD4 hash** |

Reply — always `EC_OP_NOOP`. `ExternalConn.cpp:3714-3723` reads both tags with
`GetTagByNameSafe`, resolves them with `FindClientByECID` /
`GetFileByID`, and calls `SwapToAnotherFile` only `if (client && file)` —
**discarding the bool**. An unknown ECID, an unknown hash, a peer that is
downloading, and a successful swap are all indistinguishable to the caller.

## Requested change — REST surface

Extend the **existing** action endpoint with an optional source selector rather
than adding a route:

### `POST /api/v0/downloads/{hash}/a4af`

**Auth:** `ADMIN` (unchanged)

**Body:** `{ "action": "swap_this", "client_ecid": 1234 }`

`client_ecid` is optional and **only valid with `action: "swap_this"`**:

| Body | Effect | EC op sent |
|---|---|---|
| `{"action":"swap_this"}` | unchanged — every A4AF source of this file takes it over | `EC_OP_PARTFILE_SWAP_A4AF_THIS` |
| `{"action":"swap_this","client_ecid":N}` | **new** — only peer `N` is swapped onto this file | `EC_OP_CLIENT_SWAP_TO_ANOTHER_FILE` |
| `{"action":"swap_this_auto"\|"swap_others", "client_ecid":N}` | `400 bad_request` — these have no per-source form in the core | — |

**Response:** `200 OK`, the post-action A4AF view — the same shape the endpoint
already returns (`WriteA4afObject`, `{ "a4af_auto": …, "sources": [ … ] }`).
A successful single-source swap is visible as `client_ecid` having **left**
`sources`.

`client_ecid` (not `ecid`) per the naming rule in
[api-ecid-key-naming.md](reported/api-ecid-key-naming.md): a reference to
*another* object's EC handle carries the owner prefix.

**Rejected alternative:** `POST /api/v0/clients/{ecid}/swap` with the hash in the
body. Same wire result, but it puts a file-scoped action on the client resource,
needs a new route + handler, and splits the A4AF documentation across two
sections. The action is (source, file) either way; keeping it on the file that
already owns the A4AF resource is the smaller change.

### Validation, in this order

1. Body parses, `action` present and known — existing code.
2. `client_ecid`, when present, is a non-negative integer, and `action` is
   `swap_this` → else `400 bad_request`.
3. `{hash}` resolves against the snapshot (`m_state.FindDownload`) → else
   `404 not_found` — existing code.
4. `client_ecid` is in the current client snapshot → else `404 not_found`
   (`"no client with that ECID in the current snapshot"`, matching
   `HandleClientDetail`, `Api.cpp:4529`).
5. `client_ecid` is present in this download's `download.a4af_sources` → else
   `409 conflict` (`"that client is not an A4AF source of this download"`).
   The snapshot already carries the list, so this check is free and it is what
   makes the endpoint honest: the core would silently no-op instead.

Note that `FindClientByEcid` (`Api.cpp:4385`) sits in the file-local anonymous
namespace *below* `HandleDownloadA4afAction` (`:3334`); move the helper above the
A4AF handlers (it is already shared by two call sites) rather than adding a
second copy.

### Error matrix

| Status | `code` | When |
|---|---|---|
| `400` | `bad_request` | missing/unknown `action`; `client_ecid` not an integer; `client_ecid` with `swap_this_auto` / `swap_others` |
| `403` | `forbidden` | guest token |
| `404` | `not_found` | no download with that hash; no client with that ECID |
| `409` | `conflict` | the client is not an A4AF source of this download |
| `400` | `amuled_rejected` | the daemon answered `EC_OP_FAILED` (only reachable with the core change below) |
| `503` | `ec_unavailable` | no first snapshot yet, or the EC roundtrip failed |

## Recommended core-side change (small)

Make the EC handler report what happened instead of answering `EC_OP_NOOP`
unconditionally (`src/ExternalConn.cpp:3714-3723`):

- unknown ECID → `EC_OP_FAILED` `"Client not found."` (the wording
  `Get_EC_Response_Friend` already uses for the same condition)
- unknown partfile hash → `EC_OP_FAILED` `"File not found."`
- `SwapToAnotherFile()` returned false → `EC_OP_FAILED`
  `"Client could not be swapped to that file."`
- success → `EC_OP_NOOP`, as today

This is backward compatible. amulegui sends the op through
`CRemoteConnect::SendPacket` (`src/amule-remote-gui.cpp:3999`), which registers a
**null** handler in the request FIFO (`RemoteConnect.cpp:634-637`), so the reply
is popped and discarded whatever its opcode — nothing to update on that side.

Without it, `amuleapi` can only report "the request was delivered"; the
`DS_DOWNLOADING` refusal in particular is a completely ordinary outcome that the
user would otherwise see as a silent success. Case 3 (`false`) is the one that
matters; cases 1-2 are already covered by the REST-side validation and are there
for symmetry.

If this part is dropped, the REST handler must still respond `200` with the
refreshed A4AF view — the client compares `sources` before/after — and the
documentation must say the action is best effort.

## Refresh and SSE behaviour

`HandleDownloadA4afAction` already calls `RefresherTick` before serializing the
reply (`Api.cpp:3396-3405`), so the response reflects the post-swap state and no
extra plumbing is needed.

The swap moves the peer between the two files' source lists, which changes
`sources.a4af` / `sources.total` on **both** downloads, and the peer's
`download_file_hash`. Those all ride the existing snapshot diff, so the existing
`download_updated` / `client_updated` SSE events fire on their own — **no new
event type**. Worth stating in the docs: a per-source swap emits events for two
downloads, not one.

## Implementation checklist

- [ ] `src/webapi/Api.cpp` — move `FindClientByEcid` above the A4AF handlers.
- [ ] `src/webapi/Api.cpp:3334` `HandleDownloadA4afAction` — parse optional
      `client_ecid`, run the five validation steps, and branch: with the field,
      send `EC_OP_CLIENT_SWAP_TO_ANOTHER_FILE` carrying `EC_TAG_CLIENT` +
      `EC_TAG_PARTFILE`; without it, the existing three-op path.
- [ ] `src/ExternalConn.cpp:3714-3723` — answer `EC_OP_FAILED` on
      client-not-found / file-not-found / swap-refused (recommended, above).
- [ ] `docs/api/REFERENCE.md:801-819` — document `client_ecid` in the
      `POST /downloads/{hash}/a4af` body table, the `409`, the two-download SSE
      effect, and the best-effort caveat if the core change is skipped.

## Acceptance criteria

- [ ] With peer `N` listed in `GET /downloads/{hash}/a4af` → `sources`,
      `POST {"action":"swap_this","client_ecid":N}` returns `200` and `N` is gone
      from `sources` in the response body.
- [ ] The same swap performed from the monolithic GUI's context menu and from the
      REST endpoint produce the same core state (peer's request file changed, old
      file gained it as an A4AF source).
- [ ] `POST {"action":"swap_this"}` with no `client_ecid` behaves exactly as
      before this change (all A4AF sources swapped).
- [ ] `client_ecid` pointing at a live peer that is *not* an A4AF source of this
      download → `409 conflict`, and nothing changed in the core.
- [ ] `client_ecid` pointing at an unknown/stale ECID → `404 not_found`.
- [ ] `client_ecid` alongside `swap_this_auto` or `swap_others` → `400 bad_request`.
- [ ] Guest token → `403 forbidden`; the swap is not sent.
- [ ] With the core change: swapping a peer in `DS_DOWNLOADING` returns
      `400 amuled_rejected` rather than a false success.
- [ ] An SSE subscriber sees `download_updated` for both the source's old file and
      the target file after one per-source swap.

## Out of scope

- The Web UI. Listing the A4AF sources in the download detail (so a user can pick
  one) is already tracked in
  [web-ui-unused-api-endpoints.md](web-ui-unused-api-endpoints.md) §8; the
  per-source button belongs with that work, once this endpoint exists. Note that
  [clients-per-file.md](clients-per-file.md) proposes replacing the *read* half
  (`GET /downloads/{hash}/a4af`) with `GET /downloads/{hash}/clients` rows
  carrying an `a4af` flag; that proposal keeps this `POST` and its reply body
  unchanged, so the two issues can land in either order.
- A bulk form (`"client_ecids": [...]`). One call per source is enough; add it if
  a client ever reports needing it.
- The other arguments of `SwapToAnotherFile` (`ignoreSuspensions`,
  `bRemoveCompletely`). Neither the GUI nor EC exposes them; the API should not
  be the first.
- `GET /clients/{ecid}` gaining an "A4AF for these files" list. Useful, but a
  separate read-side change — the daemon ships the relation per file, not per
  client.
