"""The mod's define overrides only set defines the game knows.

A key vanilla does not define is ignored by the game, so a rename in a game update (EU5 1.4 renamed the building
profit-margin gate) silently drops a balance setting. This fails as soon as vanilla no longer defines a key we set.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.defines import load_define_data

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
DEFINES = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "loading_screen/common/defines"


@cache
def _vanilla_keys() -> frozenset[tuple[str, str]]:
    data = load_define_data(profile="vanilla", load_order_path=LOAD_ORDER)
    return frozenset(data.defines.select("group", "name").iter_rows())


def _mod_keys() -> list[tuple[str, str, str]]:
    keys = []
    for path in sorted(DEFINES.glob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                keys += [(path.name, entry.key, child.key) for child in entry.value.entries]
    return keys


# Defines the engine registers and reads although vanilla's files do not set them (EU5 1.4, checked 2026-10-06).
HIDDEN_ENGINE_DEFINES = {("NAI", "AI_TOWN_RIGHTS_REPLACE_CHANCE")}


def test_every_define_the_mod_sets_exists_in_vanilla() -> None:
    vanilla = _vanilla_keys() | HIDDEN_ENGINE_DEFINES
    assert vanilla, "no vanilla defines loaded"
    keys = _mod_keys()
    assert keys, "no mod defines found"
    unknown = [f"{name}: {group}.{key}" for name, group, key in keys if (group, key) not in vanilla]
    assert not unknown, "defines vanilla does not know (renamed or removed in a game update?):\n" + "\n".join(unknown)


def _mod_values() -> dict[tuple[str, str], str]:
    values = {}
    for path in sorted(DEFINES.glob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                values.update({(entry.key, child.key): str(child.value) for child in entry.value.entries})
    return values


def test_food_growth_terms_are_off() -> None:
    """Growth from stored food is the Stored Food modifier (stored_food.py); the engine's storage and surplus
    terms would add growth on top of it."""
    values = _mod_values()
    assert float(values[("NPop", "FOOD_STORAGE_POP_GROWTH")]) == 0
    assert float(values[("NPop", "FOOD_SURPLUS_POP_GROWTH")]) == 0


def test_building_profit_gates_use_the_1_4_names() -> None:
    """1.4: the margin gate is AI_BUILDING_PROFIT_MARGIN_THRESHOLD; AI_BUILDING_PROFIT_THRESHOLD is a raw-profit floor."""
    set_keys = {(group, key) for _, group, key in _mod_keys()}
    assert ("NAI", "AI_BUILDING_PROFIT_MARGIN_THRESHOLD") in set_keys


def test_peace_deals_take_connected_land_only() -> None:
    """Border gore (docs/peace_deal_rulebook.md): a location that does not touch the taker's land (or land already in
    the deal) scores x 1/ADJECENT, which is exactly 0 only above 100000 (fixed point, 5 decimals). FROM_WORTH_MULT
    scales every location so connected land keeps vanilla's value of 5 x 5."""
    values = _mod_values()
    adjacent = float(values[("NAI", "AI_CONQUER_TREATY_DESIRE_ADJECENT")])
    worth_mult = float(values[("NAI", "AI_CONQUER_TREATY_DESIRE_FROM_WORTH_MULT")])
    assert adjacent > 100000
    assert abs(adjacent * worth_mult - 25) < 0.05
    # the one exception (conquest preferences outside the home region) is a scripted peace term
    assert (ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "common"
            / "peace_treaties" / "pp_cede_preferred_location.txt").exists()
