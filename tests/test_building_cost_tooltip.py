"""The building cost tooltip (2026-11-06, Jan): the price multiplier is a level bucket that multiplies the cost and a
construction efficiency bucket that divides it. Only the building-only level line (vanilla BUILDING_LEVEL_COST_MOD) names
them; the shared price keys stay vanilla, because every price tooltip uses them (war costs pass their own scale text)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOC = ROOT / "mod" / "pp" / "main_menu" / "localization"
OVERRIDES = LOC / "replace" / "english" / "pp_vanilla_overrides_l_english.yml"
SHARED_PRICE_KEYS = ("SCALE_IMPACT_ON_PRICE", "PRICE_FURTHER_MODIFIED", "MARKET_PRICE_IMPACT_HEADER")


def _level_line() -> str:
    found = re.search(r'(?m)^ BUILDING_LEVEL_COST_MOD: "(.*)"$', OVERRIDES.read_text(encoding="utf-8-sig"))
    assert found, "BUILDING_LEVEL_COST_MOD override missing"
    return found.group(1)


def test_level_line_is_red_when_it_raises_the_cost() -> None:
    line = _level_line()
    assert "$MOD|2-%=$" in line  # vanilla |2+%= showed the raise in green
    assert "$LEVEL|0Y$" in line and "[BUILDING_TYPE.GetNameWithNoTooltip]" in line


def test_level_line_names_both_buckets() -> None:
    rows = _level_line().split("\\n")
    assert rows[0] == "#T Level#!, multiplies the cost:"
    assert rows[-1] == "#T Construction Efficiency#!, divides the cost:"


def test_shared_price_keys_stay_vanilla() -> None:
    pattern = re.compile(rf"(?m)^\s*({'|'.join(SHARED_PRICE_KEYS)}):")
    offenders = [str(path.relative_to(LOC)) for path in LOC.rglob("*.yml") if pattern.search(path.read_text(encoding="utf-8-sig"))]
    assert offenders == []
