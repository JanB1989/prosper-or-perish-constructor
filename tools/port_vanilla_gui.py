"""Rebuild the mod's hand-kept vanilla GUI overrides from the current vanilla files (run after an EU5 update).

Each override is the vanilla file plus the mod's own changes, which are written down here so the next game update
only needs a rerun: the stored-food gauges (the script value ``pp_province_food_storage_months`` instead of the
vanilla food-capacity percentage), for the Europedia, the Prosper or Perish page (its button and its cards, taken from the current mod
file), for the build panel a layout that fits PP's many-slot, many-input buildings (``port_build_location``), the
same for the location view's rows (``port_location_rows``, ``port_location_production``) and the building window's
header (``port_building_view``), and
for the market, the goods and markets ledgers and the trade-order goods picker the internal goods hidden
(``port_internal_goods``). Everything else is vanilla, so whatever the game adds to these windows stays visible.

``location_window.gui`` is not handled here: it is generated from the World Builder export by the finalize step of
``ppc build`` / ``ppc sync`` (location_view.py), followed by the finalize GUI steps ``gui_compat.strip`` ->
``compile_food_storage_gui`` -> ``gui_compat.protect``, which write the food-storage divisor and the CMF-proof ``pp_``
type copies.

    uv run python tools/port_vanilla_gui.py            # write the overrides into the mod
    uv run python tools/port_vanilla_gui.py --check    # report which overrides differ from a fresh port
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD_ROOT = REPO / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
GUI = Path("in_game/gui")
MONTHS_VALUE = "pp_province_food_storage_months"   # script value, in_game/common/script_values/pp_province_food_storage.txt
# divisor placeholder; compile_food_storage_gui writes the configured maximum
DIVISOR = "24"

# file -> scope of the province whose food the vanilla gauges show
FOOD_GAUGE_FILES: dict[str, str] = {
    "attribute_columns/province.gui": "InteractionTarget.GetProvince",
    "food_production_lateralview.gui": "Province",
    "location_production_lateralview.gui": "Province",
    "selected_market_view.gui": "Province",
    "shared/province_tooltips.gui": "Province",
    "town_rights.gui": "Province",   # 1.4 moved the province list here from the expansion view
}
# overrides the mod no longer needs (pure vanilla after the port)
RETIRED = ("expansion_lateralview.gui",)
EUROPEDIA = "encyclopedia_lateralview.gui"
# the build panel ("Building <type>"): width (vanilla left panel 570; a six-slot row with the value columns needs
# ~920), row width (fixed: the rows sit in flowcontainers; panel minus list margins and scrollbar, 45 in vanilla, and
# some slack), location card (vanilla 150) and the input goods per line of a slot filter row (the Cookshop slot has 22)
BUILD_LOCATION = "build_location_lateralview.gui"
BUILD_PANEL_WIDTH = 990
BUILD_ROW_WIDTH = BUILD_PANEL_WIDTH - 60
BUILD_LOCATION_CARD_WIDTH = 175
BUILD_INPUTS_PER_LINE = 14
# the location rows keep vanilla's production efficiencies (two methods per column) and get one value per column:
# build cost, payback time, profit and tax income per level. Payback = build cost / profit per level per month, in years (the
# Construction Manager mod's ROI by profit; its tooltip also gives the years by tax income); per (built, unbuilt)
# branch the profit and the tax income per level
BUILD_EFFICIENCY_WIDTH = 70   # one column of production efficiencies (the header button sits over the last one)
BUILD_VALUE_WIDTHS = (55, 55, 60, 60)   # build cost, payback, profit, tax income
BUILD_VALUE_MARGIN = 5                  # left and right of the value columns
BUILD_PAYBACK_INCOME = ("Building.GetIncomeToOwnerPerLevel",
                        "GetBuildingTypeIncomeToOwnerInLocation(BuildingType.Self, Location.Self)")
BUILD_PAYBACK_PROFIT = ("Building.GetProfitPerLevel", "GetBuildingTypeProfitInLocation(BuildingType.Self, Location.Self)")
BUILD_PAYBACK_BASIS = BUILD_PAYBACK_PROFIT
BUILD_PAYBACK_COST = "GetBuildOrExpandBuildingCost(BuildingType.Self, Location.Self)"
BUILD_PAYBACK_TOOLTIP = ("PP_BUILD_PAYBACK_TT_BUILT", "PP_BUILD_PAYBACK_TT_UNBUILT")   # pp_build_panel_l_english.yml
BUILD_COST_SORT_KEY = "cost"   # engine key of the build list (BUILDING_LOCATION_SORT_BY_COST), unused by vanilla
# payback order: the engine sorts only by its own keys, so the header's payback button (global GUI variable) draws
# the list once per payback band, shortest first; inside a band the selected sort holds. Band upper edges in years,
# then one band above the last edge and one for no payback (profit 0 or less). The rows are vanilla's, each built
# only in its band (DataModelRepeatedItem of 1 or 0), so the payback order builds as many rows as the selected sort.
# Every band checks every location each frame (bands x locations; 27 bands of two comparisons each lagged the whole
# game in game, 2026-10-17), so each test is one cost and one profit call (whole years, payback_whole_years) and the
# bands are one year wide up to BUILD_PAYBACK_BANDS[-1], then one top band that also holds the unprofitable rows.
BUILD_PAYBACK_VARIABLE = "pp_build_payback_order"
BUILD_SORT_BUTTONS = 11   # the header's engine sort buttons (vanilla's 10 and cost); each one leaves the payback order
BUILD_PAYBACK_BANDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
# the location view ("Production in <location>"): same columns, slot layout and payback order as the build panel. Its
# rows are vanilla types in production_lateralview.gui (re-declared by CMF), so the mod uses pp_ copies of them.
LOCATION_PRODUCTION = "location_production_lateralview.gui"
PRODUCTION = "production_lateralview.gui"
LOCATION_ROWS_GUI = "shared/pp_location_building_rows.gui"
LOCATION_ROW_TYPES = ("location_filtered_header_with_candidate", "location_filtered_header_no_candidate")
LOCATION_VALUES_UNBUILT = "pp_location_values_unbuilt"
LOCATION_SORT_BUTTONS = 5
# the building window's header row: slots and efficiencies two per column (vanilla 570 wide; six slots need ~750)
BUILDING_VIEW = "building_view.gui"
BUILDING_VIEW_WIDTH = 760
BUILD_PAYBACK_MIN_PROFIT = 0.05   # profit per level per month counted at least this in the band key (no division by 0)
# the mod's internal goods: accounting goods pinned at their price floor that no one trades or consumes (in_game/common/
# goods/pp_goods_*.txt). The market, the goods ledger, the markets ledger's surplus/demand icons and the trade-order
# goods picker skip them; tooltips, building panels and production methods still show them.
INTERNAL_GOODS = ("offset", "logistics", "local_food", "province_food_sales")
INTERNAL_GOODS_TEMPLATE = "pp_hide_internal_goods"
INTERNAL_GOODS_GUI = "shared/pp_internal_goods.gui"
# file -> (datamodel of a goods list, context that gives the row its Goods; "" when the items are Goods)
INTERNAL_GOODS_LISTS: dict[str, tuple[tuple[str, str], ...]] = {
    "panels/market/market_goods.gui": (
        ("SelectedMarketLateralView.GetGoodsMarketEntries", "GoodsMarketEntry.GetGoods"),
        ("SelectedMarketLateralView.GetInRangeGoodsEntries", "GoodsMarketEntry.GetGoods"),
    ),
    "goods_overview.gui": (("GoodsView.GetGoods", "GoodsItem.GetGoods"),),
    "trade_order_lateral_view.gui": (("TradeOrderSelectGood.Parent.GetMarketGoods", ""),),
}
# file -> datamodels of top-five goods icon rows
INTERNAL_GOODS_ICONS: dict[str, tuple[str, ...]] = {
    "markets_overview.gui": ("Market.GetSurplusGoods", "Market.GetHighestDemandGoods"),
}
# file -> datamodels of top-five goods tables (TooltipTableColumn columns over GoodsMarketEntry)
INTERNAL_GOODS_TABLES: dict[str, tuple[str, ...]] = {
    "shared/market_tooltips.gui": ("Market.GetHighestProducedGoods", "Market.GetHighestLocalDemandGoods"),
}
# the goods table column the tables use instead of vanilla's TooltipTableColumn (main_menu_cooltip_types.gui)
GOODS_TABLE_COLUMN = "pp_GoodsMarketTableColumn"
COOLTIP_TYPES = Path("main_menu/gui/shared/main_menu_cooltip_types.gui")
TOP_GOODS = 5


def _months(scope: str) -> str:
    """Stored months of the province: a location-scope script value (CFixedPoint), read on its capital."""
    return f"{scope}.GetCapital.MakeScope.ScriptValue('{MONTHS_VALUE}')"


def _share(scope: str) -> str:
    return f"Divide_CFixedPoint({_months(scope)}, '(CFixedPoint){DIVISOR}')"


def port_food_gauges(text: str, scope: str) -> str:
    """Every vanilla food-capacity reading becomes the share of the stored-food maximum (pie, label, tests)."""
    percent = f"{scope}.GetFoodCapacityPercent"
    rules = (
        # "has any stored food" tests (market view warnings)
        (f"GreaterThan_float(FixedPointToFloat({percent}), '(float)0')", f"GreaterThan_CFixedPoint({_months(scope)}, '(CFixedPoint)0')"),
        # the empty part of the pie
        (f"Subtract_float('(float)100.0', FixedPointToFloat({percent}))", f"Subtract_float('(float)1.0', FixedPointToFloat({_share(scope)}))"),
        # the filled part of the pie
        (f"FixedPointToFloat({percent})", f"FixedPointToFloat({_share(scope)})"),
        # the percentage label (province list column)
        (f"[{percent}|2]%", f"[{_share(scope)}|2%]"),
    )
    for old, new in rules:
        text = text.replace(old, new)
    if "GetFoodCapacityPercent" in text:
        left = sorted({line.strip() for line in text.splitlines() if "GetFoodCapacityPercent" in line})
        raise ValueError("unported food-capacity readings:\n" + "\n".join(left))
    return text


def _block_end(text: str, open_brace: int) -> int:
    depth = 0
    quoted = comment = False
    for i in range(open_brace, len(text)):
        c = text[i]
        if comment:
            comment = c != "\n"
        elif quoted:
            quoted = c != '"'
        elif c == "#":
            comment = True
        elif c == '"':
            quoted = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("unbalanced block")


def _commented_block(text: str, comment: str) -> str:
    """The comment line and the block that follows it, with the comment's indentation."""
    m = re.search(rf"(?m)^[ \t]*# {re.escape(comment)}[^\n]*\n", text)
    if not m:
        raise ValueError(f"mod Europedia: no '# {comment}' block")
    return text[m.start():_block_end(text, text.index("{", m.end()))]


