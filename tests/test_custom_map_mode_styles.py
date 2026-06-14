from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
MAP_MODE_ROOT = MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes"
LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_building_adjustments_l_english.yml"
CALIBRATION = ROOT / "tools" / "map_mode_scale_calibration.json"
BUILDING_EFFICIENCY_SCRIPT_VALUE = (
    MOD_ROOT / "in_game" / "common" / "script_values" / "pp_building_efficiency_map_mode.txt"
)

VANILLA_TRAFFIC_COLORS = (
    "define:NMapColors|MAP_COLOR_MIN",
    "define:NMapColors|MAP_COLOR_LOW",
    "define:NMapColors|MAP_COLOR_MID",
    "define:NMapColors|MAP_COLOR_HIGH",
    "define:NMapColors|MAP_COLOR_MAX",
)

LEGACY_COLORS = (
    "rgb { 0 34 78 }",
    "rgb { 53 69 108 }",
    "rgb { 125 124 120 }",
    "rgb { 200 184 102 }",
    "rgb { 254 232 56 }",
    "rgb { 0 255 0 }",
    "rgb { 255 0 0 }",
)

CUSTOM_MAP_MODE_FILES = (
    MAP_MODE_ROOT / "pp_goods_output_map_modes_generated.txt",
    MAP_MODE_ROOT / "pp_local_output_modifier_map_modes.txt",
    MAP_MODE_ROOT / "pp_population_capacity_map_modes.txt",
    MAP_MODE_ROOT / "pp_food_map_modes.txt",
    MAP_MODE_ROOT / "pp_unemployed_peasants_map_modes.txt",
    MAP_MODE_ROOT / "pp_building_levels_map_modes.txt",
    MAP_MODE_ROOT / "pp_rgo_level_map_modes.txt",
)

VALUE_SOURCE_MODES = {
    "pp_population_capacity": "modifier:local_population_capacity",
    "pp_fishing_village_capacity": "fish_capacity",
    "pp_farming_village_capacity": "farm_capacity",
    "pp_forest_village_capacity": "forest_capacity",
    "pp_unemployed_peasants": "pp_unemployed_population",
    "pp_building_levels": "total_building_levels",
    "pp_unsupported_building_levels": "pp_unsupported_building_levels_map_value",
    "pp_building_efficiency": "pp_building_efficiency_map_value",
    "pp_rgo_level": "pp_rgo_level_for_map",
}

STRUCTURE_SNIPPETS = {
    "pp_population_capacity": (
        "category = population",
        "index = 1",
        "color_refresh_counters = { LocationDevelopmentChanged LocationPopulationChanged }",
        "color_and_names_refresh_counters = { LocationOwnerChanged CountryStatus }",
    ),
    "pp_population_growth": (
        "category = population",
        "index = 1",
        "secondary_map_color = {",
        "modifier:local_population_growth >= @pp_population_growth_cap_stripe",
        "province = { is_starving = yes }",
        "define:NMapColors|POPULATION_STARVING_COLOR_STRIPE",
        "MAPMODE_PP_POPULATION_GROWTH_STARVING",
        "color_refresh_counters = { LocationDevelopmentChanged LocationPopulationChanged }",
    ),
    "pp_market_food_price": (
        "category = economy",
        "index = 3",
        "small_map_names = market",
        "small_tooltip_context = market",
        "market_marker = yes",
        "toll_marker = yes",
        "map_lines_mode = ToMarketCenter",
        "color_and_names_refresh_counters = { MarketReach LocationOwnerChanged }",
    ),
    "pp_fishing_village_capacity": (
        "category = geography",
        "index = 1",
        "color_refresh_counters = { TopographyVegetationDatabaseUpdate }",
    ),
    "pp_farming_village_capacity": (
        "category = geography",
        "index = 1",
        "color_refresh_counters = { TopographyVegetationDatabaseUpdate }",
    ),
    "pp_forest_village_capacity": (
        "category = geography",
        "index = 1",
        "color_refresh_counters = { TopographyVegetationDatabaseUpdate }",
    ),
    "pp_unemployed_peasants": (
        "category = population",
        "index = 1",
        "color_refresh_counters = { Day }",
        "color_and_names_refresh_counters = { LocationPopulationChanged }",
    ),
    "pp_building_levels": (
        "category = economy",
        "index = 0",
        "secondary_map_color = {",
        "total_building_levels > modifier:free_building_levels",
        "MAPMODE_PP_BUILDING_LEVELS_OVER_SUPPORTED",
        "color_refresh_counters = { ProductionList LocationDevelopmentChanged }",
    ),
    "pp_building_efficiency": (
        "category = economy",
        "index = 0",
        "pp_building_efficiency_map_value",
        "MAPMODE_PP_BUILDING_EFFICIENCY_TT_LAND",
        "color_refresh_counters = { ProductionList LocationDevelopmentChanged LocationPopulationChanged }",
    ),
    "pp_unsupported_building_levels": (
        "category = economy",
        "index = 0",
        "pp_unsupported_building_levels_map_value",
        "MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_TT_LAND",
        "color_refresh_counters = { ProductionList LocationDevelopmentChanged LocationPopulationChanged }",
    ),
    "pp_rgo_level": (
        "category = economy",
        "index = 1",
        "color_refresh_counters = { ProductionList LocationDevelopmentChanged }",
    ),
}


