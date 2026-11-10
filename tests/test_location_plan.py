"""Location plan: the player's marks of what a location should produce or have (location_plan.py, mod/pp/.../
pp_location_plan*). The marks are the location's build picks: the Construction Plan builds them (the pass is tested in
test_location_profiles.py); here the marks themselves, their states' texts and the map."""

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
    assert "lumber" in keys and "furniture" in keys
    assert "trade_category" not in keys  # a mark is a good or a building (test_a_mark_is_a_good_or_a_building)
    assert "offset" not in keys and "manual_labor" not in keys


def _marks() -> list[lp.Item]:
    """What the picker marks: the goods."""
    return lp.mark_items(lp.plan_items(ROOT, lp.load_config(PROJECT)))


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, f"{name} missing"
    return match.group(1)


def test_references_exist() -> None:
    guis = _read(SCRIPTED_GUIS)
    values = _script_values()
    loc = _loc_keys()
    button = re.search(re.escape(lp.BUTTON_MARK) + r".*?action_tooltip = \{.*?\n\t*\}", _read(LOCATION_WINDOW), re.DOTALL)
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
    for item in _marks():
        assert f"'{item.var}'" in mod and f"PP_LPLAN_STATE_{item.key.upper()}" in mod, item.key
    # only locations with a plan look at the items
    assert "Location.MakeScope.Var('pp_lplan_n').IsSet" in mod


def test_only_for_the_player() -> None:
    assert "Not(IsObserving)" in _read(WINDOW)
    assert "LocationView.GetLocation.GetOwner.IsPlayer" in lp.BUTTON


PROFILE_LOC = MOD / "main_menu/localization/english"
EFFECTS = MOD / "in_game/common/scripted_effects/pp_location_plan.txt"


def _texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in LOC_FILES:
        texts.update(re.findall(r'^  ([A-Za-z0-9_]+): "(.*)"$', _read(path), re.MULTILINE))
    return texts


def test_toggle_marks_an_item_with_its_state_names() -> None:
    """One click marks or unmarks a good: the toggle passes the item's name part (g_<good>), from which the mark, its
    state and its payback note are named; unmarking takes the state along."""
    items = _marks()
    switch = _read(MOD / lp.EFFECTS)
    for item in items:
        assert f"flag:{item.key} = {{ pp_lplan_flip = {{ v = {item.suffix} }} }}" in switch, item.key
        assert item.var == f"pp_lplan_{item.suffix}" and item.state == f"pp_lplan_st_{item.suffix}"
        assert item.est == f"pp_lplan_est_{item.suffix}"
        # the states are read by the GUI only: the declaration reads them
        assert f"has_variable = {item.state}\n" in switch and f"has_variable = {item.est}\n" in switch, item.key
    flip = re.search(r"^pp_lplan_flip = \{(.*?)^\}", _read(EFFECTS), re.MULTILINE | re.DOTALL).group(1)
    assert "$var$" not in flip and "set_variable = { name = pp_lplan_$v$ value = yes }" in flip
    for name in ("pp_lplan_$v$", "pp_lplan_st_$v$", "pp_lplan_est_$v$"):
        assert f"remove_variable = {name}\n" in flip, name
    assert "refresh_map_colors = yes" in flip


def test_every_mark_state_has_a_text() -> None:
    """A mark shows its state after the last monthly pass like a profile rule does, with the profile's state texts: in
    the tile tooltip (picker, location window row) while marked, in the strip's and the map icon's tooltip always."""
    items = _marks()
    texts = _texts()
    profile_keys: set[str] = set()
    for path in PROFILE_LOC.glob("pp_location_profiles*_l_english.yml"):
        profile_keys |= set(re.findall(r"^  ([A-Za-z0-9_]+):", _read(path), re.MULTILINE))
    # a forced mark is never held for its payback (5) or by the market limit (10): those states are a profile rule's
    assert lp.MARK_STATES == (1, 2, 3, 4, 6, 7, 8, 9)
    for n in (0, *lp.MARK_STATES):
        assert f"PP_LPROF_ST_{n}" in profile_keys, n
    for item in items:
        upper = item.key.upper()
        pick, state, line = texts[f"PP_LPLAN_PICK_{upper}"], texts[f"PP_LPLAN_STATE_{upper}"], texts[f"PP_LPLAN_MST_{upper}"]
        assert f"'PP_LPLAN_MST_{upper}', 'PP_LPROF_UI_EMPTY'" in pick and f"Var('{item.var}').IsSet" in pick, item.key
        assert state.endswith(f"$PP_LPLAN_MST_{upper}$"), item.key
        # not checked yet = the profile's state 0; else one of its states 1..9, by the mark's own state variable
        assert f"Var('{item.state}').IsSet, 'PP_LPLAN_MSTS_{upper}', 'PP_LPROF_ST_0'" in line, item.key
        states = texts[f"PP_LPLAN_MSTS_{upper}"]
        for n in lp.MARK_STATES:
            assert (f"[AddTextIf(EqualTo_CFixedPoint(Location.MakeScope.Var('{item.state}').GetValue, '(CFixedPoint){100 + n}'), "
                    f"Localize('PP_LPROF_ST_{n}'))]") in states, (item.key, n)
        # no "pays back too slowly" for a mark: neither the state nor the payback beside it
        assert "PP_LPROF_ST_5'" not in states and "PP_LPROF_ST_10'" not in states, item.key
        assert item.est not in line and f"PP_LPLAN_MEST_{upper}" not in texts and f"PP_LPLAN_MESTY_{upper}" not in texts
    # every profile text the plan's texts use exists
    used = set(re.findall(r"'(PP_LPROF_[A-Z0-9_]+)'", "".join(texts.values())))
    assert {"PP_LPROF_UI_EMPTY", "PP_LPROF_ST_0"} <= used
    assert used <= profile_keys, sorted(used - profile_keys)
    # state texts: no numbers, and they fit a rule and a mark alike
    hand = dict(re.findall(r'^  ([A-Z0-9_]+): "(.*)"$', _read(PROFILE_LOC / "pp_location_profiles_l_english.yml"), re.MULTILINE))
    for n in (0, *lp.MARK_STATES):
        assert "this rule" not in hand[f"PP_LPROF_ST_{n}"] and "earlier rule" not in hand[f"PP_LPROF_ST_{n}"], n


