"""Plan run against control run (src/prosper_or_perish_constructor/plan_run_report.py, `ppc plan-run-report`).

Synthetic save tables and logs only: no game, no real saves."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

from prosper_or_perish_constructor import plan_run_report as prr
from prosper_or_perish_constructor import plan_test_report as ptr

CID = 7
KINDS = {"granary": "food", "lumber_mill": "business", "carrier_inn": "logistics", "field_drainage": "improve"}


def snap(name: str, date: str, levels: dict[tuple[int, str], float], *, tag: str = "CAS",
         owned: set[int] = frozenset({1, 2, 3}), closed: set[tuple[int, str]] = frozenset(),
         employed: dict[tuple[int, str], float] | None = None, gold: float = 100.0, income: float = 5.0,
         expense: float = 4.0, tax_base: float = 50.0, cvars: dict[str, float] | None = None,
         food: list[tuple[int, float, float, float]] = (), access: dict[int, float] | None = None,
         goods: list[tuple[int, str, float, float, float, float]] = (),
         flows: list[tuple[str, str, int, float]] = ()) -> ptr.Snapshot:
    """A save: locations 1..4 (owned ones are the country's, market 1 for 1-2 and market 2 for 3-4), buildings by
    (location, type) -> level, each fully staffed with 2 workers a level unless `employed` says otherwise."""
    ids = (1, 2, 3, 4)
    locs = pl.DataFrame({
        "location_id": list(ids), "slug": ["a", "b", "c", "d"],
        "country_tag": [tag if i in owned else "OTH" for i in ids],
        "owner_country_id": [CID if i in owned else 9 for i in ids],
        "owner": [CID if i in owned else 9 for i in ids],
        "controller": [CID if i in owned else 9 for i in ids],
        "total_population": [10.0, 20.0, 30.0, 40.0],
        "market_access": [(access or {}).get(i, 1.0) for i in ids],
        "market_id": [1, 1, 2, 2],
    })
    keys = sorted(levels)
    buildings = pl.DataFrame({
        "building_id": list(range(len(keys))), "location_id": [k[0] for k in keys],
        "building_type": [k[1] for k in keys], "level": [float(levels[k]) for k in keys],
        "employed": [(employed or {}).get(k, 2.0 * levels[k]) for k in keys],
        "open": [False if k in closed else None for k in keys],
    }, schema={"building_id": pl.Int64, "location_id": pl.Int64, "building_type": pl.Utf8, "level": pl.Float64,
               "employed": pl.Float64, "open": pl.Boolean})
    buildings = buildings.join(locs.select("location_id", "country_tag"), on="location_id", how="left")
    tables = SimpleNamespace(
        locations=locs, buildings=buildings,
        countries_raw=pl.DataFrame({"country_id": [CID, 9], "tag": [tag, "OTH"]}),
        country_ai=pl.DataFrame({"country_id": [CID], "gold": [gold], "income": [income], "expense": [expense],
                                 "tax_base": [tax_base]}),
        country_variables=pl.DataFrame({"country_id": [CID] * len(cvars or {}), "name": list(cvars or {}),
                                        "value": list((cvars or {}).values())},
                                       schema={"country_id": pl.Int64, "name": pl.Utf8, "value": pl.Float64}),
        province_food=pl.DataFrame([{"province_id": p, "food_current": f, "max_food_value": mx,
                                     "base_food_consumption": c, "cached_food_change": 0.0} for p, f, mx, c in food],
                                   schema={"province_id": pl.Int64, "food_current": pl.Float64,
                                           "max_food_value": pl.Float64, "base_food_consumption": pl.Float64,
                                           "cached_food_change": pl.Float64}),
        provinces_raw=pl.DataFrame({"province_id": [1, 2, 3], "capital_location_id": [1, 3, 4],
                                    "owner_country_id": [CID, CID, 9]}),
        market_goods=pl.DataFrame([{"market_id": m, "good_id": g, "price": p, "default_price": d, "supply": s,
                                    "demand": s, "stockpile": st} for m, g, p, d, s, st in goods],
                                  schema={"market_id": pl.Int64, "good_id": pl.Utf8, "price": pl.Float64,
                                          "default_price": pl.Float64, "supply": pl.Float64, "demand": pl.Float64,
                                          "stockpile": pl.Float64}),
        production_method_good_flows=pl.DataFrame(
            [{"good_id": g, "building_type": b, "location_id": loc, "direction": "output", "nominal_amount": a,
              "allocated_amount": a} for g, b, loc, a in flows],
            schema={"good_id": pl.Utf8, "building_type": pl.Utf8, "location_id": pl.Int64, "direction": pl.Utf8,
                    "nominal_amount": pl.Float64, "allocated_amount": pl.Float64}),
    )
    return ptr.Snapshot(name, date, ptr.parse_game_date(date), None, tables)


ON = {"pp_cplan_on": 0.00001}
START = {(1, "granary"): 1, (2, "lumber_mill"): 2}


def two_runs() -> tuple[list[ptr.Snapshot], list[ptr.Snapshot]]:
    food0 = [(1, 60.0, 240.0, 10.0), (2, 20.0, 240.0, 10.0)]
    plan = [
        snap("p_1337_04_01", "1337.4.1", START, cvars=ON, food=food0),
        snap("p_1338_01_01", "1338.1.1", {(1, "granary"): 2, (2, "lumber_mill"): 4, (3, "carrier_inn"): 1},
             cvars=ON, gold=80.0, income=7.0, tax_base=55.0, food=[(1, 120.0, 240.0, 10.0), (2, 50.0, 240.0, 10.0)],
             access={1: 0.9}),
        # Castile became Spain: the same country id under a new tag
        snap("p_1339_01_01", "1339.1.1", {(1, "granary"): 3, (2, "lumber_mill"): 6, (3, "carrier_inn"): 2},
             tag="SPA", cvars=ON, gold=60.0, income=9.0, tax_base=60.0, closed={(2, "lumber_mill")},
             employed={(1, "granary"): 3.0}, food=[(1, 240.0, 240.0, 10.0), (2, 100.0, 240.0, 10.0)]),
    ]
    control = [
        snap("c_1337_04_01", "1337.4.1", START, food=food0),
        snap("c_1338_01_01", "1338.1.1", {(1, "granary"): 1, (2, "lumber_mill"): 3}, gold=150.0, income=6.0,
             food=[(1, 70.0, 240.0, 10.0), (2, 20.0, 240.0, 10.0)], access={1: 0.9, 2: 0.9}),
        snap("c_1339_01_01", "1339.1.1", {(1, "granary"): 1, (2, "lumber_mill"): 5}, gold=200.0, income=6.5,
             tax_base=52.0, food=[(1, 80.0, 240.0, 10.0), (2, 25.0, 240.0, 10.0)], access={1: 0.9, 2: 0.9}),
    ]
    return plan, control


def test_runs_follow_the_plan_country_by_id_through_a_tag_change() -> None:
    plan_saves, control_saves = two_runs()
    plan, control, tag = prr.make_runs(plan_saves[::-1], control_saves)
    assert tag == "CAS" and plan.cid == CID and control is not None and control.cid == CID
    assert [s.name for s in plan.snaps] == ["p_1337_04_01", "p_1338_01_01", "p_1339_01_01"]  # sorted by date
    assert [plan.tag(s) for s in plan.snaps] == ["CAS", "CAS", "SPA"]
    assert [(a.name, b.name) for a, b in prr.pairs(plan, control)] == [
        ("p_1337_04_01", "c_1337_04_01"), ("p_1338_01_01", "c_1338_01_01"), ("p_1339_01_01", "c_1339_01_01")]
    # a control save half a year off is no common date
    late = prr.Run(prr.CONTROL, [snap("c_late", "1338.8.1", START)], CID)
    assert [a.name for a, _ in prr.pairs(plan, late)] == []
    with pytest.raises(SystemExit):
        prr.make_runs(plan_saves, control_saves, country="XXX")


def test_country_levels_and_type_compare() -> None:
    plan_saves, control_saves = two_runs()
    plan, control, _ = prr.make_runs(plan_saves, control_saves)
    country = prr.country_series([plan, control])
    spa = country.filter((pl.col("series") == "plan") & (pl.col("save") == "p_1339_01_01")).row(0, named=True)
    assert spa["tag"] == "SPA" and spa["building_levels"] == 11 and spa["balance"] == pytest.approx(5.0)
    assert spa["population_k"] == 60.0 and spa["locations"] == 3
    levels = prr.kind_series([plan, control], KINDS)
    diff = prr.kind_difference(levels, plan, control)
    assert diff["total"].to_list() == [0.0, 3.0, 5.0]
    assert diff["food"].to_list() == [0.0, 1.0, 2.0] and diff["logistics"].to_list() == [0.0, 1.0, 2.0]
    types = prr.type_compare(plan, control, KINDS, prr.pairs(plan, control)[-1])
    rows = {r["building_type"]: r for r in types.iter_rows(named=True)}
    assert rows["granary"]["plan_added"] == 2 and rows["granary"]["control_added"] == 0
    assert rows["granary"]["plan_lead"] == 2 and rows["granary"]["kind"] == "food"
    assert rows["lumber_mill"]["plan_lead"] == 1 and rows["carrier_inn"]["start"] == 0
    assert types["building_type"][0] in ("granary", "carrier_inn")  # the largest lead first
    alone = prr.type_compare(plan, None, KINDS)
    assert "plan_lead" not in alone.columns and dict(alone.select("building_type", "plan_added").iter_rows()) == {
        "lumber_mill": 4.0, "granary": 2.0, "carrier_inn": 2.0}


def test_closed_and_understaffed_levels() -> None:
    plan_saves, control_saves = two_runs()
    plan, control, _ = prr.make_runs(plan_saves, control_saves)
    full = prr.full_staffing([plan, control])
    assert full == {"granary": 2.0, "lumber_mill": 2.0, "carrier_inn": 2.0}  # the fullest open level of each type
    staff = prr.staffing([plan, control], full)
    last = staff.filter((pl.col("series") == "plan") & (pl.col("save") == "p_1339_01_01")).row(0, named=True)
    # the lumber mill (6 levels) is closed; the granary works 3 of 6 workers: below 90 % of full
    assert last["closed_levels"] == 6 and last["understaffed_levels"] == 3 and last["levels"] == 11
    assert staff.filter(pl.col("series") == "control")["closed_levels"].sum() == 0
    trouble = prr.trouble_by_type(plan, plan.snaps[-1], full)
    assert dict(trouble.select("building_type", "closed_levels").iter_rows()) == {"lumber_mill": 6.0, "granary": 0.0}
    # a save without staffing numbers: unknown, never under-staffed
    blank = snap("x", "1340.1.1", {(1, "granary"): 2})
    blank.tables.buildings = blank.tables.buildings.with_columns(pl.lit(None, dtype=pl.Float64).alias("employed"))
    row = prr.staffing([prr.Run("plan", [blank], CID)], full).row(0, named=True)
    assert row["understaffed_levels"] == 0 and row["staffing_unknown_levels"] == 2


def test_food_and_market_access() -> None:
    plan_saves, control_saves = two_runs()
    plan, control, _ = prr.make_runs(plan_saves, control_saves)
    food = prr.food_series([plan, control], ptr.Settings())
    first = food.filter(pl.col("save") == "p_1337_04_01").row(0, named=True)
    assert first["provinces"] == 2 and first["under_famine_line"] == 1 and first["median_months"] == pytest.approx(4.0)
    last = food.filter(pl.col("save") == "p_1339_01_01").row(0, named=True)
    assert last["under_famine_line"] == 0 and last["at_24_months"] == 1 and last["lowest_months"] == pytest.approx(10.0)
    fc = prr.food_compare(plan, control, prr.pairs(plan, control)[-1])
    assert fc["province_id"].to_list() == [2, 1]  # the plan's smallest lead first
    assert fc["plan_minus_control"].to_list() == pytest.approx([7.5, 16.0])
    access = prr.access_series([plan, control], KINDS, ptr.Settings())
    row = access.filter(pl.col("save") == "c_1339_01_01").row(0, named=True)
    assert row["below_line"] == 2 and row["mean_access"] == pytest.approx((0.9 + 0.9 + 1.0) / 3)
    plan_row = access.filter(pl.col("save") == "p_1339_01_01").row(0, named=True)
    assert plan_row["logistics_levels"] == 2 and plan_row["most_levels_in_a_location"] == 6
    assert plan_row["levels_per_location"] == pytest.approx(11 / 3)


def test_verdict_names_the_run_that_is_ahead() -> None:
    plan_saves, control_saves = two_runs()
    plan, control, _ = prr.make_runs(plan_saves, control_saves)
    runs = [plan, control]
    full = prr.full_staffing(runs)
    table, where = prr.verdict(prr.country_series(runs), prr.staffing(runs, full), prr.food_series(runs, ptr.Settings()),
                               prr.access_series(runs, KINDS, ptr.Settings()), plan, control)
    assert where.startswith("1339.1.1")
    rows = {r["measure"]: r for r in table.iter_rows(named=True)}
    assert rows["building levels"]["plan"] == 11 and rows["building levels"]["control"] == 6
    assert rows["building levels"]["ahead"] == "plan" and rows["building levels"]["in_percent"] == pytest.approx(83.3, 0.01)
    assert rows["closed building levels"]["ahead"] == "control"  # less is better
    assert rows["treasury (gold)"]["plan_minus_control"] == -140 and rows["treasury (gold)"]["ahead"] == "control"
    assert rows["locations below the access line"]["ahead"] == "plan"
    assert rows["population (thousands)"]["ahead"] == ""  # a tie
    alone, where = prr.verdict(prr.country_series([plan]), prr.staffing([plan], full),
                               prr.food_series([plan], ptr.Settings()), prr.access_series([plan], KINDS, ptr.Settings()),
                               plan, None)
    assert "no control run" in where and alone["control"].null_count() == alone.height


def test_purses_from_the_country_variables() -> None:
    cvars = {**ON, "pp_cplan_purse_101": 350.0, "pp_cplan_save_cost_101": 500.0, "pp_cplan_purse_103": 100.0,
             "pp_cplan_hs_101_1": 160.0, "pp_cplan_hs_101_2": 100.0, "pp_cplan_hs_101_12": 140.0,
             "pp_cplan_hn_101_1": 260.0, "pp_cplan_hs_107_3": 125.0}
    run = prr.Run("plan", [snap("p0", "1337.4.1", START), snap("p1", "1338.1.1", START, cvars=cvars)], CID)
    purses = prr.purse_series(run)
    assert purses["save"].unique().to_list() == ["p1"]  # the plan is off in p0
    rows = {r["group"]: r for r in purses.iter_rows(named=True)}
    assert set(rows) == set(ptr.GROUPS)
    assert rows["food"]["purse"] == 250 and rows["food"]["saving_for_cost"] == 400
    assert rows["food"]["spent_last_12_passes"] == 100 and rows["food"]["wanted_last_12_passes"] == 160
    assert rows["business"]["purse"] == 0 and rows["business"]["saving_for_cost"] is None
    assert rows["country"]["spent_last_12_passes"] == 25 and rows["logistics"]["purse"] is None


DUMP_LOG = [
    "[10:00:00][console.cpp:1174]: Running console command: run pp_run_dump.txt",
    "[10:00:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:8: PPRUN;D;begin",
    "[10:00:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:11: PPRUN;S;101",
    "[10:00:00][jomini_effect_impl.cpp:2666]: Building Type \x27Granary\x27 (350)",
    "[10:00:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:16: PPRUN;L;101",
    "[10:00:00][jomini_effect_impl.cpp:2666]: Location \x27Valladolid\x27 (2584)",
    "[10:00:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:60: PPRUN;L;107",
    "[10:00:00][jomini_effect_impl.cpp:2666]: Location \x27Burgos\x27 (2500)",
    "[10:00:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:70: PPRUN;D;end",
    "[10:00:01][console.cpp:1174]: Running console command: save pp_run_y1338",
    "[10:05:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:8: PPRUN;D;begin",
    "[10:05:00][jomini_effect_impl.cpp:479]: run/pp_run_dump.txt:70: PPRUN;D;end",
    "[10:05:01][console.cpp:1174]: Running console command: save pp_run_y1339_p1",
]


def test_dumps_say_what_each_group_saves_for() -> None:
    dumps = prr.parse_dumps(DUMP_LOG)
    rows = dumps.rows(named=True)
    assert [(r["dump"], r["group"], r["building"], r["location"], r["console_save"]) for r in rows] == [
        (1, "food", "Granary", "Valladolid", "pp_run_y1338"),
        (1, "country", None, "Burgos", "pp_run_y1338"),       # a town or city upgrade has no building type
        (2, None, None, None, "pp_run_y1339_p1"),             # a dump in which no group saves
    ]
    run = prr.Run("plan", [snap("pp_run_1337_04_01", "1337.4.1", START), snap("pp_run_1338_01_01", "1338.1.1", START)],
                  CID)
    joined = prr.dump_saves(dumps, run)
    assert joined["save"].to_list() == ["pp_run_1338_01_01", "pp_run_1338_01_01", None]  # a pause save is no kept save
    start = prr.dump_saves(pl.DataFrame([{"dump": 1, "clock": 0.0, "console_save": "pp_run_start", "group": "food",
                                          "building": "x", "location": "y"}], schema=prr.DUMP_SCHEMA), run)
    assert start["date"].to_list() == ["1337.4.1"]


def test_stops_between_monthly_passes() -> None:
    lines = []
    clock = 36000
    for month in range(12):  # a pass every 3 s; a 40 s stop with a save, a 60 s stop without any console command
        clock += {5: 40, 9: 60}.get(month, 3)
        if month == 5:
            lines.append(f"[{clock // 3600:02d}:{clock % 3600 // 60:02d}:{clock % 60 - 1:02d}][console.cpp:1174]: "
                         "Running console command: save pp_run_y1338")
        lines.append(f"[{clock // 3600:02d}:{clock % 3600 // 60:02d}:{clock % 60:02d}][x.cpp:1]: f.txt:125: PPCPLAN;P")
    plog = ptr.parse_debug_log(lines, start_year=ptr.year_fraction(1337, 4, 1))
    steps = prr.month_steps(plog, lines)
    assert steps.height == 11 and steps["seconds"].max() == 60
    slow, info = prr.stops(steps)
    assert info["months"] == 11 and info["median_seconds"] == 3 and info["stops"] == 2 and info["unexplained"] == 1
    assert slow["explained"].to_list() == [True, False]
    assert slow["console"].to_list() == ["save pp_run_y1338", None]
    assert slow["date"].to_list() == ["1337.10.1", "1338.2.1"]
    none, info = prr.stops(prr.month_steps(ptr.parse_debug_log([], start_year=1337.0), []))
    assert none.is_empty() and info == {}
    pauses = prr.run_log_pauses(["2026-11-10 20:00:00 year: game date 1338.1.1 after 60 s, pauses this year 0 -> x",
                                 "2026-11-10 20:05:00 PAUSE 1 at game date 1338.6.12 (target 1339.1.1; screenshot a.png) -> y"])
    assert pauses.select("pause", "game_date").rows() == [(1, "1338.6.12")]


def test_goods_of_the_building_types_the_plan_added() -> None:
    plan_saves, control_saves = two_runs()
    # lumber: the plan run floods its markets; tools only the control's lumber mills make
    flows = [("lumber", "lumber_mill", 2, 12.0), ("offcuts", "lumber_mill", 2, 1.0), ("grain", "granary", 4, 99.0)]
    plan_saves[0].tables.market_goods = snap("g", "1337.4.1", START, goods=[(1, "lumber", 1.0, 1.0, 10.0, 5.0),
                                                                            (2, "lumber", 1.2, 1.0, 10.0, 5.0)]).tables.market_goods
    plan_saves[2] = snap("p_1339_01_01", "1339.1.1", {(1, "granary"): 3, (2, "lumber_mill"): 6}, tag="SPA", cvars=ON,
                         goods=[(1, "lumber", 0.4, 1.0, 20.0, 80.0), (2, "lumber", 0.7, 1.0, 10.0, 10.0),
                                (3, "lumber", 9.0, 1.0, 1.0, 1.0)], flows=flows)
    control_saves[2] = snap("c_1339_01_01", "1339.1.1", {(1, "granary"): 1, (2, "lumber_mill"): 5},
                            goods=[(1, "lumber", 0.9, 1.0, 10.0, 10.0), (2, "lumber", 1.1, 1.0, 10.0, 10.0)])
    plan, control, _ = prr.make_runs(plan_saves, control_saves)
    types = prr.type_compare(plan, control, KINDS, prr.pairs(plan, control)[-1])
    goods = prr.plan_goods(plan, types)
    # the granary's grain comes from a location the country does not own; the lumber mill's goods by output
    assert goods["good"].to_list() == ["lumber", "offcuts"] and goods["building_types"].to_list() == ["lumber_mill"] * 2
    series = prr.goods_series([plan, control], ["lumber"])
    end = series.filter(pl.col("save") == "p_1339_01_01").row(0, named=True)
    # markets 1 and 2 (two and one of the country's locations): (2 x 0.4 + 0.7) / 3; market 3 is not the country's
    assert end["price_ratio"] == pytest.approx(0.5) and end["stock_months"] == pytest.approx(3.0)
    gv = prr.goods_verdict(series, plan, control).row(0, named=True)
    assert gv["plan_start"] == pytest.approx((2 * 1.0 + 1.2) / 3) and gv["plan_lowest"] == pytest.approx(0.5)
    assert gv["control_end"] == pytest.approx((2 * 0.9 + 1.1) / 3) and gv["flooded"] is True
    assert prr.plan_goods(plan, types.clear()).is_empty()


def test_build_run_report_writes_page_summary_and_csvs(tmp_path) -> None:
    plan_saves, control_saves = two_runs()
    cvars = {**ON, "pp_cplan_purse_101": 350.0, "pp_cplan_hs_101_1": 160.0}
    plan_saves[1] = snap("p_1338_01_01", "1338.1.1", {(1, "granary"): 2, (2, "lumber_mill"): 4, (3, "carrier_inn"): 1},
                         cvars=cvars, food=[(1, 120.0, 240.0, 10.0), (2, 50.0, 240.0, 10.0)],
                         goods=[(1, "lumber", 0.8, 1.0, 10.0, 10.0)], flows=[("lumber", "lumber_mill", 2, 12.0)])
    plan_saves[2] = snap("p_1339_01_01", "1339.1.1", {(1, "granary"): 3, (2, "lumber_mill"): 6, (3, "carrier_inn"): 2},
                         tag="SPA", cvars=cvars, food=[(1, 240.0, 240.0, 10.0), (2, 100.0, 240.0, 10.0)],
                         goods=[(1, "lumber", 0.4, 1.0, 20.0, 80.0)], flows=[("lumber", "lumber_mill", 2, 12.0)])
    debug = [
        "[10:00:00][x.cpp:1]: f.txt:377: PPCPLAN;B;food",
        "[10:00:00][x.cpp:2]: Building Type \x27Granary\x27 (350)",
        "[10:00:00][x.cpp:2]: Location \x27Valladolid\x27 (2584)",
        "[10:00:00][x.cpp:1]: f.txt:125: PPCPLAN;P",
        "[10:00:03][x.cpp:1]: f.txt:125: PPCPLAN;P",
        "[10:00:06][x.cpp:1]: f.txt:125: PPCPLAN;P",
        *DUMP_LOG,
    ]
    page = prr.build_run_report(plan_saves, tmp_path, control_saves=control_saves, debug_lines=debug,
                                debug_source="debug.log", error_lines=["[1:00:00]: pp_cplan broke"],
                                error_source="error.log", run_log_lines=["x PAUSE 1 at game date 1338.6.12 (target"],
                                kinds=KINDS, log=lambda _: None)
    text = page.read_text(encoding="utf-8")
    for heading in ("Verdict", "Did the game run without a stop", "Buildings", "Treasury, income, tax base, population",
                    "Stored food", "Market access", "The plan: constructions, gold, savings",
                    "Markets of the goods the plan built for", "Errors"):
        assert heading in text
    assert "Construction Plan run: CAS" in text and "prefers-color-scheme: dark" in text
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Plan lead in levels: +5" in summary and "Pauses (loop): 1" in summary
    for name in ("verdict.csv", "levels_by_save.csv", "levels_kind_lead.csv", "staffing.csv", "levels_by_type.csv",
                 "country.csv", "food.csv", "food_by_province.csv", "market_access.csv", "builds_by_year.csv",
                 "purses.csv", "saving_for.csv", "goods.csv", "goods_verdict.csv", "loop_pauses.csv", "errors.csv",
                 "levels_total.png", "levels_total_dark.png", "levels_kind_lead.png", "country_gold.png",
                 "food_median.png", "access_mean.png", "plan_purses.png", "goods_price.png"):
        assert (tmp_path / name).is_file(), name
    assert pl.read_csv(tmp_path / "saving_for.csv")["building"].to_list() == ["Granary", None]
    # without a control run the report still stands
    alone = prr.build_run_report(plan_saves, tmp_path / "alone", kinds=KINDS, log=lambda _: None)
    assert "no control run" in alone.read_text(encoding="utf-8")
