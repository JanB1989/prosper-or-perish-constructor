"""Province food simulator: victuals import/export markets, farm method switch and the harvest cycle.

Engine rules (verified in game 2026-09-24/25), one province, monthly steps:

* storage is an integrator: food += production x (1 + farmed_share x h) - consumption
  + 90 x staffed import levels - 90 x staffed export levels + 0.96 x M x farm levels on Provision;
  stored months = food / consumption, stored years = min(2, months / 12); storage clamps at 0 and a cap.
* market staffing ramps +/- RAMP per month toward the sign of the building's current profit per staffed
  level (never rests, 0..1). Levels are fixed per scenario (the AI only adds levels).
* farms are always staffed; each level runs Provision when provision_margin > sell_income, else Sell.
* each September the region's harvest h is re-rolled from {-0.5 (20 %), 0 (60 %), +0.5 (20 %)} and held;
  the crop price follows crop_base / (1 + h) clipped 0.6..1.8. The victuals price is the market's:
  a mean-reverting walk around P_MEAN, optionally pushed by a market-wide harvest correlated with the local one.

Current methods per level (prices at their floors: dummies 1.0, labour 1.0, victuals p):
  import slot 0: 0.45 offset x 20 = 9.0 - 3p - 0.3          slot 1: 0.375 x (1 + 15 - 8y + 8 starving - 0.1 N) - 3
  export:        3p + 0.375 x (1 - 1 + 8y - 0.1 N) - 11.1 - 0.3
  farm (M = 1):  provision 0.96 x 0.10 - 0.08 x crop      sell 0.005 x (1 - 1 + 8y - 0.1 N_export)

This module is independent of tools/victuals_market_sim.py (that file models the older 60-food design).

Run:
  uv run python tools/province_food_sim.py --calibrate
  uv run python tools/province_food_sim.py --sweep [--seeds 8] [--png out.png]
  uv run python tools/province_food_sim.py --trace base pair --seed 1
  uv run python tools/province_food_sim.py --sweep --set import.prem_amount=0.75 --set export.offset_cost=12.5
"""
from __future__ import annotations

import argparse
import random
import statistics
from dataclasses import dataclass, field, fields, replace

FOOD_PER_LEVEL = 90.0
HARVEST = ((-1.0, 0.2), (0.0, 0.6), (1.0, 0.2))  # sign x World.harvest_amp
SEPTEMBER = 8  # month index within the year (0 = January)


# ---------------------------------------------------------------------------------------------
# market and farm definitions
# ---------------------------------------------------------------------------------------------
@dataclass
class ImportSpec:
    offset_income: float = 9.0    # slot 0 revenue per level: 0.45 offset x (1 + 19) x 1 gold
    victuals: float = 3.0         # victuals bought per level (slot 0)
    labour: float = 0.3
    prem_amount: float = 0.375    # slot 1: province_food_purchase units per level
    prem_c: float = 15.0          # country constant on the purchase output modifier
    prem_k: float = -8.0          # per stored year
    prem_starving: float = 8.0    # province_starving
    prem_cost: float = 3.0        # slot 1 offset input (gold)
    droop: float = -0.10          # purchase output modifier per staffed import level in the location

    def profit(self, years: float, starving: bool, staffed: float, p: float) -> float:
        m = 1.0 + self.prem_c + self.prem_k * years + self.droop * staffed
        if starving:
            m += self.prem_starving
        return (self.offset_income - self.victuals * p - self.labour
                + self.prem_amount * max(0.0, m) - self.prem_cost)


@dataclass
class ExportSpec:
    victuals: float = 3.0         # victuals sold per level (negative input: efficiency-immune revenue)
    sales_amount: float = 0.375   # province_food_sales units per level
    sales_c: float = -1.0         # country constant on the sales output modifier
    sales_k: float = 8.0          # per stored year
    droop: float = -0.10          # sales output modifier per staffed export level in the location
    offset_cost: float = 11.1
    labour: float = 0.3

    def profit(self, years: float, staffed: float, p: float) -> float:
        m = 1.0 + self.sales_c + self.sales_k * years + self.droop * staffed
        return self.victuals * p + self.sales_amount * max(0.0, m) - self.offset_cost - self.labour


