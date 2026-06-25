"""
build_map_demo.py
=================
Bake the pipeline's GeoJSON warning output into a standalone, no-build MapLibre
GL page -- the same frontend stack the target platform already uses. The point
is concrete: the polygons this pipeline emits drop into MapLibre with zero
transformation. Open output/index.html in any browser.

The forecast-hour scrubber animates the warning zones the same way an operator
would step through a model run in the real product.
"""
from __future__ import annotations

import json
from collections import defaultdict

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Wind-Gust Hazard Console</title>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  :root {{
    --bg: #0b0f14;
    --panel: #121821;
    --panel-edge: #1f2935;
    --ink: #e6edf3;
    --ink-dim: #8b9aa9;
    --teal: #38d6c4;
    --advisory: #f1c40f;
    --warning: #e67e22;
    --damaging: #e0483a;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
    --sans: "Inter", system-ui, -apple-system, sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; background: var(--bg); color: var(--ink);
    font-family: var(--sans); }}
  #app {{ display: grid; grid-template-rows: auto 1fr; height: 100%; }}

  header {{ padding: 14px 20px; border-bottom: 1px solid var(--panel-edge);
    background: var(--panel); display: flex; align-items: baseline; gap: 16px;
    flex-wrap: wrap; }}
  .eyebrow {{ font-family: var(--mono); font-size: 11px; letter-spacing: .18em;
    text-transform: uppercase; color: var(--teal); }}
  h1 {{ font-size: 16px; font-weight: 600; margin: 0; letter-spacing: -.01em; }}
  .sub {{ color: var(--ink-dim); font-size: 12.5px; }}

  #map-wrap {{ position: relative; }}
  #map {{ position: absolute; inset: 0; }}

  .console {{ position: absolute; z-index: 5; top: 16px; left: 16px; width: 264px;
    background: rgba(18,24,33,.92); border: 1px solid var(--panel-edge);
    border-radius: 10px; backdrop-filter: blur(8px); overflow: hidden; }}
  .console > div {{ padding: 14px 16px; }}
  .console .row {{ border-bottom: 1px solid var(--panel-edge); }}

  .step-line {{ display: flex; align-items: center; justify-content: space-between; }}
  .fhr {{ font-family: var(--mono); font-size: 30px; font-weight: 600;
    letter-spacing: -.02em; line-height: 1; }}
  .fhr small {{ color: var(--ink-dim); font-size: 12px; font-weight: 400; }}
  .valid {{ font-family: var(--mono); font-size: 11px; color: var(--ink-dim);
    margin-top: 4px; }}

  .scrub {{ display: flex; align-items: center; gap: 10px; margin-top: 12px; }}
  .scrub input {{ flex: 1; accent-color: var(--teal); }}
  button.play {{ width: 34px; height: 34px; border-radius: 8px; cursor: pointer;
    border: 1px solid var(--panel-edge); background: #0e141c; color: var(--ink);
    font-size: 13px; line-height: 1; }}
  button.play:hover {{ border-color: var(--teal); color: var(--teal); }}

  .tier {{ display: flex; align-items: center; gap: 10px; font-size: 12.5px;
    padding: 5px 0; }}
  .tier .sw {{ width: 22px; height: 12px; border-radius: 3px; flex: none; }}
  .tier .name {{ flex: 1; }}
  .tier .ct {{ font-family: var(--mono); font-variant-numeric: tabular-nums;
    color: var(--ink); }}
  .tier .ct.zero {{ color: #455160; }}

  .foot {{ font-size: 11px; color: var(--ink-dim); line-height: 1.5; }}
  .foot b {{ color: var(--ink); font-weight: 600; }}
  .maplibregl-popup-content {{ background: #0e141c; color: var(--ink);
    font-family: var(--mono); font-size: 12px; border: 1px solid var(--panel-edge);
    border-radius: 8px; }}
  .maplibregl-popup-tip {{ border-top-color: #0e141c !important; }}

  #about-btn {{ margin-left: auto; cursor: pointer; font-family: var(--mono);
    font-size: 11px; letter-spacing: .04em; color: var(--teal);
    background: transparent; border: 1px solid var(--panel-edge);
    border-radius: 7px; padding: 7px 12px; }}
  #about-btn:hover {{ border-color: var(--teal); }}

  .about-overlay {{ position: fixed; inset: 0; z-index: 50; display: grid;
    place-items: center; padding: 24px; background: rgba(4,7,11,.72);
    backdrop-filter: blur(4px); }}
  .about-overlay[hidden] {{ display: none; }}
  .about-card {{ position: relative; max-width: 560px; width: 100%;
    background: var(--panel); border: 1px solid var(--panel-edge);
    border-radius: 14px; padding: 28px 30px; max-height: 86vh; overflow-y: auto; }}
  .about-card h2 {{ font-size: 21px; margin: 8px 0 14px; letter-spacing: -.015em; }}
  .about-card p {{ color: var(--ink-dim); font-size: 14px; line-height: 1.6; }}
  .about-card p b, .about-card li b {{ color: var(--ink); font-weight: 600; }}
  .about-steps {{ margin: 16px 0; padding-left: 20px; }}
  .about-steps li {{ color: var(--ink-dim); font-size: 13.5px; line-height: 1.55;
    margin-bottom: 11px; }}
  .about-steps .m {{ font-family: var(--mono); font-size: 12px; color: var(--teal); }}
  .about-note {{ border-left: 2px solid var(--teal); padding-left: 14px;
    margin-top: 18px !important; font-size: 13px !important; }}
  #about-close {{ position: absolute; top: 14px; right: 16px; cursor: pointer;
    background: transparent; border: none; color: var(--ink-dim); font-size: 24px;
    line-height: 1; }}
  #about-close:hover {{ color: var(--ink); }}
  .byline {{ margin-top: 8px; color: #455160; font-size: 10.5px;
    font-family: var(--mono); }}
