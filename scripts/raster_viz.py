#!/usr/bin/env python3
"""
raster_viz.py
Publication-style single-band raster visualization with configurable
stretch, colorbar orientation, coordinate tick format, gridlines,
font family, title/subtitle, and axis labels.

Designed for georeferenced GeoTIFFs (e.g. LST, NDVI, IRECI, AGC, classification
rasters) opened with rasterio. Works with any CRS but tick coordinate
formatting (DMS/DD/D) is written for geographic (lon/lat, EPSG:4326-style)
rasters, which is the common case for GEE exports.

CLI USAGE
---------
python3 raster_viz.py INPUT.tif OUTPUT.png \
    --stretch percentile --pmin 2 --pmax 98 \
    --cmap viridis \
    --colorbar-orient vertical \
    --coord-format DD --gridlines \
    --font sans-serif \
    --title "Land Surface Temperature" --subtitle "Kalimantan, 2025" \
    --xlabel "Longitude" --ylabel "Latitude" \
    --colorbar-label "LST (°C)"

Run `python3 raster_viz.py --help` for the full flag list.

PROGRAMMATIC USAGE
-------------------
from raster_viz import plot_raster
plot_raster("INPUT.tif", "OUTPUT.png", stretch="percentile",
            pmin=2, pmax=98, colorbar_orient="vertical",
            coord_format="DD", gridlines=True, font="sans-serif",
            title="Land Surface Temperature", subtitle="Kalimantan, 2025")
"""

import argparse
import sys

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap


# --------------------------------------------------------------------------
# Named palettes (domain-specific, common in remote sensing map products)
# --------------------------------------------------------------------------

# Classic GEE-style thermal/LST ramp: dark blue -> cyan -> green -> yellow -> red -> dark red
PALETTE_LST_CLASSIC = [
    '040274', '040281', '0502a3', '0502b8', '0502ce', '0502e6',
    '0602ff', '235cb1', '307ef3', '269db1', '30c8e2', '32d3ef',
    '3be285', '3ff38f', '86e26f', '3ae237', 'b5e22e', 'd6e21f',
    'fff705', 'ffd611', 'ffb613', 'ff8b13', 'ff6e08', 'ff500d',
    'ff0000', 'de0101', 'c21301', 'a71001', '911003',
]

# Water / moisture index ramp (NDWI, MNDWI, AWEI, etc.): blue -> cyan -> yellow -> red -> white
PALETTE_WATER_INDEX = ['0000ff', '00ffff', 'ffff00', 'ff0000', 'ffffff']

# NDVI ramp anchored to specific data values (not evenly spaced 0-1).
# (ndvi_value, 0xRRGGBB) — this is the standard diverging brown/red -> green NDVI ramp.
_NDVI_STOPS = [
    (-1.0, 0x000000), (-0.2, 0xA50026), (0.0, 0xD73027), (0.1, 0xF46D43),
    (0.2, 0xFDAE61), (0.3, 0xFEE08B), (0.4, 0xFFFFBF), (0.5, 0xD9EF8B),
    (0.6, 0xA6D96A), (0.7, 0x66BD63), (0.8, 0x1A9850), (0.9, 0x006837),
]
NDVI_VMIN, NDVI_VMAX = _NDVI_STOPS[0][0], _NDVI_STOPS[-1][0]


def _hex_list_to_cmap(name: str, hex_colors: list) -> LinearSegmentedColormap:
    colors = [f"#{h.lstrip('#')}" for h in hex_colors]
    return LinearSegmentedColormap.from_list(name, colors)


def _ndvi_cmap() -> LinearSegmentedColormap:
    positions = [(v - NDVI_VMIN) / (NDVI_VMAX - NDVI_VMIN) for v, _ in _NDVI_STOPS]
    colors = [f"#{c:06x}" for _, c in _NDVI_STOPS]
    return LinearSegmentedColormap.from_list("ndvi_custom", list(zip(positions, colors)))


