"""Shareable run report: map videos (MP4), interactive charts and tables, one static page per playthrough.

`ppc report` reads the multi-save dataset (`graphs/dataset`, built by `ppc savegame-notebooks build`) and
writes `graphs/report/<run>/`:

- `maps/*.mp4` - one H.264 video per map (political, population, population change, unemployment, development,
  institutions, building levels, building investment, trade between world regions, the largest trade routes, market trade
  balance, industry promotions), one frame per save, sized to stay
  under 10 MB so Discord and GitHub play it inline; `maps/*.png` - the last frame of each (a poster / thumbnail);
- `index.html` - the page: summary tiles, the videos and the interactive charts and tables of
  `run_report_charts` and `run_report_urban` (population, trade, prices, buildings, town rights and industry
  promotions, countries), drawn by Apache ECharts (loaded from
  jsDelivr) from the JSON embedded in the page. It only references files next to it and the chart library;
- `icons/<good>.png` - the goods icons (the built mod's, else the game's DDS, 40 px): goods appear as icons in
  heatmap axes, tables and the goods-group legends, with the name on hover;
- `goods.html` + `goods/` - the goods page (`run_report_goods`): for every good, save and world region what makes it
  and what uses it, by building and production method, as a flow chart and tables, linked from the report's nav.

Before reading the run, the report brings two derived parts of the dataset up to date: the building investment
table and the engine-only tables (trade routes, merchants, country economy) of snapshots ingested before the
dataset kept them, re-read from the saves that are still on disk.

Frames are painted with one NumPy lookup per frame (a location-index raster built once) and streamed to
ffmpeg, so a whole run renders in about a minute.
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
from typing import Any, Callable

import numpy as np
import polars as pl
from PIL import Image, ImageDraw, ImageFont

from prosper_or_perish_constructor.run_report_charts import (
    DUMMY_GOODS,
    GOODS_GROUPS,
    build_payload,
    goods_group_expr,
    land_region_expr,
    region_trade,
    region_trade_totals,
    speed_average,
    speed_segments,
    titleize,
    world_trade_share,
    xaxis,
)
from prosper_or_perish_constructor.run_report_urban import UrbanCatalog, industry_colours, industry_label, load_urban_catalog

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
class Labels:
    """Display names: the game's localization when the report has it, else the key titleized."""

    resolver: Any = None  # eu5gameparser NotebookLabelResolver
    goods: dict[str, str] = field(default_factory=dict)  # good_id -> name (the dataset's goods catalog)

    def _text(self, key: object) -> str | None:
        if key and self.resolver is not None and str(key) in self.resolver.localization:
            return self.resolver.label(str(key)) or None
        return None

    def country(self, tag: object, name: object = None) -> str:
        return self._text(name) or self._text(tag) or titleize(name or tag)

    def location(self, slug: object) -> str:
        return self._text(slug) or titleize(slug)

    def good(self, good_id: object) -> str:
        return self.goods.get(str(good_id)) or self._text(good_id) or titleize(good_id)


@dataclass
class RunData:
    playthrough_id: str
    name: str
    snapshots: pl.DataFrame  # snapshot_id, date, year, date_sort, mtime (save file time, seconds) (sorted)
    locations: pl.DataFrame  # per snapshot and location
    building_levels: pl.DataFrame  # snapshot_id, slug, levels
    buildings_by_category: pl.DataFrame  # snapshot_id, building_category, levels
    countries: pl.DataFrame
    # per snapshot, market and good (no mod bookkeeping goods): group, price, default_price, supply, demand,
    # production (supplied_Production), imports (supplied_Trade), exports (demanded_Trade), burgher_trade
    market_goods: pl.DataFrame = field(default_factory=pl.DataFrame)
    markets: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, market_id, center_slug
    # routes that ran (engine table trades, happened = yes): snapshot_id, from_market (exporter), to_market
    # (importer), good_id, amount (units per month), country_id (whose merchants)
    trades: pl.DataFrame = field(default_factory=pl.DataFrame)
    economy: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, country_id, income, expense
    labels: Labels = field(default_factory=Labels)
    # building investment (derived table building_investment); empty when the table is missing
    investment_by_location: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, slug, investment
    investment_by_category: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, investment_category, investment
    investment_by_country: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, country_tag, investment
    investment_basis: str = "list"  # "location": at the location's prices (investment_local), "list": list price
    # engine table location_institutions, institutions at 100 % spread: snapshot_id, institution, population (thousands
    # living where it is present); locations then carry `institutions` (count, null in snapshots without the table)
    institutions: pl.DataFrame = field(default_factory=pl.DataFrame)
    good_icons: dict[str, str] = field(default_factory=dict)  # good_id -> page-relative PNG (write_good_icons)
    # engine tables town_rights and industry_promotions (empty for snapshots ingested before the dataset kept them)
    town_rights: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, town_right_id, location_id, type
    promotions: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, promotion_id, country_id, area, type
    urban_saves: list[str] = field(default_factory=list)  # snapshots that carry those tables
    # gold per month each location makes of each good (buildings + RGO, nominal output x base price); only loaded
    # when the run has town rights or promotions
    production: pl.DataFrame = field(default_factory=pl.DataFrame)  # snapshot_id, location_id, good_id, value
    urban: UrbanCatalog = field(default_factory=UrbanCatalog)  # town right and industry type definitions

    @property
    def investment_prices(self) -> str:
        """How the investment is priced, for captions."""
        if self.investment_basis == "location":
            return "at the location's prices (list price divided by max(0.5, 1 + the location's building efficiency))"
        return "at list price"

    @property
    def years(self) -> tuple[int, int]:
        years = self.snapshots["year"].drop_nulls()
        return int(years.min()), int(years.max())


def _scan(dataset: Path, table: str, playthrough: str) -> pl.LazyFrame:
    scan = _scan_optional(dataset, table, playthrough)
    if scan is None:
        raise SystemExit(f"no {table} snapshots for playthrough {playthrough} in {dataset}")
    return scan


def _scan_optional(dataset: Path, table: str, playthrough: str) -> pl.LazyFrame | None:
    root = dataset / "tables" / table / f"playthrough_id={playthrough}"
    files = sorted(root.glob("*.parquet"))
    if not files:
        return None
    return pl.scan_parquet([str(f) for f in files], missing_columns="insert", extra_columns="ignore")


def latest_playthrough(dataset: Path) -> str:
    manifest = pl.read_parquet(dataset / "manifest.parquet")
    latest = manifest.sort("mtime").row(-1, named=True)
    return str(latest["playthrough_id"])


def load_run(dataset: Path, playthrough: str | None = None, labels: Labels | None = None) -> RunData:
    playthrough = playthrough or latest_playthrough(dataset)
    manifest = pl.read_parquet(dataset / "manifest.parquet").filter(pl.col("playthrough_id") == playthrough)
    snapshots = (
        manifest.select("snapshot_id", "date", "year", "date_sort", "mtime", "playthrough_name")
        .unique("snapshot_id")
        .sort("date_sort")
    )
    # the game writes playthrough_name only for some starts (e.g. "England #7558ddce"); else the id's first block
    name = next((n for n in snapshots["playthrough_name"].to_list() if n), f"Run {playthrough[:8]}")
    # a reloaded older save is a branch `<id>_r<yyyy_mm_dd>` of its run (eu5gameparser dataset ingest)
    reload = re.search(r"_r(\d{4})_\d{2}_\d{2}(?:_\d+)?$", playthrough)
    if reload:
        name = f"{name} (reloaded {reload.group(1)})"
    wanted = snapshots["snapshot_id"].to_list()
    loc_columns = [
        "snapshot_id", "location_id", "slug", "country_tag", "owner", "owner_country_id", "market_id", "area", "rank",
        "super_region", "macro_region", "development", "possible_tax", "total_population", "unemployed_total", "unemployed_peasants", *[f"population_{p}" for p in POP_TYPES],
    ]
    locations = _scan(dataset, "locations", playthrough).select(loc_columns).filter(pl.col("snapshot_id").is_in(wanted)).collect()
    locations, institutions = _institutions(dataset, playthrough, wanted, locations)
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
        .select("snapshot_id", "country_id", "country_tag", "country_name", "population", "owned_locations_count", "gold",
                "is_subject", "overlord_tag", "overlord_name")
        .collect()
    )
    # the engine leaves countries.population empty: fall back to the population of the owned locations (thousands);
    # landless countries (pretenders, exiles) can share a tag with a landed one, so they get none
    owned = locations.filter(pl.col("country_tag").is_not_null()).group_by("snapshot_id", "country_tag").agg(
        pl.col("total_population").sum().alias("location_population"))
    countries = (
        countries.join(owned, on=["snapshot_id", "country_tag"], how="left")
        .with_columns(
            pl.coalesce(
                pl.col("population").cast(pl.Float64),
                pl.when(pl.col("owned_locations_count").fill_null(0) > 0).then(pl.col("location_population")),
            ).alias("population")
        )
        .drop("location_population")
    )
    market_goods = (
        _scan(dataset, "market_goods", playthrough)
        .filter(pl.col("snapshot_id").is_in(wanted) & ~pl.col("good_id").is_in(sorted(DUMMY_GOODS))
                & (pl.col("default_price") > 0))
        .select(
            "snapshot_id", "market_id", "good_id", goods_group_expr().alias("group"), "price", "default_price",
            pl.col("supply").fill_null(0.0), pl.col("demand").fill_null(0.0),
            pl.col("supplied_Production").fill_null(0.0).alias("production"),
            pl.col("supplied_Trade").fill_null(0.0).alias("imports"),
            pl.col("demanded_Trade").fill_null(0.0).alias("exports"),
            pl.col("demanded_BurgherTrades").fill_null(0.0).alias("burgher_trade"),
        )
        .collect()
    )
    markets = (
        _scan(dataset, "markets", playthrough)
        .filter(pl.col("snapshot_id").is_in(wanted))
        .select("snapshot_id", "market_id", pl.col("market_center_slug").alias("center_slug"))
        .collect()
    )
    trades_scan = _scan_optional(dataset, "trades", playthrough)
    trades = (
        trades_scan.filter(pl.col("snapshot_id").is_in(wanted) & (pl.col("happened") == "yes")
                           & ~pl.col("good_id").is_in(sorted(DUMMY_GOODS)))
        .select("snapshot_id", "from_market", "to_market", "good_id", pl.col("cached").fill_null(0.0).alias("amount"), "country_id")
        .collect()
        if trades_scan is not None else pl.DataFrame()
    )
    economy_scan = _scan_optional(dataset, "country_ai", playthrough)
    economy = (
        economy_scan.filter(pl.col("snapshot_id").is_in(wanted)).select("snapshot_id", "country_id", "income", "expense").collect()
        if economy_scan is not None else pl.DataFrame()
    )
    labels = labels or Labels()
    goods_scan = _scan_optional(dataset, "goods_catalog", playthrough)
    if goods_scan is not None:
        names = goods_scan.select("good_id", "good_name").unique("good_id").collect()
        labels.goods = {**{g: n for g, n in names.iter_rows() if n}, **labels.goods}
    run = RunData(playthrough, str(name), snapshots, locations, building_levels, buildings_by_category, countries,
                  market_goods, markets, trades, economy, labels, institutions=institutions)
    _load_investment(run, dataset, wanted)
    _load_urban(run, dataset, wanted)
    return run


