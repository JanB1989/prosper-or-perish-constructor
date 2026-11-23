"""Plans free their workers (plan_closer.py, scripted_effects/pp_plan_closer.txt, 2026-11-20, Jan).

Where a plan's next level waits for workers and nothing else, the location's turn closes ONE other business of the
player's there (least profit per worker first), then waits; taking the plan off or switching the setting off opens
them again. Script cannot close a building: a hidden scripted widget closes the buildings on a country list through
the game's own GUI function (in game 2026-11-20, prototype).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_detail as cpd
from prosper_or_perish_constructor import location_profiles as lpf
from prosper_or_perish_constructor import plan_closer as pc
from prosper_or_perish_constructor import town_plan_settings_gui as tps
from prosper_or_perish_constructor import town_plans as tp
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
DATA_TYPES = Path(r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\logs\data_types")
DATA_TYPES_WSL = Path("/mnt/c/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/logs/data_types")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _code(path: Path) -> str:
    return "\n".join(line.split("#", 1)[0] for line in _read(path).splitlines())


def _block(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{", text, re.MULTILINE)
    assert match, name
    depth, index = 0, match.end() - 1
    while True:
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        index += 1
        if depth == 0:
            return text[match.end():index - 1]


@cache
def _effects() -> str:
    return _code(MOD / pc.HAND_EFFECTS)


@cache
def _triggers() -> str:
    return _code(MOD / pc.HAND_TRIGGERS)


@cache
def _engine() -> str:
    return _code(MOD / lpf.HAND_EFFECTS)


@cache
def _inputs():
    return pc.inputs(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))


# ---- the widget ----------------------------------------------------------------------------------------------------


def test_widget_and_its_registration() -> None:
    assert _read(MOD / pc.WIDGET).split() == ["gui/pp_plan_closer.gui", "=", "pp_plan_closer"]
    gui = _code(MOD / pc.GUI)
    assert 'name = "pp_plan_closer"' in gui
    # players only, never observers
    assert 'visible = "[And(GetPlayer.Exists, Not(IsObserving))]"' in gui
    # one item per listed building, hidden until it turns visible; no size on a flowcontainer
    assert gui.count("flowcontainer = {") == 2 and gui.count("visible_at_creation = no") == 2
    for container in re.findall(r"flowcontainer = \{\n\t\tdatamodel = [^\n]+\n(?:(?!\n\t\})[\s\S])*", gui):
        assert not re.search(r"^\t\tsize = ", container, re.MULTILINE)
    close, reopen = gui.split("flowcontainer = {")[1:]
    ack = ("on_start = \"[GetScriptedGui('pp_pclose_ack').Execute(GuiScope.SetRoot(GetPlayer.MakeScope)"
           ".AddScope('pp_b', Scope.GetBuilding.MakeScope).End)]\"")
    assert f"datamodel = \"[GetPlayer.MakeScope.GetList('{pc.CLOSE_LIST}')]\"" in close
    assert 'visible = "[And(Scope.GetBuilding.IsOpen, CanCloseBuilding(Scope.GetBuilding.Self))]"' in close
    assert f"datamodel = \"[GetPlayer.MakeScope.GetList('{pc.OPEN_LIST}')]\"" in reopen
    assert 'visible = "[And(Not(Scope.GetBuilding.IsOpen), CanOpenBuilding(Scope.GetBuilding.Self))]"' in reopen
    # both lines in _show (once closed the item hides: a second state never ran in game), the action first
    for part, action in ((close, "CloseBuilding"), (reopen, "OpenBuilding")):
        show = part[part.index("name = _show"):]
        assert show.index(f'on_start = "[{action}(Scope.GetBuilding.Self)]"') < show.index(ack), action
        assert "next =" not in part and part.count("state = {") == 1
    depth = 0
    for char in gui:
        depth += {"{": 1, "}": -1}.get(char, 0)
        assert depth >= 0
    assert depth == 0 and gui.count("[") == gui.count("]")


def test_widget_functions_exist_in_the_data_type_dump() -> None:
    folder = DATA_TYPES if DATA_TYPES.is_dir() else DATA_TYPES_WSL
    if not folder.is_dir():
        pytest.skip("no data type dump")
    dump = "".join(path.read_text(encoding="utf-8", errors="replace") for path in folder.glob("data_types_*.txt"))
    names = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_.]*)(?:\(|$)", dump, re.MULTILINE))
    gui = _code(MOD / pc.GUI)
    used = {"CloseBuilding", "OpenBuilding", "CanCloseBuilding", "CanOpenBuilding", "IsObserving", "Building.IsOpen",
            "Building.Self", "Building.MakeScope", "Scope.GetBuilding", "Scope.GetList", "Country.MakeScope",
            "ScriptedGui.Execute"}
    for name in ("CloseBuilding(", "OpenBuilding(", "CanCloseBuilding(", "CanOpenBuilding(", "IsObserving", ".IsOpen",
                 ".Self", "GetBuilding.MakeScope", "GetList("):
        assert name in gui, name
    missing = sorted(name for name in used if name not in names and f"{name}(" not in dump)
    assert not missing, missing


def test_handshake() -> None:
    guis = _code(MOD / pc.SCRIPTED_GUIS)
    ack = _block(guis, pc.ACK_GUI)
    assert "scope = country" in ack
    assert f"remove_list_variable = {{ name = {pc.CLOSE_LIST} target = scope:pp_b }}" in ack
    assert f"remove_list_variable = {{ name = {pc.OPEN_LIST} target = scope:pp_b }}" in ack
    # scope:pp_b is set only by the widget: declared in a never-run block of the plan pass
    assert "save_scope_as = pp_b" in _block(_effects(), "pp_pclose_declare")
    run = _block(_engine(), "pp_lprof_run")
    never = run[run.index("limit = { always = no }"):]
    assert "pp_pclose_declare = yes" in never


# ---- when ----------------------------------------------------------------------------------------------------------


def test_only_a_level_that_waits_for_workers_and_nothing_else_asks() -> None:
    may = _block(_triggers(), "pp_pclose_may")
    for guard in ("is_ai = no", "NOT = { has_variable = pp_tplan_free_off }", "has_variable = pp_cplan_now_105",
                  "NOT = { pp_lplan_measuring = yes }", "NOT = { pp_cplan_saving = { why = 105 } }",
                  "pp_cplan_room_$type$ >= 1", "pp_cplan_goods_here_$demand$ = yes", "pp_cplan_affordable = { why = 105 }"):
        assert guard in may, guard
    fail = _block(_effects(), "pp_pclose_worker_fail")
    assert fail.index("pp_pclose_may = { type = $type$ demand = $demand$ }") < fail.index("pp_lprof_fail = { r = 104.25 }")
    assert "set_variable = { name = pp_pclose_pt value = pop_type:$pt$ }" in fail
    assert "limit = { NOT = { has_variable = pp_pclose_pt } }" in fail  # the first such candidate keeps its pop type
    assert re.search(r"else = \{\s*pp_lprof_fail = \{ r = 104 \}", fail)
    # a first level sets the cost temporaries the gold test reads only on this path
    new = _block(_effects(), "pp_pclose_worker_fail_new")
    for line in ("building_type:$type$ = { save_scope_as = pp_cplan_btype }", "value = $ipl$ }",
                 "value = pp_cplan_cd_$demand$ }", "value = pp_cplan_eff_$cat$ }"):
        assert new.index(line) < new.index("pp_pclose_worker_fail = { type = $type$ demand = $demand$ pt = $pt$ }"), line
    assert "pp_pclose_worker_fail = { type = $type$ demand = $demand$ pt = $pt$ }" in _block(_engine(), "pp_lprof_expand")
    assert ("pp_pclose_worker_fail_new = { type = $type$ demand = $demand$ pt = $pt$ ipl = $ipl$ cat = $cat$ }"
            in _block(_engine(), "pp_lprof_start"))
    assert "pp_pclose" not in _block(_engine(), "pp_lprof_upgrade")  # an upgrade asks no workers
    # the plan's best reason must be that one (no construction, no closer reason): pp_lplan_mark after its target
    mark = _block(_engine(), "pp_lplan_mark")
    turn = mark[mark.index("pp_lprof_open = yes"):]
    call = turn.index("pp_pclose_plan = { g = $g$ }")
    assert turn.index("$do$ = yes") < call < turn.index("pp_lprof_finish = {")
    for guard in ("NOT = { has_variable = pp_lprof_st }", "var:pp_lprof_fail > 104.125", "var:pp_lprof_fail < 104.625"):
        assert guard in turn[:call], guard
    assert pc.FAIL_CLOSE == 104.25 and lpf.FAIL_STATE[pc.FAIL_CLOSE] == pc.STATE


# ---- what and which ------------------------------------------------------------------------------------------------


def test_one_building_a_turn_then_the_location_waits() -> None:
    pick = _block(_effects(), "pp_pclose_pick")
    walk = re.findall(r"\b(?:every|ordered|random|any)_\w+ = \{", pick)
    assert walk == ["ordered_buildings_in_location = {"]
    for line in ("limit = { pp_pclose_candidate = yes }", "order_by = pp_pclose_rank", "max = 1", "check_range_bounds = no"):
        assert line in pick, line
    assert f"add_to_variable_list = {{ name = {pc.CLOSE_LIST} target = scope:pp_pclose_b }}" in pick
    assert f"add_to_variable_list = {{ name = {pc.TYPES_LIST} target = scope:pp_pclose_b.building_type }}" in pick
    assert f"add_to_variable_list = {{ name = {pc.LOCATIONS_LIST} target = scope:pp_pclose_l }}" in pick
    assert f"set_variable = {{ name = {pc.WAIT_VAR} value = {100 + pc.WAIT_LOOKS} }}" in pick
    assert "set_variable = { name = pp_pclose_none value = yes }" in pick  # nothing found: no second walk this turn
    # the walk runs only from a plan's turn, once a turn, never while the location waits
    callers = [name for name, body in re.findall(r"^(\w+) = \{([\s\S]*?)^\}", _effects() + "\n" + _engine(), re.MULTILINE)
               if "pp_pclose_pick = yes" in body]
    assert callers == ["pp_pclose_plan"]
    plan = _block(_effects(), "pp_pclose_plan")
    first = plan[:plan.index("pp_pclose_pick = yes")]
    for guard in ("NOT = { has_variable = pp_pclose_wait }", "NOT = { has_variable = pp_pclose_none }",
                  "has_variable = pp_pclose_pt"):
        assert guard in first, guard
    # while a closing is under way the plan is one of those it is for (state 14); else its state is 4
    # (2026-11-21: one location variable per plan, pp_pclose_for_<plan>, no list of town rights)
    assert f"set_variable = {{ name = {pc.FOR_PREFIX}$g$ value = yes }}" in plan and "town_rights" not in plan
    assert "set_variable = { name = pp_lprof_fail value = 104 }" in plan
    # the wait counts down one look per look turn (not when the group goes back between looks)
    start = _block(_effects(), "pp_pclose_turn_start")
    assert "has_variable = pp_cplan_now_105" in start and "change_variable = { name = pp_pclose_wait add = -1 }" in start
    assert "var:pp_pclose_wait < 100.5" in start
    turn = _block(_engine(), "pp_lprof_location_turn")
    assert turn.index("pp_pclose_turn_start = yes") < turn.index("pp_lplan_location_turn = yes") < turn.index(
        "pp_pclose_turn_end = yes")
    assert "remove_variable = pp_pclose_pt" in _block(_engine(), "pp_lprof_open")  # each plan its own pop type


def test_candidate_guards() -> None:
    cand = _block(_triggers(), "pp_pclose_candidate")
    for guard in ("owner ?= scope:pp_cplan_country", "is_opened = yes", "building_level > 0",
                  "building_levels_under_construction < 1", "building_employed_amount > 0", "is_subsidized = no",
                  "any_production_method_of_building = { always = yes }", "NOT = { pp_pclose_never_type = yes }",
                  "NOT = { pp_pclose_planned = yes }",
                  "NOT = { scope:pp_pclose_l = { is_target_in_variable_list = { name = pp_pclose_keep target = prev.building_type } } }"):
        assert guard in cand, guard
    assert re.search(r"OR = \{\s*building_pop_type = peasants\s*pp_pclose_pt_match = yes\s*\}", cand)
    assert re.search(r"OR = \{\s*scope:pp_pclose_fed > 0\.5\s*NOT = \{ pp_pclose_food_type = yes \}\s*\}", cand)
    # food makers only while the store is not short, by the food rule's own line
    store = _block(_triggers(), "pp_pclose_store_ok")
    hungry = _block(_code(COMMON / "scripted_triggers/pp_construction_plan.txt"), "pp_cplan_hungry")
    assert "has_variable = pp_stored_food_months" in store and "pp_cplan_food_in_a_year >= pp_cplan_hungry_months" in store
    assert "< pp_cplan_hungry_months" in hungry
    pick = _block(_effects(), "pp_pclose_pick")
    assert pick.index("province ?= { pp_pclose_store_ok = yes }") < pick.index("ordered_buildings_in_location")
    for scope in ("save_temporary_scope_as = pp_pclose_l", "var:pp_pclose_pt = { save_temporary_scope_as = pp_pclose_pt }",
                  "name = pp_pclose_fed value = 0"):
        assert pick.index(scope) < pick.index("ordered_buildings_in_location"), scope


def test_generated_lists() -> None:
    plans, never, food, pop_types = _inputs()
    text = _read(MOD / pc.TRIGGERS)
    assert text == pc.render_triggers(plans, never, food, pop_types).lstrip("\ufeff"), "run ppc build (plan_closer)"
    code = _code(MOD / pc.TRIGGERS)
    assert _read(MOD / pc.EFFECTS) == pc.render_effects(plans, pop_types).lstrip("﻿"), "run ppc build (plan_closer)"
    planned = _block(code, "pp_pclose_planned")
    for plan in plans:
        part = planned[planned.index(f"scope:pp_pclose_l = {{ has_variable = {plan.var} }}"):]
        part = part[:part.index("\t\t}\n")]
        assert {f"building_type:{c}" for c in plan.candidates} == set(re.findall(r"building_type:\w+", part)), plan.key
    config = cp.load_config(PROJECT)
    for name in config.logistics_order:
        assert name in never, name
    for name in ("library", "university", "dock", "dry_dock"):  # public buildings, later tiers too
        assert name in never, name
    for name in ("field_management", "irrigation_systems"):  # improvements (capacity)
        assert name in never, name
    from prosper_or_perish_constructor import construction_plan_country as cc

    database = cc.database(MOD, vanilla_root(ROOT, PROJECT), cc.BUILDING_TYPES)
    dlc = {name for name, entry in database.items() if entry.dlc_only}
    assert not (set(never) | set(food)) & dlc  # DLC-only keys never appear in the mod's script
    by_key = {plan.key: plan for plan in plans}
    assert set(by_key["food"].candidates) - dlc <= set(food)
    for name in (*config.kitchens, *config.taverns, *config.granges, *config.yards):
        assert name in food, name
    assert set(pop_types) | {"peasants"} == set(cp._database(MOD, vanilla_root(ROOT, PROJECT), cp.POP_TYPES))
    match = _block(code, "pp_pclose_pt_match")
    for pt in pop_types:
        assert f"building_pop_type = {pt}\n\t\t\tscope:pp_pclose_pt = pop_type:{pt}" in match, pt
    for name in ("pp_pclose_never_type", "pp_pclose_food_type"):
        assert _block(code, name).count("building_type = building_type:") == len(never if "never" in name else food)
    assert "town_rights" not in code


def test_for_held_and_for_clear_cover_every_plan() -> None:
    """2026-11-21: the plans a location's closings are for are location variables pp_pclose_for_<plan> (was a list of
    plan rights). pp_pclose_for_held (generated trigger) holds while the location carries one of them together with
    that plan's marker; pp_pclose_for_clear (generated effect, its own file) removes every one; both list every plan
    once, in the plans' order."""
    plans = _inputs()[0]
    assert not hasattr(pc, "FOR_LIST") and pc.FOR_PREFIX == "pp_pclose_for_"
    held = _block(_code(MOD / pc.TRIGGERS), pc.FOR_HELD)
    assert held.strip().startswith("OR = {")
    pairs = re.findall(r"AND = \{\s*has_variable = (\w+)\s*has_variable = (\w+)\s*\}", held)
    assert pairs == [(f"{pc.FOR_PREFIX}{plan.key}", plan.var) for plan in plans]
    clear = _block(_code(MOD / pc.EFFECTS), pc.FOR_CLEAR)
    assert re.findall(r"remove_variable = (\w+)", clear) == [f"{pc.FOR_PREFIX}{plan.key}" for plan in plans]
    assert clear.count("\n\t") == len(plans)
    # the hand-written closer sets them through the plan's turn and clears them only through the generated effect
    effects = _effects()
    assert re.findall(r"pp_pclose_for_\w+", effects.replace("pp_pclose_for_$g$", "")) == [
        pc.FOR_HELD, pc.FOR_CLEAR, pc.FOR_CLEAR]
    for name in ("pp_pclose_undo", "pp_pclose_forget"):
        assert f"{pc.FOR_CLEAR} = yes" in _block(effects, name), name
    needed = _tokens(_block(effects, "pp_pclose_needed"))
    assert needed == f"if = {{ limit = {{ NOT = {{ {pc.FOR_HELD} = yes }} }} pp_pclose_undo = yes }}"


