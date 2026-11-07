"""Location plan: the player's marks of what a location should produce or have (location_plan.py, mod/pp/.../
pp_location_plan*). Only visual."""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import location_plan as lp
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / "in_game/gui/pp_location_plan.gui"
GUI_FILES = (WINDOW, MOD / lp.GUI)
LOC_FILES = (MOD / "main_menu/localization/english/pp_location_plan_l_english.yml", MOD / lp.LOC)
SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_location_plan.txt"
MAP_MODE = MOD / "in_game/gfx/map/map_modes/pp_location_plan_map_mode.txt"
LOCATION_WINDOW = MOD / "in_game/gui/location_window.gui"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _loc_keys() -> set[str]:
    keys: set[str] = set()
    for path in LOC_FILES:
        keys |= set(re.findall(r"^  ([A-Za-z0-9_]+):", _read(path), re.MULTILINE))
    return keys


def _script_values() -> set[str]:
    keys: set[str] = set()
    for path in (MOD / "in_game/common/script_values").glob("*.txt"):
        keys |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    return keys


def test_built_mod_is_in_step() -> None:
    result = lp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert result.files_changed == 0, "run ppc finalize"
    assert result.missing_icons == [], f"items without an icon: {result.missing_icons}"
    keys = [item.key for item in result.items]
    assert "lumber" in keys and "furniture" in keys and "trade_category" in keys
    assert "offset" not in keys and "manual_labor" not in keys


def test_references_exist() -> None:
    guis = _read(SCRIPTED_GUIS)
    values = _script_values()
    loc = _loc_keys()
    button = re.search(re.escape(lp.BUTTON_MARK) + r".*?BasicFunctionalTooltip", _read(LOCATION_WINDOW), re.DOTALL)
    assert button, "the location window lost the Location Plan button"
    text = "".join(_read(path) for path in GUI_FILES) + "".join(_read(path) for path in LOC_FILES) + button.group(0)
    text += _read(MAP_MODE)
    for name in set(re.findall(r"GetScriptedGui\('([a-z0-9_]+)'\)", text)):
        assert re.search(rf"^{name} = \{{", guis, re.MULTILINE), f"scripted GUI {name} missing"
    for name in set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", text)):
        assert name in values, f"script value {name} missing"
    for key in set(re.findall(r"\"((?:PP_LPLAN|MAPMODE_PP_LOCATION_PLAN)[A-Z0-9_]*)\"", text)):
        assert key in loc, f"text {key} missing"
    for key in set(re.findall(r"'(PP_LPLAN_[A-Z0-9_]+)'", text)) | set(re.findall(r"\$(PP_LPLAN_[A-Z0-9_]+)\$", text)):
        assert key in loc, f"text {key} missing"
    for name in ("pp_lplan_planned_n", "pp_lplan_open_n", "pp_lplan_done_n"):
        assert name in values


def test_map_mode_is_registered() -> None:
    """A custom map mode needs its game concept with texture map_modes/<id>, the DDS under main_menu, and its texts."""
    assert re.search(r"^pp_location_plan = \{", _read(MAP_MODE), re.MULTILINE)
    concept = _read(MOD / "main_menu/common/game_concepts/pp_location_plan_map_mode.txt")
    assert 'texture = "map_modes/pp_location_plan"' in concept
    assert (MOD / "main_menu/gfx/interface/icons/map_modes/pp_location_plan.dds").is_file()
    loc = _loc_keys()
    for key in ("game_concept_pp_location_plan", "game_concept_pp_location_plan_desc", "mapmode_pp_location_plan_name",
                "MAPMODE_PP_LOCATION_PLAN"):
        assert key in loc, key
    for variable in set(re.findall(r"@([a-z_]+)", _read(MAP_MODE))):
        assert re.search(rf"^@{variable}\s*=", _read(MAP_MODE), re.MULTILINE), f"@{variable} not defined in the map mode file"


def test_no_box_directly_inside_a_container() -> None:
    """EU5 refuses an hbox/vbox as a direct child of a (flow)container; a hot reload with one crashed the game."""
    for path in GUI_FILES:
        stack: list[str | None] = []
        for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{|\}", re.sub(r"#[^\n]*", "", _read(path))):
            if match.group(0) == "}":
                if stack:
                    stack.pop()
                continue
            name = match.group(1)
            parent = stack[-1] if stack else None
            if parent in {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}:
                assert name not in {"hbox", "vbox"}, f"{path.name}: {name} directly inside {parent}"
            stack.append(name)


def test_marker_changes_only_the_raw_goods_marker() -> None:
    """The mod's map_markers.gui is vanilla's with only the raw goods marker split (plan icons in the plan map mode)."""
    vanilla_path = vanilla_root(ROOT, PROJECT) / "game" / lp.MARKERS
    if not vanilla_path.is_file():
        return
    vanilla = vanilla_path.read_text(encoding="utf-8-sig")
    mod = _read(MOD / lp.MARKERS)

    def outside(text: str) -> str:
        start = text.index("### Raw Goods Marker")
        return text[:start] + text[lp._marker_block_end(text, start):]

    assert outside(mod) == outside(vanilla)
    assert 'name = "pp_lplan_marker"' in mod
    assert f"GetMapMode('{lp.MAP_MODE_KEY}').IsSet" in mod
    assert "raw_goods_marker = yes" in _read(MAP_MODE)
    # the engine creates raw goods markers only with the raw_material color mode (in game 2026-11-07)
    assert "color_mode = raw_material" in _read(MAP_MODE)
    for item in lp.plan_items(ROOT, lp.load_config(PROJECT)):
        assert f"'{item.var}'" in mod and f"PP_LPLAN_STATE_{item.key.upper()}" in mod, item.key
    # only locations with a plan look at the items
    assert "Location.MakeScope.Var('pp_lplan_n').IsSet" in mod


def test_only_for_the_player() -> None:
    assert "Not(IsObserving)" in _read(WINDOW)
    assert "LocationView.GetLocation.GetOwner.IsPlayer" in lp.BUTTON
