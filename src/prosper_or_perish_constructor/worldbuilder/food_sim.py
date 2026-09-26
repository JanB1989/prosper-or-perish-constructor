"""Start-food validator: the calibrated population loop for every province pool (``ppc worldbuilder food-sim``).

The start placement writes one input row per province/owner pool (``input.csv``: pops, jobs, the location yields,
building food, market levels, food capacity); this module runs 96 months (1337-1345, the pre-plague window) of the
population loop of ``tools/province_food_sim.py --depop`` on all of them at once and reports the pools that lose a
quarter of their people, the pools pinned at the storage cap (over-supplied) and the world population change.

Per pool and month (rules calibrated on the pre-plague saves 1337.4 / 1341.3 / 1345.3):

* jobs = jobs0 x (N / N0) ^ 0.5; jobless = peasants and slaves - jobs; subsistence = jobless x yield;
* consumption = demand0 x N / N0 + overpopulation (+0.5 peasant food per unit of pop / capacity - 1, location by
  location) + the free-land modifiers (peasants -50 % on abundant land, below 10 % of capacity and 10k people,
  else -32 % on available land, each x 1 - pop / capacity per location; abundant land also forages +1 food; the
  fitted stand-in ``free_land`` of -0.4 x the drop below the start size is 0 since 2026-09-26), less the share the
  tribe feeds (``tribal_feeding`` x the demand-weighted
  tribal share of the pool's locations, scaled with the pool's tribal share), plus the tribesmen's own food
  (``tribesmen_food`` per 1,000, the pop type's ``pop_food_consumption``; negative = they feed the province). A
  province whose total consumption is zero or below gets no storage growth bonus (engine, verified 2026-09-25);
  the settled consumption is further scaled by prosperity (+50 % x P, P a pool state fitted on the 1342-1437 run:
  +0.018 x stored years - 0.0025 starving - 0.075 x P per year), winter (the climates' maximum winter level for three
  months, Dec-Feb north / Jun-Aug south) and a promotion drift of +0.15 % a year;
* tribesmen (engine, verified 2026-09-25): the location growth below also carries ``tribal_growth`` x tribal share for
  every pop; when it is positive tribesmen are born at it x ``tribal_land_births`` (0.75) x the free-land factor
  max(0, 1 - ``tribal_land_slope`` x pop / capacity) (the topographies' ``local_tribesmen_pop_growth = -1`` + 0.19 in the
  scaled free-land modifiers since 2026-09-26; slope fitted on the 1345 save), when it is negative they lose it
  unscaled like every pop type;
* unowned tribal land (owner ``---``, one pool per province, no buildings or markets): no owner, so no rank gate, no
  province food store, no storage bonus and no starving; its growth is ``tribal_growth`` x tribal share (plus the class
  rows' ``growth_offset``); no free-land modifier reaches it, so its tribesmen have no births (game-verified
  2026-09-26, Boror: only the tribesmen share in the growth tooltip);
  ``unowned_brake = false`` reproduces the engine before 2026-09-26, when the brake was a country modifier and unowned
  land got births x (1 + the free-land share) (tribesmen ~ +1 %/yr there);
* farms, villages and orchards run Provisioning from month 6 while the store is below ~11 months (their Sell leg
  pays above that); Cookshops serve every dish as Province Food from month 1 (they make no victuals);
* Taverns and Victualling Yards ramp their staffing 0.15 a month toward the sign of their profit per level at the
  market victuals price (2.7): the Tavern pays below 12 stored months, the Yard above 20; each staffed level moves
  60 food (a Tavern buys 2 victuals, a Yard packs 1.5); Taverns only get the victuals their market has (staffed
  Yards and other producers; pops compete); a starving pool loses the noble who staffs its Tavern at 0.09 a year;
* growth per year on owned land: -0.0048 + 0.0086 x stored years (cap 2) when fed, -0.0048 - 0.04 - 0.012 when
  starving;
* each September the harvest rolls like the mod's harvest system (``variable_harvests.toml``): a shock per sub-continent,
  then one severity per region from the profile the shock and the region's last harvest select, for every pool of the
  region (``pp_harvest_*``: peasant food consumption +0.30 .. -0.30); a seeded generator keeps runs reproducible;
  ``harvest_regional = false`` rolls each pool on its own, ``harvest = false`` turns the rolls off.
* ``migration = true`` replaces the starving out-migration sink by the engine's market migration (``migration.py``,
  docs/migration_rulebook.md) between pools: each pool stands for its locations (fixed attraction from the setup
  plus the monthly starving, free land, overpopulation, jobs and food-storage terms), the market average and the
  1,000-people sender floor are per location, targets are chosen with the km decay, capped pop types (all but peasants)
  find room while the target pool is below its start size (``migration_room``), and the moved people leave one pool
  and join the other.

``[worldbuilder.start.food_sim]`` in constructor.toml overrides every rule. The run validates the placement, it does
not forecast a campaign.
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping

from . import migration as mig

OUTPUT_RELATIVE_PATH = Path("artifacts/data/worldbuilder/food_sim")
# pp_harvest_<region>_<quality>: local_peasants_food_consumption per yearly roll, and its weight
HARVEST_CONS = ((0.30, 0.05), (0.20, 0.10), (0.11, 0.15), (0.0, 0.40), (-0.11, 0.15), (-0.20, 0.10), (-0.30, 0.05))
# the same values by severity, for the regional rolls of the mod's harvest system (variable_harvests.toml)
HARVEST_SEVERITY = {"abysmal": 0.30, "very_poor": 0.20, "poor": 0.11, "normal": 0.0,
                    "good": -0.11, "very_good": -0.20, "bountiful": -0.30}
HARVEST_CONFIG = Path(__file__).resolve().parents[3] / "variable_harvests.toml"
# pp_roll_region_harvest_for_<shock>_shock: the profile by the region's previous harvest (generate_variable_harvests.py)
HARVEST_ROUTES = {
    "bad": {"bad": "bad_persistent", "good": "neutral", "none": "shock_bad"},
    "neutral": {"bad": "memory_bad", "good": "memory_good", "none": "neutral"},
    "good": {"bad": "neutral", "good": "good_persistent", "none": "shock_good"},
}


def load_harvest_config(path: Path = HARVEST_CONFIG) -> dict[str, Any] | None:
    import tomllib

    return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _weighted(rng: random.Random, weights: Mapping[str, float]) -> str:
    x, acc = rng.random() * sum(weights.values()), 0.0
    for key, w in weights.items():
        acc += w
        if x < acc:
            return key
    return next(reversed(weights))


def roll_regional_harvests(rng: random.Random, cfg: Mapping[str, Any], regions: Mapping[str, list[str]],
                           previous: dict[str, str]) -> dict[str, str]:
    """One September of the mod's harvest system: a shock per sub-continent (bad / neutral / good), then per region a
    severity from the profile its shock and its previous harvest select; the result holds for every location of the
    region for the next year. ``regions`` maps sub-continent -> regions; ``previous`` region -> last severity."""
    out = {}
    for sub, regs in regions.items():
        shock = _weighted(rng, cfg["shock_weights"])
        for region in regs:
            last = previous.get(region, "normal")
            memory = "bad" if last in ("abysmal", "very_poor", "poor") else "good" if last in ("good", "very_good", "bountiful") else "none"
            out[region] = _weighted(rng, cfg["profiles"][HARVEST_ROUTES[shock][memory]])
    return out
# winter_<level>: every pop's local food consumption while the winter lasts (pp_population_growth_and_food_adjustments.txt)
WINTER_CONSUMPTION = {"none": 0.0, "mild": 0.125, "normal": 0.25, "severe": 0.375}
# the maximum winter level of each climate (in_game/common/climates: vanilla and the World Builder ha1300_climate_*),
# keyed like the World Builder location attributes (without the ha1300_climate_ prefix)
CLIMATE_WINTER = {
    "arctic": "severe", "subarctic": "severe",
    "continental": "normal", "continental_monsoon": "normal", "dry_summer_continental": "normal", "cold_steppe": "normal",
    "subpolar_oceanic": "normal",
    "oceanic": "mild", "highland_monsoon": "mild", "subtropical_monsoon": "mild", "cold_arid": "mild",
    "arid": "none", "hot_steppe": "none", "savanna": "none", "mediterranean": "none", "subtropical": "none",
    "tropical": "none", "tropical_monsoon": "none",
}


def winter_consumption(climate: str | None) -> float:
    """The winter consumption share of a location at its climate's maximum winter level."""
    key = str(climate or "").removeprefix("ha1300_climate_")
    return WINTER_CONSUMPTION[CLIMATE_WINTER.get(key, "none")]
