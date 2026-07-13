"""Python API exposed to the Angular frontend via pywebview's JS bridge
(`window.pywebview.api.*`).

Each public method here is callable directly from TypeScript. Keep methods
JSON-serializable in/out (pywebview marshals args/return values as JSON).
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import webview

from app.matching.engine import find_matches
from app.matching.io import (
    LayerLoadError,
    common_metric_crs,
    find_layer_by_geom_type,
    load_layer,
    reproject_all,
)
from app.matching.point_check import find_orphan_points
from app.matching.schema import build_flagged_points_output, build_matched_output, write_output


class RunSummary(TypedDict, total=False):
    ok: bool
    error: str
    total_source_lines: int
    matched_source_lines: int
    unmatched_source_lines: int
    total_matched_rows: int
    total_source_points: int
    orphan_source_points: int
    output_path: str


class GeometryMatcherApi:
    """Instantiated once and passed to `webview.create_window(js_api=...)`."""

    def _window(self) -> webview.Window:
        return webview.windows[0]

    def pick_source_file(self) -> str | None:
        """Native Open dialog for the source .gpkg (contains the curated
        source lines + signpost points layers)."""
        result = self._window().create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("GeoPackage (*.gpkg)", "All files (*.*)"),
        )
        return result[0] if result else None

    def pick_target_file(self) -> str | None:
        """Native Open dialog for the target network .gpkg."""
        result = self._window().create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("GeoPackage (*.gpkg)", "All files (*.*)"),
        )
        return result[0] if result else None

    def pick_output_file(self) -> str | None:
        """Native Save dialog for the output .gpkg."""
        result = self._window().create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="matched_output.gpkg",
            file_types=("GeoPackage (*.gpkg)", "All files (*.*)"),
        )
        return result[0] if result else None

    def run_matching(self, source_path: str, target_path: str, output_path: str) -> RunSummary:
        """Runs the full pipeline: load layers -> reproject -> match source
        lines to target lines -> check source points for orphans -> write
        both output layers to `output_path`. Returns a JSON-able summary for
        the UI's results panel.
        """
        try:
            source_line_layer = find_layer_by_geom_type(source_path, ("linestring", "multilinestring"))
            source_point_layer = find_layer_by_geom_type(source_path, ("point", "multipoint"))

            source_lines = load_layer(
                source_path, layer=source_line_layer, expected_geom_types={"MultiLineString", "LineString"}
            )
            source_points = load_layer(
                source_path, layer=source_point_layer, expected_geom_types={"MultiPoint", "Point"}
            )
            target_lines = load_layer(
                target_path, expected_geom_types={"MultiLineString", "LineString"}
            )
        except LayerLoadError as exc:
            return RunSummary(ok=False, error=str(exc))

        crs = common_metric_crs(source_lines, target_lines)
        source_lines, source_points, target_lines = reproject_all(
            crs, source_lines, source_points, target_lines
        )

        matches = find_matches(source_lines, target_lines)
        matched_output = build_matched_output(matches, source_lines, target_lines)

        orphan_mask = find_orphan_points(source_points, source_lines)
        flagged_points_output = build_flagged_points_output(source_points, orphan_mask)

        write_output(output_path, matched_output, flagged_points_output)

        matched_source_count = matches["source_idx"].nunique() if not matches.empty else 0

        return RunSummary(
            ok=True,
            total_source_lines=len(source_lines),
            matched_source_lines=matched_source_count,
            unmatched_source_lines=len(source_lines) - matched_source_count,
            total_matched_rows=len(matched_output),
            total_source_points=len(source_points),
            orphan_source_points=int(orphan_mask.sum()),
            output_path=str(Path(output_path)),
        )
