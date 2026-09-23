"""Status chips at the top right of the location view: stored food, land pressure and this year's harvest.

The geography chips at the bottom of the scene show what a location is; these show what is happening to it. Each chip
is a set of widgets, one per state, with exclusive visibility tests, like the soil and fertility chips.

How each state is read:
- food: the stored months come from `pp_province_food_storage_months`, which `positive_province_food_growth` carries;
  starvation is the engine's `Province.IsStarving`.
- land: the engine applies `abundant_free_land`, `available_free_land` and `overpopulation` itself, and scripts
  cannot see them, so each carries a marker modifier type (`pp_land_*`, in pp_capacity_pressure_effects.txt) that
  the GUI reads through `GetModifierValueFixed`. Its value is the modifier's strength, so the tooltip lists every
  effect at its actual value (strength times the base value read from the block at build time).
- harvest: the modifiers are script-applied, so customizable localizations test `has_location_modifier` and return
  the active modifier's display name (title and effect rows), its trend (the +/- badge) and its severity (tint and
  pips); a fourth tests region membership, so the chip shows the harvest region's crop in average years too.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

HARVEST_MODIFIERS = "in_game/common/static_modifiers/pp_variable_harvest_modifiers.txt"
HARVEST_EFFECTS = "in_game/common/scripted_effects/pp_variable_harvest_effects.txt"
HARVEST_NAMES = "main_menu/localization/english/pp_variable_harvest_modifiers_l_english.yml"
CUSTOM_LOCALIZATION = "in_game/common/customizable_localization/pp_location_status.txt"
HARVEST_LOCALIZATION = "main_menu/localization/english/pp_location_status_harvest_l_english.yml"
GOOD_HARVESTS = ("good", "very_good", "bountiful")
BAD_HARVESTS = ("abysmal", "very_poor", "poor")
# Severity at a glance: the tint behind the crop and 1-3 pips; yellow-orange-red for bad years, green-green-gold for good.
SEVERITY_STYLE = {
    "poor": ("mid_yellow", 1), "very_poor": ("mid_orange", 2), "abysmal": ("mid_red", 3),
    "good": ("mid_light_green", 1), "very_good": ("mid_green", 2), "bountiful": ("color_new_gold", 3),
}
# One recognisable crop per harvest region; plain wheat outside every harvest region.
REGION_GOODS = {
    "western_europe": "wine", "eastern_europe": "wheat", "north_asia": "wild_game", "central_asia": "cotton",
    "east_asia": "rice", "south_asia": "legumes", "south_east_asia": "sugar", "middle_east": "fruit",
    "north_africa": "olives", "west_africa": "millet", "east_africa": "coffee", "central_africa": "cocoa",
    "southern_africa": "livestock", "north_america": "maize", "south_america": "potato", "australasia": "wool",
    "pacific_islands": "fish",
}
LAND_MARKERS = ("pp_land_overpopulation", "pp_land_abundant", "pp_land_available")

_ANCHOR = "\t\t\t\t\t\t\texpand = {}\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t\t# BOTTOM CONDITIONS\n"
_SPLIT = len("\t\t\t\t\t\t\texpand = {}\n\t\t\t\t\t\t}\n")   # after the IO/periphora hbox, inside the row widget
# Three visible chips of 30 px, 5 px apart, inside the card's 10/8 px margins (the bottom card's sizes).
_CARD_SIZE = "{ 120 46 }"
_LOC = "LocationView.GetLocation"
_ICONS = "gfx/interface/icons"


def harvest_modifiers(text: str) -> list[str]:
    """`pp_harvest_<region>_<severity>` keys, in file order."""
    return re.findall(r"^(pp_harvest_\w+?_(?:%s))\s*=\s*\{" % "|".join(GOOD_HARVESTS + BAD_HARVESTS), text, flags=re.MULTILINE)


@dataclass(frozen=True)
class Harvests:
    keys: list[str] = field(default_factory=list)                  # pp_harvest_<region>_<severity>
    regions: dict[str, list[str]] = field(default_factory=dict)    # harvest region -> map regions it rolls for
    names: dict[str, str] = field(default_factory=dict)            # harvest region -> display name


def severity(key: str) -> str:
    return next(s for s in sorted(SEVERITY_STYLE, key=len, reverse=True) if key.endswith(f"_{s}"))


def _trend(key: str) -> str:
    return "good" if severity(key) in GOOD_HARVESTS else "bad"


def harvest_regions(effects_text: str) -> dict[str, list[str]]:
    """Harvest region -> the map regions whose harvest it rolls, from `region:<r> = { pp_roll_...{ subcontinent = <s> } }`."""
    regions: dict[str, list[str]] = {}
    for region, sub in re.findall(r"region:(\w+) = \{\s*pp_roll_region_harvest_for_\w+ = \{ subcontinent = (\w+) \}", effects_text):
        if region not in regions.setdefault(sub, []):
            regions[sub].append(region)
    return regions


def harvest_region_names(loc_text: str) -> dict[str, str]:
    """Display names from the generated modifier names ("Failed Harvest: Western Europe")."""
    return dict(re.findall(r'STATIC_MODIFIER_NAME_pp_harvest_(\w+)_abysmal:\s*"[^":]*:\s*([^"]+)"', loc_text))


def load_harvests(mod_root: Path) -> Harvests:
    paths = [mod_root / p for p in (HARVEST_MODIFIERS, HARVEST_EFFECTS, HARVEST_NAMES)]
    if not all(p.is_file() for p in paths):
        return Harvests()
    modifiers, effects, names = (p.read_text(encoding="utf-8-sig") for p in paths)
    return Harvests(harvest_modifiers(modifiers), harvest_regions(effects), harvest_region_names(names))


def _in_regions(regions: list[str]) -> str:
    return "OR = { " + " ".join(f"region ?= region:{r}" for r in regions) + " }"


def custom_localization(harvests: Harvests) -> str:
    keys = harvests.keys
    lines = ["# Generated by the constructor (location_status.py) from the variable-harvest files; do not edit.", ""]
    lines.append("pp_harvest_state = {\n\ttype = location")
    for key in keys:
        lines.append(f"\ttext = {{ localization_key = STATIC_MODIFIER_NAME_{key} trigger = {{ has_location_modifier = {key} }} }}")
    for sub, regions in harvests.regions.items():
        lines.append(f"\ttext = {{ localization_key = PP_HARVEST_AVERAGE_{sub.upper()} trigger = {{ {_in_regions(regions)} }} }}")
    lines.append("\ttext = { localization_key = PP_HARVEST_AVERAGE fallback = yes }\n}\n")
    lines.append("pp_harvest_trend = {\n\ttype = location")
    for trend in ("good", "bad"):
        tests = " ".join(f"has_location_modifier = {key}" for key in keys if _trend(key) == trend)
        lines.append(f"\ttext = {{ localization_key = PP_HARVEST_TREND_{trend.upper()} trigger = {{ OR = {{ {tests} }} }} }}")
    lines.append("\ttext = { localization_key = PP_HARVEST_TREND_AVERAGE fallback = yes }\n}\n")
    lines.append("pp_harvest_severity = {\n\ttype = location")
    for sev in SEVERITY_STYLE:
        tests = " ".join(f"has_location_modifier = {key}" for key in keys if severity(key) == sev)
        if tests:
            lines.append(f"\ttext = {{ localization_key = PP_HARVEST_SEVERITY_{sev.upper()} trigger = {{ OR = {{ {tests} }} }} }}")
    lines.append("\ttext = { localization_key = PP_HARVEST_SEVERITY_NONE fallback = yes }\n}\n")
    lines.append("pp_harvest_region = {\n\ttype = location")
    for sub, regions in harvests.regions.items():
        lines.append(f"\ttext = {{ localization_key = PP_HARVEST_REGION_{sub.upper()} trigger = {{ {_in_regions(regions)} }} }}")
    lines.append("\ttext = { localization_key = PP_HARVEST_REGION_NONE fallback = yes }\n}")
    return "\n".join(lines) + "\n"


def harvest_localization(harvests: Harvests) -> str:
    """Region names and the comparison tokens the chip's visibility tests match against."""
    lines = ["l_english:", "  # Generated by the constructor (location_status.py); do not edit."]
    for sub in harvests.regions:
        name = harvests.names.get(sub, sub.replace("_", " ").title())
        lines.append(f'  PP_HARVEST_REGION_{sub.upper()}: "{name}"')
        lines.append(f'  PP_HARVEST_AVERAGE_{sub.upper()}: "Average Harvest: {name}"')
    lines.append('  PP_HARVEST_REGION_NONE: "none"')
    for sev in SEVERITY_STYLE:
        lines.append(f'  PP_HARVEST_SEVERITY_{sev.upper()}: "{sev}"')
    lines.append('  PP_HARVEST_SEVERITY_NONE: "none"')
    return "\n".join(lines) + "\n"


