"""
ingest.py
=========
Read GRIB2 with xarray's cfgrib engine and normalize to a clean, analysis-ready
xarray Dataset. This is the real read path you'd use against NOAA GRIB2 in
production -- the only thing that changes for live data is the source path.

Key idea worth showing Zach: NetCDF, GRIB2, and Zarr all open into the *same*
xarray object. You learn one mental model (labeled N-dimensional arrays) and the
backend format becomes an implementation detail.
"""
from __future__ import annotations

import numpy as np
import xarray as xr


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
