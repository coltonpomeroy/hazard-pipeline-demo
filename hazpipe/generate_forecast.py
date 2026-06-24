"""
generate_forecast.py
=====================
Stand-in for the "pull a forecast cycle from NOAA" step.

In production this module would fetch GRIB2 messages from a NOMADS / AWS Open
Data bucket (e.g. the HRRR or GFS S3 mirror). This environment has no access to
those feeds, so instead we SYNTHESIZE a physically-plausible 10 m wind-gust
forecast over Oklahoma and encode it as *real* GRIB2 using ecCodes -- the exact
binary format and library the production ingest would consume.

What's synthetic: the values (a modelled gust front sweeping eastward).
What's real:      the GRIB2 container, the ecCodes encode path, the grid
                  definition, the multi-step time dimension.

The downstream pipeline (ingest -> zarr -> hazard) does not know or care that
the data is synthetic. Swap this module for a NOMADS fetch and nothing else
changes.
"""
from __future__ import annotations

import numpy as np
import eccodes as ec

# --- Region: Oklahoma + surrounds. GRIB2 longitudes are 0-360. -------------
LAT0, LAT1, DLAT = 38.0, 33.0, 0.1      # north -> south (GRIB scan order)
LON0, LON1, DLON = 257.0, 266.0, 0.1    # 257E = 103W ... 266E = 94W
N_STEPS = 6                             # forecast hours F01..F06

lats = np.arange(LAT0, LAT1 - 1e-9, -DLAT)
lons = np.arange(LON0, LON1 + 1e-9, DLON)
NJ, NI = lats.size, lons.size


def _gust_field(step_hours: int) -> np.ndarray:
    """A band of high gusts (a dryline/gust front) marching west->east with
    the forecast hour, plus a calmer background and some texture. m/s."""
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    # Front center moves east ~0.6 deg/hr across the domain.
    front_lon = 258.5 + 0.6 * step_hours
    band = np.exp(-((lon_grid - front_lon) ** 2) / (2 * 0.45 ** 2))

    # Strongest gusts in a latitude window (think: warm sector).
    lat_weight = np.exp(-((lat_grid - 35.4) ** 2) / (2 * 1.1 ** 2))

    background = 7.0 + 2.0 * np.sin(lat_grid * 0.7)          # 5-9 m/s ambient
    peak = 30.0 * band * lat_weight                          # up to ~30 m/s
    texture = np.random.default_rng(step_hours).normal(0, 1.2, lat_grid.shape)

    field = background + peak + texture
    return np.clip(field, 0, None).astype(float)


def write_grib2(path: str) -> str:
    """Encode all forecast steps as GRIB2 messages into a single file."""
    with open(path, "wb") as fh:
        for step in range(1, N_STEPS + 1):
            gid = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")

            # Grid definition
            ec.codes_set(gid, "Ni", NI)
            ec.codes_set(gid, "Nj", NJ)
            ec.codes_set(gid, "latitudeOfFirstGridPointInDegrees", LAT0)
            ec.codes_set(gid, "longitudeOfFirstGridPointInDegrees", LON0)
            ec.codes_set(gid, "latitudeOfLastGridPointInDegrees", LAT1)
            ec.codes_set(gid, "longitudeOfLastGridPointInDegrees", LON1)
            ec.codes_set(gid, "iDirectionIncrementInDegrees", DLON)
            ec.codes_set(gid, "jDirectionIncrementInDegrees", DLAT)

            # Parameter: wind speed (gust). discipline 0 / cat 2 / num 22.
            ec.codes_set(gid, "discipline", 0)
            ec.codes_set(gid, "parameterCategory", 2)
            ec.codes_set(gid, "parameterNumber", 22)

            # Time: forecast hour as 'step'.
            ec.codes_set(gid, "forecastTime", step)
            ec.codes_set(gid, "indicatorOfUnitOfTimeRange", 1)  # 1 = hour

            ec.codes_set_values(gid, _gust_field(step).ravel())
            ec.codes_write(gid, fh)
            ec.codes_release(gid)
    return path


if __name__ == "__main__":
    out = write_grib2("data/gust_forecast.grib2")
    print(f"wrote {N_STEPS} GRIB2 messages -> {out}  grid {NJ}x{NI}")
