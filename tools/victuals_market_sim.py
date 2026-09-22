"""Monthly simulator for the province food stockpile with victuals import/export markets.

Models what the engine does each month with the pieces the mod controls:

* storage (food) is an integrator of local balance + 60 food per staffed market level;
* each market's staffing ramps +/- RAMP per month depending only on the sign of its profit
  (UNPROFITABLE/PROFITABLE_BUILDING_WORKERS_*_PERCENTAGE);
* profit = revenue - fixed input cost; revenue = base output x price x efficiency x (1 + output modifier)
  where the output modifier = rank + gate x stored years + droop x staffed levels + starving bonus;
* stored years feed the growth modifier, capped at CAP_MONTHS (GROWTH_FROM_FOOD_MULTIPLIER_MAX = 2 years);
* optional prosperity integrator (+0.0025/month per stored year, decay 0.005) that adds +50 % consumption.

Run:  uv run python tools/victuals_market_sim.py [--png out.png]
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace

RAMP = 0.05          # staffing change per month (mod define; vanilla 0.10)
CAP_MONTHS = 24.0    # storage months cap for the growth modifier
FOOD_PER_LEVEL = 60.0


@dataclass
class Market:
    levels: int
    gate_per_year: float      # output modifier per stored year (import negative, export positive)
    droop_per_level: float    # output modifier per fully staffed level (negative)
    offset: float = 0.0       # constant output modifier (rank bonus, constant gate offset)
    revenue_base: float = 30.0  # base output x price (6 x 5)
    extra_revenue: float = 0.0  # e.g. export's 2 victuals x 3 gold
    cost: float = 2.5           # fixed input cost per level excluding victuals (labour 2.5; export adds offset 50)
    victuals_per_level: float = 0.0  # victuals consumed (+2 import) or produced (-2 export), priced monthly
    starving_bonus: float = 0.0 # +2.0 on the import when the province starves
    food_sign: float = 1.0      # +1 import, -1 export
    subsidized: bool = False    # subsidised buildings never lay off: staffing pinned at 100 %
    staffing: float = 0.0

    level_bonus: float = 0.0    # raw_modifier per level: applies per built level, NOT scaled by staffing
    profit_log: list[float] = field(default_factory=list)  # profit per staffed level, monthly
    gold_log: list[float] = field(default_factory=list)    # whole building profit, monthly
    cost_log: list[float] = field(default_factory=list)    # input cost per staffed level, monthly

    def modifier(self, years: float, starving: bool) -> float:
        m = (self.offset + self.gate_per_year * years + self.droop_per_level * self.levels * self.staffing
             + self.level_bonus * self.levels)
        if starving:
            m += self.starving_bonus
        return m

    def profit(self, years: float, starving: bool, efficiency: float, additive: bool,
               victuals_price: float = 3.0) -> float:
        m = self.modifier(years, starving)
        if additive:
            revenue = self.revenue_base * max(0.0, 1.0 + m + (efficiency - 1.0))
        else:
            revenue = self.revenue_base * efficiency * max(0.0, 1.0 + m)
        return revenue + self.extra_revenue - self.cost - self.victuals_per_level * victuals_price

    def step(self, years: float, starving: bool, efficiency: float, additive: bool,
             workers_per_level: int = 0, victuals_price: float = 3.0) -> None:
        p = self.profit(years, starving, efficiency, additive, victuals_price)
        self.profit_log.append(p)
        self.gold_log.append(p * self.levels * self.staffing)
        self.cost_log.append(self.cost + abs(self.victuals_per_level) * victuals_price)
        if self.subsidized:
            self.staffing = 1.0
        elif workers_per_level:
            # whole workers: the engine cannot hire or fire 5 % of two nobles, it moves at least one
            total = self.levels * workers_per_level
            step = max(1, round(RAMP * total))
            employed = round(self.staffing * total) + (step if p > 0 else -step)
            self.staffing = min(1.0, max(0.0, employed / total))
        else:
            self.staffing = min(1.0, max(0.0, self.staffing + (RAMP if p > 0 else -RAMP)))

    def food(self) -> float:
        return self.food_sign * FOOD_PER_LEVEL * self.levels * self.staffing


@dataclass
class Scenario:
    name: str
    consumption: float          # base pop food consumption per month
    production: float           # local food production per month (no markets)
    markets: list[Market]
    efficiency: float = 1.0
    additive_efficiency: bool = False
    prosperity: bool = False
    prosperity_gain: float = 0.0025   # local_monthly_prosperity per stored year (positive_province_food_growth)
    prosperity_decay: float = 0.005   # local_prosperity_decay in the prosperity modifier (scaled by prosperity)
    prosperity_consumption: float = 0.5  # +50 % pop food consumption at full prosperity (mod inject)
    pop_growth: bool = False          # growth gate: +0.75 %/yr per stored year, -0.5 %/yr from rank
    decay: float = 0.0                # share of the stockpile lost per month (mod global_food_decay = 0.01)
    workers_per_level: int = 0  # 0 = continuous staffing; N = whole workers per level
    price_noise: float = 0.0    # monthly random-walk step (gold) of the victuals price, mean-reverting
    victuals_mean: float = 3.0  # mean victuals price (1355 save: 2.47)
    start_months: float = 6.0
    months: int = 480
    trace: list[tuple[float, float, float]] = field(default_factory=list)  # months stored, staffing i, staffing e


def run(s: Scenario) -> Scenario:
    import random

    rng = random.Random(42)
    markets = [replace(m) for m in s.markets]
    base_consumption = s.consumption   # pops' base demand; drifts with the growth gate when enabled
    storage = s.start_months * s.consumption
    prosperity = 0.0
    price = s.victuals_mean
    for _ in range(s.months):
        if s.price_noise:
            price += rng.gauss(0.0, s.price_noise) + 0.05 * (s.victuals_mean - price)
            price = min(2.0 * s.victuals_mean, max(0.5 * s.victuals_mean, price))
        consumption = base_consumption * (1.0 + s.prosperity_consumption * prosperity)
        years = min(CAP_MONTHS, storage / base_consumption) / 12.0
        starving = storage <= 0.0
        for m in markets:
            m.step(years, starving, s.efficiency, s.additive_efficiency, s.workers_per_level, price)
        storage = max(0.0, storage + s.production - consumption + sum(m.food() for m in markets)
                      - s.decay * storage)
        if s.prosperity:
            prosperity = min(1.0, max(0.0, prosperity + s.prosperity_gain * years
                                      - s.prosperity_decay * prosperity))
        if s.pop_growth:
            growth_per_year = 0.0075 * years - 0.005          # growth gate, yearly rate
            if starving:
                growth_per_year = -0.04
            base_consumption *= 1.0 + growth_per_year / 12.0
        imp = [m.staffing for m in markets if m.food_sign > 0]
        exp = [m.staffing for m in markets if m.food_sign < 0]
        s.trace.append((storage / base_consumption, imp[0] if imp else 0.0, exp[0] if exp else 0.0,
                        prosperity, base_consumption / s.consumption))
    s.markets = markets   # keep the instances that ran (method duty cycles live on them)
    return s


def summarize(s: Scenario) -> str:
    tail = s.trace[-120:]
    months = [t[0] for t in tail]
    lo, hi = min(months), max(months)
    verdict = "settled" if hi - lo < 0.5 else ("band drift" if hi - lo < 3 else "OSCILLATES")
    staff_i = sum(t[1] for t in tail) / len(tail)
    staff_e = sum(t[2] for t in tail) / len(tail)
    step = max(12, len(s.trace) // 20)
    strip = " ".join(f"{s.trace[i][0]:4.1f}" for i in range(0, len(s.trace), step))
    extra = ""
    if s.prosperity or s.pop_growth:
        pro = [t[3] for t in tail]
        pop = [t[4] for t in tail]
        extra = (f"  prosperity {min(pro):.0%}..{max(pro):.0%}, pops {pop[0]:.2f}x..{pop[-1]:.2f}x of start\n"
                 f"  prosperity per sample: " + " ".join(f"{s.trace[i][3]:4.0%}" for i in range(0, len(s.trace), step)) + "\n")
    return (
        f"{s.name}\n"
        f"  last 10 years: stored {lo:.1f}..{hi:.1f} months, import staffing {staff_i:.0%}, "
        f"export staffing {staff_e:.0%}  -> {verdict}\n"
        f"  stored months, {len(s.trace) // 12} years in {step // 12}-year samples:\n  {strip}\n" + extra
    )


def current_import(levels: int, rank: float = 0.0) -> Market:
    # 2 victuals in (6 gold at base price) + 0.5 labour (2.5): 8.5 per level at base prices
    return Market(levels, gate_per_year=-0.5, droop_per_level=0.0, offset=rank, cost=2.5,
                  victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)


def current_export(levels: int, rank: float = 0.0) -> Market:
    # 10 offset (50) + 0.5 labour (2.5) in, 2 victuals out (6 at base price): net 46.5 per level
    return Market(levels, gate_per_year=0.5, droop_per_level=-0.012, offset=rank, cost=52.5,
                  victuals_per_level=-2.0, food_sign=-1.0)


def proposed_import(levels: int, rank: float = 0.0, gate: float = -1.2, droop: float = -0.10) -> Market:
    return Market(levels, gate_per_year=gate, droop_per_level=droop, offset=rank, cost=2.5,
                  victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)


def scenarios() -> list[Scenario]:
    # A town: consumption 300/month, local production 200 (deficit 100), 3 import levels, 2 export levels.
    town = dict(consumption=300.0, production=200.0)
    return [
        Scenario("A  current design, import + export in one province",
                 markets=[current_import(3), current_export(2)], **town),
        Scenario("B  current design, +50% production efficiency",
                 markets=[current_import(3), current_export(2)], efficiency=1.5, **town),
        Scenario("C  current design + prosperity coupling",
                 markets=[current_import(3), current_export(2)], prosperity=True, **town),
        Scenario("D  proposed import only (gate -1.2/yr, droop -0.10/level)",
                 markets=[proposed_import(3)], **town),
        Scenario("E  proposed import, +50% efficiency (multiplicative)",
                 markets=[proposed_import(3)], efficiency=1.5, **town),
        Scenario("F  proposed import, +50% efficiency (additive)",
                 markets=[proposed_import(3)], efficiency=1.5, additive_efficiency=True, **town),
        Scenario("G  proposed import + prosperity coupling",
                 markets=[proposed_import(3)], prosperity=True, **town),
        Scenario("H  proposed import, gate only, no droop",
                 markets=[proposed_import(3, droop=0.0)], **town),
        Scenario("I  proposed import + current export in one province",
                 markets=[proposed_import(3), current_export(2)], **town),
        Scenario("J  proposed import, storage starts at 20 months",
                 markets=[proposed_import(3)], start_months=20.0, **town),
        # whole workers: one noble per level, so a 3-level market staffs in thirds
        Scenario("K  current design, whole workers (1 per level)",
                 markets=[current_import(3), current_export(2)], workers_per_level=1, **town),
        Scenario("L  current design, whole workers, +50% efficiency",
                 markets=[current_import(3), current_export(2)], workers_per_level=1, efficiency=1.5, **town),
        Scenario("M  proposed import, whole workers (1 per level)",
                 markets=[proposed_import(3)], workers_per_level=1, **town),
        Scenario("N  proposed import, whole workers, 6 levels, droop -0.05",
                 markets=[proposed_import(6, droop=-0.05)], workers_per_level=1, **town),
        Scenario("O  proposed import + current export, whole workers",
                 markets=[proposed_import(3), current_export(2)], workers_per_level=1, **town),
        # victuals price noise: a 1-gold price move is worth 2 gold per level on both markets
        Scenario("P  current design, whole workers, victuals price noise 0.3/month",
                 markets=[current_import(3), current_export(2)], workers_per_level=1, price_noise=0.3, **town),
        Scenario("Q  proposed import, whole workers, victuals price noise 0.3/month",
                 markets=[proposed_import(3)], workers_per_level=1, price_noise=0.3, **town),
        Scenario("R  proposed import + current export, whole workers, price noise 0.3",
                 markets=[proposed_import(3), current_export(2)], workers_per_level=1, price_noise=0.3, **town),
        Scenario("S  proposed import, droop -0.20, whole workers, price noise 0.3",
                 markets=[proposed_import(3, droop=-0.20)], workers_per_level=1, price_noise=0.3, **town),
    ] + observed_price_scenarios(town) + refined_scenarios(town) + final_scenarios(town) + slow_loop_scenarios(town) \
        + lever_scenarios(town) + stacking_scenarios()


def stacking_scenarios() -> list[Scenario]:
    """Other local food sources, and whether stacking levels can raise the resting point."""
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True,
             prosperity=True, decay=0.01, months=600, consumption=300.0)
    out = []
    for prod in (150.0, 200.0, 250.0, 290.0, 320.0):
        out.append(Scenario(f"S-food local production {prod:.0f} (deficit {300 - prod:.0f}), 3 levels, no level bonus",
                            markets=[final_import(3)], production=prod, **q))
    for n in (3, 6, 9):
        out.append(Scenario(f"S-stack {n} levels, raw_modifier +0.2 per level, deficit 100",
                            markets=[replace(final_import(n), level_bonus=0.2)], production=200.0, **q))
    for n in (3, 6):
        out.append(Scenario(f"S-stack {n} levels, raw +0.2, deficit 100, +50% efficiency",
                            markets=[replace(final_import(n), level_bonus=0.2)], production=200.0,
                            efficiency=1.5, **q))
    return out


def lever_scenarios(town: dict) -> list[Scenario]:
    """What a player or AI can do to raise a deficit town's resting point; decay 1 %/month included."""
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True,
             prosperity=True, decay=0.01, months=600)
    base = final_import(3)
    return [
        Scenario("L0 baseline: candidate import, deficit 100, decay on", markets=[replace(base)], **q, **town),
        Scenario("L1 build 3 more levels (6)", markets=[final_import(6)], **q, **town),
        Scenario("L2 halve the deficit (farms/cookeries: production 250)",
                 markets=[replace(base)], consumption=300.0, production=250.0, **q),
        Scenario("L3 +50% production efficiency (advances)", markets=[replace(base)], efficiency=1.5, **q, **town),
        Scenario("L4 a law worth +0.4 purchase output (like today's societal value x8)",
                 markets=[replace(base, offset=2.4)], **q, **town),
        Scenario("L5 subsidise the import (never lays off; owner eats the loss)",
                 markets=[replace(base, subsidized=True)], **q, **town),
        Scenario("L6 'hoard' method: own dummy good with constant +3.0, costs 3 victuals",
                 markets=[replace(base, offset=3.0, victuals_per_level=3.0)], **q, **town),
        Scenario("L7 cheaper victuals: mean price 1.25 instead of 2.47",
                 markets=[replace(base)], workers_per_level=1, price_noise=0.15, victuals_mean=1.25,
                 additive_efficiency=True, prosperity=True, decay=0.01, months=600, **town),
        Scenario("L8 granaries: decay 0.5%/month instead of 1%",
                 markets=[replace(base)], workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS,
                 additive_efficiency=True, prosperity=True, decay=0.005, months=600, **town),
    ]


