"""The Construction Plan opens from its own tab in the game's top-left tab row (Jan, 2026-11-20).

The mod's ``panels/left_panel/left_panel.gui`` is vanilla's plus that one tab (tools/port_vanilla_gui.py,
port_left_panel). A broken copy of this file breaks the whole top-left HUD, so these tests read the file the game loads.
"""

from __future__ import annotations

import re

from test_build_location_gui import MOD_ROOT, _tool
from test_gui_blocks import _calls, _vanilla

WINDOW = MOD_ROOT / "in_game/gui/pp_construction_plan.gui"
LOC = MOD_ROOT / "main_menu/localization/english"


def _mod() -> str:
    tool = _tool()
    return tool._read(MOD_ROOT / tool.GUI / tool.LEFT_PANEL)


def _tab() -> str:
    tool = _tool()
    text = _mod()
    start = text.rindex("\n", 0, text.index(tool.PLAN_TAB_MARKER)) + 1
    return text[start:tool._block_end(text, text.index("{", start))]


def test_left_panel_is_vanilla_plus_the_plan_tab():
    """Hand edits go into port_left_panel; after a game update rerun tools/port_vanilla_gui.py."""
    tool = _tool()
    vanilla = tool._read(_vanilla() / tool.GUI / tool.LEFT_PANEL)
    mod = _mod()
    assert mod == tool.port_left_panel(vanilla)
    tab = _tab()
    start = mod.index(tab)
    # one addition (a blank line, the tab's indentation and the tab), nothing else changed
    line = mod.rindex("\n", 0, start) + 1
    assert mod[line - 2:line] == "\n\n" and not mod[line:start].strip()
    assert mod[:line - 2] + mod[start + len(tab):] == vanilla


def test_tab_sits_last_in_the_tab_row():
    mod = _mod()
    row = mod[mod.index('name = "tabs_buttons"'):]
    tabs = re.findall(r"button_panel_tab_alt = \{ ###\s*([^\n]*)", row[:row.index("IsObservingWithoutSelectedCountry")])
    assert len(tabs) == 10
    assert tabs[-2] == "decisions tab" and tabs[-1].startswith("PP: Construction Plan tab")


def test_tab_click_down_state_tooltip_visibility_icon():
    from prosper_or_perish_constructor import construction_plan_country as cc

    tab = _tab()
    assert 'visible = "[And(GetPlayer.Exists, Not(IsObserving))]"' in tab   # never for observers
    assert tab.count("down = \"[GetVariableSystem.Exists('pp_cplan_open')]\"") == 1
    assert tab.count("visible = \"[GetVariableSystem.Exists('pp_cplan_open')]\"") == 1   # the icon's open highlight
    onclicks = re.findall(r'(?m)^\t+onclick = "([^"\n]*)"', tab)
    assert onclicks == ["[GetVariableSystem.Toggle('pp_cplan_open')]", cc.LAYOUT_CALL]
    assert 'tooltip = "PP_CPLAN_OPEN_TT"' in tab
    loc = "".join(p.read_text(encoding="utf-8-sig") for p in LOC.glob("*.yml"))
    assert re.search(r'(?m)^  PP_CPLAN_OPEN_TT: "#T ', loc)
    assert 'texture = "gfx/interface/icons/flat_icons/mass_construct.dds"' in tab
    assert "size = { 26 26 }" in tab and "texture_density = 2" in tab
    # the window it opens reads the same variable
    assert "GetVariableSystem.Exists('pp_cplan_open')" in WINDOW.read_text(encoding="utf-8-sig")


def test_tab_uses_only_what_vanilla_and_the_plan_window_use():
    """Every template, block and data function of the tab is one the vanilla file or the working plan window uses."""
    tool = _tool()
    tab = _tab()
    vanilla = tool._read(_vanilla() / tool.GUI / tool.LEFT_PANEL)
    for name in re.findall(r"using = (\w+)", tab):
        assert f"using = {name}" in vanilla, name
    for name in re.findall(r'blockoverride "(\w+)"', tab):
        assert f'blockoverride "{name}"' in vanilla, name
    for widget in re.findall(r"(?m)^\t*(\w+) = \{", tab):
        assert re.search(rf"(?m)^\t*{widget} = \{{", vanilla), widget
    known = _calls(vanilla) | _calls(WINDOW.read_text(encoding="utf-8-sig"))
    # VariableSystem.Toggle: in the game's data type dump (logs/data_types, EU5 1.4.9); the plan's opener used it in
    # game since 2026-11-06 (the floating button, then the docked tab)
    known |= {"Toggle"}
    assert not sorted(_calls(tab) - known)


def test_braces_balance():
    for text in (_mod(), _tab()):
        code = re.sub(r'"[^"\n]*"', '""', re.sub(r"#[^\n]*", "", text))
        depth = 0
        for c in code:
            depth += (c == "{") - (c == "}")
            assert depth >= 0
        assert depth == 0


def test_exactly_one_opener():
    window = WINDOW.read_text(encoding="utf-8-sig")
    assert "pp_cplan_opener" not in window
    assert 'name = "pp_construction_plan"' not in window
    assert "mass_construct.dds" not in window
    widgets = (MOD_ROOT / "in_game/gui/scripted_widgets/pp_construction_plan.txt").read_text(encoding="utf-8-sig")
    assert widgets.split() == ["gui/pp_construction_plan.gui", "=", "pp_construction_plan_window"]
    assert 'name = "pp_construction_plan_window"' in window
    openers = [p for p in (MOD_ROOT / "in_game/gui").rglob("*.gui")
               if "GetVariableSystem.Toggle('pp_cplan_open')" in p.read_text(encoding="utf-8-sig", errors="replace")]
    assert [p.relative_to(MOD_ROOT / "in_game/gui").as_posix() for p in openers] == [_tool().LEFT_PANEL]