def test_no_text_says_the_marks_are_only_visual() -> None:
    """Jan 2026-11-10: a mark is a build pick. No player text, config comment or file header still says the Location
    Plan only shows something or builds nothing."""
    import tomllib

    stale = re.compile(r"only visual|only for you|nothing is built|no rule builds|builds nothing by it", re.IGNORECASE)
    files = [*LOC_FILES, *GUI_FILES, SCRIPTED_GUIS, EFFECTS, MAP_MODE, ROOT / "src/prosper_or_perish_constructor/location_plan.py"]
    for path in files:
        assert not stale.search(_read(path)), path.name
    config = _read(PROJECT)
    section = config[config.index("[location_plan]"):config.index("[location_profiles]")]
    assert not stale.search(section) and "Construction Plan builds" in section
    assert tomllib.loads(config)["location_plan"]["per_row"] > 0
    texts = _texts()
    for key in ("PP_LPLAN_NOTE", "PP_LPLAN_LOCATION_BUTTON", "PP_LPLAN_PICK_ON", "PP_LPLAN_PICK_OFF",
                "game_concept_pp_location_plan_desc", "MAPMODE_PP_LOCATION_PLAN"):
        assert "Construction Plan" in texts[key], key
    # player text carries no numbers
    for key, text in texts.items():
        if key.startswith(("PP_LPLAN_GROUP", "PP_LPLAN_ALSO", "PP_LPLAN_NOTE", "PP_LPLAN_PICK_O", "PP_LPLAN_STATE_", "MAPMODE", "game_concept")):
            plain = re.sub(r"\[[^\]]*\]|\$[A-Z0-9_]+\$", "", text)
            assert not re.search(r"\d", plain), key


# ---------------------------------------------------------------------------------------------------------------------
# Jan 2026-11-10 (evening): a mark is a good or a building, and it is forced

PROFILE_EFFECTS = MOD / "in_game/common/scripted_effects/pp_location_profiles.txt"


