"""Construction Plan test-run report (src/prosper_or_perish_constructor/plan_test_report.py, `ppc plan-report`).

Synthetic logs and save tables only: no game, no real saves."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

from prosper_or_perish_constructor import plan_test_report as ptr

# A debug.log as the game writes it: wall clock, often a [file:line]: prefix, the date line before each pass,
# a midnight wrap, a load that jumps the date back, one tagged line in neither format.
DEBUG_LOG = """\
[23:59:50][pdx_steam.cpp:218]: Failed to initialize Steam
[23:59:58][virtualfilesystem_physfs.cpp:596]: Mounted Data: C:/Games/game 1.4.7 build 2026.11.8
[23:59:59][script_debug.cpp:12]: 1337.5.1
[23:59:59][script_debug.cpp:40]: PPCPLAN;B;food;burgos;granary
[23:59:59][script_debug.cpp:40]: PPCPLAN;B;105;avila;lumber_mill
[00:00:01][script_debug.cpp:40]: PPCPLAN;P;2;117.25
[00:00:03]: 1337.6.1
[00:00:03]: PPCPLAN;B;103;sevilla;mason
[00:00:03]: PPCPLAN;B;Improve;lisboa;field_drainage ; extra
[00:00:03]: PPCPLAN;P;2.0;80.5
[00:00:05]: 1337.7.1
[00:00:05]: PPCPLAN;X;something new
[00:00:06]: 1337.6.1
[00:00:06]: PPCPLAN;B;logistics;burgos;carrier_inn
[00:00:06]: PPCPLAN;P;1;40
"""


def test_parse_debug_log_reads_builds_passes_and_dates() -> None:
    log = ptr.parse_debug_log(DEBUG_LOG.splitlines())
    assert log.lines == 15 and log.plan_lines == 9
    b = log.builds
    assert b["group"].to_list() == ["food", "profile", "business", "improve", "logistics"]
    assert b["location"].to_list() == ["burgos", "avila", "sevilla", "lisboa", "burgos"]
    assert b["building"].to_list() == ["granary", "lumber_mill", "mason", "field_drainage", "carrier_inn"]
    assert b["date"].to_list() == ["1337.5.1", "1337.5.1", "1337.6.1", "1337.6.1", "1337.6.1"]
    # the build-number date 2026.11.8 is outside GAME_YEARS; the clock wraps past midnight
    assert log.dates["date"].to_list() == ["1337.5.1", "1337.6.1", "1337.7.1", "1337.6.1"]
    assert log.dates["clock"].to_list() == [9.0, 13.0, 15.0, 16.0]
    assert log.dates["segment"].to_list() == [0, 0, 0, 1]  # the load jumped back to June
    p = log.passes
    assert p["started"].to_list() == [2.0, 2.0, 1.0] and p["gold"].to_list() == [117.25, 80.5, 40.0]
    assert log.unparsed == ["PPCPLAN;X;something new"]


def test_reason_codes_follow_the_plan() -> None:
    """Every construction code of the plan's rule groups has a name here (a new group, e.g. 107 Towns and Buildings,
    must not land in the report as a bare number), and the game's marker lines carry the same names."""
    import re
    from pathlib import Path

    from prosper_or_perish_constructor import construction_plan as cp

    assert {int(code) for code in ptr.WHY_CODES} == set(cp.GROUP_WHY.values())
    assert set(ptr.WHY_CODES.values()) == set(ptr.GROUPS)
    assert len(ptr.GROUPS) <= len(ptr.LIGHT_SERIES)  # a chart colour per group
    names = {str(why): ("profile" if group == "profiles" else group) for group, why in cp.GROUP_WHY.items()}
    assert ptr.WHY_CODES == names
    loc = (Path(__file__).resolve().parents[1]
           / "mod/pp/main_menu/localization/english/pp_construction_plan_l_english.yml").read_text(encoding="utf-8-sig")
    for code, name in ptr.WHY_CODES.items():
        assert re.search(rf"^  PP_CPLAN_TLOG_{code}: \"PPCPLAN;B;{name}\"$", loc, re.MULTILINE), code
    log = ptr.parse_debug_log(["[10:00:00]: 1337.5.1", "[10:00:01]: PPCPLAN;B;107;toledo;marketplace",
                               "[10:00:02]: PPCPLAN;B;country;toledo;marketplace"])
    assert log.builds["group"].to_list() == ["country", "country"]