def _row(modifier: str, visible: str | None = None) -> str:
    test = f'visible = "[{visible}]" ' if visible else ""
    return f'TooltipStringPairList = {{ {test}textcontext = "[ShowModifierEffect(\'{modifier}\')]" }}'


def _chip(name: str, visible: str, icon: str, title: str, concept: str, content: str, overlay: str = "") -> str:
    return f"""widget = {{
        name = "{name}"
        size = {{ 30 30 }}
        visible = "[{visible}]"
        datacontext = "[{_LOC}]"
        tooltipwidget = {{
        ContextualTooltipType = {{
            blockoverride "title_text" {{ text = "{title}" }}
            blockoverride "concept_link" {{ visible = yes text = "[{concept}|E]" }}
            blockoverride "title_icon" {{
                widget = {{
                    using = tooltip_title_icon_size
                    background = {{ texture = "[GetClimateFrame({_LOC}.GetClimate)]" }}
                    icon = {{ using = tooltip_title_icon_size texture = "{icon}" }}
                }}
            }}
            blockoverride "tooltip_content" {{ {content} }}
        }}
    }}
        background = {{ texture = "[GetClimateFrame({_LOC}.GetClimate)]" }}
        icon = {{ size = {{ 30 30 }} texture = "{icon}" }}{overlay}
    }}
"""


