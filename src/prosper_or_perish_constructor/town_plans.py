"""Town-right plans (branch town-plans, 2026-11-19, Jan).

The player's one decision per location is a town right used as a plan: "this location is for lumber". A plan is a
town right without conditions and without a bonus (`pp_plan_<plan>`), set and removed by the mod's own button on any
owned location, rural ones included, several per location. The Construction Plan reads the held plan rights
(`has_town_rights`) and builds toward them: the good's producers, forced, tier after tier as they unlock, a higher
location rank where the producers need one, and the good's charter and rights where the mod has them.

Plans: one per good that has a forced goods target (location_profiles.targets), plus the two below.

This module holds the naming contract every part of the feature shares and the finalize pass that writes:

* ``in_game/common/town_rights/pp_plan_town_rights.txt``: one right per plan (RIGHT_BODY);
* ``main_menu/localization/english/pp_plan_town_rights_l_english.yml``: each right's name and description;
* ``main_menu/gfx/interface/icons/town_rights/pp_plan_<plan>.dds``: its icon (the good's icon; food and trade: a map
  mode's), in the game format;
* ``in_game/common/scripted_triggers/pp_town_plans_generated.txt``: ``pp_tplan_held``;
* ``in_game/common/script_values/pp_town_plans_generated.txt``: ``pp_tplan_on_<plan>``;
* ``in_game/common/scripted_effects/pp_town_plans_generated.txt``: per plan whose producers all need a higher rank than
  a rural settlement, its turn ``pp_tplan_do_<plan>`` (raise the rank where none of them stands and the rank is too low,
  else the goods target) and the rank raise ``pp_tplan_raise`` (Towns and Buildings' ``pp_cplan_country_rank_up``, paid
  from the Locations group's purse, ``why = 105``), and the plan settings' effects (``pp_tplan_pb_*``);
* ``in_game/common/scripted_guis/pp_town_plan_settings.txt``: the plan settings' buttons (see "Plan settings" below);
  the settings' script values go into the values file above.

The monthly pass that runs a held plan is location_profiles.render_marks (``pp_lplan_location_marks``, one
``pp_lplan_mark`` per plan) and the hand-written ``pp_lplan_mark`` (scripted_effects/pp_location_profiles.txt: the plan
engine of the Locations group; Location Profiles and the building marks are gone).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# The right's key is PLAN_PREFIX + plan, e.g. pp_plan_lumber, pp_plan_food, pp_plan_trade.
PLAN_PREFIX = "pp_plan_"

# Plans that are no good: food (the buildings that feed the province) and trade (the trade buildings).
EXTRA_PLANS: tuple[str, ...] = ("food", "trade")

# Script names (location scope unless noted):
#   trigger       pp_tplan_held            the location holds at least one plan right
#   script value  pp_tplan_on_<plan>       1 while the location holds that plan right, else 0
#   effect        pp_tplan_flip = { g = <plan> }   sets the plan right, or takes it off when held (the button)
#   scripted GUI  pp_tplan_toggle          scope location, scope:pp_key = flag:<plan>
#   variables     pp_lplan_st_g_<plan>     the plan's state (1..14, location_profiles.STATES), pp_lplan_est_g_<plan> its payback
HELD_TRIGGER = "pp_tplan_held"
ON_VALUE_PREFIX = "pp_tplan_on_"
FLIP_EFFECT = "pp_tplan_flip"
TOGGLE_GUI = "pp_tplan_toggle"
DO_PREFIX = "pp_tplan_do_"  # a plan's turn where its producers may need a higher rank, and the food plan's turn
RAISE_EFFECT = "pp_tplan_raise"

# The goods target (location_profiles: pp_lprof_t_<target>) of the two extra plans.
FOOD_TARGET = "food"  # producers of the staple foods and the Province Food buildings (location_profiles._read_targets)
TRADE_TARGET = "trade_category"  # the trade buildings ([construction_plan] trade_plan, location_profiles._read_targets)
EXTRA_TARGETS = {"food": FOOD_TARGET, "trade": TRADE_TARGET}
# The food plan's turn (2026-11-20, Jan: farms first, kitchens second, a Tavern only while the store is short) runs
# these targets instead of its whole list (FOOD_TARGET, which stays the plan's buildings): the staple food producers,
# then where they have nothing to do the kitchens, with the taverns while the province's store is short.
FOOD_FARMS_TARGET = "food_farms"
FOOD_KITCHENS_TARGET = "food_kitchens"
FOOD_KITCHENS_TAVERNS_TARGET = "food_kitchens_taverns"
OWN_TURNS = ("food",)  # plans with their own turn pp_tplan_do_<plan> whatever their rank (render_food_turn)

WHY = 105  # the Locations group's purse (construction_plan GROUP_WHY "profiles")
FAIL_RANK = 108  # pp_lprof_fail: the plan needs a higher rank and the raise cannot start here now (state 11)

# ---- Plan settings (2026-11-20, Jan: baseline settings the player sees and may change; defaults = just use it) ----
# Country variables (a variable at 0 counts as unset, so 0 is never stored):
#   pp_tplan_pb_all         payback limit of every plan: index 1..N into PAYBACK_STEPS (years); unset = any payback
#   pp_tplan_pb_<plan>      the plan's own limit: 1..N, or PB_ANY (N + 1) = any payback; unset = same as all plans
#   pp_tplan_loss_ok        set: a plan may add a level to a building that loses money; unset (default) = never
#   pp_tplan_staff_off      set: plans do not wait for free workers; unset (default) = they wait
#   pp_tplan_order_best     set: several plans in a location go best payback first; unset (default) = they take turns
#   pp_tplan_free_off       set: plans close no other businesses for their workers; unset (default) = they do
#                           (plan_closer.py, scripted_effects/pp_plan_closer.txt)
#   pp_tplan_alone          set: the Businesses rule builds nothing in a location that holds a plan; unset (default) =
#                           it builds there too, by its own payback and market limit (scripted_triggers/
#                           pp_construction_plan.txt pp_cplan_business_site; a plan waiting for workers always comes first)
#   pp_tplan_rights_off     set: plans grant no charter and no rights (no political influence spent); unset (default) =
#                           they grant them
#   pp_tplan_pb_some      set by the settings' effects while any payback limit is set (the pass then works out
#                           the business estimates of first levels and tier upgrades)
# Script values (country scope, the GUI reads them): pp_tplan_pb_years_all / pp_tplan_pb_years_<plan> (limit in years,
# 0 = any; a plan's includes the all-plans value), pp_tplan_pb_own_<plan> (1 = its own setting), pp_tplan_loss_n
# (1 = never at a loss), pp_tplan_staff_n (1 = waits for workers), pp_tplan_order_n (1 = take turns), pp_tplan_close_n
# (1 = the game's close-buildings automation is on), pp_tplan_free_n (1 = plans close other businesses for workers),
# pp_tplan_alone_n (1 = other businesses may be built in planned locations), pp_tplan_rights_n (1 = plans grant their
# charter and rights).
# Scripted GUIs (scope country, scripted_guis/pp_town_plan_settings.txt): pp_tplan_pb_up / pp_tplan_pb_down
# (scope:pp_key = flag:<plan> or flag:all), pp_tplan_pb_reset (flag:<plan>), pp_tplan_toggle_loss / _staff / _order /
# _close / _free / _alone / _rights.
PAYBACK_STEPS: tuple[int, ...] = (1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50)
PB_ANY = len(PAYBACK_STEPS) + 1  # a plan's own "any payback"
PB_ALL = "all"  # the all-plans key (flag:all, pp_tplan_pb_all, pp_tplan_pb_years_all)
PB_VAR_PREFIX = "pp_tplan_pb_"
PB_YEARS_PREFIX = "pp_tplan_pb_years_"
PB_OWN_PREFIX = "pp_tplan_pb_own_"
PB_SOME_VAR = "pp_tplan_pb_some"
LOSS_OK_VAR = "pp_tplan_loss_ok"
STAFF_OFF_VAR = "pp_tplan_staff_off"
ORDER_BEST_VAR = "pp_tplan_order_best"
FREE_OFF_VAR = "pp_tplan_free_off"
ALONE_VAR = "pp_tplan_alone"
RIGHTS_OFF_VAR = "pp_tplan_rights_off"
LOSS_VALUE = "pp_tplan_loss_n"
STAFF_VALUE = "pp_tplan_staff_n"
ORDER_VALUE = "pp_tplan_order_n"
CLOSE_VALUE = "pp_tplan_close_n"
FREE_VALUE = "pp_tplan_free_n"
ALONE_VALUE = "pp_tplan_alone_n"
RIGHTS_VALUE = "pp_tplan_rights_n"
CLOSE_SYSTEM = "closebuildings"  # the game's automated system (set_automated_system / is_system_automated)
PB_UP_GUI = "pp_tplan_pb_up"
PB_DOWN_GUI = "pp_tplan_pb_down"
PB_RESET_GUI = "pp_tplan_pb_reset"
TOGGLE_LOSS_GUI = "pp_tplan_toggle_loss"
TOGGLE_STAFF_GUI = "pp_tplan_toggle_staff"
TOGGLE_ORDER_GUI = "pp_tplan_toggle_order"
TOGGLE_CLOSE_GUI = "pp_tplan_toggle_close"
TOGGLE_FREE_GUI = "pp_tplan_toggle_free"
TOGGLE_ALONE_GUI = "pp_tplan_toggle_alone"
TOGGLE_RIGHTS_GUI = "pp_tplan_toggle_rights"
SETTINGS_GUIS = Path("in_game/common/scripted_guis/pp_town_plan_settings.txt")


def pb_var(key: str) -> str:
    """The country variable of a plan's payback limit (key = a plan or PB_ALL)."""
    return PB_VAR_PREFIX + key


