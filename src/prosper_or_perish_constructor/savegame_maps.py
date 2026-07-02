"""Reusable savegame map rendering helpers for notebooks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import colorsys
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from IPython.display import display
from matplotlib.colors import Normalize, TwoSlopeNorm
from PIL import Image

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import GameLayer, LoadOrderConfig
from prosper_or_perish_constructor.free_building_levels import (
    resolve_labeling_baseline_path,
    resolve_map_data_file,
    resolve_parser_config,
)
from prosper_or_perish_population_capacity.geometry import build_location_geometry_frame


GEOGRAPHY_SCOPE_ORDER = ("super_region", "macro_region", "region", "area", "location")
GEOGRAPHY_SCOPE_ALIASES = {
    "super": "super_region",
    "superregion": "super_region",
    "macro": "macro_region",
    "macroregion": "macro_region",
    "marco_region": "macro_region",
    "marcoregion": "macro_region",
    "subcontinent": "macro_region",
    "sub_continent": "macro_region",
}
GEOGRAPHY_SCOPE_SEARCH_COLUMNS = {
    "super_region": ("super_region", "super_region_label"),
    "macro_region": ("macro_region", "macro_region_label"),
    "region": ("region", "region_label"),
    "area": ("area", "area_label"),
    "location": ("slug", "location_label", "location_id"),
}

DEFAULT_RELATIVE_BOUNDS = (-100.0, 300.0)
DEFAULT_POPULATION_ABSOLUTE_BOUNDS = (0.0, 2000.0)
DEFAULT_POPULATION_ABSOLUTE_SCALE = "log1p"
DEFAULT_POPULATION_DELTA_BOUNDS = (-500.0, 500.0)
DEFAULT_DEVELOPMENT_BOUNDS = (0.0, 100.0)
DEFAULT_DEVELOPMENT_DELTA_BOUNDS = (-10.0, 10.0)
DEFAULT_BUILDING_LEVEL_BOUNDS = (0.0, 400.0)
DEFAULT_BUILDING_LEVEL_DELTA_BOUNDS = (-50.0, 50.0)
DEFAULT_FOOD_PRICE_BOUNDS = (0.0, 0.30)
DEFAULT_BACKGROUND = np.array([238, 238, 232], dtype=np.uint8)
DEFAULT_UNSELECTED = np.array([184, 184, 178], dtype=np.uint8)
DEFAULT_NO_DATA = np.array([156, 156, 150], dtype=np.uint8)
DEFAULT_NO_DATA_STRIPE = np.array([126, 126, 120], dtype=np.uint8)
DEFAULT_ANIMATION_MAX_BYTES = 9_500_000
COLOR_CONSTRUCTORS = frozenset({"rgb", "hsv", "hsv360"})


@dataclass(frozen=True)
class SavegameMapAssets:
    locations_png_path: Path
    baseline_path: Path
    geometry_cache_path: Path | None
    geometry: pl.DataFrame
    packed_locations: np.ndarray
    map_width: int
    map_height: int
    source_width: int
    source_height: int
    scale_x: float
    scale_y: float
    prepared_geometry: pl.DataFrame | None = None


@dataclass(frozen=True)
class PopulationMapFrame:
    index: int
    snapshot_id: str
    date: str
    date_sort: int
    year: int
    png: bytes
    image: Any | None = None


@dataclass(frozen=True)
class PopulationMapResult:
    frames: tuple[PopulationMapFrame, ...]
    frame_data: pl.DataFrame
    baseline_snapshot_id: str
    baseline_date: str
    scope: str
    name: str
    metric: str
    comparison: str
    relative_bounds: tuple[float, float]
    mapped_locations: int
    missing_geometry_locations: int
    value_column: str = "population_map_value"
    value_label: str = "current population"
    value_bounds: tuple[float, float] = DEFAULT_POPULATION_ABSOLUTE_BOUNDS
    widget: Any | None = None


DevelopmentMapFrame = PopulationMapFrame


@dataclass(frozen=True)
class DevelopmentMapResult:
    frames: tuple[DevelopmentMapFrame, ...]
    frame_data: pl.DataFrame
    baseline_snapshot_id: str
    baseline_date: str
    scope: str
    name: str
    mode: str
    value_column: str
    value_label: str
    value_bounds: tuple[float, float]
    mapped_locations: int
    missing_geometry_locations: int
    widget: Any | None = None


BuildingLevelsMapResult = DevelopmentMapResult
FoodPriceMapResult = DevelopmentMapResult


@dataclass(frozen=True)
class PoliticalMapResult:
    frames: tuple[PopulationMapFrame, ...]
    frame_data: pl.DataFrame
    scope: str
    name: str
    mapped_locations: int
    missing_geometry_locations: int
    value_column: str = "country_color_int"
    value_label: str = "owner country"
    widget: Any | None = None


@dataclass(frozen=True)
class AnimationExportResult:
    path: Path
    format: str
    frames: int
    duration_ms: int


@dataclass(frozen=True)
class MapViewerExportResult:
    path: Path
    frame_dir: Path
    maps: tuple[str, ...]
    frames: int
    assets: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapFrameLegend:
    title: str
    rows: tuple[tuple[str, str], ...]
    region_rows: tuple[tuple[str, str, str, str, str, str], ...] = ()
    region_value_header: str = "Total"
    unit: str = ""
    signed: bool = False
    swatch_rows: tuple[tuple[str, str, str], ...] = ()
    swatch_title: str = "Top countries"


@dataclass(frozen=True)
class RenderTimeline:
    index: int
    count: int
    year: int
    start_year: int
    end_year: int


@dataclass(frozen=True)
class MapRenderCache:
    packed: np.ndarray
    base_rgb: np.ndarray
    flat_packed: np.ndarray
    hatch_mask_flat: np.ndarray
    color_to_pixels: dict[int, np.ndarray]


class Log1pNorm(Normalize):
    scale_name = "log1p"

    def __call__(self, value: Any, clip: bool | None = None) -> Any:
        if clip is None:
            clip = self.clip
        result, is_scalar = self.process_value(value)
        self.autoscale_None(result)
        vmin, vmax = _norm_bounds(self)
        if vmax <= vmin:
            mapped = np.zeros_like(result.data, dtype=np.float64)
        else:
            data = np.clip(np.asarray(result.data, dtype=np.float64), vmin, vmax)
            mapped = np.log1p(np.maximum(data - vmin, 0.0)) / np.log1p(vmax - vmin)
        output = np.ma.array(mapped, mask=result.mask, copy=False)
        return output[0] if is_scalar else output

    def inverse(self, value: Any) -> Any:
        vmin, vmax = _norm_bounds(self)
        return np.expm1(np.asarray(value, dtype=np.float64) * np.log1p(vmax - vmin)) + vmin


def load_map_assets(
    *,
    repo: Path,
    project: Path,
    map_width: int = 2400,
    geometry_cache: str | Path | None = Path("artifacts/data/population_capacity/location_geometry.parquet"),
) -> SavegameMapAssets:
    """Load map geometry and a downsampled packed locations raster."""

    if map_width <= 0:
        raise ValueError("map_width must be positive")

    parser_config = resolve_parser_config(repo, project)
    load_order_path = repo / str(parser_config.get("load_order") or "constructor.load_order.toml")
    profile_name = str(parser_config.get("profile") or "constructor")
    profile = LoadOrderConfig.load(load_order_path).profile(profile_name)
    locations_png = resolve_map_data_file(profile, "locations.png")
    baseline_path = resolve_labeling_baseline_path(repo, project)
    cache_path = _resolve_cache_path(repo, geometry_cache)
    geometry = _load_or_build_geometry(
        baseline_path=baseline_path,
        locations_png_path=locations_png,
        cache_path=cache_path,
    )
    packed_locations, source_width, source_height = _load_packed_locations(locations_png, map_width=map_width)
    map_height = int(packed_locations.shape[0])
    scale_x = float(packed_locations.shape[1]) / float(source_width)
    scale_y = float(map_height) / float(source_height)
    prepared_geometry = _prepare_geometry_frame(
        geometry,
        scale_x=scale_x,
        scale_y=scale_y,
        map_width=int(packed_locations.shape[1]),
        map_height=map_height,
    )
    return SavegameMapAssets(
        locations_png_path=locations_png,
        baseline_path=baseline_path,
        geometry_cache_path=cache_path,
        geometry=geometry,
        packed_locations=packed_locations,
        map_width=int(packed_locations.shape[1]),
        map_height=map_height,
        source_width=source_width,
        source_height=source_height,
        scale_x=scale_x,
        scale_y=scale_y,
        prepared_geometry=prepared_geometry,
    )


def population_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "current",
    relative_bounds: tuple[float, float] = DEFAULT_POPULATION_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    absolute_scale: str = DEFAULT_POPULATION_ABSOLUTE_SCALE,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> PopulationMapResult:
    """Pre-render population comparison map frames for a scoped notebook widget."""

    assets = getattr(data, "map_assets", None)
    if assets is None:
        raise RuntimeError(
            "Map assets are not loaded. Rerun the notebook loader with "
            "`data = nb.open_data(load_map_assets=True)`."
        )
    comparison = _normalize_population_comparison(comparison)
    result_relative_bounds = DEFAULT_POPULATION_DELTA_BOUNDS
    if comparison == "delta":
        low, high = _normalize_development_delta_bounds(relative_bounds)
        result_relative_bounds = (low, high)
    else:
        low, high = 0.0, 0.0
    absolute_scale = _normalize_population_absolute_scale(absolute_scale)
    metric = _normalize_population_metric(metric)
    locations = _population_locations(
        data,
        metric=metric,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    if locations.is_empty():
        return PopulationMapResult((), pl.DataFrame(), "", "", _normalize_scope(scope), name, metric, comparison, result_relative_bounds, 0, 0)

    normalized_scope = _normalize_scope(scope)
    filtered, resolved_name = _filter_scope(locations, normalized_scope, name)
    if filtered.is_empty():
        return PopulationMapResult((), pl.DataFrame(), "", "", normalized_scope, name, metric, comparison, result_relative_bounds, 0, 0)

    geometry = _prepared_geometry(assets)
    selected = filtered.join(geometry, left_on="slug", right_on="location_tag", how="left")
    selected = selected.with_columns(
        pl.col("map_color_int").is_not_null().alias("has_geometry"),
    )
    missing_geometry_locations = selected.filter(~pl.col("has_geometry")).select("slug").n_unique()
    mapped = selected.filter(pl.col("has_geometry")).sort(["date_sort", "slug"])
    if mapped.is_empty():
        return PopulationMapResult(
            (),
            selected,
            "",
            "",
            normalized_scope,
            resolved_name,
            metric,
            comparison,
            result_relative_bounds,
            0,
            int(missing_geometry_locations),
        )

    baseline_snapshot_id = ""
    baseline_date_label = ""
    if comparison == "delta":
        baseline = _resolve_baseline_snapshot(mapped, baseline_date)
        baseline_snapshot_id = str(baseline["snapshot_id"])
        baseline_date_label = str(baseline["date"])
        baseline_values = (
            mapped.filter(pl.col("snapshot_id") == baseline_snapshot_id)
            .select("slug", pl.col(metric).cast(pl.Float64).alias("baseline_value"))
            .unique("slug")
        )
        frame_data = (
            mapped.join(baseline_values, on="slug", how="left")
            .with_columns(
                _delta_expr(metric, "baseline_value").alias("population_delta"),
            )
            .sort(["date_sort", "slug"])
        )
        value_column = "population_delta"
        value_label = "population change"
        color_norm: Normalize | TwoSlopeNorm = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
        cmap = plt.get_cmap("RdYlGn")
        title = f"{resolved_name} population change vs {_year_label(baseline)}"
        subtitle_suffix = f"population delta, displayed {_format_population_thousands(low)}..{_format_population_thousands(high)}"
        legend_title = "Population change"
        legend_context = (("Baseline", _year_label(baseline)),)
        legend_unit = "population_thousands"
        legend_signed = True
    else:
        value_column = "population_map_value"
        frame_data = (
            mapped.with_columns(
                pl.col(metric).cast(pl.Float64).alias(value_column)
            )
            .sort(["date_sort", "slug"])
        )
        value_label = "current population"
        low, high = _normalize_positive_bounds(absolute_bounds or DEFAULT_POPULATION_ABSOLUTE_BOUNDS)
        color_norm = (
            Log1pNorm(vmin=low, vmax=high, clip=True)
            if absolute_scale == "log1p"
            else Normalize(vmin=low, vmax=high, clip=True)
        )
        cmap = plt.get_cmap("YlOrRd")
        title = f"{resolved_name} current population"
        scale_label = "log1p color scale" if absolute_scale == "log1p" else "linear color scale"
        subtitle_suffix = f"population, fixed {_format_population_thousands(low)}..{_format_population_thousands(high)}, {scale_label}"
        legend_title = "Population"
        legend_context = ()
        legend_unit = "population_thousands"
        legend_signed = False
    crop = _scope_crop(frame_data, assets, padding=18)
    target_width = width or assets.map_width
    render_width = min(max(int(target_width), 200), assets.map_width)
    render_cache = _build_render_cache(assets, crop=crop, frame_data=frame_data)

    frames: list[PopulationMapFrame] = []
    snapshots = frame_data.select(["snapshot_id", "date", "date_sort", "year"]).unique().sort("date_sort")
    snapshot_frames = _partition_snapshot_frames(frame_data)
    for index, snapshot in enumerate(snapshots.iter_rows(named=True)):
        snapshot_frame = snapshot_frames[str(snapshot["snapshot_id"])]
        rendered = _render_metric_frame(
            assets,
            snapshot_frame,
            value_column=value_column,
            crop=crop,
            render_cache=render_cache,
            render_width=render_width,
            color_norm=color_norm,
            cmap=cmap,
            title=title,
            subtitle=f"{_year_label(snapshot)} - {subtitle_suffix}",
            timeline=_timeline_for_snapshot(snapshots, index, snapshot),
            legend=_frame_legend(
                snapshot_frame,
                value_column=value_column,
                title=legend_title,
                date=_year_label(snapshot),
                context=legend_context,
                unit=legend_unit,
                signed=legend_signed,
            ),
        )
        frames.append(
            PopulationMapFrame(
                index=index,
                snapshot_id=str(snapshot["snapshot_id"]),
                date=str(snapshot["date"]),
                date_sort=int(snapshot["date_sort"]),
                year=int(snapshot["year"]),
                png=rendered["png"],
                image=rendered["image"],
            )
        )

    mapped_locations = frame_data.select("slug").n_unique()
    return PopulationMapResult(
        frames=tuple(frames),
        frame_data=frame_data,
        baseline_snapshot_id=baseline_snapshot_id,
        baseline_date=baseline_date_label,
        scope=normalized_scope,
        name=resolved_name,
        metric=metric,
        comparison=comparison,
        relative_bounds=result_relative_bounds,
        mapped_locations=int(mapped_locations),
        missing_geometry_locations=int(missing_geometry_locations),
        value_column=value_column,
        value_label=value_label,
        value_bounds=(low, high),
    )


def show_population_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "current",
    relative_bounds: tuple[float, float] = DEFAULT_POPULATION_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    absolute_scale: str = DEFAULT_POPULATION_ABSOLUTE_SCALE,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> PopulationMapResult:
    result = population_map(
        data,
        scope=scope,
        name=name,
        metric=metric,
        baseline_date=baseline_date,
        comparison=comparison,
        relative_bounds=relative_bounds,
        absolute_bounds=absolute_bounds,
        absolute_scale=absolute_scale,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    widget = population_map_widget(result, interval_ms=interval_ms) if display_widget else None
    if display_widget and widget is not None:
        display(widget)
    diagnostics = pl.DataFrame(
        [
            {
                "scope": result.scope,
                "name": result.name,
                "baseline_date": result.baseline_date,
                "frames": len(result.frames),
                "mapped_locations": result.mapped_locations,
                "missing_geometry_locations": result.missing_geometry_locations,
            }
        ]
    )
    if display_diagnostics:
        display(diagnostics)
    return PopulationMapResult(
        frames=result.frames,
        frame_data=result.frame_data,
        baseline_snapshot_id=result.baseline_snapshot_id,
        baseline_date=result.baseline_date,
        scope=result.scope,
        name=result.name,
        metric=result.metric,
        comparison=result.comparison,
        relative_bounds=result.relative_bounds,
        mapped_locations=result.mapped_locations,
        missing_geometry_locations=result.missing_geometry_locations,
        value_column=result.value_column,
        value_label=result.value_label,
        value_bounds=result.value_bounds,
        widget=widget,
    )


def development_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = DEFAULT_DEVELOPMENT_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> DevelopmentMapResult:
    """Pre-render scoped development map frames."""

    assets = getattr(data, "map_assets", None)
    if assets is None:
        raise RuntimeError(
            "Map assets are not loaded. Rerun the notebook loader with "
            "`data = nb.open_data(load_map_assets=True)`."
        )
    normalized_mode = _normalize_development_mode(mode)
    low, high = _normalize_development_delta_bounds(delta_bounds) if normalized_mode == "from_gamestart" else (0.0, 0.0)
    locations = _metric_locations(
        data,
        metric="development",
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        metric_label="Development",
    )
    if locations.is_empty():
        return DevelopmentMapResult((), pl.DataFrame(), "", "", _normalize_scope(scope), name, normalized_mode, "", "", (low, high), 0, 0)

    normalized_scope = _normalize_scope(scope)
    filtered, resolved_name = _filter_scope(locations, normalized_scope, name)
    if filtered.is_empty():
        return DevelopmentMapResult((), pl.DataFrame(), "", "", normalized_scope, name, normalized_mode, "", "", (low, high), 0, 0)

    geometry = _prepared_geometry(assets)
    selected = filtered.join(geometry, left_on="slug", right_on="location_tag", how="left")
    selected = selected.with_columns(
        pl.col("map_color_int").is_not_null().alias("has_geometry"),
    )
    missing_geometry_locations = selected.filter(~pl.col("has_geometry")).select("slug").n_unique()
    mapped = selected.filter(pl.col("has_geometry")).sort(["date_sort", "slug"])
    if mapped.is_empty():
        return DevelopmentMapResult(
            (),
            selected,
            "",
            "",
            normalized_scope,
            resolved_name,
            normalized_mode,
            "",
            "",
            (low, high),
            0,
            int(missing_geometry_locations),
        )

    baseline_snapshot_id = ""
    baseline_date_label = ""
    if normalized_mode == "from_gamestart":
        baseline = _resolve_baseline_snapshot(mapped, baseline_date)
        baseline_snapshot_id = str(baseline["snapshot_id"])
        baseline_date_label = str(baseline["date"])
        baseline_values = (
            mapped.filter(pl.col("snapshot_id") == baseline_snapshot_id)
            .select("slug", pl.col("development").cast(pl.Float64).alias("baseline_development"))
            .unique("slug")
        )
        frame_data = (
            mapped.join(baseline_values, on="slug", how="left")
            .with_columns(
                _delta_expr("development", "baseline_development").alias("development_delta"),
            )
            .with_columns(pl.col("development_delta").clip(low, high).alias("development_map_value"))
            .sort(["date_sort", "slug"])
        )
        value_column = "development_map_value"
        value_label = f"development change from {_year_label(baseline)} (points)"
        color_norm: Normalize | TwoSlopeNorm = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
        cmap = plt.get_cmap("BrBG")
        title = f"{resolved_name} development change vs {_year_label(baseline)}"
        subtitle_suffix = f"development point delta, clamped to {low:g}..{high:g}"
    else:
        frame_data = (
            mapped.with_columns(
                pl.col("development").cast(pl.Float64).alias("development_map_value")
            )
            .sort(["date_sort", "slug"])
        )
        low, high = _normalize_positive_bounds(absolute_bounds or DEFAULT_DEVELOPMENT_BOUNDS)
        value_column = "development_map_value"
        value_label = "current development"
        color_norm = Normalize(vmin=low, vmax=high, clip=True)
        cmap = plt.get_cmap("cividis")
        title = f"{resolved_name} current development"
        subtitle_suffix = f"development, fixed {low:g}..{high:g} scale"

    crop = _scope_crop(frame_data, assets, padding=18)
    target_width = width or assets.map_width
    render_width = min(max(int(target_width), 200), assets.map_width)
    render_cache = _build_render_cache(assets, crop=crop, frame_data=frame_data)

    frames: list[DevelopmentMapFrame] = []
    snapshots = frame_data.select(["snapshot_id", "date", "date_sort", "year"]).unique().sort("date_sort")
    snapshot_frames = _partition_snapshot_frames(frame_data)
    for index, snapshot in enumerate(snapshots.iter_rows(named=True)):
        snapshot_frame = snapshot_frames[str(snapshot["snapshot_id"])]
        rendered = _render_metric_frame(
            assets,
            snapshot_frame,
            value_column=value_column,
            crop=crop,
            render_cache=render_cache,
            render_width=render_width,
            color_norm=color_norm,
            cmap=cmap,
            title=title,
            subtitle=f"{_year_label(snapshot)} - {subtitle_suffix}",
            timeline=_timeline_for_snapshot(snapshots, index, snapshot),
            legend=_frame_legend(
                snapshot_frame,
                value_column=value_column,
                title="Development change" if normalized_mode == "from_gamestart" else "Development",
                date=_year_label(snapshot),
                context=((("Baseline", _year_from_date_label(baseline_date_label)),) if normalized_mode == "from_gamestart" else ()),
                unit="pts" if normalized_mode == "from_gamestart" else "",
                signed=normalized_mode == "from_gamestart",
            ),
        )
        frames.append(
            DevelopmentMapFrame(
                index=index,
                snapshot_id=str(snapshot["snapshot_id"]),
                date=str(snapshot["date"]),
                date_sort=int(snapshot["date_sort"]),
                year=int(snapshot["year"]),
                png=rendered["png"],
                image=rendered["image"],
            )
        )

    mapped_locations = frame_data.select("slug").n_unique()
    return DevelopmentMapResult(
        frames=tuple(frames),
        frame_data=frame_data,
        baseline_snapshot_id=baseline_snapshot_id,
        baseline_date=baseline_date_label,
        scope=normalized_scope,
        name=resolved_name,
        mode=normalized_mode,
        value_column=value_column,
        value_label=value_label,
        value_bounds=(low, high),
        mapped_locations=int(mapped_locations),
        missing_geometry_locations=int(missing_geometry_locations),
    )


def show_development_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = DEFAULT_DEVELOPMENT_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> DevelopmentMapResult:
    result = development_map(
        data,
        scope=scope,
        name=name,
        mode=mode,
        baseline_date=baseline_date,
        delta_bounds=delta_bounds,
        absolute_bounds=absolute_bounds,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    widget = development_map_widget(result, interval_ms=interval_ms) if display_widget else None
    if display_widget and widget is not None:
        display(widget)
    diagnostics = pl.DataFrame(
        [
            {
                "scope": result.scope,
                "name": result.name,
                "mode": result.mode,
                "baseline_date": result.baseline_date,
                "frames": len(result.frames),
                "mapped_locations": result.mapped_locations,
                "missing_geometry_locations": result.missing_geometry_locations,
            }
        ]
    )
    if display_diagnostics:
        display(diagnostics)
    return DevelopmentMapResult(
        frames=result.frames,
        frame_data=result.frame_data,
        baseline_snapshot_id=result.baseline_snapshot_id,
        baseline_date=result.baseline_date,
        scope=result.scope,
        name=result.name,
        mode=result.mode,
        value_column=result.value_column,
        value_label=result.value_label,
        value_bounds=result.value_bounds,
        mapped_locations=result.mapped_locations,
        missing_geometry_locations=result.missing_geometry_locations,
        widget=widget,
    )


def building_levels_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = DEFAULT_BUILDING_LEVEL_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> BuildingLevelsMapResult:
    assets = _require_map_assets(data)
    frame = _building_level_locations(
        data,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    return _scalar_location_map(
        assets,
        frame,
        scope=scope,
        name=name,
        metric="building_levels",
        mode=mode,
        baseline_date=baseline_date,
        delta_bounds=delta_bounds,
        absolute_bounds=absolute_bounds,
        width=width,
        title_metric="building levels",
        value_label_prefix="building levels",
        absolute_cmap="inferno",
        delta_cmap="PiYG",
        absolute_scale="fixed",
        delta_scale="fixed",
    )


def food_price_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    absolute_bounds: tuple[float, float] | None = DEFAULT_FOOD_PRICE_BOUNDS,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> FoodPriceMapResult:
    assets = _require_map_assets(data)
    frame = _food_price_locations(
        data,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    return _scalar_location_map(
        assets,
        frame,
        scope=scope,
        name=name,
        metric="food_price",
        mode="current",
        baseline_date=None,
        delta_bounds=None,
        absolute_bounds=absolute_bounds,
        width=width,
        title_metric="food price",
        value_label_prefix="food price",
        absolute_cmap="RdYlGn_r",
        delta_cmap="RdBu_r",
        absolute_scale="fixed",
        delta_scale="fixed",
    )


def political_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    country_colors: Mapping[str, object] | None = None,
) -> PoliticalMapResult:
    """Pre-render current owner-country map frames."""

    assets = _require_map_assets(data)
    locations = _political_locations(
        data,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    normalized_scope = _normalize_scope(scope)
    if locations.is_empty():
        return PoliticalMapResult((), pl.DataFrame(), normalized_scope, name or "", 0, 0)

    filtered, resolved_name = _filter_scope(locations, normalized_scope, name)
    if filtered.is_empty():
        return PoliticalMapResult((), pl.DataFrame(), normalized_scope, str(name or ""), 0, 0)

    geometry = _prepared_geometry(assets)
    selected = filtered.join(geometry, left_on="slug", right_on="location_tag", how="left")
    selected = selected.with_columns(pl.col("map_color_int").is_not_null().alias("has_geometry"))
    missing_geometry_locations = selected.filter(~pl.col("has_geometry")).select("slug").n_unique()
    mapped = selected.filter(pl.col("has_geometry")).sort(["date_sort", "slug"])
    if mapped.is_empty():
        return PoliticalMapResult(
            (),
            selected,
            normalized_scope,
            resolved_name,
            0,
            int(missing_geometry_locations),
        )

    color_map = _resolved_country_color_map(data, country_colors)
    frame_data = _with_political_colors(mapped, color_map).sort(["date_sort", "slug"])
    crop = _scope_crop(frame_data, assets, padding=18)
    target_width = width or assets.map_width
    render_width = min(max(int(target_width), 200), assets.map_width)
    render_cache = _build_render_cache(assets, crop=crop, frame_data=frame_data)

    frames: list[PopulationMapFrame] = []
    snapshots = frame_data.select(["snapshot_id", "date", "date_sort", "year"]).unique().sort("date_sort")
    snapshot_frames = _partition_snapshot_frames(frame_data)
    title = f"{resolved_name} political map"
    for index, snapshot in enumerate(snapshots.iter_rows(named=True)):
        snapshot_frame = snapshot_frames[str(snapshot["snapshot_id"])]
        rendered = _render_categorical_frame(
            assets,
            snapshot_frame,
            color_column="country_color_int",
            crop=crop,
            render_cache=render_cache,
            render_width=render_width,
            title=title,
            subtitle=f"{_year_label(snapshot)} - owner and overlord colors",
            timeline=_timeline_for_snapshot(snapshots, index, snapshot),
            legend=_political_frame_legend(
                snapshot_frame,
                date=_year_label(snapshot),
            ),
        )
        frames.append(
            PopulationMapFrame(
                index=index,
                snapshot_id=str(snapshot["snapshot_id"]),
                date=str(snapshot["date"]),
                date_sort=int(snapshot["date_sort"]),
                year=int(snapshot["year"]),
                png=rendered["png"],
                image=rendered["image"],
            )
        )

    return PoliticalMapResult(
        frames=tuple(frames),
        frame_data=frame_data,
        scope=normalized_scope,
        name=resolved_name,
        mapped_locations=int(frame_data.select("slug").n_unique()),
        missing_geometry_locations=int(missing_geometry_locations),
    )


def show_political_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    country_colors: Mapping[str, object] | None = None,
) -> PoliticalMapResult:
    result = political_map(
        data,
        scope=scope,
        name=name,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        country_colors=country_colors,
    )
    widget = political_map_widget(result, interval_ms=interval_ms) if display_widget else None
    if display_widget and widget is not None:
        display(widget)
    diagnostics = pl.DataFrame(
        [
            {
                "scope": result.scope,
                "name": result.name,
                "frames": len(result.frames),
                "mapped_locations": result.mapped_locations,
                "missing_geometry_locations": result.missing_geometry_locations,
                "value_label": result.value_label,
            }
        ]
    )
    if display_diagnostics:
        display(diagnostics)
    return PoliticalMapResult(
        frames=result.frames,
        frame_data=result.frame_data,
        scope=result.scope,
        name=result.name,
        mapped_locations=result.mapped_locations,
        missing_geometry_locations=result.missing_geometry_locations,
        value_column=result.value_column,
        value_label=result.value_label,
        widget=widget,
    )


def show_building_levels_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = DEFAULT_BUILDING_LEVEL_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> BuildingLevelsMapResult:
    result = building_levels_map(
        data,
        scope=scope,
        name=name,
        mode=mode,
        baseline_date=baseline_date,
        delta_bounds=delta_bounds,
        absolute_bounds=absolute_bounds,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    return _show_scalar_map_result(
        result,
        widget_factory=building_levels_map_widget,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
    )


def show_food_price_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str | None = None,
    absolute_bounds: tuple[float, float] | None = DEFAULT_FOOD_PRICE_BOUNDS,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> FoodPriceMapResult:
    result = food_price_map(
        data,
        scope=scope,
        name=name,
        absolute_bounds=absolute_bounds,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    return _show_scalar_map_result(
        result,
        widget_factory=food_price_map_widget,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
    )


def building_levels_map_widget(result: BuildingLevelsMapResult, *, interval_ms: int = 700) -> Any | None:
    if not result.frames:
        print("No building-level map frames")
        return None
    return _map_widget(
        result.frames,
        label_for_index=lambda index: _scalar_frame_label(result, index),
        interval_ms=interval_ms,
    )


def food_price_map_widget(result: FoodPriceMapResult, *, interval_ms: int = 700) -> Any | None:
    if not result.frames:
        print("No food-price map frames")
        return None
    return _map_widget(
        result.frames,
        label_for_index=lambda index: _scalar_frame_label(result, index),
        interval_ms=interval_ms,
    )


def political_map_widget(result: PoliticalMapResult, *, interval_ms: int = 700) -> Any | None:
    if not result.frames:
        print("No political map frames")
        return None
    return _map_widget(
        result.frames,
        label_for_index=lambda index: _political_frame_label(result, index),
        interval_ms=interval_ms,
    )


def development_map_widget(result: DevelopmentMapResult, *, interval_ms: int = 700) -> Any | None:
    if not result.frames:
        print("No development map frames")
        return None
    return _map_widget(
        result.frames,
        label_for_index=lambda index: _scalar_frame_label(result, index),
        interval_ms=interval_ms,
    )


def population_map_widget(result: PopulationMapResult, *, interval_ms: int = 700) -> Any | None:
    if not result.frames:
        print("No population map frames")
        return None
    return _map_widget(
        result.frames,
        label_for_index=lambda index: _population_frame_label(result, index),
        interval_ms=interval_ms,
    )


def _map_widget(
    frames: tuple[PopulationMapFrame, ...],
    *,
    label_for_index: Any,
    interval_ms: int,
) -> Any | None:
    if not frames:
        return None
    import ipywidgets as widgets

    image = widgets.Image(value=frames[0].png, format="png", layout=widgets.Layout(width="100%"))
    label = widgets.HTML(value=label_for_index(0))
    options = [(str(frame.year), frame.index) for frame in frames]
    slider = widgets.SelectionSlider(
        options=options,
        value=0,
        description="date",
        continuous_update=False,
        layout=widgets.Layout(width="100%"),
    )
    play = widgets.Play(
        value=0,
        min=0,
        max=len(frames) - 1,
        step=1,
        interval=max(int(interval_ms), 100),
        repeat=True,
        show_repeat=True,
        description="play",
    )
    widgets.jslink((play, "value"), (slider, "index"))

    def _on_change(change: dict[str, object]) -> None:
        if change.get("name") != "index":
            return
        index = int(change["new"])
        image.value = frames[index].png
        label.value = label_for_index(index)

    slider.observe(_on_change, names="index")
    return widgets.VBox([widgets.HBox([play]), slider, label, image])


def save_population_map_animation(
    result: PopulationMapResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str = "population_change.webp",
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> AnimationExportResult:
    """Write pre-rendered population map frames as an animated WebP or GIF."""

    return save_map_animation(
        result,
        path=path,
        output_dir=output_dir,
        filename=filename,
        duration_ms=duration_ms,
        loop=loop,
        quality=quality,
        lossless=lossless,
        width=width,
        max_bytes=max_bytes,
        overwrite=overwrite,
    )


def save_development_map_animation(
    result: DevelopmentMapResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str = "development_change.webp",
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> AnimationExportResult:
    return save_map_animation(
        result,
        path=path,
        output_dir=output_dir,
        filename=filename,
        duration_ms=duration_ms,
        loop=loop,
        quality=quality,
        lossless=lossless,
        width=width,
        max_bytes=max_bytes,
        overwrite=overwrite,
    )


def save_building_levels_map_animation(
    result: BuildingLevelsMapResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str = "building_levels_change.webp",
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> AnimationExportResult:
    return save_map_animation(
        result,
        path=path,
        output_dir=output_dir,
        filename=filename,
        duration_ms=duration_ms,
        loop=loop,
        quality=quality,
        lossless=lossless,
        width=width,
        max_bytes=max_bytes,
        overwrite=overwrite,
    )


def save_food_price_map_animation(
    result: FoodPriceMapResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str = "food_price_current.webp",
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> AnimationExportResult:
    return save_map_animation(
        result,
        path=path,
        output_dir=output_dir,
        filename=filename,
        duration_ms=duration_ms,
        loop=loop,
        quality=quality,
        lossless=lossless,
        width=width,
        max_bytes=max_bytes,
        overwrite=overwrite,
    )


def save_political_map_animation(
    result: PoliticalMapResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str = "political_current.webp",
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> AnimationExportResult:
    return save_map_animation(
        result,
        path=path,
        output_dir=output_dir,
        filename=filename,
        duration_ms=duration_ms,
        loop=loop,
        quality=quality,
        lossless=lossless,
        width=width,
        max_bytes=max_bytes,
        overwrite=overwrite,
    )


def save_map_animation(
    result: Any,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str,
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> AnimationExportResult:
    if not result.frames:
        raise ValueError("Cannot export an animation without map frames.")
    output_path = _animation_output_path(path=path, output_dir=output_dir, filename=filename)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Animation already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_frames = [_frame_image(frame) for frame in result.frames]
    animation_format = _animation_format(output_path)
    duration = max(int(duration_ms), 20)
    if animation_format == "webp":
        frames = _save_webp_animation_with_size_limit(
            source_frames,
            output_path,
            width=width,
            duration_ms=duration,
            loop=loop,
            quality=quality,
            lossless=lossless,
            max_bytes=max_bytes,
        )
    elif animation_format == "gif":
        frames = [_resize_animation_frame(frame, width=width) for frame in source_frames]
        _save_gif_animation(frames, output_path, duration_ms=duration, loop=loop)
    else:
        raise ValueError("Animation path must end in .webp or .gif.")
    return AnimationExportResult(
        path=output_path,
        format=animation_format,
        frames=len(frames),
        duration_ms=duration,
    )


def save_map_viewer(
    map_results: list[tuple[str, Any]] | tuple[tuple[str, Any], ...],
    *,
    path: str | Path = Path("graphs/savegame_notebooks/exports/savegame_maps.html"),
    frame_dir: str | Path = Path("viewer_frames"),
    width: int | None = None,
    quality: int = 94,
    lossless: bool = False,
    overwrite: bool = True,
    asset_links: Sequence[tuple[str, str | Path]] = (),
) -> MapViewerExportResult:
    output_path = Path(path)
    if not output_path.is_absolute():
        output_path = _repo_relative_path(output_path)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Map viewer already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame_root = Path(frame_dir)
    if not frame_root.is_absolute():
        frame_root = output_path.parent / frame_root
    frame_root.mkdir(parents=True, exist_ok=True)

    maps: list[dict[str, Any]] = []
    total_frames = 0
    for label, result in map_results:
        if not getattr(result, "frames", None):
            continue
        map_id = _slugify_identifier(label)
        map_dir = frame_root / map_id
        map_dir.mkdir(parents=True, exist_ok=True)
        for old_frame in map_dir.glob("*.webp"):
            old_frame.unlink()
        frames: list[dict[str, Any]] = []
        for frame in result.frames:
            frame_path = map_dir / f"{frame.index:03d}_{frame.year}.webp"
            image = _resize_animation_frame(_frame_image(frame), width=width)
            image.save(
                frame_path,
                format="WEBP",
                quality=max(1, min(int(quality), 100)),
                lossless=bool(lossless),
                method=4,
            )
            frames.append(
                {
                    "url": _viewer_relative_url(output_path, frame_path),
                    "year": int(frame.year),
                    "date": str(frame.date),
                    "index": int(frame.index),
                }
            )
        total_frames += len(frames)
        maps.append({"id": map_id, "label": str(label), "frames": frames})

    assets: list[dict[str, str]] = []
    for label, asset_path in asset_links:
        path_value = Path(asset_path)
        if not path_value.is_absolute():
            path_value = output_path.parent / path_value
        assets.append({"label": str(label), "url": _viewer_relative_url(output_path, path_value)})

    output_path.write_text(_map_viewer_html(maps, assets), encoding="utf-8")
    return MapViewerExportResult(
        path=output_path,
        frame_dir=frame_root,
        maps=tuple(str(item["label"]) for item in maps),
        frames=total_frames,
        assets=tuple(str(item["label"]) for item in assets),
    )


def _require_map_assets(data: Any) -> SavegameMapAssets:
    assets = getattr(data, "map_assets", None)
    if assets is None:
        raise RuntimeError(
            "Map assets are not loaded. Rerun the notebook loader with "
            "`data = nb.open_data(load_map_assets=True)`."
        )
    return assets


def _show_scalar_map_result(
    result: DevelopmentMapResult,
    *,
    widget_factory: Any,
    interval_ms: int,
    display_widget: bool,
    display_diagnostics: bool,
) -> DevelopmentMapResult:
    widget = widget_factory(result, interval_ms=interval_ms) if display_widget else None
    if display_widget and widget is not None:
        display(widget)
    diagnostics = pl.DataFrame(
        [
            {
                "scope": result.scope,
                "name": result.name,
                "mode": result.mode,
                "baseline_date": result.baseline_date,
                "frames": len(result.frames),
                "mapped_locations": result.mapped_locations,
                "missing_geometry_locations": result.missing_geometry_locations,
                "value_label": result.value_label,
            }
        ]
    )
    if display_diagnostics:
        display(diagnostics)
    return DevelopmentMapResult(
        frames=result.frames,
        frame_data=result.frame_data,
        baseline_snapshot_id=result.baseline_snapshot_id,
        baseline_date=result.baseline_date,
        scope=result.scope,
        name=result.name,
        mode=result.mode,
        value_column=result.value_column,
        value_label=result.value_label,
        value_bounds=result.value_bounds,
        mapped_locations=result.mapped_locations,
        missing_geometry_locations=result.missing_geometry_locations,
        widget=widget,
    )


def _resolve_cache_path(repo: Path, cache: str | Path | None) -> Path | None:
    if cache is None:
        return None
    path = Path(cache)
    return path if path.is_absolute() else repo / path


def _load_or_build_geometry(*, baseline_path: Path, locations_png_path: Path, cache_path: Path | None) -> pl.DataFrame:
    if cache_path is not None and cache_path.exists():
        return pl.read_parquet(cache_path)
    geometry = build_location_geometry_frame(
        baseline_path=baseline_path,
        locations_png_path=locations_png_path,
        equator_y=3340,
    )
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        geometry.write_parquet(cache_path)
    return geometry


def _load_packed_locations(locations_png_path: Path, *, map_width: int) -> tuple[np.ndarray, int, int]:
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(locations_png_path) as image:
        image = image.convert("RGB")
        source_width, source_height = image.size
        map_height = max(1, round(map_width * source_height / source_width))
        resized = image.resize((map_width, map_height), Image.Resampling.NEAREST)
        array = np.asarray(resized, dtype=np.uint32)
    packed = (array[:, :, 0] << 16) | (array[:, :, 1] << 8) | array[:, :, 2]
    return packed.astype(np.uint32, copy=False), source_width, source_height


def _prepared_geometry(assets: SavegameMapAssets) -> pl.DataFrame:
    if assets.prepared_geometry is not None:
        return assets.prepared_geometry
    return _prepare_geometry_frame(
        assets.geometry,
        scale_x=assets.scale_x,
        scale_y=assets.scale_y,
        map_width=assets.map_width,
        map_height=assets.map_height,
    )


def _prepare_geometry_frame(
    geometry: pl.DataFrame,
    *,
    scale_x: float,
    scale_y: float,
    map_width: int,
    map_height: int,
) -> pl.DataFrame:
    required = {"location_tag", "map_color_rgb", "geometry_status"}
    missing = required.difference(geometry.columns)
    if missing:
        raise ValueError(f"map geometry is missing columns: {', '.join(sorted(missing))}")
    columns = [
        "location_tag",
        "map_color_rgb",
        "geometry_status",
        *[column for column in ("bbox_min_x", "bbox_max_x", "bbox_min_y", "bbox_max_y") if column in geometry.columns],
    ]
    return (
        geometry.select(columns)
        .filter(pl.col("geometry_status") == "ok")
        .with_columns(
            pl.col("map_color_rgb")
            .map_elements(
                lambda value: int(str(value).strip().lower().removeprefix("#").zfill(6), 16),
                return_dtype=pl.UInt32,
            )
            .alias("map_color_int"),
            (pl.col("bbox_min_x").cast(pl.Float64) * scale_x).floor().cast(pl.Int64).clip(0, map_width - 1).alias("map_min_x"),
            (pl.col("bbox_max_x").cast(pl.Float64) * scale_x).ceil().cast(pl.Int64).clip(0, map_width - 1).alias("map_max_x"),
            (pl.col("bbox_min_y").cast(pl.Float64) * scale_y).floor().cast(pl.Int64).clip(0, map_height - 1).alias("map_min_y"),
            (pl.col("bbox_max_y").cast(pl.Float64) * scale_y).ceil().cast(pl.Int64).clip(0, map_height - 1).alias("map_max_y"),
        )
        .select("location_tag", "map_color_int", "map_min_x", "map_max_x", "map_min_y", "map_max_y")
        .unique("location_tag")
    )


def load_country_color_map(
    *,
    load_order_path: str | Path,
    profile: str = "constructor",
) -> dict[str, tuple[int, int, int]]:
    """Load country map colors from the configured EU5 setup data."""

    return dict(_load_country_color_map_cached(str(Path(load_order_path).expanduser()), profile))


@lru_cache(maxsize=8)
def _load_country_color_map_cached(load_order_path: str, profile: str) -> tuple[tuple[str, tuple[int, int, int]], ...]:
    profile_config = LoadOrderConfig.load(load_order_path).profile(profile)
    named_colors = _load_named_color_map(profile_config.layers)
    country_colors: dict[str, tuple[int, int, int]] = {}
    for layer in profile_config.layers:
        root = _country_setup_dir(layer)
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.txt")):
            for entry in parse_file(path).entries:
                if not isinstance(entry.value, CList):
                    continue
                tag = _normalized_setup_key(entry.key)
                if not tag:
                    continue
                rgb = _block_color(entry.value, "color", named_colors)
                if rgb is None:
                    continue
                country_colors[tag] = rgb
                country_colors[tag.upper()] = rgb
                country_colors[tag.lower()] = rgb
    return tuple(sorted(country_colors.items()))


def _load_named_color_map(layers: Sequence[GameLayer]) -> dict[str, tuple[int, int, int]]:
    colors: dict[str, tuple[int, int, int]] = {}
    for layer in layers:
        root = layer.common_dir_for("main_menu") / "named_colors"
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.txt")):
            for entry in parse_file(path).entries:
                if entry.key != "colors" or not isinstance(entry.value, CList):
                    continue
                colors.update(_colors_from_block(entry.value, colors))
    return colors


def _country_setup_dir(layer: GameLayer) -> Path:
    if layer.kind == "vanilla":
        return layer.root / "game" / "in_game" / "setup" / "countries"
    return layer.root / "in_game" / "setup" / "countries"


def _normalized_setup_key(key: str) -> str:
    text = str(key or "").strip()
    if ":" in text:
        text = text.split(":", 1)[1]
    return text


def _colors_from_block(
    block: CList,
    named_colors: Mapping[str, tuple[int, int, int]],
) -> dict[str, tuple[int, int, int]]:
    colors: dict[str, tuple[int, int, int]] = {}
    item_index = 0
    for entry in block.entries:
        value = entry.value
        if isinstance(value, str) and value in COLOR_CONSTRUCTORS:
            raw_values = _constructor_items(block, item_index)
            item_index += 1
            rgb = _color_constructor_rgb(value, raw_values)
            if rgb is not None:
                colors[entry.key] = rgb
        elif isinstance(value, str):
            resolved = colors.get(value) or named_colors.get(value)
            if resolved is not None:
                colors[entry.key] = resolved
    return colors


def _block_color(
    block: CList,
    key: str,
    named_colors: Mapping[str, tuple[int, int, int]],
) -> tuple[int, int, int] | None:
    item_index = 0
    for entry in block.entries:
        value = entry.value
        if isinstance(value, str) and value in COLOR_CONSTRUCTORS:
            raw_values = _constructor_items(block, item_index)
            item_index += 1
            if entry.key == key:
                return _color_constructor_rgb(value, raw_values)
        elif entry.key == key and isinstance(value, str):
            return named_colors.get(value) or _parse_hex_rgb(value)
    return None


def _constructor_items(block: CList, index: int) -> tuple[object, ...]:
    if index >= len(block.items):
        return ()
    item = block.items[index]
    if not isinstance(item, CList):
        return ()
    return tuple(item.items)


def _color_constructor_rgb(kind: str, values: Sequence[object]) -> tuple[int, int, int] | None:
    if len(values) < 3:
        return None
    try:
        first, second, third = (float(values[0]), float(values[1]), float(values[2]))
    except (TypeError, ValueError):
        return None
    if kind == "rgb":
        scale = 255.0 if max(abs(first), abs(second), abs(third)) <= 1.0 else 1.0
        return (
            _clamp_channel(first * scale),
            _clamp_channel(second * scale),
            _clamp_channel(third * scale),
        )
    if kind == "hsv360":
        hue = (first % 360.0) / 360.0
        saturation = _clamp_unit(second / 100.0)
        value = _clamp_unit(third / 100.0)
    else:
        hue = first % 1.0
        saturation = _clamp_unit(second)
        value = _clamp_unit(third)
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return (_clamp_channel(red * 255.0), _clamp_channel(green * 255.0), _clamp_channel(blue * 255.0))


def _normalize_country_color_map(colors: Mapping[str, object]) -> dict[str, tuple[int, int, int]]:
    normalized: dict[str, tuple[int, int, int]] = {}
    for key, value in colors.items():
        tag = str(key or "").strip()
        if not tag:
            continue
        rgb = _coerce_rgb(value)
        if rgb is None:
            continue
        normalized[tag] = rgb
        normalized[tag.upper()] = rgb
        normalized[tag.lower()] = rgb
    return normalized


def _coerce_rgb(value: object) -> tuple[int, int, int] | None:
    if isinstance(value, int):
        return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
    if isinstance(value, str):
        return _parse_hex_rgb(value)
    if isinstance(value, Sequence) and len(value) >= 3 and not isinstance(value, (bytes, bytearray, str)):
        try:
            red, green, blue = float(value[0]), float(value[1]), float(value[2])
        except (TypeError, ValueError):
            return None
        scale = 255.0 if max(abs(red), abs(green), abs(blue)) <= 1.0 else 1.0
        return (_clamp_channel(red * scale), _clamp_channel(green * scale), _clamp_channel(blue * scale))
    return None


def _parse_hex_rgb(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip().removeprefix("#")
    if len(text) != 6:
        return None
    try:
        packed = int(text, 16)
    except ValueError:
        return None
    return ((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF)


def _fallback_country_rgb(tag: str) -> tuple[int, int, int]:
    digest = hashlib.blake2b(str(tag).encode("utf-8"), digest_size=4).digest()
    raw = int.from_bytes(digest, "big")
    hue = (raw % 360) / 360.0
    saturation = 0.48 + ((raw >> 9) % 20) / 100.0
    value = 0.70 + ((raw >> 17) % 18) / 100.0
    red, green, blue = colorsys.hsv_to_rgb(hue, min(saturation, 0.72), min(value, 0.88))
    return (_clamp_channel(red * 255.0), _clamp_channel(green * 255.0), _clamp_channel(blue * 255.0))


def _pack_rgb(rgb: tuple[int, int, int]) -> int:
    return (_clamp_channel(rgb[0]) << 16) | (_clamp_channel(rgb[1]) << 8) | _clamp_channel(rgb[2])


def _clamp_channel(value: float | int) -> int:
    return max(0, min(255, int(round(float(value)))))


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _scalar_location_map(
    assets: SavegameMapAssets,
    locations: pl.DataFrame,
    *,
    scope: str,
    name: str | None,
    metric: str,
    mode: str,
    baseline_date: int | str | None,
    delta_bounds: tuple[float, float] | None,
    absolute_bounds: tuple[float, float] | None,
    width: int | None,
    title_metric: str,
    value_label_prefix: str,
    absolute_cmap: str,
    delta_cmap: str,
    absolute_scale: str,
    delta_scale: str,
) -> DevelopmentMapResult:
    normalized_mode = _normalize_development_mode(mode)
    normalized_scope = _normalize_scope(scope)
    if locations.is_empty() or metric not in locations.columns:
        return DevelopmentMapResult((), locations, "", "", normalized_scope, name, normalized_mode, "", "", (0.0, 0.0), 0, 0)
    filtered, resolved_name = _filter_scope(locations, normalized_scope, name)
    if filtered.is_empty():
        return DevelopmentMapResult((), pl.DataFrame(), "", "", normalized_scope, name, normalized_mode, "", "", (0.0, 0.0), 0, 0)

    geometry = _prepared_geometry(assets)
    selected = filtered.join(geometry, left_on="slug", right_on="location_tag", how="left")
    selected = selected.with_columns(pl.col("map_color_int").is_not_null().alias("has_geometry"))
    missing_geometry_locations = selected.filter(~pl.col("has_geometry")).select("slug").n_unique()
    mapped = selected.filter(pl.col("has_geometry")).sort(["date_sort", "slug"])
    if mapped.is_empty():
        return DevelopmentMapResult(
            (),
            selected,
            "",
            "",
            normalized_scope,
            resolved_name,
            normalized_mode,
            "",
            "",
            (0.0, 0.0),
            0,
            int(missing_geometry_locations),
        )

    baseline_snapshot_id = ""
    baseline_date_label = ""
    center_zero = False
    if normalized_mode == "from_gamestart":
        baseline = _resolve_baseline_snapshot(mapped, baseline_date)
        baseline_snapshot_id = str(baseline["snapshot_id"])
        baseline_date_label = str(baseline["date"])
        baseline_column = f"baseline_{metric}"
        delta_column = f"{metric}_delta"
        value_column = f"{metric}_map_value"
        baseline_values = (
            mapped.filter(pl.col("snapshot_id") == baseline_snapshot_id)
            .select("slug", pl.col(metric).cast(pl.Float64).alias(baseline_column))
            .unique("slug")
        )
        frame_data = (
            mapped.join(baseline_values, on="slug", how="left")
            .with_columns(
                _delta_expr(metric, baseline_column).alias(delta_column)
            )
            .sort(["date_sort", "slug"])
        )
        if delta_scale == "fixed":
            low, high = _normalize_development_delta_bounds(delta_bounds or DEFAULT_DEVELOPMENT_DELTA_BOUNDS)
            frame_data = frame_data.with_columns(pl.col(delta_column).clip(low, high).alias(value_column))
            color_norm: Normalize | TwoSlopeNorm | None = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
            value_bounds = (low, high)
            scale_label = f"clamped to {low:g}..{high:g}"
        else:
            frame_data = frame_data.with_columns(pl.col(delta_column).alias(value_column))
            color_norm = None
            center_zero = True
            value_bounds = _overall_bounds(frame_data, value_column)
            scale_label = "frame min-max scale centered on zero"
        cmap = plt.get_cmap(delta_cmap)
        value_label = f"{value_label_prefix} change from {_year_label(baseline)}"
        title = f"{resolved_name} {title_metric} change vs {_year_label(baseline)}"
        subtitle_suffix = f"{value_label}, {scale_label}"
    else:
        value_column = f"{metric}_map_value"
        frame_data = mapped.with_columns(pl.col(metric).cast(pl.Float64).alias(value_column)).sort(["date_sort", "slug"])
        if absolute_scale == "fixed":
            low, high = _normalize_positive_bounds(absolute_bounds or _default_absolute_bounds(metric))
            color_norm = Normalize(vmin=low, vmax=high, clip=True)
            value_bounds = (low, high)
            scale_label = f"fixed {low:g}..{high:g} scale"
        else:
            color_norm = None
            value_bounds = _overall_bounds(frame_data, value_column)
            scale_label = "frame min-max scale"
        cmap = plt.get_cmap(absolute_cmap)
        value_label = value_label_prefix
        title = f"{resolved_name} current {title_metric}"
        subtitle_suffix = f"{value_label}, {scale_label}"

    crop = _scope_crop(frame_data, assets, padding=18)
    target_width = width or assets.map_width
    render_width = min(max(int(target_width), 200), assets.map_width)
    render_cache = _build_render_cache(assets, crop=crop, frame_data=frame_data)
    frames: list[DevelopmentMapFrame] = []
    snapshots = frame_data.select(["snapshot_id", "date", "date_sort", "year"]).unique().sort("date_sort")
    snapshot_frames = _partition_snapshot_frames(frame_data)
    for index, snapshot in enumerate(snapshots.iter_rows(named=True)):
        snapshot_frame = snapshot_frames[str(snapshot["snapshot_id"])]
        rendered = _render_metric_frame(
            assets,
            snapshot_frame,
            value_column=value_column,
            crop=crop,
            render_cache=render_cache,
            render_width=render_width,
            color_norm=color_norm,
            cmap=cmap,
            title=title,
            subtitle=f"{_year_label(snapshot)} - {subtitle_suffix}",
            center_zero=center_zero,
            timeline=_timeline_for_snapshot(snapshots, index, snapshot),
            legend=_frame_legend(
                snapshot_frame,
                value_column=value_column,
                title=_legend_title(value_label_prefix, normalized_mode),
                date=_year_label(snapshot),
                context=((("Baseline", _year_from_date_label(baseline_date_label)),) if normalized_mode == "from_gamestart" else ()),
                unit=_legend_unit(metric, normalized_mode),
                signed=normalized_mode == "from_gamestart",
                show_total=metric != "food_price",
            ),
        )
        frames.append(
            DevelopmentMapFrame(
                index=index,
                snapshot_id=str(snapshot["snapshot_id"]),
                date=str(snapshot["date"]),
                date_sort=int(snapshot["date_sort"]),
                year=int(snapshot["year"]),
                png=rendered["png"],
                image=rendered["image"],
            )
        )

    return DevelopmentMapResult(
        frames=tuple(frames),
        frame_data=frame_data,
        baseline_snapshot_id=baseline_snapshot_id,
        baseline_date=baseline_date_label,
        scope=normalized_scope,
        name=resolved_name,
        mode=normalized_mode,
        value_column=value_column,
        value_label=value_label,
        value_bounds=value_bounds,
        mapped_locations=int(frame_data.select("slug").n_unique()),
        missing_geometry_locations=int(missing_geometry_locations),
    )


def _population_locations(
    data: Any,
    *,
    metric: str,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    return _metric_locations(
        data,
        metric=metric,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        metric_label="Population metric",
    )


def _metric_locations(
    data: Any,
    *,
    metric: str,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
    metric_label: str,
) -> pl.DataFrame:
    locations = data.table("locations")
    if locations.is_empty():
        return pl.DataFrame()
    if metric not in locations.columns:
        raise ValueError(f"{metric_label} {metric!r} is not available in the loaded locations table.")
    selected_playthrough = playthrough or getattr(data, "playthrough", None)
    if selected_playthrough is not None and "playthrough_id" in locations.columns:
        locations = locations.filter(pl.col("playthrough_id") == selected_playthrough)
    if start_date is not None:
        locations = locations.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None:
        locations = locations.filter(pl.col("date_sort") <= int(end_date))
    dim_locations = data.dim("locations")
    geo_columns = [
        column
        for column in (
            "location_code",
            "slug",
            "location_label",
            "area",
            "area_label",
            "region",
            "region_label",
            "macro_region",
            "macro_region_label",
            "super_region",
            "super_region_label",
        )
        if column in dim_locations.columns
    ]
    if "location_code" in locations.columns and geo_columns:
        locations = locations.join(dim_locations.select(geo_columns), on="location_code", how="left")
    return locations


def _building_level_locations(
    data: Any,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    base = _metric_locations(
        data,
        metric="development",
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        metric_label="Development",
    )
    if base.is_empty():
        return pl.DataFrame()
    snapshot_columns = ["snapshot_id", "date", "date_sort", "year", "location_code"]
    geo_columns = [
        column
        for column in (
            "slug",
            "location_label",
            "area",
            "area_label",
            "region",
            "region_label",
            "macro_region",
            "macro_region_label",
            "super_region",
            "super_region_label",
        )
        if column in base.columns
    ]
    base = (
        base.select([*snapshot_columns, "development", *geo_columns])
        .unique()
        .with_columns(pl.col("development").is_not_null().alias("has_location_data"))
    )
    buildings = data.table("buildings")
    if buildings.is_empty() or not {"snapshot_id", "location_code", "level"}.issubset(buildings.columns):
        return base.with_columns(
            pl.when(pl.col("has_location_data"))
            .then(pl.lit(0.0))
            .otherwise(None)
            .cast(pl.Float64)
            .alias("building_levels")
        )
    selected_playthrough = playthrough or getattr(data, "playthrough", None)
    if selected_playthrough is not None and "playthrough_id" in buildings.columns:
        buildings = buildings.filter(pl.col("playthrough_id") == selected_playthrough)
    if start_date is not None:
        buildings = buildings.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None:
        buildings = buildings.filter(pl.col("date_sort") <= int(end_date))
    levels = (
        buildings.group_by(["snapshot_id", "location_code"])
        .agg(pl.sum("level").cast(pl.Float64).alias("building_levels"))
    )
    return base.join(levels, on=["snapshot_id", "location_code"], how="left").with_columns(
        pl.when(pl.col("has_location_data"))
        .then(pl.col("building_levels").fill_null(0.0))
        .otherwise(None)
        .cast(pl.Float64)
        .alias("building_levels")
    )


def _food_price_locations(
    data: Any,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    locations = _metric_locations(
        data,
        metric="development",
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        metric_label="Development",
    )
    if locations.is_empty() or "market_code" not in locations.columns:
        return pl.DataFrame()
    prices = data.table("market_food")
    if prices.is_empty() or not {"snapshot_id", "market_code", "food_price"}.issubset(prices.columns):
        return locations.with_columns(pl.lit(None, dtype=pl.Float64).alias("food_price"))
    selected_playthrough = playthrough or getattr(data, "playthrough", None)
    if selected_playthrough is not None and "playthrough_id" in prices.columns:
        prices = prices.filter(pl.col("playthrough_id") == selected_playthrough)
    if start_date is not None and "date_sort" in prices.columns:
        prices = prices.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in prices.columns:
        prices = prices.filter(pl.col("date_sort") <= int(end_date))
    price_by_market = (
        prices.filter(pl.col("food_price").is_not_null())
        .group_by(["snapshot_id", "market_code"])
        .agg(pl.mean("food_price").cast(pl.Float64).alias("food_price"))
    )
    result = locations.join(price_by_market, on=["snapshot_id", "market_code"], how="left")
    markets = data.dim("markets")
    if not markets.is_empty() and {"market_code", "market_label"}.issubset(markets.columns):
        result = result.join(
            markets.select(["market_code", "market_label"]).unique("market_code"),
            on="market_code",
            how="left",
        )
    return result


def _political_locations(
    data: Any,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    locations = data.table("locations")
    if locations.is_empty():
        return pl.DataFrame()
    selected_playthrough = playthrough or getattr(data, "playthrough", None)
    if selected_playthrough is not None and "playthrough_id" in locations.columns:
        locations = locations.filter(pl.col("playthrough_id") == selected_playthrough)
    if start_date is not None and "date_sort" in locations.columns:
        locations = locations.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in locations.columns:
        locations = locations.filter(pl.col("date_sort") <= int(end_date))

    dim_locations = data.dim("locations")
    geo_columns = [
        column
        for column in (
            "location_code",
            "slug",
            "location_label",
            "area",
            "area_label",
            "region",
            "region_label",
            "macro_region",
            "macro_region_label",
            "super_region",
            "super_region_label",
        )
        if column in dim_locations.columns
    ]
    if "location_code" in locations.columns and geo_columns:
        locations = locations.join(dim_locations.select(geo_columns), on="location_code", how="left")

    countries = data.dim("countries")
    if not countries.is_empty():
        country_columns = [
            column
            for column in ("country_code", "country_tag", "country_name", "country_label")
            if column in countries.columns
        ]
        if "country_code" in locations.columns and "country_code" in country_columns:
            locations = locations.join(countries.select(country_columns).unique("country_code"), on="country_code", how="left")
        elif "country_tag" in locations.columns and "country_tag" in country_columns:
            missing_labels = [column for column in ("country_name", "country_label") if column not in locations.columns and column in country_columns]
            if missing_labels:
                locations = locations.join(
                    countries.select(["country_tag", *missing_labels]).unique("country_tag"),
                    on="country_tag",
                    how="left",
                )

    if "country_name" not in locations.columns and "owner_name" in locations.columns:
        locations = locations.with_columns(pl.col("owner_name").alias("country_name"))
    if "country_tag" not in locations.columns:
        locations = locations.with_columns(pl.lit(None, dtype=pl.String).alias("country_tag"))
    if "country_name" not in locations.columns:
        locations = locations.with_columns(pl.col("country_tag").alias("country_name"))
    locations = _join_political_country_facts(
        data,
        locations,
        playthrough=selected_playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    return _with_political_color_sources(locations)


def _join_political_country_facts(
    data: Any,
    locations: pl.DataFrame,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    countries = data.table("countries")
    if countries.is_empty() or locations.is_empty() or "snapshot_id" not in locations.columns:
        return locations
    if playthrough is not None and "playthrough_id" in countries.columns:
        countries = countries.filter(pl.col("playthrough_id") == playthrough)
    if start_date is not None and "date_sort" in countries.columns:
        countries = countries.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in countries.columns:
        countries = countries.filter(pl.col("date_sort") <= int(end_date))
    if countries.is_empty() or "snapshot_id" not in countries.columns:
        return locations

    join_key = None
    for candidate in ("country_code", "country_tag"):
        if candidate in locations.columns and candidate in countries.columns:
            join_key = candidate
            break
    if join_key is None:
        return locations

    fact_columns = [
        column
        for column in (
            "snapshot_id",
            join_key,
            "country_id",
            "overlord_country_id",
            "overlord_tag",
            "overlord_name",
            "subject_type",
            "is_subject",
            "is_colony",
        )
        if column in countries.columns
    ]
    relation_columns = [column for column in fact_columns if column not in {"snapshot_id", join_key}]
    if not relation_columns:
        return locations
    facts = countries.select(fact_columns).unique(["snapshot_id", join_key])
    return locations.join(facts, on=["snapshot_id", join_key], how="left")


def _with_political_color_sources(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    additions: list[pl.Expr] = []
    for column in ("overlord_tag", "overlord_name", "subject_type"):
        if column not in frame.columns:
            additions.append(pl.lit(None, dtype=pl.String).alias(column))
    for column in ("is_subject", "is_colony"):
        if column not in frame.columns:
            additions.append(pl.lit(False, dtype=pl.Boolean).alias(column))
    if additions:
        frame = frame.with_columns(additions)

    has_overlord = (
        pl.col("is_subject").fill_null(False)
        & pl.col("overlord_tag").is_not_null()
        & (pl.col("overlord_tag").cast(pl.String) != "")
    )
    return frame.with_columns(
        pl.when(has_overlord)
        .then(pl.col("overlord_tag").cast(pl.String))
        .otherwise(pl.col("country_tag").cast(pl.String))
        .alias("political_color_tag")
    )


def _resolved_country_color_map(data: Any, country_colors: Mapping[str, object] | None) -> dict[str, tuple[int, int, int]]:
    normalized = _normalize_country_color_map(country_colors or {})
    if normalized:
        return normalized
    load_order_path = getattr(data, "load_order_path", None)
    profile = getattr(data, "profile", None)
    if load_order_path is None or profile is None:
        return {}
    try:
        return load_country_color_map(load_order_path=Path(load_order_path), profile=str(profile))
    except Exception:
        return {}


def _with_political_colors(frame: pl.DataFrame, country_colors: Mapping[str, tuple[int, int, int]]) -> pl.DataFrame:
    if frame.is_empty():
        return frame

    def _country_rgb(tag: object) -> tuple[int, int, int] | None:
        text = str(tag or "").strip()
        if not text:
            return None
        rgb = country_colors.get(text) or country_colors.get(text.upper()) or country_colors.get(text.lower())
        if rgb is None:
            rgb = _fallback_country_rgb(text)
        return rgb

    def _packed_political_color(row: dict[str, object]) -> int | None:
        color_tag = str(row.get("political_color_tag") or "").strip()
        owner_tag = str(row.get("country_tag") or "").strip()
        if not color_tag:
            color_tag = owner_tag
        rgb = _country_rgb(color_tag)
        if rgb is None:
            return None
        if owner_tag and color_tag and owner_tag.lower() != color_tag.lower():
            rgb = _subject_variant_rgb(rgb, owner_tag, str(row.get("subject_type") or ""))
        return _pack_rgb(rgb)

    def _hex_color(packed: object) -> str:
        if packed is None:
            return ""
        try:
            value = int(packed)
        except (TypeError, ValueError):
            return ""
        if value < 0:
            return ""
        return f"#{value:06x}"

    def _subject_type_label(value: object) -> str:
        text = str(value or "").strip().replace("_", " ")
        return text or "subject"

    if "political_color_tag" not in frame.columns:
        frame = _with_political_color_sources(frame)
    for column in ("overlord_tag", "overlord_name", "subject_type", "is_subject"):
        if column not in frame.columns:
            frame = _with_political_color_sources(frame)
            break

    label_column = _country_label_column(frame)
    label_expr = (
        pl.when(pl.col(label_column).is_not_null() & (pl.col(label_column).cast(pl.String) != ""))
        .then(pl.col(label_column).cast(pl.String))
        .otherwise(pl.col("country_tag").cast(pl.String))
        if label_column is not None
        else pl.col("country_tag").cast(pl.String)
    )
    frame = frame.with_columns(label_expr.alias("country_label"))

    overlord_label_expr = (
        pl.when(pl.col("overlord_name").is_not_null() & (pl.col("overlord_name").cast(pl.String) != ""))
        .then(pl.col("overlord_name").cast(pl.String))
        .otherwise(pl.col("overlord_tag").cast(pl.String))
    )
    subject_label_expr = pl.col("subject_type").map_elements(_subject_type_label, return_dtype=pl.String)
    subject_has_overlord = (
        pl.col("is_subject").fill_null(False)
        & pl.col("overlord_tag").is_not_null()
        & (pl.col("overlord_tag").cast(pl.String) != "")
    )
    frame = frame.with_columns(
        pl.when(subject_has_overlord)
        .then(pl.format("{} ({} of {})", pl.col("country_label"), subject_label_expr, overlord_label_expr))
        .otherwise(pl.col("country_label"))
        .alias("political_color_label")
    )
    frame = frame.with_columns(
        pl.struct(["political_color_tag", "country_tag", "subject_type"])
        .map_elements(_packed_political_color, return_dtype=pl.UInt32)
        .alias("country_color_int")
    )
    return frame.with_columns(
        pl.col("country_color_int")
        .map_elements(_hex_color, return_dtype=pl.String)
        .alias("country_color_hex")
    )


def _subject_variant_rgb(
    overlord_rgb: tuple[int, int, int],
    subject_tag: str,
    subject_type: str,
) -> tuple[int, int, int]:
    digest = hashlib.blake2b(
        f"{subject_tag}:{subject_type}".encode("utf-8"),
        digest_size=2,
    ).digest()
    base = np.array(overlord_rgb, dtype=np.float64)
    colonial = subject_type == "colonial_nation"
    lighten = bool(digest[0] & 1) or colonial
    factor = (0.28 if colonial else 0.16) + (digest[1] % 4) * 0.035
    target = np.array([255.0, 255.0, 255.0] if lighten else [24.0, 24.0, 24.0])
    mixed = base * (1.0 - factor) + target * factor
    return tuple(int(round(value)) for value in mixed.clip(0, 255))


def _country_label_column(frame: pl.DataFrame) -> str | None:
    for column in ("country_label", "country_name", "owner_name"):
        if column in frame.columns:
            return column
    return None


def _filter_scope(frame: pl.DataFrame, scope: str, name: str | None) -> tuple[pl.DataFrame, str]:
    if _is_world_name(name):
        return _world_land_frame(frame), "World"
    columns = [column for column in GEOGRAPHY_SCOPE_SEARCH_COLUMNS[scope] if column in frame.columns]
    if not columns:
        return frame.head(0), str(name or "")
    query = str(name).strip().lower()
    candidates = frame.select(columns).unique()
    for row in candidates.iter_rows(named=True):
        label = str(row.get(f"{scope}_label") or row.get("location_label") or next(iter(row.values())) or "")
        for column in columns:
            value = row.get(column)
            if value is None:
                continue
            text = str(value)
            normalized = text.lower()
            if normalized == query or normalized.startswith(query) or query in normalized:
                return frame.filter(pl.col(column).cast(pl.String).str.to_lowercase() == normalized), label
    return frame.head(0), str(name or "")


def _is_world_name(name: str | None) -> bool:
    if name is None:
        return True
    return str(name).strip().lower().replace("-", "_") in {"", "world", "global", "all"}


def _world_land_frame(frame: pl.DataFrame) -> pl.DataFrame:
    ocean_columns = [column for column in ("super_region", "macro_region", "region") if column in frame.columns]
    if not ocean_columns:
        return frame
    ocean_exprs = [
        pl.col(column)
        .cast(pl.String)
        .str.to_lowercase()
        .fill_null("")
        .str.contains("_ocean")
        for column in ocean_columns
    ]
    return frame.filter(~pl.any_horizontal(ocean_exprs))


def _resolve_baseline_snapshot(frame: pl.DataFrame, baseline_date: int | str | None) -> dict[str, object]:
    snapshots = frame.select(["snapshot_id", "date", "date_sort", "year"]).unique().sort("date_sort")
    if snapshots.is_empty():
        raise ValueError("No snapshots are available for the selected map.")
    if baseline_date is None:
        return snapshots.row(0, named=True)
    if isinstance(baseline_date, int):
        matches = snapshots.filter(pl.col("date_sort") == int(baseline_date))
    else:
        text = str(baseline_date)
        matches = snapshots.filter((pl.col("date") == text) | (pl.col("snapshot_id") == text))
    if matches.is_empty():
        valid = ", ".join(str(value) for value in snapshots.get_column("date").to_list())
        raise ValueError(f"Baseline snapshot {baseline_date!r} was not found. Available dates: {valid}")
    return matches.row(0, named=True)


def _relative_change_expr(metric: str, *, low: float, high: float) -> pl.Expr:
    current = pl.col(metric).cast(pl.Float64).fill_null(0.0)
    baseline = pl.col("baseline_value").cast(pl.Float64).fill_null(0.0)
    return (
        pl.when(baseline == 0.0)
        .then(pl.when(current == 0.0).then(0.0).otherwise(high))
        .otherwise(((current - baseline) / baseline * 100.0).clip(low, high))
    )


def _delta_expr(current_column: str, baseline_column: str) -> pl.Expr:
    current = pl.col(current_column).cast(pl.Float64)
    baseline = pl.col(baseline_column).cast(pl.Float64)
    return pl.when(current.is_null() | baseline.is_null()).then(None).otherwise(current - baseline)


def _scope_crop(frame: pl.DataFrame, assets: SavegameMapAssets, *, padding: int) -> tuple[int, int, int, int]:
    if frame.is_empty() or not {"map_min_x", "map_max_x", "map_min_y", "map_max_y"}.issubset(frame.columns):
        return (0, 0, assets.map_width, assets.map_height)
    x0 = max(0, int(frame.get_column("map_min_x").min()) - padding)
    x1 = min(assets.map_width, int(frame.get_column("map_max_x").max()) + padding + 1)
    y0 = max(0, int(frame.get_column("map_min_y").min()) - padding)
    y1 = min(assets.map_height, int(frame.get_column("map_max_y").max()) + padding + 1)
    if x1 <= x0 or y1 <= y0:
        return (0, 0, assets.map_width, assets.map_height)
    return (x0, y0, x1, y1)


def _frame_legend(
    frame: pl.DataFrame,
    *,
    value_column: str,
    title: str,
    date: str,
    context: tuple[tuple[str, str], ...] = (),
    unit: str = "",
    signed: bool = False,
    total_value_column: str | None = None,
    baseline_value_column: str | None = None,
    show_total: bool = True,
) -> MapFrameLegend:
    rows: list[tuple[str, str]] = [("Date", date), *context]
    if frame.is_empty() or value_column not in frame.columns:
        rows.append(("Locations", "0"))
        return MapFrameLegend(title=title, rows=tuple(rows), unit=unit, signed=signed)

    values_frame = frame.select(pl.col(value_column).cast(pl.Float64).alias("value"))
    no_data_count = int(values_frame.filter(pl.col("value").is_null() | pl.col("value").is_nan()).height)
    raw_values = values_frame.drop_nulls().get_column("value").to_list()
    values = np.array(raw_values, dtype=np.float64)
    finite = values[np.isfinite(values)]
    rows.append(("Locations", f"{finite.size:,}"))
    if no_data_count:
        rows.append(("No data", f"{no_data_count:,}"))
    if finite.size:
        stat_rows = [
            ("Mean", _format_stat_value(float(finite.mean()), unit=unit, signed=signed)),
            ("Median", _format_stat_value(float(np.median(finite)), unit=unit, signed=signed)),
            ("Stdev", _format_stat_value(float(finite.std()), unit=unit, signed=signed)),
            ("Min", _format_stat_value(float(finite.min()), unit=unit, signed=signed)),
            ("Max", _format_stat_value(float(finite.max()), unit=unit, signed=signed)),
        ]
        if show_total:
            stat_rows.insert(0, ("Total", _format_stat_value(float(finite.sum()), unit=unit, signed=signed)))
        rows.extend(stat_rows)
    region_value_header = "Total" if show_total else "Stdev"
    region_rows = _super_region_legend_rows(
        frame,
        value_column=value_column,
        unit=unit,
        signed=signed,
        total_value_column=total_value_column,
        baseline_value_column=baseline_value_column,
        show_total=show_total,
    )
    return MapFrameLegend(
        title=title,
        rows=tuple(rows),
        region_rows=region_rows,
        region_value_header=region_value_header,
        unit=unit,
        signed=signed,
    )


def _political_frame_legend(
    frame: pl.DataFrame,
    *,
    date: str,
    limit: int = 14,
) -> MapFrameLegend:
    rows: list[tuple[str, str]] = [("Date", date)]
    if frame.is_empty() or "country_tag" not in frame.columns:
        rows.extend((("Locations", "0"), ("Countries", "0")))
        return MapFrameLegend(title="Political ownership", rows=tuple(rows))

    no_data = int(frame.filter(pl.col("country_tag").is_null() | (pl.col("country_tag").cast(pl.String) == "")).height)
    owned = frame.filter(pl.col("country_tag").is_not_null() & (pl.col("country_tag").cast(pl.String) != ""))
    country_count = owned.select("country_tag").n_unique() if not owned.is_empty() else 0
    rows.append(("Locations", f"{owned.height:,}"))
    rows.append(("Countries", f"{int(country_count):,}"))
    if "is_subject" in owned.columns:
        subjects = int(owned.filter(pl.col("is_subject").fill_null(False)).select("country_tag").n_unique())
        if subjects:
            rows.append(("Subjects", f"{subjects:,}"))
    if "is_colony" in owned.columns:
        colonies = int(owned.filter(pl.col("is_colony").fill_null(False)).select("country_tag").n_unique())
        if colonies:
            rows.append(("Colonies", f"{colonies:,}"))
    if no_data:
        rows.append(("No data", f"{no_data:,}"))

    swatches: tuple[tuple[str, str, str], ...] = ()
    required = {"country_tag", "country_label", "country_color_hex"}
    if required.issubset(frame.columns) and not owned.is_empty():
        label_column = "political_color_label" if "political_color_label" in owned.columns else "country_label"
        swatch_frame = (
            owned.group_by(["country_tag", label_column, "country_color_hex"])
            .agg(pl.len().alias("locations"))
            .sort(["locations", label_column], descending=[True, False])
            .head(limit)
        )
        swatches = tuple(
            (
                str(row[label_column] or row["country_tag"]),
                f"{int(row['locations']):,}",
                str(row["country_color_hex"] or ""),
            )
            for row in swatch_frame.iter_rows(named=True)
        )

    return MapFrameLegend(
        title="Political ownership",
        rows=tuple(rows),
        swatch_rows=swatches,
        swatch_title="Largest countries",
    )


def _super_region_legend_rows(
    frame: pl.DataFrame,
    *,
    value_column: str,
    unit: str,
    signed: bool,
    total_value_column: str | None = None,
    baseline_value_column: str | None = None,
    show_total: bool = True,
    limit: int = 6,
) -> tuple[tuple[str, str, str, str, str, str], ...]:
    if frame.is_empty() or value_column not in frame.columns or "super_region" not in frame.columns:
        return ()
    label_expr = (
        pl.when(pl.col("super_region_label").is_not_null() & (pl.col("super_region_label").cast(pl.String) != ""))
        .then(pl.col("super_region_label").cast(pl.String))
        .otherwise(pl.col("super_region").cast(pl.String).map_elements(_title_from_key, return_dtype=pl.String))
        if "super_region_label" in frame.columns
        else pl.col("super_region").cast(pl.String).map_elements(_title_from_key, return_dtype=pl.String)
    )
    selected = frame.select(
        label_expr.alias("region_label"),
        pl.col(value_column).cast(pl.Float64).alias("value"),
    ).drop_nulls("value")
    aggregations: list[pl.Expr] = [
        pl.len().alias("locations"),
        pl.sum("value").alias("total"),
        pl.mean("value").alias("mean"),
        pl.median("value").alias("median"),
        pl.col("value").std(ddof=0).fill_null(0.0).alias("stddev"),
        pl.min("value").alias("min"),
        pl.max("value").alias("max"),
    ]
    stats = selected.group_by("region_label").agg(aggregations)
    stats = (
        stats
        .sort(["locations", "region_label"], descending=[True, False])
        .head(limit)
    )
    return tuple(
        (
            _compact_region_label(str(row["region_label"])),
            _format_stat_value(float(row["total" if show_total else "stddev"]), unit=unit, signed=signed),
            _format_stat_value(float(row["mean"]), unit=unit, signed=signed),
            _format_stat_value(float(row["median"]), unit=unit, signed=signed),
            _format_stat_value(float(row["min"]), unit=unit, signed=signed),
            _format_stat_value(float(row["max"]), unit=unit, signed=signed),
        )
        for row in stats.iter_rows(named=True)
    )


def _relative_change_from_totals_expr(current_column: str, baseline_column: str) -> pl.Expr:
    current = pl.col(current_column).cast(pl.Float64).fill_null(0.0)
    baseline = pl.col(baseline_column).cast(pl.Float64).fill_null(0.0)
    return (
        pl.when((baseline == 0.0) & (current == 0.0))
        .then(0.0)
        .when(baseline == 0.0)
        .then(300.0)
        .otherwise((current - baseline) / baseline * 100.0)
    )


def _title_from_key(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(part.capitalize() for part in text.replace("-", "_").split("_") if part)


def _compact_region_label(label: str) -> str:
    aliases = {
        "America": "Americas",
        "North America": "N. America",
        "South America": "S. America",
        "Atlantic Ocean": "Atlantic",
        "Indian Ocean": "Indian",
        "Pacific Ocean": "Pacific",
        "Antarctic Ocean": "Antarctic",
    }
    text = aliases.get(label, label)
    return text if len(text) <= 18 else f"{text[:17].rstrip()}."


def _legend_title(value_label_prefix: str, mode: str) -> str:
    label = value_label_prefix.strip().capitalize()
    return f"{label} change" if mode == "from_gamestart" else label


def _legend_unit(metric: str, mode: str) -> str:
    if metric == "building_levels":
        return "levels"
    if metric == "food_price":
        return "price"
    if mode == "from_gamestart":
        return "pts"
    return ""


def _format_stat_value(value: float, *, unit: str, signed: bool) -> str:
    if unit == "population_thousands":
        return _format_population_thousands(value, signed=signed)
    prefix = "+" if signed and value > 0.0 else ""
    if unit == "price":
        if abs(value) < 0.001:
            value = 0.0
        return f"{prefix}{value:,.3f}"
    text = f"{prefix}{value:,.1f}"
    if unit == "%":
        return f"{text}%"
    if unit:
        return f"{text} {unit}"
    return text


def _format_population_thousands(value: float, *, signed: bool = False) -> str:
    absolute = abs(value)
    prefix = "+" if signed and value > 0.0 else ""
    if absolute >= 1000.0:
        return f"{prefix}{value / 1000.0:,.1f}M"
    if absolute >= 10.0:
        return f"{prefix}{value:,.0f}k"
    if absolute > 0.0:
        return f"{prefix}{value:,.1f}k"
    return "0"


def _partition_snapshot_frames(frame_data: pl.DataFrame) -> dict[str, pl.DataFrame]:
    groups: dict[str, pl.DataFrame] = {}
    if frame_data.is_empty() or "snapshot_id" not in frame_data.columns:
        return groups
    for part in frame_data.partition_by("snapshot_id", maintain_order=True):
        if part.is_empty():
            continue
        groups[str(part.get_column("snapshot_id")[0])] = part
    return groups


def _timeline_for_snapshot(snapshots: pl.DataFrame, index: int, snapshot: dict[str, object]) -> RenderTimeline:
    years = snapshots.get_column("year").cast(pl.Int64).to_list() if "year" in snapshots.columns else [int(index)]
    start_year = int(min(years)) if years else int(index)
    end_year = int(max(years)) if years else int(index)
    return RenderTimeline(
        index=int(index),
        count=int(snapshots.height),
        year=int(snapshot.get("year") or start_year),
        start_year=start_year,
        end_year=end_year,
    )


def _year_label(snapshot: dict[str, object]) -> str:
    year = snapshot.get("year")
    if year is not None:
        return str(int(year))
    return _year_from_date_label(str(snapshot.get("date") or ""))


def _year_from_date_label(date: str) -> str:
    text = str(date or "").strip()
    return text.split(".", 1)[0] if "." in text else text


def _build_render_cache(
    assets: SavegameMapAssets,
    *,
    crop: tuple[int, int, int, int],
    frame_data: pl.DataFrame,
) -> MapRenderCache:
    x0, y0, x1, y1 = crop
    packed = assets.packed_locations[y0:y1, x0:x1]
    base_rgb = np.empty((*packed.shape, 3), dtype=np.uint8)
    base_rgb[:, :] = DEFAULT_BACKGROUND
    land_mask = packed != 0
    base_rgb[land_mask] = DEFAULT_UNSELECTED
    flat = packed.reshape(-1)
    hatch_y, hatch_x = np.indices(packed.shape)
    hatch_mask_flat = (((hatch_x + hatch_y) // 8) % 2 == 0).reshape(-1)
    color_to_pixels: dict[int, np.ndarray] = {}
    if not frame_data.is_empty() and "map_color_int" in frame_data.columns:
        color_values = (
            frame_data.select("map_color_int")
            .drop_nulls()
            .unique()
            .sort("map_color_int")
            .get_column("map_color_int")
            .to_list()
        )
        if color_values:
            colors = np.array(color_values, dtype=np.uint32)
            indexes = np.searchsorted(colors, flat)
            in_range = indexes < len(colors)
            matched = np.zeros(flat.shape, dtype=bool)
            matched[in_range] = colors[indexes[in_range]] == flat[in_range]
            if bool(matched.any()):
                matched_pixels = np.flatnonzero(matched)
                matched_indexes = indexes[matched]
                for color_index in np.unique(matched_indexes):
                    color_to_pixels[int(colors[int(color_index)])] = matched_pixels[matched_indexes == color_index]
    return MapRenderCache(
        packed=packed,
        base_rgb=base_rgb,
        flat_packed=flat,
        hatch_mask_flat=hatch_mask_flat,
        color_to_pixels=color_to_pixels,
    )


def _render_metric_frame(
    assets: SavegameMapAssets,
    frame: pl.DataFrame,
    *,
    value_column: str,
    crop: tuple[int, int, int, int],
    render_cache: MapRenderCache | None = None,
    render_width: int,
    color_norm: Normalize | TwoSlopeNorm | None,
    cmap: Any,
    title: str,
    subtitle: str,
    center_zero: bool = False,
    timeline: RenderTimeline | None = None,
    legend: MapFrameLegend | None = None,
) -> dict[str, Any]:
    cache = render_cache or _build_render_cache(assets, crop=crop, frame_data=frame)
    rgb = cache.base_rgb.copy()
    color_values = frame.select("map_color_int", value_column).unique("map_color_int").sort("map_color_int")
    norm = color_norm or Normalize(vmin=0.0, vmax=1.0)
    if not color_values.is_empty():
        colors = np.array(color_values.get_column("map_color_int").to_list(), dtype=np.uint32)
        raw_values = color_values.get_column(value_column).to_list()
        values = np.array([np.nan if value is None else float(value) for value in raw_values], dtype=np.float64)
        finite_mask = np.isfinite(values)
        norm = color_norm or _dynamic_norm(values[finite_mask], center_zero=center_zero)
        flat_rgb = rgb.reshape(-1, 3)
        if finite_mask.any():
            mapped_rgb = (np.asarray(cmap(norm(values[finite_mask])))[:, :3] * 255).clip(0, 255).astype(np.uint8)
            finite_colors = colors[finite_mask]
            for color, rgb_value in zip(finite_colors, mapped_rgb, strict=False):
                pixels = cache.color_to_pixels.get(int(color))
                if pixels is not None and pixels.size:
                    flat_rgb[pixels] = rgb_value
        if (~finite_mask).any():
            for color in colors[~finite_mask]:
                pixels = cache.color_to_pixels.get(int(color))
                if pixels is None or not pixels.size:
                    continue
                flat_rgb[pixels] = DEFAULT_NO_DATA
                stripe_pixels = pixels[cache.hatch_mask_flat[pixels]]
                flat_rgb[stripe_pixels] = DEFAULT_NO_DATA_STRIPE

    image = Image.fromarray(rgb, mode="RGB")
    target_height = max(1, round(image.height * render_width / image.width))
    if image.width != render_width:
        image = image.resize((render_width, target_height), Image.Resampling.NEAREST)
    image = _add_frame_chrome(
        image,
        title=title,
        subtitle=subtitle,
        legend=legend,
        norm=norm,
        cmap=cmap,
        timeline=timeline,
    )
    return {"png": _png_bytes(image), "image": image}


def _render_categorical_frame(
    assets: SavegameMapAssets,
    frame: pl.DataFrame,
    *,
    color_column: str,
    crop: tuple[int, int, int, int],
    render_cache: MapRenderCache | None = None,
    render_width: int,
    title: str,
    subtitle: str,
    timeline: RenderTimeline | None = None,
    legend: MapFrameLegend | None = None,
) -> dict[str, Any]:
    cache = render_cache or _build_render_cache(assets, crop=crop, frame_data=frame)
    rgb = cache.base_rgb.copy()
    if color_column in frame.columns:
        color_values = frame.select("map_color_int", color_column).unique("map_color_int").sort("map_color_int")
        if not color_values.is_empty():
            flat_rgb = rgb.reshape(-1, 3)
            for row in color_values.iter_rows(named=True):
                pixels = cache.color_to_pixels.get(int(row["map_color_int"]))
                if pixels is None or not pixels.size:
                    continue
                color_value = row.get(color_column)
                if color_value is None:
                    flat_rgb[pixels] = DEFAULT_NO_DATA
                    stripe_pixels = pixels[cache.hatch_mask_flat[pixels]]
                    flat_rgb[stripe_pixels] = DEFAULT_NO_DATA_STRIPE
                    continue
                packed = int(color_value)
                flat_rgb[pixels] = np.array([(packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF], dtype=np.uint8)

    image = Image.fromarray(rgb, mode="RGB")
    target_height = max(1, round(image.height * render_width / image.width))
    if image.width != render_width:
        image = image.resize((render_width, target_height), Image.Resampling.NEAREST)
    placeholder_norm = Normalize(vmin=0.0, vmax=1.0, clip=True)
    image = _add_frame_chrome(
        image,
        title=title,
        subtitle=subtitle,
        legend=legend,
        norm=placeholder_norm,
        cmap=plt.get_cmap("viridis"),
        timeline=timeline,
    )
    return {"png": _png_bytes(image), "image": image}


def _dynamic_norm(values: np.ndarray, *, center_zero: bool) -> Normalize | TwoSlopeNorm:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return Normalize(vmin=0.0, vmax=1.0)
    min_value = float(finite.min())
    max_value = float(finite.max())
    if center_zero and min_value < 0.0 < max_value:
        return TwoSlopeNorm(vmin=min_value, vcenter=0.0, vmax=max_value)
    if center_zero:
        min_value = min(min_value, 0.0)
        max_value = max(max_value, 0.0)
    if min_value == max_value:
        if max_value <= 0.0:
            min_value -= 1.0
        else:
            min_value = 0.0
        if min_value == max_value:
            max_value += 1.0
    return Normalize(vmin=min_value, vmax=max_value)


def _add_frame_chrome(
    image: Image.Image,
    *,
    title: str,
    subtitle: str,
    legend: MapFrameLegend | None,
    norm: Normalize | TwoSlopeNorm,
    cmap: Any,
    timeline: RenderTimeline | None = None,
) -> Image.Image:
    header = 102
    panel_width = _legend_panel_width(image.width) if legend is not None else 0
    content_height = max(image.height, 480 if legend is not None else image.height)
    out = Image.new("RGB", (image.width + panel_width, content_height + header), (250, 250, 247))
    out.paste(image, (0, header))
    try:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(out)
        title_font = _image_font(24, bold=True)
        subtitle_font = _image_font(16)
        draw.text((16, 12), title, fill=(24, 24, 24), font=title_font)
        draw.text((16, 52), subtitle, fill=(70, 70, 70), font=subtitle_font)
        if timeline is not None:
            _draw_timeline(draw, image_width=image.width, timeline=timeline)
        if legend is not None:
            _draw_legend_panel(
                out,
                draw,
                panel_x=image.width,
                panel_y=header,
                panel_width=panel_width,
                panel_height=content_height,
                legend=legend,
                norm=norm,
                cmap=cmap,
            )
    except Exception:
        pass
    return out


def _draw_timeline(draw: Any, *, image_width: int, timeline: RenderTimeline) -> None:
    if timeline.count <= 0:
        return
    width = min(520, max(220, image_width // 3))
    x0 = max(16, (image_width - width) // 2)
    x1 = x0 + width
    y = 34
    font = _image_font(14)
    value_font = _image_font(19, bold=True)
    draw.line((x0, y, x1, y), fill=(154, 154, 146), width=5)
    if timeline.count <= 1:
        position = 0.0
    else:
        position = timeline.index / float(timeline.count - 1)
    marker_x = int(round(x0 + (x1 - x0) * min(max(position, 0.0), 1.0)))
    draw.line((x0, y, marker_x, y), fill=(42, 90, 150), width=6)
    draw.ellipse((marker_x - 7, y - 7, marker_x + 7, y + 7), fill=(42, 90, 150), outline=(24, 24, 24))
    draw.text((x0, y + 12), str(timeline.start_year), fill=(70, 70, 70), font=font)
    _draw_text_right(draw, (x1, y + 12), str(timeline.end_year), fill=(70, 70, 70), font=font)
    year_text = str(timeline.year)
    try:
        draw.text((marker_x, 5), year_text, fill=(24, 24, 24), font=value_font, anchor="ma")
    except TypeError:
        bbox = draw.textbbox((0, 0), year_text, font=value_font)
        draw.text((marker_x - ((bbox[2] - bbox[0]) // 2), 5), year_text, fill=(24, 24, 24), font=value_font)


def _legend_panel_width(map_width: int) -> int:
    return min(900, max(620, round(map_width * 0.42)))


def _draw_legend_panel(
    canvas: Image.Image,
    draw: Any,
    *,
    panel_x: int,
    panel_y: int,
    panel_width: int,
    panel_height: int,
    legend: MapFrameLegend,
    norm: Normalize | TwoSlopeNorm,
    cmap: Any,
) -> None:
    if panel_width <= 0:
        return
    if legend.swatch_rows:
        _draw_swatch_legend_panel(
            draw,
            panel_x=panel_x,
            panel_y=panel_y,
            panel_width=panel_width,
            panel_height=panel_height,
            legend=legend,
        )
        return
    x = panel_x + 16
    y = panel_y + 16
    right = panel_x + panel_width - 16
    draw.rectangle((panel_x, panel_y, panel_x + panel_width, panel_y + panel_height), fill=(250, 250, 247))
    draw.line((panel_x, panel_y, panel_x, panel_y + panel_height), fill=(207, 207, 198), width=1)

    title_font = _image_font(22, bold=True)
    row_font = _image_font(18)
    value_font = _image_font(18, bold=True)
    draw.text((x, y), legend.title, fill=(24, 24, 24), font=title_font)
    y += 38

    bar_height = max(140, min(210, panel_height // 3))
    bar_width = 26
    bar_x = x
    bar_y = y
    bar = _colorbar_image(norm=norm, cmap=cmap, width=bar_width, height=bar_height)
    canvas.paste(bar, (bar_x, bar_y))
    draw.rectangle((bar_x, bar_y, bar_x + bar_width - 1, bar_y + bar_height - 1), outline=(95, 95, 88))
    _draw_colorbar_ticks(
        draw,
        norm=norm,
        x=bar_x + bar_width + 10,
        y=bar_y,
        height=bar_height,
        unit=legend.unit,
        signed=legend.signed,
    )
    y += bar_height + 26

    label_x = x
    main_value_x = min(right, x + 224)
    for label, value in legend.rows:
        draw.text((label_x, y), f"{label}:", fill=(70, 70, 70), font=row_font)
        draw.text((main_value_x, y), value, fill=(24, 24, 24), font=value_font)
        y += 30
        if y > panel_y + panel_height - 30:
            break
    if legend.region_rows and y <= panel_y + panel_height - 120:
        y += 10
        draw.line((x, y, right, y), fill=(218, 218, 209), width=1)
        y += 14
        small_header_font = _image_font(15, bold=True)
        small_font = _image_font(13)
        small_value_font = _image_font(13, bold=True)
        draw.text((x, y), "Super Region", fill=(70, 70, 70), font=small_header_font)
        inner_width = right - x
        total_x = min(right, x + max(210, round(inner_width * 0.36)))
        mean_x = min(right, total_x + 102)
        median_x = min(right, mean_x + 102)
        min_x = min(right, median_x + 102)
        max_x = min(right, min_x + 102)
        for column_x, label in (
            (total_x, legend.region_value_header),
            (mean_x, "Mean"),
            (median_x, "Median"),
            (min_x, "Min"),
            (max_x, "Max"),
        ):
            _draw_text_right(draw, (column_x, y), label, fill=(70, 70, 70), font=small_header_font)
        y += 25
        for region, total, mean, median, minimum, maximum in legend.region_rows:
            if y > panel_y + panel_height - 24:
                break
            draw.text((x, y), region, fill=(70, 70, 70), font=small_font)
            _draw_text_right(draw, (total_x, y), total, fill=(24, 24, 24), font=small_value_font)
            _draw_text_right(draw, (mean_x, y), mean, fill=(24, 24, 24), font=small_value_font)
            _draw_text_right(draw, (median_x, y), median, fill=(24, 24, 24), font=small_value_font)
            _draw_text_right(draw, (min_x, y), minimum, fill=(24, 24, 24), font=small_value_font)
            _draw_text_right(draw, (max_x, y), maximum, fill=(24, 24, 24), font=small_value_font)
            y += 24


def _draw_swatch_legend_panel(
    draw: Any,
    *,
    panel_x: int,
    panel_y: int,
    panel_width: int,
    panel_height: int,
    legend: MapFrameLegend,
) -> None:
    x = panel_x + 16
    y = panel_y + 16
    right = panel_x + panel_width - 16
    draw.rectangle((panel_x, panel_y, panel_x + panel_width, panel_y + panel_height), fill=(250, 250, 247))
    draw.line((panel_x, panel_y, panel_x, panel_y + panel_height), fill=(207, 207, 198), width=1)

    title_font = _image_font(22, bold=True)
    row_font = _image_font(18)
    value_font = _image_font(18, bold=True)
    draw.text((x, y), legend.title, fill=(24, 24, 24), font=title_font)
    y += 38

    label_x = x
    main_value_x = min(right, x + 224)
    for label, value in legend.rows:
        draw.text((label_x, y), f"{label}:", fill=(70, 70, 70), font=row_font)
        draw.text((main_value_x, y), value, fill=(24, 24, 24), font=value_font)
        y += 30
        if y > panel_y + panel_height - 64:
            return

    y += 12
    draw.line((x, y, right, y), fill=(218, 218, 209), width=1)
    y += 16
    heading_font = _image_font(15, bold=True)
    swatch_font = _image_font(14)
    swatch_value_font = _image_font(14, bold=True)
    draw.text((x, y), legend.swatch_title, fill=(70, 70, 70), font=heading_font)
    y += 28
    value_x = right
    label_start = x + 36
    for label, value, hex_color in legend.swatch_rows:
        if y > panel_y + panel_height - 26:
            break
        color = _parse_hex_rgb(hex_color) or (156, 156, 150)
        draw.rectangle((x, y + 2, x + 24, y + 20), fill=color, outline=(80, 80, 74))
        draw.text((label_start, y), _compact_swatch_label(label, max_chars=30), fill=(50, 50, 46), font=swatch_font)
        _draw_text_right(draw, (value_x, y), value, fill=(24, 24, 24), font=swatch_value_font)
        y += 25


def _compact_swatch_label(label: str, *, max_chars: int) -> str:
    text = str(label or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}."


def _draw_text_right(draw: Any, xy: tuple[int, int], text: str, *, fill: tuple[int, int, int], font: Any) -> None:
    try:
        draw.text(xy, text, fill=fill, font=font, anchor="ra")
    except TypeError:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        draw.text((xy[0] - width, xy[1]), text, fill=fill, font=font)


def _colorbar_image(*, norm: Normalize | TwoSlopeNorm, cmap: Any, width: int, height: int) -> Image.Image:
    positions = np.linspace(1.0, 0.0, max(height, 1), dtype=np.float64)
    colors = (np.asarray(cmap(positions))[:, :3] * 255).clip(0, 255).astype(np.uint8)
    image = np.repeat(colors[:, np.newaxis, :], max(width, 1), axis=1)
    return Image.fromarray(image, mode="RGB")


def _draw_colorbar_ticks(
    draw: Any,
    *,
    norm: Normalize | TwoSlopeNorm,
    x: int,
    y: int,
    height: int,
    unit: str,
    signed: bool,
) -> None:
    font = _image_font(14)
    ticks = _colorbar_tick_values(norm, unit=unit)
    seen: set[float] = set()
    for value in ticks:
        key = round(float(value), 10)
        if key in seen:
            continue
        seen.add(key)
        try:
            position = float(norm(value))
        except Exception:
            position = 0.0
        position = min(max(position, 0.0), 1.0)
        tick_y = int(round(y + (1.0 - position) * (height - 1)))
        draw.line((x - 5, tick_y, x - 1, tick_y), fill=(72, 72, 66), width=1)
        draw.text((x + 7, tick_y - 7), _format_stat_value(value, unit=unit, signed=signed), fill=(58, 58, 54), font=font)


def _colorbar_tick_values(norm: Normalize | TwoSlopeNorm, *, unit: str) -> list[float]:
    low, high = _norm_bounds(norm)
    if unit == "population_thousands" and getattr(norm, "scale_name", "") == "log1p":
        candidates = [high, 1000.0, 100.0, 10.0, low]
        return [value for value in candidates if low <= value <= high]
    ticks = [high]
    if low < 0.0 < high:
        ticks.append(0.0)
    ticks.append(low)
    return ticks


def _norm_bounds(norm: Normalize | TwoSlopeNorm) -> tuple[float, float]:
    low = float(getattr(norm, "vmin", 0.0) if getattr(norm, "vmin", None) is not None else 0.0)
    high = float(getattr(norm, "vmax", 1.0) if getattr(norm, "vmax", None) is not None else 1.0)
    return low, high


def _image_font(size: int, *, bold: bool = False) -> Any:
    from PIL import ImageFont

    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _image_from_png(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return image.convert("RGB")


def _frame_image(frame: PopulationMapFrame) -> Image.Image:
    image = frame.image
    if isinstance(image, Image.Image):
        return image.copy()
    return _image_from_png(frame.png)


def _resize_animation_frame(image: Image.Image, *, width: int | None) -> Image.Image:
    if width is None or width <= 0 or image.width <= width:
        return image
    height = max(1, round(image.height * int(width) / image.width))
    return image.resize((int(width), height), Image.Resampling.LANCZOS)


def _animation_output_path(*, path: str | Path | None, output_dir: str | Path, filename: str) -> Path:
    output_path = Path(path) if path is not None else Path(output_dir) / filename
    if output_path.is_absolute():
        return output_path
    return _repo_relative_path(output_path)


def _repo_relative_path(path: Path) -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / "constructor.toml").is_file():
            return candidate / path
    return path


def _slugify_identifier(value: str) -> str:
    text = str(value).strip().lower()
    chars = [char if char.isalnum() else "_" for char in text]
    slug = "_".join(part for part in "".join(chars).split("_") if part)
    return slug or "map"


def _viewer_relative_url(html_path: Path, frame_path: Path) -> str:
    try:
        return frame_path.resolve().relative_to(html_path.parent.resolve()).as_posix()
    except ValueError:
        return frame_path.resolve().as_uri()


def _map_viewer_html(maps: list[dict[str, Any]], assets: list[dict[str, str]]) -> str:
    payload = json.dumps({"maps": maps, "assets": assets}, ensure_ascii=True)
    payload = payload.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Savegame Map Playback</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f7f2;
      color: #1f1f1d;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: #f7f7f2;
    }}
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 2;
      display: grid;
      grid-template-columns: minmax(160px, 260px) auto auto 1fr minmax(64px, 92px);
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      background: rgba(247, 247, 242, 0.96);
      border-bottom: 1px solid #d2d2c8;
      box-shadow: 0 1px 8px rgba(0, 0, 0, 0.08);
    }}
    select, button, input {{
      font: inherit;
    }}
    select, button {{
      min-height: 36px;
      border: 1px solid #9e9e94;
      background: #fff;
      color: #1f1f1d;
      border-radius: 4px;
      padding: 0 10px;
    }}
    button {{
      cursor: pointer;
      font-weight: 650;
    }}
    .assetLinks {{
      display: flex;
      gap: 8px;
      align-items: center;
      min-width: 0;
    }}
    .assetLinks[hidden] {{
      display: none;
    }}
    .assetLinks a {{
      min-height: 34px;
      display: inline-flex;
      align-items: center;
      border: 1px solid #9e9e94;
      border-radius: 4px;
      padding: 0 10px;
      background: #fff;
      color: #1f1f1d;
      text-decoration: none;
      font-weight: 650;
      white-space: nowrap;
    }}
    input[type="range"] {{
      width: 100%;
      accent-color: #2a5a96;
    }}
    #yearLabel {{
      font-size: 18px;
      font-weight: 750;
      text-align: right;
      white-space: nowrap;
    }}
    .stage {{
      padding: 16px;
      overflow: auto;
    }}
    #mapImage {{
      display: block;
      width: 100%;
      height: auto;
      max-width: none;
      background: #ecece5;
    }}
    @media (max-width: 760px) {{
      .toolbar {{
        grid-template-columns: 1fr auto;
      }}
      #assetLinks {{
        grid-column: 1 / -1;
      }}
      #frameSlider {{
        grid-column: 1 / -1;
      }}
      #yearLabel {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <select id="mapSelect" aria-label="Map"></select>
    <button id="playButton" type="button">Play</button>
    <div id="assetLinks" class="assetLinks" aria-label="Exports"></div>
    <input id="frameSlider" type="range" min="0" max="0" value="0" step="1" aria-label="Frame">
    <div id="yearLabel"></div>
  </div>
  <main class="stage">
    <img id="mapImage" alt="Savegame map frame">
  </main>
  <script>
    const DATA = {payload};
    const mapSelect = document.getElementById("mapSelect");
    const playButton = document.getElementById("playButton");
    const assetLinks = document.getElementById("assetLinks");
    const slider = document.getElementById("frameSlider");
    const yearLabel = document.getElementById("yearLabel");
    const image = document.getElementById("mapImage");
    let activeMap = 0;
    let activeFrame = 0;
    let timer = null;

    function currentFrames() {{
      return DATA.maps[activeMap]?.frames || [];
    }}

    function render() {{
      const frames = currentFrames();
      slider.max = Math.max(frames.length - 1, 0);
      slider.value = Math.min(activeFrame, frames.length - 1);
      const frame = frames[Math.min(activeFrame, frames.length - 1)];
      if (!frame) {{
        image.removeAttribute("src");
        yearLabel.textContent = "";
        return;
      }}
      image.src = frame.url;
      yearLabel.textContent = frame.year;
    }}

    function setPlaying(playing) {{
      if (timer) {{
        clearInterval(timer);
        timer = null;
      }}
      playButton.textContent = playing ? "Pause" : "Play";
      if (playing) {{
        timer = setInterval(() => {{
          const frames = currentFrames();
          if (!frames.length) return;
          activeFrame = (activeFrame + 1) % frames.length;
          render();
        }}, 500);
      }}
    }}

    DATA.maps.forEach((map, index) => {{
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = map.label;
      mapSelect.appendChild(option);
    }});
    (DATA.assets || []).forEach((asset) => {{
      const link = document.createElement("a");
      link.href = asset.url;
      link.textContent = asset.label;
      link.target = "_blank";
      link.rel = "noopener";
      assetLinks.appendChild(link);
    }});
    assetLinks.hidden = assetLinks.children.length === 0;

    mapSelect.addEventListener("change", () => {{
      activeMap = Number(mapSelect.value) || 0;
      activeFrame = 0;
      render();
    }});
    slider.addEventListener("input", () => {{
      activeFrame = Number(slider.value) || 0;
      render();
    }});
    playButton.addEventListener("click", () => setPlaying(timer === null));
    document.addEventListener("keydown", (event) => {{
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const frames = currentFrames();
      if (!frames.length) return;
      activeFrame += event.key === "ArrowRight" ? 1 : -1;
      activeFrame = (activeFrame + frames.length) % frames.length;
      render();
    }});
    render();
  </script>
</body>
</html>
"""