def _once(pattern: str, repl, text: str, what: str = "vanilla Europedia") -> str:
    text, n = re.subn(pattern, repl, text, flags=re.MULTILINE)
    if n != 1:
        raise ValueError(f"{what}: expected 1 match of {pattern!r}, found {n}")
    return text


def port_europedia(vanilla: str, mod: str) -> str:
    """Vanilla encyclopedia plus the Prosper or Perish page: a page button under "All pages", the vanilla page view
    hidden while it is active, and the mod's filter buttons and cards (copied from the current mod file)."""
    active = "GetVariableSystem.HasValue('pp_encyclopedia_active', 'yes')"
    clear = "onclick = \"[GetVariableSystem.Clear('pp_encyclopedia_active')]\""
    page_button = _commented_block(mod, "Prosper or Perish — sibling of scrollbox")
    mod_content = _commented_block(mod, "Mod Content")
    t = vanilla
    # choosing "All pages" or a vanilla page leaves the mod page
    t = _once(r'^([ \t]*)(action_tooltip = \{\n[ \t]*title = "ENCYCLOPEDIA_ALL_PAGES"\n[ \t]*on_action = "\[Encyclopedia\.ViewAllEntries\]"\n[ \t]*\}\n)',
              lambda m: f"{m.group(1)}{m.group(2)}\n{m.group(1)}{clear}\n", t)
    t = _once(r'^([ \t]*)(text = "\[EncyclopediaPage\.GetTitle\]"\n)', lambda m: f"{m.group(1)}{m.group(2)}\n{m.group(1)}{clear}\n", t)
    for page in ("Encyclopedia.GetAllPage", "EncyclopediaPage.Self"):
        old = f'visible = "[ObjectsEqual( Encyclopedia.GetCurrentPage, {page} )]"'
        t = _once(re.escape(old), f'visible = "[And(ObjectsEqual( Encyclopedia.GetCurrentPage, {page} ), Not({active}))]"', t)
    # the mod page button sits between "All pages" and the page list
    t = _once(r'^([ \t]*)(scrollbox = \{\n(?:[ \t]*\n|[ \t]*layoutpolicy_\w+ = expanding\n)*[ \t]*blockoverride "scrollbox_content" \{\n[ \t]*fixedgridbox = \{\n[ \t]*name = "entries")',
              lambda m: page_button + "\n\n" + m.group(1) + m.group(2), t)
    t = _once(r'^([ \t]*)fixedgridbox = \{\n([ \t]*)name = "entries"', r'\1fixedgridbox = {\n\2layoutpolicy_vertical = expanding\n\2name = "entries"', t)
    # style keys without the formatter marker (AGENTS.md; vanilla's commented-out copy too, the test reads the file)
    t = _once(r'default_format = "#yellow_titles"(\n[ \t]*text = "\[EncyclopediaEntry\.GetTitle\]")', r'default_format = "yellow_titles"\1', t)
    t = t.replace('default_format = "#yellow_titles"', 'default_format = "yellow_titles"')
    # the vanilla page view and the mod page are siblings in the "current" column; one is visible at a time
    m = re.search(r'(?m)^([ \t]*)vbox = \{\n[ \t]*name = "current"\n', t)
    if not m:
        raise ValueError('vanilla Europedia: no vbox "current"')
    end = _block_end(t, t.index("{", m.start()))
    body_start = re.compile(r"(?m)^[ \t]*spacing = \d+\n").search(t, m.end(), end)
    if not body_start:
        raise ValueError('vanilla Europedia: no spacing line in vbox "current"')
    close = t.rindex("\n", 0, end - 1) + 1
    ind = m.group(1) + "    "
    wrapper = (f"\n{ind}# Vanilla Content\n{ind}vbox = {{\n{ind}    layoutpolicy_horizontal = expanding\n"
               f"{ind}    layoutpolicy_vertical = expanding\n{ind}    visible = \"[Not({active})]\"\n")
    return (t[:body_start.end()] + wrapper + t[body_start.end():close] + f"{ind}}}\n\n" + mod_content + "\n" + t[close:])


def _indent(text: str, tabs: int) -> str:
    return "".join("\t" * tabs + line if line.strip() else line for line in text.splitlines(keepends=True))


def _slot_columns(ind: str, model: str, item: str, spacing: int) -> str:
    """The items of ``model`` two per column, top-aligned (PP buildings have up to six production-method slots)."""
    columns = (
        (0, f"DataModelFirst({model}, '(int32)2')"),
        (2, f"DataModelFirst(DataModelSkipFirst({model}, '(int32)2'), '(int32)2')"),
        (4, f"DataModelSkipFirst({model}, '(int32)4')"),
    )
    out = []
    for skip, column in columns:
        visible = (f'{ind}\tvisible = "[GreaterThan_int32(GetDataModelSize({model}), \'(int32){skip}\')]"\n'
                   if skip else "")
        out.append(f"{ind}vbox = {{\n{visible}{ind}\tlayoutpolicy_vertical = expanding\n"
                   f"{ind}\tvbox = {{\n{ind}\t\tspacing = {spacing}\n{ind}\t\tdatamodel = \"[{column}]\"\n"
                   f"{ind}\t\titem = {{\n{_indent(item, len(ind) + 3)}{ind}\t\t}}\n{ind}\t}}\n"
                   f"{ind}\texpand = {{}}\n{ind}}}\n")
    return "".join(out)


def _item_body(block: str) -> str:
    """The widget inside a block's ``item = { ... }``, without its indentation."""
    m = re.search(r"(?m)^([ \t]*)item = \{\n", block)
    if not m:
        raise ValueError("vanilla build panel: no item block")
    body = block[m.end():_block_end(block, block.index("{", m.start())) - 1]
    body = body[:body.rfind("\n") + 1]   # without the closing brace's indentation
    depth = len(m.group(1)) + 1
    return "".join(re.sub(rf"^\t{{0,{depth}}}", "", line) for line in body.splitlines(keepends=True))


