"""Unit tests for the game-start building placement (no game files needed)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.worldbuilder import start_placement as sp
from prosper_or_perish_constructor.worldbuilder.contract import WorldBuilderConfig

POPS = """locations={

alpha = {
\tdefine_pop = {\ttype = nobles\tsize = 0.5\tculture = swedish\treligion = catholic }
\tdefine_pop = {\ttype = peasants\tsize = 10.000\tculture = swedish\treligion = catholic }
\tdefine_pop = {\ttype = peasants\tsize = 2.000\tculture = finnish\treligion = catholic }
}
beta = {
\tdefine_pop = {\ttype = peasants\tsize = 40.000\tculture = danish\treligion = catholic }
}
gamma = {
\tdefine_pop = {\ttype = peasants\tsize = 6.000\tculture = danish\treligion = catholic }
}
}
"""


def _cfg(tmp_path: Path) -> WorldBuilderConfig:
    return WorldBuilderConfig(handover=tmp_path, geography_export=tmp_path, building_map={}, farm_land={"arable": {"land": 5.0, "reserve": 5.0}}, farm_classes={}, level_scale={}, level_limit=20, goods_floor=-0.2, sync_geography=False, raw={})


def test_parse_pops_reads_type_size_culture_and_religion():
    pops = sp.parse_pops(POPS)
    assert [p.type for p in pops["alpha"]] == ["nobles", "peasants", "peasants"]
    assert pops["alpha"][1].size_k == 10.0 and pops["alpha"][1].culture == "swedish" and pops["beta"][0].religion == "catholic"


def test_plan_places_processors_and_farms_within_land_and_workers(tmp_path):
    pops = sp.parse_pops(POPS)
    locations = pl.DataFrame({
        "location_tag": ["alpha", "beta", "gamma"], "province": ["p1", "p1", "p2"],
        "raw_material": ["iron", "wheat", "wheat"], "vegetation": ["forest", "farmland", "grasslands"], "is_coastal": [False, False, False],
    })
    numbers = {"iron_mine": {"employment_size": 1.0, "pop_type": "laborers", "local_monthly_food": 0.0}, "farming_village": {"employment_size": 1.0, "pop_type": "peasants", "local_monthly_food": 0.0},
               "fruit_orchard": {"employment_size": 1.0, "pop_type": "peasants", "local_monthly_food": 0.0}, "sheep_farms": {"employment_size": 1.0, "pop_type": "peasants", "local_monthly_food": 0.0},
               "cookery": {"employment_size": 1.0, "pop_type": "laborers", "local_monthly_food": 20.0}, "victuals_market_import": {"employment_size": 0.001, "pop_type": "nobles", "local_monthly_food": 90.0}}
    start = sp.StartConfig(processors={"iron": {"building": "iron_mine", "levels": 2}})
    # alpha: 12.5k pops on 60k capacity -> spare (60-12.5-5)/5 = 8 land levels, 12k peasants x 0.6 = 7 worker levels -> farming village? no: iron RGO, forest -> no farm gate
    # beta: 40k pops on 45k capacity -> spare 0 land levels -> no farm although wheat; gamma: 6k pops on 60k -> land 9, workers 3 -> 3 levels
    placements, conversions, table, summary = sp.plan(cfg=_cfg(tmp_path), start=start, locations=locations, capacity_people={"alpha": 60000.0, "beta": 45000.0, "gamma": 60000.0}, pops=pops,
                                                      owners={"alpha": "SWE", "beta": "DAN", "gamma": "DAN"}, ranks={"alpha": "town"}, existing=set(), food_consumption={"nobles": 25.0, "peasants": 1.0, "laborers": 1.5}, numbers=numbers)
    by = {(p.location, p.building): p.level for p in placements}
    assert by[("alpha", "iron_mine")] == 2 and ("alpha", "farming_village") not in by
    assert ("beta", "farming_village") not in by                  # over the spare land: no farm on a full location
    assert by[("gamma", "farming_village")] == 3                  # workers limit 6k x 0.6 = 3
    assert table.filter(pl.col("location_tag") == "beta")["farm_limit"][0] == "land"
    assert summary["farm_land_people"] == 15000.0
    # the mine's laborers come from alpha's largest peasant pop, culture kept
    mine = [c for c in conversions if c.location == "alpha" and c.to_type == "laborers"]
    assert sum(c.size_k for c in mine) == 3.0 and all(c.culture == "swedish" for c in mine)   # 2 for the mine + 1 for the cookery
    # province p1 food: demand = 0.5*25 + 12*1 + 40*1 = 64.5 -> need 64.5*1.1 - 52 subsistence = 18.95 -> 1 cookery level in alpha (town first)
    assert by[("alpha", "cookery")] == 1 and summary["provinces_below_food_target"] == 0


def test_conversions_rewrite_the_pops_file_in_place():
    convs = [sp.PopConversion("alpha", "peasants", "laborers", 2.0, "swedish", "catholic"), sp.PopConversion("alpha", "peasants", "laborers", 1.0, "swedish", "catholic")]
    out = sp.apply_conversions(POPS, convs)
    assert "type = peasants\tsize = 7.000\tculture = swedish" in out
    assert "type = laborers\tsize = 3.000\tculture = swedish\treligion = catholic }\t# pp start: converted from peasants" in out
    assert "size = 2.000\tculture = finnish" in out and "size = 40.000\tculture = danish" in out   # untouched
    assert sp.apply_conversions(POPS, []) == POPS


def test_start_setup_rows_use_the_building_manager_format(tmp_path):
    n = sp.write_start_setup([sp.Placement("alpha", "SWE", "iron_mine", 2), sp.Placement("alpha", "SWE", "cookery", 1)], tmp_path)
    text = (tmp_path / sp.START_SETUP_PATH).read_text(encoding="utf-8-sig")
    assert n == 2 and "building_manager = {" in text and "\tiron_mine = { tag = SWE level = 2 location = alpha }" in text


def test_ranks_and_existing_buildings_come_from_the_vanilla_cities_setup(tmp_path):
    setup = tmp_path / "game/main_menu/setup/start"
    setup.mkdir(parents=True)
    (setup / "07_cities_and_buildings.txt").write_text(
        "locations={\n\t#egypt\n\tcairo = { rank = megalopolis \t\ttown_setup = cairo_city }\n"
        "\tjiaxing = { rank = town town_setup = chinese_town }\n}\n"
        "building_manager = {\n\tcastle \t= { tag = MAM level = 1 location = cairo }\n"
        "\tfarming_village = { tag = CHI level = 2 location = jiaxing }\n}\n",
        encoding="utf-8",
    )
    ranks = sp.load_ranks(tmp_path, tmp_path / "nomod")
    assert ranks == {"cairo": "megalopolis", "jiaxing": "town"}
    assert sp.load_existing_buildings(tmp_path, tmp_path / "nomod") == {("cairo", "castle"), ("jiaxing", "farming_village")}