def _animation_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".webp":
        return "webp"
    if suffix == ".gif":
        return "gif"
    return suffix.removeprefix(".")


def _save_webp_animation(
    frames: list[Image.Image],
    path: Path,
    *,
    duration_ms: int,
    loop: int,
    quality: int,
    lossless: bool,
) -> None:
    try:
        frames[0].save(
            path,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=int(loop),
            quality=max(1, min(int(quality), 100)),
            lossless=bool(lossless),
            method=4,
        )
    except OSError as exc:
        raise RuntimeError(
            "Pillow could not write an animated WebP in this environment. "
            "Use a .gif output path as a fallback."
        ) from exc


def _save_webp_animation_with_size_limit(
    source_frames: list[Image.Image],
    path: Path,
    *,
    width: int | None,
    duration_ms: int,
    loop: int,
    quality: int,
    lossless: bool,
    max_bytes: int | None,
) -> list[Image.Image]:
    base_width = int(width) if width is not None and width > 0 else int(source_frames[0].width)
    quality_values = _webp_quality_attempts(quality)
    width_values = _webp_width_attempts(base_width)
    best: tuple[int, int, int] | None = None
    last_frames: list[Image.Image] = []
    for attempt_width in width_values:
        frames = [_resize_animation_frame(frame, width=attempt_width) for frame in source_frames]
        last_frames = frames
        for attempt_quality in quality_values:
            _save_webp_animation(
                frames,
                path,
                duration_ms=duration_ms,
                loop=loop,
                quality=attempt_quality,
                lossless=False if max_bytes is not None else lossless,
            )
            size = path.stat().st_size
            if best is None or size < best[0]:
                best = (size, attempt_width, attempt_quality)
            if max_bytes is None or size <= max_bytes:
                return frames
    assert best is not None
    raise RuntimeError(
        f"Could not export {path.name} below {_format_byte_count(max_bytes or 0)}. "
        f"Smallest attempt was {_format_byte_count(best[0])} at width {best[1]} and quality {best[2]}."
    )


