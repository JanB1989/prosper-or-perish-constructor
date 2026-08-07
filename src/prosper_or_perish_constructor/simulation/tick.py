"""Outermost simulation tick: advance location state by one or more months."""

from __future__ import annotations

import polars as pl

from prosper_or_perish_constructor.simulation.food import (
    compute_location_food_consumption,
    initialize_location_food_at_cap,
)
from prosper_or_perish_constructor.simulation.modifiers import (
    SimulationModifierContext,
    finalize_location_state,
)
from prosper_or_perish_constructor.simulation.numpy_engine import numpy_state_from_polars

__all__ = [
    "advance_tick",
    "finalize_location_state",
    "prepare_start_locations",
]


def prepare_start_locations(
    locations: pl.DataFrame,
    context: SimulationModifierContext,
) -> pl.DataFrame:
    """Prepare game-start locations with ``food`` stocked at the define cap.

    Transiently computes ``food_consumption``, then sets
    ``food = food_consumption * GROWTH_FROM_FOOD_MULTIPLIER_MAX * 12`` and drops
    derived columns so only persisted state remains. Also attaches fixed
    ``peasant_employment`` plus current employed/unemployed peasant columns.
    """
    from prosper_or_perish_constructor.simulation.food import attach_peasant_employment_state

    frame = attach_peasant_employment_state(locations)
    frame = compute_location_food_consumption(frame, context.pop_food_rates)
    frame = initialize_location_food_at_cap(frame, growth_cap_years=context.growth_cap_years)
    return finalize_location_state(frame)


def advance_tick(
    locations: pl.DataFrame,
    context: SimulationModifierContext,
    *,
    months: int = 1,
) -> pl.DataFrame:
    """Advance the location game state by ``months`` ticks.

    Uses a NumPy hot path: food consumption → province food-growth scale → rank
    baselines → population growth. Derived modifier columns are not persisted.
    """
    if months < 0:
        raise ValueError(f"months must be non-negative: {months}")
    if months == 0:
        return finalize_location_state(locations)

    engine = numpy_state_from_polars(locations, context)
    engine.tick_months(months)
    return engine.to_polars()