def port_build_location(vanilla: str) -> str:
    """Vanilla build panel ("Building <type>"), laid out for PP's buildings: up to 22 inputs in one slot (Cookshop)
    and up to six production-method slots (fishing village). The panel is wider, the goods rows of the slot filter
    wrap their inputs onto more lines and grow with them, and each location row shows its slot circles and production
    efficiencies two per column, so they stay inside the row, then one value per column: build cost, payback time,
    profit and tax income per level (``_value_columns``). The header's payback button lists the rows in payback order
    (``_payback_order``). Everything else is vanilla."""
    what = "vanilla build panel"
    t = vanilla
    # the panel: wider than the 570 of the left lateral views; the market picker opens beside it
    t = _once(r'^(lateralview = \{\n\tname = "build_location_lateralview"\n)',
              rf"\1\tsize = {{ {BUILD_PANEL_WIDTH} 100% }} # PP: wider than the vanilla left panel (570)\n", t, what)
    t = _once(r"(header_title = \{\n(?:[ \t]*\w+ = \w+\n)*[ \t]*)maximumsize = \{ 420 -1 \}",
              rf"\1maximumsize = {{ {BUILD_PANEL_WIDTH - 150} -1 }}", t, what)
    # slot filter rows: inputs wrap after INPUTS_PER_LINE goods; the row grows to its content (35 for one line)
    t = _once(r'^([ \t]*)(hbox = \{\n[ \t]*using = layoutpolicy_expanding\n[ \t]*spacing = 5\n)([ \t]*)margin = \{9 0\}\n'
              r'(?=[ \t]*\n[ \t]*icon = \{\n[ \t]*visible = "\[BuildInLocationLateralView\.HasEstate\]")',
              r"\1\2\3margin = {9 5}\n\3minimumsize = { -1 35 }\n"
              r"\3set_parent_dimension_to_minimum = height # PP: the row grows when its inputs wrap\n", t, what)
    t = _once(r"^([ \t]*)hbox = \{ # HIDES PRICES IF NUMBER OF INPUTS > 5\n([ \t]*)spacing = 4\n",
              rf"\1dynamicgridbox = {{ # HIDES PRICES IF NUMBER OF INPUTS > 5 (PP: {BUILD_INPUTS_PER_LINE} per line; "
              rf"a dynamicgridbox takes no spacing)\n\2flipdirection = yes\n\2datamodel_wrap = {BUILD_INPUTS_PER_LINE}\n",
              t, what)
    # location rows: a wider location card (long names), slot circles and efficiencies two per column
    t = _once(r"(card_header_button_04 = \{\n[ \t]*)size = \{ 150 48 \}", rf"\1size = {{ {BUILD_LOCATION_CARD_WIDTH} 48 }}",
              t, what)
    circles = re.compile(r'(?m)^([ \t]*)vbox = \{ ?\n[ \t]*visible = "\[LocationToBuildItem\.HasConstructedBuildingLevels\]"\n'
                         r"[ \t]*spacing = 1\n[ \t]*datamodel = \"\[LocationToBuildItem\.GetBuildingSlots\]\"\n")
    m = circles.search(t)
    if not m or circles.search(t, m.end()):
        raise ValueError(f"{what}: expected 1 slot circle column")
    end = _block_end(t, t.index("{", m.start()))
    ind = m.group(1)
    grid = (f"{ind}hbox = {{ # PP: production-method slots, two per column\n"
            f"{ind}\tvisible = \"[LocationToBuildItem.HasConstructedBuildingLevels]\"\n{ind}\tspacing = 2\n"
            + _slot_columns(ind + "\t", "LocationToBuildItem.GetBuildingSlots", _item_body(t[m.start():end]), 1)
            + f"{ind}}}")
    t = t[:m.start()] + grid + t[end:]
    t = _once(r"^([ \t]*)widget = \{ #efficiency\n([ \t]*)size = \{ 70 -1 \}\n",
              r"\1vbox = { #efficiency (PP: a box, so it widens with the slot columns)\n\2minimumsize = { 70 -1 }\n", t, what)
    built = re.compile(r"(?m)^([ \t]*)vbox = \{ #built\n[ \t]*margin_top = 2\n")
    m = built.search(t)
    if not m or built.search(t, m.end()):
        raise ValueError(f"{what}: expected 1 built efficiency column")
    end = _block_end(t, t.index("{", m.start()))
    block = t[m.start():end]
    if 'datamodel = "[Building.GetProductionMethods]"' not in block:
        raise ValueError(f"{what}: the efficiency column no longer lists Building.GetProductionMethods")
    visible = re.search(r"(?m)^[ \t]*visible = (\"[^\n]*\")\n", block).group(1)
    ind = m.group(1)
    grid = (f"{ind}hbox = {{ #built (PP: two production methods per column)\n{ind}\tmargin_top = 2\n"
            f"{ind}\tvisible = {visible}\n{ind}\tlayoutpolicy_horizontal = expanding\n{ind}\tspacing = 6\n"
            f"{ind}\texpand = {{}}\n"
            + _slot_columns(ind + "\t", "Building.GetProductionMethods", _item_body(block), 6)
            + f"{ind}}}")
    t = t[:m.start()] + grid + t[end:]
    # sort buttons: the value columns' buttons sit over their columns at the right of the row
    t = _once(r'^([ \t]*)(sort_by_key_button = \{\n[ \t]*name = "production_efficiency"\n)',
              r"\1expand = {} # PP: the value buttons sit over their columns\n\n\1\2", t, what)
    t = _once(r'(sort_by_key_button = \{\n[ \t]*name = "production_efficiency"\n[ \t]*layoutpolicy_vertical = expanding\n'
              r"[ \t]*)size = \{ 100 -1 \}", rf"\1size = {{ {BUILD_EFFICIENCY_WIDTH} -1 }}", t, what)
    cost, pay, profit, tax = BUILD_VALUE_WIDTHS
    for key, width in (("profit", profit), ("income", tax + BUILD_VALUE_MARGIN)):
        t = _once(rf'(sort_by_key_button = \{{\n[ \t]*name = "{key}"\n[ \t]*layoutpolicy_vertical = expanding\n[ \t]*)'
                  r"size = \{ 40 -1 \}", rf"\g<1>size = {{ {width} -1 }}", t, what)
    cost_button = _block("sort_by_key_button = { # PP: the engine's cost key (vanilla has no button for it)", [
        f'name = "{BUILD_COST_SORT_KEY}"', "layoutpolicy_vertical = expanding", f"size = {{ {cost + BUILD_VALUE_MARGIN} -1 }}",
        'visible = "[BuildInLocationLateralView.GetBuildingType.IsProducing]"',
        _block('blockoverride "sort_by_key_button_texture" {', ['texture = "gfx/interface/icons/sort/cost.dds"'])])
    t = _once(r'^([ \t]*)(sort_by_key_button = \{\n[ \t]*name = "profit"\n)',
              lambda h: (_indent(cost_button + "\n" + _payback_toggle(pay), len(h.group(1))) + "\n" + h.group(0)),
              t, what)
    t = _once(r'(sort_by_key_button = \{\n[ \t]*name = "number_building"\n)([ \t]*)using = layoutpolicy_expanding\n',
              r"\1\2layoutpolicy_vertical = expanding\n\2size = { 125 -1 }\n", t, what)
    clear = f"onclick = \"[GetVariableSystem.Clear('{BUILD_PAYBACK_VARIABLE}')]\" # PP: a sort leaves the payback order"
    t, n = re.subn(r'(?m)^([ \t]*)(sort_by_key_button = \{[^\n]*\n)([ \t]*)(name = "\w+"\n)',
                   lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}{m.group(3)}{clear}\n", t)
    if n != BUILD_SORT_BUTTONS:
        raise ValueError(f"{what}: expected {BUILD_SORT_BUTTONS} sort buttons, found {n}")
    t = _constructions_text(t, what)
    t = _value_columns(t, what)
    t = _payback_order(t, what)
    # the market picker: vanilla's select_menu_left with its offset moved to the panel's new right edge
    m = re.search(r"(?m)^select_menu_left = \{\n", t)
    if not m:
        raise ValueError(f"{what}: no market picker")
    end = _block_end(t, t.index("{", m.start()))
    body = t[m.end():end - 1]
    body = _once(r'^\tdatacontext = "\[GetQuickVisibleMarkets\(Player\.Self\)\]"\n', "", body, what)
    setup = re.search(r'(?m)^\tblockoverride "menu_setup" \{\n[ \t]*name = "build_location_select_market"\n\t\}\n\n?', body)
    if not setup:
        raise ValueError(f"{what}: the market picker has no menu_setup name")
    body = body[:setup.start()] + body[setup.end():]
    x = BUILD_PANEL_WIDTH
    picker = ("window = { # PP: vanilla select_menu_left (select_menu.gui), opened beside the wider build panel\n"
              '\tname = "build_location_select_market"\n\tdatacontext = "[GetQuickVisibleMarkets(Player.Self)]"\n'
              "\tmovable = no\n\tvisible_at_creation = no\n\talwaystransparent = no\n\tallow_outside = yes\n"
              f"\tlayer = sidemenu\n\tparentanchor = left\n\tposition = {{ {x} 180 }}\n\n"
              f"\tstate = {{\n\t\tname = _show\n\t\tduration = 0.133\n\t\tposition_x = {x}\n\t\talpha = 1\n\t}}\n"
              f"\tstate = {{\n\t\tname = _hide\n\t\tduration = 0.133\n\t\tposition_x = {x - 45}\n\t\talpha = 0\n\t}}\n\n"
              "\tusing = bg_sidemenu\n\n\tselect_menu_layout = {\n" + _indent(body.strip("\n") + "\n", 1) + "\t}\n}")
    return t[:m.start()] + picker + t[end:]


def payback_years(cost: str, income: str) -> str:
    return f"Divide_CFixedPoint(Divide_CFixedPoint({cost}, {income}), '(CFixedPoint)12')"


ZERO = "'(CFixedPoint)0'"
BUILT = "LocationToBuildItem.HasConstructedBuildingLevels"
ROW_CONTEXTS = ('datacontext = "[LocationToBuildItem.GetLocation]"', 'datacontext = "[LocationToBuildItem.GetBuilding]"',
                'datacontext = "[LocationToBuildItem.GetBuildingType]"')


