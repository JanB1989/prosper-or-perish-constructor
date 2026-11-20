"""Construction Plan: forecast numbers for the window (2026-11-20; construction_plan_forecast.py) and the Locations
group's hand-on after its look's daily slices.

The numbers are script values of the state as it stands, evaluated here offline the way the engine does
(script_eval.py); the effects that keep the means are checked by their structure.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan as cp
from prosper_or_perish_constructor import construction_plan_forecast as fc
from prosper_or_perish_constructor.script_eval import ScriptEval

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game/common"
EFFECTS = COMMON / "scripted_effects/pp_construction_plan.txt"
GUIS = COMMON / "scripted_guis/pp_construction_plan.txt"
WHYS = {group: cp.GROUP_WHY[group] for group in cp.GROUPS}


class PlanEval(ScriptEval):
    """Variables are game values named ``var:<name>`` (a variable that is not there is not set)."""

    def single(self, key, op, v, safe, ctx):
        if key == "has_variable":
            return f"var:{v}" in ctx.get("game", {})
        return super().single(key, op, v, safe, ctx)


@lru_cache(maxsize=1)
def _eval() -> PlanEval:
    return PlanEval(MOD)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _effect(text: str, name: str) -> str:
    match = re.search(rf"^{name} = \{{\n(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match.group(1)


def _state(flow: float | None = 600, hands: dict[str, float] | None = None, waits: dict[str, float] | None = None,
           purses: dict[str, float] | None = None, weights: dict[str, int] | None = None, ran=cp.GROUPS,
           locations: int = 1, ticked: int = 1, measured: int = 3) -> dict:
    """The player's country after some passes: the mean new gold (None: never measured), the mean hand-ons, the gold
    each group wanted at its last look (waits), its purse, the weights (5 each unless given), the groups that looked."""
    game: dict[str, float] = {"gold": 0, "var:pp_cplan_reserve": 100, "pp_lprof_group_n": locations,
                              "pp_cplan_country_active": ticked}
    if flow is not None:
        game[f"var:{fc.FC_FLOW}"] = flow + 100
        game[f"var:{fc.FC_N}"] = 100 + measured
    for group, amount in (hands or {}).items():
        game[f"var:{fc.FC_HAND}_{WHYS[group]}"] = amount + 100
    for group, amount in (waits or {}).items():
        game[f"var:pp_cplan_dwait_{WHYS[group]}"] = amount + 100
    for group, amount in (purses or {}).items():
        game[f"var:{cp.PURSE}_{WHYS[group]}"] = amount + 100
    for group, weight in (weights or {}).items():
        game[f"var:pp_cplan_w_{group}"] = weight + 100
    for group in ran:
        game[f"var:pp_cplan_dran_{WHYS[group]}"] = 1
    return {"game": game}


def _v(name: str, ctx: dict) -> float:
    return _eval().value(name, ctx)


def _f(group: str, what: str, ctx: dict) -> float:
    return _v(f"pp_cplan_fx_{group}_{what}", ctx)


# ---- the numbers ----


def test_status_0_to_5() -> None:
    # six groups at weight 5 = 30 parts; 600 new gold a month: each group 100 a month
    ctx = _state(waits={"improve": 1300, "logistics": 100, "country": 2500}, purses={"improve": 100, "logistics": 200},
                 weights={"food": 0}, ran=tuple(g for g in cp.GROUPS if g != "business"))
    assert _f("food", "status", ctx) == 0  # off
    assert _f("business", "status", ctx) == 1  # has not looked yet
    assert _f("logistics", "missing", ctx) == 0 and _f("logistics", "years", ctx) == 0
    assert _f("logistics", "status", ctx) == 2  # its purse covers what it wanted
    # 25 parts: improve gets 600 x 5 / 25 = 120 a month
    assert _f("improve", "rate", ctx) == pytest.approx(120)
    assert _f("improve", "missing", ctx) == pytest.approx(1200)
    assert _f("improve", "years", ctx) == pytest.approx(1200 / (12 * 120))
    assert _f("improve", "status", ctx) == 3  # keeping up
    assert _f("country", "years", ctx) == pytest.approx(2500 / (12 * 120))
    assert _f("country", "status", ctx) == 4  # short of gold
    # nothing measured yet: only gold handed on counts
    ctx = _state(flow=None, waits={"food": 500, "business": 500}, hands={"business": 50})
    assert _v("pp_cplan_fx_flow_known", ctx) == 0 and _v("pp_cplan_fx_flow_n", ctx) == 0
    assert _f("food", "status", ctx) == 5 and _f("food", "years", ctx) == fc.MAX_YEARS
    assert _f("business", "rate", ctx) == pytest.approx(50)
    assert _f("business", "status", ctx) == 3 + (500 / (12 * 50) > 1)
    assert _v("pp_cplan_fx_flow_known", _state(measured=1)) == 1


def test_need_weight_agrees_with_the_years() -> None:
    """years <= 1 exactly when the group's weight is at least need_w (the other weights as they are)."""
    for missing, hand in ((1500, 0), (1500, 30), (900, 10), (3000, 120)):
        base = _state(waits={"food": missing}, hands={"food": hand})
        need = _f("food", "need_w", base)
        assert 0 < need < cp.WEIGHT_STEPS, (missing, hand, need)
        for weight in range(1, cp.WEIGHT_STEPS + 1):
            ctx = _state(waits={"food": missing}, hands={"food": hand}, weights={"food": weight})
            assert _f("food", "need_w", ctx) == pytest.approx(need)  # it does not depend on its own weight
            assert (_f("food", "years", ctx) <= 1) == (weight >= need), (missing, hand, weight, need)
            # the whole step the window prints: the smallest bar that keeps up
            up = _f("food", "need_up", ctx)
            assert up == int(up) and up - 1 < need <= up
            assert (_f("food", "years", ctx) <= 1) == (weight >= up), (missing, hand, weight, up)


