"""The plan engine of the Construction Plan's Locations group (src/prosper_or_perish_constructor/location_profiles.py,
mod/pp/.../pp_location_profiles*). Location Profiles and the building marks are gone (2026-11-19); a location's plans
(town rights pp_plan_<plan>, town_plans.py) are the one per-location decision."""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import location_profiles as lpf
from prosper_or_perish_constructor import town_plans
from prosper_or_perish_constructor.script_eval import ScriptEval
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
PLAN_EFFECTS = COMMON / "scripted_effects/pp_construction_plan.txt"
PLAN_TRIGGERS = COMMON / "scripted_triggers/pp_construction_plan.txt"
PLAN_VALUES = COMMON / "script_values/pp_construction_plan.txt"
OWN_FILES = (MOD / lpf.EFFECTS, MOD / lpf.HAND_EFFECTS, MOD / lpf.VALUES, MOD / lpf.TRIGGERS)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _code(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", _read(path))


def _defined(folder: str) -> set[str]:
    keys: set[str] = set()
    for path in (COMMON / folder).glob("*.txt"):
        keys |= set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", _read(path), re.MULTILINE))
    return keys


def _block(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, f"{name} missing"
    return match.group(1)


def _build():
    return lpf.build(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))


def test_built_mod_is_in_step() -> None:
    assert lpf.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False) == 0, "run ppc finalize"
    result, _ = _build()
    keys = list(result.targets)
    assert {"lumber", "furniture", town_plans.TRADE_TARGET, town_plans.FOOD_TARGET} <= set(keys)
    assert len(keys) == len(set(keys))
    # the targets a plan runs: the goods, the food plan's and the trade plan's; no other category, no market access
    assert list(result.categories) == [town_plans.TRADE_TARGET] == list(lpf.CATEGORIES)
    assert "logistics" not in keys and "naval_category" not in keys
    # a standing producer grows highest tier first
    assert [c.name for c in result.targets["furniture"]][:2] == ["furniture_mill", "furniture_manufactory"]
    assert result.targets[town_plans.TRADE_TARGET]


def test_category_lists_hold_only_player_buildings() -> None:
    result, _ = _build()
    database = cp._database(MOD, vanilla_root(ROOT, PROJECT), cp.BUILDING_TYPES)
    for category, names in result.categories.items():
        for name in names:
            keys, body = database[name]
            assert keys["category"] == category, name
            assert keys.get("is_foreign") != "yes" and keys.get("is_special") != "yes", name
            assert "estate" not in keys and "international_organization_link" not in keys, name
            assert not re.search(r"\ballow\s*=\s*\{\s*always\s*=\s*no\s*\}", body), name
    assert "marketplace" in result.categories["trade_category"]
    assert "trade_office" not in result.categories["trade_category"]  # a foreign building


def test_every_candidate_has_cost_data_and_guards() -> None:
    """Each building a target can start has the plan's cost data (price factor, efficiency term) and the market check
    of its construction goods; every start or expand of the hand-written effects runs the game's can-build check."""
    effects = _read(MOD / lpf.EFFECTS)
    plan_triggers = _read(MOD / cp.TRIGGERS)
    plan_values = _read(MOD / cp.VALUES) + _read(PLAN_VALUES)
    known = cp.defined_buildings(MOD, vanilla_root(ROOT, PROJECT))
    # each effect gets exactly its own arguments (a call with an argument the body never uses does nothing in game):
    # expand = cost data, workers, lc; upgrade = old, cost data, estimate; start = cost data, workers, estimate
    cost = r"type = (?P<name>\w+) demand = (?P<demand>\w+) cat = (?P<cat>\w+) ipl = [0-9.]+"
    work = r"pt = (?P<pt>\w+) sz = (?P<sz>[0-9.]+)"
    estimate = r"est = (?P<est>\w+) hasest = (?P<hasest>yes|no)"
    shapes = {
        "expand": rf"pp_lprof_expand = \{{ {cost} {work} lc = (?P<lc>yes|no) \}}",
        "upgrade": rf"pp_lprof_upgrade = \{{ old = \w+ {cost} {estimate} \}}",
        "start": rf"pp_lprof_start = \{{ {cost} {work} {estimate} \}}",
    }
    calls = [(kind, match.groupdict()) for kind, shape in shapes.items() for match in re.finditer(shape, effects)]
    assert len(calls) > 300
    assert len(calls) == len(re.findall(r"pp_lprof_(?:expand|start|upgrade) = \{", effects)), "every call matched"
    database = cp._database(MOD, vanilla_root(ROOT, PROJECT), cp.BUILDING_TYPES)
    staff = cp.staffing(database, cp.script_value_numbers(MOD, vanilla_root(ROOT, PROJECT)))
    for kind, call in calls:
        name, demand, category = call["name"], call["demand"], call["cat"]
        assert name in known, name
        if kind == "expand":
            # the loss check reads buildings that make goods
            assert (call["lc"] == "yes") == ("unique_production_methods" in re.sub(r"#[^\n]*", "", database[name][1])), name
        else:
            # a level estimate where the Businesses rule has one
            if call["hasest"] == "yes":
                assert call["est"] == f"pp_cplan_bz_est_{name}" and f"\n{call['est']} = {{" in plan_values, name
            else:
                assert call["est"] == "0", name
        if kind != "upgrade":
            # the workers one level needs (Jan 2026-11-09: no building where nobody can work in it)
            assert (call["pt"], float(call["sz"])) == staff.get(name, ("peasants", 0.0)), name
        assert f"pp_cplan_goods_here_{demand} = {{" in plan_triggers, demand
        assert f"pp_cplan_cd_{demand} = {{" in plan_values, demand
        assert f"pp_cplan_eff_{category} = {{" in plan_values, category
    hand = _code(MOD / lpf.HAND_EFFECTS)
    for name in ("pp_lprof_expand", "pp_lprof_start"):
        body = _block(hand, name)
        assert "location_and_owner_can_build = { building_type = $type$ }" in body, name
        assert "pp_cplan_goods_here_$demand$ = yes" in body, name
        assert "pp_cplan_staff = { type = $pt$ size = $sz$ }" in body, name
    # every construction goes through the plan's budget check and its construct (ledger, never twice while queued)
    build = _block(hand, "pp_lprof_build")
    assert f"pp_cplan_construct_scoped = {{ why = {lpf.WHY_PROFILE} }}" in build
    assert "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_wait } }\n\t\tpp_lprof_fail = { r = 107 }" in build
    assert "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_mlim } }\n\t\tpp_lprof_fail = { r = 106 }" in build
    assert build.index("has_variable = pp_cplan_wait") < build.index("has_variable = pp_cplan_mlim")
    assert "construct_building" not in hand
    assert "pp_lprof_payback100 > scope:pp_lprof_pb" in _block(hand, "pp_lprof_expand")