def _all_blocks() -> dict[str, str]:
    blocks: dict[str, str] = {}
    for path in CUSTOM_MAP_MODE_FILES:
        text = path.read_text(encoding="utf-8-sig")
        starts = list(re.finditer(r"^(pp_[a-z0-9_]+)\s*=\s*\{", text, flags=re.MULTILINE))
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            blocks[match.group(1)] = text[match.start() : end]
    return blocks


def _thresholds(block: str, value_name: str) -> list[float]:
    constants = _constant_values()
    pattern = rf"{re.escape(value_name)} < (@[a-zA-Z0-9_]+|-?[0-9]+(?:\.[0-9]+)?)"
    return [
        constants[value] if value.startswith("@") else float(value)
        for value in re.findall(pattern, block)
    ]


def _constant_values() -> dict[str, float]:
    constants: dict[str, float] = {}
    for path in CUSTOM_MAP_MODE_FILES:
        text = path.read_text(encoding="utf-8-sig")
        constants.update(
            {
                f"@{name}": float(value)
                for name, value in re.findall(
                    r"^@([a-zA-Z0-9_]+)\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)\s*$",
                    text,
                    flags=re.MULTILINE,
                )
            }
        )
    return constants


def test_custom_map_modes_do_not_use_rejected_palettes() -> None:
    bad: list[str] = []
    for path in CUSTOM_MAP_MODE_FILES:
        text = path.read_text(encoding="utf-8-sig")
        for snippet in LEGACY_COLORS:
            if snippet in text:
                bad.append(f"{path.name}: {snippet}")

    assert not bad


def test_custom_map_mode_constants_are_numeric_only() -> None:
    bad: list[str] = []
    for path in CUSTOM_MAP_MODE_FILES:
        text = path.read_text(encoding="utf-8-sig")
        for name, value in re.findall(r"^(@[a-zA-Z0-9_]+)\s*=\s*(.+?)\s*$", text, flags=re.MULTILINE):
            value = value.split("#", 1)[0].strip()
            if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
                bad.append(f"{path.name}: {name} = {value}")

    assert not bad


def test_quantity_map_modes_use_vanilla_traffic_light_buckets_without_losing_sources() -> None:
    blocks = _all_blocks()

    bad: list[str] = []
    for mode, value_source in VALUE_SOURCE_MODES.items():
        block = blocks[mode]
        if value_source not in block:
            bad.append(f"{mode}: missing value source {value_source}")
        if block.count("lerp = {") < 4:
            bad.append(f"{mode}: missing bucket gradients")
        if block.count("legend_key =") < 5:
            bad.append(f"{mode}: missing concise legend anchors")
        for color in VANILLA_TRAFFIC_COLORS:
            if color not in block:
                bad.append(f"{mode}: missing {color}")
        if "max = 1" not in block or "min = 0" not in block:
            bad.append(f"{mode}: missing factor clamps")

    assert not bad


