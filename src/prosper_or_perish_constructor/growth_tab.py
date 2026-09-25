"""The location view's Growth tab: population growth per estate, in the open instead of behind tooltips.

Merged into the World Builder location window by ``worldbuilder apply`` (see geography.py) next to the status chips.
One row per estate (``LocationView.GetPops``): pops, the modelled yearly rate
``location growth x (1 + local/global_<type>_pop_growth)`` clamped at zero (the engine clamps the per-type
multiplier at zero births; verified 2026-09-25), last month's actual change (births plus migration, promotion,
starvation) and the engine's own change lines under the row, which are the only per-estate split of births,
migration and class changes the engine exposes (``Location.GetGrowthTooltip(PopType)``; the numeric
``LocationPopItem.GetGrowth`` is a net figure too, so it is not shown).
"""

from __future__ import annotations

from pathlib import Path

LOCALIZATION = "main_menu/localization/english/pp_growth_tab_l_english.yml"
TAB = "growth"

_TAB_ANCHOR = (
    "\t\t\t\t\t\tdown = \"[LocationView.Vars.HasValue( 'tab', 'demography' )]\"\n"
    "\t\t\t\t\t}\n"
)
_PANE_ANCHOR = (
    "\t\t\t\t# DEMOGRAPHY\n"
    "\t\t\t\tvbox = {\n"
    "\t\t\t\t\tvisible = \"[LocationView.Vars.HasValue( 'tab', 'demography' )]\"\n"
)

_TAB_BUTTON = f"""
\t\t\t\t\t# PP GROWTH TAB (growth_tab.py)
\t\t\t\t\tbutton_secondary_tab_alt = {{
\t\t\t\t\t\tusing = layoutpolicy_expanding
\t\t\t\t\t\tblockoverride "tab_text"{{
\t\t\t\t\t\t\ttext = "PP_LOC_VIEW_GROWTH_TAB"
\t\t\t\t\t\t}}
\t\t\t\t\t\ttooltip = "PP_LOC_VIEW_GROWTH_TAB_TT"
\t\t\t\t\t\taction_tooltip = {{
\t\t\t\t\t\t\ttitle = "OPEN_TAB"
\t\t\t\t\t\t\ton_action = "[LocationView.Vars.Set( 'tab', '{TAB}' )]"
\t\t\t\t\t\t}}
\t\t\t\t\t\tdown = "[LocationView.Vars.HasValue( 'tab', '{TAB}' )]"
\t\t\t\t\t}}
"""

# per-estate multiplier: 1 + local_<type>_pop_growth (+ the owner's global_<type>_pop_growth where there is an owner)
_LOCAL = "Location.GetModifierValueFixed(Concatenate('local_', Concatenate(PopType.GetKey, '_pop_growth')))"
_GLOBAL = "Location.GetOwner.GetModifierRawValue(Concatenate('global_', Concatenate(PopType.GetKey, '_pop_growth')))"
_RATE_OWNED = (f"Max_CFixedPoint(Multiply_CFixedPoint(Location.GetPopGrowth, Add_CFixedPoint('(CFixedPoint)1', "
               f"Add_CFixedPoint({_LOCAL}, {_GLOBAL}))), '(CFixedPoint)0')")
_RATE_UNOWNED = (f"Max_CFixedPoint(Multiply_CFixedPoint(Location.GetPopGrowth, Add_CFixedPoint('(CFixedPoint)1', "
                 f"{_LOCAL})), '(CFixedPoint)0')")

# column widths: icon 26, estate 96, pops 64, yearly 70, last month 70 = 326 + spacing, inside the ~380 px pane
_COLS = ((96, "left"), (64, "right"), (70, "right"), (70, "right"))


def _cell(width: int, align: str, body: str, indent: int) -> str:
    t = "\t" * indent
    return (f"{t}text_single = {{\n"
            f"{t}\tsize = {{ {width} 18 }}\n"
            f"{t}\tautoresize = no\n"
            f"{t}\talign = {align}|nobaseline\n"
            f"{t}\tfontsize = 14\n"
            f"{body}"
            f"{t}}}\n")


def _header_line(key: str, value: str, tooltip: str) -> str:
    return (f"\t\t\t\t\t\ttext_single = {{\n"
            f"\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding\n"
            f"\t\t\t\t\t\t\talign = left|nobaseline\n"
            f"\t\t\t\t\t\t\tfontsize = 14\n"
            f"\t\t\t\t\t\t\t{tooltip}\n"
            f"\t\t\t\t\t\t\traw_text = \"[Localize('{key}')]: {value}\"\n"
            f"\t\t\t\t\t\t}}\n")


