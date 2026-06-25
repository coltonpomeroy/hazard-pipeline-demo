"""
fetch_hrrr.py
=============
Pull a REAL wind-gust forecast from NOAA's HRRR model via NOMADS.

HRRR (High-Resolution Rapid Refresh) is the 3 km CONUS model operational
forecasters lean on for short-fuse wind hazards. We use the NOMADS GRIB-filter
endpoint, which server-side subsets the GRIB2 to just the surface GUST field --
so each downloaded message carries a single variable (the ingest's
one-data-var assumption still holds) and the payload stays small.

This is the live drop-in for generate_forecast.write_grib2(): identical
contract (GRIB2 files on disk that ingest reads), real NOAA data instead of
synthetic. HRRR ships on a Lambert Conformal grid, so ingest reprojects it to a
regular lat/lon grid (see regrid.py) before the unchanged hazard pipeline runs.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests

NOMADS = "https://nomads.ncep.noaa.gov/cgi-bin/filter_hrrr_2d.pl"
GRIB_MAGIC = b"GRIB"


def _params(init: datetime, fhr: int) -> dict:
    ymd = init.strftime("%Y%m%d")
    cc = init.strftime("%H")
    return {
        "dir": f"/hrrr.{ymd}/conus",
        "file": f"hrrr.t{cc}z.wrfsfcf{fhr:02d}.grib2",
        "var_GUST": "on",
        "lev_surface": "on",
    }


def _download(init: datetime, fhr: int, dest: str, timeout: int = 90) -> bool:
    """Fetch one forecast hour. Returns True only on a real GRIB2 payload --
    NOMADS answers a bad cycle/param with a 200 HTML error page, so we check
    the GRIB magic bytes rather than trusting the status code alone."""
    try:
        r = requests.get(NOMADS, params=_params(init, fhr), timeout=timeout)
    except requests.RequestException:
        return False
    if r.status_code != 200 or r.content[:4] != GRIB_MAGIC:
        return False
    with open(dest, "wb") as fh:
        fh.write(r.content)
    return True


def fetch_hrrr(data_dir: str = "data", n_steps: int = 6,
               max_lookback: int = 8) -> dict:
    """Download HRRR surface gust for F01..F{n_steps} from the most recent
    available cycle.

    HRRR posts hourly with ~1-2 h latency, so we start ~2 h back and step
    further back hour-by-hour until a cycle whose F01 is live. Returns
    ``{"cycle_init": datetime(UTC), "paths": {fhr: path}}``.
    """
    os.makedirs(data_dir, exist_ok=True)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    for back in range(2, 2 + max_lookback):
        init = now - timedelta(hours=back)
        probe = f"{data_dir}/hrrr_f01.grib2"
        if not _download(init, 1, probe):
            continue  # this cycle isn't published yet; try an earlier one

        paths = {1: probe}
        complete = True
        for fhr in range(2, n_steps + 1):
            dest = f"{data_dir}/hrrr_f{fhr:02d}.grib2"
            if not _download(init, fhr, dest):
                complete = False
                break
            paths[fhr] = dest

        if complete:
            return {"cycle_init": init, "paths": paths}

    raise RuntimeError(
        "No complete HRRR cycle found on NOMADS within "
        f"{max_lookback} h lookback")


if __name__ == "__main__":
    meta = fetch_hrrr()
    print(f"HRRR cycle {meta['cycle_init']:%Y-%m-%d %H}Z")
    for fhr, path in sorted(meta["paths"].items()):
        print(f"  F{fhr:02d} -> {path}  ({os.path.getsize(path)//1024} KB)")
