"""Construction Plan: forecast numbers for the window (2026-11-20). The rules never read them.

How much gold comes in, how much each rule group still lacks for everything it wanted at its last look, and how long
that takes at its part of the new gold; what one step of its weight would change, and the weight at which it would keep
up (a year). Plus each group's one situation number and its history by look.

Bookkeeping (country variables, + 100, generated into pp_construction_plan_generated.txt by construction_plan.apply):

* at every pass's start, before ``pp_cplan_purses_fill`` writes (``pp_cplan_forecast_measure``): the new gold shared out
  in the pass, less what the purses had to give back (``pp_cplan_flow_new``), and what each group was handed at the end
  of the last pass (``pp_cplan_hand_<why>``; a Locations look that ended in a later daily slice adds its hand-on to it),
  each into a running mean over up to MEAN_PASSES passes (mean += (x - mean) / min(passes, MEAN_PASSES));
* the monthly budget (2026-11-20): ``pp_cplan_purses_fill`` keeps the gold above the reserve the budget left in no
  purse (``pp_cplan_budget_held``); ``pp_cplan_f_budget_binds`` = 1 while a budget is set and it left gold out, so the
  window can say that the budget, not the treasury, holds the plan back;
* switching the plan on (``pp_cplan_history_clear`` -> ``pp_cplan_forecast_clear``) clears the means and the situation
  history, and the first pass after it is not measured (it shares out the whole treasury above the reserve);
* the situation history moves on by look (``pp_cplan_hq_push_<why>``: at the pass's end for a group that looked, the
  Locations group at the end of its look's last daily slice).
"""

from __future__ import annotations

import re

from prosper_or_perish_constructor import construction_plan as cp

MEAN_PASSES = 12  # passes the running means span
HISTORY_LOOKS = 12  # looks the situation history keeps
MAX_YEARS = 99
FC_N = "pp_cplan_fc_n"  # passes measured (+ 100)
FC_SKIP = "pp_cplan_fc_skip"  # yes: the next pass is not measured (the plan was just switched on)
FC_FLOW = "pp_cplan_fc_flow"  # mean new gold a pass (+ 100)
FC_HAND = "pp_cplan_fc_hand"  # pp_cplan_fc_hand_<why>: mean gold handed on to the group a pass (+ 100)
STORE_VAR = "pp_cplan_fv_"  # pp_cplan_fv_<public name without pp_cplan_>: what the window reads (+ 100)
# the per-group numbers the window reads (pp_cplan_f_<group>_<what>)
STORED = ("status", "missing", "rate", "years", "need_w", "need_up", "up_part", "up_years", "down_part", "down_years",
          "sit")
# the monthly budget (2026-11-20): 1 while it held the plan back at the last pass, and the gold it left out then
BUDGET_VALUES = ("pp_cplan_f_budget_binds", "pp_cplan_f_budget_held")
HQ_VAR = "pp_cplan_hqv"  # pp_cplan_hqv_<why>_<k>: the group's situation at its k-th last look (+ 100)

# the group's one situation number at its last look (sums of the detail panes' readouts, construction_plan.SITUATION)
SITUATION_PARTS = {
    "food": ("pp_cplan_d_food_famine", "pp_cplan_d_food_hungry"),
    "logistics": ("pp_cplan_d_logistics_below",),
    "improve": ("pp_cplan_d_improve_over",),
    "business": ("pp_cplan_d_business_sites",),
    "profiles": ("pp_cplan_d_profiles_st7",),  # plans held back for gold
    "country": (),
}
# plans waiting for something other than gold: no workers, construction goods, rank, closed, a closing under way
BLOCKED_STATES = (4, 8, 11, 13, 14)


def _readout(name: str, var: str) -> str:
    return (f"{name} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
            f"\t\tvalue = var:{var}\n\t\tsubtract = 100\n\t}}\n}}\n")


def _years(name: str, missing: str, rate: str, comment: str) -> str:
    """missing / (12 x rate), at most MAX_YEARS; 0 when nothing is missing; MAX_YEARS when no gold comes in."""
    return (
        f"# {comment}\n{name} = {{\n\tvalue = 0\n"
        f"\tif = {{\n\t\tlimit = {{\n\t\t\t{missing} > 0\n\t\t\tNOT = {{ {rate} > 0 }}\n\t\t}}\n\t\tvalue = {MAX_YEARS}\n\t}}\n"
        f"\telse_if = {{\n\t\tlimit = {{ {missing} > 0 }}\n\t\tvalue = {missing}\n\t\tdivide = {rate}\n\t\tdivide = 12\n"
        f"\t\tmax = {MAX_YEARS}\n\t}}\n}}\n"
    )


