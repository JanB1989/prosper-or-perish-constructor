"""Location plans (2026-11-19, Jan; a plain marker on the location since 2026-11-21).

The player's one decision per location is a plan: "this location is for lumber". A plan is a marker on the location
(the location variable ``pp_tplan_p_<plan>``), set and removed by the mod's own button on any owned location, rural
ones included, several per location. It is no town right and gives nothing by itself (2026-11-21, Jan: "We just use
our plans, and the plans apply the relevant town rights if the setting is turned on"; until then every plan was a
town right ``pp_plan_<plan>`` without conditions or bonus, which sat beside the real rights in the game's list). The
Construction Plan reads the markers and builds toward them: the good's producers, forced, tier after tier as they
unlock, a higher location rank where the producers need one, and, while the setting "Grant a plan's charter and
rights" is on, the good's real charter and rights where the mod has them (construction_plan_country.py).

Plans: one per good that has a forced goods target (location_profiles.targets), plus the two below.

Where a plan is kept:

* location variable ``pp_tplan_p_<plan>`` (yes): the location holds the plan;
* location variable ``pp_tplan_any`` (yes): it holds at least one (the trigger ``pp_tplan_held``; kept in step by the
  button's effect ``pp_tplan_flip``, which asks ``pp_tplan_held_scan`` after it took a plan off);
* country variable list ``pp_tplan_locs``: the country's locations with a plan (the Locations look and the charter
  look walk it: script has no iterator over the locations that carry a variable).

A location that changes owner loses its plans (``pp_tplan_owner_changed`` on the game's
``on_location_changed_owner`` runs ``pp_tplan_strip``); the Locations look also takes off the list what the country
no longer owns (``pp_lprof_gather``).

This module holds the naming contract every part of the feature shares and the finalize pass that writes:

* ``in_game/common/scripted_triggers/pp_town_plans_generated.txt``: ``pp_tplan_held``, ``pp_tplan_held_scan``;
* ``in_game/common/scripted_effects/pp_town_plans_generated.txt``: ``pp_tplan_strip`` (every plan and what the plans
  left on a location goes); per plan whose producers all need a higher rank than a rural settlement, its turn
  ``pp_tplan_do_<plan>`` (raise the rank where none of them stands and the rank is too low, else the goods target)
  and the rank raise ``pp_tplan_raise`` (Towns and Buildings' ``pp_cplan_country_rank_up``, paid from the Locations
  group's purse, ``why = 105``), and the plan settings' effects (``pp_tplan_pb_*``);
* ``in_game/common/script_values/pp_town_plans_generated.txt``: the settings' and options' script values;
* ``in_game/common/scripted_guis/pp_town_plan_settings.txt``: the plan settings' buttons (see "Plan settings" below);
* the plan options (2026-11-20, "Plan options" below, contract town_plan_options.py): their values, effects, buttons,
  the trigger ``pp_tplan_eff_low`` and the turns' option checks (the rank raise, the food plan's parts, the trade
  plan's groups ``pp_tplan_trade_split``), in the same files.

It also removes what the plan rights left in the mod folder (``stale_paths``: the rights file, their text, their
icons).

The monthly pass that runs a held plan is location_profiles.render_marks (``pp_lplan_location_marks``, one
``pp_lplan_mark`` per plan) and the hand-written ``pp_lplan_mark`` (scripted_effects/pp_location_profiles.txt: the plan
engine of the Locations group; Location Profiles and the building marks are gone).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# The plan marker: the location variable PLAN_VAR_PREFIX + plan, e.g. pp_tplan_p_lumber, pp_tplan_p_food.
PLAN_VAR_PREFIX = "pp_tplan_p_"
ANY_VAR = "pp_tplan_any"  # location: it holds at least one plan
LOCS_LIST = "pp_tplan_locs"  # country: its locations that hold a plan

# Plans that are no good: food (the buildings that feed the province) and trade (the trade buildings).
EXTRA_PLANS: tuple[str, ...] = ("food", "trade")

# Script names (location scope unless noted):
#   trigger       pp_tplan_held            the location holds at least one plan (has_variable = pp_tplan_any)
#   trigger       pp_tplan_held_scan       the same, asked of every plan marker (after a plan was taken off)
#   effect        pp_tplan_flip = { g = <plan> }   sets the plan, or takes it off when held (the button)
#   effect        pp_tplan_strip           every plan and what the plans left here goes (owner change)
#   scripted GUI  pp_tplan_toggle          scope location, scope:pp_key = flag:<plan>
#   variables     pp_tplan_p_<plan>        the plan marker; pp_lplan_st_g_<plan> the plan's state (1..16,
#                 location_profiles.STATES), pp_lplan_est_g_<plan> its payback
HELD_TRIGGER = "pp_tplan_held"
HELD_SCAN_TRIGGER = "pp_tplan_held_scan"
STRIP_EFFECT = "pp_tplan_strip"
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

# ---- Plan options (2026-11-20, Jan: "food and trade need other options ... for the goods some additional options,
# let's not go overboard"; the names, kinds and texts the window renders: town_plan_options.py) ----
# Country variables (0 counts as unset, never stored; unset = the behaviour before the options existed):
#   pp_tplan_effv_all       lowest production efficiency of every goods plan: index 1..N into EFF_STEPS (%); unset = none
#   pp_tplan_effv_<plan>    a goods plan's own line: 1..N, or EFF_NONE (N + 1) = none; unset = same as all plans
#   pp_tplan_effv_some      set by the options' effects while any line is set (the pass then works out the location's
#                           lasting production efficiency, pp_tplan_eff_here)
#   pp_tplan_raise_off      set: a plan whose producers need a higher rank never raises it (state 11); unset = it does
#   pp_tplan_food_farms_off / pp_tplan_food_kitchens_off   set: the Food plan builds no staple food makers / kitchens
#   pp_tplan_food_taverns   the Food plan's Taverns, the state + 1 for the two states that are not the default:
#                           1 = never, 3 = always; unset = while the province's store is short (state 1, the default)
#   pp_tplan_food_store     index 1..N into FOOD_STORE_STEPS (months): the Food plan builds only while the province's
#                           store lasts less than that; unset = always
#   pp_tplan_trade_market_off / pp_tplan_trade_port_off / pp_tplan_trade_centre_off   set: the Trade plan builds none of
#                           the Marketplace line / the Port Authority / the market centre buildings
#   pp_tplan_trade_use      index 1..N into TRADE_USE_STEPS (%): the Trade plan builds only where at least that share of
#                           the country's merchant capacity in the location's market is in use; unset = always
# Script values (country scope, plain readouts for the window) and scripted GUIs: town_plan_options.OPTIONS.
# What "lasting production efficiency" is (pp_tplan_eff_here, location scope, in % + 1000): the location's
# local_production_efficiency plus its owner's global_production_efficiency, the two production efficiency modifiers
# every building of the location gets (no modifier is per building or per category), minus the short-lived ones of
# EFF_SHORT_LIVED: the event modifiers the game adds for at most five years, and raised levies. Left out because they
# belong to one building, not the location: a newly built building's establishment, the province's raw materials share
# of a method's inputs and the bonus per level.
EFF_STEPS: tuple[int, ...] = (-10, -5, 0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75)
EFF_NONE = len(EFF_STEPS) + 1  # a goods plan's own "none"
EFF_VAR_PREFIX = "pp_tplan_effv_"
EFF_SOME_VAR = "pp_tplan_effv_some"
EFF_PCT_PREFIX = "pp_tplan_eff_pct_"
EFF_SET_PREFIX = "pp_tplan_eff_set_"
EFF_OWN_PREFIX = "pp_tplan_eff_own_"
EFF_LINE_PREFIX = "pp_tplan_eff_line_"  # internal: a plan's line + 1000, 0 = none (food and trade: always 0)
EFF_HERE = "pp_tplan_eff_here"
EFF_LOW_TRIGGER = "pp_tplan_eff_low"
EFF_OFFSET = 1000
# The short-lived production efficiency modifiers taken out (vanilla 1.4.9, read 2026-11-20: every add_*_modifier of a
# modifier with local_ / global_production_efficiency, kept where the game adds it for at most five years), per the
# scope that holds them; their amounts are read from the static modifier files at finalize. raised_levies: the
# engine's own location modifier while the location's levies are raised.
EFF_SHORT_LIVED: dict[str, tuple[str, ...]] = {
    "location": ("raised_levies", "proper_administrative_ledgers_modifier",
                 "location_innovative_tooling_techniques_modifier", "local_quality_standards_modifier"),
    "province": ("pious_wealth_modifier", "province_innovative_tooling_techniques_modifier",
                 "poor_tool_quality_modifier", "local_artisans_retired_modifier", "new_tooling_techniques_modifier"),
    "country": ("trade_and_production_cutbacks", "calvinist_work_ethic", "free_trade_of_goods",
                "influential_guild_members", "guilds_cooperating", "uinal_yaxkin_modifier", "quinquatria_modifier"),
}
EFF_MODIFIER = {"location": "local_production_efficiency", "province": "local_production_efficiency",
                "country": "global_production_efficiency"}
FAIL_EFF = 103.25  # pp_lprof_fail: the location's lasting production efficiency is below the plan's line (state 15)
FAIL_SETTINGS = 102.75  # pp_lprof_fail: the plan's options hold it back here (state 16)
RAISE_OFF_VAR = "pp_tplan_raise_off"
RAISE_VALUE = "pp_tplan_raise_n"
FOOD_FARMS_OFF_VAR = "pp_tplan_food_farms_off"
FOOD_KITCHENS_OFF_VAR = "pp_tplan_food_kitchens_off"
FOOD_TAVERNS_VAR = "pp_tplan_food_taverns"
FOOD_TAVERNS_NEVER = 1  # FOOD_TAVERNS_VAR = the state + 1
FOOD_TAVERNS_ALWAYS = 3
FOOD_STORE_VAR = "pp_tplan_food_store"
FOOD_STORE_STEPS: tuple[int, ...] = (3, 6, 9, 12, 18, 24)
TRADE_MARKET_OFF_VAR = "pp_tplan_trade_market_off"
TRADE_PORT_OFF_VAR = "pp_tplan_trade_port_off"
TRADE_CENTRE_OFF_VAR = "pp_tplan_trade_centre_off"
TRADE_USE_VAR = "pp_tplan_trade_use"
TRADE_USE_STEPS: tuple[int, ...] = (10, 25, 50, 75, 90)
TRADE_USE_HERE = "pp_tplan_trade_use_here"
# The Trade plan's buildings in three groups, each with its switch: the Marketplace line (marketplace and the tiers that
# replace it), the Port Authority, the market centre's buildings (the rest of [construction_plan] trade_plan).
TRADE_MARKET_ROOT = "marketplace"
TRADE_PORT_BUILDINGS: tuple[str, ...] = ("port_authority",)
TRADE_GROUPS: tuple[tuple[str, str], ...] = (
    ("trade_market", TRADE_MARKET_OFF_VAR), ("trade_port", TRADE_PORT_OFF_VAR), ("trade_centre", TRADE_CENTRE_OFF_VAR))
FOOD_TAVERNS_TARGET = "food_taverns"  # the Food plan's Taverns alone (kitchens switched off)
TRADE_SPLIT_EFFECT = "pp_tplan_trade_split"
# The switches: script value, variable (set = off), scripted GUI.
OPTION_SWITCHES: tuple[tuple[str, str, str], ...] = (
    (RAISE_VALUE, RAISE_OFF_VAR, "pp_tplan_toggle_raise"),
    ("pp_tplan_food_farms_n", FOOD_FARMS_OFF_VAR, "pp_tplan_toggle_food_farms"),
    ("pp_tplan_food_kitchens_n", FOOD_KITCHENS_OFF_VAR, "pp_tplan_toggle_food_kitchens"),
    ("pp_tplan_trade_market_n", TRADE_MARKET_OFF_VAR, "pp_tplan_toggle_trade_market"),
    ("pp_tplan_trade_port_n", TRADE_PORT_OFF_VAR, "pp_tplan_toggle_trade_port"),
    ("pp_tplan_trade_centre_n", TRADE_CENTRE_OFF_VAR, "pp_tplan_toggle_trade_centre"),
)


def pb_var(key: str) -> str:
    """The country variable of a plan's payback limit (key = a plan or PB_ALL)."""
    return PB_VAR_PREFIX + key


