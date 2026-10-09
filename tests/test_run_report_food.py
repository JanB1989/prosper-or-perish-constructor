from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor import run_report_food as rf
from prosper_or_perish_constructor.run_report_goods import Index


def _food() -> rf.FoodRecipes:
    """Provisioning makes 2 Province Food per level (wheat farm), Cookshops 15 flat, Granges take 24 per level."""
    food = object.__new__(rf.FoodRecipes)
    food.methods = pl.DataFrame({"method": ["provision_wheat"], "per_level": [2.0]})
    food.workers = pl.DataFrame({"building_type": ["wheat_farm", "cookshop", "grange"], "workers_per_level": [1.0, 0.5, 0.1]})
    food.flat = pl.DataFrame({"building_type": ["cookshop", "grange"], "flat": [15.0, -24.0]})
    food.rgo_food = 1.75
    food.rates = {"peasants": 1.0, "nobles": 20.0, "laborers": 1.0}
    food.food_buildings = {"wheat_farm", "cookshop", "grange", "granary"}
    food.digest = "test"
    return food


def _dataset(root: Path, made: float) -> Path:
    """One pool (province 7, two locations in Paris): 10k idle peasants, 2 RGO levels, a wheat farm (2 levels, full
    staff), a Cookshop (1 level, half staffed) and a Grange (1 level)."""
    pops = {f"population_{p}": [0.0, 0.0] for p in rf.POP_TYPES}
    pops["population_peasants"] = [10.0, 5.0]
    pops["population_nobles"] = [0.5, 0.0]
    tables = {
        "province_food": {"province_id": [7], "max_food_value": [1000.0], "food_current": [600.0], "cached_food_change": [4.0],
                          "cached_structural_food_change": [10.0], "base_food_consumption": [made - 10.0],
                          "food_storage_growth_term": [0.5], "food_surplus_growth_term": [0.1]},
        "locations": {"location_id": [1, 2], "slug": ["paris", "versailles"], "province": [7, 7], "province_slug": ["ile_de_france_province"] * 2,
                      "country_tag": ["FRA", "FRA"], "macro_region": ["western_europe"] * 2, "super_region": ["europe"] * 2,
                      "total_population": [10.5, 5.0], "unemployed_peasants": [8.0, 2.0], "unemployed_slaves": [0.0, 0.0],
                      "max_raw_material_workers": [2.0, 0.0], **pops},
        "buildings": {"building_id": [1, 2, 3], "building_type": ["wheat_farm", "cookshop", "grange"], "location_id": [1, 1, 2],
                      "level": [2.0, 1.0, 1.0], "employed": [2.0, 0.25, 0.1], "last_months_profit": [1.0, 0.5, -0.2]},
        "building_methods": {"building_id": [1, 2], "production_method": ["provision_wheat", "serve_stew"]},
    }
    dataset = root / "dataset"
    for table, columns in tables.items():
        folder = dataset / "tables" / table / "playthrough_id=run"
        folder.mkdir(parents=True)
        pl.DataFrame(columns).write_parquet(folder / "s1.parquet")
    return dataset


def test_food_sources_fit_the_exact_store_totals(tmp_path: Path) -> None:
    # estimate: subsistence 10 x 1.487 = 14.87, RGOs 2 x 1.75 = 3.5, farm 2 x 2 = 4, Cookshop 15 x 0.5 = 7.5, Grange -24
    estimate = 10 * rf.SUBSISTENCE_RATE + 3.5 + 4.0 + 7.5 - 24.0
    made = 2.0 * estimate  # the pool made twice the estimate: factor 2
    flows = rf.save_food(_dataset(tmp_path, made), "run", "s1", _food())
    pool = flows["pools"].row(0, named=True)
    assert pool["made"] == pytest.approx(made) and pool["factor"] == pytest.approx(2.0)
    assert pool["sub"] == pytest.approx(2 * 10 * rf.SUBSISTENCE_RATE) and pool["rgos"] == pytest.approx(7.0)
    assert pool["farms"] == pytest.approx(8.0) and pool["kitchens"] == pytest.approx(15.0) and pool["taken"] == pytest.approx(48.0)
    assert pool["other"] == pytest.approx(0.0) and pool["unexplained"] == pytest.approx(0.0)
    assert pool["spoil"] == pytest.approx(6.0)  # structural 10 - change 4
    # inflow = outflow: sources = made + taken; consumption + spoilage + Granges + into the store = made + taken
    sources = pool["sub"] + pool["rgos"] + pool["farms"] + pool["kitchens"] + pool["taverns"] + pool["other"]
    assert sources == pytest.approx(pool["base"] + pool["spoil"] + pool["taken"] + pool["change"] + pool["unexplained"])
    eat = dict(flows["eat"].select("pop_type", "food").iter_rows())
    # 15k peasants x 1 and 0.5k nobles x 20 eat in the ratio 15 : 10
    assert eat["peasants"] == pytest.approx(pool["base"] * 15 / 25) and eat["nobles"] == pytest.approx(pool["base"] * 10 / 25)
    makers = {(r["category"], r["building_type"]): r["food"] for r in flows["makers"].iter_rows(named=True)}
    assert makers[("kitchens", "cookshop")] == pytest.approx(15.0) and makers[("subsistence", None)] == pytest.approx(pool["sub"])
    assert flows["takers"].row(0, named=True)["building_type"] == "grange"
    buildings = {r["building_type"]: r for r in flows["buildings"].iter_rows(named=True)}
    assert buildings["wheat_farm"]["levels"] == 2.0 and buildings["grange"]["profit"] == pytest.approx(-0.2)
    assert dict(flows["locations"].iter_rows())["paris"] == pytest.approx(600.0 / pool["base"])

    index, provinces = Index(), Index()
    provinces.lists.update({"province": [], "country": []})
    provinces.maps.update({"province": {}, "country": {}})
    encoded = rf.encode_food(flows, index, provinces)
    assert len(encoded["pools"][0]) == len(rf.POOL_COLUMNS)  # one value per pool column the page reads (it adds up "made" itself)


def test_a_pool_beyond_the_factor_limits_keeps_the_rest_as_other_sources(tmp_path: Path) -> None:
    estimate = 10 * rf.SUBSISTENCE_RATE + 3.5 + 4.0 + 7.5 - 24.0
    flows = rf.save_food(_dataset(tmp_path, 10 * estimate), "run", "s1", _food())
    pool = flows["pools"].row(0, named=True)
    assert pool["factor"] == pytest.approx(rf.FACTOR_LIMITS[1])
    assert pool["other"] == pytest.approx(10 * estimate - rf.FACTOR_LIMITS[1] * estimate)


def test_food_page_reads_its_data_files() -> None:
    from prosper_or_perish_constructor.run_report_food_page import food_page_html

    page = food_page_html("Run x", (1337, 1400))
    assert "food/index.json" in page and "goods/index.json" in page and "type: 'sankey'" in page and "data-v=recipes" in page
