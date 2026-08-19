from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from prosper_or_perish_constructor.simulation.capacity_model import PopulationCapacityFormula
from prosper_or_perish_constructor.simulation.profile import (
    HydeRegionTarget,
    _snapshot,
    build_population_simulation_report,
    load_population_simulation_profile,
)

ROOT = Path(__file__).resolve().parents[1]


def test_committed_population_simulation_profile_loads() -> None:
    profile = load_population_simulation_profile(
        ROOT / "population_capacity_simulation.toml",
        repo=ROOT,
    )

    assert profile.checkpoint_years == (0, 25, 100, 200, 300, 400, 500)
    assert profile.global_ratios[500] == pytest.approx(2.6632)
    assert profile.regional_tolerance == pytest.approx(0.25)
    assert profile.primary_scored_through_year == 200
    assert profile.rank_degrowth_exempt_pop_types == frozenset({"tribesmen"})
    assert profile.food_storage_growth_exempt_pop_types == frozenset({"tribesmen"})
    assert profile.development_region_start_offsets == {
        "central_asia": -4.0,
        "south_asia": 4.0,
        "east_asia": -3.0,
        "southeast_asia": -3.0,
    }
    assert len(profile.regions) == 18
    assert profile.regions[0].key == "europe"
    assert profile.regions[-1].key == "southern_cone"
    assert profile.abundant_monthly_food == pytest.approx(8.0)
    assert profile.available_monthly_food == pytest.approx(4.0)
    assert profile.min_location_capacity == pytest.approx(0.001)
    assert profile.min_irrigation_river_or_lake_fraction == pytest.approx(0.85)


def test_population_capacity_formula_combines_all_adjustable_terms() -> None:
    formula = PopulationCapacityFormula(
        physical_scale=0.10,
        development_absolute=1.0,
        development_relative=0.03,
        irrigation_absolute=10.0,
        irrigation_relative=0.0,
        development_min=0.0,
        development_max=100.0,
    )

    capacity = formula.evaluate(
        base_capacity=np.array([100.0, 100.0, 0.0]),
        development=np.array([10.0, 20.0, -5.0]),
        irrigation_levels=np.array([2.0, 2.0, 0.0]),
        starting_floor=np.array([50.0, 50.0, 12.5]),
    )

    # (10 physical + 10 dev + 20 irrigation) * (1 + .3) = 52
    # (10 physical + 20 dev + 20 irrigation) * (1 + .6) = 80
    assert capacity.tolist() == pytest.approx([52.0, 80.0, 12.5])


def test_simulation_checkpoint_does_not_share_mutable_numpy_memory() -> None:
    population = np.array([100.0])
    checkpoint = _snapshot(
        pl.DataFrame(
            {
                "location_tag": ["alpha"],
                "total_population": population,
            }
        )
    )

    population[0] = 200.0

    assert checkpoint["total_population"].to_list() == [100.0]


def test_population_simulation_report_contains_targets_and_location_sanity() -> None:
    loaded = load_population_simulation_profile(
        ROOT / "population_capacity_simulation.toml",
        repo=ROOT,
    )
    europe = HydeRegionTarget(
        region_id=1,
        key="europe",
        label="Europe",
        ratios={100: 1.10},
        excluded_years=frozenset(),
    )
    profile = replace(
        loaded,
        checkpoint_years=(0, 25, 100),
        global_ratios={0: 1.0, 100: 1.10},
        global_excluded_years=frozenset(),
        regions=(europe,),
        max_location_population=1_000.0,
        max_location_capacity_fill=2.0,
    )

    def frame(population: float, development: float) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "location_tag": ["alpha"],
                "province": ["alpha_province"],
                "macro_region": ["western_europe"],
                "hyde_region": ["europe"],
                "location_rank": ["rural_settlement"],
                "total_population": [population],
                "local_population_capacity": [200.0],
                "development": [development],
                "prosperity": [10.0],
                "profile_start_population": [100.0],
                "profile_start_development": [10.0],
                "base_population_capacity": [100.0],
                "starting_population_capacity_floor": [125.0],
                "irrigation_systems_levels": [1.0],
                "irrigation_systems_legal_cap": [2.0],
                "hyde_irrigated_area_km2": [10.0],
                "river_level": [1],
                "has_river": [True],
                "is_adjacent_to_lake": [False],
            }
        )

    report, passed = build_population_simulation_report(
        profile=profile,
        snapshots={0: frame(100.0, 10.0), 25: frame(105.0, 11.0), 100: frame(110.0, 12.0)},
        preparation={
            "locations": 1,
            "irrigation": {
                "enabled": True,
                "locations": 1,
                "levels": 1,
                "river_or_lake_location_fraction": 1.0,
                "river_supported_level_fraction": 1.0,
                "cap_violations": 0,
            },
            "starting_development_raw": {"min": 10, "median": 10, "mean": 10, "p90": 10, "max": 10},
            "starting_development_profile": {"min": 10, "median": 10, "mean": 10, "p90": 10, "max": 10},
        },
        elapsed_seconds=0.1,
    )

    assert passed is True
    assert "## Global checkpoints" in report
    assert "## HYDE regional benchmarks" in report
    assert "## HYDE region starting composition" in report
    assert "## Location sanity checks" in report
    assert "## Location ranges by checkpoint" in report
    assert "## Capacity-pressure coverage" in report
    assert "### Highest capacity fill at 100 years" in report