def _tokens(text: str) -> str:
    return " ".join(text.split())


# ---- order -----------------------------------------------------------------------------------------------------------


def test_order_least_profit_per_worker_first() -> None:
    from prosper_or_perish_constructor.script_eval import ScriptEval

    values = ScriptEval(MOD)

    def rank(profit: float, employed: float) -> float:
        return values.value("pp_pclose_rank", {"game": {"building_profit": profit, "building_employed_amount": employed}})

    # the walk takes the highest first
    assert rank(-2, 1) > rank(0, 1) > rank(1, 2) > rank(1, 1) > rank(5, 1)
    assert rank(1, 4) > rank(1, 1)  # same profit, more workers: less per worker
    assert rank(2, 2) > rank(1, 1) and rank(2, 2) - rank(1, 1) < 1  # same profit per worker: more workers first
    assert rank(-1, 0.5) > rank(3, 0.5)
    assert rank(0.5, 0) == -50000  # no division by zero (a candidate has workers: building_employed_amount > 0)
    assert "multiply = -100" in _code(COMMON / "script_values/pp_plan_closer.txt")


# ---- memory and undo -----------------------------------------------------------------------------------------------


def test_lists_never_outlive_a_month() -> None:
    month = _block(_effects(), "pp_pclose_month")
    assert month.index(f"clear_variable_list = {pc.CLOSE_LIST}") < month.index("every_in_list")
    assert f"clear_variable_list = {pc.OPEN_LIST}" in month
    # the list of locations is copied, emptied and rebuilt by the check, never changed while it is walked
    assert month.index(f"clear_variable_list = {pc.LOCATIONS_LIST}") < month.index("pp_pclose_check = yes")
    assert "variable = pp_pclose_sweep" in month
    check = _block(_effects(), "pp_pclose_check")
    assert f"add_to_variable_list = {{ name = {pc.LOCATIONS_LIST} target = scope:pp_pclose_l }}" in check
    run = _block(_engine(), "pp_lprof_run")
    assert run.lstrip().startswith("pp_pclose_month = yes")