def test_date_words_and_year_range() -> None:
    log = ptr.parse_debug_log(["[10:00:00]: 1 April 1337", "[10:00:01]: PPCPLAN;B;rule;x;y",
                               "[10:00:02]: version 3.10.2026", "[10:00:03]: PPCPLAN;P;1;2"])
    assert log.builds["date"].to_list() == ["1337.4.1"]
    assert log.passes["date"].to_list() == ["1337.4.1"]  # 3.10.2026 is not a game date


def test_latest_timeline_keeps_the_replayed_dates_of_the_later_load() -> None:
    log = ptr.parse_debug_log(DEBUG_LOG.splitlines())
    kept, dropped = ptr.latest_timeline(log.builds, log.dates)
    # segment 1 starts at 1337.6.1: segment 0's June lines are replaced, May stays
    assert dropped == 2
    assert kept["building"].to_list() == ["granary", "lumber_mill", "carrier_inn"]


def test_log_speed_per_year_and_pauses() -> None:
    rows = []
    clock = 0.0
    for i in range(25):  # monthly dates over two years, 2 s a month; one 10-minute pause
        y, m = 1337 + i // 12, i % 12 + 1
        rows.append({"clock": clock, "segment": 0, "date": f"{y}.{m}.1", "year": ptr.year_fraction(y, m, 1)})
        clock += 600.0 if i == 5 else 2.0
    per_year, total = ptr.log_speed(pl.DataFrame(rows, schema=ptr.DATE_SCHEMA))
    assert total["pauses"] == 1
    assert total["s_per_year"] == pytest.approx(24.0)
    assert per_year["year"].to_list() == [1337, 1338]
    assert per_year["s_per_year"].to_list() == pytest.approx([24.0, 24.0])


def test_error_summary_groups_plan_lines() -> None:
    lines = ["[10:00:00][jomini_script.cpp:1]: Variable 'pp_cplan_hit' is used but never set",
             "[10:05:00][jomini_script.cpp:1]: Variable 'pp_cplan_hit' is used but never set",
             "[10:06:00][x.cpp:2]: Unknown effect in common/scripted_effects/pp_location_profiles.txt:12",
             "[10:07:00][x.cpp:3]: something else", ""]
    total, frame = ptr.error_summary(lines)
    assert total == 4
    assert frame["count"].to_list() == [2, 1]
    assert frame["message"][0] == "[jomini_script.cpp:1]: Variable 'pp_cplan_hit' is used but never set"


# --- synthetic saves -------------------------------------------------------------------------------------------------
CID = 7