NAMED_PALETTES = {
    "lst_classic": lambda: _hex_list_to_cmap("lst_classic", PALETTE_LST_CLASSIC),
    "water_index": lambda: _hex_list_to_cmap("water_index", PALETTE_WATER_INDEX),
    "ndvi_custom": _ndvi_cmap,
}


def resolve_cmap(cmap_name: str):
    """Return a matplotlib-usable colormap: either a built-in name (viridis,
    magma, YlGn, Spectral, inferno, turbo, RdYlBu_r, ...) passed through as-is,
    or one of our named domain palettes resolved to a LinearSegmentedColormap."""
    if cmap_name in NAMED_PALETTES:
        return NAMED_PALETTES[cmap_name]()
    return cmap_name  # matplotlib built-in name, used directly


# --------------------------------------------------------------------------
# Coordinate tick formatting
# --------------------------------------------------------------------------

def _dms_string(value: float, is_lat: bool) -> str:
    """Format a decimal-degree value as D°M'S\" with hemisphere letter."""
    hemisphere = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    return f"{deg}\u00b0{minutes:02d}'{seconds:04.1f}\"{hemisphere}"


def _dd_string(value: float, is_lat: bool) -> str:
    """Decimal degrees with hemisphere letter, e.g. 108.59\u00b0E."""
    hemisphere = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    return f"{abs(value):.2f}\u00b0{hemisphere}"


def _plain_string(value: float, is_lat: bool) -> str:
    """Plain decimal number, no degree symbol or hemisphere (raw axis value)."""
    return f"{value:.2f}"


def resolve_colorbar_ticks(vmin: float, vmax: float, n_ticks: int = None):
    """Build colorbar tick positions that ALWAYS include the exact stretch
    min and max at the two ends of the bar, regardless of auto-spacing.

    n_ticks: if given (>=2), places that many evenly-spaced ticks from
    vmin to vmax (endpoints included by construction). If None, uses
    matplotlib's automatic locator for the interior ticks and forces the
    two endpoints on top of it.
    """
    if vmin == vmax:
        return np.array([vmin])
    if n_ticks is not None and n_ticks >= 2:
        return np.linspace(vmin, vmax, int(n_ticks))
    locator = mticker.MaxNLocator(nbins=6)
    auto_ticks = locator.tick_values(vmin, vmax)
    auto_ticks = auto_ticks[(auto_ticks > vmin) & (auto_ticks < vmax)]
    return np.unique(np.concatenate([[vmin], auto_ticks, [vmax]]))


def make_coord_formatter(coord_format: str, is_lat: bool):
    coord_format = coord_format.upper()
    if coord_format == "DMS":
        fn = _dms_string
    elif coord_format == "DD":
        fn = _dd_string
    elif coord_format == "D":
        fn = _plain_string
    else:
        raise ValueError(f"Unknown coord_format '{coord_format}'. Use DMS, DD, or D.")
    return mticker.FuncFormatter(lambda val, pos: fn(val, is_lat))


# --------------------------------------------------------------------------
# Stretch computation
# --------------------------------------------------------------------------

def compute_stretch(data: np.ndarray, stretch: str, pmin: float = 2, pmax: float = 98,
                     vmin: float = None, vmax: float = None):
    """
    Returns (vmin, vmax) for the given stretch mode.

    stretch:
      - 'minmax'     : use the true data min/max
      - 'percentile' : use the pmin/pmax percentiles (default 2/98), robust to outliers
      - 'manual'     : use the user-supplied vmin/vmax directly
    """
    valid = data[np.isfinite(data)]
    if valid.size == 0:
        raise ValueError("Raster band contains no valid (finite) pixels.")

    stretch = stretch.lower()
    if stretch == "minmax":
        return float(valid.min()), float(valid.max())
    elif stretch == "percentile":
        lo, hi = np.percentile(valid, [pmin, pmax])
        return float(lo), float(hi)
    elif stretch == "manual":
        if vmin is None or vmax is None:
            raise ValueError("stretch='manual' requires both vmin and vmax.")
        return float(vmin), float(vmax)
    else:
        raise ValueError(f"Unknown stretch '{stretch}'. Use minmax, percentile, or manual.")


