"""Charts: establishment runs B (grace) and A vs the clean baseline C (same commit) and older baselines.
uv run python est_charts2.py SCRATCH B A C B1 B2"""
import sys
from pathlib import Path

import matplotlib
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

S = Path(sys.argv[1])
B, A, C, B1, B2 = sys.argv[2:7]
spec = pl.read_parquet(S / "spec_all.parquet")
spec_e = pl.read_parquet(S / "spec_all_emp.parquet")
est = pl.read_parquet(S / "est_all.parquet")
pop = pl.read_parquet(S / "pop_all.parquet")
COL = {B: ("#c0392b", "B: establishment + cleanup with 8-year grace", 2.4, "-"),
       A: ("#e08a1e", "A: establishment + cleanup without grace", 1.6, "-"),
       C: ("#1b1b1b", "C: clean baseline, same commit", 2.2, "-"),
       B1: ("#a0a7ab", "older baseline 73a2a926", 1.0, "--"),
       B2: ("#c4c9cc", "older baseline cb516c0a", 1.0, "--")}


def agg(df):
    return df.group_by("run", "year").agg(
        pl.col("levels").sum().alias("craft_levels"),
        ((pl.col("top10_loc") * pl.col("levels")).sum() / pl.col("levels").sum()).alias("top10_loc"),
        pl.col("locations").sum().alias("producer_locations"),
        pl.col("levels_in_lq2").first(),
        (pl.col("traded").sum() / pl.col("supply").sum()).alias("trade_share"),
        pl.col("traded").sum().alias("traded"),
        pl.col("supply").sum().alias("supply"),
        pl.col("exporters").sum().alias("exporters"),
        (pl.col("pd").sum() / pl.col("dd").sum()).alias("price_idx")).sort("run", "year")


Ag, AE = agg(spec), agg(spec_e)
panels = [
    (AE, "top10_loc", "Top-10 locations' share of staffed craft capacity (per good)"),
    (A_ := Ag, "levels_in_lq2", "Craft levels in markets specialized >= 2x world mix"),
    (Ag, "producer_locations", "Locations producing (sum over goods)"),
    (Ag, "traded", "Final craft goods traded between markets (units)"),
    (Ag, "trade_share", "Traded / supply"),
    (Ag, "exporters", "Exporting markets (sum over goods)"),
    (Ag, "supply", "Final craft goods supply"),
    (Ag, "price_idx", "Final craft goods price / default"),
    (AE, "craft_levels", "Staffed craft capacity (k workers)"),
    (est, "new_buildings", "New craft buildings per 5 years"),
    (est, "gone_buildings", "Craft buildings gone per 5 years"),
    (est, "levels_per_building", "Levels per craft building"),
    (pop, "wealth_pc", "Location wealth per 1k people (possible tax)"),
    (pop, "burghers", "Burghers (k)"),
    (pop, "population", "World population (M)"),
]
fig, axes = plt.subplots(5, 3, figsize=(16, 19))
for ax, (df, col, title) in zip(axes.flat, panels):
    for run, (c, lab, lw, ls) in COL.items():
        d = df.filter(pl.col("run") == run).sort("year")
        if d.height and col in d.columns:
            ax.plot(d["year"], d[col], color=c, lw=lw, ls=ls, label=lab)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_xlim(1340, 1790)
axes.flat[0].legend(fontsize=8)
fig.suptitle("Establishment (know-how) on the final-goods craft lines: test runs vs baselines", fontsize=13)
fig.tight_layout()
fig.savefig(S / "est_compare2.png", dpi=90)

e = est.filter(pl.col("run") == B).sort("year")
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
ax[0].plot(e["year"], e["mastered_level_share"] * 100, label="levels fully established", color="#1f6fb5")
ax[0].plot(e["year"], e["full_output_level_share"] * 100, label="levels at full output (past threshold)", color="#2e8b57")
ax[0].set_ylim(0, 102)
ax[0].legend(fontsize=8)
ax[0].set_title("Run B: establishment state of craft levels (%)")
ax[1].plot(e["year"], e["ramping_buildings"], label="ramping buildings", color="#e08a1e")
ax[1].plot(e["year"], e["locs_at_cap3"], label="locations with >= 3 ramping (AI cap)", color="#c0392b")
ax[1].plot(e["year"], e["idle_buildings"], label="idle craft buildings (0 workers or closed)", color="#7f8c8d")
ax[1].legend(fontsize=8)
ax[1].set_title("Run B: ramping, AI cap, idle")
for a in ax:
    a.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(S / "est_state.png", dpi=100)
print("charts ok")
