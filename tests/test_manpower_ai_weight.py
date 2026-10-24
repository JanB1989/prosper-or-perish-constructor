from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BUILDING_TYPES = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "common" / "building_types"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
MANPOWER_BUILDINGS = ("armory", "barracks", "training_fields", "regimental_camp", "conscription_center")


def weight_lines(text: str) -> list[str]:
    block = re.search(r"ai_construct_weight = \{(.*?)\n\s*\}\n", text, re.S)
    assert block, "no ai_construct_weight"
    return [line.strip() for line in block.group(1).splitlines() if line.strip() and not line.strip().startswith("#")]


@pytest.mark.parametrize("building", MANPOWER_BUILDINGS)
def test_manpower_buildings_answer_an_empty_manpower_pool(building: str) -> None:
    # The AI never queued manpower buildings (1541 save: 0 of 573 queues); AAMO only builds armories and barracks.
    body = yaml.safe_load((BLUEPRINTS / f"{building}.yml").read_text(encoding="utf-8-sig"))["building"]["body"]
    built = (BUILDING_TYPES / f"zz_pp_{building}.txt").read_text(encoding="utf-8-sig")
    expected = [
        "value = 1",
        "subtract = scope:owner.manpower_percentage",
        "min = 0",
        "multiply = 300",
        "divide = { value = scope:owner.monthly_income_total add = 10 }",
    ]
    assert weight_lines(body) == expected
    assert weight_lines(built) == expected
    assert "important_for_AI = yes" in body and "important_for_AI = yes" in built
    # Soldiers are scarce (0.6 % of pops in a 1545 save); without this the AI skipped the buildings before scoring.
    assert "AI_ignore_available_worker_flag = yes" in body and "AI_ignore_available_worker_flag = yes" in built
