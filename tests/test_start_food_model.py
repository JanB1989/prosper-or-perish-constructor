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
    start = sp.StartConfig.from_raw({"victuals": {"absorb_share": 0.7, "consumers": {"tavern": 1.0}}})
    assert start.victuals["absorb_share"] == 0.7 and start.victuals["consumers"] == {"tavern": 1.0}
    assert start.victuals["producers"]["cookshop"] == sp.DEFAULT_VICTUALS["producers"]["cookshop"]


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
        "cookshop": block(
            "unique_production_methods = { pp_cookshop_khichdi_serve = { produced = local_food output = 24.99 } "
            "pp_cookshop_livestock_pottage_serve = { produced = local_food output = 27.57 } "
            "pp_cookshop_livestock_pottage = { produced = victuals output = 0.919 } }"
        ),
        "iron_mine": block("max_levels = 2"),
    }
    spec = sp.StartConfig().province_food
    assert province_food_per_level(r, spec) == {"cookshop": 27.57, "fishing_village": 0.8, "wheat_farm": 0.96, "wheat_farmstead": 1.28}
    assert province_food_per_level(r, {**spec, "per_level": {"iron_mine": 2}})["iron_mine"] == 2.0
    with pytest.raises(ValueError):
        province_food_per_level(r, {**spec, "serve": {"cookshop": "pp_cookshop_missing_serve"}})


def test_start_config_merges_the_province_food_section():
    start = sp.StartConfig.from_raw({"province_food": {"serve": {"cookshop": "pp_cookshop_kheer_serve"}, "per_level": {"x": "1.5"}}})
    assert start.province_food["serve"] == {"cookshop": "pp_cookshop_kheer_serve"} and start.province_food["per_level"] == {"x": 1.5}
    assert start.province_food["method_pattern"] == sp.DEFAULT_PROVINCE_FOOD["method_pattern"]
    assert sp.StartConfig().province_food == sp.DEFAULT_PROVINCE_FOOD


def test_province_food_is_added_per_level_unscaled_and_feeds_the_cookshop():
    from types import SimpleNamespace

    sim = Simulation.__new__(Simulation)
    sim.numbers = {
        "wheat_farm": {"employment_size": 1, "pop_type": "peasants", "local_monthly_food": 1.5},
        "cookshop": {"employment_size": 1, "pop_type": "laborers", "local_monthly_food": 0},
    }
    sim.province_food = {"wheat_farm": 0.96, "cookshop": 27.57}
    sim.food_mult = {"x": 0.9}
    sim.food = {"peasants": 1.0, "laborers": 1.5}
    sim.rules = SimpleNamespace(subsistence=1.5)
    assert abs(sim.food_per_level("wheat_farm", 0.9) - (0.9 * 1.5 + 0.96)) < 1e-9     # local food scaled, Province Food not
    assert sim.food_per_level("absent") == 0.0
    # the Cookshop's Serve output (every level serves) and its drink slot's Province Food, minus the laborer's lost
    # subsistence (the location's yield: define x local food modifier without a fitted one) and extra consumption
    assert abs(sim.cookshop_net_food("x") - (1.0 * 27.57 + 12.0 - 0.9 * 1.5 - 0.5)) < 1e-9
    assert Simulation.province_food == {}                                               # class default: no term


# ------------------------------------------------------------------ food model v2 (start_food_model_v2)
def test_food_model_config_reads_the_section_and_keeps_defaults():
    from prosper_or_perish_constructor.worldbuilder import start_food_model_v2 as fm

    cfg = fm.FoodModelConfig.from_raw({"yield_rank": {"town": "0.9"}, "yield_climate": {"arid": 0.8}, "capacity": {"per_location": 50},
                                       "subsistence_pop_types": ["peasants"], "cookshop_serve_share": 0.3})
    assert cfg.yield_rank == {"town": 0.9} and cfg.yield_climate == {"arid": 0.8}
    assert cfg.capacity["per_location"] == 50.0 and cfg.capacity["per_development"] == fm.DEFAULT_CAPACITY["per_development"]
    assert cfg.subsistence_pop_types == ("peasants",) and cfg.cookshop_serve_share == 0.3
    assert fm.FoodModelConfig().subsistence_pop_types == ("peasants", "slaves")      # laborers do not farm


