"""Specialization and manufactured-goods trade metrics per run and snapshot (final-goods craft lines).

uv run python spec_metrics.py OUT.parquet RUN_ID [RUN_ID ...]   (from the constructor root, dataset in graphs/dataset)
"""
import sys
import tomllib
from pathlib import Path

import os

import polars as pl

D = Path("graphs/dataset/tables")
out_path = Path(sys.argv[1])
runs = sys.argv[2:]

lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
TYPE_GOOD = {t: ("weaponry" if g == "weapons" else g) for g, ts in lines.items() for t in ts}
GOODS = sorted(set(TYPE_GOOD.values()))


def hhi(col):
    s = pl.col(col) / pl.col(col).sum()
    return (s * s).sum()


rows = []
for run in runs:
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={run}/*.parquet"))
         .filter(pl.col("building_type").is_in(list(TYPE_GOOD)))
         .select("date_sort", "year", "building_id", "building_type", "location_id", "market_id", "level", "employed",
                 "open", "establishment_progress")
         .collect()
         .with_columns(pl.col("building_type").replace_strict(TYPE_GOOD).alias("good"),
                       pl.col("employed").fill_null(0)))
    if os.environ.get("WEIGHT") == "employed":  # staffed capacity instead of standing levels
        b = b.with_columns(pl.col("employed").alias("level"))
    loc = (pl.scan_parquet(str(D / f"locations/playthrough_id={run}/*.parquet"))
           .select("date_sort", "location_id", "country_tag").collect())
    b = b.join(loc, on=["date_sort", "location_id"], how="left")
    # production side, per good and snapshot
    by_loc = b.group_by("date_sort", "year", "good", "location_id").agg(pl.col("level").sum().alias("lv"))
    by_cty = b.group_by("date_sort", "good", "country_tag").agg(pl.col("level").sum().alias("lv"))
    by_mkt = b.group_by("date_sort", "good", "market_id").agg(pl.col("level").sum().alias("lv"))
    g_loc = by_loc.group_by("date_sort", "year", "good").agg(
        pl.col("lv").sum().alias("levels"), pl.len().alias("locations"), hhi("lv").alias("hhi_loc"),
        (pl.col("lv").sort(descending=True).head(10).sum() / pl.col("lv").sum()).alias("top10_loc"),
        (pl.col("lv").sort(descending=True).head(50).sum() / pl.col("lv").sum()).alias("top50_loc"))
    g_cty = by_cty.group_by("date_sort", "good").agg(
        (pl.col("lv").sort(descending=True).head(3).sum() / pl.col("lv").sum()).alias("top3_cty"),
        hhi("lv").alias("hhi_cty"))
    g_mkt = by_mkt.group_by("date_sort", "good").agg(hhi("lv").alias("hhi_mkt"), pl.len().alias("markets_producing"))
    nb = b.group_by("date_sort", "good").agg(pl.len().alias("buildings"))
    g = g_loc.join(g_cty, on=["date_sort", "good"]).join(g_mkt, on=["date_sort", "good"]).join(nb, on=["date_sort", "good"])
    # market specialization: location quotient of each market's craft mix vs the world
    mk = by_mkt.with_columns(
        (pl.col("lv") / pl.col("lv").sum().over("date_sort", "market_id")).alias("share_m"),
        (pl.col("lv").sum().over("date_sort", "good") / pl.col("lv").sum().over("date_sort")).alias("share_w"))
    mk = mk.with_columns((pl.col("share_m") / pl.col("share_w")).alias("lq"))
    spec = mk.group_by("date_sort").agg(
        ((pl.col("lv") * (pl.col("lq") >= 2)).sum() / pl.col("lv").sum()).alias("levels_in_lq2"),
        ((pl.col("lv") * pl.col("lq")).sum() / pl.col("lv").sum()).alias("lq_weighted"))
    # country diversification: effective number of craft goods per country (1/HHI over goods), level weighted
    cd = by_cty.filter(pl.col("country_tag").is_not_null()).with_columns((pl.col("lv") / pl.col("lv").sum().over("date_sort", "country_tag")).alias("s"))
    cd = cd.group_by("date_sort", "country_tag").agg((pl.col("s") ** 2).sum().alias("h"), pl.col("lv").sum().alias("L"))
    cd = cd.group_by("date_sort").agg(((pl.col("L") / pl.col("h")).sum() / pl.col("L").sum()).alias("country_eff_goods"))
    # establishment state
    est = b.filter(pl.col("establishment_progress").is_not_null()).group_by("date_sort").agg(
        (pl.col("level") * (pl.col("employed") < 0.001)).sum().alias("idle_levels"))
    # trade side
    tr = (pl.scan_parquet(str(D / f"trades/playthrough_id={run}/*.parquet")).filter(pl.col("good_id").is_in(GOODS))
          .group_by("date_sort", "good_id").agg(pl.col("size").sum().alias("traded"), pl.len().alias("routes"),
                                                pl.col("from_market").n_unique().alias("exporters")).collect()
          .rename({"good_id": "good"}))
    mg = (pl.scan_parquet(str(D / f"market_goods/playthrough_id={run}/*.parquet")).filter(pl.col("good_id").is_in(GOODS))
          .group_by("date_sort", "good_id").agg(pl.col("supply").sum().alias("supply"),
                                                pl.col("supplied_Production").sum().alias("produced"),
                                                pl.col("supplied_Trade").sum().alias("imported"),
                                                (pl.col("price") * pl.col("demand")).sum().alias("pd"),
                                                (pl.col("default_price") * pl.col("demand")).sum().alias("dd"))
          .collect().rename({"good_id": "good"}))
    g = g.join(tr, on=["date_sort", "good"], how="left").join(mg, on=["date_sort", "good"], how="left")
    g = g.join(spec, on="date_sort", how="left").join(cd, on="date_sort", how="left").join(est, on="date_sort", how="left")
    rows.append(g.with_columns(pl.lit(run).alias("run")))

res = pl.concat(rows, how="diagonal")
res.write_parquet(out_path)
summ = res.group_by("run", "year").agg(
    pl.col("levels").sum().alias("craft_levels"), pl.col("buildings").sum(),
    ((pl.col("top10_loc") * pl.col("levels")).sum() / pl.col("levels").sum()).round(3).alias("top10_loc"),
    ((pl.col("top3_cty") * pl.col("levels")).sum() / pl.col("levels").sum()).round(3).alias("top3_cty"),
    ((pl.col("hhi_mkt") * pl.col("levels")).sum() / pl.col("levels").sum()).round(4).alias("hhi_mkt"),
    pl.col("levels_in_lq2").first().round(3), pl.col("country_eff_goods").first().round(2),
    (pl.col("traded").sum() / pl.col("supply").sum()).round(3).alias("trade_share"),
    (pl.col("imported").sum() / pl.col("supply").sum()).round(3).alias("import_share"),
    (pl.col("pd").sum() / pl.col("dd").sum()).round(3).alias("price_idx"),
).sort("run", "year")
pl.Config.set_tbl_rows(200)
pl.Config.set_tbl_width_chars(220)
print(summ.filter((pl.col("year") - 1342) % 40 == 0).drop("buildings"))
