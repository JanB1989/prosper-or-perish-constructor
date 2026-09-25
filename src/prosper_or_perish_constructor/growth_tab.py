"""The location view's Growth tab: population growth per estate, in the open instead of behind tooltips.

Merged into the World Builder location window by ``worldbuilder apply`` (see geography.py) next to the status chips.
One row per estate (``LocationView.GetPops``): pops, the engine's growth (births from the growth formula),
last month's actual change (births plus migration, promotion, starvation), the modelled yearly rate
``location growth x (1 + local/global_<type>_pop_growth)`` clamped at zero (the engine clamps the per-type
multiplier at zero births; verified 2026-09-25), and the engine's own change breakdown lines under the row.
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


def _cell(width: int, body: str, align: str = "right") -> str:
    return (f"\t\t\t\t\t\t\t\t\t\ttext_single = {{\n"
            f"\t\t\t\t\t\t\t\t\t\t\tsize = {{ {width} 16 }}\n"
            f"\t\t\t\t\t\t\t\t\t\t\tautoresize = no\n"
            f"\t\t\t\t\t\t\t\t\t\t\talign = {align}|nobaseline\n"
            f"\t\t\t\t\t\t\t\t\t\t\tfontsize = 13\n"
            f"{body}"
            f"\t\t\t\t\t\t\t\t\t\t}}\n")


def _header_cell(width: int, key: str, align: str = "right") -> str:
    return _cell(width, f"\t\t\t\t\t\t\t\t\t\t\tdefault_format = \"#medium\"\n\t\t\t\t\t\t\t\t\t\t\ttext = \"{key}\"\n", align)


_PANE = f"""\t\t\t\t# PP GROWTH (growth_tab.py): population growth per estate, growth and migration apart
\t\t\t\tvbox = {{
\t\t\t\t\tvisible = "[LocationView.Vars.HasValue( 'tab', '{TAB}' )]"
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tlayoutpolicy_vertical = expanding
\t\t\t\t\tmargin_top = 5
\t\t\t\t\tdatacontext = "[LocationView.GetLocation]"

\t\t\t\t\t# location lines: growth, migration attraction, free land
\t\t\t\t\thbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tmargin = {{ 10 4 }}
\t\t\t\t\t\tspacing = 12
\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\talign = left|nobaseline
\t\t\t\t\t\t\ttooltipwidget = {{ using = yearly_pop_growth_tooltip }}
\t\t\t\t\t\t\traw_text = "[Localize('PP_GROWTH_TAB_LOCATION_GROWTH')]: [Location.GetPopGrowth|2+=%]"
\t\t\t\t\t\t}}
\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\talign = left|nobaseline
\t\t\t\t\t\t\ttooltip = "[Location.GetLocalMigrationAttractionInfo]"
\t\t\t\t\t\t\traw_text = "[Localize('PP_GROWTH_TAB_MIGRATION_ATTRACTION')]: [Location.GetLocalMigrationAttraction|2+=]"
\t\t\t\t\t\t}}
\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\talign = left|nobaseline
\t\t\t\t\t\t\ttooltip = "PP_GROWTH_TAB_FREE_LAND_TT"
\t\t\t\t\t\t\traw_text = "[Localize('PP_GROWTH_TAB_FREE_LAND')]: [Location.GetModifierValueFixed('pp_land_available')|1%]"
\t\t\t\t\t\t}}
\t\t\t\t\t\texpand = {{}}
\t\t\t\t\t}}

\t\t\t\t\t# column headers
\t\t\t\t\thbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tmargin = {{ 10 2 }}
\t\t\t\t\t\tspacing = 4
\t\t\t\t\t\twidget = {{ size = {{ 26 16 }} }}
{_header_cell(90, "PP_GROWTH_TAB_COL_ESTATE", "left")}{_header_cell(60, "PP_GROWTH_TAB_COL_POPS")}{_header_cell(60, "PP_GROWTH_TAB_COL_GROWTH")}{_header_cell(60, "PP_GROWTH_TAB_COL_CHANGE")}{_header_cell(60, "PP_GROWTH_TAB_COL_RATE")}\t\t\t\t\t\texpand = {{}}
\t\t\t\t\t}}

