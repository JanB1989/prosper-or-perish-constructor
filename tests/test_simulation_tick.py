from __future__ import annotations

import math

import polars as pl
import pytest

from prosper_or_perish_constructor.simulation import (
    SimulationModifierContext,
    advance_tick,
    apply_population_growth,
    prepare_start_locations,
)
from prosper_or_perish_constructor.simulation.food import (
    FOOD_COLUMN,
    FOOD_CONSUMPTION_COLUMN,
    MONTHS_STORED_COLUMN,
    aggregate_province_food,
    compute_location_food_consumption,
    initialize_location_food_at_cap,
    months_of_food_at_growth_cap,
)
from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    OVERPOPULATION,
    CapacityPressureBand,
    capacity_pressure_strength,
)
from prosper_or_perish_constructor.simulation.modifiers import (
    SCALE_YEARS_COLUMN,
    SOURCE_FOOD_GROWTH,
    SOURCE_RANK,
    TRACKED_MODIFIER_KEYS,
    apply_food_growth_and_rank_modifiers,
    source_column,
)
from prosper_or_perish_constructor.simulation.population import MONTHS_PER_YEAR, monthly_growth_multiplier

from prosper_or_perish_constructor.simulation.prosperity import ProsperityBaselines


FOOD_GROWTH_BASELINES = {
    "local_population_growth": 0.01,
    "local_monthly_prosperity": 0.02,
    "local_province_food_sales_output_modifier": 0.03,
    "local_province_food_purchase_output_modifier": 0.04,
}
RANK_GROWTH = -0.005
EPHEMERAL_COLUMNS = {
    FOOD_CONSUMPTION_COLUMN,
    MONTHS_STORED_COLUMN,
    SCALE_YEARS_COLUMN,
    *TRACKED_MODIFIER_KEYS,
}


def _empty_capacity_pressure() -> dict[str, CapacityPressureBand]:
    return {
        ABUNDANT_FREE_LAND: CapacityPressureBand(ABUNDANT_FREE_LAND, {}),
        AVAILABLE_FREE_LAND: CapacityPressureBand(AVAILABLE_FREE_LAND, {}),
        OVERPOPULATION: CapacityPressureBand(OVERPOPULATION, {}),
    }


def _test_prosperity(
    *,
    base_monthly: float = 0.0,
    food_growth_monthly: float = 0.0,
    global_decay: float = 0.0,
    local_decay: float = 0.0,
    effects: dict[str, float] | None = None,
) -> ProsperityBaselines:
    return ProsperityBaselines(
        base_monthly_prosperity=base_monthly,
        food_growth_monthly_prosperity=food_growth_monthly,
        global_prosperity_decay=global_decay,
        local_prosperity_decay=local_decay,
        effects=effects or {},
    )


def _test_context(
    *,
    growth_cap_years: float = 2.0,
    subsistence_agriculture: float = 1.2,
    capacity_pressure: dict[str, CapacityPressureBand] | None = None,
    food_decay_rate: float = 0.01,
    prosperity: ProsperityBaselines | None = None,
) -> SimulationModifierContext:
    return SimulationModifierContext(
        pop_food_rates={"peasants": 1.0},
        growth_cap_years=growth_cap_years,
        food_growth_baselines=FOOD_GROWTH_BASELINES,
        rank_baselines=pl.DataFrame(
            {
                "location_rank": ["rural_settlement", "town"],
                "local_population_growth": [RANK_GROWTH, RANK_GROWTH],
                "local_monthly_prosperity": [0.0, 0.0],
                "local_province_food_sales_output_modifier": [0.0, 0.0],
                "local_province_food_purchase_output_modifier": [0.0, 0.0],
            }
        ),
        subsistence_agriculture=subsistence_agriculture,
        capacity_pressure=capacity_pressure if capacity_pressure is not None else _empty_capacity_pressure(),
        prosperity=prosperity if prosperity is not None else _test_prosperity(),
        food_decay_rate=food_decay_rate,
    )