def pb_years_value(key: str) -> str:
    """The script value of a plan's effective payback limit in years (0 = any); key = a plan or PB_ALL."""
    return PB_YEARS_PREFIX + key


def pb_own_value(plan: str) -> str:
    return PB_OWN_PREFIX + plan

TRIGGERS = Path("in_game/common/scripted_triggers/pp_town_plans_generated.txt")
VALUES = Path("in_game/common/script_values/pp_town_plans_generated.txt")
EFFECTS = Path("in_game/common/scripted_effects/pp_town_plans_generated.txt")
HEADER = "﻿# Generated by ppc finalize (town_plans.py); do not edit by hand.\n"
# What the plan rights left in the mod folder (a plan was a town right pp_plan_<plan> until 2026-11-21): removed by
# apply. The icons: every pp_plan_*.dds of the town rights' icon folder.
STALE_FILES = (Path("in_game/common/town_rights/pp_plan_town_rights.txt"),
               Path("main_menu/localization/english/pp_plan_town_rights_l_english.yml"))
STALE_ICONS = Path("main_menu/gfx/interface/icons/town_rights")
STALE_ICON_PATTERN = "pp_plan_*.dds"

# Location ranks from the lowest; a building may stand on a rank when its flag (rural_settlement / town / city) is yes.
RANKS = ("rural_settlement", "town", "city")
# A missing flag: the building_types readme names no default. rural_settlement counts as no: the repo reads it so
# (tests/test_rural_town_goods.py: rural-capable = rural_settlement = yes), and the AI's urbanization ban measured on
# that reading (memory ai-rural-urbanization-ban: transport_office, no flag, is town-only). Not checked in the engine.
# A missing town / city flag stays unknown (no plan has only such producers today).
DEFAULT_FLAGS = {"rural_settlement": "no"}


