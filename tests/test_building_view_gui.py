"""The building window's header row (tools/port_vanilla_gui.py, port_building_view): slot circles and production
efficiencies two per column, so a three-slot PP building fits the 50-high row and its checkbox column stays
clickable (Jan, 2026-10-17: auto expand on a Tailors' Guild).
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
    return tool._read(MOD_ROOT / tool.GUI / tool.BUILDING_VIEW)


def test_building_view_is_a_fresh_port():
    tool = _tool()
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
    assert _mod_file() == tool.port_building_view(tool._read(vanilla / tool.GUI / tool.BUILDING_VIEW))


def test_header_slots_and_efficiencies_two_per_column():
    text = _mod_file()
    for model in ("LocationToBuildItem.GetBuildingSlots", "Building.GetProductionMethods"):
        assert re.findall(r'datamodel = "\[(DataModel[^"]*' + re.escape(model) + r'[^"]*)\]"', text) == [
            f"DataModelFirst({model}, '(int32)2')",
            f"DataModelFirst(DataModelSkipFirst({model}, '(int32)2'), '(int32)2')",
            f"DataModelSkipFirst({model}, '(int32)4')",
        ]
    assert not re.search(r'(?m)^[ \t]*datamodel = "\[(LocationToBuildItem\.GetBuildingSlots|Building\.GetProductionMethods)\]"',
                         text)


def test_six_slot_header_fits_the_window():
    """Header row (vanilla: window minus 10+5 margins each side, 3 inside, spacing 6) with three columns of slots and
    efficiencies."""
    tool = _tool()
    columns = 3
    row = (40 + 130 + 30                                  # piechart, name, checkbox column
           + columns * 24 + (columns - 1) * 2             # slot circles
           + columns * 70 + (columns - 1) * 6             # efficiencies
           + 60 + 120 + 6 * 6)                            # profit, builder, spacing
    assert row <= tool.BUILDING_VIEW_WIDTH - 2 * (10 + 5 + 3)


def test_braces_balance():
    tool = _tool()
    text = _mod_file()
    assert tool._block_end("{" + text + "}", 0) == len(text) + 2