def _active(group: str) -> str:
    """The body of pp_cplan_f_<group>_act: 1 while the group's weight counts at all (construction_plan.COUNTED_WEIGHTS:
    the Locations group while a plan exists, Towns and Buildings while something is ticked), else 0."""
    if group == "profiles":
        return "\tvalue = pp_lprof_group_n\n"
    if group == "country":
        return "\tvalue = 0\n\tif = {\n\t\tlimit = { pp_cplan_country_active > 0 }\n\t\tvalue = 1\n\t}\n"
    return "\tvalue = 1\n"


def render_values() -> str:
    whys = [(group, cp.GROUP_WHY[group]) for group in cp.GROUPS]
    p = [
        "\n# ---- Forecast for the window (country scope; construction_plan_forecast.py; the rules never read these) ----\n\n"
        "# The new gold shared out in this pass (at most the monthly budget: pp_cplan_purse_share), less what the purses\n"
        "# had to give back (read before pp_cplan_purses_fill writes: pp_cplan_forecast_measure).\n"
        "pp_cplan_flow_new = {\n\tvalue = pp_cplan_purse_held\n\tsubtract = pp_cplan_purse_free\n\tmin = 0\n"
        "\tmultiply = -1\n\tadd = pp_cplan_purse_share\n\tmin = 0\n}\n"
        "# The monthly budget held the plan back at the last pass's start: gold above the reserve stayed in no purse\n"
        f"# because of it ({cp.BUDGET_HELD}, kept by pp_cplan_purses_fill), a budget is still set and a rule group counts.\n"
        f"# 1 / 0, and that gold.\n"
        f"pp_cplan_f_budget_held = {{\n\tvalue = {cp.BUDGET_HELD}_n\n}}\n"
        "pp_cplan_f_budget_binds = {\n\tvalue = 0\n\tif = {\n\t\tlimit = {\n\t\t\tpp_cplan_budget_gold > 0\n"
        "\t\t\tpp_cplan_w_total > 0\n\t\t\tpp_cplan_f_budget_held > 0.5\n\t\t}\n\t\tvalue = 1\n\t}\n}\n"
        f"# The running means' divisor for this pass's measure: the passes measured with it, at most {MEAN_PASSES}.\n"
        f"pp_cplan_fc_div = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {FC_N} }}\n\t\tvalue = var:{FC_N}\n"
        f"\t\tsubtract = 99\n\t}}\n\tmax = {MEAN_PASSES}\n}}\n"
        "# Gold a month coming in for the purses (the running mean), and 1 once a pass was measured.\n"
        f"pp_cplan_flow_n = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {FC_FLOW} }}\n\t\tvalue = var:{FC_FLOW}\n"
        "\t\tsubtract = 100\n\t}\n\tmin = 0\n}\n"
        f"pp_cplan_flow_known = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{\n\t\t\thas_variable = {FC_N}\n"
        f"\t\t\tvar:{FC_N} > 100.5\n\t\t}}\n\t\tvalue = 1\n\t}}\n}}\n"
        "pp_cplan_fc_flow_next = {\n\tvalue = pp_cplan_flow_new\n\tsubtract = pp_cplan_flow_n\n\tdivide = pp_cplan_fc_div\n"
        "\tadd = pp_cplan_flow_n\n}\n"
    ]
    for group, why in whys:
        cw = cp.counted_weight(group)
        f = f"pp_cplan_f_{group}"
        hand = f"{f}_hand"
        missing = f"{f}_missing"
        p.append(f"\n# {group} ({why})\n")
        p.append(f"# the mean gold handed on to it a pass, and the mean after this pass's measure\n")
        p.append(_readout(hand, f"{FC_HAND}_{why}"))
        p.append(f"pp_cplan_fc_hand_next_{why} = {{\n\tvalue = {cp.PURSE_HAND}_n_{why}\n\tsubtract = {hand}\n"
                 f"\tdivide = pp_cplan_fc_div\n\tadd = {hand}\n}}\n")
        p.append(f"# the gold it still lacks for everything it wanted at its last look\n"
                 f"{missing} = {{\n\tvalue = pp_cplan_d_{group}_wait\n\tsubtract = {cp.purse_value(group)}\n\tmin = 0\n}}\n")
        p.append(f"# its part of the new gold (the current weights), and the gold a month it gets\n"
                 f"{f}_frac = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ pp_cplan_w_total > 0 }}\n\t\tvalue = {cw}\n"
                 f"\t\tdivide = pp_cplan_w_total\n\t}}\n}}\n"
                 f"{f}_rate = {{\n\tvalue = pp_cplan_flow_n\n\tmultiply = {f}_frac\n\tadd = {hand}\n}}\n")
        p.append(_years(f"{f}_years", missing, f"{f}_rate", "the years until it has all it lacks"))
        p.append(
            "# 0 off, 1 has not looked yet, 2 has the gold for all it asks, 3 keeping up (a year or less), 4 short of gold,\n"
            "# 5 short and no gold comes in\n"
            f"{f}_status = {{\n\tvalue = 4\n"
            f"\tif = {{\n\t\tlimit = {{ NOT = {{ {cw} > 0 }} }}\n\t\tvalue = 0\n\t}}\n"
            f"\telse_if = {{\n\t\tlimit = {{ pp_cplan_d_{group}_ran < 0.5 }}\n\t\tvalue = 1\n\t}}\n"
            f"\telse_if = {{\n\t\tlimit = {{ NOT = {{ {missing} > 0 }} }}\n\t\tvalue = 2\n\t}}\n"
            f"\telse_if = {{\n\t\tlimit = {{ NOT = {{ {f}_rate > 0 }} }}\n\t\tvalue = 5\n\t}}\n"
            f"\telse_if = {{\n\t\tlimit = {{ {f}_years <= 1 }}\n\t\tvalue = 3\n\t}}\n}}\n"
        )
        p.append(
            "# the weight at which it would keep up (a year), the other groups' weights as they are: the share of the new\n"
            "# gold it needs (s), and need_w = s x others / (1 - s), at most 10\n"
            f"{f}_others = {{\n\tvalue = pp_cplan_w_total\n\tsubtract = {cw}\n\tmin = 0\n}}\n"
            f"{f}_lack = {{\n\tvalue = {missing}\n\tdivide = 12\n\tsubtract = {hand}\n}}\n"
            f"{f}_need_s = {{\n\tvalue = 0\n"
            f"\tif = {{\n\t\tlimit = {{ pp_cplan_flow_n > 0 }}\n\t\tvalue = {f}_lack\n\t\tdivide = pp_cplan_flow_n\n"
            f"\t\tmin = 0\n\t\tmax = 1\n\t}}\n"
            f"\telse_if = {{\n\t\tlimit = {{ {f}_lack > 0 }}\n\t\tvalue = 1\n\t}}\n}}\n"
            f"{f}_need_w = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ {f}_status > 1.5 }}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ NOT = {{ {f}_others > 0 }} }}\n\t\t\tvalue = {cw}\n\t\t}}\n"
            f"\t\telse_if = {{\n\t\t\tlimit = {{ {f}_need_s >= 1 }}\n\t\t\tvalue = {cp.WEIGHT_STEPS}\n\t\t}}\n"
            f"\t\telse = {{\n\t\t\tvalue = {f}_need_s\n\t\t\tmultiply = {f}_others\n"
            f"\t\t\tdivide = {{ value = 1 subtract = {f}_need_s }}\n\t\t\tmax = {cp.WEIGHT_STEPS}\n\t\t}}\n\t}}\n}}\n"
            "# ... rounded up to a whole step of the weight bar (the window prints it; 0 stays 0)\n"
            f"{f}_need_up = {{\n\tvalue = {f}_need_w\n\tceiling = yes\n\tmin = 0\n\tmax = {cp.WEIGHT_STEPS}\n}}\n"
        )
        p.append(f"# 1 while its weight counts at all\n{f}_act = {{\n{_active(group)}}}\n")
        for step, op in (("up", f"add = 1\n\tmax = {cp.WEIGHT_STEPS}"), ("down", "subtract = 1\n\tmin = 0")):
            s = f"{f}_{step}"
            p.append(
                f"# its weight one step {step}: the weight that would count, its part in %, its gold a month, its years\n"
                f"{s}_w = {{\n\tvalue = pp_cplan_{group}_w\n\t{op}\n\tmultiply = {f}_act\n}}\n"
                f"{s}_part = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ {s}_w > 0 }}\n\t\tvalue = {s}_w\n\t\tmultiply = 100\n"
                f"\t\tdivide = {{ value = {f}_others add = {s}_w }}\n\t}}\n}}\n"
                f"{s}_rate = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ {s}_w > 0 }}\n\t\tvalue = pp_cplan_flow_n\n"
                f"\t\tmultiply = {s}_part\n\t\tdivide = 100\n\t\tadd = {hand}\n\t}}\n}}\n"
            )
            p.append(_years(f"{s}_years", missing, f"{s}_rate", f"its years with its weight one step {step}"))
        parts = SITUATION_PARTS[group]
        p.append(f"# its one situation number at its last look\n{f}_sit = {{\n\tvalue = 0\n"
                 + "".join(f"\tadd = {name}\n" for name in parts) + "}\n")
        hq = f"pp_cplan_hq_{group}"
        looks = range(1, HISTORY_LOOKS + 1)
        p.append(f"# the situation at its last {HISTORY_LOOKS} looks (k = 1 the last), in % of the largest, the largest\n")
        p += [_readout(f"{hq}_{k}", f"{HQ_VAR}_{why}_{k}") for k in looks]
        p.append(f"{hq}_max = {{\n\tvalue = 1\n" + "".join(f"\tmin = {hq}_{k}\n" for k in looks) + "}\n")
        p += [f"{hq}_p_{k} = {{\n\tvalue = {hq}_{k}\n\tmultiply = 100\n\tdivide = {hq}_max\n}}\n" for k in looks]
    p.append(
        "\n# The Locations group: plans waiting for something other than gold (states "
        + ", ".join(str(n) for n in BLOCKED_STATES) + ").\n"
        "pp_cplan_f_profiles_blocked = {\n\tvalue = 0\n"
        + "".join(f"\tadd = pp_cplan_d_profiles_st{n}\n" for n in BLOCKED_STATES) + "}\n"
        "# All groups: the gold they lack, and the years the new gold takes to bring it.\n"
        "pp_cplan_f_all_missing = {\n\tvalue = 0\n"
        + "".join(f"\tadd = pp_cplan_f_{group}_missing\n" for group, _ in whys) + "}\n"
    )
    p.append(_years("pp_cplan_f_all_years", "pp_cplan_f_all_missing", "pp_cplan_flow_n",
                    "the years until all groups have what they lack"))
    return _internal("".join(p)) + render_readouts()


