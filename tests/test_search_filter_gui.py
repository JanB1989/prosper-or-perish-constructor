"""The left panels' shared search filter menu opens beside the PP panels that are wider than vanilla's 570
(tools/port_vanilla_gui.py, port_select_search_filter + _mark_width). Jan, 2026-10-17: the build panel's filters
could not be clicked, the menu opened under the 990-wide panel.
"""

from __future__ import annotations

import importlib.util
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


def test_search_filter_menu_is_a_fresh_port():
    tool = _tool()
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
    assert _mod(tool.SEARCH_FILTER) == tool.port_select_search_filter(tool._read(vanilla / tool.GUI / tool.SEARCH_FILTER))


def test_menu_opens_at_the_width_its_panel_wrote():
    tool = _tool()
    text = _mod(tool.SEARCH_FILTER)
    assert 'name = "select_search_filter_left"' in text and "select_menu_left = {" not in text
    for width in (tool.BUILD_PANEL_WIDTH, tool.BUILDING_VIEW_WIDTH):
        assert f"HasValue('{tool.PANEL_WIDTH_VARIABLE}', '{width}'), '(CVector2f){width},180'" in text
    assert "'(CVector2f)570,180'" in text
    assert "position_x" not in text[text.index('name = "select_search_filter_left"'):]   # states keep the position


def test_wide_panels_write_their_width():
    tool = _tool()
    for rel, view, width in ((tool.BUILD_LOCATION, "BuildInLocationLateralView", tool.BUILD_PANEL_WIDTH),
                             (tool.LOCATION_PRODUCTION, "LocationProductionView", tool.BUILD_PANEL_WIDTH),
                             (tool.BUILDING_VIEW, "BuildingView", tool.BUILDING_VIEW_WIDTH)):
        text = _mod(rel)
        assert f"\tsize = {{ {width} 100% }}" in text, rel
        assert f"on_start = \"[{view}.Vars.Set('{tool.PANEL_WIDTH_VARIABLE}', '{width}')]\"" in text, rel