def pb_years_value(key: str) -> str:
    """The script value of a plan's effective payback limit in years (0 = any); key = a plan or PB_ALL."""
    return PB_YEARS_PREFIX + key


def pb_own_value(plan: str) -> str:
    return PB_OWN_PREFIX + plan

RIGHTS = Path("in_game/common/town_rights/pp_plan_town_rights.txt")
LOC = Path("main_menu/localization/english/pp_plan_town_rights_l_english.yml")
ICONS = Path("main_menu/gfx/interface/icons/town_rights")
TRIGGERS = Path("in_game/common/scripted_triggers/pp_town_plans_generated.txt")
VALUES = Path("in_game/common/script_values/pp_town_plans_generated.txt")
EFFECTS = Path("in_game/common/scripted_effects/pp_town_plans_generated.txt")
HEADER = "﻿# Generated by ppc finalize (town_plans.py); do not edit by hand.\n"

# One plan right. Engine (static check of 1.4.9, 2026-11-19): a held right whose potential is false is never
# stripped, and potential = no keeps it out of the game's grant list and away from the AI (construction_plan_country
# skips it: switched off); the engine counts every held right against local_possible_town_rights, so +1 on the right
# frees the slot it takes; kept_at_conquest = no destroys it on a hostile owner change (default yes: the conqueror
# would inherit the plan). No is_specialization (a UI filter), no upgrades_to.
RIGHT_BODY = """{key} = {{
	potential = {{ always = no }}
	kept_at_conquest = no
	location_modifier = {{
		local_possible_town_rights = 1
	}}
	color = {color}
}}
"""

