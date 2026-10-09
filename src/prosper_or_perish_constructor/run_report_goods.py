"""Goods page of the run report: what makes every good and what uses it, per save and world region.

`write_goods_page` writes `goods.html` next to the run report and its data under `goods/`:

- `goods/index.json`: saves, world regions, goods (display order, group, icon, base price), buildings, production
  methods (name, building, recipe per level) and the demand types;
- `goods/<n>.json`, one per save: producers ``p`` [good, building, method, region, amount, levels, buildings, workers,
  recipe], building inputs ``c`` [good, building, method, region, wanted, received, recipe], other demand ``d``
  [good, bucket, region, wanted, received], trade and other supply ``s`` [good, bucket, region, amount], market
  figures ``m`` [good, region, price x volume, volume, supply, demand, stockpile, markets short, markets in surplus,
  markets] and trade between world regions ``x`` [good, region, imports, exports] (the trade routes that ran and
  cross the region's border); amounts are goods per month, indices point into the index lists (-1 = none);
- `goods/summary.json`: per good and save the world production, use and price, and production / use by building
  type, for the charts over the run.

How production is split. A market's totals per good are exact (`supplied_Production`, `demanded_Building`,
`taken_Building`). A good's `base_production` x the market's idle peasants (thousands) is part of that production
and comes off first ("Idle peasants (base production)"; the saves match it to the fifth digit). The save does not
say which building made how much of the rest, so every producer gets a recipe estimate =
its active method's output per level x level x staffing (workers / (workers per level x level)); RGOs get their
workers (one unit per 1,000 workers). The recipe misses production efficiency, output modifiers, throughput, input
shortages and market access, so per good one factor for buildings and one for RGOs is fitted over all markets
(least squares of market production on the two recipe totals) and each market's exact total is split by recipe x
factor. "Output vs recipe" (amount / recipe) is that rough efficiency. Building inputs are split the same way over
the recipe's input amounts, scaled to what the market's buildings wanted and received.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
import polars as pl

from prosper_or_perish_constructor.run_report_charts import (
    DUMMY_GOODS,
    OTHER_GREY,
    land_region_expr,
    region_palette,
    titleize,
)

if TYPE_CHECKING:
    from prosper_or_perish_constructor.run_report import RunData

CACHE_VERSION = "goods-4"
RGO = "rgo"  # pseudo building of the RGO rows
OTHER = "_other"  # pseudo building for market totals no recipe explains
IDLE = "_idle"  # pseudo building of the goods' base production by idle peasants
# demand that is not a building input: market bucket, label, colour
DEMAND_BUCKETS: tuple[tuple[str, str, str], ...] = (
    ("Pops", "Pops", "#1baf7a"),
    ("Construction", "Construction", "#a0522d"),
    ("Units", "Armies & navies", "#e34948"),
    ("Roads", "Roads", "#7d8b2a"),
    ("Consumption", "Consumption", "#4a3aa7"),
    ("Temporary", "Temporary", "#9a9a96"),
    ("Trade", "Exports", "#5fb8c4"),
    ("BurgherTrades", "Burgher trade out", "#00a3a3"),
)
SUPPLY_BUCKETS: tuple[tuple[str, str, str], ...] = (
    ("Trade", "Imports", "#5fb8c4"),
    ("BurgherTrades", "Burgher trade in", "#00a3a3"),
)
OTHER_REGION = "other"
# Goods page groups (display order): key, label, colour. A good's group comes from config/goods_categories.csv:
# its staple_group first (staple foods), else its subcategory, else its category.
PAGE_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("staple", "Staple foods", "#1baf7a"),
    ("cash", "Cash crops", "#eda100"),
    ("beasts", "Horses & beasts", "#a0522d"),
    ("prepared", "Prepared food & drink", "#7d8b2a"),
    ("building", "Building materials", "#8c8c88"),
    ("minerals", "Metals, ores & minerals", "#4a3aa7"),
    ("precious", "Precious & rare", "#e87ba4"),
    ("textiles", "Textiles & leather", "#2a78d6"),
    ("crafts", "Crafts & luxuries", "#00a3a3"),
    ("industry", "Tools, arms & ships", "#e34948"),
    ("other", "Other", "#9a9a96"),
)
PAGE_GROUP_BY_SUBCATEGORY = {
    "industrial_crops": "cash", "plant_fibers": "cash", "spices": "cash", "stimulants": "cash", "sweeteners": "cash",
    "tree_crops": "cash", "apiary": "cash",
    "animal_husbandry": "beasts",
    "prepared_food": "prepared", "beverages": "prepared",
    "timber": "building", "earth_materials": "building", "construction_stone": "building", "construction_materials": "building",
    "metal_ores": "minerals", "fuel": "minerals", "industrial_minerals": "minerals", "surface_minerals": "minerals",
    "precious_minerals": "precious", "aquatic_resources": "precious", "wild_luxuries": "precious", "animal_products": "precious",
    "textiles_and_leather": "textiles",
    "luxury_crafts": "crafts", "books_and_paper": "crafts", "medicinals": "crafts",
    "metal_goods": "industry", "military_goods": "industry", "naval_goods": "industry", "industrial_inputs": "industry",
}
FLOW_TABLES = ("producers", "consumers", "demand", "supply", "market", "trade")
FACTOR_LIMITS = (0.02, 50.0)


# --------------------------------------------------------------------------------------------------------
# Game data


class Recipes:
    """Production methods (output and inputs per level) and workers per building level, from the parser profile."""

    def __init__(self, repo: Path, project: Path):
        from eu5gameparser.domain.buildings import load_building_data
        from eu5gameparser.domain.goods import load_goods_data

        from prosper_or_perish_constructor.free_building_levels import resolve_parser_config
        from prosper_or_perish_constructor.pp_production_sheet import _base_production

        config = resolve_parser_config(repo, project)
        profile = str(config.get("profile") or "constructor")
        load_order = repo / str(config.get("load_order") or "constructor.load_order.toml")
        data = load_building_data(profile=profile, load_order_path=load_order)
        methods = data.production_methods
        self.outputs = methods.filter(pl.col("produced").is_not_null() & (pl.col("output") > 0)).select(
            pl.col("name").alias("method"), pl.col("produced").alias("good_id"), pl.col("output").alias("per_level"))
        self.inputs = (
            methods.select(pl.col("name").alias("method"), "input_goods", "input_amounts")
            .explode("input_goods", "input_amounts")
            .rename({"input_goods": "good_id", "input_amounts": "per_level"})
            .filter(pl.col("good_id").is_not_null() & (pl.col("per_level") > 0))
        )
        self.method_building = dict(methods.select("name", "building").iter_rows())
        self.workers = data.buildings.select(pl.col("name").alias("building_type"), pl.col("employment_size").alias("workers_per_level"))
        self.categories = dict(data.buildings.select("name", "category").iter_rows())
        # goods' base_production: what every 1,000 idle peasants of a market add to its production
        goods = load_goods_data(profile=profile, load_order_path=load_order).goods
        self.base_production = {name: value for name, raw in goods.select("name", "data").iter_rows()
                                if (value := _base_production(raw))}
        digest = hashlib.sha1()
        for frame in (self.outputs.sort("method", "good_id"), self.inputs.sort("method", "good_id"), self.workers.sort("building_type")):
            digest.update(frame.write_csv().encode())
        digest.update(json.dumps(self.base_production, sort_keys=True).encode())
        self.digest = digest.hexdigest()[:12]

    def recipe(self, method: str) -> dict[str, list[list[Any]]]:
        out = self.outputs.filter(pl.col("method") == method).select("good_id", "per_level").rows()
        inp = self.inputs.filter(pl.col("method") == method).select("good_id", "per_level").rows()
        return {"out": [list(r) for r in out], "in": [list(r) for r in inp]}


# --------------------------------------------------------------------------------------------------------
# One save


def _read(dataset: Path, table: str, playthrough: str, snapshot: str, columns: list[str]) -> pl.DataFrame:
    path = dataset / "tables" / table / f"playthrough_id={playthrough}" / f"{snapshot}.parquet"
    if not path.is_file():
        return pl.DataFrame()
    have = set(pl.read_parquet_schema(path))
    frame = pl.read_parquet(path, columns=[c for c in columns if c in have])
    return frame.with_columns([pl.lit(None).alias(c) for c in columns if c not in have])


def fit_factors(actual: np.ndarray, buildings: np.ndarray, rgos: np.ndarray) -> tuple[float, float]:
    """Factors (buildings, RGOs) so that actual ~ fb x buildings + fr x rgos over the markets (least squares, both
    positive); a kind without markets of its own falls back to its single-kind ratio, else 1."""

    def ratio(mask: np.ndarray, nominal: np.ndarray) -> float | None:
        total = nominal[mask].sum()
        return float(actual[mask].sum() / total) if total > 0 else None

    only_b, only_r = (buildings > 0) & (rgos == 0), (rgos > 0) & (buildings == 0)
    fb, fr = ratio(only_b, buildings), ratio(only_r, rgos)
    both = (buildings > 0) & (rgos > 0)
    if both.any():
        a = np.stack([buildings, rgos], axis=1)
        solution, *_ = np.linalg.lstsq(a, actual, rcond=None)
        if np.all(np.isfinite(solution)) and solution[0] > 0 and solution[1] > 0:
            fb, fr = float(solution[0]), float(solution[1])
        elif fb is None and fr is not None:
            fb = max(0.0, float((actual[both] - fr * rgos[both]).sum() / buildings[both].sum()))
        elif fr is None and fb is not None:
            fr = max(0.0, float((actual[both] - fb * buildings[both]).sum() / rgos[both].sum()))
    low, high = FACTOR_LIMITS
    return (min(high, max(low, fb if fb else 1.0)), min(high, max(low, fr if fr else 1.0)))


def save_flows(dataset: Path, playthrough: str, snapshot: str, recipes: Recipes) -> dict[str, Any]:
    """Producers, building inputs, other demand and supply and market figures of one save, keyed by name (the
    caller turns names into indices)."""
    def read(table: str, columns: list[str]) -> pl.DataFrame:
        return _read(dataset, table, playthrough, snapshot, columns)

    buckets = [b for b, _, _ in DEMAND_BUCKETS]
    supplies = [b for b, _, _ in SUPPLY_BUCKETS]
    goods = read("market_goods", [
        "market_id", "good_id", "price", "default_price", "supply", "demand", "stockpile", "supplied_Production",
        "demanded_Building", "taken_Building", *[f"demanded_{b}" for b in buckets], *[f"taken_{b}" for b in buckets],
        *[f"supplied_{b}" for b in supplies]])
    goods = goods.filter(~pl.col("good_id").is_in(sorted(DUMMY_GOODS)) & (pl.col("default_price") > 0)).with_columns(
        pl.exclude("market_id", "good_id").cast(pl.Float64).fill_null(0.0))
    locations = read("locations", ["location_id", "slug", "market_id", "raw_material", "rgo_employed", "macro_region",
                                   "super_region", "unemployed_peasants"])
    locations = locations.with_columns(pl.when(land_region_expr()).then(pl.col("macro_region")).otherwise(pl.lit(OTHER_REGION)).alias("region"))
    region_of_location = locations.select("location_id", "region")
    markets = read("markets", ["market_id", "center_location_id"]).join(
        region_of_location.rename({"location_id": "center_location_id"}), on="center_location_id", how="left").select(
        "market_id", pl.col("region").fill_null(OTHER_REGION))
    buildings = read("buildings", ["building_id", "building_type", "location_id", "market_id", "level", "employed"])
    methods = read("building_methods", ["building_id", "production_method"]).rename({"production_method": "method"})

    staffed = (
        buildings.filter(pl.col("market_id").is_not_null() & (pl.col("level") > 0))
        .join(recipes.workers, on="building_type", how="left")
        .join(region_of_location, on="location_id", how="left")
        .with_columns(
            pl.col("region").fill_null(OTHER_REGION),
            pl.when(pl.col("workers_per_level") > 0)
            .then((pl.col("employed").fill_null(0.0) / (pl.col("level") * pl.col("workers_per_level"))).clip(0.0, 1.0))
            .otherwise(1.0).alias("staffing"))
    )
    active = methods.join(staffed, on="building_id")
    recipe = (pl.col("per_level") * pl.col("level") * pl.col("staffing")).alias("recipe")
    made = active.join(recipes.outputs, on="method").with_columns(recipe)
    used = active.join(recipes.inputs, on="method").with_columns(recipe)
    # a building with several methods making (or using) the same good: its levels, workers and count are split
    # evenly over them, so method rows add up to the building
    share = 1.0 / pl.len().over("building_id", "good_id")
    made = made.with_columns((pl.col("level") * share).alias("levels"), (pl.col("employed").fill_null(0.0) * share).alias("workers"),
                             share.alias("count"))
    rgo = locations.filter(pl.col("raw_material").is_not_null() & (pl.col("rgo_employed") > 0) & pl.col("market_id").is_not_null()).select(
        "market_id", pl.col("raw_material").alias("good_id"), "region", pl.lit(RGO).alias("building_type"),
        pl.lit(None, dtype=pl.String).alias("method"), pl.col("rgo_employed").alias("recipe"), pl.lit(0.0).alias("levels"),
        pl.col("rgo_employed").alias("workers"), pl.lit(1.0).alias("count"))

    # -- base production: a good's base_production per 1,000 idle peasants of the market comes first (exact in the
    # saves, e.g. 0.003 victuals); the buildings and RGOs share the rest
    keys = ["market_id", "good_id"]
    rates = pl.DataFrame({"good_id": list(recipes.base_production), "rate": list(recipes.base_production.values())},
                         schema={"good_id": pl.String, "rate": pl.Float64})
    idle = locations.filter(pl.col("market_id").is_not_null()).group_by("market_id", "region").agg(
        pl.col("unemployed_peasants").cast(pl.Float64).fill_null(0.0).sum().alias("workers"))
    base = (
        idle.join(rates, how="cross").with_columns((pl.col("rate") * pl.col("workers")).alias("recipe"))
        .filter(pl.col("recipe") > 0)
        .join(goods.select(*keys, "supplied_Production"), on=keys, how="inner")
        .with_columns((pl.col("supplied_Production") / pl.col("recipe").sum().over(keys)).clip(upper_bound=1.0).alias("cover"))
        .with_columns((pl.col("recipe") * pl.col("cover")).alias("amount"))
    )
    base_total = base.group_by(keys).agg(pl.col("amount").sum().alias("base"))

    # -- producers: fit building / RGO factors per good, split each market's production
    nominal = (
        goods.select(*keys, "supplied_Production").join(base_total, on=keys, how="left")
        .select(*keys, (pl.col("supplied_Production") - pl.col("base").fill_null(0.0)).clip(lower_bound=0.0).alias("actual"))
        .join(made.group_by(keys).agg(pl.col("recipe").sum().alias("b")), on=keys, how="full", coalesce=True)
        .join(rgo.group_by(keys).agg(pl.col("recipe").sum().alias("r")), on=keys, how="full", coalesce=True)
        .with_columns(pl.col("actual", "b", "r").fill_null(0.0))
        .filter(~pl.col("good_id").is_in(sorted(DUMMY_GOODS)))
    )
    factors = {}
    for (good,), part in nominal.partition_by("good_id", as_dict=True).items():
        factors[good] = fit_factors(part["actual"].to_numpy(), part["b"].to_numpy(), part["r"].to_numpy())
    factor_frame = pl.DataFrame({"good_id": list(factors), "fb": [f[0] for f in factors.values()], "fr": [f[1] for f in factors.values()]},
                                schema={"good_id": pl.String, "fb": pl.Float64, "fr": pl.Float64})
    scale = nominal.join(factor_frame, on="good_id", how="left").with_columns(
        (pl.col("b") * pl.col("fb") + pl.col("r") * pl.col("fr")).alias("weighted")).with_columns(
        pl.when(pl.col("weighted") > 0).then(pl.col("actual") / pl.col("weighted")).otherwise(0.0).alias("s"))
    producer_columns = ["market_id", "good_id", "region", "building_type", "method", "recipe", "levels", "workers", "count"]
    producers = (
        pl.concat([made.select(producer_columns).with_columns(pl.lit("b").alias("kind")),
                   rgo.select(producer_columns).with_columns(pl.lit("r").alias("kind"))])
        .join(scale.select(*keys, "fb", "fr", "s"), on=keys, how="inner")
        .with_columns((pl.col("recipe") * pl.when(pl.col("kind") == "b").then(pl.col("fb")).otherwise(pl.col("fr")) * pl.col("s")).alias("amount"))
    )
    unexplained = scale.filter((pl.col("weighted") <= 0) & (pl.col("actual") > 0)).join(markets, on="market_id", how="left").select(
        "good_id", pl.col("region").fill_null(OTHER_REGION), pl.lit(OTHER).alias("building_type"), pl.lit(None, dtype=pl.String).alias("method"),
        pl.col("actual").alias("amount"), pl.lit(0.0).alias("recipe"), pl.lit(0.0).alias("levels"), pl.lit(0.0).alias("workers"), pl.lit(0.0).alias("count"))
    idle_rows = base.select("good_id", "region", pl.lit(IDLE).alias("building_type"), pl.lit(None, dtype=pl.String).alias("method"),
                            "amount", "recipe", pl.lit(0.0).alias("levels"), "workers", pl.lit(0.0).alias("count"))
    group = ["good_id", "building_type", "method", "region"]
    producers = pl.concat([
        producers.group_by(group).agg(pl.col("amount", "levels", "workers", "count", "recipe").sum()),
        unexplained.group_by(group).agg(pl.col("amount", "levels", "workers", "count", "recipe").sum()),
        idle_rows.group_by(group).agg(pl.col("amount", "levels", "workers", "count", "recipe").sum()),
    ], how="diagonal_relaxed").filter(pl.col("amount") > 0)

    # -- building inputs: split what the market's buildings wanted and received over the recipe inputs
    need = used.group_by(keys).agg(pl.col("recipe").sum().alias("total"))
    consumers = (
        used.join(need, on=keys).join(goods.select(*keys, "demanded_Building", "taken_Building"), on=keys, how="inner")
        # every user of the good in the market unstaffed (recipe 0): split evenly
        .with_columns(pl.when(pl.col("total") > 0).then(pl.col("recipe") / pl.col("total")).otherwise(1.0 / pl.len().over(keys)).alias("w"))
        .with_columns((pl.col("w") * pl.col("demanded_Building")).alias("wanted"), (pl.col("w") * pl.col("taken_Building")).alias("received"))
        .group_by(group).agg(pl.col("wanted", "received", "recipe").sum())
    )
    orphan = goods.join(need, on=keys, how="anti").filter(pl.col("demanded_Building") > 0).join(markets, on="market_id", how="left").group_by(
        "good_id", pl.col("region").fill_null(OTHER_REGION)).agg(pl.col("demanded_Building").sum().alias("wanted"), pl.col("taken_Building").sum().alias("received")).with_columns(
        pl.lit(OTHER).alias("building_type"), pl.lit(None, dtype=pl.String).alias("method"), pl.lit(0.0).alias("recipe"))
    consumers = pl.concat([consumers, orphan.select(consumers.columns)]).filter(pl.col("wanted") + pl.col("received") > 0)

    # -- other demand, trade and market figures per region of the market centre
    regional = goods.join(markets, on="market_id", how="left").with_columns(pl.col("region").fill_null(OTHER_REGION))
    demand = pl.concat([
        regional.group_by("good_id", "region").agg(pl.col(f"demanded_{b}").sum().alias("wanted"), pl.col(f"taken_{b}").sum().alias("received")).with_columns(pl.lit(b).alias("bucket"))
        for b in buckets]).filter(pl.col("wanted") + pl.col("received") > 0)
    supply = pl.concat([
        regional.group_by("good_id", "region").agg(pl.col(f"supplied_{b}").sum().alias("amount")).with_columns(pl.lit(b).alias("bucket"))
        for b in supplies]).filter(pl.col("amount") > 0)
    market = regional.with_columns((pl.col("supply") + pl.col("demand")).alias("volume")).group_by("good_id", "region").agg(
        (pl.col("price") * pl.col("volume")).sum().alias("pv"), pl.col("volume").sum(), pl.col("supply").sum(), pl.col("demand").sum(),
        pl.col("stockpile").sum(),
        ((pl.col("demand") > 0.01) & (pl.col("supply") < 0.9 * pl.col("demand"))).sum().alias("short"),
        ((pl.col("supplied_Production") > 0.01) & (pl.col("supply") > 1.1 * pl.col("demand"))).sum().alias("surplus"),
        ((pl.col("supply") + pl.col("demand")) > 0).sum().alias("markets"))
    # trade between world regions: the routes that ran, by the regions of their two markets
    routes = read("trades", ["good_id", "from_market", "to_market", "cached", "happened"])
    trade = pl.DataFrame(schema={"good_id": pl.String, "region": pl.String, "imports": pl.Float64, "exports": pl.Float64})
    if routes.height:
        ran = (
            routes.filter((pl.col("happened") == "yes") & ~pl.col("good_id").is_in(sorted(DUMMY_GOODS)))
            .join(markets.rename({"market_id": "from_market", "region": "from_region"}), on="from_market", how="left")
            .join(markets.rename({"market_id": "to_market", "region": "to_region"}), on="to_market", how="left")
            .with_columns(pl.col("from_region", "to_region").fill_null(OTHER_REGION), pl.col("cached").cast(pl.Float64).fill_null(0.0))
            .filter(pl.col("from_region") != pl.col("to_region"))
        )
        imports = ran.group_by("good_id", pl.col("to_region").alias("region")).agg(pl.col("cached").sum().alias("imports"))
        exports = ran.group_by("good_id", pl.col("from_region").alias("region")).agg(pl.col("cached").sum().alias("exports"))
        trade = imports.join(exports, on=["good_id", "region"], how="full", coalesce=True).with_columns(
            pl.col("imports", "exports").fill_null(0.0)).filter(pl.col("imports") + pl.col("exports") > 0)
    return {"producers": producers, "consumers": consumers, "demand": demand, "supply": supply, "market": market, "trade": trade}


# --------------------------------------------------------------------------------------------------------
# Page data


def _sig(value: float | None, digits: int = 4) -> float | int | None:
    if value is None or not math.isfinite(value):
        return None
    if value == 0:
        return 0
    rounded = float(f"{value:.{digits}g}")
    return int(rounded) if rounded.is_integer() else rounded


class Index:
    """Name -> index lists shared by every save file."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {"good": [], "building": [], "method": [], "region": []}
        self.maps: dict[str, dict[str, int]] = {k: {} for k in self.lists}

    def of(self, kind: str, key: str | None) -> int:
        if key is None:
            return -1
        found = self.maps[kind].get(key)
        if found is None:
            found = self.maps[kind][key] = len(self.lists[kind])
            self.lists[kind].append(key)
        return found


