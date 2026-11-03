"""Laborers and soldiers are lower class; what the goods give the upper class they keep per good.

In a pop type, upper = yes also decides culture and religion: a pop the game creates at game start then takes the owner's
primary culture and state religion (2026-11-03: 92 % of laborers, vanilla 51 %, 8 million Mongols in Yuan China). The goods'
upper lines come from vanilla, so each one has a laborers and soldiers line in goods/pp_goods_adjustments.txt and demand
does not move.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from prosper_or_perish_constructor import cap_tooltips
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "pp"
GOODS = MOD_ROOT / "in_game/common/goods"
# good -> the block its upper line sits in, and the value. Lumber is the one exception, see the test below.
UPPER_LINES = {
    "coal": ("demand_multiply", 25.0),
    "wine": ("demand_multiply", 10.0),
    "fur": ("demand_add", 0.05),
    "wheat": ("demand_multiply", 2.5),
    "maize": ("demand_multiply", 2.0),
    "rice": ("demand_multiply", 2.0),
    "millet": ("demand_multiply", 2.0),
    "legumes": ("demand_multiply", 2.0),
    "potato": ("demand_multiply", 2.0),
    "olives": ("demand_multiply", 2.0),
    "fruit": ("demand_multiply", 2.0),
    "beeswax": ("demand_multiply", 2.0),
    "porcelain": ("demand_add", 0.009),
    "liquor": ("demand_multiply", 5.0),
    "beer": ("demand_multiply", 5.0),
    "masonry": ("demand_multiply", 1.5),
    "furniture": ("demand_multiply", 10.0),
}
LUMBER = ("demand_multiply", 5.0)


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


@pytest.mark.parametrize("good", UPPER_LINES)
def test_workers_keep_the_upper_line_of_each_good(good: str) -> None:
    kind, value = UPPER_LINES[good]
    kept = dict(_blocks(_inject(good), kind))
    assert _values(kept[kind]) == {"laborers": value, "soldiers": value}


def test_lumber_still_cancels_all_pop_demand() -> None:
    """Vanilla 0.00025 x5 for the upper class; the inject takes each type's own amount back to 0."""
    add = _values(dict(_blocks(_inject("lumber"), "demand_add"))["demand_add"])
    assert add["laborers"] == add["soldiers"] == add["peasants"] == -0.00025
    assert add["nobles"] == add["clergy"] == add["burghers"] == -0.00125


def test_the_list_is_every_upper_line_in_vanilla() -> None:
    """A new upper line after a game update needs a line for laborers and soldiers too."""
    root = cap_tooltips.game_root(vanilla_root(ROOT, ROOT / "constructor.toml"))
    folder = root / "in_game/common/goods"
    if not folder.is_dir():
        pytest.skip("no vanilla game files")
    found = {}
    for path in sorted(folder.glob("*.txt")):
        for good, body in _blocks(_text(path), r"[a-z_]+"):
            for kind, block in _blocks(body, "demand_add|demand_multiply|wealth_impact_threshold"):
                values = _values(block)
                if "upper" in values:
                    found[good] = (kind, values["upper"])
    assert found == {**UPPER_LINES, "lumber": LUMBER}