def _text(key: str) -> str:
    return f'TooltipTextBlock = {{ blockoverride "text" {{ text = "{key}" }} }}'


def _marker(key: str) -> str:
    return f"GreaterThan_float(FixedPointToFloat({_LOC}.GetModifierValueFixed('{key}')), '(float)0')"


def _harvest_test(trend: str) -> str:
    return f"EqualTo_string({_LOC}.Custom('pp_harvest_trend'), Localize('PP_HARVEST_TREND_{trend.upper()}'))"


PRESSURE_MODIFIERS = "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt"
TYPE_DEFINITIONS = "main_menu/common/modifier_type_definitions"
LAND_MODIFIERS = {"pp_land_overpopulation": "overpopulation", "pp_land_abundant": "abundant_free_land", "pp_land_available": "available_free_land"}
_GOODS_OUTPUT = re.compile(r"local_(\w+)_output_modifier")
_ICONS_PER_ROW = 14   # 26 px goods icons, 3 px apart, fit the wide tooltip


def modifier_types(texts: list[str]) -> dict[str, dict[str, str]]:
    """Display settings (percent, color, decimals, boolean, already_percent) of every modifier type, later texts win."""
    types: dict[str, dict[str, str]] = {}
    for text in texts:
        for match in re.finditer(r"^(\w+)\s*=\s*\{(.*?)^\}", text, flags=re.MULTILINE | re.DOTALL):
            body = re.sub(r"#[^\n]*", "", match.group(2))
            types[match.group(1)] = dict(re.findall(r"\b(percent|color|decimals|boolean|already_percent)\s*=\s*(\w+)", body))
    return types


def modifier_effects(text: str, name: str) -> list[tuple[str, str]]:
    """`key = value` effects of the hand-authored `TRY_REPLACE:<name>` block, comments and markers dropped."""
    start = text.index(f"TRY_REPLACE:{name} = {{")
    body = text[start:text.index("\n}", start)]
    effects = re.findall(r"^\s*(\w+)\s*=\s*(-?[\d.]+|yes|no)\s*(?:#.*)?$", body, flags=re.MULTILINE)
    return [(key, value) for key, value in effects if not key.startswith("pp_land_")]


def _scaled(marker: str, key: str, base: str, info: dict[str, str]) -> str:
    percent = info.get("percent") == "yes"
    # Enough decimals that a partly applied small effect does not round to zero (vanilla's setting is for full values).
    shown = abs(float(base)) * (100 if percent else 1)
    decimals = str(max(int(info.get("decimals", 0)), min(4, math.ceil(-math.log10(shown)) + 1 if shown else 1), 1))
    sign = {"bad": "-", "neutral": ""}.get(info.get("color", "good"), "+")
    value = f"Multiply_CFixedPoint({_LOC}.GetModifierValueFixed('{marker}'), '(CFixedPoint){base}')"
    suffix = "%" if info.get("already_percent") == "yes" else ""
    return f"[{value}|{decimals}{'%' if percent else ''}{sign}]{suffix}"