@dataclass
class FarmSpec:
    M: float = 1.0
    provision_food: float = 0.96  # local_food per level (1 food per unit)
    local_food_price: float = 0.10
    crop_in: float = 0.08
    sell_scale: float = 0.005     # province_food_sales per level on Sell

    def provision_margin(self, crop_price: float) -> float:
        return self.M * (self.provision_food * self.local_food_price - self.crop_in * crop_price)

    def sell_income(self, years: float, export_staffed: float, sales: ExportSpec) -> float:
        # the sales output modifier is location-wide: the export's droop also hits the farms' sell leg
        m = 1.0 + sales.sales_c + sales.sales_k * years + sales.droop * export_staffed
        return self.M * self.sell_scale * max(0.0, m)


@dataclass
class World:
    ramp: float = 0.05            # staffing change per month (PROFITABLE/UNPROFITABLE_BUILDING_WORKERS_*)
    ramp_mult: float = 1.0        # define change relative to today (2.0 = define 0.05 -> 0.10)
    cap_months: float = 36.0      # storage cap (food capacity), in months of consumption (assumption)
    start_months: float = 12.0
    farmed_share: float = 0.8     # share of local production that moves with the harvest roll
    harvest_amp: float = 0.5      # size of a bad/good roll (20 % each, 60 % neutral)
    crop_base: float = 0.73       # crop price at a neutral harvest
    p_mean: float = 2.7           # victuals price level of the market
    p_sigma: float = 0.10         # monthly noise of the victuals price (gold)
    p_revert: float = 0.15        # monthly mean reversion of the victuals price
    p_beta: float = 0.3           # victuals price response to the market harvest: p* = p_mean / (1 + beta h_m)
                                  # (0.3: a -0.8 market harvest lifts 2.7 to 3.5, the observed p90)
    p_corr: float = 0.5           # chance the market harvest equals the local roll (else an independent roll)
    harvest: bool = True
    months: int = 120


@dataclass
class Archetype:
    name: str
    consumption: float
    ratio: float                  # local production (excluding farm Provision, neutral harvest) / consumption
    imports: int
    exports: int
    farms: int


ARCHETYPES = {
    "surplus": Archetype("surplus", 1000.0, 1.2, 0, 4, 6),
    "deficit": Archetype("deficit", 1000.0, 0.8, 4, 0, 3),
    "pair": Archetype("pair", 1000.0, 1.0, 3, 7, 5),
    # calibration references (world medians: no market 8.7 months, import only 18, pair 26)
    "nomarket": Archetype("nomarket", 1000.0, 1.0, 0, 0, 5),
    "importonly": Archetype("importonly", 1000.0, 0.9, 3, 0, 5),
}


@dataclass
class Scenario:
    name: str
    note: str = ""
    imp: dict = field(default_factory=dict)
    exp: dict = field(default_factory=dict)
    farm: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)
    exclusive: str | None = None  # None | "balance" (import iff balance < 0, else export) | "import" | "export"


# ---------------------------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------------------------
def roll(rng: random.Random, amp: float) -> float:
    x = rng.random()
    acc = 0.0
    for h, w in HARVEST:
        acc += w
        if x < acc:
            return h * amp
    return HARVEST[-1][0] * amp


@dataclass
class Run:
    months: list[float]
    s_imp: list[float]
    s_exp: list[float]
    farms_prov: list[float]
    money: list[float]            # sum |building profit| of both markets, gold per month
    profit_imp: list[float]
    profit_exp: list[float]
    harvest: list[float]
    price: list[float]
    starving: list[bool]
    churn: list[float]            # food imported and exported in the same month: 90 x min(staffed i, staffed e)


