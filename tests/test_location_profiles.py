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
        "start": rf"pp_lprof_start = \{{ {cost} {work} {estimate} how = (?P<how>cost|roi) \}}",
    }
    calls = [(kind, match.groupdict()) for kind, shape in shapes.items() for match in re.finditer(shape, effects)]
    assert len(calls) > 300
    assert len(calls) == len(re.findall(r"pp_lprof_(?:expand|start|upgrade) = \{", effects)), "every call matched"
    database = cp._database(MOD, vanilla_root(ROOT, PROJECT), cp.BUILDING_TYPES)
    methods = cp._database(MOD, vanilla_root(ROOT, PROJECT), lpf.PRODUCTION_METHODS)
    staff = cp.staffing(database, cp.script_value_numbers(MOD, vanilla_root(ROOT, PROJECT)))
    for kind, call in calls:
        name, demand, category = call["name"], call["demand"], call["cat"]
        assert name in known, name
        if kind == "expand":
            # the loss check reads buildings that make goods (a method with an output)
            assert (call["lc"] == "yes") == lpf.makes_goods(database[name][1], methods), name
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
    # every construction goes through the plan's budget check and its construct (ledger, never twice while queued):
    # the generic one for a type held at run time, the one without the type dispatches for a candidate's own type
    build = _block(hand, "pp_lprof_build")
    assert f"pp_cplan_construct_scoped = {{ why = {lpf.WHY_PROFILE} }}" in build
    known = _block(hand, "pp_lprof_build_known")
    assert (f"limit = {{ scope:pp_lprof_room >= 1 }}\n\t\tpp_cplan_construct_room = {{ why = {lpf.WHY_PROFILE} data = no }}"
            in known)
    for body in (build, known):
        assert body.index("remove_variable = pp_cplan_mlim") < body.index("pp_cplan_construct_") < body.index(
            "pp_lprof_build_end = yes")
    end = _block(hand, "pp_lprof_build_end")
    assert "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_wait } }\n\t\tpp_lprof_fail = { r = 107 }" in end
    assert "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_mlim } }\n\t\tpp_lprof_fail = { r = 106 }" in end
    assert end.index("has_variable = pp_cplan_wait") < end.index("has_variable = pp_cplan_mlim")
    assert "else = {\n\t\tpp_lprof_fail = { r = 102 }" in end  # no room: cannot be built, as before
    assert "construct_building" not in hand
    assert "pp_lprof_payback100 > scope:pp_lprof_pb" in _block(hand, "pp_lprof_expand")


