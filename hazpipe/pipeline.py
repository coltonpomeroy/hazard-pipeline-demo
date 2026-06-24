"""
pipeline.py
===========
Orchestrates one full forecast-cycle run, the way a scheduled job would:

  fetch (synthetic GRIB2)  ->  ingest  ->  persist NetCDF + Zarr  ->  derive
  hazard warning polygons  ->  write GeoJSON  ->  render preview map.

In production this is what a worker (e.g. a Celery task or an ECS scheduled
task) fires every time a new model cycle lands. It is idempotent: re-running
overwrites the cycle's artifacts in place.
"""
from __future__ import annotations

import os

from hazpipe.generate_forecast import write_grib2
from hazpipe.ingest import load_grib2
from hazpipe.store import write_netcdf, write_zarr
from hazpipe.hazard import derive_warnings, write_geojson


def run(data_dir: str = "data", out_dir: str = ".") -> dict:
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    grib = write_grib2(f"{data_dir}/gust_forecast.grib2")
    ds = load_grib2(grib)

    write_netcdf(ds, f"{data_dir}/gust_forecast.nc")
    write_zarr(ds, f"{data_dir}/gust_forecast.zarr")

    fc = derive_warnings(ds)
    gj = write_geojson(fc, f"{out_dir}/warnings.geojson")

    return {
        "grib2": grib,
        "geojson": gj,
        "n_features": fc["metadata"]["n_features"],
        "steps": int(ds.sizes["step"]),
        "grid": f'{ds.sizes["latitude"]}x{ds.sizes["longitude"]}',
        "dataset": ds,
        "fc": fc,
    }


if __name__ == "__main__":
    r = run()
    print("=== forecast cycle complete ===")
    print(f"GRIB2 in    : {r['grib2']}")
    print(f"GeoJSON out : {r['geojson']}")
    print(f"grid        : {r['grid']}  x {r['steps']} forecast hours")
    print(f"warnings    : {r['n_features']} polygons")
