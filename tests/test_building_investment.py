from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor import building_investment as bi


def _catalog(rows: list[dict]) -> pl.DataFrame:
    defaults = {"building_category": None, "footprint": None, "investment_category": "crafts", "price_basis": "explicit",
                "increase_per_level_cost": None}
    return pl.DataFrame([{**defaults, **row} for row in rows], schema=bi.CATALOG_SCHEMA)


@pytest.mark.parametrize("levels", [0, 1, 2, 5, 12])
@pytest.mark.parametrize("ipl", [0.0, 0.14, 1.0])
def test_closed_form_is_the_sum_of_the_level_prices(levels: int, ipl: float) -> None:
    price = 35.0
    by_level = sum(price * (1 + ipl * (n - 1)) for n in range(1, levels + 1))
    assert bi.list_price_investment(price, ipl, levels) == pytest.approx(by_level)
    frame = pl.DataFrame({"base_price": [price], "increase_per_level_cost": [ipl], "level": [float(levels)]})
    assert frame.select(bi.investment_expr())[0, 0] == pytest.approx(by_level)


def test_zero_or_missing_increase_per_level_is_linear_in_levels() -> None:
    assert bi.list_price_investment(50.0, 0.0, 4) == 200.0
    assert bi.list_price_investment(50.0, None, 4) == 200.0
    frame = pl.DataFrame(
        {"base_price": [50.0, 50.0, 50.0], "increase_per_level_cost": [None, 0.0, 0.5], "level": [4.0, 4.0, None]},
        schema={"base_price": pl.Float64, "increase_per_level_cost": pl.Float64, "level": pl.Float64},
    )
    assert frame.select(bi.investment_expr().alias("gold"))["gold"].to_list() == [200.0, 200.0, 0.0]


def _buildings() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "building_id": [1, 2, 3, 4],
            "building_type": ["tavern", "wheat_farm", "retired_building", "tavern"],
            "location_id": [10, 10, 11, 12],
            "location_slug": ["york", "york", "leeds", "paris"],
            "owner": [100, 100, 100, 200],
            "level": [3.0, 2.0, 1.0, 1.0],
        }
    )


def _locations() -> pl.DataFrame:
    return pl.DataFrame(
        {"location_id": [10, 11, 12], "owner": [100, 100, 200], "country_tag": ["ENG", "ENG", "FRA"]}
    )


def _price_catalog() -> pl.DataFrame:
    return _catalog([
        {"building_type": "tavern", "base_price": 35.0, "increase_per_level_cost": 1.0, "investment_category": "food_service"},
        {"building_type": "wheat_farm", "base_price": 50.0, "price_basis": "first_age", "investment_category": "food_farms"},
    ])


def test_table_values_every_building_and_flags_unknown_types() -> None:
    table = bi.investment_table(_buildings(), _locations(), _price_catalog())

    assert dict(table.schema) == bi.TABLE_SCHEMA
    rows = {r["building_id"]: r for r in table.to_dicts()}
    assert rows[1]["investment"] == pytest.approx(35 * (1 + 2 + 3))  # levels cost 35, 70, 105
    assert rows[2]["investment"] == pytest.approx(100.0)
    # a type the catalog does not know: first age's price, flagged, default category
    assert rows[3]["price_basis"] == "unknown_type"
    assert rows[3]["base_price"] == 50.0
    assert rows[3]["investment"] == 50.0
    assert rows[3]["investment_category"] == bi.DEFAULT_CATEGORY
    assert [rows[i]["country_tag"] for i in (1, 3, 4)] == ["ENG", "ENG", "FRA"]
    assert rows[4]["building_owner_tag"] == "FRA"

    by_country = bi.aggregate(table, ["country_tag"]).sort("country_tag")
    assert by_country["investment"].to_list() == pytest.approx([210 + 100 + 50, 35])


def test_categories_follow_the_food_list_food_output_footprint_and_game_category() -> None:
    cat = bi.investment_category
    assert cat("granary", building_category="infrastructure_category", footprint="rural_processing", produces_food=False) == "food_service"
    assert cat("cookshop", building_category="consumer_goods_category", footprint="urban_workshop", produces_food=True) == "food_service"
    assert cat("fruit_orchard", building_category="rgo_building_category", footprint="farm_land", produces_food=True) == "food_farms"
    assert cat("field_management", building_category="infrastructure_category", footprint="capacity_source", produces_food=False) == "land_improvement"
    assert cat("iron_mine", building_category="rgo_building_category", footprint="mining", produces_food=False) == "extraction"
    assert cat("shipyard", building_category="naval_category", footprint="maritime", produces_food=False) == "military"
    assert cat("harbor", building_category="trade_category", footprint="maritime", produces_food=False) == "infrastructure"
    assert cat("fishing_village", building_category="village_category", footprint="rural_village", produces_food=True) == "food_farms"
    assert cat("market_village", building_category="village_category", footprint="rural_village", produces_food=False) == "crafts"
    assert cat("vanilla_only", building_category="weapons_industry_category", footprint=None, produces_food=False) == "crafts"
    assert cat("vanilla_only", building_category=None, footprint=None, produces_food=False) == bi.DEFAULT_CATEGORY
    assert {key for key, _ in bi.CATEGORIES} >= set(bi.FOOTPRINT_CATEGORY.values()) | set(bi.BUILDING_CATEGORY.values())


