"""The biggest craft hubs per good at one year: location, staffed share of the world, levels, and the market's trade.
uv run python hubs.py YEAR RUN (constructor root)"""
import sys
import tomllib
from pathlib import Path

import polars as pl

D = Path("graphs/dataset/tables")
year, run = int(sys.argv[1]), sys.argv[2]
lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
TYPE_GOOD = {t: ("weaponry" if g == "weapons" else g) for g, ts in lines.items() for t in ts}
b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={run}/*.parquet"))
     .filter(pl.col("building_type").is_in(list(TYPE_GOOD)) & (pl.col("year") == year))
     .select("date_sort", "building_type", "location_id", "market_id", "level", "employed").collect())
b = b.filter(pl.col("date_sort") == b["date_sort"].max()).with_columns(
    pl.col("building_type").replace_strict(TYPE_GOOD).alias("good"), pl.col("employed").fill_null(0))
loc = (pl.scan_parquet(str(D / f"locations/playthrough_id={run}/*.parquet")).filter(pl.col("year") == year)
       .select("date_sort", "location_id", "slug", "country_tag").collect())
loc = loc.filter(pl.col("date_sort") == loc["date_sort"].max()).drop("date_sort")
mg = (pl.scan_parquet(str(D / f"market_goods/playthrough_id={run}/*.parquet")).filter(pl.col("year") == year)
      .select("date_sort", "market_id", "market_center_slug", "good_id", "supply", "taken_Trade", "supplied_Trade").collect())
mg = mg.filter(pl.col("date_sort") == mg["date_sort"].max()).drop("date_sort")
g = (b.group_by("good", "location_id", "market_id").agg(pl.col("employed").sum(), pl.col("level").sum())
     .with_columns((pl.col("employed") / pl.col("employed").sum().over("good")).alias("world_share"))
     .sort("employed", descending=True).group_by("good", maintain_order=True).head(2)
     .join(loc, on="location_id", how="left")
     .join(mg, left_on=["market_id", "good"], right_on=["market_id", "good_id"], how="left")
     .with_columns((pl.col("taken_Trade") - pl.col("supplied_Trade")).alias("market_net_export")))
pl.Config.set_tbl_rows(80)
pl.Config.set_tbl_width_chars(220)
print(g.select("good", "slug", "country_tag", "market_center_slug", "level", "world_share", "supply", "market_net_export")
      .with_columns(pl.col(pl.Float64).round(3)).sort("good"))