\t\t\t\t\tvbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tmargin = {{ 10 2 }}
\t\t\t\t\t\tspacing = 2
\t\t\t\t\t\tdatamodel = "[LocationView.GetPops]"
\t\t\t\t\t\titem = {{
\t\t\t\t\t\t\tvbox = {{
\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\tvisible = "[LocationPopItem.HasPop]"
\t\t\t\t\t\t\t\tdatacontext = "[LocationPopItem.GetType]"
\t\t\t\t\t\t\t\tdatacontext = "[LocationPopItem.GetLocation]"
\t\t\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\tspacing = 4
\t\t\t\t\t\t\t\t\ttooltipwidget = {{ using = LocationPopItem_Breakdown }}
\t\t\t\t\t\t\t\t\ticon = {{
\t\t\t\t\t\t\t\t\t\tsize = {{ 26 26 }}
\t\t\t\t\t\t\t\t\t\ttexture = "[GetGraphicalCultureTextureForLocationPopType(Location.Self, PopType.Self)]"
\t\t\t\t\t\t\t\t\t}}
{_cell(90, '\t\t\t\t\t\t\t\t\t\t\ttext = "[PopType.GetNameWithNoTooltip|L]"\n', "left")}{_cell(60, '\t\t\t\t\t\t\t\t\t\t\ttext = "[LocationPopItem.GetTotalSize]"\n')}{_cell(60, '\t\t\t\t\t\t\t\t\t\t\ttext = "[LocationPopItem.GetGrowth]"\n')}{_cell(60, '\t\t\t\t\t\t\t\t\t\t\ttext = "[LocationPopItem.GetGrowthForUI|Y]"\n')}\t\t\t\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\t\t\t\tsize = {{ 60 16 }}
\t\t\t\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\t\t\t\talign = right|nobaseline
\t\t\t\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\t\t\t\tvisible = "[Location.HasOwner]"
\t\t\t\t\t\t\t\t\t\ttooltip = "PP_GROWTH_TAB_RATE_TT"
\t\t\t\t\t\t\t\t\t\ttext = "[{_RATE_OWNED}|2+=%]"
\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\t\t\t\tsize = {{ 60 16 }}
\t\t\t\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\t\t\t\talign = right|nobaseline
\t\t\t\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\t\t\t\tvisible = "[Not(Location.HasOwner)]"
\t\t\t\t\t\t\t\t\t\ttooltip = "PP_GROWTH_TAB_RATE_TT"
\t\t\t\t\t\t\t\t\t\ttext = "[{_RATE_UNOWNED}|2+=%]"
\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t\texpand = {{}}
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t# the engine's change lines for this estate (born, starved, migrated, class changes)
\t\t\t\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\tautoresize = yes
\t\t\t\t\t\t\t\t\tmargin_left = 30
\t\t\t\t\t\t\t\t\tfontsize = 12
\t\t\t\t\t\t\t\t\tvisible = "[Not(StringIsEmpty(Location.GetGrowthTooltip(PopType.Self)))]"
\t\t\t\t\t\t\t\t\ttext = "[Location.GetGrowthTooltip(PopType.Self)]"
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\texpand = {{}}
\t\t\t\t}}

"""

LOCALIZATION_TEXT = """l_english:
 PP_LOC_VIEW_GROWTH_TAB: "Growth"
 PP_LOC_VIEW_GROWTH_TAB_TT: "Population growth per estate: the engine's growth, last month's actual change and the change lines behind it."
 PP_GROWTH_TAB_LOCATION_GROWTH: "Location growth"
 PP_GROWTH_TAB_MIGRATION_ATTRACTION: "Migration attraction"
 PP_GROWTH_TAB_FREE_LAND: "Free land"
 PP_GROWTH_TAB_FREE_LAND_TT: "Share of the population capacity that is still free. Tribesmen grow with it."
 PP_GROWTH_TAB_COL_ESTATE: "Estate"
 PP_GROWTH_TAB_COL_POPS: "Pops"
 PP_GROWTH_TAB_COL_GROWTH: "Growth"
 PP_GROWTH_TAB_COL_CHANGE: "Last month"
 PP_GROWTH_TAB_COL_RATE: "Yearly"
 PP_GROWTH_TAB_RATE_TT: "The location's yearly growth scaled by this estate's growth modifiers. Migration and class changes come on top."
"""


def add_growth_tab(text: str) -> str:
    """Insert the tab button after the Demography tab and the pane before the Demography pane."""
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
