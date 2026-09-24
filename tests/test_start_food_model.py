"""The engine start state the food budget assumes: setup promotion, RGO workers, local food modifiers."""

from __future__ import annotations

from collections import Counter

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor.worldbuilder import food_check
from prosper_or_perish_constructor.worldbuilder import start_placement as sp
from prosper_or_perish_constructor.worldbuilder.start_rules import Rules
from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation


def block(text):
    return CList(entries=parse_text(text).entries, items=[])


def test_start_config_reads_engine_promotion_and_rgo_workers():
    start = sp.StartConfig.from_raw({"engine_promotion": {"town": {"nobles": 9, "laborers": "100"}}, "rgo_workers_k": {"town": 2}})
    assert start.engine_promotion == {"town": {"nobles": 9.0, "laborers": 100.0}}
    assert start.rgo_workers_k == {"town": 2.0}
    assert sp.StartConfig().engine_promotion["rural_settlement"]["nobles"] > 0   # defaults carry the fitted rates


def test_estimate_start_pops_promotes_out_of_peasants_and_never_more_than_exist():
    start = sp.StartConfig(engine_promotion={"town": {"nobles": 10, "laborers": 100}})
    pops = [sp.Pop("peasants", 90, "a", "r"), sp.Pop("burghers", 10, "a", "r")]
    est = sp.estimate_start_pops(pops, "town", start)
    assert est["nobles"] == 1.0 and est["laborers"] == 10.0 and est["peasants"] == 79.0 and est["burghers"] == 10.0
    assert sum(est.values()) == 100.0
    # a location of nearly only elites cannot lose more peasants than it has: shares scale down together
    est = sp.estimate_start_pops([sp.Pop("peasants", 2, "a", "r"), sp.Pop("burghers", 98, "a", "r")], "town", start)
    assert abs(est["peasants"]) < 1e-9 and abs(est["nobles"] / est["laborers"] - 0.1) < 1e-9
    assert sp.estimate_start_pops(pops, "rural_settlement", start)["peasants"] == 90.0   # no rates: unchanged


def test_worker_pool_only_uses_the_peasants_left_after_promotion_and_rgo():
    start = sp.StartConfig(peasant_work_share=1.0, laborer_conversion_share=1.0)
    pool = sp._Workers([sp.Pop("peasants", 10, "a", "r")], start, peasants_k=4)
    assert pool.levels(10, 1, "peasants") == 4
    assert pool.levels(10, 1, "laborers") == 4


def test_food_modifier_sums_rank_and_class_rows_including_cancelling_injects():
    r = Rules.__new__(Rules)
    r.ranks = {"rural_settlement": block("rank_modifier = { local_monthly_food_modifier = -0.1 local_population_capacity = 5 }")}
    r.classes = {
        "vegetation": {"desert": block("location_modifier = { local_monthly_food_modifier = -0.33 } location_modifier = { local_monthly_food_modifier = 0.33 }")},
        "topography": {"hills": block("location_modifier = { local_monthly_food_modifier = -0.1 }")},
        "climate": {},
    }
    assert abs(r.food_modifier("rural_settlement", {"vegetation": "desert", "topography": "hills", "climate": "arid"}) - (-0.2)) < 1e-9
    assert r.food_modifier("town", {}) == 0.0


def test_location_pops_top_up_conversions_only_beyond_the_engine_promotion():
    sim = Simulation.__new__(Simulation)
    sim.pops = {"x": [sp.Pop("peasants", 100, "a", "r")]}
    sim.est_pops = {"x": {"peasants": 90.0, "laborers": 8.0, "nobles": 2.0}}
    pops = sim.location_pops("x", Counter({"laborers": 3.0}))     # 3k converted for a mine: inside the engine's 8k
    assert pops["laborers"] == 8.0 and pops["nobles"] == 2.0 and pops["peasants"] == 90.0
    pops = sim.location_pops("x", Counter({"laborers": 12.0}))    # 12k converted: 4k beyond the promotion
    assert pops["laborers"] == 12.0 and pops["peasants"] == 86.0
    assert sum(pops.values()) == 100.0


def test_parse_provinces_reads_the_food_block_and_owner(tmp_path):
    text = "\n".join([
        "SAV", "metadata={", "\tdate=1337.5.4", "}",
        "provinces={", "\tdatabase={", "0={", "\tcapital=1", '\tprovince_definition="uppland_province"', "\towner=3",
        "\tfood={", "\t\tmonth=0.6", "\t\tcurrent=829.5", "\t}", "\tmax_food_value=51106.1", "\tcached_food_change=-22.8",
        "\tcached_structural_food_change=-10.0", "\tbase_food_consumption=68.06", "\tlast_month_produced={", "\t\twheat=1.0", "\t}", "}",
        "1={", '\tprovince_definition="empty_province"', "\tbase_food_consumption=0", "}", "\t}", "}", "countries={", "}",
    ])
    path = tmp_path / "save.eu5"
    path.write_text(text, encoding="utf-8")
    frame = food_check.parse_provinces(path)
    assert frame.height == 2
    row = frame.filter(frame["province_definition"] == "uppland_province").row(0, named=True)
    assert row["owner_country_id"] == 3 and row["food_current"] == 829.5 and row["cached_structural_food_change"] == -10.0
    assert row["base_food_consumption"] == 68.06 and row["max_food_value"] == 51106.1
    assert frame.filter(frame["province_definition"] == "empty_province")["owner_country_id"][0] is None