def test_targets_wait_for_their_constructions() -> None:
    """A plan never starts a second level while any building of its target has one under construction here."""
    effects = _read(MOD / lpf.EFFECTS)
    result, _ = _build()
    for key, candidates in result.targets.items():
        if not candidates:
            continue
        body = _block(effects, f"pp_lprof_t_{key}")
        first = body.split("\n\t}")[0]
        assert "building_levels_under_construction > 0" in first and "value = 103" in first, key
        for candidate in candidates:
            assert f"building_type = building_type:{candidate.name}" in first, (key, candidate.name)


def test_references_exist() -> None:
    effects = _defined("scripted_effects")
    triggers = _defined("scripted_triggers")
    values = _defined("script_values")
    text = "".join(_code(path) for path in OWN_FILES if path != MOD / lpf.VALUES) + _code(PLAN_EFFECTS) + _code(PLAN_TRIGGERS)
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) = yes\b", text)):
        assert name in effects | triggers, f"{name} missing"
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) = \{ [a-z]+ = ", text)):
        assert name in effects | triggers, f"{name} missing"
    for name in set(re.findall(r"\b(?:value|add|subtract|multiply|divide) = (pp_[a-z0-9_]+)(?![\w$])", text)):
        assert name in values, f"script value {name} missing"
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) [<>]=? ", text)):
        assert name in values, f"script value {name} missing"
    own_values = _code(MOD / lpf.VALUES)
    for name in set(re.findall(r"(?<![\w:.$])(pp_[a-z0-9_]+) = yes\b", own_values)):
        assert name in triggers, f"trigger {name} missing"


def test_profiles_and_building_marks_are_gone() -> None:
    """2026-11-19, Jan: profiles and the old location marks go; the town-right plan is the only per-location
    decision. No profile slot, rule, edit buffer, global-rule switch or building mark is left in the mod's script."""
    files = [path for folder in ("scripted_effects", "scripted_triggers", "script_values", "scripted_guis", "on_action")
             for path in (COMMON / folder).glob("*.txt")]
    gone = re.compile(r"pp_lprof_(?:x[flicg]\b|rule\b|r\d|e_|s_|locs\b|examples|declare|has_good|has_category|food_target"
                      r"|try\b|t_logistics\b|editor)|pp_lplan_(?:b\b|bflip|b_|bst\b|locs\b|maps|quick|planned_n|clear_all"
                      r"|drop_categories|n\b|g_)")
    for path in files:
        found = gone.findall(_code(path))
        assert not found, (path.name, sorted(set(found))[:5])
    for name in ("in_game/gui/pp_location_profiles.gui", "in_game/gui/context_menu.gui",
                 "in_game/common/scripted_guis/pp_location_profiles.txt",
                 "main_menu/gfx/interface/component_tiles/pp_profile_symbols.dds"):
        assert not (MOD / name).exists(), name
    run = _block(_code(PLAN_EFFECTS), "pp_cplan_run")
    for scope in ("pp_slot", "pp_field", "pp_col"):
        assert f"save_scope_as = {scope}" not in run, scope