SEPTEMBER = 5   # month index from the April start


@dataclass(frozen=True)
class SimRules:
    months: int = 96
    victuals_price: float = 2.7
    growth_base: float = -0.0048
    growth_per_year: float = 0.0086
    starving_growth: float = -0.04
    starving_migration: float = -0.012
    emp_elasticity: float = 0.5
    free_land: float = 0.0              # fitted stand-in (0.4 x the drop below the start size) before the free-land modifiers below
    # free-land modifiers (pp_capacity_pressure_effects.txt), engine-scaled per location (migration.free_land_scales)
    abundant_peasant_food: float = -0.5     # abundant_free_land local_peasants_food_consumption
    available_peasant_food: float = -0.32   # available_free_land local_peasants_food_consumption
    abundant_food: float = 1.0              # abundant_free_land local_monthly_food (foraging)
    # prosperity (0..1 per location; the mod's prosperity inject: every settled pop type +50 % food at 100 %), dynamics
    # fitted on the 100-year run 1342-1437 (saves r7bee, 249k location pairs): dP/yr = +0.0181 x stored years
    # - 0.0025 starving - 0.0747 x P, so ~0.24 at one stored year and ~0.49 at two
    prosperity_consumption: float = 0.5
    prosperity_per_year: float = 0.0181
    prosperity_starving: float = -0.0025
    prosperity_decay: float = 0.0747
    # winter (winter_mild/normal/severe: every pop +12.5 / 25 / 37.5 % food while it lasts): each location at its
    # climate's maximum level for ``winter_months`` months (Dec-Feb north, Jun-Aug south; the engine's winters are
    # random up to that level), scaled by ``winter_scale``
    winter_months: int = 3
    winter_scale: float = 1.0
    # promotion: settled food per head rose +0.15 %/yr in the same run (1.305 -> 1.501 per 1k, 1342-1437; cores up,
    # peasant frontiers down as peasants take the growth)
    consumption_drift: float = 0.0015
    noble_hazard: float = 0.09
    ramp: float = 0.15                  # staffing change per month (defines LAID_OFF / REHIRED_PERCENTAGE = 15)
    tavern_food: float = 60.0            # food per staffed Tavern level (local_monthly_food)
    yard_food: float = 60.0              # food per staffed Grange level (-local_monthly_food)
    harbor_yard_food: float = 20.0       # food per staffed harbour Victualling Yard level (-local_monthly_food)
    provision_month: int = 6
    provision_below_months: float = 11.4
    serve_month: int = 1
    pin_months: float = 24.0
    pinned_limit_months: int = 48
    collapse_share: float = 0.25
    tribal_share: float = 0.5
    # tribesmen (pp_pop_adjustments.txt, pp_capacity_pressure_effects.txt, pp_country_base_values.txt)
    tribal_growth: float = 0.0          # pop_percentage_impact local_population_growth (every pop in the location; removed
                                        # 2026-09-26, 0.006 / 0.012 before)
    tribal_land_slope: float = 0.75     # free-land factor 1 - slope x pop / capacity (1345 save: 0.75 at start capacity)
    tribal_land_births: float = 0.75    # local_tribesmen_pop_growth of the free-land modifiers (topography brake -1.0)
    unowned_brake: bool = True          # the topography brake also holds on unowned land (false: the pre-2026-09-26 country brake)
    tribal_feeding: float = 0.0         # -pop_percentage_impact local_pop_food_consumption (0 = the tribe feeds nobody)
    tribal_flat_food: float = 2.0       # pop_percentage_impact local_monthly_food of the tribesmen: food per location at 100 % tribal share
    tribal_tavern_premium: float = 0.0  # pop_percentage_impact local_province_food_purchase_output_modifier (mod: none;
                                        # -16 tested 2026-09-25: tribal pools starving 38 -> 92, rejected)
    start_staffed: float = 1.0          # the setup staffs every market level on day 0 (nb.eu5)
    harvest: bool = True
    harvest_regional: bool = True       # the mod's regional rolls (variable_harvests.toml); false: independent per pool
    seed: int = 1
    # market migration between pools (migration.py); off = the flat starving_migration sink above
    migration: bool = False
    migration_decay_km: float = 900.0
    migration_speed_modifier: float = 0.0   # country speed modifiers (1345: mostly -0.1 .. -0.4)
    migration_room: float = 1.0             # capped types (not peasants) find room while the target pool is below
                                            # this x its start size of the type (stand-in for population_ratio)
    # Tavern (per level; blueprints/accepted/buildings/tavern.yml)
    tavern_income: float = 3.34         # 0.167 offset x (1 + 19)
    tavern_victuals: float = 2.0
    tavern_labour: float = 0.2
    tavern_amount: float = 0.533        # province_food_purchase
    tavern_const: float = 15.0
    tavern_per_year: float = -8.0
    tavern_starving: float = 8.0
    tavern_cost: float = 2.0
    tavern_droop: float = -0.2
    # harbour Victualling Yard (per level; blueprints/accepted/buildings/victualling_yard.yml): 20 food and shipped
    # grain for 3 victuals, a storage leg at a third of the Grange's weight; its grain is bought at grain_price
    harbor_yard_victuals: float = 3.0   # Hand Packing 0.67 + a Grain Shipment 2.33
    harbor_yard_grain: float = 5.83
    grain_price: float = 1.0
    harbor_yard_amount: float = 0.33
    harbor_yard_droop: float = -0.067
    harbor_yard_cost: float = 5.09
    harbor_yard_labour: float = 0.6
    # Grange (per level; blueprints/accepted/buildings/grange.yml; the yard_* names predate the split)
    yard_victuals: float = 1.5          # Porters (loose stores)
    yard_packing_victuals: float = 0.0  # a Packing method's extra victuals (what-if; its goods cost is not modelled)
    yard_amount: float = 2.0            # province_food_sales (shared with the farms' Sell the Surplus)
    yard_const: float = -1.0
    yard_per_year: float = 8.0
    yard_droop: float = -0.2
    yard_cost: float = 30.52
    yard_labour: float = 0.2

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | None) -> "SimRules":
        raw = dict(raw or {})
        kwargs = {}
        for f in fields(cls):
            if f.name in raw:
                kwargs[f.name] = type(getattr(cls, f.name))(raw[f.name])
        return cls(**kwargs)

    def tavern_profit(self, years: float, starving: bool, staffed: float, tribal_share: float = 0.0) -> float:
        m = (1.0 + self.tavern_const + self.tavern_per_year * years + self.tavern_droop * staffed
             + self.tribal_tavern_premium * tribal_share)
        if starving:
            m += self.tavern_starving
        return (self.tavern_income - self.tavern_victuals * self.victuals_price - self.tavern_labour
                + self.tavern_amount * max(0.0, m) - self.tavern_cost)

    def yard_packed(self) -> float:
        return self.yard_victuals + self.yard_packing_victuals

    def yard_profit(self, years: float, staffed: float) -> float:
        m = 1.0 + self.yard_const + self.yard_per_year * years + self.yard_droop * staffed
        return (self.yard_packed() * self.victuals_price + self.yard_amount * max(0.0, m)
                - self.yard_cost - self.yard_labour)

    def harbor_yard_profit(self, years: float, staffed: float) -> float:
        m = 1.0 + self.yard_const + self.yard_per_year * years + self.harbor_yard_droop * staffed
        return (self.harbor_yard_victuals * self.victuals_price + self.harbor_yard_amount * max(0.0, m)
                - self.harbor_yard_cost - self.harbor_yard_labour - self.harbor_yard_grain * self.grain_price)


