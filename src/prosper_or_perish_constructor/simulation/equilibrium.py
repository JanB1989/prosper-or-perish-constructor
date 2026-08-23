"""Algebraic province equilibrium analysis for the population simulation.

The long-run simulator is a discrete monthly map.  This module does not march
that map through time.  It eliminates the shared province food-storage scale,
prosperity, and development from their zero-change equations, then solves the
remaining scalar province food-balance equation for a composition-preserving
population multiplier.

With the current profile, capacity pressure and prosperity do not directly add
population growth.  Non-tribal population growth is therefore rank growth plus
the shared stored-food growth term, while tribesmen are stationary by explicit
profile exemptions.  That structure makes the reduction exact for a province
whose positive non-tribal locations share one rank baseline.  A mixed-rank
province receives an aggregate, composition-preserving quasi-equilibrium; the
reported individual growth spread states the approximation explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Callable

import numpy as np
import polars as pl

from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    OVERPOPULATION,
    capacity_pressure_strength_arrays,
)
from prosper_or_perish_constructor.simulation.modifiers import SimulationModifierContext
from prosper_or_perish_constructor.simulation.numpy_engine import (
    NumPyLocationState,
    numpy_state_from_polars,
)
from prosper_or_perish_constructor.simulation.population import (
    MONTHS_PER_YEAR,
    POPULATION_PREFIX,
)
from prosper_or_perish_constructor.simulation.prosperity import (
    DEVELOPMENT_MAX,
    LOCAL_MONTHLY_DEVELOPMENT_KEY,
    LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY,
    LOCAL_POPULATION_GROWTH_KEY,
    PROSPERITY_FULL_SCALE,
    PROSPERITY_MAX,
    ProsperityBaselines,
)


@dataclass(frozen=True)
class FoodBalancePoint:
    """One evaluation of the scalar province food-balance equation."""

    population_multiplier: float
    total_population: float
    movable_population: float
    fixed_population: float
    production: float
    consumption: float
    residual: float
    minimum_capacity_fill: float
    maximum_capacity_fill: float


@dataclass(frozen=True)
class ProvinceEquilibrium:
    """Algebraic aggregate or asymptotic resting point for one province."""

    province: str
    population_mode: str
    location_count: int
    starting_population: float
    starting_development_mean: float
    fixed_population: float
    movable_population: float
    eliminated_population: float
    stored_food_months: float
    stored_food_scale_years: float
    prosperity: float
    development: float
    population_multiplier: float | None
    population: float | None
    food_production: float | None
    food_consumption: float | None
    food_residual: float | None
    aggregate_annual_population_growth: float
    minimum_individual_annual_growth: float
    maximum_individual_annual_growth: float
    exact_positive_population_fixed_point: bool
    food_balance_locally_restoring: bool | None
    population_root_count: int
    pressure_threshold_crossing_count: int
    population_root_multipliers: tuple[float, ...]
    pressure_threshold_multipliers: tuple[float, ...]
    minimum_capacity_fill: float | None
    maximum_capacity_fill: float | None
    status: str


def prosperity_resting_point(
    stored_food_scale_years: float,
    baselines: ProsperityBaselines,
) -> float:
    """Solve the simulator's discrete prosperity zero-change equation.

    The monthly tick is::

        income = 100 * (base income + food income * stored years)
        next = (current + income) * (1 - global decay - local decay * current / 100)

    The positive interior solution is quadratic.  Values outside the permitted
    state interval are boundary equilibria created by the simulator clamp.
    """

    scale = max(float(stored_food_scale_years), 0.0)
    income = PROSPERITY_FULL_SCALE * (
        baselines.base_monthly_prosperity
        + baselines.food_growth_monthly_prosperity * scale
    )
    global_decay = min(max(float(baselines.global_prosperity_decay), 0.0), 1.0)
    local_per_point = max(float(baselines.local_prosperity_decay), 0.0) / PROSPERITY_FULL_SCALE

    if income <= 0.0:
        return 0.0
    if local_per_point > 0.0:
        linear = global_decay + local_per_point * income
        discriminant = linear * linear + 4.0 * local_per_point * income * (1.0 - global_decay)
        interior = (-linear + math.sqrt(max(discriminant, 0.0))) / (2.0 * local_per_point)
    elif global_decay > 0.0:
        interior = income * (1.0 - global_decay) / global_decay
    else:
        interior = PROSPERITY_MAX
    return min(max(float(interior), 0.0), PROSPERITY_MAX)


def development_resting_point(
    prosperity: float,
    baselines: ProsperityBaselines,
    *,
    minimum: float = 0.0,
    maximum: float = DEVELOPMENT_MAX,
) -> float:
    """Solve the simulator's development zero-change equation exactly."""

    prosperity_scale = min(max(float(prosperity) / PROSPERITY_FULL_SCALE, 0.0), 1.0)
    gain = prosperity_scale * baselines.get_effect(LOCAL_MONTHLY_DEVELOPMENT_KEY)
    decay_per_point = float(baselines.development_monthly_per_point)
    modifier = 1.0 + prosperity_scale * baselines.get_effect(
        LOCAL_MONTHLY_DEVELOPMENT_MODIFIER_KEY
    )

    if abs(modifier) <= 1e-15:
        return min(max(float(minimum), 0.0), float(maximum))
    if decay_per_point < 0.0:
        interior = -gain / decay_per_point
    elif gain > 0.0:
        interior = maximum
    else:
        interior = minimum
    return min(max(float(interior), float(minimum)), float(maximum))


