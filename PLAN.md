# GeometryMatcher — Implementation Plan

## Problem

Match each curated source line (44 features, `MaxDim_2ndDEL_line`, max-dimension
restriction attributes) to the corresponding line(s) in a much larger target
road network (40,925 features, `MN_R_NetworkElements_sample`, HERE-like
schema). Output: target geometry + target attributes, with the matched
source's attributes tagged onto each matched row ("known" geometry, source
attribution).

There is no shared ID/code between the two schemas (different vendor
conventions), so matching must be purely geometric: proximity, direction,
and shape similarity.

Additionally, the source `.gdb` also contains a point layer,
`MaxDim_2ndDEL_point` (42 features, EPSG:4326) — signposts carrying max
dimension values (`RoadSignContentText`, `RoadSignContentValue`, `gddCode`,
vehicle characteristics, etc.). Some signposts may not yet have a
corresponding curated source line. These orphan points must be identified
(geometrically: no source line within a proximity threshold) and flagged in
the output, so the user knows which signposts still need a source line
digitized for them.

## Confirmed decisions

- **Matching approach**: pure geometry-based (no attribute matching).
- **One-to-many handling**: target network is far more finely segmented than
  source. Each matched target segment becomes its own output row, tagged with
  the full attribute set of the source line it matched (no dissolve/merge).
- **Input format**: GeoPackage (`.gpkg`) for both source and target layers
  (single-file, avoids folder-based `.gdb` complexity and enables simple
  native file pickers). The source `.gpkg` contains two layers — the
  curated source lines and the signpost points — both converted once from
  the existing `.gdb` sample data for development/testing (not part of the
  shipped app).
- **Output format**: GeoPackage (`.gpkg`).
- **Source point coverage check**: `MaxDim_2ndDEL_point` signposts are checked
  against `MaxDim_2ndDEL_line` — any point with no source line within a
  proximity threshold is flagged as "orphan" (no corresponding source line
  yet) and written to the output `.gpkg` as its own layer
  (`flagged_source_points`), so the user can see which signposts still need
  a line digitized. This is purely a source-side data-quality check, separate
  from the source→target matching.
- **UI**: file pickers (source, target, output) + Run button + a
  text/table summary log (counts matched/unmatched, output path). No map
  preview, no exposed tuning parameters in v1.
- **App shape**: single local desktop app, no browser, launched from a
  system tray icon, running in a native window.
  - `pywebview` renders the built Angular UI in a native OS window and
    exposes native Open/Save file dialogs directly from Python (no HTTP
    server, no browser `<input type=file>` limitations).
  - `pystray` provides the tray icon to show/hide/quit the app.
  - Python and Angular run in a single process/package — Angular is built
    to static assets and loaded by pywebview; the Angular app calls a
    JS-exposed Python API (`window.pywebview.api.*`) directly.

## Architecture

```
geometry_matcher/
  app/
    main.py            # entry point: creates pystray icon + pywebview window
    api.py              # Python API class exposed to JS (pick files, run match, get summary)
    matching/
      __init__.py
      io.py             # load/validate GeoPackage layers, CRS handling
      engine.py         # candidate search, scoring, matching, aggregation
      point_check.py    # source point-vs-line orphan detection
      schema.py         # output schema / attribute prefixing rules
    tray.py             # pystray icon + menu (show/hide/quit)
  frontend/             # Angular app (built to app/webui/dist for pywebview to load)
    src/...
  tests/
    test_engine.py      # unit tests on synthetic small geometries
    test_integration.py # run against converted sample .gpkg fixtures
  scripts/
    convert_gdb_to_gpkg.py  # dev-only helper to build test fixtures from the sample .gdb data
  pyproject.toml / requirements.txt
  frontend/package.json
```

### Matching engine (core algorithm)

1. Load source & target layers via `geopandas`/`pyogrio`; validate CRS present.
2. Reproject both layers to a metric CRS suited to the data extent
   (`geopandas.GeoDataFrame.estimate_utm_crs()`, since the tool should not
   assume Hungary-only data long-term) so distances/buffers are in meters.
3. Build a spatial index (`GeoDataFrame.sindex`) on the target layer.
4. For each source line:
   - Buffer it by a configurable search distance (default constant, e.g. 20 m)
     and query the target sindex for candidate target segments.
   - Score each candidate using:
     - **Overlap ratio** — fraction of the candidate's length that falls
       within the buffer of the source line.
     - **Directional similarity** — difference between the source line's
       overall bearing and the candidate's bearing (wrapped to 0–90°).
     - **Mean perpendicular offset** — average distance from candidate
       vertices to the source line.
   - Keep all candidates passing the default thresholds (overlap ratio,
     max angle difference, max mean offset) as matches — a source line may
     match many target segments; a target segment may be matched by more
     than one source line (no dedup/conflict resolution in v1).
5. Build output rows: one row per (source, matched target) pair —
   target geometry + target attributes (prefixed `tgt_`) + source attributes
   (prefixed `src_`) + a `match_score` diagnostic field.
6. Write result to the chosen output `.gpkg` via `geopandas.to_file(driver="GPKG")`.
7. Return a run summary (source count, matched/unmatched source lines,
   total output rows, output path) to the UI.

