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


def _cost_model() -> bi.LocationCostModel:
    static_locations = pl.DataFrame(
        {
            "location_tag": ["york", "leeds", "paris"],
            "topography": ["hills", "mountains", "flatland"],
            "vegetation": ["forest", None, "farmland"],
            "climate": ["oceanic", "oceanic", "continental"],
            "river_level": [0, 2, 5],
            "is_port": [True, False, None],
        }
    )
    return bi.location_cost_model(
        static_locations,
        topography={"hills": -0.08, "mountains": -0.35},
        vegetation={"forest": -0.08},
        climate={"oceanic": 0.02, "continental": -0.02},
        rank={"rural_settlement": -0.3, "city": -0.3},
        static={"development": 0.001, "unemployed_peasants": 0.001, "is_port": 0.15, "river_flowing_through_2": 0.3,
                "river_flowing_through_5": 0.6},
    )


def _snapshot_locations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "location_id": [10, 11, 12],
            "owner": [100, 100, 200],
            "country_tag": ["ENG", "ENG", "FRA"],
            "slug": ["york", "leeds", "paris"],
            "rank": ["rural_settlement", "rural_settlement", "city"],
            "development": [10.0, 0.0, 50.0],
            "unemployed_peasants": [20.0, 0.0, None],
        }
    )


def test_location_efficiency_sums_map_attributes_rank_development_and_unemployed_peasants() -> None:
    model = _cost_model()
    fixed = dict(model.fixed.iter_rows())
    assert fixed["york"] == pytest.approx(-0.08 - 0.08 + 0.02 + 0.15)  # hills, forest, oceanic, port
    assert fixed["leeds"] == pytest.approx(-0.35 + 0.02 + 0.3)  # unknown vegetation counts 0, river level 2
    assert fixed["paris"] == pytest.approx(-0.02 + 0.6)  # flatland and farmland carry nothing, river level 5

    efficiency = dict(bi.location_efficiency(_snapshot_locations(), model).iter_rows())
    assert efficiency[10] == pytest.approx(fixed["york"] - 0.3 + 10 * 0.001 + 20 * 0.001)
    assert efficiency[11] == pytest.approx(fixed["leeds"] - 0.3)
    assert efficiency[12] == pytest.approx(fixed["paris"] - 0.3 + 50 * 0.001)


def test_cost_factor_divides_by_one_plus_efficiency_with_the_engine_floor() -> None:
    frame = pl.DataFrame({"location_efficiency": [0.0, 0.25, -0.2, -0.5, -0.9]})
    factors = frame.select(bi.cost_factor_expr())[:, 0].to_list()
    assert factors == pytest.approx([1.0, 1 / 1.25, 1 / 0.8, 2.0, 2.0])  # never more than twice the list price


def test_local_investment_prices_every_level_at_the_location_factor() -> None:
    model = _cost_model()
    efficiency = bi.location_efficiency(_snapshot_locations(), model)
    table = bi.investment_table(_buildings(), _locations(), _price_catalog(), efficiency)
    rows = {r["building_id"]: r for r in table.to_dicts()}
    york = dict(efficiency.iter_rows())[10]
    # tavern level 3 in york: levels cost 35, 70, 105 (increase per level 1.0), each divided by max(0.5, 1 + e)
    assert rows[1]["investment_local"] == pytest.approx(sum(35 * n for n in (1, 2, 3)) / max(0.5, 1 + york))
    assert rows[1]["cost_factor"] == pytest.approx(1 / max(0.5, 1 + york))
    assert rows[3]["cost_factor"] == pytest.approx(1 / (1 - 0.03 - 0.3))  # leeds: fixed -0.03, rank -0.3
    floor = bi.investment_table(_buildings(), _locations(), _price_catalog(),
                                efficiency.with_columns(pl.lit(-0.9).alias("location_efficiency")))
    assert floor["cost_factor"].to_list() == pytest.approx([2.0] * floor.height)  # the engine floor max(0.5, 1 + e)
    by_country = bi.aggregate(table, ["country_tag"]).sort("country_tag")
    assert by_country["investment_local"].to_list() == pytest.approx(
        [rows[1]["investment_local"] + rows[2]["investment_local"] + rows[3]["investment_local"],
         rows[4]["investment_local"]]
    )
    # without a model the local columns stay empty and the list price is unchanged
    plain = bi.investment_table(_buildings(), _locations(), _price_catalog())
    assert plain["investment_local"].null_count() == plain.height
    assert plain["investment"].to_list() == table["investment"].to_list()


def test_a_replaced_block_ignores_later_injects_like_the_engine(tmp_path: Path) -> None:
    import json

    replace = tmp_path / "pp_00_rivers.txt"
    replace.write_text("TRY_REPLACE:river_flowing_through_1 = {\n\tlocal_build_buildings_efficiency = 0.1\n}\n", encoding="utf-8")
    history = [
        {"file": "vanilla/location.txt", "mode": "CREATE"},
        {"file": str(replace), "mode": "TRY_REPLACE"},
        {"file": "pp_adjustments.txt", "mode": "TRY_INJECT"},
    ]
    value = bi.replaced_block_value(json.dumps(history), "river_flowing_through_1", None, bi.BUILD_EFFICIENCY)
    assert value == pytest.approx(0.1)  # the parser's merge would give 0.1 + the inject
    # no inject after the replace, or no replace at all: the parser's merged value stands
    assert bi.replaced_block_value(json.dumps(history[:2]), "river_flowing_through_1", None, bi.BUILD_EFFICIENCY) is None
    assert bi.replaced_block_value(json.dumps([history[0], history[2]]), "river_flowing_through_1", None,
                                   bi.BUILD_EFFICIENCY) is None


def test_dataset_update_writes_local_investment_and_follows_the_cost_model(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _write_snapshot(dataset, "run", "s1", _buildings())
    target = dataset / "tables" / "locations" / "playthrough_id=run" / "s1.parquet"
    snapshot = pl.read_parquet(target).drop("location_id", "owner", "country_tag")
    pl.concat([_snapshot_locations(), snapshot], how="horizontal").write_parquet(target)
    catalog = _price_catalog()
    model = _cost_model()

    first = bi.update_dataset(dataset, catalog, cost_model=model, log=lambda _: None)
    assert first.written == 1
    out = pl.read_parquet(dataset / "tables" / bi.TABLE / "playthrough_id=run" / "s1.parquet")
    assert out["investment_local"].null_count() == 0
    assert bi.update_dataset(dataset, catalog, cost_model=model, log=lambda _: None).written == 0
    # a changed attribute efficiency rebuilds every snapshot
    dearer = bi.LocationCostModel(model.fixed, {**model.rank, "rural_settlement": -0.4}, model.per_development,
                                  model.per_unemployed_peasant)
    assert bi.update_dataset(dataset, catalog, cost_model=dearer, log=lambda _: None).written == 1