# Location ranks from the lowest; a building may stand on a rank when its flag (rural_settlement / town / city) is yes.
RANKS = ("rural_settlement", "town", "city")
# A missing flag: the building_types readme names no default. rural_settlement counts as no: the repo reads it so
# (tests/test_rural_town_goods.py: rural-capable = rural_settlement = yes), and the AI's urbanization ban measured on
# that reading (memory ai-rural-urbanization-ban: transport_office, no flag, is town-only). Not checked in the engine.
# A missing town / city flag stays unknown (no plan has only such producers today).
DEFAULT_FLAGS = {"rural_settlement": "no"}
ICON_ROOTS = (Path("main_menu"), Path("in_game"))
GOODS_ICON = "gfx/interface/icons/trade_goods/icon_goods_{good}.dds"
EXTRA_ICONS = {"food": "gfx/interface/icons/map_modes/province_food.dds", "trade": "gfx/interface/icons/map_modes/market.dds"}
PLAN_SATURATION = 0.45  # the plans' colours (plan_color)
PLAN_VALUE = 0.62
EXTRA_NAMES = {"food": "Food", "trade": "Trade"}


def right_key(plan: str) -> str:
    """The town right of a plan."""
    return f"{PLAN_PREFIX}{plan}"


def plan_keys(goods: Iterable[str]) -> list[str]:
    """Every plan, in order: the goods that have a forced goods target (in the caller's order), then the extra plans."""
    keys = [*goods, *EXTRA_PLANS]
    if len(set(keys)) != len(keys):
        raise ValueError("a plan key appears twice")
    return keys


def is_plan_right(key: str) -> bool:
    """True for a plan right's key."""
    return key.startswith(PLAN_PREFIX)


@dataclass(frozen=True)
class Plan:
    key: str
    target: str  # the goods target it runs: pp_lprof_t_<target>
    candidates: tuple[str, ...]  # the target's buildings (location_profiles.targets)
    rank: str | None  # the lowest rank (RANKS) on which one of them may stand; None = a flag is unknown (no raise)

    @property
    def right(self) -> str:
        return right_key(self.key)

    @property
    def suffix(self) -> str:
        """The plan in the mark machinery's variable names (pp_lplan_st_<suffix>)."""
        return f"g_{self.key}"

    @property
    def on_value(self) -> str:
        return ON_VALUE_PREFIX + self.key

    @property
    def raises(self) -> bool:
        """None of its producers may stand on a rural settlement: its turn may raise the rank first."""
        return self.rank in RANKS[1:]

    @property
    def do(self) -> str:
        """The effect a held plan runs in the location's turn."""
        return f"{DO_PREFIX}{self.key}" if self.raises or self.key in OWN_TURNS else f"pp_lprof_t_{self.target}"


@dataclass
class Result:
    plans: list[Plan] = field(default_factory=list)
    unknown_rank: list[str] = field(default_factory=list)  # plans whose lowest rank is unknown (a flag missing)
    missing_icons: list[str] = field(default_factory=list)
    files_changed: int = 0


def lowest_rank(flags: Iterable[dict[str, str]]) -> str | None:
    """The lowest rank on which any of the buildings (their top-level keys) may stand. A building may stand on a rank
    whose flag is yes; a missing flag takes DEFAULT_FLAGS, else it is unknown: the first rank where none says yes and
    one says nothing gives None."""
    flags = list(flags)
    for rank in RANKS:
        values = [keys.get(rank, DEFAULT_FLAGS.get(rank)) for keys in flags]
        if "yes" in values:
            return rank
        if any(value is None for value in values):
            return None
    return None


def plans(repo: Path, project: Path, mod_root: Path, vanilla_root: Path) -> list[Plan]:
    """Every plan in order: the goods with a forced goods target in the picker's order, then food and trade."""
    from prosper_or_perish_constructor import construction_plan as cp
    from prosper_or_perish_constructor import location_profiles as lpf

    found, _ = lpf.targets(repo, project, mod_root, vanilla_root)
    goods = [good for good in lpf.target_goods(repo, project) if found.get(good)]
    database = cp._database(mod_root, vanilla_root, cp.BUILDING_TYPES)
    out: list[Plan] = []
    for key in plan_keys(goods):
        target = EXTRA_TARGETS.get(key, key)
        candidates = tuple(c.name for c in found.get(target, ()))
        if not candidates:
            raise ValueError(f"plan {key}: its target {target} builds nothing")
        rank = lowest_rank(database[name][0] for name in candidates)
        out.append(Plan(key, target, candidates, rank))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# rights, text, icons


def plan_color(index: int, count: int) -> str:
    """Plan i of n: its own colour, hues spread evenly at one saturation and value (no two town rights may share a
    colour: EU5 logs every pair and the town-rights map mode cannot tell them apart; the goods' named colours are taken
    by the charters and vanilla rights, tests/test_town_rights_order.py)."""
    return f"hsv {{ {(index + 0.5) / count:.3f} {PLAN_SATURATION:.3f} {PLAN_VALUE:.3f} }}"


