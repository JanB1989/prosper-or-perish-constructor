"""Start-food validator (worldbuilder/food_sim.py) on a three-pool fake."""

from __future__ import annotations

from prosper_or_perish_constructor.worldbuilder import food_sim as fs


def pools():
    common = dict(catchment="m", tribesmen=0.0, flat_food=0.0, provision_food=0.0, serve_food=0.0, cookery_levels=0.0,
                  imports=0.0, exports=0.0, victuals_demand=0.0, peasant_share=0.8)
    return [
        # 100k pops eating 100 while their 90k jobless make 0.6 x 100: starves and collapses
        fs.Pool(owner="A", province="short", pop0=100.0, demand0=100.0, workers0=90.0, jobs0=0.0, yield_=60 / 90,
                capacity=1000.0, start_food=100.0, **common),
        # fed exactly: stays level
        fs.Pool(owner="A", province="fed", pop0=100.0, demand0=100.0, workers0=90.0, jobs0=0.0, yield_=100 / 90,
                capacity=2400.0, start_food=400.0, **common),
        # large surplus and a small store: pinned at the cap
        fs.Pool(owner="B", province="rich", pop0=50.0, demand0=50.0, workers0=50.0, jobs0=0.0, yield_=2.0,
                capacity=600.0, start_food=60.0, **common),
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


def test_victualler_import_rescues_the_short_pool_when_the_market_has_victuals(tmp_path):
    rules = fs.SimRules(harvest=False)
    ps = pools()
    ps[0].imports = 1.0
    ps[2].victuals_other_supply = 10.0
    rows = {r["province"]: r for r in fs.simulate(ps, rules)}
    assert not rows["short"]["collapsing"] and rows["short"]["imported_food"] > 0
    ps[2].victuals_other_supply = 0.0                           # no victuals in the market: the import cannot help
    rows = {r["province"]: r for r in fs.simulate(ps, rules)}
    assert rows["short"]["collapsing"] and rows["short"]["imported_food"] == 0


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
