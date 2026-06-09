import re
from pathlib import Path

from eu5_mod_orchestrator.adapters.building_pipeline import evaluate_building_blueprint_data
from eu5_mod_orchestrator.adapters.parser import (
    load_balance_prices,
    load_global_building_unlock_ages,
    load_global_unlock_ages,
    load_raw_material_goods,
    load_script_values,
)
from eu5_mod_orchestrator.config import load_project_config


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
RIVER_BLUEPRINT = ROOT / "blueprints" / "accepted" / "buildings" / "river_boatmen_yard.yml"
LOGISTICS_BLUEPRINTS = (
    ROOT / "blueprints" / "accepted" / "buildings" / "carrier_inn.yml",
    RIVER_BLUEPRINT,
    ROOT / "blueprints" / "accepted" / "buildings" / "transport_office.yml",
    ROOT / "blueprints" / "accepted" / "buildings" / "coastal_shipping_office.yml",
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
        assert "custom_tags = { pp_logistics_infrastructure_priority }" in text


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
            assert "local_market_access" in modifier_names
            assert "free_building_levels" in modifier_names
            for modifier in method.building_modifiers:
                assert modifier.per_building_gold is not None
                assert modifier.per_maintenance_gold is not None
                assert modifier.per_1k is not None
