"""
regrid.py
=========
HRRR ships on a Lambert Conformal Conic grid: cfgrib hands back a field with
dims (y, x) and *2-D* ``latitude``/``longitude`` coordinate arrays. The rest of
this pipeline (hazard.py, render_preview.py, the MapLibre build) assumes a
*regular* 1-D lat/lon grid -- so we resample the curvilinear HRRR field onto a
plain EPSG:4326 grid here. This is the one scoped addition HRRR needs; nothing
downstream of ingest changes.

Method: max-binning. Each HRRR cell is dropped into the regular target cell its
true lat/lon falls in, keeping the MAXIMUM gust per target cell. Max (not mean
or nearest) is the right reducer for a *hazard* product -- averaging would wash
out exactly the peak gusts the warnings exist to flag. With the target spacing
chosen coarser than HRRR's native ~3 km, every target cell catches several
source cells, so there are no holes. Pure NumPy, and it leans on the authoritative
lat/lon cfgrib already computed rather than re-deriving the projection.
"""
from __future__ import annotations

import numpy as np

# ~5.5 km at mid-latitudes: coarser than HRRR's 3 km (so no empty cells), still
# fine enough to draw crisp hazard polygons and keep the GeoJSON light.
DEFAULT_RES_DEG = 0.05


def regrid_max(lat2d: np.ndarray, lon2d: np.ndarray, field2d: np.ndarray,
               res_deg: float = DEFAULT_RES_DEG):
    """Resample a curvilinear field onto a regular lat/lon grid by max-binning.

    Returns ``(lats_1d, lons_1d, grid_2d)`` where ``grid_2d`` has shape
    (lats, lons), ascending in both axes, NaN where no source cell landed.
    """
    lat = np.asarray(lat2d, dtype=float).ravel()
    lon = np.asarray(lon2d, dtype=float).ravel()
    val = np.asarray(field2d, dtype=float).ravel()

    # Normalize 0-360 longitudes to -180..180 so the grid lines up with web
    # tiles / PostGIS (EPSG:4326).
    lon = ((lon + 180.0) % 360.0) - 180.0

    lat0, lat1 = float(np.nanmin(lat)), float(np.nanmax(lat))
    lon0, lon1 = float(np.nanmin(lon)), float(np.nanmax(lon))

    ny = int(np.ceil((lat1 - lat0) / res_deg)) + 1
    nx = int(np.ceil((lon1 - lon0) / res_deg)) + 1

    iy = np.floor((lat - lat0) / res_deg).astype(np.intp)
    ix = np.floor((lon - lon0) / res_deg).astype(np.intp)

    ok = (np.isfinite(val) & (iy >= 0) & (iy < ny) & (ix >= 0) & (ix < nx))
    flat = iy[ok] * nx + ix[ok]

    acc = np.full(ny * nx, -np.inf)
    np.maximum.at(acc, flat, val[ok])
    acc[~np.isfinite(acc)] = np.nan
    grid = acc.reshape(ny, nx)

    lats = lat0 + np.arange(ny) * res_deg
    lons = lon0 + np.arange(nx) * res_deg
    return lats, lons, grid
