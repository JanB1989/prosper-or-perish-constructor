"""Every building the game loads does something (2026-10-24, Jan: no building without an effect, no inert stubs).

A building has an effect when one of its modifier blocks carries a non-zero value or one of its production methods
makes a good. Checks the merged building types as the game loads them (vanilla plus the built mod; REPLACE / INJECT
as the engine applies them)."""

from __future__ import annotations

from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile

ROOT = Path(__file__).resolve().parents[1]


def _numbers(node) -> list[float]:
    out: list[float] = []
    if isinstance(node, CList):
        for entry in node.entries:
            out.extend(_numbers(entry.value))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append(float(node))
    elif isinstance(node, str):
        try:
            out.append(float(node))
        except ValueError:
            out.append(1.0)   # a script value or other named amount: an effect
    return out


def _has_effect(body: CList) -> bool:
    for entry in body.entries:
        key = str(entry.key)
        if key.endswith("modifier") and any(v != 0 for v in _numbers(entry.value)):
            return True
        if key == "unique_production_methods" and isinstance(entry.value, CList):
            if any(isinstance(m.value, CList) and m.value.values("produced") for m in entry.value.entries):
                return True
        if key == "possible_production_methods" and isinstance(entry.value, CList) and entry.value.items:
            return True
    return False


def test_every_building_has_an_effect() -> None:
    profile = load_profile("constructor", load_order_path=ROOT / "constructor.load_order.toml")
    buildings = load_merged_directory(profile, "building_types", scope="in_game", include_scalars=True)
    inert = sorted(str(e.key) for e in buildings.entries if isinstance(e.value, CList) and not _has_effect(e.value))
    assert inert == []