def snap(name: str, date: str, levels: dict[tuple[int, str], float], *, owned: set[int] = frozenset({1, 2, 3, 4}),
         lvars: list[tuple[int, str, float]] = (), cons: list[dict] = (), cvars: dict[str, float] | None = None,
         food: list[tuple[int, float, float, float, float]] = (), access: dict[int, float] | None = None
         ) -> ptr.Snapshot:
    """A save: locations 1..5 (owned ones are CAS's, the rest OTH's), buildings by (location, type) -> level."""
    locs = pl.DataFrame({
        "location_id": [1, 2, 3, 4, 5], "slug": ["a", "b", "c", "d", "e"],
        "country_tag": ["CAS" if i in owned else "OTH" for i in (1, 2, 3, 4, 5)],
        "owner_country_id": [CID if i in owned else 9 for i in (1, 2, 3, 4, 5)],
        "owner": [CID if i in owned else 9 for i in (1, 2, 3, 4, 5)],
        "controller": [CID if i in owned else 9 for i in (1, 2, 3, 4, 5)],
        "total_population": [10.0, 20.0, 30.0, 40.0, 50.0],
        "market_access": [(access or {}).get(i, 1.0) for i in (1, 2, 3, 4, 5)],
    })
    bid = {key: n for n, key in enumerate(sorted(levels))}
    buildings = pl.DataFrame({
        "building_id": [bid[k] for k in sorted(levels)], "location_id": [k[0] for k in sorted(levels)],
        "building_type": [k[1] for k in sorted(levels)], "level": [float(levels[k]) for k in sorted(levels)],
    }, schema={"building_id": pl.Int64, "location_id": pl.Int64, "building_type": pl.Utf8, "level": pl.Float64})
    buildings = buildings.join(locs.select("location_id", "country_tag"), on="location_id", how="left")
    cons_rows = [{"construction_id": c["id"], "building_id": bid[(c["loc"], c["type"])], "country_id": CID,
                  "location_id": c["loc"], "progress": c.get("progress"), "total": c.get("total", 365.0),
                  "estate": c.get("estate"), "demand": "x_construction", "gold_spent": 10.0} for c in cons]
    tables = SimpleNamespace(
        locations=locs, buildings=buildings,
        countries_raw=pl.DataFrame({"country_id": [CID, 9], "tag": ["CAS", "OTH"]}),
        country_ai=pl.DataFrame({"country_id": [CID], "gold": [100.0], "income": [5.0], "expense": [4.0],
                                 "tax_base": [50.0]}),
        country_variables=pl.DataFrame({"country_id": [CID] * len(cvars or {}), "name": list(cvars or {}),
                                        "value": list((cvars or {}).values())},
                                       schema={"country_id": pl.Int64, "name": pl.Utf8, "value": pl.Float64}),
        location_variables=pl.DataFrame([{"location_id": a, "name": b, "value": c} for a, b, c in lvars],
                                        schema={"location_id": pl.Int64, "name": pl.Utf8, "value": pl.Float64}),
        constructions=pl.DataFrame(cons_rows, schema={
            "construction_id": pl.Int64, "building_id": pl.Int64, "country_id": pl.Int64, "location_id": pl.Int64,
            "progress": pl.Float64, "total": pl.Float64, "estate": pl.Utf8, "demand": pl.Utf8,
            "gold_spent": pl.Float64}),
        province_food=pl.DataFrame([{"province_id": p, "food_current": f, "max_food_value": mx,
                                     "base_food_consumption": c, "cached_food_change": ch} for p, f, mx, c, ch in food],
                                   schema={"province_id": pl.Int64, "food_current": pl.Float64,
                                           "max_food_value": pl.Float64, "base_food_consumption": pl.Float64,
                                           "cached_food_change": pl.Float64}),
        provinces_raw=pl.DataFrame({"province_id": [1, 2, 3], "capital_location_id": [1, 3, 5],
                                    "owner_country_id": [CID, 9, 9]}),
    )
    return ptr.Snapshot(name, date, ptr.parse_game_date(date), None, tables)


KINDS = {"granary": "food", "lumber_mill": "business", "carrier_inn": "logistics", "field_drainage": "improve"}


