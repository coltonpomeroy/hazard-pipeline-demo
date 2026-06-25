"""
hazard.py
=========
The part a hazard-intelligence platform actually exists to do: turn a continuous
raster forecast field into discrete, attributed WARNING ZONES that humans and
incident systems can act on.

Pipeline:
  raster gust field  ->  threshold into hazard classes  ->  polygonize (raster
  to vector)  ->  GeoJSON FeatureCollection with attributes.

The output GeoJSON is deliberately shaped to drop straight into the target
stack:
  * each polygon is EPSG:4326, ready to INSERT into a PostGIS geometry column
  * properties carry the hazard class, threshold, forecast step, valid time
  * MapLibre GL can render the FeatureCollection as a fill layer with no
    transformation

Vectorizing on ingest (rather than shipping rasters to the browser) is what
keeps the frontend fast and the warnings queryable in PostGIS.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
import xarray as xr
from rasterio.features import shapes, rasterize
from rasterio.transform import from_origin
from shapely.geometry import shape, mapping

# Wind-gust hazard tiers (mph). Loosely mirrors NWS wind headlines.
HAZARD_TIERS = [
    {"class": "wind_advisory", "min_mph": 46, "color": "#f1c40f"},
    {"class": "high_wind_warning", "min_mph": 58, "color": "#e67e22"},
    {"class": "damaging_wind", "min_mph": 70, "color": "#c0392b"},
]


def _affine_for(da: xr.DataArray):
    """Build the affine transform rasterio needs from the coord vectors."""
    lon = da.longitude.values
    lat = da.latitude.values
    dx = float(lon[1] - lon[0])
    dy = float(lat[1] - lat[0])
    # rasterio expects origin at the top-left (max lat, min lon).
    west = float(lon.min()) - dx / 2
    north = float(lat.max()) + abs(dy) / 2
    return from_origin(west, north, dx, abs(dy))


def _polygonize_tier(field_2d: np.ndarray, transform, min_mph: float):
    """Return shapely polygons where the field meets/exceeds a threshold."""
    mask = (field_2d >= min_mph).astype(np.uint8)
    if mask.sum() == 0:
        return []
    geoms = []
    for geom, val in shapes(mask, mask=mask.astype(bool), transform=transform):
        if val == 1:
            poly = shape(geom)
            if poly.is_valid and poly.area > 0:
                geoms.append(poly)
    return geoms


def derive_warnings(ds: xr.Dataset, cycle_init: datetime | None = None) -> dict:
    """Produce a GeoJSON FeatureCollection of warning polygons across all
    forecast steps and hazard tiers."""
    cycle_init = cycle_init or datetime.now().replace(
        minute=0, second=0, microsecond=0)

    features = []
    da = ds.gust_mph

    for si, step in enumerate(ds.step.values):
        # data must be top-row = north for the affine above
        field = da.isel(step=si).sortby("latitude", ascending=False)
        transform = _affine_for(da)
        arr = field.values

        fhr = int(step / np.timedelta64(1, "h"))
        valid = cycle_init + timedelta(hours=fhr)

        for tier in HAZARD_TIERS:
            for poly in _polygonize_tier(arr, transform, tier["min_mph"]):
                # Peak gust *inside this polygon* -- rasterize the polygon back
                # to a cell mask and take the max there. (Using the whole-field
                # max would give every zone in a step the same number.)
                cell_mask = rasterize(
                    [(poly, 1)], out_shape=arr.shape, transform=transform,
                    fill=0, dtype="uint8").astype(bool)
                vals = arr[cell_mask]
                vals = vals[np.isfinite(vals)]
                peak = float(vals.max()) if vals.size else float(tier["min_mph"])
                features.append({
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {
                        "hazard_class": tier["class"],
                        "threshold_mph": tier["min_mph"],
                        "peak_gust_mph": round(peak, 1),
                        "forecast_hour": fhr,
                        "valid_time": valid.isoformat() + "Z",
                        "fill_color": tier["color"],
                        "area_deg2": round(poly.area, 4),
                    },
                })

    return {
        "type": "FeatureCollection",
        "metadata": {
            "cycle_init": cycle_init.isoformat() + "Z",
            "product": "wind_gust_hazard_zones",
            "crs": "EPSG:4326",
            "tiers": HAZARD_TIERS,
            "n_features": len(features),
        },
        "features": features,
    }


def write_geojson(fc: dict, path: str) -> str:
    with open(path, "w") as f:
        json.dump(fc, f)
    return path


if __name__ == "__main__":
    from hazpipe.ingest import load_grib2

    ds = load_grib2("data/gust_forecast.grib2")
    fc = derive_warnings(ds)
    write_geojson(fc, "output/warnings.geojson")
    print(f"generated {fc['metadata']['n_features']} warning polygons")
    by_class: dict[str, int] = {}
    for ft in fc["features"]:
        c = ft["properties"]["hazard_class"]
        by_class[c] = by_class.get(c, 0) + 1
    for c, n in by_class.items():
        print(f"  {c:20s} {n}")
