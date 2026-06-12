import json
import os
import re
from pathlib import Path

from eu5_building_pipeline.template import load_template
from eu5gameparser.clausewitz.parser import parse_file, parse_text
from eu5gameparser.clausewitz.serializer import normalized_value
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.availability import annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data
from eu5gameparser.load_order import LoadOrderConfig, load_merged_directory
from eu5_mod_orchestrator.blueprints import accepted_blueprint_files, validate_blueprint_file
from eu5_mod_orchestrator.config import load_project_config
from mod_injector.config import load_mod_injector_config
from prosper_or_perish_constructor import cli
from scripts.generate_setup_building_corrections import (
    expand_town_setup,
    parse_setup_model,
    parse_town_setups,
)


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ESTATE_PRIVILEGE_ADJUSTMENTS = (
    MOD_ROOT / "in_game" / "common" / "estate_privileges" / "pp_estate_privilege_adjustments.txt"
)
GOVERNMENT_REFORM_ADJUSTMENTS = (
    MOD_ROOT / "in_game" / "common" / "government_reforms" / "pp_government_reform_adjustments.txt"
)
ESTATE_ADJUSTMENTS = MOD_ROOT / "in_game" / "common" / "estates" / "pp_estate_adjustments.txt"
GOODS_DEMAND = MOD_ROOT / "in_game" / "common" / "goods_demand" / "pp_new_goods_demands.txt"
LAW_ADJUSTMENTS = MOD_ROOT / "in_game" / "common" / "laws" / "pp_law_adjustments.txt"
SCRIPT_VALUES_ROOT = MOD_ROOT / "in_game" / "common" / "script_values"
BUILDING_CAPS = SCRIPT_VALUES_ROOT / "pp_building_caps.txt"
FARMING_CAPACITY = SCRIPT_VALUES_ROOT / "pp_farming_capacity.txt"
FISHING_CAPACITY = SCRIPT_VALUES_ROOT / "pp_fishing_capacity.txt"
FOREST_CAPACITY = SCRIPT_VALUES_ROOT / "pp_forest_capacity.txt"
BUILDING_CAPACITY_SCRIPT_VALUE_FILES = (
    BUILDING_CAPS,
    FARMING_CAPACITY,
    FISHING_CAPACITY,
    FOREST_CAPACITY,
)
BUILDING_CAP_ADJUSTMENTS = SCRIPT_VALUES_ROOT / "pp_building_cap_adjustments.txt"
BUILDING_CAPACITY_VALUES = SCRIPT_VALUES_ROOT / "pp_building_capacity_values.txt"
BUILDING_TYPE_ROOT = MOD_ROOT / "in_game" / "common" / "building_types"
EMPLOYMENT_SYSTEMS_ROOT = MOD_ROOT / "in_game" / "common" / "employment_systems"
AQUEDUCT_SYSTEM = MOD_ROOT / "in_game" / "common" / "building_types" / "pp_aqueduct_system.txt"
GAME_START = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_game_start.txt"
BUILDING_CULLING = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_building_culling.txt"
BUILDING_CAPACITY_CULLING_V2 = (
    MOD_ROOT / "in_game" / "common" / "on_action" / "pp_building_capacity_culling_v2.txt"
)
ESTATE_SETUP_CULLING = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_estate_setup_culling.txt"
ESTATE_START_PRESERVATION = (
    MOD_ROOT / "in_game" / "common" / "scripted_triggers" / "pp_estate_start_preservation.txt"
)
CAPACITY_CULLING_EFFECTS = (
    MOD_ROOT / "in_game" / "common" / "scripted_effects" / "pp_capacity_culling_effects.txt"
)
COUNTRY_FOUR_YEARLY = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_country_four_yearly.txt"
LOCATION_RANKS = MOD_ROOT / "in_game" / "common" / "location_ranks" / "pp_location_rank_adjustments.txt"
FOOD_MAP_MODES = MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes" / "pp_food_map_modes.txt"
SITUATION_ROOT = MOD_ROOT / "in_game" / "common" / "situations"
PRICE_ROOT = MOD_ROOT / "in_game" / "common" / "prices"
MODIFIER_TYPE_DEFINITIONS = MOD_ROOT / "main_menu" / "common" / "modifier_type_definitions"
MODIFIER_ICONS = MOD_ROOT / "main_menu" / "common" / "modifier_icons"
GAME_CONCEPT_ROOT = MOD_ROOT / "main_menu" / "common" / "game_concepts"
LOCALIZATION_ROOT = MOD_ROOT / "main_menu" / "localization" / "english"
BUILDING_MAINTENANCE_RULES = (
    MOD_ROOT / "main_menu" / "common" / "game_rules" / "pp_building_maintenance_rules.txt"
)
CAPACITY_PRECALC = MOD_ROOT / "in_game" / "common" / "scripted_effects" / "pp_capacity_precalc.txt"
RGO_STATIC_BONUSES = MOD_ROOT / "in_game" / "common" / "static_modifiers" / "pp_rgo_static_bonuses.txt"
RGO_STATIC_BONUS_EFFECTS = (
    MOD_ROOT / "in_game" / "common" / "scripted_effects" / "pp_rgo_static_bonus_effects.txt"
)
RAW_MATERIAL_CHANGED = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_raw_material_changed.txt"
COLUMBIAN_EXCHANGE_RGO_REFRESH_ACTIONS = (
    MOD_ROOT
    / "in_game"
    / "common"
    / "generic_actions"
    / "pp_columbian_exchange_rgo_refresh.txt"
)
COLUMBIAN_EXCHANGE_DEBUG_EVENT = (
    MOD_ROOT / "in_game" / "events" / "debug" / "pp_columbian_exchange_debug.txt"
)
BUILDING_BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"
FARMING_VILLAGE_BLUEPRINT = BUILDING_BLUEPRINT_ROOT / "farming_village.yml"
MODEL_FARM_BLUEPRINT = BUILDING_BLUEPRINT_ROOT / "model_farm.yml"
LAND_FARM_BUILDINGS = (
    "farming_village",
    "farming_village_rotations",
    "model_farm",
    "fruit_orchard",
    "pomological_orchard",
    "sheep_farms",
    "enclosed_sheep_walks",
    "horse_breeders",
    "elephant_kraal",
    "fiber_crops_farm",
    "cotton_plantation",
    "cotton_farm",
    "sugar_plantation",
    "sugarcane_farm",
    "tobacco_plantation",
    "tobacco_farm",
    "dye_plantation",
    "chili_plantation",
    "clove_grove",
    "cocoa_grove",
    "coffee_grove",
    "incense_grove",
    "pepper_garden",
    "saffron_croft",
    "sericulture_farm",
    "simplers_grove",
    "tea_garden",
    "vineyard_estate",
)
LAND_FARM_BLUEPRINTS = tuple(BUILDING_BLUEPRINT_ROOT / f"{key}.yml" for key in LAND_FARM_BUILDINGS)
FARM_CAPACITY_MAX_VALUES = tuple(f"farm_capacity_max_{key}" for key in LAND_FARM_BUILDINGS)
FISH_CAP_BUILDINGS = (
    "fishing_village",
    "ocean_fishery",
    "offshore_fishery",
)
FOREST_CAP_BUILDINGS = (
    "forest_village",
    "managed_forest_village",
    "lumber_mill",
    "water_sawmill",
    "lumber_mill_improved",
)
FISH_CAPACITY_MAX_VALUES = tuple(f"fish_capacity_max_{key}" for key in FISH_CAP_BUILDINGS)
FOREST_CAPACITY_MAX_VALUES = tuple(f"forest_capacity_max_{key}" for key in FOREST_CAP_BUILDINGS)
FISH_CAP_BLUEPRINTS = tuple(BUILDING_BLUEPRINT_ROOT / f"{key}.yml" for key in FISH_CAP_BUILDINGS)
FOREST_CAP_BLUEPRINTS = tuple(BUILDING_BLUEPRINT_ROOT / f"{key}.yml" for key in FOREST_CAP_BUILDINGS)
EXCLUDED_FARM_CAP_BUILDINGS = (
    "perfumery",
    "cookery",
    "victualling_yard",
    "saltpeter_guild",
    "saltpeter_workshop",
    "putrefaction_mill",
    "putrefaction_works",
    "fishing_village",
    "ocean_fishery",
    "offshore_fishery",
    "pearl_fishery",
    "forest_village",
    "managed_forest_village",
    "lumber_mill",
    "water_sawmill",
    "lumber_mill_improved",
    "charcoal_maker",
    "improved_charcoal_maker",
    "ivory_hunting_camp",
    "coastal_saltern",
    "salt_mine",
    "salt_mine_improved",
    "inland_saltworks",
    "engineered_brine_saltworks",
    "saltpeter_beds",
    "sand_pit",
    "sand_washery",
    "stone_quarry",
)

FOOD_SECURITY_PRIORITY_GROUPS = {
    "food_storage": (
        120,
        "Food storage needs highest priority to stop fluctuations in food for AI.",
        ("granary",),
    ),
    "direct_food_production": (
        110,
        "Direct food production needs second highest priority so we do not enter starvation loops.",
        ("cookery", "victualling_yard"),
    ),
    "food_distribution": (
        100,
        "Victuals markets need priority below cookeries so prepared food is distributed after direct food production.",
        ("victuals_market",),
    ),
    "water_control": (
        95,
        (
            "Irrigation and other water-control buildings need high priority so food production "
            "or capacity are not destroyed through underemployment."
        ),
        ("irrigation_systems", "bund", "terraces", "polders", "khmer_baray"),
    ),
    "staple_food_production": (
        90,
        (
            "Staple-food producer buildings need to be manned first to avoid being outcompeted "
            "by non-food-related buildings."
        ),
        (
            "farming_village",
            "farming_village_rotations",
            "model_farm",
            "fishing_village",
            "ocean_fishery",
            "offshore_fishery",
            "fruit_orchard",
            "pomological_orchard",
            "forest_village",
            "managed_forest_village",
            "sheep_farms",
            "enclosed_sheep_walks",
        ),
    ),
}
FOOD_SECURITY_GENERAL_PRIORITY_TAG = "pp_food_security_priority"
FOOD_SECURITY_PRIORITY_TAGS_BY_GROUP = {
    "food_storage": "pp_food_storage_priority",
    "direct_food_production": "pp_direct_food_priority",
    "food_distribution": "pp_food_distribution_priority",
    "water_control": "pp_water_control_priority",
    "staple_food_production": "pp_staple_food_priority",
}
EMPLOYMENT_SYSTEMS_WITH_FOOD_SECURITY_PRIORITY = (
    "equality",
    "first_come_first_serve",
    "capitalism",
    "capitalism_prioritising_infrastructure",
    "capitalism_prioritising_infrastructure_trade",
    "capitalism_prioritising_infrastructure_trade_and_culture",
)
FOOD_SECURITY_LABORER_BUILDINGS = {
    "cookery": ("laborers", 2),
    "victualling_yard": ("laborers", 4.0),
    "victuals_market": ("laborers", 0.25),
    "granary": ("laborers", 0.25),
}


def test_constructor_config_loads() -> None:
    config = load_project_config(ROOT / "constructor.toml")

    assert config.name == "Prosper or Perish Constructor"
    assert config.mod_root == ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    if (ROOT / "constructor.local.toml").exists():
        assert config.deploy_target is not None
    else:
        assert config.deploy_target is None
    assert config.accepted_blueprints_dir == ROOT / "blueprints" / "accepted"
    assert config.profile == "constructor"
    assert config.load_order_path == ROOT / "constructor.load_order.toml"
    assert config.building_outputs.prefix == "pp_"
    assert config.building_outputs.building_types == "in_game/common/building_types/zz_{prefix}{tag}.txt"
    assert config.building_artifact_dir == ROOT / "artifacts" / "data" / "buildings"
    assert config.savegame_artifact_dir == ROOT / "artifacts" / "data" / "savegame"
    assert config.graph_dir == ROOT / "graphs"
    assert config.labeling is not None
    assert config.labeling.enabled is True
    assert config.labeling.config_path == ROOT / "labeling_output_modifiers.yaml"
    assert config.labeling.modifier_prefix == "pp"
    assert config.labeling.generated_label == "Prosper or Perish"
    assert config.labeling.managed_write_mode == "mod_root"
    assert config.population_capacity is not None
    assert config.population_capacity.enabled is True
    assert config.population_capacity.config_path == ROOT / "population_capacity.toml"
    assert config.population_capacity.generated_label == "Prosper or Perish"
    assert config.population_capacity.managed_write_mode == "mod_root"
    assert config.blueprint_evaluation.raw_input_efficiency_per_good == 0.05
    assert config.blueprint_evaluation.profit_percent_min == -0.30
    assert config.blueprint_evaluation.profit_percent_max == 0.30
    assert config.blueprint_evaluation.base_output_per_1k_min == 0.07
    assert config.blueprint_evaluation.base_output_per_1k_max == 0.15
    assert config.blueprint_evaluation.throughput_gold_per_1k["laborers"] == 1.5
    assert config.blueprint_evaluation.age_throughput_growth == 0.10
    assert config.blueprint_evaluation.throughput_tolerance == 0.30
    assert config.blueprint_evaluation.amortization_months_min == 120.0
    assert config.blueprint_evaluation.amortization_months_max == 360.0
    assert config.blueprint_evaluation.employment_size_constants == {}
    infrastructure_modifiers = config.blueprint_evaluation.modifier_categories["infrastructure_category"]
    assert infrastructure_modifiers.modifiers == (
        "market_access",
        "local_market_access",
        "free_building_levels",
        "local_distance_from_capital_speed_propagation",
    )


def test_constructor_path_configuration_is_portable_and_documented() -> None:
    load_order_text = (ROOT / "constructor.load_order.toml").read_text(encoding="utf-8")
    load_order_example = (ROOT / "constructor.load_order.example.toml").read_text(encoding="utf-8")
    local_example = (ROOT / "constructor.local.example.toml").read_text(encoding="utf-8")

    assert r'C:\Games\steamapps\common\Europa Universalis V' in load_order_text
    assert "/mnt/c/Games/steamapps/common/Europa Universalis V" in load_order_text
    assert "Windows drive paths on WSL/Linux" in load_order_text
    assert 'root = "mod/Prosper or Perish (Population Growth & Food Rework)"' in load_order_text

    assert r'C:\Games\steamapps\common\Europa Universalis V' in load_order_example
    assert "/mnt/c/Games/steamapps/common/Europa Universalis V" in load_order_example
    assert "/mnt/d/SteamLibrary/steamapps/common/Europa Universalis V" in load_order_example
    assert 'root = "mod/Prosper or Perish (Population Growth & Food Rework)"' in load_order_example

    assert "/mnt/c/Users/<windows-user>/Documents/Paradox Interactive/Europa Universalis V" in local_example

    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    expected_vanilla_root = (
        Path(r"C:\Games\steamapps\common\Europa Universalis V")
        if os.name == "nt"
        else Path("/mnt/c/Games/steamapps/common/Europa Universalis V")
    )
    assert load_order.vanilla_root == expected_vanilla_root


def test_published_docs_examples_do_not_embed_local_constructor_roots() -> None:
    docs_examples = ROOT / "docs" / "examples"
    forbidden = (
        "/" + "mnt/c/Development/ProsperOrPerishConstructor",
        "C:" + r"\Development\ProsperOrPerishConstructor",
        "/" + "home/jan/development/ProsperOrPerishConstructor",
    )
    offenders: list[str] = []
    for path in docs_examples.glob("*"):
        if path.suffix not in {".html", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)}: {needle}")

    assert not offenders


def test_accepted_blueprints_validate() -> None:
    for blueprint in accepted_blueprint_files(ROOT / "blueprints" / "accepted"):
        validate_blueprint_file(blueprint)