def test_global_rules_keep_building_where_plans_are() -> None:
    """Plans are additive like the old marks: no global rule group stands back in a location with a plan. The
    Locations group takes its part of the budget only while a location holds a plan, and the first plan that starts a
    construction ends the location's month."""
    plan = _code(PLAN_TRIGGERS) + _code(PLAN_EFFECTS) + _code(MOD / cp.EFFECTS)
    for folder in ("scripted_triggers", "scripted_effects"):
        plan += "".join(_code(path) for path in sorted((COMMON / folder).glob("pp_construction_plan_country*.txt")))
    assert "pp_lprof" not in plan.replace("pp_lprof_run", "").replace("pp_lprof_look", "")
    assert "pp_lprof_group_n" in _code(PLAN_VALUES) + _code(MOD / cp.VALUES), "the group counts as a rule group"
    has = _block(_code(MOD / lpf.TRIGGERS), "pp_lprof_has_locations")
    assert "any_locations_with_town_rights_in_country" in has and "pp_tplan_held = yes" in has and "owner ?= root" in has
    assert "variable =" not in has
    hand = _code(MOD / lpf.HAND_EFFECTS)
    group = _block(hand, "pp_lprof_run")
    assert "pp_cplan_group_start = { why = 105 }" in _block(hand, "pp_lprof_look")
    assert "pp_cplan_group_target = { why = 105 do = pp_lprof_target_turn }" in group
    assert "pp_cplan_profiles_w > 0" in group  # the Locations weight bar at 0 switches the group off
    turn = _block(hand, "pp_lprof_location_turn")
    assert "save_temporary_scope_value_as = { name = pp_cplan_free_peasants value = pp_cplan_free_peasants_here }" in turn
    assert "owner ?= scope:pp_cplan_country" in _block(hand, "pp_lprof_gather")  # only the country's own locations
    assert turn.index("remove_variable = pp_cplan_hit") < turn.index("pp_lplan_location_turn = yes")
    opened = _block(hand, "pp_lprof_open")
    assert "has_variable = pp_cplan_hit" in opened and "value = 109" in opened
    assert "pp_cplan_hit" not in _block(_code(MOD / lpf.EFFECTS), "pp_lplan_location_marks")


def test_only_the_player() -> None:
    """The pass runs only inside the plan's monthly pass (human countries with the plan on); no on_action of its own."""
    for path in (COMMON / "on_action").glob("*.txt"):
        assert "pp_lprof" not in _read(path), path.name
    callers = [path.name for path in (COMMON / "scripted_effects").glob("*.txt") if "pp_lprof_run = yes" in _code(path)]
    assert callers == ["pp_construction_plan.txt"]


