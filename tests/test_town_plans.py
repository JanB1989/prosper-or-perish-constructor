"""Town-right plans (src/prosper_or_perish_constructor/town_plans.py, 2026-11-19): one plan right per good with a
forced goods target plus food and trade; the Construction Plan's Locations pass builds toward every held plan."""

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
        assert re.fullmatch(r"[a-z_]+", plan.key) and plan.right == f"pp_plan_{plan.key}"
        assert plan.candidates == tuple(c.name for c in found[plan.target]), plan.key
    assert {plan.key: plan.target for plan in plans if plan.key in tp.EXTRA_PLANS} == {"food": "food", "trade": "trade_category"}


def test_one_right_per_plan_with_the_template_body(plans: list[tp.Plan], vanilla: Path) -> None:
    text = _read(MOD / tp.RIGHTS)
    blocks = dict(cp._blocks(text))
    assert list(blocks) == [plan.right for plan in plans]
    for plan in plans:
        body = blocks[plan.right]
        color = re.search(r"color = (.+)", body).group(1)
        assert f"{plan.right} = {{{body}}}\n" == tp.RIGHT_BODY.format(key=plan.right, color=color), plan.key
    body = tp.RIGHT_BODY.format(key="x", color="c")
    assert "potential = { always = no }" in body and "kept_at_conquest = no" in body
    assert "local_possible_town_rights = 1" in body
    assert "is_specialization" not in text and "upgrades_to" not in text and "allow" not in text
    # each its own colour (tests/test_town_rights_order.py checks them against every other right)
    colors = re.findall(r"color = (hsv \{ [0-9. ]+ \})\n", text)
    assert len(colors) == len(plans) == len(set(colors))
    # the Towns and Buildings rule never offers them (switched off: potential always = no)
    rights, _off, _ = cpc.read_rights(MOD, vanilla)
    assert not any(tp.is_plan_right(right.key) for right in rights)
    # no plan right in the one-specialization lists of the charters
    assert "pp_plan_" not in _read(MOD / "in_game/common/town_rights/pp_specialization_town_rights.txt")


def test_name_description_and_icon_for_every_plan(plans: list[tp.Plan]) -> None:
    loc = _read(MOD / tp.LOC)
    assert loc.startswith("l_english:\n")
    for plan in plans:
        name = re.search(rf'^ {plan.right}: "Plan: ([^"]+)"$', loc, re.MULTILINE)
        desc = re.search(rf'^ {plan.right}_desc: "(.+)"$', loc, re.MULTILINE)
        assert name and desc, plan.key
        text = desc.group(1)
        assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", text)), plan.key  # no numbers
        assert "[location|e]" in text and "[town_rights|e]" in text, plan.key
        if plan.key not in tp.EXTRA_PLANS:
            assert f"[ShowGoodsName('{plan.key}')|e]" in text, plan.key
        assert ("[location_rank|e]" in text) == plan.raises, plan.key
        icon = MOD / tp.ICONS / f"{plan.right}.dds"
        assert icon.is_file() and icon.read_bytes()[:4] == b"DDS ", plan.key
    assert re.search(r'^ pp_plan_goods_gold: "Plan: Gold"$', loc, re.MULTILINE)
    assert "specialization [town_rights|e]" in _block_line(loc, "pp_plan_books_desc")
    assert "specialization" not in _block_line(loc, "pp_plan_wheat_desc")
    assert len(f"mod/pp/{tp.ICONS.as_posix()}/pp_plan_naval_supplies.dds") <= 109


def _block_line(loc: str, key: str) -> str:
    return re.search(rf"^ {key}: (.+)$", loc, re.MULTILINE).group(1)


def test_held_trigger_and_on_values_are_complete(plans: list[tp.Plan]) -> None:
    held = _block(_code(MOD / tp.TRIGGERS), tp.HELD_TRIGGER)
    assert re.findall(r"has_town_rights = town_rights_type:(\w+)", held) == [plan.right for plan in plans]
    values = _code(MOD / tp.VALUES)
    for plan in plans:
        body = _block(values, plan.on_value)
        assert body.strip().startswith("value = 0")
        assert f"limit = {{ has_town_rights = town_rights_type:{plan.right} }}\n\t\tvalue = 1" in body, plan.key
    assert len(re.findall(r"^pp_tplan_on_\w+ = \{", values, re.MULTILINE)) == len(plans)


def test_the_pass_keys_on_the_held_right_and_forces_it(plans: list[tp.Plan]) -> None:
    hand = _code(MOD / lpf.HAND_EFFECTS)
    effects = _code(MOD / lpf.EFFECTS)
    mark = _block(hand, "pp_lplan_mark")
    assert "limit = { has_town_rights = town_rights_type:pp_plan_$g$ }" in mark
    assert "pp_lplan_$v$" not in mark.replace("pp_lplan_st_$v$", "").replace("pp_lplan_est_$v$", "")
    marks = _block(effects, "pp_lplan_location_marks")
    for plan in plans:
        assert f"pp_lplan_mark = {{ v = g_{plan.key} g = {plan.key} do = {plan.do} " in marks, plan.key
    # forced: no payback limit, no market limit, inside the location's turn
    turn = _block(hand, "pp_lplan_location_turn")
    assert turn.index("name = pp_cplan_forced value = 1") < turn.index("pp_lplan_location_marks = yes")
    assert "save_temporary_scope_value_as = { name = pp_lprof_pb value = 1000000 }" in turn
    # a location holding only plans gets its turn: the gather finds it among the locations with town rights, and
    # its turn runs its plans
    gather = _block(hand, "pp_lprof_gather")
    assert "every_locations_with_town_rights_in_country = {" in gather and "pp_tplan_held = yes" in gather
    location = _block(hand, "pp_lprof_location_turn")
    assert "pp_tplan_held = yes" in location
    has = _block(_code(MOD / lpf.TRIGGERS), "pp_lprof_has_locations")
    assert "any_locations_with_town_rights_in_country" in has and "pp_tplan_held = yes" in has
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
    assert re.search(r"^pp_lprof_t_food = \{", effects, re.MULTILINE)
    assert [c.name for c in found[tp.TRADE_TARGET]] and set(categories[tp.TRADE_TARGET]) >= {"marketplace"}
    assert re.search(r"^pp_lprof_t_trade_category = \{", effects, re.MULTILINE)


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
    for name, var in ((tp.LOSS_VALUE, tp.LOSS_OK_VAR), (tp.STAFF_VALUE, tp.STAFF_OFF_VAR), (tp.ORDER_VALUE, tp.ORDER_BEST_VAR)):
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
             tp.TOGGLE_ORDER_GUI, tp.TOGGLE_CLOSE_GUI]
    assert re.findall(r"^(\w+) = \{", guis, re.MULTILINE) == names
    for name in names:
        body = _block(guis, name)
        assert "scope = country" in body and "is_valid = {\n\t\tis_ai = no\n\t}" in body, name
    assert "pp_tplan_pb_key = { dir = up }" in _block(guis, tp.PB_UP_GUI)
    assert "pp_tplan_pb_key = { dir = down }" in _block(guis, tp.PB_DOWN_GUI)
    assert "pp_tplan_pb_key_reset = yes" in _block(guis, tp.PB_RESET_GUI)
    for gui, var in ((tp.TOGGLE_LOSS_GUI, tp.LOSS_OK_VAR), (tp.TOGGLE_STAFF_GUI, tp.STAFF_OFF_VAR),
                     (tp.TOGGLE_ORDER_GUI, tp.ORDER_BEST_VAR)):
        assert f"pp_cplan_flip = {{ var = {var} }}" in _block(guis, gui), gui
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