def _province_locations(*, food: float, consumption_pops: float = 1.0) -> pl.DataFrame:
    """Two locations in one province; total monthly consumption equals ``consumption_pops``."""
    half = consumption_pops / 2.0
    return pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["prov", "prov"],
            "location_rank": ["rural_settlement", "town"],
            "food": [food / 2.0, food / 2.0],
            "population_peasants": [half, half],
            "total_population": [half, half],
        }
    )


def _assert_no_ephemeral_state(frame: pl.DataFrame) -> None:
    present = EPHEMERAL_COLUMNS.intersection(frame.columns)
    assert not present, f"ephemeral columns persisted in state: {sorted(present)}"
    assert not any(column.startswith("src__") for column in frame.columns)


def test_monthly_growth_multiplier_compounds_yearly_rate() -> None:
    assert monthly_growth_multiplier(0.0) == pytest.approx(1.0)
    assert monthly_growth_multiplier(0.02, months=12) == pytest.approx(1.02)
    assert monthly_growth_multiplier(0.02, months=1) == pytest.approx(1.02 ** (1 / 12))
    assert monthly_growth_multiplier(0.02, months=0) == pytest.approx(1.0)


def test_apply_population_growth_scales_population_columns_for_one_month() -> None:
    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "local_population_growth": [0.02, 0.0],
            "population_peasants": [100.0, 50.0],
            "population_burghers": [20.0, 10.0],
            "total_population": [120.0, 60.0],
        }
    )

    updated = apply_population_growth(locations, months=1)
    month_mult = 1.02 ** (1 / 12)

    assert updated["population_peasants"].to_list() == pytest.approx([100.0 * month_mult, 50.0])
    assert updated["population_burghers"].to_list() == pytest.approx([20.0 * month_mult, 10.0])
    assert updated["total_population"].to_list() == pytest.approx([120.0 * month_mult, 60.0])


def test_apply_population_growth_twelve_months_matches_yearly_growth() -> None:
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "local_population_growth": [0.02],
            "population_peasants": [1000.0],
            "total_population": [1000.0],
        }
    )

    updated = apply_population_growth(locations, months=12)

    assert updated["population_peasants"].item() == pytest.approx(1020.0)
    assert updated["total_population"].item() == pytest.approx(1020.0)


def test_apply_population_growth_treats_null_growth_as_zero() -> None:
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "local_population_growth": [None],
            "population_peasants": [100.0],
            "total_population": [100.0],
        }
    )

    updated = apply_population_growth(locations, months=1)

    assert updated["population_peasants"].item() == pytest.approx(100.0)
    assert math.isfinite(updated["total_population"].item())


def test_zero_food_scale_is_rank_only_growth() -> None:
    context = _test_context()
    locations = _province_locations(food=0.0, consumption_pops=2.0)
    with_consumption = compute_location_food_consumption(locations, context.pop_food_rates)

    provinces = aggregate_province_food(with_consumption)
    assert provinces[MONTHS_STORED_COLUMN].item() == pytest.approx(0.0)

    updated = apply_food_growth_and_rank_modifiers(with_consumption, context)
    assert MONTHS_STORED_COLUMN not in updated.columns
    assert SCALE_YEARS_COLUMN not in updated.columns
    assert updated["local_population_growth"].to_list() == pytest.approx([RANK_GROWTH, RANK_GROWTH])
    food_src = source_column("local_population_growth", SOURCE_FOOD_GROWTH)
    assert updated[food_src].to_list() == pytest.approx([0.0, 0.0])


def test_twelve_months_stored_adds_full_food_growth_baselines() -> None:
    context = _test_context()
    # consumption = 2.0/month → 24 food = 12 months stored → scale_years = 1
    locations = _province_locations(food=24.0, consumption_pops=2.0)
    with_consumption = compute_location_food_consumption(locations, context.pop_food_rates)

    provinces = aggregate_province_food(with_consumption)
    assert provinces[MONTHS_STORED_COLUMN].item() == pytest.approx(12.0)

    updated = apply_food_growth_and_rank_modifiers(with_consumption, context)
    expected = RANK_GROWTH + FOOD_GROWTH_BASELINES["local_population_growth"]
    assert updated["local_population_growth"].to_list() == pytest.approx([expected, expected])
    for key in TRACKED_MODIFIER_KEYS:
        food_src = source_column(key, SOURCE_FOOD_GROWTH)
        assert updated[food_src].to_list() == pytest.approx(
            [FOOD_GROWTH_BASELINES[key], FOOD_GROWTH_BASELINES[key]]
        )


