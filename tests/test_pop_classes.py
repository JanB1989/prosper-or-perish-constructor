"""Laborers and soldiers are lower class, and devastation sends them back to the land by their own cap lines.

In a pop type, upper = yes also decides culture and religion: a pop the game creates at game start then takes the owner's
primary culture and state religion (2026-11-03: 92 % of laborers, vanilla 51 %, 8 million Mongols in Yuan China).
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "pp"
GOODS = MOD_ROOT / "in_game/common/goods"


def _text(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))


def _blocks(text: str, head: str):
    """(name, body) of every `name = { ... }` whose name matches head."""
    for match in re.finditer(rf"(?m)^\s*({head})\s*=\s*\{{", text):
        depth, at = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[at], 0)
            at += 1
        yield match.group(1), text[match.end() : at - 1]


def _values(body: str) -> dict[str, float]:
    return {key: float(value) for key, value in re.findall(r"(\w+)\s*=\s*(-?[0-9.]+)", body)}


def _inject(good: str) -> str:
    bodies = [body for _, body in _blocks(_text(GOODS / "pp_goods_adjustments.txt"), rf"TRY_INJECT:{good}")]
    assert len(bodies) == 1, good
    return bodies[0]


@pytest.mark.parametrize("pop_type", ["laborers", "soldiers"])
def test_workers_are_lower_class(pop_type: str) -> None:
    text = _text(MOD_ROOT / "in_game/common/pop_types/pp_pop_adjustments.txt")
    body = next(body for _, body in _blocks(text, rf"TRY_INJECT:{pop_type}"))
    assert not re.search(r"\bupper\s*=", body)


def test_lumber_still_cancels_all_pop_demand() -> None:
    """Vanilla 0.00025 x5 for the upper class; the inject takes each type's own amount back to 0."""
    add = _values(dict(_blocks(_inject("lumber"), "demand_add"))["demand_add"])
    assert add["laborers"] == add["soldiers"] == add["peasants"] == -0.00025
    assert add["nobles"] == add["clergy"] == add["burghers"] == -0.00125


def test_devastation_hits_higher_pops_harder() -> None:
    """Without the flag only devastation's own lines send workers back to the land; share of a typical location's type lost at full devastation."""
    text = _text(MOD_ROOT / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt")
    lines = _values(next(body for _, body in _blocks(text, "TRY_REPLACE:devastation")))
    people, laborers, soldiers = 14.0, 2.4, 0.035  # 1,000s, median rural location of a 10-year run
    ladder = [
        (lines["local_laborers_desired_pop"] + lines["local_laborers_desired_pop_scaled"] * people) / laborers,
        lines["local_soldiers_desired_pop_scaled"] * people / soldiers,
        lines["local_upper_class_capacity_modifier"],  # burghers: their cap is jobs
        lines["local_clergy_desired_pop_scaled"] / 0.005,  # vanilla location_base_values
        lines["local_nobles_desired_pop_scaled"] / 0.0025,
    ]
    assert ladder == sorted(ladder)
    assert 0 < ladder[0] < 0.28  # laborers: below their idle share, so jobs stay staffed
    assert ladder[-1] < 1  # never the whole type