def test_need_weight_rounded_up_to_a_step() -> None:
    # 1500 lacking, 600 new gold, 25 other parts: need_w 6.58 -> 7 (printed 6 it would not keep up)
    ctx = _state(waits={"food": 1500})
    assert 6 < _f("food", "need_w", ctx) < 7 and _f("food", "need_up", ctx) == 7
    assert _f("food", "need_up", _state()) == 0  # nothing missing: 0 stays 0
    assert _f("food", "need_up", _state(waits={"food": 100000})) == cp.WEIGHT_STEPS
    # need_w exactly a whole step: that step (1200 lacking, 100 a month at the share 5/30)
    exact = _state(waits={"food": 1200})
    assert _f("food", "need_w", exact) == pytest.approx(5) and _f("food", "need_up", exact) == 5
    for group in cp.GROUPS:
        assert re.search(rf"^pp_cplan_fx_{group}_need_up = \{{", _read(MOD / cp.VALUES), re.MULTILINE), group


def test_need_weight_caps() -> None:
    # it would need all the new gold or more: 10
    ctx = _state(waits={"food": 100000})
    assert _f("food", "need_w", ctx) == cp.WEIGHT_STEPS and _f("food", "years", ctx) == pytest.approx(100000 / 1200)
    assert _f("food", "years", _state(waits={"food": 10 ** 7})) == fc.MAX_YEARS
    # no new gold: 10 when the hand-on does not cover it, else 0
    assert _f("food", "need_w", _state(flow=0, waits={"food": 1200})) == cp.WEIGHT_STEPS
    assert _f("food", "need_w", _state(flow=0, waits={"food": 1200}, hands={"food": 200})) == 0
    # nothing missing, off, not looked: 0
    assert _f("food", "need_w", _state()) == 0
    assert _f("food", "need_w", _state(waits={"food": 5000}, weights={"food": 0})) == 0
    assert _f("food", "need_w", _state(waits={"food": 5000}, ran=())) == 0
    # the only group that counts: its own weight (the part is all the new gold whatever the weight)
    alone = {group: 0 for group in cp.GROUPS if group != "food"} | {"food": 3}
    ctx = _state(waits={"food": 100000}, weights=alone)
    assert _f("food", "others", ctx) == 0 and _f("food", "need_w", ctx) == 3


