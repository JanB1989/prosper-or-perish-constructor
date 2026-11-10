"""Construction Plan, script time (Jan 2026-11-10: "The monthly pass takes 0.4 seconds. That is substantially too long
... it needs to be built so that it doesn't use unnecessary script time"; docs/player_construction_manager.md "Script
time").

Measured before: 0.32-0.39 s a pass in a 330-location country, 0.20 s of it the business pick (every free site against
every business type, every month). The cost rules the rework relies on, each checked by the shape of the script:

* the pass itself walks nothing; a rule group walks only at a LOOK, in its own months, and between its looks it only
  goes back to the one place it saves for (no walk);
* only the business refresh scores business types per location, for a fixed few sites a pass, and every location's turn
  comes exactly once a cycle;
* a look of the business group ranks stored picks (no scoring) and works out afresh only the few it tries;
* nothing costly is worked out twice (the store a year from now, the farm lines' returns);
* the market limit counts afresh only in its months.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_country as cpc
from prosper_or_perish_constructor.script_eval import ScriptEval

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
EFFECTS = COMMON / "scripted_effects/pp_construction_plan.txt"
TRIGGERS = COMMON / "scripted_triggers/pp_construction_plan.txt"
PROFILE_EFFECTS = COMMON / "scripted_effects/pp_location_profiles.txt"
WALK = re.compile(r"\b(?:every|ordered|random|any)_(?!in_list)\w+ = \{")  # a walk over the game's objects (not a kept list)
LOCATIONS, TYPES = 330, 224  # the plan test world, and the business types the plan knows


class PlanEval(ScriptEval):
    def single(self, key, op, v, safe, ctx):
        if key == "has_variable":
            return f"var:{v}" in ctx.get("game", {})
        return super().single(key, op, v, safe, ctx)


@lru_cache(maxsize=1)
def _config() -> cp.Config:
    return cp.load_config(PROJECT)


def _read(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def _months(name: str) -> tuple[int, ...]:
    return dict(_config().look_months)[name]


# ---- who looks when ----


def test_look_months_are_configured_and_generated() -> None:
    config = _config()
    assert [name for name, _ in config.look_months] == list(cp.LOOKS)
    triggers = _read(MOD / cp.TRIGGERS)
    for name, months in config.look_months:
        assert months and all(1 <= month <= 12 for month in months), name
        body = _effect(triggers, f"pp_cplan_looks_{name}").strip()
        assert body == "OR = { " + " ".join(f"current_month = {month}" for month in months) + " }", name
    # the walks over the whole country are spread over the year: no month has more than two of them
    walks = ("food", "logistics", "improve", "profiles", "upgrades", "public", "ranks", "rights")
    for month in range(1, 13):
        looking = [name for name in walks if month in _months(name)]
        assert len(looking) <= 2, (month, looking)
    # the three rules of Towns and Buildings never share a month (one rule a look)
    rules = [set(_months(name)) for name in ("upgrades", "public", "ranks")]
    assert not (rules[0] & rules[1]) and not (rules[0] & rules[2]) and not (rules[1] & rules[2])


def test_the_pass_itself_walks_nothing() -> None:
    """What every pass does besides the groups: the purses (arithmetic) and the bookkeeping. No loop over locations,
    provinces or buildings; the market limit's counts go only in their months."""
    effects = _read(EFFECTS)
    generated = _read(MOD / cp.EFFECTS)
    for name in ("pp_cplan_run", "pp_cplan_pass_begin", "pp_cplan_pass_end", "pp_cplan_group_start",
                 "pp_cplan_group_target", "pp_cplan_save_clear"):
        assert not WALK.search(_effect(effects, name)), name
    for name in ("pp_cplan_purses_fill", "pp_cplan_purses_hand_on", "pp_cplan_pass_reset", "pp_cplan_history_push"):
        assert not WALK.search(_effect(generated, name)), name
    begin = _effect(effects, "pp_cplan_pass_begin")
    assert "limit = { pp_cplan_looks_market_count = yes }\n\t\tpp_cplan_markets_clear = yes" in begin
    assert begin.count("pp_cplan_markets_clear") == 1 and "pp_cplan_markets_clear" not in _effect(effects, "pp_cplan_pass_end")
    # the urban rights (every ticked right against the country's locations) only in their months
    run = _effect(effects, "pp_cplan_run")
    assert "limit = { pp_cplan_looks_rights = yes }\n\t\tpp_cplan_country_rights = yes" in run
    assert run.count("pp_cplan_country_rights") == 1