def simulate(arch: Archetype, sc: Scenario, seed: int | None, overrides: dict | None = None) -> Run:
    ov = overrides or {}
    imp = replace(ImportSpec(), **{**sc.imp, **ov.get("import", {})})
    exp = replace(ExportSpec(), **{**sc.exp, **ov.get("export", {})})
    farm = replace(FarmSpec(), **{**sc.farm, **ov.get("farm", {})})
    w = replace(World(), **{**sc.world, **ov.get("world", {})})
    arch = replace(arch, **{k: (int(v) if k in ("imports", "exports", "farms") else v)
                           for k, v in ov.get("arch", {}).items()})
    if seed is None:
        w = replace(w, harvest=False, p_sigma=0.0)

    n_imp, n_exp = arch.imports, arch.exports
    if sc.exclusive:
        # a build-time allow: a province holds one market type only
        keep = sc.exclusive
        if keep == "balance":
            keep = "import" if arch.ratio < 1.0 else "export"
        total = n_imp + n_exp
        if keep == "import":
            n_imp, n_exp = (n_imp or total), 0
        else:
            n_imp, n_exp = 0, (n_exp or total)

    rng = random.Random(seed if seed is not None else 0)
    C = arch.consumption
    food = w.start_months * C
    cap = w.cap_months * C
    s_i = s_e = 0.0
    h = h_m = 0.0
    p = w.p_mean
    out = Run([], [], [], [], [], [], [], [], [], [], [])
    for t in range(int(w.months)):
        if w.harvest and t % 12 == SEPTEMBER:
            h = roll(rng, w.harvest_amp)
            h_m = h if rng.random() < w.p_corr else roll(rng, w.harvest_amp)
        if w.harvest or w.p_sigma:
            target = w.p_mean / (1.0 + w.p_beta * h_m)
            p += w.p_revert * (target - p) + rng.gauss(0.0, w.p_sigma)
            p = min(2.0 * w.p_mean, max(0.4 * w.p_mean, p))
        crop = min(1.8, max(0.6, w.crop_base / (1.0 + h)))

        years = min(2.0, food / C / 12.0)
        starving = food <= 0.0
        N_i, N_e = n_imp * s_i, n_exp * s_e

        # farms: method by profit, no hysteresis
        prov = farm.provision_margin(crop) > farm.sell_income(years, N_e, exp)
        farm_food = farm.provision_food * farm.M * arch.farms if prov else 0.0

        # markets: profit per staffed level at current staffing, then ramp
        pi = imp.profit(years, starving, N_i, p) if n_imp else 0.0
        pe = exp.profit(years, N_e, p) if n_exp else 0.0
        money = abs(pi * N_i) + abs(pe * N_e)
        flow = (arch.ratio * C * (1.0 + w.farmed_share * h) - C + farm_food
                + FOOD_PER_LEVEL * (N_i - N_e))
        food = min(cap, max(0.0, food + flow))
        if n_imp:
            s_i = min(1.0, max(0.0, s_i + (w.ramp * w.ramp_mult if pi > 0 else -w.ramp * w.ramp_mult)))
        if n_exp:
            s_e = min(1.0, max(0.0, s_e + (w.ramp * w.ramp_mult if pe > 0 else -w.ramp * w.ramp_mult)))

        out.months.append(food / C)
        out.s_imp.append(N_i / n_imp if n_imp else 0.0)
        out.s_exp.append(N_e / n_exp if n_exp else 0.0)
        out.farms_prov.append(1.0 if prov else 0.0)
        out.money.append(money)
        out.profit_imp.append(pi)
        out.profit_exp.append(pe)
        out.harvest.append(h)
        out.price.append(p)
        out.starving.append(food <= 0.0)
        out.churn.append(FOOD_PER_LEVEL * min(N_i, N_e))
    return out


# ---------------------------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------------------------
def zigzag_flips(xs: list[float], threshold: float = 1.0) -> int:
    """Direction reversals that retrace at least `threshold` months from the last extreme."""
    flips, direction = 0, 0
    hi = lo = ext = xs[0]
    for x in xs:
        if direction == 0:
            hi, lo = max(hi, x), min(lo, x)
            if hi - x >= threshold:
                direction, ext = -1, x
            elif x - lo >= threshold:
                direction, ext = 1, x
        elif direction == 1:
            if x > ext:
                ext = x
            elif ext - x >= threshold:
                flips, direction, ext = flips + 1, -1, x
        else:
            if x < ext:
                ext = x
            elif x - ext >= threshold:
                flips, direction, ext = flips + 1, 1, x
    return flips


def quarterly_flips(qs: list[float]) -> int:
    d = [b - a for a, b in zip(qs, qs[1:]) if abs(b - a) > 1e-6]
    return sum(1 for a, b in zip(d, d[1:]) if (a > 0) != (b > 0))


