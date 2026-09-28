"""Shareable run report: map videos (MP4), progression charts (PNG) and one static page per playthrough.

`ppc report` reads the multi-save dataset (`graphs/dataset`, built by `ppc savegame-notebooks build`) and
writes `graphs/report/<run>/`:

- `maps/*.mp4` - one H.264 video per map (political, population, population change, development, building
  levels, unemployment), one frame per save, sized to stay under 10 MB so Discord and GitHub play it inline;
  `maps/*.png` - the last frame of each (a poster / thumbnail);
- `charts/*.png` - progression charts (population by pop type and region, employment, buildings, prices,
  largest countries);
- `index.html` - the page that ties them together; it only references files next to it, so the folder can
  be opened locally, zipped or published as it is.

Frames are painted with one NumPy lookup per frame (a location-index raster built once) and streamed to
ffmpeg, so a whole run renders in well under a minute.
"""

from __future__ import annotations

import html
import json
import math
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import polars as pl
from PIL import Image, ImageDraw, ImageFont

POP_TYPES = ("nobles", "clergy", "burghers", "laborers", "soldiers", "peasants", "slaves", "tribesmen")
# Categorical order (fixed, never cycled), light and dark chart surfaces.
CATEGORICAL = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
OTHER_GREY = "#9a9a96"

