"""Market migration rules (worldbuilder/migration.py, docs/migration_rulebook.md) and the food_sim switch."""

from __future__ import annotations

import math

import pytest

from prosper_or_perish_constructor.worldbuilder import food_sim as fs
from prosper_or_perish_constructor.worldbuilder import migration as mig

POS = {"src": 0.0, "near": 50.0, "far": 600.0, "foreign": 100.0, "low": 20.0, "small": 10.0}


def dist(a, b):
    return abs(POS[a.key] - POS[b.key])


def place(key, attraction, owner="A", pops=None, caps=None, religion="cath", speed=0.0151, starving=True, **kw):
    return mig.Place(key=key, owner=owner, market="m", attraction=attraction, speed=speed,
                     allowed=mig.allowed_types(starving=starving), pops=pops or {}, caps=caps, religion=religion,
                     owner_religion=religion, **kw)


def market():
    src = place("src", -6.0, pops={"peasants": [(10.0, "cath")], "nobles": [(0.2, "cath")], "burghers": [(0.5, "cath")]})
    near = place("near", 2.0, caps={"nobles": 1.0, "burghers": 0.1}, pops={"burghers": [(0.2, "cath")]})
    far = place("far", 3.0, caps={"nobles": 1.0, "burghers": 1.0})
    low = place("low", -1.0)
    return [src, near, far, low]


def test_receivers_are_above_the_plain_market_mean():
    average, receivers = mig.market_lists(market())
    assert average["m"] == pytest.approx((-6.0 + 2.0 + 3.0 - 1.0) / 4)
    assert receivers == {"near", "far"}


def test_target_is_best_gain_discounted_by_distance_and_own_owner_first():
    places = market()
    src = places[0]
    receivers = places[1:3]
    # near: 8 x exp(-50/480) = 7.2; far: 9 x exp(-600/480) = 2.6
    assert mig.choose_target(src, receivers, dist).key == "near"
    foreign = place("foreign", 5.0, owner="B")
    assert mig.choose_target(src, receivers + [foreign], dist).key == "near"   # own receivers exist: no foreign
    assert mig.choose_target(src, [foreign], dist).key == "foreign"


def test_flows_amount_room_and_uncapped_peasants():
    flows = mig.monthly_flows(market(), dist)
    by = {(f.source, f.pop_type): f for f in flows}
    assert {f.target for f in flows} == {"near"}
    assert by[("src", "peasants")].amount == pytest.approx(10.0 * 0.1 * 0.0151)      # 0.15 % of the peasants
    assert by[("src", "nobles")].amount == pytest.approx(0.2 * 1.0 * 0.0151)
    assert ("src", "burghers") not in by               # near is full of burghers (0.2 >= 0.1): they stay


def test_minimum_one_person_and_source_floor():
    places = market()
    places[0].speed = 0.0001
    flows = mig.monthly_flows(places, dist)
    assert min(f.amount for f in flows) == mig.MIN_AMOUNT
    small = place("small", -6.0, pops={"peasants": [(0.9, "cath")]})
    assert not [f for f in mig.monthly_flows(market()[1:] + [small], dist) if f.source == "small"]


def test_foreign_target_needs_the_pop_religion():
    src = place("src", -6.0, pops={"peasants": [(10.0, "cath"), (5.0, "orth")]})
    foreign = place("foreign", 5.0, owner="B", religion="orth")
    flows = mig.monthly_flows([src, foreign, place("low", -8.0)], dist)
    assert [(f.religion, f.target) for f in flows] == [("orth", "foreign")]


def test_apply_moves_people_between_pops():
    places = {p.key: p for p in market()}
    flows = mig.monthly_flows(places.values(), dist)
    before = sum(p.population() for p in places.values())
    mig.apply(places, flows)
    assert sum(p.population() for p in places.values()) == pytest.approx(before)
    assert places["near"].pops["peasants"][0][0] == pytest.approx(10.0 * 0.1 * 0.0151)