def test_a_mark_is_a_good_or_a_building() -> None:
    """The eight building categories left the picker, the strip, the row and the map ("the button for trade buildings:
    it's very unclear what even is in that"). A save's category marks go quietly at the first look: each one off the
    count, with its state and payback note; nothing is logged, nothing redrawn."""
    config = lp.load_config(PROJECT)
    marks, legacy = _marks(), lp.legacy_marks(config)
    assert marks and all(item.kind == "good" for item in marks)
    assert [item.key for item in legacy] == list(config.categories) and len(legacy) == 8
    switch = _read(MOD / lp.EFFECTS)
    loc = "".join(_read(path) for path in LOC_FILES)
    for item in legacy:
        for path in (MOD / lp.GUI, MOD / lp.VALUES, MOD / lp.MARKERS):
            assert item.var not in _read(path), (path.name, item.key)
        assert f"PP_LPLAN_PICK_{item.key.upper()}" not in loc and f"PP_LPLAN_STATE_{item.key.upper()}" not in loc
        assert f"flag:{item.key} = " not in switch, "no toggle for a category"
    assert "PP_LPLAN_GROUP_BUILDINGS" not in _read(MOD / lp.GUI)
    drop = _effect(switch, "pp_lplan_drop_categories")
    clear = _effect(switch, "pp_lplan_clear_all")
    declare = _effect(switch, "pp_lplan_declare_flags")
    for item in legacy:
        assert drop.count(f"limit = {{ has_variable = {item.var} }}") == 1, item.key
        for name in (item.var, item.state, item.est):
            assert f"remove_variable = {name}\n" in drop and f"remove_variable = {name}\n" in clear, name
            # the engine logs a variable that is only ever removed: the never-run declaration sets it
            assert f"set_variable = {{ name = {name} value = 100 }}" in declare, name
    assert drop.count("change_variable = { name = pp_lplan_n subtract = 1 }") == len(legacy)
    assert "var:pp_lplan_n < 100.5" in drop and drop.rstrip().endswith("remove_variable = pp_lplan_n\n\t}")
    for loud in ("refresh_map_colors", "debug_log", "trigger_event", "custom_tooltip"):
        assert loud not in drop, loud
    # the declaration never runs
    select = _effect(_read(EFFECTS), "pp_lplan_select")
    assert select.index("limit = { always = no }") < select.index("pp_lplan_declare_flags = yes")
    assert switch.count("pp_lplan_declare_flags") == 1 and "pp_lplan_declare_flags = yes" not in _read(PROFILE_EFFECTS)
    # once per country, from the country's list, at the first pass whatever the group's weight (no walk at every
    # look), and before the list is cleaned (a location left with no mark then leaves the list); a toggle, Clear and
    # the window take them off the location they touch
    hand = _read(PROFILE_EFFECTS)
    cleanup = _effect(hand, "pp_lplan_cleanup")
    assert cleanup.index("pp_lplan_drop_categories_once = yes") < cleanup.index("limit = { NOT = { has_variable = pp_lplan_n } }")
    assert cleanup.count("pp_lplan_drop_categories = yes") == 0
    once = _effect(hand, "pp_lplan_drop_categories_once")
    assert once.index("limit = { NOT = { has_variable = pp_lplan_cats_gone } }") < once.index(
        "set_variable = { name = pp_lplan_cats_gone value = yes }") < once.index("variable = pp_lplan_locs") < once.index(
        "pp_lplan_drop_categories = yes")
    run = _effect(hand, "pp_lprof_run")
    assert run.index("pp_lplan_drop_categories_once = yes") < run.index("pp_cplan_profiles_w > 0")
    assert "pp_lplan_cleanup = yes" in _effect(hand, "pp_lprof_look") and "pp_lplan_cleanup = yes" not in run
    plan = _read(EFFECTS)
    for name in ("pp_lplan_flip", "pp_lplan_bflip", "pp_lplan_select"):
        assert _effect(plan, name).lstrip().startswith("pp_lplan_drop_categories = yes"), name


def test_a_building_is_marked_on_a_list_by_script() -> None:
    """Script cannot make a variable name per building type, so a building's mark is the building type on the
    location's variable list; the toggle keeps the count of marks and the owner's list like a goods mark's, and the GUI
    asks a scripted GUI's is_shown whether a building is marked (it cannot look into a list)."""
    plan = _read(EFFECTS)
    flip = _effect(plan, "pp_lplan_bflip")
    listed = f"{{ name = {lp.BUILDING_MARKS} target = scope:pp_bt }}"
    assert "pp_lplan_maps_ready = yes\n\tif = {\n\t\tlimit = { exists = scope:pp_bt }" in flip  # a click without a building: nothing
    assert f"limit = {{ is_target_in_variable_list = {listed} }}" in flip
    assert f"remove_list_variable = {listed}" in flip and f"add_to_variable_list = {listed}" in flip
    assert "change_variable = { name = pp_lplan_n subtract = 1 }" in flip and "change_variable = { name = pp_lplan_n add = 1 }" in flip
    assert "set_variable = { name = pp_lplan_n value = 100 }" in flip and "var:pp_lplan_n < 100.5" in flip
    assert "pp_lplan_keep_list = yes" in flip and "refresh_map_colors = yes" in flip
    # the GUI's scope is declared in a branch that never runs
    select = _effect(plan, "pp_lplan_select")
    assert select.index("limit = { always = no }") < select.index("save_scope_as = pp_bt")
    guis = _read(SCRIPTED_GUIS)
    toggle = _effect(guis, lp.BUILDING_MARK_GUI)
    assert "scope = location" in toggle and "pp_lplan_bflip = yes" in toggle
    asked = _effect(guis, lp.BUILDING_MARKED_GUI)
    assert "scope = location" in asked and "effect" not in asked
    assert "is_shown = {\n\t\texists = scope:pp_bt\n\t\tis_target_in_variable_list = " + listed in asked
    assert lp.building_mark_call("L", "B") == f"GetScriptedGui('{lp.BUILDING_MARK_GUI}').Execute(GuiScope.SetRoot(L).AddScope('pp_bt', B).End)"
    assert lp.building_marked("L", "B") == f"GetScriptedGui('{lp.BUILDING_MARKED_GUI}').IsShown(GuiScope.SetRoot(L).AddScope('pp_bt', B).End)"
    # Clear and an earlier owner's marks: the list goes too
    assert f"clear_variable_list = {lp.BUILDING_MARKS}\n" in _effect(_read(MOD / lp.EFFECTS), "pp_lplan_clear_all")
    # the window's counts: every mark, and the goods apart
    values = _read(MOD / lp.VALUES)
    goods = _effect(values, "pp_lplan_goods_n")
    assert all(f"has_variable = {item.var} }} add = 1" in goods for item in _marks())
    assert "value = pp_lplan_goods_n\n\tsubtract = pp_lplan_open_n" in _effect(values, "pp_lplan_done_n")
    assert "value = var:pp_lplan_n" in _effect(values, "pp_lplan_planned_n")