def test_farm_capacity_values_are_flat_visible_sums() -> None:
    parsed = parse_file(FARMING_CAPACITY)
    entries = {entry.key: entry.value for entry in parsed.entries}
    assert "farm_capacity" in entries
    assert set(entries) == {"farm_capacity", *FARM_CAPACITY_MAX_VALUES}
    assert "farm_gross_capacity" not in entries
    assert "farm_max_level" not in entries
    assert "farm_capacity_available" not in entries
    assert "farm_urbanization_pressure" not in entries
    assert "land_farm_capacity_used" not in entries
    assert "farm_capacity_used" not in entries
    assert "farm_capacity_from_max_rgo_workers" not in entries
    assert "fruit_orchard_max_level" not in entries
    assert "farm_capacity_remaining" not in entries
    assert "land_farm_building_levels" not in entries
    assert "farm_capacity_from_other_building_levels" not in entries
    assert "farming_capacity" not in entries
    assert "farming_village_max_level" not in entries

    text = FARMING_CAPACITY.read_text(encoding="utf-8-sig")
    block = _script_value_block(text, "farm_capacity")

    required_snippets = (
        "Public remaining-capacity path",
        "Capacity buildings subtract their levels directly from this sum",
        'desc = "BUILDING_LEVEL_BASE_FARM_RGO"\n\t\tif = {\n\t\t\tlimit = { has_variable = pp_farm_base_capacity }\n\t\t\tvalue = var:pp_farm_base_capacity',
        "limit = { has_variable = pp_farm_base_capacity }",
        'desc = "BUILDING_LEVEL_RGO_SIZE_FARMING"\n\t\t\tvalue = var:pp_farm_base_capacity\n\t\t\tmultiply = max_rgo_workers\n\t\t\tmultiply = 0.125',
        'desc = "BUILDING_LEVEL_POPULATION_CAPACITY_FARMING"\n\t\tvalue = modifier:local_population_capacity\n\t\tmultiply = 0.08',
        'desc = "BUILDING_LEVEL_FARM_LOCATION_RANK"\n\t\t\tvalue = -20',
        'desc = "BUILDING_LEVEL_FARM_LOCATION_RANK"\n\t\t\tvalue = -5',
        'desc = "BUILDING_LEVEL_FARM_LOCATION_RANK"\n\t\t\tvalue = -1',
        'desc = "BUILDING_LEVEL_FARM_RIVER"\n\t\tvalue = modifier:farm_capacity_from_river_size',
        'desc = "BUILDING_LEVEL_FARM_MANORIAL_CUSTOMALS"\n\t\t\tvalue = 1',
        'desc = "BUILDING_LEVEL_FARM_URBANIZATION"\n\t\tvalue = total_building_levels',
        "multiply = 0.05",
    )
    missing = [snippet for snippet in required_snippets if snippet not in block]
    assert not missing
    expected_water_control_rows = {
        "irrigation_systems": "0.60",
        "bund": "0.60",
        "terraces": "0.60",
        "polders": "0.60",
        "khmer_baray": "0.60",
        "aqueduct_system": "2",
    }
    for building, multiplier in expected_water_control_rows.items():
        assert f"limit = {{ has_building = building_type:{building} }}" in block
        assert f'desc = "BUILDING_LEVEL_FARM_{building.upper()}"' in block
        assert f'value = "location_building_level(building_type:{building})"' in block
        assert f"multiply = {multiplier}" in block

    for building in LAND_FARM_BUILDINGS:
        assert f"limit = {{ has_building = building_type:{building} }}" in block
        assert f'desc = "BUILDING_LEVEL_FARM_{building.upper()}"' in block
        assert f'value = "location_building_level(building_type:{building})"' in block
        assert f'subtract = "location_building_level(building_type:{building})"' in block

    for building in LAND_FARM_BUILDINGS:
        max_block = _script_value_block(text, f"farm_capacity_max_{building}")
        assert f'desc = "BUILDING_LEVEL_FARM_{building.upper()}"' not in max_block
        for other_building in LAND_FARM_BUILDINGS:
            if other_building == building:
                continue
            assert f'desc = "BUILDING_LEVEL_FARM_{other_building.upper()}"' in max_block
        assert f'subtract = "location_building_level(building_type:{building})"' in max_block

    forbidden_snippets = (
        "modifier:farm_space_used",
        "modifier:farm_capacity_cost",
        "modifier:farm_capacity_from_location_rank",
        "farm_capacity_cost",
        "farm_capacity_from_location_rank",
        "BUILDING_LEVEL_FARM_CAPACITY",
        "BUILDING_LEVEL_FARM_CAPACITY_USED",
        "BUILDING_LEVEL_FROM_LOCATION_RANK_FARMING",
        "BUILDING_LEVEL_FARM_CAPACITY_IMPROVEMENTS",
        "BUILDING_LEVEL_RIVER_FARM_CAPACITY",
        "BUILDING_LEVEL_MANORIAL_CUSTOMALS_FARMING",
        "BUILDING_LEVEL_IRRIGATION_SYSTEMS_FARMING",
        "farm_capacity_remaining",
        "pp_farming_village_fixed_env_bonus",
        "pp_farming_village_capacity_value",
        "BUILDING_LEVEL_FROM_ENVIRONMENT_FARMING",
        "value = development",
        "value = population",
        "value = max_rgo_workers\n\t\tmultiply = 0.75",
        "min = 0",
    )
    offenders = [snippet for snippet in forbidden_snippets if snippet in block]
    assert not offenders
    assert len(re.findall(r"value\s*=\s*modifier:farm_capacity\b", text)) == 0


def test_rural_capacity_max_level_invariant_example() -> None:
    total_capacity = 10
    levels = {"farming_village": 3, "fruit_orchard": 1}

    remaining_capacity = total_capacity - sum(levels.values())
    farming_village_max = remaining_capacity + levels["farming_village"]
    fruit_orchard_max = remaining_capacity + levels["fruit_orchard"]

    assert remaining_capacity == 6
    assert farming_village_max == 9
    assert fruit_orchard_max == 7


def test_granary_storage_and_startup_placement_are_compatible() -> None:
    granary_text = (BUILDING_BLUEPRINT_ROOT / "granary.yml").read_text(encoding="utf-8-sig")
    assert "local_food_capacity = 1500" in granary_text
    assert "local_food_capacity = 1000" not in granary_text
    assert "local_food_capacity = 1200" not in granary_text
    assert "is_province_capital = yes" not in granary_text
    for rank in ("rural_settlement", "town", "city", "megalopolis"):
        assert f"location_rank = location_rank:{rank}" in granary_text


def test_food_security_priority_syntax_matches_vanilla_employment_systems() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_game = load_order.vanilla_root / "game"
    building_readme = (
        vanilla_game / "in_game" / "common" / "building_types" / "readme.txt"
    ).read_text(encoding="utf-8-sig")
    employment_readme = (
        vanilla_game / "in_game" / "common" / "employment_systems" / "readme.txt"
    ).read_text(encoding="utf-8-sig")
    employment_defaults = (
        vanilla_game / "in_game" / "common" / "employment_systems" / "00_default.txt"
    ).read_text(encoding="utf-8-sig")
    building_scope_example = (
        vanilla_game / "in_game" / "common" / "generic_actions" / "japanese_shogunate.txt"
    ).read_text(encoding="utf-8-sig")

    assert "# - custom_tags = { <strings> }" in building_readme
    assert "# priority = script value to return the building priority" in employment_readme
    assert "priority = {\n\t\tvalue = building_potential_profit" in employment_defaults
    assert "building_type = building_type:kokufu" in building_scope_example


def test_building_types_do_not_render_unsupported_priority_fields() -> None:
    priority_field = re.compile(r"^\s*priority\s*=", re.MULTILINE)
    roots = (BUILDING_BLUEPRINT_ROOT, BUILDING_TYPE_ROOT)
    offenders = [
        path.relative_to(ROOT).as_posix()
        for root in roots
        for path in sorted(root.glob("*.*"))
        if priority_field.search(path.read_text(encoding="utf-8-sig"))
    ]

    assert offenders == []


def test_food_security_building_priorities_are_in_employment_systems() -> None:
    priority_text = (EMPLOYMENT_SYSTEMS_ROOT / "pp_food_security_priorities.txt").read_text(
        encoding="utf-8-sig"
    )
    rendered_buildings = _database_entries(BUILDING_TYPE_ROOT)

    assert "pp_food_security_building_priority" not in priority_text
    assert priority_text.count(f"has_tag = {FOOD_SECURITY_GENERAL_PRIORITY_TAG}") == len(
        EMPLOYMENT_SYSTEMS_WITH_FOOD_SECURITY_PRIORITY
    )

    for _group, (priority, comment, buildings) in FOOD_SECURITY_PRIORITY_GROUPS.items():
        tag = FOOD_SECURITY_PRIORITY_TAGS_BY_GROUP[_group]
        assert f"# {comment}" in priority_text
        pattern = re.compile(rf"has_tag\s*=\s*{re.escape(tag)}[\s\S]*?add\s*=\s*{priority}")
        assert pattern.search(priority_text), tag

        for building in buildings:
            blueprint_values = _accepted_blueprint_building_values(building)
            assert _custom_tags(blueprint_values["custom_tags"]) >= {
                FOOD_SECURITY_GENERAL_PRIORITY_TAG,
                tag,
            }

            rendered = rendered_buildings[building]
            assert isinstance(rendered, CList)
            assert _custom_tags(_entry_values(rendered)["custom_tags"]) >= {
                FOOD_SECURITY_GENERAL_PRIORITY_TAG,
                tag,
            }

    employment_systems = _database_entries(EMPLOYMENT_SYSTEMS_ROOT)
    for system in EMPLOYMENT_SYSTEMS_WITH_FOOD_SECURITY_PRIORITY:
        system_block = employment_systems[system]
        assert isinstance(system_block, CList)
        priority_block = _entry_values(system_block)["priority"]
        assert isinstance(priority_block, CList)
        assert any(
            entry.key == "if"
            and isinstance(entry.value, CList)
            and _clist_contains(entry.value, "has_tag", FOOD_SECURITY_GENERAL_PRIORITY_TAG)
            for entry in priority_block.entries
        )


def test_food_security_storage_and_market_workers_are_laborers() -> None:
    rendered_buildings = _database_entries(BUILDING_TYPE_ROOT)

    for building, (pop_type, employment_size) in FOOD_SECURITY_LABORER_BUILDINGS.items():
        blueprint_values = _accepted_blueprint_building_values(building)
        assert blueprint_values["pop_type"] == pop_type
        assert blueprint_values["employment_size"] == employment_size

        rendered = rendered_buildings[building]
        assert isinstance(rendered, CList)
        rendered_values = _entry_values(rendered)
        assert rendered_values["pop_type"] == pop_type
        assert rendered_values["employment_size"] == employment_size


def test_farming_capacity_uses_flat_source_rows_without_modifier_channel() -> None:
    text = FARMING_CAPACITY.read_text(encoding="utf-8-sig")
    parsed = parse_file(FARMING_CAPACITY)
    entries = {entry.key: entry.value for entry in parsed.entries}
    assert set(entries) == {"farm_capacity", *FARM_CAPACITY_MAX_VALUES}

    assert "land_farm_building_levels" not in entries
    assert "farm_capacity_remaining" not in entries
    assert "farm_capacity_from_other_building_levels" not in entries
    assert "fruit_orchard_max_level" not in entries
    assert "location_building_level(" in text
    assert "has_location_modifier = river_flowing_through_" not in text
    assert "modifier:farm_capacity_from_river_size" in text
    assert "has_town_rights = town_rights_type:manorial_customals" in text
    assert len(re.findall(r"value\s*=\s*modifier:farm_capacity\b", text)) == 0
    assert "farm_capacity_cost" not in text
    assert "farm_capacity_from_location_rank" not in text
    assert 'subtract = { value = "location_building_level(' not in text
    for building in ("irrigation_systems", "aqueduct_system", *LAND_FARM_BUILDINGS):
        assert f'value = "location_building_level(building_type:{building})"' in text
    for building in LAND_FARM_BUILDINGS:
        max_block = _script_value_block(text, f"farm_capacity_max_{building}")
        assert f"value = farm_capacity" not in max_block
        assert f'desc = "BUILDING_LEVEL_FARM_{building.upper()}"' not in max_block


def test_building_capacity_tooltip_paths_do_not_use_obsolete_helpers() -> None:
    farming_text = FARMING_CAPACITY.read_text(encoding="utf-8-sig")
    fishing_text = FISHING_CAPACITY.read_text(encoding="utf-8-sig")
    forest_text = FOREST_CAPACITY.read_text(encoding="utf-8-sig")
    text = "\n".join((farming_text, fishing_text, forest_text))
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )
    capacity_blocks = {
        "farm_capacity": _script_value_block(farming_text, "farm_capacity"),
        "fish_capacity": _script_value_block(fishing_text, "fish_capacity"),
        "forest_capacity": _script_value_block(forest_text, "forest_capacity"),
    }

    assert {entry.key for entry in parse_file(FARMING_CAPACITY).entries} == {
        "farm_capacity",
        *FARM_CAPACITY_MAX_VALUES,
    }
    assert {entry.key for entry in parse_file(FISHING_CAPACITY).entries} == {
        "fish_capacity",
        *FISH_CAPACITY_MAX_VALUES,
    }
    assert {entry.key for entry in parse_file(FOREST_CAPACITY).entries} == {
        "forest_capacity",
        *FOREST_CAPACITY_MAX_VALUES,
    }
    for block in capacity_blocks.values():
        assert "location_building_level(" in block
        assert "has_location_modifier = river_flowing_through_" not in block
        assert "min = 0" not in block
        assert 'subtract = { value = "location_building_level(' not in block

    assert "modifier:farm_capacity_from_river_size" in capacity_blocks["farm_capacity"]
    assert "modifier:fish_capacity_from_river_size" in capacity_blocks["fish_capacity"]
    assert "has_town_rights = town_rights_type:manorial_customals" in text
    assert "BUILDING_LEVEL_EXISTING_" not in text
    assert "BUILDING_LEVEL_EXISTING_" not in localization_text
    assert "BUILDING_LEVEL_CURRENT_FRUIT_ORCHARD_LEVELS" not in text
    assert "BUILDING_LEVEL_CURRENT_FRUIT_ORCHARD_LEVELS" not in localization_text

    for obsolete in (
        "farm_capacity_available",
        "fish_capacity_available",
        "forest_capacity_available",
        "fish_gross_capacity",
        "forest_gross_capacity",
        "fish_max_level",
        "forest_max_level",
        "fish_capacity_cost",
        "forest_capacity_cost",
        "forest_rank_capacity_modifier",
        "land_farm_building_levels",
        "fish_building_levels",
        "forest_building_levels",
        "non_forest_building_levels",
    ):
        assert obsolete not in text
    assert len(re.findall(r"modifier:fish_capacity\b", text)) == 0
    assert len(re.findall(r"modifier:forest_capacity\b", text)) == 0
    assert 'subtract = { value = "location_building_level(' not in text

    for max_value in FARM_CAPACITY_MAX_VALUES:
        assert "value = farm_capacity" not in _script_value_block(farming_text, max_value)
    for max_value in FISH_CAPACITY_MAX_VALUES:
        assert "value = fish_capacity" not in _script_value_block(fishing_text, max_value)
    for max_value in FOREST_CAPACITY_MAX_VALUES:
        assert "value = forest_capacity" not in _script_value_block(forest_text, max_value)

    for building in ("fishing_village", "ocean_fishery", "offshore_fishery"):
        assert f'value = "location_building_level(building_type:{building})"' in capacity_blocks[
            "fish_capacity"
        ]
    for building in FOREST_CAP_BUILDINGS:
        assert f'value = "location_building_level(building_type:{building})"' in capacity_blocks[
            "forest_capacity"
        ]


