#!/usr/bin/env bash
# Run the whole thing end to end. Produces the deployable static site at the repo root.
set -euo pipefail
cd "$(dirname "$0")"

echo ">> 1/3  forecast cycle  (GRIB2 -> xarray -> NetCDF + Zarr -> warnings.geojson)"
python3 -W ignore -m hazpipe.pipeline

echo ">> 2/3  render static preview PNG"
python3 -W ignore -m hazpipe.render_preview

echo ">> 3/3  build MapLibre console (index.html)"
python3 -W ignore -m hazpipe.build_map_demo

echo
echo "Done. Deployable static site (serve / deploy the repo root):"
echo "  index.html           interactive MapLibre console  <- open this"
echo "  warnings.geojson      hazard polygons (PostGIS / MapLibre ready)"
echo "  hazard_preview.png    static preview"
echo
echo "Generated data artifacts (gitignored):"
echo "  data/gust_forecast.grib2 / .nc / .zarr"