def _internal(text: str) -> str:
    """The formulae under their internal names (the public names are readouts of what pp_cplan_forecast_store keeps)."""
    text = re.sub(r"\bpp_cplan_f_", "pp_cplan_fx_", text)
    text = re.sub(r"\bpp_cplan_flow_(n|known)\b", r"pp_cplan_fx_flow_\1", text)
    return re.sub(r"\bpp_cplan_hq_([a-z]+)_(max|p_\d+)\b", r"pp_cplan_hqx_\1_\2", text)


def public_values() -> list[str]:
    """The names the window reads that pp_cplan_forecast_store keeps (the situation history's max and percentages are
    kept when the history moves on, pp_cplan_hq_push_<why>)."""
    names = ["pp_cplan_flow_n", "pp_cplan_flow_known", "pp_cplan_f_profiles_blocked", "pp_cplan_f_all_missing",
             "pp_cplan_f_all_years", *BUDGET_VALUES]
    for group in cp.GROUPS:
        names += [f"pp_cplan_f_{group}_{what}" for what in STORED]
        names.append(f"pp_cplan_part_{group}")
    return names


def history_values(group: str | None = None) -> list[str]:
    """The situation history's largest look and its percentages (kept by pp_cplan_hq_push_<why>)."""
    return [f"pp_cplan_hq_{g}_{what}" for g in cp.GROUPS if group in (None, g)
            for what in ("max", *(f"p_{k}" for k in range(1, HISTORY_LOOKS + 1)))]


