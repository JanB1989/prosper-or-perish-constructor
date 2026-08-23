from __future__ import annotations

from dataclasses import replace

import polars as pl
import pytest

from prosper_or_perish_constructor.simulation.capacity_model import (
    PopulationCapacityFormula,
)
from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    OVERPOPULATION,
    CapacityPressureBand,
)
from prosper_or_perish_constructor.simulation.equilibrium import (
    development_resting_point,
    prosperity_resting_point,
    solve_province_equilibrium,
)
from prosper_or_perish_constructor.simulation.modifiers import (
    SimulationModifierContext,
)
from prosper_or_perish_constructor.simulation.prosperity import (
    ProsperityBaselines,
)
from prosper_or_perish_constructor.simulation.tick import advance_tick


def _context() -> SimulationModifierContext:
    prosperity = ProsperityBaselines(
        base_monthly_prosperity=0.0025,
        food_growth_monthly_prosperity=0.0025,
        global_prosperity_decay=0.01,
        local_prosperity_decay=0.005,
        effects={
            "local_monthly_development": 0.005,
            "local_monthly_development_modifier": 0.25,
            "local_population_growth": 0.0,
            "local_peasants_food_consumption": 0.5,
        },
        development_monthly_per_point=-0.00011,
    )
    return SimulationModifierContext(
        pop_food_rates={"peasants": 1.0},
        growth_cap_years=2.0,
        food_growth_baselines={
            "local_population_growth": 0.0075,
            "local_monthly_prosperity": 0.0025,
        },
        rank_baselines=pl.DataFrame(
            {
                "location_rank": ["rural_settlement"],
                "local_population_growth": [-0.004],
            }
        ),
        subsistence_agriculture=1.0,
        capacity_pressure={
            ABUNDANT_FREE_LAND: CapacityPressureBand(
                ABUNDANT_FREE_LAND,
                {
                    "local_monthly_food": 8.0,
                    "local_peasants_food_consumption": -0.5,
                    "local_population_growth": 0.0,
                },
            ),
            AVAILABLE_FREE_LAND: CapacityPressureBand(
                AVAILABLE_FREE_LAND,
                {
                    "local_monthly_food": 3.0,
                    "local_peasants_food_consumption": -0.32,
                    "local_population_growth": 0.0,
                },
            ),
            OVERPOPULATION: CapacityPressureBand(
                OVERPOPULATION,
                {
                    "local_monthly_food": 0.0,
                    "local_peasants_food_consumption": 1.0,
                },
            ),
        },
        prosperity=prosperity,
        food_decay_rate=0.01,
        capacity_model=PopulationCapacityFormula(
            development_relative=0.00125,
            minimum_capacity=0.0,
        ),
    )


def _location() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "location_tag": ["alpha"],
            "province": ["alpha_province"],
            "location_rank": ["rural_settlement"],
            "population_peasants": [100.0],
            "total_population": [100.0],
            "peasant_employment": [0.0],
            "base_population_capacity": [100.0],
            "irrigation_systems_levels": [0.0],
            "development": [10.0],
            "prosperity": [0.0],
        }
    )


def test_closed_form_prosperity_and_development_are_monthly_fixed_points() -> None:
    context = _context()
    scale_years = 0.004 / 0.0075
    prosperity = prosperity_resting_point(scale_years, context.prosperity)
    development = development_resting_point(prosperity, context.prosperity)

    income = 100.0 * (0.0025 + 0.0025 * scale_years)
    prosperity_next = (prosperity + income) * (
        1.0 - 0.01 - 0.005 * prosperity / 100.0
    )
    prosperity_scale = prosperity / 100.0
    development_next = development + (
        prosperity_scale * 0.005 - development * 0.00011
    ) * (1.0 + prosperity_scale * 0.25)

    assert prosperity_next == pytest.approx(prosperity)
    assert development_next == pytest.approx(development)


def test_single_rank_algebraic_equilibrium_is_an_exact_simulator_fixed_point() -> None:
    context = _context()
    prediction = solve_province_equilibrium(_location(), context)

    assert prediction.status == "solved"
    assert prediction.exact_positive_population_fixed_point is True
    assert prediction.population_multiplier is not None
    assert prediction.food_consumption is not None
    assert prediction.food_residual == pytest.approx(0.0, abs=1e-7)
    assert prediction.stored_food_months == pytest.approx(6.4)

    population = 100.0 * prediction.population_multiplier
    # Stored months are read after production-consumption and before spoilage.
    # The persisted pre-tick stock is therefore (1-decay) * H * consumption.
    persisted_food = (
        (1.0 - context.food_decay_rate)
        * prediction.stored_food_months
        * prediction.food_consumption
    )
    equilibrium_state = _location().with_columns(
        pl.lit(population).alias("population_peasants"),
        pl.lit(population).alias("total_population"),
        pl.lit(prediction.prosperity).alias("prosperity"),
        pl.lit(prediction.development).alias("development"),
        pl.lit(persisted_food).alias("food"),
    )

    after = advance_tick(equilibrium_state, context, months=1)

    assert after["total_population"].item() == pytest.approx(population, rel=1e-10)
    assert after["development"].item() == pytest.approx(prediction.development, rel=1e-10)
    assert after["prosperity"].item() == pytest.approx(prediction.prosperity, rel=1e-10)
    assert after["food"].item() == pytest.approx(persisted_food, rel=1e-9)


def test_mixed_rank_province_is_reported_as_aggregate_quasi_equilibrium() -> None:
    context = _context()
    context = replace(
        context,
        rank_baselines=pl.DataFrame(
            {
                "location_rank": ["rural_settlement", "town"],
                "local_population_growth": [-0.004, -0.005],
            }
        ),
    )
    locations = pl.concat(
        [
            _location(),
            _location().with_columns(
                pl.lit("beta").alias("location_tag"),
                pl.lit("town").alias("location_rank"),
            ),
        ]
    )

    prediction = solve_province_equilibrium(locations, context)

    assert prediction.status == "solved"
    assert prediction.exact_positive_population_fixed_point is False
    assert prediction.aggregate_annual_population_growth == pytest.approx(0.0)
    assert prediction.minimum_individual_annual_growth < 0.0
    assert prediction.maximum_individual_annual_growth > 0.0

    asymptotic = solve_province_equilibrium(
        locations,
        context,
        population_mode="asymptotic",
    )
    assert asymptotic.exact_positive_population_fixed_point is True
    assert asymptotic.eliminated_population == pytest.approx(100.0)
    assert asymptotic.stored_food_months == pytest.approx(6.4)
    assert asymptotic.minimum_individual_annual_growth == pytest.approx(0.0)
    assert asymptotic.maximum_individual_annual_growth == pytest.approx(0.0)