def test_states_and_texts() -> None:
    loc_path = MOD / lpf.LOC
    raw = loc_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0] == "l_english:"
    keys = dict(re.findall(r'^  ([A-Z0-9_]+): "(.*)"$', text, re.MULTILINE))
    for n in range(0, len(lpf.STATES) + 1):
        assert f"PP_LPROF_ST_{n}" in keys, n
        assert not re.search(r"\d", keys[f"PP_LPROF_ST_{n}"]), "no numbers in player text"
    assert "PP_CPLAN_WHY_PROFILE" in (MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml").read_text(encoding="utf-8-sig")
    hand = _code(MOD / lpf.HAND_EFFECTS)
    finish = _block(hand, "pp_lprof_finish")
    ranks = sorted(lpf.FAIL_STATE)
    for below, (rank, state) in zip([None] + ranks, sorted(lpf.FAIL_STATE.items())):
        if below is None:
            assert re.search(rf"else = \{{\s*set_variable = \{{ name = \$st\$ value = {100 + state} \}}", finish), rank
        else:
            # the split between a rank and the one below sits at their midpoint (102.5 and 103.5 are half ranks)
            assert re.search(rf"var:pp_lprof_fail > {(rank + below) / 2:g} \}}\n\t\tset_variable = \{{ name = \$st\$ value = {100 + state} \}}", finish), rank
    splits = [float(x) for x in re.findall(r"var:pp_lprof_fail > ([0-9.]+) \}", finish)]
    assert splits == sorted(splits, reverse=True) and len(splits) == len(ranks) - 1
    states = {int(n) - 100 for n in re.findall(r"name = (?:pp_lprof_st|\$st\$) value = (1\d\d)", hand + _code(MOD / lpf.EFFECTS))}
    assert states == set(lpf.STATES), "every state is written somewhere, and no other"
    # the window counts every state on its own, 11 to 13 too
    count = _block(hand, "pp_lprof_count_state")
    for n in lpf.STATES:
        assert count.count(f"name = pp_cplan_ds_profiles_st{n} add = 1") == 1, n
    assert ("st13", 100) in cp.SITUATION["profiles"] and len(cp.SITUATION["profiles"]) == len(lpf.STATES) + 1
    # the Locations pane shows the states a plan can reach (all but the market limit), each with its text as tooltip
    from prosper_or_perish_constructor import construction_plan_detail as cpd
    assert set(cpd.PROFILE_STATES) == set(lpf.STATES) - {9, 10}
    gui = _read(MOD / cpd.DETAIL_GUI)
    detail_loc = _read(MOD / cpd.DETAIL_LOC)
    for n in cpd.PROFILE_STATES:
        assert f'text = "PP_CPLAN_D_PROFILES_ST{n}" tooltip = "PP_LPROF_ST_{n}"' in gui, n
        assert f"PP_CPLAN_D_PROFILES_ST{n}:" in detail_loc, n
        assert re.search(rf"^pp_cplan_d_profiles_st{n} = \{{", _read(MOD / cp.VALUES), re.MULTILINE), n
    for n in (12, 13):
        assert "[building|e]" in keys[f"PP_LPROF_ST_{n}"], n
    # the Location Plan window's state texts pick the new states up
    plan_loc = _read(MOD / "main_menu/localization/english/pp_location_plan_generated_l_english.yml")
    assert "Localize('PP_LPROF_ST_12')" in plan_loc and "Localize('PP_LPROF_ST_13')" in plan_loc


def test_no_not_with_several_conditions() -> None:
    """NOT = { a b } means neither a nor b in this script language (the v2 guard bug of 2026-11-06)."""
    for path in OWN_FILES + (PLAN_EFFECTS, PLAN_TRIGGERS):
        text = _code(path)
        for match in re.finditer(r"\bNOT = \{", text):
            depth, index = 1, match.end()
            while depth:
                depth += {"{": 1, "}": -1}.get(text[index], 0)
                index += 1
            body = text[match.end():index - 1]
            top, level = 0, 0
            for token in re.finditer(r"\{|\}|[A-Za-z_:.\"()0-9?$]+\s*(?:[<>=!?]+)", body):
                if token.group(0) == "{":
                    level += 1
                elif token.group(0) == "}":
                    level -= 1
                elif level == 0:
                    top += 1
            assert top <= 1, f"{path.name}: NOT with {top} conditions: {body.strip()[:80]}"


def test_effect_calls_pass_their_parameters() -> None:
    """Every call of a parametrized scripted effect or trigger passes each $param$ its body uses, and nothing else:
    the engine refuses a call with an argument the body never uses ("Compiling source for <effect> failed for unknown
    arguments", debug.log) and the call then does nothing, silently. In game 2026-11-20 every plan target was a no-op
    that way (expand, start and upgrade shared one argument list)."""
    definitions: dict[str, set[str]] = {}
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in (COMMON / folder).glob("pp_*.txt"):
            text = _code(path)
            for match in re.finditer(r"^([a-z_][a-z0-9_]*) = \{", text, re.MULTILINE):
                end = text.find("\n}", match.end())
                params = set(re.findall(r"\$([a-z]+)\$", text[match.end():end]))
                if params:
                    definitions[match.group(1)] = params
    assert {"pp_lplan_mark", "pp_lprof_expand", "pp_lprof_upgrade"} <= set(definitions)
    calls = 0
    for path in OWN_FILES + (PLAN_EFFECTS, MOD / town_plans.EFFECTS):
        for name, args in re.findall(r"\b([a-z_][a-z0-9_]*) = \{ ((?:[a-z]+ = [^\s{}]+ )+)\}", _code(path)):
            if name in definitions:
                calls += 1
                passed = set(re.findall(r"([a-z]+) = ", args))
                assert definitions[name] <= passed, f"{path.name}: {name} lacks {definitions[name] - passed}"
                assert passed <= definitions[name], f"{path.name}: {name} gets unknown {passed - definitions[name]}"
    assert calls > 300


def test_braces_balance() -> None:
    for path in OWN_FILES:
        text = _code(path)
        assert text.count("{") == text.count("}"), path.name
        depth = 0
        for char in text:
            depth += {"{": 1, "}": -1}.get(char, 0)
            assert depth >= 0, path.name


def test_plans_keep_the_payback_they_found() -> None:
    """A plan shows the shortest payback it found beside its state: expand notes it, finish writes it into
    pp_lplan_est_<plan>."""
    code = _code(MOD / lpf.HAND_EFFECTS)
    expand = _block(code, "pp_lprof_expand")
    assert expand.index("pp_lprof_note_payback = yes") < expand.index("pp_lprof_payback100 > scope:pp_lprof_pb")
    assert "set_variable = { name = $est$ value = var:pp_lprof_best }" in _block(code, "pp_lprof_finish")
    assert "remove_variable = pp_lprof_best" in _block(code, "pp_lprof_open")  # a plan starts without an old payback


def test_plans_run_their_targets() -> None:
    """Each held plan runs its target (pp_lprof_t_<target>, or the plan's rank-raising turn) through the same start
    (pp_lprof_open) and end (pp_lprof_finish), in the plans' order, numbered."""
    effects = _code(MOD / lpf.EFFECTS)
    hand = _code(MOD / lpf.HAND_EFFECTS)
    marks = _block(effects, "pp_lplan_location_marks")
    lines = re.findall(r"^\t(pp_lplan_mark = \{ [^\n]* \})$", marks, re.MULTILINE)
    plans = town_plans.plans(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))
    result, _ = _build()
    goods = [good for good in lpf.target_goods(ROOT, PROJECT) if result.targets.get(good)]
    assert [plan.key for plan in plans] == goods + list(town_plans.EXTRA_PLANS)
    expected = []
    for number, plan in enumerate(plans, 101):
        expected.append(f"pp_lplan_mark = {{ v = g_{plan.key} g = {plan.key} do = {plan.do} "
                        f"n = {number} lo = {number - 0.5:g} hi = {number + 0.5:g} }}")
        assert re.search(rf"^pp_lprof_t_{plan.target} = \{{", effects, re.MULTILINE), plan.key
    assert lines == expected, "one line per plan, in the plans' order, numbered"
    assert len(goods) >= len(lpf.target_goods(ROOT, PROJECT)) - 2, "nearly every good has buildings"
    mark = _block(hand, "pp_lplan_mark")
    assert "limit = { has_town_rights = town_rights_type:pp_plan_$g$ }" in mark  # only while the plan right is held
    build = mark[mark.index("pp_lprof_open = yes"):]
    assert build.index("pp_lprof_open = yes") < build.index("$do$ = yes") < build.index("pp_lprof_finish = {")
    assert "limit = { NOT = { has_variable = pp_lprof_st } }" in build  # nothing is tried while it waits
    assert "pp_lprof_finish = { st = pp_lplan_st_$v$ est = pp_lplan_est_$v$ }" in build
    for name in ("pp_lprof_expand", "pp_lprof_start", "pp_lprof_build", "pp_cplan_construct_scoped"):
        assert f"{name} = " not in mark + marks, name
    turn = _block(hand, "pp_lprof_location_turn")
    assert "limit = { pp_tplan_held = yes }\n\t\tpp_lplan_location_turn = yes" in turn