def test_location_yield_scales_the_define_by_the_static_stack_rank_and_climate():
    from prosper_or_perish_constructor.worldbuilder import start_food_model_v2 as fm

    cfg = fm.FoodModelConfig(yield_rank={"town": 0.8}, yield_climate={"arid": 0.5})
    assert fm.location_yield(1.5, 0.2, "town", "arid", cfg) == 1.5 * 1.2 * 0.8 * 0.5
    assert fm.location_yield(1.5, 0.0, "city", "oceanic", cfg) == 1.5          # unfitted classes keep factor 1
    assert fm.location_yield(1.5, -2.0, "town", None, cfg) == 0.0               # a stack below -100 % yields nothing


def test_static_food_modifier_sums_rank_classes_and_setup_statics():
    from prosper_or_perish_constructor.worldbuilder import start_food_model_v2 as fm

    r = Rules.__new__(Rules)
    r.ranks = {"rural_settlement": block("rank_modifier = { local_monthly_food_modifier = 0.1 } rank_modifier = { local_monthly_food_modifier = -0.1 }")}
    r.classes = {"vegetation": {"desert": block("location_modifier = { local_monthly_food_modifier = -0.33 }")}}
    r.statics = {"volcanic_soil": block("local_monthly_food_modifier = 0.5 local_population_capacity = 3"), "pp_wb_coastal": block("local_food_capacity = 10")}
    assert abs(fm.static_food_modifier(r, "rural_settlement", {"vegetation": "desert"}, ["volcanic_soil", "pp_wb_coastal", "absent"]) - 0.17) < 1e-9


def test_overpopulation_adds_half_the_peasant_food_per_unit_over_capacity():
    from prosper_or_perish_constructor.worldbuilder import start_food_model_v2 as fm

    cfg = fm.FoodModelConfig()
    assert fm.overpopulation_food(80, 100, 50, cfg) == 0.5 * 80 * 1.0            # twice the capacity: +50 %
    assert fm.overpopulation_food(80, 40, 50, cfg) == 0.0
    assert fm.overpopulation_food(80, 40, 0, cfg) == 0.0                          # no capacity known: no term


def test_food_capacity_and_the_cookshop_makes_no_victuals():
    from prosper_or_perish_constructor.worldbuilder import start_food_model_v2 as fm

    cfg = fm.FoodModelConfig(capacity={"per_development": 30.0, "per_population_k": 4.0, "per_location": 100.0, "rank": {"town": 500.0}})
    assert fm.food_capacity([(10, 20, "town"), (0, 5, "rural_settlement")], cfg) == 300 + 80 + 100 + 500 + 20 + 100
    # the Cookshop serves everything (no Preserve recipes); victuals come from the Victualling Yard only
    assert cfg.cookshop_serve_share == 1.0 and not hasattr(fm, "cookshop_victuals")
    assert cfg.tavern_victuals_per_level == 2.0 and cfg.yard_victuals_per_level == 1.5


def test_fit_yields_recovers_rank_and_climate_factors():
    import numpy as np

    from prosper_or_perish_constructor.worldbuilder import start_food_model_v2 as fm

    rng = np.random.default_rng(1)
    n_loc, n_pool = 600, 150
    pool = rng.integers(0, n_pool, n_loc)
    jobless = rng.uniform(1000, 5000, n_loc)
    ranks = list(rng.choice(["rural_settlement", "town"], n_loc))
    climates = list(rng.choice(["arid", "oceanic"], n_loc))
    true_r = {"rural_settlement": 1.05, "town": 0.9}
    true_c = {"arid": 0.8, "oceanic": 1.2}
    w = {"arid": jobless[np.array(climates) == "arid"].sum(), "oceanic": jobless[np.array(climates) == "oceanic"].sum()}
    s = (true_c["arid"] * w["arid"] + true_c["oceanic"] * w["oceanic"]) / (w["arid"] + w["oceanic"])   # normalised mean 1
    y = np.array([1.5 * true_r[r] * true_c[c] for r, c in zip(ranks, climates)])
    fixed = rng.uniform(0, 100, n_pool)
    overpop = rng.uniform(0, 50, n_pool)
    production = np.bincount(pool, y * jobless, n_pool) + fixed - overpop
    fit = fm.fit_yields(pool, jobless, np.zeros(n_loc), ranks, climates, overpop, fixed, production, define=1.5, min_weight_k=1.0)
    assert fit["r2_production"] > 0.999 and abs(fit["aggregate_error"]) < 1e-6
    assert abs(fit["yield_climate"]["arid"] - true_c["arid"] / s) < 1e-3
    assert abs(fit["yield_rank"]["town"] - true_r["town"] * s) < 1e-3


