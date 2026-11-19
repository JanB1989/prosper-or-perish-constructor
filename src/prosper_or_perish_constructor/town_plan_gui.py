"""The location window's Plans row (town plans, branch town-plans, 2026-11-19, Jan).

On top of the location window's Infrastructure tab, player-owned locations only (observers' commands are dropped): the
plans the location holds (``pp_plan_<plan>`` town rights, ``town_plans.py``) as pressed tiles, a click takes that plan
off, the tooltip says what the plan does and how its last check went; at the right end one round button that opens the
Location Plan window (every plan to set). It replaces the Profile row and the row "Also build here".

``render_row`` writes the row's type into ``gui/pp_location_plan_generated.gui`` (``location_plan.apply``);
``add_plan_row`` patches the location window (``location_view.build_window``).
"""

from __future__ import annotations

ROW_TYPE = "pp_tplan_location_row"
ROW_MARK = "# PP: Plans row (town_plan_gui.py)"
_INFRA_ANCHOR = "# INFRASTRUCTURE HUB\n"
ROW_TILES = 11  # tiles the row's line holds; more plans than that: the count beside the title
TILE_WIDTH = 37  # px a tile takes: the 34 px tile and its gap
PLAN_ICON = "gfx/interface/icons/map_modes/pp_location_plan.dds"
FLAT = "gfx/interface/buttons/flats/{}.dds"
VISIBLE = "And(LocationView.GetLocation.GetOwner.IsPlayer, Not(IsObserving))"
# The Location Plan window opened on the location (datacontext Location).
OPEN_PLAN = ("[GetScriptedGui('pp_lplan_select').Execute(GuiScope.SetRoot(Location.MakeScope).End)]",
             "[GetVariableSystem.Set('pp_lplan_open', 'yes')]")


# ---------------------------------------------------------------------------------------------------------------------
# expressions (from location_profiles_gui.py)


def fixed(value: int) -> str:
    return f"'(CFixedPoint){value}'"


def value_is(scope: str, name: str, value: int) -> str:
    """A script value of the scope equals value."""
    return f"EqualTo_CFixedPoint({scope}.ScriptValue('{name}'), {fixed(value)})"


def value_above(scope: str, name: str, value: int) -> str:
    return f"GreaterThan_CFixedPoint({scope}.ScriptValue('{name}'), {fixed(value)})"


# The card of the row: the corner decoration of its content box, and a round icon button of its right end.
_CARD_FLAVOR = (
    "\t\t\tusing = bg_corner_flavor\n"
    "\t\t\tblockoverride \"corner_flavor_texture\" {\n"
    "\t\t\t\ttexture = \"gfx/interface/component_decoration/bg_corner_flavor_06.dds\"\n"
    "\t\t\t\ttexture_density = 2\n\t\t\t\tspriteType = Corneredstretched\n"
    "\t\t\t\tspriteborder = { 35 35 }\n\t\t\t\talpha = 0.4\n\t\t\t}\n"
    "\t\t\tblockoverride \"corner_flavor_color\" {\n"
    "\t\t\t\tmodify_texture = { using = color_bg_blue_texture blend_mode = multiply }\n\t\t\t}\n"
)


def _card_button(tooltip: str, onclicks: tuple[str, ...], icon: str) -> str:
    return (
        "\t\t\t\theader_button_left = {\n"
        "\t\t\t\t\tblockoverride \"header_button_full_content\" {}\n"
        "\t\t\t\t\tsize = { 30 30 }\n"
        f"\t\t\t\t\ttooltip = \"{tooltip}\"\n"
        + "".join(f"\t\t\t\t\tonclick = \"{onclick}\"\n" for onclick in onclicks)
        + f"\t\t\t\t\ticon = {{ size = {{ 20 20 }} parentanchor = center texture = \"{FLAT.format(icon)}\" using = button_regular_icon_color }}\n"
        "\t\t\t\t}\n"
    )


def _tile(plan, tab: str) -> str:
    """A held plan (datacontext Location): pressed with the gold glow; a click takes the plan off (pp_tplan_toggle)."""
    from prosper_or_perish_constructor import location_plan as lp

    on = lp.held(plan)
    return (
        f"{tab}widget = {{\n{tab}\tvisible = \"[{on}]\"\n{tab}\tsize = {{ {TILE_WIDTH} 34 }}\n"
        f"{tab}\tbutton = {{\n"
        f"{tab}\t\tusing = header_button_template\n"
        f"{tab}\t\tblockoverride \"header_button_template_push_properties\" {{ using = button_tab_toggle_properties_template }}\n"
        f"{tab}\t\tblockoverride \"header_button_template_texture\" {{ using = pressed_button_texture }}\n"
        f"{tab}\t\tblockoverride \"header_button_full_content\" {{}}\n"
        f"{tab}\t\tsize = {{ 34 34 }}\n"
        f"{tab}\t\tdown = yes\n"
        f"{tab}\t\tglow = {{ glow_radius = 5 color = {{ 1.0 0.85 0.55 1.0 }} alpha = 0.8 }}\n"
        f"{tab}\t\ttooltip = \"{plan.tooltip}\"\n"
        f"{tab}\t\tonclick = \"{lp.toggle_call(plan)}\"\n"
        f"{tab}\t\ticon = {{ size = {{ 26 26 }} parentanchor = center texture = \"{plan.icon}\" }}\n"
        f"{tab}\t}}\n{tab}}}\n"
    )


