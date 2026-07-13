# GeometryMatcher — Project Overview

## Purpose

TomTom curates a small set of source lines carrying **maximum-dimension
restriction** attributes (height, width, length, weight limits) digitized
against one map/vendor schema. Separately, there is a much larger, detailed
reference road network for the same area from a different vendor schema.
The two datasets have **no shared ID or attribute code** to join on.

**Goal**: for each curated source line, find the corresponding line(s) in
the reference network purely by geometry (position, direction, shape), and
produce an output where the *reference network's geometry* is kept (since
it's the "known good" geometry) but tagged with the *source's* restriction
attributes — i.e. "translate" the curated restrictions onto known geometry.

Additionally, the source data includes a **point layer** of signposts
(physical signs stating a max-dimension value). Not every signpost
necessarily has a corresponding curated source line yet. The tool also
flags such "orphan" signposts (no source line nearby) so gaps in the
curated line data can be found and filled in later.

## Sample data

Two Esri File Geodatabases were provided initially (kept local-only, not
committed — see `.gitignore`):

- `MaxDim_sample.gdb` — the **source** data:
  - `MaxDim_2ndDEL_line` (44 features, MultiLineString, EPSG:4326) — curated
    lines with attributes like `MaximumHeightValue1/2`, `MaximumWidthValue`,
    `MaximumLengthValue`, `MaximumLadenWeightValue`,
    `MaximumWeightPerSingleAxleValue`, `vehicleType`, `condition_type`,
    various `RoadFeature_*` / GDD road-category fields.
  - `MaxDim_2ndDEL_point` (42 features, MultiPoint, EPSG:4326) — signposts
    with `RoadSignContentText`, `RoadSignContentValue`, `gddCode`, vehicle
    characteristics, etc.
- `MN_R_HUN_NetworkElements_sample.gdb` — the **target** data:
  - `MN_R_NetworkElements_sample` (40,925 features, MultiLineString,
    EPSG:4326) — a HERE-like schema (`Entity_Id`, `FRC`, `FormOfWay`,
    `Order8Code`, street names, speed/lane attributes, etc.).

The user later exported these to standalone GeoPackages for easier local
testing, placed in `SAMPLE_DATA/` (also gitignored):
- `SAMPLE_DATA/MaxDim_2ndDEL.gpkg` — layers `MaxDim_2ndDEL_line` (44) and
  `MaxDim_2ndDEL_point` (42).
- `SAMPLE_DATA/MN_R_NetworkElements.gpkg` — layer `MN_R_NetworkElements`
  (40,925).

Note: all geometries are technically 3D (`MultiLineString Z` /
`MultiPoint Z`) because the original type was "Measured 3D" (XYZM); GDAL
drops the M values on read and leaves a dummy `Z=0` for every vertex — there
is no real elevation data. The loader (`app/matching/io.py`) strips Z back
to 2D on load since matching is purely planar.

## Key decisions made (chronological)

1. **Matching approach**: pure geometry-based (proximity + direction +
   shape similarity) — no attribute-based matching, since the two schemas'
   codes don't correspond to each other.
2. **One-to-many handling**: the target network is far more finely
   segmented than the source. Each matched target segment becomes its own
   output row, tagged with the full attribute set of the source line that
   matched it (no dissolving/merging of geometry).
3. **File format**: GeoPackage (`.gpkg`) for both input layers and the
   output, rather than Esri File Geodatabase — avoids needing ArcGIS/ESRI's
   FileGDB SDK to write output, and (crucially) is a single file, which
   matters for the UI (see below).
4. **UI scope**: file pickers (source `.gpkg`, target `.gpkg`, output
   `.gpkg`) + a Run button + a text/table results summary. No map preview,
   no exposed tuning parameters (thresholds are code constants) in v1.
5. **App shape**: originally considered a browser-based local web app, but
   browsers can't reveal real OS file paths for a folder-based format —
   moot now since `.gpkg` is a single file, but the user separately wanted
   to avoid browsers entirely and run this as a **tray-launched native
   desktop app**. Settled on:
   - **`pywebview`** — renders the built Angular UI in a native OS window,
     and lets Python show native Open/Save file dialogs directly (no HTTP
     server; Angular calls Python via `window.pywebview.api.*`).
   - **`pystray`** — system tray icon with an Open/Quit menu.
   - Single Python process; Angular is pre-built to static assets and
     loaded locally by pywebview (no dev server at runtime).