def settle_month(xs: list[float], band: float = 2.0) -> int | None:
    final = statistics.fmean(xs[-12:])
    last_bad = None
    for i, x in enumerate(xs):
        if abs(x - final) > band:
            last_bad = i
    if last_bad is None:
        return 0
    if last_bad >= len(xs) - 12:
        return None
    return last_bad + 1


@dataclass
class Metrics:
    amp: float
    flips_yr: float
    settle: int | None
    money: float
    final: float
    starving: float
    churn: float
    s_imp: float
    s_exp: float
    farms_prov: float
    q_amp: float       # observed-style: max-min of quarterly samples, months 24..48
    q_flips: float     # observed-style: direction flips in those 9 samples (per 8 quarters)


def metrics(r: Run) -> Metrics:
    tail = r.months[24:]
    years = len(tail) / 12.0
    q = r.months[24:49:3]
    return Metrics(
        amp=max(tail) - min(tail),
        flips_yr=zigzag_flips(tail) / years,
        settle=settle_month(r.months),
        money=statistics.fmean(r.money[24:]),
        final=statistics.fmean(r.months[-12:]),
        starving=sum(r.starving[24:]) / len(tail),
        churn=statistics.fmean(r.churn[24:]),
        s_imp=statistics.fmean(r.s_imp[24:]),
        s_exp=statistics.fmean(r.s_exp[24:]),
        farms_prov=statistics.fmean(r.farms_prov[24:]),
        q_amp=max(q) - min(q),
        q_flips=quarterly_flips(q),
    )


def aggregate(ms: list[Metrics]) -> dict:
    med = lambda k: statistics.median(getattr(m, k) for m in ms)  # noqa: E731
    settled = [m.settle for m in ms if m.settle is not None]
    return dict(
        amp=med("amp"), flips_yr=med("flips_yr"), money=med("money"), final=med("final"),
        starving=statistics.fmean(m.starving for m in ms), s_imp=med("s_imp"), s_exp=med("s_exp"),
        churn=med("churn"),
        farms_prov=statistics.fmean(m.farms_prov for m in ms),
        settle=(statistics.median(settled) if len(settled) * 2 > len(ms) else None),
        settled_share=len(settled) / len(ms),
        q_amp=med("q_amp"), q_flips=statistics.fmean(m.q_flips for m in ms),
    )


def evaluate(arch: Archetype, sc: Scenario, seeds: list[int], overrides: dict | None = None) -> dict:
    agg = aggregate([metrics(simulate(arch, sc, s, overrides)) for s in seeds])
    det = metrics(simulate(arch, sc, None, overrides))  # no harvest, fixed price
    agg["settle_nh"] = det.settle
    agg["amp_nh"] = det.amp
    agg["final_nh"] = det.final
    return agg



# ---------------------------------------------------------------------------------------------
# regimes: the stated province size vs the loop gain that reproduces the observed swings
# ---------------------------------------------------------------------------------------------
REGIMES = {
    # 90 food per level = 9 % of consumption, ramp as the define says, harvest +/-0.5 on 80 % of production
    "spec": {},
    # calibrated on the observed paired provinces (quarterly amplitude ~20-25, ~2.5 flips per 8 quarters):
    # 90 food per level = 90 % of consumption, effective ramp 0.15/month (observed staffing moves 0.13-0.15
    # per month), harvest +/-0.8 on all local production (no-market quarterly amplitude 8.0 vs 8.7 observed)
    "calibrated": {"arch": {"consumption": 100.0},
                   "world": {"ramp": 0.15, "harvest_amp": 0.8, "farmed_share": 1.0}},
}


def merge(a: dict, b: dict) -> dict:
    out = {k: dict(v) for k, v in a.items()}
    for k, v in b.items():
        out.setdefault(k, {}).update(v)
    return out


# ---------------------------------------------------------------------------------------------
# scenarios (engine-legal levers)
# ---------------------------------------------------------------------------------------------
IMP_SPLIT = dict(offset_income=4.0, prem_amount=1.0)            # L1b
EXP_ZERO_BELOW_12 = dict(sales_c=-17.0, sales_k=16.0)            # L2c: 16(y - 1), 0 at 12 months, 16x at 24


