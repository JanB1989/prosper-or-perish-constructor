"""Population growth step for the simulation tick."""

from __future__ import annotations

import math

import polars as pl

MONTHS_PER_YEAR = 12
YEARLY_GROWTH_COLUMN = "local_population_growth"
POPULATION_PREFIX = "population_"
TOTAL_POPULATION_COLUMN = "total_population"
PEASANTS_COLUMN = "population_peasants"
UNEMPLOYED_PEASANTS_COLUMN = "unemployed_peasants"
EMPLOYED_PEASANTS_COLUMN = "employed_peasants"
PEASANT_EMPLOYMENT_COLUMN = "peasant_employment"


def rebalance_peasant_employment(
    peasants: float,
    peasant_employment: float,
) -> tuple[float, float]:
    """Fill fixed peasant jobs first; remainder is unemployed (both floored at 0)."""
    peasants = max(float(peasants), 0.0)
    jobs = max(float(peasant_employment), 0.0)
    employed = min(peasants, jobs)
    return employed, peasants - employed


def monthly_growth_multiplier(yearly_rate: float, *, months: int = 1) -> float:
    """Convert a yearly fractional growth rate into a multi-month compound multiplier.

    ``yearly_rate=0.02`` means population scales by ``1.02`` over one year, so one
    month uses ``1.02 ** (1/12)``.
    """
    if months < 0:
        raise ValueError(f"months must be non-negative: {months}")
    if months == 0:
        return 1.0
    return float((1.0 + yearly_rate) ** (months / MONTHS_PER_YEAR))


def apply_population_growth(
    locations: pl.DataFrame,
    *,
    months: int = 1,
    yearly_growth_column: str = YEARLY_GROWTH_COLUMN,
) -> pl.DataFrame:
    """Advance location population columns by ``months`` ticks using yearly growth.

    Multiplies every ``population_*`` column and ``total_population`` (when present)
    by ``(1 + local_population_growth) ** (months / 12)``. Missing/null growth is
    treated as ``0.0``.
    """
    if months < 0:
        raise ValueError(f"months must be non-negative: {months}")
    if yearly_growth_column not in locations.columns:
        raise ValueError(f"missing yearly growth column: {yearly_growth_column}")

    population_columns = [
        column
        for column in locations.columns
        if column.startswith(POPULATION_PREFIX) or column == TOTAL_POPULATION_COLUMN
    ]
    if not population_columns:
        raise ValueError("no population columns to grow")

    if months == 0:
        return locations

    multiplier = (1.0 + pl.col(yearly_growth_column).fill_null(0.0).cast(pl.Float64)).pow(
        months / MONTHS_PER_YEAR
    )
    return locations.with_columns(
        [pl.col(column).fill_null(0.0).cast(pl.Float64) * multiplier for column in population_columns]
    )


def years_to_months(years: float) -> int:
    """Convert a year span to whole months, rejecting non-finite values."""
    if not math.isfinite(years) or years < 0:
        raise ValueError(f"years must be a non-negative finite number: {years}")
    return int(round(years * MONTHS_PER_YEAR))
