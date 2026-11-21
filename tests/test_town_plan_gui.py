"""The location window's Plans row (town_plan_gui.py): on top of the Infrastructure tab, player-owned locations only,
the held plans (location variables pp_tplan_p_<plan>) as pressed tiles that take the plan off, and the button that opens the
Location Plan window. It replaces the Profile row and the row "Also build here"."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_plan as lp
from prosper_or_perish_constructor import town_plan_gui as tpg
from prosper_or_perish_constructor import town_plans
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
LOCATION_WINDOW = MOD / "in_game/gui/location_window.gui"
DATA_TYPES = Path(r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\logs\data_types")
DATA_TYPES_WSL = Path("/mnt/c/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/logs/data_types")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


@cache
def _plans() -> list[lp.Plan]:
    return lp.plannable(lp.plans_for(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT)))


def _row_type() -> str:
    gui = _read(MOD / lp.GUI)
    start = gui.index(f"type {tpg.ROW_TYPE} = hbox {{")
    return gui[start:lp._marker_block_end(gui, start)]


def test_row_sits_on_top_of_the_infrastructure_tab_for_the_player_only() -> None:
    window = _read(LOCATION_WINDOW)
    assert window.count(tpg.ROW_MARK) == 1
    at = window.index(tpg.ROW_MARK)
    assert at < window.index("# INFRASTRUCTURE HUB") < at + 400
    block = window[at:window.index("# INFRASTRUCTURE HUB")]
    assert f'visible = "[{tpg.VISIBLE}]"' in block and "Not(IsObserving)" in tpg.VISIBLE
    assert 'datacontext = "[LocationView.GetLocation]"' in block and f"{tpg.ROW_TYPE} = {{}}" in block
    assert tpg.add_plan_row(window) == window, "once"
    for gone in ("pp_lprof_location_row", "pp_lplan_location_row", "Location Profile row"):
        assert gone not in window, gone
    with pytest.raises(ValueError):
        tpg.add_plan_row("no anchor here")


def test_row_tiles_are_the_held_plans() -> None:
    """One tile per plan, shown while the location holds it, pressed; a click takes the plan off (the same toggle as
    the picker), the tooltip carries the plan's state."""
    row = _row_type()
    for plan in _plans():
        tile = row[row.index(f'visible = "[{lp.held(plan)}]"'):]
        tile = tile[:tile.index("icon = {")]
        assert f"onclick = \"{lp.toggle_call(plan)}\"" in tile and f'tooltip = "{plan.tooltip}"' in tile, plan.key
        assert "down = yes" in tile
    assert row.count("onclick = \"[GetScriptedGui('pp_tplan_toggle')") == len(_plans())
    assert "flag('fur')" not in row and "MakeScopeFlag('fur')" not in row
    # none yet / more than the line holds: the plan count
    assert f"ScriptValue('{lp.COUNT}'), '(CFixedPoint)0')" in row
    assert f"GreaterThan_CFixedPoint(Location.MakeScope.ScriptValue('{lp.COUNT}'), '(CFixedPoint){tpg.ROW_TILES}')" in row
    assert f"size = {{ {tpg.ROW_TILES * tpg.TILE_WIDTH} 34 }}" in row and "scissor = yes" in row
    # the round button opens the Location Plan window on this location
    for onclick in tpg.OPEN_PLAN:
        assert f'onclick = "{onclick}"' in row
    assert row.count("{") == row.count("}")
    assert "pp_lplan_b" not in row and "pp_lprof" not in row


def test_count_value_counts_the_plans() -> None:
    """The plan count of the Plans row: 0 unless the location holds a plan (pp_tplan_any), then 1 per held plan's
    marker (2026-11-21: plans are location variables, no town rights)."""
    values = _read(MOD / lp.VALUES)
    block = values[values.index(f"{lp.COUNT} = {{"):]
    block = block[:block.index("\n}\n")]
    assert block.index("value = 0") < block.index(f"limit = {{ has_variable = {town_plans.ANY_VAR} }}")
    adds = re.findall(r"if = \{ limit = \{ has_variable = (\w+) \} add = 1 \}", block)
    assert adds == [plan.var for plan in _plans()]
    assert "town_rights" not in block


def test_row_texts() -> None:
    texts = dict(re.findall(r'^  ([A-Za-z0-9_]+): "(.*)"$', _read(MOD / "main_menu/localization/english/pp_location_plan_l_english.yml"),
                            re.MULTILINE))
    row = _row_type()
    for key in set(re.findall(r'"(PP_TPLAN_ROW_[A-Z_]+)"', row)):
        assert key in texts, key
        assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", texts[key])), key
    assert "Construction Plan" in texts["PP_TPLAN_ROW_MORE_TT"]


def test_gui_functions_exist_in_the_data_type_dump() -> None:
    """Every GUI function the row, the picker and the map marker use beyond the old row's is in the game's dump."""
    folder = DATA_TYPES if DATA_TYPES.is_dir() else DATA_TYPES_WSL
    if not folder.is_dir():
        pytest.skip("no data type dump")
    dump = "".join(path.read_text(encoding="utf-8", errors="replace") for path in folder.glob("data_types_*.txt"))
    names = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_.]*)(?:\(|$)", dump, re.MULTILINE))
    for name in ("Location.GetTownRights", "TownRights.GetIcon", "TownRights.GetName", "GetDataModelSize",
                 "DataModelFirst", "GreaterThan_int32", "GreaterThan_CFixedPoint", "EqualTo_CFixedPoint",
                 "Location.MakeScope", "Location.GetOwner", "MakeScopeFlag", "GetScriptedGui", "Select_float"):
        assert name in names or f"{name}(" in dump, name