def test_targets_wait_for_their_constructions() -> None:
    """A plan never starts a second level while any building of its target has one under construction here."""
    effects = _read(MOD / lpf.EFFECTS)
    result, _ = _build()
    for key, candidates in result.targets.items():
        if not candidates or key in lpf.NOT_RUN:
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
    # (the console's whole Locations look sets pp_lprof_whole: its slices at once)
    # (and the pass's start refreshes the cache of "a location holds a plan", pp_lprof_any_refresh)
    assert "pp_lprof" not in (plan.replace("pp_lprof_run", "").replace("pp_lprof_look", "").replace("pp_lprof_whole", "")
                              .replace("pp_lprof_any_refresh", ""))
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
    assert ("st13", 100) in cp.SITUATION["profiles"] and len(cp.SITUATION["profiles"]) == len(lpf.STATES) + 2
    assert ("unr", 100) in cp.SITUATION["profiles"]  # the locations a look did not reach (its purse spent)
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
        if plan.key in town_plans.OWN_TURNS:  # the food plan's own turn runs its sub-targets, never its whole list
            assert plan.target in lpf.NOT_RUN and not re.search(rf"^pp_lprof_t_{plan.target} = \{{", effects, re.MULTILINE)
            assert re.search(rf"^{plan.do} = \{{", _code(MOD / town_plans.EFFECTS), re.MULTILINE), plan.key
            continue
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
    go = _block(plan, "pp_cplan_construct_go")  # the shared tail of the generic and the type-known construct
    assert ("limit = {\n\t\t\tpp_cplan_limits_market_$why$ = yes\n\t\t\tscope:pp_cplan_forced < 0.5\n\t\t}\n"
            "\t\tpp_cplan_market_do = { do = gate }") in go
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
    assert "pp_cplan_site_free = yes" in scoped and "pp_cplan_site_free = yes" in _block(plan, "pp_cplan_construct_room")
    for check in ("pp_cplan_affordable = { why = $why$ }", "pp_cplan_saving = { why = $why$ }"):
        assert check in go, check
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
    assert "pp_lprof_build_known" not in measured  # the measured type is held at run time: the generic path
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
    assert tail.index("limit = { pp_lplan_measuring = yes }\n\t\t\t\tpp_lplan_measure = yes") < tail.index("pp_lprof_build_known = yes")
    measure = _block(hand, "pp_lplan_measure")
    assert measure.count("pp_lprof_payback100") == 1
    assert "scope:pp_lplan_pb100 < 1098" in measure and "var:pp_lplan_bp > scope:pp_lplan_pb100" in measure
    start = _block(hand, "pp_lprof_start")
    assert start.lstrip().startswith("if = {\n\t\tlimit = { pp_lplan_measuring = yes }")
    assert "NOT = { pp_lplan_measuring = yes }" in _block(hand, "pp_lprof_upgrade")
    # the rank raise waits while the plans are measured (and, plan option off, never raises: town_plans.py)
    assert ("limit = { NOT = { pp_lplan_measuring = yes } }\n\t\t\tif = {\n\t\t\t\tlimit = { scope:pp_cplan_country = "
            "{ has_variable = pp_tplan_raise_off } }") in _read(MOD / town_plans.EFFECTS)
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
    # the cursor moves at the end of the look's last daily slice (pp_lprof_look_end), from what the group saves for
    after = _block(hand, "pp_lprof_look_end")
    assert "limit = { has_variable = pp_cplan_save_loc_105 }" in after
    assert "name = pp_lprof_cur value = { value = var:pp_lprof_seq subtract = 1 }" in after
    assert look.count("set_variable = { name = pp_lprof_cursor") == 1 and after.count("set_variable = { name = pp_lprof_cursor") == 1
    assert "pp_lprof_look_end = yes" in _block(hand, "pp_lprof_slice")
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
    for name, after in (("pp_lprof_start", "pp_lprof_consider_$how$ = { type = $type$ }"),
                        ("pp_lprof_upgrade", "pp_lprof_build_known = yes")):
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
    # the worker failure is 104, or 104.25 where the level waits for workers and nothing else (plan_closer.py,
    # tests/test_plan_closer.py)
    fails = {"pp_lprof_expand": r"pp_pclose_worker_fail = \{ type = \$type\$ demand = \$demand\$ pt = \$pt\$ \}",
             "pp_lprof_start": r"pp_pclose_worker_fail_new = \{ type = \$type\$ demand = \$demand\$ pt = \$pt\$ "
                               r"ipl = \$ipl\$ cat = \$cat\$ \}"}
    for name, fail in fails.items():
        body = _block(hand, name)
        assert re.search(r"limit = \{\n\t+scope:pp_cplan_country = \{ NOT = \{ has_variable = pp_tplan_staff_off \} \}\n"
                         r"\t+NOT = \{ pp_cplan_staff = \{ type = \$pt\$ size = \$sz\$ \} \}\n\t+\}\n[\t\n]+" + fail, body), name


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
    turns = _block(effects, "pp_lplan_location_marks_turns")
    lines = re.findall(r"^\t+(pp_lplan_mark_turn = \{ [^\n]* \})$", turns, re.MULTILINE)
    marks = re.findall(r"^\tpp_lplan_mark = \{ ([^\n]*) \}$", _block(effects, "pp_lplan_location_marks"), re.MULTILINE)
    assert lines == ([f"pp_lplan_mark_turn = {{ {m} first = yes }}" for m in marks]
                     + [f"pp_lplan_mark_turn = {{ {m} first = no }}" for m in marks]), "every plan twice, in order"
    # script time 2026-11-20: the second go only where a plan started the location's last construction (without one
    # every plan ran in the first go and no plan passes the second go's gate)
    second = turns.index("first = no")
    assert turns.index("limit = { scope:pp_lplan_from > 100.5 }") < second
    assert "first = no" not in turns[:turns.index("limit = { scope:pp_lplan_from > 100.5 }")]
    # the split is taken as the turn begins (scope:pp_lplan_from): a plan starting in the first go does not make the
    # plans up to it run again (they used to become "waiting" and count twice)
    rest_start = turn[turn.index("\n\telse = {"):]
    assert (rest_start.index("name = pp_lplan_from value = 0") < rest_start.index("name = pp_lplan_from value = var:pp_lplan_last")
            < rest_start.index("pp_lplan_location_marks_turns = yes"))
    mark_turn = _block(hand, "pp_lplan_mark_turn")
    assert "pp_lplan_last" not in mark_turn
    assert "always = $first$\n\t\t\t\t\tscope:pp_lplan_from < $lo$" in mark_turn
    assert "NOT = { always = $first$ }\n\t\t\t\t\tscope:pp_lplan_from > $lo$" in mark_turn
    assert "has_town_rights = town_rights_type:pp_plan_$g$" in mark_turn
    assert "pp_lplan_mark = { v = $v$ g = $g$ do = $do$ n = $n$ lo = $lo$ hi = $hi$ }" in mark_turn
    mark = _block(hand, "pp_lplan_mark")
    built = mark[mark.index("limit = { NOT = { has_variable = pp_lprof_st } }"):]
    assert built.index("$do$ = yes") < built.index("var:pp_lprof_st < 101.5") < built.index(
        "set_variable = { name = pp_lplan_last value = $n$ }") < built.index("pp_lprof_finish")

    # the order the two goes give: n > last first, then n <= last (no last: everything in the first go); the gates as
    # written, with scope:pp_lplan_from = last or 0
    def order(numbers: list[int], last: int | None) -> list[int]:
        start = 0 if last is None else last
        first = [n for n in numbers if start < n - 0.5]
        second = [n for n in numbers if start > 100.5 and start > n - 0.5]
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


