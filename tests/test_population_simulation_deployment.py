from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor.simulation.capacity_model import (
    IRRIGATION_LEVELS_COLUMN,
    ZERO_DEVELOPMENT_CAPACITY_COLUMN,
)
from prosper_or_perish_constructor.simulation.deployment import (
    _compile_development_setup_rows,
    _render_capacity_csv,
    _render_development_setup,
    _render_irrigation_setup,
)
from prosper_or_perish_constructor.simulation.profile import (
    _attach_deployed_base_capacity,
    load_population_simulation_profile,
)
from prosper_or_perish_population_capacity.merge import load_collection, profile_from


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_profile_paths_are_constructor_owned() -> None:
    profile = load_population_simulation_profile(
        ROOT / "population_capacity_simulation.toml",
        repo=ROOT,
    )

    assert profile.deployment_population_capacity_table_path == (
        ROOT / "data/population_capacity/population_capacity.csv"
    )
    assert profile.deployment_development_setup_path.name == "14_development.txt"
    assert profile.deployment_irrigation_setup_path.name == (
        "14_pp_population_irrigation.txt"
    )
    assert profile.deployment_development_decimals == 2


def test_deployed_integer_base_preserves_minimum_and_dynamic_development() -> None:
    profile = load_population_simulation_profile(
        ROOT / "population_capacity_simulation.toml",
        repo=ROOT,
    )
    state = pl.DataFrame(
        {
            ZERO_DEVELOPMENT_CAPACITY_COLUMN: [0.0, 0.0],
            "development": [0.0, 100.0],
            IRRIGATION_LEVELS_COLUMN: [0.0, 0.0],
        }
    )

    deployed = _attach_deployed_base_capacity(state, profile)

    assert deployed["deployed_static_population_capacity"].to_list() == [11.0, 0.0]
    final_capacity = profile.capacity_formula.evaluate(
        base_capacity=deployed["base_population_capacity"].to_numpy(),
        development=deployed["development"].to_numpy(),
        irrigation_levels=deployed[IRRIGATION_LEVELS_COLUMN].to_numpy(),
    )
    assert final_capacity.tolist() == [11.0, 30.0]


def test_deployment_renderers_emit_parser_valid_game_data(tmp_path: Path) -> None:
    capacity_text = _render_capacity_csv(
        [
            {"location_tag": "alpha", "population_capacity": 9},
            {"location_tag": "bravo", "population_capacity": 12},
        ]
    )
    assert list(csv.DictReader(StringIO(capacity_text))) == [
        {"location_tag": "alpha", "population_capacity": "9"},
        {"location_tag": "bravo", "population_capacity": "12"},
    ]

    development_path = tmp_path / "14_development.txt"
    development_path.write_text(
        _render_development_setup(
            [("alpha", 2.0), ("bravo", 14.125)],
            decimals=2,
        ),
        encoding="utf-8",
    )
    development = parse_file(development_path).values("development")[0]
    assert isinstance(development, CList)
    assert development.first("base") == 0
    assert development.first("alpha") == 2.0
    assert development.first("bravo") == 14.12

    irrigation_path = tmp_path / "14_pp_population_irrigation.txt"
    irrigation_path.write_text(
        _render_irrigation_setup([("alpha", "AAA", 3)]),
        encoding="utf-8",
    )
    manager = parse_file(irrigation_path).values("building_manager")[0]
    assert isinstance(manager, CList)
    irrigation = manager.first("irrigation_systems")
    assert isinstance(irrigation, CList)
    assert irrigation.first("tag") == "AAA"
    assert irrigation.first("level") == 3
    assert irrigation.first("location") == "alpha"


def test_development_setup_compiler_disambiguates_location_and_province_keys() -> None:
    compilation = _compile_development_setup_rows(
        [("alpha", 10.0), ("bravo", 20.0), ("charlie", 5.0)],
        state=pl.DataFrame(
            {
                "location_tag": ["alpha", "bravo", "charlie"],
                "province": ["alpha", "alpha", "other"],
            }
        ),
        target_decimals=2,
    )

    assert compilation.selector_collision_keys == ("alpha",)
    assert compilation.coefficient_decimals == 2
    assert dict(compilation.rows) == {
        "alpha": 5.0,
        "bravo": 15.0,
        "charlie": 5.0,
    }
    assert compilation.maximum_effective_error == 0.0


def test_development_setup_compiler_increases_precision_when_collision_doubles_cents() -> None:
    compilation = _compile_development_setup_rows(
        [("alpha", 0.67), ("bravo", 1.0)],
        state=pl.DataFrame(
            {
                "location_tag": ["alpha", "bravo"],
                "province": ["alpha", "alpha"],
            }
        ),
        target_decimals=2,
    )

    assert compilation.coefficient_decimals == 3
    assert dict(compilation.rows) == {"alpha": 0.335, "bravo": 0.665}
    assert compilation.maximum_effective_error < 1e-12


def test_rendered_capacity_reaches_applied_wuxian_location_modifier() -> None:
    with (ROOT / "data/population_capacity/population_capacity.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        capacity = next(
            int(row["population_capacity"])
            for row in csv.DictReader(handle)
            if row["location_tag"] == "wuxian"
        )

    parser_profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(parser_profile, "static_modifiers")
    modifier = next(
        entry.value for entry in static_modifiers.entries if entry.key == "pp_loc_wuxian"
    )
    assert isinstance(modifier, CList)
    assert modifier.first("local_population_capacity") == capacity

    on_action = parse_file(
        ROOT
        / "mod"
        / "Prosper or Perish (Population Growth & Food Rework)"
        / "in_game"
        / "common"
        / "on_action"
        / "pp_apply_location_modifiers.txt"
    )
    apply = on_action.values("pp_apply_location_modifiers")[0]
    assert isinstance(apply, CList)
    effect = apply.first("effect")
    assert isinstance(effect, CList)
    location = effect.first("location:wuxian")
    assert isinstance(location, CList)
    add_modifier = location.first("add_location_modifier")
    assert isinstance(add_modifier, CList)
    assert add_modifier.first("modifier") == "pp_loc_wuxian"
