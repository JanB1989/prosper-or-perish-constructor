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


def test_pause_trigger_covers_war_civil_war_and_rebels():
    """Any war pauses it: an independence war against one's own rebels is no civil war (run 4b90876a, Ottomans 1608)."""
    body = _block((COMMON / "scripted_triggers" / "pp_enclave_triggers.txt").read_text(encoding="utf-8-sig"),
                  "pp_enclave_release_paused")
    assert re.search(r"\bat_war = yes\b", body)
    assert re.search(r"\bin_civil_war = yes\b", body)
    assert re.search(r"\bis_rebel_country = yes\b", body)


@pytest.mark.parametrize("action", ["create_province_subject", "pp_release_enclave_independence"])
def test_release_actions_check_the_pause(action):
    text = (COMMON / "generic_actions" / f"{action}.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"\bpp_enclave_release_paused = no\b", _block(text, "ai_prerequisite"))


@pytest.mark.parametrize("action", ["create_province_subject", "pp_release_enclave_independence"])
def test_release_runs_outside_the_target_province(action):
    """The province is destroyed once its last location of the nation changes owner, so every effect after that in its
    scope failed ("Scoped object is not valid. Type: Province" x 563 in the first month, EU5 1.4.1, 2026-10-15) and the
    new country stayed an independent one-location country without cores or truce. Only the pick runs in the province.
    """
    effect = _block((COMMON / "generic_actions" / f"{action}.txt").read_text(encoding="utf-8-sig"), "effect")
    assert re.search(r"scope:target_province = \{ pp_enclave_pick_piece = yes \}\s*scope:actor = \{ pp_enclave_release_piece = yes \}", effect)
    assert not re.search(r"scope:target_province = \{[^}]*pp_enclave_release_piece", effect)
    release = _block((COMMON / "scripted_effects" / "pp_enclave_effects.txt").read_text(encoding="utf-8-sig"),
                     "pp_enclave_release_piece")
    assert "pp_enclave_pick_piece" not in release
    # nothing in the release may lean on the current (province) scope: every land move goes through saved scopes/lists
    assert not re.search(r"^\t(?:random|every|any)_location_in_province\b", release, re.MULTILINE)


def test_colonial_nations_and_player_subjects_are_exempt():
    """Colonial nations released their islands as one-location vassals of the overlord (Jan, Portugal 1492: 16 in the
    Caribbean); a player's subjects would hand the player new subjects."""
    body = _block((COMMON / "scripted_triggers" / "pp_enclave_triggers.txt").read_text(encoding="utf-8-sig"),
                  "pp_enclave_release_exempt")
    assert re.search(r"\bsubject_type = subject_type:colonial_nation\b", body)
    assert re.search(r"\boverlord \?= \{ is_ai = no \}", body)


@pytest.mark.parametrize("action", ["create_province_subject", "pp_release_enclave_independence"])
def test_release_actions_check_the_exemption(action):
    text = (COMMON / "generic_actions" / f"{action}.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"\bpp_enclave_release_exempt = no\b", _block(text, "ai_prerequisite"))
