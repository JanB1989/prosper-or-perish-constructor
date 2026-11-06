"""Construction Plan: player-only construction rules (src/prosper_or_perish_constructor/construction_plan.py,
mod/pp/.../pp_construction_plan*)."""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
GUI_FILES = (MOD / "in_game/gui/pp_construction_plan.gui", MOD / cp.GUI)
LOC = MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml"
SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_construction_plan.txt"
ON_ACTION = MOD / "in_game/common/on_action/pp_construction_plan.txt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _defined_keys(folder: Path) -> set[str]:
    keys: set[str] = set()
    for path in folder.glob("*.txt"):
        for match in re.finditer(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE):
            keys.add(match.group(1))
    return keys


def test_built_mod_is_in_step() -> None:
    result = cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert result.files_changed == 0, "run ppc finalize"
    assert result.missing == [], f"buildings the game does not know: {result.missing}"
    assert len(result.goods) > 60
    assert "iron_mine" in result.producers["iron"]
    assert result.farm_lines["wheat"][0] == "wheat_farm"


def test_focus_ids_match_the_panel() -> None:
    """The panel's focus labels are written by hand for these ids."""
    ids = cp.focus_ids(cp.load_config(PROJECT))
    assert ids == {"standard": 1, "breadbasket": 2, "market_town": 3, "workshop": 4, "hands_off": 5, "custom": 6}
    gui = _read(GUI_FILES[0])
    loc = _read(LOC)
    for name, number in ids.items():
        key = f"PP_CPLAN_FOCUS_{name.upper()}"
        assert f"'(CFixedPoint){number}')]\" text = \"{key}\"" in gui
        assert f"  {key}:" in loc


def test_panel_references_exist() -> None:
    guis = _read(SCRIPTED_GUIS) + "\n"
    script_values = _defined_keys(MOD / "in_game/common/script_values")
    loc = _read(LOC)
    loc_keys = set(re.findall(r"^  ([A-Z0-9_]+):", loc, re.MULTILINE))
    text = "".join(_read(path) for path in GUI_FILES) + loc
    for name in set(re.findall(r"GetScriptedGui\('([a-z0-9_]+)'\)", text)):
        assert re.search(rf"^{name} = \{{", guis, re.MULTILINE), f"scripted GUI {name} missing"
    for name in set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", text)):
        assert name in script_values, f"script value {name} missing"
    for key in set(re.findall(r"\"(PP_CPLAN_[A-Z0-9_]+)\"", text)):
        assert key in loc_keys, f"text {key} missing"


def test_only_human_countries_run_the_plan() -> None:
    text = _read(ON_ACTION)
    assert "is_ai = no" in text
    assert "has_variable = pp_cplan_on" in text


def test_effects_use_the_vanilla_can_build_check() -> None:
    """Every construction the plan starts is guarded by the location and owner can-build check."""
    effects = _read(MOD / cp.EFFECTS)
    blocks = re.findall(r"limit = \{([^\n]*)\}\n\t*pp_cplan_construct(?:_food)? = \{ type = (\w+)", effects)
    assert blocks
    for limit, building in blocks:
        if "pp_cplan_pick" in limit:
            continue  # the farm picker checked the candidate before it picked it
        assert f"location_and_owner_can_build = {{ building_type = {building} }}" in limit, building