def _block(opening: str, lines: list[str]) -> str:
    """``opening`` (e.g. ``vbox = { # comment`` or ``template x {``) with the lines one tab in and a closing brace."""
    return f"{opening}\n" + "".join(_indent(line.rstrip("\n") + "\n", 1) for line in lines) + "}\n"


def _all_of(terms: list[str]) -> str:
    if len(terms) == 1:
        return terms[0]
    half = (len(terms) + 1) // 2
    return f"And({_all_of(terms[:half])}, {_all_of(terms[half:])})"


def _dedent(text: str, tabs: int) -> str:
    return "".join(re.sub(rf"^\t{{0,{tabs}}}", "", line) for line in text.splitlines(keepends=True))


def _cut(t: str, pattern: str, what: str) -> tuple[int, int, str]:
    """Start, end and indentation of the one block whose opening line matches ``pattern`` (group 1: indentation)."""
    found = list(re.finditer(pattern, t, flags=re.MULTILINE))
    if len(found) != 1:
        raise ValueError(f"{what}: expected 1 match of {pattern!r}, found {len(found)}")
    m = found[0]
    return m.start(), _block_end(t, t.index("{", m.start())), m.group(1)


def _payback_mode() -> str:
    return (f"And(GetVariableSystem.Exists('{BUILD_PAYBACK_VARIABLE}'), "
            "BuildInLocationLateralView.GetBuildingType.IsProducing)")


def _constructions_text(t: str, what: str) -> str:
    """The location card's construction count read the first construction for its tooltip with datacontext_from_model,
    which logs an error for every row without one (error.log, 2026-10-17): the text is built only with a construction,
    as vanilla's RGO panel does."""
    start, end, ind = _cut(t, r'^([ \t]*)text_single = \{\n[ \t]*datacontext = "\[LocationToBuildItem\.GetLocation\]"\n'
                              r'[ \t]*visible = "\[DataModelHasItems\(Location\.GetCivilConstructions\)\]"\n', what)
    block = t[start:end]
    if "datacontext_from_model" not in block or "using = Construction_tooltip" not in block:
        raise ValueError(f"{what}: the construction count no longer reads the first construction")
    raw = re.search(r'(?m)^[ \t]*(raw_text = "[^\n]*")\n', block).group(1)
    text = _block("hbox = { # PP: the construction count, built only with a construction (its tooltip reads the first)", [
        'datacontext = "[LocationToBuildItem.GetLocation]"',
        "datamodel = \"[DataModelFirst(Location.GetCivilConstructions, '(int32)1')]\"",
        _block("item = {", [_block("text_single = {", ["autoresize = yes", "using = Font_Size_Very_Small", raw,
                                                       _block("tooltipwidget = {", ["using = Construction_tooltip"])])])])
    return t[:start] + _indent(text, len(ind)).rstrip("\n") + t[end:]


def _value_text(raw: str, visible: str = "", tooltip: str = "", highlight: str = "") -> str:
    lines = [f'visible = "[{visible}]"'] if visible else []
    lines += ["size = { 100% 18 }", "parentanchor = vcenter", "align = nobaseline|right", "autoresize = no",
              "fontsize = 14", f'raw_text = "{raw}"']
    if tooltip:
        lines.append(tooltip)
    if highlight:
        lines.append(_block("sort_by_highlight = {", ["size = { 105% 100% }", f'name = "{highlight}"']))
    return _block("text_single = {", lines)


def _value_column(comment: str, width: int, built: list[str], unbuilt: list[str], unbuilt_only: bool = False) -> str:
    """One value column: the built and the unbuilt branch of a LocationToBuildItem row, or (unbuilt_only) the unbuilt
    texts alone for a row that has only a building type and a location."""
    if unbuilt_only:
        return _block(f"widget = {{ # {comment}", [f"size = {{ {width} -1 }}", "layoutpolicy_vertical = expanding",
                                                    *unbuilt])
    show = "LocationToBuildItem.ShowProfit"
    return _block(f"widget = {{ # {comment}", [
        f"size = {{ {width} -1 }}", "layoutpolicy_vertical = expanding",
        _block("widget = { # built", [f'visible = "[And({show}, {BUILT})]"', "size = { 100% 100% }", *built]),
        _block("widget = { # unbuilt", [f'visible = "[And({show}, Not({BUILT}))]"', "size = { 100% 100% }", *unbuilt]),
    ])


def _values_template(unbuilt_only: bool = False) -> str:
    """Build cost, payback, profit and tax income per level, one value per column: template pp_build_location_values
    for a LocationToBuildItem row (build panel, the location view's built rows), or LOCATION_VALUES_UNBUILT for the
    location view's unbuilt rows (BuildingType and Location in context)."""
    cost = BUILD_PAYBACK_COST
    cost_width, pay, profit, tax = BUILD_VALUE_WIDTHS

    def payback(basis: str, tooltip: str) -> list[str]:
        # no cost guard: the cost call is the slow one (in game 2026-10-17), and a free level shows 0.0
        return [_value_text(f"[{payback_years(cost, basis)}|1]@time!", f"GreaterThan_CFixedPoint({basis}, {ZERO})",
                            f'tooltip = "{tooltip}"'),
                _value_text("#L -#!", f"Not(GreaterThan_CFixedPoint({basis}, {ZERO}))")]

    def build_cost(tooltip: str) -> list[str]:
        return [_value_text(f"[{cost}|0]@gold!", "", f'tooltip = "{tooltip}"', BUILD_COST_SORT_KEY)]

    built_tt = _block("tooltipwidget = {", ["using = BuildingProfit_Tooltip"])
    unbuilt_tt = _block("tooltipwidget = {", ["using = BuildingTypeProfit_Tooltip"])
    subsidized = f"And(LessThanOrEqualTo_CFixedPoint(Building.GetProfit, {ZERO}), Building.IsSubsidized)"
    (inc_b, inc_u), (prof_b, prof_u) = BUILD_PAYBACK_INCOME, BUILD_PAYBACK_PROFIT
    u = unbuilt_only
    columns = [
        _value_column("build cost of the next level", cost_width,
                      build_cost(BUILD_PAYBACK_TOOLTIP[0]), build_cost(BUILD_PAYBACK_TOOLTIP[1]), u),
        _value_column("payback: years of profit per build cost", pay,
                      payback(BUILD_PAYBACK_BASIS[0], BUILD_PAYBACK_TOOLTIP[0]),
                      payback(BUILD_PAYBACK_BASIS[1], BUILD_PAYBACK_TOOLTIP[1]), u),
        _value_column("profit per level", profit,
                      [_value_text(f"[{prof_b}|+=2]@wealth!", f"Not({subsidized})", built_tt, "profit"),
                       _value_text(f"#L [{prof_b}|2]#!@wealth!", subsidized, built_tt, "profit")],
                      [_value_text(f"[{prof_u}|+=2]@wealth!", "", unbuilt_tt, "profit")], u),
        _value_column("tax income per level", tax,
                      [_value_text(f"[{inc_b}|+=2]@income!", "", built_tt, "income")],
                      [_value_text(f"[{inc_u}|+=2]@income!", "", unbuilt_tt, "income")], u),
    ]
    if unbuilt_only:
        return _block(f"template {LOCATION_VALUES_UNBUILT} {{ # PP: the value columns of an unbuilt location-view row", [
            'visible = "[BuildingType.IsProducing]"', "layoutpolicy_vertical = expanding",
            f"margin = {{ {BUILD_VALUE_MARGIN} 0 }}", *columns])
    return _block("template pp_build_location_values { # PP: the value columns of a location row (an hbox)", [
        'visible = "[LocationToBuildItem.GetBuildingType.IsProducing]"', "layoutpolicy_vertical = expanding",
        f"margin = {{ {BUILD_VALUE_MARGIN} 0 }}", *ROW_CONTEXTS, *columns])


def _value_columns(t: str, what: str) -> str:
    """The vanilla profit cell (profit over tax income) becomes the value columns."""
    start, end, ind = _cut(t, r'^([ \t]*)hbox = \{\n[ \t]*visible = "\[LocationToBuildItem\.GetBuildingType\.IsProducing\]"\n'
                              r"[ \t]*margin = \{ 5 0 \}\n[ \t]*widget = \{ #profit\n", what)
    t = t[:start] + f"{ind}hbox = {{ using = pp_build_location_values }} # PP: build cost, payback, profit, tax income" + t[end:]
    return t.rstrip("\n") + "\n\n" + _values_template()


def _payback_toggle(width: int) -> str:
    on = f"GetVariableSystem.Exists('{BUILD_PAYBACK_VARIABLE}')"
    return _block("button = { # PP: payback order (no engine sort key: the list is drawn in payback bands)", [
        'name = "pp_payback_order"', "layoutpolicy_vertical = expanding", f"size = {{ {width} -1 }}",
        'visible = "[BuildInLocationLateralView.GetBuildingType.IsProducing]"', f'down = "[{on}]"',
        _block("background = {", [f'visible = "[{on}]"', 'texture = "gfx/interface/component_masks/mask_fade_vertical_up.dds"',
                                  "texture_density = 2", "alpha = 0.4",
                                  _block("modify_texture = {", ["using = color_sortby_off", "blend_mode = multiply"])]),
        f"onclick = \"[GetVariableSystem.Toggle('{BUILD_PAYBACK_VARIABLE}')]\"", 'tooltip = "PP_BUILD_PAYBACK_ORDER_TT"',
        _block("icon = {", ["size = { 20 20 }", "parentanchor = center", 'texture = "gfx/interface/icons/sort/time.dds"']),
    ])