def land_effect_rows(pressure_text: str, types: dict[str, dict[str, str]]) -> dict[str, str]:
    """Each land modifier's effects at the location's current strength: its marker's value times the base value.

    The game shows static modifiers only at full strength (`ShowModifierEffect`), while the engine scales these three.
    Goods-output lines with one shared value collapse into a single line that shows the affected goods as icons.
    """
    rows: dict[str, str] = {}
    for marker, name in LAND_MODIFIERS.items():
        effects = [(k, v) for k, v in modifier_effects(pressure_text, name) if v not in ("no", "0") and (v == "yes" or float(v) != 0)]
        goods = [(k, v) for k, v in effects if _GOODS_OUTPUT.fullmatch(k)]
        shared = len(goods) >= 3 and len({v for _, v in goods}) == 1
        lines: list[tuple[float, str]] = []
        for key, value in effects:
            if shared and _GOODS_OUTPUT.fullmatch(key):
                continue
            label = f"[ShowModifierTypeName('{key}')]"
            if value == "yes":
                lines.append((float("inf"), _raw_block(label)))
            else:
                lines.append((_magnitude(value, types.get(key, {})), _raw_block(f"{label}: {_scaled(marker, key, value, types.get(key, {}))}")))
        if shared:
            key, value = goods[0]
            line = f"[Localize('PP_LAND_CHIP_GOODS_OUTPUT')]: {_scaled(marker, key, value, types.get(key, {}))}"
            lines.append((_magnitude(value, types.get(key, {})), _goods_block(line, [_GOODS_OUTPUT.fullmatch(k).group(1) for k, _ in goods])))
        # One strength scales every line alike, so the build-time order is the order of the shown values.
        lines.sort(key=lambda item: -item[0])
        rows[name] = _scrolled(" ".join(block for _, block in lines))
    return rows


def _raw_block(line: str) -> str:
    return f'TooltipTextBlock = {{ blockoverride "text" {{ raw_text = "{line}" }} }}'


def _goods_block(line: str, goods: list[str]) -> str:
    """The shared goods-output line with the affected goods as rows of icons under it, in one tooltip entry."""
    per_row = math.ceil(len(goods) / math.ceil(len(goods) / _ICONS_PER_ROW))
    rows = []
    for start in range(0, len(goods), per_row):
        icons = " ".join(
            f"icon = {{ size = {{ 26 26 }} texture = \"{_ICONS}/trade_goods/icon_goods_{good}.dds\" tooltip = \"[ShowGoodsName('{good}')]\" }}"
            for good in goods[start:start + per_row]
        )
        rows.append(f"hbox = {{ layoutpolicy_horizontal = expanding spacing = 3 {icons} expand = {{}} }}")
    return (
        "TooltipListBase = { vbox = { layoutpolicy_horizontal = expanding "
        "margin = { @tooltip_inner_margin @tooltip_inner_margin } spacing = 4 "
        f'textbox = {{ using = tooltip_text_block_template raw_text = "{line}" }} {" ".join(rows)} }} }}'
    )


def _magnitude(value: str, info: dict[str, str]) -> float:
    """Size of an effect as the tooltip shows it: percent types count in percent points."""
    return abs(float(value)) * (100 if info.get("percent") == "yes" else 1)


def _scrolled(content: str) -> str:
    """Vanilla's tooltip scroll section, capped like the mod's population breakdown."""
    return (
        'TooltipScrolledContentSection = { blockoverride "block_scrollarea" { maximumsize = { -1 420 } } '
        'blockoverride "scrollarea_content" { TooltipContentSection = { set_parent_dimension_to_minimum = height '
        f'blockoverride "section_content" {{ {content} }} }} }} }}'
    )


def load_land_effect_rows(mod_root: Path, vanilla: Path | None) -> dict[str, str] | None:
    pressure = mod_root / PRESSURE_MODIFIERS
    if vanilla is None or not pressure.is_file():
        return None
    texts = [p.read_text(encoding="utf-8-sig") for root in (vanilla / "game", mod_root) for p in sorted((root / TYPE_DEFINITIONS).glob("*.txt"))]
    return land_effect_rows(pressure.read_text(encoding="utf-8-sig"), modifier_types(texts))


def _custom_is(custom: str, token: str) -> str:
    return f"EqualTo_string({_LOC}.Custom('{custom}'), Localize('{token}'))"


def _any(tests: list[str]) -> str:
    return tests[0] if len(tests) == 1 else f"Or({tests[0]}, {_any(tests[1:])})"