def formula(name: str) -> str:
    """The internal formula behind a public name."""
    if name.startswith("pp_cplan_part_"):
        return name.replace("pp_cplan_part_", cp.PART_FORMULA)
    return _internal(name)


def stored(name: str) -> str:
    """The country variable (+ 100) a public name reads."""
    return STORE_VAR + name[len("pp_cplan_"):]


def _store_line(name: str, indent: str = "\t") -> str:
    return f"{indent}set_variable = {{ name = {stored(name)} value = {{ value = {formula(name)} add = 100 }} }}\n"


def render_readouts() -> str:
    parts = ["\n# ---- The window's forecast as kept numbers (pp_cplan_forecast_store; script profile 2026-11-20: the\n"
             "# formulae, evaluated about 185 times a frame with the window open, took 4 s of 12). Plain readouts, 0 while\n"
             "# unset. ----\n"]
    parts += [_readout(name, stored(name)) for name in public_values() + history_values()]
    return "".join(parts)


def render_effects() -> str:
    whys = [(group, cp.GROUP_WHY[group]) for group in cp.GROUPS]
    reads = "".join(f"\t\tsave_temporary_scope_value_as = {{ name = pp_cplan_fch_{why} value = pp_cplan_fc_hand_next_{why} }}\n"
                    for _, why in whys)
    writes = "".join(f"\t\tset_variable = {{ name = {FC_HAND}_{why} value = {{ value = scope:pp_cplan_fch_{why} add = 100 }} }}\n"
                     for _, why in whys)
    clear = [f"\tremove_variable = {FC_N}\n", f"\tremove_variable = {FC_FLOW}\n", f"\tremove_variable = {cp.BUDGET_HELD}\n"]
    clear += [f"\tremove_variable = {FC_HAND}_{why}\n" for _, why in whys]
    clear += [f"\tremove_variable = {HQ_VAR}_{why}_{k}\n" for _, why in whys for k in range(1, HISTORY_LOOKS + 1)]
    clear += [f"\tremove_variable = {stored(name)}\n" for name in history_values()]
    store = "".join(_store_line(name) for name in public_values())
    pushes = []
    for group, why in whys:
        pushes.append(
            f"# Country scope: the {group} group looked: its situation history moves on (the oldest look drops out).\n"
            f"pp_cplan_hq_push_{why} = {{\n"
            + "".join(f"\tpp_cplan_copy_num = {{ from = {HQ_VAR}_{why}_{k - 1} to = {HQ_VAR}_{why}_{k} }}\n"
                      for k in range(HISTORY_LOOKS, 1, -1))
            + f"\tset_variable = {{ name = {HQ_VAR}_{why}_1 value = {{ value = pp_cplan_fx_{group}_sit add = 100 }} }}\n"
            + "\t# the window's chart reads these kept numbers\n"
            + "".join(_store_line(name) for name in history_values(group))
            + "}\n"
        )
    return (
        "\n# ---- Forecast for the window (construction_plan_forecast.py; the rules never read these numbers) ----\n\n"
        "# Country scope, at a pass's start before pp_cplan_purses_fill writes: the new gold and what each group was handed\n"
        f"# at the end of the last pass go into their running means (up to {MEAN_PASSES} passes). Not the first pass after\n"
        "# the plan was switched on (pp_cplan_fc_skip): it shares out the whole treasury above the reserve.\n"
        "pp_cplan_forecast_measure = {\n"
        f"\tif = {{\n\t\tlimit = {{ has_variable = {FC_SKIP} }}\n\t\tremove_variable = {FC_SKIP}\n\t}}\n"
        "\telse = {\n"
        "\t\tsave_temporary_scope_value_as = { name = pp_cplan_fcf value = pp_cplan_fc_flow_next }\n"
        + reads
        + f"\t\tset_variable = {{ name = {FC_FLOW} value = {{ value = scope:pp_cplan_fcf add = 100 }} }}\n"
        + writes
        + f"\t\tif = {{\n\t\t\tlimit = {{ has_variable = {FC_N} }}\n\t\t\tchange_variable = {{ name = {FC_N} add = 1 }}\n\t\t}}\n"
        f"\t\telse = {{\n\t\t\tset_variable = {{ name = {FC_N} value = 101 }}\n\t\t}}\n"
        "\t}\n}\n\n"
        "# Country scope (the plan was switched on, pp_cplan_history_clear): the means and the situation history start\n"
        "# afresh, and the next pass is not measured.\n"
        "pp_cplan_forecast_clear = {\n"
        f"\tset_variable = {{ name = {FC_SKIP} value = yes }}\n" + "".join(clear) + "}\n\n"
        + "\n".join(pushes)
        + "\n# Country scope: the window's numbers are worked out once and kept (the public names read them): at the end of\n"
        "# every pass, after each daily slice of the Locations look, and when the player changes a weight, the reserve or\n"
        "# a line, switches the plan on, sets or takes off a plan, or ticks something on the Towns and Buildings tab.\n"
        "# Every formula reads the game's state, never a kept number, so the order of the writes does not matter.\n"
        "pp_cplan_forecast_store = {\n" + store + "}\n"
    )
