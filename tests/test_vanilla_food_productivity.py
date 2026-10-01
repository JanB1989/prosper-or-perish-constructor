"""Prosper or Perish has no vanilla food productivity: the net of every vanilla food modifier is exactly 0 in game."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor.vanilla_food_productivity import (
    FOOD_PRODUCTIVITY_KEYS,
    FOOD_SCRIPT_VALUE_PREFIX,
    LEGACY_NIL_PATHS,
    NIL_SCRIPT_VALUES_PATH,
    food_productivity_rows,
    nil_bytes,
    nil_script_value_files,
    script_value_files,
    script_values,
    write_nil_script_values,
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
    for path in script_value_files(_vanilla_game()):
        names |= {e.key for e in parse_file(path).entries if e.key.startswith(FOOD_SCRIPT_VALUE_PREFIX)}
    return names


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def test_script_value_override_rule_of_eu5_1_4(tmp_path: Path) -> None:
    """The rule the game follows (in-game error.log 2026-10-01, the executable, a 1.3 run), which the resolver models:
    a scalar REPLACE: is dropped (the 1.4 nil that left vanilla's +7.5 % in game), a block REPLACE: replaces, a plain
    redefinition loses to the first definition, a same-name file replaces vanilla's file."""
    vanilla = tmp_path / "vanilla/game"
    mod = tmp_path / "mod"
    sv = Path("main_menu/common/script_values")
    _write(vanilla / sv / "default_values.txt", "monthly_food_productivity_severe_bonus = 0.075\nother_value = 3\n")
    _write(mod / sv / "pp_food_productivity_nil.txt", "REPLACE:monthly_food_productivity_severe_bonus = 0\n")
    assert script_values(vanilla, mod)["monthly_food_productivity_severe_bonus"] == 0.075     # the old setup: no effect
    _write(mod / sv / "pp_food_productivity_nil.txt", "REPLACE:monthly_food_productivity_severe_bonus = { value = 0 }\n")
    assert script_values(vanilla, mod)["monthly_food_productivity_severe_bonus"] == 0.0       # block form replaces
    _write(mod / sv / "pp_food_productivity_nil.txt", "monthly_food_productivity_severe_bonus = 0\n")
    assert script_values(vanilla, mod)["monthly_food_productivity_severe_bonus"] == 0.075     # duplicate: first wins
    _write(mod / sv / "00_first.txt", "monthly_food_productivity_severe_bonus = 0\n")
    assert script_values(vanilla, mod)["monthly_food_productivity_severe_bonus"] == 0.0       # sorts first: wins
    (mod / sv / "00_first.txt").unlink()
    (mod / sv / "pp_food_productivity_nil.txt").write_text("", encoding="utf-8")
    result = write_nil_script_values(mod, vanilla)
    assert result.zeroed == 1 and result.removed == ("main_menu/common/script_values/pp_food_productivity_nil.txt",)
    values = script_values(vanilla, mod)
    assert values["monthly_food_productivity_severe_bonus"] == 0.0 and values["other_value"] == 3.0   # same-name copy


def test_nil_copy_changes_only_the_food_values() -> None:
    data = "﻿# tiers\r\nstability_weak_bonus = 2.5\r\nmonthly_food_productivity_weak_penalty = -0.05 # note\r\n\tmonthly_food_productivity_unique_bonus=0.25\r\n".encode()
    out, zeroed = nil_bytes("x.txt", data)
    assert zeroed == 2
    assert out == "﻿# tiers\r\nstability_weak_bonus = 2.5\r\nmonthly_food_productivity_weak_penalty = 0 # note\r\n\tmonthly_food_productivity_unique_bonus=0\r\n".encode()


def test_every_vanilla_food_productivity_script_value_is_zero_in_game() -> None:
    vanilla = _vanilla_food_script_values()
    assert vanilla, "vanilla defines no monthly_food_productivity_* script values any more: revisit the nil"
    values = script_values(_vanilla_game(), MOD_ROOT)
    assert {name: values.get(name) for name in vanilla if values.get(name) != 0.0} == {}


def test_mod_copy_of_vanilla_script_values_matches_the_game() -> None:
    """The mod's same-name copy is vanilla's file byte for byte except the food values (0); after a game update this
    fails until `ppc build` regenerates the copy from the new game files."""
    wanted = nil_script_value_files(_vanilla_game())
    assert NIL_SCRIPT_VALUES_PATH in wanted
    stale = [str(rel) for rel, (data, _) in wanted.items() if not (MOD_ROOT / rel).is_file() or (MOD_ROOT / rel).read_bytes() != data]
    assert stale == [], "rebuild (ppc build): the mod's copy differs from the vanilla file with food values zeroed"
    assert [str(p) for p in LEGACY_NIL_PATHS if (MOD_ROOT / p).exists()] == []


def test_mod_script_values_use_no_scalar_replace() -> None:
    """EU5 1.4 drops a scalar `REPLACE:name = N` on a script value (read as the link replace:name)."""
    bad = [
        f"{path.relative_to(MOD_ROOT)}: {e.key}"
        for path in script_value_files(MOD_ROOT)
        for e in parse_file(path).entries
        if ":" in e.key and not isinstance(e.value, CList)
    ]
    assert bad == []


def test_food_productivity_script_values_are_read_only_as_food_modifiers() -> None:
    """Zeroing them is safe only while nothing but a food percentage reads them (vanilla and mod, script, GUI and
    localization)."""
    use = re.compile(rf"\b{FOOD_SCRIPT_VALUE_PREFIX}[a-z_]+")
    allowed = re.compile(rf"^\s*(?:{'|'.join(FOOD_PRODUCTIVITY_KEYS)})\s*=\s*{FOOD_SCRIPT_VALUE_PREFIX}[a-z_]+\s*(?:#.*)?$")
    other: list[str] = []
    for root in (_vanilla_game(), MOD_ROOT):
        for pattern in ("*.txt", "*.gui", "*.yml"):
            for path in root.rglob(pattern):
                if path.parent.name == "script_values" and path.name == NIL_SCRIPT_VALUES_PATH.name:
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
    """Food comes from farms, crops and storage; the mod's own objects (World Builder classes such as Thicket that
    copy a vanilla class, tooltip views) carry no food percentage either."""
    added = [f"{r.directory}/{r.obj} {r.key} = {r.net:g}" for r in _rows() if not r.in_vanilla and abs(r.net) > 1e-9]
    assert added == []