def band_design(i_be: float, e_be: float, i_zero: float = 24.0, e_zero: float = 12.0, p_ref: float = 2.7,
                income: float = 5.0, export_cost: float = 13.5, k: float = 8.0) -> tuple[dict, dict]:
    """Import/export numbers with break-evens at i_be / e_be months at the reference victuals price.

    The victuals leg is a loss at every plausible price (import slot 0 income 5.0 < 3 x 1.8 + 0.3;
    export offset 13.5 > 3 x 4.5 - 0.3), so all profit comes from the storage legs. The import leg is zero
    from i_zero months, the export leg zero below e_zero months; k is the per-stored-year slope.
    """
    i_const = k * i_zero / 12.0 - 1.0                         # 1 + c - k y = 0 at i_zero
    i_amount = (3.0 * p_ref + 0.3 + 3.0 - income) / (k * (i_zero - i_be) / 12.0)
    e_const = -1.0 - k * e_zero / 12.0                        # 1 + c + k y = 0 at e_zero
    e_amount = (export_cost + 0.3 - 3.0 * p_ref) / (k * (e_be - e_zero) / 12.0)
    imp = dict(offset_income=income, prem_amount=round(i_amount, 3), prem_c=round(i_const, 3), prem_k=-k)
    exp = dict(offset_cost=export_cost, sales_amount=round(e_amount, 3), sales_c=round(e_const, 3), sales_k=k)
    return imp, exp


def band_scenarios() -> list[Scenario]:
    out = []
    for name, kw in (
        ("B6", dict(i_be=12, e_be=18)),                                   # band 12..18, legs as shallow as allowed
        ("B6s", dict(i_be=12, e_be=18, i_zero=18, e_zero=15)),            # same band, steeper legs
        ("B4", dict(i_be=13, e_be=17, i_zero=19, e_zero=14)),
        ("B2", dict(i_be=14, e_be=16, i_zero=18, e_zero=13)),
    ):
        imp, exp = band_design(**kw)
        note = (f"band {kw['i_be']}..{kw['e_be']}: import {imp['prem_amount']} x (1{imp['prem_c']:+g} - 8y),"
                f" export {exp['sales_amount']} x (1{exp['sales_c']:+g} + 8y)")
        out.append(Scenario(name, note, imp=imp, exp=exp))
        out.append(Scenario(name + "x", note + " + one market type", imp=imp, exp=exp, exclusive="balance"))
        for droop in (0.3, 0.5, 1.0):
            tag = f"d{int(droop * 10)}"
            di, de = dict(imp, droop=-droop), dict(exp, droop=-droop)
            out.append(Scenario(name + tag, note + f" + droop -{droop}", imp=di, exp=de))
            out.append(Scenario(name + tag + "x", note + f" + droop -{droop} + one market type", imp=di, exp=de,
                                exclusive="balance"))
    return out


def scenarios() -> list[Scenario]:
    return lever_scenarios() + band_scenarios() + [recommended()]


def recommended() -> Scenario:
    """Recommendation 2026-09-25: band 12..18 months (B6) + droop -0.3 on both markets."""
    imp, exp = band_design(i_be=12, e_be=18)
    return Scenario("REC", "import 0.25 offset + 0.8 x (16 - 8y), export 13.5 offset + 1.425 x (8y - 8), droop -0.3",
                    imp=dict(imp, droop=-0.3), exp=dict(exp, droop=-0.3))