def test_levels_by_type_against_the_baseline_over_common_locations() -> None:
    start = {(1, "granary"): 1, (2, "lumber_mill"): 2, (4, "granary"): 1}
    run0 = snap("t1", "1337.4.1", start)
    run1 = snap("c10", "1347.4.1", {(1, "granary"): 3, (2, "lumber_mill"): 4, (3, "carrier_inn"): 1,
                                    (4, "granary"): 5})
    run2 = snap("c31", "1368.4.1", {(1, "granary"): 4}, owned={1, 2, 3})
    base1 = snap("a10", "1347.4.1", {(1, "granary"): 1, (2, "lumber_mill"): 3, (4, "granary"): 1})
    cmp = ptr.comparison([run0, run1, run2], [run0, base1], "CAS")
    assert cmp.run_last.name == "c10"  # the run's save at the baseline's last date
    assert cmp.locations == {1, 2, 3, 4}
    by_type = ptr.levels_by_type(cmp, "CAS", KINDS)
    rows = {r["building_type"]: r for r in by_type.iter_rows(named=True)}
    assert rows["granary"]["run_added"] == 6 and rows["granary"]["plan_extra"] == 6
    assert rows["lumber_mill"]["run_added"] == 2 and rows["lumber_mill"]["baseline_added"] == 1
    assert rows["lumber_mill"]["plan_extra"] == 1
    assert rows["carrier_inn"]["kind"] == "logistics"
    kinds = {r["kind"]: r["plan_extra"] for r in ptr.levels_by_kind(by_type).iter_rows(named=True)}
    assert kinds == {"food": 6, "logistics": 1, "business": 1}
    # without a baseline: first to last save, over the locations owned in both (4 was lost)
    plain = ptr.levels_by_type(ptr.comparison([run0, run1, run2], [], "CAS"), "CAS", KINDS)
    assert dict(plain.select("building_type", "run_added").iter_rows()) == {"granary": 3, "lumber_mill": -2}


def test_profile_states_paybacks_and_levels() -> None:
    lvars = [(1, "pp_lprof", 101), (2, "pp_lprof", 102), (3, "pp_lprof", 102),
             (1, "pp_lprof_r1_st", 101), (2, "pp_lprof_r1_st", 106), (3, "pp_lprof_r1_st", 106),
             (2, "pp_lprof_r2_st", 109), (5, "pp_lprof_r1_st", 101),  # 5 is not CAS's
             (1, "pp_lprof_r1_est", 115.5), (2, "pp_lprof_r1_est", 1099), (3, "pp_lprof_r1_est", 120)]
    s0 = snap("t1", "1337.4.1", {(1, "lumber_mill"): 1, (4, "granary"): 1}, lvars=lvars)
    s1 = snap("c10", "1347.4.1", {(1, "lumber_mill"): 4, (2, "lumber_mill"): 1, (4, "granary"): 2}, lvars=lvars)
    states = ptr.rule_states(s1, "CAS")
    got = {(r["slot"], r["rule"], r["state_name"]): r["locations"] for r in states.iter_rows(named=True)}
    assert got == {(1, 1, "started"): 1, (2, 1, "cannot be built here"): 2, (2, 2, "waiting for an earlier rule"): 1}
    pb = {(r["slot"], r["rule"]): r for r in ptr.rule_paybacks(s1, "CAS").iter_rows(named=True)}
    assert pb[(2, 1)]["no_profit"] == 1 and pb[(2, 1)]["shortest_years"] == pytest.approx(20.0)
    assert pb[(1, 1)]["shortest_years"] == pytest.approx(15.5)
    levels = ptr.profile_levels(ptr.comparison([s0, s1], [], "CAS"), "CAS", ptr.first_assignment([s0, s1]))
    rows = {r["slot"]: r for r in levels.iter_rows(named=True)}
    assert rows[0]["locations"] == 1 and rows[0]["run_added"] == 1  # location 4, no profile
    assert rows[1]["run_added"] == 3 and rows[1]["most_grown"] == "lumber_mill +3"
    assert rows[2]["locations"] == 2 and rows[2]["added_per_location"] == pytest.approx(0.5)


