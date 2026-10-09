"""Food page data of the run report: how food reaches the province stores and where it goes.

The saves keep every province food pool (province + owner) with its stock, capacity, monthly change, structural
change (food made - food eaten) and base consumption (engine table `province_food`, kept in the run dataset since
eu5-game-parser 0c7d87f). So per pool, exactly:

    made = structural change + consumption        spoilage (and overflow at the cap) = structural - monthly change

The engine adds a location's food as (flat food + subsistence + Province Food from buildings) x (1 + food modifiers).
The save does not split it, so every source gets an estimate and the estimates are fitted to the exact total per pool:

- subsistence: SUBSISTENCE_RATE per 1,000 idle peasants and slaves;
- RGOs: the `rgo_level` static modifier's `local_monthly_food` per RGO level (the location's RGO size);
- Province Food (`local_food`) from buildings: the active methods' output per level x levels x staffing (farms'
  Provisioning, Taverns' Serve Victuals and Common Table);
- flat building food: the building's `local_monthly_food` x levels x staffing (farms' per-level food, Cookshops 15,
  Public Kitchens 18; Granges -24, which is how a Grange takes food from the store to pack victuals).

One factor per pool (made / estimate, kept within FACTOR_LIMITS) scales them; it stands for the pool's food modifiers.
What the fit cannot place is "Other sources" (base food, foraging, static modifiers) or "Unexplained loss".
Consumption is split by pop type with the pop types' `pop_food_consumption`.

Written next to the goods data (the page reads both; building, method, region and good indices are the goods
page's): `food/index.json`, `food/<n>.json` per save (pools, makers per world region, consumption per pop type,
food buildings), `food/summary.json` (world and region series over the run) and `food/provinces.json` (series per
province, loaded when one province is opened).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import polars as pl

from prosper_or_perish_constructor.run_report_charts import land_region_expr, titleize

if TYPE_CHECKING:
    from prosper_or_perish_constructor.run_report import MapCanvas, RunData
    from prosper_or_perish_constructor.run_report_goods import Index, Recipes

CACHE_VERSION = "food-2"
FOOD_GOOD = "local_food"
SUBSISTENCE_RATE = 1.487  # food per month per 1,000 idle peasants or slaves (decompiled, memory location-food-production-formula)
FACTOR_LIMITS = (0.25, 4.0)
POP_TYPES = ("nobles", "clergy", "burghers", "laborers", "soldiers", "peasants", "slaves", "tribesmen")
# where food comes from (display order): key, label, colour
CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("subsistence", "Subsistence", "#9c7a3c"),
    ("rgos", "RGOs", "#c98a00"),
    ("farms", "Farms, fisheries & orchards", "#1baf7a"),
    ("kitchens", "Cookshops & kitchens", "#e8692e"),
    ("taverns", "Taverns", "#2a78d6"),
    ("other", "Other sources", "#9a9a96"),
)
KITCHENS = frozenset({"cookshop", "public_kitchen"})
TAVERNS = frozenset({"tavern", "pirate_tavern"})
# food buildings that neither make nor take store food but belong in the food buildings table
FOOD_BUILDINGS_EXTRA = frozenset({"victualling_yard", "granary", "village_granary", "fortress_granary", "grange"})
MONTH_BANDS = (0.0, 3.0, 6.0, 12.0, 18.0, 24.0)  # people by months stored: [0,3) [3,6) [6,12) [12,18) [18,24) [24,..)
POOL_COLUMNS = ("province", "country", "region", "pop", "stock", "cap", "change", "structural", "base", "spoil", "sub",
                "rgos", "farms", "kitchens", "taverns", "other", "taken", "unexplained", "factor", "growth_storage", "growth_surplus")
FLOW_TABLES = ("pools", "makers", "takers", "eat", "buildings", "locations")


def category_of(building: str | None) -> str:
    if building in KITCHENS:
        return "kitchens"
    if building in TAVERNS:
        return "taverns"
    return "farms"


class FoodRecipes:
    """Province Food methods, flat building food and pop food rates of the parser profile."""

    def __init__(self, recipes: Recipes, repo: Path, project: Path):
        from eu5gameparser.clausewitz.syntax import CList
        from eu5gameparser.load_order import load_merged_directory, load_profile

        from prosper_or_perish_constructor.free_building_levels import resolve_parser_config

        config = resolve_parser_config(repo, project)
        profile = load_profile(str(config.get("profile") or "constructor"),
                               repo / str(config.get("load_order") or "constructor.load_order.toml"))
        self.methods = recipes.outputs.filter(pl.col("good_id") == FOOD_GOOD).select("method", "per_level")
        self.workers = recipes.workers
        flat: dict[str, float] = {}
        for entry in load_merged_directory(profile, "building_types", scope="in_game").entries:
            if not isinstance(entry.value, CList):
                continue
            total = 0.0
            for block_key in ("modifier", "raw_modifier"):
                block = entry.value.first(block_key)
                value = block.first("local_monthly_food") if isinstance(block, CList) else None
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    total += float(value)
            if total:
                flat[entry.key] = total
        self.flat = pl.DataFrame({"building_type": list(flat), "flat": list(flat.values())},
                                 schema={"building_type": pl.String, "flat": pl.Float64})
        # flat food per RGO level: the rgo_level static modifier (main_menu)
        self.rgo_food = 0.0
        for entry in load_merged_directory(profile, "static_modifiers", scope="main_menu").entries:
            if entry.key == "rgo_level" and isinstance(entry.value, CList):
                value = entry.value.first("local_monthly_food")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.rgo_food = float(value)
        self.rates: dict[str, float] = {}
        for entry in load_merged_directory(profile, "pop_types", scope="in_game").entries:
            value = entry.value.first("pop_food_consumption") if isinstance(entry.value, CList) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self.rates[entry.key] = float(value)
        self.food_buildings = set(flat) | FOOD_BUILDINGS_EXTRA | {
            recipes.method_building.get(m) for m in self.methods["method"].to_list() if recipes.method_building.get(m)}
        digest = hashlib.sha1()
        digest.update(recipes.digest.encode())
        digest.update(self.flat.sort("building_type").write_csv().encode())
        digest.update(json.dumps({**self.rates, "_rgo": self.rgo_food}, sort_keys=True).encode())
        self.digest = digest.hexdigest()[:12]


# --------------------------------------------------------------------------------------------------------
# One save


def save_food(dataset: Path, playthrough: str, snapshot: str, food: FoodRecipes) -> dict[str, pl.DataFrame] | None:
    """Pools, makers and takers per region, consumption per pop type, food buildings and months per location of one
    save; None when the save has no province food table."""
    from prosper_or_perish_constructor.run_report_goods import OTHER_REGION, _read

    def read(table: str, columns: list[str]) -> pl.DataFrame:
        return _read(dataset, table, playthrough, snapshot, columns)

    pf = read("province_food", ["province_id", "max_food_value", "food_current", "cached_food_change",
                                "cached_structural_food_change", "base_food_consumption", "food_storage_growth_term",
                                "food_surplus_growth_term"])
    if pf.is_empty():
        return None
    pf = pf.with_columns(pl.exclude("province_id").cast(pl.Float64).fill_null(0.0))
    locations = read("locations", ["location_id", "slug", "province", "province_slug", "country_tag", "macro_region",
                                   "super_region", "total_population", "unemployed_peasants", "unemployed_slaves", "max_raw_material_workers",
                                   *[f"population_{p}" for p in POP_TYPES]])
    numeric = ["total_population", "unemployed_peasants", "unemployed_slaves", "max_raw_material_workers",
               *[f"population_{p}" for p in POP_TYPES]]
    locations = locations.filter(pl.col("province").is_not_null()).with_columns(
        pl.col(numeric).cast(pl.Float64).fill_null(0.0),
        pl.when(land_region_expr()).then(pl.col("macro_region")).otherwise(pl.lit(OTHER_REGION)).alias("region"))

    # pools: region and owner of the most populous location
    pools = (
        locations.sort("total_population", descending=True)
        .group_by("province", maintain_order=True)
        .agg(pl.col("province_slug").first().alias("slug"), pl.col("country_tag").first().alias("tag"), pl.col("region").first(),
             pl.col("total_population").sum().alias("pop"),
             (pl.col("unemployed_peasants") + pl.col("unemployed_slaves")).sum().alias("idle"),
             pl.col("max_raw_material_workers").sum().alias("rgo_levels"),
             *[pl.col(f"population_{p}").sum().alias(p) for p in POP_TYPES])
        .rename({"province": "province_id"})
        .join(pf, on="province_id", how="inner")
    )

    # food buildings: recipe estimates per pool
    buildings = read("buildings", ["building_id", "building_type", "location_id", "level", "employed", "last_months_profit"])
    methods = read("building_methods", ["building_id", "production_method"]).rename({"production_method": "method"})
    staffed = (
        buildings.filter(pl.col("level") > 0)
        .join(food.workers, on="building_type", how="left")
        .join(locations.select("location_id", pl.col("province").alias("province_id"), "region"), on="location_id", how="inner")
        .with_columns(
            pl.when(pl.col("workers_per_level") > 0)
            .then((pl.col("employed").fill_null(0.0) / (pl.col("level") * pl.col("workers_per_level"))).clip(0.0, 1.0))
            .otherwise(1.0).alias("staffing"))
    )
    made = methods.join(staffed, on="building_id").join(food.methods, on="method").with_columns(
        (pl.col("per_level") * pl.col("level") * pl.col("staffing")).alias("food"))
    flat = staffed.join(food.flat, on="building_type").with_columns(
        (pl.col("flat") * pl.col("level") * pl.col("staffing")).alias("food"), pl.lit(None, dtype=pl.String).alias("method"))
    parts = ["province_id", "region", "building_type", "method", "food"]
    comps = pl.concat([made.select(parts), flat.select(parts)]).filter(pl.col("food") != 0)

    est = comps.group_by("province_id").agg(pl.col("food").filter(pl.col("food") > 0).sum().alias("pos"),
                                            pl.col("food").filter(pl.col("food") < 0).sum().alias("neg"))
    low, high = FACTOR_LIMITS
    pools = (
        pools.join(est, on="province_id", how="left")
        .with_columns(pl.col("pos", "neg").fill_null(0.0))
        .with_columns(
            (pl.col("cached_structural_food_change") + pl.col("base_food_consumption")).clip(lower_bound=0.0).alias("made"),
            (pl.col("idle") * SUBSISTENCE_RATE).alias("sub_est"), (pl.col("rgo_levels") * food.rgo_food).alias("rgo_est"))
        .with_columns((pl.col("sub_est") + pl.col("rgo_est") + pl.col("pos") + pl.col("neg")).alias("estimate"))
        .with_columns(pl.when(pl.col("estimate") > 0).then((pl.col("made") / pl.col("estimate")).clip(low, high)).otherwise(1.0).alias("factor"))
        .with_columns((pl.col("made") - pl.col("factor") * pl.col("estimate")).alias("residual"))
    )
    scaled = comps.join(pools.select("province_id", "factor"), on="province_id").with_columns(
        (pl.col("food") * pl.col("factor")).alias("food"),
        pl.col("building_type").map_elements(category_of, return_dtype=pl.String).alias("category"))
    by_category = scaled.filter(pl.col("food") > 0).group_by("province_id").agg(
        *[pl.col("food").filter(pl.col("category") == c).sum().alias(c) for c in ("farms", "kitchens", "taverns")])
    taken = scaled.filter(pl.col("food") < 0).group_by("province_id").agg((-pl.col("food").sum()).alias("taken"))
    pools = (
        pools.join(by_category, on="province_id", how="left").join(taken, on="province_id", how="left")
        .with_columns(pl.col("farms", "kitchens", "taverns", "taken").fill_null(0.0))
        .with_columns(
            (pl.col("sub_est") * pl.col("factor")).alias("sub"),
            (pl.col("rgo_est") * pl.col("factor")).alias("rgos"),
            pl.col("residual").clip(lower_bound=0.0).alias("other"),
            (-pl.col("residual")).clip(lower_bound=0.0).alias("unexplained"),
            (pl.col("cached_structural_food_change") - pl.col("cached_food_change")).clip(lower_bound=0.0).alias("spoil"))
        .rename({"food_current": "stock", "max_food_value": "cap", "cached_food_change": "change",
                 "cached_structural_food_change": "structural", "base_food_consumption": "base",
                 "food_storage_growth_term": "growth_storage", "food_surplus_growth_term": "growth_surplus"})
    )

    makers = scaled.filter(pl.col("food") > 0).group_by("region", "category", "building_type", "method").agg(pl.col("food").sum())
    makers = pl.concat([
        makers,
        pools.group_by("region").agg(pl.col("sub").sum().alias("food")).with_columns(
            pl.lit("subsistence").alias("category"), pl.lit(None, dtype=pl.String).alias("building_type"), pl.lit(None, dtype=pl.String).alias("method")),
        pools.group_by("region").agg(pl.col("rgos").sum().alias("food")).with_columns(
            pl.lit("rgos").alias("category"), pl.lit(None, dtype=pl.String).alias("building_type"), pl.lit(None, dtype=pl.String).alias("method")),
        pools.group_by("region").agg(pl.col("other").sum().alias("food")).with_columns(
            pl.lit("other").alias("category"), pl.lit(None, dtype=pl.String).alias("building_type"), pl.lit(None, dtype=pl.String).alias("method")),
    ], how="diagonal_relaxed").filter(pl.col("food") > 0)
    takers = scaled.filter(pl.col("food") < 0).group_by("region", "building_type").agg((-pl.col("food").sum()).alias("food"))

    # consumption by pop type, scaled to each pool's exact consumption
    weight = sum(pl.col(p) * food.rates.get(p, 0.0) for p in POP_TYPES)
    eat = (
        pools.with_columns(weight.alias("_w"))
        .select("region", *[(pl.when(pl.col("_w") > 0).then(pl.col(p) * food.rates.get(p, 0.0) / pl.col("_w")).otherwise(0.0)
                             * pl.col("base")).alias(p) for p in POP_TYPES])
        .unpivot(index="region", variable_name="pop_type", value_name="food")
        .group_by("region", "pop_type").agg(pl.col("food").sum())
        .filter(pl.col("food") > 0)
    )
    food_buildings = (
        staffed.filter(pl.col("building_type").is_in(sorted(food.food_buildings)))
        .group_by("region", "building_type")
        .agg(pl.col("level").sum().alias("levels"), pl.len().alias("count"), pl.col("employed").fill_null(0.0).sum().alias("workers"),
             pl.col("last_months_profit").cast(pl.Float64).fill_null(0.0).sum().alias("profit"))
    )
    months = pools.select("province_id", pl.when(pl.col("base") > 0).then(pl.col("stock") / pl.col("base")).alias("months"))
    location_months = locations.select("slug", pl.col("province").alias("province_id")).join(months, on="province_id").select("slug", "months")
    keep = ["province_id", "slug", "tag", "region", "pop", "stock", "cap", "change", "structural", "base", "spoil", "made", "sub",
            "rgos", "farms", "kitchens", "taverns", "other", "taken", "unexplained", "factor", "growth_storage", "growth_surplus"]
    return {"pools": pools.select(keep), "makers": makers, "takers": takers, "eat": eat, "buildings": food_buildings,
            "locations": location_months}


# --------------------------------------------------------------------------------------------------------
# Page data


def _band(months: float | None) -> int | None:
    if months is None or not np.isfinite(months):
        return None
    return int(np.searchsorted(MONTH_BANDS, months, side="right") - 1)


def encode_food(flows: dict[str, pl.DataFrame], index: Index, provinces: Index) -> dict[str, list[list[Any]]]:
    from prosper_or_perish_constructor.run_report_goods import _sig

    of = index.of
    categories = {k: i for i, (k, _, _) in enumerate(CATEGORIES)}
    pops = {p: i for i, p in enumerate(POP_TYPES)}
    pools = [[provinces.of("province", r["slug"]), provinces.of("country", r["tag"]), of("region", r["region"]), _sig(r["pop"]),
              *[_sig(r[c]) for c in ("stock", "cap", "change", "structural", "base", "spoil", "sub", "rgos", "farms", "kitchens", "taverns",
                                    "other", "taken", "unexplained")], _sig(r["factor"], 3), _sig(r["growth_storage"], 3),
              _sig(r["growth_surplus"], 3)]
             for r in flows["pools"].iter_rows(named=True)]
    makers = [[of("region", r["region"]), categories[r["category"]], of("building", r["building_type"]), of("method", r["method"]), _sig(r["food"])]
              for r in flows["makers"].iter_rows(named=True)]
    takers = [[of("region", r["region"]), of("building", r["building_type"]), _sig(r["food"])] for r in flows["takers"].iter_rows(named=True)]
    eat = [[of("region", r["region"]), pops[r["pop_type"]], _sig(r["food"])] for r in flows["eat"].iter_rows(named=True)]
    buildings = [[of("region", r["region"]), of("building", r["building_type"]), _sig(r["levels"]), r["count"], _sig(r["workers"], 3),
                  _sig(r["profit"])] for r in flows["buildings"].iter_rows(named=True)]
    return {"pools": pools, "makers": makers, "takers": takers, "eat": eat, "buildings": buildings}


def _series_row(pools: pl.DataFrame) -> dict[str, Any]:
    """World or region figures of one save for the charts over the run."""
    sums = pools.select(pl.col("pop", "stock", "cap", "made", "base", "spoil", "taken", "change", "sub", "rgos", "farms", "kitchens",
                               "taverns", "other").sum()).row(0, named=True)
    months = pools.with_columns(pl.when(pl.col("base") > 0).then(pl.col("stock") / pl.col("base")).alias("months"))
    bands = [0.0] * len(MONTH_BANDS)
    for value, people in months.select("months", "pop").iter_rows():
        band = _band(value)
        if band is not None:
            bands[band] += people or 0.0
    sums["bands"] = bands
    sums["months"] = sums["stock"] / sums["base"] if sums["base"] else None
    return sums


def build_food_data(run: RunData, dataset: Path, out: Path, food: FoodRecipes, index: Index, *, cache: Path | None = None,
                    log: Callable[[str], None] = print) -> dict[str, Any] | None:
    from prosper_or_perish_constructor.run_report_goods import Index as IndexClass
    from prosper_or_perish_constructor.run_report_goods import OTHER_REGION, _sig

    folder = out / "food"
    folder.mkdir(parents=True, exist_ok=True)
    provinces = IndexClass()
    provinces.lists.update({"province": [], "country": []})
    provinces.maps.update({"province": {}, "country": {}})
    saves, world, regions, per_province, map_frames = [], [], {}, {}, []
    snapshots = run.snapshots.select("snapshot_id", "year", "date").to_dicts()
    for n, snap in enumerate(snapshots):
        snapshot = snap["snapshot_id"]
        cached = cache / f"{snapshot}.{food.digest}.{CACHE_VERSION}" if cache else None
        flows = None
        if cached and (cached / "done").is_file():
            try:
                flows = {k: pl.read_parquet(cached / f"{k}.parquet") for k in FLOW_TABLES}
            except (OSError, pl.exceptions.PolarsError):
                flows = None
        if flows is None:
            flows = save_food(dataset, run.playthrough_id, snapshot, food)
            if flows is not None and cached:
                cached.mkdir(parents=True, exist_ok=True)
                for k in FLOW_TABLES:
                    flows[k].write_parquet(cached / f"{k}.parquet")
                (cached / "done").write_text("", encoding="utf-8")
        if flows is None:
            saves.append(None)
            world.append(None)
            map_frames.append(None)
            continue
        name = f"food/{n:03d}.json"
        (out / name).write_text(json.dumps(encode_food(flows, index, provinces), separators=(",", ":"), allow_nan=False), encoding="utf-8")
        saves.append(name)
        pools = flows["pools"]
        world.append(_series_row(pools))
        for (region,), part in pools.partition_by("region", as_dict=True).items():
            regions.setdefault(region, {})[n] = _series_row(part)
        for slug, part in pools.partition_by("slug", as_dict=True).items():
            sums = part.select(pl.col("stock", "cap", "made", "base").sum()).row(0, named=True)
            per_province.setdefault(slug[0], {})[n] = sums
        map_frames.append(flows["locations"])
    have = [i for i, s in enumerate(saves) if s]
    if not have:
        return None
    log(f"food page: {len(have)} saves")

    count = len(snapshots)

    def series(rows: list[dict[str, Any] | None]) -> dict[str, Any]:
        out_rows: dict[str, Any] = {}
        for key in ("pop", "stock", "cap", "made", "base", "spoil", "taken", "change", "sub", "rgos", "farms", "kitchens", "taverns", "other",
                    "months"):
            out_rows[key] = [None if r is None else _sig(r[key]) for r in rows]
        out_rows["bands"] = [[None if r is None else _sig(r["bands"][b]) for r in rows] for b in range(len(MONTH_BANDS))]
        return out_rows

    summary = {"world": series(world),
               "regions": {str(index.of("region", region)): series([rows.get(i) for i in range(count)])
                           for region, rows in regions.items()}}
    (folder / "summary.json").write_text(json.dumps(summary, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    province_series = {}
    for slug, rows in per_province.items():
        def col(key: str) -> list[Any]:
            return [None if i not in rows else _sig(rows[i][key]) for i in range(count)]
        months = [None if i not in rows or not rows[i]["base"] else _sig(rows[i]["stock"] / rows[i]["base"], 3) for i in range(count)]
        province_series[str(provinces.of("province", slug))] = {"months": months, "stock": col("stock"), "cap": col("cap"),
                                                                "made": col("made"), "eaten": col("base")}
    (folder / "provinces.json").write_text(json.dumps(province_series, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    for region in regions:
        index.of("region", region)
    index.of("region", OTHER_REGION)
    return {"saves": saves, "provinces": provinces, "map": map_frames}


def food_index_payload(run: RunData, built: dict[str, Any], food: FoodRecipes) -> dict[str, Any]:
    labels = run.labels
    provinces: Index = built["provinces"]

    def province_name(slug: str) -> str:
        return labels._text(slug) or titleize(slug.removesuffix("_province"))

    names = {t: n for t, n in run.countries.select("country_tag", "country_name").unique("country_tag").iter_rows()} if not run.countries.is_empty() else {}
    return {
        "saves": built["saves"],
        "provinces": [province_name(s) for s in provinces.lists["province"]],
        "countries": [labels.country(t, names.get(t)) if t else "" for t in provinces.lists["country"]],
        "categories": [{"id": k, "name": label, "color": colour} for k, label, colour in CATEGORIES],
        "popTypes": [{"id": p, "name": titleize(p), "rate": food.rates.get(p)} for p in POP_TYPES],
        "bands": list(MONTH_BANDS),
        "poolColumns": list(POOL_COLUMNS),
        "foodGood": FOOD_GOOD,
    }


# --------------------------------------------------------------------------------------------------------
# Map video: months stored per location


MONTHS_RAMP = ("#8f1f1f", "#d9534f", "#eda100", "#d8c9c6", "#6da7ec", "#184f95")


def render_food_map(run: RunData, canvas: MapCanvas, out: Path, frames: list[pl.DataFrame | None], *, fps: int,
                    log: Callable[[str], None] = print) -> dict[str, str] | None:
    """One video: the months of food each location's province store holds (stock / monthly consumption)."""
    import time

    from PIL import Image

    from prosper_or_perish_constructor import run_report as rr

    if not any(f is not None for f in frames):
        return None
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    scale = rr.Scale("linear", 0.0, 24.0, rr._ramp(MONTHS_RAMP),
                     [(0.0, "0"), (3.0, "3"), (6.0, "6"), (12.0, "12"), (18.0, "18"), (24.0, "24 months")])
    composer = rr.FrameComposer(canvas, "Food stores", "Months of food in each province's store", scale)
    duration = run.snapshots.height / fps
    video = out / "food_months.mp4"
    writer = rr.VideoWriter(video, composer.width, composer.height, fps, int(rr.MAX_VIDEO_BYTES * 8 / 1000 / (duration + 2.0)))
    world = run.locations.group_by("snapshot_id").agg(pl.col("total_population").sum().alias("population"))
    people = dict(world.iter_rows())
    last = None
    for snap, frame in zip(run.snapshots.to_dicts(), frames):
        values = frame.rename({"months": "value"}) if frame is not None else pl.DataFrame(schema={"slug": pl.String, "value": pl.Float64})
        rgb = scale.colours(rr._values_array(canvas, values.with_columns(pl.col("value").clip(0.0, 24.0))))
        median = values["value"].drop_nulls().median() if values.height else None
        composer_frame = composer.compose(rr._paint(canvas, rgb), str(snap.get("year") or ""),
                                          [("population", rr._format_number(float(people.get(snap["snapshot_id"]) or 0) * 1000)),
                                           ("median months", "–" if median is None else f"{median:.1f}")])
        writer.write(composer_frame)
        last = composer_frame
    if last is not None:
        writer.write(last, repeat=2 * fps)
        Image.frombytes("RGB", (composer.width, composer.height), last).save(out / "food_months.png", optimize=True)
    writer.close()
    log(f"map food_months: {run.snapshots.height} frames, {video.stat().st_size / 1e6:.1f} MB, {time.perf_counter() - started:.1f}s")
    return {"key": "food_months", "title": "Food stores", "subtitle": "Months of food in each province's store",
            "video": "maps/food_months.mp4", "poster": "maps/food_months.png"}


def write_food(run: RunData, out: Path, *, repo: Path, project: Path, dataset: Path, recipes: Recipes, index: Index,
               canvas: MapCanvas | None = None, fps: int = 6, cache: Path | None = None,
               log: Callable[[str], None] = print) -> Path | None:
    """Food data, map video and page; None when the run's dataset has no province food."""
    food = FoodRecipes(recipes, repo, project)
    built = build_food_data(run, dataset, out, food, index, cache=cache, log=log)
    if built is None:
        log("food page: no province food in the dataset; skipped")
        return None
    payload = food_index_payload(run, built, food)
    if canvas is not None:
        video = render_food_map(run, canvas, out / "maps", built["map"], fps=fps, log=log)
        payload["video"] = video
    (out / "food" / "index.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    from prosper_or_perish_constructor.run_report_food_page import food_page_html

    path = out / "food.html"
    path.write_text(food_page_html(run.name, run.years), encoding="utf-8")
    return path