def slow_loop_scenarios(town: dict) -> list[Scenario]:
    """Prosperity and the pop-growth gate are slow integrators on consumption; 100-year runs."""
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True, months=1200)
    surplus = dict(consumption=300.0, production=400.0)
    return [
        Scenario("G1 FINAL import, deficit town, prosperity", markets=[final_import(3)], prosperity=True, **q, **town),
        Scenario("G2 FINAL pair, surplus, prosperity",
                 markets=[final_import(3), final_export(2)], prosperity=True, **q, **surplus),
        Scenario("G3 FINAL import, deficit town, prosperity + pop growth",
                 markets=[final_import(3)], prosperity=True, pop_growth=True, **q, **town),
        Scenario("G4 FINAL pair, surplus, prosperity + pop growth",
                 markets=[final_import(3), final_export(2)], prosperity=True, pop_growth=True, **q, **surplus),
        Scenario("G5 FINAL import, prosperity x4 gain, +100% consumption (stress)",
                 markets=[final_import(3)], prosperity=True, prosperity_gain=0.01, prosperity_consumption=1.0,
                 **q, **town),
        Scenario("G6 FINAL pair, surplus, prosperity x4 gain, +100% consumption (stress)",
                 markets=[final_import(3), final_export(2)], prosperity=True, prosperity_gain=0.01,
                 prosperity_consumption=1.0, **q, **surplus),
        Scenario("G7 CURRENT design (observed prices), deficit town, prosperity + pop growth",
                 markets=[observed_import(3), observed_export(2)], prosperity=True, pop_growth=True, **q, **town),
    ]