def test_memory_and_undo() -> None:
    check = _block(_effects(), "pp_pclose_check")
    order = ["NOT = { owner ?= scope:pp_cplan_country }", "pp_pclose_forget = yes", "has_variable = pp_tplan_free_off",
             "pp_pclose_undo = yes", "pp_pclose_taken_back = yes", "pp_pclose_needed = yes"]
    assert [check.index(part) for part in order] == sorted(check.index(part) for part in order)
    # opened again by hand: the type goes onto the keep list, off the closed types; not under the game's automation
    back = _block(_effects(), "pp_pclose_taken_back")
    assert "NOT = { is_system_automated = closebuildings }" in back
    assert back.index("is_opened = yes") < back.index(f"add_to_variable_list = {{ name = {pc.KEEP_LIST} target = scope:pp_pclose_t }}")
    assert f"remove_list_variable = {{ name = {pc.TYPES_LIST} target = scope:pp_pclose_t }}" in back
    # kept while a plan they are for is held, else every closed building of those types opens
    # (2026-11-21: the plans they are for are location variables, pp_pclose_for_held asks them)
    needed = _block(_effects(), "pp_pclose_needed")
    assert needed.index(f"NOT = {{ {pc.FOR_HELD} = yes }}") < needed.index("pp_pclose_undo = yes")
    undo = _block(_effects(), "pp_pclose_undo")
    for line in ("building_type = scope:pp_pclose_t", "owner ?= scope:pp_pclose_c", "is_opened = no",
                 f"add_to_variable_list = {{ name = {pc.OPEN_LIST} target = scope:pp_pclose_b }}",
                 f"clear_variable_list = {pc.TYPES_LIST}", f"{pc.FOR_CLEAR} = yes",
                 f"remove_variable = {pc.WAIT_VAR}"):
        assert line in undo, line
    assert re.search(rf"NOT = \{{ pp_tplan_held = yes \}} \}}\s*clear_variable_list = {pc.KEEP_LIST}", undo)
    # a plan taken off (the button and Clear go through pp_tplan_flip): its marker and pp_tplan_any first
    flip = _block(_code(COMMON / "scripted_effects/pp_location_plan.txt"), "pp_tplan_flip")
    assert (flip.index("remove_variable = pp_tplan_p_$g$") < flip.index("remove_variable = pp_tplan_any")
            < flip.index("pp_pclose_plan_off = yes") < flip.index("\telse = {"))
    off = _block(_effects(), "pp_pclose_plan_off")
    assert "owner = { save_temporary_scope_as = pp_pclose_c }" in off and "pp_pclose_needed = yes" in off
    assert "exists = owner" in off
    # the setting switched off: everything the rule closed opens
    every = _block(_effects(), "pp_pclose_undo_all")
    assert "variable = pp_pclose_locs" in every and "owner ?= scope:pp_pclose_c" in every and "pp_pclose_undo = yes" in every