def test_plans_are_forced() -> None:
    """Jan 2026-11-10: a location's pick is forced: no payback limit (unless the player sets one, plan settings
    2026-11-20), not held by the market limit; it keeps the can-build check, the workers, the construction goods, a
    free construction slot and the Locations purse."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    turn = _block(hand, "pp_lprof_location_turn")
    marks = _block(hand, "pp_lplan_location_turn")
    plan = _code(PLAN_EFFECTS)
    assert "save_temporary_scope_value_as = { name = pp_lprof_pb value = 1000000 }" in marks
    assert "max = 999" in _block(_code(PLAN_VALUES), "pp_cplan_est_payback_years")
    scoped = _block(plan, "pp_cplan_construct_scoped")
    assert ("limit = {\n\t\t\t\tpp_cplan_limits_market_$why$ = yes\n\t\t\t\tscope:pp_cplan_forced < 0.5\n\t\t\t}\n"
            "\t\t\tpp_cplan_market_do = { do = gate }") in scoped
    forced = "save_temporary_scope_value_as = { name = pp_cplan_forced value = %d }"
    assert forced % 0 in _block(plan, "pp_cplan_pass_begin")
    assert turn.index(forced % 0) < turn.index("pp_lplan_location_turn = yes") < turn.rindex(forced % 0)
    assert marks.index(forced % 1) < marks.index("pp_lplan_location_marks = yes")
    assert (hand + plan + _code(MOD / lpf.EFFECTS)).count("name = pp_cplan_forced value = 1") == 1
    expand = _block(hand, "pp_lprof_expand")
    for check in ("is_at_max_level = yes", "location_and_owner_can_build = { building_type = $type$ }",
                  "pp_cplan_staff = { type = $pt$ size = $sz$ }", "pp_cplan_goods_here_$demand$ = yes"):
        assert check in expand, check
    assert "pp_cplan_construct_scoped = { why = 105 }" in _block(hand, "pp_lprof_build")
    for check in ("pp_cplan_site_free = yes", "pp_cplan_affordable = { why = $why$ }", "pp_cplan_saving = { why = $why$ }"):
        assert check in scoped, check
    assert f"save_temporary_scope_value_as = {{ name = pp_cplan_rs value = {lpf.WHY_MARK_STEP} }}" in marks


def test_measurable_plans_go_first_by_payback() -> None:
    """Inside one location: the plans whose next level has a profit to measure first, the best payback first, built
    with the cost data it was measured with; then the plans in their order."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    marks = _block(hand, "pp_lplan_location_turn")
    mode = "save_temporary_scope_value_as = { name = pp_lplan_mode value = %d }"
    first, second = marks.index(mode % 1), marks.index(mode % 2)
    assert marks.index("pp_cplan_site_free = yes") < first and "NOT = { has_variable = pp_cplan_hit }" in marks[:first]
    measured = marks[first:second]
    assert measured.index("pp_lplan_location_marks = yes") < measured.index("limit = { has_variable = pp_lplan_bt }")
    assert measured.index("var:pp_lplan_bt = { save_scope_as = pp_cplan_btype }") < measured.index("pp_lprof_build = yes")
    for name in ("ipl", "pf", "ef"):
        restore = f"name = pp_cplan_{name} value = {{ value = var:pp_lplan_b{name} subtract = 100 }}"
        assert measured.index(restore) < measured.index("pp_lprof_build = yes"), name
        keep = f"set_variable = {{ name = pp_lplan_b{name} value = {{ value = scope:pp_cplan_{name} add = 100 }} }}"
        assert keep in _block(hand, "pp_lplan_measure"), name
        assert f"remove_variable = pp_lplan_b{name}\n" in _block(hand, "pp_lplan_measure_clear"), name
    for outcome in (101, 107, 102):
        assert f"set_variable = {{ name = pp_lplan_bo value = {outcome} }}" in measured, outcome
    built = marks[second:]
    assert built.index("pp_lplan_location_marks = yes") < built.index("pp_lplan_measure_clear = yes")
    assert "pp_lplan_b_data" not in marks and "pp_cplan_btype_data" not in marks
    measuring = _block(_code(PLAN_TRIGGERS), "pp_lplan_measuring")
    assert "scope:pp_lplan_mode > 0.5" in measuring and "scope:pp_lplan_mode < 1.5" in measuring
    expand = _block(hand, "pp_lprof_expand")
    tail = expand[expand.index("pp_cplan_goods_here_$demand$"):]
    assert tail.index("limit = { pp_lplan_measuring = yes }\n\t\t\t\tpp_lplan_measure = yes") < tail.index("pp_lprof_build = yes")
    measure = _block(hand, "pp_lplan_measure")
    assert measure.count("pp_lprof_payback100") == 1
    assert "scope:pp_lplan_pb100 < 1098" in measure and "var:pp_lplan_bp > scope:pp_lplan_pb100" in measure
    start = _block(hand, "pp_lprof_start")
    assert start.lstrip().startswith("if = {\n\t\tlimit = { pp_lplan_measuring = yes }")
    assert "NOT = { pp_lplan_measuring = yes }" in _block(hand, "pp_lprof_upgrade")
    assert "limit = { NOT = { pp_lplan_measuring = yes } }\n\t\t\tpp_tplan_raise = yes" in _read(MOD / town_plans.EFFECTS)
    mark = _block(hand, "pp_lplan_mark")
    measuring_part = mark[:mark.index("pp_lprof_open = yes")]
    assert (measuring_part.index("pp_lplan_measure_before = yes") < measuring_part.index("$do$ = yes")
            < measuring_part.index("pp_lplan_measure_after = { n = $n$ }"))
    assert "pp_lprof_finish" not in measuring_part, "measuring writes no state"
    winner = mark[mark.index("pp_lprof_open = yes"):]
    assert "var:pp_lplan_bn > $lo$" in winner and "var:pp_lplan_bn < $hi$" in winner and "has_variable = pp_lplan_bo" in winner
    for argument in ("v", "do", "n", "lo", "hi", "g"):
        assert f"${argument}$" in mark and not re.search(rf"\"[^\"\n]*\${argument}\$", mark), argument
    clear = _block(hand, "pp_lplan_measure_clear")
    for name in ("pp_lplan_bp", "pp_lplan_bt", "pp_lplan_bn", "pp_lplan_bo", "pp_lplan_bq"):
        assert f"remove_variable = {name}\n" in clear, name
        assert f"set_variable = {{ name = {name} " in hand or f"to = {name} }}" in hand, name  # never only removed


