"""
ingest.py
=========
Read GRIB2 with xarray's cfgrib engine and normalize to a clean, analysis-ready
xarray Dataset. This is the real read path used against NOAA GRIB2 -- whether
the bytes come from a live HRRR cycle (``load_hrrr``) or the synthetic
offline-fallback generator (``load_grib2``), the rest of the pipeline sees the
same tidy Dataset.

Key idea worth showing Zach: NetCDF, GRIB2, and Zarr all open into the *same*
xarray object. You learn one mental model (labeled N-dimensional arrays) and the
backend format becomes an implementation detail.

HRRR arrives on a Lambert Conformal grid (2-D lat/lon coords); ``load_hrrr``
reprojects it to a regular EPSG:4326 grid (see regrid.py) so it lands in the
exact same shape the synthetic path produces -- one variable ``gust_mph`` over
dims (step, latitude, longitude).
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from hazpipe.regrid import regrid_max

# m/s -> mph (forecasters and warning thresholds are in mph here).
MS_TO_MPH = 2.236936


def load_hrrr(paths: dict[int, str], cycle_init=None) -> xr.Dataset:
    """Assemble a tidy gust Dataset from per-forecast-hour HRRR GRIB2 files.

    ``paths`` maps forecast hour -> GRIB2 path (from fetch_hrrr). Each file holds
    a single surface-gust field on HRRR's Lambert grid; we reproject every step
    to a shared regular lat/lon grid and stack them along ``step``.
    """
    fhrs = sorted(paths)
    grids, lats, lons = [], None, None

    for fhr in fhrs:
        ds = xr.open_dataset(
            paths[fhr], engine="cfgrib", backend_kwargs={"indexpath": ""})
        (var_name,) = list(ds.data_vars)  # filtered to one var by NOMADS
        da = ds[var_name]
        lats, lons, grid = regrid_max(
            da.latitude.values, da.longitude.values, da.values)
        grids.append(grid * MS_TO_MPH)
        ds.close()

    arr = np.stack(grids, axis=0)  # (step, latitude, longitude)
    steps = np.array([np.timedelta64(int(f), "h") for f in fhrs])

    gust_mph = xr.DataArray(
        arr,
        dims=("step", "latitude", "longitude"),
        coords={"step": steps, "latitude": lats, "longitude": lons},
        name="gust_mph",
    )
    gust_mph.attrs.update(
        units="mph",
        long_name="10 m wind gust",
        note="LIVE NOAA HRRR surface gust, regridded to EPSG:4326",
    )

    out = gust_mph.to_dataset()
    out.attrs.update(
        source="NOAA HRRR via NOMADS",
        model="HRRR",
        native_resolution="3km",
        grid="regular_ll",
        crs="EPSG:4326",
    )
    if cycle_init is not None:
        out.attrs["cycle_init"] = cycle_init.isoformat()
    return out


def load_grib2(path: str) -> xr.Dataset:
    """Open a multi-step GRIB2 file and return a tidy Dataset:
    dims (step, latitude, longitude), one variable `gust_mph`.
    """
    ds = xr.open_dataset(
        path,
        engine="cfgrib",
        backend_kwargs={"indexpath": ""},  # don't litter .idx files
    )

    # cfgrib decodes our discipline/cat/num as an unknown/named var; grab the
    # single data variable robustly rather than hard-coding its name.
    (var_name,) = list(ds.data_vars)
    da = ds[var_name]

    # Normalize coords: GRIB longitudes are 0-360; convert to -180..180 so the
    # data lines up with web-map tiles and PostGIS (EPSG:4326).
    da = da.assign_coords(longitude=(((da.longitude + 180) % 360) - 180))
    da = da.sortby("longitude").sortby("latitude")

    # m/s -> mph (forecasters and warning thresholds are in mph here).
    gust_mph = da * 2.236936
    gust_mph.name = "gust_mph"
    gust_mph.attrs.update(
        units="mph",
        long_name="10 m wind gust",
        note="SYNTHETIC demo data encoded as real GRIB2",
    )

    out = gust_mph.to_dataset()
    out.attrs.update(
        source=path,
        grid="regular_ll",
        crs="EPSG:4326",
    )
    return out


if __name__ == "__main__":
    ds = load_grib2("data/gust_forecast.grib2")
    print(ds)
    print("\nsteps:", ds.step.values)
    print("gust range (mph): %.1f .. %.1f" % (
        float(ds.gust_mph.min()), float(ds.gust_mph.max())))