def render_rights(items: list[Plan]) -> str:
    parts = [
        HEADER,
        "# The plan rights (town_plans.py): the player's plan for a location, set and removed by the mod's own button\n"
        "# (grant_town_rights / revoke_town_rights_of_type); the Construction Plan builds toward every held plan.\n\n",
    ]
    for index, plan in enumerate(items):
        parts.append(RIGHT_BODY.format(key=plan.right, color=plan_color(index, len(items))) + "\n")
    return "".join(parts)


_LOC_LINE = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s*"(.*)"\s*$')


def english_names(mod_root: Path, vanilla_root: Path, keys: Iterable[str]) -> dict[str, str]:
    """The English text of plain loc keys (the goods' names): the mod's files (replace too) over the game's."""
    wanted = set(keys)
    found: dict[str, str] = {}
    for root in (mod_root / "main_menu/localization", vanilla_root / "game/main_menu/localization/english"):
        if not root.is_dir():
            continue
        paths = sorted(root.rglob("*_l_english.yml"))
        for path in paths:
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                match = _LOC_LINE.match(line)
                if match and match.group(1) in wanted and match.group(1) not in found:
                    found[match.group(1)] = match.group(2)
    return found


def _quote(text: str) -> str:
    return text.replace('"', '\\"')


def describe(plan: Plan, charters: set[str]) -> str:
    """A plan right's description: what the plan does for the player (no numbers, linked)."""
    if plan.key == "food":
        what = ("builds here the buildings that feed the [province|e]: the producers of [pp_staple_foods|e], the "
                "[ShowBuildingTypeName('cookshop')|e] and the [ShowBuildingTypeName('tavern')|e], as they become possible")
    elif plan.key == "trade":
        what = ("builds here the trade buildings, such as the [ShowBuildingTypeName('marketplace')|e], as they become "
                "possible")
    else:
        what = f"builds here the producers of [ShowGoodsName('{plan.key}')|e], tier after tier as they become possible"
    parts = [f"Your plan for this [location|e]: the Construction Plan {what}."]
    if plan.raises:
        need = "a town" if plan.rank == "town" else "a city"
        parts.append(f"They need {need}, so the plan raises the settlement's [location_rank|e] when it can.")
    if plan.key in charters:
        parts.append(f"Where the conditions of the [ShowGoodsName('{plan.key}')|e] specialization [town_rights|e] hold, "
                     "the plan grants them.")
    parts.append("The plan itself gives no bonus, and the location keeps its room for other [town_rights|e].")
    return " ".join(parts)


def charter_goods(mod_root: Path) -> set[str]:
    """Goods with a PP specialization charter or rights (pp_<good>_charter / pp_<good>_rights)."""
    text = (mod_root / "in_game/common/town_rights/pp_specialization_town_rights.txt").read_text(encoding="utf-8-sig")
    return set(re.findall(r"(?m)^pp_(\w+?)_(?:charter|rights) = \{", text))


def render_loc(items: list[Plan], names: dict[str, str], charters: set[str]) -> str:
    lines = ["﻿l_english:\n"]
    for plan in items:
        name = EXTRA_NAMES.get(plan.key) or names.get(plan.key)
        if not name:
            raise ValueError(f"plan {plan.key}: no English name for the good")
        lines.append(f' {plan.right}: "Plan: {_quote(name)}"\n')
        lines.append(f' {plan.right}_desc: "{_quote(describe(plan, charters))}"\n')
    return "".join(lines)


def icon_source(plan: Plan, mod_root: Path, vanilla_root: Path) -> Path | None:
    relative = EXTRA_ICONS.get(plan.key) or GOODS_ICON.format(good=plan.key)
    for root in (mod_root, vanilla_root / "game"):
        for sub in ICON_ROOTS:
            if (root / sub / relative).is_file():
                return root / sub / relative
    return None


def render_icons(items: list[Plan], mod_root: Path, vanilla_root: Path) -> tuple[dict[Path, bytes], list[str]]:
    from prosper_or_perish_constructor import interface_dds

    out: dict[Path, bytes] = {}
    missing: list[str] = []
    for plan in items:
        source = icon_source(plan, mod_root, vanilla_root)
        if source is None:
            missing.append(plan.key)
            continue
        target = ICONS / f"{plan.right}.dds"
        out[mod_root / target] = interface_dds.normalized(source.read_bytes(), target)
    return out, missing


# ---------------------------------------------------------------------------------------------------------------------
# script


def render_triggers(items: list[Plan]) -> str:
    return (
        HEADER
        + "\n# Location scope: the location holds at least one plan right (the Locations group gives it its turn).\n"
        f"{HELD_TRIGGER} = {{\n\tOR = {{\n"
        + "".join(f"\t\thas_town_rights = town_rights_type:{plan.right}\n" for plan in items)
        + "\t}\n}\n"
    )


def render_values(items: list[Plan]) -> str:
    parts = [HEADER, "\n# Location scope: 1 while the location holds the plan right, else 0 (the GUI reads them).\n"]
    for plan in items:
        parts.append(f"{plan.on_value} = {{\n\tvalue = 0\n\tif = {{\n"
                     f"\t\tlimit = {{ has_town_rights = town_rights_type:{plan.right} }}\n\t\tvalue = 1\n\t}}\n}}\n")
    return "".join(parts)


def _num(value: float) -> str:
    return f"{value:g}"


