"""The five manpower buildings keep vanilla 1.4's important_for_AI (the AI searches harder for a place to build them).
PP's REPLACE bodies predate the flag: only the armory had it until 2026-10-28 (Jan: "All yes (vanilla)")."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
BUILDING_TYPES = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "common" / "building_types"
MANPOWER_BUILDINGS = ("armory", "barracks", "training_fields", "regimental_camp", "conscription_center")
FLAG = re.compile(r"^\s*important_for_AI\s*=\s*yes\s*$", re.M)


@pytest.mark.parametrize("building", MANPOWER_BUILDINGS)
def test_manpower_buildings_are_important_for_ai(building: str) -> None:
    blueprint = (BLUEPRINTS / f"{building}.yml").read_text(encoding="utf-8-sig")
    built = (BUILDING_TYPES / f"zz_pp_{building}.txt").read_text(encoding="utf-8-sig")
    assert len(FLAG.findall(blueprint)) == 1, building
    assert len(FLAG.findall(built)) == 1, building