@dataclass
class Pool:
    owner: str
    province: str
    catchment: str
    pop0: float                 # k, tribesmen included
    tribesmen: float            # k at start
    demand0: float              # base food consumption of the settled pops at start (tribesmen's own food excluded)
    workers0: float             # peasants + slaves (k)
    jobs0: float                # of them in jobs (RGO, buildings)
    yield_: float               # food per 1k jobless worker
    flat_food: float            # building local food (scaled), markets excluded
    provision_food: float       # Province Food of the Provisioning methods (farms, villages, orchards)
    serve_food: float           # Cookshops' Serve output
    cookshop_levels: float
    taverns: float              # staffed Tavern levels
    yards: float                # staffed Grange levels
    capacity: float             # food capacity (max stored food)
    start_food: float
    victuals_demand: float      # the pops' and other buildings' victuals demand at start
    victuals_other_supply: float = 0.0
    harbor_yards: float = 0.0          # staffed harbour Victualling Yard levels (``yards`` counts the Granges)
    overpop: list = field(default_factory=list)   # [(peasants k, pop / capacity)] per location
    overpop_consumption: float = 0.5
    peasant_share: float = 0.6         # share of the demand the peasants eat (the harvest roll moves it)
    tribesmen_food: float = 0.0        # food per 1,000 tribesmen (pop type pop_food_consumption; negative = produce)
    tribal_fed_share: float = 0.0      # settled demand x tribal share of its location, over the settled demand
    # migration inputs (only read with migration = true)
    n_locations: float = 1.0
    lat: float = 0.0
    lon: float = 0.0
    pop_capacity: float = 0.0          # population capacity of the pool's locations (k)
    attraction_fixed: float = 0.1      # mean fixed migration attraction of its locations (base, development, statics)
    type_shares: dict = field(default_factory=dict)   # non-tribal pops by type, share of pop0 - tribesmen
    religion: str = ""                 # dominant pop religion
    growth_offset: float = 0.0         # location growth of the pool's class rows (death sources, e.g. disease burden)
    winter_cons: float = 0.0           # settled-demand-weighted winter consumption share at the climates' maximum levels
    region: str = ""                   # the harvest rolls per region and sub-continent (variable_harvests.toml)
    subcontinent: str = ""


