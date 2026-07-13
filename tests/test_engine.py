import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from app.matching.engine import MatchThresholds, find_matches
from app.matching.schema import build_matched_output

CRS = "EPSG:32634"  # UTM 34N (meters) - arbitrary metric CRS for synthetic tests


def _gdf(geoms, **attrs):
    data = {"geometry": geoms}
    data.update(attrs)
    return gpd.GeoDataFrame(data, crs=CRS)


def test_exact_overlap_matches():
    source = _gdf([LineString([(0, 0), (100, 0)])], name=["src1"])
    target = _gdf([LineString([(0, 0), (100, 0)])], name=["tgt1"])

    matches = find_matches(source, target)

    assert len(matches) == 1
    assert matches.iloc[0]["source_idx"] == 0
    assert matches.iloc[0]["target_idx"] == 0
    assert matches.iloc[0]["overlap_ratio"] == pytest_approx(1.0)


def test_reversed_direction_still_matches():
    source = _gdf([LineString([(0, 0), (100, 0)])], name=["src1"])
    target = _gdf([LineString([(100, 0), (0, 0)])], name=["tgt1"])  # reversed

    matches = find_matches(source, target)

    assert len(matches) == 1


def test_far_away_line_does_not_match():
    source = _gdf([LineString([(0, 0), (100, 0)])], name=["src1"])
    target = _gdf([LineString([(0, 1000), (100, 1000)])], name=["tgt1"])

    matches = find_matches(source, target)

    assert matches.empty


def test_perpendicular_line_does_not_match_due_to_angle():
    source = _gdf([LineString([(0, 0), (100, 0)])], name=["src1"])
    # A short perpendicular line close to the source, but at ~90 degrees.
    target = _gdf([LineString([(50, -5), (50, 5)])], name=["tgt1"])

    matches = find_matches(source, target)

    assert matches.empty


def test_short_partial_overlap_below_threshold_is_excluded():
    source = _gdf([LineString([(0, 0), (100, 0)])], name=["src1"])
    # Target mostly runs alongside source but drifts far away for most of its length.
    target = _gdf([LineString([(0, 0), (10, 0), (10, 1000)])], name=["tgt1"])

    matches = find_matches(source, target, MatchThresholds(min_overlap_ratio=0.5))

    assert matches.empty  # only ~10% of target length is within the buffer


def test_one_source_matches_multiple_target_segments():
    source = _gdf([LineString([(0, 0), (100, 0)])], name=["src1"])
    target = _gdf(
        [
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
        ],
        name=["tgt1", "tgt2"],
    )

    matches = find_matches(source, target)

    assert len(matches) == 2
    assert set(matches["target_idx"]) == {0, 1}


def test_build_matched_output_tags_source_attrs_on_each_row():
    source = _gdf([LineString([(0, 0), (100, 0)])], max_height=["4.2m"])
    target = _gdf(
        [
            LineString([(0, 0), (50, 0)]),
            LineString([(50, 0), (100, 0)]),
        ],
        road_name=["Main St part A", "Main St part B"],
    )

    matches = find_matches(source, target)
    output = build_matched_output(matches, source, target)

    assert len(output) == 2
    assert list(output["src_max_height"]) == ["4.2m", "4.2m"]
    assert set(output["tgt_road_name"]) == {"Main St part A", "Main St part B"}
    assert "match_score" in output.columns


def pytest_approx(value, rel=1e-6):
    import pytest

    return pytest.approx(value, rel=rel)
