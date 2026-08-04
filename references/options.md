# raster_viz.py — full parameter reference

## `plot_raster(...)` signature

```python
plot_raster(
    input_path, output_path, band=1,
    stretch="percentile", pmin=2, pmax=98, vmin=None, vmax=None,
    cmap="viridis",
    colorbar_orient="vertical", colorbar_label=None,
    coord_format="DD", gridlines=True, grid_step=None,
    font="sans-serif",
    title=None, subtitle=None, xlabel=None, ylabel=None,
    figsize=(10, 8), dpi=200, background="white",
)
```

## Stretch modes

- **`minmax`** — uses the true min/max of valid (finite, non-nodata) pixels.
  Sensitive to single-pixel outliers (sensor noise, cloud edge artifacts).
- **`percentile`** — uses the `pmin`/`pmax` percentiles (default 2/98). This is
  the recommended default for most GEE-derived rasters (LST, NDVI, IRECI, TRVI,
  AGC) because it clips extreme outliers without needing manual inspection.
- **`manual`** — uses caller-supplied `vmin`/`vmax`. Use this when the user
  wants a fixed, comparable scale across multiple figures (e.g. comparing LST
  across two dates, or matching an established AGC classification scheme).

## Coordinate tick formats (`coord_format`, geographic CRS only)

- **`DMS`** — sexagesimal, e.g. `108°35'18.0"E` / `2°30'00.0"N`
- **`DD`** — decimal degrees with hemisphere letter, e.g. `108.59°E`
- **`D`** — plain decimal number, no degree symbol or hemisphere, e.g. `108.59`

For a projected CRS (e.g. UTM zone), `coord_format` is ignored and ticks show
raw Easting/Northing values in the raster's native units (usually meters).

## Gridlines

`gridlines=True` draws dashed light-gray reference lines at the major tick
positions. Use `grid_step` to force a specific tick spacing (in the raster's
coordinate units, e.g. `1.0` for 1° spacing) instead of matplotlib's automatic
`MaxNLocator`.

## Typography

`font` sets `plt.rcParams["font.family"]` for the whole figure — title,
subtitle, axis labels, tick labels, and colorbar label all inherit it.
`serif` reads as more "journal typeset" (e.g. Times-like); `sans-serif` reads
as more modern/technical (e.g. Helvetica-like). Neither requires a specific
font file — matplotlib resolves to its default serif/sans-serif family.

## Title vs. subtitle

- `title` → rendered as a bold `fig.suptitle`
- `subtitle` → rendered as a smaller italic line directly beneath the title
  (or as the sole heading, styled the same way, if no title is given)

Both are optional; a figure with neither is valid (useful for figures that
will get a caption externally, e.g. in a Word/LaTeX document).

## Colorbar

`colorbar_orient` is `vertical` (right side, default) or `horizontal` (below
the plot). Always set `colorbar_label` explicitly to the variable's name and
unit — the default `"Pixel value"` is a placeholder and should not appear in
a final figure.

## Multi-panel / classification rasters

This script renders one continuous-scale figure per call. For a discrete
classification raster (e.g. land cover classes), don't force a continuous
colormap — instead build a `ListedColormap` + `BoundaryNorm` and a categorical
legend; ask the user if that's what they need, since it changes the
colorbar into a class legend rather than a continuous scale.
