"""
pipeline.py
===========
Orchestrates one full forecast-cycle run, the way a scheduled job would:

  fetch (live HRRR GRIB2)  ->  ingest + regrid  ->  persist NetCDF + Zarr  ->
  derive hazard warning polygons  ->  write GeoJSON  ->  render preview map.

In production this is what a worker (e.g. a Celery task or an ECS scheduled
task) fires every time a new model cycle lands. It is idempotent: re-running
overwrites the cycle's artifacts in place.

Source: by default we pull the latest real HRRR cycle from NOAA NOMADS. If that
fetch fails (no network, NOMADS down mid-demo), we fall back to the synthetic
generator so the pipeline still produces output -- set ``source="synthetic"``
to force it, ``source="hrrr"`` to require live data.
"""
from __future__ import annotations

import os

from hazpipe.fetch_hrrr import fetch_hrrr
from hazpipe.generate_forecast import write_grib2
from hazpipe.ingest import load_grib2, load_hrrr
from hazpipe.store import write_netcdf, write_zarr
from hazpipe.hazard import derive_warnings, write_geojson


def _ingest_source(source: str, data_dir: str):
    """Return ``(dataset, cycle_init, source_label)``. ``source`` is one of
    ``"hrrr"`` (require live), ``"synthetic"`` (force offline), or ``"auto"``
    (try live, fall back to synthetic)."""
    if source in ("hrrr", "auto"):
        try:
            meta = fetch_hrrr(data_dir=data_dir)
            ds = load_hrrr(meta["paths"], cycle_init=meta["cycle_init"])
            return ds, meta["cycle_init"], "live HRRR (NOAA NOMADS)"
        except Exception as exc:  # noqa: BLE001 - resilience for the live demo
            if source == "hrrr":
                raise
            print(f"!! live HRRR fetch failed ({exc}); using synthetic data")

    grib = write_grib2(f"{data_dir}/gust_forecast.grib2")
    return load_grib2(grib), None, "synthetic (offline fallback)"


def run(data_dir: str = "data", out_dir: str = ".", source: str = "auto") -> dict:
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    ds, cycle_init, source_label = _ingest_source(source, data_dir)

    write_netcdf(ds, f"{data_dir}/gust_forecast.nc")
    write_zarr(ds, f"{data_dir}/gust_forecast.zarr")

    # hazard.py formats timestamps as naive-UTC + "Z"; strip tzinfo so a
    # tz-aware HRRR cycle_init doesn't render as "+00:00Z".
    naive_init = cycle_init.replace(tzinfo=None) if cycle_init else None
    fc = derive_warnings(ds, cycle_init=naive_init)
    fc["metadata"]["source"] = source_label
    gj = write_geojson(fc, f"{out_dir}/warnings.geojson")

    return {
        "geojson": gj,
        "source": source_label,
        "n_features": fc["metadata"]["n_features"],
        "steps": int(ds.sizes["step"]),
        "grid": f'{ds.sizes["latitude"]}x{ds.sizes["longitude"]}',
        "dataset": ds,
        "fc": fc,
    }


if __name__ == "__main__":
    r = run()
    print("=== forecast cycle complete ===")
    print(f"source      : {r['source']}")
    print(f"GeoJSON out : {r['geojson']}")
    print(f"grid        : {r['grid']}  x {r['steps']} forecast hours")
    print(f"warnings    : {r['n_features']} polygons")