def test_farm_space_used_modifier_path_is_removed() -> None:
    roots = (
        BUILDING_BLUEPRINT_ROOT,
        MOD_ROOT / "in_game" / "common" / "building_types",
        MODIFIER_TYPE_DEFINITIONS,
        MODIFIER_ICONS,
        LOCALIZATION_ROOT,
    )
    offenders: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".txt", ".yml"}:
                continue
            if "farm_space_used" in path.read_text(encoding="utf-8-sig", errors="replace"):
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_farming_capacity_old_fixed_environment_path_is_removed() -> None:
    tokens = (
        "pp_farming_village_fixed_env_bonus",
        "pp_farming_village_capacity_value",
        "pp_farming_village_global_",
    )
    roots = (
        MOD_ROOT / "in_game" / "common" / "script_values",
        MOD_ROOT / "in_game" / "common" / "on_action",
        MOD_ROOT / "in_game" / "common" / "scripted_effects",
        MOD_ROOT / "in_game" / "common" / "customizable_localization",
        MOD_ROOT / "in_game" / "common" / "building_types",
        MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes",
        LOCALIZATION_ROOT,
        ROOT / "blueprints" / "accepted" / "buildings",
    )
    offenders: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".txt", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for token in tokens:
                if token in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {token}")

    assert offenders == []


def test_obsolete_fruit_sheep_capacity_systems_are_removed() -> None:
    tokens = (
        "sheep_farms_max_level",
        "farming_village_max_level_modifier",
        "pp_fruit_orchard_fixed_env_bonus",
        "pp_sheep_farms_fixed_env_bonus",
        "pp_fruit_orchard_global_",
        "pp_sheep_farms_global_",
        "pp_fruit_orchard_capacity_value",
        "pp_sheep_farms_capacity_value",
        "MAPMODE_PP_FRUIT_ORCHARD_CAPACITY",
        "MAPMODE_PP_SHEEP_FARMS_CAPACITY",
        "mapmode_pp_fruit_orchard_capacity_name",
        "mapmode_pp_sheep_farms_capacity_name",
    )
    roots = (
        MOD_ROOT / "in_game" / "common" / "script_values",
        MOD_ROOT / "in_game" / "common" / "on_action",
        MOD_ROOT / "in_game" / "common" / "scripted_effects",
        MOD_ROOT / "in_game" / "common" / "customizable_localization",
        MOD_ROOT / "in_game" / "common" / "building_types",
        MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes",
        MODIFIER_TYPE_DEFINITIONS,
        MODIFIER_ICONS,
        LOCALIZATION_ROOT,
        BUILDING_BLUEPRINT_ROOT,
    )
    offenders: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".txt", ".yml", ".md"}:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for token in tokens:
                if token in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {token}")

    obsolete_icons = (
        MOD_ROOT / "main_menu" / "gfx" / "interface" / "icons" / "map_modes" / "pp_fruit_orchard_capacity.dds",
        MOD_ROOT / "main_menu" / "gfx" / "interface" / "icons" / "map_modes" / "pp_sheep_farms_capacity.dds",
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "modifier_types"
        / "fruit_orchard_max_level_modifier.dds",
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "modifier_types"
        / "sheep_farms_max_level_modifier.dds",
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "modifier_types"
        / "farming_village_max_level_modifier.dds",
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "modifier_types"
        / "farm_capacity.dds"
    )
    offenders.extend(str(path.relative_to(ROOT)) for path in obsolete_icons if path.exists())

    assert offenders == []


def test_fish_and_forest_fixed_environment_paths_are_removed() -> None:
    cap_values = BUILDING_CAPACITY_VALUES.read_text(encoding="utf-8-sig")
    cap_text = "\n".join(
        path.read_text(encoding="utf-8-sig") for path in BUILDING_CAPACITY_SCRIPT_VALUE_FILES
    )
    game_start = GAME_START.read_text(encoding="utf-8-sig")
    map_text = FOOD_MAP_MODES.read_text(encoding="utf-8-sig")
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )

    required = (
        "pp_farm_base_capacity_value",
        "pp_fish_base_capacity_value",
        "pp_forest_base_capacity_value",
        "fish_capacity",
        "forest_capacity",
    )
    combined = "\n".join((cap_values, cap_text, game_start, map_text, localization_text))
    missing = [token for token in required if token not in combined]
    assert not missing

    obsolete = (
        "pp_fishing_village_fixed_env_bonus",
        "pp_forest_village_fixed_env_bonus",
        "pp_fishing_village_capacity_value",
        "pp_forest_village_capacity_value",
        "pp_fishing_village_global_",
        "pp_forest_village_global_",
        "fishing_village_max_level",
        "ocean_fishery_max_level",
        "offshore_fishery_max_level",
        "fish_gross_capacity",
        "fish_max_level",
        "fish_capacity_available",
        "fish_capacity_cost",
        "BUILDING_LEVEL_FISH_SPACE_USED_BY_OTHER_FISH_BUILDINGS",
        "BUILDING_LEVEL_FISH_CAPACITY_USED",
        "BUILDING_LEVEL_FISH_CAPACITY_IMPROVEMENTS",
        "forest_village_max_level",
        "forest_gross_capacity",
        "forest_max_level",
        "forest_capacity_available",
        "forest_capacity_cost",
        "forest_rank_capacity_modifier",
        "BUILDING_LEVEL_FOREST_CAPACITY_USED",
        "BUILDING_LEVEL_FOREST_CAPACITY_IMPROVEMENTS",
        "fishing_village_max_level_modifier",
        "forest_village_max_level_modifier",
    )
    offenders = [token for token in obsolete if token in combined]
    assert offenders == []


def test_fish_capacity_uses_water_rgo_size_and_used_fish_levels_only() -> None:
    text = FISHING_CAPACITY.read_text(encoding="utf-8-sig")
    cap_values = BUILDING_CAPACITY_VALUES.read_text(encoding="utf-8-sig")
    entries = {entry.key for entry in parse_file(FISHING_CAPACITY).entries}
    obsolete_value = "fish_" "natural_capacity"
    obsolete_modifier = f"{obsolete_value}_modifier"

    assert entries == {"fish_capacity", *FISH_CAPACITY_MAX_VALUES}
    assert "fish_rgo_capacity_bonus" not in entries
    assert "fish_rgo_scaling_capacity" not in entries
    assert "fish_capacity_remaining" not in entries
    assert "fish_building_levels" not in entries
    assert obsolete_value not in entries

    base_block = _text_block_between(
        cap_values,
        "pp_fish_base_capacity_value = {",
        "\npp_forest_base_capacity_value = {",
    )
    capacity_block = _script_value_block(text, "fish_capacity")

    for snippet in (
        "raw_material = goods:fish",
        "add = 3.00",
        "is_coastal = yes",
        "add = 4.50",
        "is_adjacent_to_lake = yes",
        "topography = wetlands",
        "add = 1.50",
    ):
        assert snippet in base_block
    assert "has_river = yes" not in base_block
    assert "add = 2.25" not in base_block

    assert "has_location_modifier = river_flowing_through_" not in base_block
    assert "has_location_modifier = river_flowing_through_" not in capacity_block
    assert "has_river = yes" not in capacity_block
    assert "limit = { has_variable = pp_fish_base_capacity }" in capacity_block
    assert "value = var:pp_fish_base_capacity" in capacity_block
    assert "value = pp_fish_base_capacity_value" in capacity_block
    assert 'desc = "BUILDING_LEVEL_BASE_FISHING"' in capacity_block
    assert 'desc = "BUILDING_LEVEL_RGO_SIZE_FISHING"' in capacity_block
    assert "add = modifier:fish_capacity_from_river_size" not in capacity_block
    assert "has_town_rights = town_rights_type:manorial_customals" in capacity_block
    assert capacity_block.count("multiply = max_rgo_workers") == 1
    assert capacity_block.count("multiply = 0.030") == 1
    assert (
        'desc = "BUILDING_LEVEL_FISH_RIVER"\n\t\tvalue = modifier:fish_capacity_from_river_size'
        in capacity_block
    )
    assert (
        'desc = "BUILDING_LEVEL_FISH_MANORIAL_CUSTOMALS"\n\t\t\tvalue = 2'
        in capacity_block
    )
    for building in FISH_CAP_BUILDINGS:
        assert f"limit = {{ has_building = building_type:{building} }}" in capacity_block
        assert f'value = "location_building_level(building_type:{building})"' in capacity_block
        assert f'desc = "BUILDING_LEVEL_FISH_{building.upper()}"' in capacity_block
    assert obsolete_value not in capacity_block
    assert obsolete_modifier not in text
    assert "max = 20" not in capacity_block
    assert "Public remaining-capacity path" in capacity_block
    for obsolete in (
        "fish_gross_capacity",
        "fish_max_level",
        "fish_capacity_available",
        "fish_capacity_cost",
        "fish_capacity_remaining",
        "fishing_village_max_level",
        "BUILDING_LEVEL_FISH_CAPACITY_USED",
        "BUILDING_LEVEL_FISH_CAPACITY_IMPROVEMENTS",
    ):
        assert obsolete not in capacity_block
    assert "min = 0" not in capacity_block
    assert "_other_fish_building_levels" not in text
    assert "BUILDING_LEVEL_FISH_SPACE_USED_BY_OTHER_FISH_BUILDINGS" not in text
    assert len(re.findall(r"modifier:fish_capacity\b", text)) == 0
    for building in FISH_CAP_BUILDINGS:
        max_block = _script_value_block(text, f"fish_capacity_max_{building}")
        assert f"value = fish_capacity" not in max_block
        assert f'desc = "BUILDING_LEVEL_FISH_{building.upper()}"' not in max_block
        for other_building in FISH_CAP_BUILDINGS:
            if other_building == building:
                continue
            assert f'desc = "BUILDING_LEVEL_FISH_{other_building.upper()}"' in max_block

    forbidden = ("value = population", "value = development", "local_population_capacity", "total_building_levels", "rank_capacity")
    assert not [token for token in forbidden if token in capacity_block]
    assert "value = max_rgo_workers\n\t\tmultiply = 0.40" not in capacity_block
    assert "multiply = 1.12" not in capacity_block


def test_irrigation_cap_scales_with_river_static_modifier_level() -> None:
    text = BUILDING_CAP_ADJUSTMENTS.read_text(encoding="utf-8-sig")
    modifier_icon_text = (MODIFIER_ICONS / "pp_building_cap_modifier_icons.txt").read_text(
        encoding="utf-8-sig"
    )
    entries = {entry.key: entry.value for entry in parse_file(BUILDING_CAP_ADJUSTMENTS).entries}
    assert "REPLACE:irrigant_cap" in entries

    irrigant_cap = text.split("REPLACE:irrigant_cap = {", 1)[1]
    assert "has_river = yes" not in irrigant_cap
    assert 'desc = "BUILDING_LEVEL_BASE"\n\t\tvalue = 1' in irrigant_cap
    assert "value = development\n\t\tmultiply = 0.1" in irrigant_cap
    assert re.search(
        r"is_adjacent_to_lake\s*=\s*yes\b.*?desc\s*=\s*\"BUILDING_LEVEL_IS_ADJACENT_TO_LAKE\".*?value\s*=\s*1\b",
        irrigant_cap,
        flags=re.S,
    )
    assert "has_location_modifier = river_flowing_through_" not in irrigant_cap
    assert (
        'desc = "BUILDING_LEVEL_HAS_RIVER"\n\t\tvalue = modifier:irrigant_cap_modifier'
        in irrigant_cap
    )
    assert (
        'desc = "BUILDING_LEVEL_FROM_OWNER_MODIFIERS"\n\t\tadd = owner.modifier:irrigant_cap_level'
        in irrigant_cap
    )
    assert (
        'irrigant_cap_modifier = {\n\tpositive = "gfx/interface/icons/buildings/irrigation_systems.dds"\n}'
        in modifier_icon_text
    )


def test_saquiyah_increases_irrigation_cap() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    advances = {row["name"]: row for row in data.advancements.select(["name", "modifiers"]).to_dicts()}
    buildings = {row["name"]: row for row in data.building_data.buildings.select(["name", "max_levels"]).to_dicts()}

    assert buildings["irrigation_systems"]["max_levels"] == "irrigant_cap"
    assert json.loads(advances["saquiyah"]["modifiers"])["irrigant_cap_level"] == 2.0
    assert "owner.modifier:irrigant_cap_level" in BUILDING_CAP_ADJUSTMENTS.read_text(
        encoding="utf-8-sig"
    )


def test_direct_fish_capacity_modifier_replaces_hidden_natural_path() -> None:
    obsolete_value = "fish_" "natural_capacity"
    obsolete_modifier = f"{obsolete_value}_modifier"
    location_modifier_adjustments = (
        MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifier_adjustments.txt"
    )
    checked_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (
            *BUILDING_CAPACITY_SCRIPT_VALUE_FILES,
            location_modifier_adjustments,
            MODIFIER_TYPE_DEFINITIONS / "pp_building_cap_modifiers.txt",
            MODIFIER_ICONS / "pp_building_cap_modifier_icons.txt",
            LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml",
        )
    )
    modifier_types = _database_keys(MODIFIER_TYPE_DEFINITIONS)
    modifier_icons = _database_keys(MODIFIER_ICONS)

    assert obsolete_value not in checked_text
    assert obsolete_modifier not in modifier_types
    assert obsolete_modifier not in modifier_icons
    assert "fish_capacity" not in modifier_types
    assert "fish_capacity" not in modifier_icons
    assert "fish_capacity_cost" not in modifier_types
    assert "fish_capacity_cost" not in modifier_icons
    assert "fish_capacity_from_river_size" in modifier_types
    assert "fish_capacity_from_river_size" in modifier_icons
    assert "MODIFIER_TYPE_NAME_fish_capacity:" not in checked_text
    assert "MODIFIER_TYPE_NAME_fish_capacity_cost:" not in checked_text
    assert "MODIFIER_TYPE_NAME_fish_capacity_from_river_size:" in checked_text


def test_forest_capacity_uses_forest_rgo_rank_urbanization_and_used_levels() -> None:
    text = FOREST_CAPACITY.read_text(encoding="utf-8-sig")
    cap_values = BUILDING_CAPACITY_VALUES.read_text(encoding="utf-8-sig")
    entries = {entry.key for entry in parse_file(FOREST_CAPACITY).entries}
    assert entries == {"forest_capacity", *FOREST_CAPACITY_MAX_VALUES}
    assert "forest_rgo_capacity_bonus" not in entries
    assert "forest_capacity_remaining" not in entries
    assert "forest_building_levels" not in entries
    assert "non_forest_building_levels" not in entries

    base_block = "pp_forest_base_capacity_value = {" + cap_values.split(
        "pp_forest_base_capacity_value = {",
        1,
    )[1]
    capacity_block = _script_value_block(text, "forest_capacity")

    for snippet in (
        "raw_material = goods:lumber",
        "raw_material = goods:fur",
        "raw_material = goods:wild_game",
        "vegetation = forest",
        "add = 6.6",
        "vegetation = woods",
        "add = 4.4",
        "vegetation = jungle",
        "add = 3.3",
    ):
        assert snippet in base_block

    assert "limit = { has_variable = pp_forest_base_capacity }" in capacity_block
    assert (
        'desc = "BUILDING_LEVEL_RGO_SIZE_FOREST"\n\t\t\tvalue = var:pp_forest_base_capacity\n\t\t\tmultiply = max_rgo_workers\n\t\t\tmultiply = 0.030'
        in capacity_block
    )
    assert "value = modifier:forest_capacity" not in capacity_block
    assert "max = 20" not in capacity_block
    assert "Public remaining-capacity path" in capacity_block
    assert "has_town_rights = town_rights_type:manorial_customals" in capacity_block
    assert 'desc = "BUILDING_LEVEL_FOREST_MANORIAL_CUSTOMALS"\n\t\t\tvalue = 1' in capacity_block
    for rank_name, value in {"megalopolis": -20, "city": -5, "town": -1}.items():
        assert f"limit = {{ location_rank = location_rank:{rank_name} }}" in capacity_block
        assert f"value = {value}" in capacity_block
    for building in FOREST_CAP_BUILDINGS:
        assert f"limit = {{ has_building = building_type:{building} }}" in capacity_block
        assert f'value = "location_building_level(building_type:{building})"' in capacity_block
        assert f'desc = "BUILDING_LEVEL_FOREST_{building.upper()}"' in capacity_block
    assert (
        'desc = "BUILDING_LEVEL_FOREST_URBANIZATION"\n\t\tvalue = total_building_levels'
        in capacity_block
    )
    assert "multiply = 0.1" in capacity_block
    for obsolete in (
        "forest_gross_capacity",
        "forest_max_level",
        "forest_capacity_available",
        "forest_capacity_cost",
        "forest_rank_capacity_modifier",
        "forest_capacity_remaining",
        "forest_building_levels",
        "non_forest_building_levels",
        "BUILDING_LEVEL_FOREST_CAPACITY_USED",
        "BUILDING_LEVEL_FOREST_CAPACITY_IMPROVEMENTS",
    ):
        assert obsolete not in capacity_block
    assert "value = non_forest_building_levels" not in capacity_block
    assert "min = 0" not in capacity_block
    assert len(re.findall(r"modifier:forest_capacity\b", text)) == 0
    for building in FOREST_CAP_BUILDINGS:
        max_block = _script_value_block(text, f"forest_capacity_max_{building}")
        assert f"value = forest_capacity" not in max_block
        assert f'desc = "BUILDING_LEVEL_FOREST_{building.upper()}"' not in max_block
        for other_building in FOREST_CAP_BUILDINGS:
            if other_building == building:
                continue
            assert f'desc = "BUILDING_LEVEL_FOREST_{other_building.upper()}"' in max_block
    assert not [token for token in ("value = population", "value = development", "local_population_capacity") if token in capacity_block]
    assert "value = max_rgo_workers\n\t\tmultiply = 0.50" not in capacity_block
    assert "multiply = 1.25" not in capacity_block


