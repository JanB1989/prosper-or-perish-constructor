"""Every building the game loads does something (2026-10-24, Jan: no building without an effect, no inert stubs).

A building has an effect when one of its modifier blocks carries a non-zero value or one of its production methods
makes a good. Checks the merged building types as the game loads them (vanilla plus the built mod; REPLACE / INJECT
as the engine applies them)."""

from __future__ import annotations

from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig, load_merged_directory, load_profile
from prosper_or_perish_constructor.vanilla_food_productivity import script_values

ROOT = Path(__file__).resolve().parents[1]


def _numbers(node, values: dict[str, float]) -> list[float]:
    out: list[float] = []
    if isinstance(node, CList):
        for entry in node.entries:
            out.extend(_numbers(entry.value, values))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append(float(node))
    elif isinstance(node, str):
        try:
            out.append(float(node))
        except ValueError:
            # a script value with the mod's number (a zeroed food value is no effect); a formula or other named amount is
            number = values.get(node, 1.0)
            out.append(1.0 if number != number else number)
    return out


def _has_effect(body: CList, values: dict[str, float]) -> bool:
    for entry in body.entries:
        key = str(entry.key)
        if key.endswith("modifier") and any(v != 0 for v in _numbers(entry.value, values)):
            return True
        if key == "unique_production_methods" and isinstance(entry.value, CList):
            if any(isinstance(m.value, CList) and m.value.values("produced") for m in entry.value.entries):
                return True
        if key == "possible_production_methods" and isinstance(entry.value, CList) and entry.value.items:
            return True
    return False


def test_every_building_has_an_effect() -> None:
    load_order = ROOT / "constructor.load_order.toml"
    profile = load_profile("constructor", load_order_path=load_order)
    values = script_values(LoadOrderConfig.load(load_order).vanilla_root / "game", ROOT / "mod" / "pp")
    buildings = load_merged_directory(profile, "building_types", scope="in_game", include_scalars=True)
    inert = sorted(
        str(e.key) for e in buildings.entries if isinstance(e.value, CList) and not _has_effect(e.value, values)
    )
    assert inert == []
