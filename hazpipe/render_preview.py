"""
render_preview.py
=================
Render a static preview of the pipeline output: the raster gust field with the
derived warning polygons overlaid, for each forecast hour. This is purely a
"proof it works" artifact -- in the real platform the GeoJSON would be served as
vector tiles to MapLibre instead.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import xarray as xr
from shapely.geometry import shape

from hazpipe.hazard import derive_warnings, HAZARD_TIERS


def render(nc_path: str, out_png: str) -> str:
    # Render from the cube the pipeline persisted, so the preview always
    # matches whatever source ran (live HRRR or synthetic fallback).
    ds = xr.open_dataset(nc_path)
    fc = derive_warnings(ds)
    da = ds.gust_mph

    steps = ds.step.values
    n = len(steps)
    ncol = 3
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 4.2 * nrow))
    axes = np.array(axes).reshape(-1)

    lon = da.longitude.values
    lat = da.latitude.values
    extent = [lon.min(), lon.max(), lat.min(), lat.max()]
    vmax = float(da.max())

    color_by_class = {t["class"]: t["color"] for t in HAZARD_TIERS}

    for si in range(n):
        ax = axes[si]
        field = da.isel(step=si).values
        im = ax.imshow(field, extent=extent, origin="lower",
                       cmap="viridis", vmin=0, vmax=vmax, aspect="auto")
        fhr = int(steps[si] / np.timedelta64(1, "h"))

        for ft in fc["features"]:
            if ft["properties"]["forecast_hour"] != fhr:
                continue
            poly = shape(ft["geometry"])
            color = color_by_class[ft["properties"]["hazard_class"]]
            polys = poly.geoms if poly.geom_type == "MultiPolygon" else [poly]
            for p in polys:
                x, y = p.exterior.xy
                ax.plot(x, y, color=color, linewidth=1.6)
                ax.fill(x, y, color=color, alpha=0.22)

        ax.set_title(f"Forecast hour F{fhr:02d}", fontsize=11)
        ax.set_xlabel("lon"); ax.set_ylabel("lat")

    for j in range(n, len(axes)):
        axes[j].axis("off")

    legend = [Patch(facecolor=t["color"], edgecolor=t["color"], alpha=0.5,
                    label=f'{t["class"].replace("_", " ")} (>={t["min_mph"]} mph)')
              for t in HAZARD_TIERS]
    fig.legend(handles=legend, loc="lower center", ncol=3, frameon=False,
               fontsize=10, bbox_to_anchor=(0.5, -0.01))

    fig.colorbar(im, ax=axes.tolist(), shrink=0.6, label="wind gust (mph)",
                 location="right")
    fig.suptitle(
        "Wind-gust hazard zones derived from a live NOAA HRRR GRIB2 forecast",
        fontsize=13, y=1.0)
    fig.savefig(out_png, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_png


if __name__ == "__main__":
    p = render("data/gust_forecast.nc", "hazard_preview.png")
    print(f"wrote {p}")