# FINAL candidate (2026-09-22): slope 4/yr so +50 % efficiency shifts a threshold by 1.5 months;
# constants on the country base values; dummy output 30 (bottoms out at 1 gold).
#   import: 1 + 2.0 - 4y - 0.3 x staffed levels + E   -> 3x at 0 months, 1x at 6, zero at 9
#   export: 1 - 6.0 + 4y - 0.3 x staffed levels + E   -> zero at 15 months, 1x at 18, 3x at 24 (cap)
def final_import(levels: int) -> Market:
    return Market(levels, gate_per_year=-4.0, droop_per_level=-0.30, offset=2.0, revenue_base=30.0 * DUMMY,
                  cost=LABOUR, victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)


def final_export(levels: int) -> Market:
    return Market(levels, gate_per_year=4.0, droop_per_level=-0.30, offset=-6.0, revenue_base=30.0 * DUMMY,
                  cost=10.0 * 1.06 + LABOUR, victuals_per_level=-2.0, food_sign=-1.0)


def final_scenarios(town: dict) -> list[Scenario]:
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True)
    surplus = dict(consumption=300.0, production=400.0)
    return [
        Scenario("F1 FINAL import alone, deficit town", markets=[final_import(3)], **q, **town),
        Scenario("F2 FINAL import alone, +50% efficiency", markets=[final_import(3)], efficiency=1.5, **q, **town),
        Scenario("F3 FINAL import alone, -10% efficiency", markets=[final_import(3)], efficiency=0.9, **q, **town),
        Scenario("F4 FINAL import alone, 6 levels", markets=[final_import(6)], **q, **town),
        Scenario("F5 FINAL pair, deficit town", markets=[final_import(3), final_export(2)], **q, **town),
        Scenario("F6 FINAL pair, deficit town, +50% efficiency",
                 markets=[final_import(3), final_export(2)], efficiency=1.5, **q, **town),
        Scenario("F7 FINAL pair, surplus province", markets=[final_import(3), final_export(2)], **q, **surplus),
        Scenario("F8 FINAL pair, surplus province, +50% efficiency",
                 markets=[final_import(3), final_export(2)], efficiency=1.5, **q, **surplus),
        Scenario("F9 FINAL pair, surplus, start at 22 months",
                 markets=[final_import(3), final_export(2)], start_months=22.0, **q, **surplus),
    ]


