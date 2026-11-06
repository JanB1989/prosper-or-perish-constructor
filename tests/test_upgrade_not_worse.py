"""An upgrade is never worse per level than the building it replaces (2026-11-06, Jan).

A building that names another as `obsolete` replaces it: once researched, the old one cannot be built any more, so the
upgrade is the only way to grow the site. Run 77768726 and a player found the Clay Washmill making less clay and earning
a third of the Clay Pit's profit per level since the June move to one worker per level (its outputs were divided by 4,
the pit's were not). Nothing checked it.

The compiled mod, every building that replaces a producing building, at base goods prices (`production_gate.load_prices`,
what the labour, gate and tier-line passes read), in every age from the upgrade's unlock with the methods each building
knows by then:

- earns: each slot's most profitable method (what the AI's method switch picks), summed: the upgrade's profit per level
  is at least the old building's;
- makes: each slot's most valuable method (every slot running), summed output value: the upgrade's is at least the old
  building's.

No exceptions. Amounts are rounded to 3 decimals, so values within TOLERANCE count as equal.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest
from eu5gameparser.domain.availability import AGE_ORDER, annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data

from prosper_or_perish_constructor import production_gate as pg

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
TOLERANCE = 0.0005


@dataclass(frozen=True)
class World:
    buildings: dict[str, dict]
    methods: dict[str, dict]
    shared: dict[str, list[str]]  # production method group -> its shared methods
    prices: dict[str, float]

    def slots(self, building: str) -> list[list[str]]:
        row = self.buildings[building]
        slots = [list(group) for group in row["unique_production_method_groups"] or []]
        for name in row["possible_production_methods"] or []:
            group = self.methods[name]["production_method_group"] if name in self.methods else None
            slots.append(self.shared.get(group, [name]) if group else [name])
        return slots

    def produces(self, building: str) -> bool:
        return any(self.methods[name]["produced"] for slot in self.slots(building) for name in slot if name in self.methods)

    def value(self, method: dict) -> float:
        return (method["output"] or 0.0) * self.prices.get(method["produced"] or "", 0.0)

    def cost(self, method: dict) -> float:
        amounts = zip(method["input_goods"] or [], method["input_amounts"] or [])
        return sum(amount * self.prices.get(good, 0.0) for good, amount in amounts if amount and amount > 0)

    def known(self, building: str, age: int) -> list[list[dict]]:
        return [
            [self.methods[name] for name in slot if name in self.methods and age_index(self.methods[name], "effective_") <= age]
            for slot in self.slots(building)
        ]

    def earns(self, building: str, age: int) -> float:
        return sum(max(self.value(m) - self.cost(m) for m in slot) for slot in self.known(building, age) if slot)

    def makes(self, building: str, age: int) -> float:
        return sum(max(self.value(m) for m in slot) for slot in self.known(building, age) if slot)

    def pairs(self) -> list[tuple[str, str]]:
        """(upgrade, the producing building it replaces), every `obsolete` line of the compiled mod."""
        return [
            (tag, old)
            for tag, row in sorted(self.buildings.items())
            for old in row["obsolete_buildings"] or []
            if old in self.buildings and self.produces(old)
        ]


def age_index(row: dict, prefix: str = "") -> int:
    """The age a building or method becomes available (0 = from the start); country-specific unlocks only where there
    is no general one."""
    age = row[f"{prefix}general_unlock_age"] or row[f"{prefix}specific_unlock_age"]
    return AGE_ORDER.index(age) if age else 0


def load_world(root: Path = ROOT, project: Path = PROJECT) -> World:
    data = load_eu5_data(profile="constructor", load_order_path=root / "constructor.load_order.toml")
    annotated = annotate_building_data_availability(data.building_data, data.advancements)
    methods = {row["name"]: row for row in annotated.production_methods.to_dicts()}
    shared: dict[str, list[str]] = defaultdict(list)
    for row in methods.values():
        if row["building"] is None and row["production_method_group"]:
            shared[row["production_method_group"]].append(row["name"])
    return World(
        buildings={row["name"]: row for row in annotated.buildings.to_dicts()},
        methods=methods,
        shared=dict(shared),
        prices=pg.load_prices(root, project),
    )


def shortfalls(world: World, measure: str) -> list[str]:
    rows = []
    for tag, old in world.pairs():
        for age in range(age_index(world.buildings[tag]), len(AGE_ORDER)):
            new_value = getattr(world, measure)(tag, age)
            old_value = getattr(world, measure)(old, age)
            if new_value < old_value - TOLERANCE:
                rows.append(f"{old} -> {tag} in {AGE_ORDER[age]}: {old_value:.3f} -> {new_value:.3f}")
                break
    return rows


@pytest.fixture(scope="module")
def world() -> World:
    return load_world()


def test_the_check_sees_the_upgrade_lines(world: World) -> None:
    """A parser change that loses the obsolete lines or the methods must not leave the checks below passing on nothing."""
    pairs = world.pairs()
    assert len(pairs) > 100
    assert ("clay_washmill", "clay_pit") in pairs and ("iron_mine_deep", "iron_mine") in pairs
    assert world.earns("clay_pit", 0) > 0 and world.makes("iron_mine", 0) > world.earns("iron_mine", 0) > 0


def test_an_upgrade_earns_at_least_what_it_replaces(world: World) -> None:
    """Profit per level, each slot's most profitable known method, base prices."""
    rows = shortfalls(world, "earns")
    assert not rows, "profit per level falls:\n" + "\n".join(rows)


def test_an_upgrade_makes_at_least_what_it_replaces(world: World) -> None:
    """Output value per level with every slot at its most valuable known method, base prices."""
    rows = shortfalls(world, "makes")
    assert not rows, "output value per level falls:\n" + "\n".join(rows)
