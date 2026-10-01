"""Bring the World Builder geography export (the "EU5 World Builder" test mod build) into the main mod.

Copies the exported class definitions (climates, vegetation, topography), the location templates that
assign them, the soil/fertility startup assignments with their scripted triggers, the river bitmap, colours,
icons and localization. Test-only files (vanilla building copies, the location window GUI, manifests) are
not copied. A manifest of copied files is kept so a later sync removes what the export no longer ships.

The location window is the one exception: it is taken from the export and re-patched here, because
the stored-food gauge, the population-capacity readout, the RGO chip and the status chips (location_status.py)
are the main mod's, not the export's.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from prosper_or_perish_constructor import location_status

MANIFEST_RELATIVE_PATH = Path("artifacts/data/worldbuilder/geography_sync.json")
EXPORT_BUILD_FILE = "ha1300-build.json"
EXCLUDED_PREFIXES = (
    "in_game/common/building_types/",   # vanilla copies used by the isolated test
    "in_game/common/goods/",             # vanilla copy
    "in_game/common/scripted_triggers/goods_triggers.txt",
    "in_game/common/scripted_triggers/location_triggers.txt",
    ".metadata/",
    "README.md",
)
# The export's assignment tables are .csv, but the map's ports and adjacencies are game files.
MAP_DATA_PREFIX = "in_game/map_data/"
EXCLUDED_SUFFIXES = (".csv","_manifest.json", "geography_compatibility.json", EXPORT_BUILD_FILE)
LEGACY_ATTRIBUTE_FILES = (
    "in_game/common/climates/pp_climate_changes.txt",
    "in_game/common/vegetation/pp_vegetation_changes.txt",
    "in_game/common/topography/pp_topography_changes.txt",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_files(export_dir: Path) -> list[str]:
    build = json.loads((export_dir / EXPORT_BUILD_FILE).read_text(encoding="utf-8-sig"))
    files = build.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{export_dir / EXPORT_BUILD_FILE}: missing files map")
    keep: list[str] = []
    for rel in sorted(files):
        if rel.startswith(EXCLUDED_PREFIXES) or (rel.endswith(EXCLUDED_SUFFIXES) and not rel.startswith(MAP_DATA_PREFIX)):
            continue
        keep.append(rel)
    return keep


LOCATION_WINDOW = "in_game/gui/location_window.gui"
MAP_MODES = "in_game/gfx/map/map_modes/map_modes.txt"
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


def sync_geography(export_dir: Path, mod_root: Path, repo: Path, vanilla: Path | None = None) -> dict[str, object]:
    """Copy the export into the mod, remove stale copies from a previous sync and the legacy attribute injects."""
    export_dir = Path(export_dir)
    if not (export_dir / EXPORT_BUILD_FILE).is_file():
        raise FileNotFoundError(f"World Builder geography export not found: {export_dir / EXPORT_BUILD_FILE}")
    manifest_path = repo / MANIFEST_RELATIVE_PATH
    previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {}) if manifest_path.is_file() else {}
    copied: dict[str, str] = {}
    changed = 0
    for rel in export_files(export_dir):
        src = export_dir / rel
        if not src.is_file():
            continue
        dst = mod_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        digest = _sha(src)
        if rel == LOCATION_WINDOW:
            bonuses = mod_root / RGO_BONUSES
            goods = rgo_bonus_goods(bonuses.read_text(encoding="utf-8-sig")) if bonuses.is_file() else []
            from .coast import water_access_chips

            merged = add_land_potential_chip(add_rgo_chip(merge_population_capacity(water_access_chips(merge_location_window(src.read_text(encoding="utf-8-sig")))), goods))
            harvests = location_status.load_harvests(mod_root)
            merged = location_status.add_status_row(merged, harvests, location_status.load_land_effect_rows(mod_root, vanilla))
            location_status.write_harvest_files(mod_root, harvests)
            if not dst.is_file() or dst.read_text(encoding="utf-8-sig") != merged:
                dst.write_text("﻿" + merged, encoding="utf-8", newline="\n")
                changed += 1
            copied[rel] = digest
            continue
        if rel == MAP_MODES:
            from .coast import topography_map_mode_without_rivers

            merged = topography_map_mode_without_rivers(src.read_text(encoding="utf-8-sig"))
            if not dst.is_file() or dst.read_text(encoding="utf-8-sig") != merged:
                dst.write_text("﻿" + merged, encoding="utf-8", newline="\n")
                changed += 1
            copied[rel] = digest
            continue
        if not dst.is_file() or _sha(dst) != digest:
            shutil.copyfile(src, dst)
            changed += 1
        copied[rel] = digest
    removed = 0
    for rel in previous:
        if rel not in copied and (mod_root / rel).is_file():
            (mod_root / rel).unlink()
            removed += 1
    legacy_removed = 0
    for rel in LEGACY_ATTRIBUTE_FILES:
        path = mod_root / rel
        if path.is_file():
            path.unlink()
            legacy_removed += 1
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"export": str(export_dir), "files": copied}, indent=2) + "\n", encoding="utf-8")
    return {"files": len(copied), "changed": changed, "removed_stale": removed, "legacy_removed": legacy_removed}
