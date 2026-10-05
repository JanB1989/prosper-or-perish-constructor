"""The location view: the main mod's location window and the geography chips' tooltips (view only).

The window is the World Builder export's (vanilla plus its native geography chips), re-patched with the mod's
stored-food gauge, population-capacity readout, Water Access and Port chips, RGO and land-potential chips, the status
chips (location_status.py) and the condition icons moved to the top left. The chip tooltips (attribute_tooltips.py)
read back the class injects and static modifiers the World Builder stage writes.

Nothing here changes a game value, so it runs in the constructor's finalize step (every ``ppc build`` and ``ppc sync``)
and not in the World Builder stage: a GUI edit no longer reruns the start setup. Its inputs are files already on disk
after the stage (the export, the mod's static modifiers and harvest files, vanilla).
"""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import attribute_tooltips, location_status
from prosper_or_perish_constructor.worldbuilder.geography import EXPORT_BUILD_FILE, LOCATION_WINDOW

_FOOD_PERCENT = 'value = "[FixedPointToFloat(Province.GetFoodCapacityPercent)]"'
_FOOD_PERCENT_REST = 'value = "[Subtract_float(\'(float)100.0\', FixedPointToFloat(Province.GetFoodCapacityPercent))]"'
_FOOD_SCOPES = ("LocationView", "LocationViewSelectProvince.Parent")


