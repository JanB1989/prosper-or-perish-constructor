"""Bring the World Builder geography export (the "EU5 World Builder" test mod build) into the main mod.

Copies the exported class definitions (climates, vegetation, topography), the location templates that
assign them, the river bitmap, colours, icons and localization. Test-only files (vanilla building copies, the location
window GUI, manifests) are not copied. A manifest of copied files is kept so a later sync removes what the export no
longer ships.

Soil and fertility (2026-10-24): the export stores them as location variables set at game start (its on_actions) and
tests those in its map modes and customizable localization. The main mod already places the same classes as the
location modifiers ``pp_wb_fertility_<class>`` / ``pp_wb_soil_<class>`` (modifiers.py, from the handover), so it ships
neither the variable on_actions nor the scripted triggers on them, and the copied map modes and customizable
localization test ``has_location_modifier`` instead (``modifier_tests``). Customizable localization nothing in the mod
uses is dropped (``DROPPED_LOCALIZATION_BLOCKS``), and so are its localization keys nothing shows
(``DROPPED_LOCALIZATION_KEYS``).

The location window is the one exception: the main mod builds it from the export's (location_view.py, in the
constructor's finalize step, so a GUI edit does not rerun this stage); the sync only keeps it out of the stale list.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

MANIFEST_RELATIVE_PATH = Path("artifacts/data/worldbuilder/geography_sync.json")
EXPORT_BUILD_FILE = "ha1300-build.json"
EXCLUDED_PREFIXES = (
    "in_game/gfx/interface/icons/map_modes/",   # map mode icons live only in main_menu (the export ships both)
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
# Files earlier exports shipped under a name the export no longer uses. The manifest of the last sync removes them too,
# but it is machine-local (artifacts/ is ignored), so a fresh checkout would keep them: removed whenever the export lacks
# them. EU5 1.4 renamed vanilla's city locators to generated_locators_city.txt (a stale old-name copy would add a second
# set of city locators); the World Builder renamed its steppe and subarctic climates to the vanilla 1.4 keys.
RENAMED_EXPORT_FILES = (
    "in_game/gfx/map/map_objects/generated_map_object_locators_city.txt",
    *(f"main_menu/gfx/interface/icons/climate/ha1300_climate_{name}{suffix}.dds"
      for name in ("hot_steppe", "cold_steppe", "subarctic") for suffix in ("", "_frame")),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_interface_dds(rel: str) -> bool:
    return rel.lower().endswith(".dds") and "/gfx/interface/" in rel


def _interface_dds_bytes(src: Path, rel: str) -> bytes:
    from prosper_or_perish_constructor import interface_dds

    data = src.read_bytes()
    try:
        return interface_dds.normalized(data, Path(rel))
    except (OSError, ValueError):
        return data


def export_files(export_dir: Path) -> list[str]:
    build = json.loads((export_dir / EXPORT_BUILD_FILE).read_text(encoding="utf-8-sig"))
    files = build.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{export_dir / EXPORT_BUILD_FILE}: missing files map")
    keep: list[str] = []
    for rel in sorted(files):
        if rel.startswith(EXCLUDED_PREFIXES) or (rel.endswith(EXCLUDED_SUFFIXES) and not rel.startswith(MAP_DATA_PREFIX)):
            continue
        if rel in DROPPED_EXPORT_FILES:
            continue
        keep.append(rel)
    return keep


LOCATION_WINDOW = "in_game/gui/location_window.gui"
MAP_MODES = "in_game/gfx/map/map_modes/map_modes.txt"
# Export files the main mod does not ship: the soil/fertility variables and the scripted triggers on them (unused).
DROPPED_EXPORT_FILES = (
    "in_game/common/on_action/ha1300_fertility.txt",
    "in_game/common/on_action/ha1300_global_soils.txt",
    "in_game/common/scripted_triggers/ha1300_fertility.txt",
    "in_game/common/scripted_triggers/ha1300_global_soils.txt",
)
# The export's class ids (fertility_id / soil_id in its assignment tables, 1-based) -> the setup's modifier classes.
FERTILITY_CLASSES = ("very_low", "low", "moderate", "high", "very_high")
SOIL_CLASSES = ("sand", "loam", "silt", "clay", "peat", "stony")
VARIABLE_MODIFIERS = {"ha1300_fertility": ("pp_wb_fertility_", FERTILITY_CLASSES),
                      "ha1300_soil_type": ("pp_wb_soil_", SOIL_CLASSES)}
_VARIABLE_TEST = re.compile(r"has_variable = (ha1300_fertility|ha1300_soil_type) var:\1 = (\d+)")
# Copied files whose variable tests become modifier tests.
MODIFIER_TESTED_FILES = (
    "in_game/common/customizable_localization/ha1300_fertility.txt",
    "in_game/common/customizable_localization/ha1300_global_soils.txt",
    "in_game/gfx/map/map_modes/ha1300_fertility.txt",
    "in_game/gfx/map/map_modes/ha1300_soils.txt",
)
# Customizable localization of the export that nothing in the main mod uses (its location window has no coast or
# winter chip; the soil evidence variable is never set).
DROPPED_LOCALIZATION_BLOCKS = {
    "in_game/common/customizable_localization/ha1300_global_soils.txt": ("ha1300_soil_type_evidence",),
    "in_game/common/customizable_localization/ha1300_native_geography.txt": ("ha1300_native_coast", "ha1300_native_max_winter"),
}
# Localization keys of the export that nothing in the main mod shows: the dropped blocks' texts (coast, maximum winter,
# soil evidence) and the export's own lake/coast chip titles (the main mod's location window has its own).
DROPPED_LOCALIZATION_KEYS = {
    "main_menu/localization/english/ha1300_global_soils_l_english.yml": (
        "HA1300_SOIL_SCOPE", "HA1300_SOIL_INFERRED", "HA1300_SOIL_DIRECT",
    ),
    "main_menu/localization/english/ha1300_native_geography_l_english.yml": (
        "HA1300_COASTAL", "HA1300_INLAND", "HA1300_LAKE_TITLE", "HA1300_COAST_TITLE", "HA1300_COAST_HELP",
        "HA1300_MAX_WINTER_TITLE", "HA1300_MAX_WINTER_HELP", "HA1300_UNKNOWN",
        "HA1300_WINTER_NONE", "HA1300_WINTER_MILD", "HA1300_WINTER_NORMAL", "HA1300_WINTER_SEVERE",
    ),
}


def modifier_tests(text: str) -> str:
    """The export's soil/fertility variable tests as tests of the setup's location modifiers."""
    def swap(match: re.Match[str]) -> str:
        prefix, classes = VARIABLE_MODIFIERS[match.group(1)]
        index = int(match.group(2)) - 1
        if not 0 <= index < len(classes):
            raise ValueError(f"World Builder export: unknown {match.group(1)} id {match.group(2)}")
        return f"has_location_modifier = {prefix}{classes[index]}"
    text = _VARIABLE_TEST.sub(swap, text)
    left = re.search(r"(?:var:|has_variable = )ha1300_(?:fertility|soil_type)\b", text)
    if left:
        raise ValueError(f"World Builder export: a soil/fertility variable test the sync cannot rewrite: {text[left.start():left.start() + 80]!r}")
    return text


def drop_blocks(text: str, names: tuple[str, ...], rel: str) -> str:
    """``text`` without the top-level blocks ``names`` (each must occur once)."""
    for name in names:
        match = list(re.finditer(rf"(?<![\w:]){re.escape(name)}\s*=\s*\{{", text))
        if len(match) != 1:
            raise ValueError(f"{rel}: expected one block {name}, found {len(match)}")
        start, depth = match[0].start(), 0
        for end in range(match[0].end() - 1, len(text)):
            depth += {"{": 1, "}": -1}.get(text[end], 0)
            if depth == 0:
                break
        else:
            raise ValueError(f"{rel}: unbalanced block {name}")
        end += 1
        if text[end:end + 1] == "\n":
            end += 1
        text = text[:start] + text[end:]
    return text


def drop_keys(text: str, keys: tuple[str, ...]) -> str:
    """``text`` (a localization file) without the entry lines of ``keys``."""
    if not keys:
        return text
    alternatives = "|".join(map(re.escape, keys))
    pattern = re.compile(r"^[ \t]*(?:" + alternatives + r"):\d*[ \t]*\".*$\n?", re.MULTILINE)
    return pattern.sub("", text)


def transformed(rel: str, text: str) -> str:
    """The main mod's version of an export file listed in MODIFIER_TESTED_FILES, DROPPED_LOCALIZATION_BLOCKS or
    DROPPED_LOCALIZATION_KEYS."""
    if rel in MODIFIER_TESTED_FILES:
        text = modifier_tests(text)
    text = drop_blocks(text, DROPPED_LOCALIZATION_BLOCKS.get(rel, ()), rel)
    text = drop_keys(text, DROPPED_LOCALIZATION_KEYS.get(rel, ()))
    return text.rstrip("\n") + "\n"


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
            # built from the export by location_view.py in the constructor's finalize step (view only, no start setup)
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
        if rel in MODIFIER_TESTED_FILES or rel in DROPPED_LOCALIZATION_BLOCKS or rel in DROPPED_LOCALIZATION_KEYS:
            own = transformed(rel, src.read_text(encoding="utf-8-sig"))
            if not dst.is_file() or dst.read_text(encoding="utf-8-sig") != own:
                dst.write_text("\ufeff" + own, encoding="utf-8", newline="\n")
                changed += 1
            copied[rel] = digest
            continue
        if _is_interface_dds(rel):
            # the export writes some icons uncompressed: copy them in the game format the finalize step enforces
            # (interface_dds.py), so a sync after a build does not flip them back every time
            data = _interface_dds_bytes(src, rel)
            if not dst.is_file() or dst.read_bytes() != data:
                dst.write_bytes(data)
                changed += 1
        elif not dst.is_file() or _sha(dst) != digest:
            shutil.copyfile(src, dst)
            changed += 1
        copied[rel] = digest
    removed = 0
    for rel in (*previous, *RENAMED_EXPORT_FILES, *DROPPED_EXPORT_FILES):
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
