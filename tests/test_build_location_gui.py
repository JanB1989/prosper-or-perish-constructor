"""The build panel ("Building <type>") is vanilla laid out for PP's buildings (tools/port_vanilla_gui.py).

PP buildings have up to six production-method slots and up to 22 inputs in one slot (Cookshop); vanilla's panel
stacked the slots out of their location row and ran the inputs out of their filter row (Jan, 2026-10-10).
"""

from __future__ import annotations

import importlib.util
import re
from functools import cache
from pathlib import Path

from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


@cache
def _tool():
    spec = importlib.util.spec_from_file_location("port_vanilla_gui", ROOT / "tools/port_vanilla_gui.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def _mod_file() -> str:
    tool = _tool()
    return tool._read(MOD_ROOT / tool.GUI / tool.BUILD_LOCATION)


def test_build_panel_is_a_fresh_port_of_the_current_vanilla_file():
    """Hand edits go into port_build_location; after a game update rerun tools/port_vanilla_gui.py."""
    tool = _tool()
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
    assert _mod_file() == tool.port_build_location(tool._read(vanilla / tool.GUI / tool.BUILD_LOCATION))


def test_six_slot_row_fits_the_panel():
    """Widest location row (six slots: three columns of circles and efficiencies) with its value columns inside the
    panel's row width."""
    tool = _tool()
    columns = 3
    row = (45 + 8                                        # building icon, card margins
           + tool.BUILD_LOCATION_CARD_WIDTH + 30         # location card, own-building checkboxes
           + columns * 24 + (columns - 1) * 2            # slot circles
           + columns * tool.BUILD_EFFICIENCY_WIDTH + (columns - 1) * 6   # production efficiencies
           + sum(tool.BUILD_VALUE_WIDTHS) + 2 * tool.BUILD_VALUE_MARGIN  # build cost, payback, profit, tax income
           + 120 + 5)                                    # builder, margin
    assert row <= tool.BUILD_ROW_WIDTH <= tool.BUILD_PANEL_WIDTH - 45   # list margins, scrollbar (vanilla 570 -> 525)


def test_slot_columns_cover_six_slots_two_each():
    text = _mod_file()
    for model in ("LocationToBuildItem.GetBuildingSlots", "Building.GetProductionMethods"):
        models = re.findall(r'datamodel = "\[(DataModel[^"]*' + re.escape(model) + r'[^"]*)\]"', text)
        assert models == [
            f"DataModelFirst({model}, '(int32)2')",
            f"DataModelFirst(DataModelSkipFirst({model}, '(int32)2'), '(int32)2')",
            f"DataModelSkipFirst({model}, '(int32)4')",
        ]


def test_market_picker_opens_beside_the_panel():
    tool = _tool()
    text = _mod_file()
    picker = text[text.index('name = "build_location_select_market"'):]
    assert f"position_x = {tool.BUILD_PANEL_WIDTH}\n" in picker
    assert "select_menu_left" not in text.replace("vanilla select_menu_left", "")


def _loc() -> str:
    return (MOD_ROOT / "main_menu/localization/english/pp_build_panel_l_english.yml").read_text(encoding="utf-8-sig")


def test_cost_and_payback_columns_for_built_and_unbuilt_rows():
    """Construction Manager's ROI by profit: build cost / monthly profit per level in years, and the build cost, once
    per branch in the value columns template of the location row; the cost column has the engine's cost sort key;
    tooltips localized."""
    tool = _tool()
    text = _mod_file()
    assert tool.BUILD_PAYBACK_BASIS == tool.BUILD_PAYBACK_PROFIT
    for basis, tooltip in zip(tool.BUILD_PAYBACK_BASIS, tool.BUILD_PAYBACK_TOOLTIP):
        assert text.count(f'raw_text = "[{tool.payback_years(tool.BUILD_PAYBACK_COST, basis)}|1]@time!"') == 1
        assert text.count(f'tooltip = "{tooltip}"') == 2                       # cost and payback column
        assert f"  {tooltip}: " in _loc()
    assert text.count(f'raw_text = "[{tool.BUILD_PAYBACK_COST}|0]@gold!"') == 2
    assert text.count(f'name = "{tool.BUILD_COST_SORT_KEY}"') == 3             # header button, two highlights
    assert text.count("template pp_build_location_values {") == 1
    assert text.count("hbox = { using = pp_build_location_values }") == 1
    assert "widget = { #profit" not in text
    assert text.count("widget = { #builder") == 1 and text.count("widget = { #upgrader") == 1   # vanilla, in place


def test_payback_bands_are_consecutive():
    tool = _tool()
    bands = tool.payback_bands()
    assert bands[0][0] == 0 and bands[-1][1] is None
    assert all(high == low for (_, high), (low, _) in zip(bands, bands[1:]))
    assert all(high == low + 1 for low, high in bands[:-1])                    # whole years: the recorded value


def test_payback_order_reads_recorded_bands():
    """The cost call is too slow for every frame (in game 2026-10-17: band tests calling it every frame took the panel
    from 33 to 65 ms per frame, the profit call alone cost nothing). Each location records its band once into a GUI
    variable (a recorder created hidden, whose _show runs when the payback order opens or its construction count
    changes); the bands only read the variables (33 ms, the frame cap). Each band builds the vanilla row only for its
    items; a location not recorded yet goes last. The selected sort is vanilla's grid on vanilla's binding; whichever
    list is hidden is not updated. No box in the list (a vbox stretched and, with an expand, did not converge)."""
    tool = _tool()
    text = _mod_file()
    var = tool.BUILD_PAYBACK_VARIABLE
    name = tool.payback_band_name()
    assert f"onclick = \"[GetVariableSystem.Toggle('{var}')]\"" in text
    assert "  PP_BUILD_PAYBACK_ORDER_TT: " in _loc()
    bands = len(tool.payback_bands()) + 1                                        # and "not recorded yet"
    rows = re.findall(r"(?m)^[ \t]*using = build_location_entry\n", text)      # not vanilla's commented-out one
    assert len(rows) == 1 + bands
    tests = re.findall(r"datamodel = \"\[DataModelRepeatedItem\(Select_int32\((.*), '\(int32\)1', '\(int32\)0'\)\)\]\"",
                       text)
    assert tests == [f"GetVariableSystem.HasValue({name}, '{low}')" for low, _ in tool.payback_bands()] + [
        f"Not(GetVariableSystem.Exists({name}))"]
    records = re.findall(r"(?m)^([ \t]*)visible_at_creation = no\n\1visible = \"\[(.*)\]\"\n\1size = \{ 0 0 \}\n"
                         r"\1state = \{\n\1\tname = _show\n\1\ton_start = \"\[GetVariableSystem\.Set\((.*)\)\]\"\n", text)
    assert len(records) == 4                                                     # built/unbuilt x odd/even constructions
    for _, visible, setter in records:
        assert tool._payback_mode() in visible
        assert setter.startswith(name + ", Select_CString(")
    assert text.count(tool.BUILD_PAYBACK_COST) == (                              # cost and payback text per branch,
        4 + 4 * tool.BUILD_PAYBACK_BANDS[-1])                                    # the four recorders
    layout = text[text.index('blockoverride "scroll_list_layout"'):]
    layout = layout[:tool._block_end(layout, layout.index("{"))]
    assert not re.search(r"(?m)^[ \t]*(vbox|expand) = \{", layout)
    assert layout.count("fixedgridbox = {") == 1 and f"addcolumn = {tool.BUILD_ROW_WIDTH}\n" in layout
    assert layout.count(f"size = {{ {tool.BUILD_ROW_WIDTH} 60 }}") == 1 + bands
    assert layout.count('datamodel = "[BuildInLocationLateralView.GetItems]"') == 1 + 1 + bands   # grid, recorder
    assert layout.count(f'visible = "[Not({tool._payback_mode()})]"') == 1
    assert "DataModelFirst(BuildInLocationLateralView.GetItems" not in text
    assert "pp_build_payback_row" not in text and "pp_build_location_builder" not in text


def test_no_properties_the_engine_rejects():
    """error.log 2026-10-17: a dynamicgridbox takes no spacing; datacontext_from_model on an empty model logs an error
    for every row without a construction."""
    text = _mod_file()
    for grid in re.finditer(r"(?m)^([ \t]*)dynamicgridbox = \{[^\n]*\n((?:\1\t[^\n]*\n|\n)*?)\1\}", text):
        assert not re.search(rf"(?m)^{grid.group(1)}\tspacing = ", grid.group(2))
    assert not re.search(r"(?m)^[ \t]*datacontext_from_model = ", text)   # vanilla keeps one commented out
    assert "DataModelFirst(Location.GetCivilConstructions, '(int32)1')" in text


def test_every_sort_button_leaves_the_payback_order():
    tool = _tool()
    text = _mod_file()
    clear = f"onclick = \"[GetVariableSystem.Clear('{tool.BUILD_PAYBACK_VARIABLE}')]\""
    buttons = re.findall(r"(?m)^[ \t]*sort_by_key_button = \{[^\n]*\n[ \t]*name = \"\w+\"\n([^\n]*)\n", text)
    assert len(buttons) == tool.BUILD_SORT_BUTTONS
    assert all(clear in line for line in buttons)


def test_braces_balance():
    tool = _tool()
    text = _mod_file()
    assert tool._block_end("{" + text + "}", 0) == len(text) + 2
