"""Province store simulator for the store lever (2026-10-02): Low Stores / Full Stores on Province Food output.

One province pool, monthly steps, the pieces the mod controls:

* store += food production - consumption, clamped 0..capacity; stored months m = store / consumption (lever capped at 24);
* the store modifiers are re-applied monthly, so buildings see last month's store (``lag``);
* Low Stores is applied at size (12 - m) / 12 below 12 months, Full Stores at size (m - 12) / 12 above; a goods output
  is base x max(0, 1 + production efficiency + the good's local output modifier);
* a building's staffing moves +-0.15 a month toward the sign of its profit per level (0..1);
* farms always run Provisioning (their crop -> Province Food); their staple output follows the store;
* Taverns make Province Food, so their revenue and food follow the store; Cookshops (since 2026-10-03) sell their
  meals for offset at a thin fixed margin and feed the province with their flat local_monthly_food, so they stay
  staffed at any store; the Grange takes 24 food per staffed level, packs victuals and earns Surplus Sales, which a
  staffed Tavern in the same location cuts;
* a starving province makes no victuals and pays double for Province Food.

Prices at their floors: Province Food 0.10, dummy goods and labour 1 gold; victuals and staples are scenario inputs.
The provinces are real game-start pools (``artifacts/data/worldbuilder``: food_sim/input.csv, start_placement.csv; land
quality from the World Builder handover), plus later-game variants built from them. The numbers come from
``store_lever.load_design`` (constructor.toml ``[stored_food]``, the accepted Tavern and Grange blueprints, the mod's
``province_starving``), so the simulator follows the mod.

Run (after a build):
  uv run python tools/province_store_sim.py                    store range per province: steady, lagged, harvest, all
  uv run python tools/province_store_sim.py --scenarios        rest points by victuals price, staple price, efficiency
  uv run python tools/province_store_sim.py --trace "Lincolnshire later" --months 240 [--eff 0.3] [--victuals 3.5] [--harvest]
"""
from __future__ import annotations

import argparse
import csv
import random
import re
from dataclasses import dataclass, replace
from pathlib import Path

from prosper_or_perish_constructor.store_lever import CAP_MONTHS, FOOD_PRICE, Design, load_design

ROOT = Path(__file__).resolve().parents[1]
RAMP = 0.15
HARVEST = ((0.30, 0.05), (0.20, 0.10), (0.11, 0.15), (0.0, 0.40), (-0.11, 0.15), (-0.20, 0.10), (-0.30, 0.05))
# wheat farm, tier 0, per level: crop with the ox ard / without cultivation, and their fixed costs at base prices
CROP_PLOUGH, CROP_PLAIN = 0.22, 0.07
COST_PLOUGH, COST_PLAIN = 0.1415, 0.022
PROVISION_FOOD, PROVISION_CROP = 0.96, 0.08


def cookshop_flat(root: Path = ROOT) -> float:
    """The Cookshop's flat local_monthly_food per staffed level, from its accepted blueprint."""
    text = (root / "blueprints/accepted/buildings/cookshop.yml").read_text(encoding="utf-8")
    return float(re.search(r"local_monthly_food = ([0-9.]+)", text).group(1))


COOK_FLAT = cookshop_flat()


# ---------------------------------------------------------------------------------------------
# provinces
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Prov:
    name: str
    cons: float
    sub: float            # subsistence food
    flat: float           # flat building food (farms' local_monthly_food)
    provision: float      # farms' Provisioning Province Food at modifier 0
    farms: float
    land: float           # the staple's local output modifier at the farms
    cook: float           # cookshop levels
    serve_per: float      # Province Food per cookshop level (0 since 2026-10-03)
    tav: float
    grange: float
    cap: float            # store capacity (food)
    peasant_share: float = 0.8
    yield_: float = 1.5
    cook_flat: float = COOK_FLAT   # flat food per cookshop level


def _f(row: dict, key: str) -> float:
    return float(row.get(key) or 0)