# Engine rules confirmed by Jan 2026-09-22: staffing ramps on profit sign until it flips or hits 0/100 %,
# output clamps at zero, production efficiency ADDS into the goods-output-modifier pool, methods carry no
# modifiers, negative inputs are efficiency-immune demand reductions.
def refined_import(levels: int, output: float = 30.0, offset: float = 1.0, gate: float = -2.0,
                   droop: float = -0.20) -> Market:
    # output = base x (1 + 1.0 - 2.0 x stored years - 0.2 x staffed levels + efficiency)
    # -> 2x at 0 months, 1x at 6, zero at 12 months (rank constant supplies the +1.0)
    return Market(levels, gate_per_year=gate, droop_per_level=droop, offset=offset, revenue_base=output * DUMMY,
                  cost=LABOUR, victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)


def refined_export(levels: int, output: float = 30.0, offset: float = -2.0, gate: float = 2.0,
                   droop: float = -0.20) -> Market:
    # zero below 12 months, 1x at 18, 2x at 24; the offset input stays so the 2 victuals of revenue
    # (efficiency-immune negative input) cannot keep the export profitable while its output is zero
    return Market(levels, gate_per_year=gate, droop_per_level=droop, offset=offset, revenue_base=output * DUMMY,
                  cost=10.0 * 1.06 + LABOUR, victuals_per_level=-2.0, food_sign=-1.0)


