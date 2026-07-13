"""Source point coverage check.

The source .gdb/.gpkg also contains signpost points carrying max-dimension
values. Some signposts may not yet have a corresponding curated source
line. This module flags such "orphan" points (purely by geometric
proximity — no source line within a threshold distance) so they can be
reviewed and a source line digitized for them later.
"""
from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

DEFAULT_POINT_LINE_PROXIMITY_M = 25.0


@dataclass
class PointCheckThresholds:
    proximity_m: float = DEFAULT_POINT_LINE_PROXIMITY_M


def find_orphan_points(
    points_gdf: gpd.GeoDataFrame,
    lines_gdf: gpd.GeoDataFrame,
    thresholds: PointCheckThresholds | None = None,
) -> pd.Series:
    """Return a boolean Series (aligned to points_gdf.index) that is True
    for points with no source line within `proximity_m`.

    `points_gdf` and `lines_gdf` must already be in the same metric CRS.
    """
    thresholds = thresholds or PointCheckThresholds()
    lines_sindex = lines_gdf.sindex

    orphan = pd.Series(True, index=points_gdf.index, name="orphan")
    for idx, row in points_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        search_area = geom.buffer(thresholds.proximity_m)
        nearby = list(lines_sindex.query(search_area, predicate="intersects"))
        if nearby:
            orphan.loc[idx] = False

    return orphan