def _headers() -> str:
    keys = ("PP_GROWTH_TAB_COL_ESTATE", "PP_GROWTH_TAB_COL_POPS", "PP_GROWTH_TAB_COL_RATE", "PP_GROWTH_TAB_COL_CHANGE")
    return "".join(_cell(w, a, f"\t\t\t\t\t\t\t\tdefault_format = \"#medium\"\n\t\t\t\t\t\t\t\ttext = \"{k}\"\n", 7)
                   for (w, a), k in zip(_COLS, keys))


def _rate_cell(expr: str, visible: str) -> str:
    return _cell(70, "right", f"\t\t\t\t\t\t\t\t\t\t\t\tvisible = \"{visible}\"\n"
                              f"\t\t\t\t\t\t\t\t\t\t\t\ttooltip = \"PP_GROWTH_TAB_RATE_TT\"\n"
                              f"\t\t\t\t\t\t\t\t\t\t\t\ttext = \"[{expr}|2+=%]\"\n", 11)


_PANE = f"""\t\t\t\t# PP GROWTH (growth_tab.py): population growth per estate, growth and migration apart
\t\t\t\tvbox = {{
\t\t\t\t\tvisible = "[LocationView.Vars.HasValue( 'tab', '{TAB}' )]"
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tlayoutpolicy_vertical = expanding
\t\t\t\t\tmargin_top = 5
\t\t\t\t\tdatacontext = "[LocationView.GetLocation]"

\t\t\t\t\t# the location: growth, migration attraction, free land
\t\t\t\t\tvbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tmargin = {{ 10 4 }}
\t\t\t\t\t\tspacing = 2
{_header_line("PP_GROWTH_TAB_LOCATION_GROWTH", "[Location.GetPopGrowth|2+=%]", "tooltipwidget = { using = yearly_pop_growth_tooltip }")}{_header_line("PP_GROWTH_TAB_MIGRATION_ATTRACTION", "[Location.GetLocalMigrationAttraction|2+=]", 'tooltip = "[Location.GetLocalMigrationAttractionInfo]"')}{_header_line("PP_GROWTH_TAB_FREE_LAND", "[Location.GetModifierValueFixed('pp_land_available')|1%]", 'tooltip = "PP_GROWTH_TAB_FREE_LAND_TT"')}\t\t\t\t\t}}

\t\t\t\t\t# column headers
\t\t\t\t\thbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tmargin = {{ 10 2 }}
\t\t\t\t\t\tspacing = 4
\t\t\t\t\t\twidget = {{ size = {{ 26 18 }} }}
{_headers()}\t\t\t\t\t\texpand = {{}}
\t\t\t\t\t}}

\t\t\t\t\tscrollarea = {{
\t\t\t\t\t\tusing = layoutpolicy_expanding
\t\t\t\t\t\tscrollbarpolicy_horizontal = always_off
\t\t\t\t\t\tautoresizescrollarea = no
\t\t\t\t\t\tscrollbar_vertical = {{
\t\t\t\t\t\t\tusing = Scrollbar_Vertical
\t\t\t\t\t\t}}
\t\t\t\t\t\tscrollwidget = {{
\t\t\t\t\t\t\tvbox = {{
\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\tmargin = {{ 10 2 }}
\t\t\t\t\t\t\t\tspacing = 4
\t\t\t\t\t\t\t\tdatamodel = "[LocationView.GetPops]"
\t\t\t\t\t\t\t\titem = {{
\t\t\t\t\t\t\t\t\tvbox = {{
\t\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\t\tvisible = "[LocationPopItem.HasPop]"
\t\t\t\t\t\t\t\t\t\tdatacontext = "[LocationPopItem.GetType]"
\t\t\t\t\t\t\t\t\t\tdatacontext = "[LocationPopItem.GetLocation]"
\t\t\t\t\t\t\t\t\t\tusing = bg_dark_paper_card
\t\t\t\t\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\t\t\tmargin = {{ 4 2 }}
\t\t\t\t\t\t\t\t\t\t\tspacing = 4
\t\t\t\t\t\t\t\t\t\t\ttooltipwidget = {{ using = LocationPopItem_Breakdown }}
\t\t\t\t\t\t\t\t\t\t\ticon = {{
\t\t\t\t\t\t\t\t\t\t\t\tsize = {{ 26 26 }}
\t\t\t\t\t\t\t\t\t\t\t\ttexture = "[GetGraphicalCultureTextureForLocationPopType(Location.Self, PopType.Self)]"
\t\t\t\t\t\t\t\t\t\t\t}}
{_cell(96, "left", '\t\t\t\t\t\t\t\t\t\t\t\ttext = "[PopType.GetNameWithNoTooltip|L]"\n', 11)}{_cell(64, "right", '\t\t\t\t\t\t\t\t\t\t\t\ttext = "[LocationPopItem.GetTotalSize]"\n', 11)}{_rate_cell(_RATE_OWNED, "[Location.HasOwner]")}{_rate_cell(_RATE_UNOWNED, "[Not(Location.HasOwner)]")}{_cell(70, "right", '\t\t\t\t\t\t\t\t\t\t\t\ttext = "[LocationPopItem.GetGrowthForUI|Y]"\n', 11)}\t\t\t\t\t\t\t\t\t\t\texpand = {{}}
\t\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t\t\t# the engine's change lines for this estate (born, starved, migrated, class changes)
\t\t\t\t\t\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\t\t\tautoresize = yes
\t\t\t\t\t\t\t\t\t\t\tmargin = {{ 34 0 }}
\t\t\t\t\t\t\t\t\t\t\tmargin_bottom = 4
\t\t\t\t\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\t\t\t\t\tvisible = "[Not(StringIsEmpty(Location.GetGrowthTooltip(PopType.Self)))]"
\t\t\t\t\t\t\t\t\t\t\ttext = "[Location.GetGrowthTooltip(PopType.Self)]"
\t\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}

"""