def overpopulation(pool: Pool, f: float) -> float:
    return pool.overpop_consumption * sum(p * f * max(0.0, f * r - 1.0) for p, r, *_ in pool.overpop)


def free_land(pool: Pool, f: float, rules: SimRules) -> tuple[float, float]:
    """(peasant food change, foraging food) of the free-land modifiers, location by location: ``abundant_free_land``
    below 10 % of capacity and 10k people, else ``available_free_land`` below capacity, each scaled 1 - pop/capacity
    (migration.free_land_scales, engine-verified). Needs the location capacity in ``overpop`` (peasants, pop/capacity,
    capacity); older two-value rows carry no free-land effect."""
    cons = forage = 0.0
    for row in pool.overpop:
        if len(row) < 3 or row[2] <= 0:
            continue
        peasants, ratio, cap = row[0], row[1], row[2]
        abundant, available, _ = mig.free_land_scales(f * ratio * cap, cap)
        cons += peasants * f * (rules.abundant_peasant_food * abundant + rules.available_peasant_food * available)
        forage += rules.abundant_food * abundant
    return cons, forage


def _km(a: Pool, b: Pool) -> float:
    x = math.radians(b.lon - a.lon) * math.cos(math.radians((a.lat + b.lat) / 2))
    return 6371.0 * math.hypot(x, math.radians(b.lat - a.lat))


def migration_month(pools: list[Pool], N: list[float], base: list[float], starving: list[bool], food_years: list[float],
                    rules: SimRules, T: list[float] | None = None) -> tuple[list[float], list[float]]:
    """One monthly market-migration tick between pools; returns (out, in) in k per pool (migration.py rules)."""
    places = {}
    for i, p in enumerate(pools):
        n = max(1, int(round(p.n_locations)))
        f = N[i] / base[i]
        pop = N[i] + (T[i] if T is not None else p.tribesmen)
        jobs = p.jobs0 * f ** rules.emp_elasticity
        workers = p.workers0 * f
        _, _, op = mig.free_land_scales(pop / n, p.pop_capacity / n)
        attraction = p.attraction_fixed + mig.dynamic_attraction(
            starving=starving[i], pop_k=pop / n, capacity_k=p.pop_capacity / n, food_years=food_years[i],
            surplus_jobs=mig.surplus_jobs_scale(max(0.0, jobs - workers) / n, 0.0),
            unemployed_peasants_k=max(0.0, workers - jobs) / n)
        rel = p.religion or None
        shares = {t: s for t, s in p.type_shares.items() if s > 0}
        places[str(i)] = mig.Place(
            key=str(i), owner=p.owner, market=p.catchment, attraction=attraction,
            speed=mig.speed(starving=starving[i], overpopulation=op, modifier=rules.migration_speed_modifier),
            allowed=mig.allowed_types(starving=starving[i]),
            pops={t: [(N[i] * s / n, rel)] * n for t, s in shares.items()},
            # room: the pool's start size of each type stands in for its population_ratio caps
            caps={t: base[i] * s * rules.migration_room for t, s in shares.items()},
            religion=rel, owned=pop / n >= mig.MIN_SOURCE_POP, weight=n)
    flows = mig.monthly_flows(places.values(), lambda a, b: _km(pools[int(a.key)], pools[int(b.key)]),
                              decay=rules.migration_decay_km, min_source_pop=0.0)
    out = [0.0] * len(pools)
    inn = [0.0] * len(pools)
    for fl in flows:
        out[int(fl.source)] += fl.amount
        inn[int(fl.target)] += fl.amount
    return out, inn


def stored_months(food: float, consumption: float) -> float:
    """Months of stored food; zero or negative consumption gives the storage signal nothing (engine: no
    positive_province_food_growth scale, verified 2026-09-25)."""
    return food / consumption if consumption > 1e-9 else 0.0


def fed_share(p: Pool, n: float, t: float, share0: float, rules: SimRules) -> float:
    """Share of the settled consumption the tribe feeds (tribesmen pop_percentage_impact local_pop_food_consumption,
    capped at -100 % per location): the start's demand-weighted tribal share, moved with the pool's tribal share."""
    if rules.tribal_feeding <= 0 or p.tribal_fed_share <= 0 or share0 <= 0:
        return 0.0
    share = t / (n + t) if n + t > 0 else 0.0
    return min(1.0, rules.tribal_feeding * p.tribal_fed_share * share / share0)


UNOWNED = "---"


def free_land_factor(p: Pool, pop: float, rules: SimRules) -> float:
    """Tribesmen birth multiplier: -100 % (topography) + ``tribal_land_births`` x the engine-scaled free-land modifiers. Unowned
    land without the brake (the old country modifier) keeps its +100 %."""
    free = max(0.0, min(1.0, 1.0 - rules.tribal_land_slope * pop / p.pop_capacity)) if p.pop_capacity > 0 else 0.0
    if p.owner == UNOWNED:
        # unowned land: the topography brake holds, but no free-land modifier reaches it (game 2026-09-26: no births);
        # without the brake (the old country modifier) births ran at 1 + the free share
        return 0.0 if rules.unowned_brake else 1.0 + rules.tribal_land_births * free
    return rules.tribal_land_births * free


