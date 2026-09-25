"""Province food simulator: victuals import/export markets, farm method switch and the harvest cycle.

Engine rules (verified in game 2026-09-24/25), one province, monthly steps:

* storage is an integrator: food += production x (1 + farmed_share x h) - consumption
  + 90 x staffed import levels - 90 x staffed export levels + 0.96 x M x farm levels on Provision;
  stored months = food / consumption, stored years = min(2, months / 12); storage clamps at 0 and a cap.
* market staffing ramps +/- RAMP per month toward the sign of the building's current profit per staffed
  level (never rests, 0..1). Levels are fixed per scenario (the AI only adds levels).
* farms are always staffed; each level runs Provision when provision_margin > sell_income, else Sell.
* each September the region's harvest h is re-rolled from {-a (20 %), 0 (60 %), +a (20 %)} and held;
  the crop price follows crop_base / (1 + h) clipped 0.6..1.8. The victuals price is the market's:
  a mean-reverting walk around p_mean (spread p_sd, reversion p_revert), pushed by a market-wide harvest
  correlated with the local one.

Observed-style metrics sample a save every 36 months (9 saves = 24 years); runs are 300 months.

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
  uv run python tools/province_food_sim.py --depop calibrate --seeds 16      (population loop, see PopRules)
  uv run python tools/province_food_sim.py --depop levers --case pre_collapse,pre_control --pop-years 8,24
  (--calib plague reproduces the first fit on the plague-culled 1361/1385 endpoints)
"""
from __future__ import annotations

import argparse
import math
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
    # None: the farms sell the export's good (its constant, slope and droop). Set sales_c/sales_k for a good of
    # their own; shared_droop says whether the export's per-level droop still reaches the farms' good.
    sales_c: float | None = None
    sales_k: float | None = None
    shared_droop: bool = True

    def provision_margin(self, crop_price: float) -> float:
        return self.M * (self.provision_food * self.local_food_price - self.crop_in * crop_price)

    def sell_income(self, years: float, export_staffed: float, sales: ExportSpec) -> float:
        # the sales output modifier is location-wide: the export's droop also hits the farms' sell leg
        c = sales.sales_c if self.sales_c is None else self.sales_c
        k = sales.sales_k if self.sales_k is None else self.sales_k
        m = 1.0 + c + k * years + (sales.droop * export_staffed if self.shared_droop else 0.0)
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
    p_sd: float = 0.19            # stationary spread of the victuals price walk (gold)
    p_revert: float = 0.15        # monthly mean reversion of the victuals price (0.02 = ~4-year memory)
    p_beta: float = 0.3           # victuals price response to the market harvest: p* = p_mean / (1 + beta h_m)
                                  # (0.3: a -0.8 market harvest lifts 2.7 to 3.5, the observed p90)
    p_corr: float = 0.5           # chance the market harvest equals the local roll (else an independent roll)
    harvest: bool = True
    months: int = 300


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
        w = replace(w, harvest=False, p_sd=0.0)

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
    p_sigma = w.p_sd * (1.0 - (1.0 - w.p_revert) ** 2) ** 0.5   # monthly step for that stationary spread
    out = Run([], [], [], [], [], [], [], [], [], [], [])
    for t in range(int(w.months)):
        if w.harvest and t % 12 == SEPTEMBER:
            h = roll(rng, w.harvest_amp)
            h_m = h if rng.random() < w.p_corr else roll(rng, w.harvest_amp)
        if w.harvest or w.p_sd:
            target = w.p_mean / (1.0 + w.p_beta * h_m)
            p += w.p_revert * (target - p) + rng.gauss(0.0, p_sigma)
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


OBS_START, OBS_EVERY, OBS_SAMPLES = 11, 36, 9   # a save every 36 months, 9 saves = 24 years