def test_land_farm_blueprints_use_shared_capacity_pool() -> None:
    missing_paths = [path for path in LAND_FARM_BLUEPRINTS if not path.exists()]
    assert missing_paths == []

    for blueprint in LAND_FARM_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8-sig")
        expected_max = f"max_levels = farm_capacity_max_{blueprint.stem}"

        assert expected_max in text
        assert re.search(r"^\s*max_levels\s*=\s*farm_capacity\s*$", text, flags=re.M) is None
        assert "fruit_orchard_max_level" not in text
        assert "farm_space_used" not in text
        assert "farm_capacity = -1" not in text
        assert "farm_capacity > 0" not in text
        assert "max_levels = farming_capacity" not in text
        assert "max_levels = farming_village_max_level" not in text
        assert "location_potential = {" in text
        assert "pp_farming_village_fixed_env_bonus" not in text

    for blueprint in (FARMING_VILLAGE_BLUEPRINT, MODEL_FARM_BLUEPRINT):
        text = blueprint.read_text(encoding="utf-8-sig")

        assert "pp_general_farmable_food_location_potential = yes" in text
        assert "max_rgo_workers > 0" not in text
        assert "modifier:local_population_capacity > 0" not in text


def test_broad_farm_capacity_buildings_have_static_location_potential_gates() -> None:
    horse_breeders = (BUILDING_BLUEPRINT_ROOT / "horse_breeders.yml").read_text(encoding="utf-8-sig")
    horse_potential = _text_block_between(horse_breeders, "location_potential = {", "\n\n    unique_production_methods = {")
    compatibility = (
        MOD_ROOT / "in_game" / "common" / "scripted_triggers" / "pp_startup_building_compatibility.txt"
    ).read_text(encoding="utf-8-sig")

    assert "pp_horse_breeders_location_potential = yes" in horse_potential
    assert "market = {\n\t\t\tis_produced_in_market = goods:horses" in compatibility
    for snippet in (
        "raw_material = goods:wool",
        "raw_material = goods:livestock",
        "raw_material = goods:horses",
        "vegetation = farmland",
        "vegetation = grasslands",
        "vegetation = sparse",
    ):
        assert snippet in compatibility
    assert "farm_capacity > 0" not in horse_breeders
    _, horse_trigger = compatibility.split("pp_horse_breeders_location_potential = {", 1)
    assert "climate =" not in horse_trigger
    assert "climate =" not in horse_breeders

    fiber_crops = (BUILDING_BLUEPRINT_ROOT / "fiber_crops_farm.yml").read_text(encoding="utf-8-sig")
    fiber_potential = _text_block_between(fiber_crops, "location_potential = {", "\n\n    unique_production_methods = {")

    assert "pp_fiber_crops_farm_location_potential = yes" in fiber_potential
    assert "raw_material = goods:fiber_crops" in compatibility
    assert "NOT = {\n\t\t\traw_material = goods:fiber_crops" not in compatibility
    for snippet in (
        "NOT = { climate = arctic }",
        "NOT = { climate = cold_arid }",
        "topography = flatland",
        "topography = hills",
        "topography = plateau",
        "topography = wetlands",
        "vegetation = farmland",
        "vegetation = grasslands",
        "vegetation = woods",
        "vegetation = forest",
    ):
        assert snippet in compatibility


def test_general_farm_eligibility_triggers_are_conservative() -> None:
    capacity_text = BUILDING_CAPACITY_VALUES.read_text(encoding="utf-8-sig")
    trigger_text = (
        MOD_ROOT / "in_game" / "common" / "scripted_triggers" / "pp_startup_building_compatibility.txt"
    ).read_text(encoding="utf-8-sig")
    farm_base_block = _text_block_between(
        capacity_text,
        "pp_farm_base_capacity_value = {",
        "\npp_fish_base_capacity_value = {",
    )
    general_block = _text_block_between(
        trigger_text,
        "pp_general_farmable_food_location_potential = {",
        "\npp_orchard_friendly_location_potential = {",
    )
    orchard_block = _text_block_between(
        trigger_text,
        "pp_orchard_friendly_location_potential = {",
        "\npp_pasture_friendly_location_potential = {",
    )
    pasture_block = _text_block_between(
        trigger_text,
        "pp_pasture_friendly_location_potential = {",
        "\npp_fiber_crops_farm_location_potential = {",
    )

    expected_allowed = {
        general_block: (
            "wheat",
            "maize",
            "rice",
            "millet",
            "legumes",
            "potato",
            "livestock",
            "olives",
            "fruit",
            "wool",
            "beeswax",
        ),
        orchard_block: (
            "fruit",
            "olives",
            "wine",
            "wheat",
            "maize",
            "rice",
            "millet",
            "legumes",
            "potato",
            "livestock",
            "beeswax",
            "silk",
            "tea",
        ),
        pasture_block: ("wool", "livestock", "horses"),
    }
    forbidden = ("fish", "clay", "lumber", "stone", "tin", "silver", "gold", "goods_gold", "gems", "saltpeter", "amber")

    for block, goods in expected_allowed.items():
        assert "is_ownable = yes" in block
        for good in goods:
            assert f"raw_material = goods:{good}" in block
        for good in forbidden:
            assert f"raw_material = goods:{good}" not in block

    assert "vegetation = farmland" in general_block
    for accepted_old_warning_good in ("wheat", "rice", "legumes", "livestock", "silk", "beeswax", "wine"):
        assert f"raw_material = goods:{accepted_old_warning_good}" in orchard_block
    for rejected_old_warning_good in ("clay", "fish", "tin", "silver", "goods_gold", "gems", "saltpeter", "amber"):
        assert f"raw_material = goods:{rejected_old_warning_good}" not in orchard_block
    assert "raw_material = goods:beeswax" in farm_base_block

    orchard_goods_order = re.findall(r"raw_material = goods:(\w+)", orchard_block)
    assert orchard_goods_order == [
        "livestock",
        "wheat",
        "millet",
        "legumes",
        "fruit",
        "rice",
        "beeswax",
        "maize",
        "wine",
        "silk",
        "potato",
        "tea",
        "olives",
    ]


def test_current_invalid_building_rows_are_covered_by_blueprint_potentials() -> None:
    # Snapshot of the invalid building rows from the current EU5 error.log.
    current_invalid_locations = {
        "farming_village": """
            hunfeld katzenelnbogen minden strelitz rohrbach klagenfurt friedberg rakovnik
            stafford cambridge minehead roxburgh naas loudun belleme riom carhaix
            monfort_sur_meu rethel tonnerre saint_claude dax st_affrique thiviers
            neufchateau_des_vosges angouleme forcalquier riano alba_de_aliste adrada
            soria cervera sora urbino asola alba nicosiasic debrecen bratislava segesd
            piotrkow_trybunalski svencionys legnica tula_russia ura_tyube kayseri cankiri
            konrapa bayramlu nusaybin manbij damavand zarghun_shahr changting putian
            ningyuan yongfeng taihe_taihe wannian guangde juegang yuexi wuhe xianzhu
            nishikanbara nyuu aki_shikoku hakata kimotsuki ou kamihei hanawa kamo_izu hoi
            adachi_kanto ganggye aju guangning yanshan longqing yanshi huangxian zhucheng
            jiaxiang otog liaoshan yilun duling rongshui bengmara lanka nabagram kasipur
            phulbani rander dhadar lahri gurramkonda chennur magadi singarh chambargonda
            palani anuradhapura devanagara chakaria minbya weithali visnupura thaungdut
            hoan_chau van_kiep purwalingga malang balibo kotabumi tizgane tlemcen
        """.split(),
        "fishing_village": "harris islay swansea laredo san_vicente_barquera bilbao valmaseda".split(),
        "fruit_orchard": """
            changsha yizhang hengyang macheng xiangyang xingguo shangrao nanchang dongliu
            jiangdu huaining linan tangxian hezhong dadu kaifeng qixia pingjin
            xinyi_gaozhou shilong nanhai bozhou jingzhao fuzhou_sichuan
        """.split(),
        "granary": """
            leuven sint_niklaas ypres deventer dordrecht mons kiel berlin rostock stralsund
            boston norwich inverness wexford chalons_champagne montauban aix_en_provence
            arles medina_del_campo tudela lleida tortosa morella ecija foggia manfredonia
            brindisi taranto matera melfi cotrone gaeta velletri orvietano lodi assisi
            vercelli villa_di_chiesa catania girgenti mazara trapani modica udine chioggia
            esztergom campulung_muscel vosporo shumen varna cherven ruse athens ioannina
            jerusalem al_ahsa jeddah gutian jinjiang yiyang_changsha lichuan changshu
            jiangning hezhou_he linan zhuji liaoyang guangping yongcheng luoyang xinzheng
            yangdi nanhai gengma gengdang leh dingqiang turpan kanauj pandua puri dhar
            khambat bidar gulbarga bombay kanchipuram kayal lamphun mansoura tidsi meknes
            azemmour begho walata manan bamako dieribakoro dutsi birni_lalle
        """.split(),
        "winery": "bordeaux xiaogan shaoxing xingzhong qingxiang luzhou".split(),
    }
    log_text = "\n".join(
        f"[11:44:00][initialize_from_bookmark.cpp:364]: Location {location} has an invalid building {building}"
        for building, locations in current_invalid_locations.items()
        for location in locations
    )
    invalid_rows = re.findall(r"Location\s+(\S+)\s+has an invalid building\s+(\w+)", log_text)

    assert len(invalid_rows) == 255

    capacity_text = BUILDING_CAPACITY_VALUES.read_text(encoding="utf-8-sig")
    trigger_text = (
        MOD_ROOT
        / "in_game"
        / "common"
        / "scripted_triggers"
        / "pp_startup_building_compatibility.txt"
    ).read_text(encoding="utf-8-sig")
    farm_base_block = _text_block_between(
        capacity_text,
        "pp_farm_base_capacity_value = {",
        "\npp_fish_base_capacity_value = {",
    )
    general_farm_block = _text_block_between(
        trigger_text,
        "pp_general_farmable_food_location_potential = {",
        "\npp_orchard_friendly_location_potential = {",
    )
    granary_text = (BUILDING_BLUEPRINT_ROOT / "granary.yml").read_text(encoding="utf-8-sig")
    fishing_text = (BUILDING_BLUEPRINT_ROOT / "fishing_village.yml").read_text(encoding="utf-8-sig")
    fishing_potential = _text_block_between(fishing_text, "location_potential = {", "\n\n        build_time")
    fruit_trigger_text = (
        MOD_ROOT
        / "in_game"
        / "common"
        / "scripted_triggers"
        / "pp_startup_building_compatibility.txt"
    ).read_text(encoding="utf-8-sig")
    fruit_text = (BUILDING_BLUEPRINT_ROOT / "fruit_orchard.yml").read_text(encoding="utf-8-sig")
    winery_blueprint = BUILDING_BLUEPRINT_ROOT / "winery.yml"
    winery_manufactory_blueprint = BUILDING_BLUEPRINT_ROOT / "winery_manufactory.yml"
    winery_text = winery_blueprint.read_text(encoding="utf-8-sig") if winery_blueprint.exists() else ""
    winery_manufactory_text = (
        winery_manufactory_blueprint.read_text(encoding="utf-8-sig")
        if winery_manufactory_blueprint.exists()
        else ""
    )

    orchard_exception_locations = set(re.findall(r"this = location:(\w+)", fruit_trigger_text))
    assert orchard_exception_locations == set(current_invalid_locations["fruit_orchard"])
    assert "var:pp_fruit_orchard_eligible > 0" in fruit_text
    assert "pp_fruit_orchard_location_potential = yes" in fruit_text
    assert "pp_vanilla_start_fruit_orchard_location" not in fruit_text
    assert "raw_material = goods:beeswax" in farm_base_block
    assert "raw_material = goods:beeswax" in general_farm_block
    assert "vegetation = farmland" in general_farm_block
    assert "is_coastal = yes" in fishing_potential
    assert "is_province_capital = yes" not in granary_text
    for rank in ("rural_settlement", "town", "city", "megalopolis"):
        assert f"location_rank = location_rank:{rank}" in granary_text
    assert not winery_blueprint.exists()
    assert not winery_manufactory_blueprint.exists()
    assert "NOT = { raw_material = goods:wine }" not in winery_text
    assert "NOT = { raw_material = goods:wine }" not in winery_manufactory_text

    unsupported = []
    for location, building in invalid_rows:
        if building == "farming_village" and "raw_material = goods:beeswax" not in general_farm_block:
            unsupported.append((location, building))
        elif building == "fruit_orchard" and location not in orchard_exception_locations:
            unsupported.append((location, building))
        elif building == "fishing_village" and "is_coastal = yes" not in fishing_potential:
            unsupported.append((location, building))
        elif building == "granary" and "is_province_capital = yes" in granary_text:
            unsupported.append((location, building))
        elif building == "winery" and "NOT = { raw_material = goods:wine }" in winery_text:
            unsupported.append((location, building))
        elif building not in {"farming_village", "fruit_orchard", "fishing_village", "granary", "winery"}:
            unsupported.append((location, building))

    assert unsupported == []


def test_fruit_and_sheep_families_use_shared_eligibility_gates() -> None:
    gates = {
        "fruit_orchard": "pp_fruit_orchard_location_potential",
        "pomological_orchard": "pp_orchard_friendly_location_potential",
        "sheep_farms": "pp_pasture_friendly_location_potential",
        "enclosed_sheep_walks": "pp_pasture_friendly_location_potential",
    }

    for building, gate in gates.items():
        text = (BUILDING_BLUEPRINT_ROOT / f"{building}.yml").read_text(encoding="utf-8-sig")
        assert f"{gate} = yes" in text
        assert "farm_capacity > 0" not in text
        assert "pp_fruit_orchard_fixed_env_bonus" not in text
        assert "pp_sheep_farms_fixed_env_bonus" not in text

    fruit_text = (BUILDING_BLUEPRINT_ROOT / "fruit_orchard.yml").read_text(encoding="utf-8-sig")
    assert "var:pp_fruit_orchard_eligible > 0" in fruit_text
    assert "NOT = { has_variable = pp_fruit_orchard_eligible }" in fruit_text

    game_start = GAME_START.read_text(encoding="utf-8-sig")
    assert "NOT = { pp_general_farmable_food_location_potential = yes }" in game_start
    assert "NOT = { pp_fruit_orchard_location_potential = yes }" in game_start
    assert "NOT = { pp_orchard_friendly_location_potential = yes }" in game_start
    assert "NOT = { pp_pasture_friendly_location_potential = yes }" in game_start
    assert "pp_general_farmable_food_location > 0" not in game_start
    assert "pp_orchard_friendly_location > 0" not in game_start
    assert "pp_pasture_friendly_location > 0" not in game_start
    assert "NOT = { raw_material = goods:fruit }" not in game_start
    assert "NOT = { raw_material = goods:wool }" not in game_start

    rgo_effects = RGO_STATIC_BONUS_EFFECTS.read_text(encoding="utf-8-sig")
    assert "pp_refresh_fruit_orchard_eligibility" in rgo_effects
    assert "set_variable = { name = pp_fruit_orchard_eligible value = 0 }" in rgo_effects
    assert "set_variable = { name = pp_fruit_orchard_eligible value = 1 }" in rgo_effects
    assert "raw_material = goods:fruit" in rgo_effects
    assert "raw_material = goods:wool" in rgo_effects


