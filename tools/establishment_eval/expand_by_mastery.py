"""Does the AI expand mastered workshops more? 5-year expansion rate of standing craft buildings by mastery state.
uv run python expand_by_mastery.py TARGETS_DIR YMAX RUN... (constructor root)"""
import re
import sys
import tomllib
from pathlib import Path

import polars as pl

D = Path("graphs/dataset/tables")
tdir, ymax, runs = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
TYPE_GOOD = {t: ("weaponry" if g == "weapons" else g) for g, ts in lines.items() for t in ts}
TARGET = {t: float(re.search(r"startup_ramp_target = (\d+)", (tdir / f"blueprints/accepted/buildings/{t}.yml").read_text())
                   .group(1)) for t in TYPE_GOOD}
out = []
for run in runs:
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={run}/*.parquet"))
         .filter(pl.col("building_type").is_in(list(TYPE_GOOD)) & (pl.col("year") <= ymax))
         .select("date_sort", "year", "building_id", "building_type", "level", "employed", "employment", "last_months_profit",
                 "establishment_progress").collect()
         .with_columns((pl.col("establishment_progress").fill_null(0) / pl.col("building_type").replace_strict(TARGET))
                       .clip(0, 1).alias("f")))
    snaps = b.select("date_sort").unique().sort("date_sort")["date_sort"].to_list()
    for d0, d1 in zip(snaps, snaps[1:]):
        x = b.filter(pl.col("date_sort") == d0)
        y = b.filter(pl.col("date_sort") == d1).select("building_id", pl.col("level").alias("lv1"))
        out.append(x.join(y, on="building_id", how="left").with_columns(pl.lit(run[:8]).alias("run")))
t = pl.concat(out).with_columns(
    pl.when(pl.col("f") >= 0.999).then(pl.lit("3 mastered")).when(pl.col("f") >= 0.333).then(pl.lit("2 full, learning"))
    .otherwise(pl.lit("1 ramping")).alias("state"),
    (pl.col("lv1").fill_null(0) - pl.col("level")).alias("dl"),
    (pl.col("employed") / pl.col("employment").clip(1e-9, None)).clip(0, 1).alias("staffing"),
    (pl.col("last_months_profit") / pl.col("level")).alias("ppl"))
t = t.filter(pl.col("employed").fill_null(0) > 0)  # working buildings only
t = t.with_columns(pl.col("ppl").qcut(4, labels=["p1 low", "p2", "p3", "p4 high"], allow_duplicates=True).alias("profit_q"))
pl.Config.set_tbl_rows(80)
pl.Config.set_tbl_width_chars(200)
agg = [pl.len().alias("n"), (pl.col("dl") > 0).mean().round(3).alias("p_expand_5y"), pl.col("dl").clip(0, None).mean().round(3).alias("levels_added"),
       pl.col("lv1").is_null().mean().round(3).alias("p_gone"), pl.col("ppl").median().round(3).alias("profit_per_level")]
print(t.group_by("run", "state").agg(*agg).sort("run", "state"))
print(t.group_by("run", "profit_q", "state").agg(*agg).sort("run", "profit_q", "state"))