def encode_save(flows: dict[str, Any], index: Index) -> dict[str, list[list[Any]]]:
    of = index.of
    buckets = {b: i for i, (b, _, _) in enumerate(DEMAND_BUCKETS)}
    supplies = {b: i for i, (b, _, _) in enumerate(SUPPLY_BUCKETS)}
    p = [[of("good", r["good_id"]), of("building", r["building_type"]), of("method", r["method"]), of("region", r["region"]),
          _sig(r["amount"]), _sig(r["levels"], 3), _sig(r["count"], 3), _sig(r["workers"], 3), _sig(r["recipe"])]
         for r in flows["producers"].sort("amount", descending=True).iter_rows(named=True)]
    c = [[of("good", r["good_id"]), of("building", r["building_type"]), of("method", r["method"]), of("region", r["region"]),
          _sig(r["wanted"]), _sig(r["received"]), _sig(r["recipe"])]
         for r in flows["consumers"].sort("received", descending=True).iter_rows(named=True)]
    d = [[of("good", r["good_id"]), buckets[r["bucket"]], of("region", r["region"]), _sig(r["wanted"]), _sig(r["received"])]
         for r in flows["demand"].iter_rows(named=True)]
    s = [[of("good", r["good_id"]), supplies[r["bucket"]], of("region", r["region"]), _sig(r["amount"])]
         for r in flows["supply"].iter_rows(named=True)]
    m = [[of("good", r["good_id"]), of("region", r["region"]), _sig(r["pv"]), _sig(r["volume"]), _sig(r["supply"]), _sig(r["demand"]),
          _sig(r["stockpile"]), r["short"], r["surplus"], r["markets"]]
         for r in flows["market"].iter_rows(named=True)]
    x = [[of("good", r["good_id"]), of("region", r["region"]), _sig(r["imports"]), _sig(r["exports"])]
         for r in flows["trade"].iter_rows(named=True)]
    return {"p": p, "c": c, "d": d, "s": s, "m": m, "x": x}