# Video theme (dark: Discord and GitHub dark mode are the common viewers).
SEA = (18, 26, 36)
LAND_NODATA = (58, 63, 72)
UNOWNED = (76, 80, 88)
TEXT = (236, 238, 240)
TEXT_MUTED = (160, 166, 176)
PANEL = (12, 16, 22)
# Sequential ramp for magnitude on a dark surface: dark (low) -> light (high), one hue (blue).
SEQUENTIAL = ("#123055", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb", "#f2f7fe")
# Diverging: red (loss) - neutral - blue (gain).
DIVERGING = ("#8f1f1f", "#c63b3b", "#e67a73", "#d8c9c6", "#8fb8ec", "#3987e5", "#184f95")
DIVERGING_DARK_MID = "#4a4a47"

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
FONT_BOLD_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
MAX_VIDEO_BYTES = 9_500_000


# --------------------------------------------------------------------------------------------------------
# Data


@dataclass
class RunData:
    playthrough_id: str
    name: str
    snapshots: pl.DataFrame  # snapshot_id, date, year, date_sort (sorted)
    locations: pl.DataFrame  # per snapshot and location
    building_levels: pl.DataFrame  # snapshot_id, slug, levels
    buildings_by_category: pl.DataFrame  # snapshot_id, building_category, levels
    countries: pl.DataFrame
    goods: pl.DataFrame  # snapshot_id, good_id, price_index, value

    @property
    def years(self) -> tuple[int, int]:
        years = self.snapshots["year"].drop_nulls()
        return int(years.min()), int(years.max())


def _scan(dataset: Path, table: str, playthrough: str) -> pl.LazyFrame:
    root = dataset / "tables" / table / f"playthrough_id={playthrough}"
    files = sorted(root.glob("*.parquet"))
    if not files:
        raise SystemExit(f"no {table} snapshots for playthrough {playthrough} in {dataset}")
    return pl.scan_parquet([str(f) for f in files], missing_columns="insert", extra_columns="ignore")


def latest_playthrough(dataset: Path) -> str:
    manifest = pl.read_parquet(dataset / "manifest.parquet")
    latest = manifest.sort("mtime").row(-1, named=True)
    return str(latest["playthrough_id"])


def load_run(dataset: Path, playthrough: str | None = None) -> RunData:
    playthrough = playthrough or latest_playthrough(dataset)
    manifest = pl.read_parquet(dataset / "manifest.parquet").filter(pl.col("playthrough_id") == playthrough)
    snapshots = (
        manifest.select("snapshot_id", "date", "year", "date_sort", "playthrough_name")
        .unique("snapshot_id")
        .sort("date_sort")
    )
    # the game writes playthrough_name only for some starts (e.g. "England #7558ddce"); else the id's first block
    name = next((n for n in snapshots["playthrough_name"].to_list() if n), f"Run {playthrough[:8]}")
    wanted = snapshots["snapshot_id"].to_list()
    loc_columns = [
        "snapshot_id", "slug", "country_tag", "owner", "super_region", "development", "total_population",
        "unemployed_total", *[f"population_{p}" for p in POP_TYPES], *[f"employed_{p}" for p in POP_TYPES],
    ]
    locations = _scan(dataset, "locations", playthrough).select(loc_columns).filter(pl.col("snapshot_id").is_in(wanted)).collect()
    buildings = _scan(dataset, "buildings", playthrough).select("snapshot_id", "building_type", "location_slug", "level")
    catalog = (
        _scan(dataset, "building_catalog", playthrough)
        .select("building_type", "building_category")
        .unique("building_type")
        .collect()
    )
    building_levels = (
        buildings.group_by("snapshot_id", "location_slug").agg(pl.col("level").sum().alias("levels"))
        .rename({"location_slug": "slug"})
        .collect()
    )
    buildings_by_category = (
        buildings.group_by("snapshot_id", "building_type").agg(pl.col("level").sum().alias("levels"))
        .collect()
        .join(catalog, on="building_type", how="left")
        .with_columns(pl.col("building_category").fill_null("other"))
        .group_by("snapshot_id", "building_category")
        .agg(pl.col("levels").sum())
    )
    countries = (
        _scan(dataset, "countries", playthrough)
        .select("snapshot_id", "country_tag", "country_name", "population", "owned_locations_count", "gold", "is_subject")
        .collect()
    )
    goods = (
        _scan(dataset, "market_goods", playthrough)
        .select("snapshot_id", "good_id", "price", "default_price", "supply", "demand")
        .filter(pl.col("price").is_not_null() & (pl.col("default_price") > 0))
        .with_columns((pl.col("supply").fill_null(0) + pl.col("demand").fill_null(0)).alias("volume"))
        .group_by("snapshot_id", "good_id")
        .agg(
            ((pl.col("price") / pl.col("default_price") * pl.col("volume")).sum() / pl.col("volume").sum()).alias("price_index"),
            (pl.col("supply").fill_null(0) * pl.col("default_price")).sum().alias("value"),
        )
        .collect()
    )
    return RunData(playthrough, str(name), snapshots, locations, building_levels, buildings_by_category, countries, goods)


# --------------------------------------------------------------------------------------------------------
# Map canvas and colour


@dataclass
class MapCanvas:
    index: np.ndarray  # H x W int32: location index, -1 sea, -2 land without a location
    tags: list[str]
    width: int
    height: int
    tag_index: dict[str, int] = field(default_factory=dict)


def build_canvas(repo: Path, project: Path, width: int) -> MapCanvas:
    from prosper_or_perish_constructor import savegame_maps as sm

    assets = sm.load_map_assets(repo=repo, project=project, map_width=width)
    geometry = assets.prepared_geometry.select("location_tag", "map_color_int").unique("map_color_int").sort("map_color_int")
    colors = geometry["map_color_int"].to_numpy().astype(np.uint32)
    tags = geometry["location_tag"].to_list()
    packed = assets.packed_locations
    flat = packed.reshape(-1)
    positions = np.searchsorted(colors, flat)
    positions = np.clip(positions, 0, len(colors) - 1)
    matched = colors[positions] == flat
    index = np.where(matched, positions, np.where(flat == 0, -1, -2)).astype(np.int32).reshape(packed.shape)
    height = index.shape[0] - index.shape[0] % 2
    index = index[:height, : width - width % 2]
    return MapCanvas(index=index, tags=tags, width=index.shape[1], height=index.shape[0],
                     tag_index={tag: i for i, tag in enumerate(tags)})


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _ramp(stops: tuple[str, ...], n: int = 256) -> np.ndarray:
    points = np.array([_hex(s) for s in stops], dtype=np.float64)
    x = np.linspace(0, 1, len(stops))
    t = np.linspace(0, 1, n)
    return np.stack([np.interp(t, x, points[:, c]) for c in range(3)], axis=1).round().astype(np.uint8)


@dataclass
class Scale:
    kind: str  # "log", "linear", "diverging"
    low: float
    high: float
    lut: np.ndarray
    ticks: list[tuple[float, str]]

    def position(self, values: np.ndarray) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            if self.kind == "log":
                v = np.log10(np.maximum(values, self.low))
                t = (v - math.log10(self.low)) / (math.log10(self.high) - math.log10(self.low))
            elif self.kind == "diverging":
                t = 0.5 + 0.5 * np.clip(values, self.low, self.high) / max(abs(self.low), abs(self.high))
            else:
                t = (values - self.low) / (self.high - self.low)
        return np.clip(t, 0.0, 1.0)

    def colours(self, values: np.ndarray) -> np.ndarray:
        t = self.position(values)
        out = self.lut[np.nan_to_num(t * (len(self.lut) - 1), nan=0).astype(np.int32)]
        out[~np.isfinite(values)] = LAND_NODATA
        return out


# --------------------------------------------------------------------------------------------------------
# Frame composition


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _format_number(value: float) -> str:
    if not math.isfinite(value):
        return "–"
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= limit:
            return f"{value / limit:.1f}{suffix}"
    return f"{value:.0f}" if abs(value) >= 10 else f"{value:.2f}"


class FrameComposer:
    """Map + bottom bar (title, year, legend, key figures) as one RGB frame."""

    BAR = 120

    def __init__(self, canvas: MapCanvas, title: str, subtitle: str, scale: Scale | None):
        self.canvas = canvas
        self.width = canvas.width
        self.height = canvas.height + self.BAR
        self.title = title
        self.subtitle = subtitle
        self.scale = scale
        self.fonts = {"title": _font(30, True), "sub": _font(18), "year": _font(58, True), "small": _font(16), "stat": _font(24, True)}
        self._bar = self._static_bar()

    def _static_bar(self) -> Image.Image:
        bar = Image.new("RGB", (self.width, self.BAR), PANEL)
        draw = ImageDraw.Draw(bar)
        draw.text((28, 18), self.title, font=self.fonts["title"], fill=TEXT)
        draw.text((28, 62), self.subtitle, font=self.fonts["sub"], fill=TEXT_MUTED)
        if self.scale is not None:
            x0, y0, w, h = self.width // 2 - 260, 38, 520, 16
            gradient = np.repeat(self.scale.lut[np.linspace(0, len(self.scale.lut) - 1, w).astype(int)][None, :, :], h, axis=0)
            bar.paste(Image.fromarray(gradient.astype(np.uint8)), (x0, y0))
            for value, label in self.scale.ticks:
                t = float(self.scale.position(np.array([value], dtype=np.float64))[0])
                x = x0 + int(t * (w - 1))
                draw.line([(x, y0 + h), (x, y0 + h + 6)], fill=TEXT_MUTED, width=1)
                box = draw.textbbox((0, 0), label, font=self.fonts["small"])
                draw.text((x - (box[2] - box[0]) / 2, y0 + h + 10), label, font=self.fonts["small"], fill=TEXT_MUTED)
            nodata_x = x0 + w + 24
            draw.rectangle([nodata_x, y0, nodata_x + 16, y0 + h], fill=LAND_NODATA)
            draw.text((nodata_x + 24, y0 - 3), "no data", font=self.fonts["small"], fill=TEXT_MUTED)
        return bar

    def compose(self, rgb_map: np.ndarray, year: str, stats: list[tuple[str, str]]) -> bytes:
        frame = Image.new("RGB", (self.width, self.height), PANEL)
        frame.paste(Image.fromarray(rgb_map), (0, 0))
        bar = self._bar.copy()
        draw = ImageDraw.Draw(bar)
        box = draw.textbbox((0, 0), year, font=self.fonts["year"])
        draw.text((self.width - 32 - (box[2] - box[0]), 20), year, font=self.fonts["year"], fill=TEXT)
        x = self.width - 32 - (box[2] - box[0]) - 40
        for label, value in reversed(stats):
            vbox = draw.textbbox((0, 0), value, font=self.fonts["stat"])
            lbox = draw.textbbox((0, 0), label, font=self.fonts["small"])
            width = max(vbox[2] - vbox[0], lbox[2] - lbox[0])
            x -= width
            draw.text((x, 30), value, font=self.fonts["stat"], fill=TEXT)
            draw.text((x, 66), label, font=self.fonts["small"], fill=TEXT_MUTED)
            x -= 36
        frame.paste(bar, (0, self.canvas.height))
        return frame.tobytes()


class VideoWriter:
    """Streams RGB frames into ffmpeg (H.264, yuv420p, faststart) with a bitrate cap."""

    def __init__(self, path: Path, width: int, height: int, fps: int, max_bitrate_kbps: int):
        self.path = path
        self.process = subprocess.Popen(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "24",
                "-maxrate", f"{max_bitrate_kbps}k", "-bufsize", f"{2 * max_bitrate_kbps}k",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path),
            ],
            stdin=subprocess.PIPE,
        )

    def write(self, frame: bytes, repeat: int = 1) -> None:
        assert self.process.stdin is not None
        for _ in range(repeat):
            self.process.stdin.write(frame)

    def close(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()
        if self.process.wait() != 0:
            raise RuntimeError(f"ffmpeg failed for {self.path}")


# --------------------------------------------------------------------------------------------------------
# Maps


@dataclass
class MapSpec:
    key: str
    title: str
    subtitle: str
    values: Callable[[RunData, pl.DataFrame], pl.DataFrame] | None  # snapshot locations -> slug, value
    scale: Callable[[pl.DataFrame], Scale] | None


def _values_array(canvas: MapCanvas, frame: pl.DataFrame) -> np.ndarray:
    values = np.full(len(canvas.tags), np.nan, dtype=np.float64)
    if frame.is_empty():
        return values
    index = frame["slug"].replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).to_numpy()
    keep = index >= 0
    values[index[keep]] = frame["value"].to_numpy()[keep]
    return values


