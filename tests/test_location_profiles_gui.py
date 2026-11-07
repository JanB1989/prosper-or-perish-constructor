"""Location Profiles, the GUI side (location_profiles_gui.py, mod/pp/.../pp_location_profiles*.gui, the Profile row of
the Location Plan window, the right-click menu section in context_menu.gui, the badge and paint frame in
map_markers.gui). Contract: docs/location_profiles.md."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_plan as lp
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
    "pp_lprof_set": {"pp_slot", "pp_field", "pp_key"},
    "pp_lprof_color": {"pp_slot", "pp_col"},
    "pp_lprof_payback": {"pp_slot", "pp_field", "pp_dir"},
    "pp_lprof_rule_clear": {"pp_slot", "pp_field"},
    "pp_lprof_rule_move": {"pp_slot", "pp_field", "pp_dir"},
    "pp_lprof_delete": {"pp_slot"},
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
    keys = {item.key for item in m.profile_items(ROOT, PROJECT)}
    allowed = {
        "pp_slot": slots | {"GetVariableSystem.Get('pp_lprof_edit')"},
        "pp_field": fields | {"GetVariableSystem.Get('pp_lprof_pick')"},
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
            ok = allowed[param] | ({"none", "GetVariableSystem.Get('pp_lprof_brush')"} if name == "pp_lprof_assign" and param == "pp_slot" else set())
            assert value in ok, f"{name}: {param} = {value}"
    assert found == text.count("Execute("), "a scripted GUI call does not read as SetRoot + AddScope flags + End"


def test_every_profile_part_is_there() -> None:
    config = _config()
    generated = _read(GENERATED)
    for k in range(1, config.slots + 1):
        assert f"type pp_lprof_face_{k} = widget" in generated
        assert f"'pp_lprof_edit', 's{k}'" in generated
        assert f"'pp_lprof_brush', 's{k}'" in generated
        for r in range(1, config.rules + 1):
            assert f"'pp_lprof_{k}_r{r}_pb'" in generated
    for r in range(1, config.rules + 1):
        assert f"GetVariableSystem.Set('pp_lprof_pick', 'r{r}')" in generated
    assert "GetVariableSystem.Set('pp_lprof_pick', 'icon')" in generated
    for item in m.profile_items(ROOT, PROJECT):
        assert f"MakeScopeFlag('{item.key}')" in generated, item.key
    assert lp.icon_exists(lp.Item(m.MARKET_ACCESS, "good", "access"), MOD, vanilla_root(ROOT, PROJECT))


def test_types_are_defined() -> None:
    texts = _gui_texts()
    defined = set(re.findall(r"type (pp_lprof_\w+) =", texts[WINDOW.name] + texts[GENERATED.name]))
    for name, text in texts.items():
        for used in set(re.findall(r"\b(pp_lprof_\w+) = \{", text)):
            assert used in defined, f"{name}: type {used} not defined"


def test_scripted_widgets_are_registered() -> None:
    lines = [line.split(" = ") for line in _read(WIDGETS).splitlines() if line.strip()]
    window = _read(WINDOW)
    assert {path for path, _ in lines} == {"gui/pp_location_profiles.gui"}
    for _, name in lines:
        assert f'name = "{name}"' in window, name
    assert {name for _, name in lines} == {"pp_location_profiles_window", "pp_location_profiles_palette"}


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
    config = _config()
    visible = re.search(r'name = "pp_lplan_marker"\n\t\tvisible = "([^"]+)"', marker).group(1)
    assert "Location.GetOwner.IsPlayer" in visible  # nothing for other locations
    for part in ("Var('pp_lplan_n').IsSet", "Var('pp_lprof').IsSet", "GetVariableSystem.Exists('pp_lprof_brush')"):
        assert part in visible
    for k in range(1, config.slots + 1):
        assert f"PP_LPROF_UI_BADGE_{k}" in marker and f"'pp_lprof_{k}_col'" in marker
    assert m.assign_call("=GetVariableSystem.Get('pp_lprof_brush')") in marker
    # the badge comes first, the plan icons stay behind pp_lplan_n
    cell, icons = marker.index("pp_lprof_marker_cell"), marker.index("PP_LPLAN_STATE_")
    assert cell < icons
    assert "\t\t\tflowcontainer = {\n\t\t\t\tvisible = \"[Location.MakeScope.Var('pp_lplan_n').IsSet]\"" in marker[cell:icons]


def test_plan_window_row_and_player_only() -> None:
    assert "pp_lprof_plan_row = {}" in _read(PLAN_WINDOW)
    assert "type pp_lprof_plan_row = vbox" in _read(GENERATED)
    window = _read(WINDOW)
    for name in ("pp_location_profiles_window", "pp_location_profiles_palette"):
        block = window[window.index(f'name = "{name}"'):][:300]
        assert "Not(IsObserving)" in block and "GetPlayer.Exists" in block, name
    assert "GetMapMode('pp_location_plan').IsSet" in window[window.index('name = "pp_location_profiles_palette"'):][:300]


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
    assert f"type {m.LOCATION_ROW} = vbox" in generated
