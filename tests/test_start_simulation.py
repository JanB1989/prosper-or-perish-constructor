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

    from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation

    sim = Simulation.__new__(Simulation)
    sim.rules = rules()
    sim.rules.subsistence = 1.5
    for key in ("victuals_market", "victuals_market_import"):
        sim.rules.buildings[key] = block("town = yes max_levels = 10")
    sim.start = sp.StartConfig(processors={}, food_target_ratio=1.1)
    sim.cfg = SimpleNamespace(raw={})
    sim.pops = {
        "donor": [sp.Pop("peasants", 100, "a", "r"), sp.Pop("nobles", 0.01, "a", "r")],
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
    assert sim.counts["donor"]["victuals_market"] == 1
    assert sim.counts["town"]["victuals_market_import"] == 1
    assert sim.counts["isolated"]["victuals_market_import"] == 0
    assert sum(r["supply"] for r in before.values()) == sum(
        r["supply"] for r in after.values()
    )
    assert after[("AAA", "donor")]["coverage"] >= 1.1
    assert after[("AAA", "town")]["shortfall"] < before[("AAA", "town")]["shortfall"]
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