</style>
</head>
<body>
<div id="app">
  <header>
    <span class="eyebrow">hazpipe // preview</span>
    <h1>Wind-Gust Hazard Console</h1>
    <span class="sub">Warning polygons derived from a GRIB2 forecast cycle &mdash; rendered straight from the pipeline's GeoJSON.</span>
    <button id="about-btn">What this is &amp; what I learned</button>
  </header>
  <div id="map-wrap">
    <div id="map"></div>
    <div class="console">
      <div class="row">
        <div class="step-line">
          <div class="fhr" id="fhr">F01 <small>fcst hr</small></div>
          <button class="play" id="play" title="Play / pause">&#9654;</button>
        </div>
        <div class="valid" id="valid"></div>
        <div class="scrub">
          <input type="range" id="slider" min="{min_h}" max="{max_h}" step="1" value="{min_h}" />
        </div>
      </div>
      <div class="row" id="tiers"></div>
      <div>
        <div class="foot">
          <b>Source: {source}.</b> {cycle_note}. Pipeline: GRIB2 &rarr; xarray &rarr;
          regrid &rarr; Zarr &rarr; threshold &rarr; polygonize &rarr; GeoJSON.
          Click a zone for attributes.
          <div class="byline">built by Colton Pomeroy &middot; hazpipe demo</div>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="about" class="about-overlay" hidden>
  <div class="about-card">
    <button id="about-close" aria-label="Close">&times;</button>
    <span class="eyebrow">hazpipe // what i learned</span>
    <h2>From a GRIB2 forecast to map-ready hazard zones</h2>
    <p>This is a working slice of an ingest-to-warnings pipeline I built to get
    hands-on with the geospatial raster formats: <b>NetCDF</b>, <b>GRIB2</b>, and
    <b>Zarr</b>. Everything you see on the map was generated by it.</p>
    <ol class="about-steps">
      <li><b>GRIB2 in.</b> The latest <b>HRRR</b> surface-gust cycle, pulled live
      from <b>NOAA NOMADS</b> as real GRIB2 (the WMO format NOAA models ship in)
      and read back with <span class="m">xarray</span> + <span class="m">cfgrib</span>.</li>
      <li><b>One mental model.</b> GRIB2, NetCDF, and Zarr all open into the same
      labeled N-dimensional <span class="m">xarray</span> object &mdash; the
      format becomes an implementation detail.</li>
      <li><b>Zarr for the cloud.</b> The cube is rechunked one-object-per-forecast-hour,
      so on S3 a client fetches only the chunks it needs. That's the answer to
      "high volume &amp; velocity."</li>
      <li><b>Raster &rarr; vector.</b> The gust field is thresholded into hazard
      tiers and polygonized with <span class="m">rasterio</span> into attributed
      GeoJSON &mdash; EPSG:4326, ready for PostGIS and this MapLibre map.</li>
    </ol>
    <p class="about-note"><b>This is live data.</b> The map shows the most recent
    real <b>HRRR</b> wind-gust cycle fetched from <b>NOAA NOMADS</b> at build time.
    HRRR ships on a Lambert Conformal grid, so the one adaptation versus the
    earlier synthetic build is a reprojection step onto a regular EPSG:4326 grid;
    everything downstream of ingest is unchanged. The synthetic generator is kept
    as an offline fallback so the pipeline still runs if NOMADS is unreachable.</p>
  </div>
