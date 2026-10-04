"""AI building-maintenance simulator (2026-10-04): how often the AI closes and reopens buildings without goods output
(libraries, temples, universities, marketplaces, ...) for given AI_ALLOWED_BUILDING_MAINTENANCE (A) and
AI_BUILDING_MAINTENANCE_LEEWAY (L).

The AI's maintenance pass (EU5 1.4, behaviour as observed and documented in docs/ai_building_rulebook.md):

* B = A x total monthly income, M = last month's building maintenance (open buildings only; closed ones cost nothing);
* M > L x B: close buildings without goods output, walking the country's locations (lowest first), until M is back at
  B; once that cut is reached, every remaining location still closes its first eligible building in that pass;
* M < B: reopen closed ones, walking the locations from the top, as long as each reopening keeps M <= L x B; once a
  reopening takes M above B only that location stops, every later location still reopens one;
* the AI queues new buildings of this kind only while M < B and M + its upkeep <= L x B, so buildings sitting closed
  leave room to build more;
* the pass runs every 2 (empire) to 8 (county) months.

Countries and their buildings (cost, location, open/closed) come from a save; income paths are synthetic monthly
series fitted to the save's 12-month income histories and to the 5-year income changes of the long observer runs.
Two stock variants: the buildings as they are, and the AI building more while the budget allows (up to +50 %).

Run (needs a save with the engine's monthly_gold column):
  uv run python tools/ai_maintenance_sim.py                         grid on the newest save
  uv run python tools/ai_maintenance_sim.py --save NAME --previous NAME   also print the observed 5-year churn
  uv run python tools/ai_maintenance_sim.py --allowed 0.15,0.2 --leeway 1.5,2.5 --years 100
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import polars as pl

OUT = Path("artifacts/data/ai_maintenance_sim")
# 5-year income behaviour of the long observer runs (dataset country_ai, 7 runs 1340-1927, measured 2026-10-04)
LONG_RUN_TARGETS = dict(sd5y=0.28, dd_p05=0.556, dd_p10=0.667, dd_p20=0.805)
RANK_MONTHS = {"rank_county": 8, "rank_duchy": 6, "rank_kingdom": 4, "rank_empire": 2}


# ------------------------------------------------------------------ income process
def income_paths(n, T, phi, s1, s2, pj, se, rng):
    """log income = AR(1) level with occasional jumps + monthly noise."""
    jump = rng.random((n, T)) < pj
    eta = np.where(jump, rng.normal(0, s2, (n, T)), rng.normal(0, s1, (n, T)))
    x = np.zeros((n, T))
    x[:, 0] = rng.normal(0, np.sqrt((1 - pj) * s1 ** 2 + pj * s2 ** 2) / np.sqrt(1 - phi ** 2), n)
    for t in range(1, T):
        x[:, t] = phi * x[:, t - 1] + eta[:, t]
    return x + rng.normal(0, se, (n, T))


def income_stats(logi):
    d = np.diff(logi[:, :12], axis=1)
    w = np.exp(logi[:, :12])
    mm = w.min(axis=1) / w.max(axis=1)
    snaps = np.exp(logi[:, ::60][:, :6])
    dd = snaps[:, 5] / snaps[:, 1:6].max(axis=1)
    return dict(sd_month=float(np.median(d.std(axis=1))),
                ac1=float(np.median([np.corrcoef(r[:-1], r[1:])[0, 1] for r in d[:2000]])),
                mm_med=float(np.median(mm)), mm_p10=float(np.quantile(mm, 0.1)), sd5y=float(np.std(logi[:, 60] - logi[:, 0])),
                dd_p05=float(np.quantile(dd, 0.05)), dd_p10=float(np.quantile(dd, 0.1)), dd_p20=float(np.quantile(dd, 0.2)))


def save_income_targets(histories):
    rows = []
    for g in histories:
        g = np.asarray(g, float)
        if len(g) == 12 and g.min() > 2 and g.mean() >= 10:
            dl = np.diff(np.log(g))
            rows.append((dl.std(), np.corrcoef(dl[:-1], dl[1:])[0, 1], g.min() / g.max()))
    a = np.array(rows)
    return dict(sd_month=float(np.median(a[:, 0])), ac1=float(np.nanmedian(a[:, 1])), mm_med=float(np.median(a[:, 2])),
                mm_p10=float(np.quantile(a[:, 2], 0.1)))


def fit_income(targets):
    best, rng = None, np.random.default_rng(1)
    for phi in (0.93, 0.95, 0.965, 0.98):
        for s1 in (0.03, 0.04, 0.05):
            for s2 in (0.15, 0.25, 0.35):
                for pj in (0.02, 0.04, 0.08):
                    for se in (0.015, 0.025, 0.04):
                        st = income_stats(income_paths(3000, 361, phi, s1, s2, pj, se, rng))
                        err = sum(((st[k] - v) / (0.3 if k == "ac1" else abs(v))) ** 2 for k, v in targets.items())
                        if best is None or err < best[0]:
                            best = (err, (phi, s1, s2, pj, se), st)
    return best


# ------------------------------------------------------------------ countries from a save
def load_countries(save, previous=None):
    from eu5gameparser.domain.buildings import load_building_data
    from eu5gameparser.domain.goods import load_goods_data
    from eu5gameparser.savegame import quick

    lo = "constructor.load_order.toml"
    gd = load_goods_data(profile="constructor", load_order_path=lo)
    pm = load_building_data(profile="constructor", load_order_path=lo, goods_data=gd).production_methods
    producing = set(pm.filter(pl.col("produced").is_not_null() & pl.col("building").is_not_null())["building"].unique().to_list())
    t = quick.load(save)
    tp = quick.load(previous) if previous else None
    b = t.buildings.with_columns(is_open=pl.col("open").is_null() | pl.col("open"))
    no_output = b.filter(~pl.col("building_type").is_in(list(producing)))
    closable = set(no_output.filter(~pl.col("is_open"))["building_type"].unique().to_list())
    if tp is not None:
        closable |= set(tp.buildings.filter((pl.col("open") == False) & ~pl.col("building_type").is_in(list(producing)))
                        ["building_type"].unique().to_list())
    if len(closable) < 10:  # early save: nothing closed yet, take every type without output that costs maintenance
        closable = set(no_output.filter(pl.col("upkeep") > 0)["building_type"].unique().to_list())
    per_level = b.filter(pl.col("is_open") & (pl.col("upkeep") > 0)).group_by("building_type").agg(
        ul=(pl.col("upkeep") / pl.col("level")).median())
    cb = b.filter(pl.col("building_type").is_in(list(closable))).join(per_level, on="building_type", how="left").with_columns(
        u=pl.when(pl.col("is_open") & (pl.col("upkeep") > 0)).then(pl.col("upkeep")).otherwise(pl.col("ul") * pl.col("level"))
    ).filter(pl.col("u") > 0).join(t.locations.select("location_id", "development"), on="location_id", how="left")
    ai = t.country_ai.filter(pl.col("monthly_gold").is_not_null()).with_columns(
        hist=pl.col("monthly_gold").str.split(",").cast(pl.List(pl.Float64))).with_columns(level=pl.col("hist").list.mean())
    obs = dict(buildings=cb.height, closed_share=float(cb.filter(~pl.col("is_open"))["u"].sum() / cb["u"].sum()))
    if tp is not None:
        j = tp.buildings.select("building_id", o0=pl.col("open").is_null() | pl.col("open")).join(
            cb.select("building_id", "is_open"), on="building_id")
        obs["closed_5y_pct"] = 100 * float((j["o0"] & ~j["is_open"]).sum()) / cb.height
        obs["reopened_5y_pct"] = 100 * float((~j["o0"] & j["is_open"]).sum()) / cb.height
    open_u = cb.filter(pl.col("is_open")).group_by("owner").agg(ou=pl.col("u").sum())
    ai = ai.join(open_u, left_on="country_id", right_on="owner", how="left").with_columns(pl.col("ou").fill_null(0))
    groups = cb.partition_by("owner", as_dict=True)
    countries = []
    for row in ai.iter_rows(named=True):
        g = groups.get((row["country_id"],))
        if g is None or not row["level"] or row["level"] < 1 or not row["income"] or row["income"] < 1:
            continue
        g = g.sort("development", "location_id", "building_id", nulls_last=True)
        countries.append(dict(
            cid=row["country_id"], k=RANK_MONTHS.get(row["country_rank"], 6), I0=row["level"],
            M_fixed=max(0.0, (row["last_months_building_maintenance"] or 0.0) - row["ou"]),
            u=g["u"].to_numpy().astype(float), loc=g["location_id"].to_numpy(), dev=g["development"].fill_null(0).to_numpy(),
            is_open=g["is_open"].to_numpy().copy()))
    return countries, obs, ai["hist"].to_list()


# ------------------------------------------------------------------ the AI's pass
class Country:
    def __init__(self, c, growth_cap, rng):
        n0 = len(c["u"])
        self.k, self.phase, self.I0, self.M_fixed = c["k"], c["cid"] % c["k"], c["I0"], c["M_fixed"]
        n_extra = int(np.ceil(n0 * (growth_cap - 1.0))) if growth_cap > 1 else 0
        pick = rng.integers(0, n0, n_extra)
        self.u = np.concatenate([c["u"], c["u"][pick]])
        self.loc = np.concatenate([c["loc"], c["loc"][pick]])
        self.dev = np.concatenate([c["dev"], c["dev"][pick]])
        self.exists = np.concatenate([np.ones(n0, bool), np.zeros(n_extra, bool)])
        self.open = np.concatenate([c["is_open"], np.zeros(n_extra, bool)])
        self.next_slot = n0
        order = np.lexsort((np.arange(len(self.u)), self.loc, self.dev))
        groups, cur, last = [], [], None
        for i in order:
            key = (self.dev[i], self.loc[i])
            if key != last and cur:
                groups.append(np.array(cur))
                cur = []
            cur.append(i)
            last = key
        if cur:
            groups.append(np.array(cur))
        self.g_asc, self.g_desc = groups, groups[::-1]

    def m_open(self):
        return self.M_fixed + self.u[self.exists & self.open].sum()

    def close_pass(self, M, B):
        cut, n = M - B, 0
        for grp in self.g_asc:
            for i in grp:
                if self.exists[i] and self.open[i]:
                    self.open[i] = False
                    M -= self.u[i]
                    cut -= self.u[i]
                    n += 1
                    if cut < 0:
                        break  # only this location stops
        return M, n

    def reopen_pass(self, M, B, L):
        n = 0
        for grp in self.g_desc:
            for i in grp:
                if self.exists[i] and not self.open[i]:
                    r2 = (M + self.u[i]) / B
                    if r2 <= L:
                        self.open[i] = True
                        M += self.u[i]
                        n += 1
                        if r2 > 1.0:
                            break  # only this location stops
        return M, n


def run(countries, logi, A, L, growth_cap, p_build, burn, T, seed=11):
    rng = np.random.default_rng(seed)
    cs = [Country(c, growth_cap, np.random.default_rng(1000 + j)) for j, c in enumerate(countries)]
    n = len(cs)
    M = np.array([c.m_open() for c in cs])
    I0 = np.array([c.I0 for c in cs])
    K = np.array([c.k for c in cs])
    PH = np.array([c.phase for c in cs])
    MF = np.array([c.M_fixed for c in cs])
    stock0 = sum(c.u[c.exists].sum() for c in cs)
    acc = dict(closed_u=0.0, stock_u=0.0, openM=0.0, inc=0.0, months=0, closures=0)
    snaps, prev = [], None
    for t in range(T):
        I = I0 * np.exp(logi[:, t])
        B = A * I
        if p_build > 0:
            for j in np.nonzero((M < B) & (rng.random(n) < p_build))[0]:
                c = cs[j]
                if c.next_slot < len(c.u) and M[j] + c.u[c.next_slot] <= L * B[j]:
                    c.exists[c.next_slot] = c.open[c.next_slot] = True
                    M[j] += c.u[c.next_slot]
                    c.next_slot += 1
        due = (t % K) == PH
        r = M / B
        for j in np.nonzero(due & (r > L))[0]:
            M[j], nn = cs[j].close_pass(M[j], B[j])
            if t >= burn:
                acc["closures"] += nn
        for j in np.nonzero(due & (r < 1.0))[0]:
            if (cs[j].exists & ~cs[j].open).any():
                M[j], _ = cs[j].reopen_pass(M[j], B[j], L)
        if t < burn:
            continue
        acc["months"] += 1
        acc["inc"] += I.sum()
        acc["openM"] += (M - MF).sum()
        if t % 12 == 0:
            acc["closed_u"] += sum(c.u[c.exists & ~c.open].sum() for c in cs)
            acc["stock_u"] += sum(c.u[c.exists].sum() for c in cs)
        if (t - burn) % 60 == 0:
            st = np.concatenate([c.open & c.exists for c in cs])
            ex = np.concatenate([c.exists for c in cs])
            if prev is not None:
                pst, pex = prev
                snaps.append(((pst[pex] & ~st[pex]).sum(), (~pst[pex] & st[pex]).sum(), pex.sum()))
            prev = (st, ex)
    years = acc["months"] / 12
    nb = np.mean([s[2] for s in snaps])
    return dict(A=A, L=L, closures_per_building_century=100 * acc["closures"] / years / nb,
                closed_5y_pct=100 * np.mean([s[0] for s in snaps]) / nb,
                reopened_5y_pct=100 * np.mean([s[1] for s in snaps]) / nb,
                closed_share=acc["closed_u"] / acc["stock_u"], spend_share_income=acc["openM"] / acc["inc"],
                stock_growth=sum(c.u[c.exists].sum() for c in cs) / stock0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--save", help="save name or path (default: newest)")
    ap.add_argument("--previous", help="a save ~5 years earlier of the same game: prints the observed churn")
    ap.add_argument("--allowed", default="0.15,0.2,0.25,0.3,0.4")
    ap.add_argument("--leeway", default="1.2,1.5,2.0,2.5,3.0,4.0")
    ap.add_argument("--years", type=int, default=100)
    ap.add_argument("--burn", type=int, default=30, help="years before measuring")
    args = ap.parse_args()
    t0 = time.time()
    from eu5gameparser.savegame import quick

    save = quick._save_path(args.save)
    countries, obs, histories = load_countries(save, quick._save_path(args.previous) if args.previous else None)
    targets = {**save_income_targets(histories), **LONG_RUN_TARGETS}
    err, params, st = fit_income(targets)
    print(f"save {save.name}: {len(countries)} countries, {sum(len(c['u']) for c in countries)} buildings without output")
    print("observed:", {k: round(v, 3) for k, v in obs.items()})
    print("income targets:", {k: round(v, 3) for k, v in targets.items()})
    print("income model:  ", {k: round(v, 3) for k, v in st.items()}, "fit error", round(err, 3))
    burn, T = args.burn * 12, (args.burn + args.years) * 12
    logi = income_paths(len(countries), T, *params, np.random.default_rng(5))
    rows = []
    for variant, cap, p in (("buildings as they are", 1.0, 0.0), ("AI keeps building (cap +50 %)", 1.5, 1 / 12)):
        for A in [float(x) for x in args.allowed.split(",")]:
            for L in [float(x) for x in args.leeway.split(",")]:
                rows.append({"variant": variant, **run(countries, logi, A, L, cap, p, burn, T)})
    df = pl.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.write_csv(OUT / "grid.csv")
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_float_precision(3)
    for variant in df["variant"].unique(maintain_order=True):
        v = df.filter(pl.col("variant") == variant)
        print(f"\n== {variant}")
        for metric in ("closures_per_building_century", "closed_5y_pct", "closed_share", "spend_share_income", "stock_growth"):
            print(f"-- {metric} (rows allowed, columns leeway)")
            print(v.pivot(on="L", index="A", values=metric, aggregate_function="first").sort("A"))
    print(f"\n{OUT / 'grid.csv'}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
