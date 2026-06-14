from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
MAP_MODES = MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes" / "pp_local_output_modifier_map_modes.txt"
SCRIPT_VALUES = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_local_output_modifier_map_modes.txt"
LOCAL_OUTPUT_MAP_VALUES = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_local_output_map_values.txt"
LOCATION_MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifiers.txt"
LOCATION_APPLICATIONS = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_apply_location_modifiers.txt"
RGO_STATIC_BONUSES = MOD_ROOT / "in_game" / "common" / "static_modifiers" / "pp_rgo_static_bonuses.txt"
LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_building_adjustments_l_english.yml"
OBSOLETE_HELPER_FILES = (
    MOD_ROOT
    / "main_menu"
    / "common"
    / "modifier_type_definitions"
    / "pp_local_output_map_mode_modifier_types.txt",
    MOD_ROOT / "main_menu" / "common" / "modifier_icons" / "pp_local_output_map_mode_modifier_icons.txt",
    MOD_ROOT
    / "main_menu"
    / "localization"
    / "english"
    / "pp_local_output_map_mode_modifier_types_l_english.yml",
)
CALIBRATION = ROOT / "tools" / "map_mode_scale_calibration.json"
ICON_DIRS = (
    MOD_ROOT / "in_game" / "gfx" / "interface" / "icons" / "map_modes",
    MOD_ROOT / "main_menu" / "gfx" / "interface" / "icons" / "map_modes",
)


def _raw_material_goods() -> list[str]:
    text = RGO_STATIC_BONUSES.read_text(encoding="utf-8-sig")
    return re.findall(r"^pp_rgo_bonus_([a-z0-9_]+)\s*=\s*\{", text, flags=re.MULTILINE)


def _map_mode_goods(text: str) -> list[str]:
    return re.findall(r"^pp_local_(.+?)_output_modifier\s*=\s*\{", text, flags=re.MULTILINE)


