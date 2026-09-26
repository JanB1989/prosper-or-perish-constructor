"""Start-food validator (worldbuilder/food_sim.py) on a three-pool fake."""

from __future__ import annotations

from prosper_or_perish_constructor.worldbuilder import food_sim as fs


def pools():
    common = dict(catchment="m", tribesmen=0.0, flat_food=0.0, provision_food=0.0, serve_food=0.0, cookshop_levels=0.0,
                  taverns=0.0, yards=0.0, victuals_demand=0.0, peasant_share=0.8)
    return [
        # 100k pops eating 100 while their 90k jobless make 0.6 x 100: starves and collapses
        fs.Pool(owner="A", province="short", pop0=100.0, demand0=100.0, workers0=90.0, jobs0=0.0, yield_=60 / 90,
                capacity=1000.0, start_food=100.0, **common),
        # fed exactly: stays level
        fs.Pool(owner="A", province="fed", pop0=100.0, demand0=100.0, workers0=90.0, jobs0=0.0, yield_=100 / 90,
                capacity=2400.0, start_food=400.0, **common),
        # large surplus and a 24-month store: pinned at the cap, grows slowly
        fs.Pool(owner="B", province="rich", pop0=50.0, demand0=50.0, workers0=50.0, jobs0=0.0, yield_=2.0,
                capacity=1200.0, start_food=60.0, **common),
    ]


def test_validator_reports_collapse_pinning_and_world_change(tmp_path):
    rules = fs.SimRules(harvest=False)
    rows = fs.simulate(pools(), rules)
    by = {r["province"]: r for r in rows}
    assert by["short"]["collapsing"] and by["short"]["months_starving"] > 48
    assert not by["fed"]["collapsing"] and abs(by["fed"]["change"]) < 0.25
    assert by["rich"]["pinned"] and by["rich"]["change"] > 0
    summary = fs.summarize(rows, rules)
    assert summary["pools"] == 3 and summary["collapsing_food_pools"] == 1 and summary["pinned_pools"] >= 1
    start = sum(p.pop0 for p in pools())
    assert abs(summary["world_pop_change"] - (sum(r["pop_end_k"] for r in rows) / start - 1)) < 1e-3


def test_tavern_rescues_the_short_pool_when_the_market_has_victuals(tmp_path):
    rules = fs.SimRules(harvest=False, starving_growth=-0.04)
    ps = pools()
    ps[0].taverns = 1.0
    ps[2].victuals_other_supply = 10.0
    rows = {r["province"]: r for r in fs.simulate(ps, rules)}
    assert not rows["short"]["collapsing"] and rows["short"]["tavern_food"] > 0
    ps[2].victuals_other_supply = 0.0                           # no victuals in the market: the import cannot help
    rows = {r["province"]: r for r in fs.simulate(ps, rules)}
    assert rows["short"]["collapsing"] and rows["short"]["tavern_food"] == 0


def test_inputs_round_trip_and_run_file(tmp_path):
    folder = tmp_path / fs.OUTPUT_RELATIVE_PATH
    ps = pools()
    ps[0].overpop = [(10.0, 1.5), (5.0, 0.5)]
    fs.write_inputs(folder / "input.csv", ps)
    back = fs.read_inputs(folder / "input.csv")
    assert back[0].overpop == [(10.0, 1.5), (5.0, 0.5)] and back[1].province == "fed" and back[2].yield_ == 2.0
    summary = fs.run_file(tmp_path, {"harvest": False}, months=24)
    assert summary["months"] == 24 and (folder / "pools.csv").is_file() and (folder / "summary.json").is_file()
    assert fs.overpopulation(back[0], 1.0) == 0.5 * 10.0 * 0.5


def tribal_pool(**kw):
    """90k tribesmen around 10k settled pops who eat 30 a month and farm nothing."""
    args = dict(owner="T", province="steppe", catchment="m", pop0=100.0, tribesmen=90.0, demand0=30.0, workers0=0.0,
                jobs0=0.0, yield_=0.0, flat_food=0.0, provision_food=0.0, serve_food=0.0, cookshop_levels=0.0,
                taverns=0.0, yards=0.0, capacity=600.0, start_food=30.0, victuals_demand=0.0, peasant_share=0.0,
                pop_capacity=1000.0)
    args.update(kw)
    return fs.Pool(**args)


def test_starvation_hits_tribesmen_unless_they_feed_the_province():
    rules = fs.SimRules(harvest=False, months=48)
    hungry = fs.simulate([tribal_pool()], rules)[0]
    assert hungry["months_starving"] > 40 and hungry["tribesmen_end_k"] < 90.0 and hungry["tribesmen_born_k"] == 0.0
    fed = fs.simulate([tribal_pool(tribesmen_food=-1.0)], rules)[0]
    assert fed["months_starving"] == 0 and fed["tribesmen_lost_k"] == 0.0 and fed["tribesmen_end_k"] > 90.0
    assert fed["end_months"] is None                   # net negative consumption: no storage signal


