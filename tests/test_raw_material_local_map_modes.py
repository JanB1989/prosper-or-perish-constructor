from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
MAP_MODES = MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes" / "pp_local_output_modifier_map_modes.txt"
SCRIPT_VALUES = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_local_output_modifier_map_modes.txt"
LOCATION_MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifiers.txt"
RGO_STATIC_BONUSES = MOD_ROOT / "in_game" / "common" / "static_modifiers" / "pp_rgo_static_bonuses.txt"
LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_building_adjustments_l_english.yml"
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


def _productivity_map_label_value_name(good: str) -> str:
    return f"pp_{good}_productivity_map_label_value"


def _productivity_location_potential_value_name(good: str) -> str:
    return f"pp_{good}_productivity_location_potential_map_value"


def _productivity_rgo_bonus_value_name(good: str) -> str:
    return f"pp_{good}_productivity_rgo_bonus_map_value"


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
            *(f"MAPMODE_PP_LOCAL_{upper}_OUTPUT_MODIFIER_{suffix}" for suffix in ANCHOR_LEGEND_KEYS),
        ]
        missing.extend(key for key in keys if key not in loc)

    assert not missing


def test_output_map_modes_use_productivity_script_values() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        value_name = _productivity_value_name(good)
        if value_name not in block:
            bad.append(f"{good}: missing {value_name}")
        if f"value = modifier:local_{good}_output_modifier" in block:
            bad.append(f"{good}: uses direct modifier in map color")

    assert not bad


def test_local_output_map_mode_script_values_cover_every_raw_material() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")

    missing: list[str] = []
    for good in _raw_material_goods():
        if f"{_productivity_value_name(good)} = {{" not in script_values:
            missing.append(good)
        if f"{_productivity_map_label_value_name(good)} = {{" not in script_values:
            missing.append(f"{good}: missing integer map label value")
        if f"{_productivity_location_potential_value_name(good)} = {{" not in script_values:
            missing.append(f"{good}: missing location-potential component")
        if f"{_productivity_rgo_bonus_value_name(good)} = {{" not in script_values:
            missing.append(f"{good}: missing RGO-bonus component")

    assert not missing


def test_productivity_script_values_use_only_location_potential_and_rgo_bonus() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    if "modifier:local_" in script_values:
        bad.append("uses live local output modifier source")
    if "pp_harvest_" in script_values:
        bad.append("uses variable harvest modifiers")
    for good, block in _script_value_blocks(script_values).items():
        if f"value = {_productivity_location_potential_value_name(good)}" not in block:
            bad.append(f"{good}: total value missing location-potential source")
        if f"add = {_productivity_rgo_bonus_value_name(good)}" not in block:
            bad.append(f"{good}: total value missing RGO-bonus source")

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


def test_productivity_script_values_have_bounded_location_potential_components() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    location_values = _location_potential_values()

    bad: list[str] = []
    for good in _raw_material_goods():
        block = _script_block(script_values, _productivity_location_potential_value_name(good))
        modifiers = location_values[good]
        found = set(re.findall(r"has_location_modifier = (pp_loc_[a-z0-9_]+)", block))
        if found != set(modifiers):
            bad.append(f"{good}: generated {len(found)} location modifiers, expected {len(modifiers)}")
        if modifiers and not re.search(r"^\t\t(add|subtract) = [-+]?[0-9.]+$", block, flags=re.MULTILINE):
            bad.append(f"{good}: location-potential block has modifiers but no operation")
        if not modifiers and re.search(r"has_location_modifier = pp_loc_", block):
            bad.append(f"{good}: zero location-potential block contains location modifiers")

    assert not bad


def test_productivity_script_values_keep_representative_location_potential_values() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    location_values = _location_potential_values()
    representative_goods = ("wheat", "livestock", "fish", "lumber", "wild_game")

    bad: list[str] = []
    for good in representative_goods:
        modifiers = location_values[good]
        assert modifiers, good
        block = _script_block(script_values, _productivity_location_potential_value_name(good))
        for modifier, value in list(modifiers.items())[:3]:
            operation = "subtract" if value.startswith("-") else "add"
            amount = value.removeprefix("-").removeprefix("+")
            if not re.search(
                rf"has_location_modifier = {re.escape(modifier)}.*?\n\t\t{operation} = {re.escape(amount)}",
                block,
                flags=re.DOTALL,
            ):
                bad.append(f"{good}: missing representative {modifier} {operation} {amount}")

    assert not bad


def test_productivity_script_values_match_rgo_bonus_modifier_values() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")
    rgo_values = _rgo_bonus_values()

    bad: list[str] = []
    for good, (modifier, value) in rgo_values.items():
        block = _script_block(script_values, _productivity_rgo_bonus_value_name(good))
        found = set(re.findall(r"has_location_modifier = (pp_rgo_bonus_[a-z0-9_]+)", block))
        if found != {modifier}:
            bad.append(f"{good}: generated {sorted(found)}, expected {modifier}")
        operation = "subtract" if value.startswith("-") else "add"
        amount = value.removeprefix("-").removeprefix("+")
        if f"\t\t{operation} = {amount}" not in block:
            bad.append(f"{good}: missing {operation} {amount}")

    assert not bad


def test_output_map_modes_use_integer_productivity_map_names() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    for good, block in blocks.items():
        label_value = _productivity_map_label_value_name(good)
        for size in ("small", "medium", "large"):
            if f"{size}_map_names = {label_value}" not in block:
                bad.append(f"{good}: {size}_map_names is not {label_value}")
            if f"{size}_map_names = location" in block:
                bad.append(f"{good}: {size}_map_names still shows location names")

    assert not bad


def test_productivity_integer_map_label_values_floor_percent_values() -> None:
    script_values = SCRIPT_VALUES.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    for good in _raw_material_goods():
        block = _script_block(script_values, _productivity_map_label_value_name(good))
        if f"value = {_productivity_value_name(good)}" not in block:
            bad.append(f"{good}: label does not source total productivity value")
        if "\tmultiply = 100" not in block:
            bad.append(f"{good}: label does not convert to percent")
        if "\tfloor = yes" not in block:
            bad.append(f"{good}: label is not floored to integer")

    assert not bad


def test_local_output_map_mode_localization_explains_static_planning_values_without_balance_numbers() -> None:
    loc = LOCALIZATION.read_text(encoding="utf-8-sig")
    output_keys = re.findall(
        r"^\s+MAPMODE_PP_LOCAL_[A-Z0-9_]+_OUTPUT_MODIFIER[^:]*: \"(.*)\"$",
        loc,
        flags=re.MULTILINE,
    )
    assert output_keys
    output_text = "\n".join(output_keys)

    assert "static wheat productivity" in output_text
    assert "static livestock productivity" in output_text
    assert "Location potential:" in output_text
    assert "Raw-material bonus:" in output_text
    assert "uses only those two static planning factors" in output_text
    assert "integer percent value" in output_text
    assert "wheat is the raw material" in output_text
    assert "livestock is the raw material" in output_text
    assert "Red marks negative productivity" in output_text
    assert "yellow marks near-neutral productivity" in output_text
    assert "green marks positive productivity" in output_text
    assert "harvest-neutral" not in output_text
    assert "Live local" not in output_text
    assert "variable harvest" not in output_text

    text_without_format_precision = output_text.replace("|2", "").replace("|0", "")
    assert not re.search(r"[-+]?\d+(?:\.\d+)?%?", text_without_format_precision)


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
