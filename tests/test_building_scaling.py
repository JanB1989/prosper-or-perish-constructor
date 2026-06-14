from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from eu5_building_pipeline.template import load_template
from eu5_mod_orchestrator.config import load_project_config
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.goods import load_goods_data
from eu5gameparser.domain.pop_types import load_pop_type_data
from prosper_or_perish_constructor.building_scaling import (
    format_output_amount,
    load_building_scaling_config,
    worker_victuals_output_amount,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BUILDING_BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"
MANIFEST = ROOT / "blueprints" / "buildings.manifest.yml"
PRIMARY_WORKER_VICTUAL_BUILDINGS = (
    "farming_village",
    "farming_village_rotations",
    "model_farm",
    "fruit_orchard",
    "pomological_orchard",
    "fishing_village",
    "ocean_fishery",
    "offshore_fishery",
    "forest_village",
    "managed_forest_village",
)


def test_building_scaling_config_loads_worker_victuals_ratio() -> None:
    config = load_building_scaling_config(PROJECT)

    assert config.worker_victuals_food_need_ratio == Decimal("1.0")


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

        pop_food_consumption = _pop_food_consumption(pop_type)
        expected_output = worker_victuals_output_amount(
            employment_size=employment_size,
            pop_food_consumption=pop_food_consumption,
            victuals_food=victuals_food,
            food_need_ratio=scaling.worker_victuals_food_need_ratio,
        )
        actual_output = Decimal(str(method["output"]))

        assert str(actual_output) == format_output_amount(expected_output)
        actual_food = actual_output * victuals_food
        target_food = employment_size * pop_food_consumption * scaling.worker_victuals_food_need_ratio
        assert float(actual_food) == pytest.approx(float(target_food), rel=0.02)


def test_worker_victuals_slots_are_limited_to_primary_food_buildings() -> None:
    assert _accepted_worker_victual_buildings() == set(PRIMARY_WORKER_VICTUAL_BUILDINGS)


def _building_block(building: str, body: str) -> CList:
    parsed = parse_text(f"{building} = {{\n{body}\n}}\n")
    block = parsed.entries[0].value
    assert isinstance(block, CList)
    return block


def _last_value(block: CList, key: str) -> object:
    values = block.values(key)
    assert values, f"missing {key}"
    return values[-1]


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
    for entry in manifest["enabled"]:
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
