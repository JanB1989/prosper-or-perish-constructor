"""The market, the goods and markets ledgers and the trade-order goods picker skip the mod's internal goods
(tools/port_vanilla_gui.py, INTERNAL_GOODS): vanilla windows whose goods lists lay out visible rows only.

Hand-kept GUI the game checks only when it draws it, so these tests read the files the game loads.
"""

from __future__ import annotations

import re
from functools import cache

from test_build_location_gui import MOD_ROOT, _tool
from test_gui_blocks import _calls, _vanilla


@cache
def _mod(rel: str) -> str:
    tool = _tool()
    return tool._read(MOD_ROOT / tool.GUI / rel)


def _files() -> list[str]:
    tool = _tool()
    return [*tool.INTERNAL_GOODS_LISTS, *tool.INTERNAL_GOODS_ICONS, *tool.INTERNAL_GOODS_TABLES]


def test_windows_are_a_fresh_port_of_the_current_vanilla_files():
    """Hand edits go into port_internal_goods; after a game update rerun tools/port_vanilla_gui.py."""
    tool = _tool()
    for rel in _files():
        assert _mod(rel) == tool.port_internal_goods(tool._read(_vanilla() / tool.GUI / rel), rel), rel
    assert _mod(tool.INTERNAL_GOODS_GUI) == tool.internal_goods_gui(tool._read(_vanilla() / tool.COOLTIP_TYPES))


def test_hidden_goods_are_the_mods_goods():
    """A renamed or retired good would stay visible without a word; every hidden key must be a good the mod defines."""
    defined = set()
    for path in (MOD_ROOT / "in_game/common/goods").glob("*.txt"):
        defined |= set(re.findall(r"(?m)^﻿?(\w+)\s*=\s*\{", path.read_text(encoding="utf-8-sig")))
    assert set(_tool().INTERNAL_GOODS) <= defined
    template = _mod(_tool().INTERNAL_GOODS_GUI)
    for key in _tool().INTERNAL_GOODS:
        assert f"EqualTo_string(Goods.GetKey, '{key}')" in template


def test_every_goods_list_uses_the_template():
    tool = _tool()
    for rel, lists in tool.INTERNAL_GOODS_LISTS.items():
        text = _mod(rel)
        assert text.count(f"using = {tool.INTERNAL_GOODS_TEMPLATE}") == len(lists), rel
        for model, _ in lists:   # a vbox lays out visible rows only; a fixedgridbox keeps a cell per item
            assert re.search(r"vbox = \{ # PP: skips the internal goods[^\n]*\n[ \t]*layoutpolicy_horizontal = "
                             rf'expanding\n[ \t]*datamodel = "\[{re.escape(model)}\]"', text), (rel, model)
    for rel, models in tool.INTERNAL_GOODS_ICONS.items():
        text = _mod(rel)
        assert text.count(f"using = {tool.INTERNAL_GOODS_TEMPLATE}") == len(models), rel
        count = tool.TOP_GOODS + len(tool.INTERNAL_GOODS)
        for model in models:   # ignoreinvisible: hidden icons take no slot; the strip clips the rest at five
            assert re.search(r"ignoreinvisible = yes\n[ \t]*datamodel = "
                             rf"\"\[DataModelFirst\({re.escape(model)}, '\(int32\){count}'\)\]\"", text), (rel, model)
            assert f"DataModelFirst({model}, '(int32){tool.TOP_GOODS}')" not in text


def test_tooltip_goods_tables_show_five_goods_that_are_not_internal():
    """Each table's columns read the first five plus one per internal good on the goods table column, whose rows
    hide the internal goods and whose rows box is five rows high (the market tooltip's Greatest Local Surplus/
    Deficits)."""
    tool = _tool()
    count = tool.TOP_GOODS + len(tool.INTERNAL_GOODS)
    for rel, models in tool.INTERNAL_GOODS_TABLES.items():
        text = _mod(rel)
        assert text.count(f"{tool.GOODS_TABLE_COLUMN} = {{") == 3 * len(models), rel   # goods, balance, price
        for model in models:
            assert f"DataModelFirst({model}, '(int32){count}')" in text
            assert f"DataModelFirst({model}, '(int32){tool.TOP_GOODS}')" not in text
    column = _mod(tool.INTERNAL_GOODS_GUI)
    column = column[column.index(f"type {tool.GOODS_TABLE_COLUMN} = vbox"):]
    assert not re.search(r"(?m)^[ \t]*scrollvbox = \{", column)   # takes no scrollbar policy (error.log, 2026-10-17)
    rows = column[column.index("scrollarea = {"):]
    assert f"maximumsize = {{ -1 {tool.TOP_GOODS * 30} }}" in rows and "scrollbarpolicy_vertical = always_off" in rows
    assert "scrollwidget = {" in rows
    assert re.search(r'block "column_datamodel" \{\}\n\n[ \t]*item = \{\n[ \t]*TooltipTableField = \{\n[ \t]*'
                     r'blockoverride "visibility" \{\n[ \t]*datacontext = "\[GoodsMarketEntry\.GetGoods\]"\n[ \t]*'
                     rf"using = {tool.INTERNAL_GOODS_TEMPLATE}\n", rows)
    assert 'blockoverride "visibility"' not in column[:column.index("scrollarea = {")]   # the header stays


def test_data_functions_exist_in_the_game():
    used = _calls(_mod(_tool().INTERNAL_GOODS_GUI))
    assert {"GetKey", "EqualTo_string", "Or", "Not"} <= used
    vanilla = set()
    for path in _vanilla().glob("*/gui/**/*.gui"):
        vanilla |= _calls(path.read_text(encoding="utf-8-sig", errors="replace"))
    assert not sorted(used - vanilla)


def test_braces_balance():
    tool = _tool()
    for rel in [*_files(), tool.INTERNAL_GOODS_GUI]:
        text = _mod(rel)
        assert tool._block_end("{" + text + "}", 0) == len(text) + 2, rel