def _btype_data() -> dict[str, tuple[float, str, str]]:
    """What the generic dispatch pp_cplan_btype_data sets for each building type it names (the first match of each
    field's chain), with the defaults for every other type."""
    body = _block(_read(MOD / cp.EFFECTS), "pp_cplan_btype_data")
    fields: dict[str, dict[str, str]] = {"ipl": {}, "pf": {}, "ef": {}}
    for names, field, value in re.findall(
            r"limit = \{ OR = \{ ([^\n]*) \} \}\n\t\tsave_temporary_scope_value_as = \{ name = pp_cplan_(ipl|pf|ef) value = (\S+) \}",
            body):
        for name in re.findall(r"building_type:(\w+)", names):
            fields[field].setdefault(name, value)
    assert len(fields["ipl"]) > 100 and len(fields["pf"]) > 100 and len(fields["ef"]) > 10
    names = set(fields["ipl"]) | set(fields["pf"]) | set(fields["ef"])
    return {name: (float(fields["ipl"].get(name, "0")),
                   fields["pf"].get(name, f"pp_cplan_cd_{cp.DEFAULT_DEMAND}").removeprefix("pp_cplan_cd_"),
                   fields["ef"].get(name, "pp_cplan_eff_std").removeprefix("pp_cplan_eff_")) for name in names}


def _dispatch(data: dict[str, tuple[float, str, str]], name: str) -> tuple[float, str, str]:
    return data.get(name, (0.0, cp.DEFAULT_DEMAND, "std"))