def plan_var(plan: str) -> str:
    """The location variable that marks a plan."""
    return f"{PLAN_VAR_PREFIX}{plan}"


def plan_keys(goods: Iterable[str]) -> list[str]:
    """Every plan, in order: the goods that have a forced goods target (in the caller's order), then the extra plans."""
    keys = [*goods, *EXTRA_PLANS]
    if len(set(keys)) != len(keys):
        raise ValueError("a plan key appears twice")
    return keys


@dataclass(frozen=True)
class Plan:
    key: str
    target: str  # the goods target it runs: pp_lprof_t_<target>
    candidates: tuple[str, ...]  # the target's buildings (location_profiles.targets)
    rank: str | None  # the lowest rank (RANKS) on which one of them may stand; None = a flag is unknown (no raise)

    @property
    def var(self) -> str:
        """The location variable that marks the plan."""
        return plan_var(self.key)

    @property
    def suffix(self) -> str:
        """The plan in the mark machinery's variable names (pp_lplan_st_<suffix>)."""
        return f"g_{self.key}"

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
    files_changed: int = 0
    stale_removed: int = 0  # files of the former plan rights taken out of the mod folder


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
# script


def render_triggers(items: list[Plan]) -> str:
    return (
        HEADER
        + "\n# Location scope: the location holds at least one plan (the Locations group gives it its turn). One variable,\n"
        f"# kept in step by the button's effect (pp_tplan_flip) and taken off with the plans ({STRIP_EFFECT}).\n"
        f"{HELD_TRIGGER} = {{\n\thas_variable = {ANY_VAR}\n}}\n"
        "\n# Location scope: the same, asked of every plan marker: after a plan was taken off, is one left?\n"
        f"{HELD_SCAN_TRIGGER} = {{\n\tOR = {{\n"
        + "".join(f"\t\thas_variable = {plan.var}\n" for plan in items)
        + "\t}\n}\n"
    )


def render_strip(items: list[Plan]) -> str:
    """Location scope: the location is no planned location any more (it changed owner): every plan marker, each plan's
    state and payback, and what the plans left here (the workers mark, the last plan that built, why a charter waits)
    go. The owner's list of planned locations (LOCS_LIST) is the caller's."""
    return (
        "\n# ---- A location loses its plans (town_plans.py) ----\n"
        "# Location scope (pp_tplan_owner_changed on the game's on_location_changed_owner; the Locations look's sweep,\n"
        "# pp_lprof_gather): every plan marker with its state and payback, the mark that it holds a plan, the workers\n"
        "# mark, the plan that built last and the reason a charter waits. The country's list of planned locations is\n"
        "# the caller's.\n"
        f"{STRIP_EFFECT} = {{\n"
        + "".join(f"\tremove_variable = {plan.var}\n\tremove_variable = pp_lplan_st_{plan.suffix}\n"
                  f"\tremove_variable = pp_lplan_est_{plan.suffix}\n" for plan in items)
        + f"\tremove_variable = {ANY_VAR}\n\tremove_variable = pp_lplan_wk\n\tremove_variable = pp_lplan_last\n"
        "\tif = {\n\t\tlimit = { has_variable = pp_tplan_cwait }\n\t\tremove_variable = pp_tplan_cwait\n\t}\n}\n"
    )


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

    c = "scope:pp_cplan_country"
    t = "\t"
    taverns_now = (
        # the Taverns now: always (option), or by default while the province's store is short (the food rule's line)
        f"OR = {{\n{t * 6}AND = {{\n{t * 7}{c} = {{ NOT = {{ has_variable = {FOOD_TAVERNS_VAR} }} }}\n"
        f"{t * 7}province ?= {{ NOT = {{ pp_pclose_store_ok = yes }} }}\n{t * 6}}}\n"
        f"{t * 6}{c} = {{\n{t * 7}has_variable = {FOOD_TAVERNS_VAR}\n"
        f"{t * 7}var:{FOOD_TAVERNS_VAR} > {FOOD_TAVERNS_ALWAYS - 0.5:g}\n{t * 6}}}\n{t * 5}}}"
    )
    tried = "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_tried value = 1 }\n"
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
        "# The plan's options (town_plans.py \"Plan options\", all unset = the above): the store limit (FOOD_STORE_VAR: nothing\n"
        f"# while the province's stored months, pp_location_stored_months, reach it: {FAIL_SETTINGS:g}, state 16), the farms\n"
        "# and the kitchens switched off, the Taverns never / while the store is short / always. Where every part is\n"
        f"# switched off, nothing is tried: state 16 ({FAIL_SETTINGS:g}).\n"
        f"{plan.do} = {{\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_hold value = 0 }\n"
        f"\tif = {{\n\t\tlimit = {{ {c} = {{ has_variable = {FOOD_STORE_VAR} }} }}\n"
        f"\t\t{c} = {{ save_temporary_scope_value_as = {{ name = pp_tplan_lim value = pp_tplan_food_store_months }} }}\n"
        "\t\tif = {\n\t\t\tlimit = { pp_location_stored_months >= scope:pp_tplan_lim }\n"
        "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_hold value = 1 }\n"
        f"\t\t\tpp_lprof_fail = {{ r = {FAIL_SETTINGS:g} }}\n\t\t}}\n\t}}\n"
        "\tif = {\n\t\tlimit = { scope:pp_tplan_hold < 0.5 }\n"
        "\t\tsave_temporary_scope_value_as = { name = pp_tplan_tried value = 0 }\n"
        f"\t\tif = {{\n\t\t\tlimit = {{ {c} = {{ NOT = {{ has_variable = {FOOD_FARMS_OFF_VAR} }} }} }}\n"
        f"\t\t\tpp_lprof_t_{FOOD_FARMS_TARGET} = yes\n" + tried + "\t\t}\n"
        "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\tNOT = { has_variable = pp_lprof_st }\n\t\t\t\tNOT = { pp_lplan_measuring = yes }\n"
        f"\t\t\t\t{nothing(chr(9) * 4)}\n\t\t\t}}\n"
        "\t\t\t# the farms' outcome: 101 = at their highest level, else 102\n"
        "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_ff value = 102 }\n"
        "\t\t\tif = {\n\t\t\t\tlimit = {\n\t\t\t\t\thas_variable = pp_lprof_fail\n\t\t\t\t\tvar:pp_lprof_fail < 101.25\n\t\t\t\t}\n"
        "\t\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_ff value = 101 }\n\t\t\t}\n"
        "\t\t\tremove_variable = pp_lprof_fail\n\t\t\tremove_variable = pp_lprof_best\n"
        f"\t\t\tif = {{\n\t\t\t\tlimit = {{\n\t\t\t\t\t{c} = {{ NOT = {{ has_variable = {FOOD_KITCHENS_OFF_VAR} }} }}\n"
        f"\t\t\t\t\t{taverns_now}\n\t\t\t\t}}\n"
        f"\t\t\t\tpp_lprof_t_{FOOD_KITCHENS_TAVERNS_TARGET} = yes\n" + "\t" + tried + "\t\t\t}\n"
        f"\t\t\telse_if = {{\n\t\t\t\tlimit = {{ {c} = {{ NOT = {{ has_variable = {FOOD_KITCHENS_OFF_VAR} }} }} }}\n"
        f"\t\t\t\tpp_lprof_t_{FOOD_KITCHENS_TARGET} = yes\n" + "\t" + tried + "\t\t\t}\n"
        f"\t\t\telse_if = {{\n\t\t\t\tlimit = {{\n\t\t\t\t\t{taverns_now}\n\t\t\t\t}}\n"
        f"\t\t\t\tpp_lprof_t_{FOOD_TAVERNS_TARGET} = yes\n" + "\t" + tried + "\t\t\t}\n"
        "\t\t\tif = {\n\t\t\t\tlimit = {\n\t\t\t\t\tNOT = { has_variable = pp_lprof_st }\n"
        f"\t\t\t\t\t{nothing(chr(9) * 5)}\n\t\t\t\t}}\n"
        "\t\t\t\tif = {\n\t\t\t\t\tlimit = {\n\t\t\t\t\t\tOR = {\n\t\t\t\t\t\t\tscope:pp_tplan_ff < 101.5\n"
        "\t\t\t\t\t\t\tAND = {\n\t\t\t\t\t\t\t\thas_variable = pp_lprof_fail\n\t\t\t\t\t\t\t\tvar:pp_lprof_fail < 101.25\n"
        "\t\t\t\t\t\t\t}\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n"
        "\t\t\t\t\tremove_variable = pp_lprof_fail\n\t\t\t\t\tpp_lprof_fail = { r = 101 }\n\t\t\t\t}\n"
        "\t\t\t\telse_if = {\n\t\t\t\t\tlimit = { scope:pp_tplan_tried > 0.5 }\n\t\t\t\t\tpp_lprof_fail = { r = 102 }\n\t\t\t\t}\n"
        f"\t\t\t\telse = {{\n\t\t\t\t\tremove_variable = pp_lprof_fail\n\t\t\t\t\tpp_lprof_fail = {{ r = {FAIL_SETTINGS:g} }}\n"
        "\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n"
    )


