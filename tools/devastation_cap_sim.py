"""What devastation's pop cap cuts do to starving and looted locations (2026-11-03, Jan).

Starts from real locations in yearly saves and steps months. Rules, all measured in saves of 1.4.6 (10-year runs):

* cap = (flat + jobs) x (1 + upper class modifiers) + scaled x people. Devastation d = -prosperity (0..1) scales its static
  modifier, so `local_X_desired_pop = f` and `local_X_desired_pop_scaled = s` cut f d + s d P. The old `upper = yes` on laborers
  and soldiers acted as a cut of 0.38 d of the type (year-on-year change against the change in d).
* demotion = min(over the cap, speed), speed = (0.10 + 0.5 d + 0.025 starving) x (1 + 0.2 starving) k a month per location and
  type. Burghers and soldiers go to laborers, laborers, clergy and nobles to peasants.
* promotion only at d ~ 0 (`local_pop_promotion_speed` on devastation), at a nearly flat speed per location and type.
* food: consumption = sum(size x food), production = flat + 1.25 x (idle peasants + slaves), store with effective decay 0.5 %.
  An idle peasant makes more than he eats, so deaths alone hardly close a gap: that is the starvation loop.
* starving: deaths and net migration per type as measured in empty stores, prosperity -0.048 a month. Fed: recovery 0.0095 a month
  below 0 (0.006 below -0.75), scaled down at a low store.

Scenarios: famines ending at the measured rate, famines with no outside help, a two-year famine, a fed location looted to -0.6.
No AI reaction, no new buildings, no wars after the start. Check: the sim gives laborers 0.03 % a month in famine without a cut
(measured 0.03-0.05 %) and 1.0 % with the old flag (measured 1.18 %).

Run from the constructor root (reads saves through eu5q, first run about 5 minutes):
  uv run python tools/devastation_cap_sim.py [--runs pp_cult_fix pp_cult_fix2]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import subprocess

import numpy as np
import polars as pl

TYPES = ["laborers", "soldiers", "burghers", "clergy", "nobles", "peasants", "slaves", "tribesmen"]
L, SO, B, C, N, PE, SL, TR = range(8)
FOOD = np.array([1.5, 4, 6.5, 6.5, 25, 1, 0.5, 0.0])
STARVING_LOSS = np.array([0.00403, 0.01384, 0.00376, 0.01034, 0.01368, 0.00503, 0.00246, 0.00258])
STARVING_DEATHS = np.array([0.00333, 0.00309, 0.00301, 0.0031, 0.00308, 0.00354, 0.00246, 0.00254])
PROMOTION = np.array([0.0075, 0.0038, 0.001, 0.0006, 0.0006, 0, 0, 0])
SCALED_BASE = {C: 0.005, N: 0.0025}  # location_base_values
SUBSISTENCE = 1.25
DECAY = 0.005
YEARS = (3, 5, 7, 10)
CACHE = Path.home() / ".cache" / "eu5save" / "devastation_cap"


@dataclass
class Rule:
    name: str
    cut: dict[int, tuple[float, float]] = field(default_factory=dict)  # type -> flat, scaled at full devastation
    share: dict[int, float] = field(default_factory=dict)  # type -> share of the cap at full devastation (the old flag)


NOW = Rule("without")
OLD_FLAG = Rule("old upper flag", share={L: 0.38, SO: 0.38})
MOD = Rule("in the mod", cut={L: (0.4, 0.01), SO: (0.0, 0.001), C: (0.0, 0.0025), N: (0.0, 0.0016)})


def query(save: str, expr: str, name: str) -> pl.DataFrame:
    path = CACHE / f"{save}_{name}.parquet"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["uv", "run", "eu5q", "--save", save, f'{expr}.write_parquet(r"{path}")'], check=True, capture_output=True)
    return pl.read_parquet(path)


def load_save(save: str) -> pl.DataFrame:
    pops = query(save, 'pops.select("location_id","pop_type","size")', "pops")
    wide = pops.group_by("location_id", "pop_type").agg(pl.col("size").sum()).pivot(on="pop_type", index="location_id", values="size").fill_null(0.0)
    wide = wide.with_columns(pl.col("location_id").cast(pl.Int64), *[pl.lit(0.0).alias(t) for t in TYPES if t not in wide.columns])
    loc = query(save, 'locations.select("location_id","province_slug","owner_country_id","total_population","unemployed_laborers","unemployed_peasants")', "locations")
    state = query(save, 'location_state.select("location_id","prosperity")', "state")
    raw = query(save, 'provinces_raw.select("province_id","capital_location_id")', "provinces")
    food = query(save, 'province_food.select("province_id","food_current","max_food_value","cached_structural_food_change","base_food_consumption")', "food")
    capital = raw.join(loc.select("location_id", "province_slug", "owner_country_id"), left_on="capital_location_id", right_on="location_id")
    food = food.join(capital, on="province_id").drop("province_id", "capital_location_id")
    frame = wide.join(loc, on="location_id").join(state, on="location_id", how="left").join(food, on=["province_slug", "owner_country_id"])
    return frame.filter(pl.col("owner_country_id").is_not_null()).with_columns(
        pl.lit(save).alias("save"), pl.col("prosperity").fill_null(0.0), pl.col("unemployed_peasants").fill_null(0.0), pl.col("unemployed_laborers").fill_null(0.0)
    )


def arrays(frame: pl.DataFrame) -> dict:
    frame = frame.with_columns((pl.col("save") + "|" + pl.col("province_slug") + "|" + pl.col("owner_country_id").cast(pl.String)).alias("part"))
    parts, index = np.unique(frame["part"].to_numpy().astype(str), return_inverse=True)
    prov = frame.group_by("part").agg(pl.col("food_current", "max_food_value", "cached_structural_food_change", "base_food_consumption").first()).sort("part")
    return {
        "parts": parts,
        "prov": index,
        "sizes": frame.select(TYPES).to_numpy().astype(float),
        "p": frame["prosperity"].to_numpy().astype(float),
        "store": prov["food_current"].to_numpy().astype(float),
        "store_max": prov["max_food_value"].to_numpy().astype(float),
        "structural": prov["cached_structural_food_change"].to_numpy().astype(float),
        "consumption": prov["base_food_consumption"].to_numpy().astype(float),
        "idle_laborers": frame["unemployed_laborers"].to_numpy().astype(float),
        "idle_peasants": frame["unemployed_peasants"].to_numpy().astype(float),
    }


def simulate(data: dict, rule: Rule, months: int, relief: np.ndarray | None = None, relief_gap: float = 0.1, looted: float | None = None) -> dict:
    prov, n_prov = data["prov"], len(data["parts"])
    sizes, start = data["sizes"].copy(), data["sizes"].copy()
    p = np.minimum(data["p"], looted) if looted is not None else data["p"].copy()
    store, store_max = data["store"].copy(), data["store_max"]
    people0 = sizes.sum(1)
    farm_peasants = np.clip(sizes[:, PE] - data["idle_peasants"], 0, None)
    jobs = np.clip(sizes[:, L] - data["idle_laborers"], 0, None)
    cap0 = sizes.copy()
    cap0[:, B] = sizes[:, B] / np.clip(1 - 0.5 * np.clip(-data["p"], 0, 1), 0.3, 1)  # the saves already carry the upper class cut
    scaled_share = {t: np.maximum(sizes[:, t] / np.clip(people0, 0.001, None), base) for t, base in SCALED_BASE.items()}
    idle = np.clip(sizes[:, PE] - farm_peasants, 0, None) + sizes[:, SL]
    flat = data["consumption"] + data["structural"] - SUBSISTENCE * np.bincount(prov, idle, n_prov)
    deaths = np.zeros(len(p))
    low = sizes.copy()
    back = np.full((len(p), 8), np.nan)
    fed_months = np.zeros(n_prov)
    ended = np.full(n_prov, np.nan)
    job_months_lost = np.zeros(len(p))
    relieved = np.zeros(n_prov, dtype=bool)
    demoted, starving_size = np.zeros(8), np.zeros(8)
    for month in range(months):
        consumption = np.bincount(prov, (sizes * FOOD).sum(1), n_prov)
        idle = np.clip(sizes[:, PE] - farm_peasants, 0, None) + sizes[:, SL]
        net = flat + SUBSISTENCE * np.bincount(prov, idle, n_prov) - consumption
        if relief is not None:
            due = (relief <= month) & ~relieved
            add = np.clip(np.where(due, relief_gap * consumption - net, 0.0), 0, None)
            flat, net = flat + add, net + add
            relieved |= due
        store = np.clip(store + net - DECAY * store, 0, store_max)
        starving_prov = (store <= 0) & (net < 0)
        fed_months = np.where(starving_prov, 0, fed_months + 1)
        ended = np.where(np.isnan(ended) & (fed_months >= 12), month - 11, ended)
        starving = starving_prov[prov]
        stored = (store / np.clip(consumption, 0.001, None))[prov]
        recovery = np.where(p < -0.75, 0.006, np.where(p < 0, 0.0095, 0.0025)) * (0.4 + 0.6 * np.clip(stored / 6, 0, 1))
        p = np.clip(p + np.where(starving, -0.048, recovery), -1, 1)
        d = np.clip(-p, 0, 1)
        growth = (0.006 * np.minimum(stored, 24) / 12 - 0.004) / 12
        deaths += (sizes * STARVING_DEATHS * starving[:, None]).sum(1)
        sizes = sizes * np.where(starving[:, None], 1 - STARVING_LOSS, 1 + growth[:, None])
        people = sizes.sum(1)
        cap = cap0.copy()
        for t, share in scaled_share.items():
            cap[:, t] = share * people
        cap[:, B] = cap0[:, B] * (1 - 0.5 * d)
        for t, (f, s) in rule.cut.items():
            cap[:, t] -= d * (f + s * people)
        for t, share in rule.share.items():
            cap[:, t] *= 1 - share * d
        cap = np.clip(cap, 0, None)
        speed = (0.10 + 0.5 * d + 0.025 * starving) * (1 + 0.2 * starving)
        demote = np.minimum(np.clip(sizes - cap, 0, None), speed[:, None])
        demote[:, PE:] = 0
        demoted += (demote * starving[:, None]).sum(0)
        starving_size += (sizes * starving[:, None]).sum(0)
        sizes = sizes - demote
        sizes[:, L] += demote[:, B] + demote[:, SO]
        sizes[:, PE] += demote[:, L] + demote[:, C] + demote[:, N]
        promote = np.minimum(np.clip(cap - sizes, 0, None), PROMOTION[None, :] * (d < 0.005)[:, None])
        promote = np.minimum(promote, (sizes[:, PE] * 0.5)[:, None])
        sizes = sizes + promote
        sizes[:, PE] -= promote.sum(1)
        low = np.minimum(low, sizes)
        back = np.where(np.isnan(back) & (sizes >= 0.9 * start) & (low < 0.9 * start), month, back)
        job_months_lost += np.clip(jobs - sizes[:, L], 0, None)
    return {
        "sizes": sizes, "start": start, "low": low, "back": back, "deaths": deaths, "ended": ended, "job_months_lost": job_months_lost,
        "jobs": jobs, "people0": people0, "months": months, "demotion_rate": demoted / np.clip(starving_size, 1e-6, None),
    }


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    return float(values[order][np.searchsorted(np.cumsum(weights[order]) / weights.sum(), 0.5)])


def row(name: str, data: dict, res: dict) -> dict:
    people_prov = np.bincount(data["prov"], res["people0"], len(data["parts"]))
    out = {"rule": name, "dead %": round(100 * res["deaths"].sum() / res["people0"].sum(), 1)}
    for years in (2, 5, 10):
        out[f"over by {years}y %"] = round(100 * float(people_prov[res["ended"] <= years * 12].sum() / people_prov.sum()), 1)
    out["laborers demoted, % a month"] = round(100 * float(res["demotion_rate"][L]), 2)
    for t, label in ((L, "lab"), (SO, "sol"), (B, "bur"), (C, "cle"), (N, "nob")):
        start, low = res["start"][:, t], res["low"][:, t]
        out[f"{label} low %"] = round(100 * (1 - low.sum() / start.sum()), 1)
        hit = low < 0.9 * start
        if hit.any() and start[hit].sum() > 0:
            years = np.where(np.isnan(res["back"][hit, t]), res["months"], res["back"][hit, t]) / 12
            out[f"{label} 90 % back, y"] = round(weighted_median(years, start[hit]), 1)
    out["job-years lost %"] = round(100 * float(res["job_months_lost"].sum() / (res["jobs"].sum() * res["months"])), 1)
    return out


def cut_table(data: dict, rule: Rule) -> pl.DataFrame:
    people = data["sizes"].sum(1)
    rows = []
    for t, (f, s) in rule.cut.items():
        size = data["sizes"][:, t]
        keep = size > (0.05 if t == L else 0.005)
        for d in (0.1, 0.25, 0.5, 1.0):
            share = np.minimum(d * (f + s * people[keep]) / size[keep], 1)
            rows.append({"type": TYPES[t], "d": d, "median %": round(100 * float(np.median(share)), 1), "locations emptied %": round(100 * float((share >= 1).mean()), 1), "people emptied %": round(100 * float(size[keep][share >= 1].sum() / size[keep].sum()), 2)})
    return pl.DataFrame(rows)


def famine_ends(count: int) -> np.ndarray:
    """Relief month per famine, from the saves: 68 % of empty stores are still empty a year on, 33 % after two years and later."""
    draw = np.random.default_rng(1337).uniform(0, 1, count)
    return np.where(draw < 0.325, 10**6, np.interp(-draw, [-1.0, -0.677, -0.325], [0.0, 12.0, 24.0]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", nargs="+", default=["pp_cult_fix", "pp_cult_fix2"], help="save stems without upper = yes on workers, with _y3 _y5 _y7 _y10 saves")
    args = parser.parse_args()
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(240)
    frames = [load_save(f"{run}_y{y}") for run in args.runs for y in YEARS]
    world = pl.concat(frames, how="diagonal").with_columns(
        (pl.col("food_current") / pl.col("base_food_consumption").clip(0.0001)).alias("stored"), (pl.col("cached_structural_food_change") / pl.col("base_food_consumption").clip(0.0001)).alias("gap")
    )
    famine = arrays(world.filter((pl.col("stored") < 0.05) & (pl.col("gap") < 0) & (pl.col("max_food_value") > 0) & (pl.col("base_food_consumption") > 0.5)))
    fed = arrays(world.filter((pl.col("stored") > 3) & (pl.col("gap") > -0.2) & (pl.col("prosperity") >= 0) & (pl.col("total_population") > 1) & (pl.col("max_food_value") > 0) & pl.col("save").str.ends_with("_y5")))
    relief = famine_ends(len(famine["parts"]))
    rules = (NOW, OLD_FLAG, MOD)
    print("Cut at devastation d, fed locations")
    print(cut_table(fed, MOD))
    for title, data, kwargs, months in (
        ("Famines end at the measured rate, 25 years", famine, {"relief": relief}, 300),
        ("No outside help, 20 years", famine, {}, 240),
        ("Two-year famine, then food +15 %, 25 years", famine, {"relief": np.full(len(famine["parts"]), 24.0), "relief_gap": 0.15}, 300),
        ("Fed location looted to prosperity -0.6, 25 years", fed, {"looted": -0.6}, 300),
    ):
        print(title)
        print(pl.DataFrame([row(rule.name, data, simulate(data, rule, months, **kwargs)) for rule in rules], strict=False))


if __name__ == "__main__":
    main()