def refined_scenarios(town: dict) -> list[Scenario]:
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True)
    return [
        Scenario("Z1 REFINED import alone (offset +1, gate -2/yr, droop -0.2, output 30)",
                 markets=[refined_import(3)], **q, **town),
        Scenario("Z2 REFINED import alone, +50% efficiency (additive)",
                 markets=[refined_import(3)], efficiency=1.5, **q, **town),
        Scenario("Z3 REFINED import + CURRENT export, same province",
                 markets=[refined_import(3), observed_export(2)], **q, **town),
        Scenario("Z4 REFINED import + REFINED export, same province",
                 markets=[refined_import(3), refined_export(2)], **q, **town),
        Scenario("Z5 REFINED pair, +50% efficiency",
                 markets=[refined_import(3), refined_export(2)], efficiency=1.5, **q, **town),
        Scenario("Z6 REFINED pair, +100% efficiency",
                 markets=[refined_import(3), refined_export(2)], efficiency=2.0, **q, **town),
        Scenario("Z7 REFINED pair, surplus province (production 400, consumption 300)",
                 markets=[refined_import(3), refined_export(2)], workers_per_level=1, price_noise=0.25,
                 victuals_mean=VICTUALS, additive_efficiency=True, consumption=300.0, production=400.0),
        Scenario("Z8 REFINED pair, surplus province, +50% efficiency",
                 markets=[refined_import(3), refined_export(2)], efficiency=1.5, workers_per_level=1,
                 price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True,
                 consumption=300.0, production=400.0),
    ]


# 1355 save export: the dummy goods have no buyers and sit at ~1.1 gold (default 5), victuals at 2.47.
DUMMY = 1.1
LABOUR = 0.5 * 1.39
VICTUALS = 2.47


def observed_import(levels: int, gate: float = -0.5, droop: float = 0.0, output: float = 6.0) -> Market:
    return Market(levels, gate_per_year=gate, droop_per_level=droop, revenue_base=output * DUMMY,
                  cost=LABOUR, victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)


