"""Start-food validator: the calibrated population loop for every province pool (``ppc worldbuilder food-sim``).

The start placement writes one input row per province/owner pool (``input.csv``: pops, jobs, the location yields,
building food, market levels, food capacity); this module runs 96 months (1337-1345, the pre-plague window) of the
population loop of ``tools/province_food_sim.py --depop`` on all of them at once and reports the pools that lose a
quarter of their people, the pools pinned at the storage cap (over-supplied) and the world population change.

Per pool and month (rules calibrated on the pre-plague saves 1337.4 / 1341.3 / 1345.3):

* jobs = jobs0 x (N / N0) ^ 0.5; jobless = peasants and slaves - jobs; subsistence = jobless x yield;
* consumption = demand0 x N / N0 x (1 - 0.4 x (1 - N / N0)) + overpopulation (+0.5 peasant food per unit of
  pop / capacity - 1, location by location), less the share the tribe feeds (``tribal_feeding`` x the demand-weighted
  tribal share of the pool's locations, scaled with the pool's tribal share), plus the tribesmen's own food
  (``tribesmen_food`` per 1,000, the pop type's ``pop_food_consumption``; negative = they feed the province). A
  province whose total consumption is zero or below gets no storage growth bonus (engine, verified 2026-09-25);
* tribesmen (engine, verified 2026-09-25): the location growth below also carries ``tribal_growth`` x tribal share for
  every pop; when it is positive tribesmen are born at it x the free-land factor max(0, 1 - ``tribal_land_slope`` x
  pop / capacity) (``global_tribesmen_pop_growth = -1`` + ``local_tribesmen_pop_growth = 1`` in the scaled free-land
  modifiers; slope fitted on the 1345 save), when it is negative they lose it unscaled like every pop type;
* farms, villages and orchards run Provisioning from month 6 while the store is below ~11 months (their Sell leg
  pays above that); cookeries serve on ``cookery_serve_share`` of their levels from month 1 (the rest and their
  container and drink slots make victuals);
* Victualler imports and exports ramp their staffing 0.05 a month toward the sign of their profit per level at the
  market victuals price (2.7): the import pays below 12 stored months, the export above 18; each staffed level moves
  90 food; imports only get the victuals their market has (cookeries on Preserve, staffed exports, pops compete);
  a starving pool loses the noble who staffs its import at 0.09 a year;
* growth per year: -0.0048 + 0.0086 x stored years (cap 2) when fed, -0.0048 - 0.04 - 0.012 when starving;
* each September a pool rolls its harvest (``pp_harvest_*``: peasant food consumption +0.30 .. -0.30, 40 % neutral)
  from a seeded generator, so the run is reproducible; ``harvest = false`` turns the rolls off.
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
    free_land: float = 0.4
    noble_hazard: float = 0.09
    ramp: float = 0.05
    food_per_market_level: float = 90.0
    provision_month: int = 6
    provision_below_months: float = 11.4
    serve_month: int = 1
    pin_months: float = 24.0
    pinned_limit_months: int = 48
    collapse_share: float = 0.25
    tribal_share: float = 0.5
    # tribesmen (pp_pop_adjustments.txt, pp_capacity_pressure_effects.txt, pp_country_base_values.txt)
    tribal_growth: float = 0.012        # pop_percentage_impact local_population_growth (every pop in the location)
    tribal_land_slope: float = 0.75     # free-land factor 1 - slope x pop / capacity (1345 save: 0.75 at start capacity)
    tribal_feeding: float = 0.0         # -pop_percentage_impact local_pop_food_consumption (0 = the tribe feeds nobody)
    start_staffed: float = 1.0          # the setup staffs every market level on day 0 (nb.eu5)
    harvest: bool = True
    seed: int = 1
    # market migration between pools (migration.py); off = the flat starving_migration sink above
    migration: bool = False
    migration_decay_km: float = 900.0
    migration_speed_modifier: float = 0.0   # country speed modifiers (1345: mostly -0.1 .. -0.4)
    migration_room: float = 1.0             # capped types (not peasants) find room while the target pool is below
                                            # this x its start size of the type (stand-in for population_ratio)
    # Victualler import (per level; blueprints/accepted/buildings/victuals_market_import.yml)
    import_income: float = 5.0          # 0.25 offset x (1 + 19)
    import_victuals: float = 3.0
    import_labour: float = 0.3
    import_amount: float = 0.8          # province_food_purchase
    import_const: float = 15.0
    import_per_year: float = -8.0
    import_starving: float = 8.0
    import_cost: float = 3.0
    import_droop: float = -0.3
    # Victualler (Export)
    export_victuals: float = 3.0
    export_amount: float = 1.425        # export_sales
    export_const: float = -9.0
    export_per_year: float = 8.0
    export_droop: float = -0.3
    export_cost: float = 13.5
    export_labour: float = 0.3

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | None) -> "SimRules":
        raw = dict(raw or {})
        kwargs = {}
        for f in fields(cls):
            if f.name in raw:
                kwargs[f.name] = type(getattr(cls, f.name))(raw[f.name])
        return cls(**kwargs)

    def import_profit(self, years: float, starving: bool, staffed: float) -> float:
        m = 1.0 + self.import_const + self.import_per_year * years + self.import_droop * staffed
        if starving:
            m += self.import_starving
        return (self.import_income - self.import_victuals * self.victuals_price - self.import_labour
                + self.import_amount * max(0.0, m) - self.import_cost)

    def export_profit(self, years: float, staffed: float) -> float:
        m = 1.0 + self.export_const + self.export_per_year * years + self.export_droop * staffed
        return (self.export_victuals * self.victuals_price + self.export_amount * max(0.0, m)
                - self.export_cost - self.export_labour)


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
    serve_food: float           # cookeries' Serve output on the levels that run Serve
    cookery_levels: float
    imports: float              # staffed import levels
    exports: float              # staffed export levels
    capacity: float             # food capacity (max stored food)
    start_food: float
    victuals_demand: float      # the pops' and other buildings' victuals demand at start
    victuals_other_supply: float = 0.0
    overpop: list = field(default_factory=list)   # [(peasants k, pop / capacity)] per location
    overpop_consumption: float = 0.5
    cookery_victuals: float = 1.0      # victuals per cookery level (start_food_model_v2.cookery_victuals)
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


def overpopulation(pool: Pool, f: float) -> float:
    return pool.overpop_consumption * sum(p * f * max(0.0, f * r - 1.0) for p, r in pool.overpop)


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


def free_land_factor(p: Pool, pop: float, rules: SimRules) -> float:
    """Tribesmen birth multiplier: -100 % (country) + 100 % x the engine-scaled free-land modifiers."""
    if p.pop_capacity <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - rules.tribal_land_slope * pop / p.pop_capacity))


def simulate(pools: list[Pool], rules: SimRules) -> list[dict[str, Any]]:
    """Run all pools month by month (markets couple them through the victuals)."""
    n = len(pools)
    base = [max(1e-9, p.pop0 - p.tribesmen) for p in pools]
    N = list(base)
    T = [max(0.0, p.tribesmen) for p in pools]
    share0 = [T[i] / p.pop0 if p.pop0 > 0 else 0.0 for i, p in enumerate(pools)]
    born = [0.0] * n
    lost = [0.0] * n
    food = [min(p.start_food, p.capacity) for p in pools]
    s_imp = [rules.start_staffed if p.imports else 0.0 for p in pools]
    s_exp = [rules.start_staffed if p.exports else 0.0 for p in pools]
    nobles = [1.0] * n
    starving = [False] * n
    months_pinned = [0] * n
    months_starving = [0] * n
    min_months = [math.inf] * n
    imported = [0.0] * n
    exported = [0.0] * n
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
    for t in range(int(rules.months)):
        if rules.harvest and t % 12 == SEPTEMBER:
            for i in range(n):
                x, acc = rng.random(), 0.0
                for value, weight in HARVEST_CONS:
                    acc += weight
                    if x < acc:
                        harvest[i] = value
                        break
        cons = [0.0] * n
        years = [0.0] * n
        serving = t >= rules.serve_month
        for i, p in enumerate(pools):
            f = N[i] / base[i]
            settled = (p.demand0 * f * (1.0 - rules.free_land * max(0.0, 1.0 - f)) * (1.0 + harvest[i] * p.peasant_share)
                       + overpopulation(p, f) * (1.0 + harvest[i]))
            cons[i] = settled * (1.0 - fed_share(p, N[i], T[i], share0[i], rules)) + p.tribesmen_food * T[i]
            years[i] = min(2.0, stored_months(food[i], cons[i]) / 12.0)
        # victuals per market: cookeries on Preserve, staffed exports, other producers; imports and pops buy
        fill = [1.0] * n
        for market, members in by_market.items():
            supply = demand = buy = 0.0
            for i in members:
                p = pools[i]
                f = N[i] / base[i]
                supply += p.cookery_levels * p.cookery_victuals
                supply += p.exports * s_exp[i] * rules.export_victuals + p.victuals_other_supply
                demand += p.victuals_demand * f
                buy += p.imports * s_imp[i] * rules.import_victuals
            total = demand + buy
            share = min(1.0, supply / total) if total > 1e-9 else 1.0
            fill_log[market].append(share)
            for i in members:
                fill[i] = share
        for i, p in enumerate(pools):
            f = N[i] / base[i]
            jobs = p.jobs0 * f ** rules.emp_elasticity
            workers = p.workers0 * f
            jobless = max(0.0, workers - min(jobs, workers))
            months = stored_months(food[i], cons[i])
            prov = t >= rules.provision_month and months < rules.provision_below_months
            L = p.imports * s_imp[i]
            E = p.exports * s_exp[i]
            inflow = rules.food_per_market_level * L * fill[i]
            outflow = rules.food_per_market_level * E
            prod = (p.yield_ * jobless + p.flat_food + (p.provision_food if prov else 0.0)
                    + (p.serve_food if serving else 0.0) + inflow - outflow)
            imported[i] += inflow
            exported[i] += outflow
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
            if p.imports:
                pi = rules.import_profit(years[i], starving[i], L)
                s_imp[i] = min(nobles[i], max(0.0, s_imp[i] + (rules.ramp if pi > 0 else -rules.ramp)))
            if p.exports:
                pe = rules.export_profit(years[i], E)
                s_exp[i] = min(1.0, max(0.0, s_exp[i] + (rules.ramp if pe > 0 else -rules.ramp)))
            if starving[i]:
                g = rules.growth_base + rules.starving_growth + (0.0 if rules.migration else rules.starving_migration)
            else:
                g = rules.growth_base + rules.growth_per_year * min(2.0, months_after / 12.0)
            pop = N[i] + T[i]
            g += rules.tribal_growth * (T[i] / pop if pop > 0 else 0.0)
            N[i] *= 1.0 + g / 12.0
            # tribesmen: no starving out-migration; births x the free-land factor, losses unscaled
            gt = g - (rules.starving_migration if starving[i] and not rules.migration else 0.0)
            dt = T[i] * (gt * free_land_factor(p, pop, rules) if gt > 0 else gt) / 12.0
            born[i] += max(0.0, dt)
            lost[i] -= min(0.0, dt)
            T[i] += dt
            years_end[i] = min(2.0, months_after / 12.0)
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
            "imports": p.imports,
            "exports": p.exports,
            "cookery_levels": p.cookery_levels,
            "start_months": round(p.start_food / cons0, 2) if cons0 > 1e-9 else None,
            "capacity_months": round(p.capacity / cons0, 2) if cons0 > 1e-9 else None,
            "min_months": round(min_months[i], 2) if min_months[i] < math.inf else None,
            "end_months": round(food[i] / cons[i], 2) if cons[i] > 1e-9 else None,
            "months_starving": months_starving[i],
            "months_pinned": months_pinned[i],
            "import_staffed_end": round(s_imp[i], 3),
            "export_staffed_end": round(s_exp[i], 3),
            "imported_food": round(imported[i], 1),
            "exported_food": round(exported[i], 1),
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
            row["overpop"] = json.dumps([[round(a, 4), round(b, 4)] for a, b in p.overpop])
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
    from .start_food_model_v2 import cookery_victuals

    model = sim.food_model
    share = float(model.cookery_serve_share)
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
        tribesmen = flat = provision = serve = cookery = victuals = other_supply = peasant_food = 0.0
        imports = exports = 0.0
        pairs = []
        by_type = defaultdict(float)
        religions = defaultdict(float)
        capacity = lat = lon = weight = fixed = fed_num = fed_den = 0.0
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
            cap = sim.capacity_k(tag)
            peasants = sum(types.get(t, 0.0) for t in model.overpopulation_pop_types)
            if cap > 0 and peasants > 0:
                pairs.append((peasants, here / cap))
            victuals += float(v["pop_demand_scale"]) * sum(n * sim.victuals_pop_factors.get(k, 0.0) for k, n in types.items())
            mult = sim.food_mult.get(tag, 1.0)
            for key, n in sim.staffed[tag].items():
                if not n:
                    continue
                if key == "victuals_market_import":
                    imports += n
                    continue
                if key == "victuals_market":
                    exports += n
                    continue
                flat += n * mult * sim.numbers.get(key, {}).get("local_monthly_food", 0)
                if key in serve_keys:
                    cookery += n
                    serve += n * share * float(sim.province_food.get(key, 0.0))
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
            yield_=yield_, flat_food=flat, provision_food=provision, serve_food=serve, cookery_levels=cookery,
            imports=imports, exports=exports, capacity=b["food_capacity"],
            start_food=model.start_food_share * b["food_capacity"], victuals_demand=victuals,
            victuals_other_supply=other_supply, overpop=pairs, overpop_consumption=model.overpopulation_consumption,
            cookery_victuals=cookery_victuals(model),
            peasant_share=peasant_food / demand0 if demand0 > 1e-9 else 0.0,
            tribesmen_food=tribesmen_food, tribal_fed_share=fed_num / fed_den if fed_den > 1e-9 else 0.0,
            n_locations=float(len(tags)), lat=lat / weight if weight else 0.0, lon=lon / weight if weight else 0.0,
            pop_capacity=capacity, attraction_fixed=fixed / len(tags) if tags else 0.1,
            type_shares={k: v / sum(by_type.values()) for k, v in by_type.items()} if by_type else {},
            religion=max(religions, key=religions.get) if religions else "",
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
