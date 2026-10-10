"""Rebuild the mod's hand-kept vanilla GUI overrides from the current vanilla files (run after an EU5 update).

Each override is the vanilla file plus the mod's own changes, which are written down here so the next game update
only needs a rerun: the stored-food gauges (the script value ``pp_province_food_storage_months`` instead of the
vanilla food-capacity percentage), for the Europedia, the Prosper or Perish page (its button and its cards, taken from the current mod
file), and for the build panel a layout that fits PP's many-slot, many-input buildings (``port_build_location``).
Everything else is vanilla, so whatever the game adds to these windows stays visible.

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
# the build panel ("Building <type>"): width (vanilla left panel 570; a six-slot row needs ~790), location card
# (vanilla 150) and the input goods per line of a slot filter row (the Cookshop slot has 22)
BUILD_LOCATION = "build_location_lateralview.gui"
BUILD_PANEL_WIDTH = 800
BUILD_LOCATION_CARD_WIDTH = 175
BUILD_INPUTS_PER_LINE = 14


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
    efficiencies two per column, so they stay inside the row. Everything else is vanilla."""
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
              rf"\1dynamicgridbox = {{ # HIDES PRICES IF NUMBER OF INPUTS > 5 (PP: {BUILD_INPUTS_PER_LINE} per line)\n"
              rf"\2flipdirection = yes\n\2datamodel_wrap = {BUILD_INPUTS_PER_LINE}\n\2spacing = 4\n", t, what)
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
    for key in ("profit", "income"):
        t = _once(rf'(sort_by_key_button = \{{\n[ \t]*name = "{key}"\n[ \t]*layoutpolicy_vertical = expanding\n[ \t]*)'
                  r"size = \{ 40 -1 \}", r"\1size = { 35 -1 }", t, what)
    t = _once(r'(sort_by_key_button = \{\n[ \t]*name = "number_building"\n)([ \t]*)using = layoutpolicy_expanding\n',
              r"\1\2layoutpolicy_vertical = expanding\n\2size = { 125 -1 }\n", t, what)
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def ported(vanilla_game: Path, mod_root: Path) -> dict[str, str | None]:
    """file (relative to in_game/gui) -> ported text, None for a retired override."""
    out: dict[str, str | None] = {}
    for rel, scope in FOOD_GAUGE_FILES.items():
        out[rel] = port_food_gauges(_read(vanilla_game / GUI / rel), scope)
    out[EUROPEDIA] = port_europedia(_read(vanilla_game / GUI / EUROPEDIA), _read(mod_root / GUI / EUROPEDIA))
    out[BUILD_LOCATION] = port_build_location(_read(vanilla_game / GUI / BUILD_LOCATION))
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
