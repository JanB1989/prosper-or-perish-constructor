"""Start-food validator (worldbuilder/food_sim.py) on a three-pool fake."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder import food_sim as fs

ROOT = Path(__file__).resolve().parents[1]


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
    assert fs.overpopulation(back[0], 1.0) == 0.25 * 10.0 * 0.5


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
    # what-if knobs of the pre-2026-09-26 design: tribesmen feeding the province and their share-weighted growth
    fed = fs.simulate([tribal_pool(tribesmen_food=-1.0)], fs.SimRules(harvest=False, months=48, tribal_growth=0.006))[0]
    assert fed["months_starving"] == 0 and fed["tribesmen_lost_k"] == 0.0 and fed["tribesmen_end_k"] > 90.0
    assert fed["end_months"] is None                   # net negative consumption: no storage signal


def test_tribesmen_births_need_free_land_and_storage_needs_positive_consumption():
    rules = fs.SimRules(harvest=False, months=24, tribal_growth=0.006)   # a positive location growth to be born from
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


def test_default_rules_are_the_mods_store_lever():
    """The defaults are the mod's values (constructor.toml, the Tavern and Grange blueprints, province_starving)."""
    project, default = asdict(fs.SimRules.from_project(ROOT)), asdict(fs.SimRules())
    assert project == pytest.approx(default)
    assert fs.SimRules.from_project(ROOT, {"months": 12}).months == 12
    assert fs.SimRules.from_project(ROOT / "nowhere") == fs.SimRules()      # no project: the defaults


def test_tavern_fills_a_low_store_and_the_grange_packs_a_full_one():
    rules = fs.SimRules()
    # Province Food is worth more below 12 stored months and less above; the lever stops at 24 months
    assert rules.food_modifier(0) == 1.75 and rules.food_modifier(12) == 1.0 and rules.food_modifier(24) == 0.25
    assert rules.food_modifier(40) == rules.food_modifier(24)
    assert rules.food_modifier(0, starving=True) == 2.75                # starving people pay more
    # the Tavern pays at a low store only, the Grange at a full one only, never both at the same store
    assert rules.tavern_profit(3, False) > 0 > rules.tavern_profit(12, False)
    # 2026-10-03: only a really full store, and only from about the default victuals price up (never below 2.86)
    assert rules.yard_profit(24, False) < 0
    base = fs.SimRules(victuals_price=3.0)
    assert base.yard_profit(24, False) > 0 > base.yard_profit(12, False)
    assert fs.SimRules(victuals_price=3.5).yard_profit(16, False) > 0
    for months in range(25):
        assert not (rules.tavern_profit(months, False) > 0 and rules.yard_profit(months, False) > 0), months
    # a staffed Tavern takes the Grange's Surplus Sales away, and a starving province packs no victuals
    assert rules.yard_profit(24, False, staffed_taverns=1.0) < 0
    assert rules.yard_profit(0, True) == -rules.yard_fixed
    assert rules.harbor_yard_profit(False) > 0 > rules.harbor_yard_profit(True)
    # a starving province still buys victuals at a price that stops the Tavern at a merely empty store
    dear = fs.SimRules(victuals_price=5.0)
    assert dear.tavern_profit(0, True) > 0 > dear.tavern_profit(0, False)


def test_cookshops_serve_up_to_their_break_even_store():
    """A pool that only its Cookshops can feed: they serve while the store is low and stop above ~11 months."""
    rules = fs.SimRules(harvest=False, months=120)
    pool = fs.Pool(owner="A", province="cooks", catchment="m", pop0=100.0, tribesmen=0.0, demand0=100.0, workers0=90.0,
                   jobs0=0.0, yield_=80 / 90, flat_food=0.0, provision_food=0.0, serve_food=60.0, cookshop_levels=2.0,
                   taverns=0.0, yards=0.0, capacity=4000.0, start_food=600.0, victuals_demand=0.0, peasant_share=0.8)
    row = fs.simulate([pool], rules)[0]
    assert 9.0 < row["end_months"] < 13.0 and not row["pinned"] and row["months_starving"] == 0
    assert 0.0 < row["cookshop_staffed_end"] < 1.0
    # with costlier staples they stop earlier and the store rests lower
    dear = fs.simulate([pool], fs.SimRules(harvest=False, months=120, cookshop_cost=1.3))[0]
    assert dear["end_months"] < row["end_months"] - 2