# A plan target's outcome "nothing to do" (pp_lprof_fail): every building at its highest level (101) or none can be
# built here (102), no construction started or under way; the other reasons (workers, gold, goods, payback, loss,
# closed, rank) sit above 102.25.
NOTHING_TO_DO = "OR = {{\n{tab}\tNOT = {{ has_variable = pp_lprof_fail }}\n{tab}\tvar:pp_lprof_fail < 102.25\n{tab}}}"


def render_food_turn(plan: Plan) -> str:
    """The food plan's turn (2026-11-20, Jan): farms first, kitchens second, a Tavern only while the store is short."""
    def nothing(tab: str) -> str:
        return NOTHING_TO_DO.format(tab=tab)

    return (
        "\n# ---- The food plan's turn (2026-11-20, Jan: farms first, kitchens second, a Tavern only when the store is short) ----\n"
        "# Location scope, in the plan's turn (pp_lplan_mark). First the staple food producers (pp_lprof_t_"
        f"{FOOD_FARMS_TARGET}; a new one\n"
        "# starts where it pays best here, the food rule's return). Where they have nothing to do (every one at its highest\n"
        "# level, or none can be built here; no construction) and the plans are not being measured: the kitchens (their cap\n"
        "# follows the province's farms), with the taverns while the province's store is short by the food rule's own line\n"
        "# (NOT pp_pclose_store_ok, province scope). Nothing to do there either: \"nothing to build\" (2) where the farms or\n"
        "# the kitchens are at their highest level, else \"cannot be built here\" (6). The plan's buildings (the plan closer,\n"
        "# the settings, the picker) stay its whole list (pp_lprof_t_food is not run).\n"
        f"{plan.do} = {{\n"
        f"\tpp_lprof_t_{FOOD_FARMS_TARGET} = yes\n"
        "\tif = {\n\t\tlimit = {\n\t\t\tNOT = { has_variable = pp_lprof_st }\n\t\t\tNOT = { pp_lplan_measuring = yes }\n"
        f"\t\t\t{nothing(chr(9) * 3)}\n\t\t}}\n"
        "\t\t# the farms' outcome: 101 = at their highest level, else 102\n"
        "\t\tsave_temporary_scope_value_as = { name = pp_tplan_ff value = 102 }\n"
        "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\thas_variable = pp_lprof_fail\n\t\t\t\tvar:pp_lprof_fail < 101.25\n\t\t\t}\n"
        "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_ff value = 101 }\n\t\t}\n"
        "\t\tremove_variable = pp_lprof_fail\n\t\tremove_variable = pp_lprof_best\n"
        "\t\tif = {\n\t\t\tlimit = { province ?= { NOT = { pp_pclose_store_ok = yes } } }\n"
        f"\t\t\tpp_lprof_t_{FOOD_KITCHENS_TAVERNS_TARGET} = yes\n\t\t}}\n"
        f"\t\telse = {{\n\t\t\tpp_lprof_t_{FOOD_KITCHENS_TARGET} = yes\n\t\t}}\n"
        "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\tNOT = { has_variable = pp_lprof_st }\n"
        f"\t\t\t\t{nothing(chr(9) * 4)}\n\t\t\t}}\n"
        "\t\t\tif = {\n\t\t\t\tlimit = {\n\t\t\t\t\tOR = {\n\t\t\t\t\t\tscope:pp_tplan_ff < 101.5\n"
        "\t\t\t\t\t\tAND = {\n\t\t\t\t\t\t\thas_variable = pp_lprof_fail\n\t\t\t\t\t\t\tvar:pp_lprof_fail < 101.25\n"
        "\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t}\n"
        "\t\t\t\tremove_variable = pp_lprof_fail\n\t\t\t\tpp_lprof_fail = { r = 101 }\n\t\t\t}\n"
        "\t\t\telse = {\n\t\t\t\tpp_lprof_fail = { r = 102 }\n\t\t\t}\n"
        "\t\t}\n\t}\n}\n"
    )