def test_static_map_modes_match_calibration_thresholds() -> None:
    blocks = _all_blocks()
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))["scales"]

    expected = {
        "pp_population_capacity": ("modifier:local_population_capacity", calibration["population_capacity"]["thresholds"]),
        "pp_fishing_village_capacity": ("fish_capacity", calibration["food_capacity"]["fish"]["thresholds"]),
        "pp_farming_village_capacity": ("farm_capacity", calibration["food_capacity"]["farm"]["thresholds"]),
        "pp_forest_village_capacity": ("forest_capacity", calibration["food_capacity"]["forest"]["thresholds"]),
        "pp_unemployed_peasants": ("pp_unemployed_population", calibration["unemployment"]["thresholds"]),
        "pp_building_levels": ("total_building_levels", calibration["building_levels"]["thresholds"]),
        "pp_rgo_level": ("pp_rgo_level_for_map", calibration["rgo_level"]["thresholds"]),
    }

    bad: list[str] = []
    for mode, (value_source, thresholds) in expected.items():
        generated = _thresholds(blocks[mode], value_source)
        wanted = [float(value) for value in thresholds]
        if generated != wanted:
            bad.append(f"{mode}: generated {generated}, calibration {wanted}")

    expected_signed = {
        "pp_building_efficiency": (
            "pp_building_efficiency_map_value",
            calibration["building_efficiency"],
        ),
    }

    for mode, (value_source, scale) in expected_signed.items():
        generated = _thresholds(blocks[mode], value_source)
        wanted = [
            *[float(value) for value in scale["negative_thresholds"]],
            float(scale["neutral_low"]),
            float(scale["neutral_high"]),
            *[float(value) for value in scale["positive_thresholds"]],
        ]
        if generated != wanted:
            bad.append(f"{mode}: generated {generated}, calibration {wanted}")

    assert not bad


def test_farm_capacity_scale_keeps_developed_locations_distinguishable() -> None:
    thresholds = [
        float(value)
        for value in json.loads(CALIBRATION.read_text(encoding="utf-8"))["scales"]["food_capacity"][
            "farm"
        ]["thresholds"]
    ]

    assert thresholds[2] < 14 < 18 < thresholds[3]
    assert thresholds[3] - thresholds[2] >= 8


def test_market_food_price_uses_reference_centered_buckets() -> None:
    block = _all_blocks()["pp_market_food_price"]
    scale = json.loads(CALIBRATION.read_text(encoding="utf-8"))["scales"]["market_food_price"]

    expected_thresholds = [
        *[float(value) for value in scale["low_thresholds"]],
        float(scale["reference"]),
        *[float(value) for value in scale["high_thresholds"]],
    ]
    assert _thresholds(block, "market.food_price") == expected_thresholds
    assert block.count("lerp = {") == 4
    assert "@pp_market_food_price_max" not in block
    assert "divide = @pp_market_food_price_max" not in block
    assert "MAPMODE_PP_MARKET_FOOD_PRICE_VERY_CHEAP" in block
    assert "MAPMODE_PP_MARKET_FOOD_PRICE_CHEAP" in block
    assert "MAPMODE_PP_MARKET_FOOD_PRICE_NEUTRAL" in block
    assert "MAPMODE_PP_MARKET_FOOD_PRICE_EXPENSIVE" in block
    assert "MAPMODE_PP_MARKET_FOOD_PRICE_SEVERE" in block
    assert "min_color = define:NMapColors|MAP_COLOR_MAX" in block
    assert "max_color = define:NMapColors|MAP_COLOR_MIN" in block


