"""The plan options of the Construction Plan's Plans tab (2026-11-20, Jan: "food and trade need other options ... for
the goods some additional options, let's not go overboard").

This module is the contract between the script side (town_plans.py and the plans' look: the country variables, the
script values below, the scripted GUIs, the rules that read them) and the window side (town_plan_settings_gui.py,
which renders every entry of ``OPTIONS`` where its ``where`` says). The eight older shared settings and the payback
limit keep their own code in both modules; only the options added on 2026-11-20 are listed here.

Kinds:

* ``switch``: ``value`` is 1 (on) or 0 (off); ``guis`` = (toggle,); ``states`` = (text while off, text while on).
* ``cycle``: ``value`` is 0..n-1; ``guis`` = (next state,); ``states`` = one text per state.
* ``stepper``: ``value`` is the number shown, ``set_value`` is 1 while a limit is set and 0 while there is none;
  ``guis`` = (down, up), for ``per_plan`` also (reset,); ``states`` = (text while no limit is set, text with the
  number, ``{value}`` stands for the number).

``per_plan`` (like the payback limit): the option sits in the All plans block with the key ``all`` and on the card
of every goods plan with the plan's key. ``value``, ``set_value`` and ``own_value`` are then prefixes: + ``all`` for
the shared setting, + the plan's key for a plan (a plan's value is its effective one: its own, else the shared one);
``own_value`` + plan is 1 while the plan has its own setting. Its scripted GUIs take ``scope:pp_key`` =
``flag:all`` or ``flag:<plan>``.

Every scripted GUI has scope country and is the player's only. Every value is a country script value that only
reads variables (a visible widget evaluates it every frame). The defaults (no variable set) are the behaviour before
these options existed.
"""

from __future__ import annotations

from dataclasses import dataclass

ALL = "all"  # where: the All plans block
GOODS = "goods"  # where: the card of every goods plan
FOOD = "food"  # where: the Food plan's card
TRADE = "trade"  # where: the Trade plan's card


@dataclass(frozen=True)
class Option:
    key: str
    where: str
    kind: str
    label: str
    tooltip: str
    value: str
    guis: tuple[str, ...]
    states: tuple[str, ...]
    set_value: str = ""
    own_value: str = ""
    step_tooltips: tuple[str, str] = ("", "")
    per_plan: bool = False


ON_OFF = ("Off", "On")