def test_a_group_walks_only_at_its_look() -> None:
    """Every rule group: in a pass in which it does not look it walks nothing; its look sits behind its months."""
    effects = _read(EFFECTS)
    for group, why, target in (("food", 101, "pp_cplan_food_target"), ("logistics", 102, "pp_cplan_logistics_target"),
                               ("improve", 106, "pp_cplan_improve_target")):
        body = _effect(effects, f"pp_cplan_group_{group}")
        assert not WALK.search(body), group
        assert (f"limit = {{ pp_cplan_looks_{group} = yes }}\n\t\t\tpp_cplan_look_{group} = yes\n\t\t}}\n"
                f"\t\telse = {{\n\t\t\tpp_cplan_group_target = {{ why = {why} do = {target} }}") in body, group
        assert body.count(f"pp_cplan_look_{group} = yes") == 1
        # the look resets the group's numbers and what it saved for, then walks
        look = _effect(effects, f"pp_cplan_look_{group}")
        assert look.lstrip().startswith(f"pp_cplan_group_start = {{ why = {why} }}") and WALK.search(look), group
        # what it goes back to between two looks is one place: no walk over the country
        assert "owned_location" not in _effect(effects, target) and "every_province" not in _effect(effects, target), group
    # the Locations group
    run = _effect(_read(PROFILE_EFFECTS), "pp_lprof_run")
    assert not WALK.search(run.replace("pp_lprof_has_locations", ""))
    assert ("limit = { pp_cplan_looks_profiles = yes }\n\t\t\tpp_lprof_look = yes\n\t\t}\n"
            "\t\telse = {\n\t\t\tpp_cplan_group_target = { why = 105 do = pp_lprof_location_turn }") in run
    turn = _effect(_read(PROFILE_EFFECTS), "pp_lprof_location_turn")
    assert not WALK.search(turn)
    # the lists are cleaned at the look only (they walk the owned locations)
    assert "pp_lprof_cleanup" not in run and "pp_lprof_cleanup = yes" in _effect(_read(PROFILE_EFFECTS), "pp_lprof_look")
    # Towns and Buildings: one rule a look, each behind its own months; no look at all while it saves
    country = _read(MOD / cpc.EFFECTS)
    group = _effect(country, "pp_cplan_group_country")
    assert not WALK.search(group)
    saving = group.index("limit = { pp_cplan_saving = { why = 107 } }")
    assert saving < group.index("pp_cplan_group_target = { why = 107 do = pp_cplan_country_target }") < group.index("else_if = {")
    for rule, effect in (("upgrades", "pp_cplan_country_upgrades"), ("public", "pp_cplan_country_buildings"),
                         ("ranks", "pp_cplan_country_ranks")):
        assert f"limit = {{ pp_cplan_looks_{rule} = yes }}\n\t\t\t\t{effect} = yes" in group, rule
        assert group.count(f"{effect} = yes") == 1
    assert not WALK.search(_effect(country, "pp_cplan_country_target"))


def test_what_a_group_saves_for_is_built_without_a_look() -> None:
    """Between its looks a group does one thing: once its purse can pay for what it saves for, it goes back to that
    one place and runs its rule there (every guard of a look). It lets go of what it saved for first, so the
    construction pays like any level and is saved for again if the gold falls short after all."""
    effects = _read(EFFECTS)
    target = _effect(effects, "pp_cplan_group_target")
    limit = target[target.index("limit = {"):target.index("var:pp_cplan_save_loc_$why$ = {")]
    for line in ("has_variable = pp_cplan_save_cost_$why$", "has_variable = pp_cplan_save_loc_$why$",
                 "pp_cplan_purse_n_$why$ >= pp_cplan_save_cost_n_$why$"):
        assert line in limit, line
    assert (target.index("save_scope_as = pp_cplan_target") < target.index("pp_cplan_save_clear = { why = $why$ }")
            < target.index("$do$ = yes"))
    assert "limit = { owner ?= scope:pp_cplan_country }\n\t\t\t\t$do$ = yes" in target
    # the reason travels with what is saved for (the ledger's line of a construction between two looks)
    note = _effect(effects, "pp_cplan_note_wait")
    for name in ("rv", "rs"):
        assert f"set_variable = {{ name = pp_cplan_save_{name}_$why$ value = scope:pp_cplan_{name} }}" in note
        assert f"value = var:pp_cplan_save_{name}_$why$" in target
        assert f"remove_variable = pp_cplan_save_{name}_$why$" in _effect(effects, "pp_cplan_save_clear")
    assert set(cp.SAVE_VARS) == {"cost", "loc", "type", "rank", "rv", "rs"}
    # each group's place runs its own rule again: the province's food rule, the location's logistics or improvement
    # rule if it still holds, the site's business pick, the location's profile rules and marks
    assert _effect(effects, "pp_cplan_food_target").strip() == "province ?= { pp_cplan_food_province = yes }"
    for group, wanted in (("logistics", "pp_cplan_logistics_wanted = yes"),
                          ("improve", "location_population_percentage >= scope:pp_cplan_country.pp_cplan_improve_line")):
        body = _effect(effects, f"pp_cplan_{group}_target")
        assert f"pp_cplan_{group}_ok = yes" in body and wanted in body and f"pp_cplan_{group}_here = yes" in body
    here = _effect(effects, "pp_cplan_business_here")
    assert here.index("pp_cplan_business_site = yes") < here.index("pp_cplan_business_pick = yes")
    # what a group that looked hands on, and what the window counts, is the look's: not this one construction's
    assert "pp_cplan_now_$why$" not in target and "pp_cplan_stats_reset" not in target