def test_location_window_building_tiles_carry_the_mark() -> None:
    """The way vanilla's auto expand toggles a building: beside each of vanilla's two Alt + click actions a Ctrl +
    click action, beside vanilla's badge a badge. Additive: taking the three blocks out gives the window without
    them, with every line of vanilla's still there."""
    import pytest

    window = _read(LOCATION_WINDOW)
    assert window.count(lp.BUILDING_MARK_COMMENT) == 3
    assert lp.add_building_marks(window) == window, "once"
    blocks = re.compile(r"[ \t]*(?:action_tooltip|icon) = \{ " + re.escape(lp.BUILDING_MARK_COMMENT) + r"\n(?:.*\n)*?[ \t]*\}\n")
    assert len(blocks.findall(window)) == 3
    without = blocks.sub("", window)
    assert lp.BUILDING_MARK_COMMENT not in without and lp.add_building_marks(without) == window, "run ppc build"
    assert without.count(lp._WINDOW_ACTION_ANCHOR) == 2 and without.count(lp._WINDOW_ICON_ANCHOR) == 1
    with pytest.raises(ValueError):
        lp.add_building_marks(without.replace(lp._WINDOW_ICON_ANCHOR, ""))
    # each action sits right after vanilla's auto-expand action, inside the same button
    for match in re.finditer(re.escape(lp._WINDOW_ACTION_ANCHOR), window):
        tail = window[match.end():match.end() + 1500]
        assert tail.index("}") < tail.index(lp.BUILDING_MARK_COMMENT) < tail.index("tooltipwidget")
    action = lp.window_mark_action("")
    assert "click_type = left" in action and "click_modifier = ctrl" in action
    assert "click_modifier = alt" not in action  # vanilla's auto expand keeps Alt
    assert 'visible = "[And(Building.GetLocation.GetOwner.IsPlayer, Not(IsObserving))]"' in action
    marked = lp.building_marked("Building.GetLocation.MakeScope", "BuildingType.MakeScope")
    assert f"title = \"[SelectLocalization({marked}, 'PP_LPLAN_BMARK_ON', 'PP_LPLAN_BMARK_OFF')]\"" in action
    assert f"on_action = \"[{lp.building_mark_call('Building.GetLocation.MakeScope', 'BuildingType.MakeScope')}]\"" in action
    icon = lp.window_mark_icon("")
    assert "parentanchor = bottom|right" in icon and 'tooltip = "PP_LPLAN_BMARK_ICON"' in icon  # vanilla's badge: top|right
    assert lp.building_marked("LocationBuildingItem.GetBuilding.GetLocation.MakeScope",
                              "LocationBuildingItem.GetBuilding.GetType.MakeScope") in icon
    assert (MOD / "main_menu" / lp.MARK_TEXTURE).is_file()
    # nothing but properties in the blocks: no box, no datamodel, no template of its own
    for block in (action, icon):
        assert block.count("{") == block.count("}") and "datamodel" not in block and "hbox" not in block


def test_marked_buildings_show_with_their_own_icons() -> None:
    """The Location Plan window lists the marked buildings from the location's list, each with the building's icon and
    name; a click takes the mark off. The texts say what a building's mark does."""
    gui = _read(MOD / lp.GUI)
    strip = gui[gui.index("type pp_lplan_bstrip = flowcontainer"):gui.index("type pp_lplan_picker")]
    assert f"datamodel = \"[Location.MakeScope.GetList('{lp.BUILDING_MARKS}')]\"" in strip
    assert 'texture = "[GetBuildingIcon(Scope.GetBuildingType.Self)]"' in strip
    assert 'tooltip = "PP_LPLAN_BMARK_TILE"' in strip
    assert lp.building_mark_call("Location.MakeScope", "Scope.GetBuildingType.MakeScope") in strip
    assert "hbox" not in strip and "vbox" not in strip
    assert "pp_lplan_bstrip = {" in _read(WINDOW)
    texts = _texts()
    assert texts["PP_LPLAN_BMARK_TILE"].startswith("#T [Scope.GetBuildingType.GetName]#!\\n$PP_LPLAN_BMARK_TILE_TEXT$\\n")
    for key in ("PP_LPLAN_BMARK_ON", "PP_LPLAN_BMARK_OFF", "PP_LPLAN_BMARK_ICON", "PP_LPLAN_BMARK_TILE_TEXT"):
        assert "Construction Plan" in texts[key] and not re.search(r"\d", texts[key]), key
    assert "Ctrl" in texts["PP_LPLAN_BMARK_ICON"] and "Ctrl" in texts["PP_LPLAN_NOTE"]


