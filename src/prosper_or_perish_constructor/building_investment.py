"""Building investment at list price: what the buildings standing in a save cost to build.

A building type has a base price in gold (its ``price`` key, or the price of the age that unlocks it when it has
none) and an ``increase_per_level_cost`` (ipl): the n-th level costs ``price x (1 + ipl x (n - 1))``. A building with
L levels therefore stands for

    price x (L + ipl x L x (L - 1) / 2)

gold. Prices and ipl come from the built mod files through the parser (after the constructor's scaling), so every
snapshot, old ones included, is valued with today's catalog. The engine also scales a construction's price by the
location's cost modifiers; the save does not keep those, so this is list-price investment, not gold actually paid.

``update_dataset`` keeps the derived table ``building_investment`` next to the engine tables in the savegame dataset
(``graphs/dataset/tables/building_investment/playthrough_id=<id>/<snapshot>.parquet``, one row per building). It is
incremental: snapshots that already have the table are skipped unless the price catalog changed since they were
written (``catalog.json`` holds its fingerprint), and tables of purged snapshots are removed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import polars as pl

TABLE = "building_investment"
CATALOG_FILE = "catalog.json"

FOOD_SERVICE_BUILDINGS = frozenset({"tavern", "grange", "victualling_yard", "cookshop", "public_kitchen", "granary"})

# Investment categories in display order.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("food_farms", "Food production"),
    ("food_service", "Food service & trade"),
    ("land_improvement", "Land improvements"),
    ("crafts", "Crafts & workshops"),
    ("extraction", "Extraction"),
    ("military", "Military"),
    ("infrastructure", "Infrastructure & institutions"),
)
CATEGORY_LABELS = dict(CATEGORIES)
DEFAULT_CATEGORY = "infrastructure"

# The blueprint footprint class (constructor.toml [building_footprint.classes]) says what a building is.
FOOTPRINT_CATEGORY = {
    "farm_land": "food_farms",
    "fishery": "food_farms",
    "capacity_source": "land_improvement",
    "urban_workshop": "crafts",
    "manufactory": "crafts",
    "mill_works": "crafts",
    "rural_processing": "crafts",
    "rural_village": "crafts",  # market villages, daywork yards; the fishing and forest villages produce food (above)
    "mining": "extraction",
    "extractive_open": "extraction",
    "forestry": "extraction",
    "barracks": "military",
    "fortification": "military",
    "military_grounds": "military",
}
# Game building category, for buildings without a blueprint or with a footprint class not listed above.
BUILDING_CATEGORY = {
    "village_category": "food_farms",
    "rgo_building_category": "extraction",
    "basic_industry_category": "crafts",
    "consumer_goods_category": "crafts",
    "weapons_industry_category": "crafts",
    "military_category": "military",
    "defense_category": "military",
    "naval_category": "military",
}

CATALOG_SCHEMA = {
    "building_type": pl.String,
    "base_price": pl.Float64,
    "price_basis": pl.String,
    "increase_per_level_cost": pl.Float64,
    "building_category": pl.String,
    "footprint": pl.String,
    "investment_category": pl.String,
}
SNAPSHOT_COLUMNS = ("snapshot_id", "playthrough_id", "date", "year", "month", "day", "date_sort")
TABLE_SCHEMA = {
    "building_id": pl.Int64,
    "building_type": pl.String,
    "location_id": pl.Int64,
    "location_slug": pl.String,
    "country_tag": pl.String,
    "building_owner_tag": pl.String,
    "level": pl.Float64,
    "base_price": pl.Float64,
    "increase_per_level_cost": pl.Float64,
    "price_basis": pl.String,
    "investment_category": pl.String,
    "investment": pl.Float64,
}


# --------------------------------------------------------------------------------------------------------
# Formula


def list_price_investment(price: float, increase_per_level_cost: float | None, levels: float) -> float:
    """Gold for `levels` levels at list price: level n costs price x (1 + ipl x (n - 1))."""
    ipl = increase_per_level_cost or 0.0
    return price * (levels + ipl * levels * (levels - 1) / 2)


def investment_expr(
    price: pl.Expr | str = "base_price",
    increase_per_level_cost: pl.Expr | str = "increase_per_level_cost",
    level: pl.Expr | str = "level",
) -> pl.Expr:
    """`list_price_investment` as a Polars expression (null ipl = 0, null or negative level = 0)."""
    p = pl.col(price) if isinstance(price, str) else price
    ipl = (pl.col(increase_per_level_cost) if isinstance(increase_per_level_cost, str) else increase_per_level_cost).fill_null(0.0)
    lv = (pl.col(level) if isinstance(level, str) else level).fill_null(0.0).clip(lower_bound=0.0)
    return p * (lv + ipl * lv * (lv - 1) / 2)


# --------------------------------------------------------------------------------------------------------
# Price catalog


def investment_category(
    building_type: str,
    *,
    building_category: str | None,
    footprint: str | None,
    produces_food: bool,
) -> str:
    if building_type in FOOD_SERVICE_BUILDINGS:
        return "food_service"
    if produces_food:
        return "food_farms"
    if footprint and footprint in FOOTPRINT_CATEGORY:
        return FOOTPRINT_CATEGORY[footprint]
    # other classes (trade, institutional, maritime, rural_village, technical, ...) are mixed: the game category decides
    return BUILDING_CATEGORY.get(building_category or "", DEFAULT_CATEGORY)


def price_catalog(eu5_data, footprints: dict[str, str] | None = None) -> pl.DataFrame:
    """One row per building type: base_price, price_basis, increase_per_level_cost and investment_category.

    price_basis: ``explicit`` (the building's price key), ``unlock_age`` (no price key: the generic price of the age
    that unlocks it, as the engine charges it), ``first_age`` (no price key, no unlocking advance: the first age's
    price), ``non_gold_price`` (the price key costs no gold, e.g. religious influence) and ``unresolved_price`` (the
    price key is not defined): both valued at the age price so their levels still count. ``investment_table`` adds
    ``unknown_type`` for a building type the catalog does not know (first age's price).
    """
    from eu5gameparser.domain.availability import (
        AGE_ORDER,
        _price_age_for_building,
        annotate_building_data_availability,
    )

    footprints = footprints or {}
    data = eu5_data.building_data
    annotated = annotate_building_data_availability(data, eu5_data.advancements, include_specific_unlocks=True)
    baseline = {age: info.gold for age, info in data.baseline_prices.items() if info.gold is not None}
    # an age without its own generic price falls back to the first age that has one
    first_price = next((baseline[age] for age in AGE_ORDER if age in baseline), None)
    baseline = {age: baseline.get(age, first_price) for age in AGE_ORDER}
    food_goods = set(
        eu5_data.goods.filter(pl.col("food").fill_null(0) > 0)["name"].to_list()
    ) if "food" in eu5_data.goods.columns else set()
    methods = annotated.production_methods
    food_buildings = set(
        methods.filter(pl.col("building").is_not_null() & pl.col("produced").is_in(sorted(food_goods)))["building"].to_list()
    )
    rows = []
    for row in annotated.buildings.to_dicts():
        name = row["name"]
        age = _price_age_for_building(row)
        unlocked = any(isinstance(row.get(k), str) for k in ("general_unlock_age", "unlock_age", "specific_unlock_age"))
        if row.get("price"):
            if row.get("price_gold") is not None:
                price, basis = row["price_gold"], "explicit"
            elif row.get("price_source"):
                price, basis = baseline.get(age), "non_gold_price"
            else:
                price, basis = baseline.get(age), "unresolved_price"
        else:
            price, basis = row.get("effective_price_gold"), ("unlock_age" if unlocked else "first_age")
        if price is None:  # no age price at all in the load order
            price, basis = baseline.get(AGE_ORDER[0]), "missing"
        footprint = footprints.get(name) or None
        rows.append({
            "building_type": name,
            "base_price": price,
            "price_basis": basis,
            "increase_per_level_cost": row.get("increase_per_level_cost"),
            "building_category": row.get("category"),
            "footprint": footprint,
            "investment_category": investment_category(
                name, building_category=row.get("category"), footprint=footprint, produces_food=name in food_buildings
            ),
        })
    return pl.DataFrame(rows, schema=CATALOG_SCHEMA).sort("building_type")


def unknown_type_price(catalog: pl.DataFrame) -> float:
    """Price of a building type the catalog does not know (removed since the save was written): the first age's
    generic building price, what the engine charges a building without a price key that no advance unlocks."""
    first_age = catalog.filter(pl.col("price_basis") == "first_age")["base_price"].drop_nulls()
    return float(first_age[0]) if first_age.len() else 50.0


def catalog_fingerprint(catalog: pl.DataFrame) -> str:
    text = catalog.sort("building_type").write_csv()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_price_catalog(
    repo: Path, project: Path, *, profile: str | None = None, load_order: Path | None = None
) -> pl.DataFrame:
    """The price catalog of the current mod build (parser profile and load order from constructor.toml)."""
    from eu5gameparser.domain.eu5 import load_eu5_data

    from prosper_or_perish_constructor.building_footprint import blueprint_classes
    from prosper_or_perish_constructor.free_building_levels import resolve_parser_config

    config = resolve_parser_config(repo, project)
    load_order = load_order or repo / str(config.get("load_order") or "constructor.load_order.toml")
    profile = profile or str(config.get("profile") or "constructor")
    data = load_eu5_data(profile=profile, load_order_path=load_order)
    try:
        footprints = {key: name for key, (name, _path) in blueprint_classes(repo).items()}
    except OSError:
        footprints = {}
    return price_catalog(data, footprints)


# --------------------------------------------------------------------------------------------------------
# Per-building table


def investment_table(buildings: pl.DataFrame, locations: pl.DataFrame, catalog: pl.DataFrame) -> pl.DataFrame:
    """One row per building: its list-price investment, category and the location owner.

    `buildings`: building_id, building_type, location_id, location_slug, owner (country id), level.
    `locations`: location_id, owner (country id), country_tag.
    """
    tags = (
        locations.select(pl.col("owner").alias("country_id"), "country_tag")
        .drop_nulls()
        .unique("country_id")
    )
    location_owner = locations.select("location_id", "country_tag").unique("location_id")
    fallback = unknown_type_price(catalog)
    columns = [c for c in ("building_id", "building_type", "location_id", "location_slug", "owner", "level") if c in buildings.columns]
    frame = (
        buildings.select(columns)
        .join(location_owner, on="location_id", how="left")
        .join(tags.rename({"country_id": "owner", "country_tag": "building_owner_tag"}), on="owner", how="left")
        .join(catalog.select("building_type", "base_price", "increase_per_level_cost", "price_basis", "investment_category"),
              on="building_type", how="left")
        .with_columns(
            pl.col("price_basis").fill_null("unknown_type"),
            pl.col("base_price").fill_null(fallback),
            pl.col("investment_category").fill_null(DEFAULT_CATEGORY),
        )
        .with_columns(investment_expr().alias("investment"))
    )
    for column, dtype in TABLE_SCHEMA.items():
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=dtype).alias(column))
    return frame.select([pl.col(c).cast(t) for c, t in TABLE_SCHEMA.items()])


def aggregate(frame: pl.DataFrame | pl.LazyFrame, by: Iterable[str]) -> pl.DataFrame | pl.LazyFrame:
    """Investment, levels and building count per group (e.g. snapshot_id + country_tag / location_slug / category)."""
    return frame.group_by(list(by)).agg(
        pl.col("investment").sum(),
        pl.col("level").sum().alias("levels"),
        pl.len().alias("buildings"),
    )


# --------------------------------------------------------------------------------------------------------
# Dataset


@dataclass
class UpdateResult:
    written: int = 0
    kept: int = 0
    removed: int = 0
    catalog_changed: bool = False
    fingerprint: str = ""


def _snapshot_files(dataset: Path, table: str) -> dict[Path, Path]:
    root = dataset / "tables" / table
    return {path.relative_to(root): path for path in sorted(root.glob("playthrough_id=*/*.parquet"))}


BUILDING_COLUMNS = ("building_id", "building_type", "location_id", "location_slug", "owner", "level")


def snapshot_investment(buildings_file: Path, locations_file: Path | None, catalog: pl.DataFrame) -> pl.DataFrame:
    schema = pl.read_parquet_schema(buildings_file)
    snap_columns = [c for c in SNAPSHOT_COLUMNS if c in schema]
    buildings = pl.read_parquet(buildings_file, columns=[c for c in (*BUILDING_COLUMNS, *snap_columns) if c in schema])
    if locations_file is not None and locations_file.is_file():
        locations = pl.read_parquet(locations_file, columns=["location_id", "owner", "country_tag"])
    else:
        locations = pl.DataFrame(schema={"location_id": pl.Int64, "owner": pl.Int64, "country_tag": pl.String})
    table = investment_table(buildings, locations, catalog)
    if buildings.height and snap_columns:
        first = buildings.select(snap_columns).row(0, named=True)
        table = table.with_columns([pl.lit(first[c]).alias(c) for c in snap_columns])
    return table


def update_dataset(
    dataset: Path,
    catalog: pl.DataFrame,
    *,
    force: bool = False,
    log: Callable[[str], None] = print,
) -> UpdateResult:
    """Write `building_investment` for every snapshot that lacks it (all of them when the catalog changed)."""
    root = dataset / "tables" / TABLE
    fingerprint = catalog_fingerprint(catalog)
    marker = root / CATALOG_FILE
    try:
        previous = json.loads(marker.read_text(encoding="utf-8")).get("fingerprint")
    except (OSError, ValueError):
        previous = None
    result = UpdateResult(fingerprint=fingerprint, catalog_changed=previous is not None and previous != fingerprint)
    rebuild = force or previous != fingerprint
    sources = _snapshot_files(dataset, "buildings")
    existing = _snapshot_files(dataset, TABLE)
    for relative, path in existing.items():
        if relative not in sources:
            path.unlink(missing_ok=True)
            result.removed += 1
    for relative, source in sources.items():
        target = root / relative
        if target.is_file() and not rebuild:
            result.kept += 1
            continue
        table = snapshot_investment(source, dataset / "tables" / "locations" / relative, catalog)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        table.write_parquet(temporary, compression="zstd", compression_level=1)
        temporary.replace(target)
        result.written += 1
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"fingerprint": fingerprint, "types": catalog.height}, indent=1), encoding="utf-8")
    log(
        f"building investment: {result.written} snapshot(s) written, {result.kept} current, {result.removed} removed"
        + (" (price catalog changed: all rebuilt)" if result.catalog_changed and rebuild else "")
    )
    return result


def price_basis_counts(catalog: pl.DataFrame) -> dict[str, int]:
    return dict(catalog.group_by("price_basis").len().sort("price_basis").iter_rows())
