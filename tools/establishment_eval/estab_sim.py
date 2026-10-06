"""Replay a PP observer run under the EU5 1.4 establishment rules (formulas from the 1.4 decompile).

Every craft building of the manufacturing lines keeps its real life from the saves (built, upgraded, levels, staffing,
profit, open state, market access, owner); only establishment progress is simulated, month by month.
Run from the constructor root: uv run python <this file> [scenario ...]
"""
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import polars as pl

P = "73a2a926_3350_4c88_96aa_3571320aad06"
D = Path("graphs/dataset/tables")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/estab_sim")
OUT.mkdir(parents=True, exist_ok=True)

lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
INTERMEDIATE = {"dyes", "paper", "saltpeter"}
FINAL = {g: t for g, t in lines.items() if g not in INTERMEDIATE}
TYPE_GOOD = {t: g for g, ts in FINAL.items() for t in ts}
TYPE_TIER = {t: i for g, ts in FINAL.items() for i, t in enumerate(ts)}
PRED = {ts[i]: ts[i - 1] for g, ts in FINAL.items() for i in range(1, len(ts))}

# ---------------------------------------------------------------- panel
cache = OUT / "panel.parquet"
if cache.exists():
    panel = pl.read_parquet(cache)
else:
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={P}/*.parquet"))
         .filter(pl.col("building_type").is_in(list(TYPE_GOOD)))
         .select("snapshot_id", "date_sort", "year", "month", "building_id", "building_type", "location_id", "level",
                 "employed", "open", "last_months_profit")
         .collect())
    loc = (pl.scan_parquet(str(D / f"locations/playthrough_id={P}/*.parquet"))
           .select("snapshot_id", "location_id", "market_access", "owner_country_id", "country_tag").collect())
    panel = b.join(loc, on=["snapshot_id", "location_id"], how="left")
    panel.write_parquet(cache)

snaps = panel.select("date_sort", "year", "month").unique().sort("date_sort")
snap_month = {r[0]: (r[1] - snaps["year"][0]) * 12 + (r[2] - snaps["month"][0]) for r in snaps.iter_rows()}
panel = panel.with_columns(
    pl.col("date_sort").replace_strict(snap_month).alias("t"),
    pl.col("building_type").replace_strict(TYPE_GOOD).alias("good"),
    pl.col("building_type").replace_strict(TYPE_TIER).alias("tier"),
    pl.col("open").fill_null(True),
    pl.col("market_access").fill_null(0.0).clip(0.01, 1.0).alias("ma"),
    pl.col("last_months_profit").fill_null(0.0).alias("profit"),
    pl.col("owner_country_id").fill_null(-1),
)
full_staff = panel.group_by("building_type").agg((pl.col("employed") / pl.col("level")).quantile(0.95).alias("fs"))
panel = panel.join(full_staff, on="building_type").with_columns(
    (pl.col("employed") / (pl.col("level") * pl.col("fs"))).clip(0, 1).fill_nan(0).alias("staff"))

ids = panel["building_id"].unique().sort().to_numpy()
id_ix = {int(v): i for i, v in enumerate(ids)}
N = len(ids)
locs = panel["location_id"].unique().sort().to_numpy()
loc_ix = {int(v): i for i, v in enumerate(locs)}
goods = sorted(FINAL)
good_ix = {g: i for i, g in enumerate(goods)}
countries = panel["owner_country_id"].unique().sort().to_numpy()
cty_ix = {int(v): i for i, v in enumerate(countries)}

# static per building
b_static = panel.group_by("building_id").agg(pl.col("building_type").first(), pl.col("location_id").first(),
                                             pl.col("good").first(), pl.col("tier").first())
st_type = np.empty(N, dtype=object)
st_loc = np.zeros(N, dtype=np.int64)
st_good = np.zeros(N, dtype=np.int64)
st_tier = np.zeros(N, dtype=np.int64)
for bid, bt, lid, g, tr in b_static.iter_rows():
    i = id_ix[bid]
    st_type[i], st_loc[i], st_good[i], st_tier[i] = bt, loc_ix[lid], good_ix[g], tr

snap_list = sorted(snap_month.values())
frames = {t: f for (t,), f in panel.partition_by("t", as_dict=True).items()}


def snap_arrays(t):
    f = frames[t]
    ix = np.array([id_ix[v] for v in f["building_id"].to_list()])
    return ix, {c: f[c].to_numpy() for c in ("level", "staff", "open", "profit", "ma", "owner_country_id")}


SNAP = {t: snap_arrays(t) for t in snap_list}


# ---------------------------------------------------------------- scenarios
def target_of(p):
    base = np.array([p["base_target"][g] for g in goods], dtype=float)
    mult = np.array(p["tier_mult"], dtype=float)
    return base[st_good] * mult[np.minimum(st_tier, len(mult) - 1)]


def spec_factor(p, lv_cg):
    """global_<good>_establishment_speed per (country, good) from levels lv_cg[c, g]."""
    mode = p.get("spec")
    if not mode:
        return np.zeros_like(lv_cg)
    tot_c = lv_cg.sum(1, keepdims=True)
    if mode == "lq":
        w = lv_cg.sum(0, keepdims=True) / max(lv_cg.sum(), 1)
        share = np.divide(lv_cg, tot_c, out=np.zeros_like(lv_cg), where=tot_c > 0)
        lq = np.divide(share, w, out=np.zeros_like(lv_cg), where=w > 0)
        v = p["spec_k"] * (lq - 1)
    else:  # raw count: +a per own level, -b per level of every other final good
        v = p["spec_a"] * lv_cg - p["spec_b"] * (tot_c - lv_cg)
    return np.clip(v, p["spec_lo"], p["spec_hi"])


def simulate(p):
    T, maxpe = p["T"], p["max_pe"]
    tgt = target_of(p)
    prog = np.zeros(N)
    born = np.full(N, -1)
    reach_thr = np.full(N, -1)
    reach_full = np.full(N, -1)
    learned_empty = np.zeros(N)  # progress gained while staffing < 25 %
    learned_total = np.zeros(N)
    start = True
    rows, cap_rows = [], []
    for k in range(len(snap_list) - 1):
        t0, t1 = snap_list[k], snap_list[k + 1]
        ix0, a0 = SNAP[t0]
        ix1, a1 = SNAP[t1]
        if start:  # game start: start buildings seeded by a one-off boost
            seed = {"zero": 0.0, "threshold": T, "full": 1.0}[p["start"]]
            prog[ix0] = seed * tgt[ix0]
            born[ix0] = -2
            start = False
        s0, s1 = set(ix0.tolist()), set(ix1.tolist())
        cont = np.array(sorted(s0 & s1), dtype=np.int64)
        dying = np.array(sorted(s0 - s1), dtype=np.int64)
        newb = np.array(sorted(s1 - s0), dtype=np.int64)
        mid = t0 + (t1 - t0) // 2
        # upgrades: a new building whose line predecessor died at the same location
        dead_at = {(st_loc[i], st_type[i]): i for i in dying}
        upgrade_of = {}
        for i in newb:
            pt = PRED.get(st_type[i])
            if pt and (st_loc[i], pt) in dead_at:
                upgrade_of[i] = dead_at[(st_loc[i], pt)]
        # per building attributes for the interval (dying/continuing: t0 values, new: t1 values)
        pos0 = {v: j for j, v in enumerate(ix0)}
        pos1 = {v: j for j, v in enumerate(ix1)}
        attr = {}
        for c in ("level", "staff", "open", "profit", "ma", "owner_country_id"):
            arr = np.zeros(N, dtype=float)
            arr[ix0] = a0[c]
            arr[newb] = a1[c][[pos1[i] for i in newb]] if len(newb) else arr[newb]
            attr[c] = arr
        # AI cap: construction events of this interval (new buildings without upgrade + level increases)
        ramping0 = np.zeros(len(locs))
        alive0 = ix0[(a0["open"].astype(bool)) & (prog[ix0] < tgt[ix0])]
        np.add.at(ramping0, st_loc[alive0], 1)
        lv_up = np.zeros(N)
        if len(cont):
            lv_up[cont] = np.maximum(0, a1["level"][[pos1[i] for i in cont]] - a0["level"][[pos0[i] for i in cont]])
        new_plain = np.array([i for i in newb if i not in upgrade_of], dtype=np.int64)
        lv_up[new_plain] = a1["level"][[pos1[i] for i in new_plain]] if len(new_plain) else 0
        ev = np.nonzero(lv_up)[0]
        blocked = ramping0[st_loc[ev]] >= p["aicap"]
        cap_rows.append({"t": t1, "levels_built": float(lv_up[ev].sum()), "levels_blocked": float(lv_up[ev][blocked].sum())})
        # specialization levels per country at t0
        lv_cg = np.zeros((len(countries), len(goods)))
        cidx = np.array([cty_ix[int(c)] for c in a0["owner_country_id"]])
        np.add.at(lv_cg, (cidx, st_good[ix0]), a0["level"])
        spec = spec_factor(p, lv_cg)
        b_cty = np.array([cty_ix.get(int(c), 0) for c in attr["owner_country_id"]])
        good_factor_all = 1.0 + p.get("good_speed", 0.0) + spec[b_cty, st_good]
        for m in range(t0, t1):
            act = np.concatenate([cont, dying if m < mid else dying[:0], newb if m >= mid else newb[:0]])
            if m == mid and len(newb):
                for i in newb:
                    born[i] = m
                    if i in upgrade_of:
                        o = upgrade_of[i]
                        prog[i] = p["transfer"] * min(1.0, prog[o] / tgt[o]) * tgt[i]
            if not len(act):
                continue
            op = attr["open"][act].astype(bool)
            ramp = op & (prog[act] < tgt[act])
            n_loc = np.bincount(st_loc[act][ramp], minlength=len(locs))
            crowd = p["crowd"] * np.maximum(0, n_loc[st_loc[act]] - 1)
            s = np.maximum(0.01, attr["ma"][act] * (1 + crowd + p.get("bld_speed", 0.0)))
            lvl = np.maximum(1, attr["level"][act])
            pf = 1 + np.clip(attr["profit"][act] / (lvl * p["pcap"]), 0, 1) * p["mpb"]
            gain = s * good_factor_all[act] * pf
            new = np.where(op, np.clip(prog[act] + gain, 0, tgt[act]), np.maximum(0, prog[act] - p["decay"]))
            d = np.maximum(0, new - prog[act])
            learned_total[act] += d
            learned_empty[act] += d * (attr["staff"][act] < 0.25)
            prog[act] = new
            f = prog[act] / tgt[act]
            hit_t = (reach_thr[act] < 0) & (f >= T - 1e-9)
            reach_thr[act[hit_t]] = m
            hit_f = (reach_full[act] < 0) & (f >= 1 - 1e-9)
            reach_full[act[hit_f]] = m
        # snapshot row at t1
        ix, a = SNAP[t1]
        f = np.minimum(1, prog[ix] / tgt[ix])
        thr = np.minimum(1, f / T) if T > 0 else np.ones_like(f)
        pe = np.maximum(0, f - T) * maxpe
        w = a["level"]
        for g in range(len(goods)):
            sel = st_good[ix] == g
            if sel.any():
                rows.append({"t": t1, "good": goods[g], "levels": float(w[sel].sum()),
                             "throughput": float((w[sel] * thr[sel]).sum() / w[sel].sum()),
                             "pe": float((w[sel] * pe[sel]).sum() / w[sel].sum()),
                             "mastered": float(w[sel][f[sel] >= 1 - 1e-9].sum() / w[sel].sum())})
    res = pl.DataFrame({"id": ids, "good": [goods[g] for g in st_good], "tier": st_tier, "born": born,
                        "thr": reach_thr, "full": reach_full, "target": tgt,
                        "learned_empty": learned_empty, "learned_total": learned_total})
    return res, pl.DataFrame(rows), pl.DataFrame(cap_rows), snaps


BASE = {
    "T": 1 / 3, "max_pe": 0.15 / (2 / 3), "decay": 1.0, "transfer": 0.5, "pcap": 1.0, "mpb": 1.0, "crowd": -0.1,
    "aicap": 3, "start": "full", "tier_mult": [1.0, 1.25, 1.5, 1.75, 2.0],
    "base_target": {g: 180 for g in goods},
}
SLOW = {"cannons", "firearms", "weapons", "fine_cloth", "porcelain", "lacquerware", "jewelry", "books"}
QUICK = {"beer", "liquor", "wine", "pottery", "leather"}
BASE["base_target"] = {g: (240 if g in SLOW else 120 if g in QUICK else 180) for g in goods}

SCEN = {
    "A_full_start": {},
    "B_threshold_start": {"start": "threshold"},
    "C_zero_start": {"start": "zero"},
    "D_T0": {"T": 0.0, "max_pe": 0.15},
    "E_no_profit_bonus": {"mpb": 0.0},
    "F_spec_lq": {"spec": "lq", "spec_k": 0.5, "spec_lo": -0.5, "spec_hi": 1.0},
    "G_spec_count": {"spec": "count", "spec_a": 0.01, "spec_b": 0.002, "spec_lo": -0.5, "spec_hi": 1.0},
    "H_aicap5": {"aicap": 5},
    "I_crowd03": {"crowd": -0.3},
}

if __name__ == "__main__":
    want = sys.argv[2:] or list(SCEN)
    meta = {"N": N, "goods": goods, "snapshots": len(snap_list), "targets": BASE["base_target"]}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    for name in want:
        p = {**BASE, **SCEN[name]}
        res, series, cap, _ = simulate(p)
        res.write_parquet(OUT / f"{name}_buildings.parquet")
        series.write_parquet(OUT / f"{name}_series.parquet")
        cap.write_parquet(OUT / f"{name}_cap.parquet")
        print(name, "done", res.height, series.height)