def test_texts_say_a_mark_is_forced() -> None:
    """A mark builds this here, level after level, from the Locations budget, whether it pays or not: no text still
    promises a payback limit for a mark."""
    texts = _texts()
    for key in ("PP_LPLAN_NOTE", "PP_LPLAN_PICK_ON", "PP_LPLAN_PICK_OFF", "PP_LPLAN_BMARK_OFF", "PP_LPLAN_BMARK_TILE_TEXT"):
        assert "level after level" in texts[key] and "Locations budget" in texts[key], key
    for key in ("PP_LPLAN_NOTE", "PP_LPLAN_PICK_OFF", "PP_LPLAN_BMARK_OFF"):
        assert "whether it pays or not" in texts[key], key
    for key, text in texts.items():
        assert "Businesses limit" not in text and "pays back within" not in text and "kind of building" not in text, key


# ---------------------------------------------------------------------------------------------------------------------
# a building mark's state and its icon on the map (2026-11-11)


def test_a_building_mark_keeps_its_state() -> None:
    """A building mark keeps its state after the last pass like a goods mark, with the same state texts. Script cannot
    name a variable per building type, so the state is an entry of the location's variable map pp_lplan_bst, keyed by
    the marked building type (the list entry, not the later tier the pass may build). Every mark writes its state in
    the second go, a waiting one too; the entry goes with the mark, with Clear and when the location is lost. An old
    save has no map: every removal asks first."""
    hand = _read(PROFILE_EFFECTS)
    walk = _effect(hand, "pp_lplan_building_marks")
    assert "scope:pp_lplan_mode > 1.5" in walk and "save_scope_as = pp_lplan_bkey" in walk
    mark = _effect(hand, "pp_lplan_building_mark")
    second = mark[mark.index("\telse = {\n\t\t# a construction started"):]
    assert second.index("pp_lprof_open = yes") < second.index("pp_lplan_b_finish = yes")
    for reason in ("pp_lprof_fail = { r = 101 }", "pp_lprof_fail = { r = 102 }", "pp_lprof_fail = { r = 104 }",
                   "pp_lprof_fail = { r = 105 }", "pp_lprof_fail = { r = 107 }",
                   "set_variable = { name = pp_lprof_st value = 103 }", "set_variable = { name = pp_lprof_st value = 101 }",
                   "pp_lprof_build = yes", "pp_cplan_note_goods = { why = 105 }"):
        assert reason in second, reason
    assert "pp_lprof_build = yes" not in mark[:mark.index(second)]  # measuring builds nothing
    finish = _effect(hand, "pp_lplan_b_finish")
    assert finish.index("pp_lprof_finish = { st = pp_lplan_bst_now est = pp_lplan_best_now }") < finish.index(
        "pp_lplan_b_state_off = { key = scope:pp_lplan_bkey }") < finish.index(
        f"add_to_variable_map = {{ name = {lp.BUILDING_STATES} key = scope:pp_lplan_bkey value = var:pp_lplan_bst_now }}")
    assert "remove_variable = pp_lplan_bst_now" in finish and "remove_variable = pp_lplan_best_now" in finish
    plan = _read(EFFECTS)
    off = _effect(plan, "pp_lplan_b_state_off")
    assert off.index(f"has_variable_map = {lp.BUILDING_STATES}") < off.index("any_key_in_variable_map") < off.index(
        f"remove_from_variable_map = {{ name = {lp.BUILDING_STATES} key = $key$ }}")
    assert "this = $key$" in off and '"$' not in off
    flip = _effect(plan, "pp_lplan_bflip")
    assert flip.index("remove_list_variable") < flip.index("pp_lplan_b_state_off = { key = scope:pp_bt }") < flip.index("else = {")
    clear = _effect(_read(MOD / lp.EFFECTS), "pp_lplan_clear_all")
    assert (f"limit = {{ has_variable_map = {lp.BUILDING_STATES} }}\n\t\tclear_variable_map = {lp.BUILDING_STATES}") in clear
    cleanup = _effect(hand, "pp_lplan_cleanup")
    lost = cleanup[cleanup.index("NOT = { owner ?= scope:pp_cplan_country }"):]
    assert lost.index(f"has_variable_map = {lp.BUILDING_STATES}") < lost.index(f"clear_variable_map = {lp.BUILDING_STATES}")
    # the texts: the tile (the row and the Location Plan window) and the map icon read the map entry
    texts = _texts()
    state = lp.building_state("Location.MakeScope", "Scope.GetBuildingType.MakeScope")
    assert state == f"Location.MakeScope.GetVariableFromVariableMap('{lp.BUILDING_STATES}', Scope.GetBuildingType.MakeScope)"
    line = f"[SelectLocalization({state}.IsSet, 'PP_LPLAN_BMSTS', 'PP_LPROF_ST_0')]"
    assert texts["PP_LPLAN_BMARK_TILE"].endswith(line) and texts["PP_LPLAN_BMARK_MAP"].endswith(line)
    for n in lp.MARK_STATES:
        assert (f"[AddTextIf(EqualTo_CFixedPoint({state}.GetValue, '(CFixedPoint){100 + n}'), "
                f"Localize('PP_LPROF_ST_{n}'))]") in texts["PP_LPLAN_BMSTS"], n
    assert "PP_LPROF_ST_5'" not in texts["PP_LPLAN_BMSTS"] and "PP_LPROF_ST_10'" not in texts["PP_LPLAN_BMSTS"]
    assert 'tooltip = "PP_LPLAN_BMARK_TILE"' in _read(MOD / lp.GUI)


