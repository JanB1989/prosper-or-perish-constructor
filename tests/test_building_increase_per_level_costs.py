from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from eu5_building_pipeline.template import load_template
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.building_types import load_building_type_data
from prosper_or_perish_constructor.building_scaling import (
    load_building_scaling_config,
    scaled_increase_per_level_cost_text,
)
from prosper_or_perish_constructor.goods_categories import (
    accepted_blueprint_paths_by_building,
    building_increase_cost_assignments,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
INTENTIONAL_SOURCE_COST_OVERRIDES = {
    "husbandry_farmstead": "bridge farmstead keeps the existing low staple-farm cadence",
    "saffron_kiln_croft": "successor croft keeps the existing tea/coffee-style crop cadence",
    "shoen": "vanilla inject keeps the existing historical estate cadence",
}


def test_goods_producer_blueprints_have_scaled_increase_per_level_cost() -> None:
    assignments = building_increase_cost_assignments(ROOT, PROJECT)
    paths_by_building = accepted_blueprint_paths_by_building(ROOT)

    assert assignments
    missing = [assignment.building for assignment in assignments if assignment.building not in paths_by_building]
    assert not missing

    mismatches: list[str] = []
    for assignment in assignments:
        template = load_template(paths_by_building[assignment.building])
        actual = _top_level_increase_per_level_cost(template.key, template.building_body)
        if actual is None or Decimal(actual) != Decimal(assignment.scaled_cost_text):
            if assignment.building in INTENTIONAL_SOURCE_COST_OVERRIDES and actual is not None:
                continue
            mismatches.append(
                f"{assignment.building}: expected {assignment.scaled_cost_text} "
                f"from {assignment.main_good}, found {actual or '<missing>'}"
            )

    assert not mismatches


def test_goods_producer_main_output_is_documented_by_assignment() -> None:
    assignments = building_increase_cost_assignments(ROOT, PROJECT)

    assignment_by_building = {assignment.building: assignment for assignment in assignments}
    assert assignment_by_building["market_village"].main_good == "tools"
    assert assignment_by_building["ablaq_palace"].main_good == "silk"
    assert assignment_by_building["cookery"].main_good == "victuals"


def test_rendered_goods_producers_have_final_scaled_increase_per_level_cost() -> None:
    assignments = building_increase_cost_assignments(ROOT, PROJECT)
    paths_by_building = accepted_blueprint_paths_by_building(ROOT)
    scaling = load_building_scaling_config(PROJECT)
    building_types = load_building_type_data(
        profile="constructor",
        load_order_path=ROOT / "constructor.load_order.toml",
    )

    mismatches: list[str] = []
    for assignment in assignments:
        template = load_template(paths_by_building[assignment.building])
        source_cost = _top_level_increase_per_level_cost(template.key, template.building_body)
        if source_cost is None:
            mismatches.append(f"{assignment.building}: missing source increase_per_level_cost")
            continue
        expected = scaled_increase_per_level_cost_text(
            Decimal(source_cost),
            scaling.increase_per_level_cost_multiplier,
        )
        actual = building_types.modifier_baseline(
            assignment.building,
            None,
            "increase_per_level_cost",
        )
        if Decimal(str(actual)) != Decimal(expected):
            mismatches.append(
                f"{assignment.building}: expected {expected}, found {actual}"
            )

    assert not mismatches


def _top_level_increase_per_level_cost(building: str, body: str) -> str | None:
    parsed = parse_text(f"{building} = {{\n{body}\n}}\n")
    block = parsed.entries[0].value
    assert isinstance(block, CList)
    values = block.values("increase_per_level_cost")
    if not values:
        return None
    return str(values[-1])