def load_pools(root: Path = ROOT) -> dict[tuple[str, str], Prov]:
    data = root / "artifacts/data/worldbuilder"
    handover = root.parent / "EU5WorldBuilder/artifacts/handover/latest"
    rows: dict[str, dict[str, float]] = {}
    with (handover / "attribute_rows.csv").open(encoding="utf-8-sig") as handle:
        for r in csv.DictReader(handle):
            rows.setdefault(r["attribute"], {})[r["value"]] = float(r["output_wheat"]) if r["output_wheat"] else 0.0
    land: dict[str, float] = {}
    with (handover / "location_attributes.csv").open(encoding="utf-8-sig") as handle:
        for r in csv.DictReader(handle):
            land[r["location_tag"]] = rows["reference"]["intercept"] + sum(
                rows[a].get(r[a], 0.0) for a in ("climate", "topography", "vegetation", "soil_type", "fertility"))
    crops = ("wheat", "rice", "millet", "maize", "legume", "potato", "olive", "cattle")
    agg: dict[tuple[str, str], dict[str, float]] = {}
    with (data / "start_placement.csv").open(encoding="utf-8-sig") as handle:
        for r in csv.DictReader(handle):
            a = agg.setdefault((r["owner"], r["province"]), {"farms": 0.0, "w": 0.0, "n": 0.0})
            levels = sum(_f(r, f"{c}_farm_levels") for c in crops)
            a["farms"] += levels
            a["w"] += levels * land.get(r["location_tag"], 0.0)
            a["n"] += levels
    pools: dict[tuple[str, str], Prov] = {}
    with (data / "food_sim/input.csv").open(encoding="utf-8-sig") as handle:
        for r in csv.DictReader(handle):
            if r["owner"] == "---" or _f(r, "demand0") <= 0:
                continue
            key = (r["owner"], r["province"])
            a = agg.get(key, {"farms": 0.0, "w": 0.0, "n": 0.0})
            cook = _f(r, "cookshop_levels")
            pools[key] = Prov(
                name=r["province"], cons=_f(r, "demand0"),
                sub=_f(r, "yield_") * max(0.0, _f(r, "workers0") - _f(r, "jobs0")),
                flat=max(0.0, _f(r, "flat_food") - cook * COOK_FLAT),   # the Cookshops' flat food is counted per level
                provision=_f(r, "provision_food"), farms=a["farms"], land=a["w"] / a["n"] if a["n"] else 0.0,
                cook=cook, serve_per=_f(r, "serve_food") / cook if cook else 0.0, tav=_f(r, "taverns"),
                grange=_f(r, "yards"), cap=_f(r, "capacity"), peasant_share=_f(r, "peasant_share"), yield_=_f(r, "yield_"))
    return pools


def later(p: Prov, name: str, more_farms: float = 0.0, **kw) -> Prov:
    """A later-game state: jobless peasants move into ``more_farms`` farm levels, other buildings as given."""
    return replace(p, name=name, sub=max(0.0, p.sub - p.yield_ * more_farms), flat=p.flat + 1.5 * more_farms,
                   provision=p.provision + PROVISION_FOOD * more_farms, farms=p.farms + more_farms, **kw)


def provinces(pools: dict[tuple[str, str], Prov]) -> list[Prov]:
    def start(owner: str, province: str, name: str) -> Prov:
        return replace(pools[(owner, province)], name=name)

    gat = start("FRA", "gatinais_province", "Gatinais start: 18 farms, 1 cookshop, 1 grange")
    lin = start("ENG", "lincolnshire_province", "Lincolnshire start: 30 farms, 2 taverns")
    fez = start("MOR", "fez_province", "Fez start: 3 cookshops, 1 tavern")
    u = start("TIB", "u_province", "U (Tibet) start: 1 cookshop, 4 taverns")
    return [
        gat, lin,
        start("CHI", "wuchang_province", "Wuchang start: 30 farms (rice), 3 cookshops"),
        start("CHI", "yongzhou_province", "Yongzhou start: 23 farms, 3 cookshops, 3 granges"),
        fez, u,
        start("MIH", "garmsir_province", "Garmsir (Persia) start: 5 farms, bad land"),
        later(gat, "Gatinais later: 58 farms, 3 cookshops, 2 granges", 40, cook=3, grange=2),
        later(gat, "Gatinais later, kitchens at cap: 58 farms, 11 cookshops, 2 granges", 40, cook=11, grange=2),
        later(lin, "Lincolnshire later: 90 farms, 2 cookshops, 8 taverns, 2 granges", 60, cook=2, tav=8, grange=2),
        later(lin, "Lincolnshire later, kitchens at cap: 90 farms, 18 cookshops, 8 taverns, 2 granges", 60, cook=18, tav=8,
              grange=2),
        later(lin, "Lincolnshire, no cookshop: 60 farms, 8 taverns, 4 granges", 30, cook=0, tav=8, grange=4),
        replace(fez, name="Fez later: 6 cookshops, 10 taverns", cook=6, tav=10, sub=fez.sub * 0.5),
        replace(u, name="U later: 2 cookshops, 11 taverns", cook=2, tav=11),
        replace(gat, name="Thin surplus: 18 farms, 4 granges, no cookshop", cook=0, grange=4, sub=gat.sub - 25),
    ]


# ---------------------------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------------------------
def harvest_roll(rng: random.Random) -> float:
    x, acc = rng.random(), 0.0
    for severity, share in HARVEST:
        acc += share
        if x < acc:
            return severity
    return 0.0


