"""Builds the final output layers (matched lines + flagged source points)
from raw match results, and writes them to a GeoPackage.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd


def build_matched_output(
    matches: pd.DataFrame,
    source_gdf: gpd.GeoDataFrame,
    target_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """One output row per (source, target) match: target geometry, target
    attributes prefixed `tgt_`, source attributes prefixed `src_`, plus the
    match diagnostics (overlap_ratio, angle_diff_deg, mean_offset_m, match_score).
    """
    if matches.empty:
        # Still produce a correctly-shaped, empty output layer.
        tgt_cols = [f"tgt_{c}" for c in target_gdf.columns if c != "geometry"]
        src_cols = [f"src_{c}" for c in source_gdf.columns if c != "geometry"]
        cols = tgt_cols + src_cols + [
            "overlap_ratio", "angle_diff_deg", "mean_offset_m", "match_score", "geometry",
        ]
        return gpd.GeoDataFrame(columns=cols, geometry="geometry", crs=target_gdf.crs)

    tgt_part = target_gdf.loc[matches["target_idx"]].drop(columns="geometry").reset_index(drop=True)
    tgt_part = tgt_part.add_prefix("tgt_")

    src_part = source_gdf.loc[matches["source_idx"]].drop(columns="geometry").reset_index(drop=True)
    src_part = src_part.add_prefix("src_")

    geometry = target_gdf.loc[matches["target_idx"], "geometry"].reset_index(drop=True)

    diagnostics = matches[
        ["overlap_ratio", "angle_diff_deg", "mean_offset_m", "match_score"]
    ].reset_index(drop=True)

    out = pd.concat([tgt_part, src_part, diagnostics], axis=1)
    return gpd.GeoDataFrame(out, geometry=geometry, crs=target_gdf.crs)


def build_flagged_points_output(points_gdf: gpd.GeoDataFrame, orphan_mask: pd.Series) -> gpd.GeoDataFrame:
    """All source points with an `orphan` boolean flag column appended
    (True = no source line found nearby; needs a line digitized later).
    """
    out = points_gdf.copy()
    out["orphan"] = orphan_mask.values
    return out


def write_output(
    output_path: str | Path,
    matched_gdf: gpd.GeoDataFrame,
    flagged_points_gdf: gpd.GeoDataFrame,
    matched_layer: str = "matched_lines",
    flagged_points_layer: str = "flagged_source_points",
) -> None:
    """Write both output layers into a single GeoPackage file."""
    path = Path(output_path)
    if path.exists():
        path.unlink()

    matched_gdf.to_file(path, layer=matched_layer, driver="GPKG")
    flagged_points_gdf.to_file(path, layer=flagged_points_layer, driver="GPKG")