def _harvest_layers(harvests: Harvests, tint: str, crop: str) -> str:
    """Severity tint behind the region's crop; sizes relative to the parent so the chip and title icon share them."""
    layers = [
        f'icon = {{ size = {{ {tint} }} parentanchor = center alpha = 0.75 texture = "gfx/interface/colors/{colour}.dds" '
        f'visible = "[{_custom_is("pp_harvest_severity", f"PP_HARVEST_SEVERITY_{sev.upper()}")}]" }}'
        for sev, (colour, _) in SEVERITY_STYLE.items()
    ]
    for sub in harvests.regions:
        good = REGION_GOODS.get(sub, "wheat")
        layers.append(f'icon = {{ size = {{ {crop} }} parentanchor = center texture = "{_ICONS}/trade_goods/icon_goods_{good}.dds" '
                      f'visible = "[{_custom_is("pp_harvest_region", f"PP_HARVEST_REGION_{sub.upper()}")}]" }}')
    layers.append(f'icon = {{ size = {{ {crop} }} parentanchor = center texture = "{_ICONS}/trade_goods/icon_goods_wheat.dds" '
                  f'visible = "[{_custom_is("pp_harvest_region", "PP_HARVEST_REGION_NONE")}]" }}')
    return "\n        ".join(layers)


def harvest_chip(harvests: Harvests) -> str:
    """One chip for every harvest: the region's crop on a severity tint, 1-3 pips and a +/- badge."""
    state = f"{_LOC}.Custom('pp_harvest_state')"
    pips = []
    for trend, severities, colour in (("good", GOOD_HARVESTS, "mid_light_green"), ("bad", BAD_HARVESTS, "light_red")):
        for n in (1, 2, 3):
            shown = [_custom_is("pp_harvest_severity", f"PP_HARVEST_SEVERITY_{s.upper()}") for s in severities if SEVERITY_STYLE[s][1] >= n]
            pips.append(f'widget = {{ position = {{ {2 + (n - 1) * 5} 22 }} size = {{ 6 6 }} visible = "[{_any(shown)}]" '
                        f'background = {{ texture = "gfx/interface/colors/super_dark_brown.dds" }} '
                        f'icon = {{ position = {{ 1 1 }} size = {{ 4 4 }} texture = "gfx/interface/colors/{colour}.dds" }} }}')
    badges = [
        f'text_single = {{ position = {{ 17 17 }} size = {{ 12 12 }} autoresize = no fontsize = 11 align = center '
        f'using = bg_number_container_bckg visible = "[{_harvest_test(trend)}]" raw_text = "{text}" }}'
        for trend, text in (("good", "#G+#!"), ("bad", "#R-#!"))
    ]
    rows = " ".join(_row(key, f"EqualTo_string({state}, Localize('STATIC_MODIFIER_NAME_{key}'))") for key in harvests.keys)
    help_texts = " ".join(
        f'TooltipTextBlock = {{ visible = "[{_harvest_test(trend)}]" blockoverride "text" {{ text = "PP_HARVEST_CHIP_{trend.upper()}" }} }}'
        for trend in ("good", "bad", "average")
    )
    return f"""widget = {{
        name = "pp_status_harvest"
        size = {{ 30 30 }}
        datacontext = "[{_LOC}]"
        tooltipwidget = {{
        ContextualTooltipType = {{
            blockoverride "title_text" {{ text = "[{state}]" }}
            blockoverride "concept_link" {{ visible = yes text = "[pp_variable_harvests|E]" }}
            blockoverride "title_icon" {{
                widget = {{
                    using = tooltip_title_icon_size
                    background = {{ texture = "[GetClimateFrame({_LOC}.GetClimate)]" }}
        {_harvest_layers(harvests, "88% 88%", "80% 80%")}
                }}
            }}
            blockoverride "tooltip_content" {{ {help_texts} {_scrolled(rows) if rows else ""} }}
        }}
    }}
        background = {{ texture = "[GetClimateFrame({_LOC}.GetClimate)]" }}
        {_harvest_layers(harvests, "26 26", "24 24")}
        {chr(10).join("        " + p for p in pips).strip()}
        {chr(10).join("        " + b for b in badges).strip()}
    }}
"""


