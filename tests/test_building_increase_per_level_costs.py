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
    "saffron_kiln_croft": "successor croft keeps the existing tea/coffee-style crop cadence",
    "shoen": "vanilla inject keeps the existing historical estate cadence",
    "tavern": "hefty repeat cost: every Tavern level costs another full base price",
    "grange": "steep repeat cost so only market centres and developed capitals grow large Granges",
    "victualling_yard": "each harbour Yard level costs another full base price, so strong Yards stay rare",
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
    # the Cookshop line only makes Province Food, which is never a main good; victuals are the Victualling Yard's
    assert "cookshop" not in assignment_by_building and "public_kitchen" not in assignment_by_building


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


def test_tavern_levels_cost_the_base_price():
    """2026-10-04 (Jan): no level cost scaling for the Tavern (was 1.33, another full base price per level)."""
    path = accepted_blueprint_paths_by_building(ROOT)['tavern']
    template = load_template(path)
    source = Decimal(_top_level_increase_per_level_cost(template.key, template.building_body))
    scaling = load_building_scaling_config(PROJECT)
    assert scaled_increase_per_level_cost_text(source, scaling.increase_per_level_cost_multiplier) == "0.00"


def test_farms_repeat_their_levels_cheaper() -> None:
    """[farm_level_cost] 2026-09-30: every farm_land blueprint pays the factor x its main good's category cost."""
    from prosper_or_perish_constructor.goods_categories import farm_level_cost_factor, load_good_category_costs, load_increase_per_level_cost_band

    factor, footprints = farm_level_cost_factor(PROJECT)
    assert footprints == frozenset({"farm_land"}) and factor < 1
    band = load_increase_per_level_cost_band(ROOT / "config/goods_category_scaling.toml")
    costs = load_good_category_costs(ROOT / "config/goods_categories.csv", band)
    by_building = {a.building: a for a in building_increase_cost_assignments(ROOT, PROJECT)}
    for building in ("wheat_farm", "cattle_farmstead", "tea_garden", "sheep_farms"):
        assignment = by_building[building]
        expected = (Decimal(costs[assignment.main_good].scaled_cost_text) * factor).quantize(Decimal("0.01"))
        assert Decimal(assignment.scaled_cost_text) == expected, building
    assert by_building["tools_guild"].scaled_cost_text != "" and "tools_guild" in by_building  # not a farm: untouched