def test_stalled_constructions() -> None:
    lv = {(1, "granary"): 1, (2, "lumber_mill"): 1, (3, "carrier_inn"): 0, (3, "cookshop"): 1, (4, "tavern"): 1,
          (4, "grange"): 0}
    a = snap("c10", "1347.4.1", lv, cons=[
        {"id": 11, "loc": 1, "type": "granary"},                        # progress unset (0) in both, alone: stuck
        {"id": 12, "loc": 2, "type": "lumber_mill", "progress": 10.0},  # moved 30 of 365 days: held up
        {"id": 13, "loc": 3, "type": "carrier_inn"},                    # 0 in both, the cookshop beside it moved
        {"id": 14, "loc": 3, "type": "cookshop", "progress": 5.0},
        {"id": 15, "loc": 4, "type": "tavern", "progress": 300.0},      # finished between the saves
        {"id": 16, "loc": 4, "type": "grange"},                         # 0 in both, the tavern beside it finished
    ])
    b = snap("c11", "1348.4.1", lv, cons=[
        {"id": 11, "loc": 1, "type": "granary"},
        {"id": 12, "loc": 2, "type": "lumber_mill", "progress": 40.0},
        {"id": 13, "loc": 3, "type": "carrier_inn"},
        {"id": 14, "loc": 3, "type": "cookshop", "progress": 362.0},    # nearly full speed: not held up
        {"id": 16, "loc": 4, "type": "grange"},
    ])
    stalled = ptr.stalled_constructions([a, b], "CAS")
    assert dict(stalled.select("building_type", "reason").iter_rows()) == {
        "granary": ptr.REASON_STUCK, "lumber_mill": ptr.REASON_SLOW, "carrier_inn": ptr.REASON_QUEUED,
        "grange": ptr.REASON_QUEUED}
    counts = ptr.construction_counts([("run", a), ("run", b)], "CAS", stalled)
    assert counts.select("stuck", "queued", "held_up").rows() == [(0, 0, 0), (1, 2, 1)]


def test_food_stores_and_market_access() -> None:
    # province 1 (capital location 1, CAS): 2 months stored; province 2 (capital 3, CAS, though provinces_raw says
    # otherwise): 20 months of 22 room, gaining -> granary due; province 3 (capital 5): not CAS's
    food = [(1, 20.0, 100.0, 10.0, -1.0), (2, 200.0, 220.0, 10.0, 2.0), (3, 300.0, 300.0, 10.0, 1.0)]
    s = snap("c10", "1347.4.1", {(3, "carrier_inn"): 2}, food=food, access={1: 0.9, 2: 0.99, 3: 0.5})
    stores = ptr.food_stores([("run", s)], "CAS", ptr.Settings())
    row = stores.row(0, named=True)
    assert row["provinces"] == 2 and row["months_under 3"] == 1 and row["months_12-24"] == 1
    assert row["granary_due"] == 1 and row["grange_due"] == 0
    access = ptr.market_access([("run", s)], "CAS", KINDS, ptr.Settings()).row(0, named=True)
    assert access["below_line"] == 2 and access["logistics_levels"] == 2
    assert ptr.improvement_fill([("run", s)], "CAS", 90) is None


def test_build_report_writes_page_summary_and_csvs(tmp_path) -> None:
    lvars = [(1, "pp_lprof", 101), (1, "pp_lprof_r1_st", 101), (1, "pp_lprof_r1_est", 112)]
    cvars = {"pp_cplan_on": 0.00001, "pp_cplan_max": 110.0, "pp_cplan_started": 102.0, "pp_cplan_spent": 180.0}
    food = [(1, 120.0, 240.0, 10.0, 1.0)]
    run = [snap("t1", "1337.4.1", {(1, "granary"): 1}, lvars=lvars, cvars=cvars, food=food),
           snap("c10", "1347.4.1", {(1, "granary"): 3, (2, "lumber_mill"): 1}, lvars=lvars, cvars=cvars, food=food,
                cons=[{"id": 1, "loc": 2, "type": "lumber_mill"}])]
    base = [run[0], snap("a10", "1347.4.1", {(1, "granary"): 1}, food=food)]
    page = ptr.build_report(run[::-1], tmp_path, baseline=base, debug_lines=DEBUG_LOG.splitlines(),
                            debug_source="debug.log", error_lines=["[1:00:00]: pp_lprof broke"],
                            error_source="error.log", kinds=KINDS, log=lambda _: None)
    text = page.read_text(encoding="utf-8")
    for heading in ("Run overview", "What the plan built", "Location profiles", "Global rule groups",
                    "Constructions in progress", "Errors"):
        assert heading in text
    assert "prefers-color-scheme: dark" in text and "builds_per_year.png" in text
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Plan extra levels: +3" in summary
    for name in ("overview.csv", "builds_by_year.csv", "builds_by_building.csv", "passes_by_year.csv",
                 "levels_by_type.csv", "profile_rule_states.csv", "food_stores.csv", "market_access.csv",
                 "constructions.csv", "errors.csv", "speed_log.csv", "builds_per_year.png", "builds_per_year_dark.png"):
        assert (tmp_path / name).is_file(), name
    by_year = pl.read_csv(tmp_path / "builds_by_year.csv")
    assert by_year["total"].sum() == 3  # the latest timeline: two June lines replayed by the load
    assert pl.read_csv(tmp_path / "errors.csv")["count"].to_list() == [1]