def observed_export(levels: int) -> Market:
    return Market(levels, gate_per_year=0.5, droop_per_level=-0.012, revenue_base=6.0 * DUMMY,
                  cost=10.0 * 1.06 + LABOUR, victuals_per_level=-2.0, food_sign=-1.0)


def observed_price_scenarios(town: dict) -> list[Scenario]:
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS)
    return [
        Scenario("T  OBSERVED prices, current design, import + export, price noise",
                 markets=[observed_import(3), observed_export(2)], **q, **town),
        Scenario("U  OBSERVED prices, current import only, price noise",
                 markets=[observed_import(3)], **q, **town),
        Scenario("V  OBSERVED prices, proposed import (gate -1.2, droop -0.10, output 6)",
                 markets=[observed_import(3, gate=-1.2, droop=-0.10)], **q, **town),
        Scenario("W  OBSERVED prices, proposed import, output raised to 30",
                 markets=[observed_import(3, gate=-1.2, droop=-0.10, output=30.0)], **q, **town),
        Scenario("X  OBSERVED prices, proposed import output 30 + current export",
                 markets=[observed_import(3, gate=-1.2, droop=-0.10, output=30.0), observed_export(2)], **q, **town),
        Scenario("Y  OBSERVED prices, proposed import output 30, +50% efficiency",
                 markets=[observed_import(3, gate=-1.2, droop=-0.10, output=30.0)], efficiency=1.5, **q, **town),
    ]


# ---------------------------------------------------------------------------------------------
# Multi-channel markets (2026-09-22): a method is a linear combination of dummy-good basis vectors.
# Produced dummy g: revenue = amount x price x max(0, 1 + c + k*y + d*N*f + E)  (efficiency adds in)
# Negative input:   revenue = amount x price                                     (efficiency-immune)
# ---------------------------------------------------------------------------------------------
@dataclass
class Channel:
    amount: float
    price: float = 1.1          # dummy goods bottom out near 1 gold
    c: float = 0.0              # country constant on this good's output modifier
    k: float = 0.0              # per stored year (growth modifier)
    d: float = 0.0              # per staffed level (building modifier block on this good)
    negative_input: bool = False
    starving_bonus: float = 0.0 # added to the modifier while the province stockpile is empty

    def revenue(self, years: float, staffed_levels: float, efficiency: float, starving: bool = False) -> float:
        if self.negative_input:
            return self.amount * self.price
        m = 1.0 + self.c + self.k * years + self.d * staffed_levels + (efficiency - 1.0)
        if starving:
            m += self.starving_bonus
        return self.amount * self.price * max(0.0, m)


@dataclass
class Method:
    name: str
    channels: list[Channel]
    victuals: float = 2.0       # victuals bought per level (import) or sold (negative)
    labour: float = 0.7         # fixed labour input cost per level
    imports_food: bool = True   # whether this method moves the +60 food (a "none" method does not)


@dataclass
class MultiMarket:
    levels: int
    methods: list[Method]
    base_channels: list[Channel] = field(default_factory=list)  # always-on income, e.g. a steady negative input
    locked: int | None = None   # player lock: index into methods; None = AI picks the most profitable
    switch_every: int = 1       # AI re-evaluates methods every N months (0 = never)
    current: int = 0
    staffing: float = 0.0
    month: int = 0
    duty: list[int] = field(default_factory=list)
    profit_log: list[float] = field(default_factory=list)
    gold_log: list[float] = field(default_factory=list)

    sign: float = 1.0           # +1 import (adds food), -1 export (removes food)

    def profit(self, i: int, years: float, efficiency: float, victuals_price: float,
               starving: bool = False) -> float:
        m = self.methods[i]
        staffed = self.levels * self.staffing
        rev = sum(ch.revenue(years, staffed, efficiency, starving) for ch in m.channels + self.base_channels)
        return rev - m.victuals * victuals_price - m.labour

    def step(self, years: float, starving: bool, efficiency: float, additive: bool,
             workers_per_level: int = 1, victuals_price: float = 3.0) -> None:
        self.month += 1
        if self.locked is not None:
            self.current = self.locked
        elif self.switch_every and self.month % self.switch_every == 0:
            self.current = max(range(len(self.methods)),
                               key=lambda i: self.profit(i, years, efficiency, victuals_price, starving))
        p = self.profit(self.current, years, efficiency, victuals_price, starving)
        self.profit_log.append(p)
        self.gold_log.append(p * self.levels * self.staffing)
        total = self.levels * max(1, workers_per_level)
        step = max(1, round(RAMP * total))
        employed = round(self.staffing * total) + (step if p > 0 else -step)
        self.staffing = min(1.0, max(0.0, employed / total))
        self.duty.append(self.current)

    def food(self) -> float:
        if not self.methods[self.current].imports_food:
            return 0.0
        return self.sign * FOOD_PER_LEVEL * self.levels * self.staffing

    @property
    def food_sign(self) -> float:
        return self.sign


