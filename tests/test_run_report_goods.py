from pathlib import Path

import numpy as np
import polars as pl
import pytest

from prosper_or_perish_constructor import run_report_goods as rg


def _recipes() -> rg.Recipes:
    """Two methods: weaving (2 wool -> 1 cloth per level, 0.5 k workers) and grazing (4 wool per level, 1 k workers)."""
    recipes = object.__new__(rg.Recipes)
    recipes.outputs = pl.DataFrame({"method": ["weave", "graze"], "good_id": ["cloth", "wool"], "per_level": [1.0, 4.0]})
    recipes.inputs = pl.DataFrame({"method": ["weave"], "good_id": ["wool"], "per_level": [2.0]})
    recipes.workers = pl.DataFrame({"building_type": ["weaver", "sheep_farm"], "workers_per_level": [0.5, 1.0]})
    recipes.method_building = {"weave": "weaver", "graze": "sheep_farm"}
    recipes.categories = {"weaver": "crafts_category", "sheep_farm": "farm_category"}
    recipes.digest = "test"
    return recipes


def _dataset(root: Path) -> Path:
    """One save, two markets: Paris (western_europe) weaves cloth from its wool RGO and a sheep farm, London weaves
    at half staffing and imports wool."""
    tables = {
        "locations": {"location_id": [1, 2], "slug": ["paris", "london"], "market_id": [1, 2], "raw_material": ["wool", None],
                      "rgo_employed": [2.0, 0.0], "macro_region": ["western_europe", "british_isles"], "super_region": ["europe", "europe"]},
        "markets": {"market_id": [1, 2], "center_location_id": [1, 2]},
        "buildings": {"building_id": [10, 11, 12], "building_type": ["weaver", "weaver", "sheep_farm"], "location_id": [1, 2, 1],
                      "market_id": [1, 2, 1], "level": [2.0, 1.0, 1.0], "employed": [1.0, 0.25, 1.0]},
        "building_methods": {"building_id": [10, 11, 12], "production_method": ["weave", "weave", "graze"]},
        "market_goods": {
            "market_id": [1, 1, 2, 2], "good_id": ["cloth", "wool", "cloth", "wool"], "price": [3.0, 1.0, 3.5, 1.2],
            "default_price": [3.0, 1.0, 3.0, 1.0], "supply": [3.0, 10.0, 1.0, 1.0], "demand": [2.0, 4.0, 1.0, 1.0],
            "stockpile": [5.0, 0.0, 0.0, 0.0], "supplied_Production": [3.0, 10.0, 1.0, 0.0],
            "demanded_Building": [0.0, 4.0, 0.0, 1.0], "taken_Building": [0.0, 3.0, 0.0, 1.0],
            "demanded_Pops": [2.0, 0.0, 1.0, 0.0], "taken_Pops": [2.0, 0.0, 0.5, 0.0],
            "supplied_Trade": [0.0, 0.0, 0.0, 1.0], "demanded_Trade": [0.0, 1.0, 0.0, 0.0],
        },
    }
    dataset = root / "dataset"
    for table, columns in tables.items():
        folder = dataset / "tables" / table / "playthrough_id=run"
        folder.mkdir(parents=True)
        pl.DataFrame(columns).write_parquet(folder / "s1.parquet")
    return dataset


def test_fit_factors_split_buildings_and_rgos() -> None:
    # buildings alone make 2 x recipe, RGOs alone 0.5 x; a mixed market follows both
    actual = np.array([4.0, 1.0, 2.0 * 3 + 0.5 * 4])
    buildings, rgos = np.array([2.0, 0.0, 3.0]), np.array([0.0, 2.0, 4.0])
    fb, fr = rg.fit_factors(actual, buildings, rgos)
    assert fb == pytest.approx(2.0) and fr == pytest.approx(0.5)
    # a kind with no markets falls back to 1
    assert rg.fit_factors(np.array([3.0]), np.array([3.0]), np.array([0.0])) == (pytest.approx(1.0), 1.0)


def test_save_flows_add_up_to_the_market_totals(tmp_path: Path) -> None:
    flows = rg.save_flows(_dataset(tmp_path), "run", "s1", _recipes())
    producers = flows["producers"]
    made = dict(producers.group_by("good_id").agg(pl.col("amount").sum()).iter_rows())
    assert made["cloth"] == pytest.approx(4.0) and made["wool"] == pytest.approx(10.0)
    cloth = {r["region"]: r for r in producers.filter(pl.col("good_id") == "cloth").iter_rows(named=True)}
    # Paris: recipe 2 (2 levels, full staff) -> 3 made; London: recipe 0.5 (half staffed) -> 1 made
    assert cloth["western_europe"]["recipe"] == pytest.approx(2.0) and cloth["western_europe"]["amount"] == pytest.approx(3.0)
    assert cloth["british_isles"]["recipe"] == pytest.approx(0.5) and cloth["british_isles"]["amount"] == pytest.approx(1.0)
    wool = {r["building_type"]: r for r in producers.filter(pl.col("good_id") == "wool").iter_rows(named=True)}
    assert set(wool) == {"sheep_farm", rg.RGO} and all(r["amount"] > 0 for r in wool.values())
    assert wool[rg.RGO]["workers"] == pytest.approx(2.0) and wool["sheep_farm"]["levels"] == pytest.approx(1.0)
    used = {r["region"]: r for r in flows["consumers"].iter_rows(named=True)}
    assert used["western_europe"]["wanted"] == pytest.approx(4.0) and used["western_europe"]["received"] == pytest.approx(3.0)
    assert used["british_isles"]["received"] == pytest.approx(1.0)
    pops = {(r["good_id"], r["region"]): r for r in flows["demand"].filter(pl.col("bucket") == "Pops").iter_rows(named=True)}
    assert pops[("cloth", "british_isles")]["wanted"] == 1.0 and pops[("cloth", "british_isles")]["received"] == 0.5
    imports = flows["supply"].filter((pl.col("bucket") == "Trade") & (pl.col("good_id") == "wool"))
    assert imports.select("region", "amount").rows() == [("british_isles", 1.0)]

    encoded = rg.encode_save(flows, rg.Index())
    assert {k: len(v) for k, v in encoded.items()}["p"] == producers.height


def test_goods_page_reads_its_data_files() -> None:
    from prosper_or_perish_constructor.run_report_goods_page import goods_page_html

    page = goods_page_html("Run x", (1337, 1400))
    assert "goods/index.json" in page and "goods/summary.json" in page and "id=goodlist" in page and "type: 'sankey'" in page
