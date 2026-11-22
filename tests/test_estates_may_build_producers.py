"""Every production building is open to the estates (Jan, 2026-11-22).

An estate may pay for a building its own people work in unless the type says `forbidden_for_estates = yes`. No
building with a goods output carries that ban; military, naval and administration buildings may.
docs/mod_authoring_rules.md "Estates may build every production building".
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
BANNED = re.compile(r"^\s*forbidden_for_estates\s*=\s*yes\b", re.M)
PRODUCES = re.compile(r"^\s*produced\s*=", re.M)


def test_no_production_building_is_forbidden_for_estates() -> None:
    banned = []
    seen = 0
    for path in sorted(BLUEPRINTS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("enabled") is False:
            continue
        body = str((data.get("building") or {}).get("body") or "")
        if not PRODUCES.search(body):
            continue
        seen += 1
        if BANNED.search(body):
            banned.append(path.name)
    assert seen > 200
    assert banned == []