def _map_mode_blocks(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"^pp_local_(.+?)_output_modifier\s*=\s*\{", text, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[match.group(1)] = text[match.start() : end]
    return blocks


def _script_value_blocks(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"^pp_(.+?)_productivity_map_value\s*=\s*\{", text, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[match.group(1)] = text[match.start() : end]
    return blocks


def _script_block(text: str, name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\s*=\s*\{{(?P<body>.*?)^\}}",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, name
    return match.group("body")


def _localization_value(text: str, key: str) -> str | None:
    matches = re.findall(rf"^\s*{re.escape(key)}:\s*\"(.*)\"\s*$", text, flags=re.MULTILINE)
    return matches[-1] if matches else None


def _uses_goods_name_reference(value: str, good: str) -> bool:
    return any(
        token in value
        for token in (
            f"${good}$",
            f"ShowGoodsName('{good}')",
            f'ShowGoodsName("{good}")',
            f"ShowGoodsNameWithNoTooltip('{good}')",
            f'ShowGoodsNameWithNoTooltip("{good}")',
        )
    )


def _rgo_bonus_values() -> dict[str, tuple[str, str]]:
    text = RGO_STATIC_BONUSES.read_text(encoding="utf-8-sig")
    values: dict[str, tuple[str, str]] = {}
    pattern = re.compile(r"^(pp_rgo_bonus_([a-z0-9_]+))\s*=\s*\{(?P<body>.*?)^\}", re.DOTALL | re.MULTILINE)
    for match in pattern.finditer(text):
        modifier = match.group(1)
        good = match.group(2)
        value_match = re.search(
            rf"^\s*local_{re.escape(good)}_output_modifier\s*=\s*([-+]?\d+(?:\.\d+)?)\s*$",
            match.group("body"),
            flags=re.MULTILINE,
        )
        assert value_match is not None, modifier
        values[good] = (modifier, value_match.group(1))
    return values


def _location_potential_values() -> dict[str, dict[str, str]]:
    text = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    raw_materials = set(_raw_material_goods())
    values: dict[str, dict[str, str]] = {good: {} for good in raw_materials}
    pattern = re.compile(r"^(pp_loc_[a-z0-9_]+)\s*=\s*\{(?P<body>.*?)^\}", re.DOTALL | re.MULTILINE)
    for match in pattern.finditer(text):
        for value_match in re.finditer(
            r"^\s*local_([a-z0-9_]+)_output_modifier\s*=\s*([-+]?\d+(?:\.\d+)?)\s*$",
            match.group("body"),
            flags=re.MULTILINE,
        ):
            good = value_match.group(1)
            value = value_match.group(2)
            if good in raw_materials and value not in {"0", "0.0", "0.00", "+0", "+0.0", "+0.00", "-0", "-0.0", "-0.00"}:
                values[good][match.group(1)] = value_match.group(2)
    return values


def _location_modifier_application_locations() -> dict[str, str]:
    text = LOCATION_APPLICATIONS.read_text(encoding="utf-8-sig")
    locations: dict[str, str] = {}
    pattern = re.compile(
        r"location:([A-Za-z0-9_]+)\s*=\s*\{\s*"
        r"add_location_modifier\s*=\s*\{\s*modifier\s*=\s*(pp_loc_[a-z0-9_]+)",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        locations[match.group(2)] = match.group(1)
    return locations


def _location_on_action_block(text: str, location: str) -> str:
    match = re.search(
        rf"^\t\tlocation:{re.escape(location)}\s*=\s*\{{(?P<body>.*?)^\t\t\}}",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, location
    return match.group("body")


ANCHOR_LEGEND_KEYS = [
    "EXTREME_DEFICIT",
    "DEFICIT",
    "NEUTRAL",
    "GOOD",
    "EXCELLENT",
    "EXCEPTIONAL",
    "RAW_MATERIAL",
]


def _productivity_value_name(good: str) -> str:
    return f"pp_{good}_productivity_map_value"


def _productivity_location_potential_value_name(good: str) -> str:
    return f"pp_{good}_productivity_location_potential_map_value"


def _productivity_rgo_bonus_value_name(good: str) -> str:
    return f"pp_{good}_productivity_rgo_bonus_map_value"


def _productivity_location_potential_variable_name(good: str) -> str:
    return f"pp_{good}_productivity_location_potential_map_var"


def _productivity_location_potential_modifier_name(good: str) -> str:
    return f"pp_{good}_productivity_location_potential_map_modifier"


def _productivity_rgo_bonus_modifier_name(good: str) -> str:
    return f"pp_{good}_productivity_rgo_bonus_map_modifier"


def _entry_block(text: str, key: str) -> str:
    match = re.search(
        rf"^{re.escape(key)}\s*=\s*\{{(?P<body>.*?)^\}}",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, key
    return match.group("body")


def _last_numeric_value(block: str, key: str) -> str | None:
    matches = re.findall(
        rf"^\s*{re.escape(key)}\s*=\s*([-+]?\d+(?:\.\d+)?)\s*$",
        block,
        flags=re.MULTILINE,
    )
    return matches[-1] if matches else None


def test_local_output_map_modes_match_rgo_bonus_goods() -> None:
    raw_materials = _raw_material_goods()
    found = _map_mode_goods(MAP_MODES.read_text(encoding="utf-8-sig"))
    counts = Counter(found)

    assert found == raw_materials
    assert not [good for good, count in counts.items() if count != 1]


def test_local_output_map_modes_have_no_non_rgo_bonus_goods() -> None:
    raw_materials = set(_raw_material_goods())
    found = set(_map_mode_goods(MAP_MODES.read_text(encoding="utf-8-sig")))

    assert found == raw_materials


def test_local_output_map_modes_have_required_localization() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")

    missing: list[str] = []
    for good in _raw_material_goods():
        upper = good.upper()
        keys = [
            f"mapmode_pp_local_{good}_output_modifier_name",
            f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER",
            f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER_TT_LAND",
            f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER_TT_LAND_BREAKDOWN",
            f"PP_LOCAL_{upper}_OUTPUT_MODIFIER_LOCATION_POTENTIAL_TT",
            f"PP_LOCAL_{upper}_OUTPUT_MODIFIER_RGO_BONUS_TT",
            f"PP_LOCAL_{upper}_OUTPUT_MODIFIER_TOTAL_TT",
            *(f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER_{suffix}" for suffix in ANCHOR_LEGEND_KEYS),
        ]
        missing.extend(key for key in keys if key not in loc)

    assert not missing


def test_local_output_map_mode_localization_uses_game_goods_names() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    for good in _raw_material_goods():
        upper = good.upper()
        keys = [
            f"mapmode_pp_local_{good}_output_modifier_name",
            f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER",
            f"PP_LOCAL_{upper}_OUTPUT_MODIFIER_LOCATION_POTENTIAL_TT",
            f"PP_LOCAL_{upper}_OUTPUT_MODIFIER_RGO_BONUS_TT",
            f"PP_LOCAL_{upper}_OUTPUT_MODIFIER_TOTAL_TT",
            *(f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER_{suffix}" for suffix in ANCHOR_LEGEND_KEYS),
        ]
        for key in keys:
            value = _localization_value(loc, key)
            if value is None:
                bad.append(f"{key}: missing localization")
            elif not _uses_goods_name_reference(value, good):
                bad.append(f"{key}: {value}")

    assert not bad


def test_local_output_map_mode_names_use_productivity_label() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    for good in _raw_material_goods():
        key = f"mapmode_pp_local_{good}_output_modifier_name"
        value = _localization_value(loc, key)
        expected = f"Local ${good}$ Productivity"
        if value != expected:
            bad.append(f"{key}: {value!r}, expected {expected!r}")

    assert not bad


def test_local_output_map_mode_helper_modifier_assets_are_removed() -> None:
    assert not [path for path in OBSOLETE_HELPER_FILES if path.exists()]


def test_output_map_modes_use_productivity_script_values() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        value_name = _productivity_value_name(good)
        if value_name not in block:
            bad.append(f"{good}: missing {value_name}")

    assert not bad


def test_local_output_map_mode_script_values_cover_every_raw_material() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")

    missing: list[str] = []
    for good in _raw_material_goods():
        if f"{_productivity_value_name(good)} = {{" not in script_values:
            missing.append(good)
        if f"{_productivity_location_potential_value_name(good)} = {{" not in script_values:
            missing.append(f"{good}: missing location-potential component")
        if f"{_productivity_rgo_bonus_value_name(good)} = {{" not in script_values:
            missing.append(f"{good}: missing RGO-bonus component")

    assert not missing


def test_productivity_script_values_use_location_potential_variables_and_rgo_bonus() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    location_values = _location_potential_values()

    bad: list[str] = []
    if "modifier:local_" in script_values:
        bad.append("uses live local output modifier source")
    if "pp_harvest_" in script_values:
        bad.append("uses variable harvest modifiers")
    if "has_location_modifier = pp_loc_" in script_values:
        bad.append("scans generated location modifiers")
    if "_productivity_location_potential_map_modifier" in script_values:
        bad.append("uses duplicate location-potential helper modifiers")
    if "_productivity_rgo_bonus_map_modifier" in script_values:
        bad.append("uses legacy RGO helper modifiers")
    for good, block in _script_value_blocks(script_values).items():
        variable = _productivity_location_potential_variable_name(good)
        if location_values.get(good) and f"value = var:{variable}" not in block:
            bad.append(f"{good}: total value missing location-potential variable source")
        if not location_values.get(good) and variable in block:
            bad.append(f"{good}: uses location-potential variable without source values")
        if f"raw_material = goods:{good}" not in block:
            bad.append(f"{good}: total value missing raw-material RGO source")
        if f"add = modifier:{_productivity_rgo_bonus_modifier_name(good)}" in block:
            bad.append(f"{good}: total value still uses RGO helper modifier")

    assert not bad


def test_output_map_modes_all_use_vanilla_traffic_light_signed_format() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        if "@factor_add" in block or "@factor_divide" in block:
            bad.append(f"{good}: still uses old generic factor ramp")
        if block.count("legend_key =") != len(ANCHOR_LEGEND_KEYS):
            bad.append(f"{good}: wrong concise legend key count")
        if block.count("lerp = {") < 5:
            bad.append(f"{good}: missing bucket shading")
        for color in (
            "define:NMapColors|MAP_COLOR_MIN",
            "define:NMapColors|MAP_COLOR_LOW",
            "define:NMapColors|MAP_COLOR_MID",
            "define:NMapColors|MAP_COLOR_HIGH",
            "define:NMapColors|MAP_COLOR_MAX",
            "define:NMapColors|MAP_COLOR_TOP",
        ):
            if color not in block:
                bad.append(f"{good}: missing {color}")
        if f"raw_material = goods:{good}" not in block:
            bad.append(f"{good}: missing matching raw-material stripes")
        if f"MAPMODE_PP_LOCAL_{good.upper()}_OUTPUT_MODIFIER_RAW_MATERIAL" not in block:
            bad.append(f"{good}: missing raw-material legend key")

    assert not bad


def test_output_map_modes_have_multi_stop_colors_and_raw_material_stripes() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        if block.count("define:NMapColors|MAP_COLOR") < 12:
            bad.append(f"{good}: too few vanilla color stops")
        if block.count("legend_key =") != len(ANCHOR_LEGEND_KEYS):
            bad.append(f"{good}: wrong legend key count")
        if block.count("lerp = {") < 5:
            bad.append(f"{good}: missing in-bucket lerps")
        if "secondary_map_color = {" not in block:
            bad.append(f"{good}: missing raw-material stripes")

    assert not bad


def test_output_map_mode_legends_use_concise_anchor_keys() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        legend_keys = re.findall(
            rf'MAPMODE_PP_LOCAL_{good.upper()}_OUTPUT_MODIFIER_([A-Z_]+)" color',
            block,
        )
        if legend_keys != ANCHOR_LEGEND_KEYS:
            bad.append(f"{good}: {legend_keys}")

    assert not bad


def test_output_map_modes_use_calibrated_signed_thresholds() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))["scales"]["local_output_modifier"]

    bad: list[str] = []
    for good, block in blocks.items():
        value_name = _productivity_value_name(good)
        generated = [
            float(value)
            for value in re.findall(
                rf"{re.escape(value_name)} < (-?[0-9]+(?:\.[0-9]+)?)",
                block,
            )
        ]
        scale = calibration[good]
        expected = [
            *[float(value) for value in scale["negative_thresholds"]],
            float(scale["neutral_low"]),
            float(scale["neutral_high"]),
            *[float(value) for value in scale["positive_thresholds"]],
        ]
        if generated != expected:
            bad.append(f"{good}: generated {generated}, calibration {expected}")

    assert not bad


def test_output_map_modes_shade_inside_each_productivity_bucket() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        if "min_color = define:NMapColors|MAP_COLOR_LOW" not in block:
            bad.append(f"{good}: missing negative-to-neutral shading")
        if "max_color = define:NMapColors|MAP_COLOR_MAX" not in block:
            bad.append(f"{good}: missing positive shading")
        if "max_color = define:NMapColors|MAP_COLOR_TOP" not in block:
            bad.append(f"{good}: missing upper positive shading")
        if "subtract = 0.05" not in block:
            bad.append(f"{good}: missing positive bucket origin")
        if "value = define:NMapColors|MAP_COLOR_MID" not in block:
            bad.append(f"{good}: missing neutral solid bucket")
        if "max = 1" not in block or "min = 0" not in block:
            bad.append(f"{good}: missing factor clamps")

    assert not bad


def test_output_map_modes_clamp_extreme_productivity_without_gradient() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        value_name = _productivity_value_name(good)
        if not re.search(
            rf"{re.escape(value_name)} < -[0-9.]+.*?value = define:NMapColors\|MAP_COLOR_MIN",
            block,
            flags=re.DOTALL,
        ):
            bad.append(f"{good}: missing low clamp")
        if not re.search(r"else = \{\s+value = define:NMapColors\|MAP_COLOR_TOP", block):
            bad.append(f"{good}: missing high clamp")

    assert not bad


def test_productivity_script_value_components_use_location_variables_and_raw_material_rgo() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    rgo_values = _rgo_bonus_values()
    location_values = _location_potential_values()

    bad: list[str] = []
    for good, (_modifier, value) in rgo_values.items():
        total_block = _script_block(script_values, _productivity_value_name(good))
        location_block = _script_block(script_values, _productivity_location_potential_value_name(good))
        rgo_block = _script_block(script_values, _productivity_rgo_bonus_value_name(good))
        variable = _productivity_location_potential_variable_name(good)
        has_location_potential = bool(location_values.get(good))
        if has_location_potential and f"has_variable = {variable}" not in total_block:
            bad.append(f"{good}: total component does not guard location-potential variable")
        if has_location_potential and f"value = var:{variable}" not in total_block:
            bad.append(f"{good}: total component does not use location-potential variable")
        if has_location_potential and f"has_variable = {variable}" not in location_block:
            bad.append(f"{good}: location component does not guard location-potential variable")
        if has_location_potential and f"value = var:{variable}" not in location_block:
            bad.append(f"{good}: location component does not use location-potential variable")
        if not has_location_potential and variable in total_block:
            bad.append(f"{good}: total component references variable without source values")
        if not has_location_potential and variable in location_block:
            bad.append(f"{good}: location component references variable without source values")
        if _productivity_location_potential_modifier_name(good) in script_values:
            bad.append(f"{good}: script values still use duplicate location-potential helper")
        if "has_location_modifier = pp_loc_" in location_block:
            bad.append(f"{good}: location-potential component scans location modifiers")
        if "value = 0" not in rgo_block:
            bad.append(f"{good}: RGO-bonus component does not start at zero")
        if f"raw_material = goods:{good}" not in rgo_block:
            bad.append(f"{good}: RGO-bonus component does not check raw material")
        if f"add = {value}" not in rgo_block:
            bad.append(f"{good}: RGO-bonus component does not add source value {value}")
        if _productivity_rgo_bonus_modifier_name(good) in rgo_block:
            bad.append(f"{good}: RGO-bonus component still uses helper modifier")

    assert not bad


def test_location_potential_helper_modifiers_are_not_applied_to_locations() -> None:
    location_text = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")

    assert not re.findall(
        r"^\s*pp_[a-z0-9_]+_productivity_location_potential_map_modifier\s*=",
        location_text,
        flags=re.MULTILINE,
    )


def test_location_potential_variables_match_source_values() -> None:
    variable_text = LOCAL_OUTPUT_MAP_VALUES.read_text(encoding="utf-8-sig")
    location_values = _location_potential_values()
    application_locations = _location_modifier_application_locations()
    representative_goods = ("wheat", "livestock", "fish", "lumber", "wild_game")

    bad: list[str] = []
    for good in representative_goods:
        modifiers = location_values[good]
        assert modifiers, good
        variable = _productivity_location_potential_variable_name(good)
        for modifier, value in list(modifiers.items())[:3]:
            location = application_locations[modifier]
            block = _location_on_action_block(variable_text, location)
            expected = f"set_variable = {{ name = {variable} value = {value} }}"
            if expected not in block:
                bad.append(f"{good}: {location} missing {expected}")

    assert not bad


def test_location_potential_variables_are_only_emitted_for_goods_with_source_values() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    variable_text = LOCAL_OUTPUT_MAP_VALUES.read_text(encoding="utf-8-sig")
    location_values = _location_potential_values()

    bad: list[str] = []
    for good, modifiers in location_values.items():
        variable = _productivity_location_potential_variable_name(good)
        if modifiers:
            if f"set_variable = {{ name = {variable}" not in variable_text:
                bad.append(f"{good}: missing generated set_variable rows")
            continue
        if variable in script_values:
            bad.append(f"{good}: script values reference unused location-potential variable")
        if variable in variable_text:
            bad.append(f"{good}: on-action references unused location-potential variable")

    assert not bad


def test_rgo_bonus_static_modifiers_do_not_include_map_mode_helper_modifiers() -> None:
    rgo_text = RGO_STATIC_BONUSES.read_text(encoding="utf-8-sig")
    rgo_values = _rgo_bonus_values()

    bad: list[str] = []
    for good, (modifier, value) in rgo_values.items():
        block = _entry_block(rgo_text, modifier)
        helper = _productivity_rgo_bonus_modifier_name(good)
        if _last_numeric_value(block, helper) is not None:
            bad.append(f"{good}: RGO helper value still present; source value is {value}")

    assert not bad


def test_output_map_modes_use_vanilla_location_map_names() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        for size in ("small", "medium", "large"):
            match = re.search(rf"^\s*{size}_map_names\s*=\s*(\S+)\s*$", block, flags=re.MULTILINE)
            if match is None:
                bad.append(f"{good}: missing {size}_map_names")
            elif match.group(1) != "location":
                bad.append(f"{good}: {size}_map_names uses unsupported provider {match.group(1)}")

    assert not bad


def test_productivity_script_values_keep_only_total_and_component_values() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    value_blocks = re.findall(r"^pp_[a-z0-9_]+_productivity_[a-z0-9_]+_value = \{", script_values, flags=re.MULTILINE)

    assert len(value_blocks) == len(_raw_material_goods()) * 3


def test_local_output_map_mode_localization_explains_static_planning_values_without_balance_numbers() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")
    output_keys = re.findall(
        r"^\s+MAPMODE_PP_LOCAL_[A-Z0-9_]+_OUTPUT_MODIFIER[^:]*: \"(.*)\"$",
        loc,
        flags=re.MULTILINE,
    )
    assert output_keys
    output_text = "\n".join(output_keys)

    assert "static $wheat$ productivity" in output_text
    assert "static $livestock$ productivity" in output_text
    assert "Location potential static modifier:" in output_text
    assert "RGO bonus static modifier:" in output_text
    assert "Total static modifier:" in output_text
    assert "#TOOLTIP:SIMPLE_CUSTOM,PP_LOCAL_WHEAT_OUTPUT_MODIFIER_TOTAL_TT #L" in output_text
    assert "#TOOLTIP:SIMPLE_CUSTOM,PP_LOCAL_WHEAT_OUTPUT_MODIFIER_LOCATION_POTENTIAL_TT #L" in output_text
    assert "#TOOLTIP:SIMPLE_CUSTOM,PP_LOCAL_WHEAT_OUTPUT_MODIFIER_RGO_BONUS_TT #L" in output_text
    assert "#TOOLTIP:MODIFIER_TYPE,pp_wheat_productivity_location_potential_map_modifier #L" not in output_text
    assert "#TOOLTIP:MODIFIER_TYPE,pp_wheat_productivity_rgo_bonus_map_modifier #L" not in output_text
    assert "$wheat$ is the raw material" in output_text
    assert "$livestock$ is the raw material" in output_text
    assert "Red marks negative productivity" in output_text
    assert "yellow marks near-neutral productivity" in output_text
    assert "green marks positive productivity" in output_text
    assert "harvest-neutral" not in output_text
    assert "Live local" not in output_text
    assert "variable harvest" not in output_text

    text_without_format_precision = output_text.replace("|2", "").replace("|0", "")
    assert not re.search(r"[-+]?\d+(?:\.\d+)?%?", text_without_format_precision)


def test_local_output_map_mode_hover_tooltips_are_short_static_modifier_breakdowns() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")
    hover_tooltips = re.findall(
        r'^\s+MAPMODE_PP_LOCAL_[A-Z0-9_]+_OUTPUT_MODIFIER_TT_LAND(?:_BREAKDOWN)?: "(.*)"$',
        loc,
        flags=re.MULTILINE,
    )
    assert hover_tooltips
    tooltip_text = "\n".join(hover_tooltips)

    assert "[ROOT.GetLocation.GetName]" not in tooltip_text
    assert "The map color uses only those two static planning factors" not in tooltip_text
    assert "Red marks negative productivity" not in tooltip_text
    assert "Static modifier value:" not in tooltip_text
    assert "Location potential static modifier:" in tooltip_text
    assert "RGO bonus static modifier:" in tooltip_text
    assert "Total static modifier:" in tooltip_text
    assert "pp_wheat_productivity_map_value')|2" in tooltip_text
    assert "#TOOLTIP:SIMPLE_CUSTOM,PP_LOCAL_WHEAT_OUTPUT_MODIFIER_LOCATION_POTENTIAL_TT #L" in tooltip_text
    assert "#TOOLTIP:SIMPLE_CUSTOM,PP_LOCAL_WHEAT_OUTPUT_MODIFIER_RGO_BONUS_TT #L" in tooltip_text
    assert "#TOOLTIP:SIMPLE_CUSTOM" in tooltip_text
    assert "#TOOLTIP:MODIFIER_TYPE" not in tooltip_text


def test_non_wheat_local_output_legends_do_not_reference_wheat() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    for good in _raw_material_goods():
        if good == "wheat":
            continue
        upper = good.upper()
        for line in re.findall(rf"^\s+MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER_[A-Z_]+: .*$", loc, flags=re.MULTILINE):
            if "wheat" in line.lower():
                bad.append(line)

    assert not bad


def test_local_output_map_mode_localization_uses_literal_newlines() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")
    block_match = re.search(
        r"  # Local output modifier map modes \(pp_local_output_modifier_map_modes\.txt\).*?"
        r"  # End generated local output modifier map modes",
        loc,
        flags=re.DOTALL,
    )
    assert block_match is not None
    block = block_match.group(0)
    bad_lines = [
        line
        for line in block.splitlines()
        if line.strip()
        and not line.startswith("  #")
        and not re.match(r'^\s+[A-Za-z0-9_]+:\s*".*"$', line)
    ]

    assert "\\n" in block
    assert "\nThis colors " not in block
    assert "\nAggregated from " not in block
    assert not bad_lines


def test_local_output_map_modes_have_icons_in_both_contexts() -> None:
    missing: list[str] = []
    for good in _raw_material_goods():
        filename = f"pp_local_{good}_output_modifier.dds"
        for icon_dir in ICON_DIRS:
            if not (icon_dir / filename).is_file():
                missing.append(str(icon_dir / filename))

    assert not missing


def test_local_output_map_modes_are_geography_index_two() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        if not re.search(r"^\s*category\s*=\s*geography\s*$", block, flags=re.MULTILINE):
            bad.append(f"{good}: missing category = geography")
        if not re.search(r"^\s*index\s*=\s*2\s*$", block, flags=re.MULTILINE):
            bad.append(f"{good}: missing index = 2")

    assert not bad