6. **Matching thresholds** (v1 defaults, not user-tunable in UI):
   - Search/buffer distance: **20 m**
   - Max direction (bearing) difference: **30°**
   - Min overlap ratio (fraction of candidate target segment length inside
     the buffer): **50%**
   - These live as constants in `app/matching/engine.py`
     (`MatchThresholds` dataclass).
7. **Source point coverage check** (signposts vs. source lines): a point is
   "orphan" if no source line is within **25 m** (separate constant in
   `app/matching/point_check.py`, `PointCheckThresholds`). Orphans are
   written to their own output layer, not dropped.
8. **Python dependency management**: plain `venv` + `requirements.txt` (no
   Poetry/uv), matching the scope of the project.
9. **Angular setup**: minimal/standalone — no routing, plain CSS, no
   component library — appropriate for a single-screen tool.
10. **No `.gdb`→`.gpkg` conversion script** in the app or dev tooling — the
    user provides `.gpkg` files directly (originally I planned a
    `scripts/convert_gdb_to_gpkg.py` helper; this was explicitly rejected).
11. **Sample data is gitignored** (`SAMPLE_DATA/`, `*.gdb/`) — kept large
    binary geodata out of the repo; it stays local-only for each
    developer/tester.
12. **GitHub repo**: no GitHub MCP tool available for repo creation/push in
    this environment (only read/search tools), and `gh` CLI isn't
    installed locally, so the user created the empty repo manually:
    https://github.com/annamesterhazy-tomtom/geometry_matcher (pushed via
    local `git` over HTTPS, credentials already configured on this
    machine).
13. **Working style**: implementation proceeds interactively — checking in
    at each meaningful design/implementation decision rather than building
    silently end-to-end, so the user can supervise and learn from the
    process.

## Architecture

```
geometry_matcher/  (repo root: C:\00PROJECTS\GeometryMatcher)
  app/
    main.py            # [not yet built] entry point: pystray icon + pywebview window
    api.py              # Python API exposed to Angular via pywebview (file pickers, run_matching)
    matching/
      __init__.py
      io.py             # load/validate GeoPackage layers, auto-detect layer by geom type,
                        #   strip dummy Z, common UTM CRS reprojection
      engine.py         # bearing/overlap/offset scoring, find_matches(), MatchThresholds
      point_check.py    # orphan signpost detection, PointCheckThresholds
      schema.py         # build output GeoDataFrames (tgt_/src_ prefixing), write GeoPackage
    tray.py             # [not yet built] pystray icon + menu (show/hide/quit)
  frontend/             # Angular app (scaffolded; not yet wired to the API)
    src/app/app.ts / .html / .css
  tests/
    test_engine.py       # unit tests, synthetic geometries (7 tests, passing)
    test_point_check.py  # unit tests, synthetic geometries (3 tests, passing)
    test_integration.py  # full pipeline against real SAMPLE_DATA/ (skipped if absent)
  requirements.txt
  .venv/                 # local Python virtualenv (gitignored)
  SAMPLE_DATA/           # real sample .gpkg files (gitignored, local only)
  MaxDim_sample.gdb/, MN_R_HUN_NetworkElements_sample.gdb/  # original .gdb data (gitignored)
  PLAN.md                # copy of the working implementation plan
  PROJECT.md             # this file
```

### Matching engine algorithm (`app/matching/engine.py`)

1. Load source & target layers (`io.py`); validate CRS present; strip Z.
2. Reproject both to one shared metric CRS
   (`GeoDataFrame.estimate_utm_crs()` over the combined extent).
3. Build a spatial index on the target layer (`GeoDataFrame.sindex`).
4. For each source line: buffer it by 20 m, query candidate target segments
   intersecting that buffer.
5. Score each candidate:
   - **Overlap ratio** = length of candidate inside the buffer / candidate's
     total length. Must be ≥ 0.5.
   - **Bearing difference** = angle between source's and candidate's
     overall start→end direction, folded to [0°, 90°] (direction-agnostic —
     a line digitized in reverse still matches). Must be ≤ 30°.
   - **Mean perpendicular offset** = average distance from candidate's
     vertices to the source line. Must be ≤ 20 m.
   - A composite `match_score` combines all three (higher is better) but
     doesn't gate matching — it's a diagnostic field in the output.