def merge_location_window(text: str) -> str:
    """Re-apply the mod's stored-food gauge on the World Builder location window.

    The World Builder file is vanilla plus its native geography view; the mod replaces the vanilla
    province food-capacity gauge (two pairs of lines: the location view and the province selector) with
    the stored-food months, the location-scope script value `pp_province_food_storage_months` (a CFixedPoint,
    hence the _CFixedPoint arithmetic). The divisor is compiled afterwards by the food-storage GUI step, which
    expects exactly these four lines.
    """
    lines = text.splitlines(keepends=True)
    pair = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == _FOOD_PERCENT:
            scope = _FOOD_SCOPES[min(pair // 2, 1)]
            lines[index] = line.replace(_FOOD_PERCENT, f"value = \"[FixedPointToFloat(Divide_CFixedPoint({scope}.GetLocation.MakeScope.ScriptValue('pp_province_food_storage_months'), '(CFixedPoint)24'))]\"")
            pair += 1
        elif stripped == _FOOD_PERCENT_REST:
            scope = _FOOD_SCOPES[min((pair - 1) // 2, 1)]
            lines[index] = line.replace(_FOOD_PERCENT_REST, f"value = \"[Subtract_float('(float)1.0', FixedPointToFloat(Divide_CFixedPoint({scope}.GetLocation.MakeScope.ScriptValue('pp_province_food_storage_months'), '(CFixedPoint)24')))]\"")
            pair += 1
    if pair != 4:
        raise ValueError(f"location_window.gui: expected 4 vanilla food-capacity gauge lines, found {pair}")
    return add_attribute_effect_rows("".join(lines))


_LOC = "LocationView.GetLocation"
# vanilla tooltip template of each chip -> the mod's copy with the goods output split off (attribute_tooltips.py)
CLASS_TOOLTIPS = {
    "Topography_tooltip": "pp_attribute_tooltip_topography", "Climate_tooltip": "pp_attribute_tooltip_climate",
    "Vegetation_tooltip": "pp_attribute_tooltip_vegetation", "location_winter_tooltip": "pp_attribute_tooltip_winter",
}


def _effect_row(modifier: str, visible: str) -> str:
    return f'TooltipStringPairList = {{ visible = "[{visible}]" textcontext = "[ShowModifierEffect(\'{modifier}\')]" }}'


def add_attribute_effect_rows(text: str) -> str:
    """Every geography chip shows its attribute's effects first and its goods output as an icon table after.

    The views are generated later in the chain (attribute_tooltips.py, after the modifiers they read are written), so
    the chips only name them: the class and winter chips use the mod's copy of the vanilla template, the fertility,
    soil, lake and coast chips get the attribute's view type, which holds every class behind a test on the location's
    class.
    """
    for vanilla, mod in CLASS_TOOLTIPS.items():
        pattern = re.compile(rf"using = {vanilla}\b")
        found = len(pattern.findall(text))
        if found != 1:
            raise ValueError(f"location_window.gui: expected 1 chip using {vanilla}, found {found}")
        text = pattern.sub(f"using = {mod}", text)
    fert_line = f'blockoverride "tooltip_content" {{ TooltipFlavorTextBlock = {{ blockoverride "text" {{ text = "[{_LOC}.Custom(\'ha1300_fertility_desc\')]" }} }} }}'
    soil_line = f'blockoverride "tooltip_content" {{ TooltipFlavorTextBlock = {{ blockoverride "text" {{ text = "[{_LOC}.Custom(\'ha1300_soil_type_description\')]" }} }} }}'
    lake_line = 'blockoverride "tooltip_content" { TooltipTextBlock = { blockoverride "text" { text = "HA1300_LAKE_HELP" } } }'
    coast_anchor = "textcontext = \"[ShowModifierEffect('coastal')]\"\n    } }"
    text = text.replace(fert_line, fert_line[:-1] + "pp_attribute_view_fertility = {} }")
    text = text.replace(soil_line, soil_line[:-1] + "pp_attribute_view_soil = {} }")
    text = text.replace(lake_line, lake_line[:-1] + "pp_attribute_view_lake = {} }")
    text = text.replace(coast_anchor, coast_anchor[:-1] + "pp_attribute_view_coast = {} }")
    return text


RGO_BONUSES = "in_game/common/static_modifiers/pp_rgo_static_bonuses.txt"
_RGO_ANCHOR = "### IS BLOCKADED by ice\n"
_RGO = f"{_LOC}.GetRawMaterial"
_RGO_CHIP = """widget = {
        name = "pp_rgo_chip"
        size = { 30 30 }
        visible = "[__LOC__.HasRawMaterial]"
        datacontext = "[__RGO__]"
        tooltipwidget = {
        ContextualTooltipType = {
            blockoverride "title_text" { text = "[__RGO__.GetNameWithNoTooltip]" }
            blockoverride "concept_link" { visible = yes text = "[rgo|E]" }
            blockoverride "title_icon" {
                widget = {
                    using = tooltip_title_icon_size
                    background = { texture = "[GetClimateFrame(__LOC__.GetClimate)]" }
                    icon = { using = tooltip_title_icon_size texture = "[GetGoodsIcon(__RGO__)]" }
                }
            }
            blockoverride "title_button" { mapmode_tooltip_button = { datacontext = "[GetMapMode('raw_material')]" } }
            blockoverride "tooltip_content" { TooltipTextBlock = { blockoverride "text" { text = "PP_RGO_CHIP_HELP" } } __ROWS__ }
        }
    }
        background = { texture = "[GetClimateFrame(__LOC__.GetClimate)]" }
        icon = { size = { 24 24 } parentanchor = center texture = "[GetGoodsIcon(__RGO__)]" }
    }
"""


def rgo_bonus_goods(text: str) -> list[str]:
    """Goods with a `pp_rgo_bonus_<good>` static modifier, in file order."""
    return re.findall(r"^pp_rgo_bonus_(\w+)\s*=\s*\{", text, flags=re.MULTILINE)


def add_rgo_chip(text: str, goods: list[str]) -> str:
    """Append the location's raw material to the geography chips, listing the effects of its RGO bonus.

    The bonus is a static modifier per good, so every good gets a row that is only visible for its own raw material.
    """
    if not goods:
        return text
    found = text.count(_RGO_ANCHOR)
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 geography-row anchor for the RGO chip, found {found}")
    rows = " ".join(_effect_row(f"pp_rgo_bonus_{good}", f"EqualTo_string({_RGO}.GetKey, '{good}')") for good in goods)
    chip = _RGO_CHIP.replace("__RGO__", _RGO).replace("__LOC__", _LOC).replace("__ROWS__", rows)
    return text.replace(_RGO_ANCHOR, chip + _RGO_ANCHOR)


def add_land_potential_chip(text: str) -> str:
    """Close the geography chips with the land potential: every good's output from the land attributes, best first.

    The chip is a generated type (attribute_tooltips.py), so only its name goes into the window."""
    found = text.count(_RGO_ANCHOR)
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 geography-row anchor for the land-potential chip, found {found}")
    return text.replace(_RGO_ANCHOR, "pp_land_potential_chip = {}\n" + _RGO_ANCHOR)


MODIFIER_ROW = "pp_location_modifier_row"
_CONDITIONS = "# BOTTOM CONDITIONS\n"
_SCENE_ROWS = "# IOs & PERIPHORA\n"
_FIRST_MODIFIER = "# SOUND TOLL\n"
_MODIFIER_ROW_FRAME = f"""name = "{MODIFIER_ROW}"
	parentanchor = top|left
	size = {{ 100% 40 }}
	background = {{
		using = color_dark_blue_texture
		alpha = 0.8
		modify_texture = {{
			using = bg_fade_vertical_down_mask_texture
			blend_mode = alphamultiply
			alpha = 1
		}}
	}}"""


def move_modifier_row(text: str) -> str:
    """Move the vanilla condition icons (winter, disease, location and province modifiers, ...) to the top left of the scene.

    Vanilla draws them in the bottom row after the geography card, which the native chips fill: in a location with every
    chip the last icons (the province modifiers, Stored Food among them) ran past the window's edge. The row keeps its
    vanilla icons and tooltips and becomes a widget pinned to the scene's top-left corner (the top-right corner holds the
    owner's construction queue buttons).
    """
    found = text.count(_CONDITIONS)
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 bottom-conditions anchor for the modifier row, found {found}")
    conditions = text.index(_CONDITIONS)
    first = text.find(_FIRST_MODIFIER, conditions)
    start = text.rfind("widget = {", conditions, first)
    if first < 0 or start < 0:
        raise ValueError("location_window.gui: expected the condition icons' widget after the bottom-conditions anchor")
    end = _block_end(text, text.index("{", start))
    row = text[start:end]
    if row.count("using = layoutpolicy_expanding") < 1 or row.index("using = layoutpolicy_expanding") > row.index(_FIRST_MODIFIER):
        raise ValueError("location_window.gui: the condition icons' widget no longer opens with layoutpolicy_expanding")
    line_start = text.rfind("\n", 0, start) + 1
    text = text[:line_start] + text[end + 1 if text[end:end + 1] == "\n" else end:]

    scene = text.rfind("vbox = {", 0, text.rfind(_SCENE_ROWS, 0, conditions))
    scene_end = _block_end(text, text.index("{", scene))
    if not scene < conditions < scene_end:
        raise ValueError("location_window.gui: expected the bottom conditions inside the scene's row stack")
    indent = text[text.rfind("\n", 0, scene) + 1:scene]
    policy = row.index("using = layoutpolicy_expanding")
    inner = row[row.rfind("\n", 0, policy) + 1:policy]
    row = row.replace("using = layoutpolicy_expanding", _MODIFIER_ROW_FRAME.replace("\n\t", "\n" + inner), 1)
    comment = f"\n{indent}# PP: the condition icons at the top left (the bottom row is full with the geography chips)\n{indent}"
    return text[:scene_end] + comment + row + text[scene_end:]


_TIMED_MODIFIERS = (("# Location timed modifiers\n", "location_modifier"), ("# Province timed modifiers\n", "province_modifier"))
_TIMED_MODIFIER_ICONS = """hbox = {{
	# PP: every modifier as its own icon (vanilla: one icon, or a count whose tooltip lists them)
	spacing = 7
	visible = "[DataModelHasItems({model})]"
	datamodel = "[{model}]"
	item = {{
		timed_modifier_icon = {{
			datacontext = "[TimedModifier]"{visible}
			tooltipwidget = {{
				using = timed_modifier_tooltip
				blockoverride "concept_link" {{
					text = "[{concept}|e]"
				}}
			}}
		}}
	}}
}}"""


def show_every_timed_modifier(text: str, hidden: dict[str, str] | None = None) -> str:
    """Show each location and province modifier as its own icon in the condition row.

    Vanilla draws a single modifier's icon, but two or more only as a count with a generic icon (the modifiers listed in
    its tooltip). The condition row at the top of the scene has room for every icon, each with its own tooltip.
    ``hidden`` maps a concept (location_modifier, province_modifier) to a GUI test on ``TimedModifier``: the modifiers a
    chip of the bottom row already shows (``shown_by_chips``) get no icon of their own.
    """
    for anchor, concept in _TIMED_MODIFIERS:
        found = text.count(anchor)
        if found != 1:
            raise ValueError(f"location_window.gui: expected 1 '{anchor.strip()}' widget in the condition row, found {found}")
        after = text.index(anchor) + len(anchor)
        start = text.find("widget = {", after)
        if start < 0 or text[after:start].strip():
            raise ValueError(f"location_window.gui: expected a widget right after '{anchor.strip()}'")
        end = _block_end(text, text.index("{", start))
        block = text[start:end]
        model = re.search(r'datamodel = "\[([\w.]+\.GetTimedModifiers)\]"', block)
        if model is None or f"[{concept}|e]" not in block:
            raise ValueError(f"location_window.gui: '{anchor.strip()}' no longer lists {concept} timed modifiers")
        indent = text[text.rfind("\n", 0, start) + 1:start]
        test = (hidden or {}).get(concept)
        visible = f'\n\t\t\tvisible = "[Not({test})]"' if test else ""
        icons = _TIMED_MODIFIER_ICONS.format(model=model.group(1), concept=concept, visible=visible).replace("\n", "\n" + indent)
        text = text[:start] + icons + text[end:]
    return text


_NAME = "TimedModifier.GetModifier.GetName"
WB_CHIP_MODIFIERS = re.compile(r"^(pp_wb_(?:fertility|soil)_\w+|pp_wb_coastal|pp_wb_lake)\s*=\s*\{", re.M)
RIVER_MODIFIERS = re.compile(r"^(river_flowing_through_\w+)\s*=\s*\{", re.M)
_STATIC_NAME = re.compile(r'^\s*STATIC_MODIFIER_NAME_(\w+):\d*\s*"(.*)"\s*$', re.M)
STORED_FOOD_STEP = "pp_food_store_0"   # every step carries the name Stored Food
CHIP_KEY_PREFIXES = ("pp_wb_", "river_flowing_through", "pp_rgo_bonus_", "pp_harvest_")


def _any(tests: list[str]) -> str:
    out = tests[-1]
    for test in reversed(tests[:-1]):
        out = f"Or({test}, {out})"
    return out


def _static_names(roots: list[Path]) -> dict[str, str]:
    """Display name of every static modifier in the English localization of ``roots`` (later roots win)."""
    names: dict[str, str] = {}
    for root in roots:
        for path in sorted((root / "main_menu/localization/english").rglob("*.yml")):
            names.update(_STATIC_NAME.findall(path.read_text(encoding="utf-8-sig", errors="replace")))
    return names


def shown_by_chips(mod_root: Path, vanilla: Path | None, goods: list[str], harvests: bool) -> dict[str, str]:
    """GUI tests for the location and province modifiers a chip of the bottom row already shows.

    The fertility, soil, water access and lake chips show the World Builder modifiers, the river chip vanilla's river
    modifiers (RiverModifier_tooltip), the RGO chip the raw material bonus, the harvest chip the location's harvest and
    the Stored Food chip the province's step. A GUI icon cannot see a modifier's key, so the test looks for its name: one
    test per distinct name, the harvest against the harvest chip's own text (one test for the ~100 harvests; its
    fallback, Average Harvest, is never empty). The tests are ``StringContains``, not equality: in game (2026-10-05,
    b921e221) ``DatabaseModifier.GetName`` never equalled the localized name, not even for plain names such as High
    Fertility, so it carries more than the bare text. The key prefixes are tested too, in case it is the key.
    """
    game = None if vanilla is None else (vanilla / "game" if (vanilla / "game" / "main_menu").is_dir() else vanilla)
    keys = WB_CHIP_MODIFIERS.findall(_read(mod_root / "main_menu/common/static_modifiers/pp_wb_attribute_modifiers.txt"))
    if game is not None:
        keys += RIVER_MODIFIERS.findall(_read(game / "main_menu/common/static_modifiers/location.txt"))
    keys += [f"pp_rgo_bonus_{good}" for good in goods]
    names = _static_names([root for root in (game, mod_root) if root is not None])
    seen: set[str] = set()
    tests = [f"StringContains({_NAME}, {_LOC}.Custom('pp_harvest_state'))"] if harvests else []
    for key in keys:
        name = names.get(key, key)
        if name not in seen:
            seen.add(name)
            tests.append(f"StringContains({_NAME}, Localize('STATIC_MODIFIER_NAME_{key}'))")
    tests += [f"StringContains({_NAME}, '{prefix}')" for prefix in CHIP_KEY_PREFIXES]
    stored = [f"StringContains({_NAME}, Localize('STATIC_MODIFIER_NAME_{STORED_FOOD_STEP}'))",
              f"StringContains({_NAME}, 'pp_food_store_')"]
    return {"location_modifier": _any(tests), "province_modifier": _any(stored)}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


# EU5 1.4 builds the population cell of `location_card` and of the location view header from one template;
# the header overrides its size, text format and gauge. The mod changes the location card's cell only, so it
# draws a pp_ copy of the template (a template another mod re-declares under the vanilla name cannot undo it).
_POP_TEMPLATE = "location_card_population_button_body"
PP_POP_TEMPLATE = "pp_" + _POP_TEMPLATE
_POP_CELL = re.compile(r'(block "location_card_population_size" \{\s*size = \{ )120( 28 \})')
# Only one of the four gauges is ever visible; the cell is 28px tall and cannot afford to reserve
# space for the hidden three.
_POP_VBOX = re.compile(r"(?m)^([ \t]*)margin_right = 8\n[ \t]*margin_bottom = 3\n")
# raw_text, not a localization key: it is evaluated against the widget's own datacontext, which is
# how vanilla wrote this cell. A `text = "KEY"` here resolved to nothing in game.
_POP_TEXT = re.compile(
    r'(visible = "\[HasPopBreakdownIntelOn\(Location\.Self\)\]"\s*)raw_text = "\[Location\.GetTotalPopulation\]@population!"'
    r'(\s*block "location_card_population_text_format" \{\}\s*)fontsize = 13'
)
_POP_TEXT_RATIO = (
    r'\g<1>raw_text = "[Location.GetTotalPopulation]/[Location.GetPopulationCapacity] · [Location.GetCapacityPercentage|0]%"'
    r"\g<2>fontsize = 12"
)
_CAPACITY_BAR = re.compile(
    r'(?m)^([ \t]*)progressbar = \{\s*layoutpolicy_horizontal = expanding\s*size = \{ -1 5 \}\s*'
    r'visible = "\[HasPopBreakdownIntelOn\(Location\.Self\)\]"\s*using = progress_bar_green_alt\s*'
    r'value = "\[Location\.GetCapacityPercentage\]"\s*direction = horizontal\s*\}'
)
_CAPACITY_BAND_BAR = """progressbar = {
\tname = "pp_pop_capacity_bar___NAME__"
\tlayoutpolicy_horizontal = expanding
\tsize = { -1 5 }
\tvisible = "[__VISIBLE__]"
\tprogresstexture = "gfx/interface/progressbars/__TEXTURE__.dds"
\tnoprogresstexture = "gfx/interface/progressbars/progress_black.dds"
\ttexture_density = 2
\tspriteType = Corneredstretched
\tspriteborder = { 12 0 }
\tmin = 0
\tmax = 100
\tvalue = "[Location.GetCapacityPercentage]"
\tdirection = horizontal
}"""
# GetCapacityPercentage is 0..100, not the 0..1 a progressbar expects. Vanilla feeds it straight to
# a bar with no min/max, which is why the vanilla gauge sits full at every fill; min/max restate the
# real range instead of rescaling the value, so no arithmetic is needed.
#
# Headroom, not fill: green while the location can still grow, red only once it is at or over
# capacity, where growth stalls and pops starve or leave. Bands are half-open, so exactly one bar is
# visible at any fill.
_CAPACITY_BANDS = (
    ("green", "progress_bar_green_alt", None, "70"),
    ("yellow", "progress_bar_yellow", "70", "90"),
    ("orange", "progress_bar_orange", "90", "100"),
    ("red", "progress_bar_red_alt", "100", None),
)
_CAPACITY_PERCENT = "Location.GetCapacityPercentage"


def _capacity_band_bar(name: str, texture: str, low: str | None, high: str | None, indent: str = "") -> str:
    tests = ["HasPopBreakdownIntelOn(Location.Self)"]
    if low is not None:
        tests.append(f"GreaterThanOrEqualTo_float({_CAPACITY_PERCENT}, '(float){low}')")
    if high is not None:
        tests.append(f"LessThan_float({_CAPACITY_PERCENT}, '(float){high}')")
    joined = ", ".join(tests)
    visible = f"And3({joined})" if len(tests) == 3 else f"And({joined})"
    bar = (
        _CAPACITY_BAND_BAR.replace("__NAME__", name)
        .replace("__VISIBLE__", visible)
        .replace("__TEXTURE__", texture)
    )
    return "\n".join(indent + line for line in bar.splitlines())


def _block_end(text: str, open_brace: int) -> int:
    """Index just past the brace matching ``text[open_brace]``; braces in comments and strings are ignored."""
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
    raise ValueError("location_window.gui: unbalanced block")


def _sub_once(pattern: re.Pattern[str], repl, text: str) -> str:
    text, found = pattern.subn(repl, text)
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 population-cell anchor, found {found}")
    return text


def merge_population_capacity(text: str) -> str:
    """Make population capacity readable in the location card.

    Vanilla shows the population alone above a single green gauge, so a location that is full looks
    like one with room to grow. Capacity is this mod's core constraint, so the cell states population,
    capacity and fill, and the gauge is banded by remaining headroom. The engine clamps the gauge at
    full, which is what we want above capacity: the red band says "over" and the percentage states how
    far over, which a rescaled gauge could only show by giving up resolution below capacity.

    The cell is the template ``location_card_population_button_body`` (EU5 1.4). It is copied as
    ``pp_location_card_population_button_body``, the copy is changed, and only ``type location_card`` switches
    to it; the location view header keeps the vanilla cell, as before 1.4.
    """
    starts = list(re.finditer(rf"(?m)^template[ \t]+{_POP_TEMPLATE}[ \t]*\{{", text))
    if len(starts) != 1 or re.search(rf"\btemplate[ \t]+{PP_POP_TEMPLATE}\b", text):
        hint = "" if starts else " (a window from before EU5 1.4: rebuild the World Builder export, `uv run worldbuilder geography-test --build-only`)"
        raise ValueError(f"location_window.gui: expected 1 population-cell anchor, found {len(starts)}{hint}")
    start = starts[0].start()
    end = _block_end(text, text.index("{", start))
    cell = text[start:end].replace(f"template {_POP_TEMPLATE}", f"template {PP_POP_TEMPLATE}", 1)
    cell = _sub_once(_POP_CELL, r"\g<1>139\g<2>", cell)
    cell = _sub_once(_POP_VBOX, lambda m: m.group(0) + f"{m.group(1)}ignoreinvisible = yes\n", cell)
    cell = _sub_once(_POP_TEXT, _POP_TEXT_RATIO, cell)
    cell = _sub_once(
        _CAPACITY_BAR,
        lambda m: "\n\n".join(_capacity_band_bar(*band, indent=m.group(1)) for band in _CAPACITY_BANDS),
        cell,
    )
    text = text[:end] + "\n\n" + cell + text[end:]

    card = re.search(r"(?m)^[ \t]*type[ \t]+location_card[ \t]*=[ \t]*\w+[ \t]*\{", text)
    if not card:
        raise ValueError("location_window.gui: expected 1 population-cell anchor, found 0")
    card_end = _block_end(text, text.index("{", card.start()))
    body = _sub_once(re.compile(rf"using = {_POP_TEMPLATE}\b"), f"using = {PP_POP_TEMPLATE}", text[card.start():card_end])
    return text[: card.start()] + body + text[card_end:]


# --- the Water Access and Port chips (water access states: worldbuilder/coast.py) -------------------------------

_FRAME = f'background = {{ texture = "[GetClimateFrame({_LOC}.GetClimate)]" }}'
SEA_ICON = "gfx/interface/icons/location_icons/coastal.dds"
WATERWAY_ICON = "gfx/interface/topography/pp_river_channel.dds"
INLAND_ICON = "gfx/interface/icons/location_icons/inland.dds"
PORT_ICON = "gfx/interface/icons/modifier_types/natural_harbor_suitability.dds"
IS_SEA = f"EqualTo_string({_LOC}.Custom('pp_water_access'), Localize('PP_WATER_SEA_COAST'))"
IS_WATERWAY = f"EqualTo_string({_LOC}.Custom('pp_water_access'), Localize('PP_WATER_WATERWAY'))"
IS_INLAND = f"EqualTo_string({_LOC}.Custom('pp_water_access'), Localize('PP_WATER_INLAND'))"
ALSO_RIVER = f"EqualTo_string({_LOC}.Custom('pp_water_access_river_note'), Localize('PP_WATER_ALSO_RIVER'))"
_COAST_CHIP = re.compile(r'widget = \{\s*name = "ha1300_native_coast".*?(?=widget = \{\s*name = "ha1300_native_river")', re.S)
# vanilla's natural harbour pie next to the river and sound toll icons; the Port chip carries its tooltip now
_HARBOR_PIE = re.compile(r'# NATURAL HABOUR\s*widget = \{.*?(?=# (?:RIVER MODIFIER|SOUND TOLL))', re.S)
_SOIL_CHIP = 'widget = { name = "ha1300_native_soil"'
# vanilla's natural harbour ring around the Port icon on the coast: green = harbour suitability, red = the rest
_SUITABILITY = f"FixedPointToFloat({_LOC}.GetModifierValueFixed('harbor_suitability'))"
_PIE = "gfx/interface/pie_charts/pie_chart_alpha_80.dds"
_HARBOR_RING = (
    f'piechart = {{ name = "pp_port_harbor_ring" visible = "[{_LOC}.IsCoastal]" size = {{ 100% 100% }} parentanchor = center '
    f"using = bg_circle using = piechart_angles using = bg_circle_piechart "
    f'icon = {{ texture = "{_PIE}" size = {{ 97% 97% }} parentanchor = center color = {{ 0 0 0 1 }} }} '
    f'pieslice_no_highlight = {{ texture = "{_PIE}" value = "[{_SUITABILITY}]" color = {{ 0.3 0.8 0.3 1 }} alpha = 0.8 }} '
    f'pieslice_no_highlight = {{ texture = "{_PIE}" value = "[Max_float(Subtract_float(\'(float)1.0\', {_SUITABILITY}), \'(float)0\')]" '
    f"color = {{ 0.8 0.3 0.3 1 }} alpha = 0.8 }} }}"
)


def _icons(size: str, extra: str = "") -> str:
    return " ".join(f'icon = {{ {size} texture = "{tex}" visible = "[{gate}]" {extra}}}'
                    for tex, gate in ((SEA_ICON, IS_SEA), (WATERWAY_ICON, IS_WATERWAY), (INLAND_ICON, IS_INLAND)))


def water_access_chip() -> str:
    return f'''widget = {{
        name = "pp_water_access"
        size = {{ 30 30 }}
        datacontext = "[{_LOC}]"
        tooltipwidget = {{
        ContextualTooltipType = {{
            blockoverride "title_text" {{ text = "[{_LOC}.Custom('pp_water_access')]" }}
            blockoverride "concept_link" {{ visible = yes text = "[coastal|E]" }}
            blockoverride "title_icon" {{
                widget = {{ using = tooltip_title_icon_size {_FRAME} {_icons("using = tooltip_title_icon_size")} }}
            }}
            blockoverride "tooltip_content" {{
                TooltipTextBlock = {{ blockoverride "text" {{ text = "[{_LOC}.Custom('pp_water_access_help')]" }} }}
                TooltipTextBlock = {{ visible = "[{ALSO_RIVER}]" blockoverride "text" {{ text = "PP_WATER_ALSO_RIVER" }} }}
                TooltipStringPairList = {{ visible = "[{_LOC}.IsCoastal]" textcontext = "[ShowModifierEffect('coastal')]" }}
                pp_attribute_view_coast = {{}}
            }}
        }}
    }}
        {_FRAME}
        {_icons("size = { 30 30 }")}
    }}
widget = {{
        name = "pp_port"
        size = {{ 30 30 }}
        datacontext = "[{_LOC}]"
        tooltipwidget = {{
        ContextualTooltipType = {{
            blockoverride "title_text" {{ text = "[SelectLocalization({_LOC}.HasPort, 'PP_PORT', 'PP_NO_PORT')]" }}
            blockoverride "concept_link" {{ visible = yes text = "[port|E]" }}
            blockoverride "title_icon" {{
                widget = {{ using = tooltip_title_icon_size {_FRAME} icon = {{ using = tooltip_title_icon_size texture = "{PORT_ICON}" }} }}
            }}
            blockoverride "title_button" {{
                mapmode_tooltip_button = {{ datacontext = "[GetMapMode('natural_harbor_suitability')]" }}
            }}
            blockoverride "tooltip_content" {{
                TooltipTextBlock = {{ blockoverride "text" {{ text = "[SelectLocalization({_LOC}.HasPort, 'PP_PORT_HELP', 'PP_NO_PORT_HELP')]" }} }}
                TooltipTextBlock = {{ visible = "[{_LOC}.IsCoastal]" blockoverride "text" {{ text = "PP_PORT_HARBOR" }} }}
                TooltipStringPairList = {{
                    visible = "[{_LOC}.IsCoastal]"
                    blockoverride "block_title" {{ text = "HARBOR_SUITABILITY_DESC" }}
                    textcontext = "[Location.GetDescriptionFor('harbor_suitability')]"
                }}
                TooltipStringPairList = {{
                    visible = "[{_LOC}.IsCoastal]"
                    blockoverride "block_title" {{ text = "HARBOR_SUITABILITY_IMPACT" }}
                    textcontext = "[Location.GetHarborCapacityImpactInfo]"
                }}
            }}
        }}
    }}
        {_FRAME}
        {_HARBOR_RING}
        icon = {{ size = {{ 20 20 }} parentanchor = center texture = "{PORT_ICON}" visible = "[And({_LOC}.IsCoastal, {_LOC}.HasPort)]" }}
        icon = {{ size = {{ 20 20 }} parentanchor = center texture = "{PORT_ICON}" alpha = 0.4 visible = "[And({_LOC}.IsCoastal, Not({_LOC}.HasPort))]" }}
        icon = {{ size = {{ 30 30 }} texture = "{PORT_ICON}" alpha = 0.3 visible = "[Not({_LOC}.IsCoastal)]" }}
    }}
'''


def water_access_chips(text: str) -> str:
    """Replace the World Builder's coast chip (engine is_coastal: Coastal / Inland) by the Water Access chip (Inland /
    Waterway / Sea Coast) and a Port chip; both sit after the river and lake chips. Vanilla's natural harbour pie goes:
    the Port chip's tooltip carries the harbour suitability, harbour capacity and its effects."""
    found = len(_COAST_CHIP.findall(text))
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 World Builder coast chip, found {found}")
    if text.count(_SOIL_CHIP) != 1:
        raise ValueError("location_window.gui: expected 1 soil chip anchor for the water access chips")
    pies = len(_HARBOR_PIE.findall(text))
    if pies != 1:
        raise ValueError(f"location_window.gui: expected 1 vanilla natural harbour widget, found {pies}")
    text = _HARBOR_PIE.sub("", _COAST_CHIP.sub("", text))
    return text.replace(_SOIL_CHIP, water_access_chip() + _SOIL_CHIP)


def build_window(export_text: str, mod_root: Path, vanilla: Path | None, stored_food: tuple[tuple[str, float], ...] = ()) -> str:
    """The mod's location window from the export's; writes the harvest chip's localization files on the way.

    ``stored_food`` is the Stored Food modifier's payload per stored year (``[stored_food.per_year]``); with it the
    Stored Food chip shows the province's step modifier.
    """
    bonuses = Path(mod_root) / RGO_BONUSES
    goods = rgo_bonus_goods(bonuses.read_text(encoding="utf-8-sig")) if bonuses.is_file() else []
    merged = add_land_potential_chip(add_rgo_chip(merge_population_capacity(water_access_chips(merge_location_window(export_text))), goods))
    harvests = location_status.load_harvests(mod_root)
    merged = location_status.add_status_row(merged, harvests, location_status.load_land_effect_rows(mod_root, vanilla),
                                            location_status.load_stored_food_rows(mod_root, vanilla, stored_food))
    location_status.write_harvest_files(mod_root, harvests)
    return show_every_timed_modifier(move_modifier_row(merged), shown_by_chips(mod_root, vanilla, goods, bool(harvests.keys)))


def apply(repo: Path, project: Path, mod_root: Path, vanilla: Path) -> dict[str, object]:
    """Write the location window and the chip tooltips (``ppc build`` / ``ppc sync`` finalize).

    Skipped while ``[worldbuilder] sync_geography`` is off or the export is missing: the window then stays as it is.
    """
    from prosper_or_perish_constructor import stored_food
    from prosper_or_perish_constructor.worldbuilder.contract import load_config

    cfg = load_config(repo, project)
    export = Path(cfg.geography_export)
    if not cfg.sync_geography or not (export / EXPORT_BUILD_FILE).is_file():
        return {"skipped": True}
    window = build_window((export / LOCATION_WINDOW).read_text(encoding="utf-8-sig"), mod_root, vanilla,
                          stored_food.configured_payload(project))
    path = Path(mod_root) / LOCATION_WINDOW
    changed = not path.is_file() or path.read_text(encoding="utf-8-sig") != window
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\ufeff" + window, encoding="utf-8", newline="\n")
    return {"window_changed": changed, "attribute_tooltips": attribute_tooltips.write(mod_root, vanilla)}