def solve_province_equilibrium(
    locations: pl.DataFrame,
    context: SimulationModifierContext,
    *,
    population_mode: str = "aggregate",
    maximum_population_multiplier: float = 1_000.0,
) -> ProvinceEquilibrium:
    """Reduce and solve one province's current algebraic resting-point model.

    ``population_mode="aggregate"`` preserves the starting composition and
    zeros aggregate population growth.  ``population_mode="asymptotic"`` keeps
    only the positive non-exempt rank class with the least-negative baseline;
    incompatible rank classes are boundary-zero in the exact long-run fixed
    point. Pop types exempt from stored-food growth remain fixed in both modes.
    """

    if locations.height == 0:
        raise ValueError("cannot solve an empty province")
    provinces = locations["province"].cast(pl.String).fill_null("").unique().to_list()
    if len(provinces) != 1:
        raise ValueError(f"expected one province, found {len(provinces)}")
    if context.capacity_model is None:
        raise ValueError("equilibrium analysis requires a population-capacity formula")
    if population_mode not in {"aggregate", "asymptotic"}:
        raise ValueError("population_mode must be 'aggregate' or 'asymptotic'")

    state = numpy_state_from_polars(locations, context)
    unsupported_growth = _unsupported_direct_population_growth(context)
    if unsupported_growth:
        raise ValueError(
            "current algebraic reduction requires zero direct capacity/prosperity "
            f"population growth; nonzero effects: {', '.join(unsupported_growth)}"
        )

    movable_weight = 0.0
    weighted_rank = 0.0
    fixed_population = 0.0
    eliminated_population = 0.0
    individual_rank_growth: list[float] = []
    population_rows: list[tuple[np.ndarray, np.ndarray, str]] = []
    for column, pop in state.population.items():
        pop_type = column.removeprefix(POPULATION_PREFIX)
        amount = float(np.sum(pop))
        rank = state.rank_population_growth
        if pop_type in state.rank_degrowth_exempt_pop_types:
            rank = np.maximum(rank, 0.0)
        if pop_type in state.food_storage_growth_exempt_pop_types:
            fixed_population += amount
            continue
        population_rows.append((pop, rank, pop_type))

    surviving_rank_growth: float | None = None
    if population_mode == "asymptotic":
        positive_ranks = [
            float(rank_value)
            for pop, rank, _pop_type in population_rows
            for rank_value, weight in zip(rank, pop, strict=True)
            if weight > 0.0
        ]
        if positive_ranks:
            surviving_rank_growth = max(positive_ranks)

    for pop, rank, _pop_type in population_rows:
        if surviving_rank_growth is None:
            selected = np.ones(pop.shape, dtype=bool)
        else:
            selected = np.isclose(rank, surviving_rank_growth, atol=1e-15, rtol=0.0)
        selected_pop = np.where(selected, pop, 0.0)
        eliminated_population += float(np.sum(np.where(selected, 0.0, pop)))
        movable_weight += float(np.sum(selected_pop))
        weighted_rank += float(np.sum(selected_pop * rank))
        individual_rank_growth.extend(
            float(value)
            for value, weight in zip(rank, selected_pop, strict=True)
            if weight > 0.0
        )

    start_population = float(np.sum(state.total_population))
    start_development_mean = float(np.mean(state.development))
    if movable_weight <= 0.0:
        return ProvinceEquilibrium(
            province=str(provinces[0]),
            population_mode=population_mode,
            location_count=state.n,
            starting_population=start_population,
            starting_development_mean=start_development_mean,
            fixed_population=fixed_population,
            movable_population=0.0,
            eliminated_population=eliminated_population,
            stored_food_months=0.0,
            stored_food_scale_years=0.0,
            prosperity=prosperity_resting_point(0.0, context.prosperity),
            development=development_resting_point(
                prosperity_resting_point(0.0, context.prosperity),
                context.prosperity,
            ),
            population_multiplier=None,
            population=fixed_population,
            food_production=None,
            food_consumption=None,
            food_residual=None,
            aggregate_annual_population_growth=0.0,
            minimum_individual_annual_growth=0.0,
            maximum_individual_annual_growth=0.0,
            exact_positive_population_fixed_point=True,
            food_balance_locally_restoring=None,
            population_root_count=0,
            pressure_threshold_crossing_count=0,
            population_root_multipliers=(),
            pressure_threshold_multipliers=(),
            minimum_capacity_fill=None,
            maximum_capacity_fill=None,
            status="all population is fixed by food-growth exemptions",
        )

    food_growth = float(context.food_growth_baselines.get("local_population_growth", 0.0))
    if food_growth <= 0.0:
        raise ValueError("positive stored-food population growth is required")
    average_rank = weighted_rank / movable_weight
    scale_years = -average_rank / food_growth
    if not (0.0 <= scale_years <= context.growth_cap_years):
        return _unsolved_growth_boundary(
            province=str(provinces[0]),
            state=state,
            start_population=start_population,
            start_development_mean=start_development_mean,
            fixed_population=fixed_population,
            movable_population=movable_weight,
            scale_years=scale_years,
            context=context,
            individual_rank_growth=individual_rank_growth,
            population_mode=population_mode,
            eliminated_population=eliminated_population,
            status="zero aggregate population growth lies outside the stored-food growth band",
        )

    stored_months = scale_years * MONTHS_PER_YEAR
    prosperity = prosperity_resting_point(scale_years, context.prosperity)
    development = development_resting_point(prosperity, context.prosperity)

    evaluate = lambda multiplier: _food_balance_at_multiplier(
        state,
        context,
        population_multiplier=multiplier,
        stored_food_months=stored_months,
        prosperity=prosperity,
        development=development,
        surviving_rank_growth=surviving_rank_growth,
    )
    roots, threshold_crossings = _find_scalar_roots(
        lambda multiplier: evaluate(multiplier).residual,
        lower=0.0,
        upper=maximum_population_multiplier,
    )
    if not roots:
        growth_values = [rank + food_growth * scale_years for rank in individual_rank_growth]
        if threshold_crossings:
            lower, upper = min(
                threshold_crossings,
                key=lambda bracket: abs(
                    math.log(max((bracket[0] + bracket[1]) / 2.0, 1e-12))
                ),
            )
            midpoint = (lower + upper) / 2.0
            point = evaluate(midpoint)
            lower_residual = evaluate(lower).residual
            upper_residual = evaluate(upper).residual
            return ProvinceEquilibrium(
                province=str(provinces[0]),
                population_mode=population_mode,
                location_count=state.n,
                starting_population=start_population,
                starting_development_mean=start_development_mean,
                fixed_population=fixed_population,
                movable_population=movable_weight,
                eliminated_population=eliminated_population,
                stored_food_months=stored_months,
                stored_food_scale_years=scale_years,
                prosperity=prosperity,
                development=development,
                population_multiplier=midpoint,
                population=point.total_population,
                food_production=point.production,
                food_consumption=point.consumption,
                food_residual=point.residual,
                aggregate_annual_population_growth=0.0,
                minimum_individual_annual_growth=min(growth_values, default=0.0),
                maximum_individual_annual_growth=max(growth_values, default=0.0),
                exact_positive_population_fixed_point=False,
                food_balance_locally_restoring=(
                    lower_residual > 0.0 and upper_residual < 0.0
                ),
                population_root_count=0,
                pressure_threshold_crossing_count=len(threshold_crossings),
                population_root_multipliers=(),
                pressure_threshold_multipliers=tuple(
                    (lower + upper) / 2.0
                    for lower, upper in threshold_crossings
                ),
                minimum_capacity_fill=point.minimum_capacity_fill,
                maximum_capacity_fill=point.maximum_capacity_fill,
                status=(
                    "pressure-threshold setpoint: food balance changes sign "
                    "discontinuously, so a small limit cycle is expected"
                ),
            )
        return ProvinceEquilibrium(
            province=str(provinces[0]),
            population_mode=population_mode,
            location_count=state.n,
            starting_population=start_population,
            starting_development_mean=start_development_mean,
            fixed_population=fixed_population,
            movable_population=movable_weight,
            eliminated_population=eliminated_population,
            stored_food_months=stored_months,
            stored_food_scale_years=scale_years,
            prosperity=prosperity,
            development=development,
            population_multiplier=None,
            population=None,
            food_production=None,
            food_consumption=None,
            food_residual=None,
            aggregate_annual_population_growth=0.0,
            minimum_individual_annual_growth=min(growth_values, default=0.0),
            maximum_individual_annual_growth=max(growth_values, default=0.0),
            exact_positive_population_fixed_point=_single_growth_class(growth_values),
            food_balance_locally_restoring=None,
            population_root_count=0,
            pressure_threshold_crossing_count=len(threshold_crossings),
            population_root_multipliers=(),
            pressure_threshold_multipliers=tuple(
                (lower + upper) / 2.0
                for lower, upper in threshold_crossings
            ),
            minimum_capacity_fill=None,
            maximum_capacity_fill=None,
            status="no positive food-balance root found in the configured population band",
        )

    selected_multiplier = min(roots, key=lambda value: abs(math.log(max(value, 1e-12))))
    point = evaluate(selected_multiplier)
    epsilon = max(selected_multiplier * 1e-4, 1e-6)
    lower_residual = evaluate(max(selected_multiplier - epsilon, 0.0)).residual
    upper_residual = evaluate(selected_multiplier + epsilon).residual
    restoring = lower_residual >= point.residual and upper_residual <= point.residual
    growth_values = [rank + food_growth * scale_years for rank in individual_rank_growth]

    return ProvinceEquilibrium(
        province=str(provinces[0]),
        population_mode=population_mode,
        location_count=state.n,
        starting_population=start_population,
        starting_development_mean=start_development_mean,
        fixed_population=fixed_population,
        movable_population=movable_weight,
        eliminated_population=eliminated_population,
        stored_food_months=stored_months,
        stored_food_scale_years=scale_years,
        prosperity=prosperity,
        development=development,
        population_multiplier=selected_multiplier,
        population=point.total_population,
        food_production=point.production,
        food_consumption=point.consumption,
        food_residual=point.residual,
        aggregate_annual_population_growth=0.0,
        minimum_individual_annual_growth=min(growth_values, default=0.0),
        maximum_individual_annual_growth=max(growth_values, default=0.0),
        exact_positive_population_fixed_point=_single_growth_class(growth_values),
        food_balance_locally_restoring=restoring,
        population_root_count=len(roots),
        pressure_threshold_crossing_count=len(threshold_crossings),
        population_root_multipliers=roots,
        pressure_threshold_multipliers=tuple(
            (lower + upper) / 2.0
            for lower, upper in threshold_crossings
        ),
        minimum_capacity_fill=point.minimum_capacity_fill,
        maximum_capacity_fill=point.maximum_capacity_fill,
        status="solved",
    )


