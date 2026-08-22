"""One-command, report-first long-run population-capacity simulation profile."""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np
import polars as pl
import rasterio
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig, load_profile

from prosper_or_perish_constructor.farming_village_unlocks import (
    DERIVED_START_LOCATIONS_RELATIVE,
    load_start_location_frame,
)
from prosper_or_perish_constructor.free_building_levels import (
    extract_river_levels_from_maps,
    resolve_map_data_file,
)
from prosper_or_perish_constructor.simulation.capacity_model import (
    BASE_POPULATION_CAPACITY_COLUMN,
    GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN,
    HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN,
    IRRIGATION_LEGAL_CAP_COLUMN,
    IRRIGATION_LEVELS_COLUMN,
    PopulationCapacityFormula,
    PHYSICAL_POPULATION_CAPACITY_COLUMN,
    ZERO_DEVELOPMENT_CAPACITY_COLUMN,
)
from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    LOCAL_MONTHLY_FOOD_KEY,
    OVERPOPULATION,
    CapacityPressureBand,
)
from prosper_or_perish_constructor.simulation.modifiers import (
    SimulationModifierContext,
    load_simulation_modifier_context,
)
from prosper_or_perish_constructor.simulation.run import Simulation
from prosper_or_perish_constructor.simulation.tick import prepare_start_locations

PEASANT_FOOD_CONSUMPTION_KEY = "local_peasants_food_consumption"
HYDE_REGION_COLUMN = "hyde_region"
HYDE_POPULATION_COLUMN = "hyde_population_people"
HYDE_CROPLAND_AREA_COLUMN = "hyde_cropland_area_km2"
HYDE_RAINFED_AREA_COLUMN = "hyde_rainfed_area_km2"
HYDE_IRRIGATED_AREA_COLUMN = "hyde_irrigated_area_km2"
HYDE_PASTURE_AREA_COLUMN = "hyde_pasture_area_km2"
HYDE_URBAN_POPULATION_COLUMN = "hyde_urban_population_people"
START_POPULATION_COLUMN = "profile_start_population"
START_DEVELOPMENT_COLUMN = "profile_start_development"
START_COUNTRY_TAG_COLUMN = "profile_start_country_tag"
START_CONSTRUCTIBLE_OWNER_COLUMN = "profile_start_constructible_owner"
VANILLA_IRRIGATION_LEVELS_COLUMN = "vanilla_irrigation_systems_levels"
GENERATED_IRRIGATION_LEVELS_COLUMN = "generated_irrigation_systems_levels"
PEOPLE_PER_GAME_UNIT_DEFAULT = 1_000.0
SIMULATION_POPULATION_COLUMNS = (
    "population_nobles",
    "population_clergy",
    "population_burghers",
    "population_laborers",
    "population_soldiers",
    "population_peasants",
    "population_slaves",
    "population_tribesmen",
    "population_unknown",
)


@dataclass(frozen=True)
class HydeRegionTarget:
    region_id: int
    key: str
    label: str
    ratios: Mapping[int, float]
    excluded_years: frozenset[int]


@dataclass(frozen=True)
class SimulationProfile:
    path: Path
    start_year: int
    checkpoint_years: tuple[int, ...]
    people_per_game_unit: float
    output_path: Path
    population_snapshot_path: Path
    parser_profile: str
    load_order_path: Path
    candidates_path: Path
    sample_points_path: Path
    hyde_root: Path
    hyde_region_mask_path: Path
    hyde_population_locations_path: Path
    hyde_cropland_path: Path
    hyde_rainfed_path: Path
    hyde_irrigated_path: Path
    hyde_pasture_path: Path
    hyde_urban_population_path: Path
    deployment_population_capacity_table_path: Path
    deployment_development_setup_path: Path
    deployment_irrigation_setup_path: Path
    deployment_manifest_path: Path
    deployment_development_decimals: int
    physical_capacity_columns: tuple[str, ...]
    gaez_zero_development_fraction: float
    gaez_zero_development_density_cap: float
    hyde_rainfed_capacity_multiplier: float
    capacity_formula: PopulationCapacityFormula
    development_base: float
    development_manageable_cropland_column: str
    development_minimum_manageable_cropland_fraction: float
    development_cropland_utilization_points: float
    development_cropland_saturation_rate: float
    development_pasture_full_share_points: float
    development_start_min: float
    development_start_max: float
    irrigation_enabled: bool
    irrigation_thresholds_km2: tuple[float, ...]
    irrigation_base_legal_levels: float
    irrigation_development_levels_per_point: float
    irrigation_lake_legal_levels: float
    irrigation_owner_legal_levels: float
    irrigation_require_river_or_lake: bool
    irrigation_exceptions: frozenset[str]
    abundant_peasant_food_consumption: float
    available_peasant_food_consumption: float
    overpopulation_peasant_food_consumption: float
    abundant_monthly_food: float
    available_monthly_food: float
    rank_degrowth_exempt_pop_types: frozenset[str]
    food_storage_growth_exempt_pop_types: frozenset[str]
    global_ratios: Mapping[int, float]
    global_excluded_years: frozenset[int]
    global_tolerance: float
    regional_tolerance: float
    required_regional_pass_fraction: float
    primary_scored_through_year: int
    regions: tuple[HydeRegionTarget, ...]
    max_report_locations: int
    spot_check_locations: tuple[str, ...]
    min_location_capacity: float
    max_location_capacity: float
    max_location_population: float
    max_location_capacity_fill: float
    min_global_start_capacity_ratio: float
    min_start_population_within_capacity_fraction: float
    start_capacity_scored_regions: frozenset[str]
    min_region_start_population_within_capacity_fraction: float
    established_population_threshold: float
    max_established_start_capacity_fill: float
    min_location_25y_growth_factor: float
    max_location_25y_growth_factor: float
    min_location_100y_growth_factor: float
    max_location_100y_growth_factor: float
    max_development: float
    min_start_development_p90: float
    max_start_development_p90: float
    max_start_development_ceiling_fraction: float
    min_start_natural_capacity_share: float
    max_start_development_capacity_share: float
    max_global_100y_development_change: float
    max_region_100y_development_change: float
    max_global_25y_deviation: float
    max_global_100y_deviation: float
    min_region_25y_ratio: float
    max_region_25y_ratio: float
    min_region_100y_ratio: float
    max_region_100y_ratio: float
    min_irrigation_river_or_lake_fraction: float
    min_irrigation_river_supported_level_fraction: float
    max_irrigation_cap_violations: int


@dataclass(frozen=True)
class ProfileRunResult:
    report_path: Path
    passed: bool
    elapsed_seconds: float
    checkpoints: tuple[int, ...]