def _unowned_tribe(capacity_k):
    """10k tribesmen on unowned land (feeding themselves), no settled pops."""
    return fs.Pool(owner=fs.UNOWNED, province="steppe", catchment=fs.UNOWNED, pop0=10.0, tribesmen=10.0, demand0=0.0,
                   workers0=0.0, jobs0=0.0, yield_=1.5, flat_food=0.0, provision_food=0.0, serve_food=0.0,
                   cookshop_levels=0.0, taverns=0.0, yards=0.0, capacity=500.0, start_food=50.0, victuals_demand=0.0,
                   tribesmen_food=-1.0, pop_capacity=capacity_k)


def test_tribal_land_follows_the_location_law_and_unowned_land_stays_put():
    from dataclasses import replace

    rules = fs.SimRules(harvest=False, months=120)
    heartland = replace(_unowned_tribe(1000.0), owner="A", tribesmen_food=0.0)   # owned, only tribesmen, who eat nothing
    row = fs.simulate([heartland], rules)[0]
    yearly = (row["tribesmen_end_k"] / 10.0) ** (1 / 10) - 1
    assert row["tribesmen_born_k"] == 0.0 and abs(yearly - rules.growth_base) < 0.0002   # no store signal: the gate only
    unowned = fs.simulate([replace(_unowned_tribe(1000.0), tribesmen_food=0.0)], rules)[0]
    assert abs(unowned["tribesmen_end_k"] - 10.0) < 1e-6                    # no gate, no offset, no births


def test_winter_levels_match_the_mod_climates():
    import re
    from pathlib import Path

    mod = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    found = {}
    for f in (mod / "in_game/common/climates").glob("*.txt"):
        name = None
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"^(?:\w+:)?([a-z_0-9]+)\s*=\s*\{", line)
            if m:
                name = m.group(1).removeprefix("ha1300_climate_")
            m = re.match(r"^\s*winter\s*=\s*(none|mild|normal|severe)", line)
            if m and name:
                found[name] = m.group(1)
    assert found and all(fs.CLIMATE_WINTER.get(k) == v for k, v in found.items()), found
    text = (mod / "in_game/common/static_modifiers/pp_population_growth_and_food_adjustments.txt").read_text(encoding="utf-8-sig")
    for level, share in fs.WINTER_CONSUMPTION.items():
        if share:
            block = text.split(f"TRY_INJECT:winter_{level}")[1].split("TRY_INJECT:")[0]
            assert f"local_peasants_food_consumption = {share:g}" in block
    assert fs.winter_consumption("subpolar") == 0.375 and fs.winter_consumption(None) == 0.0


def test_regional_harvests_follow_the_mod_tables():
    import random
    from pathlib import Path

    mod = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    text = (mod / "in_game/common/static_modifiers/pp_variable_harvest_modifiers.txt").read_text(encoding="utf-8-sig")
    for severity, value in fs.HARVEST_SEVERITY.items():
        if value:
            block = text.split(f"pp_harvest_western_europe_{severity} = {{")[1].split("\n}")[0]
            assert f"local_peasants_food_consumption = {value:.2f}" in block
    cfg = fs.load_harvest_config()
    assert cfg and set(cfg["profiles"]) >= {p for route in fs.HARVEST_ROUTES.values() for p in route.values()}
    rolled = fs.roll_regional_harvests(random.Random(3), cfg, {"europe": ["a", "b"], "asia": ["c"]}, {})
    assert set(rolled) == {"a", "b", "c"} and all(v in fs.HARVEST_SEVERITY for v in rolled.values())


def test_prosperity_raises_consumption_toward_its_fitted_equilibrium():
    rules = fs.SimRules(harvest=False, months=12 * 80, consumption_drift=0.0)
    # food far above need (the pool doubles and more in 80 years), so the store stays at its cap
    p = tribal_pool(tribesmen=0.0, pop0=10.0, demand0=10.0, yield_=0.0, flat_food=60.0, capacity=5000.0, start_food=5000.0)
    row = fs.simulate([p], rules)[0]
    # a store at the cap: P -> 0.0181 x years / 0.0747 (two years: ~0.49), so consumption +~24 %
    assert 0.45 < row["prosperity_end"] < 0.5


