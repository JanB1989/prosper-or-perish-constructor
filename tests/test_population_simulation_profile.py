from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from prosper_or_perish_constructor.simulation.capacity_model import PopulationCapacityFormula
from prosper_or_perish_constructor.simulation.profile import (
    HydeRegionTarget,
    SIMULATION_POPULATION_COLUMNS,
    _attach_population_snapshot,
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
    assert profile.population_snapshot_path == (
        ROOT / "artifacts/data/population_simulation/baseline_population.parquet"
    )
    assert profile.global_ratios[500] == pytest.approx(2.6632)
    assert profile.regional_tolerance == pytest.approx(0.25)
    assert profile.primary_scored_through_year == 200
    assert profile.rank_degrowth_exempt_pop_types == frozenset({"tribesmen"})
    assert profile.food_storage_growth_exempt_pop_types == frozenset({"tribesmen"})
    assert profile.development_manageable_cropland_column == "feasible_cultivated_fraction"
    assert profile.development_cropland_utilization_points == pytest.approx(50.0)
    assert profile.development_cropland_saturation_rate == pytest.approx(1.5)
    assert profile.development_start_max == pytest.approx(50.0)
    assert profile.min_start_development_p90 == pytest.approx(15.0)
    assert profile.max_start_development_p90 == pytest.approx(25.0)
    assert profile.max_start_development_ceiling_fraction == pytest.approx(0.005)
    assert profile.min_start_natural_capacity_share == pytest.approx(0.75)
    assert profile.max_start_development_capacity_share == pytest.approx(0.20)
    assert profile.max_global_100y_development_change == pytest.approx(2.0)
    assert profile.max_region_100y_development_change == pytest.approx(3.0)
    assert profile.capacity_formula.development_absolute == pytest.approx(0.1)
    assert profile.capacity_formula.development_relative == pytest.approx(0.02)
    assert profile.gaez_zero_development_fraction == pytest.approx(0.80)
    assert profile.gaez_zero_development_density_cap == pytest.approx(25.0)
    assert profile.hyde_rainfed_capacity_multiplier == pytest.approx(6.0)
    assert "rainfed_crop_capacity_people_p50" in profile.physical_capacity_columns
    assert len(profile.regions) == 18
    assert profile.regions[0].key == "europe"
    assert profile.regions[-1].key == "southern_cone"
    assert profile.abundant_monthly_food == pytest.approx(8.0)
    assert profile.available_monthly_food == pytest.approx(3.0)
    assert profile.min_location_capacity == pytest.approx(11.0)
    assert profile.min_irrigation_river_or_lake_fraction == pytest.approx(0.85)


def test_committed_profile_has_no_starting_population_capacity_floor() -> None:
    profile_text = (ROOT / "population_capacity_simulation.toml").read_text(
        encoding="utf-8"
    )

    assert "starting_population_floor" not in profile_text


def test_simulation_population_snapshot_replaces_only_demographics(tmp_path: Path) -> None:
    loaded = load_population_simulation_profile(
        ROOT / "population_capacity_simulation.toml",
        repo=ROOT,
    )
    snapshot_path = tmp_path / "population.parquet"
    population = {column: 0.0 for column in SIMULATION_POPULATION_COLUMNS}
    population["population_peasants"] = 7.0
    population["population_laborers"] = 3.0
    pl.DataFrame(
        [
            {
                "location_tag": "alpha",
                "total_population": 10.0,
                "unemployed_peasants": 5.0,
                **population,
            }
        ]
    ).write_parquet(snapshot_path)
    state = pl.DataFrame(
        {
            "location_tag": ["alpha"],
            "province": ["alpha_province"],
            "development": [4.0],
            "population_peasants": [99.0],
            "total_population": [99.0],
            "unemployed_peasants": [99.0],
            "food": [123.0],
        }
    )

    result, summary = _attach_population_snapshot(
        state,
        replace(loaded, population_snapshot_path=snapshot_path),
    )

    assert result.item(0, "development") == 4.0
    assert result.item(0, "population_peasants") == 7.0
    assert result.item(0, "population_laborers") == 3.0
    assert result.item(0, "total_population") == 10.0
    assert result.item(0, "unemployed_peasants") == 5.0
    assert "food" not in result.columns
    assert summary["matched_locations"] == 1


def test_population_capacity_formula_combines_all_adjustable_terms() -> None:
    formula = PopulationCapacityFormula(
        physical_scale=0.10,
        development_absolute=1.0,
        development_relative=0.03,
        irrigation_absolute=10.0,
        irrigation_relative=0.0,
        development_min=0.0,
        development_max=100.0,
        minimum_capacity=0.001,
    )

    capacity = formula.evaluate(
        base_capacity=np.array([100.0, 100.0, 0.0]),
        development=np.array([10.0, 20.0, -5.0]),
        irrigation_levels=np.array([2.0, 2.0, 0.0]),
    )

    # (10 physical + 10 dev + 20 irrigation) * (1 + .3) = 52
    # (10 physical + 20 dev + 20 irrigation) * (1 + .6) = 80
    assert capacity.tolist() == pytest.approx([52.0, 80.0, 0.001])


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
                "physical_population_capacity": [150.0],
                "gaez_zero_development_capacity": [15.0],
                "hyde_rainfed_capacity_evidence": [100.0],
                "zero_development_population_capacity": [100.0],
                "deployed_static_population_capacity": [100.0],
                "area_km2": [100.0],
                "hyde_population_people": [110_000.0],
                "hyde_cropland_area_km2": [10.0],
                "hyde_rainfed_area_km2": [9.0],
                "hyde_pasture_area_km2": [5.0],
                "hyde_urban_population_people": [10_000.0],
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
        snapshots={0: frame(100.0, 20.0), 25: frame(105.0, 21.0), 100: frame(110.0, 22.0)},
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
            "starting_development_raw": {"min": 20, "median": 20, "mean": 20, "p90": 20, "max": 20},
            "starting_development_profile": {"min": 20, "median": 20, "mean": 20, "p90": 20, "max": 20},
            "capacity_attribution": {
                "natural_share": 0.80,
                "development_share": 0.15,
                "irrigation_share": 0.05,
                "development_absolute_total": 0.1,
                "development_absolute_share": 0.001,
            },
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