def test_known_types_skip_the_type_dispatches() -> None:
    """Script time (2026-11-20): a construction whose building type is known when the script is written checks the
    room under its max level by the type's own value (pp_cplan_room_<type>, the line pp_cplan_no_room tests for it) and
    carries its cost data, so neither dispatch over every building type runs. Same outcome: every cost the candidates
    and the generated callers pass is what pp_cplan_btype_data sets for that type, every type has its room value, and
    a level without room is still "cannot be built" (102)."""
    data = _btype_data()
    rooms = set(re.findall(r"^pp_cplan_room_(\w+) = \{", _read(MOD / cp.VALUES), re.MULTILINE))
    effects = _read(MOD / lpf.EFFECTS)
    calls = 0
    for match in re.finditer(r"pp_lprof_(?:expand|start|upgrade) = \{ (?:old = \w+ )?type = (\w+) demand = (\w+) "
                             r"cat = (\w+) ipl = ([0-9.]+)", effects):
        name, demand, cat, ipl = match.groups()
        assert (float(ipl), demand, cat) == _dispatch(data, name), name
        assert name in rooms, name
        calls += 1
    assert calls > 300
    # the other rule groups' generated callers with a type written out (food, logistics, improvements, Towns and
    # Buildings' public buildings and upgrades)
    generated = "".join(_read(path) for path in (MOD / cp.EFFECTS, COMMON / "scripted_effects/pp_construction_plan_country.txt"))
    known = re.findall(r"pp_cplan_construct_(?:cost|food) = \{ type = (\w+) (?:why = \d+ )?ipl = ([0-9.]+) demand = (\w+) "
                       r"cat = (\w+) \}", generated)
    known += [(name, ipl, demand, cat) for name, demand, ipl, cat in re.findall(
        r"pp_cplan_country_(?:public|upgrade_to) = \{ type = (\w+) (?:line = \w+ )?demand = (\w+) ipl = ([0-9.]+) "
        r"cat = (\w+)", generated)]
    assert len(known) > 150
    for name, ipl, demand, cat in known:
        assert (float(ipl), demand, cat) == _dispatch(data, name), name
        assert name in rooms, name
    assert not re.search(r"pp_cplan_construct = \{ type = (?!\$type\$)", generated), "a written-out type passes its cost"
    plan = _code(PLAN_EFFECTS)
    for name in ("pp_cplan_construct", "pp_cplan_construct_cost"):
        body = _block(plan, name)
        assert body.index("building_type:$type$ = { save_scope_as = pp_cplan_btype }") < body.index(
            "limit = { pp_cplan_room_$type$ >= 1 }") < body.index("pp_cplan_construct_room = {"), name
    cost = _block(plan, "pp_cplan_construct_cost")
    for line in ("name = pp_cplan_ipl value = $ipl$", "name = pp_cplan_pf value = pp_cplan_cd_$demand$",
                 "name = pp_cplan_ef value = pp_cplan_eff_$cat$", "pp_cplan_construct_room = { why = $why$ data = no }"):
        assert line in cost, line
    assert "pp_cplan_construct_room = { why = $why$ data = yes }" in _block(plan, "pp_cplan_construct")
    # the generic path keeps both dispatches; the room path the same site checks without pp_cplan_no_room
    scoped, room, go = (_block(plan, name) for name in ("pp_cplan_construct_scoped", "pp_cplan_construct_room",
                                                         "pp_cplan_construct_go"))
    assert "NOT = { pp_cplan_no_room = yes }" in scoped and "pp_cplan_construct_go = { why = $why$ data = yes }" in scoped
    assert "pp_cplan_no_room" not in room and "pp_cplan_construct_go = { why = $why$ data = $data$ }" in room
    for check in ("pp_cplan_site_free = yes", "pp_cplan_bt_queued < 0.5", "is_opened = no"):
        assert check in scoped and check in room, check
    assert "limit = { always = $data$ }\n\t\t\tpp_cplan_btype_data = yes" in go
    assert go.index("pp_cplan_btype_data = yes") < go.index("pp_cplan_affordable = { why = $why$ }")
    # the plan engine: expand and upgrade read the room of their own type; the start pick carries it with the cost data
    hand = _code(MOD / lpf.HAND_EFFECTS)
    for name in ("pp_lprof_expand", "pp_lprof_upgrade"):
        body = _block(hand, name)
        assert "name = pp_lprof_room value = pp_cplan_room_$type$ }\n\t\t\t\tpp_lprof_build_known = yes" in body, name
        assert "pp_lprof_build = yes" not in body, name
    keep = _block(hand, "pp_lprof_keep")
    for name in ("ipl", "pf", "ef"):
        assert f"set_variable = {{ name = pp_lprof_pick_{name} value = {{ value = scope:pp_cplan_{name} add = 100 }} }}" in keep
        assert f"name = pp_cplan_{name} value = {{ value = var:pp_lprof_pick_{name} subtract = 100 }}" in _block(hand, "pp_lprof_start_pick")
        assert f"remove_variable = pp_lprof_pick_{name}\n" in _block(hand, "pp_lprof_pick_clear")
    assert "limit = { pp_cplan_room_$type$ >= 1 }\n\t\tset_variable = { name = pp_lprof_pick_room value = yes }" in keep
    pick = _block(hand, "pp_lprof_start_pick")
    assert pick.index("name = pp_lprof_room value = 0") < pick.index("has_variable = pp_lprof_pick_room") < pick.index(
        "pp_lprof_build_known = yes")
    assert "pp_lprof_pick_clear = yes" in pick and "pp_lprof_pick_clear = yes" in _block(hand, "pp_lplan_measure_after")
    assert "remove_variable = pp_lprof_pick\n" not in hand.replace(_block(hand, "pp_lprof_pick_clear"), "")
    # every reader of scope:pp_lprof_room has it set: the three callers of pp_lprof_build_known
    callers = re.findall(r"^(\w+) = \{(?:(?!^\}).)*pp_lprof_build_known = yes", hand, re.MULTILINE | re.DOTALL)
    assert sorted(callers) == ["pp_lprof_expand", "pp_lprof_start_pick", "pp_lprof_upgrade"]
    assert "pp_cplan_btype_data" not in hand  # the plan engine never dispatches over the types


EVENTS = MOD / "in_game/events/pp_construction_plan_events.txt"