def _unsupported_direct_population_growth(context: SimulationModifierContext) -> list[str]:
    unsupported: list[str] = []
    for name, band in context.capacity_pressure.items():
        value = band.get("local_population_growth", 0.0)
        if abs(value) > 1e-15:
            unsupported.append(f"{name}={value:g}")
    prosperity = context.prosperity.get_effect(LOCAL_POPULATION_GROWTH_KEY)
    if abs(prosperity) > 1e-15:
        unsupported.append(f"prosperity={prosperity:g}")
    return unsupported


def _food_balance_at_multiplier(
    state: NumPyLocationState,
    context: SimulationModifierContext,
    *,
    population_multiplier: float,
    stored_food_months: float,
    prosperity: float,
    development: float,
    surviving_rank_growth: float | None,
) -> FoodBalancePoint:
    multiplier = max(float(population_multiplier), 0.0)
    population: dict[str, np.ndarray] = {}
    fixed_population = 0.0
    movable_population = 0.0
    for column, original in state.population.items():
        pop_type = column.removeprefix(POPULATION_PREFIX)
        if pop_type in state.food_storage_growth_exempt_pop_types:
            values = original
            fixed_population += float(np.sum(values))
        else:
            values = original * multiplier
            if surviving_rank_growth is not None:
                rank = state.rank_population_growth
                if pop_type in state.rank_degrowth_exempt_pop_types:
                    rank = np.maximum(rank, 0.0)
                values = np.where(
                    np.isclose(rank, surviving_rank_growth, atol=1e-15, rtol=0.0),
                    values,
                    0.0,
                )
            movable_population += float(np.sum(values))
        population[column] = values

    total_population = np.zeros(state.n, dtype=np.float64)
    for values in population.values():
        total_population += values

    development_values = np.full(state.n, float(development), dtype=np.float64)
    capacity = context.capacity_model.evaluate(
        base_capacity=state.base_population_capacity,
        development=development_values,
        infrastructure_capacity=state.infrastructure_population_capacity,
    )
    abundant, available, overpopulated, strength = capacity_pressure_strength_arrays(
        total_population,
        capacity,
    )

    prosperity_scale = min(max(float(prosperity) / PROSPERITY_FULL_SCALE, 0.0), 1.0)
    consumption = np.zeros(state.n, dtype=np.float64)
    for original, rate, static_modifier, pop_type in state.pop_terms:
        column = f"{POPULATION_PREFIX}{pop_type}"
        pop = population[column]
        capacity_modifier = _scaled_band_effect(
            abundant,
            available,
            overpopulated,
            strength,
            state.capacity_food_consumption.get(pop_type, {}),
        )
        prosperity_modifier = prosperity_scale * context.prosperity.food_consumption_effect(
            pop_type
        )
        modifier = capacity_modifier + prosperity_modifier
        if static_modifier is not None:
            modifier = modifier + static_modifier
        consumption += pop * np.maximum(float(rate) * (1.0 + modifier), 0.0)

    peasants = population.get("population_peasants", np.zeros(state.n, dtype=np.float64))
    unemployed = np.maximum(peasants - np.maximum(state.peasant_employment, 0.0), 0.0)
    monthly_food = _scaled_band_effect(
        abundant,
        available,
        overpopulated,
        strength,
        state.capacity_monthly_food,
    )
    production = unemployed * float(context.subsistence_agriculture) + monthly_food

    total_consumption = float(np.sum(consumption))
    total_production = float(np.sum(production))
    # The simulator adds net food first, reads stored months, then destroys a
    # fraction of that post-net stock.  At equilibrium with H stored months:
    # production - consumption = food_decay_rate * H * consumption.
    residual = total_production - total_consumption * (
        1.0 + float(context.food_decay_rate) * float(stored_food_months)
    )
    fill = np.divide(
        total_population,
        capacity,
        out=np.zeros_like(total_population),
        where=capacity > 0.0,
    )
    return FoodBalancePoint(
        population_multiplier=multiplier,
        total_population=float(np.sum(total_population)),
        movable_population=movable_population,
        fixed_population=fixed_population,
        production=total_production,
        consumption=total_consumption,
        residual=residual,
        minimum_capacity_fill=float(np.min(fill)),
        maximum_capacity_fill=float(np.max(fill)),
    )