def simulate(pools: list[Pool], rules: SimRules) -> list[dict[str, Any]]:
    """Run all pools month by month (markets couple them through the victuals)."""
    n = len(pools)
    base = [max(1e-9, p.pop0 - p.tribesmen) for p in pools]
    N = list(base)
    T = [max(0.0, p.tribesmen) for p in pools]
    share0 = [T[i] / p.pop0 if p.pop0 > 0 else 0.0 for i, p in enumerate(pools)]
    born = [0.0] * n
    lost = [0.0] * n
    food = [0.0 if p.owner == UNOWNED else min(p.start_food, p.capacity) for p in pools]   # unowned land has no store
    prosperity = [0.0] * n
    s_tav = [rules.start_staffed if p.taverns else 0.0 for p in pools]
    s_yard = [rules.start_staffed if p.yards else 0.0 for p in pools]
    s_harbor = [rules.start_staffed if p.harbor_yards else 0.0 for p in pools]
    nobles = [1.0] * n
    starving = [False] * n
    months_pinned = [0] * n
    months_starving = [0] * n
    min_months = [math.inf] * n
    tavern_food = [0.0] * n
    yard_food = [0.0] * n
    migrated_out = [0.0] * n
    migrated_in = [0.0] * n
    years_end = [0.0] * n
    by_market: dict[str, list[int]] = defaultdict(list)
    for i, p in enumerate(pools):
        by_market[p.catchment].append(i)
    fill_log: dict[str, list[float]] = defaultdict(list)
    cons = [p.demand0 + overpopulation(p, 1.0) for p in pools]
    rng = random.Random(rules.seed)
    harvest = [0.0] * n
    harvest_cfg = load_harvest_config() if rules.harvest_regional else None
    regions: dict[str, list[str]] = defaultdict(list)
    for p in pools:
        if p.region and p.region not in regions[p.subcontinent]:
            regions[p.subcontinent].append(p.region)
    last_harvest: dict[str, str] = {}
    for t in range(int(rules.months)):
        if rules.harvest and t % 12 == SEPTEMBER:
            if harvest_cfg:
                # the mod's harvest system: one severity per region (sub-continent shock + the region's last harvest)
                last_harvest = roll_regional_harvests(rng, harvest_cfg, regions, last_harvest)
                for i, p in enumerate(pools):
                    harvest[i] = HARVEST_SEVERITY[last_harvest.get(p.region, "normal")]
            else:
                for i in range(n):
                    x, acc = rng.random(), 0.0
                    for value, weight in HARVEST_CONS:
                        acc += weight
                        if x < acc:
                            harvest[i] = value
                            break
        cons = [0.0] * n
        forage = [0.0] * n
        years = [0.0] * n
        serving = t >= rules.serve_month
        month = t % 12                                    # 0 = April
        drift = 1.0 + rules.consumption_drift * t / 12.0
        for i, p in enumerate(pools):
            if p.owner == UNOWNED:
                continue                                  # no owner, no province food: consumption plays no part
            f = N[i] / base[i]
            land_cons, forage[i] = free_land(p, f, rules)
            winter = (month >= 12 - rules.winter_months - 1 and month < 11) if p.lat >= 0 else (2 <= month < 2 + rules.winter_months)
            scale = (1.0 + rules.prosperity_consumption * prosperity[i]) * drift
            if winter:
                scale += rules.winter_scale * p.winter_cons
            settled = (p.demand0 * f * (1.0 - rules.free_land * max(0.0, 1.0 - f)) * (1.0 + harvest[i] * p.peasant_share)
                       + (overpopulation(p, f) + land_cons) * (1.0 + harvest[i])) * scale
            cons[i] = settled * (1.0 - fed_share(p, N[i], T[i], share0[i], rules)) + p.tribesmen_food * T[i]
            years[i] = min(2.0, stored_months(food[i], cons[i]) / 12.0)
        # victuals per market: staffed Victualling Yards and other producers; Taverns and pops buy
        fill = [1.0] * n
        for market, members in by_market.items():
            supply = demand = buy = 0.0
            for i in members:
                p = pools[i]
                f = N[i] / base[i]
                supply += (p.yards * s_yard[i] * rules.yard_packed() + p.harbor_yards * s_harbor[i] * rules.harbor_yard_victuals
                           + p.victuals_other_supply)
                demand += p.victuals_demand * f
                buy += p.taverns * s_tav[i] * rules.tavern_victuals
            total = demand + buy
            share = min(1.0, supply / total) if total > 1e-9 else 1.0
            fill_log[market].append(share)
            for i in members:
                fill[i] = share
        for i, p in enumerate(pools):
            if p.owner == UNOWNED:
                # unowned land (engine, 2026-09-26): no owner, so no rank gate, no province food store, no storage
                # bonus and no starving; only the tribesmen's share-weighted growth and the class rows reach it
                pop = N[i] + T[i]
                g = rules.tribal_growth * (T[i] / pop if pop > 0 else 0.0) + p.growth_offset
                N[i] *= 1.0 + g / 12.0
                dt = T[i] * (g * free_land_factor(p, pop, rules) if g > 0 else g) / 12.0
                born[i] += max(0.0, dt)
                lost[i] -= min(0.0, dt)
                T[i] += dt
                continue
            f = N[i] / base[i]
            jobs = p.jobs0 * f ** rules.emp_elasticity
            workers = p.workers0 * f
            jobless = max(0.0, workers - min(jobs, workers))
            months = stored_months(food[i], cons[i])
            prov = t >= rules.provision_month and months < rules.provision_below_months
            L = p.taverns * s_tav[i]
            E = p.yards * s_yard[i]
            H = p.harbor_yards * s_harbor[i]
            inflow = rules.tavern_food * L * fill[i]
            outflow = rules.yard_food * E + rules.harbor_yard_food * H
            prod = (p.yield_ * jobless + p.flat_food + (p.provision_food if prov else 0.0)
                    + (p.serve_food if serving else 0.0) + forage[i] + inflow - outflow)
            if rules.tribal_flat_food and N[i] + T[i] > 0:
                prod += rules.tribal_flat_food * p.n_locations * T[i] / (N[i] + T[i])   # production, not negative consumption
            tavern_food[i] += inflow
            yard_food[i] += outflow
            food[i] = min(p.capacity, max(0.0, food[i] + prod - cons[i]))
            starving[i] = food[i] <= 0.0
            months_after = stored_months(food[i], cons[i])
            if cons[i] > 1e-9:
                min_months[i] = min(min_months[i], months_after)
            if starving[i]:
                months_starving[i] += 1
                nobles[i] *= 1.0 - rules.noble_hazard / 12.0
            if food[i] >= (min(p.capacity, rules.pin_months * cons[i]) if cons[i] > 1e-9 else p.capacity) * 0.999:
                months_pinned[i] += 1
            if p.taverns:
                pi = rules.tavern_profit(years[i], starving[i], L, T[i] / (N[i] + T[i]) if N[i] + T[i] > 0 else 0.0)
                s_tav[i] = min(nobles[i], max(0.0, s_tav[i] + (rules.ramp if pi > 0 else -rules.ramp)))
            if p.yards:
                pe = rules.yard_profit(years[i], E)
                s_yard[i] = min(1.0, max(0.0, s_yard[i] + (rules.ramp if pe > 0 else -rules.ramp)))
            if p.harbor_yards:
                ph = rules.harbor_yard_profit(years[i], H)
                s_harbor[i] = min(1.0, max(0.0, s_harbor[i] + (rules.ramp if ph > 0 else -rules.ramp)))
            if starving[i]:
                g = rules.growth_base + rules.starving_growth + (0.0 if rules.migration else rules.starving_migration)
            else:
                g = rules.growth_base + rules.growth_per_year * min(2.0, months_after / 12.0)
            pop = N[i] + T[i]
            g += rules.tribal_growth * (T[i] / pop if pop > 0 else 0.0)
            g += p.growth_offset
            N[i] *= 1.0 + g / 12.0
            # tribesmen: no starving out-migration; births x the free-land factor, losses unscaled
            gt = g - (rules.starving_migration if starving[i] and not rules.migration else 0.0)
            dt = T[i] * (gt * free_land_factor(p, pop, rules) if gt > 0 else gt) / 12.0
            born[i] += max(0.0, dt)
            lost[i] -= min(0.0, dt)
            T[i] += dt
            years_end[i] = min(2.0, months_after / 12.0)
            prosperity[i] += (rules.prosperity_per_year * years_end[i] + (rules.prosperity_starving if starving[i] else 0.0)
                              - rules.prosperity_decay * prosperity[i]) / 12.0
        if rules.migration:
            out, inn = migration_month(pools, N, base, starving, years_end, rules, T)
            for i in range(n):
                moved = min(out[i], N[i])
                N[i] += inn[i] - moved
                migrated_out[i] += moved
                migrated_in[i] += inn[i]
    out = []
    for i, p in enumerate(pools):
        end = N[i] + T[i]
        cons0 = p.demand0 + overpopulation(p, 1.0)
        out.append({
            "owner": p.owner,
            "province": p.province,
            "catchment": p.catchment,
            "pop_start_k": round(p.pop0, 3),
            "pop_end_k": round(end, 3),
            "change": round(end / p.pop0 - 1.0, 4) if p.pop0 > 0 else 0.0,
            "tribal": p.pop0 > 0 and p.tribesmen >= rules.tribal_share * p.pop0,
            "tribesmen_start_k": round(p.tribesmen, 3),
            "tribesmen_end_k": round(T[i], 3),
            "tribesmen_born_k": round(born[i], 3),
            "tribesmen_lost_k": round(lost[i], 3),
            "consumption_start": round(cons0, 2),
            "R": round((p.yield_ * max(0.0, p.workers0 - p.jobs0) + p.flat_food + p.provision_food + p.serve_food) / cons0, 3)
            if cons0 > 1e-9 else None,
            "taverns": p.taverns,
            "yards": p.yards,
            "harbor_yards": p.harbor_yards,
            "cookshop_levels": p.cookshop_levels,
            "start_months": round(p.start_food / cons0, 2) if cons0 > 1e-9 else None,
            "capacity_months": round(p.capacity / cons0, 2) if cons0 > 1e-9 else None,
            "min_months": round(min_months[i], 2) if min_months[i] < math.inf else None,
            "end_months": round(food[i] / cons[i], 2) if cons[i] > 1e-9 else None,
            "prosperity_end": round(prosperity[i], 3),
            "food_end": round(food[i], 2),
            "consumption_end": round(cons[i], 3),
            "months_starving": months_starving[i],
            "months_pinned": months_pinned[i],
            "tavern_staffed_end": round(s_tav[i], 3),
            "yard_staffed_end": round(s_yard[i], 3),
            "harbor_yard_staffed_end": round(s_harbor[i], 3),
            "tavern_food": round(tavern_food[i], 1),
            "yard_food": round(yard_food[i], 1),
            "migrated_out_k": round(migrated_out[i], 3),
            "migrated_in_k": round(migrated_in[i], 3),
            "collapsing": p.pop0 > 0 and end / p.pop0 - 1.0 <= -rules.collapse_share,
            "pinned": months_pinned[i] > rules.pinned_limit_months,
        })
    for row, market in zip(out, (p.catchment for p in pools)):
        log = fill_log.get(market) or [1.0]
        row["market_victuals_fill"] = round(sum(log) / len(log), 3)
    return out