6. All candidates passing thresholds are kept (a source line may match many
   target segments; a target segment may be matched by more than one
   source line — no dedup in v1).
7. Output: one row per (source, target) match — target geometry + target
   attributes (prefixed `tgt_`) + source attributes (prefixed `src_`) +
   `overlap_ratio` / `angle_diff_deg` / `mean_offset_m` / `match_score`.

### Source point coverage check (`app/matching/point_check.py`)

For each signpost point, check if any source line is within 25 m
(spatial-index query on a point buffer). Points with none nearby get
`orphan=True`. All points (with the flag) are written to a
`flagged_source_points` output layer — nothing is dropped, so the user can
filter on `orphan` to see which signposts still need a source line.

### Output (`app/matching/schema.py` → `write_output`)

A single output `.gpkg` with two layers:
- `matched_lines` — the source→target match results (as above).
- `flagged_source_points` — all signpost points + `orphan` boolean flag.

### Python ↔ Angular bridge (`app/api.py`)

`GeometryMatcherApi`, passed to pywebview as `js_api`, exposes to
`window.pywebview.api` in Angular:
- `pick_source_file()` / `pick_target_file()` — native Open dialogs
  (`.gpkg` filter).
- `pick_output_file()` — native Save dialog (`.gpkg` filter,
  defaults to `matched_output.gpkg`).
- `run_matching(source_path, target_path, output_path)` — runs the full
  pipeline (load → reproject → match → point-check → write) and returns a
  JSON-able `RunSummary`:
  ```json
  {
    "ok": true,
    "total_source_lines": 44,
    "matched_source_lines": 39,
    "unmatched_source_lines": 5,
    "total_matched_rows": 261,
    "total_source_points": 42,
    "orphan_source_points": 1,
    "output_path": "..."
  }
  ```
  Source line/point layers inside the source `.gpkg` are **auto-detected by
  geometry type** (`find_layer_by_geom_type`), not hardcoded names, so the
  app isn't tied to the exact sample data's layer names.

## Validation so far

- 10 unit tests (synthetic geometries) covering: exact overlap, reversed
  direction still matching, far-away line rejected, perpendicular line
  rejected (angle), low-overlap line rejected, one source matching multiple
  target segments, output attribute tagging, orphan point detection (near
  vs. far). All passing.
- Integration test + a direct `GeometryMatcherApi.run_matching(...)` call
  against the real sample data (`SAMPLE_DATA/`) both produced identical,
  consistent results:
  - 39 of 44 source lines matched at least one target segment
    (261 total output match rows).
  - 1 of 42 signpost points flagged as an orphan (no nearby source line).
  - 5 source lines currently have no match at all — not yet investigated
    (deferred until the UI/tool itself can be used to inspect them).

## Status / what's built vs. not yet

**Done:**
- Python venv + dependencies
- Angular scaffold (not yet wired up)
- Matching engine, point-coverage check, output writer — all tested
- Python API bridge (`app/api.py`) — tested directly, not yet from the UI
- Git repo pushed to GitHub

**Not yet built:**
- Angular UI itself (file picker buttons, Run button, results table) in
  `frontend/src/app/app.ts/.html/.css`
- `app/tray.py` (pystray tray icon/menu) and `app/main.py` (entry point
  wiring the tray + pywebview window + built Angular assets together)
- End-to-end run of the *packaged app* (not just the API) against real data
- Investigation of the 5 unmatched source lines / 1 orphan point (deferred
  by the user until the tool itself is usable)

## How to run things today (dev-only, no UI yet)

```powershell
# From C:\00PROJECTS\GeometryMatcher
.\.venv\Scripts\python.exe -m pytest tests\ -v          # unit + integration tests
                                                          # (integration test needs SAMPLE_DATA/ present locally)

# Run the matching pipeline directly via the API class (no UI):
.\.venv\Scripts\python.exe -c "
from app.api import GeometryMatcherApi
api = GeometryMatcherApi()
print(api.run_matching(
    r'SAMPLE_DATA\MaxDim_2ndDEL.gpkg',
    r'SAMPLE_DATA\MN_R_NetworkElements.gpkg',
    r'SAMPLE_DATA\test_output.gpkg',
))
"
```

Angular dev server (`ng serve` in `frontend/`) can be used to iterate on UI
styling, but `window.pywebview` won't be defined outside of a real
pywebview-hosted window, so API calls need pywebview running to fully test.
