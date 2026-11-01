"""PP concept texts and PP game concepts match: a concept removed without its text leaves a dead key behind, and a
concept or alias without its text logs "Game concept '<key>': Missing localization key" (game_concepts.cpp)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
CONCEPT_KEY = re.compile(r"^\s*game_concept_((?:pp_|prosper)[A-Za-z0-9_]*?)(?:_desc)?:\d*\s*\"", re.M)
TEXT_KEY = re.compile(r"^\s*game_concept_([A-Za-z0-9_]+):\d*\s*\"", re.M)


def _concepts_and_aliases() -> tuple[set[str], set[str]]:
    concepts, aliases = set(), set()
    for path in (MOD_ROOT / "main_menu/common/game_concepts").glob("*.txt"):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        concepts.update(re.findall(r"^([A-Za-z_]\w*)\s*=\s*\{", text, re.M))
        for group in re.findall(r"\balias\s*=\s*\{([^}]*)\}", text):
            aliases.update(group.split())
    return concepts, aliases


def _english_texts() -> str:
    # Not localization/replace: vanilla's own concept texts live there (game_concept_prosperity).
    return "\n".join(p.read_text(encoding="utf-8-sig") for p in (MOD_ROOT / "main_menu/localization/english").rglob("*.yml"))


def test_pp_concept_texts_have_a_concept():
    concepts, aliases = _concepts_and_aliases()
    dead = [key for key in CONCEPT_KEY.findall(_english_texts()) if key not in concepts | aliases]
    assert sorted(dead) == []


def test_every_pp_concept_and_alias_has_its_text():
    # The engine wants game_concept_<name> for every concept and every alias (the alias prosper_or_perish of the
    # Europedia overview logged it after its text was taken for a dead key, 2026-10-28).
    concepts, aliases = _concepts_and_aliases()
    texts = set(TEXT_KEY.findall(_english_texts()))
    pp_names = {name for name in concepts | aliases if name.startswith(("pp_", "prosper"))}
    assert sorted(pp_names - texts) == []
