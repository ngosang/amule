# API inventory

`API_INVENTORY.md` is an inventory of every endpoint `amuleapi` serves, extracted
from `src/webapi` rather than written by hand: paths, methods, auth level, query
parameters, request bodies, response shapes, error codes and behaviour notes, one
section per endpoint.

It exists because `docs/api/REFERENCE.md` drifts from the code. This file is
regenerated from the sources instead of being edited in place.

## Scripts

| Script | Role |
|---|---|
| `apiscan.py` | Library, not a command. Slices a C++ file into its top-level function definitions. Comments and string-literal *contents* are blanked before brace counting, so a `{` inside a comment or a JSON literal cannot desync the depth tracking. |
| `routes.py` | Lifts the route table out of `CApiDispatcher::DispatchToHandler`: every `path == "…"` literal, every `ParsePattern("…")`, the methods compared against, the handler each one calls, and the `405` / `404` texts. → `routes.json` |
| `scan.py` | Per function: every `ErrorResponse` / `BadRequestPtr` / `BulkErr` call (parsed with a paren- and quote-aware scanner, so a `;` or `,` inside a message is safe), every `qmap.find("…")` query key, every `obj.find("…")` body field, the `ListComparators` sort keys, the auth / admin / snapshot gates, and a JSON response skeleton folded from the ordered `CJsonWriter` calls. → `facts.json` |
| `prefs.py` | The `PrefsSchema.cpp` data table: category, key, type, access level, bounds, enum values, capability gates. → `prefs.json` |
| `gendoc.py` | Joins those three JSON files with the per-endpoint prose and writes `API_INVENTORY.md`. Also re-anchors every `File.cpp:NNN` reference in the prose to the function's current line. |

The `*.json` files are throwaway intermediates — regenerate them, don't commit
them.

## Regenerating

```sh
cd issues/inventory
python3 scan.py facts.json && python3 routes.py routes.json \
  && python3 prefs.py prefs.json && python3 gendoc.py
rm -f facts.json routes.json prefs.json
```

`gendoc.py` writes `API_INVENTORY.md` next to itself; pass a path to write
somewhere else. Python 3 only, no dependencies. Paths are resolved from the
script's own location, so the directory can be moved as a unit.

`gendoc.py` **exits non-zero** when a route block in `DispatchToHandler` or a
`Handle*` function is not documented, so a new endpoint cannot be added to the
API without this file noticing. When that happens, add an `ep(...)` entry (or
an `errors_from=` reference for a delegating handler) in `gendoc.py` — the prose
annotations live there, the mechanical data does not.

## What is hand-written and what is not

Mechanical (regenerated, never edit in the `.md`): the error tables, response
skeletons, sort-key lists, the preferences table, the endpoint index, the source
line references.

Hand-written (lives in `gendoc.py`): endpoint summaries, parameter and body-field
descriptions, and the behaviour notes.

Two caveats carried in the document itself: the response-shape fold walks writer
calls linearly, so a key emitted inside an `if` appears as if it were always
present (conditional keys are called out in the per-endpoint notes), and the
types shown are the `CJsonWriter` method used, not JSON-Schema types.