class _Values(ScriptEval):
    def single(self, key, op, v, safe, ctx):
        if key == "has_variable":
            return f"var:{v}" in ctx.get("game", {})
        return super().single(key, op, v, safe, ctx)


def test_locations_take_turns() -> None:
    """A place on the country says where the last look stopped: the next look starts after it and wraps around. What
    the group saves for stays one thing; the place moves past it once it is built. No extra walk."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    look = _block(hand, "pp_lprof_look")
    take = _block(hand, "pp_lprof_take_turn")
    assert "limit = { NOT = { has_variable = pp_lprof_seq } }" in take
    assert "change_variable = { name = pp_lprof_seq_n add = 1 }" in take
    assert "set_variable = { name = pp_lprof_seq value = scope:pp_cplan_country.var:pp_lprof_seq_n }" in take
    for name in ("pp_lprof_seq_n", "pp_lprof_cursor"):
        assert f"limit = {{ NOT = {{ has_variable = {name} }} }}\n\t\tset_variable = {{ name = {name} value = 100 }}" in look
    assert look.index("name = pp_lprof_cur value = var:pp_lprof_cursor") < look.index("ordered_in_list")
    assert "order_by = pp_lprof_turn" in look
    values = _Values(MOD)

    def order(numbers: list[int], cursor: int) -> list[int]:
        key = {n: values.value("pp_lprof_turn", {"game": {"var:pp_lprof_seq": 100 + n, "scope:pp_lprof_cur": 100 + cursor}})
               for n in numbers}
        return sorted(numbers, key=lambda n: -key[n])

    assert order([1, 2, 3, 4, 5, 6], 0) == [1, 2, 3, 4, 5, 6]
    assert order([1, 2, 3, 4, 5, 6], 3) == [4, 5, 6, 1, 2, 3]
    assert order([2, 5, 9], 5) == [9, 2, 5] and order([2, 5, 9], 40) == [2, 5, 9]
    after = look[look.index("clear_variable_list = pp_lprof_turns"):]
    assert "limit = { has_variable = pp_cplan_save_loc_105 }" in after
    assert "name = pp_lprof_cur value = { value = var:pp_lprof_seq subtract = 1 }" in after
    assert look.count("set_variable = { name = pp_lprof_cursor") == 2
    target = _block(hand, "pp_lprof_target_turn")
    assert target.index("pp_lprof_location_turn = yes") < target.index("has_variable = pp_cplan_hit")
    assert "set_variable = { name = pp_lprof_cursor value = scope:pp_lprof_cur }" in target
    assert len(re.findall(r"\b(?:every|ordered|random|any)_\w+ = \{", look)) == 1
    for name in ("pp_lprof_target_turn", "pp_lprof_location_turn", "pp_lprof_take_turn"):
        assert not re.search(r"\b(?:every|ordered|random|any)_\w+ = \{", _block(hand, name)), name


def test_planned_locations_get_their_turn() -> None:
    """The look finds the locations that hold a plan among the country's locations with town rights, no list of its
    own; each once."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    look = _block(hand, "pp_lprof_look")
    gather = _block(hand, "pp_lprof_gather")
    assert look.index("pp_lprof_gather = yes") < look.index("ordered_in_list")
    assert "variable = pp_lprof_turns" in look and "clear_variable_list = pp_lprof_turns" in look
    assert "every_locations_with_town_rights_in_country = {" in gather
    for part in ("owner ?= scope:pp_cplan_country", "pp_tplan_held = yes", "pp_lprof_take_turn = yes"):
        assert part in gather, part
    assert "variable = " not in gather.replace("clear_variable_list", "")
    assert "add_to_variable_list = { name = pp_lprof_turns target = scope:pp_lprof_this }" in _block(hand, "pp_lprof_take_turn")
    finish = _block(hand, "pp_lprof_finish")
    assert "set_variable = { name = $st$ value" in finish and "set_variable = { name = $est$ value" in finish