def test_fish_blueprints_use_shared_capacity_pool_and_keep_distinctions() -> None:
    missing_paths = [path for path in FISH_CAP_BLUEPRINTS if not path.exists()]
    assert missing_paths == []

    for blueprint in FISH_CAP_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8-sig")
        assert f"max_levels = fish_capacity_max_{blueprint.stem}" in text
        assert re.search(r"^\s*max_levels\s*=\s*fish_capacity\s*$", text, flags=re.M) is None
        assert "_fishery_max_level" not in text
        assert "fishing_village_max_level" not in text
        assert "text = PP_HAS_FISHING_CAPACITY" not in text
        assert "fish_capacity > 0" not in text
        assert "fish_capacity_cost = -1" not in text
        assert "pp_fishing_village_fixed_env_bonus" not in text

    fishing_village = (BUILDING_BLUEPRINT_ROOT / "fishing_village.yml").read_text(encoding="utf-8-sig")
    for gate in (
        "has_river = yes",
        "is_adjacent_to_lake = yes",
        "topography = wetlands",
        "is_coastal = yes",
        "raw_material = goods:fish",
    ):
        assert gate in fishing_village

    for blueprint in ("ocean_fishery", "offshore_fishery"):
        text = (BUILDING_BLUEPRINT_ROOT / f"{blueprint}.yml").read_text(encoding="utf-8-sig")
        location_potential = _text_block_between(text, "location_potential = {", "\n\n    construction_demand")
        assert "is_coastal = yes" in location_potential
        assert "has_river = yes" not in location_potential
        assert "is_adjacent_to_lake = yes" not in location_potential

    pearl = (BUILDING_BLUEPRINT_ROOT / "pearl_fishery.yml").read_text(encoding="utf-8-sig")
    assert "fish_capacity" not in pearl
    assert "fish_capacity" not in pearl


def test_forest_blueprints_use_shared_capacity_pool() -> None:
    missing_paths = [path for path in FOREST_CAP_BLUEPRINTS if not path.exists()]
    assert missing_paths == []

    for blueprint in FOREST_CAP_BLUEPRINTS:
        text = blueprint.read_text(encoding="utf-8-sig")
        assert f"max_levels = forest_capacity_max_{blueprint.stem}" in text
        assert re.search(r"^\s*max_levels\s*=\s*forest_capacity\s*$", text, flags=re.M) is None
        assert "forest_capacity > 0" not in text
        assert "forest_capacity_cost = -1" not in text
        assert "forest_village_max_level" not in text
        assert "pp_forest_village_fixed_env_bonus" not in text
        for gate in (
            "vegetation = woods",
            "vegetation = forest",
            "vegetation = jungle",
            "raw_material = goods:lumber",
            "raw_material = goods:fur",
            "raw_material = goods:wild_game",
        ):
            assert gate in text

    for excluded in ("charcoal_maker", "improved_charcoal_maker", "ivory_hunting_camp", "pearl_fishery"):
        text = (BUILDING_BLUEPRINT_ROOT / f"{excluded}.yml").read_text(encoding="utf-8-sig")
        assert "forest_capacity" not in text
        assert "forest_capacity" not in text


def test_capacity_blueprints_are_tagged_for_filtered_blueprint_workflows() -> None:
    groups = {
        "farming_capacity": LAND_FARM_BUILDINGS,
        "fishing_capacity": FISH_CAP_BUILDINGS,
        "forest_capacity": FOREST_CAP_BUILDINGS,
    }

    for tag, buildings in groups.items():
        for building in buildings:
            values = _accepted_blueprint_building_values(building)
            assert tag in _custom_tags(values["custom_tags"]), f"{building} missing {tag}"


def test_location_rank_capacity_modifiers_are_canonical() -> None:
    parsed = parse_file(LOCATION_RANKS)
    entries = {entry.key: entry.value for entry in parsed.entries}
    expected = {
        "TRY_INJECT:megalopolis": -20,
        "TRY_INJECT:city": -5,
        "TRY_INJECT:town": -1,
        "TRY_INJECT:rural_settlement": 0,
    }

    for rank_key, value in expected.items():
        rank = entries[rank_key]
        assert isinstance(rank, CList)
        rank_modifier = _entry_values(rank)["rank_modifier"]
        assert isinstance(rank_modifier, CList)
        modifiers = _entry_values(rank_modifier)
        assert "farm_capacity" not in modifiers
        assert "forest_rank_capacity_modifier" not in modifiers
        assert "farm_capacity_from_location_rank" not in modifiers
        assert "fruit_orchard_max_level_modifier" not in modifiers
        assert "sheep_farms_max_level_modifier" not in modifiers
        assert "farming_village_max_level_modifier" not in modifiers
        assert "fishing_village_max_level_modifier" not in modifiers
        assert "forest_village_max_level_modifier" not in modifiers
        assert "fish_capacity" not in modifiers
        assert "forest_capacity" not in modifiers

    farm_capacity_text = FARMING_CAPACITY.read_text(encoding="utf-8-sig")
    forest_capacity_text = FOREST_CAPACITY.read_text(encoding="utf-8-sig")
    for rank_key, value in expected.items():
        rank_name = rank_key.removeprefix("TRY_INJECT:")
        if value == 0:
            assert f"location_rank = location_rank:{rank_name}" not in farm_capacity_text
            assert f"location_rank = location_rank:{rank_name}" not in forest_capacity_text
            continue
        assert f"limit = {{ location_rank = location_rank:{rank_name} }}" in farm_capacity_text
        assert f"value = {value}" in farm_capacity_text
        assert f"limit = {{ location_rank = location_rank:{rank_name} }}" in forest_capacity_text
        assert f"value = {value}" in forest_capacity_text


def test_farm_capacity_uses_direct_rows_with_a_river_size_bridge_modifier() -> None:
    modifier_types = _database_keys(MODIFIER_TYPE_DEFINITIONS)
    modifier_icons = _database_keys(MODIFIER_ICONS)
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )
    obsolete_modifier = "fish_" "natural_capacity_modifier"
    farm_capacity_text = FARMING_CAPACITY.read_text(encoding="utf-8-sig")

    assert "farm_capacity" not in modifier_types
    assert "farm_capacity" not in modifier_icons
    assert "farm_capacity_from_river_size" in modifier_types
    assert "farm_capacity_from_river_size" in modifier_icons
    assert "farm_capacity_from_location_rank" not in modifier_types
    assert "farm_capacity_from_location_rank" not in modifier_icons
    assert "farm_capacity_cost" not in modifier_types
    assert "farm_capacity_cost" not in modifier_icons
    assert "fish_capacity" not in modifier_types
    assert "fish_capacity" not in modifier_icons
    assert "fish_capacity_from_river_size" in modifier_types
    assert "fish_capacity_from_river_size" in modifier_icons
    assert "fish_capacity_cost" not in modifier_types
    assert "fish_capacity_cost" not in modifier_icons
    assert obsolete_modifier not in modifier_types
    assert obsolete_modifier not in modifier_icons
    assert "irrigant_cap_modifier" in modifier_types
    assert "irrigant_cap_modifier" in modifier_icons
    assert "forest_capacity" not in modifier_types
    assert "forest_capacity" not in modifier_icons
    assert "forest_rank_capacity_modifier" not in modifier_types
    assert "forest_rank_capacity_modifier" not in modifier_icons
    assert "forest_capacity_cost" not in modifier_types
    assert "forest_capacity_cost" not in modifier_icons
    assert "MODIFIER_TYPE_NAME_farm_capacity:" not in localization_text
    assert "MODIFIER_TYPE_DESC_farm_capacity:" not in localization_text
    assert "MODIFIER_TYPE_NAME_farm_capacity_from_river_size:" in localization_text
    assert "MODIFIER_TYPE_DESC_farm_capacity_from_river_size:" in localization_text
    assert "MODIFIER_TYPE_NAME_farm_capacity_from_location_rank:" not in localization_text
    assert "MODIFIER_TYPE_NAME_farm_capacity_cost:" not in localization_text
    assert "MODIFIER_TYPE_NAME_fish_capacity:" not in localization_text
    assert "MODIFIER_TYPE_NAME_fish_capacity_from_river_size:" in localization_text
    assert "MODIFIER_TYPE_NAME_fish_capacity_cost:" not in localization_text
    assert obsolete_modifier not in localization_text
    assert "MODIFIER_TYPE_NAME_irrigant_cap_modifier:" in localization_text
    assert "MODIFIER_TYPE_NAME_forest_capacity:" not in localization_text
    assert "MODIFIER_TYPE_NAME_forest_rank_capacity_modifier:" not in localization_text
    assert "MODIFIER_TYPE_NAME_forest_capacity_cost:" not in localization_text
    assert "BUILDING_LEVEL_FARM_CAPACITY_IMPROVEMENTS:" not in localization_text
    assert "BUILDING_LEVEL_FARM_CAPACITY:" not in localization_text
    assert "BUILDING_LEVEL_RIVER_FARM_CAPACITY:" not in localization_text
    assert "BUILDING_LEVEL_MANORIAL_CUSTOMALS_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_IRRIGATION_SYSTEMS_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_BUND_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_TERRACES_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_POLDERS_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_KHMER_BARAY_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_AQUEDUCT_SYSTEM_FARMING:" not in localization_text
    assert "BUILDING_LEVEL_FISH_CAPACITY_IMPROVEMENTS:" not in localization_text
    assert "BUILDING_LEVEL_FOREST_CAPACITY_IMPROVEMENTS:" not in localization_text
    assert 'BUILDING_LEVEL_BASE_FARM_RGO: "Farm Related [rgo|e]"' in localization_text
    assert 'BUILDING_LEVEL_RGO_SIZE_FARMING: "Maximum RGO Size"' in localization_text
    assert 'BUILDING_LEVEL_FARM_LOCATION_RANK: "Location Rank"' in localization_text
    assert 'BUILDING_LEVEL_FARM_RIVER: "[river|e] Size"' in localization_text
    assert 'BUILDING_LEVEL_FARM_MANORIAL_CUSTOMALS: "Manorial Customals"' in localization_text
    assert "BUILDING_LEVEL_FARM_CAPACITY_USED:" not in localization_text
    assert (
        'BUILDING_LEVEL_FARM_URBANIZATION: "Reduced Capacity from [pp_buildings_in_location|e]"'
        in localization_text
    )
    assert (
        'BUILDING_LEVEL_FARM_IRRIGATION_SYSTEMS: "[ShowBuildingTypeName(\'irrigation_systems\')|e]"'
        in localization_text
    )
    for building in ("aqueduct_system", "farming_village", "model_farm", "vineyard_estate"):
        key = f"BUILDING_LEVEL_FARM_{building.upper()}"
        assert f"{key}: \"[ShowBuildingTypeName('{building}')|e]\"" in localization_text
    assert "BUILDING_LEVEL_FARM_TOTAL_BUILDING_PRESSURE:" not in localization_text
    assert "BUILDING_LEVEL_FARM_CAPACITY_USED_ADJUSTED:" not in localization_text
    assert 'BUILDING_LEVEL_BASE_FISHING: "Natural Fishing Grounds"' in localization_text
    assert 'BUILDING_LEVEL_RGO_SIZE_FISHING: "Maximum RGO Size"' in localization_text
    assert 'BUILDING_LEVEL_FISH_RIVER: "[river|e] Size"' in localization_text
    assert 'BUILDING_LEVEL_FISH_MANORIAL_CUSTOMALS: "Manorial Customals"' in localization_text
    for building in FISH_CAP_BUILDINGS:
        key = f"BUILDING_LEVEL_FISH_{building.upper()}"
        assert f"{key}: \"[ShowBuildingTypeName('{building}')|e]\"" in localization_text
    assert 'BUILDING_LEVEL_BASE_FOREST: "Forest Geography and [rgo|e]"' in localization_text
    assert 'BUILDING_LEVEL_RGO_SIZE_FOREST: "Maximum RGO Size"' in localization_text
    assert 'BUILDING_LEVEL_FOREST_LOCATION_RANK: "Location Rank"' in localization_text
    for building in FOREST_CAP_BUILDINGS:
        key = f"BUILDING_LEVEL_FOREST_{building.upper()}"
        assert f"{key}: \"[ShowBuildingTypeName('{building}')|e]\"" in localization_text
    assert (
        'BUILDING_LEVEL_FOREST_URBANIZATION: "Reduced Capacity from [pp_buildings_in_location|e]"'
        in localization_text
    )
    assert "BUILDING_LEVEL_FOREST_TOTAL_BUILDING_PRESSURE:" not in localization_text
    assert "BUILDING_LEVEL_FOREST_CAPACITY_USED_ADJUSTED:" not in localization_text
    assert "From Matching Farm RGO" not in localization_text
    assert "Farming Capacity Improvements" not in localization_text
    assert '"missing key":' not in localization_text
    assert "missing_key:" not in localization_text

    expected_water_control_rows = {
        "irrigation_systems": "0.60",
        "bund": "0.60",
        "terraces": "0.60",
        "polders": "0.60",
        "khmer_baray": "0.60",
        "aqueduct_system": "2",
    }
    for building, multiplier in expected_water_control_rows.items():
        assert f"limit = {{ has_building = building_type:{building} }}" in farm_capacity_text
        assert f'value = "location_building_level(building_type:{building})"' in farm_capacity_text
        assert f"multiply = {multiplier}" in farm_capacity_text
        source_text = (
            AQUEDUCT_SYSTEM
            if building == "aqueduct_system"
            else BUILDING_BLUEPRINT_ROOT / f"{building}.yml"
        ).read_text(encoding="utf-8-sig")
        assert re.search(r"^\s*farm_capacity\s*=", source_text, re.MULTILINE) is None
        assert "farm_capacity_from_location_rank" not in source_text

    town_rights_text = (MOD_ROOT / "in_game" / "common" / "town_rights" / "pp_town_rights.txt").read_text(
        encoding="utf-8-sig"
    )
    manorial_customals = _text_block_between(
        town_rights_text,
        "TRY_INJECT:manorial_customals = {",
        "\n}",
    )
    assert "farm_capacity = 1" not in manorial_customals
    assert "has_town_rights = town_rights_type:manorial_customals" in farm_capacity_text
    assert 'desc = "BUILDING_LEVEL_FARM_MANORIAL_CUSTOMALS"' in farm_capacity_text

    static_modifier_text = (MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifier_adjustments.txt").read_text(
        encoding="utf-8-sig"
    )
    expected_river_capacity = {
        "river_flowing_through_1": "1",
        "river_flowing_through_2": "1",
        "river_flowing_through_3": "2",
        "river_flowing_through_4": "3",
        "river_flowing_through_5": "4",
    }
    for river_modifier, value in expected_river_capacity.items():
        block = _text_block_between(
            static_modifier_text,
            f"TRY_INJECT:{river_modifier} = {{",
            "\n}",
        )
        assert "farm_capacity =" not in block
        assert f"farm_capacity_from_river_size = {value}" in block
        assert "fish_capacity =" not in block
        assert f"fish_capacity_from_river_size = {value}" in block
        assert "has_location_modifier = river_flowing_through_" not in farm_capacity_text
        assert "value = modifier:farm_capacity_from_river_size" in farm_capacity_text


