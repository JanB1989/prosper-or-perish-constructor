"""Prosper or Perish has no vanilla food productivity: the net of every vanilla food modifier is exactly 0."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor.vanilla_food_productivity import (
    FOOD_PRODUCTIVITY_KEYS,
    FOOD_SCRIPT_VALUE_PREFIX,
    NIL_SCRIPT_VALUES_PATH,
    food_productivity_rows,
)

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


@cache
def _vanilla_game() -> Path:
    return LoadOrderConfig.load(LOAD_ORDER).vanilla_root / "game"


@cache
def _rows():
    return tuple(food_productivity_rows(LOAD_ORDER))


def _vanilla_food_script_values() -> set[str]:
    names: set[str] = set()
    for path in sorted((_vanilla_game() / "main_menu/common/script_values").glob("*.txt")):
        names |= {e.key for e in parse_file(path).entries if e.key.startswith(FOOD_SCRIPT_VALUE_PREFIX)}
    return names


def test_every_vanilla_food_productivity_script_value_is_zeroed() -> None:
    vanilla = _vanilla_food_script_values()
    assert vanilla, "vanilla defines no monthly_food_productivity_* script values any more: revisit the nil"
    nil = {e.key: e.value for e in parse_file(MOD_ROOT / NIL_SCRIPT_VALUES_PATH).entries}
    assert {key.removeprefix("REPLACE:") for key in nil} == vanilla
    assert all(key.startswith("REPLACE:") and value == 0 for key, value in nil.items())


def test_food_productivity_script_values_are_read_only_as_food_modifiers() -> None:
    """Zeroing them is safe only while nothing but a food percentage reads them (vanilla and mod)."""
    use = re.compile(rf"\b{FOOD_SCRIPT_VALUE_PREFIX}[a-z_]+")
    allowed = re.compile(rf"^\s*(?:{'|'.join(FOOD_PRODUCTIVITY_KEYS)})\s*=\s*{FOOD_SCRIPT_VALUE_PREFIX}[a-z_]+\s*(?:#.*)?$")
    other: list[str] = []
    for root in (_vanilla_game(), MOD_ROOT):
        for path in root.rglob("*.txt"):
            if path.name in ("default_values.txt", NIL_SCRIPT_VALUES_PATH.name) and path.parent.name == "script_values":
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if FOOD_SCRIPT_VALUE_PREFIX not in text:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if use.search(line.split("#", 1)[0]) and not allowed.match(line):
                    other.append(f"{path}:{number}: {line.strip()}")
    assert other == []


def test_net_vanilla_food_productivity_is_zero() -> None:
    rows = _rows()
    assert sum(1 for r in rows if r.in_vanilla) > 100   # the merge found vanilla 1.4's food modifiers
    unresolved = [r for r in rows if r.unresolved]
    assert unresolved == [], "values that are neither numbers nor known script values"
    left = [
        f"{r.directory}/{r.obj} {r.block or '(top)'} {r.key}: vanilla {r.vanilla:g}, with the mod {r.net:g} ({' + '.join(r.raw)}; {r.source})"
        for r in rows
        if r.in_vanilla and abs(r.net) > 1e-9
    ]
    assert left == [], "vanilla food productivity left (or a stale cancelling negative):\n" + "\n".join(left)


def test_mod_objects_add_no_food_productivity() -> None:
    """Food comes from farms, crops and storage; the mod's own objects carry no food percentage either."""
    added = [f"{r.directory}/{r.obj} {r.key} = {r.net:g}" for r in _rows() if not r.in_vanilla and abs(r.net) > 1e-9]
    assert added == []
