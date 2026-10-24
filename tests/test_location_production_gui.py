"""The location view ("Production in <location>") uses the build panel's layout (tools/port_vanilla_gui.py): building
rows with slot circles and efficiencies two per column, build cost, payback, profit and tax income, and the payback
order (Jan, 2026-10-17: "it's not using our interface"). Its rows are pp_ copies of vanilla types that CMF re-declares.
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


def _mod(rel: str) -> str:
    tool = _tool()
    return tool._read(MOD_ROOT / tool.GUI / rel)


def test_rows_file_is_a_fresh_port():
    tool = _tool()
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
    assert _mod(tool.LOCATION_ROWS_GUI) == tool.port_location_rows(tool._read(vanilla / tool.GUI / tool.PRODUCTION))


def test_rows_use_the_build_panel_layout():
    tool = _tool()
    rows = _mod(tool.LOCATION_ROWS_GUI)
    for name in tool.LOCATION_ROW_TYPES:
        assert f"type pp_{name} = hbox {{" in rows
    for model in ("LocationToBuildItem.GetBuildingSlots", "Building.GetProductionMethods"):
        assert re.findall(r'datamodel = "\[(DataModel[^"]*' + re.escape(model) + r'[^"]*)\]"', rows) == [
            f"DataModelFirst({model}, '(int32)2')",
            f"DataModelFirst(DataModelSkipFirst({model}, '(int32)2'), '(int32)2')",
            f"DataModelSkipFirst({model}, '(int32)4')",
        ]
    assert 'hbox = { datacontext = "[BuildingCandidate.GetLocationToBuildItem]" using = pp_build_location_values }' in rows
    assert f"hbox = {{ using = {tool.LOCATION_VALUES_UNBUILT} }}" in rows
    assert f"template {tool.LOCATION_VALUES_UNBUILT} {{" in rows
    assert "#upkeep" in rows                                   # buildings that produce nothing keep their upkeep
    assert "widget = { # profit/income/upkeep" not in rows and "widget = { #profit / income" not in rows


def test_rows_record_their_payback_band():
    """Built rows record from the candidate (built and unbuilt branch x construction parity), unbuilt rows from the
    building type; the variable is the build panel's, so both views share it."""
    tool = _tool()
    rows = _mod(tool.LOCATION_ROWS_GUI)
    setters = re.findall(r'on_start = "\[GetVariableSystem\.Set\((.*)\)\]"', rows)
    assert len(setters) == 4 + 2
    assert all(s.startswith(tool.payback_band_name() + ", Select_CString(") for s in setters)
    assert rows.count("visible_at_creation = no") == 6


def test_location_view_uses_the_rows_and_the_payback_order():
    tool = _tool()
    text = _mod(tool.LOCATION_PRODUCTION)
    for name in tool.LOCATION_ROW_TYPES:
        assert not re.search(rf"(?m)^[ \t]*{name} = \{{", text)
        assert re.search(rf"(?m)^[ \t]*pp_{name} = \{{", text)
    assert f"\tsize = {{ {tool.BUILD_PANEL_WIDTH} 100% }}" in text
    clear = f"onclick = \"[GetVariableSystem.Clear('{tool.BUILD_PAYBACK_VARIABLE}')]\""
    assert text.count(clear) == tool.LOCATION_SORT_BUTTONS
    assert f"onclick = \"[GetVariableSystem.Toggle('{tool.BUILD_PAYBACK_VARIABLE}')]\"" in text
    name = tool.payback_band_name()
    tests = re.findall(r"datamodel = \"\[DataModelRepeatedItem\(Select_int32\((.*), '\(int32\)1', '\(int32\)0'\)\)\]\"",
                       text)
    assert tests == [f"GetVariableSystem.HasValue({name}, '{low}')" for low, _ in tool.payback_bands()] + [
        f"Not(GetVariableSystem.Exists({name}))"]
    assert tool.BUILD_PAYBACK_COST not in text                 # never in the bands: the cost call is too slow
    assert "  PP_BUILD_COST_HEADER_TT: " in (MOD_ROOT / "main_menu/localization/english/pp_build_panel_l_english.yml"
                                             ).read_text(encoding="utf-8-sig")


def test_braces_balance():
    tool = _tool()
    for rel in (tool.LOCATION_ROWS_GUI, tool.LOCATION_PRODUCTION):
        text = _mod(rel)
        assert tool._block_end("{" + text + "}", 0) == len(text) + 2, rel