def test_water_control_capacity_buildings_use_scaled_gold_prices() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    buildings = {row["name"]: row for row in data.building_data.buildings.to_dicts()}
    expected_prices = {
        "bund": ("pp_bund_price", 75.0),
        "irrigation_systems": ("pp_irrigation_systems_price", 50.0),
        "terraces": ("pp_terraces_price", 100.0),
        "polders": ("pp_polders_price", 200.0),
        "khmer_baray": ("pp_khmer_baray_price", 125.0),
        "aqueduct_system": ("expand_aqueduct_system", 1000.0),
    }

    for building, (price_key, gold) in expected_prices.items():
        assert buildings[building]["price"] == price_key
        assert buildings[building]["price_gold"] == gold


def test_excluded_buildings_do_not_use_land_farm_capacity_pool() -> None:
    explicit_missing = [
        key for key in EXCLUDED_FARM_CAP_BUILDINGS if not (BUILDING_BLUEPRINT_ROOT / f"{key}.yml").exists()
    ]
    assert explicit_missing == []

    excluded_blueprints = _farm_cap_excluded_blueprints()
    assert excluded_blueprints

    offenders: list[str] = []
    for blueprint in excluded_blueprints:
        text = blueprint.read_text(encoding="utf-8-sig")
        if re.search(r"^\s*max_levels\s*=\s*farm_capacity\s*$", text, flags=re.M):
            offenders.append(f"{blueprint.relative_to(ROOT)}: farm_capacity")
        if "farm_capacity_max_" in text:
            offenders.append(f"{blueprint.relative_to(ROOT)}: per-building farm max level")
        if "farm_space_used" in text:
            offenders.append(f"{blueprint.relative_to(ROOT)}: farm_space_used")
        if "farm_capacity > 0" in text:
            offenders.append(f"{blueprint.relative_to(ROOT)}: farm_capacity")

    assert offenders == []


def test_farming_capacity_map_uses_current_farm_capacity_value() -> None:
    map_text = FOOD_MAP_MODES.read_text(encoding="utf-8-sig")
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )

    assert "value = farm_capacity" in map_text
    assert "ScriptValue('farm_capacity')" in localization_text
    assert "ScriptValue('farm_capacity_available')" not in localization_text
    assert "ScriptValue('farm_gross_capacity')" not in localization_text
    assert "GetModifierValue('farm_capacity_cost')" not in localization_text
    assert "ScriptValue('land_farm_capacity_used')" not in localization_text
    assert "farm_capacity_used" not in localization_text
    assert "ScriptValue('farm_urbanization_pressure')" not in localization_text
    assert "Current Capacity:" in localization_text
    assert "same value" in localization_text
    assert "Farming Villages and Model Farms" not in localization_text


def test_fish_and_forest_capacity_maps_use_current_capacity_and_tooltips_show_sources() -> None:
    map_text = FOOD_MAP_MODES.read_text(encoding="utf-8-sig")
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )

    assert "value = fish_capacity" in map_text
    assert "value = forest_capacity" in map_text
    assert "var:pp_fishing_village_fixed_env_bonus" not in map_text
    assert "var:pp_forest_village_fixed_env_bonus" not in map_text
    assert "global_var:pp_fishing_village_global_" not in map_text
    assert "global_var:pp_forest_village_global_" not in map_text

    assert "ScriptValue('fish_capacity')" in localization_text
    assert "ScriptValue('fish_gross_capacity')" not in localization_text
    assert "ScriptValue('forest_capacity')" in localization_text
    assert "ScriptValue('forest_gross_capacity')" not in localization_text
    assert "GetVariable('pp_fishing_village_fixed_env_bonus')" not in localization_text
    assert "GetVariable('pp_forest_village_fixed_env_bonus')" not in localization_text
    assert 'BUILDING_LEVEL_BASE_FISHING: "Natural Fishing Grounds"' in localization_text
    assert 'BUILDING_LEVEL_RGO_SIZE_FISHING: "Maximum RGO Size"' in localization_text
    assert "BUILDING_LEVEL_FISH_CAPACITY_IMPROVEMENTS" not in localization_text
    assert "BUILDING_LEVEL_FISH_CAPACITY_USED" not in localization_text
    assert "BUILDING_LEVEL_FISH_SPACE_USED_BY_OTHER_FISH_BUILDINGS" not in localization_text
    assert 'BUILDING_LEVEL_BASE_FOREST: "Forest Geography and [rgo|e]"' in localization_text
    assert 'BUILDING_LEVEL_RGO_SIZE_FOREST: "Maximum RGO Size"' in localization_text
    assert "BUILDING_LEVEL_FOREST_CAPACITY_IMPROVEMENTS" not in localization_text
    assert "BUILDING_LEVEL_FOREST_CAPACITY_USED" not in localization_text
    assert "Current Capacity:" in localization_text
    assert "Available Capacity:" not in localization_text
    assert "Gross Capacity:" not in localization_text
    assert "Fishing Capacity modifiers, including river size and town rights" not in localization_text


def test_market_food_price_map_mode_uses_market_price_scale_and_assets() -> None:
    map_text = FOOD_MAP_MODES.read_text(encoding="utf-8-sig")
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )
    block = _text_block_between(
        map_text,
        "pp_market_food_price = {",
        "\npp_fishing_village_capacity = {",
    )

    assert "@pp_market_food_price_neutral = 0.12" in map_text
    assert "@pp_market_food_price_cheap = 0.054" in map_text
    assert "@pp_market_food_price_expensive = 0.171" in map_text
    required_map_snippets = (
        "value = market.food_price",
        "limit = { has_owner = yes }",
        "min_color = define:NMapColors|MAP_COLOR_MAX",
        "max_color = define:NMapColors|MAP_COLOR_MIN",
        "market.food_price < @pp_market_food_price_cheap",
        "market.food_price < @pp_market_food_price_neutral",
        "market.food_price < @pp_market_food_price_expensive",
        "max = 1",
        "min = 0",
        "category = economy",
        "small_map_names = market",
        "market_marker = yes",
        "color_and_names_refresh_counters = { MarketReach LocationOwnerChanged }",
        "map_lines_mode = ToMarketCenter",
        "MAPMODE_PP_MARKET_FOOD_PRICE_VERY_CHEAP",
        "MAPMODE_PP_MARKET_FOOD_PRICE_CHEAP",
        "MAPMODE_PP_MARKET_FOOD_PRICE_NEUTRAL",
        "MAPMODE_PP_MARKET_FOOD_PRICE_EXPENSIVE",
        "MAPMODE_PP_MARKET_FOOD_PRICE_SEVERE",
    )
    missing_map_snippets = [snippet for snippet in required_map_snippets if snippet not in block]
    assert not missing_map_snippets
    assert block.count("lerp = {") == 4

    required_localization = (
        "mapmode_pp_market_food_price_name",
        "MAPMODE_PP_MARKET_FOOD_PRICE",
        "MAPMODE_PP_MARKET_FOOD_PRICE_VERY_CHEAP",
        "MAPMODE_PP_MARKET_FOOD_PRICE_CHEAP",
        "MAPMODE_PP_MARKET_FOOD_PRICE_NEUTRAL",
        "MAPMODE_PP_MARKET_FOOD_PRICE_EXPENSIVE",
        "MAPMODE_PP_MARKET_FOOD_PRICE_SEVERE",
        "MAPMODE_PP_MARKET_FOOD_PRICE_TT_LAND",
        "MAPMODE_PP_MARKET_FOOD_PRICE_TT_WATER",
        "[Market.GetName]",
        "[Market.GetFoodPrice|2]",
    )
    missing_localization = [
        snippet for snippet in required_localization if snippet not in localization_text
    ]
    assert not missing_localization

    assert (
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "map_modes"
        / "pp_market_food_price.dds"
    ).is_file()
    assert not (
        MOD_ROOT
        / "in_game"
        / "gfx"
        / "interface"
        / "icons"
        / "map_modes"
        / "pp_market_food_price.dds"
    ).exists()


def test_capacity_map_mode_europedia_links_have_game_concepts() -> None:
    expected_concepts = (
        "pp_fish_capacity",
        "pp_farm_capacity",
        "pp_forest_capacity",
    )
    localization_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (
            LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml",
            LOCALIZATION_ROOT / "pp_europedia_l_english.yml",
        )
    )

    for concept in expected_concepts:
        concept_path = GAME_CONCEPT_ROOT / f"{concept}.txt"
        assert concept_path.exists()
        assert f"{concept} = {{" in concept_path.read_text(encoding="utf-8-sig")
        assert f"[{concept}|e]" in localization_text


def test_building_capacity_europedia_explains_capacity_pools_and_rural_cap() -> None:
    localization_text = (LOCALIZATION_ROOT / "pp_europedia_l_english.yml").read_text(
        encoding="utf-8-sig"
    )
    capacity_desc = localization_text.split("game_concept_pp_farm_capacity_desc:", 1)[1].split(
        "\ngame_concept_pp_fish_capacity:",
        1,
    )[0]
    assert 'game_concept_pp_farm_capacity: "P&P: Farming/Fishing/Forest Capacities"' in localization_text

    required_terms = (
        "Geography map-mode group",
        "#T Farming Capacity:#!",
        "#T Fishing Capacity:#!",
        "#T Forest Capacity:#!",
        "#T Other Raw Material Buildings:#!",
        "Rural Building Capacity",
        "Maximum RGO Size",
        "[pp_population_capacity|e]",
        "urbanization pressure",
        "Farming Capacity is one current sum",
        "existing farming-capacity buildings",
        "the matching capacity map mode show the same current value",
        "maximum-level tooltip lists the active sources",
        "river size",
        "Manorial Customals",
        "development",
        "ShowBuildingTypeName('farming_village')",
        "ShowBuildingTypeName('fishing_village')",
        "ShowBuildingTypeName('forest_village')",
        "mines, quarries, saltworks, pearl fisheries, charcoal makers, ivory hunting camps",
    )
    missing = [term for term in required_terms if term not in capacity_desc]

    assert not missing
    for forbidden in (
        "Available Farming Capacity starts from Gross Capacity",
        "used Farming Capacity",
        "capacity already used by farming-capacity buildings",
        "map mode shows available capacity, gross capacity",
    ):
        assert forbidden not in capacity_desc


def test_game_loaded_text_files_are_finalized_with_utf8_bom() -> None:
    cli._ensure_constructor_text_boms(MOD_ROOT)
    expected_paths = (
        GAME_CONCEPT_ROOT / "pp_fish_capacity.txt",
        GAME_CONCEPT_ROOT / "pp_forest_capacity.txt",
        BUILDING_CAPACITY_VALUES,
        CAPACITY_PRECALC,
        MOD_ROOT / "in_game" / "common" / "scripted_triggers" / "pp_startup_building_compatibility.txt",
    )
    configured_paths = {MOD_ROOT / path for path in cli.BOM_TEXT_RELATIVE_PATHS}
    game_loaded_paths = set(cli._iter_game_loaded_text_files(MOD_ROOT))

    for path in expected_paths:
        assert path in configured_paths or path in game_loaded_paths

    missing_bom: list[str] = []
    invalid_utf8: list[str] = []
    for path in sorted(game_loaded_paths):
        raw = path.read_bytes()
        if not raw.startswith(b"\xef\xbb\xbf"):
            missing_bom.append(str(path.relative_to(MOD_ROOT)))
        try:
            raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            invalid_utf8.append(f"{path.relative_to(MOD_ROOT)}: {error}")

    assert not missing_bom
    assert not invalid_utf8


def test_situation_can_end_blocks_use_end_reasons() -> None:
    offenders: list[str] = []

    for path in sorted(SITUATION_ROOT.glob("*.txt")):
        for situation in parse_file(path).entries:
            if not isinstance(situation.value, CList):
                continue
            for entry in situation.value.entries:
                if entry.key != "can_end":
                    continue
                if not isinstance(entry.value, CList):
                    offenders.append(f"{path.relative_to(ROOT)}:{situation.key}: can_end is not a block")
                    continue

                invalid_keys = [child.key for child in entry.value.entries if child.key != "end_reason"]
                if invalid_keys:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{situation.key}: can_end has {', '.join(invalid_keys)}"
                    )

                for child in entry.value.entries:
                    if child.key != "end_reason":
                        continue
                    if not isinstance(child.value, CList):
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{situation.key}: end_reason is not a block"
                        )
                        continue
                    reason_keys = {reason_entry.key for reason_entry in child.value.entries}
                    missing_keys = {"trigger", "desc"} - reason_keys
                    if missing_keys:
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{situation.key}: end_reason missing "
                            f"{', '.join(sorted(missing_keys))}"
                        )

    assert not offenders


def test_legacy_capacity_culling_is_removed() -> None:
    text = BUILDING_CULLING.read_text(encoding="utf-8-sig")
    entries = {entry.key for entry in parse_file(BUILDING_CULLING).entries}

    assert "pp_yearly_cull_one_closed_building" in entries
    assert "pp_cull_over_cap_buildings" not in entries
    assert "farm_capacity_remaining < 0" not in text
    assert "fish_capacity_remaining < 0" not in text
    assert "forest_capacity_remaining < 0" not in text
    assert "value > fruit_orchard_max_level" not in text


def test_ai_victuals_market_crisis_scans_owned_capitals_not_all_provinces() -> None:
    text = BUILDING_CULLING.read_text(encoding="utf-8-sig")
    entries = {entry.key for entry in parse_file(BUILDING_CULLING).entries}
    action_text = text.split("pp_ai_victuals_market_on_food_crisis", maxsplit=1)[1]

    assert "pp_ai_victuals_market_on_food_crisis" in entries
    assert "every_owned_location" in action_text
    assert "limit = { is_province_capital = yes }" in action_text
    assert "save_scope_as = pp_food_crisis_capital" in action_text
    assert "scope:pp_food_crisis_capital" in action_text
    assert "province_monthly_food_production > 100" in action_text
    assert "province_monthly_food_production < -30" in action_text
    assert "every_province" not in action_text
    assert "every_location_in_province" not in action_text
    assert "any_location_in_province" not in action_text


def test_four_yearly_capacity_culling_v2_is_wired_without_legacy_double_cull() -> None:
    pulse_entries = {entry.key: entry.value for entry in parse_file(COUNTRY_FOUR_YEARLY).entries}
    assert "four_yearly_country_pulse" in pulse_entries

    pulse = pulse_entries["four_yearly_country_pulse"]
    assert isinstance(pulse, CList)
    on_actions = _entry_values(pulse)["on_actions"]
    assert isinstance(on_actions, CList)

    assert on_actions.items == ["pp_cull_capacity_buildings_over_max_v2", "pp_ai_victuals_market_on_food_crisis"]

    legacy_entries = {entry.key for entry in parse_file(BUILDING_CULLING).entries}
    assert "pp_cull_over_cap_buildings" not in legacy_entries


def test_capacity_culling_v2_calls_helper_for_each_capacity_building() -> None:
    expected_calls = [
        *((building, f"farm_capacity_max_{building}") for building in LAND_FARM_BUILDINGS),
        *((building, f"fish_capacity_max_{building}") for building in FISH_CAP_BUILDINGS),
        *((building, f"forest_capacity_max_{building}") for building in FOREST_CAP_BUILDINGS),
    ]

    action_entries = {entry.key: entry.value for entry in parse_file(BUILDING_CAPACITY_CULLING_V2).entries}
    action = action_entries["pp_cull_capacity_buildings_over_max_v2"]
    assert isinstance(action, CList)

    effect = _entry_values(action)["effect"]
    assert isinstance(effect, CList)
    location_scopes = [entry.value for entry in effect.entries if entry.key == "every_owned_location"]
    assert len(location_scopes) == 1
    location = location_scopes[0]
    assert isinstance(location, CList)

    calls = []
    for entry in location.entries:
        if entry.key != "pp_cull_capacity_building_above_max":
            continue
        assert isinstance(entry.value, CList)
        values = _entry_values(entry.value)
        calls.append((values["building"], values["max_level"]))

    assert calls == expected_calls