def test_twenty_four_months_stored_caps_at_growth_cap_years() -> None:
    context = _test_context(growth_cap_years=2.0)
    # 48 food / 2 consumption = 24 months → scale_years capped at 2
    locations = _province_locations(food=48.0, consumption_pops=2.0)
    with_consumption = compute_location_food_consumption(locations, context.pop_food_rates)

    provinces = aggregate_province_food(with_consumption)
    assert provinces[MONTHS_STORED_COLUMN].item() == pytest.approx(24.0)

    updated = apply_food_growth_and_rank_modifiers(with_consumption, context)
    expected = RANK_GROWTH + 2.0 * FOOD_GROWTH_BASELINES["local_population_growth"]
    assert updated["local_population_growth"].to_list() == pytest.approx([expected, expected])


def test_province_food_growth_broadcasts_to_all_locations() -> None:
    context = _test_context()
    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b", "c"],
            "province": ["prov", "prov", "other"],
            "location_rank": ["rural_settlement", "town", "rural_settlement"],
            # Only a stores food; province-level months_stored still shared by a+b.
            "food": [12.0, 0.0, 0.0],
            "population_peasants": [1.0, 1.0, 1.0],
            "total_population": [1.0, 1.0, 1.0],
        }
    )

    with_consumption = compute_location_food_consumption(locations, context.pop_food_rates)
    provinces = aggregate_province_food(with_consumption)
    months_by_province = {
        row["province"]: row[MONTHS_STORED_COLUMN] for row in provinces.to_dicts()
    }
    assert months_by_province["prov"] == pytest.approx(6.0)
    assert months_by_province["other"] == pytest.approx(0.0)

    updated = apply_food_growth_and_rank_modifiers(with_consumption, context)
    food_src = source_column("local_population_growth", SOURCE_FOOD_GROWTH)
    # scale_years = 6/12 = 0.5 for both locations in prov
    shared = 0.5 * FOOD_GROWTH_BASELINES["local_population_growth"]
    by_tag = {
        row["location_tag"]: row[food_src]
        for row in updated.select("location_tag", food_src).to_dicts()
    }
    assert by_tag["a"] == pytest.approx(shared)
    assert by_tag["b"] == pytest.approx(shared)
    assert by_tag["c"] == pytest.approx(0.0)


def test_advance_tick_sums_rank_and_food_growth_into_population() -> None:
    # Match consumption rate so fully-unemployed subsistence keeps province food stable.
    # Disable decay so months_stored stays exactly at the growth cap for this assertion.
    context = _test_context(subsistence_agriculture=1.0, food_decay_rate=0.0)
    # 2400 food / 200 consumption = 12 months → full food-growth baselines.
    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["prov", "prov"],
            "location_rank": ["rural_settlement", "town"],
            "development": [1.0, 2.0],
            "prosperity": [0.0, -0.2],
            "food": [1200.0, 1200.0],
            "population_peasants": [100.0, 100.0],
            "total_population": [100.0, 100.0],
            "unemployed_peasants": [100.0, 100.0],
        }
    )

    updated = advance_tick(locations, context, months=1)
    _assert_no_ephemeral_state(updated)
    assert updated.columns == sorted(updated.columns)
    assert "development" in updated.columns
    assert "prosperity" in updated.columns
    yearly = RANK_GROWTH + FOOD_GROWTH_BASELINES["local_population_growth"]
    month_mult = (1.0 + yearly) ** (1 / 12)
    assert updated["population_peasants"].to_list() == pytest.approx(
        [100.0 * month_mult, 100.0 * month_mult]
    )
    assert updated["food"].sum() == pytest.approx(2400.0)
    assert updated["development"].to_list() == pytest.approx([1.0, 2.0])
    # Devastation ignored for now: negative prosperity is clamped to 0.
    assert updated["prosperity"].to_list() == pytest.approx([0.0, 0.0])