def payback_bands() -> list[tuple[int, int | None]]:
    """(lower, upper) whole years of each band, shortest first; upper None = no upper edge (and no profit)."""
    edges = (0, *BUILD_PAYBACK_BANDS)
    return [*zip(edges, edges[1:]), (BUILD_PAYBACK_BANDS[-1], None)]


def payback_whole_years(profit: str) -> str:
    """Whole years of profit per build cost, from one cost and one profit call (the band tests run every frame for
    every band and location). Profit at or below BUILD_PAYBACK_MIN_PROFIT counts as that, so no profit lands in the
    top band without a division by zero."""
    floor = f"Max_CFixedPoint({profit}, '(CFixedPoint){BUILD_PAYBACK_MIN_PROFIT}')"
    return f"FixedPointToInt(Divide_CFixedPoint(Divide_CFixedPoint({BUILD_PAYBACK_COST}, '(CFixedPoint)12'), {floor}))"


def payback_band_name() -> str:
    """GUI variable that holds a location's recorded payback band for the building type of the panel."""
    return "Concatenate('pp_pb_', Concatenate(BuildingType.GetName, Location.GetKey))"


def _band_value(profit: str) -> str:
    """The band of a location as text: its whole years of payback, the top band for longer or no profit. Evaluated
    only when the location is recorded (the cost call is too slow for every frame)."""
    key = payback_whole_years(profit)
    top = BUILD_PAYBACK_BANDS[-1]
    value = f"'{top}'"
    for k in reversed(range(top)):
        value = f"Select_CString(EqualTo_int32({key}, '(int32){k}'), '{k}', {value})"
    return value


def _column(lines: list[str], comment: str = "") -> str:
    """A vertical flowcontainer: sizes to its content and skips hidden children (a box stretched to the panel's height
    and spread the spare height between the rows; with an expand its layout did not converge, error.log 2026-10-17)."""
    return _block("flowcontainer = {" + (f" # {comment}" if comment else ""),
                  ["direction = vertical", "ignoreinvisible = yes", *lines])


def _recorder(items: str) -> str:
    """Each location records its band once (a widget's _show state writes the GUI variable): when the payback order
    opens and whenever its construction count changes (one of two recorders turns visible), so a level queued in the
    panel moves its row. The bands then only read the variables."""
    constructions = "IsOdd_int32(GetDataModelSize(Location.GetCivilConstructions))"
    name = payback_band_name()
    mode = _payback_mode()

    def record(built: str, odd: str, profit: str) -> str:
        # _show runs when the widget's own visible turns true after it was created hidden (visible_at_creation = no,
        # as in the PP Observer Auto Pause mod), so it holds the payback switch too
        return _block("widget = {", ["visible_at_creation = no", f'visible = "[And({mode}, And({built}, {odd}))]"',
                                     "size = { 0 0 }",
                                     _block("state = {", ["name = _show",
                                                          f'on_start = "[GetVariableSystem.Set({name}, {_band_value(profit)})]"'])])
    sides = [record(b, o, p) for b, p in ((BUILT, BUILD_PAYBACK_BASIS[0]), (f"Not({BUILT})", BUILD_PAYBACK_BASIS[1]))
             for o in (constructions, f"Not({constructions})")]
    return _column([f'datamodel = "[{items}]"',
                    _block("item = {", [_block("widget = {", ["size = { 0 0 }", *ROW_CONTEXTS, *sides])])],
                   "records each location's payback band (the cost call is too slow for every frame)")


def _band(comment: str, items: str, row: str, shown: str) -> str:
    """The list's items once more; each builds its row (the vanilla row) only when its recorded band is this one, so
    every row is built once across all bands."""
    return _column([f'datamodel = "[{items}]"', _block("item = {", [_column([
        *ROW_CONTEXTS, f"datamodel = \"[DataModelRepeatedItem(Select_int32({shown}, '(int32)1', '(int32)0'))]\"",
        _block("item = {", [row])])])], comment)


def _payback_order(t: str, what: str) -> str:
    """The list area holds two lists of the vanilla rows over the same items: vanilla's grid (vanilla's binding) in the
    selected sort or, with the header's payback button on, the payback bands. The hidden one is not updated. Both sit
    in vertical flowcontainers, which size to their content; the rows are BUILD_ROW_WIDTH wide (a flowcontainer has no
    width of its own for vanilla's 100%). The bands read each location's recorded band (_recorder); a location not
    recorded yet goes last."""
    start, end, ind = _cut(t, r'^([ \t]*)blockoverride "scroll_list_content" \{\n', what)
    block = t[start:end]
    items = "BuildInLocationLateralView.GetItems"
    for needed in (f'datamodel = "[{items}]"', "addcolumn = 100%", "addrow = 60"):
        if needed not in block:
            raise ValueError(f"{what}: the location list no longer has {needed}")
    w = BUILD_ROW_WIDTH
    row = _once(r"^widget = \{\n\tsize = \{ 100% 60 \}\n", f"widget = {{\n\tsize = {{ {w} 60 }}\n", _item_body(block), what)
    mode = _payback_mode()
    name = payback_band_name()
    bands = [_band(f"payback {low} to {high} years" if high else f"payback {low} years or more, or no profit", items, row,
                   f"GetVariableSystem.HasValue({name}, '{low}')")
             for low, high in payback_bands()]
    bands.append(_band("not recorded yet", items, row, f"Not(GetVariableSystem.Exists({name}))"))
    grid = _block("fixedgridbox = { # the selected sort: vanilla's grid", [
        f'visible = "[Not({mode})]"', f"addcolumn = {w}", "addrow = 60", f'datamodel = "[{items}]"',
        _block("item = {", [row])])
    layout = _block('blockoverride "scroll_list_layout" { # PP: the selected sort or the payback order', [
        _column(["position = { 0 2 }", grid,
                 _column([f'visible = "[{mode}]"', _recorder(items), *bands],
                         "payback order: shortest first, the last sort inside each band")])])
    return t[:start] + _indent(layout, len(ind)).rstrip("\n") + t[end:]


def _row_recorder(sides: list[tuple[str, str]], contexts: list[str]) -> str:
    """Records a location-view row's payback band (same GUI variable as the build panel): one recorder per (condition,
    profit) and construction-count parity, created hidden, so _show runs when the row is created and when the
    location's construction count changes."""
    constructions = "IsOdd_int32(GetDataModelSize(Location.GetCivilConstructions))"
    name = payback_band_name()
    widgets = []
    for cond, profit in sides:
        for odd in (constructions, f"Not({constructions})"):
            widgets.append(_block("widget = {", [
                "visible_at_creation = no", f'visible = "[{_all_of([c for c in (cond, odd) if c])}]"', "size = { 0 0 }",
                _block("state = {", ["name = _show",
                                     f'on_start = "[GetVariableSystem.Set({name}, {_band_value(profit)})]"'])]))
    return _block("widget = { # PP: records this row's payback band (read by the payback order)",
                  ["size = { 0 0 }", "ignore_layout = yes", *contexts, *widgets])