# ---- the business group ----


def test_only_the_refresh_scores_business_types_and_only_for_a_few_sites() -> None:
    """pp_cplan_business_pick is the one effect that holds a block per business type. It runs for the sites whose turn
    it is (the refresh) and for the few picks a look tries; no other loop over owned locations reaches it."""
    effects = _read(EFFECTS)
    generated = _read(MOD / cp.EFFECTS)
    pick = _effect(generated, "pp_cplan_business_pick")
    assert pick.count("can_build_building = building_type:") >= 200
    callers = [name for name in re.findall(r"^(\w+) = \{", effects, re.MULTILINE)
               if "pp_cplan_business_pick = yes" in _effect(effects, name)]
    assert sorted(callers) == ["pp_cplan_business_here", "pp_cplan_business_turn_here"]  # the refresh, through its walk over the blocks
    refresh = _effect(effects, "pp_cplan_business_refresh")
    # no walk over the country in a normal pass (in game 2026-11-10: that walk, two comparisons a location, was 11 of
    # the refresh's 21 ms): the locations are numbered, and put on the list of their block of the order, only in the
    # months of the country's can-build check; the pass reads the lists of the blocks its numbers fall in
    every_pass = refresh[refresh.index("save_temporary_scope_value_as = { name = pp_cplan_from"):]
    assert not WALK.findall(every_pass) and "pp_cplan_business_walk = yes" in every_pass
    seldom = refresh[:refresh.index("save_temporary_scope_value_as = { name = pp_cplan_from")]
    assert len(WALK.findall(seldom)) == 2 and "pp_cplan_business_block = yes" in seldom
    assert seldom.index("pp_cplan_looks_business_types = yes") < seldom.index("every_owned_location = {")
    generated_effects = _read(MOD / cp.EFFECTS)
    walk = _effect(generated_effects, "pp_cplan_business_walk")
    assert walk.count("every_in_list = {") == cp.BUSINESS_BLOCKS and not WALK.findall(walk)
    assert walk.count("limit = { pp_cplan_business_turn = yes owner ?= scope:pp_cplan_country }") == cp.BUSINESS_BLOCKS
    assert walk.count("pp_cplan_business_turn_here = yes") == cp.BUSINESS_BLOCKS
    block = _effect(generated_effects, "pp_cplan_business_block")
    for n in range(1, cp.BUSINESS_BLOCKS + 1):
        assert f"variable = pp_cplan_bzb_{n}\n" in walk and f"name = pp_cplan_bzb_{n} target = scope:pp_cplan_numbered" in block
    assert "limit = { pp_cplan_business_site = yes }" in _effect(effects, "pp_cplan_business_turn_here")
    # the country's part of the can-build check: not every pass
    assert "pp_cplan_looks_business_types = yes" in refresh[:refresh.index("pp_cplan_business_types = yes")]
    # the look: the stored picks ranked (no scoring in the limit or the order), the best few tried
    look = _effect(effects, "pp_cplan_look_business")
    ordered = look[look.index("ordered_owned_location = {"):]
    assert "has_variable = pp_cplan_bz_pick" in ordered and "max = pp_cplan_bz_tries" in ordered
    assert "pp_cplan_business_pick" not in look and "pp_cplan_business_site" not in look
    order = "".join(_effect(_read(COMMON / "script_values/pp_construction_plan.txt"), name)
                    for name in ("pp_cplan_bz_order", "pp_cplan_bz_years", "pp_cplan_bz_short", "pp_cplan_bz_save_years"))
    assert "pp_cplan_bz_roi_" not in order.replace("pp_cplan_bz_roi_n", "") and "can_build" not in order
    # a look while it saves only in its months; else it goes for what it saves for
    group = _effect(effects, "pp_cplan_group_business")
    assert not WALK.search(group)
    assert ("NOT = { pp_cplan_saving = { why = 103 } }\n\t\t\t\t\tpp_cplan_looks_business = yes" in group
            and "pp_cplan_group_target = { why = 103 do = pp_cplan_business_here }" in group)
    # once the group saves, the look's remaining tries only count their stored cost (no scoring)
    here = _effect(effects, "pp_cplan_business_here")
    assert here.index("limit = { pp_cplan_saving = { why = 103 } }") < here.index("pp_cplan_business_pick = yes")
    assert "else_if = {\n\t\tlimit = { pp_cplan_business_site = yes }" in here