LOCALIZATION_TEXT = """l_english:
 PP_LOC_VIEW_GROWTH_TAB: "Growth"
 PP_LOC_VIEW_GROWTH_TAB_TT: "Population growth per estate: the yearly rate, last month's actual change and the change lines behind it."
 PP_GROWTH_TAB_LOCATION_GROWTH: "Location growth"
 PP_GROWTH_TAB_MIGRATION_ATTRACTION: "Migration attraction"
 PP_GROWTH_TAB_FREE_LAND: "Free land"
 PP_GROWTH_TAB_FREE_LAND_TT: "Share of the population capacity that is still free. Tribesmen grow with it."
 PP_GROWTH_TAB_COL_ESTATE: "Estate"
 PP_GROWTH_TAB_COL_POPS: "Pops"
 PP_GROWTH_TAB_COL_CHANGE: "Last month"
 PP_GROWTH_TAB_COL_RATE: "Yearly"
 PP_GROWTH_TAB_RATE_TT: "The location's yearly growth scaled by this estate's growth modifiers. Migration and class changes come on top."
"""


def strip_growth_tab(text: str) -> str:
    """Remove an earlier merge so the tab can be re-applied to a built window."""
    # end markers start with a newline so a deeper "}" line (more tabs) cannot match as a substring
    for start_marker, end in (("\n\t\t\t\t\t# PP GROWTH TAB (growth_tab.py)\n", "\n\t\t\t\t\t}\n"),
                              ("\t\t\t\t# PP GROWTH (growth_tab.py)", "\n\t\t\t\t}\n\n")):
        start = text.find(start_marker)
        if start < 0:
            continue
        stop = text.index(end, start + len(start_marker)) + len(end)
        text = text[:start] + text[stop:]
    return text


def add_growth_tab(text: str) -> str:
    """Insert the tab button after the Demography tab and the pane before the Demography pane (idempotent)."""
    text = strip_growth_tab(text)
    for anchor, label in ((_TAB_ANCHOR, "demography tab button"), (_PANE_ANCHOR, "demography pane")):
        found = text.count(anchor)
        if found != 1:
            raise ValueError(f"location_window.gui: expected 1 {label} anchor for the growth tab, found {found}")
    text = text.replace(_TAB_ANCHOR, _TAB_ANCHOR + _TAB_BUTTON)
    return text.replace(_PANE_ANCHOR, _PANE + _PANE_ANCHOR)


def write_localization(mod_root: Path) -> int:
    path = mod_root / LOCALIZATION
    body = "﻿" + LOCALIZATION_TEXT
    if path.is_file() and path.read_text(encoding="utf-8") == body:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return 1


def reapply(mod_root: Path) -> None:
    """Re-merge the tab into the built window (fast iteration without a full worldbuilder apply)."""
    window = mod_root / "in_game" / "gui" / "location_window.gui"
    merged = add_growth_tab(window.read_text(encoding="utf-8-sig"))
    window.write_text("﻿" + merged, encoding="utf-8", newline="\n")
    write_localization(mod_root)