def _webp_quality_attempts(quality: int) -> list[int]:
    requested = max(1, min(int(quality), 100))
    values = [requested, 92, 88, 84, 80, 76, 72, 66, 60, 54]
    return sorted(set(values), reverse=True)


def _webp_width_attempts(width: int) -> list[int]:
    base = max(320, int(width))
    values = [
        base,
        round(base * 0.92),
        round(base * 0.84),
        round(base * 0.76),
        round(base * 0.68),
        round(base * 0.60),
    ]
    minimum = min(900, base)
    return [value for value in dict.fromkeys(values) if value >= minimum]


def _format_byte_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} MB"
    if value >= 1_000:
        return f"{value / 1_000:.1f} KB"
    return f"{value} B"


def _save_gif_animation(frames: list[Image.Image], path: Path, *, duration_ms: int, loop: int) -> None:
    frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=int(loop),
        optimize=False,
        disposal=2,
    )


def _population_frame_label(result: PopulationMapResult, index: int) -> str:
    frame = result.frames[index]
    low, high = result.value_bounds
    if result.comparison == "delta":
        return (
            f"<b>{result.name}</b> - {frame.year} - baseline {_year_from_date_label(result.baseline_date)} "
            f"- population delta displayed {_format_population_thousands(low)}..{_format_population_thousands(high)}"
        )
    return (
        f"<b>{result.name}</b> - {frame.year} - current population "
        f"display scale {_format_population_thousands(low)}..{_format_population_thousands(high)}"
    )