def lever_scenarios() -> list[Scenario]:
    return [
        Scenario("base", "current numbers"),
        # 1 import income split
        Scenario("L1a", "import offset income 6.0, premium 0.75", imp=dict(offset_income=6.0, prem_amount=0.75)),
        Scenario("L1b", "import offset income 4.0, premium 1.0", imp=IMP_SPLIT),
        # 2 export break-even
        Scenario("L2a", "export offset cost 12.5", exp=dict(offset_cost=12.5)),
        Scenario("L2b", "export offset cost 14.0", exp=dict(offset_cost=14.0)),
        Scenario("L2c", "export sales leg 16(y-1): 0 below 12 months", exp=EXP_ZERO_BELOW_12),
        # 3 droop
        Scenario("L3a", "droop -0.3 both", imp=dict(droop=-0.3), exp=dict(droop=-0.3)),
        Scenario("L3b", "droop -0.5 both", imp=dict(droop=-0.5), exp=dict(droop=-0.5)),
        # 4 mutual exclusion (a build-time allow)
        Scenario("L4", "one market type per province (import iff balance < 0)", exclusive="balance"),
        Scenario("L4i", "one market type: import only", exclusive="import"),
        # 5 farm sell leg
        Scenario("L5a", "farm sell 0.0025", farm=dict(sell_scale=0.0025)),
        Scenario("L5b", "farm sell 0.01", farm=dict(sell_scale=0.01)),
        Scenario("L5c", "farms never sell", farm=dict(sell_scale=0.0)),
        # 6 ramp define
        Scenario("L6", "ramp define x2 (0.05 -> 0.10)", world=dict(ramp_mult=2.0)),
        Scenario("L6h", "ramp define x0.5 (0.05 -> 0.025)", world=dict(ramp_mult=0.5)),
        # 7 combinations
        Scenario("L7a", "L1b + L2c (dead band 13..19 months)", imp=IMP_SPLIT, exp=EXP_ZERO_BELOW_12),
        Scenario("L7b", "L1b + L2c + L4", imp=IMP_SPLIT, exp=EXP_ZERO_BELOW_12, exclusive="balance"),
        Scenario("L7c", "L1b + L2c + L4 + droop -0.5", imp=dict(IMP_SPLIT, droop=-0.5),
                 exp=dict(EXP_ZERO_BELOW_12, droop=-0.5), exclusive="balance"),
        Scenario("L7d", "L1b + L2c + ramp x0.5", imp=IMP_SPLIT, exp=EXP_ZERO_BELOW_12, world=dict(ramp_mult=0.5)),
        Scenario("L7e", "L1b + L2c + L4 + ramp x0.5", imp=IMP_SPLIT, exp=EXP_ZERO_BELOW_12,
                 exclusive="balance", world=dict(ramp_mult=0.5)),
    ]


# ---------------------------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------------------------
def fmt_settle(v) -> str:
    return ">120" if v is None else f"{v:.0f}"


def print_row(label: str, a: dict) -> None:
    print(f"{label:34s} amp {a['amp']:5.1f}  flips/yr {a['flips_yr']:4.2f}  settle {fmt_settle(a['settle']):>4s}"
          f" ({a['settled_share']:4.0%})  nh {fmt_settle(a['settle_nh']):>4s}/{a['amp_nh']:4.1f}"
          f"  |profit| {a['money']:5.1f}  final {a['final']:5.1f}  starv {a['starving']:4.0%}"
          f"  staff i {a['s_imp']:4.0%} e {a['s_exp']:4.0%}  prov {a['farms_prov']:4.0%}"
          f"  | obs-style q-amp {a['q_amp']:5.1f} q-flips {a['q_flips']:3.1f}")


TABLE_HEAD = ("scenario  archetype  |  amp  flips/yr  settle(seeds)  settle/amp no-harvest  |  |profit|/mo"
              "  final  starving  staff i/e  churn food/mo")


def print_table_row(sc: str, arch: str, a: dict) -> None:
    print(f"{sc:8s}  {arch:9s}  | {a['amp']:5.1f}  {a['flips_yr']:6.2f}   {fmt_settle(a['settle']):>4s} ({a['settled_share']:4.0%})"
          f"   {fmt_settle(a['settle_nh']):>4s} / {a['amp_nh']:4.1f}        | {a['money']:7.2f}"
          f"   {a['final']:5.1f}  {a['starving']:5.0%}    {a['s_imp']:3.0%}/{a['s_exp']:3.0%}  {a['churn']:7.1f}")


