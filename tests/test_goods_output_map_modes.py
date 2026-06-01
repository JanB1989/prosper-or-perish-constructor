from __future__ import annotations

import re
import json
import tomllib
from collections import Counter
from pathlib import Path

from eu5gameparser.domain.eu5 import load_eu5_data


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
MAP_MODES = MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes" / "pp_goods_output_map_modes_generated.txt"
SCRIPT_VALUES = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_goods_output_map_modes_generated.txt"
LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_goods_output_map_modes_l_english.yml"
ICON_DIR = MOD_ROOT / "in_game" / "gfx" / "interface" / "icons" / "map_modes"
CALIBRATION = ROOT / "tools" / "map_mode_scale_calibration.json"
VANILLA_TRAFFIC_COLORS = (
    "define:NMapColors|MAP_COLOR_MIN",
    "define:NMapColors|MAP_COLOR_LOW",
    "define:NMapColors|MAP_COLOR_MID",
    "define:NMapColors|MAP_COLOR_HIGH",
    "define:NMapColors|MAP_COLOR_MAX",
)
GOODS_OUTPUT_LEGEND_SUFFIXES = ("VERY_LOW", "LOW", "MEDIUM", "HIGH", "CAPPED")


def _all_goods() -> set[str]:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    return set(data.goods.select("name").to_series().to_list())


def _host_path(path: Path) -> Path:
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", str(path))
    if match is None:
        return path
    return Path("/mnt") / match.group(1).lower() / match.group(2).replace("\\", "/")


def _vanilla_root() -> Path:
    with (ROOT / "constructor.load_order.toml").open("rb") as stream:
        raw = tomllib.load(stream)
    path = _host_path(Path(raw["paths"]["vanilla_root"]))
    return path if path.is_absolute() else (ROOT / path).resolve()


def _modifier_type_definition_text() -> str:
    roots = (
        _vanilla_root() / "game" / "main_menu" / "common" / "modifier_type_definitions",
        MOD_ROOT / "main_menu" / "common" / "modifier_type_definitions",
    )
    return "\n".join(
        path.read_text(encoding="utf-8-sig")
        for root in roots
        for path in sorted(root.glob("*.txt"))
    )


def _english_localization_text() -> str:
    roots = (
        _vanilla_root() / "game" / "main_menu" / "localization" / "english",
        MOD_ROOT / "main_menu" / "localization" / "english",
    )
    return "\n".join(
        path.read_text(encoding="utf-8-sig")
        for root in roots
        for path in sorted(root.glob("*_l_english.yml"))
    )


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


def _assert_exact_goods(label: str, found: list[str], expected: set[str]) -> None:
    counts = Counter(found)
    duplicates = sorted(good for good, count in counts.items() if count != 1)
    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)

    assert not duplicates, f"{label} duplicates: {duplicates}"
    assert not missing, f"{label} missing goods: {missing}"
    assert not extra, f"{label} extra goods: {extra}"


