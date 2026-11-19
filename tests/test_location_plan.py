"""Location plan: the player's plans for a location, as town rights (location_plan.py, mod/pp/.../pp_location_plan*).
A plan is a town right pp_plan_<plan> (town_plans.py) set and taken off by the Location Plan window's icons and the
location window's Plans row (test_town_plan_gui.py); the Construction Plan builds toward the held plans (its pass is
tested elsewhere). Here the picker, the toggle, the texts, the map marker, and that the old building marks are gone."""

from __future__ import annotations

import importlib.util
import re
from functools import cache
from pathlib import Path

from prosper_or_perish_constructor import location_plan as lp
from prosper_or_perish_constructor import town_plans
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / "in_game/gui/pp_location_plan.gui"
GUI_FILES = (WINDOW, MOD / lp.GUI)
HAND_LOC = MOD / "main_menu/localization/english/pp_location_plan_l_english.yml"
LOC_FILES = (HAND_LOC, MOD / lp.LOC)
SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_location_plan.txt"
EFFECTS = MOD / "in_game/common/scripted_effects/pp_location_plan.txt"
MAP_MODE = MOD / "in_game/gfx/map/map_modes/pp_location_plan_map_mode.txt"
LOCATION_WINDOW = MOD / "in_game/gui/location_window.gui"
GUI_DIR = MOD / "in_game/gui"
PORTED = ("build_location_lateralview.gui", "building_view.gui", "shared/pp_location_building_rows.gui")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in LOC_FILES:
        texts.update(re.findall(r'^  ([A-Za-z0-9_]+): "(.*)"$', _read(path), re.MULTILINE))
    return texts


def _all_english_keys() -> set[str]:
    keys: set[str] = set()
    for path in (MOD / lp.LOC_DIR).glob("*.yml"):
        keys |= set(re.findall(r"^  ([A-Za-z0-9_.]+):", _read(path), re.MULTILINE))
    return keys


def _script_values() -> set[str]:
    keys: set[str] = set()
    for path in (MOD / "in_game/common/script_values").glob("*.txt"):
        keys |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    return keys


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, f"{name} missing"
    return match.group(1)


@cache
def _plans() -> list[lp.Plan]:
    return lp.plans_for(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))


def test_built_mod_is_in_step() -> None:
    result = lp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)
    assert result.files_changed == 0, "run ppc finalize"
    assert result.missing_icons == [], f"plans without an icon: {result.missing_icons}"


def test_picker_keys_are_the_plan_keys() -> None:
    """Every plan right has its icon in the picker, in the shared order; fur (no building makes it) is shown, not
    plannable; food and trade are a group of their own; the dummy goods never show."""
    plans = _plans()
    keys = [plan.key for plan in lp.plannable(plans)]
    assert keys == [plan.key for plan in town_plans.plans(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))]
    assert keys[-2:] == list(town_plans.EXTRA_PLANS) and "lumber" in keys and "tools" in keys
    assert [plan.key for plan in plans if not plan.plannable] == ["fur"]
    assert {plan.group for plan in plans if not plan.good} == {lp.EXTRA_GROUP}
    for hidden in ("offset", "manual_labor", "logistics", "local_food"):
        assert hidden not in [plan.key for plan in plans]
    gui = _read(MOD / lp.GUI)
    picker = gui[gui.index("type pp_lplan_picker"):gui.index(f"type {'pp_tplan_location_row'}")]
    for plan in lp.plannable(plans):
        assert picker.count(lp.toggle_call(plan)) == 1, plan.key
        assert picker.count(lp.held(plan)) == 2, plan.key  # the gold frame and the alpha
        assert f'tooltip = "{plan.tooltip}"' in picker
    fur = picker[picker.index('PP_TPLAN_NONE_FUR') - 300:picker.index('PP_TPLAN_NONE_FUR')]
    assert "onclick" not in fur and "button" not in fur
    assert "PP_LPLAN_GROUP_PLANS" in picker and "PP_LPLAN_GROUP_BUILDINGS" not in picker
    # one held check: the plan right's script value
    assert lp.held(plans[0]) == f"EqualTo_CFixedPoint(Location.MakeScope.ScriptValue('pp_tplan_on_{plans[0].key}'), '(CFixedPoint)1')"