def summarize(rows: list[dict[str, Any]], rules: SimRules) -> dict[str, Any]:
    food = [r for r in rows if not r["tribal"] and r["consumption_start"] >= 0.3 * r["pop_start_k"] and r["pop_start_k"] > 0]
    start = sum(r["pop_start_k"] for r in rows)
    end = sum(r["pop_end_k"] for r in rows)
    fstart = sum(r["pop_start_k"] for r in food)
    fend = sum(r["pop_end_k"] for r in food)
    return {
        "months": rules.months,
        "pools": len(rows),
        "food_pools": len(food),
        "collapsing_pools": sum(1 for r in rows if r["collapsing"]),
        "collapsing_food_pools": sum(1 for r in food if r["collapsing"]),
        "pinned_pools": sum(1 for r in rows if r["pinned"]),
        "starving_pools": sum(1 for r in rows if r["months_starving"] > 0),
        "world_pop_start_k": round(start),
        "world_pop_end_k": round(end),
        "world_pop_change": round(end / start - 1.0, 4) if start else None,
        "food_pools_pop_change": round(fend / fstart - 1.0, 4) if fstart else None,
        "pools_R_below_1": sum(1 for r in rows if r["R"] is not None and r["R"] < 1.0),
        "tribesmen_start_k": round(tstart := sum(r["tribesmen_start_k"] for r in rows)),
        "tribesmen_change": round(sum(r["tribesmen_end_k"] for r in rows) / tstart - 1.0, 4) if tstart else None,
        "tribal_pools": sum(1 for r in rows if r["tribal"]),
        "tribal_pools_starving": sum(1 for r in rows if r["tribal"] and r["months_starving"] > 0),
        "tribal_pools_collapsing": sum(1 for r in rows if r["tribal"] and r["collapsing"]),
        "unowned_pools": sum(1 for r in rows if r["owner"] == UNOWNED),
        "unowned_tribesmen_start_k": round(ut := sum(r["tribesmen_start_k"] for r in rows if r["owner"] == UNOWNED)),
        "unowned_tribesmen_change": round(sum(r["tribesmen_end_k"] for r in rows if r["owner"] == UNOWNED) / ut - 1.0, 4) if ut else None,
        "owned_tribesmen_change": round(sum(r["tribesmen_end_k"] for r in rows if r["owner"] != UNOWNED)
                                        / max(1e-9, sum(r["tribesmen_start_k"] for r in rows if r["owner"] != UNOWNED)) - 1.0, 4),
        "migration": bool(rules.migration),
        "migrated_k": round(sum(r.get("migrated_out_k", 0.0) for r in rows), 1),
        "note": "population loop from the planned start (seeded harvest rolls); report only",
    }