def test_one_weight_step() -> None:
    ctx = _state(waits={"food": 3000}, hands={"food": 20})
    up = _state(waits={"food": 3000}, hands={"food": 20}, weights={"food": 6})
    down = _state(waits={"food": 3000}, hands={"food": 20}, weights={"food": 4})
    assert _f("food", "up_part", ctx) == pytest.approx(_v("pp_cplan_partx_food", up))
    assert _f("food", "up_years", ctx) == pytest.approx(_f("food", "years", up))
    assert _f("food", "down_part", ctx) == pytest.approx(_v("pp_cplan_partx_food", down))
    assert _f("food", "down_years", ctx) == pytest.approx(_f("food", "years", down))
    # the ends: one up from 10 stays 10; one down from 1 is off (no part, no gold: 99 years while gold is missing)
    top = _state(waits={"food": 3000}, weights={"food": 10})
    assert _f("food", "up_part", top) == pytest.approx(_v("pp_cplan_partx_food", top))
    low = _state(waits={"food": 3000}, hands={"food": 20}, weights={"food": 1})
    assert _f("food", "down_part", low) == 0 and _f("food", "down_years", low) == fc.MAX_YEARS
    assert _f("food", "down_years", _state(weights={"food": 1})) == 0  # nothing missing
    # a group whose weight counts only while it has something to do: no plan anywhere, no step counts
    idle = _state(waits={"profiles": 3000}, locations=0)
    assert _f("profiles", "status", idle) == 0
    assert _f("profiles", "up_part", idle) == 0 and _f("profiles", "up_years", idle) == fc.MAX_YEARS
    idle = _state(waits={"country": 3000}, ticked=0)
    assert _f("country", "up_part", idle) == 0
    busy = _state(waits={"country": 3000})
    assert _f("country", "up_part", busy) == pytest.approx(600 / 31)


def test_situation_numbers_and_totals() -> None:
    ctx = _state(waits={"food": 1300, "business": 700}, purses={"food": 100})
    game = ctx["game"]
    game["var:pp_cplan_ds_food_famine"] = 102
    game["var:pp_cplan_ds_food_hungry"] = 105
    game["var:pp_cplan_ds_profiles_st7"] = 111
    for n, count in ((4, 2), (8, 1), (11, 3), (13, 1), (14, 2), (7, 11), (9, 5)):
        game[f"var:pp_cplan_ds_profiles_st{n}"] = 100 + count
    game["var:pp_cplan_ds_business_sites"] = 109
    assert _f("food", "sit", ctx) == 7
    assert _f("profiles", "sit", ctx) == 11
    assert _f("business", "sit", ctx) == 9
    assert _f("country", "sit", ctx) == 0
    assert _v("pp_cplan_fx_profiles_blocked", ctx) == 2 + 1 + 3 + 1 + 2
    assert _v("pp_cplan_fx_all_missing", ctx) == pytest.approx(1200 + 700)
    assert _v("pp_cplan_fx_all_years", ctx) == pytest.approx(1900 / (12 * 600))
    assert _v("pp_cplan_fx_all_years", _state(flow=0, waits={"food": 1})) == fc.MAX_YEARS
    assert _v("pp_cplan_fx_all_years", _state()) == 0