def test_references_exist() -> None:
    # the window's "Switch on" button (shown while the Construction Plan is off) uses the plan's own switch
    guis = _read(SCRIPTED_GUIS) + _read(SCRIPTED_GUIS.with_name("pp_construction_plan.txt"))
    values = _script_values()
    loc = _all_english_keys()
    button = re.search(re.escape(lp.BUTTON_MARK) + r".*?action_tooltip = \{.*?\n\t*\}", _read(LOCATION_WINDOW), re.DOTALL)
    assert button, "the location window lost the Location Plan button"
    text = "".join(_read(path) for path in GUI_FILES) + "".join(_read(path) for path in LOC_FILES) + button.group(0)
    text += _read(MAP_MODE) + _read(MOD / lp.MARKERS)
    for name in set(re.findall(r"GetScriptedGui\('([a-z0-9_]+)'\)", text)):
        assert re.search(rf"^{name} = \{{", guis, re.MULTILINE), f"scripted GUI {name} missing"
    for name in set(re.findall(r"ScriptValue\('([a-z0-9_]+)'\)", text)):
        assert name in values, f"script value {name} missing"
    for key in set(re.findall(r"\"((?:PP_LPLAN|PP_TPLAN|MAPMODE_PP_LOCATION_PLAN)[A-Z0-9_]*)\"", text)):
        assert key in loc, f"text {key} missing"
    for key in set(re.findall(r"'((?:PP_LPLAN|PP_TPLAN|PP_LPROF)_[A-Z0-9_]+)'", text)) | set(
            re.findall(r"\$((?:PP_LPLAN|PP_TPLAN)_[A-Z0-9_]+)\$", text)):
        assert key in loc, f"text {key} missing"


def test_toggle_flips_one_plan_right() -> None:
    """One click sets the plan or takes it off: strictly one if / else on the held right (a script grant has no checks,
    a revoke takes off one copy); a plan taken off takes its state along; the map redraws."""
    flip = _effect(_read(EFFECTS), town_plans.FLIP_EFFECT)
    assert flip.count("has_town_rights") == 1 and flip.count("grant_town_rights") == 1
    held_at = flip.index("limit = { has_town_rights = town_rights_type:pp_plan_$g$ }")
    revoke = flip.index("revoke_town_rights_of_type = town_rights_type:pp_plan_$g$")
    other = flip.index("else = {")
    assert held_at < revoke < other < flip.index("grant_town_rights = town_rights_type:pp_plan_$g$")
    for name in ("pp_lplan_st_g_$g$", "pp_lplan_est_g_$g$"):
        assert held_at < flip.index(f"remove_variable = {name}\n") < other, name
    assert "refresh_map_colors = yes" in flip
    # the switch: one case per plan, nothing for fur
    switch = _effect(_read(MOD / lp.EFFECTS), lp.TOGGLE_SWITCH)
    for plan in lp.plannable(_plans()):
        assert f"flag:{plan.key} = {{ {town_plans.FLIP_EFFECT} = {{ g = {plan.key} }} }}" in switch
    assert "flag:fur =" not in switch
    # Clear: only held plans are flipped (a flip on an unheld plan would grant it)
    clear = _effect(_read(MOD / lp.EFFECTS), lp.CLEAR_ALL)
    for plan in lp.plannable(_plans()):
        assert (f"limit = {{ has_town_rights = town_rights_type:{plan.right} }}\n\t\t"
                f"{town_plans.FLIP_EFFECT} = {{ g = {plan.key} }}") in clear
    # the scripted GUIs: location scope, a player owner only
    guis = _read(SCRIPTED_GUIS)
    for name, effect in ((town_plans.TOGGLE_GUI, lp.TOGGLE_SWITCH), ("pp_tplan_clear", "pp_tplan_clear_do")):
        block = _effect(guis, name)
        assert "scope = location" in block and f"{effect} = yes" in block
        assert "is_valid = {\n\t\texists = owner\n\t\towner = { is_ai = no }" in block
    for gone in ("pp_lplan_toggle", "pp_lplan_bmark", "pp_lplan_bmarked", "pp_lplan_bdone", "pp_lplan_bmark_all",
                 "pp_lplan_clear"):
        assert not re.search(rf"^{gone} = \{{", guis, re.MULTILINE), gone


