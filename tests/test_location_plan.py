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
    assert "lumber" in keys and "furniture" in keys and "trade_category" in keys
    assert "offset" not in keys and "manual_labor" not in keys


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
    for item in lp.plan_items(ROOT, lp.load_config(PROJECT)):
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
    """One click marks or unmarks an item: the toggle passes the item's name part (g_<good> / c_<category>), from which
    the mark, its state and its payback note are named; unmarking takes the state along."""
    items = lp.plan_items(ROOT, lp.load_config(PROJECT))
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
    items = lp.plan_items(ROOT, lp.load_config(PROJECT))
    texts = _texts()
    profile_keys: set[str] = set()
    for path in PROFILE_LOC.glob("pp_location_profiles*_l_english.yml"):
        profile_keys |= set(re.findall(r"^  ([A-Za-z0-9_]+):", _read(path), re.MULTILINE))
    assert lp.MARK_STATES == 10  # 10: the market limit (2026-11-10)
    for n in range(0, lp.MARK_STATES + 1):
        assert f"PP_LPROF_ST_{n}" in profile_keys, n
    for item in items:
        upper = item.key.upper()
        pick, state, line = texts[f"PP_LPLAN_PICK_{upper}"], texts[f"PP_LPLAN_STATE_{upper}"], texts[f"PP_LPLAN_MST_{upper}"]
        assert f"'PP_LPLAN_MST_{upper}', 'PP_LPROF_UI_EMPTY'" in pick and f"Var('{item.var}').IsSet" in pick, item.key
        assert state.endswith(f"$PP_LPLAN_MST_{upper}$"), item.key
        # not checked yet = the profile's state 0; else one of its states 1..9, by the mark's own state variable
        assert f"Var('{item.state}').IsSet, 'PP_LPLAN_MSTS_{upper}', 'PP_LPROF_ST_0'" in line, item.key
        states = texts[f"PP_LPLAN_MSTS_{upper}"]
        for n in range(1, lp.MARK_STATES + 1):
            assert (f"[AddTextIf(EqualTo_CFixedPoint(Location.MakeScope.Var('{item.state}').GetValue, '(CFixedPoint){100 + n}'), "
                    f"Localize('PP_LPROF_ST_{n}'))]") in states, (item.key, n)
        # beside "pays back too slowly" (state 5): the payback found
        assert f"'(CFixedPoint)105'), Location.MakeScope.Var('{item.est}').IsSet), 'PP_LPLAN_MEST_{upper}'" in line, item.key
        assert f"Var('{item.est}').GetValue" in texts[f"PP_LPLAN_MESTY_{upper}"], item.key
    # every profile text the plan's texts use exists
    used = set(re.findall(r"'(PP_LPROF_[A-Z0-9_]+)'", "".join(texts.values())))
    assert {"PP_LPROF_UI_EMPTY", "PP_LPROF_UI_EST_NO_PROFIT", "PP_LPROF_ST_0"} <= used
    assert used <= profile_keys, sorted(used - profile_keys)
    # state texts: no numbers, and they fit a rule and a mark alike
    hand = dict(re.findall(r'^  ([A-Z0-9_]+): "(.*)"$', _read(PROFILE_LOC / "pp_location_profiles_l_english.yml"), re.MULTILINE))
    for n in range(0, lp.MARK_STATES + 1):
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