def test_the_look_runs_in_daily_slices() -> None:
    """Daily slices (2026-11-20): the look fixes its turn order once (every location of the look on pp_lprof_todo with
    its place pp_lprof_pos), runs the first slice in the pass and every further one through a hidden event a day later.
    K = max(look_slice_min, ceil(locations / look_slice_days)) ([construction_plan], generated pp_lprof_slice_k)."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    look = _block(hand, "pp_lprof_look")
    assert look.index("pp_cplan_group_start = { why = 105 }") < look.index("pp_lprof_drop = yes")
    assert look.index("pp_lprof_drop = yes") < look.index("pp_lprof_gather = yes") < look.index("ordered_in_list = {")
    fill = look[look.index("ordered_in_list = {"):look.index("clear_variable_list = pp_lprof_turns")]
    assert "order_by = pp_lprof_turn" in fill and "variable = pp_lprof_turns" in fill
    assert "add_to_variable_list = { name = pp_lprof_todo target = scope:pp_lprof_this }" in fill
    assert "change_variable = { name = pp_cplan_ds_profiles_locs add = 1 }" in fill
    assert "set_variable = { name = pp_lprof_pos value = scope:pp_cplan_country.var:pp_lprof_todo_n }" in fill
    assert "pp_lprof_location_turn" not in fill  # the walk is the slices'
    rest = look[look.index("clear_variable_list = pp_lprof_turns"):]
    assert rest.index("set_variable = { name = pp_lprof_k value = pp_lprof_slice_k }") < rest.index(
        "set_variable = { name = pp_lprof_pend value = yes }") < rest.index("pp_lprof_slice = yes")
    assert "has_variable = pp_lprof_whole" in rest
    # a slice: the next K places in order; each still owned location that still holds a plan gets its turn
    sl = _block(hand, "pp_lprof_slice")
    walk = sl[sl.index("ordered_in_list = {"):sl.index("pp_lprof_slice_turn = yes")]
    assert "variable = pp_lprof_todo" in walk and "order_by = pp_lprof_pos_order" in walk
    assert "var:pp_lprof_pos > scope:pp_lprof_from" in walk and "var:pp_lprof_pos <= scope:pp_lprof_to" in walk
    assert "name = pp_lprof_to value = { value = var:pp_lprof_done add = var:pp_lprof_k }" in sl
    assert "name = pp_cplan_ds_profiles_unr value = { value = var:pp_lprof_todo_n subtract = var:pp_lprof_done add = 100 }" in sl
    done = sl[sl.index("limit = { var:pp_lprof_done >= var:pp_lprof_todo_n }"):]
    assert done.index("pp_lprof_look_end = yes") < done.index("else = {") < done.index(
        "trigger_event_silently = { id = pp_construction_plan.1 days = 1 }")
    turn = _block(hand, "pp_lprof_slice_turn")
    assert "owner ?= scope:pp_cplan_country" in turn and "pp_tplan_held = yes" in turn
    assert "pp_lprof_location_turn = yes" in turn
    # the load log (2026-11-20): pp_lprof_seen was set but never read; it and the look's number are gone
    for gone in ("pp_lprof_seen", "pp_lprof_look_n"):
        assert gone not in _read(MOD / lpf.HAND_EFFECTS), gone
    order = _block(_code(PLAN_VALUES), "pp_lprof_pos_order")
    assert "subtract = var:pp_lprof_pos" in order
    k = _block(_read(MOD / cp.VALUES), "pp_lprof_slice_k")
    assert "divide = pp_lprof_slice_days" in k and "ceiling = yes" in k and "min = pp_lprof_slice_min" in k
    config = cp.load_config(PROJECT)
    assert f"pp_lprof_slice_min = {{ value = {config.look_slice_min} }}" in _read(MOD / cp.VALUES)
    assert f"pp_lprof_slice_days = {{ value = {config.look_slice_days} }}" in _read(MOD / cp.VALUES)
    assert (config.look_slice_min, config.look_slice_days) == (60, 24) and config.look_slice_days < 28
    # the look's end: the cursor from what the group saves for, the list gone, the situation history moves on
    end = _block(hand, "pp_lprof_look_end")
    assert "limit = { has_variable = pp_cplan_save_loc_105 }" in end
    assert end.index("set_variable = { name = pp_lprof_cursor value = scope:pp_lprof_cur }") < end.index("pp_lprof_drop = yes")
    assert "pp_cplan_hq_push_105 = yes" in end
    drop = _block(hand, "pp_lprof_drop")
    for line in ("clear_variable_list = pp_lprof_todo", "remove_variable = pp_lprof_pend", "remove_variable = pp_lprof_pos"):
        assert line in drop
    # the console's whole look: all slices at once, no event
    test = _block(_code(PLAN_EFFECTS), "pp_cplan_test_profiles")
    assert test.index("set_variable = { name = pp_lprof_whole value = yes }") < test.index("pp_lprof_look = yes") < test.index(
        "remove_variable = pp_lprof_whole")


def test_the_slice_event_is_hidden_and_guarded() -> None:
    """The next slice comes through a hidden country event without options; its effect does nothing but drop the list
    when the plan is off, the country no longer runs it (the monthly on_action's test) or the group's weight is 0, and
    sets up what a turn reads outside a pass without filling a purse or resetting a number."""
    assert EVENTS.read_bytes().startswith(b"\xef\xbb\xbfnamespace = pp_construction_plan")
    events = _read(EVENTS)
    body = _block(re.sub(r"#[^\n]*", "", events), r"pp_construction_plan\.1")
    assert "type = country_event" in body and "hidden = yes" in body and "option" not in body
    assert "immediate = {\n\t\tpp_lprof_slice_event = yes\n\t}" in body
    ev = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_slice_event")
    guard = ev[:ev.index("save_scope_as = pp_cplan_country")]
    for line in ("has_variable = pp_lprof_pend", "has_variable = pp_cplan_on", "is_ai = no",
                 "has_variable = pp_cplan_ai_test", "pp_cplan_profiles_w > 0"):
        assert line in guard
    monthly = _read(COMMON / "on_action/pp_construction_plan.txt")
    assert "is_ai = no" in monthly and "has_variable = pp_cplan_ai_test" in monthly and "has_variable = pp_cplan_on" in monthly
    assert ev.rindex("else = {") > ev.index("pp_lprof_slice = yes") and "pp_lprof_drop = yes" in ev[ev.rindex("else = {"):]
    for line in ("save_scope_as = actor", "name = pp_cplan_rv value = 0", "name = pp_cplan_rs value = 0",
                 "name = pp_cplan_forced value = 0", "remove_variable = pp_cplan_hit", "remove_variable = pp_cplan_noted"):
        assert ev.index(line) < ev.index("pp_lprof_slice = yes"), line
    for never in ("pp_cplan_purses_fill", "pp_cplan_pass_begin", "pp_cplan_pass_reset", "pp_cplan_stats_reset",
                  "pp_cplan_group_start", "pp_cplan_history_push"):
        assert never not in ev, never
    # after the slice: the chart's month 1 from the look's totals; the Locations hand-on once the last slice ran
    after = ev[ev.index("pp_lprof_slice = yes"):]
    assert "set_variable = { name = pp_cplan_hn_105_1 value = { value = var:pp_cplan_dspent_105 add = var:pp_cplan_dwait_105 subtract = 100 } }" in after
    assert "set_variable = { name = pp_cplan_hs_105_1 value = var:pp_cplan_dspent_105 }" in after
    assert "limit = { NOT = { has_variable = pp_lprof_pend } }\n\t\t\tpp_cplan_purses_hand_on_105 = yes" in after
    # a pending list from an earlier look never survives into the next pass
    run = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_run")
    assert run.index("pp_pclose_month = yes") < run.index("has_variable = pp_lprof_pend") < run.index(
        "pp_lprof_drop = yes") < run.index("pp_lprof_look = yes")


def test_a_costing_turn_has_no_side_effects() -> None:
    """A turn that begins while the Locations group already saves for something is a costing turn: its plans run, so
    their states are set and the gold they want is counted, but nothing else happens there (before the slices such
    locations were not walked at all): nothing starts, no business closes, the closer's wait does not count down, the
    mark pp_lplan_wk is neither set nor removed."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    turn = _block(hand, "pp_lprof_location_turn")
    assert turn.index("name = pp_lprof_costing value = 0") < turn.index(
        "limit = { scope:pp_cplan_country = { has_variable = pp_cplan_save_cost_105 } }") < turn.index(
        "name = pp_lprof_costing value = 1") < turn.index("remove_variable = pp_lplan_wk")
    wk = turn[:turn.index("remove_variable = pp_lplan_wk")]
    assert wk.rstrip().endswith("limit = { scope:pp_lprof_costing < 0.5 }")
    assert turn.index("name = pp_lprof_costing value = 1") < turn.index("pp_pclose_turn_start = yes")
    finish = _block(hand, "pp_lprof_finish")
    mark = finish[:finish.index("set_variable = { name = pp_lplan_wk value = yes }")]
    assert mark[mark.rindex("limit = {"):].count("scope:pp_lprof_costing < 0.5") == 1
    assert hand.count("set_variable = { name = pp_lplan_wk value = yes }") == 1
    assert hand.count("remove_variable = pp_lplan_wk") == 1
    closer = _code(COMMON / "scripted_effects/pp_plan_closer.txt")
    start = _block(closer, "pp_pclose_turn_start")
    countdown = start[start.index("if = {"):]
    assert countdown.index("scope:pp_lprof_costing < 0.5") < countdown.index("change_variable = { name = pp_pclose_wait add = -1 }")
    mark_body = _block(hand, "pp_lplan_mark")
    call = mark_body[:mark_body.index("pp_pclose_plan = { g = $g$ }")]
    assert call[call.rindex("limit = {"):].count("scope:pp_lprof_costing < 0.5") == 1
    assert mark_body.count("pp_pclose_plan = { g = $g$ }") == 1
    costing = mark_body[mark_body.index("pp_pclose_plan = { g = $g$ }"):mark_body.index("pp_lprof_finish = {")]
    assert "scope:pp_lprof_costing > 0.5" in costing and "set_variable = { name = pp_lprof_fail value = 104.25 }" in costing
    for never in ("pp_pclose_pick", "add_to_variable_list", "pp_lplan_last", "construct"):
        assert never not in costing, never
    # the closer itself refuses while the group saves, and nothing starts while it saves
    assert "NOT = { pp_cplan_saving = { why = 105 } }" in _block(_code(COMMON / "scripted_triggers/pp_plan_closer.txt"),
                                                                 "pp_pclose_may")
    assert "NOT = { pp_cplan_saving = { why = $why$ } }" in _block(_code(PLAN_EFFECTS), "pp_cplan_construct_go")
    rank_up = _block(_code(COMMON / "scripted_effects/pp_construction_plan_country.txt"), "pp_cplan_country_rank_up")
    assert "NOT = { pp_cplan_saving = { why = $why$ } }" in rank_up
    # pp_lplan_last (the plans' turns) only moves when a construction started, which a costing turn never does
    last = mark_body[:mark_body.index("set_variable = { name = pp_lplan_last value = $n$ }")]
    assert "var:pp_lprof_st < 101.5" in last[last.rindex("limit = {"):]


def test_the_cut_is_gone() -> None:
    """Nothing is unreached for gold any more: no stop mark, no "held back until a look reaches it" value; the pane's
    counter pp_cplan_ds_profiles_unr is the look's locations still to be checked."""
    for path in (MOD / lpf.HAND_EFFECTS, MOD / lpf.VALUES, MOD / cp.VALUES, MOD / cp.EFFECTS, PLAN_EFFECTS, PLAN_VALUES):
        text = _read(path)
        assert "pp_lprof_cut" not in text and "pp_lprof_unreached" not in text, path
    assert not hasattr(lpf, "UNREACHED")
    look = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_look")
    assert "name = pp_cplan_ds_profiles_unr add = 1" not in look


def test_full_standing_line_starts_another() -> None:
    """2026-11-20: once every standing building of a target is at its highest level and nothing else stopped them
    (pp_lprof_fail exactly 101), another of its buildings starts, never one standing here nor an older tier of one; the
    plan's state is then the start's reason, or "nothing to build" where nothing could start."""
    effects = _code(MOD / lpf.EFFECTS)
    result, _ = _build()
    pairs = lpf.upgrade_pairs(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))
    checked = 0
    for key, candidates in result.targets.items():
        if not candidates or key in lpf.NOT_RUN:
            continue
        body = _block(effects, f"pp_lprof_t_{key}")
        standing = body[body.index("\telse_if = {"):body.index("\n\telse = {")]
        if len(candidates) == 1:
            assert "pp_lprof_more" not in standing, key
            continue
        more = standing[standing.index("pp_lprof_more = yes"):]
        gate = standing[standing.rindex("if = {", 0, standing.index("pp_lprof_more = yes")):standing.index("pp_lprof_more = yes")]
        for check in ("NOT = { has_variable = pp_lprof_st }", "has_variable = pp_lprof_fail", "var:pp_lprof_fail < 101.25",
                      "NOT = { pp_lplan_measuring = yes }"):
            assert check in gate, (key, check)
        assert standing.rindex("pp_lprof_expand = {") < standing.index("pp_lprof_more = yes")
        assert more.index("pp_lprof_start_pick = yes") < more.index("pp_lprof_more_end = yes")
        later = lpf.successors(candidates, pairs)
        starts = re.findall(r"limit = \{ NOT = \{ any_buildings_in_location = \{ building_level > 0 OR = \{ ([^}]*) \} \} \}"
                            r"[^\n]* \}\n\t+pp_lprof_start = \{ type = (\w+) ", more)
        assert {name for _, name in starts} == {c.name for c in candidates}, key
        for types, name in starts:
            assert re.findall(r"building_type:(\w+)", types) == [name] + later[name], (key, name)
        checked += 1
    assert checked > 50
    # wheat: the farm stands full -> a farmstead is never started while a farmstead or a later tier stands
    later = lpf.successors(result.targets["wheat"], pairs)
    assert {"wheat_farmstead", "wheat_rotations", "wheat_model_farm"} <= set(later["wheat_farm"])
    assert later["wheat_model_farm"] == []
    hand = _code(MOD / lpf.HAND_EFFECTS)
    more = _block(hand, "pp_lprof_more")
    for line in ("remove_variable = pp_lprof_fail", "remove_variable = pp_lprof_best", "pp_lprof_pick_clear = yes"):
        assert line in more, line
    end = _block(hand, "pp_lprof_more_end")
    assert "var:pp_lprof_fail < 102.25" in end and "pp_lprof_fail = { r = 101 }" in end and "NOT = { has_variable = pp_lprof_st }" in end
    # the unit: transitive successors among the target's own buildings
    a, b, c = (lpf.Candidate(name, "d", "std", 0.0) for name in ("a2", "a1", "a0"))
    assert lpf.successors([a, b, c], [("a0", "a1"), ("a1", "a2"), ("x", "a2")]) == {"a0": ["a1", "a2"], "a1": ["a2"], "a2": []}