def test_marked_buildings_on_the_map() -> None:
    """In the Location Plan map mode each marked building shows as its icon over the location after the goods: green
    once a level of it or of a later tier of its line stands there, red while not. The marker is drawn for every
    location, so it reads only the location's own list, capped, inside the part shown only where the location has
    marks; nothing in it is per building type (the line lookup is the generated trigger, asked per icon)."""
    from prosper_or_perish_constructor import location_profiles as lpf

    marker = _read(MOD / lp.MARKERS)
    plan = marker[marker.rindex("widget = {", 0, marker.index('name = "pp_lplan_marker"')):]
    plan = plan[:lp._marker_block_end(plan, 0)]
    model = f"datamodel = \"[DataModelFirst({lp.BUILDING_MARKS_MODEL}, '(int32){lp.BUILDING_MAP_ICONS}')]\""
    assert plan.count(model) == 1 and 0 < lp.BUILDING_MAP_ICONS <= 8
    buildings = plan[plan.rindex("flowcontainer = {", 0, plan.index(model)):]
    assert buildings.lstrip("flowcontainer = {\n\t").startswith("visible = \"[Location.MakeScope.Var('pp_lplan_n').IsSet]\"")
    done = lp.building_done("Location.MakeScope", "Scope.GetBuildingType.MakeScope")
    # the done check once per icon: one tile, its colour picked by it
    assert buildings.count(done) == 1
    assert f"color = \"[Select_CVector4f({done}, '(CVector4f)0.25,0.7,0.3,0.85', '(CVector4f)0.75,0.25,0.2,0.85')]\"" in buildings
    assert 'texture = "[GetBuildingIcon(Scope.GetBuildingType.Self)]"' in buildings and 'tooltip = "PP_LPLAN_BMARK_MAP"' in buildings
    assert "building_type:" not in plan and plan.count(lp.BUILDING_DONE_GUI) == 1
    assert "hbox" not in buildings and "vbox" not in buildings
    # the scripted GUI and its trigger
    asked = _effect(_read(SCRIPTED_GUIS), lp.BUILDING_DONE_GUI)
    assert "scope = location" in asked and "effect" not in asked
    assert "is_shown = {\n\t\texists = scope:pp_bt\n\t\tpp_lplan_b_done = yes" in asked
    # the done check: one key lookup, one walk over the location's buildings, each compared with the type and its
    # main line's later tiers (global maps pp_lplan_up<k>); a type without a later tier: the type alone
    done_trigger = _effect(_read(MOD / lpf.TRIGGERS), "pp_lplan_b_done")
    maps = lpf.building_mark_maps(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))
    pairs, _ = lpf.building_mark_data(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))
    assert "building_type:" not in done_trigger and done_trigger.count("any_buildings_in_location") == 2
    assert done_trigger.count("is_key_in_global_variable_map = { name = pp_lplan_up1 target = scope:pp_bt }") == 2
    for k in range(1, maps.depth + 1):
        assert f'building_type = "global_variable_map(pp_lplan_up{k}|scope:pp_bt)"' in done_trigger, k
    # every later tier of a line is on its main line (the maps hold the main line only)
    for old, names in lpf.newer_tiers(pairs).items():
        assert set(names) == set(maps.up[old]), old
    assert lpf.main_chain([("a", "b"), ("b", "c"), ("a", "c"), ("x", "y")]) == {"a": ["b", "c"], "b": ["c"], "x": ["y"]}
    # later tiers: the whole line up, a cycle ends
    assert lpf.newer_tiers([("a", "b"), ("b", "c"), ("x", "y"), ("c", "a")]) == {
        "a": ["b", "c"], "b": ["c", "a"], "x": ["y"], "c": ["a", "b"]}
    texts = _texts()
    assert "'PP_LPLAN_BMARK_DONE', 'PP_LPLAN_STATE_OPEN'" in texts["PP_LPLAN_BMARK_MAP"] and done in texts["PP_LPLAN_BMARK_MAP"]
    assert "newer kind" in texts["PP_LPLAN_BMARK_DONE"] and not re.search(r"\d", texts["PP_LPLAN_BMARK_DONE"])
    assert "building" in texts["PP_LPLAN_NOTE"].split("map mode")[1]


