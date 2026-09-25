"""The location view's Growth tab: population growth per estate, laid out like the Demography table.

Merged into the World Builder location window by ``worldbuilder apply`` (see geography.py) next to the status chips.
The pane copies the Demography list (a scroll area of 32 px card rows from ``LocationView.GetPops`` with the vanilla
estate chip) rather than instantiating the ``demography_chart`` type: an instance of that type inside the pane broke
the Demography pane's ``Location`` context on hot reload (2026-09-25). Columns: pops, the modelled yearly rate
``location growth x (1 + local/global_<type>_pop_growth)`` clamped at zero (the engine clamps the per-type multiplier
at zero births; verified 2026-09-25) and last month's actual change (births plus migration, promotion, starvation).
The chip's tooltip is the vanilla breakdown (born, starved, migrated, class changes), which the engine exposes only
as text (``Location.GetGrowthTooltip(PopType)``; no numeric per-cause functions exist, and
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
_INTEL = "HasPopBreakdownIntelOn(Location.Self)"
T = "\t" * 12   # indentation of the row cells


def _line(key: str, value: str, tooltip: str) -> str:
    """One location line of the header: label and value."""
    return (f"\t\t\t\t\t\ttext_single = {{\n"
            f"\t\t\t\t\t\t\tsize = {{ 165 16 }}\n"   # fixed: an auto-sized line widened the whole window (2026-09-25)
            f"\t\t\t\t\t\t\tautoresize = no\n"
            f"\t\t\t\t\t\t\telide = right\n"
            f"\t\t\t\t\t\t\talign = left|nobaseline\n"
            f"\t\t\t\t\t\t\tfontsize = 14\n"
            f"\t\t\t\t\t\t\t{tooltip}\n"
            f"\t\t\t\t\t\t\traw_text = \"#medium [Localize('{key}')]#! {value}\"\n"
            f"\t\t\t\t\t\t}}\n")


def _col(width: int, body: str, visible: str = "") -> str:
    return (f"{T}text_single = {{\n"
            + (f"{T}\tvisible = \"[{visible}]\"\n" if visible else "") +
            f"{T}\tsize = {{ {width} 12 }}\n"
            f"{T}\tautoresize = no\n"
            f"{T}\talign = right|nobaseline\n"
            f"{body}"
            f"{T}}}\n")


# the vanilla estate chip of the Demography rows (icon + name on the estate colour, breakdown tooltip, people view)
_CHIP = f"""{T}widget = {{
{T}\tsize = {{ 105 28 }}
{T}\tusing = bg_building_card_colors
{T}\tblockoverride "building_color" {{
{T}\t\tcolor = "[LocationPopItem.GetColor]"
{T}\t\talpha = 0.7
{T}\t\tblend_mode = overlay
{T}\t}}
{T}\tcard_header_button_04 = {{
{T}\t\tallow_outside = yes
{T}\t\tsize = {{ 100% 100% }}
{T}\t\tdatacontext = "[LocationPopItem.GetType]"
{T}\t\tdatacontext = "[LocationPopItem.GetLocation]"
{T}\t\ttooltipmeta = {{
{T}\t\t\ttexture = "[GetGraphicalCultureTextureForLocationPopType(Location.Self, PopType.Self)]"
{T}\t\t}}
{T}\t\ttooltipwidget = {{
{T}\t\t\tusing = LocationPopItem_Breakdown
{T}\t\t}}
{T}\t\taction_tooltip = {{
{T}\t\t\tclick_type = left
{T}\t\t\tclick_mode = single
{T}\t\t\ttitle = "OPEN_POP_TYPE_PEOPLE_VIEW"
{T}\t\t\ton_action = "[ShowCountryPeopleViewWithPopFilter(PopType.Self, '(bool)yes')]"
{T}\t\t\ton_action = "[ShowCountryPeopleViewWithLocation(Location.GetId, '(bool)no')]"
{T}\t\t}}
{T}\t\thbox = {{
{T}\t\t\tmargin = {{ 3 0 }}
{T}\t\t\tspacing = 1
{T}\t\t\twidget = {{
{T}\t\t\t\tsize = {{ 20 20 }}
{T}\t\t\t\tusing = bg_circle_piechart
{T}\t\t\t\ticon = {{
{T}\t\t\t\t\tsize = {{ 92% 92% }}
{T}\t\t\t\t\tparentanchor = center
{T}\t\t\t\t\tposition = {{-1 0}}
{T}\t\t\t\t\ttexture = "[GetGraphicalCultureTextureForLocationPopType(Location.Self, LocationPopItem.GetType)]"
{T}\t\t\t\t\tglow = {{
{T}\t\t\t\t\t\tname = "drop_shadow"
{T}\t\t\t\t\t\tglow_radius = 3
{T}\t\t\t\t\t\tcolor = {{0.0 0.0 0.0 1.0}}
{T}\t\t\t\t\t\talpha = 0.3
{T}\t\t\t\t\t}}
{T}\t\t\t\t}}
{T}\t\t\t}}
{T}\t\t\ttext_single = {{
{T}\t\t\t\tsize = {{70 12}}
{T}\t\t\t\tautoresize = no
{T}\t\t\t\talign = left|nobaseline
{T}\t\t\t\ttext = "[LocationPopItem.GetType.GetNameWithNoTooltip|L]"
{T}\t\t\t}}
{T}\t\t}}
{T}\t}}
{T}}}
"""

_ROW = (_CHIP
        + f"{T}expand = {{}}\n"
        + _col(65, f"{T}\ttext = \"[LocationPopItem.GetTotalSize]\"\n")
        + _col(60, f"{T}\ttooltip = \"PP_GROWTH_TAB_RATE_TT\"\n{T}\ttext = \"[{_RATE_OWNED}|2+=%]\"\n",
               "Location.HasOwner")
        + _col(60, f"{T}\ttooltip = \"PP_GROWTH_TAB_RATE_TT\"\n{T}\ttext = \"[{_RATE_UNOWNED}|2+=%]\"\n",
               "Not(Location.HasOwner)")
        + _col(55, f"{T}\ttooltip = \"PP_GROWTH_TAB_CHANGE_TT\"\n{T}\ttext = \"[LocationPopItem.GetGrowthForUI|Y]\"\n")
        + _col(180, f"{T}\ttagtooltip_enabled = yes\n{T}\ttext = \"INTEL_FOG_LOC_POP_BREAKDOWN_UNKNOWN\"\n", f"Not({_INTEL})"))


def _header_cell(width: int, key: str) -> str:
    return (f"\t\t\t\t\t\t\ttext_single = {{\n"
            f"\t\t\t\t\t\t\t\tsize = {{ {width} 14 }}\n"
            f"\t\t\t\t\t\t\t\tautoresize = no\n"
            f"\t\t\t\t\t\t\t\talign = right|nobaseline\n"
            f"\t\t\t\t\t\t\t\tdefault_format = \"#medium\"\n"
            f"\t\t\t\t\t\t\t\tfontsize = 12\n"
            f"\t\t\t\t\t\t\t\ttext = \"{key}\"\n"
            f"\t\t\t\t\t\t\t}}\n")


_PANE = f"""\t\t\t\t# PP GROWTH (growth_tab.py): population growth per estate, laid out like the Demography table
\t\t\t\tvbox = {{
\t\t\t\t\tvisible = "[LocationView.Vars.HasValue( 'tab', '{TAB}' )]"
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tlayoutpolicy_vertical = expanding
\t\t\t\t\tmaximumsize = {{ 540 -1 }}
\t\t\t\t\tmargin_top = 5

\t\t\t\t\t# the location: growth, migration attraction, free land
\t\t\t\t\thbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tmargin = {{ 15 4 }}
\t\t\t\t\t\tspacing = 14
\t\t\t\t\t\tdatacontext = "[LocationView.GetLocation]"
{_line("PP_GROWTH_TAB_LOCATION_GROWTH", "[Location.GetPopGrowth|2+=%]", 'tooltip = "[Location.GetPopGrowthInfo]"')}{_line("PP_GROWTH_TAB_MIGRATION_ATTRACTION", "[Location.GetLocalMigrationAttraction|2+=]", 'tooltip = "[Location.GetLocalMigrationAttractionInfo]"')}{_line("PP_GROWTH_TAB_FREE_LAND", "[Location.GetModifierValueFixed('pp_land_available')|1%]", 'tooltip = "PP_GROWTH_TAB_FREE_LAND_TT"')}\t\t\t\t\t\texpand = {{}}
\t\t\t\t\t}}

