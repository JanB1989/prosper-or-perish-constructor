"""Location Profiles, the GUI side (location_profiles_gui.py, mod/pp/.../pp_location_profiles*.gui, the Profile row of
the Location Plan window, the right-click menu section in context_menu.gui, the badge and paint frame in
map_markers.gui). Contract: docs/location_profiles.md."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_plan as lp
from prosper_or_perish_constructor import location_profiles as lpf
from prosper_or_perish_constructor import location_profiles_gui as m
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
WINDOW = MOD / m.WINDOW
GENERATED = MOD / m.GUI
MENU = MOD / m.CONTEXT_MENU
MARKERS = MOD / lp.MARKERS
WIDGETS = MOD / m.WIDGETS
LOC = MOD / m.LOC
PLAN_WINDOW = MOD / "in_game/gui/pp_location_plan.gui"
PLAN_SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_location_plan.txt"
PROFILE_SCRIPTED_GUIS = MOD / "in_game/common/scripted_guis/pp_location_profiles.txt"
DATA_TYPES = Path("/mnt/c/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/logs/data_types")
CONTAINERS = {"flowcontainer", "container", "dynamicgridbox", "fixedgridbox"}

# the parameters each scripted GUI takes (docs/location_profiles.md)
PARAMS = {
    "pp_lprof_assign": {"pp_slot"},
    "pp_lprof_new": {"pp_slot"},
    "pp_lprof_select": {"pp_slot"},
    "pp_lprof_set": {"pp_slot", "pp_field", "pp_key"},
    "pp_lprof_color": {"pp_slot", "pp_col"},
    "pp_lprof_payback": {"pp_slot", "pp_field", "pp_dir"},
    "pp_lprof_rule_clear": {"pp_slot", "pp_field"},
    "pp_lprof_rule_move": {"pp_slot", "pp_field", "pp_dir"},
    "pp_lprof_delete": {"pp_slot"},
    "pp_lprof_global": {"pp_slot", "pp_field"},
    "pp_lprof_examples": set(),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _config() -> m.Config:
    return m.load_config(PROJECT)


def _menu_section() -> str:
    text = _read(MENU)
    start = text.index(m.MENU_START)
    return text[start:text.index(m.MENU_END, start) + len(m.MENU_END)]


def _marker() -> str:
    text = _read(MARKERS)
    start = text.index("### Raw Goods Marker")
    return text[start:lp._marker_block_end(text, start)]


def _gui_texts() -> dict[str, str]:
    """Everything this side writes or patches in GUI files."""
    plan = _read(PLAN_WINDOW)
    return {
        WINDOW.name: _read(WINDOW),
        GENERATED.name: _read(GENERATED),
        "context_menu section": _menu_section(),
        "map marker": _marker(),
        PLAN_WINDOW.name: plan[plan.index("pp_lprof_plan_row"):][:40],
    }


def _all_text() -> str:
    return "".join(_gui_texts().values()) + _read(LOC)


def _loc_keys(folder: Path) -> set[str]:
    keys: set[str] = set()
    for path in folder.rglob("*.yml"):
        keys |= set(re.findall(r"^\s+([A-Za-z0-9_.\-]+):\d*\s", _read(path), re.MULTILINE))
    return keys


def test_built_mod_is_in_step() -> None:
    assert m.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False) == 0, "run ppc finalize"
    assert lp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False).files_changed == 0, "run ppc finalize"


def test_scripted_guis_follow_the_contract() -> None:
    calls = m.scripted_gui_calls(_all_text())
    profile_calls = {name for name in calls if name.startswith("pp_lprof")}
    assert profile_calls == set(m.SCRIPTED_GUIS) == set(PARAMS), "the GUI calls exactly the contract's scripted GUIs"
    plan_guis = _read(PLAN_SCRIPTED_GUIS)
    for name in calls - profile_calls:
        assert re.search(rf"^{name} = \{{", plan_guis, re.MULTILINE), f"scripted GUI {name} missing"
    if PROFILE_SCRIPTED_GUIS.is_file():  # the script side's file
        defined = _read(PROFILE_SCRIPTED_GUIS)
        for name in profile_calls:
            assert re.search(rf"^{name} = \{{", defined, re.MULTILINE), f"scripted GUI {name} not in {PROFILE_SCRIPTED_GUIS.name}"


def test_calls_pass_the_contract_parameters() -> None:
    config = _config()
    slots = {f"s{k}" for k in range(1, config.slots + 1)}
    fields = {"icon"} | {f"r{r}" for r in range(1, config.rules + 1)}
    keys = {item.key for item in m.profile_items(ROOT, PROJECT)} | {symbol.key for symbol in config.symbols}
    # the editor's buttons pass e (the edit buffer's slot), a new profile the first free slot (next)
    slot_values = {"pp_lprof_assign": slots | {"none", "GetVariableSystem.Get('pp_lprof_brush')"},
                   "pp_lprof_new": {m.NEXT}, "pp_lprof_select": slots}
    allowed = {
        "pp_slot": {m.EDITED},
        "pp_field": fields | {"GetVariableSystem.Get('pp_lprof_pick')"} | {flag for _, flag, _ in lpf.GLOBAL_GROUPS},
        "pp_dir": {"up", "down"},
        "pp_col": {f"c{index}" for index in range(1, len(config.colors) + 1)},
        "pp_key": keys,
    }
    text = _all_text()
    call = re.compile(
        r"GetScriptedGui\('(\w+)'\)\.Execute\(GuiScope\.SetRoot\(([\w.]+)\)"
        r"((?:\.AddScope\('\w+', MakeScopeFlag\((?:'\w*'|GetVariableSystem\.Get\('\w+'\))\)\))*)\.End\)"
    )
    found = 0
    for name, root, scopes in call.findall(text):
        found += 1
        if not name.startswith("pp_lprof"):
            continue
        params = dict(
            (param, value.strip("'") if value.startswith("'") else value)
            for param, value in re.findall(r"\.AddScope\('(\w+)', MakeScopeFlag\(('\w*'|GetVariableSystem\.Get\('\w+'\))\)\)", scopes)
        )
        assert set(params) == PARAMS[name], f"{name}: {sorted(params)}"
        assert root == ("Location.MakeScope" if name == "pp_lprof_assign" else "GetPlayer.MakeScope"), f"{name}: root {root}"
        for param, value in params.items():
            ok = slot_values.get(name, allowed[param]) if param == "pp_slot" else allowed[param]
            assert value in ok, f"{name}: {param} = {value}"
    assert found == text.count("Execute("), "a scripted GUI call does not read as SetRoot + AddScope flags + End"


def test_every_profile_part_is_there() -> None:
    config = _config()
    generated = _read(GENERATED)
    for k in range(1, config.slots + 1):
        assert f"type pp_lprof_face_{k} = widget" in generated
        assert m.player_call("pp_lprof_select", pp_slot=f"s{k}") in generated
        assert f"'pp_lprof_brush', 's{k}'" in generated
        assert m.assign_call(f"s{k}") in generated
    # the editor is one body on the edit buffer: no slot's rule is in the GUI
    assert not re.search(r"pp_lprof_\d+_r\d", generated)
    for r in range(1, config.rules + 1):
        assert f"GetVariableSystem.Set('pp_lprof_pick', 'r{r}')" in generated
        assert f"'pp_lprof_e_r{r}_pb'" in generated and f"'pp_lprof_e_r{r}_g'" in generated
    assert "GetVariableSystem.Set('pp_lprof_pick', 'icon')" in generated
    for item in m.profile_items(ROOT, PROJECT):
        assert f"MakeScopeFlag('{item.key}')" in generated, item.key
    for symbol in config.symbols:
        assert f"MakeScopeFlag('{symbol.key}')" in generated, symbol.key
    assert lp.icon_exists(lp.Item(m.MARKET_ACCESS, "good", "access"), MOD, vanilla_root(ROOT, PROJECT))
    # a new profile: one button in the editor's "Your profiles" row, shown while a slot is free
    window = _read(WINDOW)
    assert m.player_call("pp_lprof_new", pp_slot=m.NEXT) in window
    assert "ScriptValue('pp_lprof_first_free')" in window
    assert "pp_lprof_edit'" not in window + generated


def test_types_are_defined() -> None:
    texts = _gui_texts()
    defined = set(re.findall(r"type (pp_lprof_\w+) =", texts[WINDOW.name] + texts[GENERATED.name]))
    for name, text in texts.items():
        for used in set(re.findall(r"\b(pp_lprof_\w+) = \{", text)):
            assert used in defined, f"{name}: type {used} not defined"


def test_scripted_widgets_are_registered() -> None:
    """Only the paint palette is a scripted widget; the editor is a tab of the Construction Plan window."""
    lines = [line.split(" = ") for line in _read(WIDGETS).splitlines() if line.strip()]
    window = _read(WINDOW)
    assert {path for path, _ in lines} == {"gui/pp_location_profiles.gui"}
    for _, name in lines:
        assert f'name = "{name}"' in window, name
    assert {name for _, name in lines} == {"pp_location_profiles_palette"}
    assert len(re.findall(r"^(?:window|widget) = \{", window, re.MULTILINE)) == 1


def test_loc_keys_exist() -> None:
    """Every text the GUI names exists in an English loc file (the mod's or vanilla's)."""
    keys = _loc_keys(MOD / "main_menu/localization/english")
    vanilla = vanilla_root(ROOT, PROJECT) / "game/main_menu/localization/english"
    if vanilla.is_dir():
        keys |= _loc_keys(vanilla)
    text = _all_text()
    named = set(re.findall(r"\b(?:text|tooltip|title)\s*=\s*\"([A-Za-z][A-Za-z0-9_]*)\"", text))
    named |= set(re.findall(r"Localize\('([A-Za-z][A-Za-z0-9_]*)'\)", text))
    named |= set(re.findall(r"\$([A-Za-z][A-Za-z0-9_]*)\$", text))
    named |= set(re.findall(r"'([A-Z][A-Z0-9_]+)'", text))  # SelectLocalization's keys (variables are lower case)
    missing = sorted(key for key in named if key not in keys)
    assert not missing, f"texts missing: {missing}"
    for n in range(1, m.STATES + 1):  # the script side's state texts
        assert f"PP_LPROF_ST_{n}" in keys


def test_loc_file_format() -> None:
    raw = LOC.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "loc needs a UTF-8 BOM"
    lines = raw.decode("utf-8-sig").splitlines()
    assert lines[0] == "l_english:"
    for line in lines[1:]:
        assert re.match(r"^  (#|[A-Za-z0-9_]+: \".*\"$)", line), line

def test_buttons_have_tooltips() -> None:
    for name, text in _gui_texts().items():
        for match in re.finditer(r"\b(?:button_regular|pp_lprof_icon_button|button) = \{", text):
            block = text[match.start():lp._marker_block_end(text, match.start())]
            own = re.sub(r"\n(\t+)\w+ = \{.*?\n\1\}", "", block, flags=re.DOTALL)  # without child blocks
            if "onclick" in own:
                assert "tooltip = " in own, f"{name}: a button without a tooltip: {block[:200]}"


def _boxes_in_containers(text: str, types: dict[str, str]) -> list[str]:
    def base(name: str) -> str:
        seen = set()
        while name in types and name not in seen:
            seen.add(name)
            name = types[name]
        return name

    clean = re.sub(r'"[^"\n]*"', '""', re.sub(r"#[^\n]*", "", text))
    token = re.compile(r'type\s+\w+\s*=\s*(\w+)\s*\{|(\w+)\s*=\s*\{|(?:blockoverride|block)\s+""\s*\{|\{|\}')
    stack: list[str | None] = []
    bad = []
    for match in token.finditer(clean):
        if match.group(0) == "}":
            if stack:
                stack.pop()
            continue
        name = match.group(1) or match.group(2)
        name = base(name) if name else None
        parent = stack[-1] if stack else None
        if parent in CONTAINERS and name in {"hbox", "vbox"}:
            bad.append(f"{name} in {parent} at {clean.count(chr(10), 0, match.start()) + 1}")
        stack.append(name)
    return bad


def test_no_box_directly_inside_a_container() -> None:
    """EU5 refuses an hbox/vbox as a direct child of a (flow)container; a hot reload with one crashed the game."""
    texts = _gui_texts()
    types = dict(re.findall(r"type\s+(\w+)\s*=\s*(\w+)\s*\{", texts[WINDOW.name] + texts[GENERATED.name]))
    for name, text in texts.items():
        assert not _boxes_in_containers(text, types), name


def test_context_menu_is_vanilla_but_the_section() -> None:
    vanilla_path = vanilla_root(ROOT, PROJECT) / "game" / m.CONTEXT_MENU
    if not vanilla_path.is_file():
        pytest.skip("no vanilla game files")
    vanilla = _read(vanilla_path)
    mod = _read(MENU)
    section = _menu_section()
    assert mod.count(m.MENU_START) == 1
    assert mod.replace(section + "\n", "", 1) == vanilla
    start = mod.index(m._MENU_TYPE)
    assert start < mod.index(m.MENU_START) < m._block_end(mod, start), "the section sits in LocationContextMenu"
    # the type is used in other windows too: the section needs only Location
    assert "LocationView" not in section and "Location.GetOwner.IsPlayer" in section and "Not(IsObserving)" in section
    for entry in ("PP_LPROF_UI_MENU_NONE", "PP_LPROF_UI_MENU_PLAN", "pp_lplan_select", "'pp_lplan_open', 'yes'"):
        assert entry in section


def test_marker_shows_badge_and_paint_frame() -> None:
    marker = _marker()
    visible = re.search(r'name = "pp_lplan_marker"\n\t\tvisible = "([^"]+)"', marker).group(1)
    assert "Location.GetOwner.IsPlayer" in visible  # nothing for other locations
    for part in ("Var('pp_lplan_n').IsSet", "Var('pp_lprof').IsSet", "GetVariableSystem.Exists('pp_lprof_brush')"):
        assert part in visible
    # one badge from the location's copy of its profile, whatever the slot count
    cell = marker[marker.index("pp_lprof_marker_cell"):marker.index("PP_LPLAN_STATE_")]
    assert cell.count('tooltip = "PP_LPROF_UI_BADGE"') == 1
    assert not re.search(r"pp_lprof_\d|PP_LPROF_UI_BADGE_\d|pp_lprof_face_", cell)
    for name in ("pp_lprof_col", "pp_lprof_ig", "pp_lprof_in"):
        assert f"Location.MakeScope.Var('{name}')" in cell, name
    assert f'texture = "{m.FLAGS_TEXTURE}" framesize = {{ {m.FLAG_FRAME} {m.FLAG_FRAME} }}' in cell
    assert m.assign_call("=GetVariableSystem.Get('pp_lprof_brush')") in marker
    # the badge comes first, the plan icons stay behind pp_lplan_n
    cell, icons = marker.index("pp_lprof_marker_cell"), marker.index("PP_LPLAN_STATE_")
    assert cell < icons
    assert "\t\t\tflowcontainer = {\n\t\t\t\tvisible = \"[Location.MakeScope.Var('pp_lplan_n').IsSet]\"" in marker[cell:icons]


def test_plan_window_row_and_player_only() -> None:
    assert "pp_lprof_plan_row = {}" in _read(PLAN_WINDOW)
    assert "type pp_lprof_plan_row = vbox" in _read(GENERATED)
    window = _read(WINDOW)
    block = window[window.index('name = "pp_location_profiles_palette"'):][:300]
    assert "Not(IsObserving)" in block and "GetPlayer.Exists" in block
    assert "GetMapMode('pp_location_plan').IsSet" in block


def test_editor_is_the_plan_window_tab() -> None:
    """Jan 2026-11-09: the Construction Plan window has two tabs, Global settings and Location profiles. The editor's
    body is the type pp_lprof_editor_tab, which the plan window shows on its profiles tab (it fills the tab's vbox)."""
    window = _read(WINDOW)
    start = window.index("\ttype pp_lprof_editor_tab = vbox {")
    tab = window[start:lp._marker_block_end(window, start)]
    for needle in ("layoutpolicy_horizontal = expanding", "layoutpolicy_vertical = expanding", "pp_lprof_slot_strip = {}",
                   "pp_lprof_editor = {}", "pp_lprof_picker = {}", 'text = "PP_LPROF_UI_NOTE"', 'text = "PP_LPROF_UI_YOURS"',
                   "GetScriptedGui('pp_lprof_new')", "GetScriptedGui('pp_lprof_examples')", "GetMapMode('pp_location_plan').SetMapMode"):
        assert needle in tab, needle
    plan = _read(MOD / "in_game/gui/pp_construction_plan.gui")
    assert plan.count("pp_lprof_editor_tab = {}") == 1, "the plan window shows the editor tab once"
    assert "'pp_cplan_tab', 'profiles'" in plan


def test_every_editor_opener_opens_the_plan_tab() -> None:
    """Every "Edit profiles" (the palette, the Location Plan window's and the location window's Profile rows, the
    right-click menu) opens the Construction Plan window on its Location profiles tab; no editor window of its own."""
    assert m.OPEN_EDITOR == ("[GetVariableSystem.Set('pp_cplan_open', 'yes')]",
                             "[GetVariableSystem.Set('pp_cplan_tab', 'profiles')]")
    texts = _gui_texts()
    assert "pp_lprof_open" not in _all_text() + _read(WIDGETS) + _read(PLAN_WINDOW) + _read(MOD / "in_game/gui/location_window.gui")
    found = {}
    for name, text in texts.items():
        for match in re.finditer(r'(?:tooltip|title) = "PP_LPROF_UI_(?:EDIT_PROFILES|MENU_EDIT)_TT"', text):
            actions = re.findall(r'(?:onclick|on_action) = "([^"]+)"', text[match.end():text.index("}", match.end())])
            assert tuple(actions) == m.OPEN_EDITOR, f"{name}: {actions}"
            found[name] = found.get(name, 0) + 1
    # the palette; the Location Plan window's and the location window's Profile rows; the right-click menu
    assert found == {WINDOW.name: 1, GENERATED.name: 2, "context_menu section": 1}


def test_gui_functions_exist_in_the_data_type_dump() -> None:
    """Every function the GUI and the loc call is in the engine's data-type dump (logs/data_types, written by the game's
    console command; skipped where the dump is missing)."""
    files = sorted(DATA_TYPES.glob("data_types_*.txt")) if DATA_TYPES.is_dir() else []
    if not files:
        pytest.skip("no data-type dump")
    globals_, members = set(), set()
    for path in files:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            head = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?(?:\(| *$)", line)
            if head:
                (members if head.group(2) else globals_).add(head.group(2) or head.group(1))
    text = _all_text()
    used_globals, used_members = set(), set()
    for expression in re.findall(r"\[([^\]\n]+)\]", text):
        expression = re.sub(r"'[^']*'", "''", expression)
        used_globals |= set(re.findall(r"(?<![.\w])([A-Z][A-Za-z0-9_]*)\(", expression))
        used_globals |= set(re.findall(r"(?<![.\w])([A-Z][A-Za-z0-9_]*)(?=[.),])", expression))
        used_members |= set(re.findall(r"\.([A-Z][A-Za-z0-9_]*)", expression))
    data_contexts = {"Location", "ExtraTooltipInfo"}  # widget datacontexts, not globals
    assert not sorted(used_globals - globals_ - data_contexts), "unknown global GUI functions"
    assert not sorted(used_members - members), "unknown GUI member functions"


def test_location_window_has_the_profile_row() -> None:
    """The Infrastructure tab starts with the Profile row (player locations only), whose type is generated."""
    window = (MOD / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    block = re.search(re.escape(m.ROW_MARK) + r".*?\n\s*\}", window, re.DOTALL)
    assert block, "the location window lost the Profile row"
    assert "LocationView.GetLocation.GetOwner.IsPlayer" in block.group(0) and "Not(IsObserving)" in block.group(0)
    assert f"{m.LOCATION_ROW} = {{}}" in block.group(0)
    assert window.index(m.ROW_MARK) < window.index("# INFRASTRUCTURE HUB")
    generated = (MOD / "in_game/gui/pp_location_profiles_generated.gui").read_text(encoding="utf-8-sig")
    assert "type pp_lprof_plan_row = vbox" in generated
    # Jan 2026-11-09: the row looks like the tab's other rows (vanilla's card, header strip, toggle tiles)
    row = generated[generated.index(f"type {m.LOCATION_ROW} = hbox"):]
    row = row[:row.index("\n\t}\n") + 3]
    for needle in ("using = bg_paper_card", "using = bg_cabinet_card_frame", "using = bg_card_header_01",
                   "using = button_tab_toggle_properties_template", "down = \"[", "header_button_left = {"):
        assert needle in row, needle
    assert "pp_lprof_gold" not in row and "button_regular = {" not in row and "#yellow_titles" not in row
    # the header buttons: vanilla's shortcut types, 30 px apart (rename sits at 30, go to at -30)
    assert "button_minimize" not in window[window.index(lp.BUTTON_MARK) - 200:window.index(lp.BUTTON_MARK) + 2000]
    assert "position = { -60 0 }" in window and "position = { -90 0 }" not in window
    assert "button_round_shortcut = {" in window and "button_automation_shortcut = {" not in window


def _with_slots(config: m.Config, slots: int) -> m.Config:
    return dataclasses.replace(config, slots=slots)


def test_only_the_tiles_grow_with_the_slots() -> None:
    """The map marker (one per location), its badge and tooltip, and the editor are the same text for any slot count;
    only the slot tiles and their faces and tooltips are written per slot."""
    config = _config()
    small, large = _with_slots(config, 12), _with_slots(config, 100)
    items = m.profile_items(ROOT, PROJECT)
    assert m.marker_cell(small, "{ 10 10 }") == m.marker_cell(large, "{ 10 10 }")
    assert m._editor(small) == m._editor(large)
    vanilla_path = vanilla_root(ROOT, PROJECT) / "game" / lp.MARKERS
    if vanilla_path.is_file():
        vanilla = vanilla_path.read_text(encoding="utf-8-sig")
        plan_items = lp.plan_items(ROOT, lp.load_config(PROJECT))
        assert lp.render_markers(vanilla, plan_items, small) == lp.render_markers(vanilla, plan_items, large)
    loc_small, loc_large = m.render_loc(items, small), m.render_loc(items, large)
    for key in ("PP_LPROF_UI_BADGE", "PP_LPROF_UI_LINE_ST_1", "PP_LPROF_UI_LTGT_G_1", "PP_LPROF_UI_STATES_1"):
        line = re.search(rf"^  {key}: .*$", loc_small, re.MULTILINE).group(0)
        assert line in loc_large and "pp_lprof_e_" not in line and not re.search(r"pp_lprof_\d", line), key
    # the per-slot texts: a summary, three short tooltips and the icon's name (two keys) per slot, two per rule
    per_slot = len(loc_large.splitlines()) - len(loc_small.splitlines())
    assert per_slot == (100 - 12) * (6 + 2 * config.rules)


def test_no_texture_from_a_flag_name() -> None:
    """In game 2026-11-07: a texture built with Concatenate draws nothing (even from literals), and GetFlagName gives
    the flag's localized name, not its key. No texture or frame may use either; GetFlagName only shows a name."""
    for name, text in _gui_texts().items():
        for prop, value in re.findall(r"\b(texture|frame)\s*=\s*\"([^\"]*)\"", text):
            assert "Concatenate" not in value and "GetFlagName" not in value, f"{name}: {prop} = {value[:120]}"
        for expression in re.findall(r"\[[^\]\n]*GetFlagName[^\]\n]*\]", text):
            assert re.fullmatch(r"\[[\w.()']+\.GetFlagName\]", expression), f"{name}: GetFlagName used in {expression}"
    for expression in re.findall(r"\[[^\]\n]*GetFlagName[^\]\n]*\]", _read(LOC)):
        assert re.fullmatch(r"\[[\w.()']+\.GetFlagName\]", expression), f"loc: GetFlagName used in {expression}"
    # every flag drawn is a frame of the flag strip, from a frame number variable (*_in, *_r<r>_cn)
    generated = _read(GENERATED)
    frames = re.findall(r"pp_lprof_flag = \{ frame = \"\[FixedPointToInt\(Subtract_CFixedPoint\(\w+\.MakeScope\.Var\('(\w+)'\)", generated)
    assert frames and all(re.fullmatch(r"pp_lprof_(?:\d+_in|e_in|in|e_r\d+_cn)", var) for var in frames), set(frames)
    config = _config()
    assert {var for var in frames if "_r" in var} == {f"pp_lprof_e_r{r}_cn" for r in range(1, config.rules + 1)}
    assert f'texture = "{m.FLAGS_TEXTURE}"' in generated and f"framesize = {{ {m.FLAG_FRAME} {m.FLAG_FRAME} }}" in generated


def test_symbols_and_flag_pictures() -> None:
    """Every symbol has its picture (game format, for the picker), its name and its picker button; every flag a profile
    can hold (the building categories, then the symbols) is a frame of the flag strip, in the script's frame order; the
    colours are one texture of frames."""
    from eu5_building_pipeline.dds import dds_info, is_game_format

    from prosper_or_perish_constructor import location_profiles as lpf

    config = _config()
    vanilla = vanilla_root(ROOT, PROJECT)
    assert len(config.symbols) >= 15
    keys = {item.key for item in m.profile_items(ROOT, PROJECT)}
    loc = _read(LOC)
    generated = _read(GENERATED)
    for symbol in config.symbols:
        assert re.fullmatch(r"[a-z_]+", symbol.name) and symbol.key not in keys, symbol.name
        assert m.find_icon(symbol.texture, MOD, vanilla) is not None, f"{symbol.name}: no source {symbol.texture}"
        assert re.search(rf'^  {symbol.key}: "{re.escape(symbol.title)}"$', loc, re.MULTILINE), symbol.key
        assert f"PP_LPROF_UI_ITEM_{symbol.key.upper()}:" in loc
        assert f'texture = "{m.SYMBOL_TEXTURE}{symbol.key}.dds"' in generated
        picture = MOD / m.SYMBOL_DIR / f"{symbol.key}.dds"
        assert picture.is_file() and is_game_format(picture, max_side=128), symbol.key
    assert {path.stem for path in (MOD / m.SYMBOL_DIR).glob("*.dds")} == {symbol.key for symbol in config.symbols}, "stale pictures"
    assert m.SYMBOL_DIR.as_posix().endswith(m.SYMBOL_TEXTURE.rstrip("/"))
    flags = list(m.flag_sources(config))
    assert flags == lpf.frame_flags(config.categories, config)
    for flag, relative in m.flag_sources(config).items():
        assert m.find_icon(relative, MOD, vanilla) is not None, flag
    strip = MOD / m.FLAGS
    info = dds_info(strip)
    assert info and is_game_format(strip)
    assert (info.width, info.height) == (m.FLAG_FRAME * len(flags), m.FLAG_FRAME)
    assert strip.as_posix().endswith(m.FLAGS_TEXTURE) and "/icons/" not in m.FLAGS_TEXTURE  # icons/ is cut to 128 px
    colors = MOD / m.COLORS
    info = dds_info(colors)
    assert info and is_game_format(colors)
    assert (info.width, info.height) == (m.COLOR_FRAME * len(config.colors), m.COLOR_FRAME)
    assert colors.as_posix().endswith(m.COLORS_TEXTURE)
    # the symbols show only in the icon picker (they build nothing)
    picker = generated[generated.index("type pp_lprof_picker"):generated.index("type pp_lprof_plan_row")]
    group = picker[picker.index("PP_LPROF_UI_GROUP_SYMBOLS") - 200:picker.index("PP_LPROF_UI_GROUP_SYMBOLS")]
    assert "GetVariableSystem.HasValue('pp_lprof_pick', 'icon')" in group


# ---------------------------------------------------------------------------------------------------------------------
# the location window's second row, "Also build here" (Jan 2026-11-10): the location's marks as toggle tiles


def _also_row() -> str:
    generated = _read(GENERATED)
    row = generated[generated.index(f"type {m.ALSO_ROW} = hbox"):]
    return row[:row.index("\n\t}\n") + 3]


def test_also_build_row_sits_under_the_profile_row() -> None:
    """The row "Also build here" follows the Profile row in the same block of the Infrastructure tab (one wrapper:
    player locations only, the location as datacontext), in the built window and from the generator."""
    sample = "\t\tvbox = {\n\t\t\t# INFRASTRUCTURE HUB\n\t\t\thbox = {}\n\t\t}\n"
    patched = m.add_location_row(sample)
    block = patched[patched.index(m.ROW_MARK):patched.index("# INFRASTRUCTURE HUB")]
    assert block.count(" = {}") == 2
    assert block.index(f"{m.LOCATION_ROW} = {{}}") < block.index(f"{m.ALSO_ROW} = {{}}")
    assert "LocationView.GetLocation.GetOwner.IsPlayer" in block and "Not(IsObserving)" in block
    assert 'datacontext = "[LocationView.GetLocation]"' in block
    assert m.add_location_row(patched) == patched  # once
    window = (MOD / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    built = window[window.index(m.ROW_MARK):window.index("# INFRASTRUCTURE HUB")]
    assert [line.strip() for line in built.splitlines()[1:]] == [line.strip() for line in block.splitlines()[1:]], "run ppc build"


def test_also_build_row_is_the_profile_rows_card() -> None:
    """Not a new kind of widget: the Profile row's card (paper card, wooden frame, header strip, corner decoration),
    its text style, its toggle tiles (pressed + gold glow = marked) and its round button at the right end."""
    generated = _read(GENERATED)
    profile = generated[generated.index(f"type {m.LOCATION_ROW} = hbox"):]
    profile = profile[:profile.index("\n\t}\n") + 3]
    row = _also_row()
    for needle in ("using = bg_paper_card", "using = bg_cabinet_card_frame", "using = bg_card_header_01", "using = bg_corner_flavor",
                   "minimumsize = { -1 45 }", "margin = { 5 5 }", "using = header_button_template",
                   "using = button_tab_toggle_properties_template", "using = pressed_button_texture",
                   "glow_radius = 5 color = { 1.0 0.85 0.55 1.0 } alpha = 0.8", "header_button_left = {", "size = { 34 34 }",
                   "align = left|nobaseline", 'default_format = "#medium"'):
        assert needle in row and needle in profile, needle
    assert "pp_lprof_gold" not in row and "button_regular = {" not in row and "#yellow_titles" not in row
    assert 'text = "PP_LPLAN_ALSO_TITLE"' in row and 'text = "PP_LPLAN_ALSO_NONE"' in row
    assert f'texture = "{m.PLAN_ICON}"' in row
    assert (MOD / "main_menu" / m.PLAN_ICON).is_file()
    # one round button opens the Location Plan window on this location, for everything else
    button = row[row.index("header_button_left = {"):]
    assert 'tooltip = "PP_LPLAN_ALSO_MORE_TT"' in button and row.count("header_button_left = {") == 1
    for action in m.OPEN_PLAN:
        assert f'onclick = "{action}"' in button
    assert "GetScriptedGui('pp_lplan_select')" in m.OPEN_PLAN[0] and "'pp_lplan_open', 'yes'" in m.OPEN_PLAN[1]
    loc = _read(MOD / "main_menu/localization/english/pp_location_plan_l_english.yml")
    assert '  PP_LPLAN_ALSO_TITLE: "Also build here"\n' in loc


def test_also_build_row_tiles() -> None:
    """First every marked item (shown while marked, pressed), then, unmarked, the goods standing buildings make (the
    quick candidates, in chunks that show while the row has room). One click on a tile toggles the mark; the tooltip is
    the picker's (name, what the mark does, its state while marked)."""
    from prosper_or_perish_constructor import location_profiles as lpf

    row = _also_row()
    items = lp.plan_items(ROOT, lp.load_config(PROJECT))
    found, _ = lpf.targets(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))
    chunks = lpf.quick_chunks(m.profile_items(ROOT, PROJECT), found)
    first_chunk = row.rindex("flowcontainer = {", 0, row.index("pp_lplan_quick_room_1'"))
    marked, quick = row[:first_chunk], row[first_chunk:]
    position = 0
    for item in items:
        toggle = m.execute("pp_lplan_toggle", "Location.MakeScope", pp_key=item.key)
        tile = (f"visible = \"[Location.MakeScope.Var('{item.var}').IsSet]\"\n\t\t\t\t\t\tsize = {{ {m.MARK_TILE} 34 }}")
        at = marked.index(tile, position)  # the picker's order
        position = at + 1
        block = marked[at:marked.index("\n\t\t\t\t\t}\n", at)]
        assert f"down = \"[Location.MakeScope.Var('{item.var}').IsSet]\"" in block, item.key
        assert f'tooltip = "PP_LPLAN_PICK_{item.key.upper()}"' in block and f'onclick = "{toggle}"' in block, item.key
        assert f'texture = "{item.icon}"' in block, item.key
    assert marked.count("pp_lplan_toggle") == len(items)
    # the quick candidates: goods only, each once, in their chunks; not pressed; the same toggle and tooltip
    values = _read(MOD / lpf.VALUES)
    shown = re.findall(r"ScriptValue\('pp_lplan_quick_(?!room_)(\w+)'\), '\(CFixedPoint\)1'\)", quick)
    assert shown == [item.key for chunk in chunks for item in chunk] and len(shown) == len(set(shown))
    assert "down = " not in quick and "glow = " not in quick
    rooms = re.findall(r"visible = \"\[GreaterThan_CFixedPoint\(Location\.MakeScope\.ScriptValue\('pp_lplan_quick_room_(\d+)'\), '\(CFixedPoint\)0'\)\]\"", quick)
    assert rooms == [str(number) for number in range(1, len(chunks) + 1)]
    for name in [f"pp_lplan_quick_{key}" for key in shown] + [f"pp_lplan_quick_room_{number}" for number in rooms]:
        assert re.search(rf"^{name} = \{{", values, re.MULTILINE), f"script value {name} missing"
    assert re.search(r"^pp_lplan_planned_n = \{", _read(MOD / lp.VALUES), re.MULTILINE)
    for key in shown:
        assert f'tooltip = "PP_LPLAN_PICK_{key.upper()}"' in quick
        assert m.execute("pp_lplan_toggle", "Location.MakeScope", pp_key=key) in quick
    # tiles carry their own gap, so chunks that show nothing take no room: no spacing in the tile line
    line = row[row.index("flowcontainer = {"):]
    assert "spacing" not in line[:line.index("\n\t\t\tvbox = {")]
    assert lpf.QUICK_ROW * m.MARK_TILE <= m.LOCATION_TILES * 37  # as wide as the Profile row's line of tiles
    # the scripted GUI the tiles call exists and toggles a mark
    assert re.search(r"^pp_lplan_toggle = \{", _read(PLAN_SCRIPTED_GUIS), re.MULTILINE)


def test_global_rules_checkboxes() -> None:
    """Five "Global rules here" checkboxes in the editor, the fifth for the Towns and Buildings group; the badge
    tooltip lists them all."""
    from prosper_or_perish_constructor import location_profiles as lpf

    generated = _read(GENERATED)
    editor = generated[generated.index("type pp_lprof_editor = vbox"):generated.index("type pp_lprof_picker")]
    assert [flag for _, flag, _ in lpf.GLOBAL_GROUPS][-1] == "global_country"
    for name, flag, _ in lpf.GLOBAL_GROUPS:
        assert m.player_call("pp_lprof_global", pp_slot=m.EDITED, pp_field=flag) in editor, flag
        assert f"down = \"[Not(GetPlayer.MakeScope.Var('pp_lprof_e_{name}').IsSet)]\"" in editor, flag
        assert f'text = "PP_LPROF_UI_{flag.upper()}"' in editor and f'tooltip = "PP_LPROF_UI_{flag.upper()}_TT"' in editor
    assert editor.count("button_checkbox = {") == len(lpf.GLOBAL_GROUPS) == 5
    loc = _read(LOC)
    assert '  PP_LPROF_UI_GLOBAL_COUNTRY: "Towns and Buildings"\n' in loc
    badge = re.search(r"^  PP_LPROF_UI_BADGE: .*$", loc, re.MULTILINE).group(0)
    assert "$PP_LPROF_UI_GLOBAL_COUNTRY$" in badge and "Var('pp_lprof_xc').IsSet" in badge