def test_gui_only_names_are_declared() -> None:
    """The flags the GUI passes and the states only the pass writes are declared in a block that never runs, so
    error.log has no 'used but never set' line."""
    effects = _read(MOD / lp.EFFECTS)
    declare = _effect(effects, lp.DECLARE)
    for plan in lp.plannable(_plans()):
        assert f"set_variable = {{ name = pp_tplan_flag value = flag:{plan.key} }}" in declare
        for name in (plan.state, plan.est):
            assert f"set_variable = {{ name = {name} value = 100 }}" in declare, name
    select = _effect(_read(EFFECTS), "pp_lplan_select")
    assert select.index("limit = { always = no }") < select.index("save_scope_as = pp_key") < select.index(
        f"{lp.DECLARE} = yes")
    assert effects.count(f"{lp.DECLARE} = yes") == 0 and "pp_lplan_declare_flags" not in select


def test_old_marks_are_gone() -> None:
    """Location Profiles and the building marks went on 2026-11-19: the old marks' effects and their count are gone
    with the profile pass that called them."""
    effects = _read(MOD / lp.EFFECTS) + _read(EFFECTS)
    for name in ("pp_lplan_clear_all", "pp_lplan_drop_categories", "pp_lplan_declare_flags", "pp_lplan_b_promote",
                 "pp_lplan_b_state_off", "pp_lplan_bflip"):
        assert not re.search(rf"^{name} = \{{", effects, re.MULTILINE), name
    assert "pp_lplan_planned_n" not in _script_values()
    assert not hasattr(lp, "BUILDING_MARKS") and not hasattr(lp, "plan_items")


def test_every_plan_state_has_a_text() -> None:
    """A plan's tile shows its state after the last pass with the profile state texts (PP_LPROF_ST_<n>), every state
    that has a text, by number; not checked yet = state 0."""
    texts = _texts()
    keys = _all_english_keys()
    states = lp.state_numbers(MOD)
    assert states and states[0] == 1 and "PP_LPROF_ST_0" in keys
    for plan in lp.plannable(_plans()):
        upper = plan.key.upper()
        pick, line, sts = texts[f"PP_TPLAN_PICK_{upper}"], texts[f"PP_TPLAN_ST_{upper}"], texts[f"PP_TPLAN_STS_{upper}"]
        assert f"'PP_TPLAN_ST_{upper}', 'PP_TPLAN_EMPTY'" in pick and lp.held(plan) in pick
        assert f"Var('{plan.state}').IsSet, 'PP_TPLAN_STS_{upper}', 'PP_LPROF_ST_0'" in line
        for n in states:
            assert (f"[AddTextIf(EqualTo_CFixedPoint(Location.MakeScope.Var('{plan.state}').GetValue, '(CFixedPoint){100 + n}'), "
                    f"Localize('PP_LPROF_ST_{n}'))]") in sts, (plan.key, n)
        assert (("$PP_TPLAN_WHAT_GOOD$" if plan.good else f"$PP_TPLAN_WHAT_{upper}$") in pick), plan.key
    assert texts["PP_TPLAN_NONE_FUR"].endswith("$PP_TPLAN_NONE$")


def test_player_texts() -> None:
    """Plans are town rights the Construction Plan builds toward: the texts say so, link the concepts and carry no
    numbers; no text of the removed widgets is left."""
    texts = dict(re.findall(r'^  ([A-Za-z0-9_.]+): "(.*)"$', _read(HAND_LOC), re.MULTILINE))
    for key in ("PP_LPLAN_NOTE", "PP_TPLAN_PICK_ON", "PP_TPLAN_PICK_OFF", "PP_LPLAN_SHOW_MAP_TT",
                "game_concept_pp_location_plan_desc", "MAPMODE_PP_LOCATION_PLAN", "PP_TPLAN_MAP_RIGHT"):
        assert "[town_rights|e]" in texts[key], key
    for key in ("PP_LPLAN_NOTE", "PP_TPLAN_WHAT_GOOD", "PP_TPLAN_WHAT_FOOD", "PP_TPLAN_WHAT_TRADE",
                "game_concept_pp_location_plan_desc", "MAPMODE_PP_LOCATION_PLAN", "PP_TPLAN_ROW_MORE_TT"):
        assert "Construction Plan" in texts[key], key
    assert texts["PP_TPLAN_NAME_FOOD"] == "[food|e]" and texts["PP_TPLAN_NAME_TRADE"] == "[trade|e]"
    for key, text in texts.items():
        plain = re.sub(r"\[[^\]]*\]|\$[A-Za-z0-9_]+\$", "", text)
        assert not re.search(r"\d", plain), key
        assert "Ctrl" not in text and not re.search(r"\bmark(s|ed)?\b", text, re.IGNORECASE), key
    for gone in ("PP_LPLAN_BMARK", "PP_LPLAN_ALSO", "PP_LPLAN_PICK_", "PP_LPLAN_STATE_", "PP_LPLAN_COUNTS",
                 "PP_LPLAN_PLANNED"):
        assert not any(key.startswith(gone) for key in _texts()), gone


