"""Food consumption and province food-storage aggregations for simulation ticks."""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from prosper_or_perish_constructor.simulation.population import (
    MONTHS_PER_YEAR,
    POPULATION_PREFIX,
    EMPLOYED_PEASANTS_COLUMN,
    PEASANT_EMPLOYMENT_COLUMN,
    PEASANTS_COLUMN,
    UNEMPLOYED_PEASANTS_COLUMN,
)

FOOD_COLUMN = "food"
FOOD_CONSUMPTION_COLUMN = "food_consumption"
PROVINCE_FOOD_COLUMN = "province_food"
PROVINCE_FOOD_CONSUMPTION_COLUMN = "province_food_consumption"
MONTHS_STORED_COLUMN = "months_stored"
# Placeholder until food-decay modifiers are wired; fraction of stored food destroyed per month.
DEFAULT_FOOD_DECAY_RATE = 0.01


def pop_food_consumption_modifier_column(pop_type: str) -> str:
    """Location modifier key for one pop type's food consumption, e.g. local_peasants_food_consumption."""
    return f"local_{pop_type}_food_consumption"


def compute_location_food_consumption(
    locations: pl.DataFrame,
    pop_food_rates: Mapping[str, float],
) -> pl.DataFrame:
    """Attach monthly ``food_consumption`` from pops × base rates × (1 + local consumption mods).

    For each pop type present as ``population_<type>``:
    ``population_<type> * pop_food_consumption * (1 + local_<type>_food_consumption)``,
    floored at ``0``. Missing modifier columns are treated as ``0``.
    """
    if "province" not in locations.columns:
        raise ValueError("missing province column")

    expr = pl.lit(0.0)
    matched = False
    for pop_type, rate in sorted(pop_food_rates.items()):
        column = f"{POPULATION_PREFIX}{pop_type}"
        if column not in locations.columns:
            continue
        matched = True
        modifier_column = pop_food_consumption_modifier_column(pop_type)
        if modifier_column in locations.columns:
            multiplier = 1.0 + pl.col(modifier_column).fill_null(0.0).cast(pl.Float64)
        else:
            multiplier = pl.lit(1.0)
        effective_rate = (pl.lit(float(rate)) * multiplier).clip(lower_bound=0.0)
        expr = expr + pl.col(column).fill_null(0.0).cast(pl.Float64) * effective_rate
    if not matched:
        raise ValueError("no population_* columns matched pop_food_rates")
    return locations.with_columns(expr.alias(FOOD_CONSUMPTION_COLUMN))


def aggregate_province_food(locations: pl.DataFrame) -> pl.DataFrame:
    """Province totals for stored ``food`` and monthly ``food_consumption``, plus months stored.

    ``months_stored = province_food / province_food_consumption`` when consumption > 0,
    otherwise ``0.0``.
    """
    required = {"province", FOOD_COLUMN, FOOD_CONSUMPTION_COLUMN}
    missing = sorted(required - set(locations.columns))
    if missing:
        raise ValueError(f"missing columns for province food aggregation: {', '.join(missing)}")

    return (
        locations.filter(pl.col("province").is_not_null())
        .group_by("province")
        .agg(
            [
                pl.col(FOOD_COLUMN).fill_null(0.0).cast(pl.Float64).sum().alias(PROVINCE_FOOD_COLUMN),
                pl.col(FOOD_CONSUMPTION_COLUMN)
                .fill_null(0.0)
                .cast(pl.Float64)
                .sum()
                .alias(PROVINCE_FOOD_CONSUMPTION_COLUMN),
            ]
        )
        .with_columns(
            pl.when(pl.col(PROVINCE_FOOD_CONSUMPTION_COLUMN) > 0.0)
            .then(pl.col(PROVINCE_FOOD_COLUMN) / pl.col(PROVINCE_FOOD_CONSUMPTION_COLUMN))
            .otherwise(0.0)
            .alias(MONTHS_STORED_COLUMN)
        )
    )


def scale_years_from_months_stored(
    months_stored: pl.Expr,
    *,
    growth_cap_years: float,
    months_per_year: float = MONTHS_PER_YEAR,
) -> pl.Expr:
    """Convert months of stored food into a capped year-scale for food-growth modifiers."""
    if growth_cap_years < 0:
        raise ValueError(f"growth_cap_years must be non-negative: {growth_cap_years}")
    return (months_stored / months_per_year).clip(
        lower_bound=0.0,
        upper_bound=float(growth_cap_years),
    )


def months_of_food_at_growth_cap(
    *,
    growth_cap_years: float,
    months_per_year: float = MONTHS_PER_YEAR,
) -> float:
    """Months of consumption needed to max the food-growth modifier (define × 12)."""
    if growth_cap_years < 0:
        raise ValueError(f"growth_cap_years must be non-negative: {growth_cap_years}")
    return float(growth_cap_years) * float(months_per_year)


def attach_peasant_employment_state(locations: pl.DataFrame) -> pl.DataFrame:
    """Attach fixed ``peasant_employment`` and current employed/unemployed peasant columns.

    Employment capacity is fixed for the simulation. Missing ``unemployed_peasants`` is
    treated as all peasants unemployed (capacity 0), matching startup-artifact fallbacks.
    """
    if PEASANTS_COLUMN not in locations.columns:
        raise ValueError(f"missing {PEASANTS_COLUMN}")

    peasants = pl.col(PEASANTS_COLUMN).fill_null(0.0).cast(pl.Float64).clip(lower_bound=0.0)
    if PEASANT_EMPLOYMENT_COLUMN in locations.columns:
        jobs = (
            pl.col(PEASANT_EMPLOYMENT_COLUMN).fill_null(0.0).cast(pl.Float64).clip(lower_bound=0.0)
        )
    elif UNEMPLOYED_PEASANTS_COLUMN in locations.columns:
        unemployed = (
            pl.col(UNEMPLOYED_PEASANTS_COLUMN).fill_null(0.0).cast(pl.Float64).clip(lower_bound=0.0)
        )
        jobs = (peasants - unemployed).clip(lower_bound=0.0)
    else:
        jobs = pl.lit(0.0)

    employed = pl.min_horizontal(peasants, jobs)
    unemployed = peasants - employed
    return locations.with_columns(
        jobs.alias(PEASANT_EMPLOYMENT_COLUMN),
        employed.alias(EMPLOYED_PEASANTS_COLUMN),
        unemployed.alias(UNEMPLOYED_PEASANTS_COLUMN),
    )


def initialize_location_food_at_cap(
    locations: pl.DataFrame,
    *,
    growth_cap_years: float,
    months_per_year: float = MONTHS_PER_YEAR,
) -> pl.DataFrame:
    """Set location ``food`` to exactly the growth-cap storage limit.

    ``food = food_consumption * GROWTH_FROM_FOOD_MULTIPLIER_MAX * 12``, so province
    ``months_stored`` equals the define cap and the food-growth modifier is maxed.
    """
    if FOOD_CONSUMPTION_COLUMN not in locations.columns:
        raise ValueError(f"missing {FOOD_CONSUMPTION_COLUMN}")
    months_at_cap = months_of_food_at_growth_cap(
        growth_cap_years=growth_cap_years,
        months_per_year=months_per_year,
    )
    return locations.with_columns(
        (pl.col(FOOD_CONSUMPTION_COLUMN).fill_null(0.0).cast(pl.Float64) * months_at_cap).alias(
            FOOD_COLUMN
        )
    )