# Jan 2026-11-10: everywhere vanilla sets auto expand for a building, Ctrl + click marks it for the Construction Plan.
_SINGLE_CALL = lp.building_mark_call("Building.GetLocation.MakeScope", "Building.GetType.MakeScope")
_GUI_DIR = MOD / "in_game/gui"


def _single_marks(text: str) -> int:
    """Ctrl + click actions that mark the building in context, each right after one of vanilla's single toggles."""
    blocks = text.split(lp.AUTO_EXPAND_ACTION)[1:]
    return sum(1 for b in blocks if "click_modifier = ctrl" in b.split("action_tooltip = {", 2)[1][:900]
               and _SINGLE_CALL in b[:1500])


def test_build_panel_auto_expand_takes_ctrl_click() -> None:
    text = _read(_GUI_DIR / "build_location_lateralview.gui")
    assert _single_marks(text) == 1
    assert text.count(lp.mark_badge("\t\t\t\t\t\t").strip()) == 1
    mass = lp.building_mark_all_call("BuildInLocationLateralView.GetBuildingType.MakeScope")
    assert text.count(mass) == 1 and "click_type = right" in text[text.index(mass) - 300:text.index(mass)]
    # the rows without an own building: the plan's checkbox answers Ctrl + click and Ctrl + right click too
    row = lp.build_panel_mark("\t\t\t\t")
    assert row in text and row.count("click_modifier = ctrl") == 2
    assert lp.building_mark_all_call("LocationToBuildItem.GetBuildingType.MakeScope") in row


def test_building_window_auto_expand_takes_ctrl_click() -> None:
    assert _single_marks(_read(_GUI_DIR / "building_view.gui")) == 1


def test_location_view_rows_auto_expand_take_ctrl_click() -> None:
    assert _single_marks(_read(_GUI_DIR / "shared/pp_location_building_rows.gui")) == 1


def test_production_window_rows_take_ctrl_click() -> None:
    text = _read(_GUI_DIR / "shared/zz_pp_building_type_header.gui")
    assert "type building_type_header = hbox" in text and "type location_filtered_header_with_candidate = hbox" in text
    assert _single_marks(text) == 1
    mass = lp.building_mark_all_call("BuildingItem.GetBuildingType.MakeScope")
    assert text.count(mass) == 1
    assert text.index("ToggleAutoExpandBuildings(BuildingItem.GetBuildingsFunc)") < text.index(mass)


def test_mass_mark_scripted_gui_and_text() -> None:
    script = _read(SCRIPTED_GUIS)
    block = script[script.index(f"{lp.BUILDING_MARK_ALL_GUI} = {{"):]
    block = block[:block.index("\n}\n")]
    assert "scope = country" in block and block.count("pp_lplan_bflip = yes") == 2
    assert block.count("any_buildings_in_location = { building_type = scope:pp_bt }") == 3
    assert "PP_LPLAN_BMARK_ALL" in _loc_keys()
    assert block.count("{") == block.count("}") + 1


def test_auto_expand_marks_are_additive() -> None:
    """The inserts only add lines: the file without them is the vanilla text."""
    vanilla = _read(vanilla_root(ROOT, PROJECT) / "game/in_game/gui/building_view.gui")
    marked = lp.add_auto_expand_marks(vanilla, "test")
    assert len(marked) > len(vanilla)
    removed = re.sub(r"(?m)^[ \t]*(action_tooltip|icon) = \{ # PP: Construction Plan mark \(location_plan\.py\)\n"
                     r"(?:[ \t]+[^\n]*\n)*?[ \t]*\}\n", "", marked)
    assert removed == vanilla


# Jan 2026-11-10: everywhere vanilla sets auto expand for a building, Ctrl + click marks it for the Construction Plan.
_SINGLE_CALL = lp.building_mark_call("Building.GetLocation.MakeScope", "Building.GetType.MakeScope")
_GUI_DIR = MOD / "in_game/gui"