# ---- the setting -----------------------------------------------------------------------------------------------------


def test_setting() -> None:
    assert pc.OFF_VAR == tp.FREE_OFF_VAR == "pp_tplan_free_off"
    values = _code(MOD / tp.VALUES)
    assert re.search(rf"{tp.FREE_VALUE} = \{{\s*value = 1\s*if = \{{\s*limit = \{{ has_variable = {tp.FREE_OFF_VAR} \}}\s*value = 0",
                     values)
    gui = _read(MOD / tps.GUI)
    assert tps.FREE in tps.CONTRACT_VALUES and tps.TOGGLES["free"] == tp.TOGGLE_FREE_GUI
    assert f"GetScriptedGui('{tp.TOGGLE_FREE_GUI}')" in gui and 'text = "PP_TPLAN_SET_FREE"' in gui
    loc = dict(re.findall(r'^  ([A-Za-z0-9_.]+): "(.*)"$', _read(MOD / tps.LOC), re.MULTILINE))
    assert loc["PP_TPLAN_SET_FREE"] == "Close other businesses for a plan's workers"
    tooltip = loc["PP_TPLAN_SET_FREE_TT"]
    for words in ("earns least per worker", "food store is short", "Taking the plan off", "open yourself stays open",
                  "[location|e]", "[building|e]"):
        assert words in tooltip, words
    assert "cannot close buildings" not in loc["PP_TPLAN_SET_CLOSE_TT"]