def load_population_simulation_profile(path: Path, *, repo: Path) -> SimulationProfile:
    """Load and validate the adjustable TOML profile."""

    resolved = _resolve(repo, path)
    raw = tomllib.loads(resolved.read_text(encoding="utf-8-sig"))
    simulation = _mapping(raw, "simulation")
    paths = _mapping(raw, "paths")
    deployment = _mapping(raw, "deployment")
    capacity = _mapping(raw, "capacity")
    development = _mapping(raw, "development")
    irrigation = _mapping(raw, "irrigation")
    food = _mapping(raw, "food_pressure")
    population_growth = _mapping(raw, "population_growth")
    targets = _mapping(raw, "targets")
    sanity = _mapping(raw, "sanity")

    start_year = _integer(simulation, "start_year")
    checkpoints = tuple(sorted(set(_integer_list(simulation, "checkpoint_years"))))
    if not checkpoints or checkpoints[0] != 0:
        raise ValueError("simulation.checkpoint_years must include 0")
    if any(year < 0 for year in checkpoints):
        raise ValueError("simulation.checkpoint_years must be non-negative")

    hyde_root = _resolve(repo, Path(_string(paths, "hyde_root")))
    region_rows = targets.get("hyde_region") or []
    if not isinstance(region_rows, list) or not region_rows:
        raise ValueError("targets must contain at least one [[targets.hyde_region]]")
    regions: list[HydeRegionTarget] = []
    for index, item in enumerate(region_rows):
        if not isinstance(item, dict):
            raise ValueError(f"targets.hyde_region[{index}] must be a table")
        ratios = _year_mapping(item.get("ratios"), f"targets.hyde_region[{index}].ratios")
        regions.append(
            HydeRegionTarget(
                region_id=int(item["id"]),
                key=str(item["key"]),
                label=str(item.get("label") or item["key"]),
                ratios=ratios,
                excluded_years=frozenset(int(value) for value in item.get("excluded_years") or []),
            )
        )
    ids = [region.region_id for region in regions]
    keys = [region.key for region in regions]
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        raise ValueError("HYDE target region ids and keys must be unique")

    thresholds = tuple(float(value) for value in irrigation.get("level_thresholds_km2") or [])
    if any(not math.isfinite(value) or value < 0.0 for value in thresholds):
        raise ValueError("irrigation.level_thresholds_km2 must be finite and non-negative")
    if tuple(sorted(thresholds)) != thresholds:
        raise ValueError("irrigation.level_thresholds_km2 must be sorted")

    profile = SimulationProfile(
        path=resolved,
        start_year=start_year,
        checkpoint_years=checkpoints,
        people_per_game_unit=_positive_float(simulation, "people_per_game_unit"),
        output_path=_resolve(repo, Path(_string(simulation, "output"))),
        population_snapshot_path=_resolve(
            repo,
            Path(_string(paths, "population_snapshot")),
        ),
        parser_profile=str(simulation.get("parser_profile") or "constructor"),
        load_order_path=_resolve(repo, Path(str(simulation.get("load_order") or "constructor.load_order.toml"))),
        candidates_path=_resolve(repo, Path(_string(paths, "location_candidates"))),
        sample_points_path=_resolve(repo, Path(_string(paths, "location_sample_points"))),
        hyde_root=hyde_root,
        hyde_region_mask_path=_resolve(hyde_root, Path(_string(paths, "hyde_region_mask"))),
        hyde_population_locations_path=_resolve(
            hyde_root,
            Path(_string(paths, "hyde_population_locations")),
        ),
        hyde_cropland_path=_resolve(hyde_root, Path(_string(paths, "hyde_cropland"))),
        hyde_rainfed_path=_resolve(hyde_root, Path(_string(paths, "hyde_rainfed"))),
        hyde_irrigated_path=_resolve(hyde_root, Path(_string(paths, "hyde_irrigated"))),
        hyde_pasture_path=_resolve(hyde_root, Path(_string(paths, "hyde_pasture"))),
        hyde_urban_population_path=_resolve(
            hyde_root,
            Path(_string(paths, "hyde_urban_population")),
        ),
        deployment_population_capacity_table_path=_resolve(
            repo,
            Path(_string(deployment, "population_capacity_table")),
        ),
        deployment_development_setup_path=_resolve(
            repo,
            Path(_string(deployment, "development_setup")),
        ),
        deployment_irrigation_setup_path=_resolve(
            repo,
            Path(_string(deployment, "irrigation_setup")),
        ),
        deployment_manifest_path=_resolve(
            repo,
            Path(_string(deployment, "manifest")),
        ),
        deployment_development_decimals=_nonnegative_integer(
            deployment, "development_decimals"
        ),
        physical_capacity_columns=tuple(
            str(value) for value in capacity.get("physical_capacity_columns") or []
        ),
        gaez_zero_development_fraction=_nonnegative_float(
            capacity, "gaez_zero_development_fraction"
        ),
        gaez_zero_development_density_cap=_positive_float(
            capacity, "gaez_zero_development_density_cap"
        ),
        hyde_rainfed_capacity_multiplier=_nonnegative_float(
            capacity, "hyde_rainfed_capacity_multiplier"
        ),
        capacity_formula=PopulationCapacityFormula(
            physical_scale=1.0,
            development_absolute=_float(capacity, "development_absolute"),
            development_relative=_float(capacity, "development_relative"),
            irrigation_absolute=_float(capacity, "irrigation_absolute"),
            irrigation_relative=_float(capacity, "irrigation_relative"),
            development_min=_float(capacity, "development_min"),
            development_max=_float(capacity, "development_max"),
            minimum_capacity=_nonnegative_float(capacity, "minimum_capacity"),
        ),
        development_base=_float(development, "base"),
        development_manageable_cropland_column=_string(
            development, "manageable_cropland_column"
        ),
        development_minimum_manageable_cropland_fraction=_positive_float(
            development, "minimum_manageable_cropland_fraction"
        ),
        development_cropland_utilization_points=_float(
            development, "cropland_utilization_points"
        ),
        development_cropland_saturation_rate=_positive_float(
            development, "cropland_saturation_rate"
        ),
        development_pasture_full_share_points=_float(
            development, "pasture_full_share_points"
        ),
        development_start_min=_float(development, "start_min"),
        development_start_max=_float(development, "start_max"),
        irrigation_enabled=bool(irrigation.get("enabled", True)),
        irrigation_thresholds_km2=thresholds,
        irrigation_base_legal_levels=_nonnegative_float(irrigation, "base_legal_levels"),
        irrigation_development_levels_per_point=_nonnegative_float(
            irrigation, "development_legal_levels_per_point"
        ),
        irrigation_lake_legal_levels=_nonnegative_float(irrigation, "lake_legal_levels"),
        irrigation_owner_legal_levels=_nonnegative_float(irrigation, "owner_legal_levels"),
        irrigation_require_river_or_lake=bool(irrigation.get("require_river_or_lake", True)),
        irrigation_exceptions=frozenset(str(value) for value in irrigation.get("exceptions") or []),
        abundant_peasant_food_consumption=_float(food, "abundant_peasant_food_consumption"),
        available_peasant_food_consumption=_float(food, "available_peasant_food_consumption"),
        overpopulation_peasant_food_consumption=_float(
            food, "overpopulation_peasant_food_consumption"
        ),
        abundant_monthly_food=_nonnegative_float(food, "abundant_monthly_food"),
        available_monthly_food=_nonnegative_float(food, "available_monthly_food"),
        rank_degrowth_exempt_pop_types=frozenset(
            str(value)
            for value in population_growth.get("rank_degrowth_exempt_pop_types") or []
        ),
        food_storage_growth_exempt_pop_types=frozenset(
            str(value)
            for value in population_growth.get("food_storage_growth_exempt_pop_types") or []
        ),
        global_ratios=_year_mapping(targets.get("global_ratios"), "targets.global_ratios"),
        global_excluded_years=frozenset(
            int(value) for value in targets.get("global_excluded_years") or []
        ),
        global_tolerance=_fraction(targets, "global_tolerance"),
        regional_tolerance=_fraction(targets, "regional_tolerance"),
        required_regional_pass_fraction=_fraction(targets, "required_regional_pass_fraction"),
        primary_scored_through_year=_positive_integer(
            targets, "primary_scored_through_year"
        ),
        regions=tuple(regions),
        max_report_locations=_positive_integer(sanity, "max_report_locations"),
        spot_check_locations=tuple(
            str(value) for value in sanity.get("spot_check_locations") or []
        ),
        min_location_capacity=_nonnegative_float(sanity, "min_location_capacity"),
        max_location_capacity=_positive_float(sanity, "max_location_capacity"),
        max_location_population=_positive_float(sanity, "max_location_population"),
        max_location_capacity_fill=_positive_float(sanity, "max_location_capacity_fill"),
        min_global_start_capacity_ratio=_positive_float(
            sanity, "min_global_start_capacity_ratio"
        ),
        min_start_population_within_capacity_fraction=_fraction(
            sanity, "min_start_population_within_capacity_fraction"
        ),
        start_capacity_scored_regions=frozenset(
            str(value) for value in sanity.get("start_capacity_scored_regions") or []
        ),
        min_region_start_population_within_capacity_fraction=_fraction(
            sanity, "min_region_start_population_within_capacity_fraction"
        ),
        established_population_threshold=_positive_float(
            sanity, "established_population_threshold"
        ),
        max_established_start_capacity_fill=_positive_float(
            sanity, "max_established_start_capacity_fill"
        ),
        min_location_25y_growth_factor=_positive_float(
            sanity, "min_location_25y_growth_factor"
        ),
        max_location_25y_growth_factor=_positive_float(
            sanity, "max_location_25y_growth_factor"
        ),
        min_location_100y_growth_factor=_positive_float(
            sanity, "min_location_100y_growth_factor"
        ),
        max_location_100y_growth_factor=_positive_float(
            sanity, "max_location_100y_growth_factor"
        ),
        max_development=_positive_float(sanity, "max_development"),
        min_start_development_p90=_nonnegative_float(
            sanity, "min_start_development_p90"
        ),
        max_start_development_p90=_positive_float(
            sanity, "max_start_development_p90"
        ),
        max_start_development_ceiling_fraction=_fraction(
            sanity, "max_start_development_ceiling_fraction"
        ),
        min_start_natural_capacity_share=_fraction(
            sanity, "min_start_natural_capacity_share"
        ),
        max_start_development_capacity_share=_fraction(
            sanity, "max_start_development_capacity_share"
        ),
        max_global_100y_development_change=_nonnegative_float(
            sanity, "max_global_100y_development_change"
        ),
        max_region_100y_development_change=_nonnegative_float(
            sanity, "max_region_100y_development_change"
        ),
        max_global_25y_deviation=_fraction(sanity, "max_global_25y_deviation"),
        max_global_100y_deviation=_fraction(sanity, "max_global_100y_deviation"),
        min_region_25y_ratio=_positive_float(sanity, "min_region_25y_ratio"),
        max_region_25y_ratio=_positive_float(sanity, "max_region_25y_ratio"),
        min_region_100y_ratio=_positive_float(sanity, "min_region_100y_ratio"),
        max_region_100y_ratio=_positive_float(sanity, "max_region_100y_ratio"),
        min_irrigation_river_or_lake_fraction=_fraction(
            sanity, "min_irrigation_river_or_lake_fraction"
        ),
        min_irrigation_river_supported_level_fraction=_fraction(
            sanity, "min_irrigation_river_supported_level_fraction"
        ),
        max_irrigation_cap_violations=_nonnegative_integer(
            sanity, "max_irrigation_cap_violations"
        ),
    )
    if profile.development_start_max < profile.development_start_min:
        raise ValueError("development.start_max must be at least development.start_min")
    if profile.deployment_development_decimals > 6:
        raise ValueError("deployment.development_decimals must be at most 6")
    if not profile.physical_capacity_columns:
        raise ValueError("capacity.physical_capacity_columns must not be empty")
    unknown_scored_regions = sorted(set(profile.start_capacity_scored_regions) - set(keys))
    if unknown_scored_regions:
        raise ValueError(
            "sanity.start_capacity_scored_regions references unknown HYDE regions: "
            f"{unknown_scored_regions}"
        )
    if profile.max_region_25y_ratio < profile.min_region_25y_ratio:
        raise ValueError("sanity max_region_25y_ratio must be at least the minimum")
    if profile.max_region_100y_ratio < profile.min_region_100y_ratio:
        raise ValueError("sanity max_region_100y_ratio must be at least the minimum")
    if profile.max_start_development_p90 < profile.min_start_development_p90:
        raise ValueError(
            "sanity max_start_development_p90 must be at least the minimum"
        )
    missing_global = sorted(set(profile.global_ratios) - set(profile.checkpoint_years))
    if missing_global:
        raise ValueError(f"global targets reference unconfigured checkpoints: {missing_global}")
    return profile


def run_population_simulation_profile(
    *,
    repo: Path,
    project: Path,
    profile_path: Path,
) -> ProfileRunResult:
    """Run configured checkpoints and write exactly one consolidated Markdown report."""

    started = perf_counter()
    profile = load_population_simulation_profile(profile_path, repo=repo)
    state, context, preparation = _prepare_state(repo, project, profile)
    simulation = Simulation(state, context)

    snapshots: dict[int, pl.DataFrame] = {}
    previous_year = 0
    for year in profile.checkpoint_years:
        if year > previous_year:
            simulation.run(months=(year - previous_year) * 12, progress=False)
        snapshots[year] = _snapshot(simulation.state)
        previous_year = year

    report, passed = build_population_simulation_report(
        profile=profile,
        snapshots=snapshots,
        preparation=preparation,
        elapsed_seconds=perf_counter() - started,
    )
    profile.output_path.parent.mkdir(parents=True, exist_ok=True)
    profile.output_path.write_text(report, encoding="utf-8")
    return ProfileRunResult(
        report_path=profile.output_path,
        passed=passed,
        elapsed_seconds=perf_counter() - started,
        checkpoints=profile.checkpoint_years,
    )


def _prepare_state(
    repo: Path,
    project: Path,
    profile: SimulationProfile,
) -> tuple[pl.DataFrame, SimulationModifierContext, dict[str, Any]]:
    state = load_start_location_frame(repo, project)
    state, population_snapshot_summary = _attach_population_snapshot(state, profile)
    candidates = pl.read_parquet(profile.candidates_path)
    candidate_columns = [
        "location_tag",
        "calibrated_lon",
        "calibrated_lat",
        "centroid_x",
        "centroid_y",
        "area_km2",
        profile.development_manageable_cropland_column,
        *profile.physical_capacity_columns,
    ]
    missing_candidate_columns = sorted(set(candidate_columns) - set(candidates.columns))
    if missing_candidate_columns:
        raise ValueError(
            "population-capacity candidates are missing configured columns: "
            f"{missing_candidate_columns}"
        )
    state = state.join(candidates.select(candidate_columns), on="location_tag", how="left")
    state = state.with_columns(
        pl.col("total_population").fill_null(0.0).cast(pl.Float64).alias(START_POPULATION_COLUMN),
        pl.col("development").fill_null(0.0).cast(pl.Float64).alias(START_DEVELOPMENT_COLUMN),
    )
    state = _attach_hyde_regions(state, profile)
    state = _attach_hyde_inputs(state, profile)
    development = np.round(
        _hyde_starting_development(state, profile),
        decimals=profile.deployment_development_decimals,
    )
    state = state.with_columns(
        pl.Series("development", development),
    )
    state = _attach_start_owners(state, repo)

    physical_people = pl.sum_horizontal(
        [
            pl.col(column).fill_null(0.0).cast(pl.Float64)
            for column in profile.physical_capacity_columns
        ]
    )
    state = state.with_columns(
        (
            physical_people.clip(lower_bound=0.0)
            / profile.people_per_game_unit
        ).alias(PHYSICAL_POPULATION_CAPACITY_COLUMN),
    )

    if profile.irrigation_enabled:
        state, irrigation_summary = _attach_irrigation_levels(state, repo, profile)
    else:
        state = state.with_columns(
            pl.lit(0.0).alias(IRRIGATION_LEVELS_COLUMN),
            pl.lit(0.0).alias(IRRIGATION_LEGAL_CAP_COLUMN),
            pl.lit(0.0).alias(HYDE_IRRIGATED_AREA_COLUMN),
            pl.lit(0).alias("river_level"),
        )
        irrigation_summary = {"enabled": False}

    state = _attach_zero_development_capacity(state, profile)
    state = _attach_deployed_base_capacity(state, profile)

    context = load_simulation_modifier_context(
        profile=profile.parser_profile,
        load_order_path=profile.load_order_path,
    )
    context = replace(
        context,
        capacity_pressure=_capacity_pressure_overrides(context, profile),
        capacity_model=profile.capacity_formula,
        rank_degrowth_exempt_pop_types=profile.rank_degrowth_exempt_pop_types,
        food_storage_growth_exempt_pop_types=(
            profile.food_storage_growth_exempt_pop_types
        ),
    )
    state = prepare_start_locations(state, context)
    preparation = {
        "locations": state.height,
        "population_snapshot": population_snapshot_summary,
        "irrigation": irrigation_summary,
        "starting_development_raw": _numeric_summary(state[START_DEVELOPMENT_COLUMN]),
        "starting_development_profile": _numeric_summary(state["development"]),
        "development_monthly_per_point": (
            context.prosperity.development_monthly_per_point
        ),
        "gaez_zero_development_capacity": _numeric_summary(
            state[GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN]
        ),
        "hyde_rainfed_capacity_evidence": _numeric_summary(
            state[HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN]
        ),
        "zero_development_capacity": _numeric_summary(
            state[ZERO_DEVELOPMENT_CAPACITY_COLUMN]
        ),
        "capacity_sources": {
            "gaez_sum": float(state[GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN].sum()),
            "hyde_sum": float(state[HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN].sum()),
            "zero_development_sum": float(state[ZERO_DEVELOPMENT_CAPACITY_COLUMN].sum()),
            "gaez_dominant_locations": state.filter(
                pl.col(GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN)
                >= pl.col(HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN)
            ).height,
            "hyde_dominant_locations": state.filter(
                pl.col(HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN)
                > pl.col(GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN)
            ).height,
        },
        "capacity_attribution": _capacity_attribution(
            state,
            profile.capacity_formula,
        ),
    }
    return state, context, preparation


