"""Construction Plan, budgets that save (Jan 2026-11-10; docs/player_construction_manager.md "Budgets that save").

Jan's three problems after watching the plan run: it favoured cheap buildings (every pass offered all the gold above
the reserve anew, nothing was saved, and a group walked past what it could not pay for), it spammed one profitable
building type, and he wanted a budget per branch above the reserve, under the hood. The design, A-G:

A. a purse per rule group that saves; B. best pick first, the first thing a group cannot pay for is what it saves for
and it builds nothing more in the pass; C. businesses rank by payback including the time to save; D. a market limit
in one place; E. a group that saves for nothing hands its purse on at the pass's end; F. the window (tests in
test_construction_plan_detail.py); G. things held back for construction goods are counted.

The arithmetic of A, C and E sits in script values, evaluated here offline (script_eval.py) the way the engine does;
the effects that write the results and the rest are checked by their structure.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_country as cpc
from prosper_or_perish_constructor.script_eval import ScriptEval
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
EFFECTS = COMMON / "scripted_effects/pp_construction_plan.txt"
TRIGGERS = COMMON / "scripted_triggers/pp_construction_plan.txt"
VALUES = COMMON / "script_values/pp_construction_plan.txt"
PROFILE_EFFECTS = COMMON / "scripted_effects/pp_location_profiles.txt"
WHYS = {group: cp.GROUP_WHY[group] for group in cp.GROUPS}


class PlanEval(ScriptEval):
    """Variables are game values named ``var:<name>`` (a variable that is not there is not set); a building under
    construction gives its levels."""

    def single(self, key, op, v, safe, ctx):
        if key == "has_variable":
            return f"var:{v}" in ctx.get("game", {})
        return super().single(key, op, v, safe, ctx)

    def value(self, expr, ctx):
        if str(expr) == "building_levels_under_construction" and "building_type" in ctx:
            return float(ctx.get("queued", 0))
        return super().value(expr, ctx)


@lru_cache(maxsize=1)
def _eval() -> PlanEval:
    return PlanEval(MOD)


@lru_cache(maxsize=1)
def _result() -> cp.Result:
    return cp.apply(ROOT, PROJECT, MOD, vanilla_root(ROOT, PROJECT), write=False)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def _country(gold: float, purses: dict[str, float] | None = None, weights: dict[str, int] | None = None,
             reserve: float = 1000, locations: int = 1, ticked: int = 1) -> dict:
    """The player's country: its gold, the purses the groups hold, their weights (5 each unless given), whether a
    location has a profile or a mark and whether something is ticked on the Towns and Buildings tab."""
    game: dict[str, float] = {"gold": gold, "var:pp_cplan_reserve": reserve + 100, "pp_lprof_group_n": locations,
                              "pp_cplan_country_active": ticked}
    for group, weight in (weights or {}).items():
        game[f"var:pp_cplan_w_{group}"] = weight + 100
    for group, amount in (purses or {}).items():
        game[f"var:{cp.PURSE}_{WHYS[group]}"] = amount + 100
    return {"game": game}


def _purses(ctx: dict) -> dict[str, float]:
    return {group: _eval().value(cp.purse_value(group), ctx) for group in cp.GROUPS}


def _fill(ctx: dict) -> dict[str, float]:
    """What pp_cplan_purses_fill does: every new amount read first, then written. Returns what each group received."""
    new = {why: _eval().value(f"{cp.PURSE}_next_{why}", ctx) for why in WHYS.values()}
    received = {group: _eval().value(f"{cp.PURSE}_new_{why}", ctx) + _eval().value(f"{cp.PURSE_HAND}_n_{why}", ctx)
                for group, why in WHYS.items()}
    for group, why in WHYS.items():
        ctx["game"][f"var:{cp.PURSE}_{why}"] = new[why] + 100
        ctx["game"][f"var:{cp.PURSE_IN}_{why}"] = received[group] + 100
        ctx["game"].pop(f"var:{cp.PURSE_HAND}_{why}", None)
        for name in cp.SAVE_VARS:
            ctx["game"].pop(f"var:pp_cplan_save_{name}_{why}", None)
    return received


def _hand_on(ctx: dict, ran: tuple[str, ...], saves: tuple[str, ...]) -> None:
    """What pp_cplan_purses_hand_on does after a pass in which ``ran`` ran and ``saves`` save for something."""
    for group in ran:
        ctx["game"][f"var:pp_cplan_dran_{WHYS[group]}"] = 1
    for group in saves:
        ctx["game"][f"var:{cp.SAVE_COST}_{WHYS[group]}"] = 500 + 100
    new = {why: _eval().value(f"pp_cplan_hand_next_{why}", ctx) for why in WHYS.values()}
    got = {why: _eval().value(f"pp_cplan_hand_get_{why}", ctx) for why in WHYS.values()}
    for why in WHYS.values():
        ctx["game"][f"var:{cp.PURSE}_{why}"] = new[why] + 100
        ctx["game"][f"var:{cp.PURSE_HAND}_{why}"] = got[why] + 100


# ---- A. A purse per rule group that saves ----


def test_a_new_gold_is_shared_by_the_weights_and_saved() -> None:
    ctx = _country(gold=1600)
    assert _fill(ctx) == {group: pytest.approx(100) for group in cp.GROUPS}
    assert _purses(ctx) == {group: pytest.approx(100) for group in cp.GROUPS}
    # nothing was spent: next month only the gold that came in is shared; what a group had stays its own
    ctx["game"]["gold"] = 1900
    assert _fill(ctx) == {group: pytest.approx(50) for group in cp.GROUPS}
    assert _purses(ctx) == {group: pytest.approx(150) for group in cp.GROUPS}
    # a group spent its purse (the treasury fell by as much): the others keep theirs, nothing new comes in
    ctx["game"]["gold"] = 1900 - 150
    ctx["game"][f"var:{cp.PURSE}_{WHYS['food']}"] = 100
    assert _fill(ctx) == {group: pytest.approx(0) for group in cp.GROUPS}
    assert _purses(ctx) == {group: pytest.approx(0 if group == "food" else 150) for group in cp.GROUPS}
    # the purses never hold more than the gold above the reserve
    assert sum(_purses(ctx).values()) == pytest.approx(1750 - 1000)


def test_a_weights_decide_the_parts() -> None:
    ctx = _country(gold=2200, weights={"food": 10, "business": 10, "logistics": 0})
    received = _fill(ctx)
    # 10 + 10 + 0 + three groups at 5 = 35 parts of 1,200 gold
    assert received["food"] == received["business"] == pytest.approx(1200 * 10 / 35)
    assert received["improve"] == pytest.approx(1200 * 5 / 35)
    assert received["logistics"] == 0
    assert sum(_purses(ctx).values()) == pytest.approx(1200)


def test_a_a_group_that_does_not_count_gives_its_purse_back() -> None:
    purses = {group: 100 for group in cp.GROUPS}
    # its bar empty; no location with a profile or a mark; nothing ticked on the Towns and Buildings tab
    ctx = _country(gold=1600, purses=purses, weights={"food": 0}, locations=0, ticked=0)
    _fill(ctx)
    after = _purses(ctx)
    assert after["food"] == after["profiles"] == after["country"] == 0
    # their 300 gold went back to be shared among the three that count
    assert after["logistics"] == after["improve"] == after["business"] == pytest.approx(200)


def test_a_purses_shrink_alike_when_the_gold_is_gone() -> None:
    """The player or a war spent the gold: the purses together never exceed the gold above the reserve."""
    ctx = _country(gold=1300, purses={"food": 400, "business": 200, "improve": 0, "logistics": 0, "profiles": 0, "country": 0})
    received = _fill(ctx)
    after = _purses(ctx)
    assert after["food"] == pytest.approx(200) and after["business"] == pytest.approx(100)
    assert sum(after.values()) == pytest.approx(300)
    assert all(amount == 0 for amount in received.values()), "nothing new to share"
    # below the reserve nothing is left in any purse
    ctx["game"]["gold"] = 900
    _fill(ctx)
    assert all(amount == 0 for amount in _purses(ctx).values())


def test_a_every_group_has_a_purse_and_the_effects_read_before_they_write() -> None:
    values = _read(MOD / cp.VALUES)
    effects = _read(MOD / cp.EFFECTS)
    fill = _effect(effects, "pp_cplan_purses_fill")
    hand = _effect(effects, "pp_cplan_purses_hand_on")
    for body in (fill, hand):
        first_write = body.index("set_variable")
        assert body.count("save_temporary_scope_value_as") == 2 * len(cp.GROUPS)
        assert body.rindex("save_temporary_scope_value_as") < first_write, "one group's change must not reach another's sum"
    for group, why in WHYS.items():
        for name in (f"{cp.PURSE}_n_{why}", f"{cp.PURSE}_kept_{why}", f"{cp.PURSE}_new_{why}", f"{cp.PURSE}_next_{why}",
                     f"{cp.PURSE_IN}_n_{why}", f"pp_cplan_hand_get_{why}", f"pp_cplan_hand_next_{why}"):
            assert re.search(rf"^{name} = \{{", values, re.MULTILINE), name
        assert f"limit = {{ {cp.counted_weight(group)} > 0 }}" in _effect(values, f"{cp.PURSE}_kept_{why}"), group
        assert f"name = pp_cplan_np_{why} value = {cp.PURSE}_next_{why} }}" in fill
        assert f"name = {cp.PURSE}_{why} value = {{ value = scope:pp_cplan_np_{why} add = 100 }} }}" in fill
        assert f"name = pp_cplan_ni_{why} value = {{ value = {cp.PURSE}_new_{why} add = {cp.PURSE_HAND}_n_{why} }} }}" in fill
        assert f"name = {cp.PURSE_IN}_{why} value = {{ value = scope:pp_cplan_ni_{why} add = 100 }} }}" in fill
        assert f"name = pp_cplan_np_{why} value = pp_cplan_hand_next_{why} }}" in hand
        assert f"name = {cp.PURSE}_{why} value = {{ value = scope:pp_cplan_np_{why} add = 100 }} }}" in hand
        assert f"name = {cp.PURSE_HAND}_{why} value = {{ value = scope:pp_cplan_ni_{why} add = 100 }} }}" in hand
    run = _effect(_read(EFFECTS), "pp_cplan_run")
    first_group = min(run.index(f"pp_cplan_group_{group} = yes") for group in cp.GROUPS)
    last_group = max(run.rindex(f"pp_cplan_group_{group} = yes") for group in cp.GROUPS)
    assert run.index("pp_cplan_purses_fill = yes") < first_group
    assert last_group < run.index("pp_cplan_purses_hand_on = yes") < run.index("pp_cplan_history_push = yes")
    # a group "had" its purse
    start = _effect(_read(EFFECTS), "pp_cplan_group_start")
    assert "pp_cplan_dhad_$why$ value = { value = pp_cplan_purse_n_$why$ add = 100 }" in start and "$add$" not in start


def test_a_a_construction_must_fit_in_its_groups_purse_and_the_purse_pays() -> None:
    triggers = _read(TRIGGERS)
    affordable = _effect(triggers, "pp_cplan_affordable")
    assert "pp_cplan_est_cost <= scope:pp_cplan_country.pp_cplan_purse_n_$why$" in affordable
    assert "pp_cplan_est_cost <= scope:pp_cplan_country.pp_cplan_free_gold" in affordable  # the reserve, whatever happened
    effects = _read(EFFECTS)
    pay = _effect(effects, "pp_cplan_purse_pay")
    assert "change_variable = { name = pp_cplan_purse_$why$ subtract = scope:pp_cplan_paid }" in pay
    assert "limit = { var:pp_cplan_purse_$why$ < 100 }\n\t\tset_variable = { name = pp_cplan_purse_$why$ value = 100 }" in pay
    now = _effect(effects, "pp_cplan_construct_now")
    assert now.index("name = pp_cplan_paid value") < now.index("pp_cplan_purse_pay = { why = $why$ }")
    # the town and city upgrades of Towns and Buildings pay from the same purse, by the same rules
    up = _effect(_read(MOD / cpc.EFFECTS), "pp_cplan_country_rank_up")
    assert "pp_cplan_purse_pay = { why = 107 }" in up
    assert "NOT = { pp_cplan_saving = { why = 107 } }" in up
    assert "pp_cplan_country_cost_$rank$ <= scope:pp_cplan_country.pp_cplan_purse_n_107" in up


# ---- B. Best pick first; the first thing a group cannot pay for is what it saves for ----


def test_b_the_first_unpaid_thing_is_saved_for_and_nothing_more_is_built() -> None:
    effects = _read(EFFECTS)
    scoped = _effect(effects, "pp_cplan_construct_scoped")
    limit = scoped[scoped.index("pp_cplan_btype_data = yes"):scoped.index("pp_cplan_construct_now")]
    assert "NOT = { pp_cplan_saving = { why = $why$ } }" in limit and "pp_cplan_affordable = { why = $why$ }" in limit
    assert scoped.index("pp_cplan_construct_now = { why = $why$ }") < scoped.index("else = {\n\t\t\t\tpp_cplan_note_wait = { why = $why$ }")
    saving = _effect(_read(TRIGGERS), "pp_cplan_saving")
    assert saving.strip() == "scope:pp_cplan_country = { has_variable = pp_cplan_save_cost_$why$ }"
    note = _effect(effects, "pp_cplan_note_wait")
    target = note[note.index("limit = { NOT = { has_variable = pp_cplan_save_cost_$why$ } }"):]
    # only the first of the pass: the cost, the location, the building type
    for line in ("set_variable = { name = pp_cplan_save_cost_$why$ value = { value = scope:pp_cplan_wc add = 100 } }",
                 "set_variable = { name = pp_cplan_save_loc_$why$ value = scope:pp_cplan_wsite }",
                 "set_variable = { name = pp_cplan_save_type_$why$ value = scope:pp_cplan_btype }"):
        assert line in target, line
    # it is still counted as wanted, so the pane's "how much investment is missing" stays
    assert note.index("change_variable = { name = pp_cplan_dwait_$why$") < note.index("pp_cplan_save_cost_$why$")
    # things stopped for another reason are no save targets: the market limit is asked before the gold, the
    # construction goods before the construct (G), and neither writes what the group saves for
    assert scoped.index("pp_cplan_market_do = { do = gate }") < scoped.index("pp_cplan_btype_data = yes")
    for name in ("pp_cplan_note_market", "pp_cplan_note_goods"):
        assert "pp_cplan_save_" not in _effect(effects, name), name
    # what a group saves for is found afresh every pass; the saved gold is not
    fill = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_purses_fill")
    assert all(f"remove_variable = {cp.SAVE_COST}_{why}\n" in fill for why in WHYS.values())


def test_b_every_group_goes_in_its_order_of_importance() -> None:
    effects = _read(EFFECTS)
    # food: the hungriest province first (the store a year from now, lowest first)
    food = _effect(effects, "pp_cplan_group_food")
    assert "ordered_province = {" in food and "order_by = pp_cplan_food_order" in food and "every_province" not in food
    assert "limit = { has_variable = pp_stored_food_months }" in food
    order = _eval()
    hungry = order.value("pp_cplan_food_order", {"game": {"pp_cplan_food_in_a_year": 2}})
    fed = order.value("pp_cplan_food_order", {"game": {"pp_cplan_food_in_a_year": 20}})
    assert hungry > fed, "ordered lists take the highest value first"
    assert "order_by = pp_logistics_urgency_weight" in _effect(effects, "pp_cplan_group_logistics")
    assert "order_by = pp_cplan_fill_here" in _effect(effects, "pp_cplan_group_improve")
    assert "order_by = pp_cplan_bz_order" in _effect(effects, "pp_cplan_group_business")
    # Towns and Buildings: upgrades of buildings, the ticked buildings in the tab's order, towns, then cities
    country = _read(MOD / cpc.EFFECTS)
    group = _effect(country, "pp_cplan_group_country")
    assert (group.index("pp_cplan_country_upgrades = yes") < group.index("pp_cplan_country_buildings = yes")
            < group.index("pp_cplan_country_ranks = yes"))
    ranks = _effect(country, "pp_cplan_country_ranks")
    assert ranks.index("pp_cplan_rank_town") < ranks.index("pp_cplan_rank_city")
    # the Locations group: its location order, each location's rules then its marks
    run = _effect(_read(PROFILE_EFFECTS), "pp_lprof_run")
    assert "order_by = pp_lprof_turn" in run
    assert run.index("pp_lprof_location_rules = yes") < run.index("pp_lplan_location_marks = yes")
    # the rotation of the groups is still there: it only decides who gets a free construction slot first
    assert len(re.findall(r"current_month = \d+", _effect(effects, "pp_cplan_run"))) == 10


# ---- C. Businesses: payback including the time to save ----


def _order(roi: float, cost: float, purse: float, inflow: float) -> float:
    return _eval().value("pp_cplan_bz_order", {"game": {
        "var:pp_cplan_bz_roi": roi, "var:pp_cplan_bz_cost": cost,
        "scope:pp_cplan_country.pp_cplan_purse_n_103": purse, "scope:pp_cplan_country.pp_cplan_in_n_103": inflow}})


def test_c_businesses_rank_by_payback_including_the_time_to_save() -> None:
    # a level the purse pays: its payback alone (a return of 25 % a year = 4 years)
    assert _order(roi=25, cost=80, purse=100, inflow=50) == pytest.approx(-4)
    # 300 gold short at 50 gold a month: half a year more
    assert _order(roi=25, cost=400, purse=100, inflow=50) == pytest.approx(-4.5)
    # so a dear business that pays back in 4 years is waited for before a cheap one that takes 8 ...
    cheap, dear = _order(roi=12.5, cost=80, purse=100, inflow=50), _order(roi=25, cost=400, purse=100, inflow=50)
    assert dear > cheap, "the dear one comes first and is saved for"
    # ... unless saving for it takes longer than the difference (5 gold a month: five years to save 300)
    assert _order(roi=25, cost=400, purse=100, inflow=5) == pytest.approx(-9)
    assert _order(roi=12.5, cost=80, purse=100, inflow=5) > _order(roi=25, cost=400, purse=100, inflow=5)
    # with nothing coming in a pick the purse cannot pay ranks behind every pick it can
    assert _order(roi=5, cost=100, purse=100, inflow=0) > _order(roi=50, cost=101, purse=100, inflow=0)
    assert _order(roi=50, cost=100, purse=100, inflow=0) == pytest.approx(-2)


def test_c_the_group_builds_in_that_order_and_the_line_reads_the_plain_payback() -> None:
    group = _effect(_read(EFFECTS), "pp_cplan_group_business")
    assert "order_by = pp_cplan_bz_order" in group and "pp_cplan_construct_scoped = { why = 103 }" in group
    # the pick keeps the level's cost for the order; the player's line still reads the plain return
    take = _effect(_read(EFFECTS), "pp_cplan_business_take")
    assert "set_variable = { name = pp_cplan_bz_cost value = pp_cplan_est_cost }" in take
    pick = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_business_pick")
    assert "name = pp_cplan_bz_roi value = scope:pp_cplan_country.pp_cplan_business_min_roi" in pick
    assert "pp_cplan_purse" not in pick and "pp_cplan_in_" not in pick
    # what the group received for the pass: its part of the new gold and what was handed on to it
    fill = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_purses_fill")
    assert "name = pp_cplan_ni_103 value = { value = pp_cplan_purse_new_103 add = pp_cplan_hand_n_103 } }" in fill
    loc = _read(MOD / "main_menu/localization/english/pp_construction_plan_l_english.yml")
    rule = re.search(r"^  PP_CPLAN_BUSINESS_RULE_TT: \"(.+)\"$", loc, re.MULTILINE).group(1)
    assert "It builds what pays back soonest, counting the time it must save for it." in rule


# ---- D. The market limit ----


def test_d_market_room_is_a_share_of_the_demand_less_what_is_under_construction() -> None:
    config = cp.load_config(PROJECT)
    assert config.business_market_share == 10
    evaluator = _eval()
    assert evaluator.value("pp_cplan_market_share", {"game": {}}) == pytest.approx(0.10)
    # a horse breeder under construction with two levels queued, a stud farm with one
    outputs = _result().market_outputs["horses"]
    here = evaluator.value("pp_cplan_uc_here_horses", {"game": {}, "buildings": {
        "horse_breeders": {"level": 3, "queued": 2}, "stud_farm": {"level": 0, "queued": 1},
        "wheat_farm": {"level": 5, "queued": 4}, "cattle_farm": {"level": 2, "queued": 0}}})
    assert here == pytest.approx(2 * outputs["horse_breeders"] + outputs["stud_farm"])
    # a market that asks for 20 horses a month may have 2 a month on the way; 1.5 are: half a horse of room
    # (read on the market's centre location, where the pass keeps the count: a market scope holds no variables)
    market = {"game": {"market.goods_demand_in_market(goods:horses)": 20, "var:pp_cplan_uc_horses": 100 + 1.5}}
    assert evaluator.value("pp_cplan_mroom_horses", market) == pytest.approx(0.5)
    room = _effect(_read(TRIGGERS), "pp_cplan_market_room")
    # one level is always allowed while nothing of the good is under construction; no market, no limit
    for line in ("NOT = { market ?= { always = yes } }", "var:pp_cplan_uc_$g$ < 100.001", "pp_cplan_mroom_$g$ >= $out$"):
        assert line in room, line
    # no variable is read or written on a market scope (in game 2026-11-10: "This scope doesn't support variables";
    # the limit never held and every pass logged about 2,000 errors): the count lives on market.location
    effects = _read(EFFECTS)
    assert "market.location ?= {\n\t\t\tOR = {\n\t\t\t\tNOT = { has_variable = pp_cplan_uc_$g$ }" in room
    for name in ("pp_cplan_market_load", "pp_cplan_market_add_good"):
        body = _effect(effects, name)
        assert "market.location ?= {" in body, name
        for block in re.findall(r"\bmarket \?= \{(.*?)\n\t\t\}", body, re.DOTALL):
            assert "variable" not in block, name


def test_d_the_limit_covers_every_business_type_in_one_construct_path_and_in_the_pick() -> None:
    result = _result()
    generated = _read(MOD / cp.EFFECTS)
    values = _read(MOD / cp.VALUES)
    do = _effect(generated, "pp_cplan_market_do")
    pick = _effect(generated, "pp_cplan_business_pick")
    seen = set()
    for name, good in result.businesses.items():
        output = cp._num(result.market_outputs[good][name])
        branch = re.search(rf"limit = \{{ OR = \{{ ([^\n]*)\bscope:pp_cplan_btype = building_type:{name} ([^\n]*)\}} \}}\n"
                           rf"\t\tpp_cplan_market_\$do\$_good = \{{ g = {good} out = {output} \}}", do)
        assert branch, name
        assert do.count(f"building_type:{name} ") == 1, name
        assert f"pp_cplan_business_take = {{ g = {good} out = {output} demand = {result.buildings[name].demand} }}" in pick
        seen.add(good)
    for good in seen:
        for name in (f"pp_cplan_uc_here_{good}", f"pp_cplan_uc_market_{good}", f"pp_cplan_mroom_{good}"):
            assert re.search(rf"^{name} = \{{", values, re.MULTILINE), name
        assert f"remove_variable = pp_cplan_uc_{good}\n" in _effect(generated, "pp_cplan_market_clear")
        assert f'"market.goods_demand_in_market(goods:{good})"' in _effect(values, f"pp_cplan_mroom_{good}")
    # ONE place asks for everything that builds: the plan's construct path (Businesses, profile rules, marks) ...
    effects = _read(EFFECTS)
    plan_files = sorted(COMMON.glob("*/pp_construction_plan*.txt")) + sorted(COMMON.glob("*/pp_location_p*.txt"))
    gates = {path: len(re.findall(r"pp_cplan_market_do = \{ do = gate \}", re.sub(r"#[^\n]*", "", _read(path))))
             for path in plan_files}
    assert {path: count for path, count in gates.items() if count} == {EFFECTS: 1}
    scoped = _effect(effects, "pp_cplan_construct_scoped")
    assert "limit = { pp_cplan_limits_market_$why$ = yes }\n\t\t\tpp_cplan_market_do = { do = gate }" in scoped
    assert "limit = { scope:pp_cplan_mok < 0.5 }\n\t\t\tpp_cplan_note_market = { why = $why$ }" in scoped
    triggers = _read(MOD / cp.TRIGGERS)
    limited = {cp.GROUP_WHY[group] for group in cp.MARKET_LIMITED}
    assert limited == {103, 105}
    for why in WHYS.values():
        assert _effect(triggers, f"pp_cplan_limits_market_{why}").strip() == f"always = {'yes' if why in limited else 'no'}"
    # every construction of a profile rule or a mark goes through that path
    assert "pp_cplan_construct_scoped = { why = 105 }" in _effect(_read(PROFILE_EFFECTS), "pp_lprof_build")
    assert "construct_building" not in _read(PROFILE_EFFECTS)
    # ... and the pick asks the same trigger, so a site moves on to its next best good
    take = _effect(effects, "pp_cplan_business_take")
    gate = _effect(effects, "pp_cplan_market_gate_good")
    for body in (take, gate):
        assert body.index("pp_cplan_market_load = { g = $g$ }") < body.index("pp_cplan_market_room = { g = $g$ out = $out$ }")


def test_d_under_construction_is_counted_once_a_market_and_kept_for_the_pass() -> None:
    effects = _read(EFFECTS)
    load = _effect(effects, "pp_cplan_market_load")
    assert "limit = { market.location ?= { NOT = { has_variable = pp_cplan_uc_$g$ } } }" in load, "once a market and good"
    assert "save_temporary_scope_value_as = { name = pp_cplan_uc_now value = pp_cplan_uc_market_$g$ }" in load
    assert "set_variable = { name = pp_cplan_uc_$g$ value = { value = scope:pp_cplan_uc_now add = 100 } }" in load
    assert "add_to_variable_list = { name = pp_cplan_markets target = scope:pp_cplan_this_market }" in load
    # the plan's own constructions raise the count, whichever group started them
    now = _effect(effects, "pp_cplan_construct_now")
    assert "pp_cplan_market_do = { do = add }" in now
    add = _effect(effects, "pp_cplan_market_add_good")
    assert "limit = { has_variable = pp_cplan_uc_$g$ }\n\t\t\tchange_variable = { name = pp_cplan_uc_$g$ add = $out$ }" in add
    # cleared at the pass's end, through the list of the markets touched
    clear = _effect(effects, "pp_cplan_markets_clear")
    assert "variable = pp_cplan_markets\n\t\tpp_cplan_market_clear = yes" in clear
    assert "clear_variable_list = pp_cplan_markets" in clear
    run = _effect(effects, "pp_cplan_run")
    last_group = max(run.rindex(f"pp_cplan_group_{group} = yes") for group in cp.GROUPS)
    assert run.rindex("pp_cplan_markets_clear = yes") > last_group
    # everything under construction counts, whoever started it: the count reads the game, not the plan's ledger
    values = _read(MOD / cp.VALUES)
    here = _effect(values, "pp_cplan_uc_here_horses")
    assert "building_levels_under_construction > 0" in here and "pp_cplan_log" not in here and "owner" not in here
    assert "every_location_in_market" in _effect(values, "pp_cplan_uc_market_horses")


def test_d_a_stopped_pick_is_counted_apart_and_a_rule_or_mark_has_its_own_state() -> None:
    effects = _read(EFFECTS)
    note = _effect(effects, "pp_cplan_note_market")
    assert "change_variable = { name = pp_cplan_dml_$why$ add = 1 }" in note and "pp_cplan_dwait" not in note
    assert "set_variable = { name = pp_cplan_mlim value = yes }" in note
    pick = _effect(_read(MOD / cp.EFFECTS), "pp_cplan_business_pick")
    assert "limit = { scope:pp_cplan_bz_ml > 0.5 }\n\t\tpp_cplan_note_market = { why = 103 }" in pick
    from prosper_or_perish_constructor import location_profiles as lpf

    assert lpf.FAIL_STATE[106] == 10 and lpf.FAIL_STATE[107] == 7 and 10 in lpf.STATES
    build = _effect(_read(PROFILE_EFFECTS), "pp_lprof_build")
    assert "has_variable = pp_cplan_mlim } }\n\t\tpp_lprof_fail = { r = 106 }" in build
    finish = _effect(_read(PROFILE_EFFECTS), "pp_lprof_finish")
    assert "limit = { var:pp_lprof_fail > 105.5 }\n\t\tset_variable = { name = $st$ value = 110 }" in finish
    count = _effect(_read(PROFILE_EFFECTS), "pp_lprof_count_state")
    assert "pp_cplan_ds_profiles_st10" in count and ("st10", 100) in cp.SITUATION["profiles"]
    states = _read(MOD / "main_menu/localization/english/pp_location_profiles_l_english.yml")
    text = re.search(r"^  PP_LPROF_ST_10: \"(.+)\"$", states, re.MULTILINE).group(1)
    assert "market" in text and not re.search(r"\d", text)
    gold = re.search(r"^  PP_LPROF_ST_7: \"(.+)\"$", states, re.MULTILINE).group(1)
    assert "this month" not in gold and "saving" in gold


# ---- E. A group that saves for nothing hands its purse on ----


def test_e_what_is_not_needed_goes_to_the_groups_that_save() -> None:
    purses = {"food": 120, "logistics": 80, "improve": 60, "business": 300, "profiles": 40, "country": 0}
    ctx = _country(gold=1600, purses=purses)
    # improvements did not run this pass (its purse is its own); businesses save for something
    _hand_on(ctx, ran=("food", "logistics", "business", "profiles", "country"), saves=("business",))
    after = _purses(ctx)
    assert after["food"] == after["logistics"] == after["profiles"] == after["country"] == 0
    assert after["improve"] == 60
    assert after["business"] == pytest.approx(300 + 120 + 80 + 40)
    assert sum(after.values()) == pytest.approx(sum(purses.values())), "gold only moves"
    assert _eval().value("pp_cplan_hand_n_103", ctx) == pytest.approx(240), "counted as received next pass"


def test_e_several_savers_share_by_their_weights_and_nothing_moves_without_a_saver() -> None:
    purses = {"food": 100, "logistics": 100, "improve": 100, "business": 100, "profiles": 100, "country": 100}
    ctx = _country(gold=1600, purses=purses, weights={"food": 10})
    _hand_on(ctx, ran=tuple(cp.GROUPS), saves=("food", "business"))
    after = _purses(ctx)
    # four groups hand on 400 gold: the food group (weight 10) gets twice what the businesses (5) get
    assert after["food"] == pytest.approx(100 + 400 * 10 / 15) and after["business"] == pytest.approx(100 + 400 * 5 / 15)
    assert sum(after.values()) == pytest.approx(600)
    ctx = _country(gold=1600, purses=purses)
    _hand_on(ctx, ran=tuple(cp.GROUPS), saves=())
    assert _purses(ctx) == {group: pytest.approx(100) for group in cp.GROUPS}, "no group saves: purses stay"


def test_e_only_saving_groups_receive() -> None:
    values = _read(MOD / cp.VALUES)
    for group, why in WHYS.items():
        get = _effect(values, f"pp_cplan_hand_get_{why}")
        assert f"pp_cplan_saves_{why} > 0" in get and "pp_cplan_hand_weights > 0" in get
        assert f"has_variable = {cp.SAVE_COST}_{why}" in _effect(values, f"pp_cplan_saves_{why}")
        gives = _effect(values, f"pp_cplan_gives_{why}")
        assert f"has_variable = pp_cplan_dran_{why}" in gives and f"NOT = {{ has_variable = {cp.SAVE_COST}_{why} }}" in gives
        assert f"add = {{ value = {cp.PURSE}_n_{why} multiply = pp_cplan_gives_{why} }}" in _effect(values, "pp_cplan_hand_pool")
        assert (f"add = {{ value = {cp.counted_weight(group)} multiply = pp_cplan_saves_{why} }}"
                in _effect(values, "pp_cplan_hand_weights"))


# ---- G. Things held back for construction goods are counted ----


def test_g_things_the_market_lacks_the_goods_for_are_counted() -> None:
    """In game 2026-11-10: a Library needs books, a town glass; nothing happened and the pane said "wanted 0"."""
    effects = _read(EFFECTS)
    note = _effect(effects, "pp_cplan_note_goods")
    assert "change_variable = { name = pp_cplan_dgo_$why$ add = 1 }" in note
    generated = _read(MOD / cp.EFFECTS)
    # food: the capital's buildings and the Victualling Yard; logistics; improvements; the business pick
    for name, why in (("pp_cplan_try_tavern_here", 101), ("pp_cplan_try_kitchen_here", 101),
                      ("pp_cplan_try_granary_here", 101), ("pp_cplan_try_grange_here", 101),
                      ("pp_cplan_try_yard_here", 101), ("pp_cplan_try_logistics_here", 102),
                      ("pp_cplan_try_improve_here", 106), ("pp_cplan_business_pick", 103)):
        assert f"pp_cplan_note_goods = {{ why = {why} }}" in _effect(generated, name), name
    # a "first that can be built" picker still passes one over that lacks its goods (a Carrier Inn where the River
    # Boatmen's Yard lacks naval supplies), and counts only when nothing is built
    logistics = _effect(generated, "pp_cplan_try_logistics_here")
    config = cp.load_config(PROJECT)
    assert logistics.count("scope:pp_cplan_done < 0.5 location_and_owner_can_build") == len(config.logistics_order)
    assert "limit = { scope:pp_cplan_done < 0.5 scope:pp_cplan_ng > 0.5 }\n\t\tpp_cplan_note_goods = { why = 102 }" in logistics
    # Towns and Buildings: the ticked buildings, the upgrades of buildings, the town and city upgrades
    country = _read(MOD / cpc.EFFECTS)
    for name in ("pp_cplan_country_public", "pp_cplan_country_upgrade_to", "pp_cplan_country_ranks"):
        assert "pp_cplan_note_goods = { why = 107 }" in _effect(country, name), name
    # the Locations group shows them as a rule state (8), as before
    assert "pp_lprof_fail = { r = 105 }" in _read(PROFILE_EFFECTS)
    # not counted (it would take another walk): the food rule's farm step, whose line returns already leave out a line
    # the market lacks the goods for
    assert "pp_cplan_note_goods" not in _effect(generated, "pp_cplan_try_farm_here")
    assert "goods" in cp.GROUP_NUMBERS and "limited" in cp.GROUP_NUMBERS
