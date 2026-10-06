"""Per-good comparison at common years + top centres.  uv run python per_good.py SCRATCH TEST B1 B2 YEAR [YEAR...]"""
import sys
import tomllib
from pathlib import Path

import polars as pl

S = Path(sys.argv[1])
test, b1, b2 = sys.argv[2:5]
years = [int(y) for y in sys.argv[5:]]
D = Path("graphs/dataset/tables")
pl.Config.set_tbl_rows(80)
pl.Config.set_tbl_width_chars(260)
pl.Config.set_tbl_cols(30)
spec = pl.read_parquet(S / "spec_all.parquet")
emp = pl.read_parquet(S / "spec_all_emp.parquet")
for y in years:
    t = spec.filter(pl.col("year") == y)
    te = emp.filter(pl.col("year") == y)
    if t.filter(pl.col("run") == test).height == 0:
        continue
    def pick(df, run, cols, suf):
        return df.filter(pl.col("run") == run).select(["good"] + [pl.col(c).alias(f"{c}_{suf}") for c in cols])
    cols = ["levels", "locations", "top10_loc", "top3_cty", "markets_producing", "exporters"]
    x = pick(t, test, cols, "T").join(pick(t, b1, cols, "B1"), on="good", how="left").join(pick(t, b2, cols, "B2"), on="good", how="left")
    tr = t.with_columns((pl.col("traded") / pl.col("supply")).alias("trade_sh"), (pl.col("pd") / pl.col("dd")).alias("price"))
    x = x.join(pick(tr, test, ["trade_sh", "price", "supply"], "T"), on="good").join(pick(tr, b1, ["trade_sh", "price", "supply"], "B1"), on="good", how="left")
    x = x.join(pick(te, test, ["levels", "top10_loc"], "Temp"), on="good").join(pick(te, b1, ["levels", "top10_loc"], "B1emp"), on="good", how="left")
    print(f"=== {y}")
    print(x.with_columns(pl.col(pl.Float64).round(3)).sort("good"))
    x.write_csv(S / f"per_good_{y}.csv")

# top centres per good in the test run's last common year
y = max(y for y in years if spec.filter((pl.col("year") == y) & (pl.col("run") == test)).height)
lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
TYPE_GOOD = {t: ("weaponry" if g == "weapons" else g) for g, ts in lines.items() for t in ts}
for run in (test, b1):
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={run}/*.parquet")).filter(pl.col("year") == y)
         .filter(pl.col("building_type").is_in(list(TYPE_GOOD))).collect()
         .with_columns(pl.col("building_type").replace_strict(TYPE_GOOD).alias("good")))
    loc = pl.scan_parquet(str(D / f"locations/playthrough_id={run}/*.parquet")).filter(pl.col("year") == y).select("location_id", "slug", "country_tag").collect()
    b = b.join(loc, on="location_id", how="left")
    top = (b.group_by("good", "slug", "country_tag").agg(pl.col("level").sum().alias("lv"), pl.col("employed").sum().alias("emp"))
           .sort("lv", descending=True).group_by("good").head(3).sort("good", "lv", descending=[False, True]))
    print(f"=== top-3 locations per good, {run[:8]}, {y}")
    print(top.select("good", "slug", "country_tag", "lv", pl.col("emp").round(2)))