def _attach_population_snapshot(
    state: pl.DataFrame,
    profile: SimulationProfile,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Replace only simulator demographics with one generated save snapshot."""

    _require_file(profile.population_snapshot_path, "simulation population snapshot")
    snapshot = pl.read_parquet(profile.population_snapshot_path)
    if "location_tag" not in snapshot.columns and "slug" in snapshot.columns:
        snapshot = snapshot.rename({"slug": "location_tag"})
    required = {
        "location_tag",
        "total_population",
        "unemployed_peasants",
        *SIMULATION_POPULATION_COLUMNS,
    }
    missing = sorted(required - set(snapshot.columns))
    if missing:
        raise ValueError(f"simulation population snapshot is missing columns: {missing}")
    if snapshot["location_tag"].n_unique() != snapshot.height:
        raise ValueError("simulation population snapshot location tags are not unique")

    selected = snapshot.select(
        pl.col("location_tag").cast(pl.String),
        pl.col("total_population").cast(pl.Float64),
        *[pl.col(column).cast(pl.Float64) for column in SIMULATION_POPULATION_COLUMNS],
        pl.col("unemployed_peasants").cast(pl.Float64),
    )
    missing_locations = state.select("location_tag").join(
        selected.select("location_tag"),
        on="location_tag",
        how="anti",
    )
    if not missing_locations.is_empty():
        examples = missing_locations["location_tag"].head(8).to_list()
        raise ValueError(
            "simulation population snapshot does not cover all simulator locations; "
            f"missing={missing_locations.height}, examples={examples}"
        )

    population_sum = pl.sum_horizontal(
        pl.col(column) for column in SIMULATION_POPULATION_COLUMNS
    )
    max_error = selected.select(
        (population_sum - pl.col("total_population")).abs().max()
    ).item()
    if max_error is not None and float(max_error) > 1e-6:
        raise ValueError(
            "simulation population snapshot pop types do not reconcile to total_population; "
            f"maximum error={float(max_error):.9f}"
        )
    invalid_unemployed = selected.filter(
        (pl.col("unemployed_peasants") < 0.0)
        | (pl.col("unemployed_peasants") > pl.col("population_peasants") + 1e-6)
    )
    if not invalid_unemployed.is_empty():
        raise ValueError(
            "simulation population snapshot has unemployed peasants outside the peasant total; "
            f"locations={invalid_unemployed.height}"
        )

    replaced = [
        column
        for column in state.columns
        if column.startswith("population_")
        or column
        in {
            "total_population",
            "peasant_employment",
            "employed_peasants",
            "unemployed_peasants",
            "food",
        }
    ]
    joined = state.drop(replaced).join(selected, on="location_tag", how="left")
    metadata = snapshot.select(
        *[
            pl.col(column)
            for column in ("snapshot_date", "source_save")
            if column in snapshot.columns
        ]
    )
    metadata_row = metadata.row(0, named=True) if metadata.width and metadata.height else {}
    summary = {
        "path": str(profile.population_snapshot_path),
        "snapshot_rows": snapshot.height,
        "matched_locations": joined.height,
        "total_population": float(selected["total_population"].sum()),
        "snapshot_date": str(metadata_row.get("snapshot_date") or ""),
        "source_save": str(metadata_row.get("source_save") or ""),
    }
    return joined, summary


def _attach_zero_development_capacity(
    state: pl.DataFrame,
    profile: SimulationProfile,
) -> pl.DataFrame:
    """Derive the natural, zero-development baseline from GAEZ and HYDE.

    GAEZ supplies potential even where nobody lives. HYDE supplies independent
    historical evidence where the physical crop model is too conservative, but
    only the rainfed share may support the natural baseline. The capacity effect
    of the observed starting development is backed out so HYDE does not get
    counted once in the static potential and again through the development
    modifier. Irrigation is deliberately absent from this calculation.
    """

    formula = profile.capacity_formula
    physical = np.maximum(
        state[PHYSICAL_POPULATION_CAPACITY_COLUMN].to_numpy(),
        0.0,
    )
    development = np.clip(
        state["development"].to_numpy(),
        formula.development_min,
        formula.development_max,
    )
    cropland = np.maximum(state[HYDE_CROPLAND_AREA_COLUMN].to_numpy(), 0.0)
    rainfed = np.maximum(state[HYDE_RAINFED_AREA_COLUMN].to_numpy(), 0.0)
    rainfed_share = np.divide(
        rainfed,
        cropland,
        out=np.ones_like(rainfed),
        where=cropland > 1e-12,
    )
    rainfed_share = np.clip(rainfed_share, 0.0, 1.0)
    # HYDE sometimes contains a tiny irrigated trace in a location where the
    # river/legal/evidence gates do not produce an irrigation building. Such a
    # trace cannot carry the location in game, so only partition HYDE population
    # away from the natural baseline when irrigation is actually deployed.
    has_deployed_irrigation = state[IRRIGATION_LEVELS_COLUMN].to_numpy() > 0.0
    rainfed_share = np.where(has_deployed_irrigation, rainfed_share, 1.0)
    hyde_rainfed_population = (
        np.maximum(state[HYDE_POPULATION_COLUMN].to_numpy(), 0.0)
        / profile.people_per_game_unit
        * rainfed_share
    )
    hyde_managed_target = (
        hyde_rainfed_population * profile.hyde_rainfed_capacity_multiplier
    )
    development_relative = np.maximum(
        1.0 + development * formula.development_relative,
        1e-12,
    )
    hyde_static_evidence = np.maximum(
        hyde_managed_target / development_relative
        - development * formula.development_absolute,
        0.0,
    )
    gaez_fractional = physical * profile.gaez_zero_development_fraction
    gaez_density_cap = (
        np.maximum(state["area_km2"].to_numpy(), 0.0)
        * profile.gaez_zero_development_density_cap
        / profile.people_per_game_unit
    )
    gaez_static = np.minimum(gaez_fractional, gaez_density_cap)
    zero_development = np.maximum(gaez_static, hyde_static_evidence)
    return state.with_columns(
        pl.Series(GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN, gaez_static),
        pl.Series(HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN, hyde_static_evidence),
        pl.Series(ZERO_DEVELOPMENT_CAPACITY_COLUMN, zero_development),
    )


def _attach_deployed_base_capacity(
    state: pl.DataFrame,
    profile: SimulationProfile,
) -> pl.DataFrame:
    """Quantize the independent static base exactly as the game compiler does."""

    formula = profile.capacity_formula
    natural = state[ZERO_DEVELOPMENT_CAPACITY_COLUMN].to_numpy()
    development = state["development"].to_numpy()
    irrigation = state[IRRIGATION_LEVELS_COLUMN].to_numpy()
    desired = formula.evaluate(
        base_capacity=natural,
        development=development,
        irrigation_levels=irrigation,
    )
    relative = np.maximum(
        1.0
        + development * formula.development_relative
        + irrigation * formula.irrigation_relative,
        1e-12,
    )
    required_static_base = np.maximum(
        desired / relative
        - development * formula.development_absolute
        - irrigation * formula.irrigation_absolute,
        0.0,
    )
    # The compiler contract is integral EU5 population units. Ceil rather than
    # nearest-round so quantization can never push a location below the modeled
    # physical/minimum base.
    deployed_static_base = np.ceil(required_static_base - 1e-12)
    return state.with_columns(
        pl.Series(
            BASE_POPULATION_CAPACITY_COLUMN,
            deployed_static_base,
        ),
        pl.Series("deployed_static_population_capacity", deployed_static_base),
    )


def _capacity_attribution(
    state: pl.DataFrame,
    formula: PopulationCapacityFormula,
) -> dict[str, float]:
    """Split starting capacity into natural, development, and irrigation increments."""

    base = state[BASE_POPULATION_CAPACITY_COLUMN].to_numpy()
    development = state["development"].to_numpy()
    irrigation = state[IRRIGATION_LEVELS_COLUMN].to_numpy()
    zero = np.zeros_like(development)
    natural = formula.evaluate(
        base_capacity=base,
        development=zero,
        irrigation_levels=zero,
    )
    with_development = formula.evaluate(
        base_capacity=base,
        development=development,
        irrigation_levels=zero,
    )
    full = formula.evaluate(
        base_capacity=base,
        development=development,
        irrigation_levels=irrigation,
    )
    without_development_absolute = replace(
        formula,
        development_absolute=0.0,
    ).evaluate(
        base_capacity=base,
        development=development,
        irrigation_levels=irrigation,
    )
    total = max(float(np.sum(full)), 1e-12)
    natural_total = float(np.sum(natural))
    development_total = float(np.sum(with_development - natural))
    irrigation_total = float(np.sum(full - with_development))
    development_absolute_total = float(np.sum(full - without_development_absolute))
    return {
        "total": total,
        "natural_total": natural_total,
        "natural_share": natural_total / total,
        "development_total": development_total,
        "development_share": development_total / total,
        "development_absolute_total": development_absolute_total,
        "development_absolute_share": development_absolute_total / total,
        "irrigation_total": irrigation_total,
        "irrigation_share": irrigation_total / total,
    }


def prepare_population_simulation_state(
    repo: Path,
    project: Path,
    profile: SimulationProfile,
) -> tuple[pl.DataFrame, SimulationModifierContext, dict[str, Any]]:
    """Build the canonical profile state used by simulation and deployment."""

    return _prepare_state(repo, project, profile)


def _attach_start_owners(state: pl.DataFrame, repo: Path) -> pl.DataFrame:
    """Attach parser-derived 1337 owners needed for generated starting buildings."""

    artifact = repo / DERIVED_START_LOCATIONS_RELATIVE
    if artifact.is_file():
        owners = pl.read_parquet(artifact)
    else:
        from prosper_or_perish_constructor import food_building_startup
        from prosper_or_perish_constructor.food_building_startup import (
            load_food_startup_config,
        )

        owners = food_building_startup._load_start_locations(
            load_food_startup_config(repo)
        )
    tag_column = "slug" if "slug" in owners.columns else "location_tag"
    required = {tag_column, "country_tag", "startup_constructible_owner"}
    missing = sorted(required - set(owners.columns))
    if missing:
        raise ValueError(f"starting-owner data is missing columns: {missing}")
    owner_frame = owners.select(
        pl.col(tag_column).cast(pl.String).alias("location_tag"),
        pl.col("country_tag").cast(pl.String).alias(START_COUNTRY_TAG_COLUMN),
        pl.col("startup_constructible_owner")
        .fill_null(False)
        .cast(pl.Boolean)
        .alias(START_CONSTRUCTIBLE_OWNER_COLUMN),
    ).unique("location_tag")
    return state.join(owner_frame, on="location_tag", how="left").with_columns(
        pl.col(START_COUNTRY_TAG_COLUMN).fill_null(""),
        pl.col(START_CONSTRUCTIBLE_OWNER_COLUMN).fill_null(False),
    )


def _capacity_pressure_overrides(
    context: SimulationModifierContext,
    profile: SimulationProfile,
) -> dict[str, CapacityPressureBand]:
    settings = {
        ABUNDANT_FREE_LAND: (
            profile.abundant_peasant_food_consumption,
            profile.abundant_monthly_food,
        ),
        AVAILABLE_FREE_LAND: (
            profile.available_peasant_food_consumption,
            profile.available_monthly_food,
        ),
        OVERPOPULATION: (profile.overpopulation_peasant_food_consumption, 0.0),
    }
    out: dict[str, CapacityPressureBand] = {}
    for name, band in context.capacity_pressure.items():
        effects = dict(band.effects)
        consumption, monthly_food = settings[name]
        effects[PEASANT_FOOD_CONSUMPTION_KEY] = consumption
        effects[LOCAL_MONTHLY_FOOD_KEY] = monthly_food
        out[name] = CapacityPressureBand(name=name, effects=effects)
    return out


def _attach_hyde_regions(state: pl.DataFrame, profile: SimulationProfile) -> pl.DataFrame:
    _require_file(profile.hyde_region_mask_path, "HYDE region mask")
    coords = state.select("calibrated_lon", "calibrated_lat").to_dicts()
    points = [
        (float(row["calibrated_lon"] or 0.0), float(row["calibrated_lat"] or 0.0))
        for row in coords
    ]
    with rasterio.open(profile.hyde_region_mask_path) as src:
        ids = [int(sample[0]) for sample in src.sample(points)]
    labels = {region.region_id: region.key for region in profile.regions}
    return state.with_columns(
        pl.Series(
            HYDE_REGION_COLUMN,
            [labels.get(region_id, "unassigned") for region_id in ids],
            dtype=pl.String,
        )
    )


def _attach_hyde_inputs(
    state: pl.DataFrame,
    profile: SimulationProfile,
) -> pl.DataFrame:
    """Attach independently sampled 1337 HYDE population and land-use totals."""

    samples = pl.read_parquet(profile.sample_points_path).select(
        "location_tag",
        "calibrated_lon",
        "calibrated_lat",
        "sample_weight",
    )
    lon = samples["calibrated_lon"].to_numpy()
    lat = samples["calibrated_lat"].to_numpy()
    inputs = state.select("location_tag", "area_km2")
    _require_file(
        profile.hyde_population_locations_path,
        "HYDE population-by-location raster",
    )
    with rasterio.open(profile.hyde_population_locations_path) as src:
        map_x = state["centroid_x"].to_numpy()
        map_y = float(src.height) - state["centroid_y"].to_numpy()
        population = np.asarray(
            [float(value[0]) for value in src.sample(zip(map_x, map_y))],
            dtype=np.float64,
        )
    population[~np.isfinite(population)] = 0.0
    inputs = inputs.with_columns(pl.Series(HYDE_POPULATION_COLUMN, population))
    rasters = (
        (profile.hyde_cropland_path, HYDE_CROPLAND_AREA_COLUMN),
        (profile.hyde_rainfed_path, HYDE_RAINFED_AREA_COLUMN),
        (profile.hyde_irrigated_path, HYDE_IRRIGATED_AREA_COLUMN),
        (profile.hyde_pasture_path, HYDE_PASTURE_AREA_COLUMN),
        (profile.hyde_urban_population_path, HYDE_URBAN_POPULATION_COLUMN),
    )
    for path, column in rasters:
        _require_file(path, f"HYDE input {column}")
        density = _sample_raster_density(path, lon=lon, lat=lat)
        weighted = samples.with_columns(
            pl.Series("sample_density", density),
        ).with_columns(
            (pl.col("sample_density") * pl.col("sample_weight")).alias(
                "weighted_density"
            )
        )
        mean_density = weighted.group_by("location_tag").agg(
            (
                pl.col("weighted_density").sum()
                / pl.col("sample_weight").sum().clip(lower_bound=1e-12)
            ).alias("mean_density")
        )
        totals = inputs.select("location_tag", "area_km2").join(
            mean_density,
            on="location_tag",
            how="left",
        ).select(
            "location_tag",
            (
                pl.col("mean_density").fill_null(0.0)
                * pl.col("area_km2").fill_null(0.0)
            ).alias(column),
        )
        inputs = inputs.join(totals, on="location_tag", how="left")
    return state.join(
        inputs.drop("area_km2"),
        on="location_tag",
        how="left",
    )


def _sample_raster_density(
    path: Path,
    *,
    lon: np.ndarray,
    lat: np.ndarray,
) -> np.ndarray:
    """Sample a per-cell HYDE total and convert it to density per km²."""

    with rasterio.open(path) as src:
        band = src.read(1).astype(np.float64, copy=False)
        rows, cols = rasterio.transform.rowcol(src.transform, lon, lat)
        rows = np.asarray(rows, dtype=np.int64)
        cols = np.asarray(cols, dtype=np.int64)
        valid = (
            (rows >= 0)
            & (rows < src.height)
            & (cols >= 0)
            & (cols < src.width)
        )
        values = np.zeros(lon.shape[0], dtype=np.float64)
        values[valid] = band[rows[valid], cols[valid]]
        values[~np.isfinite(values)] = 0.0
        cell_lat = src.transform.f + (rows.astype(np.float64) + 0.5) * src.transform.e
        cell_area = _spherical_cell_area_km2(
            cell_lat,
            abs(float(src.transform.a)),
            abs(float(src.transform.e)),
        )
    return np.divide(
        values,
        cell_area,
        out=np.zeros_like(values),
        where=cell_area > 0.0,
    )


def _hyde_starting_development(
    state: pl.DataFrame,
    profile: SimulationProfile,
) -> np.ndarray:
    """Derive starting development from external HYDE land use and density."""

    area = np.maximum(state["area_km2"].to_numpy(), 1e-12)
    cropland_share = np.clip(
        state[HYDE_CROPLAND_AREA_COLUMN].to_numpy() / area,
        0.0,
        1.0,
    )
    pasture_share = np.clip(
        state[HYDE_PASTURE_AREA_COLUMN].to_numpy() / area,
        0.0,
        1.0,
    )
    manageable_cropland = np.maximum(
        state[profile.development_manageable_cropland_column].to_numpy(),
        profile.development_minimum_manageable_cropland_fraction,
    )
    cropland_evidence_ratio = np.maximum(
        cropland_share / manageable_cropland,
        0.0,
    )
    cropland_management = -np.expm1(
        -profile.development_cropland_saturation_rate
        * cropland_evidence_ratio
    )
    development = (
        profile.development_base
        + cropland_management * profile.development_cropland_utilization_points
        + pasture_share * profile.development_pasture_full_share_points
    )
    return np.clip(
        development,
        profile.development_start_min,
        profile.development_start_max,
    )


def _attach_irrigation_levels(
    state: pl.DataFrame,
    repo: Path,
    profile: SimulationProfile,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    _require_file(profile.hyde_irrigated_path, "HYDE irrigated-area raster")
    _require_file(profile.sample_points_path, "location sample points")

    data_profile = load_profile(profile.parser_profile, profile.load_order_path)
    river_levels = extract_river_levels_from_maps(
        state,
        locations_png_path=resolve_map_data_file(data_profile, "locations.png"),
        rivers_png_path=resolve_map_data_file(data_profile, "rivers.png"),
    )
    state = state.join(river_levels, on="location_tag", how="left").with_columns(
        pl.col("river_level").fill_null(0).cast(pl.Int64),
        pl.col(HYDE_IRRIGATED_AREA_COLUMN).fill_null(0.0),
    )
    vanilla = _vanilla_irrigation_levels(profile)
    state = state.join(vanilla, on="location_tag", how="left").with_columns(
        pl.col(VANILLA_IRRIGATION_LEVELS_COLUMN).fill_null(0).cast(pl.Int64),
    )

    hyde_proposed = pl.sum_horizontal(
        [
            (pl.col(HYDE_IRRIGATED_AREA_COLUMN) >= threshold).cast(pl.Int64)
            for threshold in profile.irrigation_thresholds_km2
        ]
    )
    legal = (
        pl.lit(profile.irrigation_base_legal_levels)
        + pl.col("development").clip(lower_bound=0.0)
        * profile.irrigation_development_levels_per_point
        + pl.col("river_level").cast(pl.Float64)
        + pl.col("is_adjacent_to_lake").fill_null(False).cast(pl.Float64)
        * profile.irrigation_lake_legal_levels
        + profile.irrigation_owner_legal_levels
    ).floor()
    exception = pl.col("location_tag").is_in(sorted(profile.irrigation_exceptions))
    supported = (
        pl.col("has_river").fill_null(False)
        | pl.col("is_adjacent_to_lake").fill_null(False)
        | exception
    )
    if profile.irrigation_require_river_or_lake:
        hyde_proposed = pl.when(supported).then(hyde_proposed).otherwise(0)
    hyde_proposed = (
        pl.when(pl.col(START_CONSTRUCTIBLE_OWNER_COLUMN).fill_null(False))
        .then(hyde_proposed)
        .otherwise(0)
    )
    proposed = pl.max_horizontal(
        hyde_proposed,
        pl.col(VANILLA_IRRIGATION_LEVELS_COLUMN),
    )
    state = state.with_columns(
        pl.max_horizontal(
            legal.clip(lower_bound=0.0),
            pl.col(VANILLA_IRRIGATION_LEVELS_COLUMN).cast(pl.Float64),
        ).alias(IRRIGATION_LEGAL_CAP_COLUMN),
        proposed.alias("profile_irrigation_proposed_levels"),
    ).with_columns(
        pl.min_horizontal(
            pl.col("profile_irrigation_proposed_levels").cast(pl.Float64),
            pl.col(IRRIGATION_LEGAL_CAP_COLUMN).cast(pl.Float64),
        ).alias(IRRIGATION_LEVELS_COLUMN)
    ).with_columns(
        (
            pl.col(IRRIGATION_LEVELS_COLUMN)
            - pl.col(VANILLA_IRRIGATION_LEVELS_COLUMN).cast(pl.Float64)
        )
        .clip(lower_bound=0.0)
        .alias(GENERATED_IRRIGATION_LEVELS_COLUMN)
    )

    irrigated = state.filter(pl.col(IRRIGATION_LEVELS_COLUMN) > 0)
    levels = float(irrigated[IRRIGATION_LEVELS_COLUMN].sum() or 0.0)
    river_or_lake = irrigated.filter(
        pl.col("has_river").fill_null(False) | pl.col("is_adjacent_to_lake").fill_null(False)
    )
    river_levels_supported = float(
        irrigated.select(
            pl.min_horizontal(
                pl.col(IRRIGATION_LEVELS_COLUMN),
                pl.col("river_level").cast(pl.Float64),
            ).sum()
        ).item()
        or 0.0
    )
    summary = {
        "enabled": True,
        "locations": irrigated.height,
        "levels": levels,
        "vanilla_levels": float(state[VANILLA_IRRIGATION_LEVELS_COLUMN].sum() or 0.0),
        "generated_levels": float(state[GENERATED_IRRIGATION_LEVELS_COLUMN].sum() or 0.0),
        "river_or_lake_location_fraction": river_or_lake.height / irrigated.height
        if irrigated.height
        else 1.0,
        "river_supported_level_fraction": river_levels_supported / levels if levels else 1.0,
        "cap_violations": state.filter(
            pl.col(IRRIGATION_LEVELS_COLUMN) > pl.col(IRRIGATION_LEGAL_CAP_COLUMN)
        ).height,
        "nonriver_locations": irrigated.height - river_or_lake.height,
        "proposed_locations": state.filter(pl.col("profile_irrigation_proposed_levels") > 0).height,
        "evidence_locations": state.filter(pl.col(HYDE_IRRIGATED_AREA_COLUMN) > 0).height,
    }
    return state, summary


def _vanilla_irrigation_levels(profile: SimulationProfile) -> pl.DataFrame:
    """Read historical irrigation already present in vanilla's 1337 setup."""

    vanilla_root = LoadOrderConfig.load(profile.load_order_path).vanilla_root
    path = vanilla_root / "game/main_menu/setup/start/07_cities_and_buildings.txt"
    _require_file(path, "vanilla starting-building setup")
    rows: dict[str, int] = {}
    document = parse_file(path)
    for manager in document.values("building_manager"):
        if not isinstance(manager, CList):
            continue
        for entry in manager.entries:
            if str(entry.key) != "irrigation_systems" or not isinstance(entry.value, CList):
                continue
            location = str(entry.value.first("location") or "").strip()
            if not location:
                continue
            rows[location] = rows.get(location, 0) + int(entry.value.first("level") or 0)
    return pl.DataFrame(
        {
            "location_tag": list(rows),
            VANILLA_IRRIGATION_LEVELS_COLUMN: list(rows.values()),
        },
        schema={"location_tag": pl.String, VANILLA_IRRIGATION_LEVELS_COLUMN: pl.Int64},
    )


def _spherical_cell_area_km2(
    latitude_degrees: np.ndarray,
    width_degrees: float,
    height_degrees: float,
) -> np.ndarray:
    radius_km = 6_371.0088
    latitude = np.asarray(latitude_degrees, dtype=np.float64)
    lower = np.deg2rad(latitude - height_degrees / 2.0)
    upper = np.deg2rad(latitude + height_degrees / 2.0)
    return (
        radius_km**2
        * math.radians(width_degrees)
        * np.abs(np.sin(upper) - np.sin(lower))
    )


def _snapshot(state: pl.DataFrame) -> pl.DataFrame:
    columns = [
        "location_tag",
        "province",
        "macro_region",
        HYDE_REGION_COLUMN,
        "location_rank",
        "total_population",
        "local_population_capacity",
        "development",
        "prosperity",
        START_POPULATION_COLUMN,
        START_DEVELOPMENT_COLUMN,
        BASE_POPULATION_CAPACITY_COLUMN,
        PHYSICAL_POPULATION_CAPACITY_COLUMN,
        GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN,
        HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN,
        ZERO_DEVELOPMENT_CAPACITY_COLUMN,
        "deployed_static_population_capacity",
        "area_km2",
        HYDE_POPULATION_COLUMN,
        HYDE_CROPLAND_AREA_COLUMN,
        HYDE_RAINFED_AREA_COLUMN,
        HYDE_IRRIGATED_AREA_COLUMN,
        HYDE_PASTURE_AREA_COLUMN,
        HYDE_URBAN_POPULATION_COLUMN,
        IRRIGATION_LEVELS_COLUMN,
        IRRIGATION_LEGAL_CAP_COLUMN,
        "river_level",
        "has_river",
        "is_adjacent_to_lake",
        "population_peasants",
        "population_tribesmen",
    ]
    # NumPy-backed Polars columns may share memory with the running engine. Convert
    # each selected column to a list so later in-place ticks cannot mutate an older
    # checkpoint through a zero-copy view.
    selected = [column for column in columns if column in state.columns]
    return pl.DataFrame({column: state[column].to_list() for column in selected})


def build_population_simulation_report(
    *,
    profile: SimulationProfile,
    snapshots: Mapping[int, pl.DataFrame],
    preparation: Mapping[str, Any],
    elapsed_seconds: float,
) -> tuple[str, bool]:
    """Build the single human-readable report and return its overall status."""

    initial = snapshots[0]
    initial_population = float(initial["total_population"].sum())
    global_rows = _global_rows(profile, snapshots, initial_population)
    region_rows = _region_rows(profile, snapshots)
    sanity_rows = _sanity_rows(profile, snapshots, preparation)

    global_scored = [row for row in global_rows if row["scored"]]
    global_pass = all(bool(row["pass"]) for row in global_scored)
    regional_scored = [row for row in region_rows if row["scored"]]
    regional_pass_fraction = (
        sum(bool(row["pass"]) for row in regional_scored) / len(regional_scored)
        if regional_scored
        else 0.0
    )
    regional_pass = regional_pass_fraction >= profile.required_regional_pass_fraction
    sanity_pass = all(bool(row["pass"]) for row in sanity_rows)
    passed = global_pass and regional_pass and sanity_pass

    lines = [
        "# Population Capacity Simulation Report",
        "",
        f"**Overall: {'PASS' if passed else 'FAIL'}**",
        "",
        f"- Profile: `{profile.path}`",
        f"- Runtime: {elapsed_seconds:.1f} seconds",
        f"- Locations: {int(preparation.get('locations') or initial.height):,}",
        f"- Checkpoints: {', '.join(str(year) for year in profile.checkpoint_years)} years",
        (
            f"- Primary target window: 0–{profile.primary_scored_through_year} years; "
            "later checkpoints are advisory"
        ),
        f"- Global primary target result: {'PASS' if global_pass else 'FAIL'}",
        (
            f"- Scored HYDE region checkpoints: {regional_pass_fraction:.1%} pass "
            f"(required {profile.required_regional_pass_fraction:.1%})"
        ),
        f"- Location sanity result: {'PASS' if sanity_pass else 'FAIL'}",
        "",
        "## Global checkpoints",
        "",
        "| Years | Calendar | Population | Growth | HYDE target | Error | Capacity | Fill | Development | Result |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in global_rows:
        lines.append(
            "| {year} | {calendar} | {population} | {ratio:.2f}× | {target} | {error} | "
            "{capacity} | {fill:.1%} | {development:.1f} | {result} |".format(
                year=row["year"],
                calendar=profile.start_year + int(row["year"]),
                population=_people(float(row["population"]), profile),
                ratio=float(row["ratio"]),
                target="—" if row["target_ratio"] is None else f"{float(row['target_ratio']):.2f}×",
                error="—" if row["error"] is None else f"{float(row['error']):+.1%}",
                capacity=_people(float(row["capacity"]), profile),
                fill=float(row["fill"]),
                development=float(row["development"]),
                result=(
                    "—"
                    if row["target_ratio"] is None
                    else (
                        str(row["unscored_label"])
                        if not row["scored"]
                        else ("PASS" if row["pass"] else "FAIL")
                    )
                ),
            )
        )

    lines.extend(
        [
            "",
            "## HYDE regional benchmarks",
            "",
            (
                f"Targets are normalized to each region's simulated year-0 population. "
                f"The ordinary tolerance is ±{profile.regional_tolerance:.0%}. "
                "Rows marked reference are plague/contact-shock observations; rows after the primary window are advisory. Neither is scored against the capacity-only model."
            ),
            (
                "HYDE source slices are 1300 (baseline), 1400, 1500, 1600, 1740, and 1840; "
                f"the report compares them with simulation years 0, 100, 200, 300, 400, and 500 from {profile.start_year}."
            ),
            "",
            "| Region | Years | Population | Growth | HYDE target | Error | Fill | Development | Result |",
            "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
        ]
    )
    for row in region_rows:
        result = (
            str(row["unscored_label"])
            if not row["scored"]
            else ("PASS" if row["pass"] else "FAIL")
        )
        lines.append(
            "| {region} | {year} | {population} | {ratio:.2f}× | {target:.2f}× | "
            "{error:+.1%} | {fill:.1%} | {development:.1f} | {result} |".format(
                region=row["label"],
                year=row["year"],
                population=_people(float(row["population"]), profile),
                ratio=float(row["ratio"]),
                target=float(row["target_ratio"]),
                error=float(row["error"]),
                fill=float(row["fill"]),
                development=float(row["development"]),
                result=result,
            )
        )

    lines.extend(
        [
            "",
            "## HYDE region starting composition",
            "",
            "The current simulator has no migration or pop-type promotion/demotion. Tribesmen have a parsed zero food-consumption baseline, so this profile exempts them from negative location-rank growth. That keeps tribesmen-heavy regions stable, but it does not manufacture the later transitions needed to follow every HYDE growth target.",
            "",
            "| Region | Game population | HYDE population signal | Peasants | Tribesmen | Capacity fill | Population within capacity | Development | Irrigation levels |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in _region_start_composition_rows(profile, snapshots[0]):
        lines.append(
            "| {label} | {population} | {hyde_population} | {peasant_share:.1%} | {tribesmen_share:.1%} | "
            "{fill:.1%} | {within_share:.1%} | {development:.1f} | {irrigation_levels:,.0f} |".format(
                label=row["label"],
                population=_people(float(row["population"]), profile),
                hyde_population=_people(
                    float(row["hyde_population"]) / profile.people_per_game_unit,
                    profile,
                ),
                peasant_share=float(row["peasant_share"]),
                tribesmen_share=float(row["tribesmen_share"]),
                fill=float(row["fill"]),
                within_share=float(row["within_share"]),
                development=float(row["development"]),
                irrigation_levels=float(row["irrigation_levels"]),
            )
        )

    spot_by_tag = {
        str(row["location_tag"]): row
        for row in initial.filter(
            pl.col("location_tag").is_in(profile.spot_check_locations)
        ).to_dicts()
    }
    lines.extend(
        [
            "",
            "## Named start-location checks",
            "",
            "| Location | HYDE region | Population | Capacity | Fill | Zero-dev potential | GAEZ zero-dev | HYDE zero-dev | Development | Irrigation |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for tag in profile.spot_check_locations:
        row = spot_by_tag.get(tag)
        if row is None:
            lines.append(f"| {tag} | missing | — | — | — | — | — | — | — | — |")
            continue
        capacity = float(row["local_population_capacity"] or 0.0)
        population = float(row["total_population"] or 0.0)
        lines.append(
            f"| {tag} | {row.get(HYDE_REGION_COLUMN) or 'unassigned'} | "
            f"{_people(population, profile)} | {_people(capacity, profile)} | "
            f"{population / max(capacity, 1e-12):.2f}× | "
            f"{float(row.get(ZERO_DEVELOPMENT_CAPACITY_COLUMN) or 0.0):,.1f} | "
            f"{float(row.get(GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN) or 0.0):,.1f} | "
            f"{float(row.get(HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN) or 0.0):,.1f} | "
            f"{float(row.get('development') or 0.0):.1f} | "
            f"{float(row.get(IRRIGATION_LEVELS_COLUMN) or 0.0):.0f} |"
        )

    irrigation = dict(preparation.get("irrigation") or {})
    capacity_sources = dict(preparation.get("capacity_sources") or {})
    capacity_attribution = dict(preparation.get("capacity_attribution") or {})
    lines.extend(
        [
            "",
            "## Development and capacity settings",
            "",
            "- Starting-population capacity floor: none (starting population is validation-only)",
            (
                "- Zero-development potential: the larger of "
                f"{profile.gaez_zero_development_fraction:.1%} of independent GAEZ capacity "
                f"(capped at {profile.gaez_zero_development_density_cap:g} people/km²) "
                f"or {profile.hyde_rainfed_capacity_multiplier:g}× HYDE rainfed population "
                "with the current development effect backed out"
            ),
            (
                "- Independent physical inputs: "
                + ", ".join(profile.physical_capacity_columns)
            ),
            (
                "- Development capacity: "
                f"+{profile.capacity_formula.development_absolute:g} absolute and "
                f"{profile.capacity_formula.development_relative:+g} relative per point"
            ),
            (
                "- Parsed inherent development change: "
                f"{float(preparation.get('development_monthly_per_point') or 0.0):+g} "
                "local monthly development per current development point"
            ),
            (
                "- Irrigation capacity: "
                f"+{profile.capacity_formula.irrigation_absolute:g} absolute and "
                f"{profile.capacity_formula.irrigation_relative:+g} relative per level"
            ),
            (
                "- HYDE development model: "
                f"HYDE cropland / GAEZ `{profile.development_manageable_cropland_column}` "
                f"through an exponential saturation curve at rate "
                f"{profile.development_cropland_saturation_rate:g} toward "
                f"{profile.development_cropland_utilization_points:g} points; full pasture "
                f"share +{profile.development_pasture_full_share_points:g}; no population or "
                "regional-offset input"
            ),
            "",
            "```text",
            (
                "U = HYDE cropland share / GAEZ manageable cropland"
            ),
            (
                "D = clamp("
                f"{profile.development_cropland_utilization_points:g} × "
                f"(1 - exp(-{profile.development_cropland_saturation_rate:g} × U)) + "
                f"{profile.development_pasture_full_share_points:g} × HYDE pasture share, "
                f"{profile.development_start_min:g}, {profile.development_start_max:g})"
            ),
            (
                "G0 = min("
                f"{profile.gaez_zero_development_fraction:g} × GAEZ optimal capacity, "
                f"area × {profile.gaez_zero_development_density_cap:g} people/km²)"
            ),
            (
                "H0 = max(0, "
                f"{profile.hyde_rainfed_capacity_multiplier:g} × HYDE rainfed population / "
                f"(1 + {profile.capacity_formula.development_relative:g} × D) - "
                f"{profile.capacity_formula.development_absolute:g} × D)"
            ),
            "P0 = max(G0, H0)",
            (
                "Capacity = max(minimum, (ceil(P0) + "
                f"{profile.capacity_formula.development_absolute:g} × D + "
                f"{profile.capacity_formula.irrigation_absolute:g} × irrigation) × "
                f"(1 + {profile.capacity_formula.development_relative:g} × D))"
            ),
            "```",
            "",
            (
                "- Zero-development source totals: GAEZ "
                f"{_people(float(capacity_sources.get('gaez_sum') or 0.0), profile)}, HYDE "
                f"{_people(float(capacity_sources.get('hyde_sum') or 0.0), profile)}, selected max "
                f"{_people(float(capacity_sources.get('zero_development_sum') or 0.0), profile)}"
            ),
            (
                "- Dominant zero-development source by location: GAEZ "
                f"{int(capacity_sources.get('gaez_dominant_locations') or 0):,}; HYDE "
                f"{int(capacity_sources.get('hyde_dominant_locations') or 0):,}"
            ),
            (
                "- Starting capacity attribution: natural Location Potential "
                f"{float(capacity_attribution.get('natural_share') or 0.0):.1%}, "
                "Development "
                f"{float(capacity_attribution.get('development_share') or 0.0):.1%}, "
                "irrigation "
                f"{float(capacity_attribution.get('irrigation_share') or 0.0):.1%}"
            ),
            (
                "- Development absolute-term attribution: "
                f"{_people(float(capacity_attribution.get('development_absolute_total') or 0.0), profile)} "
                f"({float(capacity_attribution.get('development_absolute_share') or 0.0):.2%} "
                "of starting capacity)"
            ),
            "",
            "| Development | Minimum | Median | Mean | P90 | Maximum |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, summary in (
        ("Raw game start", preparation.get("starting_development_raw") or {}),
        ("Profile game start", preparation.get("starting_development_profile") or {}),
        ("Final", _numeric_summary(snapshots[max(snapshots)]["development"])),
    ):
        lines.append(
            f"| {label} | {float(summary.get('min', 0.0)):.1f} | "
            f"{float(summary.get('median', 0.0)):.1f} | {float(summary.get('mean', 0.0)):.1f} | "
            f"{float(summary.get('p90', 0.0)):.1f} | {float(summary.get('max', 0.0)):.1f} |"
        )

    lines.extend(
        [
            "",
            "## Irrigation placement",
            "",
            f"- Enabled: {bool(irrigation.get('enabled'))}",
            f"- HYDE evidence locations: {int(irrigation.get('evidence_locations') or 0):,}",
            f"- Starting irrigation locations: {int(irrigation.get('locations') or 0):,}",
            f"- Starting irrigation levels: {float(irrigation.get('levels') or 0.0):,.0f}",
            (
                "- River/lake-supported placements: "
                f"{float(irrigation.get('river_or_lake_location_fraction') or 0.0):.1%}"
            ),
            (
                "- Levels directly backed by river size: "
                f"{float(irrigation.get('river_supported_level_fraction') or 0.0):.1%}"
            ),
            f"- Non-river/lake placements: {int(irrigation.get('nonriver_locations') or 0):,}",
            f"- Legal-cap violations: {int(irrigation.get('cap_violations') or 0):,}",
            "",
            "## Capacity-pressure food settings",
            "",
            "| Band | Peasant consumption modifier | Absolute monthly food |",
            "|---|---:|---:|",
            (
                f"| Abundant | {profile.abundant_peasant_food_consumption:+.2f} | "
                f"{profile.abundant_monthly_food:g} |"
            ),
            (
                f"| Available | {profile.available_peasant_food_consumption:+.2f} | "
                f"{profile.available_monthly_food:g} |"
            ),
            f"| Overpopulation | {profile.overpopulation_peasant_food_consumption:+.2f} | 0 |",
            "",
            (
                "- Pop types exempt from negative location-rank growth: "
                + (
                    ", ".join(sorted(profile.rank_degrowth_exempt_pop_types))
                    if profile.rank_degrowth_exempt_pop_types
                    else "none"
                )
            ),
            (
                "- Pop types exempt from food-storage population growth: "
                + (
                    ", ".join(
                        sorted(profile.food_storage_growth_exempt_pop_types)
                    )
                    if profile.food_storage_growth_exempt_pop_types
                    else "none"
                )
            ),
            "",
            "## Capacity-pressure coverage",
            "",
            "Population share reports how much of the world is actually receiving each band. The neutral gap is the intentional below-10%-fill, 10k-or-more population case.",
            "",
            "| Years | Abundant pop | Available pop | Neutral-gap pop | Over-capacity pop | Abundant locations | Available locations | Neutral-gap locations | Over-capacity locations |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in _capacity_pressure_rows(snapshots):
        lines.append(
            "| {year} | {abundant_population:.1%} | {available_population:.1%} | "
            "{neutral_population:.1%} | {over_population:.1%} | "
            "{abundant_locations:,} | {available_locations:,} | "
            "{neutral_locations:,} | {over_locations:,} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Location ranges by checkpoint",
            "",
            "| Years | Population min | Population max | Capacity min | Capacity max | Fill min | Fill max | Development min | Development max | Over capacity |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in _location_range_rows(snapshots):
        lines.append(
            "| {year} | {population_min:.3f} | {population_max:,.1f} | "
            "{capacity_min:.3f} | {capacity_max:,.1f} | {fill_min:.3f}× | "
            "{fill_max:.3f}× | {development_min:.1f} | {development_max:.1f} | "
            "{over_capacity:,} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Location sanity checks",
            "",
            "| Check | Observed | Limit | Result |",
            "|---|---:|---:|:---:|",
        ]
    )
    for row in sanity_rows:
        lines.append(
            f"| {row['name']} | {row['observed']} | {row['limit']} | "
            f"{'PASS' if row['pass'] else 'FAIL'} |"
        )

    lines.extend(["", "## Starting-capacity contradictions", ""])
    lines.extend(_starting_capacity_contradiction_report(profile, snapshots[0]))
    lines.extend(["", "## Location extremes", ""])
    lines.extend(_location_extreme_report(profile, snapshots))
    lines.extend(
        [
            "",
            "## Iteration notes",
            "",
            "Edit the profile TOML and rerun the same command. This report is replaced in place; no monthly history files are produced.",
            "",
        ]
    )
    return "\n".join(lines), passed


def _global_rows(
    profile: SimulationProfile,
    snapshots: Mapping[int, pl.DataFrame],
    initial_population: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year, frame in snapshots.items():
        population = float(frame["total_population"].sum())
        capacity = float(frame["local_population_capacity"].sum())
        ratio = population / initial_population if initial_population else 0.0
        target = profile.global_ratios.get(year)
        error = ratio / target - 1.0 if target else None
        scored = (
            target is not None
            and year not in profile.global_excluded_years
            and year <= profile.primary_scored_through_year
        )
        rows.append(
            {
                "year": year,
                "population": population,
                "capacity": capacity,
                "ratio": ratio,
                "target_ratio": target,
                "error": error,
                "scored": scored,
                "unscored_label": (
                    "advisory"
                    if year > profile.primary_scored_through_year
                    else "reference"
                ),
                "pass": abs(error) <= profile.global_tolerance if scored and error is not None else None,
                "fill": population / capacity if capacity else math.inf,
                "development": float(frame["development"].mean()),
            }
        )
    return rows


def _region_rows(
    profile: SimulationProfile,
    snapshots: Mapping[int, pl.DataFrame],
) -> list[dict[str, Any]]:
    aggregates: dict[int, dict[str, dict[str, float]]] = {}
    for year, frame in snapshots.items():
        grouped = frame.group_by(HYDE_REGION_COLUMN).agg(
            pl.col("total_population").sum().alias("population"),
            pl.col("local_population_capacity").sum().alias("capacity"),
            pl.col("development").mean().alias("development"),
        )
        aggregates[year] = {str(row[HYDE_REGION_COLUMN]): row for row in grouped.to_dicts()}
    rows: list[dict[str, Any]] = []
    for region in profile.regions:
        start = float(aggregates[0].get(region.key, {}).get("population") or 0.0)
        if start <= 0.0:
            continue
        for year, target in sorted(region.ratios.items()):
            current = aggregates.get(year, {}).get(region.key)
            if current is None:
                continue
            population = float(current["population"] or 0.0)
            capacity = float(current["capacity"] or 0.0)
            ratio = population / start
            error = ratio / target - 1.0
            scored = (
                year not in region.excluded_years
                and year <= profile.primary_scored_through_year
            )
            rows.append(
                {
                    "region": region.key,
                    "label": region.label,
                    "year": year,
                    "population": population,
                    "ratio": ratio,
                    "target_ratio": target,
                    "error": error,
                    "fill": population / capacity if capacity else math.inf,
                    "development": float(current["development"] or 0.0),
                    "scored": scored,
                    "unscored_label": (
                        "advisory"
                        if year > profile.primary_scored_through_year
                        else "reference"
                    ),
                    "pass": abs(error) <= profile.regional_tolerance if scored else None,
                }
            )
    return rows


def _region_start_composition_rows(
    profile: SimulationProfile,
    initial: pl.DataFrame,
) -> list[dict[str, Any]]:
    peasants = (
        pl.col("population_peasants")
        if "population_peasants" in initial.columns
        else pl.lit(0.0)
    )
    tribesmen = (
        pl.col("population_tribesmen")
        if "population_tribesmen" in initial.columns
        else pl.lit(0.0)
    )
    grouped = initial.group_by(HYDE_REGION_COLUMN).agg(
        pl.col("total_population").sum().alias("population"),
        pl.col(HYDE_POPULATION_COLUMN).sum().alias("hyde_population"),
        peasants.sum().alias("peasants"),
        tribesmen.sum().alias("tribesmen"),
        pl.col("local_population_capacity").sum().alias("capacity"),
        pl.when(pl.col("total_population") <= pl.col("local_population_capacity"))
        .then(pl.col("total_population"))
        .otherwise(0.0)
        .sum()
        .alias("within_population"),
        pl.col("development").mean().alias("development"),
        pl.col(IRRIGATION_LEVELS_COLUMN).sum().alias("irrigation_levels"),
    )
    by_region = {str(row[HYDE_REGION_COLUMN]): row for row in grouped.to_dicts()}
    rows: list[dict[str, Any]] = []
    for region in profile.regions:
        current = by_region.get(region.key)
        if current is None:
            continue
        population = float(current["population"] or 0.0)
        capacity = float(current["capacity"] or 0.0)
        rows.append(
            {
                "key": region.key,
                "label": region.label,
                "population": population,
                "hyde_population": float(current["hyde_population"] or 0.0),
                "peasant_share": float(current["peasants"] or 0.0) / population
                if population
                else 0.0,
                "tribesmen_share": float(current["tribesmen"] or 0.0) / population
                if population
                else 0.0,
                "fill": population / capacity if capacity else math.inf,
                "within_share": float(current["within_population"] or 0.0)
                / population
                if population
                else 0.0,
                "development": float(current["development"] or 0.0),
                "irrigation_levels": float(current["irrigation_levels"] or 0.0),
            }
        )
    return rows


def _sanity_rows(
    profile: SimulationProfile,
    snapshots: Mapping[int, pl.DataFrame],
    preparation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    initial = snapshots[0].select("location_tag", pl.col("total_population").alias("start_population"))
    primary_snapshots = {
        year: frame
        for year, frame in snapshots.items()
        if year <= profile.primary_scored_through_year
    }
    all_capacities = np.concatenate(
        [frame["local_population_capacity"].to_numpy() for frame in primary_snapshots.values()]
    )
    all_populations = np.concatenate(
        [frame["total_population"].to_numpy() for frame in primary_snapshots.values()]
    )
    all_fill = all_populations / np.maximum(all_capacities, 1e-12)
    populated_start = snapshots[0].filter(pl.col("total_population") > 0)
    start_population = populated_start["total_population"].to_numpy()
    start_capacity = populated_start["local_population_capacity"].to_numpy()
    global_start_capacity_ratio = float(np.sum(start_capacity)) / max(
        float(np.sum(start_population)),
        1e-12,
    )
    start_population_within_capacity_fraction = float(
        np.sum(start_population[start_population <= start_capacity])
    ) / max(
        float(np.sum(start_population)),
        1e-12,
    )
    region_start = _region_start_composition_rows(profile, snapshots[0])
    scored_region_within = [
        float(row["within_share"])
        for row in region_start
        if str(row["key"]) in profile.start_capacity_scored_regions
    ]
    min_region_start_within = min(scored_region_within) if scored_region_within else 0.0
    established_start = populated_start.filter(
        pl.col("total_population") >= profile.established_population_threshold
    )
    established_start_fill = (
        established_start["total_population"].to_numpy()
        / np.maximum(
            established_start["local_population_capacity"].to_numpy(),
            1e-12,
        )
    )
    max_established_start_fill = (
        float(np.max(established_start_fill)) if established_start_fill.size else 0.0
    )
    start_development = snapshots[0]["development"].to_numpy()
    start_development_p90 = float(np.quantile(start_development, 0.90))
    start_development_ceiling_fraction = float(
        np.mean(
            np.isclose(
                start_development,
                profile.development_start_max,
                atol=10 ** (-profile.deployment_development_decimals),
            )
        )
    )
    capacity_attribution = dict(preparation.get("capacity_attribution") or {})
    natural_capacity_share = float(capacity_attribution.get("natural_share") or 0.0)
    development_capacity_share = float(
        capacity_attribution.get("development_share") or 0.0
    )
    finite = all(
        np.isfinite(frame[column].to_numpy()).all()
        for frame in primary_snapshots.values()
        for column in ("total_population", "local_population_capacity", "development")
    )
    nonnegative = all(
        (frame[column].to_numpy() >= 0.0).all()
        for frame in primary_snapshots.values()
        for column in ("total_population", "local_population_capacity")
    )
    rows = [
        _check("Finite population/capacity/development", int(finite), "1", finite),
        _check("Non-negative population and capacity", int(nonnegative), "1", nonnegative),
        _check(
            "Global start capacity/population",
            f"{global_start_capacity_ratio:.3f}×",
            f">= {profile.min_global_start_capacity_ratio:.3f}×",
            global_start_capacity_ratio >= profile.min_global_start_capacity_ratio,
        ),
        _check(
            "Start population living within local capacity",
            f"{start_population_within_capacity_fraction:.1%}",
            f">= {profile.min_start_population_within_capacity_fraction:.1%}",
            start_population_within_capacity_fraction
            >= profile.min_start_population_within_capacity_fraction,
        ),
        _check(
            "Worst scored HYDE-region start population within local capacity",
            f"{min_region_start_within:.1%}",
            f">= {profile.min_region_start_population_within_capacity_fraction:.1%}",
            min_region_start_within
            >= profile.min_region_start_population_within_capacity_fraction,
        ),
        _check(
            "Maximum established-location start capacity fill",
            f"{max_established_start_fill:.3f}×",
            f"<= {profile.max_established_start_capacity_fill:.3f}×",
            max_established_start_fill <= profile.max_established_start_capacity_fill,
        ),
        _check(
            "Minimum location capacity",
            f"{float(np.min(all_capacities)):.3f}",
            f">= {profile.min_location_capacity:.3f}",
            float(np.min(all_capacities)) >= profile.min_location_capacity,
        ),
        _check(
            "Maximum location capacity",
            f"{float(np.max(all_capacities)):,.1f}",
            f"<= {profile.max_location_capacity:,.1f}",
            float(np.max(all_capacities)) <= profile.max_location_capacity,
        ),
        _check(
            "Maximum location population",
            f"{float(np.max(all_populations)):,.1f}",
            f"<= {profile.max_location_population:,.1f}",
            float(np.max(all_populations)) <= profile.max_location_population,
        ),
        _check(
            "Maximum capacity fill",
            f"{float(np.max(all_fill)):.3f}×",
            f"<= {profile.max_location_capacity_fill:.3f}×",
            float(np.max(all_fill)) <= profile.max_location_capacity_fill,
        ),
        _check(
            "Maximum development",
            f"{max(float(frame['development'].max()) for frame in primary_snapshots.values()):.2f}",
            f"<= {profile.max_development:.2f}",
            max(float(frame["development"].max()) for frame in primary_snapshots.values())
            <= profile.max_development,
        ),
        _check(
            "Starting development P90",
            f"{start_development_p90:.2f}",
            (
                f"{profile.min_start_development_p90:.2f}–"
                f"{profile.max_start_development_p90:.2f}"
            ),
            profile.min_start_development_p90
            <= start_development_p90
            <= profile.max_start_development_p90,
        ),
        _check(
            "Locations at starting development ceiling",
            f"{start_development_ceiling_fraction:.2%}",
            f"<= {profile.max_start_development_ceiling_fraction:.2%}",
            start_development_ceiling_fraction
            <= profile.max_start_development_ceiling_fraction,
        ),
        _check(
            "Natural Location Potential share of starting capacity",
            f"{natural_capacity_share:.1%}",
            f">= {profile.min_start_natural_capacity_share:.1%}",
            natural_capacity_share >= profile.min_start_natural_capacity_share,
        ),
        _check(
            "Development share of starting capacity",
            f"{development_capacity_share:.1%}",
            f"<= {profile.max_start_development_capacity_share:.1%}",
            development_capacity_share
            <= profile.max_start_development_capacity_share,
        ),
    ]
    initial_total = float(snapshots[0]["total_population"].sum())
    for year, tolerance in (
        (25, profile.max_global_25y_deviation),
        (100, profile.max_global_100y_deviation),
    ):
        if year not in snapshots:
            continue
        ratio = float(snapshots[year]["total_population"].sum()) / initial_total
        rows.append(
            _check(
                f"Global {year}y stability",
                f"{ratio:.3f}×",
                f"within {tolerance:.1%} of start",
                abs(ratio - 1.0) <= tolerance + 1e-12,
            )
        )

    if 100 in snapshots:
        global_development_change = abs(
            float(snapshots[100]["development"].mean())
            - float(snapshots[0]["development"].mean())
        )
        region_keys = [region.key for region in profile.regions]
        start_region_development = (
            snapshots[0]
            .filter(pl.col(HYDE_REGION_COLUMN).is_in(region_keys))
            .group_by(HYDE_REGION_COLUMN)
            .agg(pl.col("development").mean().alias("start_development"))
        )
        region_development_change = (
            snapshots[100]
            .filter(pl.col(HYDE_REGION_COLUMN).is_in(region_keys))
            .group_by(HYDE_REGION_COLUMN)
            .agg(pl.col("development").mean().alias("development"))
            .join(start_region_development, on=HYDE_REGION_COLUMN, how="inner")
            .with_columns(
                (pl.col("development") - pl.col("start_development"))
                .abs()
                .alias("change")
            )
        )
        max_region_development_change = float(
            region_development_change["change"].max()
        )
        rows.extend(
            [
                _check(
                    "Global mean development change at 100y",
                    f"{global_development_change:.2f}",
                    f"<= {profile.max_global_100y_development_change:.2f}",
                    global_development_change
                    <= profile.max_global_100y_development_change,
                ),
                _check(
                    "Maximum HYDE-region mean development change at 100y",
                    f"{max_region_development_change:.2f}",
                    f"<= {profile.max_region_100y_development_change:.2f}",
                    max_region_development_change
                    <= profile.max_region_100y_development_change,
                ),
            ]
        )

    start_regions = snapshots[0].group_by(HYDE_REGION_COLUMN).agg(
        pl.col("total_population").sum().alias("start_population")
    )
    for year, lower, upper in (
        (25, profile.min_region_25y_ratio, profile.max_region_25y_ratio),
        (100, profile.min_region_100y_ratio, profile.max_region_100y_ratio),
    ):
        if year not in snapshots:
            continue
        region_growth = snapshots[year].group_by(HYDE_REGION_COLUMN).agg(
            pl.col("total_population").sum().alias("population")
        ).join(start_regions, on=HYDE_REGION_COLUMN, how="inner").filter(
            pl.col("start_population") > 0.0
        ).with_columns(
            (pl.col("population") / pl.col("start_population")).alias("growth_ratio")
        )
        observed_min = float(region_growth["growth_ratio"].min())
        observed_max = float(region_growth["growth_ratio"].max())
        rows.append(
            _check(
                f"HYDE-region {year}y stability range",
                f"{observed_min:.3f}×–{observed_max:.3f}×",
                f"{lower:.3f}×–{upper:.3f}×",
                observed_min >= lower and observed_max <= upper,
            )
        )
    irrigation = dict(preparation.get("irrigation") or {})
    if bool(irrigation.get("enabled")):
        river_or_lake_fraction = float(
            irrigation.get("river_or_lake_location_fraction") or 0.0
        )
        river_level_fraction = float(
            irrigation.get("river_supported_level_fraction") or 0.0
        )
        cap_violations = int(irrigation.get("cap_violations") or 0)
        rows.extend(
            [
                _check(
                    "Irrigation locations with river/lake support",
                    f"{river_or_lake_fraction:.1%}",
                    f">= {profile.min_irrigation_river_or_lake_fraction:.1%}",
                    river_or_lake_fraction
                    >= profile.min_irrigation_river_or_lake_fraction,
                ),
                _check(
                    "Irrigation levels directly supported by river size",
                    f"{river_level_fraction:.1%}",
                    f">= {profile.min_irrigation_river_supported_level_fraction:.1%}",
                    river_level_fraction
                    >= profile.min_irrigation_river_supported_level_fraction,
                ),
                _check(
                    "Irrigation legal-cap violations",
                    cap_violations,
                    f"<= {profile.max_irrigation_cap_violations}",
                    cap_violations <= profile.max_irrigation_cap_violations,
                ),
            ]
        )
    for year, lower, upper in (
        (
            25,
            profile.min_location_25y_growth_factor,
            profile.max_location_25y_growth_factor,
        ),
        (
            100,
            profile.min_location_100y_growth_factor,
            profile.max_location_100y_growth_factor,
        ),
    ):
        if year not in snapshots:
            continue
        growth = snapshots[year].join(initial, on="location_tag", how="left").filter(
            pl.col("start_population") >= 10.0
        ).with_columns(
            (pl.col("total_population") / pl.col("start_population")).alias("growth_factor")
        )
        minimum = float(growth["growth_factor"].min()) if growth.height else 0.0
        maximum = float(growth["growth_factor"].max()) if growth.height else 0.0
        rows.extend(
            [
                _check(
                    f"Minimum established-location {year}y growth",
                    f"{minimum:.3f}×",
                    f">= {lower:.3f}×",
                    minimum >= lower,
                ),
                _check(
                    f"Maximum established-location {year}y growth",
                    f"{maximum:.3f}×",
                    f"<= {upper:.3f}×",
                    maximum <= upper,
                ),
            ]
        )
    return rows


def _capacity_pressure_rows(
    snapshots: Mapping[int, pl.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year, frame in snapshots.items():
        population = frame["total_population"].to_numpy()
        capacity = frame["local_population_capacity"].to_numpy()
        fill = population / np.maximum(capacity, 1e-12)
        abundant = (fill < 0.10) & (population < 10.0)
        available = (fill >= 0.10) & (fill <= 1.0)
        neutral = (fill < 0.10) & (population >= 10.0)
        over = fill > 1.0
        total = max(float(np.sum(population)), 1e-12)
        rows.append(
            {
                "year": year,
                "abundant_population": float(np.sum(population[abundant])) / total,
                "available_population": float(np.sum(population[available])) / total,
                "neutral_population": float(np.sum(population[neutral])) / total,
                "over_population": float(np.sum(population[over])) / total,
                "abundant_locations": int(np.count_nonzero(abundant)),
                "available_locations": int(np.count_nonzero(available)),
                "neutral_locations": int(np.count_nonzero(neutral)),
                "over_locations": int(np.count_nonzero(over)),
            }
        )
    return rows


def _location_range_rows(
    snapshots: Mapping[int, pl.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year, frame in snapshots.items():
        population = frame["total_population"].to_numpy()
        capacity = frame["local_population_capacity"].to_numpy()
        development = frame["development"].to_numpy()
        fill = population / np.maximum(capacity, 1e-12)
        rows.append(
            {
                "year": year,
                "population_min": float(np.min(population)),
                "population_max": float(np.max(population)),
                "capacity_min": float(np.min(capacity)),
                "capacity_max": float(np.max(capacity)),
                "fill_min": float(np.min(fill)),
                "fill_max": float(np.max(fill)),
                "development_min": float(np.min(development)),
                "development_max": float(np.max(development)),
                "over_capacity": int(np.count_nonzero(fill > 1.0)),
            }
        )
    return rows


def _starting_capacity_contradiction_report(
    profile: SimulationProfile,
    initial: pl.DataFrame,
) -> list[str]:
    frame = initial.with_columns(
        (
            pl.col("total_population")
            / pl.col("local_population_capacity").clip(lower_bound=1e-12)
        ).alias("capacity_fill"),
        (
            pl.col(HYDE_CROPLAND_AREA_COLUMN)
            / pl.col("area_km2").clip(lower_bound=1e-12)
        ).alias("cropland_share"),
    )
    lines: list[str] = []
    selections = (
        (
            "Highest starting capacity pressure",
            frame.filter(pl.col("total_population") > 0.0).sort(
                "capacity_fill",
                descending=True,
            ),
        ),
        (
            "Highest established-location starting capacity pressure",
            frame.filter(
                pl.col("total_population") >= profile.established_population_threshold
            ).sort("capacity_fill", descending=True),
        ),
        (
            "Largest independent capacities in locations below 10k population",
            frame.filter(pl.col("total_population") < 10.0).sort(
                "local_population_capacity",
                descending=True,
            ),
        ),
    )
    for title, selected in selections:
        lines.extend(
            [
                f"### {title}",
                "",
                "| Location | HYDE region | Game population | HYDE population signal | Capacity | Fill | GAEZ full | GAEZ zero-dev | HYDE zero-dev | Final zero-dev | HYDE cropland share | Development | Irrigation |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in selected.head(profile.max_report_locations).to_dicts():
            lines.append(
                f"| {row['location_tag']} | {row.get(HYDE_REGION_COLUMN) or 'unassigned'} | "
                f"{_people(float(row['total_population']), profile)} | "
                f"{_people(float(row.get(HYDE_POPULATION_COLUMN) or 0.0) / profile.people_per_game_unit, profile)} | "
                f"{float(row['local_population_capacity']):,.2f} | "
                f"{float(row['capacity_fill']):.2f}× | "
                f"{float(row.get(PHYSICAL_POPULATION_CAPACITY_COLUMN) or 0.0):,.1f} | "
                f"{float(row.get(GAEZ_ZERO_DEVELOPMENT_CAPACITY_COLUMN) or 0.0):,.1f} | "
                f"{float(row.get(HYDE_RAINFED_CAPACITY_EVIDENCE_COLUMN) or 0.0):,.1f} | "
                f"{float(row.get(ZERO_DEVELOPMENT_CAPACITY_COLUMN) or 0.0):,.1f} | "
                f"{float(row['cropland_share']):.1%} | "
                f"{float(row['development']):.1f} | "
                f"{float(row.get(IRRIGATION_LEVELS_COLUMN) or 0.0):.0f} |"
            )
        lines.append("")
    return lines


def _location_extreme_report(
    profile: SimulationProfile,
    snapshots: Mapping[int, pl.DataFrame],
) -> list[str]:
    observation_year = max(
        year for year in snapshots if year <= profile.primary_scored_through_year
    )
    initial = snapshots[0].select(
        "location_tag",
        pl.col("total_population").alias("start_population"),
    )
    frame = snapshots[observation_year].join(initial, on="location_tag", how="left").with_columns(
        (
            pl.col("total_population")
            / pl.col("local_population_capacity").clip(lower_bound=1e-12)
        ).alias("capacity_fill"),
        (
            pl.col("total_population")
            / pl.col("start_population").clip(lower_bound=1e-12)
        ).alias("growth_factor"),
    )
    lines: list[str] = []
    metrics = (
        ("Largest populations", "total_population", True),
        ("Highest capacity fill", "capacity_fill", True),
        ("Fastest growth", "growth_factor", True),
        ("Largest capacities", "local_population_capacity", True),
        ("Lowest positive capacities", "local_population_capacity", False),
    )
    for title, metric, descending in metrics:
        selected = frame
        if title == "Lowest positive capacities":
            selected = selected.filter(pl.col(metric) > 0.0)
        selected = selected.sort(metric, descending=descending).head(profile.max_report_locations)
        lines.extend(
            [
                f"### {title} at {observation_year} years",
                "",
                "| Location | HYDE region | Population | Capacity | Fill | Growth | Development | Irrigation |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in selected.to_dicts():
            lines.append(
                f"| {row['location_tag']} | {row.get(HYDE_REGION_COLUMN) or 'unassigned'} | "
                f"{float(row['total_population']):,.2f} | "
                f"{float(row['local_population_capacity']):,.2f} | "
                f"{float(row['capacity_fill']):.2f}× | {float(row['growth_factor']):.2f}× | "
                f"{float(row['development']):.1f} | "
                f"{float(row.get(IRRIGATION_LEVELS_COLUMN) or 0.0):.0f} |"
            )
        lines.append("")
    return lines


def _numeric_summary(series: pl.Series) -> dict[str, float]:
    values = series.fill_null(0.0).cast(pl.Float64)
    return {
        "min": float(values.min() or 0.0),
        "median": float(values.median() or 0.0),
        "mean": float(values.mean() or 0.0),
        "p90": float(values.quantile(0.9, interpolation="linear") or 0.0),
        "max": float(values.max() or 0.0),
    }


def _people(game_units: float, profile: SimulationProfile) -> str:
    people = game_units * profile.people_per_game_unit
    if abs(people) >= 1_000_000_000:
        return f"{people / 1_000_000_000:.3f}b"
    if abs(people) >= 1_000_000:
        return f"{people / 1_000_000:.1f}m"
    if abs(people) >= 1_000:
        return f"{people / 1_000:.1f}k"
    return f"{people:.0f}"


def _check(name: str, observed: Any, limit: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "observed": observed, "limit": limit, "pass": bool(passed)}


def _mapping(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing [{key}] table")
    return value


def _string(raw: Mapping[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise ValueError(f"missing {key}")
    return value


def _float(raw: Mapping[str, Any], key: str) -> float:
    try:
        value = float(raw[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid numeric value {key}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def _nonnegative_float(raw: Mapping[str, Any], key: str) -> float:
    value = _float(raw, key)
    if value < 0.0:
        raise ValueError(f"{key} must be non-negative")
    return value


def _positive_float(raw: Mapping[str, Any], key: str) -> float:
    value = _float(raw, key)
    if value <= 0.0:
        raise ValueError(f"{key} must be positive")
    return value


def _integer(raw: Mapping[str, Any], key: str) -> int:
    try:
        return int(raw[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid integer {key}") from exc


def _positive_integer(raw: Mapping[str, Any], key: str) -> int:
    value = _integer(raw, key)
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _nonnegative_integer(raw: Mapping[str, Any], key: str) -> int:
    value = _integer(raw, key)
    if value < 0:
        raise ValueError(f"{key} must be non-negative")
    return value


def _integer_list(raw: Mapping[str, Any], key: str) -> list[int]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return [int(item) for item in value]


def _fraction(raw: Mapping[str, Any], key: str) -> float:
    value = _float(raw, key)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{key} must be between 0 and 1")
    return value


def _year_mapping(raw: Any, label: str) -> dict[int, float]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a table")
    out: dict[int, float] = {}
    for key, value in raw.items():
        year = int(key)
        ratio = float(value)
        if year < 0 or not math.isfinite(ratio) or ratio <= 0.0:
            raise ValueError(f"{label}.{key} must be a positive finite ratio")
        out[year] = ratio
    return out


def _string_float_mapping(raw: Any, label: str) -> dict[str, float]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a table")
    out: dict[str, float] = {}
    for key, value in raw.items():
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{label}.{key} must be finite")
        out[str(key)] = number
    return out


def _resolve(root: Path, path: Path) -> Path:
    return path.expanduser().resolve() if path.is_absolute() else (root / path).resolve()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