def _scalar_frame_label(result: DevelopmentMapResult, index: int) -> str:
    frame = result.frames[index]
    low, high = result.value_bounds
    if result.mode == "from_gamestart":
        detail = f"change from {result.baseline_date}, displayed range {low:g}..{high:g}"
    else:
        detail = f"current value, displayed range {low:g}..{high:g}"
    if result.value_label:
        detail = f"{result.value_label}, {detail}"
    return f"<b>{result.name}</b> - {frame.year} - {detail}"


def _political_frame_label(result: PoliticalMapResult, index: int) -> str:
    frame = result.frames[index]
    return f"<b>{result.name}</b> - {frame.year} - owner and overlord colors"


def _normalize_relative_bounds(bounds: tuple[float, float]) -> tuple[float, float]:
    low, high = float(bounds[0]), float(bounds[1])
    if low >= 0 or high <= 0 or low >= high:
        raise ValueError("relative_bounds must span zero, for example (-100, 300).")
    return low, high


def _normalize_population_comparison(comparison: str | None) -> str:
    text = (comparison or "current").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "relative": "delta",
        "relative_pct": "delta",
        "relative_percent": "delta",
        "relative_percentage": "delta",
        "pct": "delta",
        "percent": "delta",
        "percentage": "delta",
        "change": "delta",
        "from_gamestart": "delta",
        "from_game_start": "delta",
        "absolute": "current",
        "absolute_value": "current",
        "current_value": "current",
        "value": "current",
    }
    normalized = aliases.get(text, text)
    if normalized not in {"delta", "current"}:
        raise ValueError("population comparison must be 'delta' or 'current'.")
    return normalized