def _load_urban(run: RunData, dataset: Path, wanted: list[str]) -> None:
    """Town rights, industry promotions and, for their fit, what every location makes."""
    have: set[str] = set()
    for table in ("town_rights", "industry_promotions"):
        root = dataset / "tables" / table / f"playthrough_id={run.playthrough_id}"
        have |= {f.stem for f in root.glob("*.parquet")}
    run.urban_saves = [s for s in wanted if s in have]
    rights = _scan_optional(dataset, "town_rights", run.playthrough_id)
    if rights is not None:
        run.town_rights = rights.filter(pl.col("snapshot_id").is_in(wanted)).select(
            "snapshot_id", "town_right_id", "location_id", "type").collect()
    promotions = _scan_optional(dataset, "industry_promotions", run.playthrough_id)
    if promotions is not None:
        run.promotions = promotions.filter(pl.col("snapshot_id").is_in(wanted)).select(
            "snapshot_id", pl.col("industry_promotion_id").alias("promotion_id"), "country_id", "area", "type").collect()
    if (run.town_rights.is_empty() and run.promotions.is_empty()) or run.market_goods.is_empty():
        return
    parts = []
    for table in ("production_method_good_flows", "rgo_flows"):
        scan = _scan_optional(dataset, table, run.playthrough_id)
        if scan is not None:
            parts.append(scan.filter(pl.col("snapshot_id").is_in(wanted) & (pl.col("direction") == "output")
                                     & pl.col("location_id").is_not_null())
                         .select("snapshot_id", "location_id", "good_id", pl.col("nominal_amount").fill_null(0.0).alias("amount")))
    if not parts:
        return
    prices = run.market_goods.group_by("snapshot_id", "good_id").agg(pl.col("default_price").first())
    run.production = (
        pl.concat(parts).group_by("snapshot_id", "location_id", "good_id").agg(pl.col("amount").sum()).collect()
        .join(prices, on=["snapshot_id", "good_id"], how="inner")  # base price; drops the mod's bookkeeping goods
        .select("snapshot_id", "location_id", "good_id", (pl.col("amount") * pl.col("default_price")).alias("value"))
        .filter(pl.col("value") > 0)
    )


INSTITUTION_PRESENT = 100.0  # location spread at which the game counts the institution as present