def _paint(canvas: MapCanvas, location_rgb: np.ndarray) -> np.ndarray:
    # colours that are not named locations (sea zones, lakes) and the black background are both water
    palette = np.vstack([location_rgb, np.array([SEA, SEA], dtype=np.uint8)])  # index -2 and -1
    return palette[canvas.index]


def _log_scale(frames: pl.DataFrame, factor: float = 1.0) -> Scale:
    """Log scale over the observed values; tick labels show value x factor (pops are thousands)."""
    values = frames["value"].drop_nulls()
    values = values.filter(values > 0)
    high = float(values.quantile(0.995)) if values.len() else 1.0
    low = max(high / 10_000, float(values.quantile(0.02)) if values.len() else 0.001)
    ticks = [10 ** e for e in range(math.floor(math.log10(low)), math.ceil(math.log10(high)) + 1)]
    ticks = [t for t in ticks if low <= t <= high] or [low, high]
    return Scale("log", low, high, _ramp(SEQUENTIAL), [(t, _format_number(t * factor)) for t in ticks])


def _linear_scale(low: float, high: float, labels: list[tuple[float, str]]) -> Scale:
    return Scale("linear", low, high, _ramp(SEQUENTIAL), labels)


def _population_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    return locs.select("slug", pl.col("total_population").alias("value"))


def _development_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    return locs.select("slug", pl.col("development").alias("value"))


def _unemployment_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    return locs.select(
        "slug",
        pl.when(pl.col("total_population") > 0)
        .then(pl.col("unemployed_total") / pl.col("total_population"))
        .otherwise(None)
        .alias("value"),
    )


def _building_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    snapshot = locs["snapshot_id"][0] if locs.height else None
    levels = run.building_levels.filter(pl.col("snapshot_id") == snapshot).select("slug", pl.col("levels").alias("value"))
    return locs.select("slug").join(levels, on="slug", how="left").with_columns(pl.col("value").fill_null(0.0))


def default_maps() -> list[MapSpec]:
    return [
        MapSpec("political", "Political map", "Owner of every location", None, None),
        MapSpec("population", "Population", "People per location (log scale)", _population_values,
                lambda f: _log_scale(f, 1000.0)),
        MapSpec("population_change", "Population change", "Change against the first save of the run", None,
                lambda f: Scale("diverging", -1.0, 1.0, _ramp(DIVERGING[:3] + (DIVERGING_DARK_MID,) + DIVERGING[4:]),
                                [(-1.0, "-100%"), (-0.5, "-50%"), (0.0, "0"), (0.5, "+50%"), (1.0, "+100%")])),
        MapSpec("development", "Development", "Development of every location", _development_values,
                lambda f: _linear_scale(0.0, max(1.0, float(f["value"].quantile(0.995) or 1.0)),
                                        [(v, f"{v:.0f}") for v in np.linspace(0, max(1.0, float(f["value"].quantile(0.995) or 1.0)), 5)])),
        MapSpec("buildings", "Building levels", "Sum of building levels per location (log scale)", _building_values,
                lambda f: _log_scale(f)),
        MapSpec("unemployment", "Unemployment", "Unemployed share of the population", _unemployment_values,
                lambda f: _linear_scale(0.0, 0.5, [(0.0, "0%"), (0.1, "10%"), (0.2, "20%"), (0.3, "30%"), (0.4, "40%"), (0.5, "50%+")])),
    ]