def test_advance_tick_applies_food_growth_prosperity_income_and_decay() -> None:
    # Full food scale (12 months stored) → food_growth monthly prosperity 0.0025.
    # income points = 0.0025 * 100 = 0.25; then 1% global decay → 0.25 * 0.99.
    context = _test_context(
        subsistence_agriculture=1.0,
        food_decay_rate=0.0,
        prosperity=_test_prosperity(
            food_growth_monthly=0.0025,
            global_decay=0.01,
        ),
    )
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [2400.0],
            "population_peasants": [200.0],
            "total_population": [200.0],
            "unemployed_peasants": [200.0],
            "prosperity": [0.0],
            "development": [10.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    assert updated["prosperity"].item() == pytest.approx(0.25 * 0.99)


def test_advance_tick_applies_prosperity_food_consumption_and_development() -> None:
    # At prosperity 100 → scale 1.0: +0.5 peasant food cons, +0.005 monthly dev * (1+0.25).
    context = _test_context(
        subsistence_agriculture=0.0,
        food_decay_rate=0.0,
        prosperity=_test_prosperity(
            effects={
                "local_peasants_food_consumption": 0.5,
                "local_monthly_development": 0.005,
                "local_monthly_development_modifier": 0.25,
                "local_population_growth": 0.0,
            },
        ),
    )
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [100.0],
            "population_peasants": [10.0],
            "total_population": [10.0],
            "unemployed_peasants": [0.0],
            "prosperity": [100.0],
            "development": [10.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    # cons = 10 * 1.0 * (1+0.5) = 15 → food 100-15=85; prosperity decays 0 in this fixture.
    assert updated["food"].item() == pytest.approx(85.0)
    assert updated["development"].item() == pytest.approx(10.0 + 0.005 * 1.25)


def test_prepare_start_locations_fills_food_at_define_cap() -> None:
    context = _test_context(growth_cap_years=2.0)
    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["prov", "prov"],
            "location_rank": ["rural_settlement", "town"],
            "development": [5.0, 8.0],
            "prosperity": [0.1, 0.0],
            "population_peasants": [10.0, 30.0],
            "total_population": [10.0, 30.0],
            "local_population_growth": [0.99, 0.99],  # must not persist
        }
    )

    prepared = prepare_start_locations(locations, context)
    _assert_no_ephemeral_state(prepared)
    assert prepared.columns == sorted(prepared.columns)
    months_at_cap = months_of_food_at_growth_cap(growth_cap_years=2.0)
    assert months_at_cap == pytest.approx(24.0)
    assert prepared[FOOD_COLUMN].to_list() == pytest.approx([10.0 * months_at_cap, 30.0 * months_at_cap])
    assert prepared["development"].to_list() == pytest.approx([5.0, 8.0])
    assert prepared["prosperity"].to_list() == pytest.approx([0.1, 0.0])

    with_consumption = compute_location_food_consumption(prepared, context.pop_food_rates)
    provinces = aggregate_province_food(with_consumption)
    assert provinces[MONTHS_STORED_COLUMN].item() == pytest.approx(months_at_cap)

    scaled = apply_food_growth_and_rank_modifiers(with_consumption, context)
    expected = RANK_GROWTH + 2.0 * FOOD_GROWTH_BASELINES["local_population_growth"]
    assert scaled["local_population_growth"].to_list() == pytest.approx([expected, expected])


def test_initialize_location_food_at_cap_uses_growth_cap_years() -> None:
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            FOOD_CONSUMPTION_COLUMN: [5.0],
        }
    )
    filled = initialize_location_food_at_cap(locations, growth_cap_years=1.5)
    assert filled[FOOD_COLUMN].item() == pytest.approx(5.0 * 1.5 * MONTHS_PER_YEAR)