def _single_marks(text: str) -> int:
    """Ctrl + click actions that mark the building in context, each right after one of vanilla's single toggles."""
    count = 0
    for after in text.split(lp.AUTO_EXPAND_ACTION)[1:]:
        head = after[:1500]
        if lp.BUILDING_MARK_COMMENT in head and "click_modifier = ctrl" in head and _SINGLE_CALL in head:
            count += 1
    return count


def test_build_panel_auto_expand_takes_ctrl_click() -> None:
    text = _read(_GUI_DIR / "build_location_lateralview.gui")
    assert _single_marks(text) == 1
    mass = lp.building_mark_all_call("BuildInLocationLateralView.GetBuildingType.MakeScope")
    assert text.count(mass) == 1 and "click_type = right" in text[text.index(mass) - 300:text.index(mass)]
    # the rows without an own building: the plan's checkbox answers Ctrl + click and Ctrl + right click too
    row = lp.build_panel_mark("\t\t\t\t")
    assert row in text and row.count("click_modifier = ctrl") == 2
    assert lp.building_mark_all_call("LocationToBuildItem.GetBuildingType.MakeScope") in row


def test_building_window_auto_expand_takes_ctrl_click() -> None:
    assert _single_marks(_read(_GUI_DIR / "building_view.gui")) == 1


def test_location_view_rows_auto_expand_take_ctrl_click() -> None:
    assert _single_marks(_read(_GUI_DIR / "shared/pp_location_building_rows.gui")) == 1


def test_production_window_rows_take_ctrl_click() -> None:
    text = _read(_GUI_DIR / "shared/zz_pp_building_type_header.gui")
    assert "type building_type_header = hbox" in text and "type location_filtered_header_with_candidate = hbox" in text
    assert _single_marks(text) == 1
    mass = lp.building_mark_all_call("BuildingItem.GetBuildingType.MakeScope")
    assert text.count(mass) == 1
    assert text.index("ToggleAutoExpandBuildings(BuildingItem.GetBuildingsFunc)") < text.index(mass)
    assert text.count("{") == text.count("}")


def test_mass_mark_scripted_gui_and_text() -> None:
    script = _read(SCRIPTED_GUIS)
    block = script[script.index(f"{lp.BUILDING_MARK_ALL_GUI} = {{"):]
    block = block[:block.index("\n}\n") + 2]
    assert "scope = country" in block and block.count("pp_lplan_bflip = yes") == 2
    assert block.count("any_buildings_in_location = { building_type = scope:pp_bt }") == 3
    assert block.count("{") == block.count("}")
    assert "PP_LPLAN_BMARK_ALL" in _loc_keys()


def test_auto_expand_marks_are_additive() -> None:
    """The inserts only add blocks: the file without them is the vanilla text."""
    vanilla = _read(vanilla_root(ROOT, PROJECT) / "game/in_game/gui/building_view.gui")
    marked = lp.add_auto_expand_marks(vanilla, "test")
    assert len(marked) > len(vanilla)
    removed = re.sub(r"(?m)^([ \t]*)(action_tooltip|icon) = \{ # PP: Construction Plan mark \(location_plan\.py\)\n"
                     r"(?:\1\t[^\n]*\n)*\1\}\n", "", marked)
    assert removed == vanilla


def test_a_building_mark_shows_the_tier_the_plan_builds() -> None:
    """The icon takes the object (Scope.GetBuildingType is only a promote: blank in game 2026-11-11), and a marked type
    whose line the country researched further becomes that tier on the list: at the mark and at each location turn,
    changing the list only after the walk over it."""
    assert lp.BUILDING_MARK_ICON == "GetBuildingIcon(Scope.GetBuildingType.Self)"
    effects = _read(MOD / "in_game/common/scripted_effects/pp_location_plan.txt")
    body = effects[effects.index("pp_lplan_b_promote = {"):effects.index("pp_lplan_b_state_off = {\n")]
    first, second = body.index("variable = pp_lplan_b\n"), body.index("variable = pp_lplan_bold\n")
    assert first < second and "remove_list_variable" not in body[:second] and "pp_lplan_b_newest = yes" in body[second:]
    assert "change_variable = { name = pp_lplan_n subtract = 1 }" in body[second:]
    flip = effects[effects.index("pp_lplan_bflip = {"):effects.index("pp_lplan_b_promote = {")]
    assert flip.index("add_to_variable_list = { name = pp_lplan_b") < flip.index("pp_lplan_b_promote = yes")
    turn = _read(MOD / "in_game/common/scripted_effects/pp_location_profiles.txt")
    turn = turn[turn.index("pp_lplan_location_turn = {"):]
    assert turn.index("pp_lplan_b_promote = yes") < turn.index("pp_lplan_building_marks = yes")
