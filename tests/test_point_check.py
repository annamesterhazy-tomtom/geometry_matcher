import geopandas as gpd
from shapely.geometry import LineString, Point

from app.matching.point_check import find_orphan_points

CRS = "EPSG:32634"


def test_point_near_line_is_not_orphan():
    points = gpd.GeoDataFrame({"geometry": [Point(50, 5)]}, crs=CRS)
    lines = gpd.GeoDataFrame({"geometry": [LineString([(0, 0), (100, 0)])]}, crs=CRS)

    orphan = find_orphan_points(points, lines)

    assert orphan.iloc[0] == False  # noqa: E712


def test_point_far_from_any_line_is_orphan():
    points = gpd.GeoDataFrame({"geometry": [Point(50, 500)]}, crs=CRS)
    lines = gpd.GeoDataFrame({"geometry": [LineString([(0, 0), (100, 0)])]}, crs=CRS)

    orphan = find_orphan_points(points, lines)

    assert orphan.iloc[0] == True  # noqa: E712


def test_mixed_points_flagged_independently():
    points = gpd.GeoDataFrame({"geometry": [Point(50, 5), Point(50, 500)]}, crs=CRS)
    lines = gpd.GeoDataFrame({"geometry": [LineString([(0, 0), (100, 0)])]}, crs=CRS)

    orphan = find_orphan_points(points, lines)

    assert list(orphan) == [False, True]