def test_map_mode_is_registered() -> None:
    """A custom map mode needs its game concept with texture map_modes/<id>, the DDS under main_menu, and its texts."""
    assert re.search(r"^pp_location_plan = \{", _read(MAP_MODE), re.MULTILINE)
    concept = _read(MOD / "main_menu/common/game_concepts/pp_location_plan_map_mode.txt")
    assert 'texture = "map_modes/pp_location_plan"' in concept
    assert (MOD / "main_menu/gfx/interface/icons/map_modes/pp_location_plan.dds").is_file()
    loc = _all_english_keys()
    for key in ("game_concept_pp_location_plan", "game_concept_pp_location_plan_desc", "mapmode_pp_location_plan_name",
                "MAPMODE_PP_LOCATION_PLAN"):
        assert key in loc, key
    for variable in set(re.findall(r"@([a-z_]+)", _read(MAP_MODE))):
        assert re.search(rf"^@{variable}\s*=", _read(MAP_MODE), re.MULTILINE), f"@{variable} not defined in the map mode file"


def test_every_map_mode_sits_in_a_shown_row() -> None:
    """A map mode's index is its row in the category menu, and hud_bot.gui lists only some rows per category
    (GetMapModeGroupFromCategory): the plan map mode at index 40 never showed in the menu (2026-11-07)."""
    hud = vanilla_root(ROOT, PROJECT) / "game/in_game/gui/hud_bot.gui"
    if not hud.is_file():
        return
    shown: dict[str, set[int]] = {}
    for category, row in re.findall(r"GetMapModeGroupFromCategory\('([a-z_]+)', '\(int32\)(\d+)'\)", _read(hud)):
        shown.setdefault(category, set()).add(int(row))

    def places(folder: Path) -> dict[str, tuple[str, int]]:
        found: dict[str, tuple[str, int]] = {}
        for path in folder.glob("*.txt"):
            for name, body in re.findall(r"^([a-z_0-9]+) = \{(.*?)^\}", _read(path), re.MULTILINE | re.DOTALL):
                category = re.search(r"^\s*category = ([a-z_]+)", body, re.MULTILINE)
                index = re.search(r"^\s*index = (\d+)", body, re.MULTILINE)
                if category:
                    found[name] = (category.group(1), int(index.group(1)) if index else 0)
        return found

    vanilla = places(hud.parents[1] / "gfx/map/map_modes")  # vanilla keeps a few out of the menu on purpose
    for name, (category, row) in places(MOD / "in_game/gfx/map/map_modes").items():
        if category in shown and vanilla.get(name) != (category, row):
            assert row in shown[category], f"{name}: {category} row {row} is not in the map mode menu"


def test_no_box_directly_inside_a_container() -> None:
    """EU5 refuses an hbox/vbox as a direct child of a (flow)container; a hot reload with one crashed the game."""
    for path in (*GUI_FILES, MOD / lp.MARKERS):
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


