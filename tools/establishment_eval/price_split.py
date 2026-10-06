"""Price level and supply per good, run A vs run B at one year.  uv run python price_split.py YEAR RUN_A RUN_B"""
import sys
from pathlib import Path

import polars as pl

D = Path("graphs/dataset/tables")
year, ra, rb = int(sys.argv[1]), sys.argv[2], sys.argv[3]
print(pl.scan_parquet(str(D / f"market_goods/playthrough_id={ra}/*.parquet")).collect_schema().names())


def load(r):
    m = pl.scan_parquet(str(D / f"market_goods/playthrough_id={r}/*.parquet")).select("year", "date_sort", "good_id", "goods_category", "price", "default_price", "supply").filter(pl.col("year") == year).collect()
    m = m.filter(pl.col("date_sort") == m["date_sort"].max())
    sup = next(c for c in ("supply", "total_supply") if c in m.columns)
    return m.group_by("good_id").agg(pl.col(sup).sum().alias("supply"),
                                     ((pl.col("price") * pl.col(sup)).sum() / pl.col(sup).sum()).alias("price"),
                                     pl.col("default_price").first().alias("dp"), pl.col("goods_category").first().alias("cat"))


a, b = load(ra), load(rb)
j = a.join(b, on="good_id", suffix="_b").with_columns(
    (pl.col("supply") / pl.col("supply_b") - 1).alias("supply_vs"), (pl.col("price") / pl.col("price_b") - 1).alias("price_vs"),
    ((pl.col("supply") * pl.col("price")) - (pl.col("supply_b") * pl.col("price_b"))).alias("dvalue"))
pl.Config.set_tbl_rows(80)
pl.Config.set_tbl_width_chars(200)
print("total value", (j["supply"] * j["price"]).sum(), (j["supply_b"] * j["price_b"]).sum())
print(j.sort("dvalue", descending=True).select("good_id", "supply", "supply_b", "supply_vs", "price", "price_b", "price_vs",
                                              "dvalue").with_columns(pl.col(pl.Float64).round(3)))
print(j.group_by("cat").agg((pl.col("supply") * pl.col("price")).sum().alias("value"), (pl.col("supply_b") * pl.col("price_b")).sum().alias("value_b"),
                            ((pl.col("price") * pl.col("supply_b")).sum() / (pl.col("price_b") * pl.col("supply_b")).sum() - 1).alias("price_index_vs"),
                            (pl.col("supply") / pl.col("supply_b")).median().alias("supply_ratio_p50")))