OPTIONS: tuple[Option, ...] = (
    # ---- every plan ----
    Option(
        key="eff", where=ALL, kind="stepper", per_plan=True,
        label="Lowest production efficiency",
        tooltip=(
            "#T Lowest production efficiency#!\nA goods plan starts a first level, a further level or a newer tier "
            "only where the lasting [production_efficiency|e] of the [location|e] is at least this: what the location "
            "and your [country|e] give every [building|e] there. Effects that last only a few years and raised levies "
            "are left out, and so is what belongs to one building alone, such as a new building settling in. At none, "
            "a plan builds whatever the efficiency. Each goods plan below can have its own line."
        ),
        value="pp_tplan_eff_pct_", set_value="pp_tplan_eff_set_", own_value="pp_tplan_eff_own_",
        guis=("pp_tplan_eff_down", "pp_tplan_eff_up", "pp_tplan_eff_reset"),
        states=("none", "{value}%"),
        step_tooltips=("A lower line; below the lowest: none", "A higher line"),
    ),
    Option(
        key="raise", where=ALL, kind="switch",
        label="Raise a settlement for its plan",
        tooltip=(
            "#T Raise a settlement for its plan#!\nWhile on, where none of a plan's buildings can stand on the "
            "settlement's [location_rank|e], the plan raises the rank first and saves for it. Off: such a plan waits "
            "until you raise the settlement yourself."
        ),
        value="pp_tplan_raise_n", guis=("pp_tplan_toggle_raise",), states=ON_OFF,
    ),
    # ---- the Food plan ----
    Option(
        key="food_farms", where=FOOD, kind="switch",
        label="Farms and other staple food makers",
        tooltip=(
            "#T Staple food makers#!\nWhile on, the Food plan builds the buildings that make the "
            "[pp_staple_foods|e] here, before anything else. Off: it builds none of them and goes straight to the "
            "kitchens and Taverns."
        ),
        value="pp_tplan_food_farms_n", guis=("pp_tplan_toggle_food_farms",), states=ON_OFF,
    ),
    Option(
        key="food_kitchens", where=FOOD, kind="switch",
        label="Kitchens",
        tooltip=(
            "#T Kitchens#!\nWhile on, the Food plan builds the [ShowBuildingTypeName('cookshop')|e] and its newer "
            "kinds where the staple food makers have nothing left to build. Off: it builds no kitchens."
        ),
        value="pp_tplan_food_kitchens_n", guis=("pp_tplan_toggle_food_kitchens",), states=ON_OFF,
    ),
    Option(
        key="food_taverns", where=FOOD, kind="cycle",
        label="Taverns",
        tooltip=(
            "#T Taverns#!\nWhen the Food plan builds the [ShowBuildingTypeName('tavern')|e], always after the staple "
            "food makers: never, only while the [provincial_food|e] of the [province|e] is short (a normal year would "
            "leave little in store), or whenever one can be built."
        ),
        value="pp_tplan_food_taverns_n", guis=("pp_tplan_cycle_food_taverns",),
        states=("Never", "While the store is short", "Always"),
    ),
    Option(
        key="food_store", where=FOOD, kind="stepper",
        label="Build only while the store lasts less than",
        tooltip=(
            "#T A full store#!\nThe Food plan builds nothing while the [provincial_food|e] of the [province|e] lasts "
            "this many months or more. At always, it builds however full the store is."
        ),
        value="pp_tplan_food_store_months", set_value="pp_tplan_food_store_set",
        guis=("pp_tplan_food_store_down", "pp_tplan_food_store_up"),
        states=("always", "{value} months"),
        step_tooltips=("Fewer months", "More months; past the longest: always"),
    ),
    # ---- the Trade plan ----
    Option(
        key="trade_use", where=TRADE, kind="stepper",
        label="Build only while our trade capacity is used",
        tooltip=(
            "#T Trade capacity in use#!\nEvery building of the Trade plan adds [merchant_capacity|e]. The plan builds "
            "only where at least this share of the merchant capacity you already have in that location's [market|e] "
            "is in use; where you have none there yet, it builds. At always, it builds whether you use your capacity "
            "or not."
        ),
        value="pp_tplan_trade_use_pct", set_value="pp_tplan_trade_use_set",
        guis=("pp_tplan_trade_use_down", "pp_tplan_trade_use_up"),
        states=("always", "{value}%"),
        step_tooltips=("A lower share; below the lowest: always", "A higher share"),
    ),
    Option(
        key="trade_market", where=TRADE, kind="switch",
        label="Marketplaces",
        tooltip=(
            "#T Marketplaces#!\nWhile on, the Trade plan builds the [ShowBuildingTypeName('marketplace')|e] and its "
            "newer kinds. Off: it builds none of them."
        ),
        value="pp_tplan_trade_market_n", guis=("pp_tplan_toggle_trade_market",), states=ON_OFF,
    ),
    Option(
        key="trade_port", where=TRADE, kind="switch",
        label="[ShowBuildingTypeName('port_authority')|e]",
        tooltip=(
            "#T Port buildings#!\nWhile on, the Trade plan builds the [ShowBuildingTypeName('port_authority')|e]. "
            "Off: it does not."
        ),
        value="pp_tplan_trade_port_n", guis=("pp_tplan_toggle_trade_port",), states=ON_OFF,
    ),
    Option(
        key="trade_centre", where=TRADE, kind="switch",
        label="Market centre buildings",
        tooltip=(
            "#T Market centre buildings#!\nWhile on, the Trade plan builds the buildings of a [market|e] centre. "
            "Off: it builds none of them."
        ),
        value="pp_tplan_trade_centre_n", guis=("pp_tplan_toggle_trade_centre",), states=ON_OFF,
    ),
)


def options(where: str) -> tuple[Option, ...]:
    return tuple(option for option in OPTIONS if option.where == where)


def per_plan() -> tuple[Option, ...]:
    return tuple(option for option in OPTIONS if option.per_plan)


def value_names(plans: list[str]) -> set[str]:
    """Every country script value the options read, for the given goods plans' keys."""
    names: set[str] = set()
    for option in OPTIONS:
        fields = [name for name in (option.value, option.set_value) if name]
        if option.per_plan:
            names |= {name + key for name in (*fields, option.own_value) for key in (ALL, *plans)}
            names.discard(option.own_value + ALL)
        else:
            names |= set(fields)
    return names


def gui_names() -> set[str]:
    return {name for option in OPTIONS for name in option.guis}
