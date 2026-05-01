from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from eu5gameparser.domain.eu5 import load_eu5_data


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
MAP_MODES = MOD_ROOT / "in_game" / "gfx" / "map" / "map_modes" / "pp_local_output_modifier_map_modes.txt"
LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_building_adjustments_l_english.yml"
ICON_DIRS = (
    MOD_ROOT / "in_game" / "gfx" / "interface" / "icons" / "map_modes",
    MOD_ROOT / "main_menu" / "gfx" / "interface" / "icons" / "map_modes",
)


def _raw_material_goods() -> list[str]:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    return (
        data.goods.filter(data.goods["category"] == "raw_material")
        .select("name")
        .to_series()
        .to_list()
    )


def _all_goods() -> set[str]:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    return set(data.goods.select("name").to_series().to_list())


def _map_mode_goods(text: str) -> list[str]:
    return re.findall(r"^pp_local_(.+?)_output_modifier\s*=\s*\{", text, flags=re.MULTILINE)


def _map_mode_blocks(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"^pp_local_(.+?)_output_modifier\s*=\s*\{", text, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[match.group(1)] = text[match.start() : end]
    return blocks


def test_local_output_map_modes_match_parser_raw_materials() -> None:
    raw_materials = _raw_material_goods()
    found = _map_mode_goods(MAP_MODES.read_text(encoding="utf-8-sig"))
    counts = Counter(found)

    assert found == raw_materials
    assert not [good for good, count in counts.items() if count != 1]
    assert set(found).issubset(_all_goods())


def test_local_output_map_modes_have_no_non_raw_material_goods() -> None:
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
        ]
        missing.extend(key for key in keys if key not in loc)

    assert not missing


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
