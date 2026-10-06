"""Where do the runs differ? Building levels, staffing and profit by building group at matched years.
uv run python wealth_split.py YEAR RUN... (constructor root)"""
import sys
import tomllib
from pathlib import Path

import polars as pl

D = Path("graphs/dataset/tables")
year = int(sys.argv[1])
runs = sys.argv[2:]
lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
CRAFT = {t for ts in lines.values() for t in ts}
cat = pl.scan_parquet(str(D / "building_catalog/**/*.parquet")).collect()
print(cat.columns)
gcol = next((c for c in ("category", "building_category", "group") if c in cat.columns), None)
cmap = cat.select("building_type", gcol).unique("building_type") if gcol else None
rows = []
for r in runs:
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={r}/*.parquet")).filter(pl.col("year") == year)
         .select("date_sort", "building_type", "level", "employed", "last_months_profit").collect())
    b = b.filter(pl.col("date_sort") == b["date_sort"].max())
    if cmap is not None:
        b = b.join(cmap, on="building_type", how="left")
    b = b.with_columns(pl.when(pl.col("building_type").is_in(list(CRAFT))).then(pl.lit("CRAFT"))
                       .otherwise(pl.col(gcol) if gcol else pl.lit("other")).alias("grp"))
    rows.append(b.group_by("grp").agg(pl.col("level").sum().alias("levels"), pl.col("employed").sum().alias("employed"),
                                      pl.col("last_months_profit").sum().alias("profit"))
                .with_columns(pl.lit(r[:8]).alias("run")))
t = pl.concat(rows)
w = t.pivot(on="run", index="grp", values=["levels", "employed", "profit"])
pl.Config.set_tbl_rows(60)
pl.Config.set_tbl_width_chars(250)
print(w.sort(w.columns[-1], descending=True))
# top building types by level difference first run vs last run
bt = []
for r in runs:
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={r}/*.parquet")).filter(pl.col("year") == year)
         .select("date_sort", "building_type", "level", "last_months_profit").collect())
    b = b.filter(pl.col("date_sort") == b["date_sort"].max())
    bt.append(b.group_by("building_type").agg(pl.col("level").sum().alias(f"lv_{r[:8]}"),
                                              pl.col("last_months_profit").sum().alias(f"pr_{r[:8]}")))
j = bt[0].join(bt[-1], on="building_type", how="full", coalesce=True).fill_null(0)
a, c = runs[0][:8], runs[-1][:8]
j = j.with_columns((pl.col(f"lv_{a}") - pl.col(f"lv_{c}")).alias("dlv"), (pl.col(f"pr_{a}") - pl.col(f"pr_{c}")).alias("dpr"))
print("largest level gains", a, "vs", c)
print(j.sort("dlv", descending=True).head(20))
print("largest level losses")
print(j.sort("dlv").head(15))
print("largest profit gains")
print(j.sort("dpr", descending=True).head(15))
