# Search panel: the **Category** dropdown is a download destination, not a search filter — move it out of "Extended Parameters"

## Summary

The desktop Search panel's **Extended Parameters** row holds six controls. Five
are search filters that go out with the query — File Type, Extension, Min Size,
Max Size, Availability. The sixth, **Category**, is not: nothing about it ever
reaches the core with the search. It is read once, much later, as the default
**download category** when the user presses **Download**
(`src/SearchListCtrl.cpp:1027-1036`).

Sitting in that row makes it read as "search only in this category", which aMule
cannot do — ed2k and Kad searches have no notion of your local categories. Worse,
the code took the neighbourhood literally and gated the value on the same
checkbox the real filters are gated on, so the category a user picked is
**silently dropped** whenever "Extended Parameters" is unticked:

```cpp
// src/SearchListCtrl.cpp:1031-1036
if (category == -1) {
        category = 0;
        if (CastByID(IDC_EXTENDEDSEARCHCHECK, NULL, wxCheckBox)->GetValue()) {
                category = CastByID(ID_AUTOCATASSIGN, NULL, wxChoice)->GetSelection();
        }
}
```

Tick **Extended Parameters**, pick a category, untick it again to get the screen
space back, press **Download** — everything lands in *Main*, with no warning and
no visible reason. The same conflation shows up twice more: choosing a category
alone is enough to enable the **Reset Fields** button
(`src/SearchDlg.cpp:1029`), and **Reset Fields** resets the category
(`src/SearchDlg.cpp:1549`) as though it were a search term.

This is a GUI-only fix. It affects both the monolithic client and `amulegui`,
which share the panel definition, and needs no core, EC or protocol change.

## Current state

| Piece | Location |
|---|---|
| The control | `src/muuli_wdr.cpp:256-261` — `wxStaticText _("Category")` + `wxChoice ID_AUTOCATASSIGN`, added to `item13` |
| `item13` is the collapsible extended-parameters sizer | `src/muuli_wdr.cpp:237` (`s_extended_sizer = item13`), shown/hidden at `src/SearchDlg.cpp:749` and hidden at startup at `:160` |
| The always-visible button row it should join | `src/muuli_wdr.cpp:336-373` (`item43`): Start │ Extend │ Stop │ **Download** │ Clear Search Results │ Reset Fields |
| The only reader | `src/SearchListCtrl.cpp:1027-1036` (`CSearchListCtrl::DownloadSelected`) |
| The "Extended Parameters" gate it borrowed | `src/SearchDlg.cpp:1359` — where the **real** filters are correctly gated |
| Counted as a search field for Reset Fields | `src/SearchDlg.cpp:1029` |
| Cleared by Reset Fields | `src/SearchDlg.cpp:1549` (in `OnBnClickedReset`) |
| Repopulated when categories change | `src/SearchDlg.cpp:1553-1567` (`UpdateCatChoice`), called from `src/amuleDlg.cpp:395`, `src/CatDialog.cpp:198`, `src/TransferWnd.cpp:157,286`, `src/GuiEvents.cpp:823` |
| What actually travels with a search | `CSearchList::CSearchParams` — `searchString`, `strKeyword`, `typeText`, `extension`, `minSize`, `maxSize`, `availability` (`src/SearchList.h:83-102`). No category field, in any build. |
| The explicit per-download alternative that already works | right-click → **Download in category** (`MP_ASSIGNCAT`, `src/SearchListCtrl.cpp:766-773`), which passes the category directly and ignores both the dropdown and the checkbox |

## Steps to reproduce the silent drop

1. Search tab → tick **Extended Parameters**.
2. Set **Category** to any category other than *Main*.
3. Untick **Extended Parameters** (the row hides; the choice keeps its value).
4. Run a search, select a result, press **Download**.
5. The download is added to *Main*. Expected: the category still shown as chosen,
   or no way to have chosen it at all.

A second, quieter case needs no unticking: the value persists across searches and
across result tabs, so a category picked for one search keeps applying to every
later download from any tab until someone changes it back.

## Requested change

**1. Move the control to the button row, next to Download.**

Move the `_("Category")` label and the `ID_AUTOCATASSIGN` choice out of `item13`
(`src/muuli_wdr.cpp:256-261`) into `item43` (`:336-373`), immediately after the
**Download** button and before the separator that precedes *Clear Search
Results*. That row is always visible, so the control can no longer be set and
then hidden, and its meaning becomes positional: it is the destination of the
button next to it.

**2. Relabel it so it cannot be read as a filter.**

`_("Category")` → `_("Download to category")` (or `_("Add to category")`).
This is a new translatable string; the existing bare `_("Category")` stays in use
elsewhere. Keep *Main* as the first entry, exactly as `UpdateCatChoice`
populates it today.

**3. Drop the "Extended Parameters" gate on the value.**

In `CSearchListCtrl::DownloadSelected` (`src/SearchListCtrl.cpp:1031-1036`),
read the choice unconditionally:

```cpp
if (category == -1) {
        category = CastByID(ID_AUTOCATASSIGN, NULL, wxChoice)->GetSelection();
}
```