def render_effects(items: list[Plan], ranks) -> str:
    """The turns of the plans whose producers need a higher rank, and the rank raise. ``ranks``: the town and city as
    construction_plan_country.read_ranks gives them (source rank, population minimum)."""
    from prosper_or_perish_constructor import construction_plan_country as cc

    parts = [
        HEADER,
        "\n# ---- Plans whose producers need a higher location rank (town_plans.py) ----\n"
        "# Location scope, in the plan's turn (pp_lplan_mark: forced, scope:pp_cplan_country set). Where none of the\n"
        "# producers stands and the rank is below the lowest one they may stand on, the turn raises the rank (one step,\n"
        "# pp_tplan_raise); else it runs the goods target. While the marks are measured the raise does nothing (it has no\n"
        "# payback to offer).\n",
    ]
    for plan in items:
        if not plan.raises:
            continue
        low = ("location_rank = location_rank:rural_settlement" if plan.rank == "town"
               else "NOT = { location_rank = location_rank:city }")
        types = " ".join(f"building_type = building_type:{name}" for name in plan.candidates)
        parts.append(
            f"\n{plan.do} = {{\n\tif = {{\n\t\tlimit = {{\n\t\t\t{low}\n"
            f"\t\t\tNOT = {{ any_buildings_in_location = {{ building_level > 0 OR = {{ {types} }} }} }}\n\t\t}}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ NOT = {{ pp_lplan_measuring = yes }} }}\n\t\t\t{RAISE_EFFECT} = yes\n\t\t}}\n"
            f"\t}}\n\telse = {{\n\t\tpp_lprof_t_{plan.target} = yes\n\t}}\n}}\n"
        )
    for plan in items:
        if plan.key in OWN_TURNS:
            if plan.raises:
                raise ValueError(f"plan {plan.key}: its own turn cannot raise the rank too")
            parts.append(render_food_turn(plan))
    parts.append(
        "\n# Location scope: the next rank up, from the rank below it (Towns and Buildings' upgrade, paid from the\n"
        f"# Locations group's purse: pp_cplan_country_rank_up why = {WHY}). Its state: 1 started, 7 gold (the purse saves\n"
        "# for it), 8 the market lacks the upgrade's construction goods, 11 the rank cannot be raised here now (only\n"
        "# conquered, a modifier forbids it, the population is below the rank's minimum, or the game refused it).\n"
        f"{RAISE_EFFECT} = {{\n"
    )
    for position, rank in enumerate(ranks):
        parts.append(f"\t{'if' if position == 0 else 'else_if'} = {{\n"
                     f"\t\tlimit = {{ location_rank = location_rank:{rank.source} }}\n"
                     f"\t\t{RAISE_EFFECT}_{rank.key} = yes\n\t}}\n")
    parts.append(f"\telse = {{\n\t\tpp_lprof_fail = {{ r = {FAIL_RANK} }}\n\t}}\n"
                 "\t# the ledger's step and value of the next construction in this turn\n"
                 "\tsave_temporary_scope_value_as = { name = pp_cplan_rs value = 0 }\n}\n")
    for rank in ranks:
        minimum = f"\t\t\t\tpopulation < {_num(rank.population)}\n" if rank.population > 0 else ""
        parts.append(
            f"\n{RAISE_EFFECT}_{rank.key} = {{\n\tif = {{\n\t\tlimit = {{\n\t\t\tOR = {{\n"
            "\t\t\t\tintegration_level = conquered\n\t\t\t\tmodifier:cannot_upgrade_location = yes\n"
            + minimum
            + "\t\t\t}\n\t\t}\n"
            f"\t\tpp_lprof_fail = {{ r = {FAIL_RANK} }}\n\t}}\n"
            f"\telse_if = {{\n\t\tlimit = {{ NOT = {{ pp_cplan_country_goods_{rank.key} = yes }} }}\n"
            f"\t\tpp_lprof_fail = {{ r = 105 }}\n\t\tpp_cplan_note_goods = {{ why = {WHY} }}\n\t}}\n"
            "\telse = {\n"
            "\t\tscope:pp_cplan_country = { remove_variable = pp_cplan_wait }\n"
            f"\t\tpp_cplan_country_rank_up = {{ rank = {rank.key} n = {cc.SAVE_RANK[rank.key]} why = {WHY} }}\n"
            "\t\tif = {\n\t\t\tlimit = { scope:pp_cplan_country = { has_variable = pp_cplan_hit } }\n"
            "\t\t\tset_variable = { name = pp_lprof_st value = 101 }\n\t\t}\n"
            "\t\telse_if = {\n\t\t\tlimit = { scope:pp_cplan_country = { has_variable = pp_cplan_wait } }\n"
            "\t\t\tpp_lprof_fail = { r = 107 }\n\t\t}\n"
            f"\t\telse = {{\n\t\t\tpp_lprof_fail = {{ r = {FAIL_RANK} }}\n\t\t}}\n"
            "\t\tscope:pp_cplan_country = { remove_variable = pp_cplan_wait }\n"
            "\t}\n}\n"
        )
    return "".join(parts)


# ---------------------------------------------------------------------------------------------------------------------
# plan settings (country scope)


def _years_chain(var: str, indent: str) -> str:
    """value = the years of the step index var:<var> (1..N); an index past the steps leaves the value as it was."""
    lines = []
    for index, years in enumerate(PAYBACK_STEPS, 1):
        lines.append(f"{indent}{'if' if index == 1 else 'else_if'} = {{ limit = {{ var:{var} < {index + 0.5:g} }} "
                     f"value = {years} }}\n")
    return "".join(lines)