def test_capacity_culling_helper_uses_exact_max_plus_one_threshold() -> None:
    effect_entries = {entry.key: entry.value for entry in parse_file(CAPACITY_CULLING_EFFECTS).entries}
    helper = effect_entries["pp_cull_capacity_building_above_max"]
    assert isinstance(helper, CList)

    helper_if = _entry_values(helper)["if"]
    assert isinstance(helper_if, CList)
    helper_if_values = _entry_values(helper_if)

    limit = helper_if_values["limit"]
    assert isinstance(limit, CList)
    limit_values = _entry_values(limit)
    assert limit_values["has_building"] == "building_type:$building$"
    building_level = _entry_values(limit)["location_building_level"]
    assert isinstance(building_level, CList)

    building_level_entries = {entry.key: entry for entry in building_level.entries}
    assert building_level_entries["building_type"].value == "building_type:$building$"
    assert building_level_entries["value"].op == ">"

    threshold = building_level_entries["value"].value
    assert isinstance(threshold, CList)
    assert _entry_values(threshold) == {"value": "$max_level$", "add": 1}

    change = helper_if_values["change_building_level_in_location"]
    assert isinstance(change, CList)
    assert _entry_values(change) == {"building": "building_type:$building$", "value": -1}


def test_capacity_culling_v2_avoids_pooled_and_iterative_culling() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (BUILDING_CAPACITY_CULLING_V2, CAPACITY_CULLING_EFFECTS)
    )

    forbidden_tokens = (
        "destroy_building",
        "while =",
        "random_buildings_in_location",
        "ordered_buildings_in_location",
        "every_buildings_in_location",
        "farm_capacity_remaining < 0",
        "fish_capacity_remaining < 0",
        "forest_capacity_remaining < 0",
    )
    assert not [token for token in forbidden_tokens if token in text]


def test_setup_estate_building_culling_is_registered_and_internal() -> None:
    game_start_entries = {entry.key: entry.value for entry in parse_file(GAME_START).entries}
    game_start = game_start_entries["on_game_start"]
    assert isinstance(game_start, CList)
    on_actions = _entry_values(game_start)["on_actions"]
    assert isinstance(on_actions, CList)

    assert "pp_cull_setup_estate_buildings" in on_actions.items
    assert on_actions.items.index("pp_cull_setup_estate_buildings") < on_actions.items.index(
        "pp_game_start_effect"
    )

    culling_entries = {entry.key: entry.value for entry in parse_file(ESTATE_SETUP_CULLING).entries}
    assert "pp_cull_setup_estate_buildings" in culling_entries

    culling_text = ESTATE_SETUP_CULLING.read_text(encoding="utf-8-sig")
    assert "has_game_rule" not in culling_text
    assert not (
        MOD_ROOT / "main_menu" / "common" / "game_rules" / "pp_estate_setup_culling_rules.txt"
    ).exists()

    localization = (LOCALIZATION_ROOT / "pp_game_rules_l_english.yml").read_text(encoding="utf-8-sig")
    assert "estate_setup_culling" not in localization


def test_setup_estate_building_culling_covers_vanilla_estate_buildings() -> None:
    estate_buildings = set(_vanilla_estate_buildings())
    culling_text = ESTATE_SETUP_CULLING.read_text(encoding="utf-8-sig")

    gated_buildings = set(re.findall(r"has_building = building_type:([A-Za-z0-9_]+)", culling_text))
    destroyed_buildings = set(
        re.findall(r"destroy_all_buildings_of_type = building_type:([A-Za-z0-9_]+)", culling_text)
    )

    assert gated_buildings == estate_buildings
    assert destroyed_buildings == estate_buildings
    assert culling_text.count("chance = 65") == len(estate_buildings)
    assert "construct_building" not in culling_text
    assert "construct_estate_building" not in culling_text
    assert "destroy_building =" not in culling_text
    assert "destroy_building_forcefully" not in culling_text


def test_setup_estate_building_culling_preserves_vanilla_start_estate_locations() -> None:
    explicit_locations = _vanilla_start_estate_locations_by_building()
    trigger_entries = {entry.key: entry.value for entry in parse_file(ESTATE_START_PRESERVATION).entries}

    expected_triggers = {
        f"pp_vanilla_start_{building}_location" for building in explicit_locations
    }
    assert set(trigger_entries) == expected_triggers

    culling_text = ESTATE_SETUP_CULLING.read_text(encoding="utf-8-sig")
    for building, locations in explicit_locations.items():
        trigger_name = f"pp_vanilla_start_{building}_location"
        assert f"NOT = {{ {trigger_name} = yes }}" in culling_text

        trigger = trigger_entries[trigger_name]
        assert isinstance(trigger, CList)
        values = _entry_values(trigger)
        or_block = values["OR"]
        assert isinstance(or_block, CList)
        preserved = {entry.value for entry in or_block.entries if entry.key == "this"}
        assert preserved == {f"location:{location}" for location in locations}


def test_replaced_buildings_do_not_reuse_vanilla_unique_method_names() -> None:
    vanilla_methods_by_building = _vanilla_unique_methods_by_building()
    offenders = []

    for blueprint in accepted_blueprint_files(ROOT / "blueprints" / "accepted"):
        template = load_template(blueprint)
        if template.mode != "REPLACE":
            continue
        vanilla_methods = vanilla_methods_by_building.get(template.key)
        if not vanilla_methods:
            continue
        rendered = parse_text(
            f"{template.key} = {{\n{template.building_body}\n}}\n",
            path=blueprint,
        )
        unique_methods = _unique_production_method_names(rendered.entries[0].value)
        reused = sorted(unique_methods & vanilla_methods)
        if reused:
            offenders.append(f"{blueprint.relative_to(ROOT)}: {', '.join(reused)}")
        non_pp = sorted(method for method in unique_methods if not method.startswith("pp_"))
        if non_pp:
            offenders.append(f"{blueprint.relative_to(ROOT)} non-pp methods: {', '.join(non_pp)}")

    assert not offenders


def test_replaced_buildings_preserve_vanilla_audio_and_startup_fields() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_profile = load_order.profile("vanilla")
    vanilla_buildings = {
        entry.key: entry.value
        for entry in load_merged_directory(vanilla_profile, "building_types").entries
    }
    checked_fields = ("audio_tier", "startup_ramp_target")
    offenders = []

    for blueprint in accepted_blueprint_files(ROOT / "blueprints" / "accepted"):
        template = load_template(blueprint)
        if template.mode != "REPLACE":
            continue
        vanilla = vanilla_buildings.get(template.key)
        if vanilla is None:
            offenders.append(f"{blueprint.relative_to(ROOT)}: missing vanilla building {template.key}")
            continue
        rendered = parse_text(
            f"{template.key} = {{\n{template.building_body}\n}}\n",
            path=blueprint,
        )
        body = rendered.entries[0].value
        assert isinstance(body, CList)
        for field in checked_fields:
            expected = vanilla.values(field)
            actual = body.values(field)
            if actual != expected:
                offenders.append(
                    f"{blueprint.relative_to(ROOT)}: {field} expected {expected!r}, got {actual!r}"
                )

    assert not offenders


def test_land_owning_farmers_is_a_full_privilege_replacement() -> None:
    parsed = parse_file(ESTATE_PRIVILEGE_ADJUSTMENTS)
    entries = {entry.key: entry.value for entry in parsed.entries}

    assert "TRY_REPLACE:land_owning_farmers" in entries
    assert "TRY_INJECT:land_owning_farmers" not in entries
    privilege = entries["TRY_REPLACE:land_owning_farmers"]
    assert isinstance(privilege, CList)

    privilege_values = _entry_values(privilege)
    assert privilege_values["estate"] == "peasants_estate"
    assert privilege_values["content_priority"] == 200
    assert "potential" in privilege_values
    assert "can_revoke" in privilege_values

    country_modifier = privilege_values["country_modifier"]
    assert isinstance(country_modifier, CList)
    modifier_values = _entry_values(country_modifier)
    assert "global_monthly_food_modifier" not in modifier_values
    assert modifier_values["levy_combat_efficiency_modifier"] == 0.05
    assert modifier_values["global_population_capacity_modifier"] == 0.05
    assert modifier_values["global_wheat_output_modifier"] == 0.05
    assert modifier_values["global_fish_output_modifier"] == 0.05
    assert modifier_values["global_millet_output_modifier"] == 0.05
    assert modifier_values["global_peasants_estate_power"] == 0.5


def test_powerful_magnates_food_modifier_is_zeroed_by_replacement() -> None:
    parsed = parse_file(GOVERNMENT_REFORM_ADJUSTMENTS)
    entries = {entry.key: entry.value for entry in parsed.entries}

    assert "REPLACE:hun_power_to_magnates" in entries
    assert "TRY_INJECT:hun_power_to_magnates" not in entries
    reform = entries["REPLACE:hun_power_to_magnates"]
    assert isinstance(reform, CList)

    reform_values = _entry_values(reform)
    assert reform_values["age"] == "age_2_renaissance"
    assert reform_values["unique"] is True
    assert reform_values["content_priority"] == 600
    assert "potential" in reform_values
    assert reform_values["years"] == 2

    country_modifier = reform_values["country_modifier"]
    assert isinstance(country_modifier, CList)
    modifier_values = _entry_values(country_modifier)
    assert modifier_values["global_nobles_estate_power"] == 1.0
    assert modifier_values["global_estate_target_satisfaction"] == "medium_permanent_target_satisfaction"
    assert modifier_values["global_monthly_food_modifier"] == 0


def test_dhimmi_satisfaction_is_not_overridden_by_estate_adjustments() -> None:
    parsed = parse_file(ESTATE_ADJUSTMENTS)
    entries = {entry.key: entry.value for entry in parsed.entries}

    assert "TRY_INJECT:dhimmi_estate" not in entries


def test_inject_targets_exist_in_constructor_load_order() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_root = load_order.vanilla_root
    offenders: list[str] = []

    for relative_common, vanilla_common in (
        (Path("in_game") / "common", vanilla_root / "game" / "in_game" / "common"),
        (Path("main_menu") / "common", vanilla_root / "game" / "main_menu" / "common"),
    ):
        mod_common = MOD_ROOT / relative_common
        for collection_dir in sorted(path for path in mod_common.iterdir() if path.is_dir()):
            collection = collection_dir.relative_to(mod_common)
            existing = _database_keys(vanilla_common / collection)
            if collection == Path("static_modifiers"):
                existing |= _database_keys(vanilla_root / "game" / "main_menu" / "common" / collection)

            for path in sorted(collection_dir.rglob("*.txt")):
                for entry in parse_file(path).entries:
                    if not isinstance(entry.value, CList):
                        continue
                    mode, key = _entry_mode(entry.key)
                    if mode in {"INJECT", "TRY_INJECT"} and key not in existing:
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{entry.location.line} {mode}:{key}"
                        )
                    if mode in {"CREATE", "REPLACE", "REPLACE_OR_CREATE", "INJECT_OR_CREATE"}:
                        existing.add(key)
                    elif mode in {"TRY_REPLACE", "INJECT", "TRY_INJECT"} and key in existing:
                        existing.add(key)

    assert not offenders


def test_constructor_building_methods_are_resolved_and_unique() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")

    assert data.building_data.duplicate_production_methods.is_empty()
    assert data.building_data.unresolved_production_methods.is_empty()
    assert data.building_data.warnings == []


def test_cookery_building_line_has_resolved_prices() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    buildings = {row["name"]: row for row in data.building_data.buildings.to_dicts()}

    assert buildings["cookery"]["price"] == "pp_cookery_price"
    assert buildings["cookery"]["price_gold"] == 100.0
    assert buildings["victualling_yard"]["price"] == "pp_victualling_yard_price"
    assert buildings["victualling_yard"]["price_gold"] == 225.0
    assert buildings["victuals_market"]["price"] == "pp_victuals_market_price"
    assert buildings["victuals_market"]["price_gold"] == 100.0


def test_victuals_pop_demand_uses_scalar_database_value() -> None:
    entries = {entry.key: entry.value for entry in parse_file(GOODS_DEMAND).entries}
    pop_demand = entries["INJECT:pop_demand"]
    assert isinstance(pop_demand, CList)

    values = _entry_values(pop_demand)
    assert values["victuals"] == 1


def test_pp_law_adjustments_use_existing_modifier_types() -> None:
    text = LAW_ADJUSTMENTS.read_text(encoding="utf-8-sig")

    assert "army_infantry_maintenance_cost_modifier" not in text
    assert "trade_efficiency =" not in text
    assert "enable_pronoia_subject = yes" in text
    assert "subject_income_modifier = 0.15" in text
    assert "trade_land_efficiency = small_trade_efficiency_bonus" in text
    assert "trade_sea_efficiency = small_trade_efficiency_bonus" in text


def test_feudal_administration_override_tracks_vanilla_law() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_entries = _database_entries(
        load_order.vanilla_root / "game" / "in_game" / "common" / "laws"
    )
    mod_entries = {entry.key: entry.value for entry in parse_file(LAW_ADJUSTMENTS).entries}

    vanilla_admin = vanilla_entries["administrative_system"]
    mod_admin = mod_entries["TRY_REPLACE:administrative_system"]
    assert isinstance(vanilla_admin, CList)
    assert isinstance(mod_admin, CList)

    assert _normalized_without_entry(vanilla_admin, "feudal_administration") == (
        _normalized_without_entry(mod_admin, "feudal_administration")
    )

    feudal = _entry_values(mod_admin)["feudal_administration"]
    assert isinstance(feudal, CList)
    country_modifier = _entry_values(feudal)["country_modifier"]
    assert isinstance(country_modifier, CList)

    modifier_values = _entry_values(country_modifier)
    assert "global_monthly_food_modifier" not in modifier_values
    assert modifier_values["global_wheat_output_modifier"] == 0.1
    assert modifier_values["global_fish_output_modifier"] == 0.1
    assert modifier_values["global_horses_output_modifier"] == 0.025
    assert modifier_values["global_fiber_crops_output_modifier"] == 0.025
    assert modifier_values["global_peasants_food_consumption"] == -0.01


def test_pp_building_prices_have_modifier_type_assets_and_localization() -> None:
    price_keys = {
        key
        for key in _database_keys(PRICE_ROOT)
        if key.startswith("pp_") and key.endswith("_price")
    }
    expected = {f"{price_key}_cost_modifier" for price_key in price_keys}

    modifier_types = _database_keys(MODIFIER_TYPE_DEFINITIONS)
    modifier_icons = _database_keys(MODIFIER_ICONS)
    localization_text = "\n".join(
        path.read_text(encoding="utf-8-sig") for path in sorted(LOCALIZATION_ROOT.glob("*.yml"))
    )

    assert expected
    assert not (expected - modifier_types)
    assert not (expected - modifier_icons)
    assert not [
        key
        for key in sorted(expected)
        if f"MODIFIER_TYPE_DESC_{key}:" not in localization_text
        or f"MODIFIER_TYPE_NAME_{key}:" not in localization_text
    ]
    assert not [key for key in sorted(price_keys) if f"{key}:" not in localization_text]


def test_victuals_pop_demand_modifier_type_is_registered() -> None:
    modifier_types = _database_keys(MODIFIER_TYPE_DEFINITIONS)
    modifier_icons = _database_keys(MODIFIER_ICONS)
    localization_text = "\n".join(
        path.read_text(encoding="utf-8-sig") for path in sorted(LOCALIZATION_ROOT.glob("*.yml"))
    )

    assert "global_victuals_pop_demand" in modifier_types
    assert "global_victuals_pop_demand" in modifier_icons
    assert "MODIFIER_TYPE_NAME_global_victuals_pop_demand:" in localization_text
    assert "MODIFIER_TYPE_DESC_global_victuals_pop_demand:" in localization_text


