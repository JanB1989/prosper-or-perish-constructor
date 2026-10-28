"""Every PP concept text names a PP game concept; a concept removed without its text leaves a dead key behind."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
CONCEPT_KEY = re.compile(r"^\s*game_concept_((?:pp_|prosper)[A-Za-z0-9_]*?)(?:_desc)?:\d*\s*\"", re.M)


def test_pp_concept_texts_have_a_concept():
    concepts = set()
    for path in (MOD_ROOT / "main_menu/common/game_concepts").glob("*.txt"):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        concepts.update(re.findall(r"^([A-Za-z_]\w*)\s*=\s*\{", text, re.M))
    dead = []
    for path in (MOD_ROOT / "main_menu/localization/english").rglob("*.yml"):
        dead += [key for key in CONCEPT_KEY.findall(path.read_text(encoding="utf-8-sig")) if key not in concepts]
    assert sorted(dead) == []