def test_loss_check_only_for_buildings_that_make_goods() -> None:
    """2026-11-20: "never at a loss" reads only buildings with a method that has an output; a building whose methods
    only consume (the Marketplace's upkeep, the market centre's shared maintenance) always shows a loss and would never
    grow."""
    shared = {"upkeep": ({}, "\n\tpaper = 2\n\tcategory = building_maintenance\n"),
              "make": ({}, "\n\tproduced = tools\n\toutput = 1\n")}
    assert not lpf.makes_goods("unique_production_methods = { m = { cloth = 0.06 category = building_maintenance } }", shared)
    assert lpf.makes_goods("unique_production_methods = { m = { iron = 1 produced = tools output = 2 } }", shared)
    assert not lpf.makes_goods("possible_production_methods = { upkeep }", shared)
    assert lpf.makes_goods("possible_production_methods = { upkeep make }", shared)
    assert not lpf.makes_goods("# produced = tools\nunique_production_methods = { m = { paper = 1 } }", shared)
    effects = _code(MOD / lpf.EFFECTS)
    lc = dict(re.findall(r"pp_lprof_expand = \{ type = (\w+) [^}]* lc = (yes|no) \}", effects))
    for name in ("marketplace", "merchants_quarters", "port_authority", "trading_hub"):
        assert lc[name] == "no", name
    for name in ("wheat_farm", "lumber_mill", "cookshop"):
        if name in lc:
            assert lc[name] == "yes", name
    assert lc["wheat_farm"] == "yes"


