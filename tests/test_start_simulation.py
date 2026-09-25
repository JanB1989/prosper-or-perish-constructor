from collections import Counter

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor.worldbuilder import start_placement as sp
from prosper_or_perish_constructor.worldbuilder.start_rules import Rules
from prosper_or_perish_constructor.worldbuilder.start_simulation import setup_counts


def block(text):
    return CList(entries=parse_text(text).entries, items=[])


def rules():
    r = Rules.__new__(Rules)
    r.values = {}
    r.triggers = {}
    r.buildings = {}
    r.unsupported = Counter()
    return r


def test_cap_evaluates_conditions_floor_and_game_bound_semantics():
    r = rules()
    r.values["cap"] = block(
        "add = 1 add = { value = development multiply = 0.12 } if = { limit = { is_coastal = yes } add = 2 } min = 0 max = 5 floor = yes"
    )
    assert r.value("cap", {"development": 10, "is_coastal": False}) == 2
    assert r.value("cap", {"development": 10, "is_coastal": True}) == 4
    assert r.value("cap", {"development": 100, "is_coastal": True}) == 5


def test_unknown_cap_syntax_cannot_grant_building_levels():
    r = rules()
    r.buildings["test"] = block("rural_settlement = yes max_levels = unknown_cap")
    assert r.cap("test", {"location_rank": "rural_settlement"}) == 0
    assert r.unsupported


def test_native_safe_equality_is_evaluated_for_rank_caps():
    r = rules()
    assert r.test(
        parse_text("test = { location_rank ?= location_rank:city }").entries[0].value,
        {"location_rank": "city"},
    )
    assert not r.test(
        parse_text("test = { location_rank ?= location_rank:city }").entries[0].value,
        {"location_rank": "town"},
    )


def test_shared_capacity_counts_other_buildings():
    r = rules()
    r.values["shared"] = block(
        'value = 4 subtract = { value = "location_building_level(building_type:other)" }'
    )
    r.buildings["test"] = block("rural_settlement = yes max_levels = shared")
    assert r.cap("test", {"buildings": {"other": 3}}) == 1


def test_live_waterway_state_changes_cap_without_rebuilding():
    r = rules()
    v = block(
        "value = 1 if = { limit = { any_neighbor_location = { has_variable = pp_navigation_map_state var:pp_navigation_map_state = 4 } } add = 2 }"
    )
    assert (
        r.value(v, {"neighbors": [{"variables": {"pp_navigation_map_state": 2}}]}) == 1
    )
    assert (
        r.value(v, {"neighbors": [{"variables": {"pp_navigation_map_state": 4}}]}) == 3
    )


def test_worker_pool_cannot_double_use_farm_workers_or_create_nobles():
    start = sp.StartConfig(peasant_work_share=0.6, laborer_conversion_share=0.5)
    pool = sp._Workers([sp.Pop("peasants", 10, "a", "r")], start)
    conversions = []
    pool.take(6, 1, "peasants", "x", conversions)       # the whole work share (60 %) staffs farms
    assert pool.levels(5, 1, "laborers") == 4           # conversions only get the peasants that are left
    assert pool.levels(1, 0.001, "nobles") == 0
    pool.take(4, 1, "laborers", "x", conversions)
    assert pool.levels(1, 1, "laborers") == 0


def test_worker_conversion_uses_multiple_cultures_without_understaffing():
    pool = sp._Workers(
        [sp.Pop("peasants", 2, "a", "r"), sp.Pop("peasants", 2, "b", "r")],
        sp.StartConfig(peasant_work_share=1, laborer_conversion_share=1),
    )
    conversions = []
    pool.take(3, 1, "laborers", "x", conversions)
    assert sum(c.size_k for c in conversions) == 3
    assert {c.culture for c in conversions} == {"a", "b"}


def test_conversion_spanning_identical_pop_rows_preserves_total():
    text = "locations = {\nx = {\n define_pop = { type = peasants size = 1 culture = a religion = r }\n define_pop = { type = peasants size = 2 culture = a religion = r }\n}\n}\n"
    result = sp.parse_pops(
        sp.apply_conversions(
            text, [sp.PopConversion("x", "peasants", "laborers", 2.5, "a", "r")]
        )
    )["x"]
    assert sum(p.size_k for p in result) == 3
    assert sum(p.size_k for p in result if p.type == "laborers") == 2.5