def test_food_consumption_applies_per_pop_local_modifier() -> None:
    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["prov", "prov"],
            "population_peasants": [100.0, 100.0],
            "population_burghers": [10.0, 10.0],
            "local_peasants_food_consumption": [0.5, -0.25],
            "local_burghers_food_consumption": [None, 1.0],
        }
    )
    updated = compute_location_food_consumption(
        locations,
        {"peasants": 2.0, "burghers": 4.0},
    )
    # a: 100*2*(1.5) + 10*4*(1.0) = 300 + 40 = 340
    # b: 100*2*(0.75) + 10*4*(2.0) = 150 + 80 = 230
    assert updated[FOOD_CONSUMPTION_COLUMN].to_list() == pytest.approx([340.0, 230.0])


def test_food_consumption_floors_effective_rate_at_zero() -> None:
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "population_peasants": [100.0],
            "local_peasants_food_consumption": [-2.0],
        }
    )
    updated = compute_location_food_consumption(locations, {"peasants": 1.0})
    assert updated[FOOD_CONSUMPTION_COLUMN].item() == pytest.approx(0.0)


def test_attach_peasant_employment_fills_jobs_first() -> None:
    from prosper_or_perish_constructor.simulation.food import attach_peasant_employment_state

    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "population_peasants": [100.0, 40.0],
            "unemployed_peasants": [30.0, 10.0],
        }
    )
    updated = attach_peasant_employment_state(locations)
    assert updated["peasant_employment"].to_list() == pytest.approx([70.0, 30.0])
    assert updated["employed_peasants"].to_list() == pytest.approx([70.0, 30.0])
    assert updated["unemployed_peasants"].to_list() == pytest.approx([30.0, 10.0])