def render_trade_split() -> str:
    """The trade plan's buildings group by group, once a group is switched off (plan options, 2026-11-20)."""
    c = "scope:pp_cplan_country"
    nothing = NOTHING_TO_DO.format(tab="\t\t\t")
    parts = [
        "\n# ---- The trade plan with a group of its buildings switched off (plan options, 2026-11-20) ----\n"
        "# Location scope, in the trade plan's turn (pp_tplan_do_trade, where it does not raise the rank). Its groups in\n"
        "# start order, each only while its switch is on: the Marketplace line, the Port Authority, the market centre's\n"
        "# buildings (pp_lprof_t_trade_market / _port / _centre: the same lists and start order as pp_lprof_t_trade_category,\n"
        "# which runs while every group is on). A group runs where the groups before it have nothing to do (every building\n"
        "# at its highest level, or none can be built here; no construction) and, after the first group that ran, not while\n"
        "# the plans are being measured. Nothing to do anywhere: \"nothing to build\" (101) where a group is at its highest\n"
        f"# level, else \"cannot be built here\" (102); every group switched off: state 16 ({FAIL_SETTINGS:g}).\n"
        f"{TRADE_SPLIT_EFFECT} = {{\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_ff value = 0 }\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_tried value = 0 }\n"
    ]
    for target, var in TRADE_GROUPS:
        parts.append(
            f"\tif = {{\n\t\tlimit = {{\n\t\t\t{c} = {{ NOT = {{ has_variable = {var} }} }}\n"
            "\t\t\tNOT = { has_variable = pp_lprof_st }\n"
            "\t\t\tOR = {\n\t\t\t\tscope:pp_tplan_tried < 0.5\n\t\t\t\tNOT = { pp_lplan_measuring = yes }\n\t\t\t}\n"
            f"\t\t\t{nothing}\n\t\t}}\n"
            "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\thas_variable = pp_lprof_fail\n\t\t\t\tvar:pp_lprof_fail < 101.25\n\t\t\t}\n"
            "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_ff value = 1 }\n\t\t}\n"
            "\t\tremove_variable = pp_lprof_fail\n\t\tremove_variable = pp_lprof_best\n"
            f"\t\tpp_lprof_t_{target} = yes\n"
            "\t\tsave_temporary_scope_value_as = { name = pp_tplan_tried value = 1 }\n\t}\n"
        )
    parts.append(
        f"\tif = {{\n\t\tlimit = {{\n\t\t\tNOT = {{ has_variable = pp_lprof_st }}\n\t\t\t{nothing}\n\t\t}}\n"
        "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\tOR = {\n\t\t\t\t\tscope:pp_tplan_ff > 0.5\n"
        "\t\t\t\t\tAND = {\n\t\t\t\t\t\thas_variable = pp_lprof_fail\n\t\t\t\t\t\tvar:pp_lprof_fail < 101.25\n\t\t\t\t\t}\n"
        "\t\t\t\t}\n\t\t\t}\n\t\t\tremove_variable = pp_lprof_fail\n\t\t\tpp_lprof_fail = { r = 101 }\n\t\t}\n"
        "\t\telse_if = {\n\t\t\tlimit = { scope:pp_tplan_tried > 0.5 }\n\t\t\tpp_lprof_fail = { r = 102 }\n\t\t}\n"
        f"\t\telse = {{\n\t\t\tremove_variable = pp_lprof_fail\n\t\t\tpp_lprof_fail = {{ r = {FAIL_SETTINGS:g} }}\n\t\t}}\n"
        "\t}\n}\n"
    )
    return "".join(parts)


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
        "# payback to offer). With the plan option \"raise a settlement for its plan\" off (pp_tplan_raise_off) the turn\n"
        f"# raises nothing and the plan waits for a higher rank (pp_lprof_fail {FAIL_RANK}, state 11). The trade plan's\n"
        "# turn first asks its option \"trade capacity in use\" (pp_tplan_trade_use: below the line nothing happens here,\n"
        f"# {FAIL_SETTINGS:g}, state 16) and, with a group of its buildings switched off, runs its groups one after the other\n"
        f"# ({TRADE_SPLIT_EFFECT}).\n",
    ]
    c = "scope:pp_cplan_country"
    for plan in items:
        if not plan.raises:
            continue
        low = ("location_rank = location_rank:rural_settlement" if plan.rank == "town"
               else "NOT = { location_rank = location_rank:city }")
        types = " ".join(f"building_type = building_type:{name}" for name in plan.candidates)
        trade = plan.key == "trade"
        run = f"\t\tpp_lprof_t_{plan.target} = yes\n"
        if trade:
            switched = "".join(f"\t\t\t\t\t\thas_variable = {var}\n" for _, var in TRADE_GROUPS)
            run = (f"\t\tif = {{\n\t\t\tlimit = {{\n\t\t\t\t{c} = {{\n\t\t\t\t\tNOR = {{\n" + switched
                   + f"\t\t\t\t\t}}\n\t\t\t\t}}\n\t\t\t}}\n\t\t\tpp_lprof_t_{plan.target} = yes\n\t\t}}\n"
                   f"\t\telse = {{\n\t\t\t{TRADE_SPLIT_EFFECT} = yes\n\t\t}}\n")
        body = (
            f"\tif = {{\n\t\tlimit = {{\n\t\t\t{low}\n"
            f"\t\t\tNOT = {{ any_buildings_in_location = {{ building_level > 0 OR = {{ {types} }} }} }}\n\t\t}}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ NOT = {{ pp_lplan_measuring = yes }} }}\n"
            f"\t\t\tif = {{\n\t\t\t\tlimit = {{ {c} = {{ has_variable = {RAISE_OFF_VAR} }} }}\n"
            f"\t\t\t\tpp_lprof_fail = {{ r = {FAIL_RANK} }}\n\t\t\t}}\n"
            f"\t\t\telse = {{\n\t\t\t\t{RAISE_EFFECT} = yes\n\t\t\t}}\n\t\t}}\n"
            f"\t}}\n\telse = {{\n{run}\t}}\n"
        )
        if trade:
            # the option "trade capacity in use" first: below its line nothing happens here (no raise either)
            body = (
                "\tsave_temporary_scope_value_as = { name = pp_tplan_hold value = 0 }\n"
                f"\tif = {{\n\t\tlimit = {{ {c} = {{ has_variable = {TRADE_USE_VAR} }} }}\n"
                f"\t\t{c} = {{ save_temporary_scope_value_as = {{ name = pp_tplan_lim value = pp_tplan_trade_use_pct }} }}\n"
                f"\t\tif = {{\n\t\t\tlimit = {{ {TRADE_USE_HERE} < scope:pp_tplan_lim }}\n"
                "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_hold value = 1 }\n"
                f"\t\t\tpp_lprof_fail = {{ r = {FAIL_SETTINGS:g} }}\n\t\t}}\n\t}}\n"
                "\tif = {\n\t\tlimit = { scope:pp_tplan_hold < 0.5 }\n"
                + "".join(f"\t{line}\n" if line else "\n" for line in body.rstrip("\n").split("\n"))
                + "\t}\n"
            )
        parts.append(f"\n{plan.do} = {{\n{body}}}\n")
    trade_plans = [plan for plan in items if plan.key == "trade"]
    if trade_plans:
        if not trade_plans[0].raises:
            raise ValueError("the trade plan's turn is written with the rank raise (its producers need a town)")
        parts.append(render_trade_split())
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


