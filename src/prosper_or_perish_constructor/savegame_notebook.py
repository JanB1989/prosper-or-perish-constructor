"""Notebook-facing savegame analysis helpers.

This module keeps the savegame notebook thin: notebook cells should set a few
section parameters, call one function, and optionally bind returned frames for
interactive inspection.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from io import BytesIO
import importlib
from pathlib import Path
import re
from typing import Any

import matplotlib.pyplot as plt
import polars as pl
from IPython.display import display
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter

from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile
from eu5gameparser.savegame.notebook_dataset import (
    DIMENSION_SPECS,
    FACT_TABLES,
    SavegameNotebookDataset,
)
from prosper_or_perish_constructor import savegame_maps


NOTEBOOK_FIGSIZE = (22, 8.5)
NOTEBOOK_MIN_FIGURE_WIDTH = 22
NOTEBOOK_MIN_FIGURE_HEIGHT = 8.5

LOCATION_RANK_ORDER = ("rural_settlement", "town", "city", "megalopolis")
LOCATION_RANK_LABELS = {
    "rural_settlement": "Rural",
    "town": "Town",
    "city": "City",
    "megalopolis": "Megalopolis",
}

POP_TYPE_BASE_ORDER = (
    "nobles",
    "clergy",
    "burghers",
    "laborers",
    "soldiers",
    "peasants",
    "slaves",
    "tribesmen",
)
POP_TYPE_ORDER = (
    "nobles",
    "clergy",
    "burghers",
    "laborers",
    "soldiers",
    "peasants",
    "unemployed_peasants",
    "slaves",
    "tribesmen",
)
POP_TYPE_LABELS = {value: value.replace("_", " ").title() for value in POP_TYPE_ORDER}

INFRASTRUCTURE_BUILDING_ORDER = (
    "carrier_inn",
    "coastal_shipping_office",
    "river_boatmen_yard",
    "transport_office",
    "road_wardens_yard",
    "paviors_yard",
    "macadam_works",
    "permanent_way_depot",
)

POPULATION_POOL_TABLE = "market_population_pools"

DEFAULT_NOTEBOOK_TABLES = (*FACT_TABLES, POPULATION_POOL_TABLE)
RAW_PASSTHROUGH_TABLES = frozenset({POPULATION_POOL_TABLE})

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
GEOGRAPHY_SCOPE_LABELS = {
    "super_region": "super region",
    "macro_region": "macro region",
    "region": "region",
    "area": "area",
    "location": "location",
}
GEOGRAPHY_SCOPE_SEARCH_COLUMNS = {
    "super_region": ("super_region", "super_region_label"),
    "macro_region": ("macro_region", "macro_region_label"),
    "region": ("region", "region_label"),
    "area": ("area", "area_label"),
    "location": ("slug", "location_label", "location_id"),
}


@dataclass(frozen=True)
class SavegameNotebookData:
    """Loaded notebook data context.

    The context owns the repository paths, manifest/snapshot frame, and dataset
    handle. Raw fact rows remain in parquet and are scanned lazily by section
    functions.
    """

    wb: Any
    dataset: Any
    snapshots: pl.DataFrame
    tables: dict[str, pl.DataFrame]
    dimensions: dict[str, pl.DataFrame]
    data_root: Path
    load_order_path: Path | None
    profile: str | None
    playthrough: str | None
    map_assets: Any | None = None

    def workbench(
        self,
        *,
        playthrough: str | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
        snapshot_date: int | None = None,
        good_search: str | None = "victuals",
        market_search: str | None = None,
        building_search: str | None = "cookery",
        pm_drilldown_search: str | None = None,
        country_search: str | None = "england",
        group_by: str = "super_region",
        building_scope: str = "super_region",
        flow_group_by: str | Sequence[str] = ("flow_table", "market"),
        consumption_group_by: str = "bucket",
        imbalance_sort: str = "mean_flow",
        agg: str = "sum",
        top_n: int = 6,
        bucket_years: int = 25,
        start_year: int = 1337,
        population_metric: str = "total_population",
        food_rank_by: str = "food_fill_ratio",
        building_metric: str = "level",
    ) -> Any:
        return self.wb.open_workbench(
            self.wb.WorkbenchConfig(
                data_root=self.data_root,
                profile=self.profile,
                load_order_path=self.load_order_path,
                playthrough=playthrough or self.playthrough,
                start_date=start_date,
                end_date=end_date,
                snapshot_date=snapshot_date,
                good_search=good_search,
                market_search=market_search,
                building_search=building_search,
                pm_drilldown_search=pm_drilldown_search,
                country_search=country_search,
                group_by=group_by,
                building_scope=building_scope,
                flow_group_by=tuple(flow_group_by) if not isinstance(flow_group_by, str) else (flow_group_by,),
                consumption_group_by=consumption_group_by,
                imbalance_sort=imbalance_sort,
                agg=agg,
                top_n=top_n,
                bucket_years=bucket_years,
                start_year=start_year,
                population_metric=population_metric,
                food_rank_by=food_rank_by,
                building_metric=building_metric,
            )
        )

    def table(self, name: str) -> pl.DataFrame:
        """Return one eagerly loaded fact table."""

        return self.tables.get(name, pl.DataFrame())

    def dim(self, name: str) -> pl.DataFrame:
        """Return one eagerly loaded dimension table."""

        return self.dimensions.get(name, pl.DataFrame())

    @property
    def loaded_tables(self) -> tuple[str, ...]:
        return tuple(self.tables)


@dataclass(frozen=True)
class RuntimeCadenceResult:
    plot_frame: pl.DataFrame
    stats: pl.DataFrame
    interval_label: str
    running_window_label: str

    @property
    def df(self) -> pl.DataFrame:
        """Summary dataframe displayed below the wall-time graph."""

        return self.stats

    @property
    def intervals_df(self) -> pl.DataFrame:
        """Interval-level dataframe used by the wall-time graph."""

        return self.plot_frame


@dataclass(frozen=True)
class DistributionResult:
    frame: pl.DataFrame


@dataclass(frozen=True)
class PopulationResult:
    global_df: pl.DataFrame
    breakdown_df: pl.DataFrame
    latest_breakdown_df: pl.DataFrame
    delta_df: pl.DataFrame
    stats: pl.DataFrame
    metric: str
    display_metric: str
    breakdown_scope: str
    filter_scope: str | None
    filter_name: str | None

    @property
    def df(self) -> pl.DataFrame:
        """Global pop-type statistics dataframe."""

        return self.stats

    @property
    def latest(self) -> pl.DataFrame:
        """Latest scoped population breakdown dataframe."""

        return self.latest_breakdown_df

    @property
    def delta(self) -> pl.DataFrame:
        """First-to-latest scoped population delta dataframe."""

        return self.delta_df

    @property
    def time_series(self) -> pl.DataFrame:
        """Scoped population time-series dataframe."""

        return self.breakdown_df

    @property
    def top_time_series(self) -> pl.DataFrame:
        """Top scoped population time-series dataframe."""

        return self.breakdown_df

    @property
    def global_time_series(self) -> pl.DataFrame:
        """Global population time-series dataframe."""

        return self.global_df


@dataclass(frozen=True)
class GlobalBuildingsResult:
    time_series: pl.DataFrame


@dataclass(frozen=True)
class InfrastructureBuildingsResult:
    buildings: pl.DataFrame
    time_series: pl.DataFrame
    latest: pl.DataFrame
    building_types: list[str]


@dataclass(frozen=True)
class BuildingAbsoluteResult:
    time_series: pl.DataFrame
    top_time_series: pl.DataFrame
    tag_matches: pl.DataFrame
    tag_options: pl.DataFrame
    metric: str


@dataclass(frozen=True)
class GlobalMapExportResult:
    animations: tuple[savegame_maps.AnimationExportResult, ...]
    viewer: savegame_maps.MapViewerExportResult


@dataclass(frozen=True)
class FoodPriceVolatilityResult:
    global_distribution: pl.DataFrame
    market_time_series: pl.DataFrame
    stats: pl.DataFrame
    top_erratic: pl.DataFrame
    top_victuals_erratic: pl.DataFrame
    market_search: str | None
    linked_good: str | None = "victuals"
    linked_good_label: str | None = "Victuals"

    @property
    def df(self) -> pl.DataFrame:
        """Per-market food price summary dataframe."""

        return self.stats


@dataclass(frozen=True)
class FoodPriceVolatilityWebPExportResult:
    path: Path
    format: str
    width: int
    height: int
    markets: int
    snapshots: int


@dataclass(frozen=True)
class GoodsPressureResult:
    global_time_series: pl.DataFrame
    summary: pl.DataFrame
    global_shortages: pl.DataFrame
    global_oversupply: pl.DataFrame
    problem_goods: pl.DataFrame
    selected_good: str | None
    selected_good_label: str | None
    selected_good_global: pl.DataFrame
    selected_good_markets: pl.DataFrame
    selected_good_market_time_series: pl.DataFrame
    rank_mode: str


def open_data(
    *,
    repo: str | Path | None = None,
    data_root: str | Path | None = None,
    load_order_path: str | Path | None = None,
    profile: str | None = "constructor",
    playthrough: str | None = None,
    tables: Sequence[str] | str | None = DEFAULT_NOTEBOOK_TABLES,
    reload_workbench: bool = True,
    load_map_assets: bool = False,
    map_width: int = 2400,
    map_geometry_cache: str | Path | None = Path("artifacts/data/population_capacity/location_geometry.parquet"),
) -> SavegameNotebookData:
    """Load notebook parquet data and configure notebook plotting defaults."""

    from eu5gameparser.savegame import notebook_workbench as notebook_workbench

    wb = importlib.reload(notebook_workbench) if reload_workbench else notebook_workbench
    _configure_notebook_plots(wb)
    resolved_repo = _find_repo_root(_portable_path(repo) if repo is not None else None)
    resolved_data_root = _portable_path(data_root) if data_root is not None else resolved_repo / "graphs" / "dataset"
    resolved_load_order = (
        _portable_path(load_order_path)
        if load_order_path is not None
        else resolved_repo / "constructor.load_order.toml"
    )
    resolved_profile = profile if resolved_load_order.is_file() else None
    dataset = SavegameNotebookDataset(
        resolved_data_root,
        profile=resolved_profile,
        load_order_path=resolved_load_order,
    )
    snapshots = dataset.snapshots()
    if snapshots.is_empty():
        raise RuntimeError(
            "No raw savegame dataset found. Run `uv run ppc savegame-notebooks build` "
            "from the constructor repo, then restart this kernel."
    )
    selected_playthrough = playthrough or dataset.latest_playthrough()
    dimensions = _load_dimensions(dataset)
    loaded_tables = _load_tables(dataset, selected_playthrough, tables)
    map_assets = (
        savegame_maps.load_map_assets(
            repo=resolved_repo,
            project=resolved_repo / "constructor.toml",
            map_width=map_width,
            geometry_cache=map_geometry_cache,
        )
        if load_map_assets
        else None
    )
    return SavegameNotebookData(
        wb=wb,
        dataset=dataset,
        snapshots=snapshots,
        tables=loaded_tables,
        dimensions=dimensions,
        data_root=resolved_data_root,
        load_order_path=resolved_load_order,
        profile=resolved_profile,
        playthrough=selected_playthrough,
        map_assets=map_assets,
    )


def show_selection(workbench: Any) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    workbench.print_selection()
    preview = workbench.preview()
    for frame in preview:
        display(frame)
    return preview


def runtime_cadence(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    interval_years: int = 5,
    rolling_intervals: int = 5,
) -> RuntimeCadenceResult:
    if interval_years <= 0:
        raise ValueError("interval_years must be positive")
    if rolling_intervals <= 0:
        raise ValueError("rolling_intervals must be positive")

    snapshots = _selected_snapshots(data, workbench).sort("date_sort")
    return wall_time_cadence(
        data,
        snapshots=snapshots,
        interval_years=interval_years,
        rolling_intervals=rolling_intervals,
    )


def wall_time_cadence(
    data: SavegameNotebookData,
    *,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    snapshots: pl.DataFrame | None = None,
    interval_years: int = 5,
    rolling_intervals: int = 5,
) -> RuntimeCadenceResult:
    if interval_years <= 0:
        raise ValueError("interval_years must be positive")
    if rolling_intervals <= 0:
        raise ValueError("rolling_intervals must be positive")

    snapshots = (
        snapshots.sort("date_sort")
        if snapshots is not None
        else _selected_snapshots_values(
            data,
            playthrough=playthrough,
            start_date=start_date,
            end_date=end_date,
        )
    )
    cadence = (
        snapshots.select(["snapshot_id", "date", "year", "month", "day", "date_sort", "mtime_ns", "path"])
        .with_columns(
            pl.col("date").shift(1).alias("previous_date"),
            pl.col("year").shift(1).alias("previous_year"),
            pl.col("date_sort").shift(1).alias("previous_date_sort"),
            pl.col("mtime_ns").shift(1).alias("previous_mtime_ns"),
        )
        .with_columns(
            pl.concat_str(["previous_date", pl.lit(" -> "), "date"]).alias("interval"),
            (pl.col("year").cast(pl.Int64) - pl.col("previous_year").cast(pl.Int64)).alias("elapsed_game_years"),
            ((pl.col("mtime_ns") - pl.col("previous_mtime_ns")).cast(pl.Float64) / 1_000_000_000.0).alias("elapsed_seconds"),
        )
        .with_columns(
            pl.when(pl.col("elapsed_game_years") > 0)
            .then(pl.col("elapsed_seconds") / pl.col("elapsed_game_years").cast(pl.Float64))
            .otherwise(None)
            .alias("elapsed_seconds_per_year")
        )
        .filter(pl.col("elapsed_seconds_per_year").is_not_null())
    )
    cadence_interval = cadence.filter(pl.col("elapsed_game_years") == interval_years)
    using_interval = not cadence_interval.is_empty()
    plot_frame = cadence_interval if using_interval else cadence
    interval_label = f"{interval_years}-year intervals" if using_interval else "available intervals"
    running_window_label = (
        f"{rolling_intervals * interval_years} years"
        if using_interval
        else f"{rolling_intervals} intervals"
    )

    if plot_frame.is_empty():
        return RuntimeCadenceResult(plot_frame, pl.DataFrame(), interval_label, running_window_label)

    plot_frame = plot_frame.with_columns(
        pl.col("elapsed_seconds_per_year")
        .rolling_mean(window_size=rolling_intervals, min_samples=1)
        .alias("running_mean_seconds_per_year"),
        pl.col("elapsed_seconds_per_year")
        .rolling_median(window_size=rolling_intervals, min_samples=1)
        .alias("running_median_seconds_per_year"),
    )
    stats = plot_frame.select(
        pl.len().alias("intervals"),
        pl.sum("elapsed_game_years").alias("total_game_years"),
        pl.sum("elapsed_seconds").round(2).alias("total_seconds"),
        pl.min("elapsed_seconds_per_year").round(2).alias("min_seconds_per_year"),
        pl.mean("elapsed_seconds_per_year").round(2).alias("mean_seconds_per_year"),
        pl.median("elapsed_seconds_per_year").round(2).alias("median_seconds_per_year"),
        pl.max("elapsed_seconds_per_year").round(2).alias("max_seconds_per_year"),
        pl.std("elapsed_seconds_per_year").round(2).alias("stddev_seconds_per_year"),
    )
    return RuntimeCadenceResult(plot_frame, stats, interval_label, running_window_label)


def show_wall_time(
    data: SavegameNotebookData,
    *,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    interval_years: int = 5,
    rolling_intervals: int = 5,
) -> RuntimeCadenceResult:
    """Display wall-clock seconds per game year and the summary dataframe."""

    result = wall_time_cadence(
        data,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        interval_years=interval_years,
        rolling_intervals=rolling_intervals,
    )
    plot_runtime_cadence(result)
    if not result.stats.is_empty():
        display(result.stats)
    return result


def show_runtime_cadence(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    interval_years: int = 5,
    rolling_intervals: int = 5,
) -> RuntimeCadenceResult:
    result = runtime_cadence(
        data,
        workbench,
        interval_years=interval_years,
        rolling_intervals=rolling_intervals,
    )
    plot_runtime_cadence(result)
    if not result.stats.is_empty():
        display(result.stats)
    return result


def plot_runtime_cadence(result: RuntimeCadenceResult) -> None:
    frame = result.plot_frame
    if frame.is_empty():
        print("No savegame interval rows")
        return
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(
        frame["year"].to_list(),
        frame["elapsed_seconds_per_year"].to_list(),
        marker="o",
        linewidth=2.0,
        label="Seconds per game year",
    )
    ax.plot(
        frame["year"].to_list(),
        frame["running_mean_seconds_per_year"].to_list(),
        linewidth=2.4,
        label=f"Running mean ({result.running_window_label})",
    )
    ax.plot(
        frame["year"].to_list(),
        frame["running_median_seconds_per_year"].to_list(),
        linewidth=2.4,
        linestyle="--",
        label=f"Running median ({result.running_window_label})",
    )
    ax.set_title(f"Wall-clock seconds per game year ({result.interval_label})")
    ax.set_xlabel("ending year")
    ax.set_ylabel("seconds per game year")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc="best")
    fig.tight_layout()
    _display_figure(fig)


def location_rank_distribution(data: SavegameNotebookData, workbench: Any) -> DistributionResult:
    categories = pl.DataFrame(
        {
            "rank": list(LOCATION_RANK_ORDER),
            "rank_label": [LOCATION_RANK_LABELS[value] for value in LOCATION_RANK_ORDER],
            "rank_sort": list(range(len(LOCATION_RANK_ORDER))),
        }
    )
    locations = _selected_locations(data, workbench)
    if "rank" not in locations.collect_schema().names():
        return DistributionResult(pl.DataFrame())
    counts = (
        locations.filter(pl.col("rank").is_in(LOCATION_RANK_ORDER))
        .group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year", "rank"])
        .agg(pl.len().alias("locations"))
        .collect()
    )
    if counts.is_empty():
        return DistributionResult(pl.DataFrame())
    snapshot_columns = ["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"]
    snapshots = counts.select(snapshot_columns).unique()
    frame = (
        snapshots.join(categories, how="cross")
        .join(
            counts,
            on=[*snapshot_columns, "rank"],
            how="left",
        )
        .with_columns(pl.col("locations").fill_null(0))
        .with_columns(pl.sum("locations").over("snapshot_id").alias("total_locations"))
        .with_columns(
            pl.when(pl.col("total_locations") > 0)
            .then(pl.col("locations") / pl.col("total_locations") * 100.0)
            .otherwise(0.0)
            .alias("percent")
        )
        .sort(["date_sort", "rank_sort"])
    )
    return DistributionResult(frame)


def show_location_rank_distribution(data: SavegameNotebookData, workbench: Any) -> DistributionResult:
    result = location_rank_distribution(data, workbench)
    plot_percent_stack(
        result.frame,
        category="rank_label",
        sort_col="rank_sort",
        title="Global location rank distribution",
    )
    return result


def pop_type_distribution(data: SavegameNotebookData, workbench: Any) -> DistributionResult:
    pool_distribution = _population_pool_distribution_frame(
        data,
        playthrough=getattr(workbench, "playthrough", data.playthrough),
        start_date=getattr(workbench.config, "start_date", None),
        end_date=getattr(workbench.config, "end_date", None),
    )
    if not pool_distribution.is_empty():
        return DistributionResult(pool_distribution)
    locations = _selected_locations(data, workbench)
    return DistributionResult(_pop_type_distribution_frame(locations))


def show_pop_type_distribution(data: SavegameNotebookData, workbench: Any) -> DistributionResult:
    result = pop_type_distribution(data, workbench)
    plot_percent_stack(
        result.frame,
        category="pop_type_label",
        sort_col="pop_type_sort",
        title="Global pop type distribution",
    )
    return result


def population_statistics(
    data: SavegameNotebookData,
    workbench: Any | None = None,
    *,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    scope: str = "super_region",
    name: str | None = None,
) -> pl.DataFrame:
    """Compute global pop-type distribution statistics for the selected period."""

    if workbench is not None:
        locations = _selected_locations(data, workbench).collect()
        scope = getattr(workbench.config, "group_by", scope)
        playthrough = getattr(workbench, "playthrough", playthrough)
        start_date = getattr(workbench.config, "start_date", start_date)
        end_date = getattr(workbench.config, "end_date", end_date)
    else:
        locations = _population_locations(
            data,
            metric="total_population",
            playthrough=playthrough,
            start_date=start_date,
            end_date=end_date,
        )
    return _population_statistics_from_sources(
        data,
        _population_scope_locations(locations, scope=scope, name=name),
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        use_population_pools=_text_or_none(name) is None,
    )


def population_over_time(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    child_scope: str | None = None,
    metric: str = "total_population",
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    top_n: int | None = None,
) -> PopulationResult:
    """Compute global and scoped population time series from loaded data."""

    locations = _population_locations(
        data,
        metric=metric,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    global_df = _population_global_time_series(locations, metric=metric)
    breakdown_df, breakdown_scope, filter_scope, filter_name = _population_breakdown_time_series(
        locations,
        scope=scope,
        name=name,
        child_scope=child_scope,
        metric=metric,
        top_n=top_n,
    )
    display_metric = metric
    latest_breakdown_df = _latest_population_breakdown(
        breakdown_df,
        metric=metric,
        display_metric=display_metric,
    )
    delta_df = _population_breakdown_delta(breakdown_df, metric=metric)
    stats = _population_statistics_from_sources(
        data,
        _population_scope_locations(locations, scope=scope, name=name),
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        use_population_pools=_text_or_none(name) is None,
    )
    return PopulationResult(
        global_df=global_df,
        breakdown_df=breakdown_df,
        latest_breakdown_df=latest_breakdown_df,
        delta_df=delta_df,
        stats=stats,
        metric=metric,
        display_metric=display_metric,
        breakdown_scope=breakdown_scope,
        filter_scope=filter_scope,
        filter_name=filter_name,
    )


def show_population(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    child_scope: str | None = None,
    metric: str = "total_population",
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    top_n: int | None = None,
) -> PopulationResult:
    result = population_over_time(
        data,
        scope=scope,
        name=name,
        child_scope=child_scope,
        metric=metric,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
    )
    return show_population_result(result)


def show_population_result(result: PopulationResult) -> PopulationResult:
    _plot_population_global(result.global_df, metric=result.metric, display_metric=result.display_metric)
    title = _population_breakdown_title(
        breakdown_scope=result.breakdown_scope,
        filter_scope=result.filter_scope,
        filter_name=result.filter_name,
        metric=result.metric,
    )
    _plot_population_grouped(
        result.breakdown_df,
        metric=result.metric,
        display_metric=result.display_metric,
        group_label="scope_label",
        title=title,
    )
    if not result.stats.is_empty():
        display(result.stats)
    return result


def population_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "current",
    relative_bounds: tuple[float, float] = savegame_maps.DEFAULT_POPULATION_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    absolute_scale: str = savegame_maps.DEFAULT_POPULATION_ABSOLUTE_SCALE,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.PopulationMapResult:
    return savegame_maps.population_map(
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


def show_population_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "current",
    relative_bounds: tuple[float, float] = savegame_maps.DEFAULT_POPULATION_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    absolute_scale: str = savegame_maps.DEFAULT_POPULATION_ABSOLUTE_SCALE,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.PopulationMapResult:
    return savegame_maps.show_population_map(
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
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def save_population_map_animation(
    result: savegame_maps.PopulationMapResult,
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
) -> savegame_maps.AnimationExportResult:
    return savegame_maps.save_population_map_animation(
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


def development_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = savegame_maps.DEFAULT_DEVELOPMENT_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.DevelopmentMapResult:
    return savegame_maps.development_map(
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


def show_development_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = savegame_maps.DEFAULT_DEVELOPMENT_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.DevelopmentMapResult:
    return savegame_maps.show_development_map(
        data,
        scope=scope,
        name=name,
        mode=mode,
        baseline_date=baseline_date,
        delta_bounds=delta_bounds,
        absolute_bounds=absolute_bounds,
        width=width,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def save_development_map_animation(
    result: savegame_maps.DevelopmentMapResult,
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
) -> savegame_maps.AnimationExportResult:
    return savegame_maps.save_development_map_animation(
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


def building_levels_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = savegame_maps.DEFAULT_BUILDING_LEVEL_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.BuildingLevelsMapResult:
    return savegame_maps.building_levels_map(
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


def show_building_levels_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    mode: str = "from_gamestart",
    baseline_date: int | str | None = None,
    delta_bounds: tuple[float, float] = savegame_maps.DEFAULT_BUILDING_LEVEL_DELTA_BOUNDS,
    absolute_bounds: tuple[float, float] | None = None,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.BuildingLevelsMapResult:
    return savegame_maps.show_building_levels_map(
        data,
        scope=scope,
        name=name,
        mode=mode,
        baseline_date=baseline_date,
        delta_bounds=delta_bounds,
        absolute_bounds=absolute_bounds,
        width=width,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def food_price_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    absolute_bounds: tuple[float, float] | None = savegame_maps.DEFAULT_FOOD_PRICE_BOUNDS,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.FoodPriceMapResult:
    return savegame_maps.food_price_map(
        data,
        scope=scope,
        name=name,
        absolute_bounds=absolute_bounds,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def show_food_price_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    absolute_bounds: tuple[float, float] | None = savegame_maps.DEFAULT_FOOD_PRICE_BOUNDS,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.FoodPriceMapResult:
    return savegame_maps.show_food_price_map(
        data,
        scope=scope,
        name=name,
        absolute_bounds=absolute_bounds,
        width=width,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def employment_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    absolute_bounds: tuple[float, float] | None = savegame_maps.DEFAULT_EMPLOYMENT_BOUNDS,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.EmploymentMapResult:
    return savegame_maps.employment_map(
        data,
        scope=scope,
        name=name,
        absolute_bounds=absolute_bounds,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def show_employment_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    absolute_bounds: tuple[float, float] | None = savegame_maps.DEFAULT_EMPLOYMENT_BOUNDS,
    width: int | None = None,
    interval_ms: int = 700,
    display_widget: bool = True,
    display_diagnostics: bool = True,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> savegame_maps.EmploymentMapResult:
    return savegame_maps.show_employment_map(
        data,
        scope=scope,
        name=name,
        absolute_bounds=absolute_bounds,
        width=width,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )


def political_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    width: int | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    country_colors: Mapping[str, object] | None = None,
) -> savegame_maps.PoliticalMapResult:
    return savegame_maps.political_map(
        data,
        scope=scope,
        name=name,
        width=width,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        country_colors=country_colors,
    )


def show_political_map(
    data: SavegameNotebookData,
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
) -> savegame_maps.PoliticalMapResult:
    return savegame_maps.show_political_map(
        data,
        scope=scope,
        name=name,
        width=width,
        interval_ms=interval_ms,
        display_widget=display_widget,
        display_diagnostics=display_diagnostics,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        country_colors=country_colors,
    )


def save_building_levels_map_animation(
    result: savegame_maps.BuildingLevelsMapResult,
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
) -> savegame_maps.AnimationExportResult:
    return savegame_maps.save_building_levels_map_animation(
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
    result: savegame_maps.FoodPriceMapResult,
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
) -> savegame_maps.AnimationExportResult:
    return savegame_maps.save_food_price_map_animation(
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


def save_employment_map_animation(
    result: savegame_maps.EmploymentMapResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports"),
    filename: str = "employment_current.webp",
    duration_ms: int = 700,
    loop: int = 0,
    quality: int = 100,
    lossless: bool = True,
    width: int | None = None,
    max_bytes: int | None = None,
    overwrite: bool = True,
) -> savegame_maps.AnimationExportResult:
    return savegame_maps.save_employment_map_animation(
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
    result: savegame_maps.PoliticalMapResult,
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
) -> savegame_maps.AnimationExportResult:
    return savegame_maps.save_political_map_animation(
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


def goods_pressure(
    data: SavegameNotebookData,
    workbench: Any | None = None,
    *,
    selected_good: str | None = None,
    rank_mode: str = "shortage",
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    snapshot_date: int | None = None,
    top_n: int = 12,
    exclude_goods: Sequence[str] = ("food_revenue",),
    min_global_flow: float = 100.0,
    min_market_flow: float = 1.0,
) -> GoodsPressureResult:
    """Summarize global and market-level goods shortages or oversupply."""

    normalized_rank_mode = _normalize_goods_rank_mode(rank_mode)
    selected_playthrough = playthrough or getattr(workbench, "playthrough", None) or data.playthrough
    selected_start = (
        start_date
        if start_date is not None
        else getattr(getattr(workbench, "config", None), "start_date", None)
    )
    selected_end = (
        end_date
        if end_date is not None
        else getattr(getattr(workbench, "config", None), "end_date", None)
    )
    rows = _goods_pressure_rows(
        data,
        playthrough=selected_playthrough,
        start_date=selected_start,
        end_date=selected_end,
        exclude_goods=exclude_goods,
    )
    empty = _empty_goods_pressure_result(normalized_rank_mode)
    if rows.is_empty():
        return empty

    global_time_series = _goods_pressure_global_time_series(rows)
    if global_time_series.is_empty():
        return empty
    summary = _goods_pressure_summary(global_time_series, min_global_flow=min_global_flow)
    global_shortages = _goods_pressure_shortage_rank(summary, top_n=top_n)
    global_oversupply = _goods_pressure_oversupply_rank(summary, top_n=top_n)
    problem_goods = _goods_pressure_problem_goods(
        summary,
        global_shortages=global_shortages,
        global_oversupply=global_oversupply,
        rank_mode=normalized_rank_mode,
        top_n=top_n,
    )
    active_good = _resolve_goods_pressure_good(
        global_time_series,
        selected_good=selected_good,
        problem_goods=problem_goods,
    )
    if active_good is None:
        return GoodsPressureResult(
            global_time_series=global_time_series,
            summary=summary,
            global_shortages=global_shortages,
            global_oversupply=global_oversupply,
            problem_goods=problem_goods,
            selected_good=None,
            selected_good_label=None,
            selected_good_global=pl.DataFrame(),
            selected_good_markets=pl.DataFrame(),
            selected_good_market_time_series=pl.DataFrame(),
            rank_mode=normalized_rank_mode,
        )

    selected_global = global_time_series.filter(pl.col("good_id") == active_good).sort("date_sort")
    selected_label = _first_string(selected_global, "good_label") or active_good
    market_time_series = _goods_pressure_market_time_series(rows, active_good)
    latest_markets = _goods_pressure_latest_market_rank(
        market_time_series,
        snapshot_date=snapshot_date,
        rank_mode=normalized_rank_mode,
        min_market_flow=min_market_flow,
        top_n=top_n,
    )
    selected_market_time_series = _goods_pressure_top_market_time_series(
        market_time_series,
        latest_markets,
    )
    return GoodsPressureResult(
        global_time_series=global_time_series,
        summary=summary,
        global_shortages=global_shortages,
        global_oversupply=global_oversupply,
        problem_goods=problem_goods,
        selected_good=active_good,
        selected_good_label=selected_label,
        selected_good_global=selected_global,
        selected_good_markets=latest_markets,
        selected_good_market_time_series=selected_market_time_series,
        rank_mode=normalized_rank_mode,
    )


def show_goods_pressure(
    data: SavegameNotebookData,
    workbench: Any | None = None,
    *,
    selected_good: str | None = None,
    rank_mode: str = "shortage",
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    snapshot_date: int | None = None,
    top_n: int = 12,
    exclude_goods: Sequence[str] = ("food_revenue",),
    min_global_flow: float = 100.0,
    min_market_flow: float = 1.0,
    display_tables: bool = True,
) -> GoodsPressureResult:
    """Display goods pressure tables and selected-good trend plots."""

    result = goods_pressure(
        data,
        workbench,
        selected_good=selected_good,
        rank_mode=rank_mode,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        snapshot_date=snapshot_date,
        top_n=top_n,
        exclude_goods=exclude_goods,
        min_global_flow=min_global_flow,
        min_market_flow=min_market_flow,
    )
    fig = _goods_pressure_figure(result, top_n=top_n)
    if fig is None:
        print("No market goods rows")
    else:
        _display_figure(fig)
    if display_tables:
        if not result.problem_goods.is_empty():
            display(result.problem_goods)
        if not result.selected_good_markets.is_empty():
            display(result.selected_good_markets)
    return result


def food_price_volatility(
    data: SavegameNotebookData,
    workbench: Any | None = None,
    *,
    market_search: str | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    top_n: int = 12,
    min_snapshots: int = 2,
) -> FoodPriceVolatilityResult:
    """Summarize food-price volatility globally and per market."""

    selected_playthrough = playthrough or getattr(workbench, "playthrough", None) or data.playthrough
    selected_start = (
        start_date
        if start_date is not None
        else getattr(getattr(workbench, "config", None), "start_date", None)
    )
    selected_end = (
        end_date
        if end_date is not None
        else getattr(getattr(workbench, "config", None), "end_date", None)
    )
    selected_market_search = (
        market_search
        if market_search is not None
        else getattr(workbench, "market_query", None)
    )
    prices = _food_price_rows(
        data,
        playthrough=selected_playthrough,
        start_date=selected_start,
        end_date=selected_end,
        market_search=selected_market_search,
    )
    if prices.is_empty():
        empty_stats = pl.DataFrame(
            schema={
                "market_id": pl.Int64,
                "market_label": pl.String,
                "snapshots": pl.UInt32,
                "mean_food_price": pl.Float64,
                "median_food_price": pl.Float64,
                "stddev_food_price": pl.Float64,
                "min_food_price": pl.Float64,
                "max_food_price": pl.Float64,
                "price_range": pl.Float64,
                "mean_abs_price_change": pl.Float64,
                "max_abs_price_change": pl.Float64,
            }
        )
        return FoodPriceVolatilityResult(
            global_distribution=pl.DataFrame(),
            market_time_series=pl.DataFrame(),
            stats=empty_stats,
            top_erratic=empty_stats,
            top_victuals_erratic=empty_stats,
            market_search=selected_market_search,
        )

    group_columns = [
        column
        for column in ("market_id", "market_label")
        if column in prices.columns
    ]
    market_time_series = (
        prices.group_by(
            [
                "snapshot_id",
                "date_sort",
                "year",
                "month",
                "day",
                "date",
                "plot_year",
                *group_columns,
            ]
        )
        .agg(
            pl.mean("food_price").alias("food_price"),
            pl.mean("food_fill_ratio").alias("food_fill_ratio")
            if "food_fill_ratio" in prices.columns
            else pl.lit(None, dtype=pl.Float64).alias("food_fill_ratio"),
            pl.sum("food_balance").alias("food_balance")
            if "food_balance" in prices.columns
            else pl.lit(None, dtype=pl.Float64).alias("food_balance"),
        )
        .sort([*group_columns, "date_sort"] if group_columns else ["date_sort"])
    )
    if "market_id" not in market_time_series.columns:
        market_time_series = market_time_series.with_row_index("market_id")
    victuals = _market_good_price_rows(
        data,
        good_search="victuals",
        playthrough=selected_playthrough,
        start_date=selected_start,
        end_date=selected_end,
        market_search=selected_market_search,
    )
    market_time_series = _with_linked_victuals_columns(market_time_series, victuals)
    market_time_series = market_time_series.with_columns(
        (
            pl.col("food_price")
            - pl.col("food_price").shift(1).over("market_id")
        ).alias("price_delta"),
        (
            pl.col("victuals_price")
            - pl.col("victuals_price").shift(1).over("market_id")
        ).alias("victuals_price_delta"),
        pl.col("food_price").shift(1).over("market_id").alias("lagged_food_price"),
        pl.col("victuals_price").shift(1).over("market_id").alias("lagged_victuals_price"),
    ).with_columns(
        pl.col("price_delta").abs().alias("abs_price_delta"),
        pl.col("victuals_price_delta").abs().alias("victuals_abs_price_delta"),
    )

    global_distribution = (
        market_time_series.group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"])
        .agg(
            pl.len().alias("markets"),
            pl.mean("food_price").alias("mean_food_price"),
            pl.median("food_price").alias("median_food_price"),
            pl.col("food_price").std(ddof=0).alias("stddev_food_price"),
            pl.min("food_price").alias("min_food_price"),
            pl.max("food_price").alias("max_food_price"),
            pl.col("food_price").quantile(0.10).alias("price_p10"),
            pl.col("food_price").quantile(0.90).alias("price_p90"),
            pl.col("victuals_price").is_not_null().sum().alias("victuals_markets"),
            pl.mean("victuals_price").alias("mean_victuals_price"),
            pl.median("victuals_price").alias("median_victuals_price"),
            pl.col("victuals_price").std(ddof=0).alias("stddev_victuals_price"),
            pl.min("victuals_price").alias("min_victuals_price"),
            pl.max("victuals_price").alias("max_victuals_price"),
            pl.col("victuals_price").quantile(0.10).alias("victuals_price_p10"),
            pl.col("victuals_price").quantile(0.90).alias("victuals_price_p90"),
        )
        .sort("date_sort")
    )

    stats = (
        market_time_series.group_by("market_id", "market_label")
        .agg(
            pl.len().alias("snapshots"),
            pl.first("date").alias("first_date"),
            pl.last("date").alias("last_date"),
            pl.mean("food_price").alias("mean_food_price"),
            pl.median("food_price").alias("median_food_price"),
            pl.col("food_price").std(ddof=0).fill_null(0.0).alias("stddev_food_price"),
            pl.min("food_price").alias("min_food_price"),
            pl.max("food_price").alias("max_food_price"),
            (pl.max("food_price") - pl.min("food_price")).alias("price_range"),
            pl.mean("abs_price_delta").fill_null(0.0).alias("mean_abs_price_change"),
            pl.max("abs_price_delta").fill_null(0.0).alias("max_abs_price_change"),
            pl.col("victuals_price").is_not_null().sum().alias("victuals_snapshots"),
            pl.mean("victuals_price").alias("mean_victuals_price"),
            pl.median("victuals_price").alias("median_victuals_price"),
            pl.col("victuals_price").std(ddof=0).alias("stddev_victuals_price"),
            pl.min("victuals_price").alias("min_victuals_price"),
            pl.max("victuals_price").alias("max_victuals_price"),
            (pl.max("victuals_price") - pl.min("victuals_price")).alias("victuals_price_range"),
            pl.mean("victuals_abs_price_delta").alias("mean_abs_victuals_price_change"),
            pl.max("victuals_abs_price_delta").alias("max_abs_victuals_price_change"),
            pl.mean("victuals_price_ratio").alias("mean_victuals_price_ratio"),
            pl.corr("lagged_food_price", "victuals_price").alias("food_to_victuals_lag1_corr"),
            pl.corr("lagged_victuals_price", "food_price").alias("victuals_to_food_lag1_corr"),
        )
        .filter(pl.col("snapshots") >= min_snapshots)
        .with_columns(
            pl.when(pl.col("victuals_snapshots") > 0)
            .then(pl.col("stddev_victuals_price").fill_null(0.0))
            .otherwise(None)
            .alias("stddev_victuals_price"),
            pl.when(pl.col("victuals_snapshots") > 0)
            .then(pl.col("mean_abs_victuals_price_change").fill_null(0.0))
            .otherwise(None)
            .alias("mean_abs_victuals_price_change"),
            pl.when(pl.col("victuals_snapshots") > 0)
            .then(pl.col("max_abs_victuals_price_change").fill_null(0.0))
            .otherwise(None)
            .alias("max_abs_victuals_price_change"),
            pl.when(pl.col("mean_food_price").abs() > 0)
            .then(pl.col("stddev_food_price") / pl.col("mean_food_price").abs())
            .otherwise(None)
            .alias("coefficient_of_variation"),
            pl.when(pl.col("mean_victuals_price").abs() > 0)
            .then(pl.col("stddev_victuals_price") / pl.col("mean_victuals_price").abs())
            .otherwise(None)
            .alias("victuals_coefficient_of_variation"),
        )
        .sort(
            ["stddev_food_price", "mean_abs_price_change", "price_range", "market_label"],
            descending=[True, True, True, False],
        )
    )
    top_erratic = stats.head(top_n)
    top_victuals_erratic = (
        stats.filter(pl.col("victuals_snapshots") >= min_snapshots)
        .sort(
            [
                "stddev_victuals_price",
                "mean_abs_victuals_price_change",
                "victuals_price_range",
                "market_label",
            ],
            descending=[True, True, True, False],
        )
        .head(top_n)
    )
    return FoodPriceVolatilityResult(
        global_distribution=global_distribution,
        market_time_series=market_time_series,
        stats=stats,
        top_erratic=top_erratic,
        top_victuals_erratic=top_victuals_erratic,
        market_search=selected_market_search,
    )


def show_food_price_volatility(
    data: SavegameNotebookData,
    workbench: Any | None = None,
    *,
    market_search: str | None = None,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    top_n: int = 12,
    min_snapshots: int = 2,
    display_tables: bool = True,
) -> FoodPriceVolatilityResult:
    """Display compact food price volatility plots and summary tables."""

    result = food_price_volatility(
        data,
        workbench,
        market_search=market_search,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
        min_snapshots=min_snapshots,
    )
    fig = _food_price_volatility_figure(result, top_n=top_n)
    if fig is None:
        print("No food price rows")
    else:
        _display_figure(fig)
    if display_tables:
        if not result.top_erratic.is_empty():
            display(result.top_erratic)
        if not result.top_victuals_erratic.is_empty():
            display(result.top_victuals_erratic)
    return result


def save_food_price_volatility_webp(
    result: FoodPriceVolatilityResult,
    *,
    path: str | Path | None = None,
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports/absolute"),
    filename: str = "food_price_volatility.webp",
    quality: int = 92,
    lossless: bool = False,
    width: int | None = 1800,
    overwrite: bool = True,
    top_n: int = 8,
) -> FoodPriceVolatilityWebPExportResult | None:
    """Write a static WebP summary of food-price volatility."""

    output_path = _repo_relative_output_file(path=path, output_dir=output_dir, filename=filename)
    if output_path.exists() and not overwrite:
        raise FileExistsError(output_path)
    fig = _food_price_volatility_figure(result, top_n=top_n)
    if fig is None:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = _figure_to_image(fig, width=width)
    image.save(output_path, format="WEBP", quality=quality, lossless=lossless, method=6)
    return FoodPriceVolatilityWebPExportResult(
        path=output_path,
        format="webp",
        width=image.width,
        height=image.height,
        markets=result.stats.height,
        snapshots=result.global_distribution.height,
    )


def export_food_price_volatility_webp(
    *,
    repo: str | Path | None = None,
    data_root: str | Path | None = None,
    load_order_path: str | Path | None = None,
    profile: str | None = "constructor",
    output_dir: str | Path = Path("graphs/savegame_notebooks/exports/absolute"),
    filename: str = "food_price_volatility.webp",
    quality: int = 92,
    lossless: bool = False,
    width: int | None = 1800,
    top_n: int = 8,
) -> FoodPriceVolatilityWebPExportResult | None:
    """Open the raw savegame dataset and export the compact food-price WebP."""

    resolved_repo = _find_repo_root(_portable_path(repo) if repo is not None else None)
    data = open_data(
        repo=resolved_repo,
        data_root=data_root if data_root is not None else resolved_repo / "graphs" / "dataset",
        load_order_path=load_order_path if load_order_path is not None else resolved_repo / "constructor.load_order.toml",
        profile=profile,
        tables=("market_food", "market_goods"),
        load_map_assets=False,
    )
    result = food_price_volatility(data, top_n=max(top_n, 12))
    return save_food_price_volatility_webp(
        result,
        output_dir=_resolve_output_path(resolved_repo, output_dir),
        filename=filename,
        quality=quality,
        lossless=lossless,
        width=width,
        top_n=top_n,
    )


def export_global_map_animations(
    *,
    repo: str | Path | None = None,
    data_root: str | Path | None = None,
    load_order_path: str | Path | None = None,
    profile: str | None = "constructor",
    map_asset_width: int = 2400,
    map_width: int = 2000,
    export_width: int = 2200,
    interval_ms: int = 400,
    quality: int = 92,
    lossless: bool = False,
    max_webp_bytes: int | None = savegame_maps.DEFAULT_ANIMATION_MAX_BYTES,
    comparison_export_dir: str | Path = Path("graphs/savegame_notebooks/exports/comparison"),
    absolute_export_dir: str | Path = Path("graphs/savegame_notebooks/exports/absolute"),
) -> tuple[savegame_maps.AnimationExportResult, ...]:
    """Render the standard global savegame map WebP animations."""

    return export_global_map_outputs(
        repo=repo,
        data_root=data_root,
        load_order_path=load_order_path,
        profile=profile,
        map_asset_width=map_asset_width,
        map_width=map_width,
        export_width=export_width,
        interval_ms=interval_ms,
        quality=quality,
        lossless=lossless,
        max_webp_bytes=max_webp_bytes,
        comparison_export_dir=comparison_export_dir,
        absolute_export_dir=absolute_export_dir,
    ).animations


def export_global_map_outputs(
    *,
    repo: str | Path | None = None,
    data_root: str | Path | None = None,
    load_order_path: str | Path | None = None,
    profile: str | None = "constructor",
    map_asset_width: int = 2400,
    map_width: int = 2000,
    export_width: int = 2200,
    interval_ms: int = 400,
    quality: int = 92,
    lossless: bool = False,
    max_webp_bytes: int | None = savegame_maps.DEFAULT_ANIMATION_MAX_BYTES,
    comparison_export_dir: str | Path = Path("graphs/savegame_notebooks/exports/comparison"),
    absolute_export_dir: str | Path = Path("graphs/savegame_notebooks/exports/absolute"),
    viewer_path: str | Path = Path("graphs/savegame_notebooks/exports/savegame_maps.html"),
    viewer_frame_dir: str | Path = Path("viewer_frames"),
    viewer_assets: Sequence[tuple[str, str | Path]] = (),
) -> GlobalMapExportResult:
    """Render the standard global savegame map WebPs and HTML scrubber viewer."""

    resolved_repo = _find_repo_root(_portable_path(repo) if repo is not None else None)
    comparison_dir = _resolve_output_path(resolved_repo, comparison_export_dir)
    absolute_dir = _resolve_output_path(resolved_repo, absolute_export_dir)
    viewer_output = _resolve_output_path(resolved_repo, viewer_path)
    _remove_stale_comparison_exports(comparison_dir)
    _remove_stale_absolute_exports(absolute_dir)
    data = open_data(
        repo=resolved_repo,
        data_root=data_root if data_root is not None else resolved_repo / "graphs" / "dataset",
        load_order_path=load_order_path if load_order_path is not None else resolved_repo / "constructor.load_order.toml",
        profile=profile,
        tables=("locations", "countries", "buildings", "market_food"),
        load_map_assets=True,
        map_width=map_asset_width,
    )
    common = {
        "scope": "super_region",
        "name": None,
        "width": map_width,
    }
    exports: list[savegame_maps.AnimationExportResult] = []

    population_current = population_map(
        data,
        metric="total_population",
        comparison="current",
        absolute_bounds=savegame_maps.DEFAULT_POPULATION_ABSOLUTE_BOUNDS,
        absolute_scale="log1p",
        **common,
    )
    exports.append(
        save_population_map_animation(
            population_current,
            output_dir=absolute_dir,
            filename="population_current.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
            max_bytes=max_webp_bytes,
        )
    )

    employment_current = employment_map(
        data,
        absolute_bounds=savegame_maps.DEFAULT_EMPLOYMENT_BOUNDS,
        **common,
    )
    exports.append(
        save_employment_map_animation(
            employment_current,
            output_dir=absolute_dir,
            filename="employment_current.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
            max_bytes=max_webp_bytes,
        )
    )

    development_current = development_map(
        data,
        mode="current",
        absolute_bounds=savegame_maps.DEFAULT_DEVELOPMENT_BOUNDS,
        **common,
    )
    exports.append(
        save_development_map_animation(
            development_current,
            output_dir=absolute_dir,
            filename="development_current.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
            max_bytes=max_webp_bytes,
        )
    )

    building_levels_current = building_levels_map(
        data,
        mode="current",
        absolute_bounds=savegame_maps.DEFAULT_BUILDING_LEVEL_BOUNDS,
        **common,
    )
    exports.append(
        save_building_levels_map_animation(
            building_levels_current,
            output_dir=absolute_dir,
            filename="building_levels_current.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
            max_bytes=max_webp_bytes,
        )
    )

    food_price_current = food_price_map(
        data,
        absolute_bounds=savegame_maps.DEFAULT_FOOD_PRICE_BOUNDS,
        **common,
    )
    exports.append(
        save_food_price_map_animation(
            food_price_current,
            output_dir=absolute_dir,
            filename="food_price_current.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
            max_bytes=max_webp_bytes,
        )
    )
    political_current = political_map(
        data,
        **common,
    )
    exports.append(
        save_political_map_animation(
            political_current,
            output_dir=absolute_dir,
            filename="political_current.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
            max_bytes=max_webp_bytes,
        )
    )
    viewer = savegame_maps.save_map_viewer(
        [
            ("Population current", population_current),
            ("Employment current", employment_current),
            ("Development current", development_current),
            ("Building levels current", building_levels_current),
            ("Food price current", food_price_current),
            ("Political current", political_current),
        ],
        path=viewer_output,
        frame_dir=viewer_frame_dir,
        width=export_width,
        quality=quality,
        lossless=lossless,
        asset_links=viewer_assets,
    )
    return GlobalMapExportResult(animations=tuple(exports), viewer=viewer)


def _resolve_output_path(repo: Path, path: str | Path) -> Path:
    output = Path(path)
    return output if output.is_absolute() else repo / output


def _repo_relative_output_file(*, path: str | Path | None, output_dir: str | Path, filename: str) -> Path:
    output_path = Path(path) if path is not None else Path(output_dir) / filename
    if output_path.is_absolute():
        return output_path
    return _find_repo_root() / output_path


def _remove_stale_comparison_exports(comparison_dir: Path) -> None:
    for filename in (
        "population_change.webp",
        "development_from_gamestart.webp",
        "building_levels_from_gamestart.webp",
    ):
        path = comparison_dir / filename
        if path.exists():
            path.unlink()


def _remove_stale_absolute_exports(absolute_dir: Path) -> None:
    path = absolute_dir / "food_price_volatility.webp"
    if path.exists():
        path.unlink()


def global_buildings(data: SavegameNotebookData, workbench: Any) -> GlobalBuildingsResult:
    schema = {
        "snapshot_id": pl.String,
        "date_sort": pl.Int64,
        "year": pl.Int64,
        "month": pl.Int64,
        "day": pl.Int64,
        "date": pl.String,
        "level": pl.Float64,
    }
    frame = _selected_fact(data, workbench, "buildings", schema=schema)
    time_series = (
        frame.group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"])
        .agg(
            pl.sum("level").alias("total_building_levels"),
            pl.len().alias("building_records"),
        )
        .sort("date_sort")
        .collect()
    )
    return GlobalBuildingsResult(time_series)


def show_global_buildings(data: SavegameNotebookData, workbench: Any) -> GlobalBuildingsResult:
    result = global_buildings(data, workbench)
    if result.time_series.is_empty():
        print("No building rows")
        return result
    fig, ax = plt.subplots(figsize=NOTEBOOK_FIGSIZE)
    ax.plot(
        result.time_series["plot_year"].to_list(),
        result.time_series["total_building_levels"].to_list(),
        marker="o",
        linewidth=2.2,
        label="Total building levels",
    )
    ax.set_title("Global building levels over time")
    ax.set_xlabel("year")
    ax.set_ylabel("total building levels")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc="best")
    fig.tight_layout()
    _display_figure(fig)
    return result


def infrastructure_buildings(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    tag: str = "pp_logistics_infrastructure_priority",
    fallback_order: Sequence[str] = INFRASTRUCTURE_BUILDING_ORDER,
) -> InfrastructureBuildingsResult:
    building_types = building_types_for_custom_tag(data, tag, fallback_order)
    lookup = pl.DataFrame(
        {
            "building_type": building_types,
            "building_sort": list(range(len(building_types))),
        },
        schema={"building_type": pl.String, "building_sort": pl.Int64},
    )
    buildings = (
        lookup.join(
            data.dim("building_types").select(["building_type", "building_label"]),
            on="building_type",
            how="left",
        )
        .with_columns(pl.coalesce(pl.col("building_label"), pl.col("building_type")).alias("building_label"))
        .sort("building_sort")
    )
    schema = {
        "snapshot_id": pl.String,
        "date_sort": pl.Int64,
        "year": pl.Int64,
        "month": pl.Int64,
        "day": pl.Int64,
        "date": pl.String,
        "building_type": pl.String,
        "level": pl.Float64,
    }
    aggregated = (
        _selected_fact(data, workbench, "buildings", schema=schema)
        .filter(pl.col("building_type").is_in(building_types))
        .select(list(schema))
        .group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "building_type"])
        .agg(
            pl.sum("level").alias("total_building_levels"),
            pl.len().alias("building_records"),
        )
        .collect()
    )
    snapshots = _selected_snapshots(data, workbench)
    if buildings.is_empty() or snapshots.is_empty():
        return InfrastructureBuildingsResult(buildings, pl.DataFrame(), pl.DataFrame(), list(building_types))

    snapshot_plot = _with_plot_year(snapshots).select(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"]).sort("date_sort")
    time_series = (
        snapshot_plot.join(buildings, how="cross")
        .join(
            aggregated,
            on=["snapshot_id", "date_sort", "year", "month", "day", "date", "building_type"],
            how="left",
        )
        .with_columns(
            pl.col("total_building_levels").fill_null(0.0),
            pl.col("building_records").fill_null(0).cast(pl.Int64),
        )
        .sort(["building_sort", "date_sort"])
    )
    latest_date = time_series.get_column("date_sort").max()
    latest = (
        time_series.filter(pl.col("date_sort") == latest_date)
        .sort("building_sort")
        .select(["building_type", "building_label", "total_building_levels", "building_records"])
    )
    return InfrastructureBuildingsResult(buildings, time_series, latest, list(building_types))


def show_infrastructure_buildings(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    tag: str = "pp_logistics_infrastructure_priority",
    fallback_order: Sequence[str] = INFRASTRUCTURE_BUILDING_ORDER,
) -> InfrastructureBuildingsResult:
    result = infrastructure_buildings(data, workbench, tag=tag, fallback_order=fallback_order)
    if result.time_series.is_empty():
        print("No infrastructure building rows")
        return result
    fig, ax = plt.subplots(figsize=NOTEBOOK_FIGSIZE)
    for row in result.buildings.iter_rows(named=True):
        series = result.time_series.filter(pl.col("building_type") == row["building_type"]).sort("date_sort")
        ax.plot(
            series["plot_year"].to_list(),
            series["total_building_levels"].to_list(),
            marker="o",
            linewidth=2.0,
            label=row["building_label"],
        )
    ax.set_title(f"Global infrastructure building levels over time ({tag})")
    ax.set_xlabel("year")
    ax.set_ylabel("total building levels")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    fig.tight_layout()
    _display_figure(fig)
    display(result.latest)
    return result


def building_absolute_time_series(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    tag_filter: str | None = None,
    metric: str | None = None,
    top_n: int | None = None,
) -> BuildingAbsoluteResult:
    selected_types, tag_matches, tag_options = selected_building_types(data, workbench, tag_filter=tag_filter)
    buildings = _selected_fact(data, workbench, "buildings")
    columns = set(buildings.collect_schema().names())
    metric_name = metric or workbench.config.building_metric
    if metric_name not in columns:
        metric_name = "level"
    if selected_types is not None:
        buildings = buildings.filter(pl.col("building_type").is_in(selected_types))
    labels = data.dim("building_types").select(["building_type", "building_label"]).lazy()
    time_series = (
        buildings.group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year", "building_type"])
        .agg(pl.sum(metric_name).alias(metric_name))
        .join(labels, on="building_type", how="left")
        .with_columns(pl.coalesce(pl.col("building_label"), pl.col("building_type")).alias("building_label"))
        .sort(["date_sort", "building_label"])
        .collect()
    )
    top_time_series = top_building_absolute_time_series(
        time_series,
        metric=metric_name,
        top_n=top_n or workbench.config.top_n,
    )
    return BuildingAbsoluteResult(time_series, top_time_series, tag_matches, tag_options, metric_name)


def top_building_absolute_time_series(frame: pl.DataFrame, *, metric: str, top_n: int) -> pl.DataFrame:
    if frame.is_empty() or not {"date_sort", "building_label", metric}.issubset(frame.columns):
        return frame
    latest_date = frame.get_column("date_sort").max()
    top_labels = (
        frame.filter(pl.col("date_sort") == latest_date)
        .sort(metric, descending=True)
        .get_column("building_label")
        .head(top_n)
        .to_list()
    )
    return frame.filter(pl.col("building_label").is_in(top_labels)).sort(["building_label", "date_sort"])


def show_building_absolute_time_series(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    tag_filter: str | None = None,
    metric: str | None = None,
    top_n: int | None = None,
) -> BuildingAbsoluteResult:
    result = building_absolute_time_series(
        data,
        workbench,
        tag_filter=tag_filter,
        metric=metric,
        top_n=top_n,
    )
    plot_frame = result.top_time_series
    metric_name = result.metric
    if plot_frame.is_empty() or not {"plot_year", "date_sort", "building_label", metric_name}.issubset(plot_frame.columns):
        print("No rows")
        return result

    title_parts = [f"Building {metric_name} over time"]
    if tag_filter:
        title_parts.append(f"tag: {tag_filter}")
    if workbench.building_query is not None:
        title_parts.append(f"search: {workbench.building_query}")

    fig, ax = plt.subplots(figsize=(14, 6))
    for label in plot_frame.get_column("building_label").unique(maintain_order=True).to_list():
        series = plot_frame.filter(pl.col("building_label") == label).sort("date_sort")
        ax.plot(
            series["plot_year"].to_list(),
            series[metric_name].to_list(),
            marker="o",
            linewidth=2.0,
            label=label,
        )
    ax.set_title(" - ".join(title_parts))
    ax.set_xlabel("year")
    ax.set_ylabel(metric_name)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    fig.tight_layout()
    _display_figure(fig)
    return result


def show_building_slot(workbench: Any, buildings: Any, *, slot: int | str) -> None:
    if not hasattr(buildings, "pm_slot_time_series"):
        print("No building slot rows")
        return
    workbench.plot_building_slot(buildings, slot)


def plot_percent_stack(
    frame: pl.DataFrame,
    *,
    category: str,
    sort_col: str,
    title: str,
) -> None:
    if frame.is_empty() or not {"plot_year", "date_sort", category, "percent"}.issubset(frame.columns):
        print("No rows")
        return

    pivot = (
        frame.sort(["date_sort", sort_col])
        .pivot(
            index=["plot_year", "date_sort", "date"],
            on=category,
            values="percent",
            aggregate_function="first",
        )
        .sort("date_sort")
        .fill_null(0)
    )
    categories = [
        value
        for value in frame.sort(sort_col).get_column(category).unique(maintain_order=True).to_list()
        if value in pivot.columns
    ]
    if not categories:
        print("No rows")
        return

    x_values = pivot.get_column("plot_year").to_list()
    series = [pivot.get_column(value).to_list() for value in categories]
    fig, ax = plt.subplots(figsize=NOTEBOOK_FIGSIZE)
    if len(x_values) == 1:
        bottom = 0.0
        for label, values in zip(categories, series, strict=True):
            value = values[0] if values else 0.0
            ax.bar(x_values[0], value, bottom=bottom, width=0.45, label=label)
            bottom += value
        ax.set_xlim(x_values[0] - 0.75, x_values[0] + 0.75)
    else:
        ax.stackplot(x_values, series, labels=categories, alpha=0.88)
    ax.set_ylim(0, 100)
    ax.set_yticks(list(range(0, 101, 10)))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.grid(axis="y", which="major", linewidth=0.8, alpha=0.45)
    ax.grid(axis="x", which="major", linewidth=0.4, alpha=0.18)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title)
    ax.set_xlabel("year")
    ax.set_ylabel("global share")
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    fig.tight_layout()
    _display_figure(fig)


def _population_locations(
    data: SavegameNotebookData,
    *,
    metric: str,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    metric = _normalize_population_metric(metric)
    locations = data.table("locations")
    if locations.is_empty():
        return pl.DataFrame()
    if metric not in locations.columns:
        raise ValueError(f"Population metric {metric!r} is not available in the loaded locations table.")
    if "playthrough_id" in locations.columns:
        locations = locations.filter(pl.col("playthrough_id") == (playthrough or data.playthrough))
    if start_date is not None:
        locations = locations.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None:
        locations = locations.filter(pl.col("date_sort") <= int(end_date))
    locations = _with_plot_year(locations)

    geo_columns = [
        column
        for column in (
            "location_code",
            "slug",
            "location_id",
            "location_label",
            "area",
            "area_label",
            "region",
            "region_label",
            "macro_region",
            "macro_region_label",
            "super_region",
            "super_region_label",
            "country_label",
        )
        if column in data.dim("locations").columns
    ]
    if "location_code" in locations.columns and geo_columns:
        locations = locations.join(
            data.dim("locations").select(geo_columns),
            on="location_code",
            how="left",
        )
    return locations


def _population_global_time_series(locations: pl.DataFrame, *, metric: str) -> pl.DataFrame:
    if locations.is_empty():
        return pl.DataFrame()
    return (
        locations.group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"])
        .agg(pl.sum(metric).alias(metric))
        .sort("date_sort")
    )


def _population_breakdown_time_series(
    locations: pl.DataFrame,
    *,
    scope: str,
    name: str | None,
    child_scope: str | None,
    metric: str,
    top_n: int | None,
) -> tuple[pl.DataFrame, str, str | None, str | None]:
    if locations.is_empty():
        normalized_scope = _normalize_geography_scope(scope)
        return pl.DataFrame(), normalized_scope, None, None

    filter_scope = _normalize_geography_scope(scope)
    filter_name: str | None = None
    filtered = locations
    if _text_or_none(name) is not None:
        filtered, filter_name = _filter_population_scope(filtered, filter_scope, str(name))
    breakdown_scope = (
        _normalize_geography_scope(child_scope)
        if child_scope is not None
        else _child_geography_scope(filter_scope)
        if filter_name is not None
        else filter_scope
    )
    label_column = _scope_label_column(filtered, breakdown_scope)
    if label_column is None:
        return pl.DataFrame(), breakdown_scope, filter_scope if filter_name else None, filter_name
    frame = (
        filtered.with_columns(pl.col(label_column).fill_null("Unknown").cast(pl.String).alias("scope_label"))
        .group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year", "scope_label"])
        .agg(pl.sum(metric).alias(metric))
        .sort(["date_sort", "scope_label"])
    )
    frame = _limit_population_groups(frame, metric=metric, top_n=top_n)
    return frame, breakdown_scope, filter_scope if filter_name else None, filter_name


def _population_scope_locations(locations: pl.DataFrame, *, scope: str, name: str | None) -> pl.DataFrame:
    if locations.is_empty() or _text_or_none(name) is None:
        return locations
    filtered, _ = _filter_population_scope(locations, _normalize_geography_scope(scope), str(name))
    return filtered


def _pop_type_distribution_frame(locations: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    columns = (
        set(locations.collect_schema().names())
        if isinstance(locations, pl.LazyFrame)
        else set(locations.columns)
    )
    split_unemployed_peasants = {"population_peasants", "unemployed_peasants"}.issubset(columns)
    aggregations = [
        pl.sum(f"population_{pop_type}").alias(pop_type)
        for pop_type in POP_TYPE_BASE_ORDER
        if f"population_{pop_type}" in columns
    ]
    if split_unemployed_peasants:
        aggregations.append(pl.sum("unemployed_peasants").alias("unemployed_peasants"))
    if not aggregations:
        return pl.DataFrame()

    lazy_locations = locations if isinstance(locations, pl.LazyFrame) else locations.lazy()
    index = ["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"]
    wide = lazy_locations.group_by(index).agg(aggregations).sort("date_sort").collect()
    if split_unemployed_peasants:
        wide = wide.with_columns(
            pl.max_horizontal(
                pl.col("peasants") - pl.col("unemployed_peasants"),
                pl.lit(0.0),
            ).alias("peasants")
        )
    population_columns = [pop_type for pop_type in POP_TYPE_ORDER if pop_type in wide.columns]
    labels = _pop_type_labels(split_unemployed_peasants=split_unemployed_peasants)
    frame = (
        wide.unpivot(
            index=index,
            on=population_columns,
            variable_name="pop_type",
            value_name="population",
        )
        .with_columns(
            pl.col("pop_type")
            .replace_strict(labels, default=pl.col("pop_type"))
            .alias("pop_type_label")
        )
        .with_columns(pl.sum("population").over("snapshot_id").alias("total_population"))
        .with_columns(
            pl.when(pl.col("total_population") > 0)
            .then(pl.col("population") / pl.col("total_population") * 100.0)
            .otherwise(0.0)
            .alias("percent")
        )
    )
    size_order = (
        frame.group_by("pop_type")
        .agg(pl.sum("population").alias("sort_population"))
        .sort(["sort_population", "pop_type"], descending=[True, False])
        .with_row_index("pop_type_sort")
        .select(["pop_type", "pop_type_sort"])
    )
    return frame.join(size_order, on="pop_type", how="left").sort(["date_sort", "pop_type_sort"])


def _pop_type_labels(*, split_unemployed_peasants: bool) -> dict[str, str]:
    labels = dict(POP_TYPE_LABELS)
    if split_unemployed_peasants:
        labels["peasants"] = "Employed Peasants"
    return labels


def _population_pool_distribution_frame(
    data: SavegameNotebookData,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    pools = _selected_population_pool_table(
        data,
        playthrough=playthrough,
        start_date=start_date,
        end_date=end_date,
    )
    if pools.is_empty():
        return pl.DataFrame()
    columns = set(pools.columns)
    if not {"employed_peasants", "unemployed_peasants"}.issubset(columns):
        return pl.DataFrame()

    if "market_id" in columns:
        global_pools = pools.filter(pl.col("market_id").is_null())
    elif "market_center_slug" in columns:
        global_pools = pools.filter(pl.col("market_center_slug") == "Global")
    else:
        global_pools = pl.DataFrame()
    if global_pools.is_empty():
        return pl.DataFrame()

    aggregations: list[pl.Expr] = []
    for pop_type in POP_TYPE_BASE_ORDER:
        if pop_type == "peasants":
            aggregations.append(pl.sum("employed_peasants").alias("peasants"))
            aggregations.append(pl.sum("unemployed_peasants").alias("unemployed_peasants"))
            continue
        parts = [
            pl.col(column).fill_null(0)
            for column in (f"employed_{pop_type}", f"unemployed_{pop_type}")
            if column in columns
        ]
        if parts:
            aggregations.append(sum(parts).sum().alias(pop_type))
    if not aggregations:
        return pl.DataFrame()

    index = ["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"]
    wide = global_pools.lazy().group_by(index).agg(aggregations).sort("date_sort").collect()
    population_columns = [pop_type for pop_type in POP_TYPE_ORDER if pop_type in wide.columns]
    labels = _pop_type_labels(split_unemployed_peasants=True)
    frame = (
        wide.unpivot(
            index=index,
            on=population_columns,
            variable_name="pop_type",
            value_name="population",
        )
        .with_columns(
            pl.col("pop_type")
            .replace_strict(labels, default=pl.col("pop_type"))
            .alias("pop_type_label")
        )
        .with_columns(pl.sum("population").over("snapshot_id").alias("total_population"))
        .with_columns(
            pl.when(pl.col("total_population") > 0)
            .then(pl.col("population") / pl.col("total_population") * 100.0)
            .otherwise(0.0)
            .alias("percent")
        )
    )
    size_order = (
        frame.group_by("pop_type")
        .agg(pl.sum("population").alias("sort_population"))
        .sort(["sort_population", "pop_type"], descending=[True, False])
        .with_row_index("pop_type_sort")
        .select(["pop_type", "pop_type_sort"])
    )
    return frame.join(size_order, on="pop_type", how="left").sort(["date_sort", "pop_type_sort"])


def _selected_population_pool_table(
    data: SavegameNotebookData,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
) -> pl.DataFrame:
    frame = data.table(POPULATION_POOL_TABLE)
    dataset = getattr(data, "dataset", None)
    if (frame.is_empty() or "employed_peasants" not in frame.columns) and dataset is not None:
        frame = _load_population_pool_table(dataset, playthrough=playthrough or data.playthrough)
    if frame.is_empty():
        return frame
    if "playthrough_id" in frame.columns and (playthrough or data.playthrough) is not None:
        frame = frame.filter(pl.col("playthrough_id") == (playthrough or data.playthrough))
    if start_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") <= int(end_date))
    return _with_plot_year(frame)


def _load_population_pool_table(
    dataset: SavegameNotebookDataset,
    *,
    playthrough: str | None,
) -> pl.DataFrame:
    if not getattr(dataset, "is_raw", False):
        return dataset.scan_fact(POPULATION_POOL_TABLE, playthrough_id=playthrough).collect()
    return _load_raw_passthrough_table(dataset, POPULATION_POOL_TABLE, playthrough)


def _population_statistics_from_sources(
    data: SavegameNotebookData,
    locations: pl.DataFrame,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
    use_population_pools: bool,
) -> pl.DataFrame:
    if use_population_pools:
        pool_distribution = _population_pool_distribution_frame(
            data,
            playthrough=playthrough or data.playthrough,
            start_date=start_date,
            end_date=end_date,
        )
        if not pool_distribution.is_empty():
            return _population_statistics_from_distribution(pool_distribution)
    return _population_statistics_from_locations(locations)


def _population_statistics_from_locations(locations: pl.DataFrame) -> pl.DataFrame:
    if locations.is_empty():
        return _empty_population_statistics()
    return _population_statistics_from_distribution(_pop_type_distribution_frame(locations))


def _population_statistics_from_distribution(frame: pl.DataFrame) -> pl.DataFrame:
    required = {"date_sort", "pop_type", "pop_type_label", "population", "percent", "date", "pop_type_sort"}
    if frame.is_empty() or not required.issubset(frame.columns):
        return _empty_population_statistics()

    first_date_sort = frame.get_column("date_sort").min()
    latest_date_sort = frame.get_column("date_sort").max()
    first = (
        frame.filter(pl.col("date_sort") == first_date_sort)
        .select(
            [
                "pop_type",
                pl.col("date").alias("first_date"),
                pl.col("population").alias("first_population"),
                pl.col("percent").alias("first_share_percent"),
            ]
        )
    )
    latest = (
        frame.filter(pl.col("date_sort") == latest_date_sort)
        .select(
            [
                "pop_type",
                "pop_type_label",
                "pop_type_sort",
                pl.col("date").alias("latest_date"),
                pl.col("population").alias("latest_population"),
                pl.col("percent").alias("latest_share_percent"),
            ]
        )
    )
    return (
        latest.join(first, on="pop_type", how="left")
        .with_columns(
            [
                (pl.col("latest_population") - pl.col("first_population")).alias("population_delta"),
                (pl.col("latest_share_percent") - pl.col("first_share_percent")).alias("share_point_delta"),
            ]
        )
        .select(
            [
                "pop_type",
                "pop_type_label",
                "first_date",
                "latest_date",
                "first_population",
                "latest_population",
                "population_delta",
                "first_share_percent",
                "latest_share_percent",
                "share_point_delta",
                "pop_type_sort",
            ]
        )
        .sort("pop_type_sort")
    )


def _empty_population_statistics() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "pop_type": pl.String,
            "pop_type_label": pl.String,
            "first_date": pl.String,
            "latest_date": pl.String,
            "first_population": pl.Float64,
            "latest_population": pl.Float64,
            "population_delta": pl.Float64,
            "first_share_percent": pl.Float64,
            "latest_share_percent": pl.Float64,
            "share_point_delta": pl.Float64,
            "pop_type_sort": pl.UInt32,
        }
    )


def _population_breakdown_delta(frame: pl.DataFrame, *, metric: str) -> pl.DataFrame:
    if frame.is_empty() or not {"date_sort", "date", "scope_label", metric}.issubset(frame.columns):
        return pl.DataFrame()
    first_date_sort = frame.get_column("date_sort").min()
    latest_date_sort = frame.get_column("date_sort").max()
    first = (
        frame.filter(pl.col("date_sort") == first_date_sort)
        .select(
            [
                "scope_label",
                pl.col("date").alias("first_date"),
                pl.col(metric).alias(f"first_{metric}"),
            ]
        )
    )
    latest = (
        frame.filter(pl.col("date_sort") == latest_date_sort)
        .select(
            [
                "scope_label",
                pl.col("date").alias("latest_date"),
                pl.col(metric).alias(f"latest_{metric}"),
            ]
        )
    )
    delta_column = f"{metric}_delta"
    percent_column = f"{metric}_delta_percent"
    return (
        latest.join(first, on="scope_label", how="left")
        .with_columns((pl.col(f"latest_{metric}") - pl.col(f"first_{metric}")).alias(delta_column))
        .with_columns(
            pl.when(pl.col(f"first_{metric}") != 0)
            .then(pl.col(delta_column) / pl.col(f"first_{metric}") * 100.0)
            .otherwise(None)
            .alias(percent_column)
        )
        .select(
            [
                "scope_label",
                "first_date",
                "latest_date",
                f"first_{metric}",
                f"latest_{metric}",
                delta_column,
                percent_column,
            ]
        )
        .sort(delta_column, descending=True)
    )


def _plot_population_global(frame: pl.DataFrame, *, metric: str, display_metric: str) -> None:
    if frame.is_empty() or display_metric not in frame.columns:
        print("No population rows")
        return
    fig, ax = plt.subplots(figsize=NOTEBOOK_FIGSIZE)
    ax.plot(
        frame["plot_year"].to_list(),
        frame[display_metric].to_list(),
        marker="o",
        linewidth=2.2,
        label=_population_display_label(metric),
    )
    ax.set_title(f"Global {_population_metric_label(metric)} over time")
    ax.set_xlabel("year")
    ax.set_ylabel(_population_display_label(metric))
    ax.yaxis.set_major_formatter(FuncFormatter(_format_thousands_tick))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc="best")
    fig.tight_layout()
    _display_figure(fig)


def _plot_population_grouped(
    frame: pl.DataFrame,
    *,
    metric: str,
    display_metric: str,
    group_label: str,
    title: str,
) -> None:
    if frame.is_empty() or not {"plot_year", "date_sort", group_label, display_metric}.issubset(frame.columns):
        print("No population breakdown rows")
        return
    fig, ax = plt.subplots(figsize=NOTEBOOK_FIGSIZE)
    for label in frame.sort(group_label).get_column(group_label).unique(maintain_order=True).to_list():
        series = frame.filter(pl.col(group_label) == label).sort("date_sort")
        ax.plot(
            series["plot_year"].to_list(),
            series[display_metric].to_list(),
            marker="o",
            linewidth=2.0,
            label=str(label),
        )
    ax.set_title(title)
    ax.set_xlabel("year")
    ax.set_ylabel(_population_display_label(metric))
    ax.yaxis.set_major_formatter(FuncFormatter(_format_thousands_tick))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    fig.tight_layout()
    _display_figure(fig)


def _latest_population_breakdown(frame: pl.DataFrame, *, metric: str, display_metric: str) -> pl.DataFrame:
    if frame.is_empty() or not {"date_sort", "scope_label", metric, display_metric}.issubset(frame.columns):
        return pl.DataFrame()
    latest_date = frame.get_column("date_sort").max()
    return (
        frame.filter(pl.col("date_sort") == latest_date)
        .sort(metric, descending=True)
        .select(["scope_label", "date", display_metric])
    )


def _limit_population_groups(frame: pl.DataFrame, *, metric: str, top_n: int | None) -> pl.DataFrame:
    if top_n is None or top_n <= 0 or frame.is_empty():
        return frame
    latest_date = frame.get_column("date_sort").max()
    top_labels = (
        frame.filter(pl.col("date_sort") == latest_date)
        .sort(metric, descending=True)
        .get_column("scope_label")
        .head(top_n)
        .to_list()
    )
    return frame.filter(pl.col("scope_label").is_in(top_labels)).sort(["date_sort", "scope_label"])


def _population_breakdown_title(
    *,
    breakdown_scope: str,
    filter_scope: str | None,
    filter_name: str | None,
    metric: str,
) -> str:
    scope_label = GEOGRAPHY_SCOPE_LABELS[breakdown_scope]
    if filter_scope and filter_name:
        parent_label = GEOGRAPHY_SCOPE_LABELS[filter_scope]
        return f"{_population_metric_label(metric)} by {scope_label} within {parent_label} {filter_name}"
    return f"{_population_metric_label(metric)} by {scope_label}"


def _normalize_population_metric(metric: str) -> str:
    text = str(metric).strip()
    if text in {"population", "total", "total_pop"}:
        return "total_population"
    return text


def _population_metric_label(metric: str) -> str:
    return metric.replace("_", " ")


def _population_display_label(metric: str) -> str:
    return f"{_population_metric_label(metric)} (thousands)"


def _format_thousands_tick(value: float, _position: int) -> str:
    return f"{value:,.0f}"


def _normalize_geography_scope(scope: str | None) -> str:
    text = (scope or "super_region").strip().lower().replace(" ", "_").replace("-", "_")
    text = GEOGRAPHY_SCOPE_ALIASES.get(text, text)
    if text not in GEOGRAPHY_SCOPE_ORDER:
        valid = ", ".join(GEOGRAPHY_SCOPE_ORDER)
        raise ValueError(f"Unknown population scope {scope!r}. Expected one of: {valid}")
    return text


def _child_geography_scope(scope: str) -> str:
    index = GEOGRAPHY_SCOPE_ORDER.index(scope)
    if index >= len(GEOGRAPHY_SCOPE_ORDER) - 1:
        return scope
    return GEOGRAPHY_SCOPE_ORDER[index + 1]


def _scope_label_column(frame: pl.DataFrame, scope: str) -> str | None:
    candidates = (f"{scope}_label", "location_label") if scope == "location" else (f"{scope}_label", scope)
    for column in candidates:
        if column in frame.columns:
            return column
    return None


def _filter_population_scope(frame: pl.DataFrame, scope: str, name: str) -> tuple[pl.DataFrame, str]:
    columns = [column for column in GEOGRAPHY_SCOPE_SEARCH_COLUMNS[scope] if column in frame.columns]
    if not columns:
        return frame.head(0), name
    candidates = frame.select(columns).unique()
    query = name.strip().lower()
    candidate_texts: list[tuple[str, str, dict[str, object]]] = []
    for row in candidates.iter_rows(named=True):
        label = str(row.get(f"{scope}_label") or row.get("location_label") or next(iter(row.values())) or "")
        for column in columns:
            value = row.get(column)
            if value is None:
                continue
            candidate_texts.append((column, str(value), {**row, "_display_label": label}))

    for matcher in (
        lambda value: value == query,
        lambda value: value.startswith(query),
        lambda value: query in value,
    ):
        for column, value, row in candidate_texts:
            if matcher(value.lower()):
                return _filter_exact_scope_value(frame, column, value), str(row["_display_label"])

    close = get_close_matches(query, [value.lower() for _, value, _ in candidate_texts], n=1, cutoff=0.72)
    if close:
        for column, value, row in candidate_texts:
            if value.lower() == close[0]:
                return _filter_exact_scope_value(frame, column, value), str(row["_display_label"])
    return frame.head(0), name


def _filter_exact_scope_value(frame: pl.DataFrame, column: str, value: str) -> pl.DataFrame:
    return frame.filter(pl.col(column).cast(pl.String).str.to_lowercase() == value.lower())


def building_custom_tags(data: SavegameNotebookData) -> pl.DataFrame:
    schema = {"building_type": pl.String, "custom_tags": pl.List(pl.String)}
    if data.profile is None:
        return pl.DataFrame(schema=schema)
    try:
        profile = load_profile(data.profile, data.load_order_path)
        merged = load_merged_directory(profile, "building_types")
    except (FileNotFoundError, KeyError, OSError, pl.exceptions.PolarsError) as exc:
        print(f"Could not load building tags: {exc}")
        return pl.DataFrame(schema=schema)

    rows = []
    for entry in merged.entries:
        tags: list[str] = []
        if isinstance(entry.value, CList):
            for value in entry.value.values("custom_tags"):
                tags.extend(_clausewitz_string_list(value))
        rows.append({"building_type": entry.key, "custom_tags": sorted(set(tags))})
    return pl.DataFrame(rows, schema=schema)


def selected_building_types(
    data: SavegameNotebookData,
    workbench: Any,
    *,
    tag_filter: str | None = None,
) -> tuple[list[str] | None, pl.DataFrame, pl.DataFrame]:
    selected_sets: list[set[str]] = []
    if workbench.building_query is not None and "building_type" in workbench.building_matches.columns:
        selected_sets.append(set(workbench.building_matches.get_column("building_type").to_list()))

    tags = building_custom_tags(data)
    tag_options = (
        tags.explode("custom_tags")
        .drop_nulls("custom_tags")
        .group_by("custom_tags")
        .agg(pl.len().alias("buildings"))
        .sort("custom_tags")
        if not tags.is_empty()
        else pl.DataFrame(schema={"custom_tags": pl.String, "buildings": pl.UInt32})
    )

    if _text_or_none(tag_filter) is None:
        tag_matches = tags.head(0)
    else:
        tag_matches = tags.filter(pl.col("custom_tags").list.contains(str(tag_filter)))
        selected_sets.append(set(tag_matches.get_column("building_type").to_list()))

    if selected_sets:
        return sorted(set.intersection(*selected_sets)), tag_matches, tag_options
    return None, tag_matches, tag_options


def building_types_for_custom_tag(
    data: SavegameNotebookData,
    tag: str,
    fallback_order: Sequence[str],
) -> list[str]:
    tags = building_custom_tags(data)
    if tags.is_empty():
        return list(fallback_order)
    tagged = tags.filter(pl.col("custom_tags").list.contains(tag)).get_column("building_type").to_list()
    if not tagged:
        print(f"No buildings found for tag {tag!r}; using fallback list.")
        return list(fallback_order)
    sort_order = {building_type: index for index, building_type in enumerate(fallback_order)}
    return sorted(tagged, key=lambda building_type: (sort_order.get(building_type, len(sort_order)), building_type))


def _goods_pressure_rows(
    data: SavegameNotebookData,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
    exclude_goods: Sequence[str],
) -> pl.DataFrame:
    frame = data.table("market_goods")
    if frame.is_empty() or not {"good_id", "good_code"}.intersection(frame.columns):
        return pl.DataFrame()
    if playthrough is not None and "playthrough_id" in frame.columns:
        frame = frame.filter(pl.col("playthrough_id") == playthrough)
    if start_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") <= int(end_date))
    if frame.is_empty():
        return frame
    frame = _with_plot_year(frame)
    frame = _with_good_label_columns(data, frame)
    frame = _with_market_label_columns(data, frame)
    excluded = [str(good) for good in exclude_goods]
    if excluded:
        excluded_lower = [good.lower() for good in excluded]
        predicate = ~pl.col("good_id").cast(pl.String).str.to_lowercase().is_in(excluded_lower)
        if "good_label" in frame.columns:
            predicate = predicate & ~pl.col("good_label").cast(pl.String).str.to_lowercase().is_in(excluded_lower)
        frame = frame.filter(predicate)
    if frame.is_empty():
        return frame
    return _with_goods_pressure_numeric_columns(frame)


def _with_goods_pressure_numeric_columns(frame: pl.DataFrame) -> pl.DataFrame:
    result = frame
    numeric_columns = (
        "supply",
        "demand",
        "net",
        "stockpile",
        "price",
        "default_price",
    )
    for column in numeric_columns:
        if column not in result.columns:
            result = result.with_columns(pl.lit(None, dtype=pl.Float64).alias(column))
    return result.with_columns(
        *[pl.col(column).cast(pl.Float64).alias(column) for column in numeric_columns]
    )


def _goods_pressure_global_time_series(frame: pl.DataFrame) -> pl.DataFrame:
    required = {"snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year", "good_id", "good_label"}
    if frame.is_empty() or not required.issubset(frame.columns):
        return pl.DataFrame()
    grouped = (
        frame.group_by(["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year", "good_id", "good_label"])
        .agg(
            pl.len().alias("market_rows"),
            pl.sum("supply").alias("supply"),
            pl.sum("demand").alias("demand"),
            pl.sum("stockpile").alias("stockpile"),
            pl.mean("price").alias("mean_price"),
            pl.median("price").alias("median_price"),
            pl.col("price").quantile(0.10).alias("price_p10"),
            pl.col("price").quantile(0.90).alias("price_p90"),
            pl.max("default_price").alias("default_price"),
        )
        .with_columns(
            pl.col("supply").fill_null(0.0),
            pl.col("demand").fill_null(0.0),
            pl.col("stockpile").fill_null(0.0),
        )
    )
    return _with_goods_pressure_derived_columns(grouped).sort(["good_label", "date_sort"])


def _goods_pressure_market_time_series(frame: pl.DataFrame, good_id: str) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    selected = frame.filter(pl.col("good_id") == good_id)
    if selected.is_empty():
        return selected
    groups = [
        column
        for column in (
            "snapshot_id",
            "date_sort",
            "year",
            "month",
            "day",
            "date",
            "plot_year",
            "market_id",
            "market_label",
            "good_id",
            "good_label",
        )
        if column in selected.columns
    ]
    grouped = (
        selected.group_by(groups)
        .agg(
            pl.sum("supply").alias("supply"),
            pl.sum("demand").alias("demand"),
            pl.sum("stockpile").alias("stockpile"),
            pl.mean("price").alias("mean_price"),
            pl.median("price").alias("median_price"),
            pl.max("default_price").alias("default_price"),
        )
        .with_columns(
            pl.col("supply").fill_null(0.0),
            pl.col("demand").fill_null(0.0),
            pl.col("stockpile").fill_null(0.0),
        )
    )
    return _with_goods_pressure_derived_columns(grouped).sort(["market_label", "date_sort"])


def _with_goods_pressure_derived_columns(frame: pl.DataFrame) -> pl.DataFrame:
    result = frame.with_columns((pl.col("supply") - pl.col("demand")).alias("net")).with_columns(
        pl.col("net").alias("balance"),
        pl.max_horizontal(-pl.col("net"), pl.lit(0.0)).alias("shortage"),
        pl.max_horizontal(pl.col("net"), pl.lit(0.0)).alias("oversupply"),
        (pl.col("supply").fill_null(0.0) + pl.col("demand").fill_null(0.0)).alias("flow"),
    )
    return result.with_columns(
        pl.when(pl.col("flow") > 0)
        .then(100.0 * pl.col("net") / pl.col("flow"))
        .otherwise(None)
        .alias("imbalance_pct_of_flow"),
        pl.when(pl.col("default_price") > 0)
        .then(pl.col("mean_price") / pl.col("default_price"))
        .otherwise(None)
        .alias("price_ratio"),
        pl.when(pl.col("demand") > 0)
        .then(pl.col("stockpile") / pl.col("demand"))
        .otherwise(None)
        .alias("stockpile_months"),
    )


def _goods_pressure_summary(frame: pl.DataFrame, *, min_global_flow: float) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    grouped = (
        frame.sort(["good_id", "date_sort"])
        .group_by(["good_id", "good_label"])
        .agg(
            pl.len().alias("snapshots"),
            pl.first("date").alias("first_date"),
            pl.last("date").alias("last_date"),
            pl.mean("supply").alias("mean_supply"),
            pl.mean("demand").alias("mean_demand"),
            pl.mean("flow").alias("mean_flow"),
            pl.mean("net").alias("mean_net"),
            pl.min("net").alias("min_net"),
            pl.max("net").alias("max_net"),
            pl.mean("shortage").alias("mean_shortage"),
            pl.sum("shortage").alias("total_shortage"),
            pl.max("shortage").alias("max_shortage"),
            pl.mean("oversupply").alias("mean_oversupply"),
            pl.sum("oversupply").alias("total_oversupply"),
            pl.max("oversupply").alias("max_oversupply"),
            pl.col("balance").abs().mean().alias("mean_abs_balance"),
            pl.mean("imbalance_pct_of_flow").alias("mean_imbalance_pct_of_flow"),
            pl.mean("price_ratio").alias("mean_price_ratio"),
            pl.mean("stockpile_months").alias("mean_stockpile_months"),
            pl.last("supply").alias("latest_supply"),
            pl.last("demand").alias("latest_demand"),
            pl.last("net").alias("latest_net"),
            pl.last("balance").alias("latest_balance"),
            pl.last("shortage").alias("latest_shortage"),
            pl.last("oversupply").alias("latest_oversupply"),
            pl.last("imbalance_pct_of_flow").alias("latest_imbalance_pct_of_flow"),
            pl.last("mean_price").alias("latest_mean_price"),
            pl.last("median_price").alias("latest_median_price"),
            pl.last("price_ratio").alias("latest_price_ratio"),
            pl.last("stockpile").alias("latest_stockpile"),
            pl.last("stockpile_months").alias("latest_stockpile_months"),
        )
    )
    return (
        grouped.with_columns(
            pl.when(pl.col("mean_demand") > 0)
            .then(100.0 * pl.col("mean_shortage") / pl.col("mean_demand"))
            .otherwise(None)
            .alias("mean_shortage_pct_of_demand"),
            pl.when(pl.col("latest_demand") > 0)
            .then(100.0 * pl.col("latest_shortage") / pl.col("latest_demand"))
            .otherwise(None)
            .alias("latest_shortage_pct_of_demand"),
            pl.when(pl.col("mean_supply") > 0)
            .then(100.0 * pl.col("mean_oversupply") / pl.col("mean_supply"))
            .otherwise(None)
            .alias("mean_oversupply_pct_of_supply"),
            pl.when(pl.col("latest_supply") > 0)
            .then(100.0 * pl.col("latest_oversupply") / pl.col("latest_supply"))
            .otherwise(None)
            .alias("latest_oversupply_pct_of_supply"),
            pl.col("latest_balance").abs().alias("latest_abs_balance"),
        )
        .filter(pl.col("mean_flow") >= float(min_global_flow))
        .sort(["mean_abs_balance", "good_label"], descending=[True, False])
    )


def _goods_pressure_shortage_rank(summary: pl.DataFrame, *, top_n: int) -> pl.DataFrame:
    if summary.is_empty() or "mean_shortage" not in summary.columns:
        return summary
    return (
        summary.filter(pl.col("mean_shortage") > 0)
        .sort(
            ["mean_shortage", "latest_shortage", "mean_shortage_pct_of_demand", "good_label"],
            descending=[True, True, True, False],
        )
        .head(top_n)
    )


def _goods_pressure_oversupply_rank(summary: pl.DataFrame, *, top_n: int) -> pl.DataFrame:
    if summary.is_empty() or "mean_oversupply" not in summary.columns:
        return summary
    return (
        summary.filter(pl.col("mean_oversupply") > 0)
        .sort(
            ["mean_oversupply", "latest_oversupply", "mean_oversupply_pct_of_supply", "good_label"],
            descending=[True, True, True, False],
        )
        .head(top_n)
    )


def _goods_pressure_problem_goods(
    summary: pl.DataFrame,
    *,
    global_shortages: pl.DataFrame,
    global_oversupply: pl.DataFrame,
    rank_mode: str,
    top_n: int,
) -> pl.DataFrame:
    if rank_mode == "shortage":
        return global_shortages
    if rank_mode == "oversupply":
        return global_oversupply
    if summary.is_empty():
        return summary
    return summary.sort(
        ["mean_abs_balance", "latest_abs_balance", "good_label"],
        descending=[True, True, False],
    ).head(top_n)


def _goods_pressure_latest_market_rank(
    frame: pl.DataFrame,
    *,
    snapshot_date: int | None,
    rank_mode: str,
    min_market_flow: float,
    top_n: int,
) -> pl.DataFrame:
    latest = _latest_goods_snapshot_frame(frame, snapshot_date=snapshot_date)
    if latest.is_empty():
        return latest
    ranked = latest.filter(pl.col("flow") >= float(min_market_flow))
    if ranked.is_empty():
        return ranked
    if rank_mode == "shortage":
        sort_columns = ["shortage", "price_ratio", "market_label"]
        descending = [True, True, False]
    elif rank_mode == "oversupply":
        sort_columns = ["oversupply", "market_label"]
        descending = [True, False]
    else:
        ranked = ranked.with_columns(pl.col("balance").abs().alias("abs_balance"))
        sort_columns = ["abs_balance", "market_label"]
        descending = [True, False]
    return ranked.sort(sort_columns, descending=descending).head(top_n)


def _goods_pressure_top_market_time_series(
    frame: pl.DataFrame,
    latest_markets: pl.DataFrame,
) -> pl.DataFrame:
    if frame.is_empty() or latest_markets.is_empty() or "market_id" not in frame.columns:
        return pl.DataFrame()
    market_ids = latest_markets.get_column("market_id").to_list()
    return frame.filter(pl.col("market_id").is_in(market_ids)).sort(["market_label", "date_sort"])


def _latest_goods_snapshot_frame(frame: pl.DataFrame, *, snapshot_date: int | None) -> pl.DataFrame:
    if frame.is_empty() or "date_sort" not in frame.columns:
        return frame
    selected = frame
    if snapshot_date is not None:
        selected = selected.filter(pl.col("date_sort") <= int(snapshot_date))
    if selected.is_empty():
        return selected
    latest_date = selected.get_column("date_sort").max()
    return selected.filter(pl.col("date_sort") == latest_date)


def _resolve_goods_pressure_good(
    frame: pl.DataFrame,
    *,
    selected_good: str | None,
    problem_goods: pl.DataFrame,
) -> str | None:
    if frame.is_empty() or "good_id" not in frame.columns:
        return None
    query = _text_or_none(selected_good)
    if query is None:
        return _first_string(problem_goods, "good_id") or _first_string(frame, "good_id")
    options = frame.select(["good_id", "good_label"]).unique()
    lowered = query.lower()
    exact = options.filter(pl.col("good_id").cast(pl.String).str.to_lowercase() == lowered)
    if exact.is_empty() and "good_label" in options.columns:
        exact = options.filter(pl.col("good_label").cast(pl.String).str.to_lowercase() == lowered)
    if exact.is_empty() and "good_label" in options.columns:
        exact = options.filter(
            pl.col("good_id").cast(pl.String).str.to_lowercase().str.contains(lowered, literal=True)
            | pl.col("good_label").cast(pl.String).str.to_lowercase().str.contains(lowered, literal=True)
        )
    return _first_string(exact, "good_id")


def _normalize_goods_rank_mode(value: str) -> str:
    normalized = str(value or "shortage").strip().lower()
    if normalized in {"shortage", "shortages", "scarcity", "deficit"}:
        return "shortage"
    if normalized in {"oversupply", "surplus", "glut", "gluts"}:
        return "oversupply"
    if normalized in {"absolute", "abs", "imbalance", "balance"}:
        return "absolute"
    raise ValueError("rank_mode must be one of: shortage, oversupply, absolute")


def _empty_goods_pressure_result(rank_mode: str) -> GoodsPressureResult:
    return GoodsPressureResult(
        global_time_series=pl.DataFrame(),
        summary=pl.DataFrame(),
        global_shortages=pl.DataFrame(),
        global_oversupply=pl.DataFrame(),
        problem_goods=pl.DataFrame(),
        selected_good=None,
        selected_good_label=None,
        selected_good_global=pl.DataFrame(),
        selected_good_markets=pl.DataFrame(),
        selected_good_market_time_series=pl.DataFrame(),
        rank_mode=rank_mode,
    )


def _with_good_label_columns(data: SavegameNotebookData, frame: pl.DataFrame) -> pl.DataFrame:
    result = frame
    goods = data.dim("goods")
    if not goods.is_empty() and "good_label" not in result.columns:
        for key in ("good_code", "good_id"):
            if key in result.columns and key in goods.columns:
                label_columns = [
                    key,
                    *[
                        column
                        for column in ("good_id", "good_label", "good_name", "goods_category")
                        if column in goods.columns and column != key
                    ],
                ]
                result = result.join(goods.select(label_columns).unique(key), on=key, how="left")
                break
    if "good_label" not in result.columns:
        label_candidates: list[pl.Expr] = []
        for column in ("good_name", "good_id"):
            if column in result.columns:
                label_candidates.append(pl.col(column).cast(pl.String))
        if label_candidates:
            result = result.with_columns(pl.coalesce(label_candidates).alias("good_label"))
        else:
            result = result.with_columns(pl.lit("Good").alias("good_label"))
    return result.with_columns(pl.col("good_label").cast(pl.String).alias("good_label"))


def _market_good_price_rows(
    data: SavegameNotebookData,
    *,
    good_search: str,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
    market_search: str | None,
) -> pl.DataFrame:
    frame = data.table("market_goods")
    if frame.is_empty() or "price" not in frame.columns:
        return pl.DataFrame()
    if not {"good_id", "good_code", "good_label", "good_name"}.intersection(frame.columns):
        return pl.DataFrame()
    if playthrough is not None and "playthrough_id" in frame.columns:
        frame = frame.filter(pl.col("playthrough_id") == playthrough)
    if start_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") <= int(end_date))
    if frame.is_empty():
        return frame
    frame = _with_plot_year(frame)
    frame = _with_good_label_columns(data, frame)
    frame = _with_market_label_columns(data, frame)
    frame = _filter_food_price_markets(frame, market_search)
    frame = _filter_market_good(frame, good_search)
    if frame.is_empty():
        return frame
    frame = _with_goods_pressure_numeric_columns(frame).filter(pl.col("price").is_not_null())
    if frame.is_empty():
        return frame
    group_columns = [
        column
        for column in (
            "snapshot_id",
            "date_sort",
            "year",
            "month",
            "day",
            "date",
            "plot_year",
            "market_id",
            "market_label",
        )
        if column in frame.columns
    ]
    if "market_id" not in group_columns or not {"snapshot_id", "date_sort"}.intersection(group_columns):
        return pl.DataFrame()
    return (
        frame.group_by(group_columns)
        .agg(
            pl.mean("price").alias("victuals_price"),
            pl.max("default_price").alias("victuals_default_price"),
            pl.sum("supply").alias("victuals_supply"),
            pl.sum("demand").alias("victuals_demand"),
            pl.sum("stockpile").alias("victuals_stockpile"),
        )
        .with_columns(
            pl.when(pl.col("victuals_default_price") > 0)
            .then(pl.col("victuals_price") / pl.col("victuals_default_price"))
            .otherwise(None)
            .alias("victuals_price_ratio")
        )
        .sort(["market_label", "date_sort"] if "market_label" in group_columns else ["market_id", "date_sort"])
    )


def _filter_market_good(frame: pl.DataFrame, good_search: str) -> pl.DataFrame:
    query = _text_or_none(good_search)
    if query is None or frame.is_empty():
        return frame
    lowered = query.lower()
    predicates: list[pl.Expr] = []
    for column in ("good_id", "good_code"):
        if column in frame.columns:
            predicates.append(pl.col(column).cast(pl.String).str.to_lowercase() == lowered)
    for column in ("good_label", "good_name"):
        if column in frame.columns:
            lowered_column = pl.col(column).cast(pl.String).str.to_lowercase()
            predicates.append((lowered_column == lowered) | lowered_column.str.contains(lowered, literal=True))
    if not predicates:
        return frame.head(0)
    predicate = predicates[0]
    for term in predicates[1:]:
        predicate = predicate | term
    return frame.filter(predicate)


def _with_linked_victuals_columns(market_time_series: pl.DataFrame, victuals: pl.DataFrame) -> pl.DataFrame:
    value_columns = (
        "victuals_price",
        "victuals_default_price",
        "victuals_price_ratio",
        "victuals_supply",
        "victuals_demand",
        "victuals_stockpile",
    )
    result = market_time_series
    if not victuals.is_empty():
        join_columns = _price_link_join_columns(result, victuals)
        if join_columns:
            selected_columns = [*join_columns, *[column for column in value_columns if column in victuals.columns]]
            result = result.join(victuals.select(selected_columns), on=join_columns, how="left")
    for column in value_columns:
        if column not in result.columns:
            result = result.with_columns(pl.lit(None, dtype=pl.Float64).alias(column))
    return result


def _price_link_join_columns(left: pl.DataFrame, right: pl.DataFrame) -> list[str]:
    for candidate in (
        ("snapshot_id", "market_id"),
        ("date_sort", "market_id"),
        ("snapshot_id", "market_label"),
        ("date_sort", "market_label"),
    ):
        if all(column in left.columns and column in right.columns for column in candidate):
            return list(candidate)
    return []


def _first_string(frame: pl.DataFrame, column: str) -> str | None:
    if frame.is_empty() or column not in frame.columns:
        return None
    value = frame.item(0, column)
    return None if value is None else str(value)


def _food_price_rows(
    data: SavegameNotebookData,
    *,
    playthrough: str | None,
    start_date: int | None,
    end_date: int | None,
    market_search: str | None,
) -> pl.DataFrame:
    frame = data.table("market_food")
    if frame.is_empty() or "food_price" not in frame.columns:
        return pl.DataFrame()
    if playthrough is not None and "playthrough_id" in frame.columns:
        frame = frame.filter(pl.col("playthrough_id") == playthrough)
    if start_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None and "date_sort" in frame.columns:
        frame = frame.filter(pl.col("date_sort") <= int(end_date))
    frame = frame.filter(pl.col("food_price").is_not_null())
    if frame.is_empty():
        return frame
    frame = _with_plot_year(_with_food_fill_ratio(frame))
    frame = _with_market_label_columns(data, frame)
    frame = _filter_food_price_markets(frame, market_search)
    return frame.sort(["market_label", "date_sort"])


def _with_food_fill_ratio(frame: pl.DataFrame) -> pl.DataFrame:
    if "food_fill_ratio" in frame.columns:
        return frame
    if {"food", "food_max"}.issubset(frame.columns):
        return frame.with_columns(
            pl.when(pl.col("food_max") > 0)
            .then(pl.col("food") / pl.col("food_max"))
            .otherwise(None)
            .alias("food_fill_ratio")
        )
    if "food_fill_percent" in frame.columns:
        return frame.with_columns(
            pl.when(pl.col("food_fill_percent") > 1)
            .then(pl.col("food_fill_percent") / 100)
            .otherwise(pl.col("food_fill_percent"))
            .alias("food_fill_ratio")
        )
    return frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("food_fill_ratio"))


def _with_market_label_columns(data: SavegameNotebookData, frame: pl.DataFrame) -> pl.DataFrame:
    result = frame
    markets = data.dim("markets")
    if not markets.is_empty() and "market_label" not in result.columns:
        for key in ("market_code", "market_id"):
            if key in result.columns and key in markets.columns:
                label_columns = [
                    key,
                    *[
                        column
                        for column in ("market_id", "market_label", "market_name", "market_center_slug")
                        if column in markets.columns and column != key
                    ],
                ]
                result = result.join(markets.select(label_columns).unique(key), on=key, how="left")
                break

    if "market_id" not in result.columns:
        id_source = next(
            (
                column
                for column in ("market_code", "market_label", "market_name", "market_center_slug")
                if column in result.columns
            ),
            None,
        )
        if id_source is None:
            result = result.with_row_index("market_id")
        else:
            result = result.with_columns(pl.col(id_source).rank("dense").cast(pl.Int64).alias("market_id"))
    label_candidates: list[pl.Expr] = []
    for column in ("market_label", "market_name", "market_center_slug"):
        if column in result.columns:
            label_candidates.append(pl.col(column).cast(pl.String))
    if "market_id" in result.columns:
        label_candidates.append(pl.concat_str([pl.lit("Market #"), pl.col("market_id").cast(pl.String)]))
    if label_candidates:
        result = result.with_columns(pl.coalesce(label_candidates).alias("market_label"))
    else:
        result = result.with_columns(pl.lit("Market").alias("market_label"))
    return result


def _filter_food_price_markets(frame: pl.DataFrame, market_search: str | None) -> pl.DataFrame:
    query = _text_or_none(market_search)
    if query is None or frame.is_empty():
        return frame
    terms = []
    for column in ("market_label", "market_name", "market_center_slug", "market_id"):
        if column in frame.columns:
            terms.append(pl.col(column).cast(pl.String).str.to_lowercase().str.contains(query.lower(), literal=True))
    if not terms:
        return frame.head(0)
    predicate = terms[0]
    for term in terms[1:]:
        predicate = predicate | term
    return frame.filter(predicate)


def _goods_pressure_figure(
    result: GoodsPressureResult,
    *,
    top_n: int,
) -> Any | None:
    if result.selected_good_global.is_empty():
        return None
    selected = result.selected_good_global.sort("date_sort")
    title_good = result.selected_good_label or result.selected_good or "selected good"
    fig, axes = plt.subplots(2, 2, figsize=(18, 10))
    ax_flow, ax_stockpile, ax_price, ax_markets = axes.ravel()
    x_values = selected["plot_year"].to_list() if "plot_year" in selected.columns else selected["year"].to_list()

    for metric, label, linewidth in (
        ("supply", "Supply", 2.0),
        ("demand", "Demand", 2.0),
        ("balance", "Balance", 1.8),
    ):
        if metric in selected.columns:
            ax_flow.plot(x_values, selected[metric].to_list(), marker="o", linewidth=linewidth, label=label)
    ax_flow.axhline(0, color="#111827", linewidth=0.9, alpha=0.45)
    ax_flow.set_title(f"{title_good}: global supply, demand, and balance")
    ax_flow.set_xlabel("year")
    ax_flow.set_ylabel("goods")
    ax_flow.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_flow.legend(loc="best", fontsize=9)

    if "stockpile" in selected.columns:
        ax_stockpile.plot(x_values, selected["stockpile"].to_list(), marker="o", linewidth=2.0, label="Stockpile")
    if "stockpile_months" in selected.columns:
        ax_stockpile.plot(x_values, selected["stockpile_months"].to_list(), marker="o", linewidth=1.8, label="Stockpile / monthly demand")
    ax_stockpile.set_title(f"{title_good}: stockpile")
    ax_stockpile.set_xlabel("year")
    ax_stockpile.set_ylabel("value")
    ax_stockpile.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_stockpile.legend(loc="best", fontsize=9)

    if {"price_p10", "price_p90"}.issubset(selected.columns):
        ax_price.fill_between(
            x_values,
            selected["price_p10"].to_list(),
            selected["price_p90"].to_list(),
            alpha=0.20,
            label="10th-90th percentile",
        )
    for metric, label in (("median_price", "Median price"), ("mean_price", "Mean price"), ("price_ratio", "Mean / default")):
        if metric in selected.columns:
            ax_price.plot(x_values, selected[metric].to_list(), marker="o", linewidth=1.9, label=label)
    ax_price.set_title(f"{title_good}: price")
    ax_price.set_xlabel("year")
    ax_price.set_ylabel("price")
    ax_price.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_price.legend(loc="best", fontsize=9)

    market_frame = result.selected_good_market_time_series
    if not market_frame.is_empty() and "market_label" in market_frame.columns:
        metric = "shortage" if result.rank_mode == "shortage" else "oversupply"
        if result.rank_mode == "absolute":
            market_frame = market_frame.with_columns(pl.col("balance").abs().alias("abs_balance"))
            metric = "abs_balance"
        labels = (
            result.selected_good_markets.get_column("market_label").head(top_n).to_list()
            if "market_label" in result.selected_good_markets.columns
            else market_frame.get_column("market_label").unique().head(top_n).to_list()
        )
        for label in labels:
            series = market_frame.filter(pl.col("market_label") == label).sort("date_sort")
            if series.is_empty() or metric not in series.columns:
                continue
            x_market = series["plot_year"].to_list() if "plot_year" in series.columns else series["year"].to_list()
            ax_markets.plot(x_market, series[metric].to_list(), marker="o", linewidth=1.6, label=str(label))
        ax_markets.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    ax_markets.set_title(f"{title_good}: worst markets by {result.rank_mode}")
    ax_markets.set_xlabel("year")
    ax_markets.set_ylabel(result.rank_mode)
    ax_markets.xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.tight_layout()
    return fig


def _food_price_volatility_figure(
    result: FoodPriceVolatilityResult,
    *,
    top_n: int,
) -> Any | None:
    if result.global_distribution.is_empty() or result.top_erratic.is_empty():
        return None
    plot_markets = result.top_erratic.get_column("market_label").head(top_n).to_list()
    line_frame = result.market_time_series.filter(pl.col("market_label").is_in(plot_markets)).sort(["market_label", "date_sort"])
    has_victuals = _has_non_null_values(result.market_time_series, "victuals_price")

    if has_victuals:
        fig, (ax_band, ax_victuals, ax_lines) = plt.subplots(
            1,
            3,
            figsize=(21, 6),
            gridspec_kw={"width_ratios": [1.0, 1.0, 1.4]},
        )
    else:
        fig, (ax_band, ax_lines) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1.05, 1.35]})
    global_frame = result.global_distribution.sort("date_sort")
    x_values = global_frame["plot_year"].to_list()
    ax_band.fill_between(
        x_values,
        global_frame["price_p10"].to_list(),
        global_frame["price_p90"].to_list(),
        alpha=0.20,
        label="10th-90th percentile",
    )
    ax_band.plot(
        x_values,
        global_frame["median_food_price"].to_list(),
        linewidth=2.3,
        label="Global median",
    )
    ax_band.plot(
        x_values,
        global_frame["mean_food_price"].to_list(),
        linewidth=1.8,
        linestyle="--",
        label="Global mean",
    )
    ax_band.set_title("Food Price Distribution")
    ax_band.set_xlabel("year")
    ax_band.set_ylabel("food price")
    ax_band.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_band.legend(loc="best", fontsize=9)

    if has_victuals:
        victuals_global = global_frame.filter(pl.col("victuals_markets") > 0).sort("date_sort")
        x_victuals = victuals_global["plot_year"].to_list()
        ax_victuals.fill_between(
            x_victuals,
            victuals_global["victuals_price_p10"].to_list(),
            victuals_global["victuals_price_p90"].to_list(),
            alpha=0.20,
            label="10th-90th percentile",
        )
        ax_victuals.plot(
            x_victuals,
            victuals_global["median_victuals_price"].to_list(),
            linewidth=2.3,
            label="Global median",
        )
        ax_victuals.plot(
            x_victuals,
            victuals_global["mean_victuals_price"].to_list(),
            linewidth=1.8,
            linestyle="--",
            label="Global mean",
        )
        ax_victuals.set_title("Victuals Price Distribution")
        ax_victuals.set_xlabel("year")
        ax_victuals.set_ylabel("victuals price")
        ax_victuals.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax_victuals.legend(loc="best", fontsize=9)

    for label in plot_markets:
        series = line_frame.filter(pl.col("market_label") == label).sort("date_sort")
        if series.is_empty():
            continue
        x_market = series["plot_year"].to_list()
        if has_victuals:
            food_line = ax_lines.plot(
                x_market,
                _indexed_price_values(series, "food_price"),
                linewidth=1.9,
                marker="o",
                markersize=3.5,
                label=str(label),
            )[0]
            victuals_values = _indexed_price_values(series, "victuals_price")
            if any(value is not None for value in victuals_values):
                ax_lines.plot(
                    x_market,
                    victuals_values,
                    linewidth=1.7,
                    linestyle="--",
                    marker="x",
                    markersize=3.5,
                    color=food_line.get_color(),
                    label="_nolegend_",
                )
        else:
            ax_lines.plot(
                x_market,
                series["food_price"].to_list(),
                linewidth=1.9,
                marker="o",
                markersize=3.5,
                label=str(label),
            )
    title = "Most Erratic Food Markets"
    if result.market_search:
        title = f"{title}: {result.market_search}"
    if has_victuals:
        title = f"{title} (solid food, dashed victuals)"
    ax_lines.set_title(title)
    ax_lines.set_xlabel("year")
    ax_lines.set_ylabel("price index (market mean = 1)" if has_victuals else "food price")
    ax_lines.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_lines.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)

    summary = result.stats.select(
        pl.len().alias("markets"),
        pl.mean("stddev_food_price").alias("mean_stddev"),
        pl.median("stddev_food_price").alias("median_stddev"),
        pl.max("stddev_food_price").alias("max_stddev"),
        pl.mean("mean_abs_price_change").alias("mean_step_change"),
        pl.mean("stddev_victuals_price").alias("mean_victuals_stddev"),
        pl.mean("mean_abs_victuals_price_change").alias("mean_victuals_step_change"),
    ).to_dicts()[0]
    subtitle = (
        f"{int(summary['markets'])} markets | "
        f"stdev mean {summary['mean_stddev']:.3f}, "
        f"median {summary['median_stddev']:.3f}, "
        f"max {summary['max_stddev']:.3f} | "
        f"mean step {summary['mean_step_change']:.3f}"
    )
    if has_victuals and summary["mean_victuals_stddev"] is not None:
        subtitle = (
            f"{subtitle} | victuals stdev mean {summary['mean_victuals_stddev']:.3f}, "
            f"mean step {summary['mean_victuals_step_change']:.3f}"
        )
    fig.suptitle(subtitle, fontsize=11, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def _has_non_null_values(frame: pl.DataFrame, column: str) -> bool:
    return not frame.is_empty() and column in frame.columns and frame.get_column(column).drop_nulls().len() > 0


def _indexed_price_values(frame: pl.DataFrame, column: str) -> list[float | None]:
    if column not in frame.columns:
        return [None] * frame.height
    values = frame.get_column(column).to_list()
    numeric_values = [float(value) for value in values if value is not None]
    if not numeric_values:
        return [None] * len(values)
    baseline = sum(numeric_values) / len(numeric_values)
    if baseline == 0:
        return [None if value is None else float(value) for value in values]
    return [None if value is None else float(value) / baseline for value in values]


def _figure_to_image(fig: Any, *, width: int | None) -> Any:
    from PIL import Image

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    image = Image.open(buffer).convert("RGB")
    if width is not None and width > 0 and image.width != int(width):
        height = max(1, round(image.height * int(width) / image.width))
        image = image.resize((int(width), height), Image.Resampling.LANCZOS)
    return image


def _find_repo_root(start: Path | None = None) -> Path:
    current = _portable_path(start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "constructor.toml").is_file():
            return candidate
    raise FileNotFoundError("Could not find constructor.toml; run this notebook from the constructor repo.")


def _portable_path(value: str | Path) -> Path:
    path = Path(value)
    if path.exists():
        return path
    text = str(value).replace("\\", "/")
    wsl_match = re.match(r"^/mnt/([A-Za-z])/(.*)$", text)
    if wsl_match:
        drive, rest = wsl_match.groups()
        return Path(f"{drive.upper()}:/{rest}")
    windows_match = re.match(r"^([A-Za-z]):/(.*)$", text)
    if windows_match:
        drive, rest = windows_match.groups()
        candidate = Path("/mnt") / drive.lower() / rest
        if candidate.exists():
            return candidate
    return path


def _load_dimensions(dataset: SavegameNotebookDataset) -> dict[str, pl.DataFrame]:
    dimensions: dict[str, pl.DataFrame] = {}
    for name in ("playthroughs", *DIMENSION_SPECS.keys()):
        frame = dataset.dim(name)
        if not frame.is_empty():
            dimensions[name] = frame
    return dimensions


def _load_tables(
    dataset: SavegameNotebookDataset,
    playthrough: str | None,
    tables: Sequence[str] | str | None,
) -> dict[str, pl.DataFrame]:
    table_names = _normalize_table_names(tables)
    loaded: dict[str, pl.DataFrame] = {}
    for table in table_names:
        if table in RAW_PASSTHROUGH_TABLES and getattr(dataset, "is_raw", False):
            loaded[table] = _load_raw_passthrough_table(dataset, table, playthrough)
        else:
            loaded[table] = dataset.scan_fact(table, playthrough_id=playthrough).collect()
    return loaded


def _normalize_table_names(tables: Sequence[str] | str | None) -> tuple[str, ...]:
    if tables is None:
        return ()
    if isinstance(tables, str):
        if tables in {"all", "default", "analysis"}:
            return DEFAULT_NOTEBOOK_TABLES
        return (tables,)
    return tuple(dict.fromkeys(str(table) for table in tables))


def _load_raw_passthrough_table(
    dataset: SavegameNotebookDataset,
    table: str,
    playthrough: str | None,
) -> pl.DataFrame:
    files = dataset.fact_files(table, playthrough_id=playthrough)
    if not files:
        return pl.DataFrame()
    return pl.scan_parquet(
        [str(path) for path in files],
        hive_partitioning=False,
        missing_columns="insert",
        extra_columns="ignore",
    ).collect()


def _configure_notebook_plots(wb: Any) -> None:
    plt.rcParams["figure.figsize"] = NOTEBOOK_FIGSIZE
    plt.rcParams["figure.dpi"] = 110
    plt.rcParams["savefig.dpi"] = 140

    original = getattr(plt, "_ppc_original_subplots", plt.subplots)

    def _ppc_wide_subplots(*args: Any, **kwargs: Any) -> Any:
        figsize = kwargs.get("figsize")
        if figsize is None:
            figsize = NOTEBOOK_FIGSIZE
        else:
            figsize = (
                max(float(figsize[0]), NOTEBOOK_MIN_FIGURE_WIDTH),
                max(float(figsize[1]), NOTEBOOK_MIN_FIGURE_HEIGHT),
            )
        kwargs["figsize"] = figsize
        return original(*args, **kwargs)

    plt._ppc_original_subplots = original
    plt.subplots = _ppc_wide_subplots
    wb.plt.subplots = _ppc_wide_subplots


def _selected_snapshots(data: SavegameNotebookData, workbench: Any) -> pl.DataFrame:
    return _selected_snapshots_values(
        data,
        playthrough=workbench.playthrough,
        start_date=workbench.config.start_date,
        end_date=workbench.config.end_date,
    )


def _selected_snapshots_values(
    data: SavegameNotebookData,
    *,
    playthrough: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> pl.DataFrame:
    selected_playthrough = playthrough or data.playthrough
    frame = data.snapshots
    if selected_playthrough is not None:
        frame = frame.filter(pl.col("playthrough_id") == selected_playthrough)
    frame = frame.sort("date_sort")
    if start_date is not None:
        frame = frame.filter(pl.col("date_sort") >= int(start_date))
    if end_date is not None:
        frame = frame.filter(pl.col("date_sort") <= int(end_date))
    return frame


def _selected_locations(data: SavegameNotebookData, workbench: Any) -> pl.LazyFrame:
    return _selected_fact(data, workbench, "locations")


def _selected_fact(
    data: SavegameNotebookData,
    workbench: Any,
    table: str,
    *,
    schema: dict[str, pl.DataType] | None = None,
) -> pl.LazyFrame:
    frame = data.table(table)
    if frame.is_empty():
        return pl.DataFrame(schema=schema or {}).lazy()
    if "playthrough_id" in frame.columns:
        frame = frame.filter(pl.col("playthrough_id") == workbench.playthrough)
    if workbench.config.start_date is not None:
        frame = frame.filter(pl.col("date_sort") >= int(workbench.config.start_date))
    if workbench.config.end_date is not None:
        frame = frame.filter(pl.col("date_sort") <= int(workbench.config.end_date))
    return _with_plot_year(frame.lazy())


def _with_plot_year(frame: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    return frame.with_columns(
        (
            pl.col("year").cast(pl.Float64)
            + (pl.col("month").cast(pl.Float64) - 1.0) / 12.0
            + (pl.col("day").cast(pl.Float64) - 1.0) / 365.25
        ).alias("plot_year")
    )


def _clausewitz_string_list(value: object) -> list[str]:
    if isinstance(value, CList):
        return [str(item) for item in value.items]
    if value is None:
        return []
    return [str(value)]


def _text_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _display_figure(fig: Any) -> None:
    display(fig, include=["image/png"])
    plt.close(fig)