def test_marker_draws_the_town_rights_and_leaves_vanilla_alone() -> None:
    """The mod's map_markers.gui is vanilla's with only the raw goods marker split: vanilla's content outside the plan
    map mode, and in it one datamodel over the location's own town rights (plans among them), shown only for the
    player's locations that hold any right (vanilla's own size test); nothing per plan, no building icons."""
    vanilla_path = vanilla_root(ROOT, PROJECT) / "game" / lp.MARKERS
    if not vanilla_path.is_file():
        return
    vanilla = vanilla_path.read_text(encoding="utf-8-sig")
    mod = _read(MOD / lp.MARKERS)

    def outside(text: str) -> str:
        start = text.index("### Raw Goods Marker")
        return text[:start] + text[lp._marker_block_end(text, start):]

    assert outside(mod) == outside(vanilla)
    start = mod.index("### Raw Goods Marker")
    marker = mod[start:lp._marker_block_end(mod, start)]
    assert f"visible = \"[Not(GetMapMode('{lp.MAP_MODE_KEY}').IsSet)]\"" in marker
    plan = marker[marker.index('name = "pp_lplan_marker"'):]
    assert (f"visible = \"[And(GetMapMode('{lp.MAP_MODE_KEY}').IsSet, And(Location.GetOwner.IsPlayer, "
            f"{lp.HAS_RIGHTS}))]\"") in plan
    assert plan.count("datamodel = \"[DataModelFirst(Location.GetTownRights, ") == 1
    assert 'texture = "[TownRights.GetIcon]"' in plan and f'tooltip = "{lp.MAP_TOOLTIP}"' in plan
    for gone in ("ScriptValue(", "Var(", "pp_lplan_b", "pp_lprof", "GetBuildingIcon", "pp_lplan_done"):
        assert gone not in plan, gone
    assert "raw_goods_marker = yes" in _read(MAP_MODE) and "color_mode = raw_material" in _read(MAP_MODE)
    assert "[TownRights.GetName]" in _texts()[lp.MAP_TOOLTIP]


def test_only_for_the_player() -> None:
    assert "Not(IsObserving)" in _read(WINDOW)
    assert "LocationView.GetLocation.GetOwner.IsPlayer" in lp.BUTTON
    assert "Location.GetOwner.IsPlayer" in _read(MOD / lp.MARKERS)


def test_window_has_no_profile_or_building_strip() -> None:
    window = _read(WINDOW)
    for gone in ("pp_lprof_plan_row", "pp_lplan_bstrip", "pp_lplan_strip", "pp_lplan_planned_n", "pp_lplan_clear'"):
        assert gone not in window, gone
    assert "pp_lplan_picker = {}" in window and "GetScriptedGui('pp_tplan_clear')" in window


# ---------------------------------------------------------------------------------------------------------------------
# the building marks are gone from the GUI (2026-11-19: a plan is a town right; the Ctrl + click marks, the build
# panel's checkbox, the Production window's mass mark and the badges went)

_LEFTOVERS = ("Construction Plan mark", "pp_lplan_bmark", "pp_lplan_bmarked", "pp_lplan_bdone", "pp_lplan_b'",
              "pp_lplan_toggle", "PP_LPLAN_BMARK", "pp_lprof_location_row", "pp_lplan_location_row",
              "Location Profile row")


@cache
def _tool():
    spec = importlib.util.spec_from_file_location("port_vanilla_gui", ROOT / "tools/port_vanilla_gui.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def test_no_building_marks_left_in_the_gui() -> None:
    for path in (LOCATION_WINDOW, MOD / lp.MARKERS, *GUI_FILES, *(GUI_DIR / rel for rel in PORTED)):
        text = _read(path)
        for needle in _LEFTOVERS:
            assert needle not in text, (path.name, needle)
    assert not (GUI_DIR / "shared/zz_pp_building_type_header.gui").exists()
    for name in ("add_building_marks", "add_auto_expand_marks", "build_panel_mark", "mark_action", "render_marker_buildings"):
        assert not hasattr(lp, name), name


def test_ported_files_are_the_port_without_marks() -> None:
    """The three ported files that carried building marks are a fresh port (the build's pp_ copies undone), and the
    Production window's re-declared rows are retired."""
    tool = _tool()
    vanilla = vanilla_root(ROOT, PROJECT) / "game"
    fresh = tool.ported(vanilla, MOD)
    for rel in PORTED:
        assert tool._normalised(tool._read(GUI_DIR / rel)) == fresh[rel], rel
    assert fresh["shared/zz_pp_building_type_header.gui"] is None
    assert "zz_pp_building_type_header.gui" in tool.RETIRED[1]
