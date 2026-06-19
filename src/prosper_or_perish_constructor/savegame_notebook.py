"""Notebook-facing savegame analysis helpers.

This module keeps the savegame notebook thin: notebook cells should set a few
section parameters, call one function, and optionally bind returned frames for
interactive inspection.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from difflib import get_close_matches
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

DEFAULT_NOTEBOOK_TABLES = tuple(FACT_TABLES)

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
    metric: str
    display_metric: str
    breakdown_scope: str
    filter_scope: str | None
    filter_name: str | None


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
    locations = _selected_locations(data, workbench)
    columns = set(locations.collect_schema().names())
    split_unemployed_peasants = {"population_peasants", "unemployed_peasants"}.issubset(columns)
    aggregations = [
        pl.sum(f"population_{pop_type}").alias(pop_type)
        for pop_type in POP_TYPE_BASE_ORDER
        if f"population_{pop_type}" in columns
    ]
    if split_unemployed_peasants:
        aggregations.append(pl.sum("unemployed_peasants").alias("unemployed_peasants"))
    if not aggregations:
        return DistributionResult(pl.DataFrame())

    index = ["snapshot_id", "date_sort", "year", "month", "day", "date", "plot_year"]
    wide = locations.group_by(index).agg(aggregations).sort("date_sort").collect()
    if split_unemployed_peasants:
        wide = wide.with_columns(
            pl.max_horizontal(
                pl.col("peasants") - pl.col("unemployed_peasants"),
                pl.lit(0.0),
            ).alias("peasants")
        )
    population_columns = [pop_type for pop_type in POP_TYPE_ORDER if pop_type in wide.columns]
    frame = (
        wide.unpivot(
            index=index,
            on=population_columns,
            variable_name="pop_type",
            value_name="population",
        )
        .with_columns(
            pl.col("pop_type")
            .replace_strict(POP_TYPE_LABELS, default=pl.col("pop_type"))
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
    return DistributionResult(frame.join(size_order, on="pop_type", how="left").sort(["date_sort", "pop_type_sort"]))


def show_pop_type_distribution(data: SavegameNotebookData, workbench: Any) -> DistributionResult:
    result = pop_type_distribution(data, workbench)
    plot_percent_stack(
        result.frame,
        category="pop_type_label",
        sort_col="pop_type_sort",
        title="Global pop type distribution",
    )
    return result


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
    return PopulationResult(
        global_df=global_df,
        breakdown_df=breakdown_df,
        latest_breakdown_df=latest_breakdown_df,
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
    return result


def population_map(
    data: SavegameNotebookData,
    *,
    scope: str = "super_region",
    name: str | None = None,
    metric: str = "total_population",
    baseline_date: int | str | None = None,
    comparison: str = "relative_pct",
    relative_bounds: tuple[float, float] = savegame_maps.DEFAULT_RELATIVE_BOUNDS,
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
    comparison: str = "relative_pct",
    relative_bounds: tuple[float, float] = savegame_maps.DEFAULT_RELATIVE_BOUNDS,
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
        overwrite=overwrite,
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
    quality: int = 98,
    lossless: bool = False,
    comparison_export_dir: str | Path = Path("graphs/savegame_notebooks/exports/comparison"),
    absolute_export_dir: str | Path = Path("graphs/savegame_notebooks/exports/absolute"),
) -> tuple[savegame_maps.AnimationExportResult, ...]:
    """Render the standard global savegame map WebP animations."""

    resolved_repo = _find_repo_root(_portable_path(repo) if repo is not None else None)
    comparison_dir = _resolve_output_path(resolved_repo, comparison_export_dir)
    absolute_dir = _resolve_output_path(resolved_repo, absolute_export_dir)
    data = open_data(
        repo=resolved_repo,
        data_root=data_root if data_root is not None else resolved_repo / "graphs" / "dataset",
        load_order_path=load_order_path if load_order_path is not None else resolved_repo / "constructor.load_order.toml",
        profile=profile,
        load_map_assets=True,
        map_width=map_asset_width,
    )
    common = {
        "scope": "super_region",
        "name": None,
        "width": map_width,
    }
    exports: list[savegame_maps.AnimationExportResult] = []

    population_change = population_map(
        data,
        metric="total_population",
        comparison="relative_pct",
        relative_bounds=(-100, 300),
        **common,
    )
    exports.append(
        save_population_map_animation(
            population_change,
            output_dir=comparison_dir,
            filename="population_change.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
        )
    )

    population_current = population_map(
        data,
        metric="total_population",
        comparison="current",
        absolute_bounds=None,
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
        )
    )

    development_from_gamestart = development_map(
        data,
        mode="from_gamestart",
        delta_bounds=(-10, 10),
        **common,
    )
    exports.append(
        save_development_map_animation(
            development_from_gamestart,
            output_dir=comparison_dir,
            filename="development_from_gamestart.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
        )
    )

    development_current = development_map(
        data,
        mode="current",
        absolute_bounds=None,
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
        )
    )

    building_levels_from_gamestart = building_levels_map(
        data,
        mode="from_gamestart",
        delta_bounds=(-50, 50),
        absolute_bounds=None,
        **common,
    )
    exports.append(
        save_building_levels_map_animation(
            building_levels_from_gamestart,
            output_dir=comparison_dir,
            filename="building_levels_from_gamestart.webp",
            duration_ms=interval_ms,
            quality=quality,
            lossless=lossless,
            width=export_width,
        )
    )

    building_levels_current = building_levels_map(
        data,
        mode="current",
        absolute_bounds=None,
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
        )
    )
    return tuple(exports)


def _resolve_output_path(repo: Path, path: str | Path) -> Path:
    output = Path(path)
    return output if output.is_absolute() else repo / output


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
