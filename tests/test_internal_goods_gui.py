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
    # a scrollvbox (a scrollarea misaligned the columns in game) without scrollbar policies (error.log, 2026-10-17)
    assert not re.search(r"(?m)^[ \t]*scrollarea = \{", column)
    rows = column[column.index("scrollvbox = {"):]
    assert f"maximumsize = {{ -1 {tool.TOP_GOODS * 30} }}" in rows and "scrollbarpolicy" not in rows
    assert re.search(r'block "column_datamodel" \{\}\n\n[ \t]*item = \{\n[ \t]*TooltipTableField = \{\n[ \t]*'
                     r'blockoverride "visibility" \{\n[ \t]*datacontext = "\[GoodsMarketEntry\.GetGoods\]"\n[ \t]*'
                     rf"using = {tool.INTERNAL_GOODS_TEMPLATE}\n", rows)
    assert 'blockoverride "visibility"' not in column[:column.index("scrollvbox = {")]   # the header stays


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


def test_market_stockpile_column_shows_fill_and_amount():
    """Jan, 2026-11-01: vanilla's 5 px stockpile bar was unreadable. The goods row shows a wide bar with the fill in
    whole percent and the stockpile amount beside it, and the header buttons follow the wider column."""
    tool = _tool()
    text = _mod(tool.MARKET_GOODS)
    assert "size = { 5 22 }" not in text
    assert text.count(f"size = {{ {tool.STOCKPILE_CELL_WIDTH} 22 }}") == 1
    assert text.count('value = "[GoodsMarketEntry.GetStockpilePercentage]"') == 1
    assert text.count('raw_text = "[GoodsMarketEntry.GetStockpilePercentage|0]%"') == 1
    assert text.count('text = "[GoodsMarketEntry.GetStockpile|0]"') == 2   # the amount; weak when the stock is empty
    view = _mod(tool.MARKET_VIEW)
    assert f"\tsize = {{ {tool.MARKET_PANEL_WIDTH} 100% }}" in view   # the wider panel holds the wider row
    picker = view[view.index('name = "market_view_select_market"'):]
    assert f"position = {{ {tool.MARKET_PANEL_WIDTH} 180 }}" in picker   # its market picker opens beside it


def test_market_stock_months_column():
    """Jan, 2026-11-01: the stock in months of demand beside the fill, as a bar; the engine has no sort key for it, so
    its header is an icon. Guarded where a market has no demand of the good, and every text key exists."""
    tool = _tool()
    text = _mod(tool.MARKET_GOODS)
    assert text.count(f"size = {{ {tool.STOCK_MONTHS_CELL_WIDTH} 22 }}") == 1
    assert text.count(f'value = "[FixedPointToFloat({tool.STOCK_MONTHS})]"') == 1
    assert text.count(f'raw_text = "[{tool.STOCK_MONTHS}|1]"') == 1
    assert text.count(f"max = {tool.STOCK_MONTHS_BAR_MAX}") == 1
    assert text.count("GreaterThan_CFixedPoint(Market.GetDemand(GoodsMarketEntry.GetGoods), '(CFixedPoint)0')") == 1
    assert tool.STOCK_MONTHS_HEADER not in text   # a marker in the tool, never a sort key in the game
    # every division sits behind the demand check, its tooltip too: a fixed-point divide by zero can crash the game
    assert re.search(r'visible = "\[GreaterThan_CFixedPoint\(Market\.GetDemand\(GoodsMarketEntry\.GetGoods\), \'\(CFixedPoint\)0\'\)\]"\n'
                     r'[ \t]*tooltip = "PP_MARKET_STOCK_MONTHS_TT"\n', text)
    assert text.count('tooltip = "PP_MARKET_STOCK_MONTHS_TT"') == 1
    english = "\n".join(p.read_text(encoding="utf-8-sig") for p in (tool.MOD_ROOT / "main_menu/localization/english").glob("*.yml"))
    for key in ("PP_MARKET_STOCK_MONTHS_TT", "PP_MARKET_STOCK_MONTHS_HEADER_TT"):
        assert key in text and f"{key}:" in english


def _header(text: str, index: int) -> list[tuple[str | None, int]]:
    start = [m.start() for m in re.finditer(r'blockoverride "sort_buttons_filtered_list"', text)][index]
    block = text[start:text.index("expand = {}", start)]
    out = []
    for m in re.finditer(r'(?:name = "(\w+)"\n[ \t]*layoutpolicy_vertical = expanding\n[ \t]*)?size = \{ (\d+) (?:-1|1) \}',
                         block):
        out.append((m.group(1), int(m.group(2))))
    return out


def test_market_header_buttons_sit_over_their_cells():
    """Jan, 2026-11-01: the values under a header button must be the ones it sorts. The rows lay their cells side by
    side from the left (the free room at the end) and each header button is as wide as its cell."""
    tool = _tool()
    text = _mod(tool.MARKET_GOODS)
    assert text.count("expand = {} # PP: the cells side by side from the left") == 2   # Goods and Regional rows
    lead = tool.MARKET_ROW_LEAD + 30
    cells = [tool.STOCKPILE_CELL_WIDTH, tool.STOCK_MONTHS_CELL_WIDTH, 62, 62, 62, 15, 62, tool.MARKET_PRICE_WIDTH,
             tool.MARKET_PRICE_DIFF_WIDTH]
    columns = [None if c == tool.STOCK_MONTHS_HEADER else c for c in tool.MARKET_COLUMNS]   # the icon has no sort key
    assert _header(text, 0) == [("name", lead), *zip(columns, cells)]
    assert _header(text, 1) == [("name", lead), *zip(tool.IN_RANGE_COLUMNS, [62, 62, 62, 62, 62, 15, 62])]
    for key in ('name = "market_price"', 'name = "market_price_diff"'):   # its header button and its own cell
        assert text.count(key) == 2, key
    # the price against its default as a signed percentage (red above, green below), not vanilla's coin icons
    assert text.count(f'text = "[{tool.PRICE_AGAINST_DEFAULT}|-=0%]"') == 1
    assert "GetPriceDifferenceIconName" not in text
    row = 30 + sum(cells) + 2 + tool.MARKET_ACTIONS_WIDTH
    assert row <= tool.MARKET_PANEL_WIDTH - tool.MARKET_ROW_LOSS   # the actions stay clear of the scrollbar


def test_market_row_actions_skip_the_observer():
    """An observer has an empty country: the row's action checks (CanGoodGetProduced runs the producers'
    country_potential) logged about a thousand script errors a second (2026-11-01). Hidden for observers, in a box
    that keeps their room so the columns stay put."""
    tool = _tool()
    text = _mod(tool.MARKET_GOODS)
    box = re.search(rf"widget = \{{ # PP: the actions only for a player[^\n]*\n[ \t]*size = \{{ {tool.MARKET_ACTIONS_WIDTH} 30 \}}\n"
                    r'\n[ \t]*hbox = \{\n[ \t]*visible = "\[Not\(IsPlayerObserver\)\]"\n', text)
    assert box
    assert "CanGoodGetProduced" not in text[:box.start()]
    assert text.count("CanGoodGetProduced") == 4 and text.count("header_button_left = {", box.end()) >= 4
