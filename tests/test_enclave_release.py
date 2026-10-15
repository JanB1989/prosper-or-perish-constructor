"""Enclave release (docs/peace_deal_rulebook.md "Enclaves") is paused during civil wars.

A revolt country is born as scattered low-control pieces far from its capital, and the loyalist side is cut apart by
the rebels' land, so without the pause both would let their heartland go and the winner would keep those subjects
(run 4b42459e, Castile 1378-1380).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

COMMON = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "common"


def _block(text: str, key: str) -> str:
    start = text.index(f"{key} = {{") + len(key) + 4
    depth = 1
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i]
    raise AssertionError(f"unclosed {key}")


def test_pause_trigger_covers_civil_war_and_rebels():
    body = _block((COMMON / "scripted_triggers" / "pp_enclave_triggers.txt").read_text(encoding="utf-8-sig"),
                  "pp_enclave_release_paused")
    assert re.search(r"\bin_civil_war = yes\b", body)
    assert re.search(r"\bis_rebel_country = yes\b", body)


@pytest.mark.parametrize("action", ["create_province_subject", "pp_release_enclave_independence"])
def test_release_actions_check_the_pause(action):
    text = (COMMON / "generic_actions" / f"{action}.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"\bpp_enclave_release_paused = no\b", _block(text, "ai_prerequisite"))