def test_rank_raise_saved_under_105() -> None:
    """A plan's rank raise saves under the Locations group (pp_cplan_save_rank_105): the window reads it, every place
    that lets go of what a group saves for removes it, and the group's target turn lets go of it before the plan's turn
    raises the rank again."""
    values = _read(MOD / cp.VALUES)
    effects = _read(MOD / cp.EFFECTS)
    assert "has_variable = pp_cplan_save_rank_105" in _block(values, "pp_cplan_save_rank_n_105")
    assert "remove_variable = pp_cplan_save_rank_105" in _block(effects, "pp_cplan_stats_reset_105")
    assert "remove_variable = pp_cplan_log_rank" in _block(effects, "pp_cplan_stats_reset_105")
    assert "remove_variable = pp_cplan_save_rank_105" in _block(effects, "pp_cplan_purses_fill")
    target = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_target_turn")
    assert target.index("remove_variable = pp_cplan_save_rank_105") < target.index("pp_lprof_location_turn = yes")


def test_each_plan_runs_with_its_payback_limit() -> None:
    """Plan settings (2026-11-20): a held plan runs with its own payback limit, else the all-plans one, else none
    (forced). Further levels compare the standing building's payback; first levels and tier upgrades the Businesses
    rule's level estimate, where it has one, and only under a limit (the estimate needs this year's harvest)."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    mark = _block(hand, "pp_lplan_mark")
    assert mark.index("has_town_rights = town_rights_type:pp_plan_$g$") < mark.index("pp_tplan_set_pb = { g = $g$ }")
    assert mark.index("pp_tplan_set_pb = { g = $g$ }") < mark.index("$do$ = yes"), "measuring and building read it"
    setpb = _block(hand, "pp_tplan_set_pb")
    assert "scope:pp_cplan_country = {\n\t\tsave_temporary_scope_value_as = { name = pp_tplan_pby value = pp_tplan_pb_years_$g$ }" in setpb
    assert "name = pp_lprof_pb value = { value = scope:pp_tplan_pby add = 100 }" in setpb
    assert "name = pp_lprof_pb value = 1000000" in setpb  # 0 years = any payback
    expand = _block(hand, "pp_lprof_expand")
    assert "limit = { pp_lprof_payback100 > scope:pp_lprof_pb }\n\t\t\t\tpp_lprof_fail = { r = 103 }" in expand
    for name, after in (("pp_lprof_start", "pp_lprof_consider = yes"), ("pp_lprof_upgrade", "pp_lprof_build = yes")):
        body = _block(hand, name)
        assert body.index("pp_cplan_ef value = pp_cplan_eff_$cat$") < body.index(
            "pp_lprof_new_check = { est = $est$ hasest = $hasest$ }") < body.index(after), name
        assert "limit = { scope:pp_lprof_over > 0.5 }\n\t\t\t\tpp_lprof_fail = { r = 103 }" in body, name
    check = _block(hand, "pp_lprof_new_check")
    assert check.index("name = pp_lprof_over value = 0") < check.index("always = $hasest$")
    assert "scope:pp_lprof_pb < 999999" in check and "name = pp_lprof_newp value = $est$" in check
    assert "pp_lprof_new_payback100 > scope:pp_lprof_pb" in check
    turn = _block(hand, "pp_lplan_location_turn")
    assert ("limit = { scope:pp_cplan_country = { has_variable = pp_tplan_pb_some } }\n\t\tpp_cplan_business_harvest = yes"
            in turn)
    assert turn.index("pp_cplan_business_harvest = yes") < turn.index("pp_lplan_location_marks")
    # the estimate's payback: cost over a year of the level's profit, + 100; no profit = too long
    class _Cost(ScriptEval):  # the level's price is the plan's cost formula, given here
        def value(self, expr, ctx):
            if expr == "pp_cplan_est_cost":
                return 1200.0
            return super().value(expr, ctx)

    values = _Cost(MOD)
    assert values.value("pp_lprof_new_payback100", {"game": {"scope:pp_lprof_newp": 10.0}}) == 110
    assert values.value("pp_lprof_new_payback100", {"game": {"scope:pp_lprof_newp": 0.0}}) == 1099
    assert values.value("pp_lprof_new_payback100", {"game": {"scope:pp_lprof_newp": 0.01}}) == 1099  # capped at 999 years


def test_never_at_a_loss_unless_switched_off() -> None:
    """Plan settings (default on): no level for a standing building that would lose money with every job filled (the
    game lays off its workers each month); a closed one gets its own state. The upgrade replaces the building and
    keeps going."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    expand = _block(hand, "pp_lprof_expand")
    loss = expand[expand.index("always = $lc$") - 40:expand.index("pp_lprof_fail = { r = 103.5 }")]
    for check in ("always = $lc$", "scope:pp_cplan_country = { NOT = { has_variable = pp_tplan_loss_ok } }",
                  "building_type = building_type:$type$", "building_potential_profit < 0"):
        assert check in loss, check
    assert expand.index("pp_lprof_fail = { r = 103.5 }") < expand.index("pp_lprof_payback100 > scope:pp_lprof_pb")
    assert expand.index("pp_lprof_note_payback = yes") < expand.index("always = $lc$")
    closed = "limit = { any_buildings_in_location = { building_type = building_type:$type$ is_opened = no } }\n\t\t\tpp_lprof_fail = { r = 102.5 }"
    assert closed in expand
    assert expand.index("is_at_max_level = yes") < expand.index(closed) < expand.index("location_and_owner_can_build")
    assert "building_potential_profit" not in _block(hand, "pp_lprof_upgrade") + _block(hand, "pp_lprof_start")
    assert lpf.FAIL_STATE[103.5] == 12 and lpf.FAIL_STATE[102.5] == 13