def test_situation_history_by_look() -> None:
    ctx = _state()
    for k, value in ((1, 8), (2, 4), (5, 2)):
        ctx["game"][f"var:{fc.HQ_VAR}_{WHYS['food']}_{k}"] = 100 + value
    assert _v("pp_cplan_hq_food_1", ctx) == 8 and _v("pp_cplan_hq_food_3", ctx) == 0  # a look that never happened
    assert _v("pp_cplan_hqx_food_max", ctx) == 8
    assert _v("pp_cplan_hqx_food_p_2", ctx) == 50 and _v("pp_cplan_hqx_food_p_5", ctx) == 25
    assert _v("pp_cplan_hqx_logistics_p_1", ctx) == 0 and _v("pp_cplan_hqx_logistics_max", ctx) == 1
    effects = _read(MOD / cp.EFFECTS)
    for group, why in WHYS.items():
        push = _effect(effects, f"pp_cplan_hq_push_{why}")
        assert push.index(f"from = {fc.HQ_VAR}_{why}_11 to = {fc.HQ_VAR}_{why}_12") < push.index(
            f"from = {fc.HQ_VAR}_{why}_1 to = {fc.HQ_VAR}_{why}_2") < push.index(
            f"set_variable = {{ name = {fc.HQ_VAR}_{why}_1 value = {{ value = pp_cplan_fx_{group}_sit add = 100 }} }}")
    # it moves on by look: at the pass's end for a group that looked; the Locations group at its look's end
    history = _effect(effects, "pp_cplan_history_push")
    for group, why in WHYS.items():
        skipped = "\n\t\t\tvar:pp_cplan_ds_business_skipped < 100.5" if group == "business" else ""
        line = f"limit = {{\n\t\t\thas_variable = {cp.NOW}_{why}{skipped}\n\t\t}}\n\t\tpp_cplan_hq_push_{why} = yes"
        assert (line in history) == (group != "profiles"), group
        assert history.count(f"pp_cplan_hq_push_{why} = yes") == (group != "profiles"), group
    # a Businesses look skipped for lack of gold (pp_cplan_look_business) leaves no 0 column: the push waits for it
    assert "set_variable = { name = pp_cplan_ds_business_skipped value = 101 }" in _read(EFFECTS)
    assert "pp_cplan_hq_push_105 = yes" in _effect(_read(COMMON / "scripted_effects/pp_location_profiles.txt"),
                                                   "pp_lprof_look_end")


def test_the_new_gold_and_the_running_means() -> None:
    # the new gold of a pass: the gold above the reserve in no purse, less what the purses had to give back
    ctx = {"game": {"gold": 1600, "var:pp_cplan_reserve": 1100, "pp_lprof_group_n": 1, "pp_cplan_country_active": 1}}
    assert _v("pp_cplan_flow_new", ctx) == pytest.approx(600)
    ctx["game"][f"var:{cp.PURSE}_101"] = 100 + 400
    assert _v("pp_cplan_flow_new", ctx) == pytest.approx(200)
    ctx["game"][f"var:{cp.PURSE}_102"] = 100 + 400  # the purses hold 800 of 600: nothing new
    assert _v("pp_cplan_flow_new", ctx) == 0
    # the mean over up to 12 passes, as pp_cplan_forecast_measure writes it
    game: dict[str, float] = {}
    seen: list[float] = []
    expected = 0.0
    for n, amount in enumerate([600, 0, 300, 900] + [120] * 20, start=1):
        game["pp_cplan_flow_new"] = amount
        mean = _v("pp_cplan_fc_flow_next", {"game": game})
        game[f"var:{fc.FC_FLOW}"] = mean + 100
        game[f"var:{fc.FC_N}"] = game.get(f"var:{fc.FC_N}", 100) + 1
        seen.append(amount)
        expected += (amount - expected) / min(n, fc.MEAN_PASSES)
        assert mean == pytest.approx(expected), n
        if n <= fc.MEAN_PASSES:
            assert mean == pytest.approx(sum(seen) / n), n  # the plain mean while it spans fewer passes
    assert 120 < mean < sum(seen[-12:]) / 12 + 50  # the old passes fade out
    assert _v("pp_cplan_fc_div", {"game": game}) == fc.MEAN_PASSES
    # the hand-on means read what was handed on at the end of the last pass
    for group, why in WHYS.items():
        assert _v(f"pp_cplan_fc_hand_next_{why}", {"game": {f"var:{cp.PURSE_HAND}_{why}": 160}}) == pytest.approx(60)