\t\t\t\t\t# column headers, right-aligned over the row columns (chip 105 | expand | 65 | 60 | 55)
\t\t\t\t\twidget = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tsize = {{ -1 18 }}
\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\tmargin = {{ 22 0 }}
\t\t\t\t\t\t\tspacing = 3
\t\t\t\t\t\t\texpand = {{}}
{_header_cell(65, "PP_GROWTH_TAB_COL_POPS")}{_header_cell(60, "PP_GROWTH_TAB_COL_RATE")}{_header_cell(55, "PP_GROWTH_TAB_COL_CHANGE")}\t\t\t\t\t\t}}
\t\t\t\t\t}}

\t\t\t\t\t# the Demography list, one card row per estate
\t\t\t\t\tscrollarea = {{
\t\t\t\t\t\tusing = layoutpolicy_expanding
\t\t\t\t\t\tscrollbarpolicy_horizontal = always_off
\t\t\t\t\t\tautoresizescrollarea = no
\t\t\t\t\t\tscrollbar_vertical = {{
\t\t\t\t\t\t\tusing = Scrollbar_Vertical
\t\t\t\t\t\t}}
\t\t\t\t\t\tscrollwidget = {{
\t\t\t\t\t\t\tfixedgridbox = {{
\t\t\t\t\t\t\t\taddcolumn = 520
\t\t\t\t\t\t\t\taddrow = 32
\t\t\t\t\t\t\t\tdatamodel = "[LocationView.GetPops]"
\t\t\t\t\t\t\t\titem = {{
\t\t\t\t\t\t\t\t\twidget = {{
\t\t\t\t\t\t\t\t\t\tsize = {{ 510 32 }}
\t\t\t\t\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\t\t\t\t\tmargin = {{ 5 2 }}
\t\t\t\t\t\t\t\t\t\t\twidget = {{
\t\t\t\t\t\t\t\t\t\t\t\tusing = layoutpolicy_expanding
\t\t\t\t\t\t\t\t\t\t\t\tusing = bg_dark_paper_card
\t\t\t\t\t\t\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\t\t\t\t\t\t\tdatacontext = "[LocationPopItem.GetType]"
\t\t\t\t\t\t\t\t\t\t\t\t\tdatacontext = "[LocationPopItem.GetLocation]"
\t\t\t\t\t\t\t\t\t\t\t\t\tmargin_right = 5
\t\t\t\t\t\t\t\t\t\t\t\t\tspacing = 3
{_ROW}\t\t\t\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t\t\t\t}}
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
 PP_LOC_VIEW_GROWTH_TAB_TT: "Population growth per estate: the yearly rate and last month's actual change."
 PP_GROWTH_TAB_LOCATION_GROWTH: "Growth"
 PP_GROWTH_TAB_MIGRATION_ATTRACTION: "Attraction"
 PP_GROWTH_TAB_FREE_LAND: "Free land"
 PP_GROWTH_TAB_FREE_LAND_TT: "Share of the population capacity that is still free. Tribesmen grow with it."
 PP_GROWTH_TAB_COL_POPS: "Pops"
 PP_GROWTH_TAB_COL_CHANGE: "Month"
 PP_GROWTH_TAB_COL_RATE: "Yearly"
 PP_GROWTH_TAB_RATE_TT: "Yearly growth of this estate: the location's growth scaled by the estate's growth modifiers. Migration and class changes come on top."
 PP_GROWTH_TAB_CHANGE_TT: "Last month's actual change of this estate: births, deaths, migration and class changes. Hover the estate for the breakdown."
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
