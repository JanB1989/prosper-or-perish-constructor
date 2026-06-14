import re
from pathlib import Path

import pytest
import yaml
from eu5_mod_orchestrator.adapters.building_pipeline import evaluate_building_blueprint_data
from eu5_mod_orchestrator.adapters.parser import (
    load_balance_prices,
    load_global_building_unlock_ages,
    load_global_unlock_ages,
    load_raw_material_goods,
    load_script_values,
)
from eu5_mod_orchestrator.config import load_project_config
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
RIVER_BLUEPRINT = ROOT / "blueprints" / "accepted" / "buildings" / "river_boatmen_yard.yml"
LOGISTICS_BLUEPRINTS = (
    ROOT / "blueprints" / "accepted" / "buildings" / "carrier_inn.yml",
    RIVER_BLUEPRINT,
    ROOT / "blueprints" / "accepted" / "buildings" / "transport_office.yml",
    ROOT / "blueprints" / "accepted" / "buildings" / "coastal_shipping_office.yml",
)
LOGISTICS_BALANCE_TARGETS = {
    "carrier_inn": {
        "max_levels": "10",
        "pop_type": "peasants",
        "upkeep": 3.025,
    },
    "river_boatmen_yard": {
        "max_levels": "pp_river_boatmen_yard_max_level",
        "pop_type": "laborers",
        "upkeep": 2.0,
    },
    "transport_office": {
        "max_levels": "100",
        "pop_type": "laborers",
        "upkeep": 3.0,
    },
    "coastal_shipping_office": {
        "max_levels": "3",
        "pop_type": "laborers",
        "upkeep": 2.0,
    },
}
GOOD_PRICES = {
    "cloth": 3.0,
    "horses": 3.0,
    "livestock": 1.5,
    "lumber": 1.5,
    "naval_supplies": 3.0,
    "paper": 2.0,
    "tar": 2.0,
    "tools": 3.0,
    "victuals": 2.5,
}
ROAD_MAINTENANCE_BLUEPRINTS = (
    ROOT / "blueprints" / "accepted" / "buildings" / "road_wardens_yard.yml",
    ROOT / "blueprints" / "accepted" / "buildings" / "paviors_yard.yml",
    ROOT / "blueprints" / "accepted" / "buildings" / "macadam_works.yml",
    ROOT / "blueprints" / "accepted" / "buildings" / "permanent_way_depot.yml",
)
LOGISTICS_CAPS = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_logistics_building_caps.txt"
LOCATION_MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifier_adjustments.txt"
BUILDING_CAP_TYPES = (
    MOD_ROOT / "main_menu" / "common" / "modifier_type_definitions" / "pp_building_cap_modifiers.txt"
)
BUILDING_CAP_ICONS = MOD_ROOT / "main_menu" / "common" / "modifier_icons" / "pp_building_cap_modifier_icons.txt"
BUILDING_ADJUSTMENTS_LOC = (
    MOD_ROOT / "main_menu" / "localization" / "english" / "pp_building_adjustments_l_english.yml"
)
MARKET_VILLAGE_MARKET_ACCESS_BLUEPRINT = (
    ROOT / "blueprints" / "accepted" / "buildings" / "market_village_market_access.yml"
)
MARKET_VILLAGE_MARKET_ACCESS_RENDERED = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "building_types"
    / "zz_pp_market_village_market_access.txt"
)
VICTUALS_MARKET_BLUEPRINT = ROOT / "blueprints" / "accepted" / "buildings" / "victuals_market.yml"
VICTUALS_MARKET_RENDERED = (
    MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_victuals_market.txt"
)
FOUR_YEARLY_COUNTRY_PULSE = (
    MOD_ROOT / "in_game" / "common" / "on_action" / "pp_country_four_yearly.txt"
)
BUILDING_CULLING_ACTIONS = (
    MOD_ROOT / "in_game" / "common" / "on_action" / "pp_building_culling.txt"
)
LOGISTICS_AI_BUILD_ORDER = (
    "coastal_shipping_office",
    "river_boatmen_yard",
    "carrier_inn",
    "transport_office",
)


