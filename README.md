# Wind-Gust Hazard Pipeline — a working demo

A small but **end-to-end** pipeline that ingests a GRIB2 weather forecast,
stages it in cloud-native formats, and turns it into **attributed hazard
warning polygons** ready for PostGIS and MapLibre.

I built this to get hands-on with the geospatial raster side of the platform —
NetCDF, GRIB2, and Zarr — and to show how that data flows from a model cycle all
the way to something an operator (or an incident system) can act on.

**Live demo:** _(add your Vercel URL here once deployed)_

```
 GRIB2 forecast ──► xarray/cfgrib ──► NetCDF + Zarr (S3-style chunks)
                                              │
                                              ▼
                      threshold ──► polygonize ──► GeoJSON warning zones
                                              │
                                              ▼
                              PostGIS  +  MapLibre GL (vector)
```

![preview](hazard_preview.png)

## What it does

A gust front sweeps eastward across Oklahoma over six forecast hours. For each
hour the pipeline thresholds the 10 m wind-gust field into three hazard tiers
(advisory ≥46 mph, high-wind warning ≥58, damaging ≥70), vectorizes each tier
into polygons, and emits a single GeoJSON `FeatureCollection`. Every polygon
carries `hazard_class`, `peak_gust_mph`, `forecast_hour`, and `valid_time`, in
EPSG:4326 — so it `INSERT`s into a PostGIS geometry column and renders in
MapLibre with zero transformation.

Open **`index.html`** for an interactive console: a forecast-hour
scrubber animates the warning zones across the run, and an "About" panel on the
page summarizes what each pipeline stage does.

## Honest scope

This environment can't reach NOAA's feeds, so the forecast **values are
synthetic** — a modelled gust front, not a real model run. Everything *around*
the values is the real thing: the data is encoded as genuine GRIB2 via ecCodes,
read back through the exact `xarray`/`cfgrib` path you'd use in production,
rechunked to real Zarr, and polygonized with `rasterio`. To run it on live data
you swap one module (`generate_forecast.py`) for a NOMADS / AWS-Open-Data fetch;
nothing downstream changes. The synthetic generator is the seam, and it's
isolated on purpose.

## How it maps to the platform stack

| Platform piece            | What this demo exercises                                  |
|---------------------------|-----------------------------------------------------------|
| GRIB2 / NetCDF / Zarr     | all three written and read; one `xarray` model across them |
| "high volume & velocity"  | Zarr chunked one-object-per-forecast-hour for cheap partial reads on S3 |
| PostgreSQL + PostGIS      | GeoJSON polygons in EPSG:4326, attribute-tagged, ready to insert |
| MapLibre GL + vanilla JS  | `output/index.html` renders the output directly, no build step |
| Python ingest/processing  | `xarray`, `cfgrib`, `rasterio`, `shapely`, `dask`         |
| AWS S3                    | Zarr object layout mirrors an S3 key structure            |

## Run it

```bash
pip install -r requirements.txt
./run.sh
# then open output/index.html
```

Or step by step:

```bash
python3 -m hazpipe.pipeline        # GRIB2 -> NetCDF + Zarr -> warnings.geojson
python3 -m hazpipe.render_preview  # static PNG (hazard_preview.png)
python3 -m hazpipe.build_map_demo  # interactive MapLibre page (index.html)
```

## Layout

```
index.html               deployable MapLibre console (Vercel serves this)
warnings.geojson         pipeline output (PostGIS / MapLibre ready)
hazard_preview.png       static preview montage
vercel.json              zero-build static deploy config
hazpipe/
  generate_forecast.py   synthetic forecast -> real GRIB2  (the swappable seam)
  ingest.py              GRIB2 -> clean xarray Dataset
  store.py               NetCDF archive + cloud-native Zarr (chunking strategy)
  hazard.py              threshold -> polygonize -> attributed GeoJSON
  pipeline.py            orchestrates one forecast cycle (idempotent)
  render_preview.py      static map montage
  build_map_demo.py      bakes GeoJSON into the MapLibre console
data/                    GRIB2 / NetCDF / Zarr artifacts (gitignored, regenerable)
```

## Deploy (Vercel)

The site is static — `index.html` has the GeoJSON inlined, so there's no build
step and no server. Vercel just serves the repo root.

1. Push this repo to GitHub.
2. In Vercel, **Add New → Project → Import** the GitHub repo.
3. Framework preset: **Other**. Build command: _none_. Output directory: _root_.
4. Deploy. The committed `index.html` is served as-is.

To refresh the data, run `./run.sh` locally and commit the regenerated
`index.html` / `warnings.geojson`.

## Notes toward production

A few things I'd carry into the real system, happy to talk through:

- **Vectorize on ingest, not in the browser.** Shipping rasters to the client
  doesn't scale; serving pre-derived vector warnings (or vector tiles) keeps the
  frontend fast and the warnings queryable in PostGIS.
- **Chunk to the access pattern.** Here it's one chunk per forecast hour because
  the dominant read is "the field for F03." Point-time-series access would chunk
  the other way; the right answer depends on how the platform reads.
- **Idempotent, per-cycle jobs.** Each model cycle is a self-contained run that
  overwrites its artifacts in place — safe to retry when a feed hiccups.
- **Polygon hygiene.** Real warnings want simplification, small-area filtering,
  and smoothing before they hit operators; the threshold→polygonize core is here,
  the cleanup is a known next layer.