def _normalize_population_absolute_scale(scale: str | None) -> str:
    text = (scale or DEFAULT_POPULATION_ABSOLUTE_SCALE).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "log": "log1p",
        "logarithmic": "log1p",
        "log_scale": "log1p",
        "logarithmic_scale": "log1p",
        "lin": "linear",
        "fixed": "linear",
    }
    normalized = aliases.get(text, text)
    if normalized not in {"log1p", "linear"}:
        raise ValueError("population absolute_scale must be 'log1p' or 'linear'.")
    return normalized


def _normalize_development_delta_bounds(bounds: tuple[float, float]) -> tuple[float, float]:
    low, high = float(bounds[0]), float(bounds[1])
    if low >= 0 or high <= 0 or low >= high:
        raise ValueError("delta_bounds must span zero, for example (-10, 10).")
    return low, high


def _normalize_positive_bounds(bounds: tuple[float, float]) -> tuple[float, float]:
    low, high = float(bounds[0]), float(bounds[1])
    if low < 0 or high <= low:
        raise ValueError("absolute bounds must be non-negative and increasing, for example (0, 500).")
    return low, high


def _default_absolute_bounds(metric: str) -> tuple[float, float]:
    if metric == "building_levels":
        return DEFAULT_BUILDING_LEVEL_BOUNDS
    if metric == "food_price":
        return DEFAULT_FOOD_PRICE_BOUNDS
    if metric == "development":
        return DEFAULT_DEVELOPMENT_BOUNDS
    if metric == "total_population" or metric.startswith("population_"):
        return DEFAULT_POPULATION_ABSOLUTE_BOUNDS
    return (0.0, 1.0)