def test_price_catalog_resolves_prices_and_ipl_from_the_parser() -> None:
    from types import SimpleNamespace

    import eu5gameparser
    from eu5gameparser.config import ParserConfig
    from eu5gameparser.domain.advancements import load_advancement_data
    from eu5gameparser.domain.buildings import load_building_data
    from eu5gameparser.domain.goods import load_goods_data

    fixture = Path(eu5gameparser.__file__).resolve().parents[2] / "tests" / "fixtures" / "eu5"
    if not fixture.is_dir():
        pytest.skip("eu5-game-parser test fixture not available")
    config = ParserConfig(game_root=fixture)
    data = SimpleNamespace(
        building_data=load_building_data(config),
        advancements=load_advancement_data(config).advancements,
        goods=load_goods_data(config).goods,
    )
    catalog = {r["building_type"]: r for r in bi.price_catalog(data, {"mason": "urban_workshop"}).to_dicts()}

    assert (catalog["mason"]["base_price"], catalog["mason"]["price_basis"]) == (100.0, "explicit")
    assert catalog["mason"]["increase_per_level_cost"] == 0.25
    assert catalog["mason"]["investment_category"] == "crafts"
    assert (catalog["early_workshop"]["base_price"], catalog["early_workshop"]["price_basis"]) == (200.0, "unlock_age")
    assert catalog["early_workshop"]["increase_per_level_cost"] is None
    assert catalog["late_workshop"]["price_basis"] == "non_gold_price"
    assert catalog["bridge_infrastructure"]["price_basis"] == "unresolved_price"
    assert all(row["base_price"] is not None for row in catalog.values())


def _write_snapshot(dataset: Path, playthrough: str, snapshot: str, buildings: pl.DataFrame) -> None:
    columns = {"snapshot_id": snapshot, "playthrough_id": playthrough, "date": "1400.1.1", "year": 1400, "month": 1,
               "day": 1, "date_sort": 14000101}
    for table, frame in (("buildings", buildings), ("locations", _locations())):
        target = dataset / "tables" / table / f"playthrough_id={playthrough}" / f"{snapshot}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.with_columns([pl.lit(v).alias(k) for k, v in columns.items()]).write_parquet(target)


def test_dataset_update_is_incremental_and_follows_the_catalog(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _write_snapshot(dataset, "run", "s1", _buildings())
    _write_snapshot(dataset, "run", "s2", _buildings().with_columns(pl.col("level") + 1))
    catalog = _price_catalog()
    logs: list[str] = []

    first = bi.update_dataset(dataset, catalog, log=logs.append)
    assert (first.written, first.kept, first.removed) == (2, 0, 0)
    out = dataset / "tables" / bi.TABLE / "playthrough_id=run"
    table = pl.read_parquet(out / "s1.parquet")
    assert set(bi.TABLE_SCHEMA) | {"snapshot_id", "playthrough_id", "date", "year", "date_sort"} <= set(table.columns)
    assert table["snapshot_id"].unique().to_list() == ["s1"]
    assert table["investment"].sum() == pytest.approx(210 + 100 + 50 + 35)

    again = bi.update_dataset(dataset, catalog, log=logs.append)
    assert (again.written, again.kept) == (0, 2)

    cheaper = catalog.with_columns(pl.col("base_price") / 2)
    changed = bi.update_dataset(dataset, cheaper, log=logs.append)
    assert changed.catalog_changed and changed.written == 2
    # the unknown type follows the first-age price too
    assert pl.read_parquet(out / "s1.parquet")["investment"].sum() == pytest.approx((210 + 100 + 50 + 35) / 2)

    (dataset / "tables" / "buildings" / "playthrough_id=run" / "s2.parquet").unlink()
    purged = bi.update_dataset(dataset, cheaper, log=logs.append)
    assert (purged.written, purged.kept, purged.removed) == (0, 1, 1)
    assert not (out / "s2.parquet").exists()
