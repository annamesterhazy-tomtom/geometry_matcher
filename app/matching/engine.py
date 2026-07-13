"""Core geometry matching engine.

Matches each "source" line (small curated set) to zero or more "target"
lines (large reference network) using purely geometric criteria: spatial
proximity (buffer overlap), directional similarity (bearing difference),
and how much of the candidate target segment actually runs alongside the
source line.

No attribute matching is used — the two schemas have no shared identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry.base import BaseGeometry

# Default thresholds (not currently exposed in the UI; tune here if needed).
DEFAULT_BUFFER_DISTANCE_M = 20.0
DEFAULT_MAX_ANGLE_DEG = 30.0
DEFAULT_MIN_OVERLAP_RATIO = 0.5


@dataclass
class MatchThresholds:
    buffer_distance_m: float = DEFAULT_BUFFER_DISTANCE_M
    max_angle_deg: float = DEFAULT_MAX_ANGLE_DEG
    min_overlap_ratio: float = DEFAULT_MIN_OVERLAP_RATIO


def _endpoints(geom: BaseGeometry):
    """Return (first_coord, last_coord) for a LineString or MultiLineString,
    using the first part's start and the last part's end.
    """
    if geom.geom_type == "MultiLineString":
        parts = list(geom.geoms)
        first_coord = parts[0].coords[0]
        last_coord = parts[-1].coords[-1]
    else:
        coords = list(geom.coords)
        first_coord = coords[0]
        last_coord = coords[-1]
    return first_coord, last_coord


def line_bearing_deg(geom: BaseGeometry) -> float:
    """Overall bearing of a line's start->end vector, in degrees, folded
    into [0, 180) since road matching here is direction-agnostic (a line
    digitized in either direction should match).
    """
    (x0, y0), (x1, y1) = _endpoints(geom)
    angle = np.degrees(np.arctan2(y1 - y0, x1 - x0))
    return angle % 180.0


def angle_difference_deg(a_deg: float, b_deg: float) -> float:
    """Smallest difference between two direction-agnostic bearings (each in [0, 180))."""
    diff = abs(a_deg - b_deg) % 180.0
    return min(diff, 180.0 - diff)


def overlap_ratio(candidate_geom: BaseGeometry, buffer_geom: BaseGeometry) -> float:
    """Fraction of candidate_geom's length that falls within buffer_geom."""
    if candidate_geom.length == 0:
        return 0.0
    intersection = candidate_geom.intersection(buffer_geom)
    return intersection.length / candidate_geom.length


def mean_perpendicular_offset_m(candidate_geom: BaseGeometry, source_geom: BaseGeometry) -> float:
    """Average distance from candidate_geom's vertices to source_geom."""
    if candidate_geom.geom_type == "MultiLineString":
        coords = [pt for part in candidate_geom.geoms for pt in part.coords]
    else:
        coords = list(candidate_geom.coords)
    if not coords:
        return float("inf")
    distances = [source_geom.distance(_point(c)) for c in coords]
    return float(np.mean(distances))


def _point(coord):
    from shapely.geometry import Point

    return Point(coord)


def find_matches(
    source_gdf: gpd.GeoDataFrame,
    target_gdf: gpd.GeoDataFrame,
    thresholds: MatchThresholds | None = None,
) -> pd.DataFrame:
    """Find all (source_idx, target_idx) pairs that pass the matching thresholds.

    `source_gdf` and `target_gdf` must already be in the same metric CRS.

    Returns a DataFrame with columns: source_idx, target_idx, overlap_ratio,
    angle_diff_deg, mean_offset_m, match_score — one row per accepted match.
    A source line may match multiple target segments and vice versa; no
    deduplication/conflict-resolution is performed.
    """
    thresholds = thresholds or MatchThresholds()
    target_sindex = target_gdf.sindex

    rows = []
    for src_idx, src_row in source_gdf.iterrows():
        src_geom = src_row.geometry
        if src_geom is None or src_geom.is_empty:
            continue

        src_buffer = src_geom.buffer(thresholds.buffer_distance_m)
        src_bearing = line_bearing_deg(src_geom)

        candidate_positions = list(target_sindex.query(src_buffer, predicate="intersects"))
        if not candidate_positions:
            continue

        for pos in candidate_positions:
            tgt_idx = target_gdf.index[pos]
            tgt_geom = target_gdf.geometry.iloc[pos]
            if tgt_geom is None or tgt_geom.is_empty:
                continue

            ratio = overlap_ratio(tgt_geom, src_buffer)
            if ratio < thresholds.min_overlap_ratio:
                continue

            tgt_bearing = line_bearing_deg(tgt_geom)
            angle_diff = angle_difference_deg(src_bearing, tgt_bearing)
            if angle_diff > thresholds.max_angle_deg:
                continue

            offset = mean_perpendicular_offset_m(tgt_geom, src_geom)
            if offset > thresholds.buffer_distance_m:
                continue

            # Composite score: higher overlap, lower angle diff / offset -> higher score.
            score = (
                ratio
                * (1.0 - angle_diff / max(thresholds.max_angle_deg, 1e-9))
                * (1.0 - offset / max(thresholds.buffer_distance_m, 1e-9))
            )

            rows.append(
                {
                    "source_idx": src_idx,
                    "target_idx": tgt_idx,
                    "overlap_ratio": ratio,
                    "angle_diff_deg": angle_diff,
                    "mean_offset_m": offset,
                    "match_score": score,
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "source_idx",
            "target_idx",
            "overlap_ratio",
            "angle_diff_deg",
            "mean_offset_m",
            "match_score",
        ],
    )