def test_advance_tick_updates_province_food_by_production_minus_consumption() -> None:
    context = _test_context(subsistence_agriculture=1.2, food_decay_rate=0.0)
    # Fully unemployed peasants: production = 100 * 1.2 = 120, consumption = 100 * 1.0 = 100
    # net +20 on the province stock.
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [50.0],
            "population_peasants": [100.0],
            "total_population": [100.0],
            "unemployed_peasants": [100.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    assert updated["food"].item() == pytest.approx(70.0)
    assert updated["peasant_employment"].item() == pytest.approx(0.0)
    assert updated["unemployed_peasants"].item() == pytest.approx(
        updated["population_peasants"].item()
    )


def test_advance_tick_applies_food_decay_to_stored_food() -> None:
    # Balanced prod/cons, then 1% decay on remaining stock.
    context = _test_context(subsistence_agriculture=1.0, food_decay_rate=0.01)
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [100.0],
            "population_peasants": [10.0],
            "total_population": [10.0],
            "unemployed_peasants": [10.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    assert updated["food"].item() == pytest.approx(99.0)


def test_advance_tick_floors_province_food_at_zero() -> None:
    context = _test_context(subsistence_agriculture=0.0)
    locations = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["prov", "prov"],
            "location_rank": ["rural_settlement", "rural_settlement"],
            "food": [5.0, 5.0],
            "population_peasants": [100.0, 100.0],
            "total_population": [100.0, 100.0],
            "unemployed_peasants": [0.0, 0.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    assert updated["food"].sum() == pytest.approx(0.0)


def test_advance_tick_rebalances_unemployed_after_growth() -> None:
    context = _test_context(subsistence_agriculture=0.0)
    # Zero food-growth (no food) and rank growth RANK_GROWTH so pop shrinks.
    # Start with 100 peasants, 60 jobs → 40 unemployed. After shrink, fill jobs first.
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [0.0],
            "population_peasants": [100.0],
            "total_population": [100.0],
            "unemployed_peasants": [40.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    peasants = updated["population_peasants"].item()
    assert updated["peasant_employment"].item() == pytest.approx(60.0)
    assert updated["employed_peasants"].item() == pytest.approx(min(peasants, 60.0))
    assert updated["unemployed_peasants"].item() == pytest.approx(max(peasants - 60.0, 0.0))
    # Employment capacity stays fixed while total peasants shrink under negative rank growth.
    assert peasants < 100.0


def test_capacity_pressure_strength_bands_are_exclusive() -> None:
    name, strength = capacity_pressure_strength(5.0, 100.0)
    assert name == ABUNDANT_FREE_LAND
    assert strength == pytest.approx(0.95)
    # Below 10% fill but at/above 10 pop → no abundant band.
    assert capacity_pressure_strength(10.0, 200.0) == (None, 0.0)
    name, strength = capacity_pressure_strength(50.0, 100.0)
    assert name == AVAILABLE_FREE_LAND
    assert strength == pytest.approx(0.5)
    name, strength = capacity_pressure_strength(100.0, 100.0)
    assert name == AVAILABLE_FREE_LAND
    assert strength == pytest.approx(0.0)
    name, strength = capacity_pressure_strength(200.0, 100.0)
    assert name == OVERPOPULATION
    assert strength == pytest.approx(1.0)
    name, strength = capacity_pressure_strength(300.0, 100.0)
    assert name == OVERPOPULATION
    assert strength == pytest.approx(2.0)


def test_advance_tick_applies_available_free_land_monthly_food_and_consumption() -> None:
    # fill = 50/100 = 0.5 → available, strength = 0.5
    # monthly food = 4 * 0.5 = 2
    # peasants food cons mod = -0.3 * 0.5 = -0.15 → effective rate 0.85
    # unemployed = 50, subsistence 0 → production = 2
    # consumption = 50 * 0.85 = 42.5
    # food: 100 + 2 - 42.5 = 59.5
    capacity_pressure = {
        ABUNDANT_FREE_LAND: CapacityPressureBand(
            ABUNDANT_FREE_LAND,
            {"local_monthly_food": 8.0, "local_peasants_food_consumption": -0.6},
        ),
        AVAILABLE_FREE_LAND: CapacityPressureBand(
            AVAILABLE_FREE_LAND,
            {"local_monthly_food": 4.0, "local_peasants_food_consumption": -0.3},
        ),
        OVERPOPULATION: CapacityPressureBand(
            OVERPOPULATION,
            {"local_peasants_food_consumption": 0.05, "local_population_growth": -0.0015},
        ),
    }
    context = _test_context(
        subsistence_agriculture=0.0,
        capacity_pressure=capacity_pressure,
        food_decay_rate=0.0,
    )
    # Neutralize rank/food-growth so food math is isolated (0 stored months → rank only,
    # but we only assert food which is applied before growth).
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [100.0],
            "population_peasants": [50.0],
            "total_population": [50.0],
            "unemployed_peasants": [50.0],
            "local_population_capacity": [100.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    assert updated["food"].item() == pytest.approx(59.5)


def test_advance_tick_applies_overpopulation_food_consumption() -> None:
    # fill = 2.0 → overpopulation strength 1.0 → +0.05 peasants food consumption
    # rate 1.05, pop 200, cons = 210, production = 0, food 50 → 0
    capacity_pressure = {
        ABUNDANT_FREE_LAND: CapacityPressureBand(ABUNDANT_FREE_LAND, {}),
        AVAILABLE_FREE_LAND: CapacityPressureBand(AVAILABLE_FREE_LAND, {}),
        OVERPOPULATION: CapacityPressureBand(
            OVERPOPULATION,
            {"local_peasants_food_consumption": 0.05},
        ),
    }
    context = _test_context(subsistence_agriculture=0.0, capacity_pressure=capacity_pressure)
    locations = pl.DataFrame(
        {
            "location_tag": ["a"],
            "province": ["prov"],
            "location_rank": ["rural_settlement"],
            "food": [50.0],
            "population_peasants": [200.0],
            "total_population": [200.0],
            "unemployed_peasants": [0.0],
            "local_population_capacity": [100.0],
        }
    )
    updated = advance_tick(locations, context, months=1)
    assert updated["food"].item() == pytest.approx(0.0)