The gate only existed because the control lived inside the gated row. Once it is
always visible, "what the user can see is what gets used" holds without it. Both
call sites use `CastByID(..., NULL, ...)`, i.e. `wxWindow::FindWindowById(id,
NULL)` (`src/OtherFunctions.h:188`), which is a global lookup — moving the
control between sizers of the same panel does not affect them.

**4. Stop treating it as a search parameter.**

- `src/SearchDlg.cpp:1029` — remove
  `enable |= (CastChild(ID_AUTOCATASSIGN, wxChoice)->GetSelection() > 0);` from
  `OnFieldChanged`. Picking a download destination is not a reason to offer
  **Reset Fields**; today it is the only control outside the search parameters
  that arms that button.
- `src/SearchDlg.cpp:1549` — remove the category reset from `OnBnClickedReset`.
  **Reset Fields** is the counterpart of **Reset Filters** and should clear
  search parameters only; silently sending the next download somewhere else is
  not part of that. (If maintainers prefer the button to clear the whole panel,
  keep this one line and drop only the `:1029` change — the two are
  independent.)

**5. Hide it when there is nothing to choose.**

With a single category configured, the selector offers only *Main* and is pure
noise. Disable (or hide) it when `theApp->glob_prefs->GetCatCount() <= 1`,
mirroring the gate the context menu already applies to its **Download in
category** submenu (`menu.Enable(MP_MENU_CATS, (theApp->glob_prefs->GetCatCount() > 1))`,
`src/SearchListCtrl.cpp:795`). `UpdateCatChoice` (`src/SearchDlg.cpp:1553-1567`)
already runs on every category add / rename / delete, so it is the natural place
to apply it.

**6. Leave the right-click path alone.**

**Download in category** (`MP_ASSIGNCAT`) passes an explicit category and must
keep overriding the dropdown for that one action, which is what
`DownloadSelected(int category)`'s `category != -1` branch already does.

## Implementation checklist

- [ ] `src/muuli_wdr.cpp` — move the label + `ID_AUTOCATASSIGN` choice from
      `item13` to `item43` after `IDC_SDOWNLOAD`, with a separator matching the
      row's existing rhythm; drop the now-orphaned static line in `item13` if the
      row's separators no longer line up.
- [ ] `src/muuli_wdr.cpp` — new label string `_("Download to category")`.
- [ ] `src/SearchListCtrl.cpp:1031-1036` — read the choice unconditionally.
- [ ] `src/SearchDlg.cpp:1029` — drop the category from `OnFieldChanged`'s
      dirty test.
- [ ] `src/SearchDlg.cpp:1549` — drop the category from `OnBnClickedReset`.
- [ ] `src/SearchDlg.cpp:1553-1567` — `UpdateCatChoice` disables/hides the
      selector while `GetCatCount() <= 1`, and re-enables it as soon as a second
      category exists.
- [ ] `po/` — no action beyond the usual extraction: `src/muuli_wdr.cpp` is
      already listed in `po/POTFILES.in:60`, so the new label is picked up like
      any other string. No other string changes.
- [ ] Verify in **both** builds — monolithic `amule` and `amulegui` — since
      `muuli_wdr.cpp` is shared. `muuli_wdr.cpp` is hand-maintained (the
      `muuli.wdr` wxDesigner source is no longer round-trip-able,
      `src/muuli_wdr.cpp:25-28`), so this is an ordinary source edit.
- [ ] No core, EC, `CSearchParams` or preferences change.

## Acceptance criteria

- [ ] The category selector is visible whenever the Download button is, and is
      not affected by the **Extended Parameters** checkbox.
- [ ] A category chosen in the panel is applied to a download started from the
      **Download** button, from double-clicking a result
      (`OnItemActivated` → `DownloadSelected()`, `src/SearchListCtrl.cpp:803-816`)
      and from the context menu's plain **Download** (`MP_RESUME`, `:1021`), with
      **Extended Parameters** both ticked and unticked.
- [ ] Right-click → **Download in category** still wins over the panel's
      selection for that action.
- [ ] Its label states that it is a download destination, and no user-visible
      string suggests searches can be restricted to a category.
- [ ] Choosing a category alone does not enable **Reset Fields**, and pressing
      **Reset Fields** does not change the download destination.
- [ ] Adding, renaming or removing a category still repopulates the choice
      (`UpdateCatChoice`) with *Main* first and a valid selection afterwards.
- [ ] With only *Main* configured the selector is not offered; creating a second
      category makes it available without restarting the client.
- [ ] Both `amule` and `amulegui` show the same, working control.

## Out of scope

- Remembering a **per-tab** or per-search category. Today the selection is
  global to the panel and stays that way; this issue only makes it visible and
  reliable.
- Adding a category column, or any grouping by category, to the search results.
- Restricting a *search* by category. It is not a thing ed2k or Kad can do, which
  is the whole reason the control has to stop looking like it.
- The REST API. `POST /api/v0/search/results/{hash}/download` already takes an
  explicit `category` per call, and `POST /api/v0/search` correctly has no
  category parameter, so nothing there is affected.