def _scaled_band_effect(
    abundant: np.ndarray,
    available: np.ndarray,
    overpopulated: np.ndarray,
    strength: np.ndarray,
    baselines: Mapping[str, float],
) -> np.ndarray:
    out = np.zeros(strength.shape, dtype=np.float64)
    for mask, name in (
        (abundant, ABUNDANT_FREE_LAND),
        (available, AVAILABLE_FREE_LAND),
        (overpopulated, OVERPOPULATION),
    ):
        baseline = float(baselines.get(name, 0.0) or 0.0)
        if baseline:
            out[mask] = strength[mask] * baseline
    return out


def _find_scalar_roots(
    function: Callable[[float], float],
    *,
    lower: float,
    upper: float,
    samples: int = 2_048,
) -> tuple[tuple[float, ...], tuple[tuple[float, float], ...]]:
    if upper <= lower:
        raise ValueError("root-search upper bound must exceed lower bound")
    positive_lower = max(lower, 1e-8)
    grid = np.concatenate(
        (
            np.array([lower], dtype=np.float64),
            np.geomspace(positive_lower, upper, num=samples, dtype=np.float64),
        )
    )
    roots: list[float] = []
    threshold_crossings: list[tuple[float, float]] = []
    previous_x = float(grid[0])
    previous_y = float(function(previous_x))
    if abs(previous_y) <= 1e-10:
        roots.append(previous_x)
    for raw_x in grid[1:]:
        x = float(raw_x)
        y = float(function(x))
        if not (math.isfinite(previous_y) and math.isfinite(y)):
            previous_x, previous_y = x, y
            continue
        if abs(y) <= 1e-10:
            roots.append(x)
        elif previous_y * y < 0.0:
            candidate, residual, bracket = _bisect(
                function,
                previous_x,
                x,
                previous_y,
                y,
            )
            if abs(residual) <= 1e-7:
                roots.append(candidate)
            else:
                threshold_crossings.append(bracket)
        previous_x, previous_y = x, y
    deduplicated: list[float] = []
    for root in sorted(roots):
        if not deduplicated or abs(root - deduplicated[-1]) > max(1e-8, abs(root) * 1e-7):
            deduplicated.append(root)
    return tuple(deduplicated), tuple(threshold_crossings)