def test_switching_the_plan_off_opens_what_the_plans_closed() -> None:
    """The monthly check runs only while the Construction Plan is on, so its switch undoes the closings itself."""
    guis = _code(MOD / "in_game/common/scripted_guis/pp_construction_plan.txt")
    toggle = _block(guis, "pp_cplan_toggle_on")
    # (switched on, the cache of "a location holds a plan" is refreshed too: pp_lprof_any_refresh)
    assert re.search(r"if = \{\s*limit = \{ has_variable = pp_cplan_on \}\s*pp_cplan_history_clear = yes\s*"
                     r"pp_lprof_any_refresh = yes\s*pp_cplan_forecast_store = yes\s*\}\s*"
                     r"else = \{\s*pp_pclose_undo_all = yes\s*\}", toggle)


# ---- free workers, states --------------------------------------------------------------------------------------------


def test_free_workers_ignore_closed_buildings() -> None:
    from prosper_or_perish_constructor.script_eval import ScriptEval

    class _Open(ScriptEval):
        def single(self, key, op, v, safe, ctx):
            if key == "is_opened" and "building_type" in ctx:
                return ctx["open"] == (v is True or str(v) == "yes")
            return super().single(key, op, v, safe, ctx)

        def value(self, expr, ctx):
            if str(expr) in ("building_employment_size_amount", "building_employed_amount") and "building_type" in ctx:
                return float(ctx[str(expr)])
            return super().value(expr, ctx)

    values = _Open(MOD)
    game = {"unemployed_peasants": 3.0}
    mill = {"open": True, "building_employment_size_amount": 2.0, "building_employed_amount": 1.5}
    closed = {"open": False, "building_employment_size_amount": 2.0, "building_employed_amount": 0.0}
    assert values.value("pp_cplan_free_peasants_here", {"game": game, "buildings": {"mill": mill}}) == 2.5
    # a closed building keeps its employment size but hires nobody: its jobs are not open
    assert values.value("pp_cplan_free_peasants_here", {"game": game, "buildings": {"mill": mill, "kiln": closed}}) == 2.5