def _window(numbered: int) -> float:
    return PlanEval(MOD).value("pp_cplan_bz_window", {"game": {"var:pp_cplan_seq_n": 100 + numbered}})


def test_every_locations_turn_comes_exactly_once_a_cycle() -> None:
    """The slices: every owned location has a number in the order the plan first saw it; a pass takes the numbers
    after the country's place in that order, a window's worth, then moves the place on and starts again after the
    last number. Simulated here as the script does it."""
    config = _config()
    assert _window(100) == config.business_sites == 16  # a small country: the fixed few
    assert _window(LOCATIONS) == pytest.approx(LOCATIONS / cp.business_refresh_passes(config))  # 330 locations
    # a large one: seen within the cycle (the refresh rests in the food look's months: the passes that are left)
    assert cp.business_refresh_passes(config) == config.business_cycle_months * 8 / 12
    assert _window(1200) == pytest.approx(1200 / cp.business_refresh_passes(config))
    group = _effect(_read(EFFECTS), "pp_cplan_group_business")
    assert "limit = { NOT = { pp_cplan_looks_food = yes } }\n\t\t\tpp_cplan_business_refresh = yes" in group
    assert _window(0) == config.business_sites
    turn = _effect(_read(TRIGGERS), "pp_cplan_business_turn")
    assert turn.split() == "var:pp_cplan_seq > scope:pp_cplan_from var:pp_cplan_seq <= scope:pp_cplan_to".split()
    refresh = _effect(_read(EFFECTS), "pp_cplan_business_refresh")
    for line in ("name = pp_cplan_from value = var:pp_cplan_cursor }",
                 "name = pp_cplan_to value = { value = var:pp_cplan_cursor add = pp_cplan_bz_window } }",
                 "set_variable = { name = pp_cplan_cursor value = scope:pp_cplan_to }",
                 "limit = { var:pp_cplan_cursor >= var:pp_cplan_seq_n }\n\t\tset_variable = { name = pp_cplan_cursor value = 100 }",
                 "limit = { NOT = { has_variable = pp_cplan_seq } }",
                 "set_variable = { name = pp_cplan_seq value = scope:pp_cplan_country.var:pp_cplan_seq_n }"):
        assert line in refresh, line
    for locations in (1, 15, 16, 17, LOCATIONS, 1200):
        numbers = [100 + n for n in range(1, locations + 1)]  # pp_cplan_seq, + 100 like the counter
        counter, cursor, turns, passes = 100 + locations, 100.0, {n: 0 for n in numbers}, 0
        while True:
            window = max(config.business_sites, (counter - 100) / cp.business_refresh_passes(config))
            low, high = cursor, cursor + window
            for n in numbers:
                if low < n <= high:
                    turns[n] += 1
            cursor = high
            passes += 1
            if cursor >= counter:
                break
        assert set(turns.values()) == {1}, locations  # exactly once a cycle
        assert passes <= max(config.business_cycle_months, 1) + 1, (locations, passes)
        # the sites a pass scores never exceed the window (+ 1 for a fractional window's edge)
        assert max(sum(1 for n in numbers if 100 + k * window < n <= 100 + (k + 1) * window) for k in range(passes)) <= window + 1


