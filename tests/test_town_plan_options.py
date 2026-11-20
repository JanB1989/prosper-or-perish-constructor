"""The plan options of the Construction Plan's Plans tab (2026-11-20, town_plan_options.py, the script side in
town_plans.py "Plan options"): every value and scripted GUI of the contract exists, the values read only variables,
no variable set reads as the behaviour before the options existed, and the pass's checks cost nothing at the defaults."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import location_profiles as lpf
from prosper_or_perish_constructor import town_plan_options as tpo
from prosper_or_perish_constructor import town_plans as tp
from prosper_or_perish_constructor.script_eval import ScriptEval
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _code(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", _read(path))


def _block(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, f"{name} missing"
    return match.group(1)


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return vanilla_root(ROOT, PROJECT)


@pytest.fixture(scope="module")
def plans(vanilla: Path) -> list[tp.Plan]:
    return tp.plans(ROOT, PROJECT, MOD, vanilla)


@pytest.fixture(scope="module")
def goods(plans: list[tp.Plan]) -> list[str]:
    return [plan.key for plan in plans if plan.key not in tp.EXTRA_PLANS]


class _Eval(ScriptEval):
    """Country variables as ``var:<name>`` in ctx["game"]; province / market scopes and their modifier tests."""

    def single(self, key, op, v, safe, ctx):
        if key == "has_variable":
            return f"var:{v}" in ctx.get("game", {})
        if key in ("has_province_modifier", "has_country_modifier"):
            return str(v) in ctx.get("location_modifiers", set())
        return super().single(key, op, v, safe, ctx)

    def op(self, key, v, ctx, result):
        if key in ("province", "market"):
            scope = ctx.get(key)
            return self.block(v, scope, result) if scope is not None else result
        return super().op(key, v, ctx, result)


@pytest.fixture(scope="module")
def evaluator() -> _Eval:
    return _Eval(MOD)


def test_every_value_and_gui_of_the_contract_exists(goods: list[str]) -> None:
    values = _code(MOD / tp.VALUES)
    defined = set(re.findall(r"^(\w+) = \{", values, re.MULTILINE))
    missing = sorted(tpo.value_names(goods) - defined)
    assert not missing, missing
    guis = _code(MOD / tp.SETTINGS_GUIS)
    for name in tpo.gui_names():
        body = _block(guis, name)
        assert "scope = country" in body and "is_valid = {\n\t\tis_ai = no\n\t}" in body, name
    # the kinds: a switch has one GUI, a cycle one, a stepper two (+ reset per plan)
    for option in tpo.OPTIONS:
        count = {"switch": 1, "cycle": 1, "stepper": 3 if option.per_plan else 2}[option.kind]
        assert len(option.guis) == count, option.key
    # the switches' GUIs flip exactly their variable (pp_cplan_flip: set = off)
    for value, var, gui in tp.OPTION_SWITCHES:
        assert f"pp_cplan_flip = {{ var = {var} }}" in _block(guis, gui), gui
        option = next(o for o in tpo.OPTIONS if o.value == value)
        assert option.kind == "switch" and option.guis == (gui,)


def test_the_window_values_only_read_variables(goods: list[str]) -> None:
    """A visible widget evaluates them every frame: no modifier, no scope, no list walk."""
    values = _code(MOD / tp.VALUES)
    names = tpo.value_names(goods)
    for name in sorted(names):
        body = _block(values, name)
        for pattern in (r"modifier:", r"scope:", r"\b(any|every|ordered)_", r"\?=", r"\b(owner|market|province) ="):
            assert not re.search(pattern, body), (name, pattern)
        for ref in re.findall(r"value = ([a-z_][a-z_0-9]*)\s", body):
            assert ref in names, (name, ref)  # a plan's value may read the all-plans one


def test_defaults_read_as_before(evaluator: _Eval, goods: list[str]) -> None:
    game: dict = {}
    for option in tpo.OPTIONS:
        keys = [tpo.ALL, "lumber"] if option.per_plan else [""]
        for key in keys:
            value = evaluator.value(option.value + key, {"game": game})
            if option.kind == "switch":
                assert value == 1, option.key
            elif option.kind == "cycle":
                assert value == 1, option.key  # the Taverns: while the store is short, the rule before the options
            else:
                assert value == 0 and evaluator.value(option.set_value + key, {"game": game}) == 0, option.key
            if option.per_plan and key != tpo.ALL:
                assert evaluator.value(option.own_value + key, {"game": game}) == 0
    for plan in [*goods, "food", "trade"]:
        assert evaluator.value(f"{tp.EFF_LINE_PREFIX}{plan}", {"game": game}) == 0, plan


def test_lowest_production_efficiency_values(evaluator: _Eval) -> None:
    def ev(name: str, game: dict) -> float:
        return evaluator.value(name, {"game": game})

    assert tp.EFF_NONE == len(tp.EFF_STEPS) + 1
    for index, pct in enumerate(tp.EFF_STEPS, 1):
        assert ev("pp_tplan_eff_pct_all", {"var:pp_tplan_effv_all": index}) == pct
        assert ev("pp_tplan_eff_set_all", {"var:pp_tplan_effv_all": index}) == 1
        assert ev("pp_tplan_eff_pct_lumber", {"var:pp_tplan_effv_lumber": index}) == pct
        assert ev("pp_tplan_eff_line_lumber", {"var:pp_tplan_effv_lumber": index}) == pct + tp.EFF_OFFSET
    zero = tp.EFF_STEPS.index(0) + 1
    # a line of 0 % is a line (set 1), the window shows it as 0 %
    assert ev("pp_tplan_eff_set_lumber", {"var:pp_tplan_effv_all": zero}) == 1
    assert ev("pp_tplan_eff_line_lumber", {"var:pp_tplan_effv_all": zero}) == tp.EFF_OFFSET
    # a plan follows all plans, its own wins, its own "none" is none
    assert ev("pp_tplan_eff_pct_lumber", {"var:pp_tplan_effv_all": 5}) == tp.EFF_STEPS[4]
    assert ev("pp_tplan_eff_pct_lumber", {"var:pp_tplan_effv_all": 5, "var:pp_tplan_effv_lumber": 2}) == tp.EFF_STEPS[1]
    own_none = {"var:pp_tplan_effv_all": 5, "var:pp_tplan_effv_lumber": tp.EFF_NONE}
    assert ev("pp_tplan_eff_set_lumber", own_none) == 0 and ev("pp_tplan_eff_pct_lumber", own_none) == 0
    assert ev("pp_tplan_eff_own_lumber", own_none) == 1 and ev("pp_tplan_eff_line_lumber", own_none) == 0
    assert ev("pp_tplan_eff_line_food", {"var:pp_tplan_effv_all": 5}) == 0  # food and trade have no line
    # one step from scope:pp_tplan_cur: none (0) below the first step, never above the last
    n = len(tp.EFF_STEPS)
    up = lambda cur: ev("pp_tplan_eff_next_up", {"scope:pp_tplan_cur": cur})  # noqa: E731
    down = lambda cur: ev("pp_tplan_eff_next_down", {"scope:pp_tplan_cur": cur})  # noqa: E731
    assert up(0) == 1 and up(n) == n and down(1) == 0 and down(0) == 0 and down(5) == 4


def test_lasting_production_efficiency_here(evaluator: _Eval, vanilla: Path) -> None:
    amounts = tp.eff_short_lived_amounts(MOD, vanilla)
    assert {scope: [name for name, _ in found] for scope, found in amounts.items()} == {
        scope: list(names) for scope, names in tp.EFF_SHORT_LIVED.items()}
    assert all(amount != 0 for found in amounts.values() for _, amount in found)
    assert dict(amounts["location"])["raised_levies"] == -0.05  # PP's own value (pp_location_modifier_adjustments)
    ctx = {"game": {}, "modifiers": {"local_production_efficiency": 0.12},
           "owner": {"game": {}, "modifiers": {"global_production_efficiency": 0.05}, "location_modifiers": set()},
           "location_modifiers": set(), "province": {"game": {}, "location_modifiers": set()}}
    assert evaluator.value(tp.EFF_HERE, ctx) == pytest.approx(tp.EFF_OFFSET + 17)
    # raised levies (-0.05) and a five-year province modifier (+0.05) are taken out
    ctx["location_modifiers"] = {"raised_levies"}
    ctx["province"] = {"game": {}, "location_modifiers": {"province_innovative_tooling_techniques_modifier"}}
    ctx["owner"]["location_modifiers"] = {"calvinist_work_ethic"}
    assert evaluator.value(tp.EFF_HERE, ctx) == pytest.approx(tp.EFF_OFFSET + 17 + 5 - 5 - 2.5)


def test_the_pass_reads_the_line_only_when_one_is_set() -> None:
    hand = _code(MOD / lpf.HAND_EFFECTS)
    turn = _block(hand, "pp_lplan_location_turn")
    assert (f"limit = {{ scope:pp_cplan_country = {{ has_variable = {tp.EFF_SOME_VAR} }} }}\n"
            f"\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_effh value = {tp.EFF_HERE} }}") in turn
    low = _block(_code(MOD / tp.TRIGGERS), tp.EFF_LOW_TRIGGER)
    # the guard first: nothing else is evaluated while no line is set anywhere
    assert low.strip().startswith(f"scope:pp_cplan_country = {{\n\t\thas_variable = {tp.EFF_SOME_VAR}")
    assert f"{tp.EFF_LINE_PREFIX}$g$ > scope:pp_tplan_effh" in low
    mark = _block(hand, "pp_lplan_mark")
    # building go: below the line the plan starts nothing (fail 103.25 -> state 15), before its target runs
    check = mark.index("pp_tplan_eff_low = { g = $g$ }\n\t\t\t\t}\n\t\t\t\tpp_lprof_fail = { r = 103.25 }")
    assert mark.index("pp_lprof_open = yes") < check < mark.index("limit = { NOT = { has_variable = pp_lprof_st } }\n\t\t\t\t$do$ = yes")
    # measuring go: below the line nothing is offered
    assert "limit = { NOT = { pp_tplan_eff_low = { g = $g$ } } }\n\t\t\t\t$do$ = yes" in mark
    # the refresh keeps the guard in step with every line
    effects = _code(MOD / tp.EFFECTS)
    assert _block(effects, "pp_tplan_eff_key").rstrip().endswith("pp_tplan_eff_refresh = yes")
    assert _block(effects, "pp_tplan_eff_key_reset").rstrip().endswith("pp_tplan_eff_refresh = yes")
    refresh = _block(effects, "pp_tplan_eff_refresh")
    assert f"set_variable = {{ name = {tp.EFF_SOME_VAR} value = yes }}" in refresh
    assert f"has_variable = {tp.eff_var('lumber')} var:{tp.eff_var('lumber')} < {tp.EFF_NONE - 0.5:g}" in refresh


def test_states_15_and_16() -> None:
    assert lpf.FAIL_STATE[tp.FAIL_EFF] == 15 and lpf.FAIL_STATE[tp.FAIL_SETTINGS] == 16
    loc = dict(re.findall(r'^  ([A-Z0-9_]+): "(.*)"$', _read(MOD / lpf.LOC), re.MULTILINE))
    assert "[production_efficiency|e]" in loc["PP_LPROF_ST_15"]
    for n in (15, 16):
        assert not re.search(r"\d", loc[f"PP_LPROF_ST_{n}"]), n
    # 11 covers the switched-off rank raise
    assert "plan options" in loc["PP_LPROF_ST_11"]


def test_raise_switch(plans: list[tp.Plan]) -> None:
    effects = _code(MOD / tp.EFFECTS)
    for plan in plans:
        if not plan.raises:
            continue
        body = _block(effects, plan.do)
        off = body.index(f"limit = {{ scope:pp_cplan_country = {{ has_variable = {tp.RAISE_OFF_VAR} }} }}\n"
                         f"\t\t\t\t\tpp_lprof_fail = {{ r = {tp.FAIL_RANK} }}" if plan.key == "trade" else
                         f"limit = {{ scope:pp_cplan_country = {{ has_variable = {tp.RAISE_OFF_VAR} }} }}\n"
                         f"\t\t\t\tpp_lprof_fail = {{ r = {tp.FAIL_RANK} }}")
        assert off < body.index("pp_tplan_raise = yes"), plan.key
    assert "pp_tplan_raise = yes" not in _block(effects, "pp_tplan_do_food")


def test_food_options(evaluator: _Eval) -> None:
    effects = _code(MOD / tp.EFFECTS)
    turn = _block(effects, "pp_tplan_do_food")
    # the store limit first, read only while it is set; at or above it nothing happens (state 16)
    store = turn[:turn.index("limit = { scope:pp_tplan_hold < 0.5 }")]
    assert f"limit = {{ scope:pp_cplan_country = {{ has_variable = {tp.FOOD_STORE_VAR} }} }}" in store
    assert "limit = { pp_location_stored_months >= scope:pp_tplan_lim }" in store
    assert f"pp_lprof_fail = {{ r = {tp.FAIL_SETTINGS:g} }}" in store
    # the farms only while switched on; the kitchens' and taverns' targets by the switches and the Taverns' state
    assert (f"limit = {{ scope:pp_cplan_country = {{ NOT = {{ has_variable = {tp.FOOD_FARMS_OFF_VAR} }} }} }}\n"
            f"\t\t\tpp_lprof_t_{tp.FOOD_FARMS_TARGET} = yes") in turn
    assert f"pp_lprof_t_{tp.FOOD_TAVERNS_TARGET} = yes" in turn
    assert turn.count(f"var:{tp.FOOD_TAVERNS_VAR} > {tp.FOOD_TAVERNS_ALWAYS - 0.5:g}") == 2
    # nothing tried at all (every part switched off): state 16
    assert "else = {\n\t\t\t\t\tremove_variable = pp_lprof_fail\n\t\t\t\t\tpp_lprof_fail = { r = 102.75 }" in turn
    found = lpf.targets(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT))[0]
    config = cp.load_config(PROJECT)
    assert [c.name for c in found[tp.FOOD_TAVERNS_TARGET]] == list(config.taverns)
    assert re.search(rf"^pp_lprof_t_{tp.FOOD_TAVERNS_TARGET} = \{{", _code(MOD / lpf.EFFECTS), re.MULTILINE)

    def ev(name: str, game: dict) -> float:
        return evaluator.value(name, {"game": game})

    # Taverns: unset = 1 (while short), the cycle: 1 -> 2 (always, var 3) -> 0 (never, var 1) -> 1 (unset)
    assert ev("pp_tplan_food_taverns_n", {f"var:{tp.FOOD_TAVERNS_VAR}": tp.FOOD_TAVERNS_ALWAYS}) == 2
    assert ev("pp_tplan_food_taverns_n", {f"var:{tp.FOOD_TAVERNS_VAR}": tp.FOOD_TAVERNS_NEVER}) == 0
    cycle = _block(effects, "pp_tplan_food_taverns_next")
    assert cycle.index(f"value = {tp.FOOD_TAVERNS_ALWAYS} }}") < cycle.index(f"value = {tp.FOOD_TAVERNS_NEVER} }}") < cycle.index(
        f"remove_variable = {tp.FOOD_TAVERNS_VAR}")
    for index, months in enumerate(tp.FOOD_STORE_STEPS, 1):
        assert ev("pp_tplan_food_store_months", {f"var:{tp.FOOD_STORE_VAR}": index}) == months
        assert ev("pp_tplan_food_store_set", {f"var:{tp.FOOD_STORE_VAR}": index}) == 1
    n = len(tp.FOOD_STORE_STEPS)
    up = lambda cur: ev("pp_tplan_food_store_next_up", {"scope:pp_tplan_cur": cur})  # noqa: E731
    down = lambda cur: ev("pp_tplan_food_store_next_down", {"scope:pp_tplan_cur": cur})  # noqa: E731
    assert up(n) == n + 1 and up(n + 1) == n + 1 and down(n + 1) == n and down(1) == 1  # n + 1 = always (unset)
    step = _block(effects, "pp_tplan_food_store_step")
    assert f"limit = {{ scope:pp_tplan_new > {n + 0.5:g} }}\n\t\tremove_variable = {tp.FOOD_STORE_VAR}" in step


def test_trade_options(evaluator: _Eval, vanilla: Path) -> None:
    config = cp.load_config(PROJECT)
    database = cp._database(MOD, vanilla, cp.BUILDING_TYPES)
    # every building of the trade plan adds merchant capacity: the capacity-in-use line holds the whole plan
    for name in config.trade_plan:
        assert re.search(r"\blocal_merchant_capacity\s*=", database[name][1]), name
    groups = lpf.trade_groups(config.trade_plan, database)
    assert list(groups) == [target for target, _ in tp.TRADE_GROUPS]
    assert sorted(n for names in groups.values() for n in names) == sorted(config.trade_plan)
    assert groups["trade_market"] == ["marketplace", "merchants_quarters", "grand_marketplace", "commerce_center"]
    assert groups["trade_port"] == ["port_authority"]
    effects = _code(MOD / tp.EFFECTS)
    generated = _code(MOD / lpf.EFFECTS)
    for target, names in groups.items():
        body = _block(generated, f"pp_lprof_t_{target}")
        fresh = body[body.index("\n\telse = {"):]
        assert re.findall(r"pp_lprof_start = \{ type = (\w+) ", fresh) == names, target  # the plan's start order
    turn = _block(effects, "pp_tplan_do_trade")
    # the use line first, read only while set: below it nothing, no rank raise either (state 16)
    assert turn.index(f"has_variable = {tp.TRADE_USE_VAR}") < turn.index("limit = { scope:pp_tplan_hold < 0.5 }") < turn.index(
        "pp_tplan_raise = yes")
    assert f"limit = {{ {tp.TRADE_USE_HERE} < scope:pp_tplan_lim }}" in turn
    # every group on (the default): the whole list as before; a group off: the groups one after the other
    default = turn.index("pp_lprof_t_trade_category = yes")
    assert turn.index("NOR = {") < default < turn.index(f"{tp.TRADE_SPLIT_EFFECT} = yes")
    split = _block(effects, tp.TRADE_SPLIT_EFFECT)
    order = [split.index(f"has_variable = {var} }} }}") for _, var in tp.TRADE_GROUPS]
    assert order == sorted(order)
    assert "pp_lprof_fail = { r = 102.75 }" in split  # every group off

    def ev(name: str, ctx: dict) -> float:
        return evaluator.value(name, ctx)

    for index, pct in enumerate(tp.TRADE_USE_STEPS, 1):
        assert ev("pp_tplan_trade_use_pct", {"game": {f"var:{tp.TRADE_USE_VAR}": index}}) == pct
    used, cap = "used_merchant_capacity(scope:pp_cplan_country)", "merchant_capacity(scope:pp_cplan_country)"
    assert ev(tp.TRADE_USE_HERE, {"game": {}, "market": {"game": {used: 3, cap: 4}}}) == 75
    assert ev(tp.TRADE_USE_HERE, {"game": {}, "market": {"game": {used: 0, cap: 0}}}) == 100  # none there yet
    n = len(tp.TRADE_USE_STEPS)
    up = lambda cur: ev("pp_tplan_trade_use_next_up", {"game": {"scope:pp_tplan_cur": cur}})  # noqa: E731
    down = lambda cur: ev("pp_tplan_trade_use_next_down", {"game": {"scope:pp_tplan_cur": cur}})  # noqa: E731
    assert up(0) == 1 and up(n) == n and down(1) == 0 and down(0) == 0


def test_player_text(vanilla: Path) -> None:
    concepts: set[str] = set()
    for root in (vanilla / "game/main_menu/common/game_concepts", MOD / "main_menu/common/game_concepts"):
        for path in root.glob("*.txt"):
            text = _code(path)
            for name, body in re.findall(r"^(\w+) = \{(.*?)^\}", text, re.MULTILINE | re.DOTALL):
                concepts.add(name)
                for alias in re.findall(r"alias = \{([^}]*)\}", body):
                    concepts |= set(alias.split())
    database = cp._database(MOD, vanilla, cp.BUILDING_TYPES)
    for option in tpo.OPTIONS:
        text = " ".join((option.label, option.tooltip, *option.states, *option.step_tooltips))
        for concept in re.findall(r"\[(\w+)\|e\]", text):
            assert concept in concepts, (option.key, concept)
        for building in re.findall(r"ShowBuildingTypeName\('(\w+)'\)", text):
            assert building in database, (option.key, building)
        plain = re.sub(r"\[[^\]]*\]", "", text).replace("{value}", "")
        assert not re.search(r"\d", plain), option.key  # numbers come from the script values