def _map_mode_blocks(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"^pp_(.+?)_output\s*=\s*\{", text, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[match.group(1)] = text[match.start() : end]
    return blocks


def test_goods_output_map_modes_cover_all_goods_and_no_more() -> None:
    expected = _all_goods()

    map_mode_goods = re.findall(
        r"^pp_(.+?)_output\s*=\s*\{",
        MAP_MODES.read_text(encoding="utf-8-sig"),
        flags=re.MULTILINE,
    )
    script_value_goods = re.findall(
        r"^pp_(.+?)_output_raw\s*=\s*\{",
        SCRIPT_VALUES.read_text(encoding="utf-8-sig"),
        flags=re.MULTILINE,
    )
    localization_goods = re.findall(
        r"^\s*mapmode_pp_(.+?)_output_name:",
        LOCALIZATION.read_text(encoding="utf-8-sig"),
        flags=re.MULTILINE,
    )
    icon_goods = [
        match.group(1)
        for path in sorted(ICON_DIR.glob("pp_*_output.dds"))
        if (match := re.match(r"pp_(.+?)_output\.dds$", path.name))
    ]

    _assert_exact_goods("map modes", map_mode_goods, expected)
    _assert_exact_goods("script values", script_value_goods, expected)
    _assert_exact_goods("localization", localization_goods, expected)
    _assert_exact_goods("icons", icon_goods, expected)


def test_output_modifier_types_cover_all_goods_and_use_goods_localization() -> None:
    expected = _all_goods()
    definitions = _modifier_type_definition_text()
    localization = _english_localization_text()

    for scope in ("local", "global"):
        found = re.findall(
            rf"^{scope}_([a-z0-9_]+)_output_modifier\s*=\s*\{{",
            definitions,
            flags=re.MULTILINE,
        )
        _assert_exact_goods(f"{scope} output modifier types", found, expected)

    bad: list[str] = []
    for good in sorted(expected):
        for scope in ("local", "global"):
            for kind in ("NAME", "DESC"):
                key = f"MODIFIER_TYPE_{kind}_{scope}_{good}_output_modifier"
                value = _localization_value(localization, key)
                if value is None:
                    bad.append(f"{key}: missing localization")
                elif not _uses_goods_name_reference(value, good):
                    bad.append(f"{key}: {value}")

    assert not bad


def test_goods_output_map_mode_localization_uses_game_goods_names() -> None:
    expected = _all_goods()
    localization = LOCALIZATION.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    for good in sorted(expected):
        upper = good.upper()
        for key in (
            f"mapmode_pp_{good}_output_name",
            f"MAPMODE_PP_{upper}_OUTPUT",
            f"MAPMODE_PP_{upper}_OUTPUT_TT_LAND",
        ):
            value = _localization_value(localization, key)
            if value is None:
                bad.append(f"{key}: missing localization")
            elif not _uses_goods_name_reference(value, good):
                bad.append(f"{key}: {value}")

    assert not bad


def test_goods_output_map_modes_use_per_good_vanilla_traffic_light_bucket_format() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))
    localization = LOCALIZATION.read_text(encoding="utf-8-sig")

    bad: list[str] = []
    for good, block in blocks.items():
        upper = good.upper()
        if "rgb { 0 255 0 }" in block or "rgb { 255 0 0 }" in block:
            bad.append(f"{good}: uses saturated red/green")
        if block.count("legend_key =") != len(GOODS_OUTPUT_LEGEND_SUFFIXES):
            bad.append(f"{good}: wrong legend key count")
        if block.count("lerp = {") != 4:
            bad.append(f"{good}: wrong bucket gradient count")
        for color in VANILLA_TRAFFIC_COLORS:
            if color not in block:
                bad.append(f"{good}: missing {color}")
        for suffix in GOODS_OUTPUT_LEGEND_SUFFIXES:
            key = f"MAPMODE_PP_{upper}_OUTPUT_{suffix}"
            if key not in block:
                bad.append(f"{good}: missing legend key {key} in map block")
            if key not in localization:
                bad.append(f"{good}: missing legend key {key} in localization")
        if "@pp_goods_output_color_scale_max" in block:
            bad.append(f"{good}: still uses one global display cap")
        thresholds = [
            float(match)
            for match in re.findall(rf"pp_{re.escape(good)}_output_raw < ([0-9]+(?:\.[0-9]+)?)", block)
        ]
        if len(thresholds) != 4 or thresholds != sorted(set(thresholds)):
            bad.append(f"{good}: thresholds are not four strict per-good cutoffs: {thresholds}")
        if f'"goods_output(goods:{good})" > 0' not in block:
            bad.append(f"{good}: zero-output locations are not guarded")

    assert not bad


def test_goods_output_map_modes_use_artifact_calibrated_thresholds() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))["scales"]["goods_output"]

    threshold_sets = {
        tuple(
            float(value)
            for value in re.findall(
                rf"pp_{re.escape(good)}_output_raw < ([0-9]+(?:\.[0-9]+)?)",
                block,
            )
        )
        for good, block in blocks.items()
    }

    assert len(threshold_sets) > 10
    assert (0.25, 1.0, 4.0, 16.0) not in threshold_sets

    bad: list[str] = []
    for good, block in blocks.items():
        generated = [
            float(value)
            for value in re.findall(
                rf"pp_{re.escape(good)}_output_raw < ([0-9]+(?:\.[0-9]+)?)",
                block,
            )
        ]
        expected = [float(value) for value in calibration[good]["thresholds"]]
        if generated != expected:
            bad.append(f"{good}: generated {generated}, calibration {expected}")

    assert not bad


def test_goods_output_map_modes_preserve_context_and_refresh_behavior() -> None:
    blocks = _map_mode_blocks(MAP_MODES.read_text(encoding="utf-8-sig"))

    bad: list[str] = []
    required = (
        "category = economy",
        "index = 3",
        "small_map_names = location",
        "small_tooltip_context = location",
        "map_markers = { all = no }",
        "color_refresh_counters = { Month ProductionList LocationConstructionUnitChanged MarketReach }",
        "color_and_names_refresh_counters = { LocationOwnerChanged CountryStatus MarketReach }",
        "value = rgb { 128 128 128 }",
    )
    for good, block in blocks.items():
        missing = [snippet for snippet in required if snippet not in block]
        if missing:
            bad.append(f"{good}: {missing}")

    assert not bad


def test_goods_output_map_mode_localization_avoids_old_red_green_copy() -> None:
    text = LOCALIZATION.read_text(encoding="utf-8-sig")

    assert "dark blue" not in text.lower()
    assert "cividis" not in text.lower()
    assert "purple" not in text.lower()
    assert "Heatmap 0" not in text
    assert "Red marks low output" in text
    assert "yellow marks the middle" in text
    assert "green marks the strongest output" in text
