from __future__ import annotations

from pathlib import Path

import polars as pl

from prosper_or_perish_constructor import cli
from prosper_or_perish_constructor.simulation.calibration_optimizer import (
    CONSTRAINT_NAMES,
    evaluate_static_candidate,
    load_calibration_config,
    physical_regime_training_data,
    solve_infrastructure_effects,
)
from prosper_or_perish_constructor.simulation.capacity_model import (
    PHYSICAL_POPULATION_CAPACITY_COLUMN,
    ZERO_DEVELOPMENT_CAPACITY_COLUMN,
)
from prosper_or_perish_constructor.simulation.profile import (
    load_population_simulation_profile,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "population_capacity_simulation.toml"


def test_population_calibration_command_is_registered() -> None:
    args, extra = cli._build_parser().parse_known_args(
        ["population-calibration", "--trials", "12", "--static-only"]
    )

    assert extra == []
    assert args.handler is cli._population_calibration
    assert args.trials == 12
    assert args.static_only is True


def test_calibration_search_space_uses_typed_profile_overrides() -> None:
    config = load_calibration_config(PROFILE, repo=ROOT)

    assert config.algorithm == "regime_tree_lp"
    assert config.startup_trials == 64
    assert config.search_space["capacity.location_area_exponent"].kind == "float"
    assert config.search_space["infrastructure.max_levels.farming_village"].kind == "int"
    assert config.regime_min_samples_leaf == 7
    assert config.regime_max_leaf_nodes == 2310
    assert config.global_capacity_safety_margin_people == 10_000_000
    assert config.minimum_infrastructure_share == 0.35
    assert "cropland_fraction_1300" in config.regime_features
    assert "irrigation.river_level_fraction" in config.search_space


def test_every_ordinary_location_is_part_of_the_hard_fill_constraint() -> None:
    profile = load_population_simulation_profile(PROFILE, repo=ROOT)
    state = pl.DataFrame(
        {
            "location_tag": ["dense", "suzhou", "cairo"],
            "province": ["ordinary_province", "suzhou_province", "cairo_province"],
            "total_population": [116.0, 10.0, 10.0],
            "local_population_capacity": [100.0, 200.0, 190.0],
            ZERO_DEVELOPMENT_CAPACITY_COLUMN: [100.0, 200.0, 190.0],
            "development": [0.0, 0.0, 0.0],
        }
    )

    _loss, metrics, constraints = evaluate_static_candidate(state, profile)

    assert len(constraints) == len(CONSTRAINT_NAMES) - 4
    assert metrics["maximum_ordinary_fill"] == 1.16
    assert metrics["overfilled_locations"] == 1
    assert constraints[0] > 0


def test_static_fill_constraint_passes_only_when_all_locations_pass() -> None:
    profile = load_population_simulation_profile(PROFILE, repo=ROOT)
    state = pl.DataFrame(
        {
            "location_tag": ["ordinary", "suzhou", "cairo"],
            "province": ["ordinary_province", "suzhou_province", "cairo_province"],
            "total_population": [115.0, 10.0, 10.0],
            "local_population_capacity": [100.0, 200.0, 190.0],
            ZERO_DEVELOPMENT_CAPACITY_COLUMN: [100.0, 200.0, 190.0],
            "development": [0.0, 0.0, 0.0],
        }
    )

    _loss, metrics, constraints = evaluate_static_candidate(state, profile)

    assert metrics["overfilled_locations"] == 0
    assert constraints[0] <= 0


def test_starting_population_cannot_change_ml_regimes() -> None:
    state = pl.DataFrame(
        {
            "physical_feature": [1.0, 4.0],
            PHYSICAL_POPULATION_CAPACITY_COLUMN: [20.0, 80.0],
            "total_population": [10.0, 1000.0],
        }
    )
    changed_population = state.with_columns(
        (pl.col("total_population") * 100).alias("total_population")
    )

    features, target = physical_regime_training_data(state, ["physical_feature"])
    changed_features, changed_target = physical_regime_training_data(
        changed_population, ["physical_feature"]
    )

    assert (features == changed_features).all()
    assert (target == changed_target).all()


def test_inner_solver_selects_building_effects_for_the_hard_fill_boundary() -> None:
    profile = load_population_simulation_profile(PROFILE, repo=ROOT)
    config = load_calibration_config(PROFILE, repo=ROOT)
    levels = {
        f"infrastructure_{building}_levels": [1.0 if building == "irrigation_systems" else 0.0]
        for building in profile.infrastructure_capacity_per_level
    }
    state = pl.DataFrame(
        {
            "location_tag": ["river_location"],
            "province": ["ordinary_province"],
            "total_population": [100.0],
            "base_population_capacity": [10.0],
            "local_population_capacity": [10.0],
            "infrastructure_population_capacity": [0.0],
            "development": [0.0],
            **levels,
        }
    )

    solved, effects, metrics = solve_infrastructure_effects(
        state, profile, config.search_space
    )

    assert metrics["inner_maximum_relative_shortfall"] == 0
    assert metrics["inner_global_overflow"] == 0
    assert solved["local_population_capacity"].item() >= 100 / 1.15
    assert effects["infrastructure.capacity_per_level.irrigation_systems"] > 70