def _years_chain(var: str, indent: str, steps: tuple[int, ...] = PAYBACK_STEPS) -> str:
    """value = the step of the index var:<var> (1..N); an index past the steps leaves the value as it was."""
    lines = []
    for index, years in enumerate(steps, 1):
        lines.append(f"{indent}{'if' if index == 1 else 'else_if'} = {{ limit = {{ var:{var} < {index + 0.5:g} }} "
                     f"value = {years} }}\n")
    return "".join(lines)


def eff_var(key: str) -> str:
    """The country variable of a goods plan's lowest production efficiency (key = a plan or PB_ALL)."""
    return EFF_VAR_PREFIX + key


def _number(text: str, numbers: dict[str, float]) -> float | None:
    try:
        return float(text)
    except ValueError:
        return numbers.get(text)


def eff_short_lived_amounts(mod_root: Path, vanilla_root: Path) -> dict[str, list[tuple[str, float]]]:
    """Per scope (EFF_SHORT_LIVED) the short-lived modifiers with the production efficiency they give (the mod's files
    over the game's, the DLC folders included; a named amount through the plain-number script values)."""
    from prosper_or_perish_constructor import construction_plan as cp

    numbers = cp.script_value_numbers(mod_root, vanilla_root)
    data: dict[str, tuple[dict[str, str], str]] = {}
    for folder in cp.STATIC_MODIFIERS:
        for dlc in sorted((vanilla_root / "game" / "dlc").glob("*")):
            directory = dlc / folder
            for path in sorted(directory.glob("*.txt")) if directory.is_dir() else ():
                for block, body in cp._blocks(path.read_text(encoding="utf-8-sig", errors="replace")):
                    data[block.split(":")[-1]] = (cp._top_keys(body), body)
        data.update(cp._database(mod_root, vanilla_root, folder))
    found: dict[str, list[tuple[str, float]]] = {}
    for scope, names in EFF_SHORT_LIVED.items():
        found[scope] = []
        for name in names:
            if name not in data:
                raise ValueError(f"EFF_SHORT_LIVED: no static modifier {name}")
            text = data[name][0].get(EFF_MODIFIER[scope])
            amount = _number(text, numbers) if text is not None else None
            if amount is None:
                raise ValueError(f"EFF_SHORT_LIVED: {name} has no {EFF_MODIFIER[scope]} amount ({text})")
            found[scope].append((name, amount))
    return found