def _bisect(
    function: Callable[[float], float],
    lower: float,
    upper: float,
    lower_value: float,
    upper_value: float,
) -> tuple[float, float, tuple[float, float]]:
    left, right = float(lower), float(upper)
    left_value, right_value = float(lower_value), float(upper_value)
    best_x, best_value = (
        (left, left_value)
        if abs(left_value) <= abs(right_value)
        else (right, right_value)
    )
    for _ in range(100):
        middle = (left + right) / 2.0
        middle_value = float(function(middle))
        if abs(middle_value) < abs(best_value):
            best_x, best_value = middle, middle_value
        if abs(middle_value) <= 1e-10 or right - left <= max(1e-10, abs(middle) * 1e-10):
            return best_x, best_value, (left, right)
        if left_value * middle_value <= 0.0:
            right, right_value = middle, middle_value
        else:
            left, left_value = middle, middle_value
    return best_x, best_value, (left, right)


def _single_growth_class(growth_values: list[float], tolerance: float = 1e-12) -> bool:
    if not growth_values:
        return True
    return max(growth_values) - min(growth_values) <= tolerance


def _unsolved_growth_boundary(
    *,
    province: str,
    state: NumPyLocationState,
    start_population: float,
    start_development_mean: float,
    fixed_population: float,
    movable_population: float,
    scale_years: float,
    context: SimulationModifierContext,
    individual_rank_growth: list[float],
    population_mode: str,
    eliminated_population: float,
    status: str,
) -> ProvinceEquilibrium:
    bounded_scale = min(max(scale_years, 0.0), context.growth_cap_years)
    prosperity = prosperity_resting_point(bounded_scale, context.prosperity)
    development = development_resting_point(prosperity, context.prosperity)
    food_growth = float(context.food_growth_baselines.get("local_population_growth", 0.0))
    growth_values = [rank + food_growth * bounded_scale for rank in individual_rank_growth]
    aggregate = (
        sum(growth_values) / len(growth_values)
        if growth_values
        else 0.0
    )
    return ProvinceEquilibrium(
        province=province,
        population_mode=population_mode,
        location_count=state.n,
        starting_population=start_population,
        starting_development_mean=start_development_mean,
        fixed_population=fixed_population,
        movable_population=movable_population,
        eliminated_population=eliminated_population,
        stored_food_months=bounded_scale * MONTHS_PER_YEAR,
        stored_food_scale_years=bounded_scale,
        prosperity=prosperity,
        development=development,
        population_multiplier=None,
        population=None,
        food_production=None,
        food_consumption=None,
        food_residual=None,
        aggregate_annual_population_growth=aggregate,
        minimum_individual_annual_growth=min(growth_values, default=0.0),
        maximum_individual_annual_growth=max(growth_values, default=0.0),
        exact_positive_population_fixed_point=False,
        food_balance_locally_restoring=None,
        population_root_count=0,
        pressure_threshold_crossing_count=0,
        population_root_multipliers=(),
        pressure_threshold_multipliers=(),
        minimum_capacity_fill=None,
        maximum_capacity_fill=None,
        status=status,
    )