def test_workers_flag_for_the_other_rule_groups() -> None:
    """2026-11-20: a location whose plan ended its turn waiting for workers (state 4, or 14 while a business closes for
    it) carries pp_lplan_wk until its next turn, for the other rule groups."""
    hand = _code(MOD / lpf.HAND_EFFECTS)
    turn = _block(hand, "pp_lprof_location_turn")
    assert turn.index("remove_variable = pp_lplan_wk") < turn.index("pp_lplan_location_turn = yes")
    finish = _block(hand, "pp_lprof_finish")
    flag = finish[finish.index("var:$st$ > 103.5"):finish.index("set_variable = { name = pp_lplan_wk value = yes }")]
    assert "var:$st$ < 104.5" in flag and "var:$st$ > 113.5" in flag and "var:$st$ < 114.5" in flag
    assert finish.rindex("set_variable = { name = $st$ value") < finish.index("pp_lplan_wk")
    assert hand.count("name = pp_lplan_wk value") == 1


ITERATOR = re.compile(r"\b(?:every|ordered|random|any)_\w+\s*=\s*\{|\bvariable\s*=")


def test_group_n_reads_a_cached_variable() -> None:
    """Script profile 2026-11-20: pp_lprof_group_n (through pp_cplan_profiles_cw / pp_cplan_w_total in every forecast
    value the window shows) walked the country's locations with town rights about a hundred times a frame. It reads
    the cache pp_lprof_any only; the real test runs at every pass's start before the weights are read, when the plan is
    switched on, and when a location's last plan is taken off (setting a plan sets the cache)."""
    body = _block(_code(MOD / lpf.VALUES), "pp_lprof_group_n")
    assert not ITERATOR.search(body) and "pp_lprof_has_locations" not in body
    assert f"has_variable = {lpf.ANY}" in body
    hand = _code(MOD / lpf.HAND_EFFECTS)
    refresh = _block(hand, "pp_lprof_any_refresh")
    assert "any_locations_with_town_rights_in_country" in refresh and "pp_tplan_held = yes" in refresh
    assert "owner ?= scope:pp_lprof_c" in refresh and "root" not in refresh  # the flip's root is a location
    assert f"set_variable = {{ name = {lpf.ANY} value = yes }}" in refresh and f"remove_variable = {lpf.ANY}" in refresh
    begin = _block(_code(PLAN_EFFECTS), "pp_cplan_pass_begin")
    assert begin.index("pp_lprof_any_refresh = yes") < begin.index("pp_cplan_forecast_measure = yes") < begin.index(
        "pp_cplan_purses_fill = yes")
    flip = _block(_code(COMMON / "scripted_effects/pp_location_plan.txt"), "pp_tplan_flip")
    off = flip[:flip.index("else = {\n\t\tgrant_town_rights")]
    assert off.index("revoke_town_rights_of_type") < off.index("pp_lprof_any_refresh = yes")
    on = flip[flip.index("grant_town_rights"):]
    assert f"owner ?= {{ set_variable = {{ name = {lpf.ANY} value = yes }} }}" in on
    toggle = _block(_code(COMMON / "scripted_guis/pp_construction_plan.txt"), "pp_cplan_toggle_on")
    assert toggle.index("has_variable = pp_cplan_on") < toggle.index("pp_lprof_any_refresh = yes")