def render_option_values(items: list[Plan], short_lived: dict[str, list[tuple[str, float]]]) -> str:
    """The plan options' script values (town_plan_options.OPTIONS; country scope, plain readouts) and the two location
    values the pass reads."""
    goods = [plan for plan in items if plan.key not in EXTRA_PLANS]
    all_var = eff_var(PB_ALL)
    parts = [
        "\n# ---- Plan options (country scope; town_plans.py \"Plan options\", town_plan_options.py; the window reads them) ----\n"
        "# Lowest production efficiency in %: every goods plan's (pp_tplan_effv_all, a step of EFF_STEPS) and each goods\n"
        f"# plan's own (pp_tplan_effv_<plan>: a step, {EFF_NONE} = none; unset = the all-plans line). _pct = the line shown\n"
        "# (0 while none), _set = 1 while a line holds (a line of 0 % is a line), _own = 1 while the plan has its own.\n"
        f"{EFF_PCT_PREFIX}{PB_ALL} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {all_var} }}\n"
        + _years_chain(all_var, "\t\t", EFF_STEPS) + "\t}\n}\n"
        f"{EFF_SET_PREFIX}{PB_ALL} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {all_var} }}\n\t\tvalue = 1\n\t}}\n}}\n",
    ]
    for plan in goods:
        var = eff_var(plan.key)
        parts.append(
            f"{EFF_PCT_PREFIX}{plan.key} = {{\n\tvalue = {EFF_PCT_PREFIX}{PB_ALL}\n\tif = {{\n"
            f"\t\tlimit = {{ has_variable = {var} }}\n\t\tvalue = 0\n" + _years_chain(var, "\t\t", EFF_STEPS) + "\t}\n}\n"
            f"{EFF_SET_PREFIX}{plan.key} = {{\n\tvalue = {EFF_SET_PREFIX}{PB_ALL}\n\tif = {{\n"
            f"\t\tlimit = {{ has_variable = {var} }}\n\t\tvalue = 0\n"
            f"\t\tif = {{ limit = {{ var:{var} < {EFF_NONE - 0.5:g} }} value = 1 }}\n\t}}\n}}\n"
            f"{EFF_OWN_PREFIX}{plan.key} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
            "\t\tvalue = 1\n\t}\n}\n"
        )
    parts.append(
        f"\n# The line a plan's turn compares with (pp_tplan_eff_low): its line in % + {EFF_OFFSET}, 0 = none (food and trade\n"
        "# have none).\n"
    )
    for plan in items:
        if plan.key in EXTRA_PLANS:
            parts.append(f"{EFF_LINE_PREFIX}{plan.key} = {{\n\tvalue = 0\n}}\n")
        else:
            parts.append(
                f"{EFF_LINE_PREFIX}{plan.key} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ {EFF_SET_PREFIX}{plan.key} > 0.5 }}\n"
                f"\t\tvalue = {EFF_PCT_PREFIX}{plan.key}\n\t\tadd = {EFF_OFFSET}\n\t}}\n}}\n"
            )
    parts.append(
        "\n# The switches, 1 = on (the default): raise a settlement for its plan, the Food plan's staple food makers and\n"
        "# kitchens, the Trade plan's Marketplace line, Port Authority and market centre buildings.\n"
        + "".join(f"{value} = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n\t\tvalue = 0\n\t}}\n}}\n"
                  for value, var, _ in OPTION_SWITCHES)
        + "# The Food plan's Taverns: 0 never, 1 while the province's store is short (the default), 2 always.\n"
        f"pp_tplan_food_taverns_n = {{\n\tvalue = 1\n\tif = {{\n\t\tlimit = {{ has_variable = {FOOD_TAVERNS_VAR} }}\n"
        f"\t\tvalue = var:{FOOD_TAVERNS_VAR}\n\t\tsubtract = 1\n\t}}\n}}\n"
        "# The Food plan builds only while the province's store lasts less than this many months (0 = always).\n"
        f"pp_tplan_food_store_months = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {FOOD_STORE_VAR} }}\n"
        + _years_chain(FOOD_STORE_VAR, "\t\t", FOOD_STORE_STEPS) + "\t}\n}\n"
        f"pp_tplan_food_store_set = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {FOOD_STORE_VAR} }}\n\t\tvalue = 1\n\t}}\n}}\n"
        "# The Trade plan builds only where at least this share (%) of the country's merchant capacity in the market is in\n"
        "# use (0 = always).\n"
        f"pp_tplan_trade_use_pct = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {TRADE_USE_VAR} }}\n"
        + _years_chain(TRADE_USE_VAR, "\t\t", TRADE_USE_STEPS) + "\t}\n}\n"
        f"pp_tplan_trade_use_set = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {TRADE_USE_VAR} }}\n\t\tvalue = 1\n\t}}\n}}\n"
        "\n# One step of the options' steppers from scope:pp_tplan_cur. The lowest production efficiency and the trade\n"
        "# capacity in use have \"none\" below their first step (0); the store limit has \"always\" past its last step.\n"
        f"pp_tplan_eff_next_up = {{\n\tvalue = scope:pp_tplan_cur\n\tadd = 1\n\tmax = {len(EFF_STEPS)}\n}}\n"
        "pp_tplan_eff_next_down = {\n\tvalue = scope:pp_tplan_cur\n\tsubtract = 1\n\tmin = 0\n}\n"
        f"pp_tplan_trade_use_next_up = {{\n\tvalue = scope:pp_tplan_cur\n\tadd = 1\n\tmax = {len(TRADE_USE_STEPS)}\n}}\n"
        "pp_tplan_trade_use_next_down = {\n\tvalue = scope:pp_tplan_cur\n\tsubtract = 1\n\tmin = 0\n}\n"
        f"pp_tplan_food_store_next_up = {{\n\tvalue = scope:pp_tplan_cur\n\tadd = 1\n\tmax = {len(FOOD_STORE_STEPS) + 1}\n}}\n"
        "pp_tplan_food_store_next_down = {\n\tvalue = scope:pp_tplan_cur\n\tsubtract = 1\n\tmin = 1\n}\n"
    )
    # location scope: what the pass compares
    subtract = []
    for scope, entries in short_lived.items():
        if not entries:
            continue
        check = {"location": "has_location_modifier", "province": "has_province_modifier",
                 "country": "has_country_modifier"}[scope]
        lines = "".join(f"{{tab}}if = {{{{ limit = {{{{ {check} = {name} }}}} "
                        f"{'subtract' if amount >= 0 else 'add'} = {_num(abs(amount))} }}}}\n"
                        for name, amount in entries)
        if scope == "location":
            subtract.append(lines.format(tab="\t"))
        else:
            link = "owner" if scope == "country" else "province"
            subtract.append(f"\t{link} ?= {{\n" + lines.format(tab="\t\t") + "\t}\n")
    parts.append(
        "\n# Location scope (in the pass): the location's lasting production efficiency in % + 1000 (plan option \"lowest\n"
        "# production efficiency\"): its local_production_efficiency and its owner's global_production_efficiency, the\n"
        "# production efficiency every building here gets, without the short-lived modifiers (town_plans.EFF_SHORT_LIVED:\n"
        "# the event modifiers the game adds for at most five years, and raised levies). A building's own terms\n"
        "# (establishment, the province's raw materials, the bonus per level) are left out.\n"
        f"{EFF_HERE} = {{\n\tvalue = modifier:local_production_efficiency\n"
        "\towner ?= { add = modifier:global_production_efficiency }\n"
        + "".join(subtract)
        + f"\tmultiply = 100\n\tadd = {EFF_OFFSET}\n}}\n"
        "\n# Location scope (in the pass: scope:pp_cplan_country): the share (%) of the country's merchant capacity in the\n"
        "# location's market that is in use (plan option \"trade capacity in use\"); 100 where it has none there yet (the\n"
        "# plan's buildings give the first).\n"
        f"{TRADE_USE_HERE} = {{\n\tvalue = 100\n\tmarket ?= {{\n"
        "\t\tif = {\n\t\t\tlimit = { \"merchant_capacity(scope:pp_cplan_country)\" > 0 }\n"
        "\t\t\tvalue = \"used_merchant_capacity(scope:pp_cplan_country)\"\n"
        "\t\t\tdivide = \"merchant_capacity(scope:pp_cplan_country)\"\n\t\t\tmultiply = 100\n\t\t}\n\t}\n}\n"
    )
    return "".join(parts)


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


