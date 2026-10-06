"""Establishment + construction dynamics of the craft lines per run and 5-year step.

uv run python est_metrics.py OUT.parquet TARGETS_DIR RUN_ID [RUN_ID ...]   (constructor root)
TARGETS_DIR: a constructor checkout whose blueprints carry the branch's startup_ramp_target values.
"""
import re
import sys
import tomllib
from pathlib import Path

import polars as pl

D = Path("graphs/dataset/tables")
out_path = Path(sys.argv[1])
tdir = Path(sys.argv[2])
runs = sys.argv[3:]
lines = tomllib.loads(Path("constructor.toml").read_text())["legacy_methods"]["lines"]
lines["jewelry"] = ["jewelry_guild"]
for g in ("dyes", "paper", "saltpeter"):
    lines.pop(g)
TYPE_GOOD = {t: ("weaponry" if g == "weapons" else g) for g, ts in lines.items() for t in ts}
TARGET = {}
for t in TYPE_GOOD:
    m = re.search(r"startup_ramp_target = (\d+)", (tdir / f"blueprints/accepted/buildings/{t}.yml").read_text())
    TARGET[t] = float(m.group(1)) if m else 0.0

rows = []
for run in runs:
    b = (pl.scan_parquet(str(D / f"buildings/playthrough_id={run}/*.parquet"))
         .filter(pl.col("building_type").is_in(list(TYPE_GOOD)))
         .select("date_sort", "year", "building_id", "building_type", "location_id", "level", "employed", "open",
                 "establishment_progress")
         .collect()
         .with_columns(pl.col("building_type").replace_strict(TARGET).alias("target"),
                       pl.col("employed").fill_null(0), pl.col("open").fill_null(True)))
    b = b.with_columns((pl.col("establishment_progress").fill_null(0) / pl.col("target")).clip(0, 1).alias("f"))
    snaps = b.select("date_sort", "year").unique().sort("date_sort")
    prev = None
    for ds, yr in snaps.iter_rows():
        cur = b.filter(pl.col("date_sort") == ds)
        ramping = cur.filter((pl.col("f") < 0.999) & pl.col("open") & (pl.col("level") >= 1))
        per_loc = ramping.group_by("location_id").len()
        r = {"run": run, "year": yr, "levels": cur["level"].sum(), "buildings": cur.height,
             "mastered_level_share": float((cur["level"] * (cur["f"] >= 0.999)).sum() / max(cur["level"].sum(), 1)),
             "full_output_level_share": float((cur["level"] * (cur["f"] >= 0.333)).sum() / max(cur["level"].sum(), 1)),
             "ramping_buildings": ramping.height, "locs_at_cap3": int((per_loc["len"] >= 3).sum()),
             "idle_buildings": int(((cur["employed"] < 0.001) | ~cur["open"]).sum()),
             "levels_per_building": float(cur["level"].sum() / max(cur.height, 1))}
        if prev is not None:
            j = cur.join(prev.select("building_id", pl.col("level").alias("lv0")), on="building_id", how="left")
            new = j.filter(pl.col("lv0").is_null())
            gone = prev.join(cur.select("building_id"), on="building_id", how="anti")
            r.update({"new_buildings": new.height, "new_levels": float(new["level"].sum()),
                      "expansion_levels": float((j["level"] - j["lv0"]).clip(0, None).fill_null(0).sum()),
                      "gone_buildings": gone.height, "gone_levels": float(gone["level"].sum()),
                      "gone_idle_before": int(((gone["employed"] < 0.001) | ~gone["open"]).sum())})
        rows.append(r)
        prev = cur
res = pl.DataFrame(rows)
res.write_parquet(out_path)
pl.Config.set_tbl_rows(200)
pl.Config.set_tbl_width_chars(250)
pl.Config.set_tbl_cols(30)
print(res.filter((pl.col("year") - 1342) % 20 == 0).with_columns(pl.col(pl.Float64).round(3)))