# --------------------------------------------------------------------------
# Main plotting function
# --------------------------------------------------------------------------

def plot_raster(
    input_path: str,
    output_path: str,
    band: int = 1,
    # stretch
    stretch: str = "percentile",
    pmin: float = 2,
    pmax: float = 98,
    vmin: float = None,
    vmax: float = None,
    # colormap / colorbar
    cmap: str = "viridis",
    colorbar_orient: str = "vertical",
    colorbar_label: str = None,
    colorbar_label_position: str = "side",
    colorbar_nticks: int = None,
    colorbar_decimals: int = None,
    # coordinates / gridlines
    coord_format: str = "DD",
    gridlines: bool = True,
    grid_step: float = None,
    # typography
    font: str = "sans-serif",
    # text
    title: str = None,
    subtitle: str = None,
    title_align: str = "left",
    title_fontsize: float = 15,
    subtitle_fontsize: float = 10.5,
    title_gap: float = 0.045,
    xlabel: str = None,
    ylabel: str = None,
    # canvas
    figsize=(10, 8),
    dpi: int = 200,
    background: str = "white",
    language: str = "en",
):
    """
    Render a single-band georeferenced raster to a publication-style figure.

    Defaults follow the common case: percentile stretch (2-98%), vertical
    colorbar, decimal-degree (DD) coordinate ticks with gridlines on,
    sans-serif font, white background, and axis labels of
    "Longitude" / "Latitude".
    """
    font = font.lower()
    if font in ("sans-serif", "sans serif", "sans"):
        family = "sans-serif"
    elif font == "serif":
        family = "serif"
    else:
        raise ValueError("font must be 'serif' or 'sans-serif'")
    plt.rcParams["font.family"] = family

    with rasterio.open(input_path) as src:
        data = src.read(band).astype("float64")
        nodata = src.nodata
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)
        bounds = src.bounds  # left, bottom, right, top
        is_geographic = src.crs is not None and src.crs.is_geographic

    # ndvi_custom's colors are anchored to specific NDVI values (-1.0..0.9), not
    # a relative stretch. If the caller didn't pin vmin/vmax explicitly, align
    # the stretch to the palette's own range so colors map correctly.
    if cmap == "ndvi_custom" and stretch != "manual" and vmin is None and vmax is None:
        stretch, vmin, vmax = "manual", NDVI_VMIN, NDVI_VMAX

    vmin_calc, vmax_calc = compute_stretch(data, stretch, pmin, pmax, vmin, vmax)
    resolved_cmap = resolve_cmap(cmap)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(background)
    ax.set_facecolor(background)

    im = ax.imshow(
        data,
        cmap=resolved_cmap,
        vmin=vmin_calc,
        vmax=vmax_calc,
        extent=[bounds.left, bounds.right, bounds.bottom, bounds.top],
        origin="upper",
        interpolation="nearest",
    )

    # --- Titles ---
    # title_align: 'left' (default) or 'center' — aligned relative to the axes,
    # not the full figure, so it lines up with the map edge when 'left'.
    # title_gap controls the vertical spacing between title and subtitle
    # (axes-fraction units); title_fontsize/subtitle_fontsize control sizing
    # independently.
    align = title_align.lower()
    if align not in ("center", "left"):
        raise ValueError("title_align must be 'center' or 'left'")
    ha = "center" if align == "center" else "left"
    tx = 0.5 if align == "center" else 0.0
    base_y = 1.015
    if title and subtitle:
        ax.text(tx, base_y, subtitle, transform=ax.transAxes, ha=ha, va="bottom",
                 fontsize=subtitle_fontsize, color="#333333")
        ax.text(tx, base_y + title_gap, title, transform=ax.transAxes, ha=ha, va="bottom",
                 fontsize=title_fontsize, fontweight="bold")
    elif title:
        ax.text(tx, base_y, title, transform=ax.transAxes, ha=ha, va="bottom",
                 fontsize=title_fontsize, fontweight="bold")
    elif subtitle:
        ax.text(tx, base_y, subtitle, transform=ax.transAxes, ha=ha, va="bottom",
                 fontsize=subtitle_fontsize, color="#333333")

    # --- Axis labels ---
    labels_en = {"x_geo": "Longitude", "y_geo": "Latitude", "x_proj": "Easting",
                 "y_proj": "Northing", "colorbar": "Pixel value"}
    labels_id = {"x_geo": "Bujur", "y_geo": "Lintang", "x_proj": "Timur (Easting)",
                 "y_proj": "Utara (Northing)", "colorbar": "Nilai piksel"}
    L = labels_id if language.lower() in ("id", "indonesia", "bahasa", "bahasa indonesia") else labels_en
    default_xlabel = L["x_geo"] if is_geographic else L["x_proj"]
    default_ylabel = L["y_geo"] if is_geographic else L["y_proj"]
    ax.set_xlabel(xlabel if xlabel is not None else default_xlabel, fontsize=11)
    ax.set_ylabel(ylabel if ylabel is not None else default_ylabel, fontsize=11)

    # --- Coordinate tick formatting ---
    if is_geographic:
        ax.xaxis.set_major_formatter(make_coord_formatter(coord_format, is_lat=False))
        ax.yaxis.set_major_formatter(make_coord_formatter(coord_format, is_lat=True))
    if grid_step:
        ax.xaxis.set_major_locator(mticker.MultipleLocator(grid_step))
        ax.yaxis.set_major_locator(mticker.MultipleLocator(grid_step))
    else:
        ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=5))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5))
    plt.setp(ax.get_xticklabels(), rotation=0, fontsize=8.5)
    plt.setp(ax.get_yticklabels(), fontsize=8.5)

    # --- Gridlines ---
    if gridlines:
        ax.grid(True, linestyle="--", linewidth=0.5, color="#888888", alpha=0.6)
    else:
        ax.grid(False)

    # --- Colorbar ---
    orient = colorbar_orient.lower()
    if orient not in ("vertical", "horizontal"):
        raise ValueError("colorbar_orient must be 'vertical' or 'horizontal'")
    cbar = fig.colorbar(
        im, ax=ax,
        orientation=orient,
        fraction=0.046 if orient == "vertical" else 0.05,
        pad=0.04,
    )
    # Force the colorbar ends to always show the actual stretch min/max values
    # (the real data bounds used for the stretch), plus optional custom tick count.
    ticks = resolve_colorbar_ticks(vmin_calc, vmax_calc, colorbar_nticks)
    cbar.set_ticks(ticks)
    if colorbar_decimals is not None:
        decimals = int(colorbar_decimals)
    else:
        span = vmax_calc - vmin_calc
        decimals = 0 if span >= 20 else (1 if span >= 2 else 2)
    cbar.set_ticklabels([f"{t:.{decimals}f}" for t in ticks])

    label_text = colorbar_label if colorbar_label else L["colorbar"]
    label_pos = colorbar_label_position.lower()
    if label_pos not in ("side", "top"):
        raise ValueError("colorbar_label_position must be 'side' or 'top'")
    if label_pos == "top":
        # Unrotated label placed above the colorbar (common in GEE-app-style legends)
        cbar.ax.set_title(label_text, fontsize=10, pad=6)
    else:
        # Default: rotated label at the side for vertical bars, below for horizontal
        cbar.set_label(label_text, fontsize=10)
    cbar.ax.tick_params(labelsize=8.5)

    ax.set_aspect("equal" if is_geographic else "auto")

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, facecolor=background, bbox_inches="tight")
    plt.close(fig)
    return output_path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_arg_parser():
    p = argparse.ArgumentParser(description="Raster visualization with configurable stretch, "
                                             "colorbar, coordinate format, gridlines, and typography.")
    p.add_argument("input", help="Path to input GeoTIFF (single band read via --band)")
    p.add_argument("output", help="Path to output image (PNG/JPG/PDF/SVG)")
    p.add_argument("--band", type=int, default=1)

    p.add_argument("--stretch", choices=["minmax", "percentile", "manual"], default="percentile")
    p.add_argument("--pmin", type=float, default=2)
    p.add_argument("--pmax", type=float, default=98)
    p.add_argument("--vmin", type=float, default=None)
    p.add_argument("--vmax", type=float, default=None)

    p.add_argument("--cmap", default="viridis",
                    help="Matplotlib colormap name (viridis, magma, YlGn, Spectral, inferno, "
                         "turbo, RdYlBu_r, ...) or a named domain palette: "
                         "lst_classic, water_index, ndvi_custom")
    p.add_argument("--colorbar-orient", choices=["vertical", "horizontal"], default="vertical")
    p.add_argument("--colorbar-label", default=None)
    p.add_argument("--colorbar-label-position", choices=["side", "top"], default="side")
    p.add_argument("--colorbar-nticks", type=int, default=None,
                    help="Number of evenly-spaced colorbar ticks (endpoints always included). "
                         "Omit for automatic spacing.")
    p.add_argument("--colorbar-decimals", type=int, default=None,
                    help="Number of decimal places for colorbar tick labels. "
                         "Omit for automatic (0 if span>=20, 1 if span>=2, else 2).")

    p.add_argument("--coord-format", choices=["DMS", "DD", "D"], default="DD")
    p.add_argument("--gridlines", action="store_true", default=True)
    p.add_argument("--no-gridlines", dest="gridlines", action="store_false")
    p.add_argument("--grid-step", type=float, default=None)

    p.add_argument("--font", choices=["serif", "sans-serif"], default="sans-serif")

    p.add_argument("--title", default=None)
    p.add_argument("--subtitle", default=None)
    p.add_argument("--title-align", choices=["center", "left"], default="left")
    p.add_argument("--title-fontsize", type=float, default=15)
    p.add_argument("--subtitle-fontsize", type=float, default=10.5)
    p.add_argument("--title-gap", type=float, default=0.045,
                    help="Vertical spacing between title and subtitle, in axes-fraction units. "
                         "Smaller = tighter. Default 0.045.")
    p.add_argument("--xlabel", default=None)
    p.add_argument("--ylabel", default=None)

    p.add_argument("--figsize", type=float, nargs=2, default=(10, 8))
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--background", default="white")
    p.add_argument("--language", choices=["en", "id"], default="en",
                    help="Language for default axis/colorbar labels (en=English, id=Bahasa Indonesia)")
    return p


def main():
    args = _build_arg_parser().parse_args()
    out = plot_raster(
        input_path=args.input,
        output_path=args.output,
        band=args.band,
        stretch=args.stretch,
        pmin=args.pmin,
        pmax=args.pmax,
        vmin=args.vmin,
        vmax=args.vmax,
        cmap=args.cmap,
        colorbar_orient=args.colorbar_orient,
        colorbar_label=args.colorbar_label,
        colorbar_label_position=args.colorbar_label_position,
        colorbar_nticks=args.colorbar_nticks,
        colorbar_decimals=args.colorbar_decimals,
        coord_format=args.coord_format,
        gridlines=args.gridlines,
        grid_step=args.grid_step,
        font=args.font,
        title=args.title,
        subtitle=args.subtitle,
        title_align=args.title_align,
        title_fontsize=args.title_fontsize,
        subtitle_fontsize=args.subtitle_fontsize,
        title_gap=args.title_gap,
        xlabel=args.xlabel,
        ylabel=args.ylabel,
        figsize=tuple(args.figsize),
        dpi=args.dpi,
        background=args.background,
        language=args.language,
    )
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
