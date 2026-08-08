from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re

import pytest
import yaml
from eu5_building_pipeline.template import load_template
from eu5_mod_orchestrator.blueprints import enabled_manifest_entries
from eu5_mod_orchestrator.config import load_project_config
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.goods import load_goods_data
from eu5gameparser.domain.pop_types import load_pop_type_data
from prosper_or_perish_constructor.building_scaling import (
    apply_increase_per_level_cost_multiplier,
    format_increase_per_level_cost,
    format_output_amount,
    load_building_scaling_config,
    scaled_increase_per_level_cost_text,
    worker_victuals_output_amount,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BUILDING_BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"
MANIFEST = ROOT / "blueprints" / "buildings.manifest.yml"
PRIMARY_WORKER_VICTUAL_BUILDINGS = (
    "farming_village",
    "husbandry_farmstead",
    "farming_village_rotations",
    "model_farm",
    "fruit_orchard",
    "nursery_orchard",
    "pomological_orchard",
    "fishing_village",
    "net_curing_yard",
    "ocean_fishery",
    "drift_net_fishery",
    "offshore_fishery",
    "forest_village",
    "managed_forest_village",
)


def test_building_scaling_config_loads_worker_victuals_ratio() -> None:
    config = load_building_scaling_config(PROJECT)

    assert config.worker_victuals_food_need_ratio == Decimal("1.0")
    assert config.increase_per_level_cost_multiplier == Decimal("0.75")
    assert config.burgher_building_employment_size == Decimal("0.3")


def test_burgher_buildings_do_not_exceed_configured_employment_baseline() -> None:
    scaling = load_building_scaling_config(PROJECT)
    offenders: list[str] = []
    baseline_count = 0

    for entry in enabled_manifest_entries(
        yaml.safe_load(MANIFEST.read_text(encoding="utf-8")).get("enabled", []),
        source=MANIFEST,
    ):
        template = load_template(ROOT / "blueprints" / "accepted" / entry)
        block = _building_block(template.key, template.building_body)
        pop_type_values = block.values("pop_type")
        if not pop_type_values or str(pop_type_values[-1]) != "burghers":
            continue
        employment_size = Decimal(str(_last_value(block, "employment_size")))
        if employment_size == scaling.burgher_building_employment_size:
            baseline_count += 1
        if employment_size > scaling.burgher_building_employment_size:
            offenders.append(
                f"{template.key}: employment_size={employment_size} "
                f"> burgher baseline {scaling.burgher_building_employment_size}"
            )

    assert baseline_count > 0
    assert not offenders


def test_increase_per_level_cost_multiplier_rounds_to_two_decimals() -> None:
    assert scaled_increase_per_level_cost_text(Decimal("0.13"), Decimal("0.75")) == "0.10"
    assert scaled_increase_per_level_cost_text(Decimal("0.30"), Decimal("0.75")) == "0.23"
    assert format_increase_per_level_cost(Decimal("0.225")) == "0.23"


def test_increase_per_level_cost_compilation_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path
    project = repo / "constructor.toml"
    blueprint = repo / "blueprints" / "accepted" / "buildings" / "test_market.yml"
    manifest = repo / "blueprints" / "buildings.manifest.yml"
    mod_root = repo / "mod" / "test"
    building_type = mod_root / "in_game" / "common" / "building_types" / "zz_test_market.txt"

    project.write_text(
        "[building_scaling]\n"
        "worker_victuals_food_need_ratio = 1.0\n"
        "increase_per_level_cost_multiplier = 0.75\n",
        encoding="utf-8",
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text("enabled:\n- buildings/test_market.yml\n", encoding="utf-8")
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(
        "version: 2\n"
        "tag: test_market\n"
        "building:\n"
        "  key: test_market\n"
        "  mode: CREATE\n"
        "  source: test.txt\n"
        "  production_method_slots: []\n"
        "  possible_production_methods: []\n"
        "  body: |2-\n"
        "    increase_per_level_cost = 0.13\n",
        encoding="utf-8",
    )
    building_type.parent.mkdir(parents=True)
    building_type.write_text(
        "test_market = {\n"
        "\tincrease_per_level_cost = 0.13\n"
        "\tmodifier = {\n"
        "\t\tlocal_monthly_food = 1\n"
        "\t}\n"
        "}\n",
        encoding="utf-8-sig",
    )

    first = apply_increase_per_level_cost_multiplier(repo, mod_root, project)
    second = apply_increase_per_level_cost_multiplier(repo, mod_root, project)

    assert first.entries_scaled == 1
    assert second.entries_scaled == 1
    assert building_type.read_text(encoding="utf-8-sig") == (
        "test_market = {\n"
        "\tincrease_per_level_cost = 0.10\n"
        "\tmodifier = {\n"
        "\t\tlocal_monthly_food = 1\n"
        "\t}\n"
        "}\n"
    )


def test_primary_food_buildings_worker_victuals_slots_match_configured_worker_food_need() -> None:
    scaling = load_building_scaling_config(PROJECT)
    victuals_food = _good_food("victuals")

    for building in PRIMARY_WORKER_VICTUAL_BUILDINGS:
        template = load_template(BUILDING_BLUEPRINT_ROOT / f"{building}.yml")
        worker_method = f"pp_{building}_worker_victuals"
        no_worker_method = f"pp_{building}_no_worker_victuals"

        assert (no_worker_method, worker_method) in {slot.methods for slot in template.production_method_slots}

        block = _building_block(template.key, template.building_body)
        pop_type = str(_last_value(block, "pop_type"))
        employment_size = Decimal(str(_last_value(block, "employment_size")))
        method = _unique_method_values(block, worker_method)
        assert method["produced"] == "victuals"
        actual_output = Decimal(str(method["output"]))
        assert actual_output > 0

        if victuals_food > 0:
            pop_food_consumption = _pop_food_consumption(pop_type)
            expected_output = worker_victuals_output_amount(
                employment_size=employment_size,
                pop_food_consumption=pop_food_consumption,
                victuals_food=victuals_food,
                food_need_ratio=scaling.worker_victuals_food_need_ratio,
            )

            assert str(actual_output) == format_output_amount(expected_output)
            actual_food = actual_output * victuals_food
            target_food = employment_size * pop_food_consumption * scaling.worker_victuals_food_need_ratio
            assert float(actual_food) == pytest.approx(float(target_food), rel=0.02)


def test_worker_victuals_slots_are_limited_to_primary_food_buildings() -> None:
    assert _accepted_worker_victual_buildings() == set(PRIMARY_WORKER_VICTUAL_BUILDINGS)


def test_victuals_producers_supply_local_food_above_worker_consumption() -> None:
    for building in PRIMARY_WORKER_VICTUAL_BUILDINGS + ("eng_royal_forest", "victualling_yard"):
        template = load_template(BUILDING_BLUEPRINT_ROOT / f"{building}.yml")
        block = _building_block(template.key, template.building_body)
        pop_type = str(_last_value(block, "pop_type"))
        employment_size = Decimal(str(_last_value(block, "employment_size")))
        worker_food = employment_size * _pop_food_consumption(pop_type)
        modifier = _last_block(block, "modifier")
        local_food = Decimal(str(_last_value(modifier, "local_monthly_food")))

        assert local_food >= worker_food * Decimal("1.5")
        assert re.search(
            rf"local_monthly_food\s*=\s*{re.escape(str(local_food))}(?:\.0)?\b",
            template.building_body,
        )

    cookery = load_template(BUILDING_BLUEPRINT_ROOT / "cookery.yml")
    cookery_block = _building_block(cookery.key, cookery.building_body)
    cookery_modifier = _last_block(cookery_block, "modifier")
    cookery_local_food = Decimal(str(_last_value(cookery_modifier, "local_monthly_food")))
    assert cookery_local_food == Decimal("20.0")
    assert "local_monthly_food = 20.0" in cookery.building_body


def _building_block(building: str, body: str) -> CList:
    parsed = parse_text(f"{building} = {{\n{body}\n}}\n")
    block = parsed.entries[0].value
    assert isinstance(block, CList)
    return block


def _last_value(block: CList, key: str) -> object:
    values = block.values(key)
    assert values, f"missing {key}"
    return values[-1]


def _last_block(block: CList, key: str) -> CList:
    value = _last_value(block, key)
    assert isinstance(value, CList)
    return value


def _unique_method_values(building: CList, method: str) -> dict[str, object]:
    for group in building.values("unique_production_methods"):
        assert isinstance(group, CList)
        for entry in group.entries:
            if entry.key == method:
                assert isinstance(entry.value, CList)
                return {item.key: item.value for item in entry.value.entries}
    raise AssertionError(f"missing unique production method {method}")


def _pop_food_consumption(pop_type: str) -> Decimal:
    project = load_project_config(PROJECT)
    data = load_pop_type_data(profile=project.profile, load_order_path=project.load_order_path)
    rows = data.pop_types.filter(data.pop_types["name"] == pop_type).select("pop_food_consumption").to_dicts()
    assert rows
    return Decimal(str(rows[0]["pop_food_consumption"]))


def _good_food(good: str) -> Decimal:
    project = load_project_config(PROJECT)
    data = load_goods_data(profile=project.profile, load_order_path=project.load_order_path)
    rows = data.goods.filter(data.goods["name"] == good).select("food").to_dicts()
    assert rows
    return Decimal(str(rows[0]["food"]))


def _accepted_worker_victual_buildings() -> set[str]:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    result: set[str] = set()
    for entry in enabled_manifest_entries(manifest.get("enabled", []), source=MANIFEST):
        template = load_template(ROOT / "blueprints" / "accepted" / entry)
        methods = {
            method
            for slot in template.production_method_slots
            for method in slot.methods
            if method.endswith("_worker_victuals")
        }
        if methods:
            result.add(template.key)
    return result
