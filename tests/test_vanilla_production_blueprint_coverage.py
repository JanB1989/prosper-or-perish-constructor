from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eu5gameparser.domain.availability import AGE_ORDER
from eu5gameparser.domain.eu5 import load_eu5_data
from prosper_or_perish_constructor.production_profit import (
    _attached_production_methods,
    _clean_employment_size,
    _profit_rows_for_age,
    _rows_and_benchmarks_by_age,
    positive_output_buildings,
    production_building_coverage,
    validate_employment_size_step,
)
from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS


ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
DOCUMENTED_PRODUCED_GOOD_REPLACEMENTS = {
    # The food/forest capacity rework replaces vanilla village side-industry global
    # methods with explicit food, fish, forest-resource, and worker-victual methods.
    "fishing_village": {"naval_supplies", "pottery"},
    "forest_village": {"tools", "weaponry"},
}


def test_every_vanilla_production_building_has_enabled_blueprint_target() -> None:
    coverage = production_building_coverage(ROOT, load_order_path=LOAD_ORDER)

    assert coverage.missing_buildings == set()


def test_vanilla_production_blueprints_are_full_replacements_not_cost_stubs() -> None:
    coverage = production_building_coverage(ROOT, load_order_path=LOAD_ORDER)

    assert coverage.stub_only_buildings == set()
    for building in sorted(coverage.vanilla_buildings):
        path = coverage.accepted_blueprints_by_building[building]
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        body = str(raw.get("building", {}).get("body") or "")
        assert raw.get("building", {}).get("mode") == "REPLACE", building
        assert raw.get("building", {}).get("production_method_slots"), building
        assert "unique_production_methods" in body, building
        assert "possible_production_methods" not in body, building


def test_constructor_output_preserves_vanilla_produced_good_coverage() -> None:
    vanilla = load_eu5_data(profile="vanilla", load_order_path=LOAD_ORDER)
    constructor = load_eu5_data(profile="constructor", load_order_path=LOAD_ORDER)
    _vanilla_buildings, vanilla_goods = positive_output_buildings(vanilla.building_data)
    _constructor_buildings, constructor_goods = positive_output_buildings(constructor.building_data)

    missing: dict[str, set[str]] = {}
    for building, goods in vanilla_goods.items():
        documented = DOCUMENTED_PRODUCED_GOOD_REPLACEMENTS.get(building, set())
        absent = goods - documented - constructor_goods.get(building, set())
        if absent:
            missing[building] = absent

    assert missing == {}


def test_vanilla_production_blueprint_employment_sizes_use_50_pop_steps() -> None:
    coverage = production_building_coverage(ROOT, load_order_path=LOAD_ORDER)
    invalid: dict[str, object] = {}

    for building in sorted(coverage.vanilla_buildings):
        path = coverage.accepted_blueprints_by_building[building]
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        body = str(raw.get("building", {}).get("body") or "")
        match = next(
            (
                line.split("=", 1)[1].strip()
                for line in body.splitlines()
                if line.strip().startswith("employment_size =")
            ),
            None,
        )
        if not validate_employment_size_step(match):
            invalid[building] = match

    assert invalid == {}


def test_profit_rows_select_best_positive_method_per_slot_and_subtract_food_once() -> None:
    methods = [
        {
            "building": "workshop",
            "name": "low_profit",
            "produced": "tools",
            "output_value": 1.0,
            "input_cost": 0.4,
            "production_method_group_index": 0,
            "effective_availability_kind": "available_by_default",
        },
        {
            "building": "workshop",
            "name": "high_profit",
            "produced": "tools",
            "output_value": 1.2,
            "input_cost": 0.2,
            "production_method_group_index": 0,
            "effective_availability_kind": "available_by_default",
        },
        {
            "building": "workshop",
            "name": "second_slot",
            "produced": "beer",
            "output_value": 0.5,
            "input_cost": 0.1,
            "production_method_group_index": 1,
            "effective_availability_kind": "unlocked_by_advancement",
            "effective_unlock_age": "age_2_renaissance",
        },
    ]

    rows = _profit_rows_for_age(
        methods,
        {"workshop": 0.25},
        "age_2_renaissance",
        include_specific=True,
    )

    row = next(item for item in rows if item.building == "workshop")
    assert row.profit == pytest.approx(1.15)
    assert set(row.method_names) == {"high_profit", "second_slot"}


def test_global_possible_production_methods_count_as_production_surface() -> None:
    rows = _attached_production_methods(
        [{"name": "market_village", "possible_production_methods": ["rural_blacksmith"]}],
        [
            {
                "name": "rural_blacksmith",
                "source_kind": "global",
                "produced": "tools",
                "output_value": 0.3,
                "input_cost": 0.1,
            }
        ],
    )

    assert rows == [
        {
            "name": "rural_blacksmith",
            "source_kind": "global",
            "produced": "tools",
            "output_value": 0.3,
            "input_cost": 0.1,
            "building": "market_village",
            "production_method_group": "possible_production_methods",
            "production_method_group_index": None,
        }
    ]


def test_benchmark_ratios_use_land_farm_buildings_and_carry_forward() -> None:
    first_farm = LAND_FARM_BUILDINGS[0]
    rows, benchmarks = _rows_and_benchmarks_by_age(
        [
            {
                "building": first_farm,
                "name": "farm_base",
                "produced": "grain",
                "output_value": 0.6,
                "input_cost": 0.1,
                "production_method_group_index": 0,
                "effective_availability_kind": "available_by_default",
            },
            {
                "building": "workshop",
                "name": "workshop_base",
                "produced": "tools",
                "output_value": 1.0,
                "input_cost": 0.25,
                "production_method_group_index": 0,
                "effective_availability_kind": "available_by_default",
            },
        ],
        {first_farm: 0.05, "workshop": 0.0},
        include_specific=False,
    )

    assert set(benchmarks) == set(AGE_ORDER)
    assert all(value == pytest.approx(0.45) for value in benchmarks.values())
    assert next(row for row in rows if row.building == first_farm).profit == pytest.approx(0.45)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.0, True),
        ("0.05", True),
        ("0.10", True),
        ("0.075", False),
        (0, False),
        (None, False),
    ],
)
def test_employment_size_step_validation(value: object, expected: bool) -> None:
    assert validate_employment_size_step(value) is expected


def test_converter_uses_configured_burgher_employment_baseline() -> None:
    assert (
        _clean_employment_size(
            1.0,
            pop_type="burghers",
            burgher_employment_size=0.3,
        )
        == 0.3
    )
    assert (
        _clean_employment_size(
            1.0,
            pop_type="laborers",
            burgher_employment_size=0.3,
        )
        == 1.0
    )
