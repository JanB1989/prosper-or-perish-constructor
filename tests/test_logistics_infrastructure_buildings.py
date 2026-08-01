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
        "max_levels": "100",
        "increase_per_level_cost": "0.30",
        "pop_type": "peasants",
        "upkeep": 2.5,
    },
    "river_boatmen_yard": {
        "max_levels": "pp_river_boatmen_yard_max_level",
        "increase_per_level_cost": "0.15",
        "pop_type": "laborers",
        "upkeep": 1.25,
    },
    "transport_office": {
        "max_levels": "100",
        "increase_per_level_cost": "0.30",
        "pop_type": "laborers",
        "upkeep": 3.0,
    },
    "coastal_shipping_office": {
        "max_levels": "pp_coastal_shipping_office_max_level",
        "increase_per_level_cost": "0.20",
        "pop_type": "laborers",
        "upkeep": 1.75,
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
VICTUALS_MARKET_BLUEPRINT = (
    ROOT / "blueprints" / "accepted" / "buildings" / "victuals_market_export.yml"
)
VICTUALS_MARKET_IMPORT_BLUEPRINT = (
    ROOT / "blueprints" / "accepted" / "buildings" / "victuals_market_import.yml"
)
VICTUALS_MARKET_RENDERED = (
    MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_victuals_market.txt"
)
VICTUALS_MARKET_IMPORT_RENDERED = (
    MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_victuals_market_import.txt"
)
VICTUALS_MARKET_ICON = (
    MOD_ROOT / "in_game" / "gfx" / "interface" / "icons" / "buildings" / "victuals_market.dds"
)
VICTUALS_MARKET_IMPORT_ICON = (
    MOD_ROOT
    / "in_game"
    / "gfx"
    / "interface"
    / "icons"
    / "buildings"
    / "victuals_market_import.dds"
)
FOUR_YEARLY_COUNTRY_PULSE = (
    MOD_ROOT / "in_game" / "common" / "on_action" / "pp_country_four_yearly.txt"
)
BUILDING_CULLING_ACTIONS = (
    MOD_ROOT / "in_game" / "common" / "on_action" / "pp_building_culling.txt"
)
LOGISTICS_SCRIPTED_EFFECTS = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "scripted_effects"
    / "pp_ai_logistics_building_effects.txt"
)
LOGISTICS_DEBUG_EVENT = MOD_ROOT / "in_game" / "events" / "debug" / "pp_logistics_debug.txt"
DEBUG_LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_debug_l_english.yml"
EMPLOYMENT_PRIORITIES = (
    MOD_ROOT / "in_game" / "common" / "employment_systems" / "pp_food_security_priorities.txt"
)
LOGISTICS_PRIORITY_GROUPS = (
    ("river_boatmen_yard", "pp_river_logistics_priority", 80),
    ("coastal_shipping_office", "pp_coastal_logistics_priority", 70),
    ("transport_office", "pp_city_logistics_priority", 60),
    ("carrier_inn", "pp_rural_logistics_priority", 50),
)
LOGISTICS_AI_BUILD_ORDER = (
    "river_boatmen_yard",
    "coastal_shipping_office",
    "transport_office",
    "carrier_inn",
)
LOGISTICS_AI_LEVEL_GUARD_TARGETS = {
    "carrier_inn": "10",
}


def _custom_tags(text: str) -> set[str]:
    match = re.search(r"custom_tags\s*=\s*\{\s*(?P<tags>[^}]*)\}", text)
    assert match is not None
    return set(match.group("tags").split())