def _location_row_with_candidate(t: str, what: str) -> str:
    """The location view's built row: slot circles and production efficiencies two per column (vanilla stacks them out
    of the row), the value columns of the build panel (the candidate's LocationToBuildItem) in place of profit over
    tax income, upkeep kept for buildings that produce nothing, and the band recorder."""
    start, end, ind = _cut(t, r'^([ \t]*)vbox = \{\n[ \t]*datacontext = "\[BuildingCandidate\.GetLocationToBuildItem\]"\n'
                              r'[ \t]*visible = "\[LocationToBuildItem\.HasConstructedBuildingLevels\]"\n[ \t]*spacing = 1\n'
                              r'[ \t]*datamodel = "\[LocationToBuildItem\.GetBuildingSlots\]"\n', what)
    grid = (f"{ind}hbox = {{ # PP: production-method slots, two per column\n"
            f"{ind}\tdatacontext = \"[BuildingCandidate.GetLocationToBuildItem]\"\n"
            f"{ind}\tvisible = \"[LocationToBuildItem.HasConstructedBuildingLevels]\"\n{ind}\tspacing = 2\n"
            + _slot_columns(ind + "\t", "LocationToBuildItem.GetBuildingSlots", _item_body(t[start:end]), 1)
            + f"{ind}}}")
    t = t[:start] + grid + t[end:]
    start, end, ind = _cut(t, r"^([ \t]*)widget = \{ #efficiency\n[ \t]*size = \{ 70 -1 \}\n", what)
    block = t[start:end]
    inner = re.search(r'(?m)^([ \t]*)vbox = \{ ?\n[ \t]*visible = "\[Building\.IsProducing\]"\n', block)
    if not inner or 'datamodel = "[Building.GetProductionMethods]"' not in block:
        raise ValueError(f"{what}: the built row's efficiency no longer lists Building.GetProductionMethods")
    methods = block[inner.start():_block_end(block, block.index("{", inner.start()))]
    grid = (f"{ind}vbox = {{ #efficiency (PP: two production methods per column)\n{ind}\tminimumsize = {{ 70 -1 }}\n"
            f"{ind}\tlayoutpolicy_vertical = expanding\n{ind}\thbox = {{\n{ind}\t\tvisible = \"[Building.IsProducing]\"\n"
            f"{ind}\t\tmargin_top = 2\n{ind}\t\tspacing = 6\n{ind}\t\texpand = {{}}\n"
            + _slot_columns(ind + "\t\t", "Building.GetProductionMethods", _item_body(methods), 6)
            + f"{ind}\t}}\n{ind}\texpand = {{}}\n{ind}}}")
    t = t[:start] + grid + t[end:]
    start, end, ind = _cut(t, r"^([ \t]*)widget = \{ # profit/income/upkeep\n", what)
    block = t[start:end]
    upkeep = re.search(r"(?m)^([ \t]*)hbox = \{ #upkeep\n", block)
    if not upkeep:
        raise ValueError(f"{what}: the built row has no upkeep cell")
    upkeep_text = _dedent(block[upkeep.start():_block_end(block, block.index("{", upkeep.start()))], len(upkeep.group(1)))
    cell = _block("hbox = { # PP: build cost, payback, profit, tax income; upkeep for buildings that produce nothing", [
        "layoutpolicy_vertical = expanding",
        "hbox = { datacontext = \"[BuildingCandidate.GetLocationToBuildItem]\" using = pp_build_location_values }",
        _block("widget = {", ['visible = "[Not(BuildingItem.GetBuildingType.IsProducing)]"', "size = { 60 36 }",
                              upkeep_text])])
    t = t[:start] + _indent(cell, len(ind)).rstrip("\n") + t[end:]
    anchor = re.search(r'(?m)^([ \t]*)datacontext = "\[Building\.GetLocation\]"\n', t)
    if not anchor:
        raise ValueError(f"{what}: the built row sets no Location")
    recorder = _row_recorder([(BUILT, BUILD_PAYBACK_BASIS[0]), (f"Not({BUILT})", BUILD_PAYBACK_BASIS[1])],
                             ['datacontext = "[BuildingCandidate.GetLocationToBuildItem]"'])
    return t[:anchor.end()] + "\n" + _indent(recorder, len(anchor.group(1))) + t[anchor.end():]


def _location_row_no_candidate(t: str, what: str) -> str:
    """The location view's unbuilt row: the value columns from the building type and the location, and the band
    recorder."""
    start, end, ind = _cut(t, r"^([ \t]*)widget = \{ #profit / income\n", what)
    cell = (f"{ind}hbox = {{ using = {LOCATION_VALUES_UNBUILT} }} # PP: build cost, payback, profit, tax income\n\n"
            + _indent(_row_recorder([("", BUILD_PAYBACK_BASIS[1])], []), len(ind)).rstrip("\n"))
    return t[:start] + cell + t[end:]


def port_location_rows(production: str) -> str:
    """The location view's two building rows (vanilla types in production_lateralview.gui, which CMF re-declares) as
    pp_ copies with the build panel's layout, plus the unbuilt rows' value columns template."""
    what = "vanilla location view rows"
    out = []
    for name, port in zip(LOCATION_ROW_TYPES, (_location_row_with_candidate, _location_row_no_candidate)):
        m = re.search(rf"(?m)^\ttype {name} = hbox \{{\n", production)
        if not m:
            raise ValueError(f"{what}: no type {name}")
        block = production[m.start():_block_end(production, production.index("{", m.start()))]
        block = block.replace(f"type {name} = hbox", f"type pp_{name} = hbox", 1)
        out.append(port(_dedent(block, 1), f"{what} ({name})"))
    return ("# Generated by tools/port_vanilla_gui.py (port_location_rows): the location view's building rows with the\n"
            "# build panel's layout (slots and efficiencies two per column, build cost, payback, profit, tax income) and\n"
            "# the payback band recorder. pp_ copies: CMF re-declares the vanilla types.\n"
            f"types PPLocationBuildingRows {{\n{_indent(''.join(b.rstrip() + chr(10) + chr(10) for b in out).rstrip() + chr(10), 1)}}}\n\n"
            + _values_template(unbuilt_only=True))


def port_building_view(t: str) -> str:
    """The building window's header row: slot circles and production efficiencies two per column. Vanilla stacks them,
    so a three-slot PP building overflows the 50-high row and squeezes its checkbox column (Jan, 2026-10-17: the
    auto-expand box could not be clicked on a Tailors' Guild). The window is wider to hold the extra columns."""
    what = "vanilla building view"
    w = BUILDING_VIEW_WIDTH
    t = _once(r'^(lateralview = \{\n\tname = "building_view"\n)',
              rf"\1\tsize = {{ {w} 100% }} # PP: wider than the vanilla left panel (570) for the slot columns\n", t, what)
    t = _once(r'(text = "\[BuildingView\.GetTitle\]"\n[ \t]*default_format = "#yellow_titles"\n[ \t]*)maximumsize = \{ 420 -1 \}',
              rf"\1maximumsize = {{ {w - 150} -1 }}", t, what)
    start, end, ind = _cut(t, r'^([ \t]*)vbox = \{\n[ \t]*datacontext = "\[BuildingView\.GetLocationToBuildItem\]"\n'
                              r'[ \t]*(visible = "[^\n]*")\n[ \t]*spacing = 1\n'
                              r'[ \t]*datamodel = "\[LocationToBuildItem\.GetBuildingSlots\]"\n', what)
    visible = re.search(r'(?m)^[ \t]*(visible = "[^\n]*")\n', t[start:end]).group(1)
    grid = (f"{ind}hbox = {{ # PP: production-method slots, two per column\n"
            f"{ind}\tdatacontext = \"[BuildingView.GetLocationToBuildItem]\"\n{ind}\t{visible}\n{ind}\tspacing = 2\n"
            + _slot_columns(ind + "\t", "LocationToBuildItem.GetBuildingSlots", _item_body(t[start:end]), 1)
            + f"{ind}}}")
    t = t[:start] + grid + t[end:]
    start, end, ind = _cut(t, r"^([ \t]*)widget = \{\n[ \t]*size = \{ 70 -1 \}\n[ \t]*layoutpolicy_vertical = expanding\n"
                              r"[ \t]*vbox = \{\n", what)
    block = t[start:end]
    inner = re.search(r'(?m)^([ \t]*)vbox = \{ ?\n[ \t]*visible = "\[Building\.IsProducing\]"\n', block)
    if not inner or 'datamodel = "[Building.GetProductionMethods]"' not in block:
        raise ValueError(f"{what}: the header's efficiency no longer lists Building.GetProductionMethods")
    methods = block[inner.start():_block_end(block, block.index("{", inner.start()))]
    grid = (f"{ind}vbox = {{ # PP: production efficiencies, two per column\n{ind}\tminimumsize = {{ 70 -1 }}\n"
            f"{ind}\tlayoutpolicy_vertical = expanding\n{ind}\thbox = {{\n{ind}\t\tvisible = \"[Building.IsProducing]\"\n"
            f"{ind}\t\tmargin_top = 2\n{ind}\t\tspacing = 6\n{ind}\t\texpand = {{}}\n"
            + _slot_columns(ind + "\t\t", "Building.GetProductionMethods", _item_body(methods), 6)
            + f"{ind}\t}}\n{ind}\texpand = {{}}\n{ind}}}")
    return t[:start] + grid + t[end:]