def farm_profit(d: Design, months: float, land: float, staple: float = 1.0, eff: float = 0.0,
                starving: bool = False) -> tuple[float, float, float]:
    """(profit, food, crop) of a wheat farm level: the better of plough and no cultivation, plus Provisioning."""
    crop_mod = d.staple_modifier(months, land, eff)
    plough, plain = CROP_PLOUGH * crop_mod * staple - COST_PLOUGH, CROP_PLAIN * crop_mod * staple - COST_PLAIN
    food_mod = d.food_modifier(months, starving, eff)
    profit = max(plough, plain) + PROVISION_FOOD * food_mod * FOOD_PRICE - PROVISION_CROP * staple
    return profit, 1.5 + PROVISION_FOOD * food_mod, (CROP_PLOUGH if plough > plain else CROP_PLAIN) * crop_mod


def simulate(p: Prov, d: Design, months: int = 720, eff: float = 0.0, victuals: float = 2.7, staple: float = 1.0,
             cook_cost: float = 1.04, harvest: bool = False, seed: int = 1, start_months: float = 6.0, lag: int = 1,
             prosperity: bool = False, victuals_fn=None) -> list[dict]:
    """``cook_cost``: the Cookshop's input cost as a share of its Province Food revenue at modifier 0 (default prices 1.04)."""
    rng = random.Random(seed)
    store = min(p.cap, start_months * p.cons)
    hist = [store] * 6
    s_t = s_g = 0.0
    s_c = s_f = 1.0
    sev = prosp = 0.0
    log = []
    for t in range(months):
        if harvest and t % 12 == 8:
            sev = harvest_roll(rng)
        vp = victuals_fn(t) if victuals_fn else victuals
        cons = p.cons * (1 + sev * p.peasant_share) * (1 + 0.5 * prosp)
        m = min(CAP_MONTHS, hist[-lag] / p.cons)
        starving = store <= 0.0
        food_mod = d.food_modifier(m, starving, eff)

        f_profit, _, crop = farm_profit(d, m, p.land, staple, eff, starving)
        # a Province Food recipe follows the store; the offset recipes (2026-10-03) earn a thin margin at any store
        cook_profit = p.serve_per * FOOD_PRICE * (food_mod - cook_cost * staple) if p.serve_per else 0.05
        tav_profit = d.tavern_profit(m, vp, starving, eff)
        gr_profit = d.grange_profit(m, vp, starving, p.tav * s_t, eff)

        def ramp(s: float, profit: float) -> float:
            return min(1.0, max(0.0, s + (RAMP if profit > 0 else -RAMP)))

        s_f = ramp(s_f, f_profit)
        s_c = ramp(s_c, cook_profit) if p.cook else s_c
        s_t = ramp(s_t, tav_profit) if p.tav else s_t
        s_g = ramp(s_g, gr_profit) if p.grange else s_g

        tavern_food = p.tav * s_t * d.tavern_food * food_mod
        grange_take = p.grange * s_g * d.grange_food
        production = (p.sub + p.flat * s_f + p.provision * s_f * food_mod
                      + p.cook * s_c * (p.cook_flat + p.serve_per * food_mod)
                      + tavern_food - grange_take)
        store = min(p.cap, max(0.0, store + production - cons))
        hist.append(store)
        if prosperity:
            years = min(2.0, m / 12)
            prosp = min(1.0, max(0.0, prosp + (0.018 * years - (0.0025 if starving else 0.0) - 0.075 * prosp) / 12))
        log.append(dict(months=store / p.cons, farm=s_f, cook=s_c, tav=s_t, grange=s_g, farm_profit=f_profit,
                        cook_profit=cook_profit, tav_profit=tav_profit, grange_profit=gr_profit, starving=starving,
                        pump=min(tavern_food, grange_take) / p.cons, crop=crop))
    return log


def summary(log: list[dict], tail: int = 240) -> dict:
    rows = log[-tail:]
    months = sorted(r["months"] for r in rows)
    pick = lambda share: months[min(len(months) - 1, int(share * len(months)))]
    out = dict(mean=sum(months) / len(months), lo=pick(0.02), hi=pick(0.98), starving=sum(r["starving"] for r in rows),
               pump=sum(r["pump"] for r in rows) / len(rows))
    for key in ("farm", "cook", "tav", "grange"):
        out[key] = sum(r[key] for r in rows) / len(rows)
    return out


def cell(p: Prov, d: Design, **kw) -> dict:
    seeds = (1, 2, 3) if kw.get("harvest") else (1,)
    runs = [summary(simulate(p, d, seed=s, **kw)) for s in seeds]
    out = dict(runs[0])
    out["mean"] = sum(r["mean"] for r in runs) / len(runs)
    out["lo"], out["hi"] = min(r["lo"] for r in runs), max(r["hi"] for r in runs)
    out["starving"] = sum(r["starving"] for r in runs) / len(runs)
    out["pump"] = max(r["pump"] for r in runs)
    return out