def test_the_means_are_kept_at_the_pass_start_and_cleared_when_switched_on() -> None:
    effects = _read(MOD / cp.EFFECTS)
    begin = _effect(_read(EFFECTS), "pp_cplan_pass_begin")
    assert begin.index("pp_cplan_forecast_measure = yes") < begin.index("pp_cplan_purses_fill = yes")
    measure = _effect(effects, "pp_cplan_forecast_measure")
    assert measure.index(f"limit = {{ has_variable = {fc.FC_SKIP} }}\n\t\tremove_variable = {fc.FC_SKIP}") < measure.index("else = {")
    body = measure[measure.index("else = {"):]
    assert body.rindex("save_temporary_scope_value_as") < body.index("set_variable")
    for why in WHYS.values():
        assert f"name = pp_cplan_fch_{why} value = pp_cplan_fc_hand_next_{why} }}" in body
    clear = _effect(effects, "pp_cplan_forecast_clear")
    assert f"set_variable = {{ name = {fc.FC_SKIP} value = yes }}" in clear
    for name in (fc.FC_N, fc.FC_FLOW, f"{fc.FC_HAND}_101", f"{fc.HQ_VAR}_105_12"):
        assert f"remove_variable = {name}\n" in clear
    assert "pp_cplan_forecast_clear = yes" in _effect(effects, "pp_cplan_history_clear")
    toggle = _effect(_read(GUIS), "pp_cplan_toggle_on")
    assert "pp_cplan_history_clear = yes" in toggle


def test_every_name_the_window_reads_exists() -> None:
    values = _read(MOD / cp.VALUES)
    names = ["pp_cplan_flow_n", "pp_cplan_flow_known", "pp_cplan_f_profiles_blocked", "pp_cplan_f_all_missing",
             "pp_cplan_f_all_years", "pp_cplan_f_budget_binds", "pp_cplan_f_budget_held"]
    for group in cp.GROUPS:
        names += [f"pp_cplan_f_{group}_{what}" for what in (
            "missing", "rate", "years", "status", "need_w", "up_part", "up_years", "down_part", "down_years", "sit")]
        names += [f"pp_cplan_hq_{group}_{k}" for k in range(1, 13)] + [f"pp_cplan_hq_{group}_p_{k}" for k in range(1, 13)]
        names.append(f"pp_cplan_hq_{group}_max")
    names += [f"pp_cplan_f_{group}_need_up" for group in cp.GROUPS] + [f"pp_cplan_part_{group}" for group in cp.GROUPS]
    for name in names:
        assert re.search(rf"^{name} = \{{", values, re.MULTILINE), name
    assert set(fc.public_values()) | set(fc.history_values()) <= set(names)


ARITHMETIC = re.compile(r"\b(?:add|multiply|divide|min|max|ceiling|floor)\s*=|\b(?:every|ordered|random|any)_\w+\s*=")


def test_the_window_reads_kept_numbers() -> None:
    """Script profile 2026-11-20: the formulae, evaluated about 185 times a frame with the window open, took 4 s of
    12. Every number the window reads is a plain readout of a kept variable (+ 100, 0 while unset): no arithmetic but
    the offset, no iterator; pp_cplan_forecast_store keeps them from the formulae (the history's from
    pp_cplan_hq_push_<why>)."""
    values = _read(MOD / cp.VALUES)
    effects = _read(MOD / cp.EFFECTS)
    store = _effect(effects, "pp_cplan_forecast_store")
    for name in fc.public_values() + fc.history_values():
        body = _effect(values, name)
        assert body == (f"\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {fc.stored(name)} }}\n"
                        f"\t\tvalue = var:{fc.stored(name)}\n\t\tsubtract = 100\n\t}}\n"), name
        assert not ARITHMETIC.search(body), name
        assert re.search(rf"^{fc.formula(name)} = \{{", values, re.MULTILINE), fc.formula(name)
        assert fc.formula(name) != name
    for name in fc.public_values():
        assert (f"set_variable = {{ name = {fc.stored(name)} value = {{ value = {fc.formula(name)} add = 100 }} }}"
                in store), name
    for group, why in WHYS.items():
        push = _effect(effects, f"pp_cplan_hq_push_{why}")
        for name in fc.history_values(group):
            assert push.index(f"name = {fc.HQ_VAR}_{why}_1 ") < push.index(f"name = {fc.stored(name)} value = {{ value = "
                                                                          f"{fc.formula(name)} add = 100 }}"), name
        clear = _effect(effects, "pp_cplan_forecast_clear")
        assert all(f"remove_variable = {fc.stored(name)}\n" in clear for name in fc.history_values(group))
    # no formula reads a kept number: the store's order does not matter
    formulas = re.findall(r"^(pp_cplan_(?:fx_|partx_|hqx_)\w+) = \{\n(.*?)^\}", values, re.MULTILINE | re.DOTALL)
    assert formulas
    for name, body in formulas:
        assert fc.STORE_VAR not in body, name
        assert not re.search(r"\bpp_cplan_f_|\bpp_cplan_part_|\bpp_cplan_flow_(?:n|known)\b", body), name
    # the purses and the rules never read the window's part (they use their own values)
    rules = "".join(_read(path) for path in sorted(COMMON.rglob("*.txt")))
    rules = rules.replace(values, "")
    assert not re.search(r"\bpp_cplan_part_\w+", re.sub(r"#[^\n]*", "", rules))