def test_cost_model_a_pass_scores_a_tenth_or_less() -> None:
    """Location-level business type checks, the measured two thirds of the old pass: before, every pass scored every
    owned location against every type; now a pass scores the window's sites, and a look the few picks it tries."""
    config = _config()
    before = LOCATIONS * TYPES
    refresh = _window(LOCATIONS) * TYPES
    worst = refresh + config.business_tries * TYPES  # a pass with a look that tries every pick
    assert refresh <= before / cp.business_refresh_passes(config) + 1 and worst <= before / 10, (before, refresh, worst)
    # ... and it no longer grows with locations x types: ten times the locations, not ten times the sites
    assert _window(10 * LOCATIONS) * TYPES <= (10 * LOCATIONS * TYPES) / cp.business_refresh_passes(config) + 1
    # walks over all owned locations a year (each a cheap limit per location; the ticked public buildings walk once
    # each): before every pass, now only in the look months
    ticked = len(cpc.load_config(PROJECT).public_buildings)
    before_walks = 12 * (2 + 1 + 1 + ticked + 1 + 2)  # business x2, logistics, improvements, public, upgrades, ranks
    after_walks = (12 + 2 * 12  # the business turn every pass; a look's two cheap walks, every month at most
                   + len(_months("logistics")) + len(_months("improve")) + ticked * len(_months("public"))
                   + len(_months("upgrades")) + 2 * len(_months("ranks")))
    assert after_walks <= before_walks / 4, (before_walks, after_walks)


# ---- nothing costly twice ----


def test_costly_values_are_worked_out_once() -> None:
    effects = _read(EFFECTS)
    # the store a year from now (it walks the province's locations several times): once a province at a look, kept on
    # the province for the order and the rule
    look = _effect(effects, "pp_cplan_look_food")
    assert look.count("pp_cplan_food_in_a_year") == 1
    order = _effect(_read(COMMON / "script_values/pp_construction_plan.txt"), "pp_cplan_food_order")
    assert "pp_cplan_food_in_a_year" not in order and "var:pp_cplan_fy" in order
    province = _effect(effects, "pp_cplan_food_province")
    assert province.count("pp_cplan_food_in_a_year") == 1
    assert province.index("limit = { has_variable = pp_cplan_fy }") < province.index("value = pp_cplan_food_in_a_year")
    assert "remove_variable = pp_cplan_fy" in province
    # a farm site's best line (every farm line's can-build check): once, for the order; not in the limit as well
    farms = province[province.index("ordered_location_in_province = {"):province.index("pp_cplan_try_farm_here = yes")]
    assert farms.count("pp_cplan_farm_best_roi") == 1 and "order_by = pp_cplan_farm_best_roi" in farms
    # the window's counts are not taken twice when a group goes back to one place between its looks
    for name in ("provinces", "famine", "hungry", "granary", "grange"):
        line = province[:province.index(f"name = pp_cplan_ds_food_{name} add = 1")]
        assert "has_variable = pp_cplan_now_101" in line[line.rindex("limit = {"):], name
    assert "has_variable = pp_cplan_now_105" in _effect(_read(PROFILE_EFFECTS), "pp_lprof_finish")


# ---- for the profiler ----


def test_every_group_can_be_run_alone_from_the_console() -> None:
    """effect c:TAG = { pp_cplan_test_<name> = yes }: a pass with only that look, whatever the month."""
    effects = _read(EFFECTS)
    looks = {"food": "pp_cplan_look_food", "logistics": "pp_cplan_look_logistics", "improve": "pp_cplan_look_improve",
             "profiles": "pp_lprof_look", "business_refresh": "pp_cplan_business_refresh",
             "business_look": "pp_cplan_look_business", "country": "pp_cplan_look_country_all",
             "rights": "pp_cplan_country_rights"}
    defined = set()
    for path in sorted(COMMON.glob("scripted_effects/pp_*.txt")):
        defined |= set(re.findall(r"^(\w+) = \{", _read(path), re.MULTILINE))
    for name, look in looks.items():
        body = _effect(effects, f"pp_cplan_test_{name}").split()
        assert body == ["pp_cplan_pass_begin", "=", "yes", look, "=", "yes", "pp_cplan_pass_end", "=", "yes"], name
        assert look in defined, look
    assert _effect(effects, "pp_cplan_test_empty").split() == ["pp_cplan_pass_begin", "=", "yes", "pp_cplan_pass_end", "=", "yes"]
    # the test mode still writes its line per pass
    assert "limit = { has_variable = pp_cplan_ai_test }\n\t\tdebug_log = PP_CPLAN_TLOG_PASS" in _effect(effects, "pp_cplan_pass_end")