def cycle_period(xs: list[float], max_lag: int = 150) -> float | None:
    """Lag of the first autocorrelation peak (> 0.1) after the autocorrelation turns negative."""
    n = len(xs)
    mean = statistics.fmean(xs)
    d = [x - mean for x in xs]
    var = sum(v * v for v in d)
    if var < 1e-9:
        return None
    acf = [sum(d[i] * d[i + k] for i in range(n - k)) / var for k in range(min(max_lag, n // 2) + 1)]
    k = 1
    while k < len(acf) and acf[k] > 0:
        k += 1
    for j in range(k + 1, len(acf) - 1):
        if acf[j] >= acf[j - 1] and acf[j] >= acf[j + 1] and acf[j] > 0.1:
            return float(j)
    return None


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
    period: float | None
    q_amp: float       # observed-style: max-min of 9 saves 36 months apart
    q_flips: float     # observed-style: direction flips in those 9 saves (8 intervals)
    q_step: float      # mean |change| between consecutive saves (per 36-month interval)
    win36: float       # mean max-min within each 36-month window (the swing inside one interval)


def metrics(r: Run) -> Metrics:
    tail = r.months[24:]
    years = len(tail) / 12.0
    q = r.months[OBS_START::OBS_EVERY][:OBS_SAMPLES]
    wins = [r.months[i:i + OBS_EVERY] for i in range(24, len(r.months) - OBS_EVERY + 1, OBS_EVERY)]
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
        period=cycle_period(tail),
        q_amp=max(q) - min(q),
        q_flips=quarterly_flips(q),
        q_step=statistics.fmean(abs(b - a) for a, b in zip(q, q[1:])),
        win36=statistics.fmean(max(w) - min(w) for w in wins),
    )


def aggregate(ms: list[Metrics]) -> dict:
    med = lambda k: statistics.median(getattr(m, k) for m in ms)  # noqa: E731
    settled = [m.settle for m in ms if m.settle is not None]
    periods = [m.period for m in ms if m.period is not None]
    return dict(
        amp=med("amp"), flips_yr=med("flips_yr"), money=med("money"), final=med("final"),
        starving=statistics.fmean(m.starving for m in ms), s_imp=med("s_imp"), s_exp=med("s_exp"),
        churn=med("churn"),
        farms_prov=statistics.fmean(m.farms_prov for m in ms),
        settle=(statistics.median(settled) if len(settled) * 2 > len(ms) else None),
        settled_share=len(settled) / len(ms),
        q_amp=med("q_amp"), q_flips=statistics.fmean(m.q_flips for m in ms), q_step=med("q_step"),
        win36=med("win36"),
        period=(statistics.median(periods) if len(periods) * 2 > len(ms) else None),
    )


def evaluate(arch: Archetype, sc: Scenario, seeds: list[int], overrides: dict | None = None) -> dict:
    agg = aggregate([metrics(simulate(arch, sc, s, overrides)) for s in seeds])
    det = metrics(simulate(arch, sc, None, overrides))  # no harvest, fixed price
    agg["settle_nh"] = det.settle
    agg["amp_nh"] = det.amp
    agg["final_nh"] = det.final
    agg["period_nh"] = det.period
    return agg



# ---------------------------------------------------------------------------------------------
# regimes. Observed saves are 36 months apart (9 saves = 24 years): pair swing 26 months max-min,
# 2.5 direction flips in 8 intervals, both markets ~half staffed; import only 18; no market 8.7.
# ---------------------------------------------------------------------------------------------
REGIMES = {
    # stated numbers: 90 food per level = 9 % of consumption, ramp 0.05, harvest +/-0.5 on 80 % of production,
    # victuals price a short-memory walk (spread 0.19 gold, 15 %/month reversion)
    "stated": {},
    # calibrated 2026-09-25 on the 36-month saves: 90 food per level = 22.5 % of consumption (400/month),
    # ramp 0.05, harvest +/-0.35 on 80 % of production, victuals price a slow walk with the observed
    # cross-market spread (sd 0.66 gold ~ p10 1.8 / p90 3.5) and 1 %/month reversion (~8-year memory)
    "calibrated": {"arch": {"consumption": 400.0},
                   "world": {"harvest_amp": 0.35, "p_sd": 0.66, "p_revert": 0.01}},
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
    return lever_scenarios() + band_scenarios() + [recommended(), live(), merged()]


# the farms' own Surplus Sales leg in game: 0.005 x (1 - 1 + 8y)
FARM_OWN_SALES = dict(sales_c=-1.0, sales_k=8.0)


def live() -> Scenario:
    """REC as shipped (e724de95): the export on its own export_sales good, the farms on province_food_sales."""
    rec = recommended()
    return Scenario("LIVE", "REC with the farms on their own good (-1 constant, no export droop)",
                    imp=rec.imp, exp=rec.exp, farm=dict(FARM_OWN_SALES, shared_droop=False))


def merged() -> Scenario:
    """2026-09-25: the export pays on the farms' province_food_sales; its fixed cost takes the old -8 constant gap.

    Above 12 months 1.425 x (8y - 0.3 N) - 11.4 equals 1.425 x (8y - 8 - 0.3 N): the same export. Below it the
    export only loses more (staffing follows the sign of profit), and its droop now also reaches the farms.
    """
    rec = recommended()
    gap = rec.exp["sales_amount"] * (rec.exp["sales_c"] - FARM_OWN_SALES["sales_c"])  # 1.425 x -8 = -11.4
    exp = dict(rec.exp, sales_c=FARM_OWN_SALES["sales_c"], offset_cost=round(rec.exp["offset_cost"] - gap, 3))
    return Scenario("MERGED", f"LIVE with the export on province_food_sales, offset {exp['offset_cost']}",
                    imp=rec.imp, exp=exp, farm=dict(FARM_OWN_SALES, shared_droop=True))


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
# population loop (depopulation study 2026-09-25, fresh game saves 1337.4 / 1361.3 / 1385.2)
#
# Measured from the saves (province pools = province x owner):
# * base_food_consumption = sum of pops x rate per 1k (peasants 1, laborers 1.5, burghers/clergy 10, nobles 25,
#   soldiers 4, slaves 0.5, tribesmen 0), R2 1.00.
# * production (= cached_structural_food_change + base_food_consumption) = 1.44..1.57 x unemployed
#   (peasants + laborers + slaves) + building food (farms 1.5 flat + 0.96 Provision, Serve ~27.6, import 90 per
#   staffed level), R2 0.95..0.97; RGO slots and employed pops add nothing. So subsistence is the define
#   SUBSISTENCE_AGRICULTURE 1.5 per 1k unemployed worker; pops in jobs (RGO, buildings) eat but do not farm.
# * growth is a yearly rate applied /12 per month: not starving -0.004 (rank) + 0.0075-0.0084 x stored years
#   (fit over 2,700 pools, R2 0.6-0.8); starving pools lose 0.043/yr (Starvation = -0.04 province_starving
#   -0.004 rank), plus some out-migration.
# * collapse provinces keep their jobs while the subsistence farmers die: 1337->1361 pop x0.41, unemployed
#   x0.23, employed x0.59 -> the employment elasticity below.
#
# Recalibrated 2026-09-25 on PRE-PLAGUE saves of the same game (1337.4 / 1341.3 / 1345.3; the Black Death spawns
# after 1346.1, so the 1361/1385 endpoints above are plague-culled and must not be used for calibration):
# * not starving: yearly growth -0.0048 + 0.0086 x stored years (+0.002 x prosperity), 2,500 pools, R2 0.52;
#   starving: Starvation -0.043/yr flat (any deficit above ~8 %), net migration -0.012/yr.
# * subsistence 1.44..1.45 per 1k unemployed worker (R2 0.94..0.97).
# * pools that lost >= 25 % by 1345 (food pools): jobs fall with elasticity ~0.44 to pop, consumption per head
#   x0.875 at pop x0.67 (upper classes flee/starve first: nobles -65 %, burghers -60 %, laborers -51 %,
#   peasants -21 %) -> free_land ~0.4.
# * nobles leave starving pools: 3 % of loser pools had no noble at 1337, 30 % at 1341, 40 % at 1345 (control
#   pools 0 / 1 / 2 %). A Victualler (pop_type nobles, 1 pop per level) in such a pool cannot staff:
#   noble_hazard = chance per starving year that the pool loses its last noble (fit to 30 % after 4 years).
# ---------------------------------------------------------------------------------------------
HARVEST_CONS = ((0.30, 0.05), (0.20, 0.10), (0.11, 0.15), (0.0, 0.40), (-0.11, 0.15), (-0.20, 0.10), (-0.30, 0.05))
# pp_harvest_<region>_<quality>: local_peasants_food_consumption +0.30 (abysmal) .. -0.30 (bountiful), rolled
# yearly per region (20 % bad / 60 % neutral / 20 % good shock with memory); the weights here are an iid stand-in.


@dataclass
class PopCase:
    name: str
    pop0: float          # k pops at 1337 (tribesmen included; they eat nothing)
    cons_pc: float       # base_food_consumption per 1k pop per month
    work_share: float    # peasants + laborers + slaves share of pop
    emp0: float          # workers in jobs (k): peasants + laborers + slaves minus their unemployed
    sub_yield: float     # food per 1k unemployed worker per month ((production - building food) / unemployed)
    fixed_food: float    # building food at 1337 (farms, Provision, Serve, staffed imports)
    months0: float       # stored months at 1337
    cap_months: float    # max_food_value / consumption
    vprice: float        # market victuals price at 1337
    victuals_supply: float = 15.0   # market victuals supply per month (collapse median 14.8)
    pop1361: float | None = None
    pop1385: float | None = None
    peasant_share: float = 0.6      # share of consumption that the harvest shock moves
    builds: tuple = ()              # AI builds seen in the later saves: (month, "import"|"cookshop", levels, staffed share)
    obs: tuple = ()                 # observed endpoints ((years, pop k), ...); empty -> (24, pop1361), (48, pop1385)

    def endpoints(self) -> tuple:
        return self.obs or ((24, self.pop1361), (48, self.pop1385))


# per-province inputs from ~/scratch/switch/depop_b_inputs.py (save nb = 1337.4.1, final build)
PROVINCE_CASES = {
    # collapse set medians (176 food provinces that lost >= 50 % by 1361)
    "collapse": PopCase("collapse", 42.11, 1.329, 0.925, 17.675, 1.11, 4.23, 3.675, 41.75, 2.48, 14.8,
                        42.11 * 0.409, 42.11 * 0.406),
    # matched control medians (pop within +-10 % by 1361, same starting size)
    "control": PopCase("control", 46.43, 1.264, 0.937, 20.555, 1.819, 4.71, 3.69, 46.65, 2.33, 18.3,
                       46.43 * 0.982, 46.43 * 1.051),
    "penza": PopCase("penza", 70.07, 0.9323, 0.987, 18.91, 0.763, 1.5, 7.01, 70.1, 2.25, 2.0, 24.98, 17.34),
    # 1 Victualler by 1361 (60 % staffed then, 25 % in 1385)
    "finland": PopCase("finland", 30.6, 2.0848, 0.889, 19.0, 0.999, 9.0, 2.98, 29.8, 1.87, 24.0, 10.72, 10.98,
                       builds=((216, "import", 1, 0.4),)),
    # 2 Victualler levels by 1361 (20 % staffed, 60 % in 1385)
    "kremenets": PopCase("kremenets", 47.95, 1.2297, 0.981, 24.6, 1.824, 11.88, 4.75, 47.5, 2.21, 18.0, 49.61, 53.54,
                         builds=((144, "import", 2, 0.2), (288, "import", 0, 0.6))),
    # cookshop on Serve: 2 levels by 1361, 4 by 1385 (build dates unknown; midpoints assumed)
    "pocutia": PopCase("pocutia", 26.08, 1.323, 0.976, 18.63, 2.443, 4.5, 7.27, 72.7, 2.18, 18.0, 23.59, 27.4,
                       builds=((72, "cookshop", 2, 1.0), (432, "cookshop", 2, 1.0))),
}
CALIBRATION_CASES = ("penza", "finland", "kremenets", "pocutia")   # plague-culled endpoints: do not calibrate on


def _pre(name, pop0, cons_pc, work_share, emp0, sub_yield, fixed_food, months0, cap_months, vprice, supply,
         pop41, pop45, peasant_share, provision=0.0, serve=0.0) -> PopCase:
    # provision / serve: farm levels switching to Provision and standing cookeries switching to Serve by 1341
    # (seen in the 1341 save; month 6 assumed)
    builds = tuple(b for b in ((6, "provision", provision, 1.0), (6, "serve", serve, 1.0)) if b[2])
    return PopCase(name, pop0, cons_pc, work_share, emp0, sub_yield, fixed_food, months0, cap_months, vprice, supply,
                   peasant_share=peasant_share, builds=builds, obs=((4, pop41), (8, pop45)))


# pre-plague pool inputs from ~/scratch/switch/pre_inputs.py (pools = province x owner, same owner and locations
# 1337.4 / 1341.3 / 1345.3; endpoints at 4 and 8 years)
PRE_CASES = {
    # medians of the 223 food pools that lost >= 25 % by 1345 (pop x0.816 by 1341, x0.672 by 1345)
    "pre_collapse": _pre("pre_collapse", 17.64, 1.306, 0.941, 0.464 * 17.64, 1.065, 0.0, 4.62, 52.1, 2.36, 17.1,
                         17.64 * 0.816, 17.64 * 0.672, 0.24, provision=1.0, serve=0.04),
    # medians of the matched controls (pop within +-5 % by 1345)
    "pre_control": _pre("pre_control", 17.64, 1.285, 0.98, 0.548 * 17.64, 1.993, 3.0, 4.36, 47.1, 2.24, 39.7,
                        17.64 * 1.002, 17.64 * 1.004, 0.59, provision=1.8, serve=0.13),
    # collapsing pools (no Victualler / Serve built by 1345)
    "saratov": _pre("saratov", 39.35, 0.9451, 0.986, 10.49, 0.287, 1.5, 6.36, 63.6, 2.25, 1.7, 32.37, 26.15, 0.153, provision=1),
    "hanyang": _pre("hanyang", 52.53, 2.3857, 0.865, 23.05, 1.237, 11.88, 2.21, 22.1, 2.78, 87.8, 42.04, 29.82, 0.283, provision=2),
    # stable pools with a structural deficit at 1337
    "wielun": _pre("wielun", 37.65, 1.2764, 0.971, 24.65, 1.026, 21.0, 4.75, 47.5, 2.18, 21.3, 37.59, 39.17, 0.638, serve=1),
    "lutsk": _pre("lutsk", 54.86, 1.2932, 0.979, 39.11, 0.643, 28.38, 5.72, 57.2, 2.21, 28.9, 55.44, 56.86, 0.574, provision=6, serve=1),
}
PROVINCE_CASES.update(PRE_CASES)
PRE_CALIBRATION_CASES = ("saratov", "hanyang", "wielun", "lutsk")


@dataclass
class PopRules:
    subsistence: float = 1.5          # NLocation SUBSISTENCE_AGRICULTURE; sub_yield scales with subsistence / 1.5
    growth_base: float = -0.0048      # yearly (location rank term); pre-plague fit -0.0048..-0.0049
    growth_per_year: float = 0.0086   # positive_province_food_growth per stored year (cap 2 years); pre-plague fit
    starving_growth: float = -0.04    # province_starving local_population_growth
    starving_migration: float = -0.012  # yearly net out-migration while starving (pre-plague median -0.012 / -0.008)
    noble_hazard: float = 0.09        # chance per starving year that the pool loses its last noble (pre-plague fit)
    emp_elasticity: float = 0.5       # jobs held = emp0 x (pop / pop0) ^ e   (pre-plague loser pools 0.44..0.59)
    free_land: float = 0.4            # per-capita consumption falls d x (1 - pop/pop0): upper classes flee and
                                      # starve first (pre-plague loser pools: x0.875 at pop x0.67 -> 0.38)
    yield_mult: float = 1.5           # correction on the 1337 snapshot's sub_yield (pre-plague fit 1.5: the loser
                                      # pools' food per subsistence worker rose 1.07 -> 1.68 by 1345)
    ramp: float = 0.05                # staffing change per month
    harvest: bool = True


@dataclass
class PopLever:
    name: str
    note: str
    imports: int = 0                  # Victualler levels built at build_month
    import_spec: str = "current"      # "current" = dead band numbers (REC), "old" = numbers of the fresh-game run
    nobles: bool = True               # False: no noble in the location, the import never staffs
    staff_pop: str = "nobles"         # "nobles": staffing stops once starvation drove the last noble out
                                      # (PopRules.noble_hazard); "peasants": pop_type peasants, staff always there
    cookshop: int = 0                  # cookshop levels on Serve (1k laborers each, 27.6 Province Food per level)
    farms: int = 0                    # extra farm levels on Provision (1k peasants each, 1.5 flat + 0.96 Provision)
    build_month: int = 12
    rules: dict = field(default_factory=dict)


def import_spec(kind: str) -> ImportSpec:
    if kind == "old":
        return ImportSpec()
    rec = recommended()
    return replace(ImportSpec(), **rec.imp)


@dataclass
class PopRun:
    pop: list[float]
    months: list[float]
    starving: list[bool]
    import_staff: list[float]
    import_profit: list[float]


def simulate_pop(case: PopCase, lever: PopLever, seed: int | None, rules: PopRules | None = None,
                 months: int = 576) -> PopRun:
    r = replace(rules or PopRules(), **lever.rules)
    spec = import_spec(lever.import_spec)
    rng = random.Random(seed if seed is not None else 0)
    rng_nob = random.Random(7919 * (seed if seed is not None else 0) + 1)   # own stream: levers stay paired
    has_nobles = True
    N, N0 = case.pop0, case.pop0
    C0 = case.cons_pc * N0
    food = case.months0 * C0
    cap = case.cap_months * C0
    y = case.sub_yield * r.yield_mult * r.subsistence / 1.5
    s_imp = 0.0
    s_cook = 0.0
    h = 0.0
    starving = False
    out = PopRun([], [], [], [], [])
    for t in range(months):
        if r.harvest and seed is not None and t % 12 == SEPTEMBER:
            x, acc = rng.random(), 0.0
            for v, wgt in HARVEST_CONS:
                acc += wgt
                if x < acc:
                    h = v
                    break
        built = t >= lever.build_month
        L = lever.imports if built else 0
        K = lever.cookshop if built else 0
        Fm = lever.farms if built else 0
        Lc = sum(b[2] for b in case.builds if b[1] == "import" and t >= b[0])
        cap_c = next((b[3] for b in reversed(case.builds) if b[1] == "import" and t >= b[0]), 0.0)
        Kc = sum(b[2] for b in case.builds if b[1] == "cookshop" and t >= b[0])
        K += Kc
        # method switches of buildings standing at 1337 (setup runs every farm on Sell and no cookshop on Serve;
        # by 1341 58 % of farm levels run Provision): food only, their jobs are already in emp0
        switched = sum(b[2] * (0.96 if b[1] == "provision" else 27.6) for b in case.builds
                       if b[1] in ("provision", "serve") and t >= b[0])
        jobs = case.emp0 * (N / N0) ** r.emp_elasticity + K * s_cook + Fm
        workers = case.work_share * N
        U = max(0.0, workers - min(jobs, workers))
        cons_pc = case.cons_pc * (1.0 - r.free_land * max(0.0, 1.0 - N / N0))
        cons = cons_pc * N * (1.0 + h * case.peasant_share) + 0.5 * K * s_cook
        years = min(2.0, food / max(cons, 1e-9) / 12.0)
        # Victualler: staffing ramps toward the sign of its profit per staffed level
        pi = spec.profit(years, starving, L * s_imp, case.vprice) if L else 0.0
        imported = min(FOOD_PER_LEVEL * (L * s_imp + Lc * cap_c), 30.0 * case.victuals_supply)
        prod = y * U + case.fixed_food + switched + imported + 27.6 * K * s_cook + (1.5 + 0.96) * Fm
        food = min(cap, max(0.0, food + prod - cons))
        starving = food <= 0.0
        if starving and has_nobles and seed is not None and rng_nob.random() < r.noble_hazard / 12.0:
            has_nobles = False
        staffable = lever.nobles and (lever.staff_pop == "peasants" or has_nobles)
        if L and staffable:
            s_imp = min(1.0, max(0.0, s_imp + (r.ramp if pi > 0 else -r.ramp)))
        elif L:
            s_imp = max(0.0, s_imp - r.ramp)
        if K:
            s_cook = min(1.0, s_cook + r.ramp)
        g = r.growth_base + (r.starving_growth + r.starving_migration if starving
                             else r.growth_per_year * min(2.0, food / max(cons, 1e-9) / 12.0))
        N *= 1.0 + g / 12.0
        out.pop.append(N)
        out.months.append(food / max(cons, 1e-9))
        out.starving.append(starving)
        out.import_staff.append(s_imp)
        out.import_profit.append(pi * L * s_imp)
    return out


def pop_at(run: PopRun, years: float) -> float:
    return run.pop[min(len(run.pop), int(years * 12)) - 1]


def pop_seeds(case: PopCase, lever: PopLever, seeds: list[int], rules: PopRules | None = None, months: int = 576):
    return [simulate_pop(case, lever, s, rules, months) for s in seeds]


def calibration_set(name: str) -> tuple:
    return PRE_CALIBRATION_CASES if name == "pre" else CALIBRATION_CASES


def calibrate_pop(seeds: list[int], cases: tuple = PRE_CALIBRATION_CASES) -> tuple[PopRules, list]:
    """Grid fit of emp_elasticity, free_land and yield_mult on the calibration cases (squared log error at each
    observed endpoint; pre-plague cases: 4 and 8 years, plague-era cases: 24 and 48 years)."""
    base = PopLever("asis", "as is")
    best = None
    # over 8 years the fit is flat in emp_elasticity and free_land (collapsing pools starve all along; SSE 0.0178
    # anywhere in e 0.5..2, d 0..0.8), so the pre-plague fit pins them to the values measured in the loser set
    # (jobs elasticity 0.44..0.59, consumption per head x0.875 at pop x0.67) and fits yield_mult only
    pre = cases == PRE_CALIBRATION_CASES
    for e in ((0.5,) if pre else (0.2, 0.4, 0.6, 0.8, 1.0, 1.25)):
        for d in ((0.4,) if pre else (0.0, 0.2, 0.4, 0.6)):
            for ym in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8):
                rules = PopRules(emp_elasticity=e, free_land=d, yield_mult=ym)
                err = 0.0
                for name in cases:
                    c = PROVINCE_CASES[name]
                    horizon = int(max(yy for yy, _ in c.endpoints()) * 12)
                    runs = pop_seeds(c, base, seeds, rules, horizon)
                    for yy, obs in c.endpoints():
                        err += math.log(statistics.median(pop_at(x, yy) for x in runs) / obs) ** 2
                if best is None or err < best[0]:
                    best = (err, rules)
    return best[1], best


def pop_levers() -> list[PopLever]:
    return [
        PopLever("a", "as is (buildings of 1337, no AI builds)"),
        PopLever("b1-old", "Victualler 1 level, numbers of this run", imports=1, import_spec="old"),
        PopLever("b1", "Victualler 1 level (current dead-band numbers)", imports=1),
        PopLever("b2", "Victualler 2 levels (current)", imports=2),
        PopLever("b4", "Victualler 4 levels (current)", imports=4),
        PopLever("b1-nonoble", "Victualler 1 level, no noble in the location", imports=1, nobles=False),
        PopLever("b1-peas", "Victualler 1 level, pop_type peasants (staff always available)", imports=1,
                 staff_pop="peasants"),
        PopLever("b2-peas", "Victualler 2 levels, pop_type peasants", imports=2, staff_pop="peasants"),
        # AI timing seen pre-plague: queued once storage runs low (~month 5), 365-day build that stalls on missing
        # lumber / masonry / tools (median progress 45 %; 48 of 260 queued by 1341 unfinished in 1345) -> month 30
        PopLever("b1-ai", "Victualler 1 level at month 30 (AI timing), nobles", imports=1, build_month=30),
        PopLever("b1-ai-peas", "Victualler 1 level at month 30, pop_type peasants", imports=1, build_month=30,
                 staff_pop="peasants"),
        PopLever("c", "cookshop 1 level on Serve", cookshop=1),
        PopLever("d", "+2 farm levels on Provision", farms=2),
        PopLever("e2.0", "subsistence define 1.5 -> 2.0", rules=dict(subsistence=2.0)),
        PopLever("e2.5", "subsistence define 1.5 -> 2.5", rules=dict(subsistence=2.5)),
        PopLever("f", "starving growth -0.04 -> -0.02", rules=dict(starving_growth=-0.02)),
    ]


def run_depop(mode: str, seeds: list[int], case_names: list[str], fixed: str | None = None,
              calib: str = "pre", years: tuple = (12, 24, 48)) -> None:
    cases = calibration_set(calib)

    def fitted() -> PopRules:
        if fixed:
            e, d, ym = (float(x) for x in fixed.split(","))
            return PopRules(emp_elasticity=e, free_land=d, yield_mult=ym)
        return calibrate_pop(seeds, cases)[0]

    if mode == "calibrate":
        rules, best = calibrate_pop(seeds, cases)
        print(f"fit on {calib} cases {cases}: emp_elasticity {rules.emp_elasticity}, free_land {rules.free_land},"
              f" yield_mult {rules.yield_mult} (sum of squared log errors {best[0]:.3f}, {len(seeds)} harvest seeds)")
        print("case           pop 1337   endpoints: years obs / sim ...                    R (subsistence capacity)")
        extra = ["pre_collapse", "pre_control"] if calib == "pre" else ["collapse", "control"]
        for name in list(cases) + extra:
            c = PROVINCE_CASES[name]
            horizon = int(max(yy for yy, _ in c.endpoints()) * 12)
            runs = pop_seeds(c, PopLever("a", "as is"), seeds, rules, horizon)
            cells = "   ".join(f"{yy:>2}y {obs:6.1f} / {statistics.median(pop_at(x, yy) for x in runs):6.1f}"
                               for yy, obs in c.endpoints())
            R = (c.sub_yield * c.work_share * c.pop0 + c.fixed_food) / (c.cons_pc * c.pop0)
            print(f"{name:13s} {c.pop0:8.1f}   {cells}      {R:4.2f}")
        return
    rules = PopRules()
    if mode.startswith("levers"):
        rules = fitted()
        horizon = int(max(years) * 12)
        print(f"rules: emp_elasticity {rules.emp_elasticity}, free_land {rules.free_land},"
              f" yield_mult {rules.yield_mult}, noble_hazard {rules.noble_hazard}; {len(seeds)} harvest seeds, medians")
        for name in case_names:
            c = PROVINCE_CASES[name]
            print(f"=== {name}: pop {c.pop0:.1f}k, consumption {c.cons_pc * c.pop0:.1f}/month,"
                  f" balance {((c.sub_yield * (c.work_share * c.pop0 - c.emp0) + c.fixed_food) / (c.cons_pc * c.pop0) - 1):+.2f},"
                  f" storage {c.months0:.1f} months, victuals {c.vprice:.2f}")
            print("lever      " + "".join(f"  pop {yy:>2}y" for yy in years)
                  + "  (x start)  starving share  import staffed  import profit/mo   note")
            for lv in pop_levers():
                runs = pop_seeds(c, lv, seeds, rules, horizon)
                ps = [statistics.median(pop_at(x, yy) for x in runs) for yy in years]
                st = statistics.fmean(sum(x.starving) / len(x.starving) for x in runs)
                si = statistics.fmean(statistics.fmean(x.import_staff[lv.build_month:]) for x in runs)
                pr = statistics.fmean(statistics.fmean(x.import_profit[lv.build_month:]) for x in runs)
                print(f"{lv.name:10s} " + "".join(f"  {p:8.1f}" for p in ps) + f"   (x{ps[-1] / c.pop0:4.2f})"
                      f"      {st:5.0%}          {si:4.0%}          {pr:+6.2f}        {lv.note}")
        return
    if mode == "trace":
        rules = fitted()
        c = PROVINCE_CASES[case_names[0]]
        for lv in pop_levers():
            if lv.name in ("a", "b1"):
                r = simulate_pop(c, lv, seeds[0], rules)
                print(f"--- {c.name} {lv.name}: year, pop, stored months, starving months in year, import staffed")
                for yy in range(0, 48, 3):
                    sl = slice(yy * 12, yy * 12 + 12)
                    print(f"  {yy:3d} {r.pop[yy * 12]:7.2f} {r.months[yy * 12]:6.1f} {sum(r.starving[sl]):3d}"
                          f" {r.import_staff[yy * 12]:4.2f}")


# ---------------------------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------------------------
def fmt_settle(v) -> str:
    return "never" if v is None else f"{v:.0f}"


def fmt_period(v) -> str:
    return "none" if v is None else f"{v:.0f}"


def print_row(label: str, a: dict) -> None:
    print(f"{label:34s} amp {a['amp']:5.1f}  flips/yr {a['flips_yr']:4.2f}  settle {fmt_settle(a['settle']):>4s}"
          f" ({a['settled_share']:4.0%})  nh {fmt_settle(a['settle_nh']):>4s}/{a['amp_nh']:4.1f}"
          f"  |profit| {a['money']:5.1f}  final {a['final']:5.1f}  starv {a['starving']:4.0%}"
          f"  staff i {a['s_imp']:4.0%} e {a['s_exp']:4.0%}  prov {a['farms_prov']:4.0%}"
          f"  | saves every 36 months: amp {a['q_amp']:5.1f} flips {a['q_flips']:3.1f} step {a['q_step']:4.1f}"
          f"  | swing within 36 months {a['win36']:4.1f}  period {fmt_period(a['period'])}"
          f" (no harvest {fmt_period(a['period_nh'])})")


TABLE_HEAD = ("scenario  archetype  |  amp  flips/yr  period (no-harv)  settle(seeds)  settle/amp no-harvest"
              "  |  |profit|/mo  final  starving  staff i/e  churn food/mo  | 36-mo saves: amp  flips")


def print_table_row(sc: str, arch: str, a: dict) -> None:
    print(f"{sc:8s}  {arch:9s}  | {a['amp']:5.1f}  {a['flips_yr']:6.2f}   {fmt_period(a['period']):>5s} "
          f"({fmt_period(a['period_nh']):>4s})    {fmt_settle(a['settle']):>5s} ({a['settled_share']:4.0%})"
          f"   {fmt_settle(a['settle_nh']):>5s} / {a['amp_nh']:4.1f}        | {a['money']:7.2f}"
          f"   {a['final']:5.1f}  {a['starving']:5.0%}    {a['s_imp']:3.0%}/{a['s_exp']:3.0%}  {a['churn']:7.1f}"
          f"        | {a['q_amp']:5.1f}  {a['q_flips']:4.1f}")


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
    ap.add_argument("--depop", choices=("calibrate", "levers", "trace"),
                    help="population loop: fit on saved provinces, lever table, or a trace")
    ap.add_argument("--case", default="collapse", help="comma list of PROVINCE_CASES for --depop levers/trace")
    ap.add_argument("--pop-rules", help="skip the fit: emp_elasticity,free_land,yield_mult (e.g. 0.6,0.4,1.0)")
    ap.add_argument("--calib", default="pre", choices=("pre", "plague"),
                    help="calibration cases: pre-plague pools (4/8-year endpoints) or the plague-era ones (24/48)")
    ap.add_argument("--pop-years", default="12,24,48", help="years reported by --depop levers (e.g. 8,24)")
    args = ap.parse_args()
    if args.depop:
        run_depop(args.depop, list(range(1, args.seeds + 1)), args.case.split(","), args.pop_rules, args.calib,
                  tuple(int(x) for x in args.pop_years.split(",")))
        return
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
        print(f"regime {args.regime}; observed (world medians, 9 saves 36 months apart): pair amp 26,"
              " 2.5 flips in 8 intervals, both markets ~50 %; import-only 18; no market 8.7")
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
                ax.set_xlim(0, len(r.months))
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