def render_option_effects(items: list[Plan]) -> str:
    """The plan options' effects behind their buttons (country scope) and the triggers' location parts."""
    goods = [plan for plan in items if plan.key not in EXTRA_PLANS]
    all_var = eff_var(PB_ALL)
    keyed = "".join(f"\t\tflag:{plan.key} = {{ pp_tplan_eff_step = {{ var = {eff_var(plan.key)} dir = $dir$ all = no }} }}\n"
                    for plan in goods)
    reset = "".join(f"\t\tflag:{plan.key} = {{ remove_variable = {eff_var(plan.key)} }}\n" for plan in goods)
    some = "".join(f"\t\t\t\tAND = {{ has_variable = {eff_var(plan.key)} var:{eff_var(plan.key)} < {EFF_NONE - 0.5:g} }}\n"
                   for plan in goods)
    n_store = len(FOOD_STORE_STEPS)
    return (
        "\n# ---- Plan options (country scope; the Plans tab's buttons, scripted_guis/pp_town_plan_settings.txt) ----\n"
        "# scope:pp_key = flag:all or flag:<goods plan>: its lowest production efficiency one step $dir$ (up = higher).\n"
        "pp_tplan_eff_key = {\n\tswitch = {\n\t\ttrigger = scope:pp_key\n"
        f"\t\tflag:{PB_ALL} = {{ pp_tplan_eff_step = {{ var = {all_var} dir = $dir$ all = yes }} }}\n"
        + keyed + "\t}\n\tpp_tplan_eff_refresh = yes\n}\n"
        "\n# scope:pp_key = flag:<goods plan>: its line is the all-plans one again.\n"
        "pp_tplan_eff_key_reset = {\n\tswitch = {\n\t\ttrigger = scope:pp_key\n" + reset + "\t}\n\tpp_tplan_eff_refresh = yes\n}\n"
        "\n# The line $var$ one step $dir$, from its own step, else (a plan, $all$ = no) the all-plans step, else none (0).\n"
        f"# Below the first step: none (the all-plans line unset; a plan's own none is {EFF_NONE}).\n"
        "pp_tplan_eff_step = {\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_cur value = 0 }\n"
        f"\tif = {{\n\t\tlimit = {{ has_variable = $var$ }}\n\t\tif = {{\n\t\t\tlimit = {{ var:$var$ < {EFF_NONE - 0.5:g} }}\n"
        "\t\t\tsave_temporary_scope_value_as = { name = pp_tplan_cur value = var:$var$ }\n\t\t}\n\t}\n"
        f"\telse_if = {{\n\t\tlimit = {{\n\t\t\tNOT = {{ always = $all$ }}\n\t\t\thas_variable = {all_var}\n\t\t}}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = var:{all_var} }}\n\t}}\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_new value = pp_tplan_eff_next_$dir$ }\n"
        "\tif = {\n\t\tlimit = { scope:pp_tplan_new > 0.5 }\n\t\tset_variable = { name = $var$ value = scope:pp_tplan_new }\n\t}\n"
        "\telse_if = {\n\t\tlimit = { always = $all$ }\n\t\tremove_variable = $var$\n\t}\n"
        f"\telse = {{\n\t\tset_variable = {{ name = $var$ value = {EFF_NONE} }}\n\t}}\n}}\n"
        f"\n# {EFF_SOME_VAR} while a line holds anywhere (the pass then works out the location's lasting production\n"
        "# efficiency, pp_lplan_location_turn).\n"
        f"pp_tplan_eff_refresh = {{\n\tif = {{\n\t\tlimit = {{\n\t\t\tOR = {{\n\t\t\t\thas_variable = {all_var}\n" + some
        + f"\t\t\t}}\n\t\t}}\n\t\tset_variable = {{ name = {EFF_SOME_VAR} value = yes }}\n\t}}\n"
        f"\telse = {{\n\t\tremove_variable = {EFF_SOME_VAR}\n\t}}\n}}\n"
        "\n# The Food plan's Taverns, the next state: while the store is short (unset) -> always -> never -> while short.\n"
        "pp_tplan_food_taverns_next = {\n"
        f"\tif = {{\n\t\tlimit = {{ NOT = {{ has_variable = {FOOD_TAVERNS_VAR} }} }}\n"
        f"\t\tset_variable = {{ name = {FOOD_TAVERNS_VAR} value = {FOOD_TAVERNS_ALWAYS} }}\n\t}}\n"
        f"\telse_if = {{\n\t\tlimit = {{ var:{FOOD_TAVERNS_VAR} > {FOOD_TAVERNS_ALWAYS - 0.5:g} }}\n"
        f"\t\tset_variable = {{ name = {FOOD_TAVERNS_VAR} value = {FOOD_TAVERNS_NEVER} }}\n\t}}\n"
        f"\telse = {{\n\t\tremove_variable = {FOOD_TAVERNS_VAR}\n\t}}\n}}\n"
        "\n# The Food plan's store limit one step $dir$ (up = more months; past the last step: always, unset; from always\n"
        "# down: the last step).\n"
        "pp_tplan_food_store_step = {\n"
        f"\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = {n_store + 1} }}\n"
        f"\tif = {{\n\t\tlimit = {{ has_variable = {FOOD_STORE_VAR} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = var:{FOOD_STORE_VAR} }}\n\t}}\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_new value = pp_tplan_food_store_next_$dir$ }\n"
        f"\tif = {{\n\t\tlimit = {{ scope:pp_tplan_new > {n_store + 0.5:g} }}\n\t\tremove_variable = {FOOD_STORE_VAR}\n\t}}\n"
        f"\telse = {{\n\t\tset_variable = {{ name = {FOOD_STORE_VAR} value = scope:pp_tplan_new }}\n\t}}\n}}\n"
        "\n# The Trade plan's line of capacity in use one step $dir$ (up = a higher share; below the first step: always,\n"
        "# unset; from always up: the first step).\n"
        "pp_tplan_trade_use_step = {\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_cur value = 0 }\n"
        f"\tif = {{\n\t\tlimit = {{ has_variable = {TRADE_USE_VAR} }}\n"
        f"\t\tsave_temporary_scope_value_as = {{ name = pp_tplan_cur value = var:{TRADE_USE_VAR} }}\n\t}}\n"
        "\tsave_temporary_scope_value_as = { name = pp_tplan_new value = pp_tplan_trade_use_next_$dir$ }\n"
        f"\tif = {{\n\t\tlimit = {{ scope:pp_tplan_new < 0.5 }}\n\t\tremove_variable = {TRADE_USE_VAR}\n\t}}\n"
        f"\telse = {{\n\t\tset_variable = {{ name = {TRADE_USE_VAR} value = scope:pp_tplan_new }}\n\t}}\n}}\n"
    )


