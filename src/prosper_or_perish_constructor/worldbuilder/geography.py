"""Bring the World Builder geography export (the "EU5 World Builder" test mod build) into the main mod.

Copies the exported class definitions (climates, vegetation, topography), the location templates that
assign them, the soil/fertility startup assignments with their scripted triggers, the river bitmap, colours,
icons and localization. Test-only files (vanilla building copies, the location window GUI, manifests) are
not copied. A manifest of copied files is kept so a later sync removes what the export no longer ships.

The location window is the one exception: it is taken from the export and re-patched here, because
both the stored-food gauge and the population-capacity readout are the main mod's, not the export's.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

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
EXCLUDED_SUFFIXES = (".csv", "_manifest.json", "geography_compatibility.json", EXPORT_BUILD_FILE)
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
        if rel.startswith(EXCLUDED_PREFIXES) or rel.endswith(EXCLUDED_SUFFIXES):
            continue
        keep.append(rel)
    return keep


LOCATION_WINDOW = "in_game/gui/location_window.gui"
_FOOD_PERCENT = 'value = "[FixedPointToFloat(Province.GetFoodCapacityPercent)]"'
_FOOD_PERCENT_REST = 'value = "[Subtract_float(\'(float)100.0\', FixedPointToFloat(Province.GetFoodCapacityPercent))]"'
_FOOD_SCOPES = ("LocationView", "LocationViewSelectProvince.Parent")


def merge_location_window(text: str) -> str:
    """Re-apply the mod's stored-food gauge on the World Builder location window.

    The World Builder file is vanilla plus its native geography view; the mod replaces the vanilla
    province food-capacity gauge (two pairs of lines: the location view and the province selector) with
    the stored-food months from `pp_province_food_storage_months`. The divisor is compiled afterwards by
    the food-storage GUI step, which expects exactly these four lines.
    """
    lines = text.splitlines(keepends=True)
    pair = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == _FOOD_PERCENT:
            scope = _FOOD_SCOPES[min(pair // 2, 1)]
            lines[index] = line.replace(_FOOD_PERCENT, f"value = \"[FixedPointToFloat(Divide_CFixedPoint({scope}.GetLocation.GetModifierValueFixed('pp_province_food_storage_months'), '(CFixedPoint)24'))]\"")
            pair += 1
        elif stripped == _FOOD_PERCENT_REST:
            scope = _FOOD_SCOPES[min((pair - 1) // 2, 1)]
            lines[index] = line.replace(_FOOD_PERCENT_REST, f"value = \"[Subtract_float('(float)1.0', FixedPointToFloat(Divide_CFixedPoint({scope}.GetLocation.GetModifierValueFixed('pp_province_food_storage_months'), '(CFixedPoint)24')))]\"")
            pair += 1
    if pair != 4:
        raise ValueError(f"location_window.gui: expected 4 vanilla food-capacity gauge lines, found {pair}")
    return add_attribute_effect_rows("".join(lines))


FERTILITY_CLASSES = ("very_low", "low", "moderate", "high", "very_high")
SOIL_CLASSES = ("sand", "loam", "stony", "clay", "silt", "peat")
_LOC = "LocationView.GetLocation"


def _effect_row(modifier: str, visible: str) -> str:
    return f'TooltipStringPairList = {{ visible = "[{visible}]" textcontext = "[ShowModifierEffect(\'{modifier}\')]" }}'


def add_attribute_effect_rows(text: str) -> str:
    """Fertility, soil, lake and coast chips list the fitted effects of their pp_wb static modifier.

    The World Builder export knows nothing about the constructor's modifier keys, so the rows are added here. Every
    class row is emitted with a visibility test on the location's class, so chips that serve several classes work.
    """
    fert_rows = " ".join(_effect_row(f"pp_wb_fertility_{c}", f"EqualTo_string({_LOC}.Custom('ha1300_fertility_name'), Localize('HA1300_FERTILITY_{c.upper()}'))") for c in FERTILITY_CLASSES)
    soil_rows = " ".join(_effect_row(f"pp_wb_soil_{c}", f"EqualTo_string({_LOC}.Custom('ha1300_soil_type_name'), Localize('HA1300_SOIL_{c.upper()}_TITLE'))") for c in SOIL_CLASSES)
    fert_line = f'blockoverride "tooltip_content" {{ TooltipFlavorTextBlock = {{ blockoverride "text" {{ text = "[{_LOC}.Custom(\'ha1300_fertility_desc\')]" }} }} }}'
    soil_line = f'blockoverride "tooltip_content" {{ TooltipFlavorTextBlock = {{ blockoverride "text" {{ text = "[{_LOC}.Custom(\'ha1300_soil_type_description\')]" }} }} }}'
    lake_line = 'blockoverride "tooltip_content" { TooltipTextBlock = { blockoverride "text" { text = "HA1300_LAKE_HELP" } } }'
    coast_anchor = "textcontext = \"[ShowModifierEffect('coastal')]\"\n    } }"
    text = text.replace(fert_line, fert_line[:-1] + fert_rows + " }")
    text = text.replace(soil_line, soil_line[:-1] + soil_rows + " }")
    text = text.replace(lake_line, lake_line[:-1] + _effect_row("pp_wb_lake", f"EqualTo_string({_LOC}.Custom('ha1300_native_lake'), Localize('HA1300_LAKESIDE'))") + " }")
    text = text.replace(coast_anchor, coast_anchor[:-1] + _effect_row("pp_wb_coastal", f"{_LOC}.IsCoastal") + " }")
    return text


_POP_CELL = "\t\t\t\t\t\tsize = { 120 28 }"
_POP_CELL_WIDE = "\t\t\t\t\t\tsize = { 185 28 }"
# Only one of the four gauges is ever visible; the cell is 28px tall and cannot afford to reserve
# space for the hidden three.
_POP_VBOX = "\t\t\t\t\t\t\t\tmargin_right = 8\n\t\t\t\t\t\t\t\tmargin_bottom = 3"
_POP_VBOX_IGNORING = _POP_VBOX + "\n\t\t\t\t\t\t\t\tignoreinvisible = yes"
_POP_TEXT = """\t\t\t\t\t\t\t\ttext_single = {
\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\t\t\talign = center
\t\t\t\t\t\t\t\t\tsize = { -1 15 }
\t\t\t\t\t\t\t\t\tvisible = "[HasPopBreakdownIntelOn(Location.Self)]"
\t\t\t\t\t\t\t\t\traw_text = "[Location.GetTotalPopulation]@population!"
\t\t\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\t\t\tblock "location_population_sort_highlight" {}
\t\t\t\t\t\t\t\t}"""
# raw_text, not a localization key: it is evaluated against the widget's own datacontext, which is
# how vanilla wrote this cell. A `text = "KEY"` here resolved to nothing in game.
_POP_TEXT_RATIO = """\t\t\t\t\t\t\t\ttext_single = {
\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\t\t\talign = center
\t\t\t\t\t\t\t\t\tsize = { -1 15 }
\t\t\t\t\t\t\t\t\tvisible = "[HasPopBreakdownIntelOn(Location.Self)]"
\t\t\t\t\t\t\t\t\traw_text = "[Location.GetTotalPopulation]/[Location.GetPopulationCapacity] · [Location.GetCapacityPercentage|0]%"
\t\t\t\t\t\t\t\t\tfontsize = 12
\t\t\t\t\t\t\t\t\tblock "location_population_sort_highlight" {}
\t\t\t\t\t\t\t\t}"""
_CAPACITY_BAR = """\t\t\t\t\t\t\t\tprogressbar = {
\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\tsize = { -1 5 }
\t\t\t\t\t\t\t\t\tvisible = "[HasPopBreakdownIntelOn(Location.Self)]"
\t\t\t\t\t\t\t\t\tusing = progress_bar_green_alt
\t\t\t\t\t\t\t\t\tvalue = "[Location.GetCapacityPercentage]"
\t\t\t\t\t\t\t\t\tdirection = horizontal
\t\t\t\t\t\t\t\t}"""
_CAPACITY_BAND_BAR = """\t\t\t\t\t\t\t\tprogressbar = {
\t\t\t\t\t\t\t\t\tname = "pp_pop_capacity_bar___NAME__"
\t\t\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\t\t\tsize = { -1 5 }
\t\t\t\t\t\t\t\t\tvisible = "[__VISIBLE__]"
\t\t\t\t\t\t\t\t\tprogresstexture = "gfx/interface/progressbars/__TEXTURE__.dds"
\t\t\t\t\t\t\t\t\tnoprogresstexture = "gfx/interface/progressbars/progress_black.dds"
\t\t\t\t\t\t\t\t\ttexture_density = 2
\t\t\t\t\t\t\t\t\tspriteType = Corneredstretched
\t\t\t\t\t\t\t\t\tspriteborder = { 12 0 }
\t\t\t\t\t\t\t\t\tmin = 0
\t\t\t\t\t\t\t\t\tmax = 100
\t\t\t\t\t\t\t\t\tvalue = "[Location.GetCapacityPercentage]"
\t\t\t\t\t\t\t\t\tdirection = horizontal
\t\t\t\t\t\t\t\t}"""
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


def _capacity_band_bar(name: str, texture: str, low: str | None, high: str | None) -> str:
    tests = ["HasPopBreakdownIntelOn(Location.Self)"]
    if low is not None:
        tests.append(f"GreaterThanOrEqualTo_float({_CAPACITY_PERCENT}, '(float){low}')")
    if high is not None:
        tests.append(f"LessThan_float({_CAPACITY_PERCENT}, '(float){high}')")
    joined = ", ".join(tests)
    visible = f"And3({joined})" if len(tests) == 3 else f"And({joined})"
    return (
        _CAPACITY_BAND_BAR.replace("__NAME__", name)
        .replace("__VISIBLE__", visible)
        .replace("__TEXTURE__", texture)
    )


def merge_population_capacity(text: str) -> str:
    """Make population capacity readable in the location header.

    Vanilla shows the population alone above a single green gauge, so a location that is full looks
    like one with room to grow. Capacity is this mod's core constraint, so the cell states population,
    capacity and fill, and the gauge is banded by remaining headroom. The engine clamps the gauge at
    full, which is what we want above capacity: the red band says "over" and the percentage states how
    far over, which a rescaled gauge could only show by giving up resolution below capacity.
    """
    replacements = (
        (_POP_CELL, _POP_CELL_WIDE),
        (_POP_VBOX, _POP_VBOX_IGNORING),
        (_POP_TEXT, _POP_TEXT_RATIO),
        (_CAPACITY_BAR, "\n\n".join(_capacity_band_bar(*band) for band in _CAPACITY_BANDS)),
    )
    for old, new in replacements:
        found = text.count(old)
        if found != 1:
            raise ValueError(f"location_window.gui: expected 1 population-cell anchor, found {found}")
        text = text.replace(old, new)
    return text


def sync_geography(export_dir: Path, mod_root: Path, repo: Path) -> dict[str, object]:
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
            merged = merge_population_capacity(merge_location_window(src.read_text(encoding="utf-8-sig")))
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
