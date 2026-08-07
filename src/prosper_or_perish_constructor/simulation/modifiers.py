"""Modifier source loading, food-growth scaling, broadcast, and summing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
from eu5gameparser.domain.defines import load_define_data
from eu5gameparser.domain.location_ranks import load_location_rank_data
from eu5gameparser.domain.pop_types import load_pop_type_data
from eu5gameparser.domain.static_modifiers import load_static_modifier_data

from prosper_or_perish_constructor.simulation.capacity_pressure import (
    CapacityPressureBand,
    load_capacity_pressure_baselines,
)
from prosper_or_perish_constructor.simulation.food import (
    DEFAULT_FOOD_DECAY_RATE,
    FOOD_CONSUMPTION_COLUMN,
    MONTHS_STORED_COLUMN,
    aggregate_province_food,
    scale_years_from_months_stored,
)
from prosper_or_perish_constructor.simulation.population import MONTHS_PER_YEAR
from prosper_or_perish_constructor.simulation.prosperity import (
    LOCAL_MONTHLY_PROSPERITY_KEY,
    ProsperityBaselines,
    load_prosperity_baselines,
)

FOOD_GROWTH_MODIFIER_NAME = "positive_province_food_growth"
GROWTH_CAP_DEFINE_GROUP = "NEconomy"
GROWTH_CAP_DEFINE_KEY = "GROWTH_FROM_FOOD_MULTIPLIER_MAX"
SUBSISTENCE_DEFINE_GROUP = "NLocation"
SUBSISTENCE_DEFINE_KEY = "SUBSISTENCE_AGRICULTURE"
LOCATION_RANK_COLUMN = "location_rank"
SCALE_YEARS_COLUMN = "food_growth_scale_years"
SOURCE_RANK = "rank"
SOURCE_FOOD_GROWTH = "food_growth"

TRACKED_MODIFIER_KEYS = (
    "local_population_growth",
    "local_monthly_prosperity",
    "local_province_food_sales_output_modifier",
    "local_province_food_purchase_output_modifier",
)


@dataclass(frozen=True)
class SimulationModifierContext:
    """Parser-backed baselines reused across many ticks."""

    pop_food_rates: Mapping[str, float]
    growth_cap_years: float
    food_growth_baselines: Mapping[str, float]
    rank_baselines: pl.DataFrame
    subsistence_agriculture: float
    capacity_pressure: Mapping[str, CapacityPressureBand]
    prosperity: ProsperityBaselines
    food_decay_rate: float = DEFAULT_FOOD_DECAY_RATE


def load_pop_food_rates(
    *,
    profile: str,
    load_order_path: str | Path,
) -> dict[str, float]:
    """Load pop-type monthly food consumption rates from the constructor profile."""
    pop_types = load_pop_type_data(profile=profile, load_order_path=load_order_path)
    return {
        str(row["name"]): float(row["pop_food_consumption"] or 0.0)
        for row in pop_types.pop_types.select("name", "pop_food_consumption").to_dicts()
    }


def load_growth_cap_years(
    *,
    profile: str,
    load_order_path: str | Path,
) -> float:
    """Load ``NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX`` (years) from defines."""
    define_data = load_define_data(profile=profile, load_order_path=load_order_path)
    growth_cap = define_data.numeric_value(GROWTH_CAP_DEFINE_GROUP, GROWTH_CAP_DEFINE_KEY)
    if growth_cap is None:
        raise ValueError(f"missing define {GROWTH_CAP_DEFINE_GROUP}.{GROWTH_CAP_DEFINE_KEY}")
    growth_cap_years = float(growth_cap)
    if growth_cap_years < 0:
        raise ValueError(f"{GROWTH_CAP_DEFINE_KEY} must be non-negative: {growth_cap_years}")
    return growth_cap_years


def load_subsistence_agriculture(
    *,
    profile: str,
    load_order_path: str | Path,
) -> float:
    """Load ``NLocation.SUBSISTENCE_AGRICULTURE`` (food per unemployed peasant) from defines."""
    define_data = load_define_data(profile=profile, load_order_path=load_order_path)
    value = define_data.numeric_value(SUBSISTENCE_DEFINE_GROUP, SUBSISTENCE_DEFINE_KEY)
    if value is None:
        raise ValueError(f"missing define {SUBSISTENCE_DEFINE_GROUP}.{SUBSISTENCE_DEFINE_KEY}")
    subsistence = float(value)
    if subsistence < 0:
        raise ValueError(f"{SUBSISTENCE_DEFINE_KEY} must be non-negative: {subsistence}")
    return subsistence


def load_simulation_modifier_context(
    *,
    profile: str,
    load_order_path: str | Path,
    tracked_keys: Sequence[str] = TRACKED_MODIFIER_KEYS,
) -> SimulationModifierContext:
    """Load pop food rates, growth cap, food-growth baselines, and rank baselines."""
    pop_food_rates = load_pop_food_rates(profile=profile, load_order_path=load_order_path)
    growth_cap_years = load_growth_cap_years(profile=profile, load_order_path=load_order_path)
    subsistence_agriculture = load_subsistence_agriculture(
        profile=profile,
        load_order_path=load_order_path,
    )
    capacity_pressure = load_capacity_pressure_baselines(
        profile=profile,
        load_order_path=load_order_path,
    )

    static = load_static_modifier_data(profile=profile, load_order_path=load_order_path)
    food_growth_baselines = {
        key: float(static.modifier_baseline(FOOD_GROWTH_MODIFIER_NAME, None, key))
        for key in tracked_keys
    }

    ranks = load_location_rank_data(profile=profile, load_order_path=load_order_path)
    rank_rows: list[dict[str, Any]] = []
    for name in ranks._by_name:
        row: dict[str, Any] = {LOCATION_RANK_COLUMN: name}
        for key in tracked_keys:
            row[key] = float(ranks.modifier_baseline(name, "rank_modifier", key))
        rank_rows.append(row)
    rank_baselines = pl.DataFrame(rank_rows) if rank_rows else pl.DataFrame({LOCATION_RANK_COLUMN: []})

    prosperity = load_prosperity_baselines(
        profile=profile,
        load_order_path=load_order_path,
        food_growth_monthly_prosperity=float(
            food_growth_baselines.get(LOCAL_MONTHLY_PROSPERITY_KEY, 0.0)
        ),
        repo=Path(load_order_path).resolve().parent,
    )

    return SimulationModifierContext(
        pop_food_rates=pop_food_rates,
        growth_cap_years=growth_cap_years,
        food_growth_baselines=food_growth_baselines,
        rank_baselines=rank_baselines,
        subsistence_agriculture=subsistence_agriculture,
        capacity_pressure=capacity_pressure,
        prosperity=prosperity,
        food_decay_rate=DEFAULT_FOOD_DECAY_RATE,
    )


def source_column(key: str, source: str) -> str:
    return f"src__{key}__{source}"


def scale_positive_province_food_growth(
    provinces: pl.DataFrame,
    baselines: Mapping[str, float],
    *,
    growth_cap_years: float,
    months_per_year: float = MONTHS_PER_YEAR,
) -> pl.DataFrame:
    """Attach capped year-scale and scaled food-growth modifier columns to a province frame."""
    if MONTHS_STORED_COLUMN not in provinces.columns:
        raise ValueError(f"missing {MONTHS_STORED_COLUMN}")
    if "province" not in provinces.columns:
        raise ValueError("missing province column")

    scaled = provinces.with_columns(
        scale_years_from_months_stored(
            pl.col(MONTHS_STORED_COLUMN).fill_null(0.0).cast(pl.Float64),
            growth_cap_years=growth_cap_years,
            months_per_year=months_per_year,
        ).alias(SCALE_YEARS_COLUMN)
    )
    return scaled.with_columns(
        [
            (pl.col(SCALE_YEARS_COLUMN) * float(baselines.get(key, 0.0))).alias(key)
            for key in baselines
        ]
    )


def broadcast_province_modifiers_to_locations(
    locations: pl.DataFrame,
    provinces: pl.DataFrame,
    *,
    keys: Sequence[str],
    source: str = SOURCE_FOOD_GROWTH,
) -> pl.DataFrame:
    """Join province-level modifier values onto every location in the province as source columns."""
    if "province" not in locations.columns or "province" not in provinces.columns:
        raise ValueError("locations and provinces both require a province column")
    select_cols = ["province", *[key for key in keys if key in provinces.columns]]
    if len(select_cols) == 1:
        raise ValueError("provinces frame has none of the requested modifier keys")
    renamed = provinces.select(select_cols).rename(
        {key: source_column(key, source) for key in select_cols if key != "province"}
    )
    return locations.join(renamed, on="province", how="left")


def attach_rank_modifier_sources(
    locations: pl.DataFrame,
    rank_baselines: pl.DataFrame,
    *,
    keys: Sequence[str],
    source: str = SOURCE_RANK,
) -> pl.DataFrame:
    """Join location-rank baselines onto locations as source columns."""
    rank_column = LOCATION_RANK_COLUMN
    if rank_column not in locations.columns and "rank" in locations.columns:
        locations = locations.with_columns(pl.col("rank").alias(rank_column))
    if rank_column not in locations.columns:
        raise ValueError(f"missing {rank_column} (or rank) column")
    if LOCATION_RANK_COLUMN not in rank_baselines.columns:
        raise ValueError(f"rank_baselines missing {LOCATION_RANK_COLUMN}")

    select_cols = [LOCATION_RANK_COLUMN, *[key for key in keys if key in rank_baselines.columns]]
    renamed = rank_baselines.select(select_cols).rename(
        {key: source_column(key, source) for key in select_cols if key != LOCATION_RANK_COLUMN}
    )
    return locations.join(renamed, on=LOCATION_RANK_COLUMN, how="left")


def sum_modifier_sources(
    locations: pl.DataFrame,
    *,
    keys: Sequence[str],
    sources: Sequence[str],
) -> pl.DataFrame:
    """Sum ``src__<key>__<source>`` columns into effective ``local_*`` / tracked keys."""
    updates: list[pl.Expr] = []
    for key in keys:
        parts = [
            pl.col(source_column(key, source)).fill_null(0.0).cast(pl.Float64)
            for source in sources
            if source_column(key, source) in locations.columns
        ]
        if not parts:
            updates.append(pl.lit(0.0).alias(key))
        else:
            total = parts[0]
            for part in parts[1:]:
                total = total + part
            updates.append(total.alias(key))
    return locations.with_columns(updates)


def apply_food_growth_and_rank_modifiers(
    locations: pl.DataFrame,
    context: SimulationModifierContext,
    *,
    tracked_keys: Sequence[str] = TRACKED_MODIFIER_KEYS,
) -> pl.DataFrame:
    """Compute province food-growth sources, attach rank sources, and sum into effective modifiers.

    ``months_stored`` / ``food_growth_scale_years`` stay on a temporary province frame
    only; they are not written onto location state.
    """
    provinces = aggregate_province_food(locations)
    scaled = scale_positive_province_food_growth(
        provinces,
        context.food_growth_baselines,
        growth_cap_years=context.growth_cap_years,
    )
    stale = [
        column
        for column in locations.columns
        if column in {MONTHS_STORED_COLUMN, SCALE_YEARS_COLUMN}
        or column.startswith("src__")
    ]
    base = locations.drop(stale) if stale else locations
    with_food = broadcast_province_modifiers_to_locations(
        base,
        scaled,
        keys=tracked_keys,
        source=SOURCE_FOOD_GROWTH,
    )
    with_rank = attach_rank_modifier_sources(
        with_food,
        context.rank_baselines,
        keys=tracked_keys,
        source=SOURCE_RANK,
    )
    return sum_modifier_sources(
        with_rank,
        keys=tracked_keys,
        sources=(SOURCE_RANK, SOURCE_FOOD_GROWTH),
    )


def drop_ephemeral_simulation_columns(locations: pl.DataFrame) -> pl.DataFrame:
    """Remove tick-derived columns that are not part of persisted game state."""
    ephemeral = {
        FOOD_CONSUMPTION_COLUMN,
        MONTHS_STORED_COLUMN,
        SCALE_YEARS_COLUMN,
        *TRACKED_MODIFIER_KEYS,
    }
    drop = [
        column
        for column in locations.columns
        if column in ephemeral or column.startswith("src__")
    ]
    return locations.drop(drop) if drop else locations


def sort_location_state_columns(locations: pl.DataFrame) -> pl.DataFrame:
    """Stable alphabetical column order for persisted location state frames."""
    return locations.select(sorted(locations.columns))


def finalize_location_state(locations: pl.DataFrame) -> pl.DataFrame:
    """Strip derived tick columns and sort remaining state columns."""
    return sort_location_state_columns(drop_ephemeral_simulation_columns(locations))