def test_state_fourteen_everywhere() -> None:
    assert pc.STATE in lpf.STATES and pc.STATE in cpd.PROFILE_STATES and "[building|e]" in cpd.PROFILE_STATES[pc.STATE]
    assert ("st14", 100) in cp.SITUATION["profiles"]
    loc = dict(re.findall(r'^  ([A-Z0-9_]+): "(.*)"$', _read(MOD / lpf.LOC), re.MULTILINE))
    assert "[building|e]" in loc["PP_LPROF_ST_14"] and not re.search(r"\d", loc["PP_LPROF_ST_14"])
    assert "name = pp_cplan_ds_profiles_st14 add = 1" in _block(_engine(), "pp_lprof_count_state")
    assert "Localize('PP_LPROF_ST_14')" in _read(MOD / "main_menu/localization/english/pp_location_plan_generated_l_english.yml")
    assert 'text = "PP_CPLAN_D_PROFILES_ST14" tooltip = "PP_LPROF_ST_14"' in _read(MOD / cpd.DETAIL_GUI)


def test_calls_pass_exactly_what_the_bodies_use() -> None:
    """The engine makes a call with an argument its body never uses a silent no-op (tests/test_script_call_arguments.py
    scans the whole mod); here the new effects and triggers by name."""
    expected = {"pp_pclose_worker_fail": {"type", "demand", "pt"},
                "pp_pclose_worker_fail_new": {"type", "demand", "pt", "ipl", "cat"},
                "pp_pclose_plan": {"g"}}
    for name, params in expected.items():
        assert set(re.findall(r"\$(\w+)\$", _block(_effects(), name))) == params, name
    assert set(re.findall(r"\$(\w+)\$", _block(_triggers(), "pp_pclose_may"))) == {"type", "demand"}
    for name in ("pp_pclose_month", "pp_pclose_check", "pp_pclose_undo", "pp_pclose_pick", "pp_pclose_turn_start"):
        assert "$" not in _block(_effects(), name), name
    for path in (MOD / pc.HAND_EFFECTS, MOD / pc.HAND_TRIGGERS, MOD / pc.SCRIPTED_GUIS, MOD / pc.TRIGGERS):
        text = _code(path)
        assert text.count("{") == text.count("}"), path.name