def render_row(plans: list) -> str:
    """The Plans row's type (datacontext Location), styled like the Infrastructure tab's other rows: a paper card in a
    wooden frame, the plan icon in the header strip, the held plans as pressed tiles in one line (ROW_TILES wide and cut
    there), and the button that opens the Location Plan window. ``plans``: the plannable plans (location_plan.Plan)."""
    from prosper_or_perish_constructor import location_plan as lp

    tab = "\t\t\t\t\t\t\t"
    none = value_is("Location.MakeScope", lp.COUNT, 0)
    cut = value_above("Location.MakeScope", lp.COUNT, ROW_TILES)
    out = [
        "\n\t# The Plans row of the location window's Infrastructure tab (datacontext Location): the location's plans\n"
        "\t# (town rights) as pressed tiles, a click takes one off; the round button opens the Location Plan window.\n"
        f"\ttype {ROW_TYPE} = hbox {{\n"
        "\t\tlayoutpolicy_horizontal = expanding\n\t\tminimumsize = { -1 45 }\n\t\tmargin = { 5 5 }\n"
        "\t\tusing = bg_paper_card\n\t\tusing = bg_cabinet_card_frame\n"
        "\t\twidget = {\n\t\t\tsize = { 40 -1 }\n\t\t\tlayoutpolicy_vertical = expanding\n"
        "\t\t\tusing = bg_card_header_01\n"
        f"\t\t\ticon = {{ size = {{ 28 28 }} parentanchor = center texture = \"{PLAN_ICON}\" }}\n\t\t}}\n"
        "\t\thbox = {\n\t\t\tlayoutpolicy_horizontal = expanding\n\t\t\tlayoutpolicy_vertical = expanding\n"
        "\t\t\tmargin = { 5 0 }\n\t\t\tmargin_right = 2\n\t\t\tspacing = 4\n"
        + _CARD_FLAVOR
        + "\t\t\tvbox = {\n\t\t\t\tlayoutpolicy_horizontal = expanding\n\t\t\t\tmargin_top = 3\n\t\t\t\tmargin_bottom = 3\n"
        "\t\t\t\tspacing = 3\n"
        "\t\t\t\thbox = {\n\t\t\t\t\tlayoutpolicy_horizontal = expanding\n\t\t\t\t\tspacing = 5\n"
        "\t\t\t\t\ttext_single = { text = \"PP_TPLAN_ROW_TITLE\" align = left|nobaseline }\n"
        f"\t\t\t\t\ttext_single = {{ visible = \"[{none}]\" text = \"PP_TPLAN_ROW_NONE\" "
        "align = left|nobaseline default_format = \"#medium\" }\n"
        f"\t\t\t\t\ttext_single = {{ visible = \"[{cut}]\" text = \"PP_TPLAN_ROW_COUNT\" "
        "align = left|nobaseline default_format = \"#medium\" }\n"
        "\t\t\t\t\texpand = {}\n\t\t\t\t}\n"
        # the line: ROW_TILES tiles wide and cut there (vanilla's scissor), at the left under the title
        "\t\t\t\thbox = {\n\t\t\t\t\tlayoutpolicy_horizontal = expanding\n"
        f"\t\t\t\t\twidget = {{\n\t\t\t\t\t\tsize = {{ {ROW_TILES * TILE_WIDTH} 34 }}\n\t\t\t\t\t\tscissor = yes\n"
        "\t\t\t\t\t\tflowcontainer = {\n\t\t\t\t\t\t\tdirection = horizontal\n\t\t\t\t\t\t\tignoreinvisible = yes\n",
    ]
    out += [_tile(plan, tab) for plan in plans]
    out.append(
        "\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t\texpand = {}\n\t\t\t\t}\n\t\t\t}\n"
        "\t\t\tvbox = {\n\t\t\t\tlayoutpolicy_vertical = expanding\n\t\t\t\tmargin = { 0 5 }\n\t\t\t\tspacing = 3\n"
        + _card_button("PP_TPLAN_ROW_MORE_TT", OPEN_PLAN, "plus")
        + "\t\t\t\texpand = {}\n\t\t\t}\n\t\t}\n\t}\n"
    )
    return "".join(out)


def add_plan_row(text: str) -> str:
    """The location window's Infrastructure tab starts with the Plans row; player-owned locations, not observers."""
    if ROW_MARK in text:
        return text
    if text.count(_INFRA_ANCHOR) != 1:
        raise ValueError("location window: the Infrastructure tab's hub comment not found once")
    at = text.index(_INFRA_ANCHOR)
    line_start = text.rindex("\n", 0, at) + 1
    tab = text[line_start:at]
    row = (
        f"{tab}vbox = {{ {ROW_MARK}\n"
        f"{tab}\tvisible = \"[{VISIBLE}]\"\n"
        f"{tab}\tlayoutpolicy_horizontal = expanding\n"
        f"{tab}\tdatacontext = \"[LocationView.GetLocation]\"\n"
        f"{tab}\t{ROW_TYPE} = {{}}\n"
        f"{tab}}}\n"
    )
    return text[:line_start] + row + text[line_start:]
