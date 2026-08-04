# continuous-raster-visualization

A Claude Skill for rendering single-band, continuous-value georeferenced rasters
(GeoTIFF) into publication-style map figures, built for remote sensing workflows
such as LST, NDVI, IRECI, TRVI, and AGC outputs.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Matplotlib](https://img.shields.io/badge/matplotlib-3.x-11557c)](https://matplotlib.org/)
[![Rasterio](https://img.shields.io/badge/rasterio-1.x-3a7ca5)](https://rasterio.readthedocs.io/)
[![NumPy](https://img.shields.io/badge/numpy-1.x%2F2.x-013243)](https://numpy.org/)
[![Claude Skill](https://img.shields.io/badge/claude-skill-6a5acd)](SKILL.md)
[![Remote Sensing](https://img.shields.io/badge/domain-remote%20sensing-0f6e56)](#what-it-does)
[![GeoTIFF](https://img.shields.io/badge/input-GeoTIFF-3a7ca5)](#quick-start)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Demo

![Land Surface Temperature map of Kalimantan rendered by this skill](assets/demo.png)

*Percentile stretch, `lst_classic` palette, left-aligned title, English labels — all current defaults.*

## Skill preview

An interactive, self-contained HTML preview of this skill (badges, palette
gallery, feature list, tech stack, and the demo above) is bundled at
[`assets/preview.html`](assets/preview.html) — download it and open it in any
browser, no server needed.

## What it does

Given a single-band GeoTIFF and a set of options, the skill produces one map
figure (PNG/PDF/SVG) with control over:

- Stretch: min-max, percentile (default 2-98%), or manual vmin/vmax
- Colormap: built-in domain palettes (`lst_classic`, `water_index`, `ndvi_custom`)
  or any matplotlib colormap (viridis, magma, YlGn, Spectral, and more)
- Colorbar orientation (vertical/horizontal), label position (side/top), and
  tick count — the two ends always show the actual data min/max used for the
  stretch, never rounded placeholder numbers
- Coordinate tick format for geographic rasters: DMS, DD, or plain decimal
- Gridlines on/off
- Font family (serif/sans-serif) and independent title/subtitle font sizes
- Title/subtitle spacing and alignment (left by default, or center)
- Output language for default labels: English or Bahasa Indonesia

## Files

```
continuous-raster-visualization/
  SKILL.md                 skill definition and usage guide
  scripts/raster_viz.py    the rendering engine (CLI + importable function)
  references/options.md    full parameter reference
  README.md                this file
  LICENSE                  MIT license
```

## Quick start

```bash
python3 scripts/raster_viz.py INPUT.tif OUTPUT.png \
    --stretch percentile --pmin 2 --pmax 98 \
    --cmap lst_classic \
    --colorbar-orient vertical --colorbar-label "LST (deg C)" \
    --coord-format DD --gridlines \
    --font sans-serif \
    --title "Land Surface Temperature" --subtitle "Kalimantan, 2025"
```

Or from Python:

```python
from scripts.raster_viz import plot_raster

plot_raster(
    "INPUT.tif", "OUTPUT.png",
    stretch="percentile", pmin=2, pmax=98,
    cmap="lst_classic",
    colorbar_orient="vertical", colorbar_label="LST (deg C)",
    coord_format="DD", gridlines=True,
    font="sans-serif",
    title="Land Surface Temperature", subtitle="Kalimantan, 2025",
)
```

See `SKILL.md` for the full workflow Claude follows when using this skill, and
`references/options.md` for every parameter in detail.

## License

MIT. See [LICENSE](LICENSE).
