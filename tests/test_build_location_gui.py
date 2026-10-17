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
    assert row <= tool.BUILD_PANEL_WIDTH - 45            # list margins and scrollbar (vanilla: 570 panel, 525 row)


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


def test_payback_order_lists_every_item_once():
    """Each band builds the vanilla row only for its items (bands do not overlap, plus one band for no profit); the
    selected sort and the payback order each take all items or none, so the hidden list builds no rows. The list ends
    in an expand (without it the box spread the panel's spare height above and between the rows, seen in game)."""
    tool = _tool()
    text = _mod_file()
    var = tool.BUILD_PAYBACK_VARIABLE
    assert f"onclick = \"[GetVariableSystem.Toggle('{var}')]\"" in text
    assert "  PP_BUILD_PAYBACK_ORDER_TT: " in _loc()
    bands = len(tool.payback_bands()) + 1
    rows = re.findall(r"(?m)^[ \t]*using = build_location_entry\n", text)      # not vanilla's commented-out one
    assert len(rows) == 1 + 2 * bands                                            # selected sort, built/unbuilt per band
    assert text.count("DataModelRepeatedItem(Select_int32(") == 2 * bands
    assert "pp_build_payback_row" not in text and "pp_build_location_builder" not in text
    layout = text[text.index('blockoverride "scroll_list_layout"'):]
    layout = layout[:tool._block_end(layout, layout.index("{"))]
    assert re.search(r"expand = \{\}\n[ \t]*\}\n[ \t]*\}$", layout)   # last in the list's box
    every = "GetDataModelSize(BuildInLocationLateralView.GetItems)"
    assert text.count(f"Select_int32({tool._payback_mode()}, {every}, '(int32)0'))]\"") == bands
    assert text.count(f"Select_int32({tool._payback_mode()}, '(int32)0', {every}))]\"") == 1
    assert 'blockoverride "scroll_list_content"' not in text


def test_braces_balance():
    tool = _tool()
    text = _mod_file()
    assert tool._block_end("{" + text + "}", 0) == len(text) + 2