def render_settings_values(items: list[Plan]) -> str:
    all_var = pb_var(PB_ALL)
    parts = [
        "\n# ---- Plan settings (country scope; town_plans.py PAYBACK_STEPS, the settings tab reads them) ----\n"
        "# The payback limit in years, 0 = any payback: every plan's (pp_tplan_pb_all, a step of PAYBACK_STEPS), and each\n"
        f"# plan's own (pp_tplan_pb_<plan>: a step, {PB_ANY} = any payback; unset = the all-plans value).\n"
        f"{pb_years_value(PB_ALL)} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {all_var} }}\n"
        + _years_chain(all_var, "\t\t") + "\t}\n}\n",
    ]
    for plan in items:
        var = pb_var(plan.key)
        parts.append(
            f"{pb_years_value(plan.key)} = {{\n\tvalue = {pb_years_value(PB_ALL)}\n\tif = {{\n"
            f"\t\tlimit = {{ has_variable = {var} }}\n\t\tvalue = 0\n" + _years_chain(var, "\t\t") + "\t}\n}\n"
            f"{pb_own_value(plan.key)} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
            "\t\tvalue = 1\n\t}\n}\n"
        )
    parts.append(
        "\n# The switches, 1 = the default: never at a loss, wait for free workers, take turns, close other businesses for\n"
        "# a plan's workers, other businesses in planned locations, grant a plan's charter and rights; and the game's own\n"
        "# automation that closes buildings, 1 = on.\n"
        f"{LOSS_VALUE} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {LOSS_OK_VAR} }}\n\t\tvalue = 0\n\t}}\n}}\n"
        f"{STAFF_VALUE} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {STAFF_OFF_VAR} }}\n\t\tvalue = 0\n\t}}\n}}\n"
        f"{ORDER_VALUE} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {ORDER_BEST_VAR} }}\n\t\tvalue = 0\n\t}}\n}}\n"
        f"{CLOSE_VALUE} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ is_system_automated = {CLOSE_SYSTEM} }}\n\t\tvalue = 1\n\t}}\n}}\n"
        f"{FREE_VALUE} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {FREE_OFF_VAR} }}\n\t\tvalue = 0\n\t}}\n}}\n"
        f"{ALONE_VALUE} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {ALONE_VAR} }}\n\t\tvalue = 0\n\t}}\n}}\n"
        f"{RIGHTS_VALUE} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {RIGHTS_OFF_VAR} }}\n\t\tvalue = 0\n\t}}\n}}\n"
        "\n# One payback step from scope:pp_tplan_cur (the index it starts from, any = the last step + 1): longer (past the\n"
        "# last step: any payback) and shorter (from any: the last step; never below the first).\n"
        f"pp_tplan_pb_next_up = {{\n\tvalue = scope:pp_tplan_cur\n\tadd = 1\n\tmax = {PB_ANY}\n}}\n"
        "pp_tplan_pb_next_down = {\n\tvalue = scope:pp_tplan_cur\n\tsubtract = 1\n\tmin = 1\n}\n"
    )
    return "".join(parts)


def render_settings_effects(items: list[Plan]) -> str:
    all_var = pb_var(PB_ALL)
    keyed = "".join(f"\t\tflag:{plan.key} = {{ pp_tplan_pb_step = {{ var = {pb_var(plan.key)} dir = $dir$ all = no }} }}\n"
                    for plan in items)
    reset = "".join(f"\t\tflag:{plan.key} = {{ remove_variable = {pb_var(plan.key)} }}\n" for plan in items)
    some = "".join(f"\t\t\t\tAND = {{ has_variable = {pb_var(plan.key)} var:{pb_var(plan.key)} < {PB_ANY - 0.5:g} }}\n"
                   for plan in items)
    declare = "".join(f"\tset_variable = {{ name = pp_tplan_sflag value = flag:{key} }}\n"
                      for key in [PB_ALL] + [plan.key for plan in items])
    return (
        "\n# ---- Plan settings (country scope; the settings tab's buttons, scripted_guis/pp_town_plan_settings.txt) ----\n"
        "# scope:pp_key = flag:all or flag:<plan>: its payback limit one step $dir$ (up = longer, down = shorter).\n"
        "pp_tplan_pb_key = {\n\tswitch = {\n\t\ttrigger = scope:pp_key\n"
        f"\t\tflag:{PB_ALL} = {{ pp_tplan_pb_step = {{ var = {all_var} dir = $dir$ all = yes }} }}\n"
        + keyed + "\t}\n\tpp_tplan_pb_refresh = yes\n}\n"
        "\n# scope:pp_key = flag:<plan>: the plan's payback limit is the all-plans one again.\n"
        "pp_tplan_pb_key_reset = {\n\tswitch = {\n\t\ttrigger = scope:pp_key\n" + reset + "\t}\n\tpp_tplan_pb_refresh = yes\n}\n"
        "\n# The payback limit $var$ one step $dir$. It starts from its own step, else (a plan, $all$ = no) from the\n"
        f"# all-plans step, else from any payback ({PB_ANY}). The all-plans limit at any payback is unset; a plan keeps its\n"
        "# own value, any payback too.\n"
        "pp_tplan_pb_step = {\n"
        "\tif = {\n\t\tlimit = { has_variable = $var$ }\n"
        "\t\tsave_temporary_scope_value_as = { name = pp_tplan_cur value = var:$var$ }\n\t}\n"
        f"\telse_if = {{\n\t\tlimit = {{ always = $all$ }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = {PB_ANY} }}\n\t}}\n"
        f"\telse_if = {{\n\t\tlimit = {{ has_variable = {all_var} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = var:{all_var} }}\n\t}}\n"
        f"\telse = {{\n\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = {PB_ANY} }}\n\t}}\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_new value = pp_tplan_pb_next_$dir$ }\n"
        f"\tif = {{\n\t\tlimit = {{\n\t\t\talways = $all$\n\t\t\tscope:pp_tplan_new > {PB_ANY - 0.5:g}\n\t\t}}\n"
        "\t\tremove_variable = $var$\n\t}\n"
        "\telse = {\n\t\tset_variable = { name = $var$ value = scope:pp_tplan_new }\n\t}\n}\n"
        f"\n# {PB_SOME_VAR} while a payback limit is set anywhere (the pass then works out the estimates of first levels\n"
        "# and tier upgrades, pp_lplan_location_turn).\n"
        f"pp_tplan_pb_refresh = {{\n\tif = {{\n\t\tlimit = {{\n\t\t\tOR = {{\n\t\t\t\thas_variable = {all_var}\n" + some
        + f"\t\t\t}}\n\t\t}}\n\t\tset_variable = {{ name = {PB_SOME_VAR} value = yes }}\n\t}}\n"
        f"\telse = {{\n\t\tremove_variable = {PB_SOME_VAR}\n\t}}\n}}\n"
        "\n# Never runs (pp_lprof_run calls it under always = no): the flags the settings' buttons pass exist for the\n"
        "# script check.\n"
        "pp_tplan_settings_declare = {\n" + declare + "}\n"
    )