### Source point coverage check (orphan signposts)

1. Load `MaxDim_2ndDEL_point` (or equivalent point layer) from the source
   `.gpkg`, reproject to the same metric CRS as the matching engine.
2. For each point, query the source line layer's spatial index for any
   source line within a proximity threshold (default constant, e.g. 25 m —
   tunable independently from the source→target thresholds).
3. Points with no source line within the threshold are marked `orphan=True`;
   all points (with their original attributes + the flag) are written to
   the output `.gpkg` as a `flagged_source_points` layer, so orphans are
   easy to filter/review.
4. The run summary reported to the UI includes: total points checked and
   orphan point count.

### Python ↔ Angular bridge (pywebview)

`api.py` exposes methods callable from Angular via `window.pywebview.api`:
- `pick_source_file()` / `pick_target_file()` — native Open dialogs, `.gpkg` filter.
- `pick_output_file()` — native Save dialog, `.gpkg` filter.
- `run_matching(source_path, target_path, output_path)` — runs the engine
  synchronously (or reports progress via a JS callback if needed) and
  returns the summary dict.

### Packaging / entry point

- `main.py` starts a `pystray` tray icon with a menu (Open / Quit). Selecting
  "Open" creates/shows the `pywebview` window (or focuses it if already
  open); "Quit" tears down the tray + window and exits.
- Angular is built once (`ng build`) into a static folder that `pywebview`
  loads via a local file URL — no dev server involved at runtime.

## Todos

Tracked in SQL (`todos` table): project scaffolding, matching engine,
Python↔Angular bridge, Angular UI, tray/window packaging, test fixture
conversion, and end-to-end validation against the sample data.

## Notes / open items for later iterations (not blocking v1)

- Default buffer distance / angle / overlap thresholds are implementation
  constants for v1 (not user-tunable in the UI yet, per your choice).
- No map preview in v1.
- No conflict resolution when multiple source lines match the same target
  segment — all matches are kept as separate rows.

## Working style for implementation

Per your request, implementation will proceed interactively: at each
meaningful step (design choice, library/API used, non-trivial code change),
I will explain what I'm doing and check in with you before/while proceeding,
rather than silently completing the whole build. This is slower but keeps
you in the loop to supervise and learn from the process.

## Progress so far (as of latest session)

- **Repo**: pushed to https://github.com/annamesterhazy-tomtom/geometry_matcher
  (main branch). Sample data (`SAMPLE_DATA/`, `*.gdb/`) is gitignored —
  local-only, not committed.
- **Python env**: `.venv` + `requirements.txt` (geopandas, pyogrio, shapely,
  pyproj, pywebview, pystray, Pillow, pytest). Done.
- **Angular scaffold**: `frontend/` created via Angular CLI 22
  (`--routing=false --style=css --ssr=false`). Not yet wired to pywebview API.
- **Matching engine** (`app/matching/`): `io.py` (load/validate GeoPackage
  layers, auto-detect line/point layers by geometry type, strip dummy Z=0
  coords, common UTM CRS reprojection), `engine.py` (bearing/overlap/offset
  scoring, `find_matches`), `point_check.py` (orphan signpost detection),
  `schema.py` (build output GeoDataFrames + write GeoPackage). Done.
- **Tests**: `tests/test_engine.py` (7 synthetic-geometry unit tests),
  `tests/test_point_check.py` (3 unit tests) — all passing.
  `tests/test_integration.py` runs the full pipeline against real sample
  data in `SAMPLE_DATA/` (skipped automatically if that folder is absent,
  e.g. on a fresh clone/CI) — passing locally: 39/44 source lines matched
  (261 output rows), 1/42 signpost points flagged orphan.
- **Python API bridge** (`app/api.py`): `GeometryMatcherApi` class with
  `pick_source_file`/`pick_target_file`/`pick_output_file` (native pywebview
  dialogs) and `run_matching(...)` (runs the full pipeline, returns a JSON
  summary). Verified directly (bypassing the UI) against real sample data —
  matches integration test results.
- **Not started yet**: Angular UI (file pickers/run button/results table),
  `app/tray.py` + `app/main.py` (pystray tray icon + pywebview window
  wiring), end-to-end packaged app validation.

## Next steps

All planned v1 todos are complete:

1. ✅ Angular UI built and wired to `window.pywebview.api`.
2. ✅ `app/tray.py` + `app/main.py` built (pystray tray icon, hidden
   pywebview window shown on open).
3. ✅ End-to-end validation done through the real packaged window (not just
   the API directly) — results match the integration test exactly.
4. Deferred by user choice: investigating the 5 unmatched source lines / 1
   orphan point — now possible any time via `python -m app.main`.

Known gotcha fixed during e2e testing: `webview.create_window(url=...)`
must be given the plain filesystem path to `index.html`, not a `file://`
URI — the latter breaks Angular's `base href`-relative asset loading
(blank page). Passing the plain path lets pywebview serve it through its
internal HTTP server instead.

Repo: https://github.com/annamesterhazy-tomtom/geometry_matcher (main).
`PROJECT.md` in the repo has the fully up to date status/how-to-run info.
