from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.availability import AGE_ORDER
from eu5gameparser.domain.eu5 import load_eu5_data
from prosper_or_perish_constructor.production_profit import (
    DISABLED_PRODUCTION_EXPERIMENTS,
    FAITHFUL_IMPORT_ALLOW_RULES,
    _attached_production_methods,
    _body_from_block,
    _clean_employment_size,
    _converted_building_block,
    _enable_manifest_entries,
    _localization_entries,
    _profit_rows_for_age,
    _rows_and_benchmarks_by_age,
    import_missing_production_buildings,
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


def test_every_constructor_production_building_has_enabled_blueprint_target() -> None:
    coverage = production_building_coverage(ROOT, load_order_path=LOAD_ORDER)

    assert coverage.missing_constructor_buildings == set()
    assert coverage.missing_import_targets == set()
    assert coverage.constructor_only_buildings <= set(coverage.accepted_blueprints_by_building)
    assert DISABLED_PRODUCTION_EXPERIMENTS.isdisjoint(coverage.constructor_buildings)


def test_constructor_production_buildings_are_mod_owned_create_or_replace() -> None:
    coverage = production_building_coverage(ROOT, load_order_path=LOAD_ORDER)

    assert coverage.unowned_constructor_buildings == set()
    for building in sorted(coverage.vanilla_buildings):
        mode, layer = coverage.constructor_source_by_building[building]
        assert (mode, layer) == ("REPLACE", "constructor"), building
    for building in sorted(coverage.constructor_only_buildings):
        mode, layer = coverage.constructor_source_by_building[building]
        assert (mode, layer) == ("CREATE", "constructor"), building


def test_mercury_patio_is_not_a_production_building() -> None:
    coverage = production_building_coverage(ROOT, load_order_path=LOAD_ORDER)

    assert "mercury_patio" not in coverage.vanilla_buildings
    assert "mercury_patio" not in coverage.constructor_buildings


def test_import_missing_production_buildings_is_a_noop_when_coverage_is_complete() -> None:
    brewery = ROOT / "blueprints" / "accepted" / "buildings" / "brewery.yml"
    before = brewery.read_text(encoding="utf-8-sig")
    results = import_missing_production_buildings(
        ROOT,
        profile="constructor",
        vanilla_profile="vanilla",
        load_order_path=LOAD_ORDER,
        dry_run=False,
        burgher_employment_size=0.3,
    )

    assert results == []
    assert brewery.read_text(encoding="utf-8-sig") == before


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


def test_faithful_import_renames_unique_methods_without_scaling_inputs() -> None:
    parsed = parse_text(
        """
        workshop = {
            pop_type = burghers
            unique_production_methods = {
                beer_method = {
                    wheat = 1.0
                    produced = beer
                    output = 1
                    category = guild_input
                }
            }
            possible_production_methods = {
                rural_blacksmith
            }
        }
        """
    )
    block = parsed.entries[0].value
    assert isinstance(block, CList)
    converted, slots, method_count, mapping = _converted_building_block(
        "workshop",
        block,
        building_row={"pop_type": "burghers", "employment_size": 1.0},
        production_methods={
            "rural_blacksmith": {
                "name": "rural_blacksmith",
                "produced": "tools",
                "output_value": 0.3,
                "input_cost": 0.1,
            }
        },
        production_methods_by_building={},
        global_method_blocks={
            "rural_blacksmith": parse_text(
                """
                rural_blacksmith = {
                    iron = 0.2
                    produced = tools
                    output = 0.3
                }
                """
            ).entries[0].value
        },
        benchmarks={},
        burgher_employment_size=0.3,
    )
    body = _body_from_block(converted)

    assert method_count == 2
    assert mapping == {
        "beer_method": "pp_workshop_beer_method",
        "rural_blacksmith": "pp_workshop_rural_blacksmith",
    }
    assert [slot["methods"] for slot in slots] == [
        ["pp_workshop_beer_method"],
        ["pp_workshop_rural_blacksmith"],
    ]
    assert "pp_workshop_beer_method" in body
    assert "pp_workshop_rural_blacksmith" in body
    assert "\nbeer_method =" not in f"\n{body}"
    assert "possible_production_methods" not in body
    assert "wheat = 1.0" in body
    assert "iron = 0.2" in body
    assert "employment_size = 0.3" in body
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


def test_localization_entries_copy_vanilla_method_names() -> None:
    entries = _localization_entries(
        "brewery",
        [{"name": "slot_0", "methods": ["pp_brewery_wheat_brewery_maintenance"]}],
        method_names={"wheat_brewery_maintenance": "pp_brewery_wheat_brewery_maintenance"},
        loc={"wheat_brewery_maintenance": "Wheat Breweries", "brewery": "Brewery"},
        include_building=False,
    )

    assert entries["pp_brewery_wheat_brewery_maintenance"] == "Wheat Breweries"
    assert "brewery" not in entries
    assert entries["brewery_slot_0"] == "Brewery Work"


def test_enable_manifest_entries_appends_missing_paths(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yml"
    empty.write_text("enabled: {}\n", encoding="utf-8")
    _enable_manifest_entries(empty, ["buildings/brewery.yml"])
    empty_raw = yaml.safe_load(empty.read_text(encoding="utf-8"))
    assert empty_raw["enabled"] == {"buildings/brewery.yml": True}

    existing = tmp_path / "existing.yml"
    existing.write_text("enabled:\n  buildings/winery.yml: true\n", encoding="utf-8")
    _enable_manifest_entries(existing, ["buildings/brewery.yml", "buildings/winery.yml"])
    text = existing.read_text(encoding="utf-8")
    assert "buildings/winery.yml: true" in text
    assert text.count("buildings/brewery.yml: true") == 1


def test_non_production_hand_overrides_remain_in_place() -> None:
    building_types = (
        ROOT
        / "mod"
        / "Prosper or Perish (Population Growth & Food Rework)"
        / "in_game"
        / "common"
        / "building_types"
    )

    assert (building_types / "pp_mercury_patio_adjustments.txt").is_file()
    assert (building_types / "pp_culture_building_adjustments.txt").is_file()
    assert (building_types / "pp_gold_to_jewelry_buildings.txt").is_file()
    assert (building_types / "pp_governor_building_adjustments.txt").is_file()


def test_import_missing_writes_faithful_replace_yaml_without_touching_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from prosper_or_perish_constructor.production_profit import ProductionBuildingCoverage

    brewery = ROOT / "blueprints" / "accepted" / "buildings" / "brewery.yml"
    before = brewery.read_text(encoding="utf-8-sig")
    manifest = tmp_path / "blueprints" / "buildings.manifest.yml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("enabled: {}\n", encoding="utf-8")

    def fake_coverage(repo: Path, **kwargs: object) -> ProductionBuildingCoverage:
        return ProductionBuildingCoverage(
            vanilla_buildings={"brewery"},
            vanilla_goods_by_building={"brewery": {"beer"}},
            constructor_buildings={"brewery"},
            constructor_goods_by_building={"brewery": {"beer"}},
            constructor_source_by_building={"brewery": ("REPLACE", "constructor")},
            accepted_blueprints_by_building={},
            cost_only_stub_buildings=set(),
            production_blueprint_buildings=set(),
        )

    monkeypatch.setattr(
        "prosper_or_perish_constructor.production_profit.production_building_coverage",
        fake_coverage,
    )
    monkeypatch.setattr(
        "prosper_or_perish_constructor.production_profit._english_localization",
        lambda profile, path: {"wheat_brewery_maintenance": "Wheat Breweries"},
    )

    results = import_missing_production_buildings(
        tmp_path,
        profile="constructor",
        vanilla_profile="vanilla",
        load_order_path=LOAD_ORDER,
        dry_run=False,
        burgher_employment_size=0.3,
    )

    written = tmp_path / "blueprints" / "accepted" / "buildings" / "brewery.yml"
    raw = yaml.safe_load(written.read_text(encoding="utf-8"))
    body = str(raw["building"]["body"])
    enabled = yaml.safe_load(manifest.read_text(encoding="utf-8"))["enabled"]

    assert [result.building for result in results] == ["brewery"]
    assert results[0].changed is True
    assert brewery.read_text(encoding="utf-8-sig") == before
    assert raw["building"]["mode"] == "REPLACE"
    assert raw["building"]["possible_production_methods"] == []
    assert raw["evaluation"]["allow_rules"] == FAITHFUL_IMPORT_ALLOW_RULES
    assert "pp_brewery_wheat_brewery_maintenance" in body
    assert "wheat = 0.994" in body
    assert "\nwheat_brewery_maintenance =" not in f"\n{body}"
    assert "audio_tier =" in body
    assert "startup_ramp_target =" in body
    assert "possible_production_methods" not in body
    assert raw["localization"]["entries"]["pp_brewery_wheat_brewery_maintenance"] == "Wheat Breweries"
    assert "brewery" not in raw["localization"]["entries"]
    assert enabled["buildings/brewery.yml"] is True

