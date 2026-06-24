"""
store.py
========
Persist the ingested forecast in the two formats that matter downstream:

  * NetCDF  -- the canonical self-describing archive format. One file, CF-style
              metadata. Great for "download the cube and analyze it" workflows.

  * Zarr    -- the cloud-native format. The array is split into CHUNKS, each
              stored as its own object. On S3 every chunk is a key, so a client
              can fetch just the chunks it needs over HTTP, in parallel, without
              pulling the whole dataset. This is the answer to the job post's
              "high volume and velocity" requirement: rechunk once on ingest,
              then serve partial reads cheaply.

The chunking strategy below (one chunk per forecast step, whole spatial field
per chunk) matches the dominant access pattern: "give me the hazard field for
forecast hour F03." Time-series-at-a-point access would chunk the other way.
"""
from __future__ import annotations

import os
import xarray as xr


def write_netcdf(ds: xr.Dataset, path: str) -> str:
    ds.to_netcdf(path)
    return path


def write_zarr(ds: xr.Dataset, path: str) -> str:
    # Chunk: 1 forecast step at a time, full spatial slab. Mirrors how a tile
    # server or warning job reads "one forecast hour" at a time.
    chunked = ds.chunk({"step": 1, "latitude": -1, "longitude": -1})

    # Encoding sets the on-disk/S3 chunk shape per variable.
    encoding = {
        "gust_mph": {"chunks": (1, ds.sizes["latitude"], ds.sizes["longitude"])}
    }
    chunked.to_zarr(path, mode="w", encoding=encoding, consolidated=True)
    return path


def _describe_zarr_layout(path: str) -> None:
    """Show the S3-key-like object layout that makes partial reads cheap."""
    print(f"\nZarr store object layout under {path}/ :")
    for root, _dirs, files in os.walk(path):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), path)
            print(f"  {rel}")


if __name__ == "__main__":
    from hazpipe.ingest import load_grib2

    ds = load_grib2("data/gust_forecast.grib2")
    nc = write_netcdf(ds, "data/gust_forecast.nc")
    zz = write_zarr(ds, "data/gust_forecast.zarr")
    print(f"NetCDF  -> {nc}")
    print(f"Zarr    -> {zz}")
    _describe_zarr_layout(zz)