def test_multiline_setup_counts_and_ranks_are_not_lost(tmp_path):
    root = tmp_path / "game/main_menu/setup/start"
    root.mkdir(parents=True)
    p = root / "07_cities_and_buildings.txt"
    p.write_text(
        "locations = { alpha = { rank = city } }\nbuilding_manager = { farm = {\n location = alpha\n level = 3\n tag = SWE\n} }"
    )
    assert setup_counts(p)["alpha"]["farm"] == 3
    assert sp.load_ranks(tmp_path, tmp_path / "absent") == {"alpha": "city"}


def test_initial_placements_do_not_spend_on_start_navigation_bonus():
    r = rules()
    r.buildings["victuals_market"] = block("rural_settlement = yes max_levels = cap")
    r.values["cap"] = block(
        "value = 2 if = { limit = { any_neighbor_location = { has_variable = pp_navigation_map_state } } add = 5 }"
    )
    ctx = {"neighbors": [{"variables": {"pp_navigation_map_state": 1}}]}
    assert r.cap("victuals_market", ctx) == 7
    assert r.cap("victuals_market", {**ctx, "initializing": True}) == 2


def test_sanitized_setup_preserves_foreign_building_owner(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.start_simulation import (
        write_vanilla,
    )

    doc = parse_text(
        "locations = { port = { rank = town town_setup = old } } building_manager = { trade_office = { location = port tag = HSA level = 3 } }"
    )
    (tmp_path / "main_menu/setup/start").mkdir(parents=True)
    write_vanilla(
        doc,
        {"port": Counter({"trade_office": 2, "temple": 1})},
        {"port": "DAN"},
        tmp_path,
    )
    output = (tmp_path / "main_menu/setup/start/07_cities_and_buildings.txt").read_text(
        encoding="utf-8-sig"
    )
    assert "tag = HSA" in output and "town_setup" not in output
    assert (
        setup_counts(tmp_path / "main_menu/setup/start/07_cities_and_buildings.txt")[
            "port"
        ]["trade_office"]
        == 2
    )


def budget_simulation():
    """A surplus donor, a needy town, and an isolated needy province."""
    from collections import defaultdict
    from types import SimpleNamespace

    from prosper_or_perish_constructor.worldbuilder.start_food_model_v2 import FoodModelConfig
    from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation

    sim = Simulation.__new__(Simulation)
    sim.rules = rules()
    sim.rules.subsistence = 1.5
    for key in ("victuals_market", "victuals_market_import"):
        sim.rules.buildings[key] = block("town = yes max_levels = 10")
    sim.start = sp.StartConfig(processors={}, food_target_ratio=1.1)
    sim.cfg = SimpleNamespace(raw={})
    # food capacity 20 per 1,000 pops: every pool's store can reach the export band
    sim.food_model = FoodModelConfig(capacity={"per_development": 0.0, "per_population_k": 20.0, "per_location": 0.0, "rank": {}})
    sim.pops = {
        "donor": [sp.Pop("peasants", 300, "a", "r"), sp.Pop("nobles", 0.01, "a", "r")],
        "town": [sp.Pop("clergy", 30, "a", "r"), sp.Pop("nobles", 0.01, "a", "r")],
        "isolated": [sp.Pop("clergy", 30, "a", "r"), sp.Pop("nobles", 0.01, "a", "r")],
    }
    sim.owners = {t: "AAA" for t in sim.pops}
    sim.locations = {t: {"region": "test"} for t in sim.pops}
    sim.groups = {("AAA", t): [t] for t in sim.pops}
    sim.catchments = {
        g: ("isolated" if g[1] == "isolated" else "shared") for g in sim.groups
    }
    sim.attrs = {}
    sim.food = {"peasants": 0.5, "clergy": 2, "nobles": 2, "laborers": 1}
    sim.counts = defaultdict(Counter)
    sim.raw = {}
    sim.conversions = []
    sim.placements = []
    sim.rejections = Counter()
    sim.trimmed = []
    sim.audit = []
    sim.numbers = {
        "victuals_market": {
            "employment_size": 0.001,
            "pop_type": "nobles",
            "local_monthly_food": -60,
        },
        "victuals_market_import": {
            "employment_size": 0.001,
            "pop_type": "nobles",
            "local_monthly_food": 60,
        },
        "cookery": {
            "employment_size": 1,
            "pop_type": "laborers",
            "local_monthly_food": 0,
        },
    }
    sim.base = {
        t: {
            "location_rank": "town",
            "population": sum(p.size_k for p in pops),
            "modifiers": {"local_population_capacity": 1000},
        }
        for t, pops in sim.pops.items()
    }
    sim.workers()
    return sim


def test_trade_conserves_food_and_keeps_donor_reserve_and_catchment_boundary():
    sim = budget_simulation()
    before = sim.budgets()
    sim.place()
    after = sim.budgets()
    # the town needs 60 x 1.1 = 66 food: two import levels of 60, whose 3 victuals (its gap / 20 food per victual) the
    # donor's exports must supply x 1.1 -> two export levels; the isolated province's market has no victuals
    assert sim.counts["donor"]["victuals_market"] == 2
    assert sim.counts["town"]["victuals_market_import"] == 2
    assert sim.counts["isolated"]["victuals_market_import"] == 0
    assert abs(sum(r["supply"] for r in before.values()) - sum(r["supply"] for r in after.values())) < 1e-9
    assert after[("AAA", "donor")]["coverage"] >= 1.1
    assert after[("AAA", "town")]["shortfall"] == 0 < before[("AAA", "town")]["shortfall"]
    assert sim.verify() == 2


def test_staffed_production_subtracts_lost_subsistence():
    sim = budget_simulation()
    sim.numbers["farm"] = {
        "employment_size": 1,
        "pop_type": "peasants",
        "local_monthly_food": 1.5,
    }
    before = sim.budgets()[("AAA", "donor")]["supply"]
    sim.staffed["donor"]["farm"] = 5
    assert sim.budgets()[("AAA", "donor")]["supply"] == before


def test_clamp_removes_levels_when_live_cap_falls():
    sim = budget_simulation()
    sim.counts["donor"]["victuals_market"] = 15
    sim.clamp()
    assert sim.counts["donor"]["victuals_market"] == 10
    assert sim.trimmed == [
        {"location": "donor", "building": "victuals_market", "before": 15, "after": 10}
    ]


def test_additional_setup_preserves_nonbuilding_sections_and_foreign_owners(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.start_simulation import write_setup

    doc = parse_text(
        "religion_manager = { catholic = { value = 7 } } building_manager = { seat = { location = x tag = PAP level = 2 } }"
    )
    path = tmp_path / "religion.txt"
    write_setup(doc, {"x": Counter({"seat": 1})}, {"x": "FRA"}, path)
    output = parse_text(path.read_text(encoding="utf-8-sig"))
    from eu5gameparser.clausewitz.serializer import render_value

    assert render_value(output.values("religion_manager")[0]) == render_value(
        doc.values("religion_manager")[0]
    )
    assert "tag = PAP" in path.read_text()
    assert setup_counts(path)["x"]["seat"] == 1


def test_every_city_gets_import_infrastructure_even_without_workers_or_exports():
    sim = budget_simulation()
    sim.base["town"]["location_rank"] = "city"
    sim.base["isolated"]["location_rank"] = "megalopolis"
    sim.rules.buildings["victuals_market_import"] = block(
        "city = yes megalopolis = yes max_levels = 10"
    )
    sim.pools["isolated"].existing["nobles"] = 0
    before = sim.budgets()
    sim.ensure_city_imports({})
    assert sim.counts["town"]["victuals_market_import"] == 1
    assert sim.counts["isolated"]["victuals_market_import"] == 1
    assert sim.counts["donor"]["victuals_market_import"] == 0
    assert sim.budgets() == before
    assert sim.city_import_minimum["added"] == 2
    sim.ensure_city_imports({})
    assert sim.city_import_minimum["added"] == 0
    assert sim.verify() == 2


def test_budget_counts_province_food_of_staffed_levels_unscaled():
    sim = budget_simulation()
    sim.numbers["farm"] = {"employment_size": 1, "pop_type": "peasants", "local_monthly_food": 1.5}
    sim.province_food = {"farm": 0.96}
    before = sim.budgets()[("AAA", "donor")]["supply"]
    sim.staffed["donor"]["farm"] = 5
    assert abs(sim.budgets()[("AAA", "donor")]["supply"] - (before + 5 * 0.96)) < 1e-9


def crop_simulation():
    """budget_simulation plus two rural crop locations with a fake crop plan (weights and availability)."""
    from prosper_or_perish_constructor.worldbuilder import crop_allocation as ca

    sim = budget_simulation()
    farm = "rural_settlement = yes max_levels = 10"
    for key in ("wheat_farm", "rice_farm", "cattle_farm", "maize_farm", "potato_farm"):
        sim.rules.buildings[key] = block(farm)
    sim.rules.buildings["millet_farm"] = block("rural_settlement = yes max_levels = 1")          # refuses its second level
    sim.rules.buildings["legume_farm"] = block("rural_settlement = yes max_levels = legume_cap")
    sim.rules.values["legume_cap"] = block("value = 10 if = { limit = { location_tag = farm_b } value = 2 }")
    sim.rules.buildings["olive_farm"] = block(farm + " location_potential = { climate = mediterranean }")
    for key in sim.rules.buildings:
        if key.endswith("_farm"):
            sim.numbers[key] = {"employment_size": 1, "pop_type": "peasants", "local_monthly_food": 1.5}
    for tag, rgo in (("farm_a", "wheat"), ("farm_b", "rice")):
        sim.pops[tag] = [sp.Pop("peasants", 20, "a", "r")]
        sim.owners[tag] = "AAA"
        sim.locations[tag] = {"region": "test", "raw_material": rgo, "vegetation": "farmland"}
        sim.groups[("AAA", tag)] = [tag]
        sim.catchments[("AAA", tag)] = "farms"
        sim.base[tag] = {
            "location_tag": tag,
            "location_rank": "rural_settlement",
            "climate": "oceanic",
            "population": 20,
            "modifiers": {"local_population_capacity": 1000},
        }
    sim.crop_cfg = ca.CropConfig()
    zero = {g: 0.0 for g in sim.crop_cfg.goods}
    sim.crop_weights = {
        # wheat is the RGO (+0.5); olives are heavier but fail their location potential; legumes fall under the floor
        "farm_a": {**zero, "wheat": 1.0, "millet": 1.2, "legumes": 0.5, "olives": 3.0, "livestock": 0.2},
        # rice is the RGO but not native here (unavailable): no bonus, no levels
        "farm_b": {**zero, "wheat": 1.0, "millet": 0.5, "legumes": 1.1, "rice": 3.0, "livestock": 0.1},
    }
    ungated = frozenset({"wheat", "millet", "legumes", "livestock"})
    sim.crop_available = {"farm_a": ungated | {"olives"}, "farm_b": ungated}
    sim.crop_plan = {}
    sim.workers()
    return sim


def test_place_spreads_farm_levels_over_crop_farms_and_gives_refused_levels_to_the_rgo_crop():
    sim = crop_simulation()
    sim.place()
    a, b = sim.counts["farm_a"], sim.counts["farm_b"]
    # farm_a plan: livestock round(0.2 x 6) = 1, wheat (RGO) 3, millet 2; millet stops at its cap of 1 and the
    # refused level goes to the RGO crop's farm
    assert sim.crop_plan["farm_a"] == {"wheat_farm": 3, "millet_farm": 2, "cattle_farm": 1}
    assert (a["wheat_farm"], a["millet_farm"], a["cattle_farm"], a["olive_farm"], a["legume_farm"]) == (4, 1, 1, 0, 0)
    # farm_b plan: legumes 3, wheat 2, livestock 1; legumes stop at 2 there and, the RGO (rice) being unavailable,
    # the refused level goes to the heaviest other candidate that has room (wheat)
    assert sim.crop_plan["farm_b"] == {"legume_farm": 3, "wheat_farm": 2, "cattle_farm": 1}
    assert (b["legume_farm"], b["wheat_farm"], b["cattle_farm"], b["rice_farm"]) == (2, 3, 1, 0)
    for tag in ("farm_a", "farm_b"):
        crop_levels = sum(sim.counts[tag][k] for k in sim.crop_cfg.buildings.values())
        assert crop_levels == sim.start.max_farm_levels_per_location == sum(sim.crop_placed[tag].values())
    assert sim.rejections["millet_farm: cap or gate"] == 1 and sim.rejections["legume_farm: cap or gate"] == 1


def test_crop_placement_stops_when_no_peasants_are_left():
    sim = crop_simulation()
    sim.pops["farm_a"] = [sp.Pop("peasants", 5, "a", "r")]     # 5k x 0.6 work share = 3 staffed levels
    sim.workers()
    sim.place()
    a = sim.counts["farm_a"]
    assert sum(a[k] for k in sim.crop_cfg.buildings.values()) == 3
    # wheat takes its 3 planned levels, millet finds no worker and placing stops (no leftover attempts)
    assert a["wheat_farm"] == 3 and sim.rejections["millet_farm: workers"] == 1
    assert sim.rejections["cattle_farm: workers"] == 0


def test_cattle_takes_at_most_one_fallback_level_and_the_rest_is_not_placed():
    sim = crop_simulation()
    sim.rules.buildings["wheat_farm"] = block("rural_settlement = yes max_levels = wheat_cap")
    sim.rules.values["wheat_cap"] = block("value = 10 if = { limit = { location_tag = farm_a } value = 1 }")
    sim.rules.values["legume_cap"] = block(
        "value = 10 if = { limit = { location_tag = farm_b } value = 2 } else_if = { limit = { location_tag = farm_a } value = 0 }"
    )
    sim.place()
    a = sim.counts["farm_a"]
    # plan wheat 3, millet 2, cattle 1: wheat and millet stop at 1, no other crop has room, cattle gets its planned
    # level plus one fallback level and the last 2 levels are not placed
    assert sim.crop_plan["farm_a"] == {"wheat_farm": 3, "millet_farm": 2, "cattle_farm": 1}
    assert (a["wheat_farm"], a["millet_farm"], a["cattle_farm"], a["legume_farm"]) == (1, 1, 2, 0)
    assert sim.rejections["crop farms: no room"] == 2


# ------------------------------------------------------------------ placement v2 (start_simulation.place_food_chain)
def v2_simulation():
    """One market: a two-location deficit province (a town and a village), a surplus province and a producer of
    victuals (a brewery counted as a configured victuals producer)."""
    sim = budget_simulation()
    sim.pops = {
        "burgh": [sp.Pop("clergy", 40, "a", "r"), sp.Pop("nobles", 0.05, "a", "r")],
        "hamlet": [sp.Pop("peasants", 2, "a", "r"), sp.Pop("nobles", 0.01, "a", "r")],
        "farms": [sp.Pop("peasants", 300, "a", "r"), sp.Pop("nobles", 0.05, "a", "r")],
        "brewery": [sp.Pop("peasants", 1, "a", "r")],
    }
    sim.owners = {t: "AAA" for t in sim.pops}
    sim.locations = {t: {"region": "test"} for t in sim.pops}
    sim.groups = {("AAA", "deficit"): ["burgh", "hamlet"], ("AAA", "surplus"): ["farms"], ("AAA", "brew"): ["brewery"]}
    sim.catchments = {g: "market" for g in sim.groups}
    sim.base = {
        t: {"location_tag": t, "location_rank": "town" if t == "burgh" else "rural_settlement",
            "population": sum(p.size_k for p in pops), "modifiers": {"local_population_capacity": 1000}}
        for t, pops in sim.pops.items()
    }
    for key in ("victuals_market", "victuals_market_import"):
        sim.rules.buildings[key] = block("town = yes rural_settlement = yes max_levels = 10")
    sim.numbers["brewery"] = {"employment_size": 0, "pop_type": "peasants", "local_monthly_food": 0}
    sim.counts["brewery"]["brewery"] = 1
    return sim


def test_deficit_pool_gets_victualler_levels_sized_to_its_need_at_the_province_capital():
    sim = v2_simulation()
    sim.start = sp.StartConfig(processors={}, food_target_ratio=1.1,
                               victuals={"producers": {"brewery": 100.0}, "consumers": {}, "pop_demand_scale": 0.0})
    sim.workers()
    need = sim.budgets()[("AAA", "deficit")]
    assert need["cookery_levels"] == 0 and need["subsistence"] > 0
    sim.place()
    wanted = -(-(need["demand"] * 1.1 - need["supply"]) // 60)          # ceil(need / 60 food per level)
    assert sim.counts["burgh"]["victuals_market_import"] == wanted       # the town is the province capital
    assert sim.counts["hamlet"]["victuals_market_import"] == 0
    assert sim.budgets()[("AAA", "deficit")]["coverage"] >= 1.1
    assert sim.counts["farms"]["victuals_market"] == 0                  # the brewery covers the victuals: no export


def test_market_short_of_victuals_gets_exports_in_its_surplus_pool_and_stays_balanced():
    sim = v2_simulation()
    sim.start = sp.StartConfig(processors={}, food_target_ratio=1.1,
                               victuals={"producers": {"brewery": 1.0}, "consumers": {}, "pop_demand_scale": 0.0})
    sim.workers()
    sim.place()
    assert sim.counts["farms"]["victuals_market"] >= 1
    assert sim.counts["burgh"]["victuals_market_import"] >= 1
    report = sim.victuals["market"]
    assert report["placed_export_levels"] == sim.counts["farms"]["victuals_market"]
    assert report["covered"] >= sim.food_model.victuals_target - 1e-9       # per-market victuals balance
    # food is conserved: the exports' food is what the imports move, and both sides keep their reserve
    b = sim.budgets()
    assert b[("AAA", "surplus")]["coverage"] >= 1.1 and b[("AAA", "deficit")]["coverage"] > 1.0


def test_no_province_gets_both_an_import_and_an_export():
    sim = v2_simulation()
    # the surplus province already has an import market (a vanilla setup row): it must not export as well
    sim.counts["farms"]["victuals_market_import"] = 1
    sim.start = sp.StartConfig(processors={}, food_target_ratio=1.1,
                               victuals={"producers": {"brewery": 1.0}, "consumers": {}, "pop_demand_scale": 0.0})
    sim.workers()
    sim.place()
    for tags in sim.groups.values():
        exports = sum(sim.counts[t]["victuals_market"] for t in tags)
        imports = sum(sim.counts[t]["victuals_market_import"] for t in tags)
        assert not (exports and imports)
    assert sim.counts["farms"]["victuals_market"] == 0


def test_market_that_cannot_supply_imports_places_serve_cookeries_instead():
    sim = v2_simulation()
    sim.pops["hamlet"] = [sp.Pop("peasants", 20, "a", "r"), sp.Pop("laborers", 6, "a", "r"), sp.Pop("nobles", 0.01, "a", "r")]
    sim.pops["burgh"] = [sp.Pop("clergy", 40, "a", "r")]   # no noble: the capital cannot staff a Victualler
    sim.base["hamlet"]["population"] = 26.01
    sim.rules.buildings["cookery"] = block("rural_settlement = yes town = yes max_levels = 10")
    sim.numbers["cookery"] = {"employment_size": 1, "pop_type": "laborers", "local_monthly_food": 0}
    sim.province_food = {"cookery": 27.57}
    sim.rgo_k = {"hamlet": 10.0}
    sim.locations["hamlet"] = {"region": "test", "raw_material": "wheat"}
    sim.__dict__["_serve_inputs"] = (frozenset({"wheat"}), 2.0)
    sim.start = sp.StartConfig(processors={}, food_target_ratio=1.1, max_cookery_levels_per_location=6,
                               victuals={"producers": {}, "consumers": {}, "pop_demand_scale": 0.0})
    sim.workers()
    sim.place()
    assert sim.counts["hamlet"]["cookery"] > 0
    assert sim.victuals["market"]["serve_cookery_levels"] + sim.victuals["market"]["fallback_cookery_levels"] == sim.counts["hamlet"]["cookery"]


def test_construction_materials_fill_markets_without_supply():
    from types import SimpleNamespace

    sim = v2_simulation()
    sim.rules.buildings["mason"] = block("rural_settlement = yes town = yes max_levels = 5")
    sim.numbers["mason"] = {"employment_size": 1, "pop_type": "peasants", "local_monthly_food": 0}
    sim.locations["farms"] = {"region": "test", "raw_material": "stone"}
    sim.cfg = SimpleNamespace(raw={"start": {"construction_materials": {"margin": 2.0, "goods": {
        "masonry": {"producers": {"mason": 0.5}, "place": ["mason"], "inputs": ["stone"], "construction_per_million_pops": 1000.0,
                    "per_victualler": 0.1, "max_levels_per_location": 5},
        "tools": {"producers": {"tools_guild": 0.2}, "place": ["tools_guild"], "inputs": ["iron"], "construction_per_million_pops": 1.0},
    }}}})
    sim.workers()
    sim.victuals = {}
    sim.place_construction_materials()
    masonry = sim.construction["masonry"]
    # 2 x 1,000 per million pops x 0.343 M pops = 686 masonry wanted; 5 levels per location, 4 locations cap it
    assert masonry["zero_before"] == 1 and masonry["levels_added"]["mason"] == sum(sim.counts[t]["mason"] for t in sim.pops)
    assert masonry["supply_after"] == 0.5 * masonry["levels_added"]["mason"] > 0
    assert sim.construction["tools"]["no_inputs"] == 1 and sim.construction["tools"]["levels_added"] == {}
