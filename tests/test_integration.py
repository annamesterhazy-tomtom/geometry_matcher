"""Integration test: runs the matching engine and point-coverage check
against the real sample data provided in SAMPLE_DATA/, end-to-end.

This does not assert exact match counts (those depend on real-world data
and may shift slightly if thresholds are tuned) but does sanity-check that
the pipeline runs cleanly and produces a plausible, well-formed result.
"""
from pathlib import Path

import geopandas as gpd
import pytest

from app.matching.engine import find_matches
from app.matching.io import common_metric_crs, load_layer, reproject_all
from app.matching.point_check import find_orphan_points
from app.matching.schema import build_flagged_points_output, build_matched_output, write_output

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA = REPO_ROOT / "SAMPLE_DATA"
SOURCE_GPKG = SAMPLE_DATA / "MaxDim_2ndDEL.gpkg"
TARGET_GPKG = SAMPLE_DATA / "MN_R_NetworkElements.gpkg"

pytestmark = pytest.mark.skipif(
    not SOURCE_GPKG.exists() or not TARGET_GPKG.exists(),
    reason="Sample GeoPackage data not present in SAMPLE_DATA/",
)


@pytest.fixture(scope="module")
def loaded_data():
    source_lines = load_layer(SOURCE_GPKG, layer="MaxDim_2ndDEL_line")
    source_points = load_layer(SOURCE_GPKG, layer="MaxDim_2ndDEL_point")
    target_lines = load_layer(TARGET_GPKG, layer="MN_R_NetworkElements")

    crs = common_metric_crs(source_lines, target_lines)
    source_lines, source_points, target_lines = reproject_all(
        crs, source_lines, source_points, target_lines
    )
    return source_lines, source_points, target_lines


def test_source_to_target_matching_runs_end_to_end(loaded_data):
    source_lines, _source_points, target_lines = loaded_data

    matches = find_matches(source_lines, target_lines)

    assert not matches.empty, "expected at least some source lines to match the target network"
    assert matches["overlap_ratio"].between(0, 1).all()
    assert (matches["angle_diff_deg"] <= 30.0).all()

    matched_count = matches["source_idx"].nunique()
    total_sources = len(source_lines)
    print(f"\n{matched_count}/{total_sources} source lines matched at least one target segment")
    print(f"Total output rows (matches): {len(matches)}")


def test_point_coverage_check_runs_end_to_end(loaded_data):
    source_lines, source_points, _target_lines = loaded_data

    orphan = find_orphan_points(source_points, source_lines)

    orphan_count = int(orphan.sum())
    print(f"\n{orphan_count}/{len(source_points)} source signpost points are orphaned (no nearby source line)")

    assert orphan.index.equals(source_points.index)


def test_full_pipeline_writes_output_gpkg(loaded_data, tmp_path):
    source_lines, source_points, target_lines = loaded_data

    matches = find_matches(source_lines, target_lines)
    matched_output = build_matched_output(matches, source_lines, target_lines)

    orphan = find_orphan_points(source_points, source_lines)
    flagged_points_output = build_flagged_points_output(source_points, orphan)

    out_path = tmp_path / "result.gpkg"
    write_output(out_path, matched_output, flagged_points_output)

    assert out_path.exists()

    reread_matches = gpd.read_file(out_path, layer="matched_lines")
    reread_points = gpd.read_file(out_path, layer="flagged_source_points")

    assert len(reread_matches) == len(matched_output)
    assert len(reread_points) == len(source_points)
    assert "orphan" in reread_points.columns
