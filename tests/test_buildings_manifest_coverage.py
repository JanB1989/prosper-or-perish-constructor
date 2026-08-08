from __future__ import annotations

from pathlib import Path

import yaml

from eu5_mod_orchestrator.blueprints import declared_manifest_entries


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
BLUEPRINT_BUILDINGS_ROOT = ROOT / "blueprints" / "accepted" / "buildings"


def _on_disk_building_entries() -> set[str]:
    return {
        f"buildings/{path.name}"
        for path in BLUEPRINT_BUILDINGS_ROOT.glob("*.yml")
    }


def _manifest_declared_entries() -> list[str]:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    return declared_manifest_entries(manifest.get("enabled", []), source=MANIFEST_PATH)


def test_all_accepted_building_blueprints_are_declared_in_manifest() -> None:
    declared = set(_manifest_declared_entries())
    on_disk = _on_disk_building_entries()

    missing = sorted(on_disk - declared)
    orphans = sorted(declared - on_disk)

    assert missing == [], (
        "Accepted building blueprints missing from buildings.manifest.yml; "
        "add them with true/false toggles:\n" + "\n".join(missing)
    )
    assert orphans == [], (
        "buildings.manifest.yml entries without matching accepted blueprints:\n"
        + "\n".join(orphans)
    )


def test_buildings_manifest_has_no_duplicate_declared_entries() -> None:
    declared = _manifest_declared_entries()
    duplicates = sorted({entry for entry in declared if declared.count(entry) > 1})
    assert duplicates == [], f"Duplicate buildings.manifest.yml entries:\n" + "\n".join(duplicates)
