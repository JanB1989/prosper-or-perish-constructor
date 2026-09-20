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
    "in_game/gui/",                      # the main mod has its own location window
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
