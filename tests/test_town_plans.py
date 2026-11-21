"""Location plans (src/prosper_or_perish_constructor/town_plans.py, 2026-11-19): one plan per good with a forced goods
target plus food and trade; the Construction Plan's Locations pass builds toward every held plan. Since 2026-11-21 a
plan is the location variable pp_tplan_p_<plan> (until then a town right pp_plan_<plan>)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_country as cpc
from prosper_or_perish_constructor import location_profiles as lpf
from prosper_or_perish_constructor import staple_foods
from prosper_or_perish_constructor import town_plans as tp
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


def test_built_mod_is_in_step(vanilla: Path) -> None:
    assert tp.apply(ROOT, PROJECT, MOD, vanilla, write=False).files_changed == 0, "run ppc finalize"


def test_one_plan_per_forced_good_plus_food_and_trade(plans: list[tp.Plan], vanilla: Path) -> None:
    found, _ = lpf.targets(ROOT, PROJECT, MOD, vanilla)
    goods = [good for good in lpf.target_goods(ROOT, PROJECT) if found.get(good)]
    assert [plan.key for plan in plans] == goods + ["food", "trade"]
    assert len(goods) == 75 and "fur" not in goods  # fur: no producer
    for plan in plans:
        assert re.fullmatch(r"[a-z_]+", plan.key) and plan.var == tp.plan_var(plan.key) == f"pp_tplan_p_{plan.key}"
        assert plan.candidates == tuple(c.name for c in found[plan.target]), plan.key
    assert {plan.key: plan.target for plan in plans if plan.key in tp.EXTRA_PLANS} == {"food": "food", "trade": "trade_category"}


ON_ACTION = MOD / "in_game/common/on_action/pp_construction_plan.txt"
PLAN_EFFECTS = MOD / "in_game/common/scripted_effects/pp_location_plan.txt"
PLAN_RIGHT = re.compile(r"town_rights_type:pp_plan_|ShowTownRightsName\('pp_plan_|^\s*pp_plan_\w+\s*[:=]",
                        re.MULTILINE)


def test_no_plan_right_is_left(plans: list[tp.Plan], vanilla: Path) -> None:
    """2026-11-21 (Jan: "We just use our plans, and the plans apply the relevant town rights if the setting is turned
    on"): a plan is no town right any more. No file of the mod defines, grants, tests or names a right pp_plan_*, the
    pass removed the former rights file, its text and its icons, and the rule's rights database has none."""
    found = []
    for path in sorted(MOD.rglob("*")):
        if path.suffix in {".txt", ".gui", ".yml"} and path.is_file():
            if PLAN_RIGHT.search(_read(path)):
                found.append(path.relative_to(MOD).as_posix())
    assert found == []
    assert tp.stale_paths(MOD) == []
    for relative in tp.STALE_FILES:
        assert not (MOD / relative).exists(), relative
    assert not list((MOD / tp.STALE_ICONS).glob(tp.STALE_ICON_PATTERN))
    rights, _off, _ = cpc.read_rights(MOD, vanilla)
    assert not any(right.key.startswith("pp_plan_") for right in rights)
    for gone in ("PLAN_PREFIX", "right_key", "is_plan_right", "RIGHTS", "LOC", "ICONS", "RIGHT_BODY", "render_rights",
                 "render_values", "ON_VALUE_PREFIX"):
        assert not hasattr(tp, gone), gone
    assert not hasattr(tp.Plan, "right") and not hasattr(tp.Plan, "on_value")


def test_stale_paths_finds_what_the_plan_rights_left(tmp_path: Path) -> None:
    """2026-11-21: the pass deletes the former rights file, its English text and every pp_plan_*.dds of the town
    rights' icons, and nothing else in that folder."""
    for relative in tp.STALE_FILES:
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text("x", encoding="utf-8")
    icons = tmp_path / tp.STALE_ICONS
    icons.mkdir(parents=True)
    for name in ("pp_plan_wheat.dds", "pp_plan_food.dds", "pp_wheat_charter.dds"):
        (icons / name).write_bytes(b"DDS ")
    found = {path.relative_to(tmp_path).as_posix() for path in tp.stale_paths(tmp_path)}
    assert found == {relative.as_posix() for relative in tp.STALE_FILES} | {
        (tp.STALE_ICONS / name).as_posix() for name in ("pp_plan_wheat.dds", "pp_plan_food.dds")}
    assert tp.stale_paths(tmp_path / "nothing") == []


def test_held_triggers(plans: list[tp.Plan]) -> None:
    """2026-11-21: pp_tplan_held asks one variable (pp_tplan_any, kept in step by the flip); pp_tplan_held_scan asks
    every plan's marker, each once, in the plans' order (the flip asks it after a plan went)."""
    triggers = _code(MOD / tp.TRIGGERS)
    held = _block(triggers, tp.HELD_TRIGGER)
    assert held.split() == ["has_variable", "=", tp.ANY_VAR] and tp.ANY_VAR == "pp_tplan_any"
    scan = _block(triggers, tp.HELD_SCAN_TRIGGER)
    assert scan.strip().startswith("OR = {")
    assert re.findall(r"has_variable = (\w+)", scan) == [plan.var for plan in plans]
    assert "town_rights" not in triggers
    # no on-values any more: the values file is the header and the settings' values
    values = _read(MOD / tp.VALUES)
    assert values.startswith("# Generated by ppc finalize (town_plans.py)") and "pp_tplan_on_" not in values


def test_strip_takes_every_plan_and_its_traces(plans: list[tp.Plan]) -> None:
    """2026-11-21: pp_tplan_strip (an owner change, the Locations look's sweep) removes every plan's marker, state and
    payback, the mark that the location holds a plan, the workers mark, the plan that built last, and why a charter
    waits (only when set). The list of planned locations is the caller's."""
    strip = _block(_code(MOD / tp.EFFECTS), tp.STRIP_EFFECT)
    removed = re.findall(r"remove_variable = (\w+)", strip)
    for plan in plans:
        for name in (plan.var, f"pp_lplan_st_{plan.suffix}", f"pp_lplan_est_{plan.suffix}"):
            assert removed.count(name) == 1, name
    for name in (tp.ANY_VAR, "pp_lplan_wk", "pp_lplan_last", "pp_tplan_cwait"):
        assert removed.count(name) == 1, name
    assert len(removed) == 3 * len(plans) + 4
    assert "limit = { has_variable = pp_tplan_cwait }\n\t\tremove_variable = pp_tplan_cwait" in strip
    assert tp.LOCS_LIST not in strip and "town_rights" not in strip


def test_owner_change_strips_the_plans() -> None:
    """2026-11-21: a location that changes owner keeps no plan (the plan rights went by kept_at_conquest = no). The
    game's on_location_changed_owner calls pp_tplan_owner_changed, only for a location that holds a plan; its effect
    takes the location off the previous owner's (scope:loser) list and that owner's saving for it, then strips it."""
    actions = _code(ON_ACTION)
    changed = _block(actions, "on_location_changed_owner")
    assert changed.split() == ["on_actions", "=", "{", "pp_tplan_owner_changed", "}"]
    action = _block(actions, "pp_tplan_owner_changed")
    assert "trigger = {\n\t\thas_variable = pp_tplan_any\n\t}" in action
    assert "effect = {\n\t\tpp_tplan_owner_changed_effect = yes\n\t}" in action
    effect = _block(_code(PLAN_EFFECTS), "pp_tplan_owner_changed_effect")
    assert effect.index("limit = { pp_tplan_held = yes }") < effect.index("save_temporary_scope_as = pp_tplan_lost_l")
    loser = effect[effect.index("scope:loser ?= {"):effect.index(f"{tp.STRIP_EFFECT} = yes")]
    assert effect.index("save_temporary_scope_as = pp_tplan_lost_l") < effect.index("scope:loser ?= {")
    assert f"remove_list_variable = {{ name = {tp.LOCS_LIST} target = scope:pp_tplan_lost_l }}" in loser
    assert "scope:pp_tplan_lost_l = var:pp_cplan_save_loc_105" in loser
    assert "pp_cplan_save_clear = { why = 105 }" in loser
    assert "pp_lprof_any_refresh = yes" in loser
    assert effect.count(f"{tp.STRIP_EFFECT} = yes") == 1


def test_the_pass_keys_on_the_held_plan_and_forces_it(plans: list[tp.Plan]) -> None:
    hand = _code(MOD / lpf.HAND_EFFECTS)
    effects = _code(MOD / lpf.EFFECTS)
    mark = _block(hand, "pp_lplan_mark")
    assert "limit = { has_variable = pp_tplan_p_$g$ }" in mark
    assert "pp_lplan_$v$" not in mark.replace("pp_lplan_st_$v$", "").replace("pp_lplan_est_$v$", "")
    marks = _block(effects, "pp_lplan_location_marks")
    for plan in plans:
        assert f"pp_lplan_mark = {{ v = g_{plan.key} g = {plan.key} do = {plan.do} " in marks, plan.key
    # forced: no payback limit, no market limit, inside the location's turn
    turn = _block(hand, "pp_lplan_location_turn")
    assert turn.index("name = pp_cplan_forced value = 1") < turn.index("pp_lplan_location_marks = yes")
    assert "save_temporary_scope_value_as = { name = pp_lprof_pb value = 1000000 }" in turn
    # a location holding only plans gets its turn: the gather walks the country's list of planned locations
    # (2026-11-21), and its turn runs its plans
    gather = _block(hand, "pp_lprof_gather")
    assert f"variable = {tp.LOCS_LIST}" in gather and "pp_tplan_held = yes" in gather
    assert "locations_with_town_rights" not in gather
    location = _block(hand, "pp_lprof_location_turn")
    assert "pp_tplan_held = yes" in location
    has = _block(_code(MOD / lpf.TRIGGERS), "pp_lprof_has_locations")
    assert has.split() == ["any_in_list", "=", "{", "variable", "=", tp.LOCS_LIST, "owner", "?=", "root",
                           "pp_tplan_held", "=", "yes", "}"]
    # the state variables stay the marks' (the GUI reads pp_lplan_st_g_<plan>)
    assert "pp_lprof_finish = { st = pp_lplan_st_$v$ est = pp_lplan_est_$v$ }" in mark


def test_food_and_trade_targets(vanilla: Path) -> None:
    found, categories = lpf.targets(ROOT, PROJECT, MOD, vanilla)
    food = {c.name for c in found[tp.FOOD_TARGET]}
    config = cp.load_config(PROJECT)
    assert set(config.kitchens) | set(config.taverns) <= food
    staples = set(staple_foods.staple_foods())
    for good in ("wheat", "fish", "livestock", "fruit"):
        assert good in staples and {c.name for c in found[good]} <= food, good
    for name in ("wheat_farm", "furniture_mill"):
        assert (name in food) == (name == "wheat_farm"), name
    effects = _code(MOD / lpf.EFFECTS)
    # the whole food list is the plan's buildings, never run; its turn runs the farms, then the kitchens
    assert not re.search(r"^pp_lprof_t_food = \{", effects, re.MULTILINE)
    farms = [c.name for c in found[tp.FOOD_FARMS_TARGET]]
    assert set(farms) == food - set(config.kitchens) - set(config.taverns)
    assert {c.name for c in found[tp.FOOD_KITCHENS_TARGET]} == set(config.kitchens)
    assert {c.name for c in found[tp.FOOD_KITCHENS_TAVERNS_TARGET]} == set(config.kitchens) | set(config.taverns)
    for key in (tp.FOOD_FARMS_TARGET, tp.FOOD_KITCHENS_TARGET, tp.FOOD_KITCHENS_TAVERNS_TARGET):
        assert re.search(rf"^pp_lprof_t_{key} = \{{", effects, re.MULTILINE), key
    assert [c.name for c in found[tp.TRADE_TARGET]] and set(categories[tp.TRADE_TARGET]) >= {"marketplace"}
    assert re.search(r"^pp_lprof_t_trade_category = \{", effects, re.MULTILINE)


def test_food_turn_farms_then_kitchens(plans: list[tp.Plan]) -> None:
    """2026-11-20, Jan: the food plan builds farms first, kitchens second, a Tavern only while the store is short."""
    food = next(plan for plan in plans if plan.key == "food")
    assert food.do == "pp_tplan_do_food" and not food.raises
    turn = _block(_code(MOD / tp.EFFECTS), food.do)
    farms = turn.index(f"pp_lprof_t_{tp.FOOD_FARMS_TARGET} = yes")
    gate = turn.index("if = {", farms)
    kitchens = turn.index(f"pp_lprof_t_{tp.FOOD_KITCHENS_TARGET} = yes")
    taverns = turn.index(f"pp_lprof_t_{tp.FOOD_KITCHENS_TAVERNS_TARGET} = yes")
    assert farms < gate < taverns < kitchens
    # the kitchens only where the farms have nothing to do (101 full / 102 cannot be built), not while measuring
    limit = turn[gate:taverns]
    for check in ("NOT = { has_variable = pp_lprof_st }", "NOT = { pp_lplan_measuring = yes }",
                  "NOT = { has_variable = pp_lprof_fail }", "var:pp_lprof_fail < 102.25"):
        assert check in limit, check
    # the taverns only while the province's store is short, by the food rule's own line (the plan closer's trigger),
    # unless the plan option for Taverns is set (tests/test_town_plan_options.py)
    with_taverns = turn[turn.rindex("if = {", 0, taverns):taverns]
    assert (f"scope:pp_cplan_country = {{ NOT = {{ has_variable = {tp.FOOD_TAVERNS_VAR} }} }}\n"
            "\t\t\t\t\t\t\tprovince ?= { NOT = { pp_pclose_store_ok = yes } }") in with_taverns
    assert f"else_if = {{\n\t\t\t\tlimit = {{ scope:pp_cplan_country = {{ NOT = {{ has_variable = {tp.FOOD_KITCHENS_OFF_VAR} }} }} }}\n\t\t\t\tpp_lprof_t_food_kitchens = yes" in turn
    store = _block(_code(MOD / "in_game/common/scripted_triggers/pp_plan_closer.txt"), "pp_pclose_store_ok")
    assert "pp_cplan_food_in_a_year >= pp_cplan_hungry_months" in store
    # the kitchens start clean; nothing to do in either: "nothing to build" (101) when the farms or kitchens are full
    assert turn.index("remove_variable = pp_lprof_fail") < taverns and turn.index("remove_variable = pp_lprof_best") < taverns
    end = turn[kitchens:]
    assert "scope:pp_tplan_ff < 101.5" in end and "pp_lprof_fail = { r = 101 }" in end and "pp_lprof_fail = { r = 102 }" in end
    # the farm start picks the best return here (the food rule's measure); the kitchens the cheapest
    effects = _code(MOD / lpf.EFFECTS)
    farm_target = _block(effects, f"pp_lprof_t_{tp.FOOD_FARMS_TARGET}")
    assert "how = roi" in farm_target and "how = cost" not in farm_target
    values = _read(MOD / cp.VALUES)
    for name in re.findall(r"pp_lprof_start = \{ type = (\w+) ", farm_target):
        assert f"\npp_cplan_farm_roi_{name} = {{" in values, name
    assert "how = roi" not in _block(effects, f"pp_lprof_t_{tp.FOOD_KITCHENS_TAVERNS_TARGET}")
    roi = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_consider_roi")
    assert "value = { value = pp_cplan_farm_roi_$type$ add = 10000 }" in roi and "var:pp_lprof_best < scope:pp_lprof_key" in roi
    # the construction stays the Locations group's (why 105, its purse): the same pick and build path
    assert "pp_lprof_build_known = yes" in _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_start_pick")


def test_trade_plan_builds_the_trade_carriers(vanilla: Path) -> None:
    """2026-11-20, Jan: the trade plan's buildings are the configured list, started in its order (the first that can
    start); no Hired Labor Yard, Smuggler's Cove or unique building."""
    config = cp.load_config(PROJECT)
    assert config.trade_plan[:5] == ("marketplace", "merchants_quarters", "grand_marketplace", "commerce_center",
                                     "port_authority")
    for name in ("hired_labor_yard", "smuggler_cove", "al_qaysariyya_market"):
        assert name not in config.trade_plan, name
    found, _ = lpf.targets(ROOT, PROJECT, MOD, vanilla)
    names = {c.name for c in found[tp.TRADE_TARGET]}
    assert names == set(config.trade_plan) & names and "marketplace" in names and "hired_labor_yard" not in names
    target = _block(_code(MOD / lpf.EFFECTS), "pp_lprof_t_trade_category")
    fresh = target[target.index("\n\telse = {"):]
    order = re.findall(r"pp_lprof_start = \{ type = (\w+) ", fresh)
    assert order == [name for name in config.trade_plan if name in names]
    # every start after the first waits for no pick: the first that can start wins
    assert fresh.count("limit = { NOT = { has_variable = pp_lprof_pick } }") == len(order) - 1
    assert "how = cost" in fresh and "how = roi" not in fresh


def test_targets_follow_the_tiers(vanilla: Path) -> None:
    """A standing older tier whose successor the country has researched is upgraded before anything grows (a target
    used to be stuck once only an obsolete tier stood)."""
    effects = _code(MOD / lpf.EFFECTS)
    wheat = _block(effects, "pp_lprof_t_wheat")
    standing = wheat[wheat.index("else_if"):wheat.index("\telse = {")]
    steps = re.findall(r"pp_lprof_upgrade = \{ old = (\w+) type = (\w+) ", standing)
    assert ("wheat_farm", "wheat_farmstead") in steps and ("wheat_rotations", "wheat_model_farm") in steps
    assert standing.index("pp_lprof_upgrade = {") < standing.index("pp_lprof_expand = {")
    pairs = lpf.upgrade_pairs(ROOT, PROJECT, MOD, vanilla)
    found, _ = lpf.targets(ROOT, PROJECT, MOD, vanilla)
    for older, successor in steps:
        assert (older, successor) in pairs
        assert {older, successor} <= {c.name for c in found["wheat"]}
    upgrade = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_upgrade")
    for check in ("NOT = { has_variable = pp_cplan_hit }", "NOT = { pp_lplan_measuring = yes }",
                  "building_type = building_type:$old$", "pp_cplan_country_upgradable = yes",
                  "scope:pp_cplan_country = { can_build_building = building_type:$type$ }",
                  "pp_cplan_goods_here_$demand$ = yes", "pp_lprof_build_known = yes"):
        assert check in upgrade, check
    assert "location_and_owner_can_build" not in upgrade  # the location's part refuses an obsolete tier, not an upgrade
    # the unit: pairs of other targets are not this target's steps
    a, b, c = (lpf.Candidate(name, "d", "std", 0.0) for name in ("a2", "a1", "a0"))
    assert lpf.target_upgrades([a, b, c], [("a0", "a1"), ("a1", "a2"), ("x", "a2")]) == [("a1", a), ("a0", b)]


def test_settings_values_for_every_plan(plans: list[tp.Plan]) -> None:
    """Plan settings (2026-11-20): the payback limit in years for all plans and for each plan (0 = any; a plan without
    its own setting follows the all-plans one), whether it has its own, and the four switches, as the GUI reads them."""
    from prosper_or_perish_constructor.script_eval import ScriptEval

    class _Vars(ScriptEval):
        def single(self, key, op, v, safe, ctx):
            if key == "has_variable":
                return f"var:{v}" in ctx.get("game", {})
            if key == "is_system_automated":
                return v in ctx.get("automated", set())
            return super().single(key, op, v, safe, ctx)

    values = _Vars(MOD)
    text = _code(MOD / tp.VALUES)
    keys = [tp.PB_ALL] + [plan.key for plan in plans]
    assert len(keys) == 78 and tp.PAYBACK_STEPS == (1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50) and tp.PB_ANY == 13
    for key in keys:
        assert re.search(rf"^{tp.pb_years_value(key)} = \{{", text, re.MULTILINE), key
    for plan in plans:
        assert re.search(rf"^{tp.pb_own_value(plan.key)} = \{{", text, re.MULTILINE), plan.key

    def years(key: str, game: dict) -> float:
        return values.value(tp.pb_years_value(key), {"game": game})

    assert years("all", {}) == 0  # default: any payback
    for index, step in enumerate(tp.PAYBACK_STEPS, 1):
        assert years("all", {"var:pp_tplan_pb_all": index}) == step
        assert years("lumber", {"var:pp_tplan_pb_lumber": index}) == step
    assert years("lumber", {}) == 0
    assert years("lumber", {"var:pp_tplan_pb_all": 7}) == 10  # follows all plans
    assert years("lumber", {"var:pp_tplan_pb_all": 7, "var:pp_tplan_pb_lumber": 2}) == 2  # its own wins
    assert years("lumber", {"var:pp_tplan_pb_all": 7, "var:pp_tplan_pb_lumber": tp.PB_ANY}) == 0  # its own "any"
    assert values.value(tp.pb_own_value("lumber"), {"game": {"var:pp_tplan_pb_lumber": 3}}) == 1
    assert values.value(tp.pb_own_value("lumber"), {"game": {"var:pp_tplan_pb_all": 3}}) == 0
    for name, var in ((tp.LOSS_VALUE, tp.LOSS_OK_VAR), (tp.STAFF_VALUE, tp.STAFF_OFF_VAR), (tp.ORDER_VALUE, tp.ORDER_BEST_VAR),
                      (tp.FREE_VALUE, tp.FREE_OFF_VAR), (tp.ALONE_VALUE, tp.ALONE_VAR),
                      (tp.RIGHTS_VALUE, tp.RIGHTS_OFF_VAR)):
        assert values.value(name, {"game": {}}) == 1, name  # the default
        assert values.value(name, {"game": {f"var:{var}": 1}}) == 0, name
    assert values.value(tp.CLOSE_VALUE, {"game": {}}) == 0
    assert values.value(tp.CLOSE_VALUE, {"game": {}, "automated": {"closebuildings"}}) == 1
    # one step from scope:pp_tplan_cur: longer past the last = any, shorter from any = the last, never below the first
    step = {d: (lambda cur, d=d: values.value(f"pp_tplan_pb_next_{d}", {"game": {"scope:pp_tplan_cur": cur}})) for d in ("up", "down")}
    assert step["up"](1) == 2 and step["up"](12) == 13 and step["up"](13) == 13
    assert step["down"](13) == 12 and step["down"](5) == 4 and step["down"](1) == 1


def test_settings_buttons_and_effects(plans: list[tp.Plan]) -> None:
    """The settings' scripted GUIs (country scope, player only) and the effects behind them, for every plan and all."""
    guis = _code(MOD / tp.SETTINGS_GUIS)
    names = [tp.PB_UP_GUI, tp.PB_DOWN_GUI, tp.PB_RESET_GUI, tp.TOGGLE_LOSS_GUI, tp.TOGGLE_STAFF_GUI,
             tp.TOGGLE_ORDER_GUI, tp.TOGGLE_CLOSE_GUI, tp.TOGGLE_FREE_GUI, tp.TOGGLE_ALONE_GUI, tp.TOGGLE_RIGHTS_GUI]
    # the plan options' buttons follow (tests/test_town_plan_options.py)
    assert re.findall(r"^(\w+) = \{", guis, re.MULTILINE)[:len(names)] == names
    for name in names:
        body = _block(guis, name)
        assert "scope = country" in body and "is_valid = {\n\t\tis_ai = no\n\t}" in body, name
    assert "pp_tplan_pb_key = { dir = up }" in _block(guis, tp.PB_UP_GUI)
    assert "pp_tplan_pb_key = { dir = down }" in _block(guis, tp.PB_DOWN_GUI)
    assert "pp_tplan_pb_key_reset = yes" in _block(guis, tp.PB_RESET_GUI)
    for gui, var in ((tp.TOGGLE_LOSS_GUI, tp.LOSS_OK_VAR), (tp.TOGGLE_STAFF_GUI, tp.STAFF_OFF_VAR),
                     (tp.TOGGLE_ORDER_GUI, tp.ORDER_BEST_VAR), (tp.TOGGLE_FREE_GUI, tp.FREE_OFF_VAR),
                     (tp.TOGGLE_ALONE_GUI, tp.ALONE_VAR), (tp.TOGGLE_RIGHTS_GUI, tp.RIGHTS_OFF_VAR)):
        assert f"pp_cplan_flip = {{ var = {var} }}" in _block(guis, gui), gui
    # switched off, every building the rule closed for a plan's workers opens again (plan_closer.py)
    free = _block(guis, tp.TOGGLE_FREE_GUI)
    assert free.index("pp_cplan_flip") < free.index(f"limit = {{ has_variable = {tp.FREE_OFF_VAR} }}\n\t\t\tpp_pclose_undo_all = yes")
    close = _block(guis, tp.TOGGLE_CLOSE_GUI)
    assert "limit = { is_system_automated = closebuildings }" in close
    assert close.index("set_automated_system = { system = closebuildings activate = no }") < close.index(
        "set_automated_system = { system = closebuildings activate = yes }")
    effects = _code(MOD / tp.EFFECTS)
    key = _block(effects, "pp_tplan_pb_key")
    assert "trigger = scope:pp_key" in key and key.rstrip().endswith("pp_tplan_pb_refresh = yes")
    assert "flag:all = { pp_tplan_pb_step = { var = pp_tplan_pb_all dir = $dir$ all = yes } }" in key
    reset = _block(effects, "pp_tplan_pb_key_reset")
    some = _block(effects, "pp_tplan_pb_refresh")
    declare = _block(effects, "pp_tplan_settings_declare")
    assert "set_variable = { name = pp_tplan_sflag value = flag:all }" in declare
    for plan in plans:
        assert f"flag:{plan.key} = {{ pp_tplan_pb_step = {{ var = pp_tplan_pb_{plan.key} dir = $dir$ all = no }} }}" in key
        assert f"flag:{plan.key} = {{ remove_variable = pp_tplan_pb_{plan.key} }}" in reset
        assert f"AND = {{ has_variable = pp_tplan_pb_{plan.key} var:pp_tplan_pb_{plan.key} < 12.5 }}" in some
        assert f"set_variable = {{ name = pp_tplan_sflag value = flag:{plan.key} }}" in declare
    assert "flag:all" not in reset  # the all-plans limit has no "same as" to go back to
    step = _block(effects, "pp_tplan_pb_step")
    order = ["limit = { has_variable = $var$ }", "limit = { always = $all$ }", "limit = { has_variable = pp_tplan_pb_all }",
             "name = pp_tplan_new value = pp_tplan_pb_next_$dir$"]
    assert [step.index(part) for part in order] == sorted(step.index(part) for part in order)
    assert "always = $all$\n\t\t\tscope:pp_tplan_new > 12.5\n\t\t}\n\t\tremove_variable = $var$" in step
    assert "set_variable = { name = $var$ value = scope:pp_tplan_new }" in step
    assert "set_variable = { name = pp_tplan_pb_some value = yes }" in some and "remove_variable = pp_tplan_pb_some" in some
    # the flags exist for the script check: the declare runs in a never-run block of the plan pass
    run = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_run")
    assert "limit = { always = no }\n\t\tpp_tplan_settings_declare = yes" in run
    for path in (MOD / tp.SETTINGS_GUIS, MOD / tp.EFFECTS, MOD / tp.VALUES):
        text = _code(path)
        assert text.count("{") == text.count("}"), path.name


def test_rank_step(plans: list[tp.Plan], vanilla: Path) -> None:
    assert tp.lowest_rank([{"rural_settlement": "yes"}]) == "rural_settlement"
    assert tp.lowest_rank([{"town": "yes", "city": "yes"}]) == "town"  # no rural flag: town-only
    assert tp.lowest_rank([{"rural_settlement": "no", "town": "no", "city": "yes"}]) == "city"
    assert tp.lowest_rank([{"rural_settlement": "no"}]) is None  # town flag unknown
    assert tp.lowest_rank([{"town": "yes"}, {"rural_settlement": "yes"}]) == "rural_settlement"
    by_key = {plan.key: plan for plan in plans}
    assert by_key["books"].raises and by_key["books"].rank == "town" and by_key["trade"].raises
    assert not by_key["wheat"].raises and not by_key["food"].raises and not by_key["iron"].raises
    effects = _code(MOD / tp.EFFECTS)
    for plan in plans:
        if plan.key in tp.OWN_TURNS:
            assert not plan.raises and plan.do == f"{tp.DO_PREFIX}{plan.key}"
            assert "pp_tplan_raise" not in _block(effects, plan.do), plan.key
            continue
        if not plan.raises:
            assert f"{tp.DO_PREFIX}{plan.key} =" not in effects and plan.do == f"pp_lprof_t_{plan.target}"
            continue
        body = _block(effects, plan.do)
        assert "location_rank = location_rank:rural_settlement" in body, plan.key
        for name in plan.candidates:
            assert f"building_type = building_type:{name}" in body, (plan.key, name)
        assert body.index("pp_tplan_raise = yes") < body.index(f"pp_lprof_t_{plan.target} = yes")
    raise_ = _block(effects, tp.RAISE_EFFECT)
    ranks = cpc.read_ranks(MOD, vanilla)
    for rank in ranks:
        assert f"location_rank = location_rank:{rank.source}" in raise_
        step = _block(effects, f"{tp.RAISE_EFFECT}_{rank.key}")
        assert f"pp_cplan_country_rank_up = {{ rank = {rank.key} n = {cpc.SAVE_RANK[rank.key]} why = {tp.WHY} }}" in step
        for check in ("integration_level = conquered", "modifier:cannot_upgrade_location = yes",
                      f"pp_cplan_country_goods_{rank.key} = yes", f"pp_lprof_fail = {{ r = {tp.FAIL_RANK} }}",
                      "pp_lprof_fail = { r = 107 }", "set_variable = { name = pp_lprof_st value = 101 }"):
            assert check in step, (rank.key, check)
        if rank.population:
            assert f"population < {rank.population:g}" in step
    # the state: 108 -> 11, with its text
    assert lpf.FAIL_STATE[tp.FAIL_RANK] == 11 and 11 in lpf.STATES
    finish = _block(_code(MOD / lpf.HAND_EFFECTS), "pp_lprof_finish")
    assert finish.index("var:pp_lprof_fail > 107.5 }\n\t\tset_variable = { name = $st$ value = 111 }") < finish.index(
        "var:pp_lprof_fail > 106.5")
    assert re.search(r'^  PP_LPROF_ST_11: "[^"\d]+"$', _read(MOD / lpf.LOC), re.MULTILINE)