def test_tribesmen_births_need_free_land_and_storage_needs_positive_consumption():
    rules = fs.SimRules(harvest=False, months=24)
    full = fs.simulate([tribal_pool(tribesmen_food=-1.0, pop_capacity=100.0 * rules.tribal_land_slope)], rules)[0]
    empty = fs.simulate([tribal_pool(tribesmen_food=-1.0)], rules)[0]
    assert full["tribesmen_born_k"] == 0.0 and empty["tribesmen_born_k"] > 0.0
    assert full["pop_end_k"] - full["tribesmen_end_k"] > 10.0     # the settled pops still get the tribal growth share
    assert fs.stored_months(100.0, 0.0) == 0.0 and fs.stored_months(100.0, -5.0) == 0.0 and fs.stored_months(120.0, 10.0) == 12.0


def test_the_tribe_can_feed_the_settled_share_up_to_all_of_it():
    p = tribal_pool(tribal_fed_share=0.9)
    rules = fs.SimRules(harvest=False, tribal_feeding=1.0)
    assert abs(fs.fed_share(p, 10.0, 90.0, 0.9, rules) - 0.9) < 1e-9
    assert fs.fed_share(p, 10.0, 90.0, 0.9, fs.SimRules()) == 0.0
    assert fs.fed_share(p, 0.0, 90.0, 0.5, fs.SimRules(tribal_feeding=2.0)) == 1.0


def test_tribal_share_can_cut_the_scarcity_premium():
    rules = fs.SimRules(tribal_tavern_premium=-16.0)
    assert rules.tavern_profit(0.0, False, 1.0, 1.0) < fs.SimRules().tavern_profit(0.0, False, 1.0, 1.0)
    assert rules.tavern_profit(0.0, True, 1.0, 0.6) > 0                 # a starving tribal province still imports
    assert fs.SimRules().tavern_profit(0.0, False, 1.0, 1.0) == fs.SimRules().tavern_profit(0.0, False, 1.0)


def _unowned_tribe(capacity_k):
    """10k tribesmen on unowned land (feeding themselves), no settled pops."""
    return fs.Pool(owner=fs.UNOWNED, province="steppe", catchment=fs.UNOWNED, pop0=10.0, tribesmen=10.0, demand0=0.0,
                   workers0=0.0, jobs0=0.0, yield_=1.5, flat_food=0.0, provision_food=0.0, serve_food=0.0,
                   cookshop_levels=0.0, taverns=0.0, yards=0.0, capacity=500.0, start_food=50.0, victuals_demand=0.0,
                   tribesmen_food=-1.0, pop_capacity=capacity_k)


def test_tribesmen_grow_at_most_about_015_percent_a_year_and_not_at_all_on_unowned_land():
    from dataclasses import replace

    rules = fs.SimRules(harvest=False, months=120)
    owned = replace(_unowned_tribe(1000.0), owner="A")
    empty = fs.simulate([owned], rules)[0]
    full = fs.simulate([replace(_unowned_tribe(10.0 * 0.75), owner="A")], rules)[0]   # free-land factor 1 - 0.75 pop/cap = 0
    yearly = (empty["tribesmen_end_k"] / 10.0) ** (1 / 10) - 1
    assert 0.0002 < yearly <= 0.0016                                  # ~0.15 %/yr at most, on empty owned land
    assert abs(full["tribesmen_end_k"] - 10.0) < 1e-6                  # no births at capacity
    unowned = fs.simulate([_unowned_tribe(1000.0)], rules)[0]
    assert abs(unowned["tribesmen_end_k"] - 10.0) < 1e-6               # no free-land modifier on unowned land: no births
    # the engine before 2026-09-26 (brake as a country modifier): unowned tribesmen grew ~1 %/yr
    old = fs.simulate([_unowned_tribe(1000.0)], fs.SimRules(harvest=False, months=120, unowned_brake=False, tribal_land_births=1.0,
                                                             growth_base=-0.0048, tribal_growth=0.012))[0]
    assert (old["tribesmen_end_k"] / 10.0) ** (1 / 10) - 1 > 0.01


def test_the_tribesmen_birth_brake_is_on_every_topography_not_a_rank_or_country():
    from pathlib import Path

    mod = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    ranks = (mod / "in_game/common/location_ranks/pp_location_rank_adjustments.txt").read_text(encoding="utf-8-sig")
    country = (mod / "in_game/common/auto_modifiers/pp_country_base_values.txt").read_text(encoding="utf-8-sig")
    land = (mod / "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt").read_text(encoding="utf-8-sig")
    topo = (mod / "in_game/common/topography/pp_wb_attribute_rows.txt").read_text(encoding="utf-8-sig")
    blocks = topo.count("TRY_INJECT:")
    assert blocks >= 20 and topo.count("local_tribesmen_pop_growth = -1.0") == blocks   # every topography, owned or not
    assert "local_tribesmen_pop_growth" not in ranks                     # unowned land gets no rank modifiers
    assert not any(l.strip().startswith("global_tribesmen_pop_growth") for l in country.splitlines())
    assert land.count("local_tribesmen_pop_growth = 0.75") == 2