def _field(body: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*([^\s#]+)", body, flags=re.M)
    assert match is not None, f"missing {key}"
    return match.group(1)


def _modifier_block(body: str, key: str = "modifier") -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*\{{(?P<body>.*?)\n\s*\}}", body, flags=re.S)
    assert match is not None, f"missing {key} block"
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


def _ai_logistics_builder_block() -> str:
    return _named_block(
        LOGISTICS_SCRIPTED_EFFECTS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_build_unsupported_infrastructure",
    )


def _ai_logistics_record_block() -> str:
    return _named_block(
        LOGISTICS_SCRIPTED_EFFECTS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_record_infrastructure_build",
    )


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
        assert f"pp_river_boatmen_yard_cap_modifier = {river_level * 3}" in block.group("body")

    assert "pp_river_boatmen_yard_cap_modifier" in BUILDING_CAP_TYPES.read_text(encoding="utf-8-sig")
    assert "gfx/interface/icons/buildings/river_boatmen_yard.dds" in BUILDING_CAP_ICONS.read_text(
        encoding="utf-8-sig"
    )

    localization = BUILDING_ADJUSTMENTS_LOC.read_text(encoding="utf-8-sig")
    assert 'BUILDING_LEVEL_RIVER_FREIGHT_CAPACITY: "From River Size"' in localization
    assert 'MODIFIER_TYPE_NAME_pp_river_boatmen_yard_cap_modifier: "River Freight Capacity"' in localization


def test_coastal_shipping_office_cap_scales_with_natural_harbor() -> None:
    blueprint = (ROOT / "blueprints" / "accepted" / "buildings" / "coastal_shipping_office.yml").read_text(
        encoding="utf-8"
    )
    assert "max_levels = pp_coastal_shipping_office_max_level" in blueprint
    assert "is_port = yes" in blueprint

    cap_value = LOGISTICS_CAPS.read_text(encoding="utf-8")
    assert "pp_coastal_shipping_office_max_level" in cap_value
    assert 'desc = "BUILDING_LEVEL_BASE"' in cap_value
    assert "value = 10" in cap_value
    assert 'desc = "BUILDING_LEVEL_NATURAL_HARBOR_SUITABILITY"' in cap_value
    assert "value = modifier:pp_coastal_shipping_office_cap_modifier" in cap_value
    assert "min = 0" in cap_value

    modifiers = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    poor_block = re.search(
        r"TRY_INJECT:location_template_natural_harbor_suitability_poor = \{(?P<body>.*?)\n\}",
        modifiers,
        flags=re.S,
    )
    good_block = re.search(
        r"TRY_INJECT:location_template_natural_harbor_suitability_good = \{(?P<body>.*?)\n\}",
        modifiers,
        flags=re.S,
    )
    assert poor_block is not None
    assert good_block is not None
    assert "pp_coastal_shipping_office_cap_modifier = -20" in poor_block.group("body")
    assert "pp_coastal_shipping_office_cap_modifier = 10" in good_block.group("body")

    assert "pp_coastal_shipping_office_cap_modifier" in BUILDING_CAP_TYPES.read_text(
        encoding="utf-8-sig"
    )
    assert "gfx/interface/icons/buildings/coastal_shipping_office.dds" in BUILDING_CAP_ICONS.read_text(
        encoding="utf-8-sig"
    )

    localization = BUILDING_ADJUSTMENTS_LOC.read_text(encoding="utf-8-sig")
    assert (
        'BUILDING_LEVEL_NATURAL_HARBOR_SUITABILITY: "From Natural Harbor Suitability"'
        in localization
    )
    assert (
        'MODIFIER_TYPE_NAME_pp_coastal_shipping_office_cap_modifier: "Coastal Shipping Capacity"'
        in localization
    )


def test_logistics_infrastructure_buildings_are_tagged_for_modifier_evaluation() -> None:
    priority_tags = {building: tag for building, tag, _priority in LOGISTICS_PRIORITY_GROUPS}
    for blueprint in LOGISTICS_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8")
        building = yaml.safe_load(text)["building"]["key"]
        assert "category = infrastructure_category" in text
        assert _custom_tags(text) == {
            "pp_logistics_infrastructure_priority",
            "pp_logistics",
            priority_tags[building],
        }


def test_logistics_infrastructure_balance_targets_are_current() -> None:
    for blueprint_path in LOGISTICS_BLUEPRINTS:
        blueprint = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
        key = blueprint["building"]["key"]
        expected = LOGISTICS_BALANCE_TARGETS[key]
        body = blueprint["building"]["body"]
        raw_modifier_body = _modifier_block(body, "raw_modifier")
        method_body = blueprint["production_methods"][0]["body"]
        localization_keys = set(blueprint["localization"]["entries"])

        assert "price =" not in body
        assert "prices" not in blueprint
        assert not any(localization_key.endswith("_price") for localization_key in localization_keys)
        assert not any("price_cost_modifier" in localization_key for localization_key in localization_keys)
        assert _field(body, "max_levels") == expected["max_levels"]
        assert _field(body, "increase_per_level_cost") == expected["increase_per_level_cost"]
        assert _field(body, "pop_type") == expected["pop_type"]
        assert _field(body, "employment_size") == "3"
        assert _field(body, "can_close") == "no"
        assert _field(body, "always_add_demands") == "yes"
        assert _field(body, "forbidden_for_estates") == "yes"
        assert _field(body, "ai_forbid_shutdown") == "yes"
        assert "local_market_access" not in raw_modifier_body
        assert _field(raw_modifier_body, "free_building_levels") == "10"
        assert re.search(r"(?m)^\s*modifier\s*=", body) is None
        assert _goods_total(method_body) == pytest.approx(expected["upkeep"])


def test_logistics_infrastructure_building_priorities_are_below_food_priorities() -> None:
    priority_text = EMPLOYMENT_PRIORITIES.read_text(encoding="utf-8-sig")

    assert priority_text.count("limit = { has_tag = pp_logistics }") == 6
    assert max(priority for _building, _tag, priority in LOGISTICS_PRIORITY_GROUPS) < 90
    assert [building for building, _tag, _priority in LOGISTICS_PRIORITY_GROUPS] == list(
        LOGISTICS_AI_BUILD_ORDER
    )

    for building, tag, priority in LOGISTICS_PRIORITY_GROUPS:
        text = (ROOT / "blueprints" / "accepted" / "buildings" / f"{building}.yml").read_text(
            encoding="utf-8"
        )
        assert tag in _custom_tags(text)
        pattern = re.compile(rf"has_tag\s*=\s*{re.escape(tag)}[\s\S]*?add\s*=\s*{priority}")
        assert pattern.search(priority_text), tag


def test_road_maintenance_buildings_keep_separate_logistics_tag() -> None:
    for blueprint in ROAD_MAINTENANCE_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8")
        assert "category = infrastructure_category" in text
        assert _custom_tags(text) == {"pp_logistics_infrastructure_priority", "pp_road_maintenance"}


def test_logistics_infrastructure_raw_free_levels_are_not_method_scaled() -> None:
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
            assert method.building_category == "infrastructure_category"
            assert not method.building_modifiers


def test_ai_logistics_unsupported_levels_action_runs_on_four_year_pulse() -> None:
    pulse = FOUR_YEARLY_COUNTRY_PULSE.read_text(encoding="utf-8-sig")
    action = _named_block(
        BUILDING_CULLING_ACTIONS.read_text(encoding="utf-8-sig"),
        "pp_ai_logistics_on_unsupported_building_levels",
    )

    assert "pp_ai_logistics_on_unsupported_building_levels" in pulse
    assert "pp_ai_logistics_build_unsupported_infrastructure = yes" in action
    assert "every_area_with_owned_province = {" not in action


def test_ai_logistics_unsupported_levels_action_keeps_required_guards() -> None:
    block = _ai_logistics_builder_block()

    assert "is_ai = yes" in block
    assert "monthly_balance > 0" in block
    assert "ordered_owned_location = {" not in block
    assert block.count("every_area_with_owned_province = {") == 4
    assert block.count("ordered_location_in_area = {") == 4
    assert "order_by = pp_unsupported_building_levels_map_value" in block
    assert "check_range_bounds = no" in block
    assert "instant = yes" not in block
    assert "cost_multiplier = 0" not in block
    assert block.count("construct_building = {") == 16
    assert block.count("change_building_level_in_location = {") == 16
    assert block.count("add_gold = {") == 16

    for building in LOGISTICS_AI_BUILD_ORDER:
        assert block.count(f"can_build_building = building_type:{building}") == 8
        assert block.count(f"NOT = {{ has_building_with_at_least_one_level = {building} }}") == 8
        assert f"has_building_with_at_least_one_level = {building}" in block
        assert f"value = building_type:{building}.building_base_cost_in_gold" in block
        max_levels = LOGISTICS_AI_LEVEL_GUARD_TARGETS.get(
            building, LOGISTICS_BALANCE_TARGETS[building]["max_levels"]
        )
        level_guard = re.compile(
            rf"has_building_with_at_least_one_level\s*=\s*{re.escape(building)}\s+"
            rf"location_building_level\s*=\s*\{{\s*"
            rf"building_type\s*=\s*building_type:{re.escape(building)}\s+"
            rf"value\s*<\s*{re.escape(max_levels)}\s*"
            r"\}",
            flags=re.S,
        )
        assert len(level_guard.findall(block)) == 8

    assert block.count("gold >= {") >= len(LOGISTICS_AI_BUILD_ORDER)


def test_ai_logistics_unsupported_levels_uses_area_tracking_and_budget() -> None:
    block = _ai_logistics_builder_block()
    record_block = _ai_logistics_record_block()

    assert "clear_variable_list = pp_ai_logistics_handled_areas" in block
    assert "is_target_in_variable_list = {" in block
    assert "name = pp_ai_logistics_handled_areas" in block
    assert "target = prev" in block
    assert "scope:pp_ai_logistics_country = {" in block
    assert (
        "add_to_variable_list = { name = pp_ai_logistics_handled_areas target = scope:pp_ai_logistics_current_area }"
        in record_block
    )
    assert "set_variable = { name = pp_ai_logistics_build_count value = 0 }" in block
    assert "set_variable = { name = pp_ai_logistics_budget value = gold }" in block
    assert "change_variable = { name = pp_ai_logistics_budget multiply = 0.25 }" in block
    assert "max = { value = monthly_balance multiply = 24 }" in block
    assert block.count("var:pp_ai_logistics_build_count < 20") == 4
    assert "change_variable = { name = pp_ai_logistics_build_count add = 1 }" in record_block
    assert (
        "change_variable = { name = pp_ai_logistics_budget subtract = { value = building_type:$building$.building_base_cost_in_gold } }"
        in record_block
    )


def test_ai_logistics_unsupported_levels_severity_passes_are_exact() -> None:
    block = _ai_logistics_builder_block()

    severity_blocks = _logistics_severity_blocks(block)
    assert [threshold for threshold, _ in severity_blocks] == ["30", "15", "5", "1"]

    for threshold, severity_block in severity_blocks:
        assert f"pp_unsupported_building_levels_map_value >= {threshold}" in severity_block


def test_ai_logistics_unsupported_levels_build_priority_is_exact() -> None:
    block = _ai_logistics_builder_block()

    for _, severity_block in _logistics_severity_blocks(block):
        ordered_actions = re.findall(
            r"(construct_building|change_building_level_in_location)\s*=\s*\{\s*"
            r"(?:building_type|building)\s*=\s*building_type:([a-z_]+)",
            severity_block,
            flags=re.S,
        )
        assert ordered_actions == [
            (action, building)
            for building in LOGISTICS_AI_BUILD_ORDER
            for action in ("construct_building", "change_building_level_in_location")
        ]


def test_logistics_debug_event_mimics_global_ai_iteration() -> None:
    text = LOGISTICS_DEBUG_EVENT.read_text(encoding="utf-8-sig")
    block = _named_block(text, "pp_logistics_debug.1")

    assert "type = country_event" in block
    assert "orphan = yes" in block
    assert "every_country = {" in block
    assert "pp_ai_logistics_build_unsupported_infrastructure = yes" in block
    assert "construct_building" not in block
    assert "change_building_level_in_location" not in block
    assert "every_area_with_owned_province = {" not in block
    assert "instant = yes" not in block
    assert "cost_multiplier = 0" not in block

    builder_block = _ai_logistics_builder_block()
    assert "every_area_with_owned_province = {" in builder_block
    assert "ordered_location_in_area = {" in builder_block

    localization = DEBUG_LOCALIZATION.read_text(encoding="utf-8-sig")
    assert "pp_logistics_debug.1.title" in localization
    assert "pp_logistics_debug.1.desc" in localization
    assert "four-year country pulse" in localization
    assert "for every country" in localization


def test_market_village_market_access_is_neutralized_by_inject_blueprint() -> None:
    blueprint = MARKET_VILLAGE_MARKET_ACCESS_BLUEPRINT.read_text(encoding="utf-8")
    assert "mode: REPLACE" in blueprint
    assert "key: market_village" in blueprint
    assert "local_market_access = -0.005" in blueprint
    assert "unique_production_methods" in blueprint
    assert "pp_market_village_rural_blacksmith" in blueprint

    rendered = MARKET_VILLAGE_MARKET_ACCESS_RENDERED.read_text(encoding="utf-8-sig")
    assert "REPLACE:market_village" in rendered
    assert "local_market_access = -0.005" in rendered
    assert "unique_production_methods" in rendered
    assert "pp_market_village_rural_blacksmith" in rendered

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


def test_victuals_market_templates_split_export_and_import_flows() -> None:
    export_texts = tuple(
        path.read_text(encoding="utf-8-sig")
        for path in (VICTUALS_MARKET_BLUEPRINT, VICTUALS_MARKET_RENDERED)
    )
    import_texts = tuple(
        path.read_text(encoding="utf-8-sig")
        for path in (VICTUALS_MARKET_IMPORT_BLUEPRINT, VICTUALS_MARKET_IMPORT_RENDERED)
    )

    assert "victuals_market: Victuals Market (Export)" in export_texts[0]
    for text in export_texts:
        assert "pp_province_food_to_market" in text
        assert "produced = province_food_sales" in text
        assert "pp_province_food_from_market" not in text

    assert "victuals_market_import: Victuals Market (Import)" in import_texts[0]
    for text in import_texts:
        assert "pp_province_food_from_market" in text
        assert "produced = province_food_purchase" in text
        assert "pp_province_food_to_market" not in text

    for text in (*export_texts, *import_texts):
        assert "local_nobles_estate_power = 0.05" in text
        assert "local_peasant_enfranchisment = -0.01" in text
        assert "local_market_access" not in text

    assert VICTUALS_MARKET_IMPORT_ICON.read_bytes() == VICTUALS_MARKET_ICON.read_bytes()
