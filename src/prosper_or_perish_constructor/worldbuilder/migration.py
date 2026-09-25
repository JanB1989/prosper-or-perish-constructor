"""EU5 market migration, one monthly tick (engine rules measured in game 2026-09-25; docs/migration_rulebook.md).

The engine works on locations: every owned location whose attraction is not above its market's average and that
holds at least 1,000 people picks one target (same owner first, the best gain in attraction discounted by distance)
and each of its allowed pops sends ``max(1 person, size x migration factor x speed)`` there if the target has room for
that pop type. ``monthly_flows`` implements exactly that; ``attraction`` and the scale helpers rebuild the parts of
attraction and speed that change during a simulation. ``food_sim`` drives it on province pools (``migration = true``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

# pop_types/00_default.txt migration_factor (nobles, clergy and tribesmen use the default 1)
MIGRATION_FACTOR = {"nobles": 1.0, "clergy": 1.0, "burghers": 0.5, "laborers": 0.1, "soldiers": 0.05, "peasants": 0.1,
                    "tribesmen": 1.0, "slaves": 0.01}
# country_base_values: which types may migrate without a local or global *_migration_allowed modifier
BASE_ALLOWED = frozenset({"nobles", "clergy", "burghers"})
STARVING_ALLOWED = frozenset({"laborers", "peasants"})    # province_starving (mod; tribesmen removed)
UNCAPPED = frozenset({"peasants"})                         # no population_ratio room check
GLOBAL_SPEED = 0.0001
STARVING_SPEED = 0.015
OVERPOP_SPEED = 0.0025
MIN_AMOUNT = 0.001          # one person per moving pop
MIN_SOURCE_POP = 1.0        # k people: smaller locations never send
DECAY_PX = 480.0            # target score = gain x exp(-map pixels / 480)
DECAY_KM = 900.0            # the same on calibrated lon/lat (slightly less exact than pixels)


@dataclass
class Place:
    """A location (or a pool standing for several). Sizes in thousands of people."""

    key: str
    owner: str
    market: str
    attraction: float
    speed: float                                   # (global + local speed) x (1 + speed modifiers)
    allowed: frozenset
    pops: dict = field(default_factory=dict)       # type -> [(size_k, religion)]
    caps: dict | None = None                       # type -> population_ratio; None = every type has room
    religion: str | None = None                    # dominant religion of the location
    owner_religion: str | None = None              # primary religion of the owner
    owned: bool = True
    weight: float = 1.0                            # locations it stands for (market average)

    def population(self) -> float:
        return sum(size for pops in self.pops.values() for size, _ in pops)

    def room(self, pop_type: str) -> bool:
        if self.caps is None or pop_type in UNCAPPED:
            return True
        cap = self.caps.get(pop_type)
        return cap is not None and sum(size for size, _ in self.pops.get(pop_type, ())) < cap


@dataclass(frozen=True)
class Flow:
    source: str
    target: str
    pop_type: str
    religion: str | None
    amount: float


def market_lists(places: Iterable[Place]) -> tuple[dict[str, float], set[str]]:
    """Market average attraction (weighted by the locations a place stands for) and the receivers above it."""
    total: dict[str, float] = {}
    weight: dict[str, float] = {}
    places = list(places)
    for p in places:
        total[p.market] = total.get(p.market, 0.0) + p.attraction * p.weight
        weight[p.market] = weight.get(p.market, 0.0) + p.weight
    average = {m: total[m] / weight[m] for m in total if weight[m] > 0}
    receivers = {p.key for p in places if p.attraction > average.get(p.market, math.inf)}
    return average, receivers


def choose_target(source: Place, receivers: Iterable[Place], distance: Callable[[Place, Place], float],
                  decay: float = DECAY_PX) -> Place | None:
    gainers = [r for r in receivers if r.market == source.market and r.attraction > source.attraction and r.key != source.key]
    own = [r for r in gainers if r.owner == source.owner]
    best, best_score = None, 0.0
    for r in own or gainers:
        score = (r.attraction - source.attraction) * math.exp(-distance(source, r) / decay)
        if score > best_score:
            best, best_score = r, score
    return best


def monthly_flows(places: Iterable[Place], distance: Callable[[Place, Place], float], decay: float = DECAY_PX,
                  min_source_pop: float = MIN_SOURCE_POP, min_amount: float = MIN_AMOUNT) -> list[Flow]:
    """All market-migration flows of one monthly tick, from the state just before it."""
    places = list(places)
    _, receiver_keys = market_lists(places)
    receivers: dict[str, list[Place]] = {}
    for p in places:
        if p.key in receiver_keys:
            receivers.setdefault(p.market, []).append(p)
    flows: list[Flow] = []
    for s in places:
        if not s.owned or s.key in receiver_keys or s.population() < min_source_pop:
            continue
        target = choose_target(s, receivers.get(s.market, ()), distance, decay)
        if target is None:
            continue
        foreign = target.owner != s.owner
        for pop_type, pops in s.pops.items():
            if pop_type not in s.allowed or not target.room(pop_type):
                continue
            factor = MIGRATION_FACTOR.get(pop_type, 1.0)
            for size, religion in pops:
                if size <= 0:
                    continue
                if foreign and religion not in (target.owner_religion, target.religion):
                    continue
                flows.append(Flow(s.key, target.key, pop_type, religion, max(min_amount, size * factor * s.speed)))
    return flows


# ------------------------------------------------------------------------------------------ attraction and speed parts
def free_land_scales(pop_k: float, capacity_k: float) -> tuple[float, float, float]:
    """(abundant_free_land, available_free_land, overpopulation) scales of a location."""
    if capacity_k <= 0:
        return 0.0, 0.0, 0.0
    x = pop_k / capacity_k
    if x < 0.1 and pop_k < 10.0:
        return 1.0 - x, 0.0, 0.0
    if x < 1.0:
        return 0.0, 1.0 - x, 0.0
    return 0.0, 0.0, x - 1.0


def surplus_jobs_scale(laborer_jobs_k: float, laborers_k: float, cap: float = 1.0) -> float:
    return min(cap, max(0.0, laborer_jobs_k - laborers_k))


DYNAMIC_TERMS = {
    "starving": -7.5,
    "abundant_free_land": 2.0,
    "available_free_land": 1.0,
    "overpopulation": -0.25,
    "surplus_jobs": 2.0,
    "unemployed_peasants_k": -0.001,
    "food_years": 0.045,
    "prosperity": 0.1,
    "development": 0.0025,
}


def dynamic_attraction(*, starving: bool, pop_k: float, capacity_k: float, food_years: float = 0.0,
                       surplus_jobs: float = 0.0, unemployed_peasants_k: float = 0.0, prosperity: float = 0.0,
                       development: float = 0.0) -> float:
    """The attraction terms a simulation moves; add the location's fixed part (``fixed_attraction``)."""
    ab, av, op = free_land_scales(pop_k, capacity_k)
    t = DYNAMIC_TERMS
    return (t["starving"] * starving + t["abundant_free_land"] * ab + t["available_free_land"] * av
            + t["overpopulation"] * op + t["surplus_jobs"] * surplus_jobs
            + t["unemployed_peasants_k"] * unemployed_peasants_k + t["food_years"] * min(2.0, max(0.0, food_years))
            + t["prosperity"] * max(0.0, prosperity) + t["development"] * development)