# ---------------------------------------------------------------------------------------------------- I/O
INPUT_FIELDS = [f.name for f in fields(Pool)]


def write_inputs(path: Path, pools: list[Pool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INPUT_FIELDS)
        writer.writeheader()
        for p in pools:
            row = asdict(p)
            row["overpop"] = json.dumps([[round(x, 4) for x in r] for r in p.overpop])
            row["type_shares"] = json.dumps({k: round(v, 5) for k, v in sorted(p.type_shares.items())})
            writer.writerow(row)


def read_inputs(path: Path) -> list[Pool]:
    pools = []
    types = {f.name: f.type for f in fields(Pool)}
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            kwargs: dict[str, Any] = {}
            for name, value in row.items():
                if name not in types:
                    continue
                if name == "overpop":
                    kwargs[name] = [tuple(x) for x in json.loads(value or "[]")]
                elif name == "type_shares":
                    kwargs[name] = json.loads(value or "{}")
                elif types[name] in ("str", str):  # annotations are strings (from __future__)
                    kwargs[name] = value
                else:
                    kwargs[name] = float(value or 0.0)
            pools.append(Pool(**kwargs))
    return pools


def write_outputs(folder: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r["change"])
    with (folder / "pools.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["owner"])
        writer.writeheader()
        writer.writerows(rows)
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def run_file(repo: Path, raw: Mapping[str, Any] | None = None, months: int | None = None) -> dict[str, Any]:
    """``ppc worldbuilder food-sim``: rerun the validator on the last build's input.csv."""
    folder = repo / OUTPUT_RELATIVE_PATH
    path = folder / "input.csv"
    if not path.is_file():
        raise FileNotFoundError(f"run ppc worldbuilder apply first: {path}")
    rules = SimRules.from_raw(raw)
    if months:
        rules = SimRules(**{**asdict(rules), "months": int(months)})
    rows = simulate(read_inputs(path), rules)
    summary = summarize(rows, rules)
    write_outputs(folder, rows, summary)
    return summary


# ---------------------------------------------------------------------------------------------------- from the planner
def pools_from_simulation(sim, budgets: Mapping[tuple, Mapping[str, Any]]) -> list[Pool]:
    """One validator pool per province/owner group of the start simulation (start_simulation.Simulation)."""
    model = sim.food_model
    share = float(model.cookshop_serve_share)
    v = sim.start.victuals
    serve_keys = sim.serve_keys()
    converted = defaultdict(lambda: defaultdict(float))
    for c in sim.conversions:
        converted[c.location][c.to_type] += c.size_k
    out = []
    from .start_simulation import summed

    def rgo_attraction(tag):
        good = str(sim.locations[tag].get("raw_material") or "")
        body = sim.rules.statics.get(f"pp_rgo_bonus_{good}") if good else None
        return summed(body).get("local_migration_attraction", 0.0) if body is not None else 0.0

    for group, tags in sim.groups.items():
        b = budgets[group]
        tribesmen = flat = provision = serve = cookshop = victuals = other_supply = peasant_food = 0.0
        taverns = yards = harbor_yards = 0.0
        pairs = []
        by_type = defaultdict(float)
        religions = defaultdict(float)
        capacity = lat = lon = weight = fixed = fed_num = fed_den = winter_num = 0.0
        capital = sim.province_capital(group)
        for tag in tags:
            types = sim.location_pops(tag, converted[tag])
            for kind, k in types.items():
                if kind != "tribesmen" and k > 0:
                    by_type[kind] += k
            for pop in sim.pops.get(tag, []):
                religions[pop.religion] += pop.size_k
            ctx = sim.base[tag]
            a = sim.attrs.get(tag, {})
            w = max(1e-6, float(ctx.get("population") or 0.0))
            lat += w * float(a.get("calibrated_lat") or 0.0)
            lon += w * float(a.get("calibrated_lon") or 0.0)
            weight += w
            capacity += max(0.0, sim.capacity_k(tag))
            buildings = sum(n * sim.rules.modifiers(key).get("local_migration_attraction", 0.0)
                            for key, n in sim.staffed[tag].items() if n)
            fixed += 0.0025 * float(ctx.get("development") or 0.0) + mig.fixed_attraction(
                province_capital=tag == capital, market_center=bool(ctx.get("is_market_center")),
                static_modifiers=ctx["modifiers"].get("local_migration_attraction", 0.0) + rgo_attraction(tag),
                buildings=buildings)
            tribesmen += max(0.0, types.get("tribesmen", 0.0))
            peasant_food += max(0.0, types.get("peasants", 0.0)) * float(sim.food.get("peasants", 0.0))
            here = sum(max(0.0, x) for x in types.values())
            settled = sum(n * float(sim.food.get(kind, 0.0)) for kind, n in types.items() if kind != "tribesmen" and n > 0)
            fed_num += settled * (max(0.0, types.get("tribesmen", 0.0)) / here if here > 0 else 0.0)
            fed_den += settled
            winter_num += settled * winter_consumption(a.get("climate"))
            cap = sim.capacity_k(tag)
            peasants = sum(types.get(t, 0.0) for t in model.overpopulation_pop_types)
            if cap > 0 and peasants > 0:
                pairs.append((peasants, here / cap, cap))
            victuals += float(v["pop_demand_scale"]) * sum(n * sim.victuals_pop_factors.get(k, 0.0) for k, n in types.items())
            mult = sim.food_mult.get(tag, 1.0)
            for key, n in sim.staffed[tag].items():
                if not n:
                    continue
                if key == "tavern":
                    taverns += n
                    continue
                if key == "victualling_yard":
                    harbor_yards += n
                    continue
                if key == "grange":
                    yards += n
                    continue
                flat += n * mult * sim.numbers.get(key, {}).get("local_monthly_food", 0)
                if key in serve_keys:
                    cookshop += n
                    serve += n * (share * float(sim.province_food.get(key, 0.0)) + float(model.cookshop_drink_food))
                else:
                    provision += n * float(sim.province_food.get(key, 0.0))
                    other_supply += n * float(v["producers"].get(key, 0.0))
                    victuals += n * float(v["consumers"].get(key, 0.0))
        tribesmen_food = float(sim.food.get("tribesmen", 0.0))
        demand0 = b["demand_base"] - tribesmen_food * tribesmen   # the start demand counts the tribesmen at their rate
        jobless = b["subsistence_workers_k"]
        yield_ = b["subsistence"] / jobless if jobless > 1e-9 else sum(sim.location_yield(t) for t in tags) / len(tags)
        out.append(Pool(
            owner=str(group[0]), province=str(group[1]), catchment=str(sim.catchments[group]),
            pop0=b["pop_k"], tribesmen=tribesmen, demand0=demand0, workers0=b["workers_k"], jobs0=b["jobs_k"],
            yield_=yield_, flat_food=flat, provision_food=provision, serve_food=serve, cookshop_levels=cookshop,
            taverns=taverns, yards=yards, capacity=b["food_capacity"],
            start_food=model.start_food_share * b["food_capacity"], victuals_demand=victuals,
            victuals_other_supply=other_supply, harbor_yards=harbor_yards, overpop=pairs,
            overpop_consumption=model.overpopulation_consumption,
            peasant_share=peasant_food / demand0 if demand0 > 1e-9 else 0.0,
            tribesmen_food=tribesmen_food, tribal_fed_share=fed_num / fed_den if fed_den > 1e-9 else 0.0,
            winter_cons=winter_num / fed_den if fed_den > 1e-9 else 0.0,
            region=str(sim.base[tags[0]].get("region") or ""),
            subcontinent=str(sim.base[tags[0]].get("sub_continent") or ""),
            n_locations=float(len(tags)), lat=lat / weight if weight else 0.0, lon=lon / weight if weight else 0.0,
            pop_capacity=capacity, attraction_fixed=fixed / len(tags) if tags else 0.1,
            type_shares={k: v / sum(by_type.values()) for k, v in by_type.items()} if by_type else {},
            religion=max(religions, key=religions.get) if religions else "",
        ))
    out.extend(unowned_pools(sim))
    return out


def unowned_pools(sim) -> list[Pool]:
    """One pool per province of unowned land (tribal land mostly): its pops from the setup, population capacity from the
    World Builder attribute rows, no buildings, jobs or markets."""
    from .start_food_model_v2 import food_capacity

    rows = getattr(sim, "unowned_locations", {}) or {}
    by_province: dict[str, list[str]] = defaultdict(list)
    for tag, loc in rows.items():
        if sim.pops.get(tag):
            by_province[str(loc.get("province") or tag)].append(tag)
    tribesmen_food = float(sim.food.get("tribesmen", 0.0))
    out = []
    for province, tags in sorted(by_province.items()):
        tribesmen = settled = workers = peasant_food = capacity_k = 0.0
        cap_rows = []
        for tag in tags:
            for pop in sim.pops.get(tag, []):
                if pop.type == "tribesmen":
                    tribesmen += pop.size_k
                else:
                    settled += pop.size_k * float(sim.food.get(pop.type, 0.0))
                    if pop.type in ("peasants", "slaves"):
                        workers += pop.size_k
                    if pop.type == "peasants":
                        peasant_food += pop.size_k * float(sim.food.get("peasants", 0.0))
            target = sim.targets.get(tag, {})
            capacity_k += float(target.get("attribute_flat_people") or 0.0) / 1000.0
            cap_rows.append((float(target.get("development") or 0.0), sum(p.size_k for p in sim.pops.get(tag, [])), "rural_settlement"))
        pop0 = sum(p.size_k for t in tags for p in sim.pops.get(t, []))
        if pop0 <= 0:
            continue
        food_cap = food_capacity(cap_rows, sim.food_model)
        out.append(Pool(
            owner=UNOWNED, province=province, catchment=UNOWNED, pop0=pop0, tribesmen=tribesmen, demand0=settled,
            workers0=workers, jobs0=0.0, yield_=float(sim.rules.subsistence), flat_food=0.0, provision_food=0.0,
            serve_food=0.0, cookshop_levels=0.0, taverns=0.0, yards=0.0, capacity=food_cap,
            start_food=sim.food_model.start_food_share * food_cap, victuals_demand=0.0,
            peasant_share=peasant_food / settled if settled > 1e-9 else 0.0, tribesmen_food=tribesmen_food,
            n_locations=float(len(tags)), pop_capacity=capacity_k,
        ))
    return out


def write_inputs_and_run(repo: Path, sim, budgets, cfg) -> dict[str, Any]:
    folder = repo / OUTPUT_RELATIVE_PATH
    pools = pools_from_simulation(sim, budgets)
    write_inputs(folder / "input.csv", pools)
    rules = SimRules.from_raw((cfg.raw.get("start") or {}).get("food_sim"))
    rows = simulate(pools, rules)
    summary = summarize(rows, rules)
    write_outputs(folder, rows, summary)
    return summary