def _country_colours(repo: Path, project: Path, tags: list[str]) -> dict[str, tuple[int, int, int]]:
    from prosper_or_perish_constructor import savegame_maps as sm
    from prosper_or_perish_constructor.free_building_levels import resolve_parser_config

    config = resolve_parser_config(repo, project)
    load_order = repo / str(config.get("load_order") or "constructor.load_order.toml")
    profile = str(config.get("profile") or "constructor")
    colours = sm.load_country_color_map(load_order_path=load_order, profile=profile)
    out = {}
    for tag in tags:
        rgb = colours.get(tag) or sm._fallback_country_rgb(tag)
        out[tag] = tuple(int(c) for c in rgb)
    return out


def render_maps(run: RunData, canvas: MapCanvas, out: Path, *, repo: Path, project: Path, fps: int,
                specs: list[MapSpec] | None = None, log: Callable[[str], None] = print) -> list[dict[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    specs = specs or default_maps()
    snapshots = run.snapshots.to_dicts()
    by_snapshot = run.locations.partition_by("snapshot_id", as_dict=True)
    first = by_snapshot.get((snapshots[0]["snapshot_id"],), pl.DataFrame())
    baseline = first.select("slug", pl.col("total_population").alias("base"))
    world = run.locations.group_by("snapshot_id").agg(
        pl.col("total_population").sum().alias("population"),
        pl.col("country_tag").filter(pl.col("owner").is_not_null()).n_unique().alias("countries"),
    )
    world_by = {r["snapshot_id"]: r for r in world.to_dicts()}
    tags = sorted(t for t in run.locations["country_tag"].unique().to_list() if t)
    colours = _country_colours(repo, project, tags)
    results = []
    duration = len(snapshots) / fps
    max_kbps = int(MAX_VIDEO_BYTES * 8 / 1000 / (duration + 2.0))
    for spec in specs:
        started = time.perf_counter()
        frames: list[tuple[dict, pl.DataFrame]] = []
        for snap in snapshots:
            locs = by_snapshot.get((snap["snapshot_id"],), pl.DataFrame())
            if spec.key == "population_change":
                values = locs.select("slug", "total_population").join(baseline, on="slug", how="left").select(
                    "slug", pl.when(pl.col("base") > 0).then(pl.col("total_population") / pl.col("base") - 1).alias("value"))
            elif spec.values is not None:
                values = spec.values(run, locs)
            else:
                values = locs.select("slug", "country_tag", "owner")
            frames.append((snap, values))
        scale = None
        if spec.scale is not None:
            scale = spec.scale(pl.concat([f for _, f in frames if not f.is_empty()]).filter(pl.col("value").is_finite()))
        composer = FrameComposer(canvas, spec.title, spec.subtitle, scale)
        video = out / f"{spec.key}.mp4"
        writer = VideoWriter(video, composer.width, composer.height, fps, max_kbps)
        last = None
        for snap, values in frames:
            if spec.key == "political":
                location_rgb = np.full((len(canvas.tags), 3), UNOWNED, dtype=np.uint8)
                if not values.is_empty():
                    owned = values.filter(pl.col("owner").is_not_null() & pl.col("country_tag").is_not_null())
                    index = owned["slug"].replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).to_numpy()
                    rgb = np.array([colours.get(t, UNOWNED) for t in owned["country_tag"].to_list()], dtype=np.uint8).reshape(-1, 3)
                    keep = index >= 0
                    location_rgb[index[keep]] = rgb[keep]
            else:
                location_rgb = scale.colours(_values_array(canvas, values))
            stats = world_by.get(snap["snapshot_id"], {})
            frame = composer.compose(
                _paint(canvas, location_rgb),
                str(snap.get("year") or snap.get("date") or ""),
                [("population", _format_number(float(stats.get("population") or 0) * 1000)),
                 ("countries", str(stats.get("countries") or 0))],
            )
            writer.write(frame)
            last = frame
        if last is not None:
            writer.write(last, repeat=2 * fps)  # hold the last year
            Image.frombytes("RGB", (composer.width, composer.height), last).save(out / f"{spec.key}.png", optimize=True)
        writer.close()
        size = video.stat().st_size
        log(f"map {spec.key}: {len(frames)} frames, {size / 1e6:.1f} MB, {time.perf_counter() - started:.1f}s")
        results.append({"key": spec.key, "title": spec.title, "subtitle": spec.subtitle,
                        "video": f"maps/{spec.key}.mp4", "poster": f"maps/{spec.key}.png", "bytes": str(size)})
    return results


# --------------------------------------------------------------------------------------------------------
# Charts


def _chart_style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": 110, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#d9d9d6", "grid.linewidth": 0.6, "axes.edgecolor": "#8a8a86",
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left", "legend.frameon": False,
        "lines.linewidth": 2.0, "savefig.bbox": "tight", "savefig.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    })
    return plt


def _years(run: RunData) -> pl.DataFrame:
    return run.snapshots.select("snapshot_id", pl.col("year").cast(pl.Float64) + (pl.col("date_sort") % 10000) / 10000 * 0)


def render_charts(run: RunData, out: Path, log: Callable[[str], None] = print) -> list[dict[str, str]]:
    plt = _chart_style()
    out.mkdir(parents=True, exist_ok=True)
    years = run.snapshots.select("snapshot_id", pl.col("year").cast(pl.Float64).alias("x"))
    charts: list[dict[str, str]] = []

    def save(fig, key: str, title: str, caption: str) -> None:
        fig.savefig(out / f"{key}.png", dpi=120)
        plt.close(fig)
        charts.append({"key": key, "title": title, "caption": caption, "image": f"charts/{key}.png"})

    # World population by pop type (stacked, millions)
    pops = (
        run.locations.group_by("snapshot_id").agg([pl.col(f"population_{p}").sum() for p in POP_TYPES])
        .join(years, on="snapshot_id").sort("x")
    )
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.stackplot(pops["x"], *[pops[f"population_{p}"] / 1000 for p in POP_TYPES], labels=[p.title() for p in POP_TYPES],
                 colors=CATEGORICAL, edgecolor="#fcfcfb", linewidth=0.6)
    ax.set_ylabel("million people")
    ax.set_title("World population by pop type")
    ax.legend(loc="upper left", ncols=4, fontsize=9)
    save(fig, "population_by_type", "World population by pop type", "Population of every location, summed per save.")

    # Population by super region (top 8, rest as other)
    regions = (
        run.locations.group_by("snapshot_id", "super_region").agg(pl.col("total_population").sum())
        .join(years, on="snapshot_id")
    )
    last_snapshot = run.snapshots["snapshot_id"][-1]
    order = (
        regions.filter(pl.col("snapshot_id") == last_snapshot).sort("total_population", descending=True)["super_region"].to_list()
    )
    top = [r for r in order if r][:8]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for i, region in enumerate(top):
        series = regions.filter(pl.col("super_region") == region).sort("x")
        ax.plot(series["x"], series["total_population"] / 1000, color=CATEGORICAL[i], label=str(region).replace("_", " ").title())
    ax.set_ylabel("million people")
    ax.set_title("Population by super region")
    ax.legend(loc="upper left", ncols=4, fontsize=9)
    save(fig, "population_by_region", "Population by super region", "The eight most populous super regions at the end of the run.")

    # Employment: unemployed share of the population per pop type (world)
    jobs = (
        run.locations.group_by("snapshot_id").agg(
            pl.col("total_population").sum().alias("population"),
            pl.col("unemployed_total").sum().alias("unemployed"),
        ).join(years, on="snapshot_id").sort("x")
    )
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(jobs["x"], jobs["unemployed"] / jobs["population"] * 100, color=CATEGORICAL[0])
    ax.set_ylabel("% of population")
    ax.set_title("Unemployment")
    save(fig, "unemployment", "Unemployment", "Unemployed people as a share of the world population.")

    # Buildings by category (stacked levels, top 7 + other)
    categories = run.buildings_by_category.join(years, on="snapshot_id")
    order = (
        categories.filter(pl.col("snapshot_id") == last_snapshot).sort("levels", descending=True)["building_category"].to_list()
    )
    top_categories = order[:7]
    categories = categories.with_columns(
        pl.when(pl.col("building_category").is_in(top_categories)).then(pl.col("building_category")).otherwise(pl.lit("other")).alias("group")
    ).group_by("x", "group").agg(pl.col("levels").sum())
    groups = [*top_categories, "other"]
    wide = categories.pivot(on="group", index="x", values="levels").sort("x").fill_null(0)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.stackplot(wide["x"], *[wide[g] / 1000 if g in wide.columns else np.zeros(wide.height) for g in groups],
                 labels=[g.replace("_category", "").replace("_", " ").title() for g in groups],
                 colors=[*CATEGORICAL[:7], OTHER_GREY], edgecolor="#fcfcfb", linewidth=0.6)
    ax.set_ylabel("thousand levels")
    ax.set_title("Building levels by category")
    ax.legend(loc="upper left", ncols=4, fontsize=9)
    save(fig, "buildings_by_category", "Building levels by category", "All building levels, grouped by building category.")

    # Prices: price index against base for the eight goods with the most supply value at the end
    goods = run.goods.join(years, on="snapshot_id")
    top_goods = (
        goods.filter(pl.col("snapshot_id") == last_snapshot).sort("value", descending=True)["good_id"].to_list()[:8]
    )
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.axhline(1.0, color="#8a8a86", linewidth=1, linestyle="--")
    for i, good in enumerate(top_goods):
        series = goods.filter(pl.col("good_id") == good).sort("x")
        ax.plot(series["x"], series["price_index"], color=CATEGORICAL[i], label=good.replace("_", " ").title(), linewidth=1.6)
    ax.set_ylabel("price ÷ base (volume-weighted)")
    ax.set_title("Prices of the most produced goods")
    ax.legend(loc="upper left", ncols=4, fontsize=9)
    save(fig, "prices", "Prices of the most produced goods",
         "World price of each good as a multiple of its base price, weighted by traded volume; dashed line = base.")

    # Largest countries (population, top 8 at the end)
    countries = run.countries.join(years, on="snapshot_id")
    leaders = (
        countries.filter(pl.col("snapshot_id") == last_snapshot).sort("population", descending=True)
        .select("country_tag", "country_name").head(8).to_dicts()
    )
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for i, leader in enumerate(leaders):
        series = countries.filter(pl.col("country_tag") == leader["country_tag"]).sort("x")
        ax.plot(series["x"], series["population"] / 1000, color=CATEGORICAL[i], label=leader["country_name"] or leader["country_tag"])
    ax.set_ylabel("million people")
    ax.set_title("Largest countries")
    ax.legend(loc="upper left", ncols=4, fontsize=9)
    save(fig, "countries", "Largest countries", "The eight most populous countries at the end of the run.")
    log(f"charts: {len(charts)} written")
    return charts


# --------------------------------------------------------------------------------------------------------
# Page


def _summary(run: RunData) -> dict[str, object]:
    first, last = run.snapshots["snapshot_id"][0], run.snapshots["snapshot_id"][-1]
    world = run.locations.group_by("snapshot_id").agg(
        pl.col("total_population").sum().alias("population"),
        pl.col("country_tag").filter(pl.col("owner").is_not_null()).n_unique().alias("countries"),
        pl.col("owner").is_null().mean().alias("unowned_share"),
    )
    at = {r["snapshot_id"]: r for r in world.to_dicts()}
    levels = run.building_levels.group_by("snapshot_id").agg(pl.col("levels").sum())
    lv = {r["snapshot_id"]: r["levels"] for r in levels.to_dicts()}
    leaders = (
        run.countries.filter(pl.col("snapshot_id") == last).sort("population", descending=True).head(10)
        .select("country_name", "country_tag", "population", "owned_locations_count", "gold", "is_subject").to_dicts()
    )
    return {"first": at.get(first, {}), "last": at.get(last, {}), "levels_first": lv.get(first, 0), "levels_last": lv.get(last, 0),
            "leaders": leaders}


def write_page(run: RunData, out: Path, maps: list[dict[str, str]], charts: list[dict[str, str]]) -> Path:
    start, end = run.years
    summary = _summary(run)
    first, last = summary["first"], summary["last"]  # type: ignore[assignment]
    pop0, pop1 = float(first.get("population") or 0) * 1000, float(last.get("population") or 0) * 1000  # type: ignore[union-attr]
    change = (pop1 / pop0 - 1) * 100 if pop0 else 0.0
    esc = html.escape
    tiles = [
        ("Years", f"{start}–{end}", f"{run.snapshots.height} saves"),
        ("Population", _format_number(pop1), f"{change:+.1f}% since {start}"),
        ("Countries", str(last.get("countries", "–")), f"{first.get('countries', '–')} in {start}"),  # type: ignore[union-attr]
        ("Building levels", _format_number(float(summary["levels_last"] or 0)), f"{_format_number(float(summary['levels_first'] or 0))} in {start}"),
        ("Unowned land", f"{float(last.get('unowned_share') or 0) * 100:.0f}%", f"{float(first.get('unowned_share') or 0) * 100:.0f}% in {start}"),  # type: ignore[union-attr]
    ]
    leader_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(str(r['country_name'] or r['country_tag']))}{' <span class=muted>(subject)</span>' if r['is_subject'] else ''}</td>"
        f"<td class=num>{_format_number(float(r['population'] or 0) * 1000)}</td><td class=num>{r['owned_locations_count'] or 0}</td>"
        f"<td class=num>{_format_number(float(r['gold'] or 0))}</td></tr>"
        for i, r in enumerate(summary["leaders"], start=1)  # type: ignore[arg-type]
    )
    videos = "".join(
        f"<figure class=card><video controls loop muted playsinline preload=metadata poster='{esc(m['poster'])}'>"
        f"<source src='{esc(m['video'])}' type='video/mp4'></video>"
        f"<figcaption><b>{esc(m['title'])}</b> · {esc(m['subtitle'])} · <a href='{esc(m['video'])}' download>MP4</a></figcaption></figure>"
        for m in maps
    )
    chart_html = "".join(
        f"<figure class=card><img loading=lazy src='{esc(c['image'])}' alt='{esc(c['title'])}'>"
        f"<figcaption>{esc(c['caption'])}</figcaption></figure>"
        for c in charts
    )
    tile_html = "".join(f"<div class=tile><div class=label>{esc(a)}</div><div class=value>{esc(b)}</div><div class=sub>{esc(c)}</div></div>" for a, b, c in tiles)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(run.name)} · {start}–{end} · Prosper or Perish</title>