def test_budget_v2_jobless_laborers_do_not_farm_and_cookshops_serve_their_share():
    from types import SimpleNamespace

    from prosper_or_perish_constructor.worldbuilder.start_food_model_v2 import FoodModelConfig

    sim = Simulation.__new__(Simulation)
    sim.rules = SimpleNamespace(subsistence=1.5)
    sim.start = sp.StartConfig()
    sim.food_model = FoodModelConfig(cookshop_serve_share=0.5, capacity={"per_development": 0.0, "per_population_k": 0.0, "per_location": 0.0, "rank": {}})
    sim.pops = {"x": [sp.Pop("peasants", 100, "a", "r"), sp.Pop("laborers", 20, "a", "r")]}
    sim.groups = {("AAA", "p"): ["x"]}
    sim.catchments = {("AAA", "p"): "m"}
    sim.locations = {"x": {"region": "r"}}
    sim.attrs = {}
    sim.food = {"peasants": 1.0, "laborers": 1.5}
    sim.food_mult = {"x": 1.0}
    sim.yield_k = {"x": 1.4}
    sim.rgo_k = {"x": 2.0}
    sim.base = {"x": {"modifiers": {"local_population_capacity": 60.0}, "location_rank": "rural_settlement", "development": 0.0}}
    sim.raw = {}
    sim.conversions = []
    sim.numbers = {"cookshop": {"employment_size": 1, "pop_type": "laborers", "local_monthly_food": 0},
                   "wheat_farm": {"employment_size": 1, "pop_type": "peasants", "local_monthly_food": 1.5}}
    sim.province_food = {"cookshop": 27.57, "wheat_farm": 0.96}
    from collections import defaultdict
    sim.counts = defaultdict(Counter, {"x": Counter({"cookshop": 2, "wheat_farm": 3})})
    sim.staffed = defaultdict(Counter, {"x": Counter({"cookshop": 2, "wheat_farm": 3})})
    b = sim.budgets()[("AAA", "p")]
    jobless = 100 - 3 - 2.0                                  # peasants minus farm staff minus RGO workers
    assert abs(b["subsistence"] - 1.4 * jobless) < 1e-9 and b["subsistence_workers_k"] == jobless
    assert abs(b["demand_base"] - 130) < 1e-9
    assert abs(b["overpopulation"] - 0.5 * 100 * (120 / 60 - 1)) < 1e-9     # twice the capacity
    assert abs(b["serve_food"] - 2 * (0.5 * 27.57 + 12.0)) < 1e-9          # Serve share + the drink slot
    assert abs(b["building_food"] - 3 * (1.5 + 0.96)) < 1e-9
    assert abs(b["day0_production"] - (1.4 * jobless + 3 * 1.5 - b["overpopulation"])) < 1e-9   # no Provisioning, no Serve yet
    assert abs(b["R"] - (b["subsistence"] + b["building_food"] + b["serve_food"]) / b["demand"]) < 1e-9


def test_linear_engine_promotion_follows_the_rgo_not_the_population():
    start = sp.StartConfig(engine_promotion={"rural_settlement": {"nobles": 2.0, "laborers": 100.0}},
                           engine_promotion_linear={"rural_settlement": {"laborers": (1.0, 0.01, 0.1)}})
    est = sp.estimate_start_pops([sp.Pop("peasants", 300, "a", "r")], "rural_settlement", start, development=20)
    assert abs(est["laborers"] - (1.0 + 0.01 * 300 + 0.1 * 20)) < 1e-9       # 6k, not 30k
    assert abs(est["nobles"] - 0.6) < 1e-9                                   # per-1,000 share where no linear term
    raw = sp.StartConfig.from_raw({"engine_promotion_linear": {"town": {"laborers": [1, "0.02", 0]}}})
    assert raw.engine_promotion_linear == {"town": {"laborers": (1.0, 0.02, 0.0)}}