def fixed_attraction(*, capital: bool = False, province_capital: bool = False, market_center: bool = False,
                     static_modifiers: float = 0.0, buildings: float = 0.0, country: float = 0.0) -> float:
    """``location_base_values`` + capitals/market centre + the summed flat modifiers (RGO bonus, lake, town rights,
    events, cabinet actions, employed buildings) + the country's global and rural/non-rural attraction."""
    return 0.1 + 0.025 * capital + 0.01 * province_capital + 0.025 * market_center + static_modifiers + buildings + country


def speed(*, starving: bool, overpopulation: float = 0.0, local_extra: float = 0.0, modifier: float = 0.0,
          global_speed: float = GLOBAL_SPEED) -> float:
    return max(0.0, (global_speed + STARVING_SPEED * starving + OVERPOP_SPEED * overpopulation + local_extra) * (1.0 + modifier))


def allowed_types(*, starving: bool, extra: Iterable[str] = ()) -> frozenset:
    return BASE_ALLOWED | (STARVING_ALLOWED if starving else frozenset()) | frozenset(extra)


def apply(places: Mapping[str, Place], flows: Iterable[Flow]) -> None:
    """Move the people: sources shrink pop by pop, targets grow in a pop of the same type and religion."""
    for f in flows:
        src, dst = places[f.source], places[f.target]
        pops = src.pops.get(f.pop_type, [])
        for i, (size, rel) in enumerate(pops):
            if rel == f.religion and size > 0:
                take = min(size, f.amount)
                pops[i] = (size - take, rel)
                break
        else:
            continue
        target = dst.pops.setdefault(f.pop_type, [])
        for i, (size, rel) in enumerate(target):
            if rel == f.religion:
                target[i] = (size + take, rel)
                break
        else:
            target.append((take, f.religion))