def _institutions(dataset: Path, playthrough: str, wanted: list[str],
                  locations: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Institutions present per location (engine table location_institutions, spread >= 100): adds the count
    `institutions` to the locations and returns the population living where each institution is present."""
    scan = _scan_optional(dataset, "location_institutions", playthrough)
    if scan is None:
        return locations.with_columns(pl.lit(None, dtype=pl.Float64).alias("institutions")), pl.DataFrame()
    present = (
        scan.filter(pl.col("snapshot_id").is_in(wanted) & (pl.col("progress") >= INSTITUTION_PRESENT))
        .select("snapshot_id", "location_id", "institution")
        .collect()
    )
    have = scan.select("snapshot_id").unique().collect()["snapshot_id"]
    counts = present.group_by("snapshot_id", "location_id").agg(pl.len().cast(pl.Float64).alias("institutions"))
    locations = locations.join(counts, on=["snapshot_id", "location_id"], how="left").with_columns(
        pl.when(pl.col("snapshot_id").is_in(have.implode())).then(pl.col("institutions").fill_null(0.0)).alias("institutions"))
    population = (
        present.join(locations.select("snapshot_id", "location_id", "total_population"), on=["snapshot_id", "location_id"])
        .group_by("snapshot_id", "institution").agg(pl.col("total_population").sum().alias("population"))
    )
    return locations, population


def _load_investment(run: RunData, dataset: Path, wanted: list[str]) -> None:
    root = dataset / "tables" / "building_investment" / f"playthrough_id={run.playthrough_id}"
    files = sorted(root.glob("*.parquet"))
    if not files:
        return
    frame = (
        pl.scan_parquet([str(f) for f in files], missing_columns="insert", extra_columns="ignore")
        .select("snapshot_id", "location_slug", "country_tag", "investment_category", "investment", "investment_local",
                "level")
        .filter(pl.col("snapshot_id").is_in(wanted))
        .collect()
    )
    # gold at the location's prices when every snapshot has it (building_investment.LocationCostModel), else list price
    if frame.height and frame["investment_local"].null_count() == 0:
        frame = frame.with_columns(pl.col("investment_local").alias("investment"))
        run.investment_basis = "location"
    frame = frame.drop("investment_local")
    run.investment_by_location = frame.group_by("snapshot_id", "location_slug").agg(pl.col("investment").sum()).rename(
        {"location_slug": "slug"})
    run.investment_by_category = frame.group_by("snapshot_id", "investment_category").agg(pl.col("investment").sum())
    run.investment_by_country = frame.filter(pl.col("country_tag").is_not_null()).group_by("snapshot_id", "country_tag").agg(
        pl.col("investment").sum())


def load_labels(repo: Path, project: Path) -> Labels:
    """Localized country, location and good names of the constructor's parser profile."""
    from eu5gameparser.savegame.notebook_labels import NotebookLabelResolver

    from prosper_or_perish_constructor.free_building_levels import resolve_parser_config

    config = resolve_parser_config(repo, project)
    load_order = repo / str(config.get("load_order") or "constructor.load_order.toml")
    profile = str(config.get("profile") or "constructor")
    return Labels(NotebookLabelResolver.from_profile(profile=profile, load_order_path=load_order))


GOOD_ICON_DIR = Path("main_menu/gfx/interface/icons/trade_goods")
GOOD_ICON_PX = 40  # drawn at 18 px: sharp on high-density screens, about 2 KB each


def good_icon_sources(repo: Path, project: Path) -> list[Path]:
    """Folders with icon_goods_<good>.dds, first match wins: the built mod (its own goods), then the game."""
    import tomllib

    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    roots = []
    mod_root = tomllib.loads(project.read_text(encoding="utf-8")).get("project", {}).get("mod_root")
    if isinstance(mod_root, str):
        roots.append((Path(mod_root) if Path(mod_root).is_absolute() else repo / mod_root) / GOOD_ICON_DIR)
    try:
        roots.append(vanilla_root(repo, project) / "game" / GOOD_ICON_DIR)
    except Exception:  # no load order: the report falls back to good names
        pass
    return roots


def write_good_icons(goods: list[str], sources: list[Path], out: Path, log: Callable[[str], None] = print) -> dict[str, str]:
    """icons/<good>.png under out for every good with a game icon; good_id -> page-relative path."""
    found: dict[str, str] = {}
    missing = []
    for good in sorted(set(goods)):
        dds = next((root / f"icon_goods_{good}.dds" for root in sources if (root / f"icon_goods_{good}.dds").is_file()), None)
        if dds is None:
            missing.append(good)
            continue
        try:
            image = Image.open(dds).convert("RGBA").resize((GOOD_ICON_PX, GOOD_ICON_PX), Image.Resampling.LANCZOS)
        except Exception:  # an undecodable DDS: the page shows the name instead
            missing.append(good)
            continue
        (out / "icons").mkdir(parents=True, exist_ok=True)
        image.save(out / "icons" / f"{good}.png", optimize=True)
        found[good] = f"icons/{good}.png"
    log(f"goods icons: {len(found)}" + (f", no icon for {', '.join(missing)}" if missing else ""))
    return found


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
    kind: str  # "log", "linear", "diverging", "symlog" (diverging, log of |value|; low = linear threshold)
    low: float
    high: float
    lut: np.ndarray
    ticks: list[tuple[float, str]]

    def position(self, values: np.ndarray) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            if self.kind == "log":
                v = np.log10(np.maximum(values, self.low))
                t = (v - math.log10(self.low)) / (math.log10(self.high) - math.log10(self.low))
            elif self.kind == "symlog":
                span = math.log10(1 + self.high / self.low)
                v = np.sign(values) * np.log10(1 + np.abs(values) / self.low) / span
                t = 0.5 + 0.5 * np.clip(v, -1.0, 1.0)
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

    def __init__(self, canvas: MapCanvas, title: str, subtitle: str, scale: Scale | None,
                 legend: list[tuple[str, tuple[int, int, int]]] | None = None, nodata_label: str = "no data"):
        self.canvas = canvas
        self.legend = legend or []
        self.nodata_label = nodata_label
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
            draw.text((nodata_x + 24, y0 - 3), self.nodata_label, font=self.fonts["small"], fill=TEXT_MUTED)
        start = self.width // 2 - 480
        x, y = start, 30 if len(self.legend) > 6 else 42
        for label, rgb in self.legend:
            box = draw.textbbox((0, 0), label, font=self.fonts["small"])
            step = 30 + (box[2] - box[0]) + 28
            if x + step > self.width - 470 and x > start:  # wrap before the year and key figures
                x, y = start, y + 28
            draw.rounded_rectangle([x, y + 3, x + 22, y + 13], radius=3, fill=rgb)
            draw.text((x + 30, y - 2), label, font=self.fonts["small"], fill=TEXT_MUTED)
            x += step
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


def _symlog_scale(frames: pl.DataFrame) -> Scale:
    """Diverging scale on log10 of the absolute change, the same length both ways: from +-threshold (a tenth of a
    typical change, linear below it) to the largest change (99.5th percentile of |value|)."""
    values = frames["value"].drop_nulls().abs()
    values = values.filter(values > 0)
    high = float(values.quantile(0.995)) if values.len() else 1.0
    low = max(high / 100_000, float(values.quantile(0.5)) / 10 if values.len() else 1.0)
    decades = [10 ** e for e in range(math.ceil(math.log10(low)), math.floor(math.log10(high)) + 1)]
    ticks = [(0.0, "0")] + [(sign * d, ("+" if sign > 0 else "-") + _format_number(d)) for d in (decades if len(decades) <= 3 else decades[1::2])
                            for sign in (-1, 1)]
    return Scale("symlog", low, high, _ramp(DIVERGING[:3] + (DIVERGING_DARK_MID,) + DIVERGING[4:]), ticks)


def _linear_scale(low: float, high: float, labels: list[tuple[float, str]]) -> Scale:
    return Scale("linear", low, high, _ramp(SEQUENTIAL), labels)


def _population_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    return locs.select("slug", pl.col("total_population").alias("value"))


def _development_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    return locs.select("slug", pl.col("development").alias("value"))


def _institution_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    return locs.select("slug", pl.col("institutions").alias("value"))


def _count_scale(frames: pl.DataFrame) -> Scale:
    high = max(1.0, float(frames["value"].max() or 1.0))
    step = max(1, math.ceil(high / 6))
    return _linear_scale(0.0, high, [(float(v), str(v)) for v in range(0, int(high) + 1, step)])


def _unemployment_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    # subsistence peasants (peasants without a job) as a share of all people
    return locs.select(
        "slug",
        pl.when(pl.col("total_population") > 0)
        .then(pl.col("unemployed_peasants").fill_null(0.0) / pl.col("total_population"))
        .otherwise(None)
        .alias("value"),
    )


def _building_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    snapshot = locs["snapshot_id"][0] if locs.height else None
    levels = run.building_levels.filter(pl.col("snapshot_id") == snapshot).select("slug", pl.col("levels").alias("value"))
    return locs.select("slug").join(levels, on="slug", how="left").with_columns(pl.col("value").fill_null(0.0))


def _investment_values(run: RunData, locs: pl.DataFrame) -> pl.DataFrame:
    snapshot = locs["snapshot_id"][0] if locs.height else None
    if run.investment_by_location.is_empty():
        return locs.select("slug", pl.lit(None, dtype=pl.Float64).alias("value"))
    gold = run.investment_by_location.filter(pl.col("snapshot_id") == snapshot).select(
        "slug", pl.col("investment").alias("value"))
    return locs.select("slug").join(gold, on="slug", how="left").with_columns(pl.col("value").fill_null(0.0))


def default_maps() -> list[MapSpec]:
    return [
        MapSpec("political", "Political map", "Owner of every location", None, None),
        MapSpec("population", "Population", "People per location (log scale)", _population_values,
                lambda f: _log_scale(f, 1000.0)),
        MapSpec("population_change", "Population change", "Change against the first save of the run", None,
                lambda f: Scale("diverging", -1.0, 1.0, _ramp(DIVERGING[:3] + (DIVERGING_DARK_MID,) + DIVERGING[4:]),
                                [(-1.0, "-100%"), (-0.5, "-50%"), (0.0, "0"), (0.5, "+50%"), (1.0, "+100%")])),
        MapSpec("unemployment", "Unemployment", "Subsistence peasants as a share of the population", _unemployment_values,
                lambda f: _linear_scale(0.0, 1.0, [(0.0, "0%"), (0.25, "25%"), (0.5, "50%"), (0.75, "75%"), (1.0, "100%")])),
        MapSpec("development", "Development", "Development of every location", _development_values,
                lambda f: _linear_scale(0.0, max(1.0, float(f["value"].quantile(0.995) or 1.0)),
                                        [(v, f"{v:.0f}") for v in np.linspace(0, max(1.0, float(f["value"].quantile(0.995) or 1.0)), 5)])),
        MapSpec("institutions", "Institutions", "Institutions present in every location (spread at 100 %)",
                _institution_values, _count_scale),
        MapSpec("buildings", "Building levels", "Sum of building levels per location (log scale)", _building_values,
                lambda f: _log_scale(f)),
        MapSpec("investment", "Building investment", "Gold the buildings of a location cost to build (log scale)",
                _investment_values, lambda f: _log_scale(f)),
        MapSpec("investment_change", "Building investment change",
                "Gold built or lost per location since the first save (log scale both ways)", None, _symlog_scale),
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
    if run.investment_by_location.is_empty():
        specs = [s for s in specs if s.key not in {"investment", "investment_change"}]
    if run.institutions.is_empty():
        specs = [s for s in specs if s.key != "institutions"]
    snapshots = run.snapshots.to_dicts()
    by_snapshot = run.locations.partition_by("snapshot_id", as_dict=True)
    first = by_snapshot.get((snapshots[0]["snapshot_id"],), pl.DataFrame())
    baseline = first.select("slug", pl.col("total_population").alias("base"))
    investment_base = (
        run.investment_by_location.filter(pl.col("snapshot_id") == snapshots[0]["snapshot_id"]).select(
            "slug", pl.col("investment").alias("base"))
        if not run.investment_by_location.is_empty() else pl.DataFrame(schema={"slug": pl.String, "base": pl.Float64})
    )
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
            elif spec.key == "investment_change":
                # absolute change in gold per location; no data where the location never had a building
                values = _investment_values(run, locs).join(investment_base, on="slug", how="left").select(
                    "slug",
                    pl.when((pl.col("base").fill_null(0.0) > 0) | (pl.col("value").fill_null(0.0) > 0))
                    .then(pl.col("value").fill_null(0.0) - pl.col("base").fill_null(0.0))
                    .alias("value"))
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
# Industry promotions map

PROMOTION_VIDEOS = ("industry_promotions",)
PROMOTION_SHORT = {"paper_goods": "Paper"}  # legend names that would not fit


def render_promotion_map(run: RunData, canvas: MapCanvas, out: Path, *, fps: int,
                         log: Callable[[str], None] = print) -> list[dict[str, str]]:
    """One video: every location coloured by the industry its owner promotes in its area."""
    if run.promotions.is_empty() or not {"owner_country_id", "area"} <= set(run.locations.columns):
        return []
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    colours = {k: _hex(c) for k, c in industry_colours(run).items()}
    several = _hex("#d8d8d4")
    present = set(run.promotions["type"].to_list())
    legend = [(PROMOTION_SHORT.get(k) or industry_label(run, k), rgb) for k, rgb in colours.items() if k in present]
    composer = FrameComposer(canvas, "Industry promotions", "Promoted by the owner, per area", None,
                             legend=legend + [("Several", several)])
    duration = run.snapshots.height / fps
    video = out / "industry_promotions.mp4"
    writer = VideoWriter(video, composer.width, composer.height, fps, int(MAX_VIDEO_BYTES * 8 / 1000 / (duration + 2.0)))
    by_snapshot = run.locations.partition_by("snapshot_id", as_dict=True)
    promotions = run.promotions.group_by("snapshot_id", "country_id", "area").agg(pl.col("type").unique())
    by_promotion = promotions.partition_by("snapshot_id", as_dict=True)
    last = None
    for snap in run.snapshots.to_dicts():
        locs = by_snapshot.get((snap["snapshot_id"],), pl.DataFrame())
        location_rgb = np.full((len(canvas.tags), 3), NO_MARKET_LAND, dtype=np.uint8)
        promoted = by_promotion.get((snap["snapshot_id"],), pl.DataFrame())
        count = countries = 0
        if not locs.is_empty():
            owned = locs.filter(pl.col("owner_country_id").is_not_null())
            index = owned["slug"].replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).to_numpy()
            location_rgb[index[index >= 0]] = TRADE_LAND
            if not promoted.is_empty():
                count = int(promoted["type"].list.len().sum())
                countries = promoted["country_id"].n_unique()
                hit = owned.join(promoted.rename({"country_id": "owner_country_id"}), on=["owner_country_id", "area"], how="inner")
                index = hit["slug"].replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).to_numpy()
                rgb = np.array([colours.get(t[0], several) if len(t) == 1 else several for t in hit["type"].to_list()],
                               dtype=np.uint8).reshape(-1, 3)
                keep = index >= 0
                location_rgb[index[keep]] = rgb[keep]
        frame = composer.compose(_paint(canvas, location_rgb), str(snap.get("year") or snap.get("date") or ""),
                                 [("promotions", str(count)), ("countries promoting", str(countries))])
        writer.write(frame)
        last = frame
    if last is not None:
        writer.write(last, repeat=2 * fps)
        Image.frombytes("RGB", (composer.width, composer.height), last).save(out / "industry_promotions.png", optimize=True)
    writer.close()
    size = video.stat().st_size
    log(f"map industry_promotions: {run.snapshots.height} frames, {size / 1e6:.1f} MB, {time.perf_counter() - started:.1f}s")
    return [{"key": "industry_promotions", "title": "Industry promotions",
             "subtitle": "The industry each location's owner promotes in its area (dark: none, light grey: several)",
             "video": "maps/industry_promotions.mp4", "poster": "maps/industry_promotions.png", "bytes": str(size)}]


# --------------------------------------------------------------------------------------------------------
# Trade maps