# basis vectors
def G_steep(amount: float, d: float) -> Channel:   # gate: 10x at empty, zero at 15 months
    return Channel(amount, c=9.0, k=-8.0, d=-d)


def G_shallow(amount: float, d: float) -> Channel:  # current basis: 5x at empty, zero at 15 months
    return Channel(amount, c=4.0, k=-4.0, d=-d)


def steady_income(gold: float) -> Channel:          # negative input of a demanded dummy, efficiency-immune
    return Channel(gold / 1.1, negative_input=True)


def multi_scenarios() -> list[Scenario]:
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True,
             prosperity=True, decay=0.01, months=600)
    out = []
    cases = [(100, 8), (300, 14), (600, 24)]     # deficit, levels (generous: cap never binds)

    def market(levels, methods, base, locked=None, switch=1):
        return MultiMarket(levels, methods, base_channels=base, locked=locked, switch_every=switch)

    variants = {
        "M1 single channel a6 shallow d0.03 (today, droop 0.03)":
            (lambda: [Method("std", [G_shallow(6.0, 0.03)])], []),
        "M2 gate a2 steep d0.10 + steady 4.2":
            (lambda: [Method("std", [G_steep(2.0, 0.10)])], [steady_income(4.2)]),
        "M3 gate a2 steep d0.03 + steady 4.2":
            (lambda: [Method("std", [G_steep(2.0, 0.03)])], [steady_income(4.2)]),
        "M4 gate a4 steep d0.10 + steady 2.0":
            (lambda: [Method("std", [G_steep(4.0, 0.10)])], [steady_income(2.0)]),
    }
    for name, (mk, base) in variants.items():
        for D, N in cases:
            for E in (1.0, 1.5):
                out.append(Scenario(f"{name} | deficit {D} N{N} eff {E:.1f}",
                                    markets=[market(N, mk(), base, locked=0)],
                                    consumption=300.0 + D, production=300.0, efficiency=E, **q))
    # AI switching among standard / prudent / none, M2 parameters
    def methods_ai():
        return [Method("std", [G_steep(2.0, 0.10)]),
                Method("prudent", [G_shallow(2.0, 0.10)]),
                Method("none", [], victuals=0.0, imports_food=False)]
    for cadence in (1, 3, 12):
        for D, N in cases:
            out.append(Scenario(f"S{cadence:02d} AI switches every {cadence} months (std/prudent/none) | deficit {D} N{N}",
                                markets=[market(N, methods_ai(), [steady_income(4.2)], switch=cadence)],
                                consumption=300.0 + D, production=300.0, **q))
    for D, N in cases:
        out.append(Scenario(f"P  player locks prudent | deficit {D} N{N}",
                            markets=[market(N, methods_ai(), [steady_income(4.2)], locked=1)],
                            consumption=300.0 + D, production=300.0, **q))
    return out


def summarize_multi(s: Scenario) -> str:
    tail = s.trace[-120:]
    ms = [t[0] for t in tail]
    m = s.markets[0]
    duty = ""
    if isinstance(m, MultiMarket) and m.duty:
        d = m.duty[-120:]
        names = [x.name for x in m.methods]
        duty = "  methods " + " ".join(f"{n}:{d.count(i)/len(d):.0%}" for i, n in enumerate(names) if d.count(i))
    return (f"{s.name:70s} rest {min(ms):4.1f}..{max(ms):4.1f} ({max(ms)-min(ms):3.1f} wide) "
            f"staff {sum(t[1] for t in tail)/len(tail):3.0%}{duty}")


def profit_report(name: str, s: Scenario, years_tail: int = 40) -> str:
    """Gold per level and per building, against input cost, over the last `years_tail` years."""
    lines = [name]
    n = years_tail * 12
    for m in s.markets:
        if not isinstance(m, Market) or not m.profit_log:
            continue
        pl, gl, cl = m.profit_log[-n:], m.gold_log[-n:], m.cost_log[-n:]
        mean = sum(pl) / len(pl)
        sd = (sum((x - mean) ** 2 for x in pl) / len(pl)) ** 0.5
        cost = sum(cl) / len(cl)
        gold_month = sum(gl) / len(gl)
        pos = sum(x for x in gl if x > 0)
        neg = -sum(x for x in gl if x < 0)
        kind = "import" if m.food_sign > 0 else "export"
        lines.append(
            f"  {kind} x{m.levels:<2d}: profit/level mean {mean:6.2f}  sd {sd:5.2f}  min {min(pl):6.2f}  max {max(pl):6.2f} gold/month"
            f"  | input cost/level {cost:5.2f}  -> noise/cost {sd / cost:4.2f}"
            f"  | building {gold_month:+7.1f} gold/month, {years_tail} yrs: +{pos:8.0f} earned, -{neg:7.0f} lost")
    return "\n".join(lines)