def render_settings_guis() -> str:
    guard = "\tscope = country\n\tis_valid = {\n\t\tis_ai = no\n\t}\n"

    def gui(name: str, comment: str, effect: str) -> str:
        return f"\n# {comment}\n{name} = {{\n{guard}\teffect = {{\n{effect}\t}}\n}}\n"

    return "".join([
        HEADER,
        "# The Construction Plan's plan settings (town_plans.py): the payback limit of every plan and of each plan, and\n"
        "# the switches. Player only (observers' commands are dropped; the script checks the country is a player's).\n"
        "# scope:pp_key = flag:all or flag:<plan>.\n",
        gui(PB_UP_GUI, "One payback step longer (past the last step: any payback).",
            "\t\tpp_tplan_pb_key = { dir = up }\n"),
        gui(PB_DOWN_GUI, "One payback step shorter (from any payback: the last step; never below the first).",
            "\t\tpp_tplan_pb_key = { dir = down }\n"),
        gui(PB_RESET_GUI, "The plan's payback limit is the all-plans one again.", "\t\tpp_tplan_pb_key_reset = yes\n"),
        gui(TOGGLE_LOSS_GUI, "Plans may add levels to buildings that lose money, or never (the default).",
            f"\t\tpp_cplan_flip = {{ var = {LOSS_OK_VAR} }}\n"),
        gui(TOGGLE_STAFF_GUI, "Plans wait for free workers (the default), or not.",
            f"\t\tpp_cplan_flip = {{ var = {STAFF_OFF_VAR} }}\n"),
        gui(TOGGLE_ORDER_GUI, "Several plans in one location take turns (the default), or go best payback first.",
            f"\t\tpp_cplan_flip = {{ var = {ORDER_BEST_VAR} }}\n"),
        gui(TOGGLE_CLOSE_GUI, "The game's own automation that closes buildings losing money: on or off.",
            f"\t\tif = {{\n\t\t\tlimit = {{ is_system_automated = {CLOSE_SYSTEM} }}\n"
            f"\t\t\tset_automated_system = {{ system = {CLOSE_SYSTEM} activate = no }}\n\t\t}}\n"
            f"\t\telse = {{\n\t\t\tset_automated_system = {{ system = {CLOSE_SYSTEM} activate = yes }}\n\t\t}}\n"),
        gui(TOGGLE_FREE_GUI, "Plans close other businesses for their workers (the default), or not; switched off, every\n"
            "# building the rule closed opens again (scripted_effects/pp_plan_closer.txt).",
            f"\t\tpp_cplan_flip = {{ var = {FREE_OFF_VAR} }}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ has_variable = {FREE_OFF_VAR} }}\n\t\t\tpp_pclose_undo_all = yes\n\t\t}}\n"),
        gui(TOGGLE_ALONE_GUI, "The Businesses rule also builds in locations with a plan (the default), or not there\n"
            "# (scripted_triggers/pp_construction_plan.txt, pp_cplan_business_site).",
            f"\t\tpp_cplan_flip = {{ var = {ALONE_VAR} }}\n"),
        gui(TOGGLE_RIGHTS_GUI, "Plans grant their charter and rights (the default), or none.",
            f"\t\tpp_cplan_flip = {{ var = {RIGHTS_OFF_VAR} }}\n"),
    ])


# ---------------------------------------------------------------------------------------------------------------------


def _write_text(path: Path, text: str, write: bool) -> bool:
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    if old == text:
        return False
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return True


def _write_bytes(path: Path, data: bytes, write: bool) -> bool:
    if path.is_file() and path.read_bytes() == data:
        return False
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return True


def apply(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, write: bool = True) -> Result:
    """Writes the plan rights, their text and icons and the plan's triggers, values and rank raise."""
    from prosper_or_perish_constructor import construction_plan_country as cc

    items = plans(repo, project, mod_root, vanilla_root)
    result = Result(plans=items, unknown_rank=[plan.key for plan in items if plan.rank is None])
    names = english_names(mod_root, vanilla_root, [plan.key for plan in items])
    texts = {
        mod_root / RIGHTS: render_rights(items),
        mod_root / LOC: render_loc(items, names, charter_goods(mod_root)),
        mod_root / TRIGGERS: render_triggers(items),
        mod_root / VALUES: render_values(items) + render_settings_values(items),
        mod_root / EFFECTS: render_effects(items, cc.read_ranks(mod_root, vanilla_root)) + render_settings_effects(items),
        mod_root / SETTINGS_GUIS: render_settings_guis(),
    }
    icons, result.missing_icons = render_icons(items, mod_root, vanilla_root)
    result.files_changed = sum(_write_text(path, text, write) for path, text in texts.items())
    result.files_changed += sum(_write_bytes(path, data, write) for path, data in icons.items())
    return result


def summary(result: Result) -> str:
    raising = [plan.key for plan in result.plans if plan.raises]
    return (f"Town plans: {len(result.plans)} plan rights, {len(raising)} raise the rank first"
            + (f", lowest rank unknown for: {', '.join(result.unknown_rank)}" if result.unknown_rank else "")
            + (f"; NO ICON for: {', '.join(result.missing_icons)}" if result.missing_icons else "")
            + f", {result.files_changed} files changed.")