def describe(d: Design) -> str:
    lines = [
        f"Province Food output {d.food_line(0):+.0%} (empty) .. {d.food_line(24):+.0%} (24 months); staples "
        f"{d.staple_line(0):+.0%} .. {d.staple_line(24):+.0%}; Surplus Sales {d.sales_low:+.0%} .. {d.sales_full:+.0%} "
        f"per year from {d.pivot:g} months",
        "Tavern fills to " + " / ".join(f"{d.tavern_fill(v):.1f}" for v in (2.0, 2.7, 3.5))
        + " months at victuals 2.0 / 2.7 / 3.5; Grange packs down to "
        + " / ".join(f"{d.grange_dig(v):.1f}" for v in (2.0, 2.7, 3.5, 4.5, 6.0)) + " months at 2.0 / 2.7 / 3.5 / 4.5 / 6.0",
        f"Cookshop: {COOK_FLAT:g} flat food per staffed level at any store (offset recipes, 2026-10-03)",
        "wheat farm profit per level (store 0 / 6 / 12 / 18 / 24 months): " + "; ".join(
            f"land {land:+.2f}: " + " ".join(f"{farm_profit(d, m, land)[0]:+.3f}" for m in (0, 6, 12, 18, 24))
            for land in (-0.54, -0.14, 0.06, 0.11)),
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", action="store_true")
    parser.add_argument("--trace")
    parser.add_argument("--months", type=int, default=240)
    parser.add_argument("--eff", type=float, default=0.0)
    parser.add_argument("--victuals", type=float, default=2.7)
    parser.add_argument("--harvest", action="store_true")
    args = parser.parse_args()
    design = load_design(ROOT)
    provs = provinces(load_pools())
    print(describe(design))
    if args.trace:
        p = next(x for x in provs if x.name.lower().startswith(args.trace.lower()))
        print(f"\n{p.name}: month, stored months, staffing cookshop / tavern / grange, profit tavern / grange")
        for i, r in enumerate(simulate(p, design, months=args.months, eff=args.eff, victuals=args.victuals,
                                       harvest=args.harvest)):
            if i % 3 == 0:
                print(f"{i:4d} {r['months']:5.1f}  {r['cook']:.2f} {r['tav']:.2f} {r['grange']:.2f}  "
                      f"{r['tav_profit']:+.2f} {r['grange_profit']:+.2f}")
        return
    if args.scenarios:
        scen = [("base", {}), ("vict 2.0", dict(victuals=2.0)), ("vict 3.5", dict(victuals=3.5)),
                ("vict 4.5", dict(victuals=4.5)), ("vict 6", dict(victuals=6.0)), ("staple -15%", dict(staple=0.85)),
                ("staple +15%", dict(staple=1.15)), ("eff -10%", dict(eff=-0.1)), ("eff +15%", dict(eff=0.15)),
                ("eff +30%", dict(eff=0.3)), ("eff +50%", dict(eff=0.5)), ("v4.5 e+30%", dict(victuals=4.5, eff=0.3)),
                ("v6 e+50%", dict(victuals=6.0, eff=0.5))]
        print("\nrest point in months (* starving; pNN = share of consumption cycled Grange -> Tavern)")
        print(" " * 50 + "".join(f"{n:>13s}" for n, _ in scen))
        for p in provs:
            cells = []
            for _, kw in scen:
                c = cell(p, design, **kw)
                cells.append(f"{c['mean']:5.1f}{'*' if c['starving'] else ' '}"
                             f"{('p%02d' % round(100 * c['pump'])) if c['pump'] > 0.005 else '   '}".rjust(13))
            print(f"{p.name[:50]:50s}" + "".join(cells))
        return
    tests = [("steady", {}), ("lag 3", dict(lag=3)), ("harvest", dict(harvest=True)), ("prosperity", dict(prosperity=True)),
             ("all three", dict(harvest=True, lag=2, prosperity=True))]
    print("\nstore range in months over the last 20 of 60 years (2 % .. 98 %; * starving), staffing in the steady run")
    print(" " * 62 + "".join(f"{n:>13s}" for n, _ in tests) + "   cook  tav  grange")
    for p in provs:
        cells, steady = [], None
        for _, kw in tests:
            c = cell(p, design, **kw)
            steady = steady or c
            cells.append(f"{c['lo']:4.1f}-{c['hi']:4.1f}{'*' if c['starving'] else ' '}".rjust(13))
        print(f"{p.name[:62]:62s}" + "".join(cells) + f"   {steady['cook']:.2f} {steady['tav']:.2f} {steady['grange']:.2f}")


if __name__ == "__main__":
    main()
