#!/usr/bin/env bash
# Run the whole thing end to end. Produces the deployable static site at the repo root.
set -euo pipefail
cd "$(dirname "$0")"

# Prefer the project venv (has the geospatial stack); fall back to python3.
PY="python3"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"

# cfgrib/eccodes need the eccodes C library; point at the Homebrew install.
if command -v brew >/dev/null 2>&1 && brew --prefix eccodes >/dev/null 2>&1; then
  export ECCODES_DIR="$(brew --prefix eccodes)"
fi

echo ">> 1/3  forecast cycle  (live HRRR GRIB2 -> xarray -> regrid -> NetCDF + Zarr -> warnings.geojson)"
$PY -W ignore -m hazpipe.pipeline

echo ">> 2/3  render static preview PNG"
$PY -W ignore -m hazpipe.render_preview

echo ">> 3/3  build MapLibre console (index.html)"
$PY -W ignore -m hazpipe.build_map_demo

echo
echo "Done. Deployable static site (serve / deploy the repo root):"
echo "  index.html           interactive MapLibre console  <- open this"
echo "  warnings.geojson      hazard polygons (PostGIS / MapLibre ready)"
echo "  hazard_preview.png    static preview"
echo
echo "Generated data artifacts (gitignored):"
echo "  data/hrrr_f0*.grib2   live HRRR gust (one file per forecast hour)"
echo "  data/gust_forecast.nc / .zarr"