def port_location_production(t: str) -> str:
    """The location view (after its food gauges): wider, the pp_ rows, the header's value columns (build cost label,
    payback button; every sort leaves the payback order) and the list as vanilla's grid or the payback bands."""
    what = "vanilla location view"
    w = BUILD_PANEL_WIDTH
    t = _once(r'^(lateralview = \{\n\tname = "location_production_lateralview"\n)',
              rf"\1\tsize = {{ {w} 100% }} # PP: wider than the vanilla left panel (570), like the build panel\n", t, what)
    t = _once(r"(header_title = \{\n(?:[ \t]*\w+ = \w+\n)*[ \t]*)maximumsize = \{ 415 -1 \}",
              rf"\1maximumsize = {{ {w - 150} -1 }}", t, what)
    mode = f"GetVariableSystem.Exists('{BUILD_PAYBACK_VARIABLE}')"
    clear = f"onclick = \"[GetVariableSystem.Clear('{BUILD_PAYBACK_VARIABLE}')]\" # PP: a sort leaves the payback order"
    t, n = re.subn(r"(?m)^([ \t]*)(sort_by_key_button = \{\n)", lambda m: f"{m.group(1)}{m.group(2)}{m.group(1)}\t{clear}\n", t)
    if n != LOCATION_SORT_BUTTONS:
        raise ValueError(f"{what}: expected {LOCATION_SORT_BUTTONS} sort buttons, found {n}")
    t = _once(r'(sort_by_key_button = \{\n[^\n]*\n[ \t]*)size = \{ 110 -1 \}(\n[ \t]*name = "production_efficiency")',
              rf"\1size = {{ {BUILD_EFFICIENCY_WIDTH} -1 }}\2", t, what)
    cost, pay, profit, tax = BUILD_VALUE_WIDTHS
    for key, width in (("profit", profit), ("income", tax + BUILD_VALUE_MARGIN)):
        t = _once(rf'(sort_by_key_button = \{{\n[^\n]*\n[ \t]*name = "{key}"\n[ \t]*layoutpolicy_vertical = expanding\n[ \t]*)'
                  r"size = \{ 40 -1 \}", rf"\g<1>size = {{ {width} -1 }}", t, what)
    label = _block("widget = { # PP: build cost (no engine sort key in this list)", [
        "layoutpolicy_vertical = expanding", f"size = {{ {cost + BUILD_VALUE_MARGIN} -1 }}", 'tooltip = "PP_BUILD_COST_HEADER_TT"',
        _block("icon = {", ["size = { 20 20 }", "parentanchor = center", 'texture = "gfx/interface/icons/sort/cost.dds"'])])
    t = _once(r'^([ \t]*)(sort_by_key_button = \{\n[^\n]*\n[ \t]*name = "profit"\n)',
              lambda h: (_indent(label + "\n" + _payback_toggle(pay).replace(
                  'visible = "[BuildInLocationLateralView.GetBuildingType.IsProducing]"\n', ""), len(h.group(1)))
                  + "\n" + h.group(0)), t, what)
    t = _once(r'^([ \t]*)(sort_by_key_button = \{\n[^\n]*\n[ \t]*size = \{ 70 -1 \}\n[ \t]*name = "production_efficiency")',
              r"\1expand = {} # PP: the value buttons sit over their columns\n\n\1\2", t, what)
    t = _once(r'(sort_by_key_button = \{\n[^\n]*\n[ \t]*name = "level"\n)([ \t]*)using = layoutpolicy_expanding\n',
              r"\1\2layoutpolicy_vertical = expanding\n\2size = { 125 -1 }\n", t, what)
    # the list: vanilla's grid (selected sort) or the payback bands, rows BUILD_ROW_WIDTH wide (flowcontainers)
    start, end, ind = _cut(t, r'^([ \t]*)blockoverride "scroll_list_layout" \{\n', what)
    block = t[start:end]
    items = "LocationProductionView.GetBuildingItems"
    shown = re.search(r'(?m)^[ \t]*visible = "\[(.*)\]"\n', block)
    if not shown or f'datamodel = "[{items}]"' not in block or "addrow = 65" not in block:
        raise ValueError(f"{what}: the building list is no longer vanilla's grid")
    shown = shown.group(1)
    rw = BUILD_ROW_WIDTH
    row = _item_body(block)
    for name in LOCATION_ROW_TYPES:
        row, k = re.subn(rf"(?m)^([ \t]*){name} = \{{", rf"\1pp_{name} = {{", row)
        if k != 1:
            raise ValueError(f"{what}: the list does not use {name} once")
    row = _once(r"^widget = \{\n\tsize = \{ 100% 60 \}\n", f"widget = {{\n\tsize = {{ {rw} 60 }}\n", row, what)
    cell = _block("widget = {", [f"size = {{ {rw} 65 }}", row])
    name = payback_band_name()
    contexts = ['datacontext = "[BuildingItem.GetBuildingType]"', 'datacontext = "[LocationProductionView.GetSelectedLocation]"']
    bands = [(f"payback {low} to {high} years" if high else f"payback {low} years or more, or no profit",
              f"GetVariableSystem.HasValue({name}, '{low}')") for low, high in payback_bands()]
    bands.append(("not recorded yet", f"Not(GetVariableSystem.Exists({name}))"))
    bands = [_column([f'datamodel = "[{items}]"', _block("item = {", [_column([
        *contexts, f"datamodel = \"[DataModelRepeatedItem(Select_int32({test}, '(int32)1', '(int32)0'))]\"",
        _block("item = {", [cell])])])], comment) for comment, test in bands]
    grid = _block("fixedgridbox = { # the selected sort: vanilla's grid", [
        f'visible = "[And({shown}, Not({mode}))]"', "addrow = 65", f"addcolumn = {rw}", f'datamodel = "[{items}]"',
        _block("item = {", [row])])
    layout = _block('blockoverride "scroll_list_layout" { # PP: the selected sort or the payback order', [
        _column([grid, _column([f'visible = "[And({shown}, {mode})]"', *bands],
                               "payback order: shortest first, the last sort inside each band")])])
    return t[:start] + _indent(layout, len(ind)).rstrip("\n") + t[end:]


def _any_of(terms: list[str]) -> str:
    """The GUI's Or takes two arguments: a balanced tree of them."""
    if len(terms) == 1:
        return terms[0]
    half = (len(terms) + 1) // 2
    return f"Or({_any_of(terms[:half])}, {_any_of(terms[half:])})"


def goods_table_column(cooltips: str) -> str:
    """Vanilla's TooltipTableColumn for goods tables: its rows skip the internal goods and a scroll box five rows high
    (scrollbar off) clips the rest, so a table over the first five plus one per internal good shows the first five
    that are not internal; a plain box would grow to its rows' minimum height instead. The header stays outside the
    rows (vanilla's only per-row block, "visibility", would reach it too)."""
    what = "vanilla TooltipTableColumn"
    m = re.search(r"(?m)^\ttype TooltipTableColumn = vbox \{\n", cooltips)
    if not m:
        raise ValueError(f"{what}: not found")
    body = cooltips[m.end():_block_end(cooltips, m.end() - 2) - 1]
    body = _once(r'^\t\tblock "column_datamodel" \{\}\n\n?', "", body, what)
    item = re.search(r"(?m)^\t\titem = \{\n", body)
    if not item:
        raise ValueError(f"{what}: no item")
    item_end = _block_end(body, item.end() - 2)
    rows = body[item.start():item_end] + "\n"
    body = body[:item.start()].rstrip("\n") + "\n" + body[item_end:].lstrip("\n")
    rows = _once(r"^([ \t]*)(TooltipTableField = \{\n)",
                 lambda f: (f"{f.group(1)}{f.group(2)}{f.group(1)}\tblockoverride \"visibility\" {{\n"
                            f'{f.group(1)}\t\tdatacontext = "[GoodsMarketEntry.GetGoods]"\n'
                            f"{f.group(1)}\t\tusing = {INTERNAL_GOODS_TEMPLATE}\n{f.group(1)}\t}}\n"), rows, what)
    field = re.search(r'(?m)^\ttype TooltipTableField = \w+ \{\n(?:.*\n)*?\t\tblock "row_size" \{\n'
                      r"\t\t\tmaximumsize = \{ -1 (\d+) \}\n", cooltips)
    if not field:
        raise ValueError("vanilla TooltipTableField: no row_size")
    height = TOP_GOODS * int(field.group(1))
    return (f"\ttype {GOODS_TABLE_COLUMN} = vbox {{ # PP: vanilla TooltipTableColumn, rows without the internal goods\n"
            f"{body.rstrip()}\n\n\t\tscrollvbox = {{ # the first {TOP_GOODS} visible rows (takes no scrollbar policy; "
            "a scrollarea misaligned the columns in game, 2026-10-17)\n"
            f"\t\t\tlayoutpolicy_horizontal = expanding\n\t\t\tmaximumsize = {{ -1 {height} }}\n\n"
            "\t\t\tvbox = {\n\t\t\t\tlayoutpolicy_horizontal = expanding\n\t\t\t\tblock \"column_datamodel\" {}\n\n"
            f"{_indent(rows, 2)}\t\t\t}}\n\t\t}}\n\t}}\n")


def internal_goods_gui(cooltips: str) -> str:
    """The template every hidden list uses (invisible when the Goods in context is an internal good) and the goods
    table column of the tooltips."""
    hidden = _any_of([f"EqualTo_string(Goods.GetKey, '{key}')" for key in INTERNAL_GOODS])
    return ("# Generated by tools/port_vanilla_gui.py (INTERNAL_GOODS): the mod's internal goods are pinned at their price\n"
            "# floor and never traded, so the market, the ledgers, the market tooltip and the trade-order picker skip them.\n"
            "# Needs a Goods context; the lists that use it lay out visible items only (vbox, dynamicgridbox with\n"
            "# ignoreinvisible).\n"
            f"template {INTERNAL_GOODS_TEMPLATE} {{\n\tvisible = \"[Not({hidden})]\"\n}}\n\n"
            f"types PPInternalGoods {{\n{goods_table_column(cooltips)}}}\n")


