"""Reusable savegame map rendering helpers for notebooks."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from IPython.display import display
from matplotlib.colors import TwoSlopeNorm
from PIL import Image

from eu5gameparser.load_order import LoadOrderConfig
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
DEFAULT_BACKGROUND = np.array([238, 238, 232], dtype=np.uint8)
DEFAULT_UNSELECTED = np.array([184, 184, 178], dtype=np.uint8)


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


@dataclass(frozen=True)
class PopulationMapFrame:
    index: int
    snapshot_id: str
    date: str
    date_sort: int
    year: int
    png: bytes


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
    widget: Any | None = None


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
        scale_x=float(packed_locations.shape[1]) / float(source_width),
        scale_y=float(map_height) / float(source_height),
    )


def population_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "relative_pct",
    relative_bounds: tuple[float, float] = DEFAULT_RELATIVE_BOUNDS,
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
    if comparison != "relative_pct":
        raise ValueError("Only comparison='relative_pct' is currently supported.")
    low, high = _normalize_relative_bounds(relative_bounds)
    metric = _normalize_population_metric(metric)
    locations = _population_locations(
        data,
        metric=metric,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    if locations.is_empty():
        return PopulationMapResult((), pl.DataFrame(), "", "", _normalize_scope(scope), name, metric, comparison, (low, high), 0, 0)

    normalized_scope = _normalize_scope(scope)
    filtered, resolved_name = _filter_scope(locations, normalized_scope, name)
    if filtered.is_empty():
        return PopulationMapResult((), pl.DataFrame(), "", "", normalized_scope, name, metric, comparison, (low, high), 0, 0)

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
            (low, high),
            0,
            int(missing_geometry_locations),
        )

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
            _relative_change_expr(metric, low=low, high=high).alias("relative_change_pct"),
        )
        .sort(["date_sort", "slug"])
    )
    crop = _scope_crop(frame_data, assets, padding=18)
    target_width = width or assets.map_width
    render_width = min(max(int(target_width), 200), assets.map_width)
    color_norm = TwoSlopeNorm(vmin=low, vcenter=0.0, vmax=high)
    cmap = plt.get_cmap("RdYlGn")

    frames: list[PopulationMapFrame] = []
    snapshots = frame_data.select(["snapshot_id", "date", "date_sort", "year"]).unique().sort("date_sort")
    for index, snapshot in enumerate(snapshots.iter_rows(named=True)):
        snapshot_frame = frame_data.filter(pl.col("snapshot_id") == snapshot["snapshot_id"])
        png = _render_population_frame(
            assets,
            snapshot_frame,
            crop=crop,
            render_width=render_width,
            color_norm=color_norm,
            cmap=cmap,
            title=f"{resolved_name} population change vs {baseline_date_label}",
            subtitle=f"{snapshot['date']} - {comparison.replace('_', ' ')}",
        )
        frames.append(
            PopulationMapFrame(
                index=index,
                snapshot_id=str(snapshot["snapshot_id"]),
                date=str(snapshot["date"]),
                date_sort=int(snapshot["date_sort"]),
                year=int(snapshot["year"]),
                png=png,
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
        relative_bounds=(low, high),
        mapped_locations=int(mapped_locations),
        missing_geometry_locations=int(missing_geometry_locations),
    )


def show_population_map(
    data: Any,
    *,
    scope: str = "super_region",
    name: str,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "relative_pct",
    relative_bounds: tuple[float, float] = DEFAULT_RELATIVE_BOUNDS,
    width: int | None = None,
    interval_ms: int = 700,
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
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    widget = population_map_widget(result, interval_ms=interval_ms)
    if widget is not None:
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
        widget=widget,
    )


def population_map_widget(result: PopulationMapResult, *, interval_ms: int = 700) -> Any | None:
    if not result.frames:
        print("No population map frames")
        return None
    import ipywidgets as widgets

    image = widgets.Image(value=result.frames[0].png, format="png", layout=widgets.Layout(width="100%"))
    label = widgets.HTML(value=_frame_label(result, 0))
    options = [(f"{frame.date} ({frame.year})", frame.index) for frame in result.frames]
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
        max=len(result.frames) - 1,
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
        image.value = result.frames[index].png
        label.value = _frame_label(result, index)

    slider.observe(_on_change, names="index")
    return widgets.VBox([widgets.HBox([play]), slider, label, image])


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
    geometry = assets.geometry
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
            (pl.col("bbox_min_x").cast(pl.Float64) * assets.scale_x).floor().cast(pl.Int64).clip(0, assets.map_width - 1).alias("map_min_x"),
            (pl.col("bbox_max_x").cast(pl.Float64) * assets.scale_x).ceil().cast(pl.Int64).clip(0, assets.map_width - 1).alias("map_max_x"),
            (pl.col("bbox_min_y").cast(pl.Float64) * assets.scale_y).floor().cast(pl.Int64).clip(0, assets.map_height - 1).alias("map_min_y"),
            (pl.col("bbox_max_y").cast(pl.Float64) * assets.scale_y).ceil().cast(pl.Int64).clip(0, assets.map_height - 1).alias("map_max_y"),
        )
        .select("location_tag", "map_color_int", "map_min_x", "map_max_x", "map_min_y", "map_max_y")
        .unique("location_tag")
    )


def _population_locations(
    data: Any,
    *,
    metric: str,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    locations = data.table("locations")
    if locations.is_empty():
        return pl.DataFrame()
    if metric not in locations.columns:
        raise ValueError(f"Population metric {metric!r} is not available in the loaded locations table.")
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


def _filter_scope(frame: pl.DataFrame, scope: str, name: str) -> tuple[pl.DataFrame, str]:
    columns = [column for column in GEOGRAPHY_SCOPE_SEARCH_COLUMNS[scope] if column in frame.columns]
    if not columns:
        return frame.head(0), name
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
    return frame.head(0), name


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


def _render_population_frame(
    assets: SavegameMapAssets,
    frame: pl.DataFrame,
    *,
    crop: tuple[int, int, int, int],
    render_width: int,
    color_norm: TwoSlopeNorm,
    cmap: Any,
    title: str,
    subtitle: str,
) -> bytes:
    x0, y0, x1, y1 = crop
    packed = assets.packed_locations[y0:y1, x0:x1]
    rgb = np.empty((*packed.shape, 3), dtype=np.uint8)
    rgb[:, :] = DEFAULT_BACKGROUND
    land_mask = packed != 0
    rgb[land_mask] = DEFAULT_UNSELECTED
    color_values = frame.select("map_color_int", "relative_change_pct").unique("map_color_int").sort("map_color_int")
    if not color_values.is_empty():
        colors = np.array(color_values.get_column("map_color_int").to_list(), dtype=np.uint32)
        values = np.array(color_values.get_column("relative_change_pct").to_list(), dtype=np.float64)
        mapped_rgb = (np.asarray(cmap(color_norm(values)))[:, :3] * 255).astype(np.uint8)
        flat = packed.reshape(-1)
        indexes = np.searchsorted(colors, flat)
        in_range = indexes < len(colors)
        matched = np.zeros(flat.shape, dtype=bool)
        matched[in_range] = colors[indexes[in_range]] == flat[in_range]
        if bool(matched.any()):
            rgb.reshape(-1, 3)[matched] = mapped_rgb[indexes[matched]]

    image = Image.fromarray(rgb, mode="RGB")
    target_height = max(1, round(image.height * render_width / image.width))
    if image.width != render_width:
        image = image.resize((render_width, target_height), Image.Resampling.NEAREST)
    image = _add_frame_header(image, title=title, subtitle=subtitle)
    return _png_bytes(image)


def _add_frame_header(image: Image.Image, *, title: str, subtitle: str) -> Image.Image:
    header = 72
    out = Image.new("RGB", (image.width, image.height + header), (250, 250, 247))
    out.paste(image, (0, header))
    try:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(out)
        draw.text((12, 10), title, fill=(24, 24, 24))
        draw.text((12, 36), subtitle, fill=(70, 70, 70))
    except Exception:
        pass
    return out


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _frame_label(result: PopulationMapResult, index: int) -> str:
    frame = result.frames[index]
    low, high = result.relative_bounds
    return (
        f"<b>{result.name}</b> - {frame.date} - baseline {result.baseline_date} "
        f"- relative population change clamped to {low:g}%..{high:g}%"
    )


def _normalize_relative_bounds(bounds: tuple[float, float]) -> tuple[float, float]:
    low, high = float(bounds[0]), float(bounds[1])
    if low >= 0 or high <= 0 or low >= high:
        raise ValueError("relative_bounds must span zero, for example (-100, 300).")
    return low, high


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