def _zero_to_global_max_bounds(
    frame: pl.DataFrame,
    column: str,
    *,
    absolute_bounds: tuple[float, float] | None,
) -> tuple[float, float]:
    if absolute_bounds is not None:
        return _normalize_positive_bounds(absolute_bounds)
    if frame.is_empty() or column not in frame.columns:
        return (0.0, 1.0)
    max_value = frame.select(pl.col(column).cast(pl.Float64).max().alias("max")).item()
    high = float(max_value or 0.0)
    if not np.isfinite(high) or high <= 0.0:
        high = 1.0
    return (0.0, high)


def _overall_bounds(frame: pl.DataFrame, column: str) -> tuple[float, float]:
    if frame.is_empty() or column not in frame.columns:
        return (0.0, 0.0)
    values = frame.select(pl.min(column).alias("min"), pl.max(column).alias("max")).row(0, named=True)
    low = float(values["min"] or 0.0)
    high = float(values["max"] or 0.0)
    return low, high


def _normalize_development_mode(mode: str | None) -> str:
    text = (mode or "from_gamestart").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "game_start": "from_gamestart",
        "gamestart": "from_gamestart",
        "from_game_start": "from_gamestart",
        "from_start": "from_gamestart",
        "delta": "from_gamestart",
        "delta_from_start": "from_gamestart",
        "change": "from_gamestart",
        "change_from_start": "from_gamestart",
        "absolute": "current",
        "value": "current",
        "current_value": "current",
    }
    normalized = aliases.get(text, text)
    if normalized not in {"from_gamestart", "current"}:
        raise ValueError("development mode must be 'from_gamestart' or 'current'.")
    return normalized


def _normalize_population_metric(metric: str) -> str:
    text = str(metric).strip()
    if text in {"population", "total", "total_pop"}:
        return "total_population"
    return text


def _normalize_scope(scope: str | None) -> str:
    text = (scope or "super_region").strip().lower().replace(" ", "_").replace("-", "_")
    text = GEOGRAPHY_SCOPE_ALIASES.get(text, text)
    if text not in GEOGRAPHY_SCOPE_ORDER:
        valid = ", ".join(GEOGRAPHY_SCOPE_ORDER)
        raise ValueError(f"Unknown population scope {scope!r}. Expected one of: {valid}")
    return text