</div>

<script>
const WARNINGS = {geojson};
const COUNTS = {counts};
const TIERS = [
  {{ cls: "wind_advisory",     label: "Wind advisory",     color: "var(--advisory)", hex: "#f1c40f" }},
  {{ cls: "high_wind_warning", label: "High wind warning", color: "var(--warning)",  hex: "#e67e22" }},
  {{ cls: "damaging_wind",     label: "Damaging wind",     color: "var(--damaging)", hex: "#e0483a" }},
];
const HOURS = {hours};
const BOUNDS = {bounds};
let current = HOURS[0];
let playing = false, timer = null;

const map = new maplibregl.Map({{
  container: "map",
  style: {{
    version: 8,
    sources: {{
      base: {{
        type: "raster",
        tiles: ["https://a.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}.png",
                "https://b.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}.png"],
        tileSize: 256,
        attribution: "&copy; OpenStreetMap &copy; CARTO"
      }}
    }},
    layers: [{{ id: "base", type: "raster", source: "base" }}]
  }},
  center: [-98.0, 38.5],
  zoom: 3.4
}});

map.addControl(new maplibregl.NavigationControl({{ showCompass: false }}), "bottom-right");

map.on("load", () => {{
  map.addSource("warnings", {{ type: "geojson", data: WARNINGS }});

  // Fill, painted by hazard class.
  map.addLayer({{
    id: "warn-fill", type: "fill", source: "warnings",
    paint: {{
      "fill-color": ["match", ["get", "hazard_class"],
        "wind_advisory", "#f1c40f",
        "high_wind_warning", "#e67e22",
        "damaging_wind", "#e0483a", "#888"],
      "fill-opacity": 0.32
    }}
  }});
  map.addLayer({{
    id: "warn-line", type: "line", source: "warnings",
    paint: {{
      "line-color": ["match", ["get", "hazard_class"],
        "wind_advisory", "#f1c40f",
        "high_wind_warning", "#e67e22",
        "damaging_wind", "#e0483a", "#888"],
      "line-width": 1.4
    }}
  }});

  setHour(current);
  // Frame wherever today's hazards actually are (auto-find active wind).
  map.fitBounds(BOUNDS, {{ padding: 48, duration: 0, maxZoom: 7 }});

  map.on("click", "warn-fill", (e) => {{
    const p = e.features[0].properties;
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(
        `${{p.hazard_class.replace(/_/g," ")}}<br>` +
        `peak gust ${{p.peak_gust_mph}} mph<br>` +
        `valid ${{p.valid_time}}`
      ).addTo(map);
  }});
  map.on("mouseenter", "warn-fill", () => map.getCanvas().style.cursor = "pointer");
  map.on("mouseleave", "warn-fill", () => map.getCanvas().style.cursor = "");
}});