def test_row_lock() -> None:
    """The padlock on each pop type row of the location window (2026-11-23, Jan): one click closes the row's
    producing buildings of the player, the next opens them, through the widget's two lists."""
    window = _read(MOD / "in_game/gui/location_window.gui")
    assert window.count(pc.ROW_MARK) == 1
    assert pc.add_row_locks(window) == window
    button = window[window.index(pc.ROW_MARK):]
    button = button[:button.index("action_tooltip") + 700]
    assert "tooltipwidget" in button and "ContextualTooltipType" in button
    for key in ("PP_ROW_LOCK_TITLE_OPEN", "PP_ROW_LOCK_TITLE_CLOSED"):
        assert f"'{key}'" in button, key
    assert f"GetScriptedGui('{pc.ROW_GUI}').Execute(" in button and "MakeScopeFlag(PopType.GetKey)" in button
    assert f"Concatenate('{pc.ROW_VAR}', PopType.GetKey)" in button and pc.ROW_VISIBLE in button
    # the lock lies after the header's own button (on top of it)
    assert window.index("ShowLocationProductionViewForPopType(LocationView.GetLocation.GetId") < window.index(pc.ROW_MARK)
    gui = _block(_code(MOD / pc.SCRIPTED_GUIS), pc.ROW_GUI)
    assert "scope = location" in gui and "save_scope_as = pp_row_c" in gui and f"{pc.ROW_PICK} = yes" in gui
    assert "is_ai = no" in gui
    pick = _block(_code(MOD / pc.EFFECTS), pc.ROW_PICK)
    _, _, _, pop_types = _inputs()
    for pt in {*pop_types, "peasants"}:
        assert f"scope:pp_key = flag:{pt} }}\n\t\tpp_row_toggle_do = {{ pt = {pt} }}" in pick, pt
    do = _block(_effects(), "pp_row_toggle_do")
    assert set(re.findall(r"\$(\w+)\$", do)) == {"pt"}
    opened, closed = do.split("else_if", 1)
    assert f"has_variable = {pc.ROW_VAR}$pt$" in opened and f"remove_variable = {pc.ROW_VAR}$pt$" in opened
    assert "is_opened = no" in opened and f"add_to_variable_list = {{ name = {pc.OPEN_LIST} " in opened
    assert f"remove_list_variable = {{ name = {pc.CLOSE_LIST} " in opened
    assert f"set_variable = {pc.ROW_VAR}$pt$" in closed and "is_opened = no" not in closed
    assert f"add_to_variable_list = {{ name = {pc.CLOSE_LIST} " in closed
    assert f"remove_list_variable = {{ name = {pc.OPEN_LIST} " in closed
    building = _block(_triggers(), "pp_row_building")
    assert set(re.findall(r"\$(\w+)\$", building)) == {"pt"}
    for line in ("owner ?= scope:pp_row_c", "building_pop_type = $pt$", "any_production_method_of_building"):
        assert line in building, line
    text = _read(MOD / "main_menu/localization/english/pp_location_plan_l_english.yml")
    for key in ("PP_ROW_LOCK_CLOSE", "PP_ROW_LOCK_OPEN", "PP_ROW_LOCK_DESC"):
        assert f"  {key}: " in text and f"'{key}'" in button or f'"{key}"' in button, key