def test_the_store_runs_wherever_an_input_changes() -> None:
    call = "pp_cplan_forecast_store = yes"
    end = _effect(_read(EFFECTS), "pp_cplan_pass_end")
    assert end.index("pp_cplan_purses_hand_on = yes") < end.index("pp_cplan_history_push = yes") < end.index(call)
    slice_event = _effect(_read(COMMON / "scripted_effects/pp_location_profiles.txt"), "pp_lprof_slice_event")
    assert slice_event.index("pp_lprof_slice = yes") < slice_event.index("pp_cplan_purses_hand_on_105 = yes") < slice_event.index(call)
    guis = _read(GUIS)
    for name in ("pp_cplan_weight", "pp_cplan_step"):
        body = _effect(guis, name)
        assert body.index("switch = {") < body.index(call), name
    toggle = _effect(guis, "pp_cplan_toggle_on")
    assert toggle.index("pp_cplan_history_clear = yes") < toggle.index("pp_lprof_any_refresh = yes") < toggle.index(call)
    flip = _effect(_read(COMMON / "scripted_effects/pp_location_plan.txt"), "pp_tplan_flip")
    assert flip.rindex("owner ?= { pp_cplan_forecast_store = yes }") > flip.index("grant_town_rights")
    country = _effect(_read(COMMON / "scripted_guis/pp_construction_plan_country.txt"), "pp_cplan_country_toggle")
    assert country.index("switch = {") < country.index(call)


# ---- the Locations group's hand-on after its daily slices ----


def test_the_locations_group_hands_on_after_its_last_slice() -> None:
    ctx = _state(purses={"profiles": 300, "food": 50})
    game = ctx["game"]
    game[f"var:{cp.NOW}_105"] = 1
    game[f"var:{cp.SAVE_COST}_101"] = 600  # food saves
    game["var:pp_lprof_pend"] = 1
    assert _v("pp_cplan_gives_105", ctx) == 0  # slices pending: nothing handed on at the pass's end
    assert _v("pp_cplan_hand_next_105", ctx) == pytest.approx(300)
    del game["var:pp_lprof_pend"]
    assert _v("pp_cplan_gives_105", ctx) == 1
    assert _v("pp_cplan_hand_get_101", ctx) == pytest.approx(300)  # the only saver gets it all
    effects = _read(MOD / cp.EFFECTS)
    late = _effect(effects, "pp_cplan_purses_hand_on_105")
    assert "pp_cplan_gives_105 > 0" in late and "pp_cplan_hand_weights > 0" in late
    assert late.rindex("save_temporary_scope_value_as") < late.index("set_variable")
    assert f"set_variable = {{ name = {cp.PURSE}_105 value = 100 }}" in late
    for why in WHYS.values():
        if why == 105:
            assert f"name = {cp.PURSE_HAND}_105" not in late
            continue
        assert f"change_variable = {{ name = {cp.PURSE}_{why} add = scope:pp_cplan_ni_{why} }}" in late
        assert (f"set_variable = {{ name = {cp.PURSE_HAND}_{why} value = {{ value = {cp.PURSE_HAND}_n_{why} "
                f"add = scope:pp_cplan_ni_{why} add = 100 }} }}") in late
    # only the Locations group waits for its slices
    for group, why in WHYS.items():
        gives = _effect(_read(MOD / cp.VALUES), f"pp_cplan_gives_{why}")
        assert ("pp_lprof_pend" in gives) == (group == "profiles"), group