def _custom_tags(text: str) -> set[str]:
    match = re.search(r"custom_tags\s*=\s*\{\s*(?P<tags>[^}]*)\}", text)
    assert match is not None
    return set(match.group("tags").split())


def _field(body: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*([^\s#]+)", body, flags=re.M)
    assert match is not None, f"missing {key}"
    return match.group(1)


def _modifier_block(body: str) -> str:
    match = re.search(r"(?m)^\s*modifier\s*=\s*\{(?P<body>.*?)\n\s*\}", body, flags=re.S)
    assert match is not None, "missing modifier block"
    return match.group("body")


def _named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}\s*=\s*\{{", text)
    assert match is not None, f"missing block {name}"
    depth = 0
    for index in range(match.end() - 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"unterminated block {name}")


def _logistics_severity_blocks(block: str) -> list[tuple[str, str]]:
    starts = list(
        re.finditer(
            r"# Logistics severity pass: unsupported building levels >= ([0-9]+)",
            block,
        )
    )
    assert starts, "missing logistics severity pass markers"
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else block.find(
            "clear_variable_list = pp_ai_logistics_handled_areas",
            match.end(),
        )
        assert end != -1
        sections.append((match.group(1), block[match.start() : end]))
    return sections


def _goods_total(body: str) -> float:
    total = 0.0
    for good, amount in re.findall(r"^\s*([A-Za-z0-9_]+)\s*=\s*([0-9.]+)\s*$", body, flags=re.M):
        if good == "category":
            continue
        total += GOOD_PRICES[good] * float(amount)
    return total


def test_river_boatmen_yard_cap_scales_with_river_level() -> None:
    blueprint = RIVER_BLUEPRINT.read_text(encoding="utf-8")
    assert "max_levels = pp_river_boatmen_yard_max_level" in blueprint
    location_potential = blueprint.split("location_potential = {", 1)[1].split("}", 1)[0]
    assert "has_river = yes" in location_potential
    assert "is_adjacent_to_lake = yes" not in location_potential

    cap_value = LOGISTICS_CAPS.read_text(encoding="utf-8")
    assert 'desc = "BUILDING_LEVEL_RIVER_FREIGHT_CAPACITY"' in cap_value
    assert "value = modifier:pp_river_boatmen_yard_cap_modifier" in cap_value
    assert "min = 0" in cap_value

    modifiers = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    for river_level in range(1, 6):
        block = re.search(
            rf"TRY_INJECT:river_flowing_through_{river_level} = \{{(?P<body>.*?)\n\}}",
            modifiers,
            flags=re.S,
        )
        assert block is not None
        assert f"pp_river_boatmen_yard_cap_modifier = {river_level * 2}" in block.group("body")

    assert "pp_river_boatmen_yard_cap_modifier" in BUILDING_CAP_TYPES.read_text(encoding="utf-8-sig")
    assert "gfx/interface/icons/buildings/river_boatmen_yard.dds" in BUILDING_CAP_ICONS.read_text(
        encoding="utf-8-sig"
    )

    localization = BUILDING_ADJUSTMENTS_LOC.read_text(encoding="utf-8-sig")
    assert 'BUILDING_LEVEL_RIVER_FREIGHT_CAPACITY: "From River Size"' in localization
    assert 'MODIFIER_TYPE_NAME_pp_river_boatmen_yard_cap_modifier: "River Freight Capacity"' in localization


def test_logistics_infrastructure_buildings_are_tagged_for_modifier_evaluation() -> None:
    for blueprint in LOGISTICS_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8")
        assert "category = infrastructure_category" in text
        assert _custom_tags(text) == {"pp_logistics_infrastructure_priority", "pp_logistics"}


def test_logistics_infrastructure_balance_targets_are_current() -> None:
    for blueprint_path in LOGISTICS_BLUEPRINTS:
        blueprint = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
        key = blueprint["building"]["key"]
        expected = LOGISTICS_BALANCE_TARGETS[key]
        body = blueprint["building"]["body"]
        modifier_body = _modifier_block(body)
        method_body = blueprint["production_methods"][0]["body"]
        localization_keys = set(blueprint["localization"]["entries"])

        assert "price =" not in body
        assert "prices" not in blueprint
        assert not any(localization_key.endswith("_price") for localization_key in localization_keys)
        assert not any("price_cost_modifier" in localization_key for localization_key in localization_keys)
        assert _field(body, "max_levels") == expected["max_levels"]
        assert _field(body, "pop_type") == expected["pop_type"]
        assert _field(body, "employment_size") == "1"
        assert "local_market_access" not in modifier_body
        assert _field(modifier_body, "free_building_levels") == "10"
        assert _goods_total(method_body) == pytest.approx(expected["upkeep"])


def test_road_maintenance_buildings_keep_separate_logistics_tag() -> None:
    for blueprint in ROAD_MAINTENANCE_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8")
        assert "category = infrastructure_category" in text
        assert _custom_tags(text) == {"pp_logistics_infrastructure_priority", "pp_road_maintenance"}


def test_logistics_infrastructure_buildings_emit_modifier_ratio_metrics() -> None:
    config = load_project_config(ROOT / "constructor.toml")
    price_by_good = load_balance_prices(profile=config.profile, load_order_path=config.load_order_path)
    raw_material_goods = load_raw_material_goods(profile=config.profile, load_order_path=config.load_order_path)
    global_unlock_age_by_method = load_global_unlock_ages(
        profile=config.profile,
        load_order_path=config.load_order_path,
    )
    global_unlock_age_by_building = load_global_building_unlock_ages(
        profile=config.profile,
        load_order_path=config.load_order_path,
    )
    script_values = load_script_values(profile=config.profile, load_order_path=config.load_order_path)

    for blueprint in LOGISTICS_BLUEPRINTS:
        evaluation = evaluate_building_blueprint_data(
            blueprint,
            config,
            price_by_good=price_by_good,
            raw_material_goods=raw_material_goods,
            script_values=script_values,
            global_unlock_age_by_method=global_unlock_age_by_method,
            global_unlock_age_by_building=global_unlock_age_by_building,
        )
        assert evaluation.methods
        for method in evaluation.methods:
            modifier_names = {modifier.name for modifier in method.building_modifiers}
            assert method.building_category == "infrastructure_category"
            assert modifier_names == {"free_building_levels"}
            for modifier in method.building_modifiers:
                assert modifier.per_maintenance_gold is not None
                assert modifier.per_1k is not None


def test_ai_logistics_unsupported_levels_action_runs_on_four_year_pulse() -> None:
    pulse = FOUR_YEARLY_COUNTRY_PULSE.read_text(encoding="utf-8-sig")

    assert "pp_ai_logistics_on_unsupported_building_levels" in pulse


def test_ai_logistics_unsupported_levels_action_keeps_required_guards() -> None:
    block = _named_block(
        BUILDING_CULLING_ACTIONS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_on_unsupported_building_levels",
    )

    assert "is_ai = yes" in block
    assert "monthly_balance > 0" in block
    assert "ordered_owned_location = {" not in block
    assert block.count("every_area_with_owned_province = {") == 4
    assert block.count("ordered_location_in_area = {") == 4
    assert "order_by = pp_unsupported_building_levels_map_value" in block
    assert "check_range_bounds = no" in block
    assert "instant = yes" not in block
    assert "cost_multiplier = 0" not in block

    for building in LOGISTICS_AI_BUILD_ORDER:
        assert f"can_build_building = building_type:{building}" in block
        assert f"value = building_type:{building}.building_base_cost_in_gold" in block

    assert block.count("gold >= {") >= len(LOGISTICS_AI_BUILD_ORDER)


def test_ai_logistics_unsupported_levels_uses_area_tracking_and_budget() -> None:
    block = _named_block(
        BUILDING_CULLING_ACTIONS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_on_unsupported_building_levels",
    )

    assert "clear_variable_list = pp_ai_logistics_handled_areas" in block
    assert "is_target_in_variable_list = {" in block
    assert "name = pp_ai_logistics_handled_areas" in block
    assert "target = prev" in block
    assert "scope:pp_ai_logistics_country = {" in block
    assert (
        "add_to_variable_list = { name = pp_ai_logistics_handled_areas target = scope:pp_ai_logistics_current_area }"
        in block
    )
    assert "set_variable = { name = pp_ai_logistics_build_count value = 0 }" in block
    assert "set_variable = { name = pp_ai_logistics_budget value = gold }" in block
    assert "change_variable = { name = pp_ai_logistics_budget multiply = 0.25 }" in block
    assert "max = { value = monthly_balance multiply = 24 }" in block
    assert block.count("var:pp_ai_logistics_build_count < 20") == 4
    assert "change_variable = { name = pp_ai_logistics_build_count add = 1 }" in block

    for building in LOGISTICS_AI_BUILD_ORDER:
        assert (
            f"change_variable = {{ name = pp_ai_logistics_budget subtract = {{ value = building_type:{building}.building_base_cost_in_gold }} }}"
            in block
        )


def test_ai_logistics_unsupported_levels_severity_passes_are_exact() -> None:
    block = _named_block(
        BUILDING_CULLING_ACTIONS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_on_unsupported_building_levels",
    )

    severity_blocks = _logistics_severity_blocks(block)
    assert [threshold for threshold, _ in severity_blocks] == ["30", "15", "5", "1"]

    for threshold, severity_block in severity_blocks:
        assert f"pp_unsupported_building_levels_map_value >= {threshold}" in severity_block


def test_ai_logistics_unsupported_levels_build_priority_is_exact() -> None:
    block = _named_block(
        BUILDING_CULLING_ACTIONS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_on_unsupported_building_levels",
    )

    for _, severity_block in _logistics_severity_blocks(block):
        ordered_buildings = re.findall(
            r"construct_building\s*=\s*\{\s*building_type\s*=\s*building_type:([a-z_]+)\s*\}",
            severity_block,
            flags=re.S,
        )
        assert ordered_buildings == list(LOGISTICS_AI_BUILD_ORDER)


def test_market_village_market_access_is_neutralized_by_inject_blueprint() -> None:
    blueprint = MARKET_VILLAGE_MARKET_ACCESS_BLUEPRINT.read_text(encoding="utf-8")
    assert "mode: TRY_INJECT" in blueprint
    assert "key: market_village" in blueprint
    assert "local_market_access = -0.005" in blueprint

    rendered = MARKET_VILLAGE_MARKET_ACCESS_RENDERED.read_text(encoding="utf-8-sig")
    assert "TRY_INJECT:market_village" in rendered
    assert "local_market_access = -0.005" in rendered

    profile = load_profile("constructor", ROOT / "constructor.load_order.toml")
    merged = load_merged_directory(profile, "building_types")
    market_village = next(entry for entry in merged.entries if entry.key == "market_village")
    assert isinstance(market_village.value, CList)

    total = 0.0
    for modifier in market_village.value.values("modifier"):
        assert isinstance(modifier, CList)
        for entry in modifier.entries:
            if entry.key == "local_market_access":
                assert isinstance(entry.value, int | float)
                total += float(entry.value)

    assert total == 0.0


def test_victuals_market_does_not_provide_market_access() -> None:
    for path in (VICTUALS_MARKET_BLUEPRINT, VICTUALS_MARKET_RENDERED):
        text = path.read_text(encoding="utf-8-sig")
        assert "local_monthly_food = 60" in text
        assert "local_crown_estate_power = 0.025" in text
        assert "local_market_access" not in text
