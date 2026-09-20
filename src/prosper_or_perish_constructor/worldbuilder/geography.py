"""Bring the World Builder geography export (the "EU5 World Builder" test mod build) into the main mod.

Copies the exported class definitions (climates, vegetation, topography), the location templates that
assign them, the soil/fertility startup assignments with their scripted triggers, the river bitmap, colours,
icons and localization. Test-only files (vanilla building copies, the location window GUI, manifests) are
not copied. A manifest of copied files is kept so a later sync removes what the export no longer ships.
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
    return "".join(lines)


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
            merged = merge_location_window(src.read_text(encoding="utf-8-sig"))
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