def parse_sets(items: list[str]) -> dict:
    out: dict = {}
    for item in items or []:
        key, val = item.split("=", 1)
        group, name = key.split(".", 1)
        out.setdefault(group, {})[name] = float(val)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--calibrate", action="store_true", help="current numbers on the calibration archetypes")
    ap.add_argument("--sweep", action="store_true", help="scenario x archetype table")
    ap.add_argument("--verbose", action="store_true", help="long rows (staffing, farms, observed-style metrics)")
    ap.add_argument("--regime", default="calibrated", choices=sorted(REGIMES))
    ap.add_argument("--scenario", help="comma list of scenario names to run (default all)")
    ap.add_argument("--archetype", help="comma list of archetypes (default surplus,deficit,pair)")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--prices", help="comma list of victuals price levels to sweep (world.p_mean)")
    ap.add_argument("--set", action="append", help="override, e.g. import.prem_amount=0.75, world.p_mean=1.8,"
                                                   " arch.consumption=600")
    ap.add_argument("--trace", nargs=2, metavar=("SCENARIO", "ARCHETYPE"), help="print a monthly trace")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--png", help="plot stored months for baseline vs --best on the three archetypes")
    ap.add_argument("--best", default="REC", help="scenario plotted against the baseline")
    args = ap.parse_args()
    ov = merge(REGIMES[args.regime], parse_sets(args.set))
    seeds = list(range(1, args.seeds + 1))
    scs = {s.name: s for s in scenarios()}

    if args.trace:
        sc, arch = scs[args.trace[0]], ARCHETYPES[args.trace[1]]
        r = simulate(arch, sc, args.seed, ov)
        print("month  stored  imp_s  exp_s  prov   h     p     pi     pe")
        for t in range(len(r.months)):
            print(f"{t:5d} {r.months[t]:7.1f} {r.s_imp[t]:6.2f} {r.s_exp[t]:6.2f} {r.farms_prov[t]:4.0f}"
                  f" {r.harvest[t]:+5.1f} {r.price[t]:5.2f} {r.profit_imp[t]:6.2f} {r.profit_exp[t]:6.2f}")
        return

    if args.calibrate:
        print(f"regime {args.regime}; observed (world medians, months 24-48, quarterly): pair q-amp 26,"
              " q-flips 2.5 per 8 quarters, both markets ~50 %; import-only 18; no market 8.7")
        for name in ("nomarket", "importonly", "pair"):
            print_row(f"{name}", evaluate(ARCHETYPES[name], scs["base"], list(range(1, 201)), ov))
        return

    if args.sweep or args.png:
        names = args.scenario.split(",") if args.scenario else list(scs)
        archs = (args.archetype or "surplus,deficit,pair").split(",")
        prices = [float(p) for p in args.prices.split(",")] if args.prices else [None]
        if args.sweep:
            for p in prices:
                o = merge(ov, {"world": {"p_mean": p}}) if p is not None else ov
                print(f"=== regime {args.regime}, victuals price {o.get('world', {}).get('p_mean', World.p_mean)},"
                      f" {len(seeds)} seeds, {int(o.get('world', {}).get('months', World.months))} months")
                if not args.verbose:
                    print(TABLE_HEAD)
                for n in names:
                    if args.verbose:
                        print(f"--- {n}: {scs[n].note}")
                    for a in archs:
                        agg = evaluate(ARCHETYPES[a], scs[n], seeds, o)
                        if args.verbose:
                            print_row(f"  {a}", agg)
                        else:
                            print_table_row(n, a, agg)
        if args.png:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(len(archs), 1, figsize=(11, 3.0 * len(archs)), sharex=True)
            for ax, a in zip(axes, archs):
                for sc_name, color in (("base", "#d62728"), (args.best, "#1f77b4")):
                    for i, s in enumerate(seeds[:3]):
                        r = simulate(ARCHETYPES[a], scs[sc_name], s, ov)
                        ax.plot(r.months, color=color, lw=1.1, alpha=0.85 - 0.25 * i,
                                label=f"{sc_name}: {scs[sc_name].note}" if i == 0 else None)
                ax.set_title(f"{a} ({args.regime}): stored months, 3 harvest seeds", fontsize=9, loc="left")
                ax.set_ylabel("months")
                ax.set_ylim(0, 37)
                ax.grid(alpha=0.3)
                ax.legend(fontsize=7, loc="upper right")
            axes[-1].set_xlabel("month")
            fig.tight_layout()
            fig.savefig(args.png, dpi=110)
            print(f"chart written to {args.png}")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