def test_tribal_values_match_the_mod():
    from pathlib import Path

    from prosper_or_perish_constructor.worldbuilder.start_food_model_v2 import FoodModelConfig

    mod = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    text = (mod / "in_game/common/pop_types/pp_pop_adjustments.txt").read_text(encoding="utf-8-sig")
    block = text.split("TRY_INJECT:tribesmen")[1]
    assert "pop_food_consumption = 0\n" in block and "local_population_growth" not in block
    assert f"local_monthly_food = {fs.SimRules().tribal_flat_food:g}" in block
    assert FoodModelConfig().tribal_share_food == fs.SimRules().tribal_flat_food and fs.SimRules().tribal_growth == 0.0


def test_tribesmen_grow_at_most_about_015_percent_a_year_and_not_at_all_on_unowned_land():
    from dataclasses import replace

    rules = fs.SimRules(harvest=False, months=120, tribal_growth=0.006)   # the land-birth mechanism under the old offset
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


def test_unowned_land_has_no_rank_gate_store_or_starving():
    from dataclasses import replace

    rules = fs.SimRules(harvest=False, months=120)
    mixed = replace(_unowned_tribe(1000.0), pop0=20.0, demand0=50.0)          # 10k settled among 10k tribesmen, no food
    row = fs.simulate([mixed], rules)[0]
    assert row["months_starving"] == 0 and row["tribesmen_lost_k"] == 0.0
    settled_rate = ((row["pop_end_k"] - row["tribesmen_end_k"]) / 10.0) ** (1 / 10) - 1
    assert abs(settled_rate - rules.tribal_growth * 0.5) < 0.0002           # only the tribal share's growth, no gate
    bare = fs.simulate([mixed], replace(rules, tribal_growth=0.0))[0]
    assert abs(bare["pop_end_k"] - 20.0) < 1e-6                             # nothing moves without the offset


def test_free_land_cuts_peasant_food_by_the_engine_scales():
    p = tribal_pool(tribesmen=0.0, pop0=10.0, demand0=10.0, overpop=[(10.0, 0.2, 50.0), (5.0, 0.05, 100.0)])
    rules = fs.SimRules()
    cons, forage = fs.free_land(p, 1.0, rules)
    # 10k peasants at 20 % of capacity: available land, -0.32 x 0.8; 5k at 5 % of 100k (pop 5k < 10k): abundant, -0.5 x 0.95
    assert abs(cons - (10.0 * -0.32 * 0.8 + 5.0 * -0.5 * 0.95)) < 1e-9 and abs(forage - 0.95) < 1e-9
    cons5, forage5 = fs.free_land(p, 5.0, rules)                    # 5x the people: the first location is full,
    assert abs(cons5 - 25.0 * -0.32 * 0.75) < 1e-9 and forage5 == 0.0  # the second at 25 % (25k): available, x 0.75
    assert fs.free_land(replace_overpop(p, [(10.0, 0.2)]), 1.0, rules) == (0.0, 0.0)             # no capacity known: no effect


def replace_overpop(p, rows):
    from dataclasses import replace

    return replace(p, overpop=rows)


def test_free_land_values_match_the_mod():
    from pathlib import Path

    mod = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    text = (mod / "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt").read_text(encoding="utf-8-sig")
    abundant = text.split("TRY_REPLACE:abundant_free_land")[1].split("TRY_REPLACE:")[0]
    available = text.split("TRY_REPLACE:available_free_land")[1].split("TRY_REPLACE:")[0]
    rules = fs.SimRules()
    assert f"local_peasants_food_consumption = {rules.abundant_peasant_food}" in abundant
    assert f"local_peasants_food_consumption = {rules.available_peasant_food}" in available
    assert f"local_monthly_food = {rules.abundant_food:g}" in abundant


def test_overpopulation_value_matches_the_mod():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    mod = root / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    text = (mod / "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt").read_text(encoding="utf-8-sig")
    over = text.split("TRY_REPLACE:overpopulation = {")[1].split("\n}")[0]
    cfg = tomllib.loads((root / "constructor.toml").read_text(encoding="utf-8"))
    value = cfg["worldbuilder"]["start"]["food_model"]["overpopulation_consumption"]
    assert f"\tlocal_peasants_food_consumption = {value:g}\n" in over
    assert fs.Pool.__dataclass_fields__["overpop_consumption"].default == value


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