def test_worker_switch() -> None:
    """Plan settings: plans wait for free workers (default); with pp_tplan_staff_off they do not (expand and start)."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    for name in ("pp_lprof_expand", "pp_lprof_start"):
        body = _block(hand, name)
        assert re.search(r"limit = \{\n\t+scope:pp_cplan_country = \{ NOT = \{ has_variable = pp_tplan_staff_off \} \}\n"
                         r"\t+NOT = \{ pp_cplan_staff = \{ type = \$pt\$ size = \$sz\$ \} \}\n\t+\}\n\t+pp_lprof_fail = \{ r = 104 \}",
                         body), name


def test_plans_take_turns_unless_best_payback_first() -> None:
    """Plan settings: several plans in one location take turns (default): one go, the plans after the one that started
    the last construction first, then the rest; no measuring go. pp_tplan_order_best keeps the old two goes."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    effects = _code(MOD / lpf.EFFECTS)
    turn = _block(hand, "pp_lplan_location_turn")
    best = turn.index("limit = { scope:pp_cplan_country = { has_variable = pp_tplan_order_best } }")
    other = turn.index("\n\telse = {")  # the location turn's own else (one tab): the plans take turns
    assert best < turn.index("name = pp_lplan_mode value = 1") < turn.index("pp_lplan_location_marks = yes") < other
    rest = turn[other:]
    assert "pp_lplan_location_marks_turns = yes" in rest and "pp_lplan_mode value = 1" not in rest
    assert rest.index("name = pp_lplan_mode value = 2") < rest.index("pp_lplan_location_marks_turns = yes")
    lines = re.findall(r"^\t(pp_lplan_mark_turn = \{ [^\n]* \})$", _block(effects, "pp_lplan_location_marks_turns"), re.MULTILINE)
    marks = re.findall(r"^\tpp_lplan_mark = \{ ([^\n]*) \}$", _block(effects, "pp_lplan_location_marks"), re.MULTILINE)
    assert lines == ([f"pp_lplan_mark_turn = {{ {m} first = yes }}" for m in marks]
                     + [f"pp_lplan_mark_turn = {{ {m} first = no }}" for m in marks]), "every plan twice, in order"
    mark_turn = _block(hand, "pp_lplan_mark_turn")
    assert mark_turn.index("has_town_rights = town_rights_type:pp_plan_$g$") < mark_turn.index("always = $first$")
    assert "NOT = { has_variable = pp_lplan_last }\n\t\t\t\t\t\tvar:pp_lplan_last < $lo$" in mark_turn
    assert "NOT = { always = $first$ }\n\t\t\t\t\thas_variable = pp_lplan_last\n\t\t\t\t\tvar:pp_lplan_last > $lo$" in mark_turn
    assert "pp_lplan_mark = { v = $v$ g = $g$ do = $do$ n = $n$ lo = $lo$ hi = $hi$ }" in mark_turn
    mark = _block(hand, "pp_lplan_mark")
    built = mark[mark.index("limit = { NOT = { has_variable = pp_lprof_st } }"):]
    assert built.index("$do$ = yes") < built.index("var:pp_lprof_st < 101.5") < built.index(
        "set_variable = { name = pp_lplan_last value = $n$ }") < built.index("pp_lprof_finish")

    # the order the two goes give: n > last first, then n <= last (no last: everything in the first go)
    def order(numbers: list[int], last: int | None) -> list[int]:
        first = [n for n in numbers if last is None or last < n - 0.5]
        second = [n for n in numbers if last is not None and last > n - 0.5]
        return first + second

    assert order([101, 102, 103], None) == [101, 102, 103]
    assert order([101, 102, 103], 101) == [102, 103, 101] and order([101, 102, 103], 103) == [101, 102, 103]
    assert sorted(order([101, 105, 107], 105)) == [101, 105, 107]


def test_one_check_for_a_free_construction_site() -> None:
    """A plan waits while a construction is under way in the location; the check is the plan's own trigger."""
    opened = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_open")
    assert "limit = { NOT = { pp_cplan_site_free = yes } }" in opened and "value = 103" in opened
    assert re.search(r"^pp_cplan_site_free = \{", _read(PLAN_TRIGGERS), re.MULTILINE)
    for path in OWN_FILES:
        assert "num_civil_constructions" not in _code(path), path.name
    for name in ("pp_lprof_expand", "pp_lprof_start"):
        assert "pp_cplan_staff = { type = $pt$ size = $sz$ }" in _block(_code(MOD / lpf.HAND_EFFECTS), name), name