def _hide_list(text: str, model: str, context: str, what: str) -> str:
    """A goods list on a fixedgridbox (which keeps a cell for a hidden item) as a vbox of rows that skip the internal
    goods. Row height from the grid's addrow; a list that only fills the scroll list's grid (blockoverride
    "scroll_list_content") overrides the whole layout instead."""
    found = list(re.finditer(rf'(?m)^[ \t]*datamodel = "\[{re.escape(model)}\]"\n', text))
    if len(found) != 1:
        raise ValueError(f"{what}: expected 1 list on {model}, found {len(found)}")
    openers = list(re.finditer(r'(?m)^([ \t]*)(fixedgridbox = \{|blockoverride "scroll_list_content" \{)\n',
                               text[:found[0].start()]))
    if not openers:
        raise ValueError(f"{what}: the list on {model} is not on a fixedgridbox")
    opener = openers[-1]
    ind = opener.group(1)
    end = _block_end(text, text.index("{", opener.start()))
    block = text[opener.start():end]
    row = re.search(r"(?m)^[ \t]*addrow = (\d+)\n", block)
    if not row:
        raise ValueError(f"{what}: the list on {model} has no addrow")
    body = _item_body(block)
    head = "" if not context else f'\t\t\tdatacontext = "[{context}]"\n'
    vbox = ("vbox = { # PP: skips the internal goods (a fixedgridbox would keep their rows empty)\n"
            f'\tlayoutpolicy_horizontal = expanding\n\tdatamodel = "[{model}]"\n\n\titem = {{\n\t\twidget = {{\n{head}'
            f"\t\t\tusing = {INTERNAL_GOODS_TEMPLATE}\n\t\t\tlayoutpolicy_horizontal = expanding\n"
            f"\t\t\tsize = {{ -1 {row.group(1)} }}\n\n{_indent(body, 3)}\t\t}}\n\t}}\n}}\n")
    if opener.group(2).startswith("blockoverride"):
        vbox = 'blockoverride "scroll_list_layout" {\n' + _indent(vbox, 1) + "}\n"
    return text[:opener.start()] + _indent(vbox, len(ind)).rstrip("\n") + text[end:]


def _hide_icons(text: str, model: str, what: str) -> str:
    """A top-five goods icon row (overlappingitembox) as the first five goods that are not internal: the first five
    plus one per internal good, in a strip five icons wide that clips the rest."""
    first = f"DataModelFirst({model}, '(int32){TOP_GOODS}')"
    found = list(re.finditer(rf'(?m)^[ \t]*datamodel = "\[{re.escape(first)}\]"\n', text))
    if len(found) != 1:
        raise ValueError(f"{what}: expected 1 icon row on {first}, found {len(found)}")
    opener = list(re.finditer(r"(?m)^([ \t]*)overlappingitembox = \{\n", text[:found[0].start()]))[-1]
    ind = opener.group(1)
    end = _block_end(text, text.index("{", opener.start()))
    body = _item_body(text[opener.start():end])
    icon = re.match(r"icon = \{\n\tsize = \{ (\d+) \d+ \}\n", body)
    if not icon:
        raise ValueError(f"{what}: the icon row on {model} is not a sized icon")
    size = int(icon.group(1))
    body = body[:icon.end()] + f"\tusing = {INTERNAL_GOODS_TEMPLATE}\n" + body[icon.end():]
    count = TOP_GOODS + len(INTERNAL_GOODS)
    strip = ("widget = { # PP: the first five goods that are not internal (vanilla overlappingitembox of the first five)\n"
             f"\tsize = {{ {TOP_GOODS * size} {size} }}\n\tparentanchor = center\n\tscissor = yes\n\n"
             f"\tdynamicgridbox = {{\n\t\tflipdirection = yes\n\t\tdatamodel_wrap = {count}\n\t\tignoreinvisible = yes\n"
             f"\t\tdatamodel = \"[DataModelFirst({model}, '(int32){count}')]\"\n\t\titem = {{\n{_indent(body, 3)}"
             "\t\t}\n\t}\n}\n")
    return text[:opener.start()] + _indent(strip, len(ind)).rstrip("\n") + text[end:]


def _hide_table(text: str, model: str, what: str) -> str:
    """A top-five goods table (TooltipTableColumn columns) on the goods table column, over the first five plus one per
    internal good: it shows the first five that are not internal."""
    first = f"DataModelFirst({model}, '(int32){TOP_GOODS}')"
    found = list(re.finditer(rf'datamodel = "\[{re.escape(first)}\]"', text))
    if len(found) != 1:
        raise ValueError(f"{what}: expected 1 table on {first}, found {len(found)}")
    opener = list(re.finditer(r"(?m)^[ \t]*TooltipListColumnContent = \{\n", text[:found[0].start()]))[-1]
    end = _block_end(text, text.index("{", opener.start()))
    table, n = re.subn(r"(?m)^([ \t]*)TooltipTableColumn = \{", rf"\1{GOODS_TABLE_COLUMN} = {{",
                       text[opener.start():end])
    if not n:
        raise ValueError(f"{what}: the table on {model} has no TooltipTableColumn")
    table = table.replace(first, f"DataModelFirst({model}, '(int32){TOP_GOODS + len(INTERNAL_GOODS)}')")
    return text[:opener.start()] + table + text[end:]


def port_internal_goods(vanilla: str, rel: str) -> str:
    """Vanilla goods lists of ``rel`` without the internal goods (INTERNAL_GOODS_LISTS, _ICONS, _TABLES)."""
    what = f"vanilla {rel}"
    t = vanilla
    for model, context in INTERNAL_GOODS_LISTS.get(rel, ()):
        t = _hide_list(t, model, context, what)
    for model in INTERNAL_GOODS_ICONS.get(rel, ()):
        t = _hide_icons(t, model, what)
    for model in INTERNAL_GOODS_TABLES.get(rel, ()):
        t = _hide_table(t, model, what)
    return t


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def ported(vanilla_game: Path, mod_root: Path) -> dict[str, str | None]:
    """file (relative to in_game/gui) -> ported text, None for a retired override."""
    out: dict[str, str | None] = {}
    for rel, scope in FOOD_GAUGE_FILES.items():
        out[rel] = port_food_gauges(_read(vanilla_game / GUI / rel), scope)
    out[LOCATION_PRODUCTION] = port_location_production(out[LOCATION_PRODUCTION])
    out[LOCATION_ROWS_GUI] = port_location_rows(_read(vanilla_game / GUI / PRODUCTION))
    out[BUILDING_VIEW] = port_building_view(_read(vanilla_game / GUI / BUILDING_VIEW))
    out[EUROPEDIA] = port_europedia(_read(vanilla_game / GUI / EUROPEDIA), _read(mod_root / GUI / EUROPEDIA))
    out[BUILD_LOCATION] = port_build_location(_read(vanilla_game / GUI / BUILD_LOCATION))
    for rel in {**INTERNAL_GOODS_LISTS, **INTERNAL_GOODS_ICONS, **INTERNAL_GOODS_TABLES}:
        out[rel] = port_internal_goods(_read(vanilla_game / GUI / rel), rel)
    out[INTERNAL_GOODS_GUI] = internal_goods_gui(_read(vanilla_game / COOLTIP_TYPES))
    for rel in RETIRED:
        out[rel] = None
    return out


def _normalised(text: str) -> str:
    """Mod file without the build's own steps (compiled divisor, CMF-proof pp_ type copies), for --check."""
    from prosper_or_perish_constructor import gui_compat
    from prosper_or_perish_constructor.food_storage_gui import FOOD_STORAGE_GUI_DIVISOR_RE

    for types in gui_compat.PROTECTED.values():
        for name in types:
            span = gui_compat._type_span(text, gui_compat.PREFIX + name)
            if span:
                start = text.rfind("\n", 0, span[0]) + 1
                if text[start - 2:start] == "\n\n":
                    start -= 2
                text = text[:start] + text[span[1]:]
            text = re.sub(rf"(?m)^([ \t]*){gui_compat.PREFIX}{name}([ \t]*=[ \t]*\{{)", rf"\g<1>{name}\g<2>", text)
    return FOOD_STORAGE_GUI_DIVISOR_RE.sub(rf"\g<1>{DIVISOR}\g<2>", text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vanilla", type=Path, help="vanilla game folder (default: the constructor's vanilla root)/game")
    parser.add_argument("--mod-root", type=Path, default=MOD_ROOT)
    parser.add_argument("--check", action="store_true", help="only report overrides that differ from a fresh port")
    args = parser.parse_args(argv)
    vanilla = args.vanilla
    if vanilla is None:
        from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

        vanilla = vanilla_root(REPO, REPO / "constructor.toml") / "game"
    differ = []
    for rel, text in ported(vanilla, args.mod_root).items():
        path = args.mod_root / GUI / rel
        if args.check:
            current = _normalised(_read(path)) if path.is_file() else None
            if current != text:
                differ.append(rel)
            continue
        if text is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("﻿" + text, encoding="utf-8", newline="\n")
        print(("removed " if text is None else "wrote ") + rel)
    if args.check:
        print("differ from a fresh port: " + (", ".join(differ) if differ else "none"))
        return 1 if differ else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