TRADE_LAND = (46, 52, 62)
NO_MARKET_LAND = (34, 38, 46)
MARKET_BORDER = (98, 106, 120)
BALANCE_BORDER = (16, 20, 26)
REGION_BORDER = (12, 16, 22)
TRADE_VIDEOS = ("trade_regions", "trade_routes", "trade_balance")
TOP_ROUTES = 40  # market pairs drawn per frame in the routes video
TOP_REGION_FLOWS = 18  # region pairs drawn per frame in the regions video


def _location_centroids(canvas: MapCanvas) -> np.ndarray:
    """(n, 2) pixel centre (x, y) of every location of the canvas; NaN for locations without pixels."""
    flat = canvas.index.reshape(-1)
    pixels = np.nonzero(flat >= 0)[0]
    location = flat[pixels]
    n = len(canvas.tags)
    count = np.bincount(location, minlength=n).astype(np.float64)
    xs = np.bincount(location, weights=(pixels % canvas.width).astype(np.float64), minlength=n)
    ys = np.bincount(location, weights=(pixels // canvas.width).astype(np.float64), minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.stack([xs / count, ys / count], axis=1)


def _market_raster(canvas: MapCanvas, locs: pl.DataFrame) -> np.ndarray:
    """H x W market id per pixel: the location's market, -1 land without a market, -2 water."""
    market_of = np.full(len(canvas.tags), -1, dtype=np.int64)
    if not locs.is_empty():
        frame = locs.filter(pl.col("market_id").is_not_null()).select("slug", "market_id")
        index = frame["slug"].replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).to_numpy()
        keep = index >= 0
        market_of[index[keep]] = frame["market_id"].to_numpy()[keep]
    return np.where(canvas.index >= 0, market_of[np.maximum(canvas.index, 0)], np.where(canvas.index == -1, -2, -1))


def _market_borders(raster: np.ndarray) -> np.ndarray:
    mask = np.zeros(raster.shape, dtype=bool)
    edge = (raster[:, 1:] != raster[:, :-1]) & (raster[:, 1:] >= 0) & (raster[:, :-1] >= 0)
    mask[:, 1:] |= edge
    edge = (raster[1:, :] != raster[:-1, :]) & (raster[1:, :] >= 0) & (raster[:-1, :] >= 0)
    mask[1:, :] |= edge
    return mask


def _arc(x0: float, y0: float, x1: float, y1: float, r0: float, r1: float, bend: float = 0.2, steps: int = 24) -> list[tuple[float, float]]:
    """Quadratic curve from the exporter to the importer, bent to one side of the direction of travel (so the two
    directions between a pair of markets never overlap), cut where it enters the two market dots."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    cx, cy = (x0 + x1) / 2 + dy * bend, (y0 + y1) / 2 - dx * bend
    t0 = min(0.4, (r0 + 1) / (length * 1.1))
    t1 = max(0.6, 1 - (r1 + 1) / (length * 1.1))
    out = []
    for i in range(steps + 1):
        t = t0 + (t1 - t0) * i / steps
        out.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1))
    return out


def _draw_trade(base: np.ndarray, routes: list[tuple], dots: list[tuple[float, float, float]], scale: int = 2) -> np.ndarray:
    """Routes (x0, y0, r0, x1, y1, r1, width, rgba), smallest first, and market dots (x, y, r) over the base map;
    drawn at `scale` x the size and scaled down for smooth lines."""
    h, w = base.shape[:2]
    layer = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    full = w * scale
    for x0, y0, r0, x1, y1, r1, width, rgba in routes:
        x0, y0, x1, y1, r0, r1 = (v * scale for v in (x0, y0, x1, y1, r0, r1))
        shifts = [0.0]
        if abs(x1 - x0) > full / 2:  # the short way runs over the map edge: draw it from both edges
            step = -full if x1 > x0 else full
            x1 += step
            shifts = [0.0, -step]
        for shift in shifts:
            points = _arc(x0 + shift, y0, x1 + shift, y1, r0, r1)
            draw.line(points, fill=rgba, width=max(1, round(width * scale)), joint="curve")
            (ax, ay), (bx, by) = points[-2], points[-1]
            norm = math.hypot(bx - ax, by - ay) or 1.0
            ux, uy = (bx - ax) / norm, (by - ay) / norm
            head, half = 3.5 * scale + 1.8 * width * scale, 2.2 * scale + 1.1 * width * scale
            draw.polygon([(bx, by), (bx - ux * head - uy * half, by - uy * head + ux * half),
                          (bx - ux * head + uy * half, by - uy * head - ux * half)], fill=rgba)
    for x, y, r in dots:
        x, y, r = x * scale, y * scale, r * scale
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(236, 238, 240, 235), outline=(12, 16, 22, 255), width=scale)
    layer = layer.resize((w, h), Image.Resampling.LANCZOS)
    out = Image.fromarray(base).convert("RGBA")
    out.alpha_composite(layer)
    return np.asarray(out.convert("RGB"))


def _region_layout(canvas: MapCanvas, run: RunData) -> tuple[np.ndarray, list[str], dict[str, tuple[float, float]]]:
    """H x W index into the sorted world regions per pixel (-1 none), the regions, and each region's centre: the
    pixel mean of its locations (a region drawn across the map edge is measured unwrapped)."""
    pairs = run.locations.filter(land_region_expr()).select("slug", "macro_region").unique("slug")
    regions = sorted(pairs["macro_region"].unique().to_list())
    region_index = {r: i for i, r in enumerate(regions)}
    of_location = np.full(len(canvas.tags), -1, dtype=np.int64)
    index = pairs["slug"].replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).to_numpy()
    keep = index >= 0
    of_location[index[keep]] = pairs["macro_region"].replace_strict(region_index, return_dtype=pl.Int64).to_numpy()[keep]
    raster = np.where(canvas.index >= 0, of_location[np.maximum(canvas.index, 0)], -1)
    centres: dict[str, tuple[float, float]] = {}
    ys, xs = np.nonzero(raster >= 0)
    ids = raster[ys, xs]
    for region, i in region_index.items():
        mask = ids == i
        if not mask.any():
            continue
        rx, ry = xs[mask], ys[mask]
        columns = np.bincount(rx, minlength=canvas.width) > 0
        if columns[0] and columns[-1] and not columns.all():  # wraps the map edge: shift the left part right
            gap = np.nonzero(~columns)[0]
            rx = np.where(rx < gap[0], rx + canvas.width, rx)
        centres[region] = ((float(rx.mean()) % canvas.width), float(ry.mean()))
    return raster, regions, centres


def _region_borders(raster: np.ndarray) -> np.ndarray:
    mask = np.zeros(raster.shape, dtype=bool)
    mask[:, 1:] |= (raster[:, 1:] != raster[:, :-1]) & ((raster[:, 1:] >= 0) | (raster[:, :-1] >= 0))
    mask[1:, :] |= (raster[1:, :] != raster[:-1, :]) & ((raster[1:, :] >= 0) | (raster[:-1, :] >= 0))
    return mask


def _draw_labels(rgb: np.ndarray, labels: list[tuple[float, float, str, str]]) -> np.ndarray:
    """Region labels (x, y, name, figures) centred on (x, y), with a dark outline so they read over any colour."""
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    name_font, figure_font = _font(17, True), _font(15)
    for x, y, name, figures in labels:
        for text, font, dy, fill in ((name, name_font, -11, TEXT), (figures, figure_font, 10, (214, 220, 228))):
            box = draw.textbbox((0, 0), text, font=font)
            draw.text((x - (box[2] - box[0]) / 2, y + dy - (box[3] - box[1]) / 2), text, font=font, fill=fill,
                      stroke_width=3, stroke_fill=(8, 10, 14))
    return np.asarray(image)


def render_trade_maps(run: RunData, canvas: MapCanvas, out: Path, *, fps: int,
                      log: Callable[[str], None] = print) -> list[dict[str, str]]:
    """Three videos: trade between world regions (in, out and the largest flows), the largest trade routes between
    markets, and each market's net trade (exports - imports)."""
    if run.trades.is_empty() or run.market_goods.is_empty() or run.markets.is_empty():
        log("trade maps: no trade routes in the dataset; skipped")
        return []
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    centroids = _location_centroids(canvas)
    snapshots = run.snapshots.to_dicts()
    by_snapshot = run.locations.partition_by("snapshot_id", as_dict=True)
    prices = run.market_goods.group_by("snapshot_id", "good_id").agg(pl.col("default_price").first(), pl.col("group").first())
    routes = (
        run.trades.join(prices, on=["snapshot_id", "good_id"], how="left")
        .with_columns((pl.col("amount") * pl.col("default_price").fill_null(1.0)).alias("value"), pl.col("group").fill_null("produced"))
        .group_by("snapshot_id", "from_market", "to_market")
        .agg(pl.col("value").sum(), pl.col("group").sort_by("value").last())
    )
    totals = run.market_goods.group_by("snapshot_id", "market_id").agg(
        (pl.col("imports") * pl.col("default_price")).sum().alias("imp_v"),
        (pl.col("exports") * pl.col("default_price")).sum().alias("exp_v"),
        (pl.col("production") * pl.col("default_price")).sum().alias("prod_v"),
    ).with_columns(
        ((pl.col("exp_v") - pl.col("imp_v")) / (pl.col("prod_v") + pl.col("imp_v"))).alias("net_share"),
        (pl.col("exp_v") + pl.col("imp_v")).alias("traded"),
    )
    centres = run.markets.with_columns(
        pl.col("center_slug").replace_strict(canvas.tag_index, default=-1, return_dtype=pl.Int64).alias("tag_index"))
    route_ref = float(routes["value"].quantile(0.995) or 1.0) or 1.0
    trade_ref = float(totals["traded"].quantile(0.99) or 1.0) or 1.0
    group_rgb = {key: _hex(dark) for key, _, _, dark in GOODS_GROUPS}
    share_by_snapshot = world_trade_share(run)
    duration = len(snapshots) / fps
    max_kbps = int(MAX_VIDEO_BYTES * 8 / 1000 / (duration + 2.0))
    legend = [(label, group_rgb[key]) for key, label, _, _ in GOODS_GROUPS]
    route_composer = FrameComposer(canvas, "Largest trade routes", f"Top {TOP_ROUTES} market pairs, base prices",
                                   None, legend=legend)
    # world regions: flows between them (exporter -> importer, main goods group) and their net trade
    flows = region_trade(run)
    pair_flows = (flows.filter(pl.col("from_region") != pl.col("to_region"))
                  .group_by("snapshot_id", "from_region", "to_region")
                  .agg(pl.col("value").sum(), pl.col("group").sort_by("value").last()))
    region_totals = region_trade_totals(flows)
    flow_ref = float(pair_flows["value"].quantile(0.99) or 1.0) if not pair_flows.is_empty() else 1.0
    region_raster, regions, region_centre = _region_layout(canvas, run)
    region_edges = _region_borders(region_raster)
    region_scale = Scale("diverging", -1.0, 1.0, _ramp(DIVERGING[:3] + (DIVERGING_DARK_MID,) + DIVERGING[4:]),
                         [(-1.0, "imports only"), (-0.5, "-50%"), (0.0, "balanced"), (0.5, "+50%"), (1.0, "exports only")])
    region_composer = FrameComposer(canvas, "Trade between world regions", "Colour: net trade · arrows: largest flows",
                                    region_scale, nodata_label="little trade")
    balance_scale = Scale("diverging", -0.3, 0.3, _ramp(DIVERGING[:3] + (DIVERGING_DARK_MID,) + DIVERGING[4:]),
                          [(-0.3, "-30% importer"), (-0.15, "-15%"), (0.0, "0"), (0.15, "+15%"), (0.3, "+30% exporter")])
    balance_composer = FrameComposer(canvas, "Market trade balance", "Exports minus imports, share of production + imports",
                                     balance_scale)
    writers = {
        "trade_regions": (region_composer, VideoWriter(out / "trade_regions.mp4", region_composer.width, region_composer.height, fps, max_kbps)),
        "trade_routes": (route_composer, VideoWriter(out / "trade_routes.mp4", route_composer.width, route_composer.height, fps, max_kbps)),
        "trade_balance": (balance_composer, VideoWriter(out / "trade_balance.mp4", balance_composer.width, balance_composer.height, fps, max_kbps)),
    }
    last: dict[str, bytes] = {}
    for snap in snapshots:
        snapshot = snap["snapshot_id"]
        locs = by_snapshot.get((snapshot,), pl.DataFrame())
        raster = _market_raster(canvas, locs)
        borders = _market_borders(raster)
        year = str(snap.get("year") or snap.get("date") or "")
        total = totals.filter(pl.col("snapshot_id") == snapshot)
        # routes over a neutral map with the market borders
        base = np.empty((canvas.height, canvas.width, 3), dtype=np.uint8)
        base[:] = SEA
        base[raster >= 0] = TRADE_LAND
        base[raster == -1] = NO_MARKET_LAND
        base[borders] = MARKET_BORDER
        centre = {}
        for market_id, tag_index in centres.filter(pl.col("snapshot_id") == snapshot).select("market_id", "tag_index").iter_rows():
            if tag_index is not None and tag_index >= 0 and np.isfinite(centroids[tag_index]).all():
                centre[market_id] = tuple(centroids[tag_index])
        radius = {m: 2.0 + 7.0 * math.sqrt(min(1.0, (t or 0.0) / trade_ref)) for m, t in total.select("market_id", "traded").iter_rows()}
        lines = []
        frame_routes = routes.filter(pl.col("snapshot_id") == snapshot)
        top_routes = frame_routes.sort("value", descending=True).head(TOP_ROUTES).sort("value")
        on_routes: set[Any] = set()
        for from_market, to_market, value, group in top_routes.select("from_market", "to_market", "value", "group").iter_rows():
            a, b = centre.get(from_market), centre.get(to_market)
            if a is None or b is None or not value:
                continue
            t = min(1.0, math.sqrt(value / route_ref))
            rgb = group_rgb.get(group, group_rgb["produced"])
            lines.append((a[0], a[1], radius.get(from_market, 2.0), b[0], b[1], radius.get(to_market, 2.0),
                          1.0 + 6.0 * t, (*rgb, int(120 + 135 * t))))
            on_routes.update((from_market, to_market))
        dots = [(centre[m][0], centre[m][1], radius.get(m, 2.0)) for m in on_routes if m in centre]
        traded = float(frame_routes["value"].sum() or 0.0)
        top_share = float(top_routes["value"].sum() or 0.0) / traded if traded else 0.0
        composer = writers["trade_routes"][0]
        frame = composer.compose(_draw_trade(base, lines, dots), year,
                                 [("traded per month", f"{_format_number(traded)} gold"), ("market pairs", str(frame_routes.height)),
                                  (f"top {TOP_ROUTES} carry", f"{top_share * 100:.0f}%")])
        writers["trade_routes"][1].write(frame)
        last["trade_routes"] = frame
        # world regions filled by net trade with other regions, the largest flows between them, labels in / out
        region_frame = region_totals.filter(pl.col("snapshot_id") == snapshot)
        net = np.full(len(regions) + 1, np.nan)
        labels = []
        cross_total = float(region_frame["exports"].sum() or 0.0)
        for region, exports, imports, inside in region_frame.select("region", "exports", "imports", "inside").iter_rows():
            if region not in region_centre:
                continue
            if cross_total and exports + imports >= 0.01 * cross_total:  # under 1 % of the world's: "little trade"
                net[regions.index(region)] = (exports - imports) / (exports + imports)
            if cross_total and (exports + imports) >= 0.04 * cross_total:
                cx, cy = region_centre[region]
                labels.append((cx, cy, titleize(region), f"in {_format_number(imports)} · out {_format_number(exports)}"))
        lut = region_scale.colours(net[:-1])
        palette = np.vstack([lut, np.array([TRADE_LAND], dtype=np.uint8)])
        region_rgb = np.empty((canvas.height, canvas.width, 3), dtype=np.uint8)
        region_rgb[:] = SEA
        land = canvas.index >= 0
        region_rgb[land] = palette[region_raster[land]]  # -1 (land outside a world region) takes the last row
        region_rgb[region_edges & land] = REGION_BORDER
        flows_frame = pair_flows.filter(pl.col("snapshot_id") == snapshot).sort("value", descending=True).head(TOP_REGION_FLOWS).sort("value")
        arrows = []
        for from_region, to_region, value, group in flows_frame.select("from_region", "to_region", "value", "group").iter_rows():
            a, b = region_centre.get(from_region), region_centre.get(to_region)
            if a is None or b is None or not value:
                continue
            t = min(1.0, math.sqrt(value / flow_ref))
            rgb = group_rgb.get(group, group_rgb["produced"])
            arrows.append((a[0], a[1], 26.0, b[0], b[1], 26.0, 1.5 + 9.0 * t, (*rgb, int(150 + 105 * t))))
        region_map = _draw_labels(_draw_trade(region_rgb, arrows, []), labels)
        inside_total = float(region_frame["inside"].sum() or 0.0)
        frame = writers["trade_regions"][0].compose(region_map, year, [
            ("between regions", f"{_format_number(cross_total)} gold"), ("inside regions", f"{_format_number(inside_total)} gold")])
        writers["trade_regions"][1].write(frame)
        last["trade_regions"] = frame
        # every location in its market's colour: net exporter blue, net importer red
        values = locs.select("slug", "market_id").join(total.select("market_id", pl.col("net_share").alias("value")), on="market_id",
                                                       how="left") if not locs.is_empty() else pl.DataFrame(schema={"slug": pl.String, "value": pl.Float64})
        rgb_map = _paint(canvas, balance_scale.colours(_values_array(canvas, values)))
        rgb_map[borders] = BALANCE_BORDER
        share = share_by_snapshot.get(snapshot, 0.0)
        frame = writers["trade_balance"][0].compose(rgb_map, year, [("imported share", f"{share * 100:.1f}%"),
                                                                    ("markets", str(total.height))])
        writers["trade_balance"][1].write(frame)
        last["trade_balance"] = frame
    results = []
    titles = {"trade_regions": ("Trade between world regions", "World regions coloured by exports − imports as a share of "
                                                               "their trade with other regions (blue: exporter, red: importer); "
                                                               f"the {TOP_REGION_FLOWS} largest flows as arrows (width = value per "
                                                               "month at base prices, colour = main goods group); labels: imports "
                                                               "and exports in gold per month"),
              "trade_routes": ("Largest trade routes", f"The {TOP_ROUTES} largest routes between markets: width = value moved "
                                                       "per month (base prices), arrow = importer, colour = main goods group, "
                                                       "dot = market (size: trade)"),
              "trade_balance": ("Market trade balance", "Exports minus imports of each market, as a share of its "
                                                        "production plus imports (blue: net exporter, red: net importer)")}
    for key, (composer, writer) in writers.items():
        if key in last:
            writer.write(last[key], repeat=2 * fps)
            Image.frombytes("RGB", (composer.width, composer.height), last[key]).save(out / f"{key}.png", optimize=True)
        writer.close()
        size = (out / f"{key}.mp4").stat().st_size
        title, subtitle = titles[key]
        results.append({"key": key, "title": title, "subtitle": subtitle, "video": f"maps/{key}.mp4",
                        "poster": f"maps/{key}.png", "bytes": str(size)})
        log(f"map {key}: {len(snapshots)} frames, {size / 1e6:.1f} MB")
    log(f"trade maps: {time.perf_counter() - started:.1f}s")
    return results


# --------------------------------------------------------------------------------------------------------
# Page


def institutions_per_person(locations: pl.DataFrame, order: list[str]) -> list[float]:
    """Population-weighted institutions present per location, per save that has institution data (in save order)."""
    if "institutions" not in locations.columns:
        return []
    rows = (
        locations.filter(pl.col("institutions").is_not_null())
        .group_by("snapshot_id")
        .agg((pl.col("institutions") * pl.col("total_population")).sum().alias("w"), pl.col("total_population").sum().alias("p"))
        .filter(pl.col("p") > 0)
    )
    by = {r["snapshot_id"]: r["w"] / r["p"] for r in rows.to_dicts()}
    return [by[snap] for snap in order if snap in by]


def _summary(run: RunData) -> dict[str, object]:
    first, last = run.snapshots["snapshot_id"][0], run.snapshots["snapshot_id"][-1]
    subsistence = (
        pl.col("unemployed_peasants").sum() / pl.col("total_population").sum()
        if "unemployed_peasants" in run.locations.columns else pl.lit(None, dtype=pl.Float64)
    )
    world = run.locations.group_by("snapshot_id").agg(
        pl.col("total_population").sum().alias("population"),
        pl.col("country_tag").filter(pl.col("owner").is_not_null()).n_unique().alias("countries"),
        pl.col("owner").is_null().mean().alias("unowned_share"),
        subsistence.alias("subsistence_share"),
    )
    at = {r["snapshot_id"]: r for r in world.to_dicts()}
    levels = run.building_levels.group_by("snapshot_id").agg(pl.col("levels").sum())
    lv = {r["snapshot_id"]: r["levels"] for r in levels.to_dicts()}
    investment = (
        run.investment_by_country.filter(pl.col("snapshot_id") == last).select("country_tag", "investment")
        if not run.investment_by_country.is_empty()
        else pl.DataFrame(schema={"country_tag": pl.String, "investment": pl.Float64})
    )
    leaders = (
        run.countries.filter((pl.col("snapshot_id") == last) & (pl.col("owned_locations_count").fill_null(0) > 0))
        .join(investment, on="country_tag", how="left")
        .sort("population", descending=True, nulls_last=True).head(10)
        .select("country_name", "country_tag", "population", "owned_locations_count", "gold", "investment", "is_subject")
        .to_dicts()
    )
    world_investment = (
        {r["snapshot_id"]: r["investment"] for r in run.investment_by_category.group_by("snapshot_id").agg(
            pl.col("investment").sum()).to_dicts()}
        if not run.investment_by_category.is_empty() else {}
    )
    trade = world_trade_share(run)
    urban: dict[str, int] = {}
    if run.urban_saves and last in run.urban_saves:
        def count(frame: pl.DataFrame, snapshot: str) -> int:
            return frame.filter(pl.col("snapshot_id") == snapshot).height if not frame.is_empty() else 0

        urban = {"rights_last": count(run.town_rights, last), "rights_first": count(run.town_rights, run.urban_saves[0]),
                 "promotions_last": count(run.promotions, last)}
    per_person = institutions_per_person(run.locations, run.snapshots["snapshot_id"].to_list())
    return {"first": at.get(first, {}), "last": at.get(last, {}), "levels_first": lv.get(first, 0), "levels_last": lv.get(last, 0),
            "investment_first": world_investment.get(first), "investment_last": world_investment.get(last),
            "institutions_first": per_person[0] if per_person else None,
            "institutions_last": per_person[-1] if per_person else None,
            "trade_first": trade.get(first), "trade_last": trade.get(last), "leaders": leaders, **urban}


SECTIONS = (
    ("population", "Population", "Who lives where, and how many have work."),
    ("institutions", "Institutions", "How far the institutions have spread: a location has an institution once its "
                                     "spread reaches 100 %."),
    ("trade", "Trade", "What moved between markets and what did not: the routes and the trade balance of every market "
                       "as videos, then trade per goods group, per good and per market."),
    ("prices", "Prices", "Every good's price against its base price, and whether the world uses more than it makes."),
    ("buildings", "Buildings", "Building levels and what they cost to build."),
    ("towns", "Town rights & industry", "Which town rights and industry promotions the AI grants, where, and whether they "
                                        "sit where their goods are made."),
    ("countries", "Countries", "The largest countries by population and by income."),
    ("speed", "Game speed", "How long the game took per game year, from the times the saves were written."),
)

ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"

PAGE_CSS = """
:root{--bg:#f6f6f4;--card:#fcfcfb;--ink:#1d1d1b;--muted:#6b6b67;--line:#e2e2de;--accent:#2a78d6;--pos:#1f5fae;--neg:#b23a3a;--chip:#ebebe7}
@media (prefers-color-scheme: dark){:root{--bg:#121418;--card:#1a1d22;--ink:#eceef0;--muted:#a0a6b0;--line:#2c3038;--accent:#6da7ec;--pos:#8fb8ec;--neg:#e67a73;--chip:#252a31}}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1320px;margin:0 auto;padding:28px 16px 48px} h1{margin:0 0 4px;font-size:28px;line-height:1.2}
h2{margin:48px 0 4px;font-size:22px} .lead{margin:0 0 16px;color:var(--muted);font-size:14px;max-width:80ch} h3{margin:0;font-size:16px}
.muted{color:var(--muted)} nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
nav a{padding:4px 12px;border-radius:999px;background:var(--chip);color:var(--ink);text-decoration:none;font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:20px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:10px}
.tile{padding:14px 16px} .tile .label{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.tile .value{font-size:24px;font-weight:700;margin-top:2px} .tile .sub{font-size:13px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:16px;margin-bottom:16px}
figure{margin:0;overflow:hidden} video{display:block;width:100%;height:auto;background:#12161c}
figcaption{padding:10px 14px;font-size:13px;color:var(--muted)}
.card{margin-bottom:16px;overflow:hidden} .card>header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;padding:14px 16px 6px}
.chart{width:100%} .caption{margin:0;padding:6px 16px 14px;font-size:13px;color:var(--muted);max-width:110ch}
.views{display:flex;flex-wrap:wrap;gap:4px}
.views button{font:inherit;font-size:13px;padding:3px 10px;border-radius:6px;border:1px solid var(--line);background:transparent;color:var(--muted);cursor:pointer}
.views button.active{background:var(--accent);border-color:var(--accent);color:#fff}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13px;color:var(--muted)}
.controls select,.controls input{font:inherit;font-size:13px;padding:3px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
.table-wrap{overflow-x:auto} table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);cursor:pointer;white-space:nowrap;user-select:none}
th.sorted{color:var(--ink)} th.sorted::after{content:" \\25BE"} th.sorted.asc::after{content:" \\25B4"}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.wide{min-width:240px;color:var(--muted);font-size:12px} td.pos{color:var(--pos)} td.neg{color:var(--neg)}
.more{display:block;margin:8px 16px 0;font:inherit;font-size:13px;background:none;border:none;color:var(--accent);cursor:pointer;padding:0}
a{color:var(--accent)} footer{margin-top:40px;font-size:12px;color:var(--muted)}
nav a.goodslink{background:var(--accent);color:#fff}
img.gi{width:18px;height:18px;vertical-align:-4px} td.good{white-space:nowrap} td.good img.gi{margin-right:6px}
td.goods{white-space:nowrap} td.goods .gv{display:inline-block;margin-right:12px;color:var(--muted);font-variant-numeric:tabular-nums}
td.goods .gv img.gi{margin-right:3px}
.glegend{display:flex;flex-wrap:wrap;gap:6px 18px;padding:0 16px 14px;font-size:12px;color:var(--muted)}
.glegend.full{flex-direction:column} .glegend .grp{display:flex;align-items:flex-start;gap:4px 8px}
.glegend .name{display:inline-flex;align-items:center;gap:6px;color:var(--ink);font-weight:600;line-height:20px}
.glegend.full .name{flex:0 0 200px} .glegend .icons{display:flex;flex-wrap:wrap;gap:2px 3px}
@media (max-width:600px){.glegend .grp{flex-direction:column} .glegend.full .name{flex-basis:auto}}
.glegend .sw{display:inline-block;width:10px;height:10px;border-radius:2px}
.glegend .txt{padding:0 4px;border:1px solid var(--line);border-radius:4px}
"""

PAGE_JS = r"""
(() => {
  const DATA = JSON.parse(document.getElementById('report-data').textContent);
  const dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  const compact = v => {
    const a = Math.abs(v);
    if (a < 0.005) return '0';
    if (a >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (a >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    return a >= 10 ? v.toFixed(0) : a >= 1 ? v.toFixed(1) : v.toFixed(2);
  };
  const UNITS = {
    mpeople: v => v === 0 ? '0' : v.toFixed(Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2) + 'M',
    kpeople: v => compact(v * 1000),
    pct: v => v.toFixed(1) + '%',
    pct0: v => v.toFixed(0) + '%',
    pct2: v => (v > 0 ? '+' : '') + v.toFixed(2) + '%',
    ratio: v => v.toFixed(2) + '×',
    index: v => v.toFixed(0),
    gold: v => compact(v),
    gold2: v => v.toFixed(2),
    num: v => compact(v),
    count: v => String(Math.round(v)),
    sec: v => v.toFixed(1) + ' s',
  };
  const fmt = (v, unit) => (v == null || !isFinite(v)) ? '–' : (UNITS[unit] || compact)(v);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  // goods by id: icon where the game has one, the name in tooltips (and in place of a missing icon)
  const GOODS = DATA.goods || {};
  const goodName = id => (GOODS[id] && GOODS[id].name) || String(id).replace(/_/g, ' ');
  const goodIcon = id => GOODS[id] && GOODS[id].icon;
  const goodHtml = id => (goodIcon(id) ? `<img class=gi src="${esc(goodIcon(id))}" alt="" style="margin-right:6px">` : '') + esc(goodName(id));
  const richKey = id => 'g_' + String(id).replace(/\W/g, '_');
  // charts draw axis icons from loaded images: ECharts does not repaint labels whose image arrives late
  const ICON_IMG = {};
  const iconsReady = Promise.all(Object.keys(GOODS).filter(goodIcon).map(id => new Promise(done => {
    const image = new Image();
    image.onload = image.onerror = () => done();
    image.src = goodIcon(id);
    ICON_IMG[id] = image;
  })));
  let RICH = null;
  const goodRich = () => {
    if (RICH) return RICH;
    RICH = {sp: {width: 5}, name: {fontSize: 11}};
    for (const g of DATA.groups || []) RICH['bar_' + g.key] = {width: 4, height: 18, backgroundColor: g.color, borderRadius: 1};
    for (const id in ICON_IMG) if (ICON_IMG[id].naturalWidth) RICH[richKey(id)] = {width: 18, height: 18, backgroundColor: {image: ICON_IMG[id]}};
    return RICH;
  };
  const goodLabel = id => {
    const g = GOODS[id] || {};
    const drawn = g.icon && ICON_IMG[id] && ICON_IMG[id].naturalWidth;
    return (g.group ? `{bar_${g.group}| }{sp| }` : '') + (drawn ? `{${richKey(id)}| }` : `{name|${goodName(id).replace(/[{}|]/g, '')}}`);
  };

  const axisTip = unit => params => {
    if (!params || !params.length) return '';
    const year = new Date(params[0].value[0]).getUTCFullYear();
    const rows = params.filter(p => p.value && p.value[1] != null).sort((a, b) => b.value[1] - a.value[1]);
    return `<div style="font-weight:600;margin-bottom:2px">${year}</div>` + rows.map(p =>
      `<div style="display:flex;justify-content:space-between;gap:18px"><span>${p.marker}${esc(p.seriesName)}</span><b>${fmt(p.value[1], unit)}</b></div>`).join('');
  };
  const heatTip = (view, option) => p => {
    const v = p.value;
    const y = option.yAxis.data[v[1]];
    let s = `<b>${GOODS[y] ? goodHtml(y) : esc(y)}</b> · ${esc(option.xAxis.data[v[0]])}`;
    for (const [label, i, unit] of (view.fields || [])) s += `<br>${esc(label)}: <b>${fmt(v[i], unit)}</b>`;
    return s;
  };
  const WORLD = '#1d1d1b', WORLD_DARK = '#eceef0';  // the world line: ink on either page
  const resolve = (obj, view, root) => {
    if (Array.isArray(obj)) return obj.map(o => resolve(o, view, root));
    if (obj && typeof obj === 'object') { const out = {}; for (const k in obj) out[k] = resolve(obj[k], view, root); return out; }
    if (dark && obj === WORLD) return WORLD_DARK;
    if (typeof obj === 'string' && obj.startsWith('fn:')) {
      const [, name, arg] = obj.split(':');
      if (name === 'axis') return axisTip(arg || view.unit);
      if (name === 'heat') return heatTip(view, root);
      if (name === 'year') return v => String(new Date(v).getUTCFullYear());
      if (name === 'unit') return v => fmt(v, arg || view.unit);
      if (name === 'pow2') return v => Math.pow(2, v).toFixed(Math.abs(v) > 1.5 ? 1 : 2) + '×';
      if (name === 'pow2n') return v => String(Math.round(Math.pow(2, v)));
      if (name === 'goodlabel') return goodLabel;
      if (name === 'goodrich') return goodRich();
    }
    return obj;
  };

  const specs = Object.fromEntries(DATA.charts.map(c => [c.key, c]));
  const init = el => {
    if (el.dataset.ready) return;
    el.dataset.ready = '1';
    const spec = specs[el.dataset.key];
    const chart = echarts.init(el, dark ? 'dark' : null);
    // a good's icon on a heatmap axis names itself on hover
    chart.on('mouseover', p => { if (p.componentType === 'yAxis' && GOODS[p.value]) el.title = goodName(p.value); });
    chart.on('mouseout', p => { if (p.componentType === 'yAxis') el.title = ''; });
    const buttons = el.closest('.card').querySelectorAll('.views button');
    const show = i => {
      const view = spec.views[i];
      const option = resolve(view.option, view, view.option);
      option.backgroundColor = 'transparent';
      if (option.visualMap) {
        if (dark && option.visualMap.darkColors) option.visualMap.inRange.color = option.visualMap.darkColors;
        delete option.visualMap.darkColors;
      }
      chart.setOption(option, true);
      buttons.forEach((b, j) => b.classList.toggle('active', i === j));
    };
    buttons.forEach((b, j) => b.addEventListener('click', () => show(j)));
    iconsReady.then(() => show(0));
    new ResizeObserver(() => chart.resize()).observe(el);
  };
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { io.unobserve(e.target); init(e.target); }
  }), {rootMargin: '400px'});
  const all = [...document.querySelectorAll('.chart[data-key]')];
  all.forEach(el => io.observe(el));
  // charts not scrolled to yet are drawn in the background, one at a time, so every chart is ready
  window.addEventListener('load', () => {
    const next = () => {
      const el = all.find(e => !e.dataset.ready);
      if (!el) return;
      io.unobserve(el);
      init(el);
      setTimeout(next, 60);
    };
    setTimeout(next, 1200);
  });

  // table cells of kind good (one id) and goods ([[id, value], ...]): filtered by name, sorted by name / first value
  const cellText = (v, c) => c.kind === 'good' ? goodName(v)
    : c.kind === 'goods' ? (v || []).map(([id]) => goodName(id)).join(' ') : (v == null ? '' : String(v));
  const sortKey = (v, c) => c.kind === 'good' ? goodName(v) : c.kind === 'goods' ? ((v && v.length) ? v[0][1] : null) : v;
  const numeric = c => c.kind === 'num' || c.kind === 'goods';
  const goodsCell = (v, c) => (v || []).map(([id, x]) => `<span class=gv title="${esc(goodName(id))}">` +
    (goodIcon(id) ? `<img class=gi src="${esc(goodIcon(id))}" alt="${esc(goodName(id))}">` : esc(goodName(id)) + ' ') +
    `${fmt(x, c.unit)}</span>`).join('');

  for (const spec of DATA.tables) {
    const root = document.getElementById('table-' + spec.key);
    const card = root.closest('.card');
    const select = card.querySelector('select');
    const search = card.querySelector('input[type=search]');
    const more = card.querySelector('.more');
    const limit = spec.limit || 50;
    spec.snapshots.forEach((label, i) => select.add(new Option(label, i)));
    let snap = spec.snapshots.length - 1;
    while (snap > 0 && !(spec.rows[snap] || []).length) snap--;
    select.value = String(snap);
    let sortIndex = Math.max(0, spec.columns.findIndex(c => c.key === spec.sort)), desc = true, all = false;
    const render = () => {
      const q = search.value.trim().toLowerCase();
      let rows = spec.rows[snap] || [];
      if (q) rows = rows.filter(r => r.some((v, i) => spec.columns[i].kind !== 'num' && cellText(v, spec.columns[i]).toLowerCase().includes(q)));
      const col = spec.columns[sortIndex];
      rows = rows.slice().sort((a, b) => {
        const x = sortKey(a[sortIndex], col), y = sortKey(b[sortIndex], col);
        if (x == null || x === '') return 1;
        if (y == null || y === '') return -1;
        const c = numeric(col) ? x - y : String(x).localeCompare(String(y));
        return desc ? -c : c;
      });
      const total = rows.length;
      if (!all) rows = rows.slice(0, limit);
      const head = spec.columns.map((c, i) => `<th class="${c.kind === 'num' ? 'num' : ''}${i === sortIndex ? ' sorted' + (desc ? '' : ' asc') : ''}"` +
        `${c.title ? ` title="${esc(c.title)}"` : ''} data-i="${i}">${esc(c.label)}</th>`).join('');
      const body = rows.map(r => '<tr>' + r.map((v, i) => {
        const c = spec.columns[i];
        if (c.kind === 'good') return `<td class=good>${goodHtml(v)}</td>`;
        if (c.kind === 'goods') return `<td class=goods>${goodsCell(v, c)}</td>`;
        if (c.kind !== 'num') return `<td${c.wide ? ' class="wide"' : ''}>${v == null ? '' : esc(v)}</td>`;
        const cls = 'num' + (c.signed && v != null ? (v > 0 ? ' pos' : v < 0 ? ' neg' : '') : '');
        return `<td class="${cls}">${(c.signed && v > 0 ? '+' : '') + fmt(v, c.unit)}</td>`;
      }).join('') + '</tr>').join('');
      root.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
      root.querySelectorAll('th').forEach(th => th.addEventListener('click', () => {
        const i = Number(th.dataset.i);
        desc = i === sortIndex ? !desc : numeric(spec.columns[i]);
        sortIndex = i;
        render();
      }));
      more.hidden = total <= limit;
      more.textContent = all ? 'Show fewer' : `Show all ${total}`;
    };
    select.addEventListener('change', () => { snap = Number(select.value); render(); });
    search.addEventListener('input', render);
    more.addEventListener('click', () => { all = !all; render(); });
    render();
  }
})();
"""


def _video_card(m: dict[str, str]) -> str:
    esc = html.escape
    return (f"<figure class=card><video controls loop muted playsinline preload=metadata poster='{esc(m['poster'])}'>"
            f"<source src='{esc(m['video'])}' type='video/mp4'></video>"
            f"<figcaption><b>{esc(m['title'])}</b> · {esc(m['subtitle'])} · <a href='{esc(m['video'])}' download>MP4</a></figcaption></figure>")


def _goods_legend(payload: dict[str, Any], full: bool) -> str:
    """The goods groups with their colour; full: every group's goods (icons, the name on hover), in heatmap order."""
    esc = html.escape
    goods = payload.get("goods") or {}
    rows = []
    for group in payload.get("groups") or []:
        members = [info for info in goods.values() if info.get("group") == group["key"]]
        if not members:
            continue
        name = f"<span class=name><i class=sw style='background:{esc(group['color'])}'></i>{esc(group['label'])}</span>"
        items = "".join(
            f"<img class=gi src='{esc(m['icon'])}' alt='{esc(m['name'])}' title='{esc(m['name'])}'>" if m.get("icon")
            else f"<span class=txt>{esc(m['name'])}</span>" for m in members) if full else ""
        rows.append(f"<div class=grp>{name}<span class=icons>{items}</span></div>" if full else f"<div class=grp>{name}</div>")
    return f"<div class='glegend{' full' if full else ''}'>{''.join(rows)}</div>" if rows else ""


def _chart_card(c: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
    esc = html.escape
    buttons = "".join(f"<button type=button>{esc(v['label'])}</button>" for v in c["views"]) if len(c["views"]) > 1 else ""
    legend = _goods_legend(payload or {}, c["goods_legend"] == "goods") if c.get("goods_legend") else ""
    return (f"<section class=card><header><h3>{esc(c['title'])}</h3><div class=views>{buttons}</div></header>"
            f"<div class=chart data-key='{esc(c['key'])}' style='height:{int(c['height'])}px'></div>"
            f"<p class=caption>{esc(c['caption'])}</p>{legend}</section>")


def _table_card(t: dict[str, Any]) -> str:
    esc = html.escape
    return (f"<section class=card><header><h3>{esc(t['title'])}</h3><div class=controls><label>Save <select></select></label>"
            f"<input type=search placeholder='Filter' aria-label='Filter rows'></div></header>"
            f"<div class=table-wrap id='table-{esc(t['key'])}'></div><button type=button class=more hidden></button>"
            f"<p class=caption>{esc(t['caption'])}</p></section>")


def write_page(run: RunData, out: Path, maps: list[dict[str, str]], payload: dict[str, Any]) -> Path:
    start, end = run.years
    summary = _summary(run)
    first, last = summary["first"], summary["last"]  # type: ignore[assignment]
    pop0, pop1 = float(first.get("population") or 0) * 1000, float(last.get("population") or 0) * 1000  # type: ignore[union-attr]
    change = (pop1 / pop0 - 1) * 100 if pop0 else 0.0
    esc = html.escape
    pct = lambda v: "–" if v is None else f"{float(v) * 100:.0f}%"  # noqa: E731
    speed = speed_average(speed_segments(xaxis(run), run.snapshots))  # same average as the Game speed chart
    tiles = [
        ("Years", f"{start}–{end}", f"{run.snapshots.height} saves" + (f" · {speed:.1f} s per game year" if speed is not None else "")),
        ("Population", _format_number(pop1), f"{change:+.1f}% since {start}"),
        ("Unemployment", pct(last.get("subsistence_share")), f"{pct(first.get('subsistence_share'))} in {start}"),  # type: ignore[union-attr]
        ("Countries", str(last.get("countries", "–")), f"{first.get('countries', '–')} in {start}"),  # type: ignore[union-attr]
        ("Building levels", _format_number(float(summary["levels_last"] or 0)), f"{_format_number(float(summary['levels_first'] or 0))} in {start}"),
        ("Unowned land", f"{float(last.get('unowned_share') or 0) * 100:.0f}%", f"{float(first.get('unowned_share') or 0) * 100:.0f}% in {start}"),  # type: ignore[union-attr]
    ]
    if summary.get("trade_last") is not None:
        tiles.insert(3, ("Imported share", f"{float(summary['trade_last']) * 100:.1f}%",  # type: ignore[arg-type]
                         f"{float(summary['trade_first'] or 0) * 100:.1f}% in {start}"))  # type: ignore[arg-type]
    if summary.get("institutions_last") is not None:
        tiles.insert(3, ("Institutions per person", f"{float(summary['institutions_last']):.1f}",  # type: ignore[arg-type]
                         f"{float(summary['institutions_first'] or 0):.1f} in {start}"))  # type: ignore[arg-type]
    if summary.get("rights_last") is not None:
        tiles.insert(-1, ("Town rights", str(summary["rights_last"]),
                          f"{summary['rights_first']} in {start} · {summary['promotions_last']} industry promotions"))
    if summary.get("investment_last") is not None:
        tiles.insert(-1, ("Building investment", f"{_format_number(float(summary['investment_last']))} gold",  # type: ignore[arg-type]
                          f"{_format_number(float(summary['investment_first'] or 0))} in {start}"))  # type: ignore[arg-type]
    tile_html = "".join(f"<div class=tile><div class=label>{esc(a)}</div><div class=value>{esc(b)}</div><div class=sub>{esc(c)}</div></div>"
                        for a, b, c in tiles)
    section_videos = {"trade": TRADE_VIDEOS, "towns": PROMOTION_VIDEOS}
    in_sections = {key for keys in section_videos.values() for key in keys}
    world_maps = "".join(_video_card(m) for m in maps if m["key"] not in in_sections)
    sections, nav = [], ["<a href='#maps'>Maps</a>"]
    goods_link = "<a href='goods.html' class=goodslink>Goods: what makes and uses them →</a>" if (out / "goods.html").is_file() else ""
    for key, title, lead in SECTIONS:
        charts = [c for c in payload["charts"] if c["section"] == key]
        tables = [t for t in payload["tables"] if t["section"] == key]
        videos = "".join(_video_card(m) for m in maps if m["key"] in section_videos.get(key, ()))
        if not (charts or tables or videos):
            continue
        nav.append(f"<a href='#{key}'>{esc(title)}</a>")
        body = (f"<div class=grid>{videos}</div>" if videos else "") + "".join(_chart_card(c, payload) for c in charts) + "".join(
            _table_card(t) for t in tables)
        sections.append(f"<h2 id={key}>{esc(title)}</h2><p class=lead>{esc(lead)}</p>{body}")
    data = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(run.name)} · {start}–{end} · Prosper or Perish</title>
<meta property="og:title" content="{esc(run.name)} · {start}–{end}">
<meta property="og:description" content="Prosper or Perish observer run: {run.snapshots.height} saves, maps, trade, prices and countries.">
<meta property="og:image" content="maps/political.png">
<style>{PAGE_CSS}</style></head><body><main>
<h1>{esc(run.name)}</h1>
<div class=muted>Prosper or Perish · observer run {start}–{end} · {run.snapshots.height} saves</div>
<div class=tiles>{tile_html}</div>
<nav>{goods_link}{''.join(nav)}</nav>
<h2 id=maps>Maps</h2><p class=lead>One frame per save.</p><div class=grid>{world_maps}</div>
{''.join(sections)}
<footer>Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by <code>ppc report</code> from {run.snapshots.height} saves. Charts: Apache ECharts.</footer>
</main>
<script id=report-data type="application/json">{data}</script>
<script src="{ECHARTS_URL}"></script>
<script>{PAGE_JS}</script>
</body></html>
"""
    path = out / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def _backfill_engine_tables(repo: Path, project: Path, dataset: Path, playthrough: str, log: Callable[[str], None]) -> None:
    """Trade routes, merchants and country economy for snapshots ingested before the dataset kept them."""
    from eu5gameparser.savegame.dataset import backfill_engine_tables

    from prosper_or_perish_constructor.free_building_levels import resolve_parser_config

    config = resolve_parser_config(repo, project)
    manifest = pl.read_parquet(dataset / "manifest.parquet").filter(pl.col("playthrough_id") == playthrough)
    profiles = manifest["parser_profile"].drop_nulls().to_list() if "parser_profile" in manifest.columns else []
    profile = profiles[0] if profiles else str(config.get("profile") or "constructor")
    done = backfill_engine_tables(dataset, playthrough_id=playthrough, profile=profile,
                                  load_order_path=repo / str(config.get("load_order") or "constructor.load_order.toml"), log=log)
    if done:
        log(f"engine tables added to {done} snapshots")


def build_report(repo: Path, project: Path, *, dataset: Path, out_root: Path, playthrough: str | None = None,
                 width: int = 1920, fps: int = 6, log: Callable[[str], None] = print) -> Path:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required for the map videos (sudo apt install ffmpeg)")
    started = time.perf_counter()
    from prosper_or_perish_constructor import building_investment

    # the derived table is incremental: a no-op when `ppc savegame-notebooks build` already brought it up to date
    building_investment.update_dataset(
        dataset,
        building_investment.load_price_catalog(repo, project),
        cost_model=building_investment.load_location_cost_model(repo, project),
        log=log,
    )
    playthrough = playthrough or latest_playthrough(dataset)
    _backfill_engine_tables(repo, project, dataset, playthrough, log)
    run = load_run(dataset, playthrough, labels=load_labels(repo, project))
    if run.urban_saves:
        run.urban = load_urban_catalog(repo, project)
    log(f"run {run.name} ({run.playthrough_id}): {run.snapshots.height} saves {run.years[0]}-{run.years[1]}")
    out = out_root / run.playthrough_id
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    canvas = build_canvas(repo, project, width)
    maps = render_maps(run, canvas, out / "maps", repo=repo, project=project, fps=fps, log=log)
    maps += render_trade_maps(run, canvas, out / "maps", fps=fps, log=log)
    maps += render_promotion_map(run, canvas, out / "maps", fps=fps, log=log)
    run.good_icons = write_good_icons(run.market_goods["good_id"].to_list() if not run.market_goods.is_empty() else [],
                                      good_icon_sources(repo, project), out, log)
    payload = build_payload(run)
    log(f"charts: {len(payload['charts'])}, tables: {len(payload['tables'])}")
    from prosper_or_perish_constructor.run_report_goods import write_goods_page  # imports this module

    write_goods_page(run, out, repo=repo, project=project, dataset=dataset,
                     cache=out_root / ".goods_cache" / run.playthrough_id, log=log)
    page = write_page(run, out, maps, payload)
    (out / "report.json").write_text(json.dumps({
        "playthrough_id": run.playthrough_id, "name": run.name, "years": run.years, "saves": run.snapshots.height,
        "maps": maps, "charts": [{"key": c["key"], "section": c["section"], "title": c["title"]} for c in payload["charts"]],
        "tables": [{"key": t["key"], "section": t["section"], "title": t["title"]} for t in payload["tables"]],
        "goods_page": (out / "goods.html").is_file(),
    }, indent=2), encoding="utf-8")
    log(f"report written to {page} ({page.stat().st_size / 1e6:.1f} MB) in {time.perf_counter() - started:.1f}s")
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