def test_food_chain_plan_balances_victuals_with_the_import_markets():
    from prosper_or_perish_constructor.worldbuilder.start_simulation import plan_food_chain

    # 60 food per import, 18 net per cookery, 0.65 victuals per cookery, 1.2 per import, imports buy 80 %
    cookery, imports = plan_food_chain(1000, 0.0, 60, 18, 0.65, 1.2, 0.8)
    assert cookery > 0 and imports > 0
    assert cookery * 18 + imports * 60 >= 1000
    assert abs(imports * 1.2 - 0.8 * cookery * 0.65) < 1.2 + 1e-9          # imports absorb 80 % of the new victuals
    # an existing victuals surplus feeds imports first; no cookeries when it covers the deficit
    assert plan_food_chain(100, 500.0, 60, 18, 0.65, 1.2, 0.8) == (0, 2)
    assert plan_food_chain(0, 500.0, 60, 18, 0.65, 1.2, 0.8) == (0, 0)


def test_worker_budgets_for_farms_and_conversions_do_not_starve_each_other():
    start = sp.StartConfig(peasant_work_share=0.6, laborer_conversion_share=0.5)
    pool = sp._Workers([sp.Pop("peasants", 10, "a", "r")], start)
    pool.take(6, 1, "peasants", "x", [])          # farms use the whole work share
    assert pool.levels(10, 1, "laborers") == 4    # conversions still get the peasants that are left (10 - 6)
    conversions = []
    pool.take(4, 1, "laborers", "x", conversions)
    assert sum(c.size_k for c in conversions) == 4 and pool.levels(1, 1, "laborers") == 0


def test_victuals_pop_factors_multiply_demand_add_by_demand_multiply():
    r = Rules.__new__(Rules)
    r.goods = {"victuals": block("demand_add = { nobles = 0.01 peasants = 0.01 } demand_multiply = { nobles = 4 }")}
    assert r.victuals_pop_factors() == {"nobles": 0.04, "peasants": 0.01}
    assert r.victuals_pop_factors("absent") == {}


def test_start_config_merges_victuals_overrides_into_defaults():
    start = sp.StartConfig.from_raw({"victuals": {"absorb_share": 0.7, "consumers": {"victuals_market_import": 1.0}}})
    assert start.victuals["absorb_share"] == 0.7 and start.victuals["consumers"] == {"victuals_market_import": 1.0}
    assert start.victuals["producers"]["cookery"] == sp.DEFAULT_VICTUALS["producers"]["cookery"]


def test_province_food_per_level_reads_the_provisioning_and_serve_methods():
    import pytest

    from prosper_or_perish_constructor.worldbuilder.start_simulation import province_food_per_level

    r = Rules.__new__(Rules)
    r.buildings = {
        "wheat_farm": block(
            "unique_production_methods = { pp_wheat_farm_base = { produced = wheat output = 0.06 } } "
            "unique_production_methods = { pp_wheat_farm_provision = { wheat = 0.08 produced = local_food output = 0.96 } "
            "pp_wheat_farm_sell_surplus = { produced = province_food_sales output = 0.005 } }"
        ),
        "wheat_farmstead": block("unique_production_methods = { pp_wheat_farmstead_provision = { produced = local_food output = 1.28 } }"),
        "fishing_village": block("unique_production_methods = { pp_fishing_village_provision = { fish = 0.067 produced = local_food output = 0.8 } }"),
        "cookery": block(
            "unique_production_methods = { pp_cookery_khichdi_serve = { produced = local_food output = 24.99 } "
            "pp_cookery_livestock_pottage_serve = { produced = local_food output = 27.57 } "
            "pp_cookery_livestock_pottage = { produced = victuals output = 0.919 } }"
        ),
        "iron_mine": block("max_levels = 2"),
    }
    spec = sp.StartConfig().province_food
    assert province_food_per_level(r, spec) == {"cookery": 27.57, "fishing_village": 0.8, "wheat_farm": 0.96, "wheat_farmstead": 1.28}
    assert province_food_per_level(r, {**spec, "per_level": {"iron_mine": 2}})["iron_mine"] == 2.0
    with pytest.raises(ValueError):
        province_food_per_level(r, {**spec, "serve": {"cookery": "pp_cookery_missing_serve"}})


def test_start_config_merges_the_province_food_section():
    start = sp.StartConfig.from_raw({"province_food": {"serve": {"cookery": "pp_cookery_kheer_serve"}, "per_level": {"x": "1.5"}}})
    assert start.province_food["serve"] == {"cookery": "pp_cookery_kheer_serve"} and start.province_food["per_level"] == {"x": 1.5}
    assert start.province_food["method_pattern"] == sp.DEFAULT_PROVINCE_FOOD["method_pattern"]
    assert sp.StartConfig().province_food == sp.DEFAULT_PROVINCE_FOOD


def test_province_food_is_added_per_level_unscaled_and_feeds_the_cookery():
    from types import SimpleNamespace

    sim = Simulation.__new__(Simulation)
    sim.numbers = {
        "wheat_farm": {"employment_size": 1, "pop_type": "peasants", "local_monthly_food": 1.5},
        "cookery": {"employment_size": 1, "pop_type": "laborers", "local_monthly_food": 0},
    }
    sim.province_food = {"wheat_farm": 0.96, "cookery": 27.57}
    sim.food_mult = {"x": 0.9}
    sim.food = {"peasants": 1.0, "laborers": 1.5}
    sim.rules = SimpleNamespace(subsistence=1.5)
    assert abs(sim.food_per_level("wheat_farm", 0.9) - (0.9 * 1.5 + 0.96)) < 1e-9     # local food scaled, Province Food not
    assert sim.food_per_level("absent") == 0.0
    # the cookery's Serve output minus the laborer's lost subsistence (scaled) and extra consumption
    assert abs(sim.cookery_net_food("x") - (27.57 - 0.9 * 1.5 - 0.5)) < 1e-9
    assert Simulation.province_food == {}                                               # class default: no term