<meta property="og:title" content="{esc(run.name)} · {start}–{end}">
<meta property="og:description" content="Prosper or Perish observer run: {run.snapshots.height} saves, maps and progression charts.">
<meta property="og:image" content="maps/political.png">
<style>
:root{{--bg:#f6f6f4;--card:#fcfcfb;--ink:#1d1d1b;--muted:#6b6b67;--line:#e2e2de;--accent:#2a78d6}}
@media (prefers-color-scheme: dark){{:root{{--bg:#121418;--card:#1a1d22;--ink:#eceef0;--muted:#a0a6b0;--line:#2c3038;--accent:#6da7ec}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1240px;margin:0 auto;padding:28px 16px 48px}} h1{{margin:0 0 4px;font-size:28px}} h2{{margin:36px 0 12px;font-size:19px}}
.muted{{color:var(--muted)}} .tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:20px}}
.tile,.card{{background:var(--card);border:1px solid var(--line);border-radius:10px}} .tile{{padding:14px 16px}}
.tile .label{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}} .tile .value{{font-size:24px;font-weight:700;margin-top:2px}}
.tile .sub{{font-size:13px;color:var(--muted)}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:16px}}
@media (max-width:600px){{.grid{{grid-template-columns:1fr}}}} figure{{margin:0;overflow:hidden}} video,img{{display:block;width:100%;height:auto;background:#12161c}}
figcaption{{padding:10px 14px;font-size:13px;color:var(--muted)}} a{{color:var(--accent)}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th,td{{padding:8px 12px;border-bottom:1px solid var(--line);text-align:left}} th{{font-size:12px;text-transform:uppercase;color:var(--muted)}}
.num{{text-align:right;font-variant-numeric:tabular-nums}} footer{{margin-top:40px;font-size:12px;color:var(--muted)}}
</style></head><body><main>
<h1>{esc(run.name)}</h1>
<div class=muted>Prosper or Perish · observer run {start}–{end} · {run.snapshots.height} saves</div>
<div class=tiles>{tile_html}</div>
<h2>Maps</h2><div class=grid>{videos}</div>
<h2>Progression</h2><div class=grid>{chart_html}</div>
<h2>Largest countries in {end}</h2>
<table><thead><tr><th>#</th><th>Country</th><th class=num>Population</th><th class=num>Locations</th><th class=num>Gold</th></tr></thead><tbody>{leader_rows}</tbody></table>
<footer>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by <code>ppc report</code> from {run.snapshots.height} autosaves.</footer>
</main></body></html>
"""
    path = out / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def build_report(repo: Path, project: Path, *, dataset: Path, out_root: Path, playthrough: str | None = None,
                 width: int = 1920, fps: int = 6, log: Callable[[str], None] = print) -> Path:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required for the map videos (sudo apt install ffmpeg)")
    started = time.perf_counter()
    run = load_run(dataset, playthrough)
    log(f"run {run.name} ({run.playthrough_id}): {run.snapshots.height} saves {run.years[0]}-{run.years[1]}")
    out = out_root / run.playthrough_id
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    canvas = build_canvas(repo, project, width)
    maps = render_maps(run, canvas, out / "maps", repo=repo, project=project, fps=fps, log=log)
    charts = render_charts(run, out / "charts", log=log)
    page = write_page(run, out, maps, charts)
    (out / "report.json").write_text(json.dumps({"playthrough_id": run.playthrough_id, "name": run.name,
                                                 "years": run.years, "saves": run.snapshots.height,
                                                 "maps": maps, "charts": charts}, indent=2), encoding="utf-8")
    log(f"report written to {page} in {time.perf_counter() - started:.1f}s")
    return page


# --------------------------------------------------------------------------------------------------------
# Publishing: the preview site on GitHub Pages
#
# One public repository (default JanB1989/prosper-or-perish-preview), separate from the constructor and its
# released docs on main: the site root holds a work-in-progress copy of docs/ (`ppc publish-wip`), runs/
# the observer-run reports (`ppc report --publish`). Each command replaces only its own part and pushes one
# fresh commit, so the repository never accumulates history. Both are dry runs unless --yes.

DEFAULT_SITE_REPO = "JanB1989/prosper-or-perish-preview"
RELEASED_DOCS_URL = "https://janb1989.github.io/prosper-or-perish-constructor/"


@dataclass
class PublishPlan:
    site: Path
    remote: str
    url: str
    runs: list[dict[str, object]]
    added: str
    dropped: list[str]
    message: str = ""


def _git(site: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(site), *args], check=check, capture_output=True, text=True)


def _noindex(page: str) -> str:
    """Keep search engines off the preview (the pages stay reachable by link)."""
    meta = '<meta name="robots" content="noindex">'
    if 'name="robots"' in page:
        return page
    if not re.search(r"<head[\s>]", page, flags=re.IGNORECASE):
        return meta + page
    return re.sub(r"(<head(?:\s[^>]*)?>)", lambda m: m.group(1) + meta, page, count=1, flags=re.IGNORECASE)


def _clone_site(site_repo: str, work_root: Path, remote: str | None) -> tuple[Path, str, str]:
    owner, name = site_repo.split("/", 1)
    remote = remote or f"https://github.com/{site_repo}.git"
    url = f"https://{owner.lower()}.github.io/{name}/"
    site = work_root / name
    if site.exists():
        shutil.rmtree(site)
    site.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(["git", "clone", "--depth", "1", "--quiet", remote, str(site)], capture_output=True, text=True)
    if clone.returncode != 0:
        message = clone.stderr.lower()
        if "not found" in message or "does not exist" in message or "does not appear to be a git repository" in message:
            raise SystemExit(f"{site_repo} does not exist yet; create it with `ppc publish-wip --create-site` (public repository).")
        raise SystemExit(f"cannot clone {remote}: {clone.stderr.strip()}")
    return site, remote, url


def _published_runs(runs_dir: Path) -> list[dict[str, object]]:
    runs = []
    if runs_dir.is_dir():
        for folder in runs_dir.iterdir():
            meta = folder / "report.json"
            if meta.is_file():
                runs.append(json.loads(meta.read_text(encoding="utf-8")))
    return sorted(runs, key=lambda r: str(r.get("published_at", "")), reverse=True)


def _site_index(runs: list[dict[str, object]], title: str) -> str:
    esc = html.escape
    cards = "".join(
        f"<a class=card href='{esc(str(r['playthrough_id']))}/'>"
        f"<img loading=lazy src='{esc(str(r['playthrough_id']))}/maps/political.png' alt=''>"
        f"<div><b>{esc(str(r['name']))}</b><br><span>{r['years'][0]}–{r['years'][1]} · {r['saves']} saves</span></div></a>"
        for r in runs
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{esc(title)}</title><style>
:root{{--bg:#f6f6f4;--card:#fcfcfb;--ink:#1d1d1b;--muted:#6b6b67;--line:#e2e2de}}
@media (prefers-color-scheme: dark){{:root{{--bg:#121418;--card:#1a1d22;--ink:#eceef0;--muted:#a0a6b0;--line:#2c3038}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}} main{{max-width:1100px;margin:0 auto;padding:28px 16px}}
a{{color:inherit}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:20px}}
.card{{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;color:inherit;text-decoration:none}}
.card img{{display:block;width:100%;background:#12161c}} .card div{{padding:10px 14px}} .card span{{color:var(--muted);font-size:13px}}
</style></head><body><main><p><a href="../">← Work-in-progress docs</a></p><h1>{esc(title)}</h1>
<p style="color:var(--muted)">Observer runs of the Prosper or Perish mod for Europa Universalis V: map videos and progression charts, newest first.</p>
<div class=grid>{cards}</div></main></body></html>
"""


def _placeholder_root(site: Path) -> None:
    if not (site / "index.html").exists():
        (site / "index.html").write_text(
            '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><title>Prosper or Perish preview</title>'
            '<p>Work-in-progress docs are not published yet. <a href="runs/">Observer runs</a></p>',
            encoding="utf-8",
        )


def prepare_publish(
    report_dir: Path,
    *,
    site_repo: str,
    work_root: Path,
    keep: int = 5,
    remote: str | None = None,
    title: str = "Prosper or Perish runs",
) -> PublishPlan:
    """Stage a site checkout with this run added under runs/ (newest `keep` runs kept); nothing is pushed yet."""
    report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
    site, remote, url = _clone_site(site_repo, work_root, remote)
    runs_dir = site / "runs"
    runs_dir.mkdir(exist_ok=True)
    run_id = str(report["playthrough_id"])
    target = runs_dir / run_id
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(report_dir, target)
    report["published_at"] = datetime.now().isoformat(timespec="microseconds")
    (target / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # absolute preview image for link unfurls (Discord and other chat apps)
    page = target / "index.html"
    page.write_text(
        _noindex(
            page.read_text(encoding="utf-8").replace(
                'content="maps/political.png"', f'content="{url}runs/{run_id}/maps/political.png"'
            )
        ),
        encoding="utf-8",
    )
    # newest first; the run being published always leads
    runs = sorted(_published_runs(runs_dir), key=lambda r: str(r["playthrough_id"]) == run_id, reverse=True)
    dropped = [str(r["playthrough_id"]) for r in runs[keep:]]
    for old in dropped:
        shutil.rmtree(runs_dir / old, ignore_errors=True)
    runs = runs[:keep]
    (runs_dir / "index.html").write_text(_site_index(runs, title), encoding="utf-8")
    _placeholder_root(site)
    (site / ".nojekyll").write_text("", encoding="utf-8")
    message = f"Publish {len(runs)} run(s), newest {run_id}"
    return PublishPlan(site=site, remote=remote, url=url, runs=runs, added=run_id, dropped=dropped, message=message)


def _wip_banner(branch: str, commit: str, dirty: bool, published: str) -> str:
    esc = html.escape
    state = " with uncommitted changes" if dirty else ""
    return (
        '<div style="background:#fff7e3;border-bottom:1px solid #e6c35c;color:#3a2f10;padding:8px 16px;'
        'font:14px/1.5 system-ui,sans-serif">'
        f"<b>Work in progress</b>: {esc(branch)} @ {esc(commit)}{state}, published {esc(published)}. "
        f'Not a release: the released docs are at <a href="{RELEASED_DOCS_URL}">{RELEASED_DOCS_URL}</a>. '
        '<a href="runs/">Observer runs →</a></div>'
    )


def prepare_wip(
    docs_dir: Path,
    *,
    site_repo: str,
    work_root: Path,
    branch: str,
    commit: str,
    dirty: bool,
    remote: str | None = None,
) -> PublishPlan:
    """Stage a site checkout whose root is replaced by a copy of docs/ (runs/ kept); nothing is pushed yet."""
    site, remote, url = _clone_site(site_repo, work_root, remote)
    for entry in site.iterdir():
        if entry.name in {".git", "runs"}:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for entry in docs_dir.iterdir():
        if entry.name == "runs":
            continue
        target = site / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)
    for page in site.rglob("*.html"):
        if "runs" in page.relative_to(site).parts[:1] or ".git" in page.parts:
            continue
        text = page.read_text(encoding="utf-8", errors="surrogateescape")
        text = _noindex(text)
        if page == site / "index.html":
            published = datetime.now().strftime("%Y-%m-%d %H:%M")
            text = re.sub(
                r"(<body[^>]*>)", lambda m: m.group(1) + _wip_banner(branch, commit, dirty, published),
                text, count=1, flags=re.IGNORECASE,
            )
        page.write_text(text, encoding="utf-8", errors="surrogateescape")
    (site / "wip.json").write_text(
        json.dumps({"branch": branch, "commit": commit, "dirty": dirty, "published_at": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )
    (site / ".nojekyll").write_text("", encoding="utf-8")
    runs = _published_runs(site / "runs")
    message = f"Publish work-in-progress docs from {branch} @ {commit}{' (dirty)' if dirty else ''}"
    return PublishPlan(site=site, remote=remote, url=url, runs=runs, added="wip", dropped=[], message=message)


def push_publish(plan: PublishPlan) -> None:
    """One fresh commit (no history, so old videos and docs never pile up) force-pushed to main."""
    site = plan.site
    _git(site, "checkout", "--quiet", "--orphan", "publish")
    _git(site, "add", "--all")
    _git(
        site, "-c", "user.name=ppc report", "-c", "user.email=ppc-report@users.noreply.github.com",
        "commit", "--quiet", "-m", plan.message or f"Publish {plan.added}",
    )
    _git(site, "push", "--quiet", "--force", "origin", "publish:main")


def create_site_repo(
    site_repo: str, *, description: str = "Prosper or Perish work-in-progress preview: docs and observer-run reports"
) -> None:
    """Create the public GitHub repository with a placeholder page and enable Pages on main (gh CLI)."""
    subprocess.run(["gh", "repo", "create", site_repo, "--public", "--description", description], check=True)
    placeholder = Path(subprocess.run(["mktemp", "-d"], capture_output=True, text=True, check=True).stdout.strip())
    _git(placeholder, "init", "--quiet", "-b", "main")
    _placeholder_root(placeholder)
    _git(placeholder, "add", "--all")
    _git(
        placeholder, "-c", "user.name=ppc report", "-c", "user.email=ppc-report@users.noreply.github.com",
        "commit", "--quiet", "-m", "Initial page",
    )
    _git(placeholder, "remote", "add", "origin", f"https://github.com/{site_repo}.git")
    _git(placeholder, "push", "--quiet", "origin", "main")
    subprocess.run(
        ["gh", "api", "-X", "POST", f"repos/{site_repo}/pages", "-f", "source[branch]=main", "-f", "source[path]=/"],
        check=True, capture_output=True,
    )