def test_parse_the_game_format_of_2026_11_09() -> None:
    """In game: static markers, then debug_log_scopes lines for the building type and the location; passes without
    numbers; no date lines, so months count from the first save by pass lines."""
    from prosper_or_perish_constructor import plan_test_report as r

    lines = [
        "[02:10:15][console.cpp:1174]: Running console command: tick_day 365",
        "[02:10:15][jomini_effect_impl.cpp:479]: common/scripted_effects/pp_construction_plan.txt:377: PPCPLAN;B;profile",
        "[02:10:15][jomini_effect_impl.cpp:2666]: Building Type \x27Lumber Mill\x27 (120)",
        "[02:10:15][jomini_effect_impl.cpp:2666]: Location \x27Valladolid\x27 (2584)",
        "[02:10:15][jomini_effect_impl.cpp:479]: common/scripted_effects/pp_construction_plan.txt:377: PPCPLAN;B;food",
        "[02:10:15][jomini_effect_impl.cpp:2666]: Building Type \x27Granary\x27 (350)",
        "[02:10:15][jomini_effect_impl.cpp:2666]: Location \x27Burgos\x27 (2500)",
        "[02:10:15][jomini_effect_impl.cpp:479]: common/scripted_effects/pp_construction_plan.txt:125: PPCPLAN;P",
        "[02:10:16][jomini_effect_impl.cpp:479]: common/scripted_effects/pp_construction_plan.txt:125: PPCPLAN;P",
    ]
    log = r.parse_debug_log(lines, start_year=r.year_fraction(1337, 4, 1))
    assert log.builds["building"].to_list() == ["Lumber Mill", "Granary"]
    assert log.builds["location_id"].to_list() == [2584, 2500]
    assert log.builds["group"].to_list() == ["profile", "food"]
    assert log.builds["date"].to_list() == ["1337.5.1", "1337.5.1"]
    assert log.passes["started"].to_list() == [2.0, 0.0]
    assert log.passes["date"].to_list() == ["1337.5.1", "1337.6.1"]
    assert log.dates.height == 2 and not log.unparsed


def test_errors_from_console_run_files_stand_apart() -> None:
    """The console description pass of a run file logs unset-variable errors for the profile buttons (in game
    2026-11-09); the report counts them apart from the game run."""
    from prosper_or_perish_constructor import plan_test_report as r

    lines = [
        "[02:22:20][jomini_script_system.cpp:256]: Script system error!",
        "  Error: Failed to fetch variable for \x27pp_lprof_k\x27 due to not being set",
        "  Script location: common/script_values/pp_location_profiles_generated.txt:84",
        "run/pp_plan_ai_setup.txt:31",
        "[02:23:00][jomini_script_system.cpp:256]: Script system error!",
        "  Error: Event target link \x27var:pp_cplan_x\x27 returned an unset scope",
        "  Script location: common/scripted_effects/pp_construction_plan.txt:99",
        "[02:23:01][other.cpp:1]: something else entirely",
    ]
    total, frame = r.error_summary(lines)
    assert total == 3
    rows = {row["source"]: row for row in frame.iter_rows(named=True)}
    assert rows["console run file"]["count"] == 1 and "pp_lprof_k" in rows["console run file"]["message"]
    assert rows["game"]["count"] == 1 and rows["game"]["where"].endswith("pp_construction_plan.txt:99")
