"""I/O helpers: loading GeoPackage layers and getting them onto a common,
metric (meters) coordinate reference system so that distance/buffer based
matching thresholds are meaningful.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd


class LayerLoadError(RuntimeError):
    """Raised when a GeoPackage layer can't be loaded or is the wrong geometry type."""


def list_layers(gpkg_path: str | Path) -> list[str]:
    """Return the layer names available in a GeoPackage file."""
    import pyogrio

    return [name for name, _geom_type in pyogrio.list_layers(str(gpkg_path))]


def find_layer_by_geom_type(gpkg_path: str | Path, geom_type_prefixes: Iterable[str]) -> str:
    """Return the name of the (single) layer whose geometry type starts with
    one of `geom_type_prefixes` (case-insensitive), e.g. ("linestring",) or
    ("point", "multipoint"). Raises LayerLoadError if none or more than one match.

    This lets the app work with a source .gpkg regardless of what its line/point
    layers happen to be named.
    """
    import pyogrio

    path = Path(gpkg_path)
    prefixes = tuple(p.lower() for p in geom_type_prefixes)
    matches = [
        name
        for name, geom_type in pyogrio.list_layers(str(path))
        if geom_type and geom_type.lower().startswith(prefixes)
    ]
    if not matches:
        raise LayerLoadError(
            f"No layer with geometry type in {geom_type_prefixes} found in {path}"
        )
    if len(matches) > 1:
        raise LayerLoadError(
            f"Multiple layers with geometry type in {geom_type_prefixes} found in {path}: "
            f"{matches}. Expected exactly one."
        )
    return matches[0]


def load_layer(
    gpkg_path: str | Path,
    layer: str | None = None,
    expected_geom_types: Iterable[str] | None = None,
) -> gpd.GeoDataFrame:
    """Load a single layer from a GeoPackage as a GeoDataFrame.

    If `layer` is None, the file must contain exactly one layer.
    If `expected_geom_types` is given, raises LayerLoadError if the loaded
    layer's geometry type isn't one of them (e.g. {"LineString", "MultiLineString"}).
    """
    path = Path(gpkg_path)
    if not path.exists():
        raise LayerLoadError(f"File not found: {path}")

    available = list_layers(path)
    if not available:
        raise LayerLoadError(f"No layers found in {path}")

    if layer is None:
        if len(available) != 1:
            raise LayerLoadError(
                f"{path} contains multiple layers ({available}); "
                "please specify which one to use."
            )
        layer = available[0]
    elif layer not in available:
        raise LayerLoadError(f"Layer '{layer}' not found in {path}. Available: {available}")

    gdf = gpd.read_file(path, layer=layer)

    if gdf.empty:
        raise LayerLoadError(f"Layer '{layer}' in {path} has no features")

    # The source data's original geometry type is "Measured 3D" (XYZM); GDAL
    # drops the M values on read and leaves a dummy Z=0 for every vertex, so
    # there's no real elevation info here. Matching is purely planar (2D),
    # so drop the Z coordinate to keep downstream geometry ops (buffer,
    # distance, coords unpacking) simple and consistent.
    if gdf.geometry.has_z.any():
        gdf["geometry"] = gdf.geometry.force_2d()

    if gdf.crs is None:
        raise LayerLoadError(f"Layer '{layer}' in {path} has no CRS defined")

    if expected_geom_types is not None:
        expected = set(expected_geom_types)
        actual_types = set(gdf.geom_type.unique())
        if not actual_types & expected:
            raise LayerLoadError(
                f"Layer '{layer}' in {path} has geometry type(s) {actual_types}, "
                f"expected one of {expected}"
            )

    return gdf


def common_metric_crs(*gdfs: gpd.GeoDataFrame):
    """Estimate a single UTM CRS suited to the combined extent of all inputs.

    Using one shared CRS (rather than estimating separately per layer) is
    important here so that distances/buffers computed between layers are
    consistent.
    """
    combined_bounds = pd.concat([gdf.geometry for gdf in gdfs], ignore_index=True)
    combined_gdf = gpd.GeoDataFrame(geometry=combined_bounds, crs=gdfs[0].crs)
    return combined_gdf.estimate_utm_crs()


def reproject_all(crs, *gdfs: gpd.GeoDataFrame) -> list[gpd.GeoDataFrame]:
    """Reproject each GeoDataFrame to `crs`, returning new objects."""
    return [gdf.to_crs(crs) for gdf in gdfs]