def status_row(harvests: Harvests, land_rows: dict[str, str] | None = None) -> str:
    # Without the modifier types the land chips fall back to the full-strength effects.
    land_rows = land_rows or {name: _scrolled(_row(name)) for name in LAND_MODIFIERS.values()}
    starving = f"{_LOC}.GetProvince.IsStarving"
    months = f"[FixedPointToFloat({_LOC}.GetModifierValueFixed('pp_province_food_storage_months'))|0]"
    overlay = f"""
        text_single = {{ position = {{ 13 18 }} size = {{ 17 12 }}
            autoresize = no fontsize = 11 align = center
            using = bg_number_container_bckg
            raw_text = "{months}" }}"""
    food = _chip("pp_status_food_stored", f"Not({starving})", f"{_ICONS}/flat_icons/trade_market/food_stockpile.dds",
                 "PP_FOOD_CHIP_TITLE", "pp_food_storage",
                 _text("PP_FOOD_CHIP_STORED") + " " + _row("positive_province_food_growth"), overlay)
    food += _chip("pp_status_food_starving", starving, f"{_ICONS}/alerts_icons/starving_provinces.dds",
                  "PP_FOOD_CHIP_STARVING_TITLE", "pp_starvation",
                  _text("PP_FOOD_CHIP_STARVING") + " " + _row("province_starving"))

    over, abundant, available = (_marker(key) for key in LAND_MARKERS)
    land = _chip("pp_status_land_overpopulation", over, f"{_ICONS}/modifiers/overpopulation.dds",
                 "PP_LAND_CHIP_OVERPOPULATION_TITLE", "population_capacity",
                 _text("PP_LAND_CHIP_OVERPOPULATION") + " " + _text("PP_LAND_CHIP_OVERPOPULATION_STRENGTH") + " " + land_rows["overpopulation"])
    land += _chip("pp_status_land_abundant", f"And(Not({over}), {abundant})", f"{_ICONS}/location_icons/monthly_growth.dds",
                  "PP_LAND_CHIP_ABUNDANT_TITLE", "pp_abundant_free_land",
                  _text("PP_LAND_CHIP_ABUNDANT") + " " + _text("PP_LAND_CHIP_ABUNDANT_STRENGTH") + " " + land_rows["abundant_free_land"])
    land += _chip("pp_status_land_available", f"And3(Not({over}), Not({abundant}), {available})",
                  f"{_ICONS}/modifier_types/total_population_capacity_modifier.dds",
                  "PP_LAND_CHIP_AVAILABLE_TITLE", "pp_available_free_land",
                  _text("PP_LAND_CHIP_AVAILABLE") + " " + _text("PP_LAND_CHIP_AVAILABLE_STRENGTH") + " " + land_rows["available_free_land"])
    land += _chip("pp_status_land_settled", f"And3(Not({over}), Not({abundant}), Not({available}))",
                  f"{_ICONS}/location_icons/population.dds",
                  "PP_LAND_CHIP_SETTLED_TITLE", "population_capacity", _text("PP_LAND_CHIP_SETTLED"))

    harvest = harvest_chip(harvests)

    return f"""\t\t\t\t\t\t# PP STATUS CHIPS: top right, mirroring the geography card at the bottom left
\t\t\t\t\t\twidget = {{
\t\t\t\t\t\t\tname = "pp_location_status_row"
\t\t\t\t\t\t\tsize = {_CARD_SIZE}
\t\t\t\t\t\t\tparentanchor = right|top
\t\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\t\tmargin = {{ 10 8 }}
\t\t\t\t\t\t\t\tusing = bg_paper_card
\t\t\t\t\t\t\t\tusing = bg_cabinet_card_frame
\t\t\t\t\t\t\t\thbox = {{
\t\t\t\t\t\t\t\t\tspacing = 5
{food}{land}{harvest}\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
"""


def add_status_row(text: str, harvests: Harvests, land_rows: dict[str, str] | None = None) -> str:
    """Anchor the status card to the top-right corner of the scene, beside the IO and periphora buttons' row."""
    found = text.count(_ANCHOR)
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 top-row anchor for the status chips, found {found}")
    return text.replace(_ANCHOR, _ANCHOR[:_SPLIT] + status_row(harvests, land_rows) + _ANCHOR[_SPLIT:])


def write_harvest_files(mod_root: Path, harvests: Harvests) -> int:
    """The chip's customizable localization and its generated localization; returns how many files changed."""
    changed = 0
    for rel, body in ((CUSTOM_LOCALIZATION, custom_localization(harvests)), (HARVEST_LOCALIZATION, harvest_localization(harvests))):
        path = mod_root / rel
        text = "﻿" + body
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        changed += 1
    return changed
