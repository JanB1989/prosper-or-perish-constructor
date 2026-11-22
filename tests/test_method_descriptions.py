"""Every production method carries a short description (the flavour text of its tooltip).

Jan, 2026-11-22: each method says what it is and why it is there; real techniques in two or three sentences of
history, accounting methods (upkeep, deposits, empty choices) in one. docs/mod_authoring_rules.md.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
MAX_WORDS = 60


def _methods() -> list[tuple[str, str, object]]:
    rows = []
    for path in sorted(BLUEPRINTS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        building = data.get("building") or {}
        entries = (data.get("localization") or {}).get("entries") or {}
        names = [m for slot in building.get("production_method_slots") or [] for m in slot.get("methods") or []]
        names += building.get("possible_production_methods") or []
        rows += [(path.name, name, entries.get(f"{name}_desc")) for name in names]
    return rows


@pytest.fixture(scope="module")
def methods() -> list[tuple[str, str, object]]:
    return _methods()


def test_every_production_method_has_a_description(methods) -> None:
    assert methods
    assert [f"{file}: {name}" for file, name, desc in methods if not desc] == []


def test_descriptions_stay_short_and_carry_no_numbers_of_the_balance(methods) -> None:
    off = []
    for file, name, desc in methods:
        if not desc:
            continue
        text = str(desc)
        plain = re.sub(r"\[[^\]]*\]", "X", text)
        if len(plain.split()) > MAX_WORDS:
            off.append(f"{file}: {name}: longer than {MAX_WORDS} words")
        if "%" in plain or '"' in text or "\n" in text.strip():
            off.append(f"{file}: {name}: percent sign, double quote or line break")
    assert off == []
