"""Bring the World Builder geography export (the "EU5 World Builder" test mod build) into the main mod.

Copies the exported class definitions (climates, vegetation, topography), the location templates that
assign them, the soil/fertility startup assignments with their scripted triggers, the river bitmap, colours,
icons and localization. Test-only files (vanilla building copies, the location window GUI, manifests) are
not copied. A manifest of copied files is kept so a later sync removes what the export no longer ships.

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
        if not dst.is_file() or _sha(dst) != digest:
            shutil.copyfile(src, dst)
            changed += 1
        copied[rel] = digest
    removed = 0
    for rel in (*previous, *RENAMED_EXPORT_FILES):
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