def _summary_rows(flows: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per good: world production, use (received), price x volume / volume, production by building type and use by
    building type or demand bucket."""
    out: dict[str, dict[str, Any]] = {}
    for good, building, amount in flows["producers"].group_by("good_id", "building_type").agg(pl.col("amount").sum()).iter_rows():
        out.setdefault(good, {"made": {}, "used": {}})["made"][building] = amount
    for good, building, amount in flows["consumers"].group_by("good_id", "building_type").agg(pl.col("received").sum()).iter_rows():
        out.setdefault(good, {"made": {}, "used": {}})["used"][building] = amount
    for good, bucket, amount in flows["demand"].filter(~pl.col("bucket").is_in(["Trade", "BurgherTrades"])).group_by("good_id", "bucket").agg(
            pl.col("received").sum()).iter_rows():
        out.setdefault(good, {"made": {}, "used": {}})["used"][f"@{bucket}"] = amount
    for good, pv, volume in flows["market"].group_by("good_id").agg(pl.col("pv").sum(), pl.col("volume").sum()).iter_rows():
        out.setdefault(good, {"made": {}, "used": {}})["price"] = pv / volume if volume else None
    return out


def build_goods_data(run: RunData, dataset: Path, out: Path, recipes: Recipes, *, cache: Path | None = None,
                     log: Callable[[str], None] = print) -> dict[str, Any]:
    """Write goods/<n>.json per save and goods/summary.json; returns the index payload (written by the caller)."""
    folder = out / "goods"
    folder.mkdir(parents=True, exist_ok=True)
    index = Index()
    # regions first, in the report's palette order, so their indices are stable
    palette = region_palette(run)
    for key, _, _ in palette:
        index.of("region", key)
    index.of("region", OTHER_REGION)
    saves, summaries = [], []
    snapshots = run.snapshots.select("snapshot_id", "year", "date").to_dicts()
    for n, snap in enumerate(snapshots):
        snapshot = snap["snapshot_id"]
        # the flows of a save never change while the recipes stay the same: cached per save as parquet
        cached = cache / f"{snapshot}.{recipes.digest}.{CACHE_VERSION}" if cache else None
        flows = None
        if cached and (cached / "done").is_file():
            try:
                flows = {k: pl.read_parquet(cached / f"{k}.parquet") for k in FLOW_TABLES}
            except (OSError, pl.exceptions.PolarsError):
                flows = None
        if flows is None:
            flows = save_flows(dataset, run.playthrough_id, snapshot, recipes)
            if cached:
                cached.mkdir(parents=True, exist_ok=True)
                for k in FLOW_TABLES:
                    flows[k].write_parquet(cached / f"{k}.parquet")
                (cached / "done").write_text("", encoding="utf-8")
        name = f"goods/{n:03d}.json"
        (out / name).write_text(json.dumps(encode_save(flows, index), separators=(",", ":"), allow_nan=False), encoding="utf-8")
        summaries.append(_summary_rows(flows))
        saves.append({"id": snapshot, "label": str(snap.get("year") or snap.get("date") or snapshot), "date": snap.get("date"), "file": name})
    log(f"goods page: {len(saves)} saves")

    # over the run: production by building type and use by building type / bucket (top 8 + other) per good
    summary: dict[str, Any] = {}
    goods = sorted({g for s in summaries for g in s})
    for good in goods:
        rows = [s.get(good, {"made": {}, "used": {}}) for s in summaries]
        entry: dict[str, Any] = {
            "made": [_sig(sum(r["made"].values())) for r in rows],
            "used": [_sig(sum(r["used"].values())) for r in rows],
            "price": [_sig(r.get("price")) for r in rows],
        }
        for side in ("made", "used"):
            peak: dict[str, float] = {}
            for r in rows:
                for k, v in r[side].items():
                    peak[k] = max(peak.get(k, 0.0), v)
            top = [k for k, _ in sorted(peak.items(), key=lambda kv: -kv[1])[:8]]
            series = {k: [_sig(r[side].get(k, 0.0)) for r in rows] for k in top}
            rest = [_sig(sum(v for k, v in r[side].items() if k not in top)) for r in rows]
            if any(rest):
                series["_rest"] = rest
            entry[f"{side}_by"] = series
        summary[good] = entry
        for side in ("made_by", "used_by"):
            for key in entry[side]:
                if not key.startswith("@") and key != "_rest":
                    index.of("building", key)
    (folder / "summary.json").write_text(json.dumps(summary, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return {"saves": saves, "index": index, "palette": palette}


def page_groups(repo: Path) -> dict[str, str]:
    """good -> goods page group (PAGE_GROUPS) from config/goods_categories.csv."""
    path = repo / "config" / "goods_categories.csv"
    if not path.is_file():
        return {}
    out = {}
    for good, subcategory, staple in pl.read_csv(path, infer_schema=False).select("good", "subcategory", "staple_group").iter_rows():
        out[good] = "staple" if staple else PAGE_GROUP_BY_SUBCATEGORY.get(subcategory or "", "other")
    return out


def index_payload(run: RunData, built: dict[str, Any], recipes: Recipes, dataset: Path, repo: Path | None = None) -> dict[str, Any]:
    from prosper_or_perish_constructor.run_report_urban import LOC_NAME_CALL

    index: Index = built["index"]
    labels = run.labels

    def clean(text: str | None, key: str) -> str:
        text = text or labels._text(key) or titleize(key)
        return LOC_NAME_CALL.sub(lambda m: labels._text(m.group(1)) or titleize(m.group(1)), text)

    last = run.snapshots["snapshot_id"][-1]
    root = dataset / "tables"

    def catalog(table: str, key: str, name: str) -> dict[str, str]:
        path = root / table / f"playthrough_id={run.playthrough_id}" / f"{last}.parquet"
        if not path.is_file():
            return {}
        return {k: v for k, v in pl.read_parquet(path, columns=[key, name]).iter_rows() if k}

    building_names = catalog("building_catalog", "building_type", "building_name")
    method_names = catalog("production_method_catalog", "production_method", "production_method_name")
    # goods: every good any save has, in the report's order (group, then the most produced at the last save)
    groups = page_groups(repo) if repo else {}
    prices = {g: p for g, p in run.market_goods.select("good_id", "default_price").unique("good_id").iter_rows()} if not run.market_goods.is_empty() else {}
    order = {k: i for i, (k, _, _) in enumerate(PAGE_GROUPS)}
    made_last = run.market_goods.filter(pl.col("snapshot_id") == last).group_by("good_id").agg(
        (pl.col("production") * pl.col("default_price")).sum().alias("v")) if not run.market_goods.is_empty() else pl.DataFrame()
    value = dict(made_last.iter_rows()) if made_last.height else {}
    goods = []
    for good in index.lists["good"]:
        goods.append({"id": good, "name": labels.good(good), "group": groups.get(good, "other"),
                      "price": prices.get(good), "icon": run.good_icons.get(good)})
    good_order = sorted(range(len(goods)), key=lambda i: (order.get(goods[i]["group"], 99), -(value.get(goods[i]["id"]) or 0.0), goods[i]["name"]))
    buildings = []
    for key in index.lists["building"]:
        if key == RGO:
            buildings.append({"id": key, "name": "RGO", "cat": "rgo"})
        elif key == OTHER:
            buildings.append({"id": key, "name": "Other sources (no recipe)", "cat": "other"})
        elif key == IDLE:
            buildings.append({"id": key, "name": "Idle peasants (base production)", "cat": "base"})
        else:
            buildings.append({"id": key, "name": clean(building_names.get(key), key),
                              "cat": (recipes.categories.get(key) or "").replace("_category", "")})
    methods = []
    for key in index.lists["method"]:
        recipe = recipes.recipe(key)
        methods.append({"id": key, "name": clean(method_names.get(key), key), "b": recipes.method_building.get(key), **recipe})
    regions = [{"id": k, "name": label, "color": colour} for k, label, colour in built["palette"]]
    known = {r["id"] for r in regions}
    for key in index.lists["region"]:
        if key not in known:
            regions.append({"id": key, "name": "Seas and other" if key == OTHER_REGION else titleize(key), "color": OTHER_GREY})
    return {
        "run": run.name, "years": list(run.years), "saves": built["saves"], "regions": regions, "goods": goods,
        "goodOrder": good_order, "groups": [{"key": k, "label": label, "color": colour} for k, label, colour in PAGE_GROUPS],
        "buildings": buildings, "methods": methods,
        "demand": [{"id": b, "name": label, "color": colour} for b, label, colour in DEMAND_BUCKETS],
        "supply": [{"id": b, "name": label, "color": colour} for b, label, colour in SUPPLY_BUCKETS],
    }


def write_goods_page(run: RunData, out: Path, *, repo: Path, project: Path, dataset: Path, cache: Path | None = None,
                     canvas: Any = None, fps: int = 6, log: Callable[[str], None] = print) -> Path | None:
    """The goods page and, when the dataset has province food, the food page (run_report_food), which shares the
    goods page's index of buildings, methods and regions."""
    if run.market_goods.is_empty():
        return None
    recipes = Recipes(repo, project)
    built = build_goods_data(run, dataset, out, recipes, cache=cache, log=log)
    from prosper_or_perish_constructor.run_report_food import write_food

    write_food(run, out, repo=repo, project=project, dataset=dataset, recipes=recipes, index=built["index"], canvas=canvas,
               fps=fps, cache=cache.parent / f"{cache.name}.food" if cache else None, log=log)
    payload = index_payload(run, built, recipes, dataset, repo)
    (out / "goods" / "index.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    from prosper_or_perish_constructor.run_report_goods_page import goods_page_html

    path = out / "goods.html"
    path.write_text(goods_page_html(run.name, run.years), encoding="utf-8")
    return path