def test_current_megalopolis_buildings_allow_megalopolis() -> None:
    for blueprint_name in ("dock", "fruit_orchard", "irrigation_systems"):
        template = load_template(ROOT / "blueprints" / "accepted" / "buildings" / f"{blueprint_name}.yml")
        rendered = parse_text(
            f"{template.key} = {{\n{template.building_body}\n}}\n",
            path=Path(f"{blueprint_name}.yml"),
        )
        values = _entry_values(rendered.entries[0].value)
        assert values["megalopolis"] is True


def test_victuals_market_construction_and_coastal_saltern_debug_keys_are_localized() -> None:
    victuals_market = load_template(ROOT / "blueprints" / "accepted" / "buildings" / "victuals_market.yml")
    coastal_saltern = load_template(ROOT / "blueprints" / "accepted" / "buildings" / "coastal_saltern.yml")

    assert victuals_market.localization["victuals_market_construction"] == "Victuals Market Construction"

    rendered = parse_text(
        f"{coastal_saltern.key} = {{\n{coastal_saltern.building_body}\n}}\n",
        path=Path("coastal_saltern.yml"),
    )
    body = rendered.entries[0].value
    assert isinstance(body, CList)
    methods = body.values("unique_production_methods")[0]
    assert isinstance(methods, CList)
    base = _entry_values(methods)["pp_coastal_saltern_base_salt"]
    assert isinstance(base, CList)
    base_values = _entry_values(base)
    assert base_values["output"] == 0.24

    worked_methods = body.values("unique_production_methods")[1]
    assert isinstance(worked_methods, CList)
    lined_pans = _entry_values(worked_methods)["pp_coastal_saltern_lined_evaporation_pans"]
    assert isinstance(lined_pans, CList)
    values = _entry_values(lined_pans)
    assert values["output"] == 0.72
    assert values["clay"] == 4.0
    assert values["pottery"] == 1.15


def test_salt_rgo_bonus_reduces_food_decay_without_affecting_saltpeter() -> None:
    bonuses = {entry.key: entry.value for entry in parse_file(RGO_STATIC_BONUSES).entries}

    salt = bonuses["pp_rgo_bonus_salt"]
    saltpeter = bonuses["pp_rgo_bonus_saltpeter"]
    assert isinstance(salt, CList)
    assert isinstance(saltpeter, CList)

    assert _entry_values(salt)["local_food_decay_modifier"] == -0.00070
    assert "local_food_decay_modifier" not in _entry_values(saltpeter)


def test_rgo_static_bonus_own_good_outputs_are_twenty_percent() -> None:
    for good, values in _rgo_bonus_values().items():
        own_output = f"local_{good}_output_modifier"
        assert values[own_output] == 0.20, good


def test_rgo_static_bonus_manpower_effects_are_toned_down() -> None:
    bonuses = _rgo_bonus_values()

    assert bonuses["elephants"]["local_manpower"] == 0.001
    assert bonuses["horses"]["local_manpower"] == 0.001
    assert bonuses["lead"]["local_manpower_modifier"] == 0.001
    assert bonuses["saltpeter"]["local_manpower_modifier"] == 0.002


def test_rgo_static_bonuses_do_not_use_rejected_modifier_hooks() -> None:
    rejected = {
        "local_trade_center_power",
        "local_ship_build_speed",
        "local_slave_pop_satisfaction",
    }

    for good, values in _rgo_bonus_values().items():
        assert rejected.isdisjoint(values), good


def test_rgo_static_bonus_production_efficiency_is_limited_and_has_downsides() -> None:
    bonuses = _rgo_bonus_values()
    allowed = {"alum", "dyes", "mercury"}
    actual = {good for good, values in bonuses.items() if "local_production_efficiency" in values}
    assert actual == allowed

    negative_downsides = {
        "local_disease_resistance",
        "local_population_capacity_modifier",
        "local_population_growth",
    }
    for good in allowed:
        values = bonuses[good]
        has_negative_downside = any(float(values.get(key, 0)) < 0 for key in negative_downsides)
        has_unrest_downside = float(values.get("local_unrest", 0)) > 0
        assert has_negative_downside or has_unrest_downside, good


def test_rgo_static_bonus_max_control_magnitude_is_capped() -> None:
    for good, values in _rgo_bonus_values().items():
        if "local_max_control" in values:
            assert abs(float(values["local_max_control"])) <= 0.05, good


def test_wool_rgo_bonus_has_no_population_growth_penalty() -> None:
    assert "local_population_growth" not in _rgo_bonus_values()["wool"]


def test_rgo_static_bonus_game_start_uses_shared_refresh_effect() -> None:
    game_start = GAME_START.read_text(encoding="utf-8-sig")

    assert "pp_refresh_rgo_static_bonus = yes" in game_start
    assert "pp_refresh_fruit_orchard_eligibility = yes" in game_start
    assert "set_variable = { name = pp_fruit_orchard_eligible value = 0 }" in game_start
    assert "modifier = pp_rgo_bonus_" not in game_start


def test_raw_material_change_hook_refreshes_rgo_static_bonus() -> None:
    entries = {entry.key: entry.value for entry in parse_file(RAW_MATERIAL_CHANGED).entries}

    on_raw_material_changed = entries["on_raw_material_changed"]
    refresh_on_action = entries["pp_refresh_rgo_static_bonus_on_raw_material_changed"]
    assert isinstance(on_raw_material_changed, CList)
    assert isinstance(refresh_on_action, CList)

    on_actions = _entry_values(on_raw_material_changed)["on_actions"]
    assert isinstance(on_actions, CList)
    assert "pp_refresh_rgo_static_bonus_on_raw_material_changed" in {str(item) for item in on_actions.items}
    assert _clist_contains(refresh_on_action, "pp_refresh_rgo_static_bonus", True)
    assert _clist_contains(refresh_on_action, "pp_refresh_fruit_orchard_eligibility", True)


def test_rgo_static_bonus_refresh_removes_and_reapplies_all_bonus_modifiers() -> None:
    bonuses = _rgo_bonus_values()
    effect_text = RGO_STATIC_BONUS_EFFECTS.read_text(encoding="utf-8-sig")
    effects = {entry.key: entry.value for entry in parse_file(RGO_STATIC_BONUS_EFFECTS).entries}
    refresh = effects["pp_refresh_rgo_static_bonus"]
    orchard_refresh = effects["pp_refresh_fruit_orchard_eligibility"]
    assert isinstance(refresh, CList)
    assert isinstance(orchard_refresh, CList)
    assert "set_variable = { name = pp_fruit_orchard_eligible value = 0 }" in effect_text
    assert "set_variable = { name = pp_fruit_orchard_eligible value = 1 }" in effect_text
    assert "pp_fruit_orchard_location_potential = yes" in effect_text

    for good in bonuses:
        modifier = f"pp_rgo_bonus_{good}"
        assert _clist_contains(refresh, "remove_location_modifier", modifier), good
        assert f"raw_material = goods:{good}" in effect_text, good
        assert f"modifier = {modifier}" in effect_text, good


def test_columbian_exchange_actions_refresh_rgo_bonus_after_raw_material_swap() -> None:
    action_text = COLUMBIAN_EXCHANGE_RGO_REFRESH_ACTIONS.read_text(encoding="utf-8-sig")
    entries = {entry.key: entry.value for entry in parse_file(COLUMBIAN_EXCHANGE_RGO_REFRESH_ACTIONS).entries}

    for action_key in (
        "TRY_REPLACE:move_nw_good_to_new_location",
        "TRY_REPLACE:move_ow_good_to_new_location",
    ):
        assert action_key in entries

    assert action_text.count("change_raw_material = scope:target_good") == 2
    assert action_text.count("pp_refresh_rgo_static_bonus = yes") == 2
    assert action_text.count("pp_refresh_fruit_orchard_eligibility = yes") == 2
    assert action_text.count(
        "change_raw_material = scope:target_good\n\t\t\tpp_refresh_rgo_static_bonus = yes"
    ) == 2


def test_columbian_exchange_debug_event_refreshes_after_raw_material_swap() -> None:
    event_text = COLUMBIAN_EXCHANGE_DEBUG_EVENT.read_text(encoding="utf-8-sig")
    entries = {entry.key: entry.value for entry in parse_file(COLUMBIAN_EXCHANGE_DEBUG_EVENT).entries}

    assert "pp_columbian_exchange_debug.1" in entries
    assert "activate_situation = situation:columbian_exchange" in event_text
    assert "set_variable = { name = is_in_columbian_exchange value = yes }" in event_text
    assert "change_raw_material = goods:maize" in event_text
    assert "change_raw_material = goods:potato" in event_text
    assert "pp_refresh_rgo_static_bonus = yes" in event_text
    assert "pp_refresh_fruit_orchard_eligibility = yes" in event_text
    assert event_text.count(
        "change_raw_material = goods:maize\n\t\t\t}\n\t\t\tpp_refresh_rgo_static_bonus = yes"
    ) == 1


def test_columbian_exchange_debug_event_keys_are_localized() -> None:
    localization_text = (LOCALIZATION_ROOT / "pp_debug_l_english.yml").read_text(encoding="utf-8-sig")

    for key in (
        "pp_columbian_exchange_debug.1.title",
        "pp_columbian_exchange_debug.1.desc",
        "pp_columbian_exchange_debug.1.a",
    ):
        assert f" {key}:" in localization_text


def test_farming_village_uses_baseline_building_price() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    annotated = annotate_building_data_availability(data.building_data, data.advancements)
    buildings = {row["name"]: row for row in annotated.buildings.to_dicts()}

    farming_village = buildings["farming_village"]
    assert farming_village["price"] is None
    assert farming_village["effective_price"] == "p_building_age_1_traditions"
    assert farming_village["effective_price_gold"] == 50.0
    assert farming_village["price_kind"] == "baseline_age"


def test_labeling_output_modifier_config_loads_explicit_goods() -> None:
    cfg = load_mod_injector_config(ROOT / "labeling_output_modifiers.yaml")

    assert cfg.defaults["null_productivity"] == -0.7
    assert cfg.defaults["raw_material_output_floor"] == -0.2
    assert cfg.defaults["scale_args"] == {"output_min": -0.7, "output_max": 0.3}
    assert cfg.location_templates_load_order == ROOT / "constructor.load_order.toml"
    assert [g.trade_good for g in cfg.goods] == [
        "beeswax",
        "chili",
        "cloves",
        "cocoa",
        "coffee",
        "cotton",
        "dyes",
        "elephants",
        "fiber_crops",
        "fish",
        "fruit",
        "fur",
        "horses",
        "incense",
        "ivory",
        "legumes",
        "livestock",
        "lumber",
        "maize",
        "medicaments",
        "millet",
        "olives",
        "pepper",
        "potato",
        "rice",
        "saffron",
        "silk",
        "sugar",
        "tea",
        "tobacco",
        "wheat",
        "wild_game",
        "wine",
        "wool",
    ]
    assert all(g.enabled for g in cfg.goods)


def _vanilla_estate_buildings() -> tuple[str, ...]:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    estate_buildings = (
        load_order.vanilla_root
        / "game"
        / "in_game"
        / "common"
        / "building_types"
        / "estate_buildings.txt"
    )
    return tuple(entry.key for entry in parse_file(estate_buildings).entries if isinstance(entry.value, CList))


def _vanilla_start_estate_locations_by_building() -> dict[str, set[str]]:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_root = load_order.vanilla_root / "game"
    estate_buildings = set(_vanilla_estate_buildings())

    setup = parse_setup_model(
        (vanilla_root / "main_menu" / "setup" / "start" / "07_cities_and_buildings.txt").read_text(
            encoding="utf-8-sig"
        )
    )
    town_setups = parse_town_setups(
        (vanilla_root / "in_game" / "common" / "town_setups" / "00_default.txt").read_text(
            encoding="utf-8-sig"
        )
    )

    result: dict[str, set[str]] = {building: set() for building in estate_buildings}
    for entry in setup.direct_entries:
        if entry.building in estate_buildings:
            result[entry.building].add(entry.location)

    for location, entry in setup.locations.items():
        if entry.town_setup is None:
            continue
        expanded = expand_town_setup(entry.town_setup, town_setups)
        for building in expanded:
            if building in estate_buildings:
                result[building].add(location)

    return {building: locations for building, locations in sorted(result.items()) if locations}


def _vanilla_unique_methods_by_building() -> dict[str, set[str]]:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    building_dir = load_order.vanilla_root / "game" / "in_game" / "common" / "building_types"
    result: dict[str, set[str]] = {}
    for path in sorted(building_dir.glob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                methods = _unique_production_method_names(entry.value)
                if methods:
                    result[entry.key] = methods
    return result


def _custom_tags(value: object) -> set[str]:
    assert isinstance(value, CList)
    return {str(item) for item in value.items}


def _clist_contains(block: CList, key: str, value: object) -> bool:
    return any(
        (entry.key == key and entry.value == value)
        or (isinstance(entry.value, CList) and _clist_contains(entry.value, key, value))
        for entry in block.entries
    )


def _entry_values(block: CList) -> dict[str, object]:
    return {entry.key: entry.value for entry in block.entries}


def _accepted_blueprint_building_values(building: str) -> dict[str, object]:
    blueprint = BUILDING_BLUEPRINT_ROOT / f"{building}.yml"
    template = load_template(blueprint)
    rendered = parse_text(
        f"{template.key} = {{\n{template.building_body}\n}}\n",
        path=blueprint,
    )
    body = rendered.entries[0].value
    assert isinstance(body, CList)
    return _entry_values(body)


def _rgo_bonus_values() -> dict[str, dict[str, object]]:
    bonuses: dict[str, dict[str, object]] = {}
    for entry in parse_file(RGO_STATIC_BONUSES).entries:
        if not entry.key.startswith("pp_rgo_bonus_"):
            continue
        assert isinstance(entry.value, CList)
        bonuses[entry.key.removeprefix("pp_rgo_bonus_")] = _entry_values(entry.value)
    return bonuses


def _database_keys(root: Path) -> set[str]:
    if not root.exists():
        return set()
    keys: set[str] = set()
    for path in sorted(root.rglob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                keys.add(_entry_mode(entry.key)[1])
    return keys


def _database_entries(root: Path) -> dict[str, object]:
    entries: dict[str, object] = {}
    for path in sorted(root.rglob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                entries[_entry_mode(entry.key)[1]] = entry.value
    return entries


def _normalized_without_entry(block: CList, key: str) -> object:
    normalized = normalized_value(block)
    assert isinstance(normalized, dict)
    normalized["entries"] = [
        {"key": entry["key"], "op": entry["op"], "value": f"<{key}>"}
        if entry["key"] == key
        else entry
        for entry in normalized["entries"]
    ]
    return normalized


def _entry_mode(raw_key: str) -> tuple[str, str]:
    if ":" not in raw_key:
        return "CREATE", raw_key
    mode, key = raw_key.split(":", 1)
    return mode.strip().upper(), key


def _text_block_between(text: str, start: str, end: str) -> str:
    _, tail = text.split(start, 1)
    block, _ = tail.split(end, 1)
    return start + block


def _script_value_block(text: str, key: str) -> str:
    marker = f"{key} = {{"
    start = text.index(marker)
    brace_start = text.index("{", start)
    depth = 0
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated scripted value block: {key}")


def _farm_cap_excluded_blueprints() -> tuple[Path, ...]:
    excluded = set(EXCLUDED_FARM_CAP_BUILDINGS)
    extractive_markers = (
        "_mine",
        "_quarry",
        "_pit",
        "_washmill",
        "_collector",
        "_smelter",
        "_diggings",
        "_sluice",
        "_beds",
        "_washery",
    )

    for path in BUILDING_BLUEPRINT_ROOT.glob("*.yml"):
        key = path.stem
        if key in LAND_FARM_BUILDINGS:
            continue
        if any(marker in key for marker in extractive_markers):
            excluded.add(key)
        if "smelter" in key:
            excluded.add(key)

    return tuple(sorted(BUILDING_BLUEPRINT_ROOT / f"{key}.yml" for key in excluded))


def _unique_production_method_names(block: CList) -> set[str]:
    names: set[str] = set()
    for value in block.values("unique_production_methods"):
        if isinstance(value, CList):
            names.update(entry.key for entry in value.entries)
    return names