def test_scale_helpers():
    assert mig.free_land_scales(0.5, 10.0) == pytest.approx((0.95, 0.0, 0.0))    # abundant under 10 % and 10k
    assert mig.free_land_scales(15.0, 200.0) == pytest.approx((0.0, 0.925, 0.0))  # 10k or more: available
    assert mig.free_land_scales(12.0, 10.0) == pytest.approx((0.0, 0.0, 0.2))
    assert mig.surplus_jobs_scale(3.0, 1.5) == 1.0 and mig.surplus_jobs_scale(1.0, 1.5) == 0.0
    assert mig.speed(starving=True, overpopulation=0.4) == pytest.approx(0.0001 + 0.015 + 0.001)
    assert mig.speed(starving=False, modifier=-0.25) == pytest.approx(0.000075)
    starving = mig.dynamic_attraction(starving=True, pop_k=5.0, capacity_k=5.0)
    fed = mig.dynamic_attraction(starving=False, pop_k=5.0, capacity_k=5.0)
    assert fed - starving == pytest.approx(7.5)
    assert mig.fixed_attraction(capital=True, market_center=True, static_modifiers=0.3) == pytest.approx(0.45)


def pools():
    common = dict(catchment="m", tribesmen=0.0, flat_food=0.0, provision_food=0.0, serve_food=0.0, cookshop_levels=0.0,
                  taverns=0.0, yards=0.0, victuals_demand=0.0, peasant_share=0.8, n_locations=5.0, lon=0.0,
                  type_shares={"peasants": 0.8, "laborers": 0.1, "nobles": 0.05, "clergy": 0.05}, religion="cath")
    return [
        fs.Pool(owner="A", province="short", pop0=100.0, demand0=100.0, workers0=90.0, jobs0=0.0, yield_=60 / 90,
                capacity=1000.0, start_food=100.0, lat=0.0, pop_capacity=120.0, attraction_fixed=0.2, **common),
        fs.Pool(owner="A", province="fed", pop0=100.0, demand0=100.0, workers0=90.0, jobs0=0.0, yield_=100 / 90,
                capacity=2400.0, start_food=400.0, lat=1.0, pop_capacity=150.0, attraction_fixed=0.3, **common),
    ]


def test_food_sim_migration_moves_the_starving_pool_into_the_fed_one():
    off = {r["province"]: r for r in fs.simulate(pools(), fs.SimRules(harvest=False))}
    on_rules = fs.SimRules(harvest=False, migration=True)
    on = {r["province"]: r for r in fs.simulate(pools(), on_rules)}
    assert off["short"]["migrated_out_k"] == 0.0
    assert on["short"]["migrated_out_k"] > 0 and on["fed"]["migrated_in_k"] == pytest.approx(on["short"]["migrated_out_k"])
    assert on["fed"]["migrated_out_k"] == 0.0 and on["fed"]["pop_end_k"] > off["fed"]["pop_end_k"]
    summary = fs.summarize(list(on.values()), on_rules)
    assert summary["migration"] and summary["migrated_k"] == pytest.approx(on["short"]["migrated_out_k"], abs=0.1)
    # with the switch the starving pool's flat out-migration sink is gone: the world keeps the migrants
    world_on = sum(r["pop_end_k"] for r in on.values())
    world_off = sum(r["pop_end_k"] for r in off.values())
    assert world_on > world_off


def test_migration_inputs_round_trip(tmp_path):
    path = tmp_path / "input.csv"
    fs.write_inputs(path, pools())
    back = fs.read_inputs(path)
    assert back[0].type_shares == {"clergy": 0.05, "laborers": 0.1, "nobles": 0.05, "peasants": 0.8}
    assert back[1].religion == "cath" and back[1].pop_capacity == 150.0 and math.isclose(back[0].n_locations, 5.0)
