# Demo recording script — walkthrough for Zach

A ~3-minute screen recording. Have the live Vercel page open in one tab and the
GitHub repo in another. Read this loosely — it's a script to talk *from*, not
word-for-word. `[ ]` lines are on-screen actions.

---

## 0:00 — Open (15s)

> "Hey Zach — after we talked about the hazard platform, I wanted to actually get
> my hands on the geospatial raster side rather than just say I'd pick it up. So
> I built a small end-to-end slice of an ingest-to-warnings pipeline over a
> weekend. Let me walk you through it and what I learned."

`[ Live Vercel page on screen — the hazard console ]`

---

## 0:15 — What's on screen (30s)

> "This is a wind-gust forecast over Oklahoma. Each colored zone is a hazard
> warning my pipeline generated automatically — advisory, high-wind warning, and
> damaging-wind tiers."

`[ Drag the forecast-hour scrubber, or hit play ]`

> "If I scrub through the forecast hours, you can watch the gust front move east
> and the warning polygons redraw with it. The counts on the left update per
> hour."

`[ Click one polygon to pop its attributes ]`

> "Each polygon carries its hazard class, peak gust, and valid time — so this
> isn't just a picture, it's queryable warning data."

---

## 0:45 — What I learned: the three formats (50s)

`[ Click the "What this is & what I learned" button to open the About panel ]`

> "The thing I really wanted to learn was the raster formats you mentioned —
> NetCDF, GRIB2, and Zarr. Here's the short version of what clicked for me:"

> "GRIB2 is the WMO weather format — it's what NOAA models like HRRR and GFS
> ship in. It's a stack of compact binary messages, one parameter per message.
> That's the format closest to your domain."

> "NetCDF is the self-describing science archive format — clean metadata, but
> built for 'download the whole file then read it.'"

> "Zarr is the cloud-native one, and that's the piece I think matters most for
> your 'high volume and velocity' requirement. It splits the data into chunks,
> each stored as its own object — so on S3 a client fetches only the chunks it
> needs, in parallel, instead of pulling whole files. I chunk one object per
> forecast hour here."

> "And the big realization: with xarray, all three open into the *same* object.
> You learn one mental model and the format becomes an implementation detail."

---

## 1:35 — The pipeline / architecture (45s)

`[ Switch to the GitHub repo, show the README diagram, scroll the hazpipe/ folder ]`

> "Under the hood the flow is: read GRIB2 with xarray and cfgrib, stage it as
> NetCDF and Zarr, then the hazard step thresholds the gust field and
> *polygonizes* it — turns the raster into vector warning zones with rasterio —
> and writes GeoJSON in EPSG:4326."

> "That GeoJSON drops straight into PostGIS as geometries, and straight into
> MapLibre on the frontend — which is exactly your stack, so the map you're
> looking at is rendering the pipeline's raw output with zero transformation."

---

## 2:20 — Honest scope (25s)

> "One thing I want to be straight about: my sandbox couldn't reach NOAA's live
> feeds, so the forecast *values* here are synthetic — a modeled gust front, not
> a real model run. But everything around the values is the real deal: it's
> encoded as genuine GRIB2, read through the real libraries, real Zarr chunking,
> real polygonization."

`[ Point at the generate_forecast.py file in the repo ]`

> "Going live just means swapping this one module for a NOMADS fetch. Nothing
> downstream changes — I isolated that seam on purpose."

---

## 2:45 — Close (20s)

> "So that's where I am: I'm not the meteorology-data specialist yet, but I came
> up to speed on the formats fast because the surrounding engineering — taking a
> prototype to production — is what I do every day. The README has a few notes
> on what I'd carry into the real system. I'd love to talk through your vision
> and where I could add the most value early. Thanks Zach."

`[ End ]`

---

## Recording tips

- **Tools:** Loom or CleanShot are easiest; both give a shareable link. QuickTime
  works if you'd rather just send a file.
- **Do a silent dry run first** — practice the scrubber drag and the polygon
  click once so the on-screen actions are smooth.
- **Keep it one take.** A slightly rough 3-minute take beats a polished 8-minute
  one. Zach is evaluating whether you understand the problem, not your editing.
- **Resolution:** record at 1080p so the small console text and the polygon
  attributes are legible.
- **Optional cold open:** start on the animated map (hit play before you start
  talking) so there's motion in the first frame.