def render_option_triggers() -> str:
    """Location scope, in a plan's turn: the goods plan $g$ holds a line of lowest production efficiency and the
    location's lasting production efficiency (scope:pp_tplan_effh, pp_lplan_location_turn) is below it."""
    return (
        "\n# Location scope, in the plan $g$'s turn (pp_lplan_mark): a line of lowest production efficiency holds for it\n"
        "# (plan option, pp_tplan_effv_some first: nothing is worked out while no line is set anywhere) and the location's\n"
        "# lasting production efficiency (scope:pp_tplan_effh = pp_tplan_eff_here, saved as the turn began) is below it.\n"
        f"{EFF_LOW_TRIGGER} = {{\n\tscope:pp_cplan_country = {{\n\t\thas_variable = {EFF_SOME_VAR}\n"
        f"\t\t{EFF_LINE_PREFIX}$g$ > 0.5\n\t\t{EFF_LINE_PREFIX}$g$ > scope:pp_tplan_effh\n\t}}\n}}\n"
    )


def render_option_guis() -> str:
    guard = "\tscope = country\n\tis_valid = {\n\t\tis_ai = no\n\t}\n"

    def gui(name: str, comment: str, effect: str) -> str:
        return f"\n# {comment}\n{name} = {{\n{guard}\teffect = {{\n{effect}\t}}\n}}\n"

    parts = [
        "\n# ---- Plan options (2026-11-20, town_plan_options.py) ----\n",
        gui("pp_tplan_eff_down", "Lowest production efficiency one step lower (below the first step: none).",
            "\t\tpp_tplan_eff_key = { dir = down }\n"),
        gui("pp_tplan_eff_up", "Lowest production efficiency one step higher (from none: the first step).",
            "\t\tpp_tplan_eff_key = { dir = up }\n"),
        gui("pp_tplan_eff_reset", "The goods plan's lowest production efficiency is the all-plans one again.",
            "\t\tpp_tplan_eff_key_reset = yes\n"),
    ]
    for _value, var, name in OPTION_SWITCHES:
        parts.append(gui(name, f"A plan option on (the default) or off ({var} set).", f"\t\tpp_cplan_flip = {{ var = {var} }}\n"))
    parts += [
        gui("pp_tplan_cycle_food_taverns", "The Food plan's Taverns: while the store is short (the default), always, never.",
            "\t\tpp_tplan_food_taverns_next = yes\n"),
        gui("pp_tplan_food_store_down", "The Food plan's store limit: fewer months (from always: the longest).",
            "\t\tpp_tplan_food_store_step = { dir = down }\n"),
        gui("pp_tplan_food_store_up", "The Food plan's store limit: more months (past the longest: always).",
            "\t\tpp_tplan_food_store_step = { dir = up }\n"),
        gui("pp_tplan_trade_use_down", "The Trade plan's capacity in use: a lower share (below the lowest: always).",
            "\t\tpp_tplan_trade_use_step = { dir = down }\n"),
        gui("pp_tplan_trade_use_up", "The Trade plan's capacity in use: a higher share (from always: the lowest).",
            "\t\tpp_tplan_trade_use_step = { dir = up }\n"),
    ]
    return "".join(parts)


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


def stale_paths(mod_root: Path) -> list[Path]:
    """What the plan rights left in the mod folder (STALE_FILES, the plan rights' icons)."""
    found = [mod_root / relative for relative in STALE_FILES if (mod_root / relative).is_file()]
    icons = mod_root / STALE_ICONS
    if icons.is_dir():
        found += sorted(icons.glob(STALE_ICON_PATTERN))
    return found


def apply(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, write: bool = True) -> Result:
    """Writes the plans' triggers, values, effects and settings buttons, and removes what the plan rights left."""
    from prosper_or_perish_constructor import construction_plan_country as cc

    items = plans(repo, project, mod_root, vanilla_root)
    result = Result(plans=items, unknown_rank=[plan.key for plan in items if plan.rank is None])
    texts = {
        mod_root / TRIGGERS: render_triggers(items) + render_option_triggers(),
        mod_root / VALUES: (HEADER + render_settings_values(items)
                            + render_option_values(items, eff_short_lived_amounts(mod_root, vanilla_root))),
        mod_root / EFFECTS: (render_effects(items, cc.read_ranks(mod_root, vanilla_root)) + render_strip(items)
                             + render_settings_effects(items) + render_option_effects(items)),
        mod_root / SETTINGS_GUIS: render_settings_guis() + render_option_guis(),
    }
    result.files_changed = sum(_write_text(path, text, write) for path, text in texts.items())
    stale = stale_paths(mod_root)
    result.stale_removed = len(stale)
    if write:
        for path in stale:
            path.unlink()
    return result


def summary(result: Result) -> str:
    raising = [plan.key for plan in result.plans if plan.raises]
    return (f"Location plans: {len(result.plans)} plans, {len(raising)} raise the rank first"
            + (f", lowest rank unknown for: {', '.join(result.unknown_rank)}" if result.unknown_rank else "")
            + (f"; {result.stale_removed} files of the former plan rights removed" if result.stale_removed else "")
            + f", {result.files_changed} files changed.")