def profit_scenarios() -> list[tuple[str, Scenario]]:
    """The recommended parameter set (import +6.7/-8/-0.03, export -13/+8/-0.03, output 6) with profit logs."""
    q = dict(workers_per_level=1, price_noise=0.25, victuals_mean=VICTUALS, additive_efficiency=True,
             prosperity=True, decay=0.01, months=600)
    R = 6 * DUMMY

    def imp(n: int) -> Market:
        return Market(n, gate_per_year=-8.0, droop_per_level=-0.03, offset=6.7, revenue_base=R, cost=LABOUR,
                      victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)

    def exp(n: int) -> Market:
        return Market(n, gate_per_year=8.0, droop_per_level=-0.03, offset=-13.0, revenue_base=R,
                      cost=10 * 1.06 + LABOUR, victuals_per_level=-2.0, food_sign=-1.0)

    cases = [
        ("village, deficit 60, 3 import levels", [imp(3)], 360, 300, 1.0, 6.0),
        ("town, deficit 100, 8 levels", [imp(8)], 400, 300, 1.0, 6.0),
        ("town, starts empty", [imp(8)], 400, 300, 1.0, 0.0),
        ("town, +50% efficiency", [imp(8)], 400, 300, 1.5, 6.0),
        ("big city, deficit 600, 24 levels", [imp(24)], 900, 300, 1.0, 6.0),
        ("surplus province (+200), 3 import + 3 export", [imp(3), exp(3)], 300, 500, 1.0, 6.0),
        ("surplus province, starts at 24 months", [imp(3), exp(3)], 300, 500, 1.0, 24.0),
        ("today's live numbers: town (+4/-4/-0.30)",
         [Market(8, gate_per_year=-4.0, droop_per_level=-0.30, offset=4.0, revenue_base=R, cost=LABOUR,
                 victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)], 400, 300, 1.0, 6.0),
        ("pre-2026-09-22 numbers: town (+0.5/-0.5, no droop)",
         [Market(8, gate_per_year=-0.5, droop_per_level=0.0, offset=0.5, revenue_base=R, cost=LABOUR,
                 victuals_per_level=2.0, starving_bonus=2.0, food_sign=1.0)], 400, 300, 1.0, 6.0),
    ]
    out = []
    for name, mk, c, p, e, start in cases:
        out.append((name, Scenario(name, markets=mk, consumption=float(c), production=float(p),
                                   efficiency=e, start_months=start, **q)))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", help="write a chart of stored months per scenario")
    parser.add_argument("--multi", action="store_true", help="run the multi-channel method scenarios only")
    parser.add_argument("--profit", action="store_true", help="profit/loss report for the recommended parameter set")
    args = parser.parse_args()

    if args.profit:
        for name, s in profit_scenarios():
            run(s)
            print(profit_report(name, s))
        return

    if args.multi:
        for s in multi_scenarios():
            print(summarize_multi(run(s)))
        return

    results = [run(s) for s in scenarios()]
    for s in results:
        print(summarize(s))

    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(len(results), 1, figsize=(11, 2.0 * len(results)), sharex=True)
        for ax, s in zip(axes, results):
            ys = [t[0] for t in s.trace]
            ax.plot(ys, color="#1f77b4", lw=1.2, label="months stored")
            ax2 = ax.twinx()
            ax2.plot([t[1] for t in s.trace], color="#2ca02c", lw=0.8, alpha=0.7, label="import staffing")
            if any(t[2] for t in s.trace):
                ax2.plot([t[2] for t in s.trace], color="#d62728", lw=0.8, alpha=0.7, label="export staffing")
            ax2.set_ylim(0, 1.05)
            ax.set_ylim(0, 26)
            ax.set_ylabel("months")
            ax.set_title(s.name, fontsize=9, loc="left")
            ax.grid(alpha=0.3)
        axes[-1].set_xlabel("month")
        fig.tight_layout()
        fig.savefig(args.png, dpi=110)
        print(f"chart written to {args.png}")


if __name__ == "__main__":
    main()