def test_population_growth_preserves_working_gradient_and_stripes() -> None:
    block = _all_blocks()["pp_population_growth"]

    assert block.count("lerp = {") == 4
    assert "limit = { has_owner = yes }" in block
    assert "value = modifier:local_population_growth" in block
    assert "modifier:local_population_growth < @pp_population_growth_negative_cap" in block
    assert "modifier:local_population_growth < @pp_population_growth_neutral_low" in block
    assert "modifier:local_population_growth < @pp_population_growth_neutral_high" in block
    assert "modifier:local_population_growth < @pp_population_growth_cap_stripe" in block
    assert "secondary_map_color = {" in block
    assert "province = { is_starving = yes }" in block
    assert "define:NMapColors|POPULATION_STARVING_COLOR_STRIPE" in block
    assert "modifier:local_population_growth >= @pp_population_growth_cap_stripe" in block
    assert block.index("modifier:local_population_growth >= @pp_population_growth_cap_stripe") < block.index(
        "province = { is_starving = yes }"
    )
    assert "MAPMODE_PP_POPULATION_GROWTH_STARVING" in block
    assert "MAPMODE_PP_POPULATION_GROWTH_STRIPE" in block


def test_building_levels_stripes_locations_above_supported_levels() -> None:
    block = _all_blocks()["pp_building_levels"]
    text = LOCALIZATION.read_text(encoding="utf-8-sig")

    assert "secondary_map_color = {" in block
    assert "has_owner = yes" in block
    assert "total_building_levels > modifier:free_building_levels" in block
    assert "MAPMODE_PP_BUILDING_LEVELS_OVER_SUPPORTED" in block
    assert "Above supported building levels" in text
    assert "supports [ROOT.GetLocation.GetModifierValueFixed('free_building_levels')|0] levels" in text


def test_supported_building_levels_map_mode_uses_weighted_capacity_buckets() -> None:
    block = _all_blocks()["pp_supported_building_levels"]
    text = LOCALIZATION.read_text(encoding="utf-8-sig")

    assert _thresholds(block, "modifier:free_building_levels") == [30.0, 70.0, 120.0, 200.0, 300.0]
    assert "limit = { has_owner = yes }" not in block
    assert block.count("lerp = {") == 5
    assert block.count("legend_key =") == 5
    assert "max_color = rgb { 245 245 245 }" in block
    assert "color_refresh_counters = { ProductionList LocationDevelopmentChanged LocationPopulationChanged }" in block
    assert "mapmode_pp_supported_building_levels_name" in text
    assert 'mapmode_pp_supported_building_levels_name: "Supported Building Levels"' in text
    assert "MAPMODE_PP_SUPPORTED_BUILDING_LEVELS_TT_LAND" in text
    assert "GetModifierValueFixed('free_building_levels')|0" in text
    assert (
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "map_modes"
        / "pp_supported_building_levels.dds"
    ).is_file()
    assert (
        MOD_ROOT
        / "main_menu"
        / "common"
        / "game_concepts"
        / "pp_supported_building_levels_map_mode.txt"
    ).is_file()


def test_building_efficiency_map_mode_uses_local_modifier_and_assets() -> None:
    block = _all_blocks()["pp_building_efficiency"]
    text = LOCALIZATION.read_text(encoding="utf-8-sig")
    script_value = BUILDING_EFFICIENCY_SCRIPT_VALUE.read_text(encoding="utf-8-sig")

    assert block.count("lerp = {") == 4
    assert "pp_building_efficiency_map_value < -1" in block
    assert "pp_building_efficiency_map_value < -0.5" in block
    assert "pp_building_efficiency_map_value < -0.1" in block
    assert "pp_building_efficiency_map_value < 0.1" in block
    assert "pp_building_efficiency_map_value < 0.5" in block
    assert "pp_building_efficiency_map_value < 1" in block
    assert "value = pp_building_efficiency_map_value" in block
    assert "add = 1" in block
    assert "subtract = 0.5" in block
    assert "pp_building_efficiency_map_value = {" in script_value
    assert "value = modifier:local_build_buildings_efficiency" in script_value
    assert "mapmode_pp_building_efficiency_name" in text
    assert 'mapmode_pp_building_efficiency_name: "Building Cost Modifier"' in text
    assert "MAPMODE_PP_BUILDING_EFFICIENCY_TT_LAND" in text
    assert "GetModifierValue('local_build_buildings_efficiency')|2%+" in text
    assert (
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "map_modes"
        / "pp_building_efficiency.dds"
    ).is_file()
    assert (
        MOD_ROOT
        / "main_menu"
        / "common"
        / "game_concepts"
        / "pp_building_efficiency_map_mode.txt"
    ).is_file()


