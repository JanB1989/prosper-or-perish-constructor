from __future__ import annotations

import polars as pl
import pytest

from prosper_or_perish_constructor.simulation import Simulation, SimulationModifierContext
from prosper_or_perish_constructor.simulation.capacity_pressure import (
    ABUNDANT_FREE_LAND,
    AVAILABLE_FREE_LAND,
    OVERPOPULATION,
    CapacityPressureBand,
)
from prosper_or_perish_constructor.simulation.prosperity import ProsperityBaselines
from prosper_or_perish_constructor.simulation.trackers import list_trackers, require_tracker


def _empty_capacity_pressure() -> dict[str, CapacityPressureBand]:
    return {
        ABUNDANT_FREE_LAND: CapacityPressureBand(ABUNDANT_FREE_LAND, {}),
        AVAILABLE_FREE_LAND: CapacityPressureBand(AVAILABLE_FREE_LAND, {}),
        OVERPOPULATION: CapacityPressureBand(OVERPOPULATION, {}),
    }


def _empty_prosperity() -> ProsperityBaselines:
    return ProsperityBaselines(
        base_monthly_prosperity=0.0,
        food_growth_monthly_prosperity=0.0,
        global_prosperity_decay=0.0,
        local_prosperity_decay=0.0,
        effects={},
    )


def _context() -> SimulationModifierContext:
    return SimulationModifierContext(
        pop_food_rates={"peasants": 1.0},
        growth_cap_years=2.0,
        food_growth_baselines={
            "local_population_growth": 0.0,
            "local_monthly_prosperity": 0.0,
            "local_province_food_sales_output_modifier": 0.0,
            "local_province_food_purchase_output_modifier": 0.0,
        },
        rank_baselines=pl.DataFrame(
            {
                "location_rank": ["rural_settlement"],
                "local_population_growth": [0.0],
                "local_monthly_prosperity": [0.0],
                "local_province_food_sales_output_modifier": [0.0],
                "local_province_food_purchase_output_modifier": [0.0],
            }
        ),
        subsistence_agriculture=0.0,
        capacity_pressure=_empty_capacity_pressure(),
        prosperity=_empty_prosperity(),
        food_decay_rate=0.0,
    )


def _two_province_state() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "location_tag": ["a", "b", "c"],
            "province": ["north", "north", "south"],
            "location_rank": ["rural_settlement"] * 3,
            "food": [10.0, 20.0, 5.0],
            "population_peasants": [100.0, 50.0, 25.0],
            "total_population": [100.0, 50.0, 25.0],
            "development": [10.0, 30.0, 50.0],
            "prosperity": [20.0, -10.0, 0.0],
            "local_population_capacity": [100.0, 200.0, 40.0],
        }
    )


def test_list_trackers_includes_province_total_population() -> None:
    assert "province_total_population" in list_trackers()


def test_unknown_tracker_raises() -> None:
    with pytest.raises(KeyError, match="unknown tracker"):
        require_tracker("not_a_real_tracker")


def test_run_without_track_keeps_history_empty_and_skips_work() -> None:
    sim = Simulation(_two_province_state(), _context())
    sim.run(months=3, progress=False)
    assert sim.tracked == ()
    assert dict(sim.history) == {}
    assert sim.tick == 3


def test_track_province_total_population_records_tick_zero_and_monthly() -> None:
    sim = Simulation(_two_province_state(), _context())
    sim.track("province_total_population")
    sim.run(months=2, progress=False)

    hist = sim.history["province_total_population"]
    assert hist.columns == ["tick", "province", "value"]
    assert set(hist["tick"].to_list()) == {0, 1, 2}

    by_tick_province = {
        (row["tick"], row["province"]): row["value"] for row in hist.to_dicts()
    }
    assert by_tick_province[(0, "north")] == pytest.approx(150.0)
    assert by_tick_province[(0, "south")] == pytest.approx(25.0)
    # Growth rate 0 in this fixture → population unchanged across ticks.
    assert by_tick_province[(2, "north")] == pytest.approx(150.0)


def test_history_value_column_is_always_named_value() -> None:
    sim = Simulation(_two_province_state(), _context())
    sim.track("location_food").run(months=1, progress=False)
    hist = sim.history["location_food"]
    assert "value" in hist.columns
    assert "location_food" not in hist.columns
    assert hist.filter(pl.col("tick") == 0).sort("location_tag")["value"].to_list() == pytest.approx(
        [10.0, 20.0, 5.0]
    )


def test_track_is_idempotent() -> None:
    sim = Simulation(_two_province_state(), _context())
    sim.track("province_food").track("province_food")
    assert sim.tracked == ("province_food",)


def test_track_province_capacity_development_and_prosperity() -> None:
    sim = Simulation(_two_province_state(), _context())
    (
        sim.track("province_average_capacity_fill")
        .track("province_average_development")
        .track("province_average_prosperity")
        .run(months=0, progress=False)
    )

    fill = {
        row["province"]: row["value"]
        for row in sim.history["province_average_capacity_fill"].to_dicts()
    }
    development = {
        row["province"]: row["value"]
        for row in sim.history["province_average_development"].to_dicts()
    }
    prosperity = {
        row["province"]: row["value"]
        for row in sim.history["province_average_prosperity"].to_dicts()
    }

    # north: mean(100/100, 50/200) * 100 = mean(100%, 25%) = 62.5%
    # south: 25/40 * 100 = 62.5%
    assert fill["north"] == pytest.approx(62.5)
    assert fill["south"] == pytest.approx(62.5)
    assert development["north"] == pytest.approx(20.0)  # (10 + 30) / 2
    assert development["south"] == pytest.approx(50.0)
    # Prosperity state is a single signed value: >0 prosperity, <0 devastation.
    assert prosperity["north"] == pytest.approx(5.0)  # (20 + -10) / 2
    assert prosperity["south"] == pytest.approx(0.0)
