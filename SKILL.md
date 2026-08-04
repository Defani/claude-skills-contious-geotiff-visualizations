---
name: continuous-raster-visualization
description: Render a single-band georeferenced continuous raster (GeoTIFF — LST, NDVI, IRECI, TRVI, AGC, or other continuous remote sensing output) into a publication-style map with configurable stretch (min-max/percentile/manual), colormap (built-in LST/water-index/NDVI palettes plus viridis/magma/YlGn/Spectral), colorbar orientation, label position, and tick count (endpoints always show real data min/max), coordinate format (DMS/DD/decimal), gridlines, font family/sizes, and title/subtitle spacing/alignment. Use whenever the user wants to visualize, plot, map, or "buat peta"/"visualisasikan" a .tif/.tiff continuous raster, or adjust stretch/palette/colorbar/gridline/coordinate-format/font/title options for one. Not for discrete/classification rasters (needs a categorical legend, not a continuous colorbar). Trigger even for a subset of these options — apply sensible defaults otherwise.
---

# Continuous Raster Visualization

Produces a single, publication-style map figure from a single-band, continuous-value
GeoTIFF, with full control over the visual/cartographic options a remote-sensing
paper or thesis figure typically needs.

## Step 0 — language

The first time this skill is used in a conversation, ask the user (once) whether
they want **English** or **Bahasa Indonesia** — this sets the default axis labels
("Longitude"/"Latitude" vs "Bujur"/"Lintang"), default colorbar label ("Pixel
value" vs "Nilai piksel"), and the language Claude uses when talking about the
visualization for the rest of the session. Use `ask_user_input_v0` with a single
single_select question (English / Bahasa Indonesia) if available; otherwise just
ask in plain text. Don't re-ask on later calls in the same conversation — carry
the choice forward via the `language` parameter (`en`/`id`). If the user has
already stated a language preference (e.g. they're writing in Indonesian), it's
fine to infer instead of asking.


## When to use this skill

- The user uploads or references a `.tif`/`.tiff` file and asks to visualize, plot,
  or map it (LST, NDVI, IRECI, TRVI, AGC, land-cover classification, etc.)
- The user asks to adjust stretch, percentile, colorbar orientation, gridlines,
  coordinate format (DMS/DD/D), font, title/subtitle, or axis labels for a raster map
- The user wants a figure suitable for a skripsi/thesis or journal manuscript

Do NOT use this for multi-band RGB composites, vector data, or non-georeferenced
images — this skill assumes a single-band raster opened with rasterio.

## Workflow

1. **Inspect the raster first.** Before plotting, always check band count, CRS,
   nodata value, and the valid-data min/max/percentiles:

   ```python
   import rasterio, numpy as np
   with rasterio.open(path) as src:
       print(src.crs, src.count, src.nodata)
       data = src.read(1)
       valid = data[np.isfinite(data)] if src.nodata is None else data[data != src.nodata]
       print(valid.min(), valid.max(), np.percentile(valid, [2, 98]))
   ```

   This tells you whether a percentile stretch will meaningfully differ from
   min-max (e.g. LST/NDVI rasters often have extreme outlier pixels at the
   scene edge — percentile stretch is usually the better default), and whether
   the CRS is geographic (lon/lat) — coordinate tick formatting (DMS/DD/D) only
   applies to geographic CRS; for projected CRS (e.g. UTM) ticks are shown as
   plain Easting/Northing meters regardless of `coord_format`.

2. **Ask only for what's ambiguous.** If the user has already specified an
   option (e.g. "pakai DMS, grid on"), don't re-ask. For anything unspecified,
   use the defaults below rather than blocking on questions — this is a
   visualization tool, not a form.

3. **Call `scripts/raster_viz.py`** (CLI or import `plot_raster` directly) with
   the resolved options. See `references/options.md` for the full parameter
   reference and value meanings if you need more detail than below.

4. **Show the result inline** (view the output PNG) before presenting it, so
   you can catch an obviously wrong stretch or unreadable ticks and adjust
   before showing the user.

## Options and defaults

| Option | Choices | Default | Notes |
|---|---|---|---|
| `stretch` | `minmax`, `percentile`, `manual` | `percentile` (2–98%) | `manual` requires `vmin`/`vmax` |
| `pmin`/`pmax` | any 0–100 | `2`/`98` | only used when `stretch=percentile` |
| `colorbar_orient` | `vertical`, `horizontal` | `vertical` | |
| `coord_format` | `DMS`, `DD`, `D` | `DD` | DMS = D°M'S″ + hemisphere; DD = decimal degrees + hemisphere; D = plain decimal number, no symbol. Only affects geographic CRS. |
| `gridlines` | on/off | **on** | dashed, light gray |
| `font` | `serif`, `sans-serif` | `sans-serif` | applies to the whole figure |
| `background` | any matplotlib color | `white` | white is the standard default — don't ask unless the user wants something else |
| `title` | free text | none | bold, above the plot |
| `title_fontsize` | number | `15` | |
| `subtitle` | free text | none | plain (not italic), smaller, directly under the title |
| `subtitle_fontsize` | number | `10.5` | |
| `title_gap` | number (axes-fraction) | `0.045` | vertical spacing between title and subtitle — lower = tighter |
| `language` | `en`, `id` | `en` | sets default axis/colorbar label wording — see Step 0 |
| `xlabel`/`ylabel` | free text | `Longitude`/`Latitude` (geographic) or `Easting`/`Northing` (projected) | |
| `colorbar_label` | free text | `Pixel value` | strongly recommend setting this to the actual unit, e.g. `LST (°C)`, `AGC (ton/ha)`, `NDVI` |
| `colorbar_label_position` | `side`, `top` | `side` | `side` = rotated label along the bar; `top` = unrotated label above the bar (GEE-app legend style) |
| `colorbar_nticks` | integer ≥2 | auto (~6) | Colorbar end ticks **always** show the actual stretch min/max, regardless of this setting — set this only to control how many ticks appear *between* the ends. Ask the user how many ticks they want if the default auto count looks cluttered or sparse. |
| `colorbar_decimals` | integer ≥0 | auto (0/1/2 by span) | Decimal places shown on colorbar tick labels. Auto often produces awkward values like `28.5` next to a rounder `28.8` endpoint — if the user finds a tick label ugly or inconsistent, offer to set this explicitly (e.g. `0` for whole degrees) rather than leaving it to the automatic rule. |
| `cmap` | any matplotlib colormap, or a named palette (`lst_classic`, `water_index`, `ndvi_custom`) | `viridis` | pick a perceptually appropriate one for the variable — see below |
| `title_align` | `left`, `center` | `left` | `left` aligns to the map's left edge, not the figure |

### Colormap guidance (ask or infer from context, don't default blindly)

- Temperature (LST): `lst_classic` (the classic GEE thermal ramp) is the standard
  choice; `inferno`, `RdYlBu_r`, `turbo` also work
- Water/moisture indices (NDWI, MNDWI, AWEI): `water_index`
- NDVI specifically: `ndvi_custom` (auto-aligns stretch to -1.0..0.9 — see below).
  Other vegetation indices (IRECI, TRVI) that aren't on the same fixed scale:
  `RdYlGn` or `YlGn` (low→high greenness)
- Biomass/carbon (AGC): sequential, e.g. `viridis`, `YlGn`, `Greens`
- Classification (land cover): a discrete/qualitative colormap, not continuous —
  flag this to the user, this script is built for continuous single-band data

### Colorbar end ticks always match the actual data

Regardless of stretch mode or `colorbar_nticks`, the two ends of the colorbar
always display the exact numeric min/max that the stretch resolved to (e.g. the
true data min/max for `minmax`, or the actual 2nd/98th percentile *values* for
`percentile`) — never rounded-off "nice" numbers that don't correspond to real
data. This is enforced automatically; no flag needed.

## Example call

```bash
python3 scripts/raster_viz.py INPUT.tif OUTPUT.png \
    --stretch percentile --pmin 2 --pmax 98 \
    --cmap inferno \
    --colorbar-orient vertical \
    --coord-format DD --gridlines \
    --font sans-serif \
    --title "Land Surface Temperature" --subtitle "Kalimantan, 2025" \
    --colorbar-label "LST (°C)"
```

Or programmatically:

```python
import sys
sys.path.insert(0, "scripts")
from raster_viz import plot_raster

plot_raster(
    "INPUT.tif", "OUTPUT.png",
    stretch="percentile", pmin=2, pmax=98,
    cmap="inferno",
    colorbar_orient="vertical",
    coord_format="DD", gridlines=True,
    font="sans-serif",
    title="Land Surface Temperature", subtitle="Kalimantan, 2025",
    colorbar_label="LST (\u00b0C)",
)
```

## Output

Save the rendered PNG (or PDF/SVG if the user needs a vector figure for a
manuscript — just change the output extension) to `/mnt/user-data/outputs/`
and present it with `present_files`.