def test_unsupported_building_levels_map_mode_uses_over_capacity_buckets() -> None:
    block = _all_blocks()["pp_unsupported_building_levels"]
    text = LOCALIZATION.read_text(encoding="utf-8-sig")
    script_value = BUILDING_EFFICIENCY_SCRIPT_VALUE.read_text(encoding="utf-8-sig")

    assert _thresholds(block, "pp_unsupported_building_levels_map_value") == [
        1.0,
        5.0,
        15.0,
        30.0,
        60.0,
    ]
    assert "limit = { has_owner = yes }" in block
    assert block.count("lerp = {") == 4
    assert block.count("legend_key =") == 5
    assert "value = define:NMapColors|MAP_COLOR_MAX" in block
    assert "max_color = define:NMapColors|MAP_COLOR_MIN" in block
    assert "pp_unsupported_building_levels_map_value = {" in script_value
    assert "value = total_building_levels" in script_value
    assert "subtract = modifier:free_building_levels" in script_value
    assert "min = 0" in script_value
    assert "mapmode_pp_unsupported_building_levels_name" in text
    assert 'mapmode_pp_unsupported_building_levels_name: "Unsupported Building Levels"' in text
    assert 'MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_SUPPORTED: "No unsupported building levels"' in text
    assert 'MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_LOW: "1 to 4 unsupported building levels"' in text
    assert 'MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_MEDIUM: "5 to 14 unsupported building levels"' in text
    assert 'MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_HIGH: "15 to 29 unsupported building levels"' in text
    assert 'MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_SEVERE: "30 or more unsupported building levels"' in text
    assert "MAPMODE_PP_UNSUPPORTED_BUILDING_LEVELS_TT_LAND" in text
    assert "ScriptValue('pp_unsupported_building_levels_map_value')|0" in text
    assert (
        MOD_ROOT
        / "main_menu"
        / "gfx"
        / "interface"
        / "icons"
        / "map_modes"
        / "pp_unsupported_building_levels.dds"
    ).is_file()
    concept = (
        MOD_ROOT
        / "main_menu"
        / "common"
        / "game_concepts"
        / "pp_unsupported_building_levels_map_mode.txt"
    ).read_text(encoding="utf-8-sig")
    assert 'texture = "map_modes/pp_unsupported_building_levels"' in concept


def test_custom_map_modes_preserve_context_and_refresh_behavior() -> None:
    blocks = _all_blocks()

    bad: list[str] = []
    for mode, snippets in STRUCTURE_SNIPPETS.items():
        block = blocks[mode]
        missing = [snippet for snippet in snippets if snippet not in block]
        if missing:
            bad.append(f"{mode}: {missing}")

    assert not bad


def test_custom_map_mode_localization_uses_traffic_light_copy_without_hardcoded_caps() -> None:
    text = LOCALIZATION.read_text(encoding="utf-8-sig")

    stale_phrases = (
        "Dark blue",
        "dark blue",
        "Cividis",
        "purple-to-green",
        "Purple-to-green",
        "Brown marks",
        "teal marks",
        "50k unemployed",
        "0-150",
        "0-10",
        "0-300",
        "0-70",
    )
    found = [phrase for phrase in stale_phrases if phrase in text]

    assert not found
    assert "Red marks scarce capacity" in text
    assert "Green marks low unemployment" in text
    assert "yellow marks the base price" in text
    assert "green marks the strongest capacity" in text
