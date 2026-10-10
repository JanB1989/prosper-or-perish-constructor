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
    """Widest location row (six slots: three columns of circles and efficiencies) inside the panel's row width."""
    tool = _tool()
    columns = 3
    row = (45 + 8                                   # building icon, card margins
           + tool.BUILD_LOCATION_CARD_WIDTH + 30    # location card, own-building checkboxes
           + columns * 24 + (columns - 1) * 2       # slot circles
           + columns * 70 + (columns - 1) * 6       # production efficiencies
           + 70 + 120 + 5)                          # profit, builder, margin
    assert row <= tool.BUILD_PANEL_WIDTH - 45       # list margins and scrollbar (vanilla: 570 panel, 525 row)


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


def test_braces_balance():
    tool = _tool()
    text = _mod_file()
    assert tool._block_end("{" + text + "}", 0) == len(text) + 2