function setHour(h) {{
  current = h;
  const filter = ["==", ["get", "forecast_hour"], h];
  if (map.getLayer("warn-fill")) map.setFilter("warn-fill", filter);
  if (map.getLayer("warn-line")) map.setFilter("warn-line", filter);

  document.getElementById("fhr").innerHTML =
    `F${{String(h).padStart(2,"0")}} <small>fcst hr</small>`;
  const meta = COUNTS[h] || {{ valid: "", counts: {{}} }};
  document.getElementById("valid").textContent = "valid " + (meta.valid || "");
  document.getElementById("slider").value = h;

  const box = document.getElementById("tiers");
  box.innerHTML = TIERS.map(t => {{
    const n = (meta.counts && meta.counts[t.cls]) || 0;
    return `<div class="tier">
      <span class="sw" style="background:${{t.hex}}"></span>
      <span class="name">${{t.label}}</span>
      <span class="ct ${{n===0?"zero":""}}">${{n}}</span>
    </div>`;
  }}).join("");
}}

document.getElementById("slider").addEventListener("input", (e) => {{
  stop(); setHour(parseInt(e.target.value, 10));
}});

function step() {{
  const i = HOURS.indexOf(current);
  setHour(HOURS[(i + 1) % HOURS.length]);
}}
function play() {{ playing = true; document.getElementById("play").innerHTML = "&#10073;&#10073;";
  timer = setInterval(step, 900); }}
function stop() {{ playing = false; document.getElementById("play").innerHTML = "&#9654;";
  if (timer) clearInterval(timer); timer = null; }}
document.getElementById("play").addEventListener("click", () => playing ? stop() : play());

// About overlay
const about = document.getElementById("about");
document.getElementById("about-btn").addEventListener("click", () => about.hidden = false);
document.getElementById("about-close").addEventListener("click", () => about.hidden = true);
about.addEventListener("click", (e) => {{ if (e.target === about) about.hidden = true; }});
document.addEventListener("keydown", (e) => {{ if (e.key === "Escape") about.hidden = true; }});
</script>
</body>
</html>
"""


def _bounds(fc: dict):
    """[[minLon, minLat], [maxLon, maxLat]] over every feature vertex, so the
    map can fitBounds to wherever today's wind hazards actually are."""
    xs, ys = [], []

    def walk(coords):
        if coords and isinstance(coords[0], (int, float)):
            xs.append(coords[0]); ys.append(coords[1]); return
        for c in coords:
            walk(c)

    for ft in fc["features"]:
        walk(ft["geometry"]["coordinates"])
    if not xs:  # no hazards this cycle -- fall back to a CONUS view
        return [[-125.0, 24.0], [-66.5, 49.5]]
    return [[min(xs), min(ys)], [max(xs), max(ys)]]


def build(geojson_path: str, out_html: str) -> str:
    with open(geojson_path) as f:
        fc = json.load(f)

    # Per-hour counts + valid time for the readout.
    counts: dict[int, dict] = {}
    by_hour_class: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    valid_by_hour: dict[int, str] = {}
    hours_set = set()
    for ft in fc["features"]:
        p = ft["properties"]
        h = p["forecast_hour"]
        hours_set.add(h)
        by_hour_class[h][p["hazard_class"]] += 1
        valid_by_hour[h] = p["valid_time"]

    hours = sorted(hours_set)
    for h in hours:
        counts[h] = {"valid": valid_by_hour[h], "counts": dict(by_hour_class[h])}

    meta = fc.get("metadata", {})
    source = meta.get("source", "live HRRR (NOAA NOMADS)")
    iso = (meta.get("cycle_init") or "").replace("+00:00", "").rstrip("Z")
    # "2026-06-25T13:00:00" -> "2026-06-25 13Z" (HRRR cycles are hourly)
    cycle_note = f"HRRR cycle {iso[:13].replace('T', ' ')}Z" if iso \
        else "HRRR forecast cycle"

    html = TEMPLATE.format(
        geojson=json.dumps(fc),
        counts=json.dumps(counts),
        hours=json.dumps(hours),
        min_h=hours[0],
        max_h=hours[-1],
        bounds=json.dumps(_bounds(fc)),
        source=source,
        cycle_note=cycle_note,
    )
    with open(out_html, "w") as f:
        f.write(html)
    return out_html


if __name__ == "__main__":
    out = build("warnings.geojson", "index.html")
    print(f"wrote {out}")
