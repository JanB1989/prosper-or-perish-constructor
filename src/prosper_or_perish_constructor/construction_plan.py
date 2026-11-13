"""Construction Plan (branch player-construction-manager, 2026-11-06, Jan): player-only construction rules.

The player sets the rules once in the Construction Plan window (Global Settings, Location Profiles and, since
2026-11-10, Towns and Buildings); a monthly pass for countries with ``is_ai = no`` starts the constructions with
``construct_building`` (a normal, paid construction). The AI never runs it. Global settings: the plan on or off, a gold
reserve in gold, and six rule groups (``GROUPS``: the location profiles, the four below, and Towns and Buildings, whose
rules and tab are ``construction_plan_country.py``'s), each with a weight: its part of the gold above the reserve is
its weight over the sum of the weights (0 = off; Jan 2026-11-09), and since 2026-11-10 a budget that saves (its
purse: ``render_purse_values``, "Budgets that save" below in this module). The four below:

* Food, per province, one construction a month, first that applies (baseline rules, Jan 2026-11-08). Nothing is kept
  between passes; the hunger checks read the store a year from now in a normal year (this year's Variable Harvest and
  spoilage taken out). Famine: a Tavern; hungry: the staple food maker that pays back fastest (recipe profit at the
  market's prices and the location's output); a Granary while the store can hold less than the line's months, is
  nearly full and grows; a kitchen whenever the Cookshop budget allows; hungry without a farm: a Tavern; a Grange where
  a two-year store still grows; a Victualling Yard by payback.
* Logistics, per location: market access without event modifiers below the player's line while the owner controls
  the location: the first logistics building that can be built.
* Improvements, per location: where population over capacity reaches the player's line, the improvement with the most
  capacity per gold.
* Businesses (Jan 2026-11-09): every building that makes goods (the producers of ``market_short_weight.main_good``,
  without the food, logistics and improvement rules' own buildings) wherever a level pays back within the player's
  line, shortest payback first across the country. Profit = each slot's best recipe at the market's prices and the
  location's output with this year's Variable Harvest taken out, the same estimate for a new building and for one more
  level, so both compare. A level is only built where it finds its workers: idle peasants left after the open jobs of
  the buildings there (peasants are promoted into the other classes), or idle pops of its own class.

The per-location layer is the "profiles" group (the player's "Locations"; ``location_profiles.py``): a location's
profile, which takes from these groups only what it sets, and since 2026-11-10 the Location Plan's marks ("Also build
here", ``location_plan.py``), which add to them and switch nothing off.

Payback is the one money number (Jan: cost and profit alone say nothing across buildings): a level's build cost over
its monthly profit. The cost follows the engine's own formula, calibrated in game on 158 constructions (all within
1 %): base x (1 + increase_per_level_cost x levels) / max(0.5, 1 + build efficiency) x the construction goods' price
factor (each good's price / default clamped to 1 + MIN/MAX_PRICE_IMPACT, averaged by amount; vanilla
default_construct_building when a building names none). The same cost keeps the gold reserve and the budgets: a
construction starts only when it fits in the purse of the rule group that wants it and in the gold above the
reserve; the first thing a group cannot pay for is what it saves for.

The market limit (``render_market``, 2026-11-10) keeps the plan from flooding a market with one building type.

The engine (monthly pass, window, settings) is hand-written in the mod (``pp_construction_plan*.txt``,
``pp_construction_plan.gui``). This module writes the parts that follow the mod's buildings, goods and the
``[construction_plan]`` settings, so they stay in step with every rebalance:

* ``scripted_effects/pp_construction_plan_generated.txt``: the farm, logistics, improvement and business pickers,
  the building cost data lookup, the purses' two effects and the market limit's dispatch;
* ``script_values/pp_construction_plan_generated.txt``: the defaults, the rule groups' weights and parts, farm and
  business profit estimates, the construction goods price factors, the baseline rules' blacklists, the idle pops
  per pop type (the worker check), the purses' arithmetic and the market limit's counts;
* ``scripted_triggers/pp_construction_plan_generated.txt``: the construction goods and food queue checks and which
  rule groups the market limit holds for;
* ``gui/pp_construction_plan_weights.gui``: the weight bar of each rule group, with its share and its saved gold.

Variables carry + 100 (a variable at 0 counts as unset; ``var:x = n`` compares scopes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from prosper_or_perish_constructor import crop_farms
from prosper_or_perish_constructor import market_short_weight

EFFECTS = Path("in_game/common/scripted_effects/pp_construction_plan_generated.txt")
VALUES = Path("in_game/common/script_values/pp_construction_plan_generated.txt")
TRIGGERS = Path("in_game/common/scripted_triggers/pp_construction_plan_generated.txt")
WEIGHT_GUI = Path("in_game/gui/pp_construction_plan_weights.gui")
SCRIPT_VALUES = (Path("main_menu/common/script_values"), Path("in_game/common/script_values"))
# the rule groups with a weight (their order in the window and in the pass's turn); a weight runs 0 (off) ..
# WEIGHT_STEPS. "profiles" is the player's "Locations" group (the location profiles), "country" the "Towns and
# Buildings" group (construction_plan_country.py: pp_cplan_group_country, its own tab).
GROUPS = ("profiles", "food", "logistics", "improve", "business", "country")
# the rule groups' construction codes (pp_cplan_construct_scoped's why; the pass keeps its numbers per code)
GROUP_WHY = {"food": 101, "logistics": 102, "business": 103, "profiles": 105, "improve": 106, "country": 107}
HISTORY_MONTHS = 12  # months the window's chart shows
WEIGHT_STEPS = 10
SEGMENT = 14  # px of one weight step in the bar
PURSE_WIDTH = 64  # px of the saved gold beside the bar's %
BUILDING_TYPES = Path("in_game/common/building_types")
GOODS_DEMAND = Path("in_game/common/goods_demand")
DEFINES = Path("loading_screen/common/defines")
HEADER = "﻿# Generated by ppc finalize (construction_plan.py) from [construction_plan]; do not edit by hand.\n"
# why codes (+ 100) the ledger shows; 105 is the location profiles (pp_location_profiles.txt)
WHY_FOOD, WHY_LOGISTICS, WHY_BUSINESS, WHY_IMPROVE = 101, 102, 103, 106
DEFAULT_DEMAND = "default_construct_building"  # vanilla: the construction demand of a building that names none
# the Variable Harvest modifiers (one per sub-continent and severity): the food rules take out their peasant food
# consumption, the business rule their goods output ([construction_plan] baseline rules)
HARVEST_MODIFIERS = Path("in_game/common/static_modifiers/pp_variable_harvest_modifiers.txt")
HARVEST_SEVERITIES = ("abysmal", "very_poor", "poor", "good", "very_good", "bountiful")
STATIC_MODIFIERS = (Path("main_menu/common/static_modifiers"), Path("in_game/common/static_modifiers"))
POP_TYPES = Path("in_game/common/pop_types")
BLUEPRINT_BUILDINGS = Path("blueprints/accepted/buildings")
# building categories a location profile rule can name ([location_plan] categories): the business rule leaves a
# building of such a category to the profile that names it
PROFILE_CATEGORIES_KEY = "location_plan"


@dataclass(frozen=True)
class Config:
    reserve_gold: int
    access_threshold: int
    farm_sites_per_province: int
    kitchens: tuple[str, ...]
    taverns: tuple[str, ...]
    granaries: tuple[str, ...]
    logistics_order: tuple[str, ...]
    hidden_goods: frozenset[str]
    hungry_months: int = 6
    granges: tuple[str, ...] = ("grange",)
    yards: tuple[str, ...] = ("victualling_yard",)
    granary_capacity_months: int = 24
    granary_fill_pct: int = 85
    grange_surplus_pct: int = 5
    famine_months: int = 3
    yard_payback_years: int = 10
    tavern_victuals: float = 10.0
    improve_fill_pct: int = 90
    construction_goods_months: int = 12
    access_blacklist: tuple[str, ...] = ()
    business_years: int = 10
    business_market_share: int = 10  # % of a market's monthly demand a good's levels under construction may add up to
    # script time (2026-11-10): the months a rule group or a chore looks (LOOKS), and the business group's numbers
    look_months: tuple[tuple[str, tuple[int, ...]], ...] = ()
    business_sites: int = 16  # sites whose business pick is refreshed a pass, at least
    business_cycle_months: int = 24  # ... and every site within this many months, however large the country
    business_tries: int = 6  # stored picks a look tries to build, best first
    profile_categories: tuple[str, ...] = ()
    weights: tuple[tuple[str, int], ...] = tuple((group, 5) for group in GROUPS)


@dataclass(frozen=True)
class BuildingCost:
    """What the engine's build cost formula needs of a building type."""

    ipl: float
    demand: str
    category: str  # std (urban or rural by the location), fort, port, foreign, mill


@dataclass
class Result:
    businesses: dict[str, str] = field(default_factory=dict)  # building type -> its main good (the business rule)
    staff: dict[str, tuple[str, float]] = field(default_factory=dict)  # building type -> (pop type, workers a level)
    pop_types: list[str] = field(default_factory=list)  # every pop type of the game (pp_cplan_idle_<pop type>)
    # the market limit: good -> business type -> one level's output of the good
    market_outputs: dict[str, dict[str, float]] = field(default_factory=dict)
    farm_lines: dict[str, list[str]] = field(default_factory=dict)
    food_lines: dict[str, list[str]] = field(default_factory=dict)
    improvements: list[str] = field(default_factory=list)
    logistics: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    buildings: dict[str, BuildingCost] = field(default_factory=dict)
    demands: dict[str, dict[str, float]] = field(default_factory=dict)
    files_changed: int = 0


def load_config(project: Path) -> Config:
    whole = tomllib.loads(project.read_text(encoding="utf-8"))
    data = whole["construction_plan"]
    return Config(
        reserve_gold=int(data["reserve_gold"]),
        access_threshold=int(data["access_threshold"]),
        farm_sites_per_province=int(data["farm_sites_per_province"]),
        kitchens=tuple(data["kitchens"]),
        taverns=tuple(data["taverns"]),
        granaries=tuple(data["granaries"]),
        logistics_order=tuple(data["logistics_order"]),
        hidden_goods=frozenset(data["hidden_goods"]),
        hungry_months=int(data["hungry_months"]),
        granges=tuple(data["granges"]),
        yards=tuple(data["yards"]),
        granary_capacity_months=int(data["granary_capacity_months"]),
        granary_fill_pct=int(data["granary_fill_pct"]),
        grange_surplus_pct=int(data["grange_surplus_pct"]),
        famine_months=int(data["famine_months"]),
        yard_payback_years=int(data["yard_payback_years"]),
        tavern_victuals=float(data["tavern_victuals"]),
        improve_fill_pct=int(data["improve_fill_pct"]),
        construction_goods_months=int(data["construction_goods_months"]),
        access_blacklist=tuple(data["access_blacklist"]),
        business_years=int(data["business_years"]),
        business_market_share=int(data["business_market_share"]),
        look_months=_look_months(data["look_months"]),
        business_sites=int(data["business_sites"]),
        business_cycle_months=int(data["business_cycle_months"]),
        business_tries=int(data["business_tries"]),
        profile_categories=tuple(whole.get(PROFILE_CATEGORIES_KEY, {}).get("categories", ())),
        weights=_weights(data["weights"]),
    )


# Script time (Jan 2026-11-10: "the monthly pass takes 0.4 seconds ... it needs to be built so that it doesn't use
# unnecessary script time"). The pass still runs every month (the purses fill, the business group refreshes a few
# sites), but a rule group LOOKS (walks what it wants, best first) only in its months; between its looks it does one
# thing only: build what it saves for once its purse can pay for it. [construction_plan] look_months names the
# months of every look and chore (trigger pp_cplan_looks_<name>):
LOOKS = (
    "food", "logistics", "improve", "profiles",  # the rule groups that walk the whole country at a look
    "business",  # the months the business group ranks its stored picks again while it saves (else every month)
    "upgrades", "public", "ranks", "rights",  # Towns and Buildings, one rule a look
    "market_count",  # the months the market limit counts what is under construction afresh
    "business_types",  # the months the country's part of the business can-build check is asked again
)


def business_refresh_passes(config: "Config") -> float:
    """The passes in which the business refresh runs within one cycle of [construction_plan] business_cycle_months:
    it rests in the months of the food look (the dearest of the year), so the window is sized for the others."""
    food = len(dict(config.look_months)["food"])
    return config.business_cycle_months * (12 - food) / 12


def _look_months(table: dict) -> tuple[tuple[str, tuple[int, ...]], ...]:
    if set(table) != set(LOOKS):
        raise ValueError(f"[construction_plan] look_months: give exactly {', '.join(LOOKS)}")
    found = tuple((name, tuple(sorted(int(month) for month in table[name]))) for name in LOOKS)
    for name, months in found:
        if not months or len(set(months)) != len(months) or not all(1 <= month <= 12 for month in months):
            raise ValueError(f"[construction_plan] look_months.{name}: distinct months 1..12, at least one")
    return found


def render_looks(config: "Config") -> str:
    """pp_cplan_looks_<name> (any scope): this month is one of the look's months."""
    parts = [
        "\n# ---- Script time: who looks when ([construction_plan] look_months) ----\n"
        "# Any scope: the game's month is one of the months this rule group, rule or chore does its walk.\n"
    ]
    for name, months in config.look_months:
        tests = " ".join(f"current_month = {month}" for month in months)
        parts.append(f"pp_cplan_looks_{name} = {{\n\tOR = {{ {tests} }}\n}}\n")
    return "".join(parts)


def _weights(table: dict) -> tuple[tuple[str, int], ...]:
    if set(table) != set(GROUPS):
        raise ValueError(f"[construction_plan] weights: give exactly {', '.join(GROUPS)}")
    weights = tuple((group, int(table[group])) for group in GROUPS)
    for group, weight in weights:
        if not 0 <= weight <= WEIGHT_STEPS:
            raise ValueError(f"[construction_plan] weights.{group}: 0..{WEIGHT_STEPS}")
    return weights


# ---------------------------------------------------------------------------------------------------------------------
# reading the game's and the mod's database files


def _strip_comments(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text)


def _blocks(text: str):
    """Top-level ``name = { body }`` blocks of a database file, in file order."""
    text = _strip_comments(text)
    pattern = re.compile(r"([A-Za-z0-9_:@.\-]+)\s*=\s*\{")
    index, size = 0, len(text)
    while index < size:
        match = pattern.search(text, index)
        if not match:
            return
        depth, end = 1, match.end()
        while end < size and depth:
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
            end += 1
        yield match.group(1), text[match.end():end - 1]
        index = end


def _top_keys(body: str) -> dict[str, str]:
    """``key = scalar`` pairs at the top level of a block body."""
    found: dict[str, str] = {}
    depth = 0
    for token in re.finditer(r"\{|\}|([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_.\-]+)(?!\s*\{)", body):
        if token.group(0) == "{":
            depth += 1
        elif token.group(0) == "}":
            depth -= 1
        elif depth == 0 and token.group(1):
            found[token.group(1)] = token.group(2)
    return found


def _database(mod_root: Path, vanilla_root: Path, folder: Path) -> dict[str, tuple[dict[str, str], str]]:
    """name -> (top-level keys, body) after the load order: vanilla files a mod file of the same name replaces are
    skipped, files load by name, REPLACE/plain blocks replace, INJECT/TRY_INJECT blocks merge their keys."""
    files: dict[str, Path] = {}
    for root in (vanilla_root / "game", mod_root):
        directory = root / folder
        if directory.is_dir():
            for path in directory.glob("*.txt"):
                files[path.name] = path
    data: dict[str, tuple[dict[str, str], str]] = {}
    for name in sorted(files):
        for block, body in _blocks(files[name].read_text(encoding="utf-8-sig", errors="replace")):
            mode = ""
            if ":" in block:
                mode, block = block.split(":", 1)
            keys = _top_keys(body)
            if mode in ("INJECT", "TRY_INJECT") and block in data:
                old_keys, old_body = data[block]
                data[block] = ({**old_keys, **keys}, old_body + "\n" + body)
            elif mode == "TRY_REPLACE" and block not in data:
                continue
            else:
                data[block] = (keys, body)
    return data


def script_value_numbers(mod_root: Path, vanilla_root: Path) -> dict[str, float]:
    """Script values that are a plain number (``name = 0.5`` at the top of a file), the mod's files over vanilla's of the
    same name (buildings name their workers through them: employment_size = manpower_employment)."""
    files: dict[str, Path] = {}
    for folder in SCRIPT_VALUES:
        for root in (vanilla_root / "game", mod_root):
            directory = root / folder
            if directory.is_dir():
                for path in directory.glob("*.txt"):
                    files[f"{folder}/{path.name}"] = path
    found: dict[str, float] = {}
    for key in sorted(files):
        depth = 0
        for line in _strip_comments(files[key].read_text(encoding="utf-8-sig", errors="replace")).splitlines():
            if depth == 0:
                match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?[0-9.]+)\s*$", line)
                if match:
                    found[match.group(1)] = float(match.group(2))
            depth += line.count("{") - line.count("}")
    return found


def staffing(database: dict[str, tuple[dict[str, str], str]], numbers: dict[str, float]) -> dict[str, tuple[str, float]]:
    """Building -> (the pop type it employs, the workers one level needs, in thousands like the pops); buildings
    without workers are left out."""
    found: dict[str, tuple[str, float]] = {}
    for name, (keys, _) in database.items():
        pop, size = keys.get("pop_type"), keys.get("employment_size")
        if not pop or size is None:
            continue
        try:
            value = float(size)
        except ValueError:
            value = numbers.get(size, 0.0)
        if value > 0:
            found[name] = (pop, value)
    return found


def staff_check(staff: tuple[str, float] | None) -> str:
    """The worker check of one building (pp_cplan_staff), or nothing for a building without workers."""
    if not staff:
        return ""
    return f"pp_cplan_staff = {{ type = {staff[0]} size = {_num(staff[1])} }}"


def render_idle_values(pop_types: list[str]) -> str:
    """``pp_cplan_idle_<pop type>`` (location scope) for every pop type of the game: the idle pops of a building's own
    class, which pp_cplan_staff reads as ``pp_cplan_idle_$type$``. One value per type with the type written out, as
    vanilla writes the call: with the argument inside the quoted call the trigger logged a script error on every
    check (in game 2026-11-10). Peasants give 0: their idle count less the open jobs is the check's other line
    (scope:pp_cplan_free_peasants)."""
    parts = [
        "\n# ---- Workers (location scope): idle pops of a building's own class, in thousands (pp_cplan_staff) ----\n"
        "# Peasants 0: the idle peasants left after the open jobs here are scope:pp_cplan_free_peasants.\n\n"
    ]
    for pop in sorted(pop_types):
        if pop == "peasants":
            parts.append(f"pp_cplan_idle_{pop} = {{ value = 0 }}\n")
        else:
            parts.append(f"pp_cplan_idle_{pop} = {{ value = \"unemployed_pops_of_pop_type_in_location(pop_type:{pop})\" }}\n")
    return "".join(parts)


def defined_buildings(mod_root: Path, vanilla_root: Path) -> set[str]:
    """Building type keys the game will know."""
    return set(_database(mod_root, vanilla_root, BUILDING_TYPES))


def _modifier_number(body: str, key: str) -> float:
    for match in re.finditer(r"\b(?:raw_)?modifier\s*=\s*\{([^{}]*)\}", body):
        found = re.search(rf"\b{key}\s*=\s*(-?[0-9.]+)", match.group(1))
        if found:
            return float(found.group(1))
    return 0.0


def building_costs(mod_root: Path, vanilla_root: Path,
                   database: dict[str, tuple[dict[str, str], str]] | None = None,
                   ) -> tuple[dict[str, BuildingCost], dict[str, dict[str, float]]]:
    """Per building type the cost data (increase_per_level_cost, construction demand, efficiency category) and the
    construction demands they use (good -> amount). Category as the engine picks it: a fort_level in the building's
    modifier -> fort, max_ships_built_at_same_time -> port, is_foreign -> foreign, is_mill -> mill (no category term),
    else urban or rural by the location (construction_efficiency_140.md, calibrated 2026-11-06)."""
    buildings = database if database is not None else _database(mod_root, vanilla_root, BUILDING_TYPES)
    demand_blocks = _database(mod_root, vanilla_root, GOODS_DEMAND)
    costs: dict[str, BuildingCost] = {}
    used: dict[str, dict[str, float]] = {}
    for name, (keys, body) in sorted(buildings.items()):
        demand = keys.get("construction_demand") or DEFAULT_DEMAND
        if demand not in demand_blocks:
            demand = DEFAULT_DEMAND
        if demand not in used:
            amounts = {
                good: float(value)
                for good, value in demand_blocks.get(demand, ({}, ""))[0].items()
                if good != "category" and re.fullmatch(r"[0-9.]+", value) and float(value) > 0
            }
            used[demand] = amounts
        if _modifier_number(body, "fort_level") > 0:
            category = "fort"
        elif _modifier_number(body, "max_ships_built_at_same_time") > 0:
            category = "port"
        elif keys.get("is_foreign") == "yes":
            category = "foreign"
        elif keys.get("is_mill") == "yes":
            category = "mill"
        else:
            category = "std"
        costs[name] = BuildingCost(ipl=float(keys.get("increase_per_level_cost", "0") or 0), demand=demand,
                                   category=category)
    return costs, used


def price_impact_bounds(mod_root: Path, vanilla_root: Path) -> tuple[float, float]:
    """1 + MIN_PRICE_IMPACT and 1 + MAX_PRICE_IMPACT (NMarket), the mod's defines over vanilla's."""
    found: dict[str, float] = {}
    for root in (vanilla_root / "game", mod_root):
        directory = root / DEFINES
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.txt")):
            text = _strip_comments(path.read_text(encoding="utf-8-sig", errors="replace"))
            for key in ("MIN_PRICE_IMPACT", "MAX_PRICE_IMPACT"):
                match = re.search(rf"\b{key}\s*=\s*(-?[0-9.]+)", text)
                if match:
                    found[key] = float(match.group(1))
    return 1 + found.get("MIN_PRICE_IMPACT", -0.33), 1 + found.get("MAX_PRICE_IMPACT", 3.0)


def harvest_rates(mod_root: Path) -> dict[str, dict[str, float]]:
    """Sub-continent -> severity -> the peasant food consumption of that Variable Harvest modifier."""
    rates: dict[str, dict[str, float]] = {}
    path = mod_root / HARVEST_MODIFIERS
    if not path.is_file():
        return rates
    for name, body in _blocks(path.read_text(encoding="utf-8-sig")):
        if not name.startswith("pp_harvest_"):
            continue
        rest = name[len("pp_harvest_"):]
        # the longest suffix first: "very_good" is not sub-continent "..._very" with "good"
        severity = next((s for s in sorted(HARVEST_SEVERITIES, key=len, reverse=True) if rest.endswith("_" + s)), None)
        value = _top_keys(body).get("local_peasants_food_consumption")
        if severity and value is not None:
            rates.setdefault(rest[: -len(severity) - 1], {})[severity] = float(value)
    return rates


def harvest_outputs(mod_root: Path) -> dict[str, dict[str, dict[str, float]]]:
    """Sub-continent -> severity -> good -> the local goods output modifier of that Variable Harvest modifier."""
    found: dict[str, dict[str, dict[str, float]]] = {}
    path = mod_root / HARVEST_MODIFIERS
    if not path.is_file():
        return found
    for name, body in _blocks(path.read_text(encoding="utf-8-sig")):
        if not name.startswith("pp_harvest_"):
            continue
        rest = name[len("pp_harvest_"):]
        severity = next((s for s in sorted(HARVEST_SEVERITIES, key=len, reverse=True) if rest.endswith("_" + s)), None)
        if not severity:
            continue
        goods = {
            match.group(1): float(value)
            for key, value in _top_keys(body).items()
            if (match := re.fullmatch(r"local_(\w+)_output_modifier", key))
        }
        found.setdefault(rest[: -len(severity) - 1], {})[severity] = goods
    return found


def peasant_food_consumption(mod_root: Path, vanilla_root: Path) -> float:
    """Food a unit of peasants eats a month (pop_food_consumption of the peasants pop type)."""
    found = _database(mod_root, vanilla_root, POP_TYPES).get("peasants")
    return float(found[0].get("pop_food_consumption", 1.0)) if found else 1.0


def access_modifier_amounts(mod_root: Path, vanilla_root: Path, names: tuple[str, ...]) -> dict[str, float]:
    """Static modifier -> its local_market_access (the access blacklist)."""
    amounts: dict[str, float] = {}
    for folder in STATIC_MODIFIERS:
        data = _database(mod_root, vanilla_root, folder)
        for name in names:
            if name in data and "local_market_access" in data[name][0]:
                amounts[name] = float(data[name][0]["local_market_access"])
    return amounts


def staple_food_lines(repo: Path, mod_root: Path, crop_lines: dict[str, list[str]], crop_goods: dict[str, str],
                      main_good: dict[str, str], skip: set[str]) -> tuple[dict[str, list[str]], dict[str, str | None]]:
    """Every staple food maker the hunger rule may build, as upgrade lines (oldest tier first) with the good a Never
    mode blocks: the crop farm lines, then the other buildings that count toward the Cookshop budget (orchards,
    fisheries, herds, forest villages: food_level_counts), chained by their ``obsolete`` keys."""
    from prosper_or_perish_constructor import food_level_counts
    from prosper_or_perish_constructor import yaml_io

    lines: dict[str, list[str]] = {line: list(tiers) for line, tiers in crop_lines.items()}
    goods: dict[str, str | None] = dict(crop_goods)
    in_lines = {b for tiers in lines.values() for b in tiers}
    makers = {key for key, per in food_level_counts.counters(mod_root).items()
              if per.get("local_pp_farm_levels") or per.get("local_pp_staple_levels")}
    makers -= in_lines | skip
    older: dict[str, set[str]] = {key: set() for key in makers}
    for path in sorted((repo / BLUEPRINT_BUILDINGS).glob("*.yml")):
        building = yaml_io.safe_load(path.read_text(encoding="utf-8-sig")).get("building") or {}
        key = building.get("key")
        if key in makers:
            older[key] = {name for name in re.findall(r"(?m)^\s*obsolete\s*=\s*(\w+)", building.get("body") or "")
                          if name in makers}

    def root(key: str, seen: frozenset[str] = frozenset()) -> str:
        parents = sorted(older[key] - seen)
        return root(parents[0], seen | {key}) if parents else key

    chains: dict[str, list[str]] = {}
    for key in sorted(makers):
        chains.setdefault(root(key), []).append(key)
    for start, members in sorted(chains.items()):
        members.sort(key=lambda key: (len(older[key]), key))
        lines[start] = members
        goods[start] = next((main_good[m] for m in members if m in main_good), None)
    return lines, goods


@dataclass(frozen=True)
class Recipe:
    """One production method: the good it makes, how much, and its inputs (per level)."""

    produced: str | None
    output: float
    inputs: tuple[tuple[str, float], ...]


def farm_recipes(repo: Path, buildings: list[str]) -> dict[str, list[list[Recipe]]]:
    """Building -> its slots, each a list of methods (from the accepted blueprints)."""
    from prosper_or_perish_constructor import production_gate as pg
    from prosper_or_perish_constructor import yaml_io

    wanted = set(buildings)
    found: dict[str, list[list[Recipe]]] = {}
    for path in sorted((repo / BLUEPRINT_BUILDINGS).glob("*.yml")):
        building = yaml_io.safe_load(path.read_text(encoding="utf-8-sig")).get("building") or {}
        key = building.get("key")
        if key not in wanted:
            continue
        slots, _ = pg.body_slots(building.get("body") or "")
        found[key] = [
            [Recipe(m.produced, float(m.output or 0.0), tuple(sorted((g, float(a)) for g, a in (m.inputs or {}).items())))
             for m in slot.methods]
            for slot in slots
        ]
    return found


def built_recipes(database: dict[str, tuple[dict[str, str], str]], buildings: list[str]) -> dict[str, list[list[Recipe]]]:
    """Building -> its slots, each a list of methods, from the building files the game loads (the mod over vanilla, after
    every finalize pass that rewrites methods)."""
    from prosper_or_perish_constructor import production_gate as pg

    found: dict[str, list[list[Recipe]]] = {}
    for key in buildings:
        if key not in database:
            continue
        slots, _ = pg.body_slots(database[key][1], key)
        found[key] = [
            [Recipe(m.produced, float(m.output or 0.0), tuple(sorted((g, float(a)) for g, a in (m.inputs or {}).items())))
             for m in slot.methods]
            for slot in slots
        ]
    return found


# ---------------------------------------------------------------------------------------------------------------------
# script values


def _num(value: float) -> str:
    return f"{value:g}"


def _default_value(name: str, var: str, default: int, scope_note: str) -> str:
    return (
        f"# {scope_note}\n"
        f"{name} = {{\n"
        f"\tvalue = {default}\n"
        f"\tif = {{\n"
        f"\t\tlimit = {{ has_variable = {var} }}\n"
        f"\t\tvalue = var:{var}\n"
        f"\t\tsubtract = 100\n"
        f"\t}}\n"
        f"}}\n"
    )


def _constant(name: str, value: float, comment: str) -> str:
    return f"# {comment}\n{name} = {{ value = {_num(value)} }}\n"


def render_price_factors(demands: dict[str, dict[str, float]], bounds: tuple[float, float]) -> str:
    low, high = bounds
    parts = [
        "\n# ---- Build cost: the construction goods' price factor (location scope, its market) ----\n"
        f"# Each good's price / default price, clamped to {low:g}..{high:g} (1 + MIN/MAX_PRICE_IMPACT), averaged by the\n"
        "# demand's amounts; 1 where the location has no market or the demand names no goods.\n\n"
    ]
    for key in sorted(demands):
        amounts = demands[key]
        total = sum(amounts.values())
        if not amounts or total <= 0:
            parts.append(f"pp_cplan_cd_{key} = {{ value = 1 }}\n")
            continue
        lines = [f"pp_cplan_cd_{key} = {{", "\tvalue = 1", "\tif = {", "\t\tlimit = { market ?= { always = yes } }", "\t\tvalue = 0"]
        for good, amount in sorted(amounts.items()):
            lines.append(
                f"\t\tadd = {{ value = \"market.market_price(goods:{good})\" divide = \"default_price(goods:{good})\" "
                f"min = {low:g} max = {high:g} multiply = {_num(amount)} }}"
            )
        lines += [f"\t\tdivide = {_num(total)}", "\t}", "}"]
        parts.append("\n".join(lines) + "\n")
    return "".join(parts)


# groups whose weight counts only while they have something to do (render_weight_values writes these values)
COUNTED_WEIGHTS = {"profiles": "pp_cplan_profiles_cw", "country": "pp_cplan_country_cw"}


def counted_weight(group: str) -> str:
    """The script value of a group's weight as it counts in the sum (its own weight, or 0 while it has nothing to do)."""
    return COUNTED_WEIGHTS.get(group, f"pp_cplan_{group}_w")


def render_weight_values(config: Config) -> str:
    """The rule groups' weights (Jan 2026-11-09): a group's part of the gold above the reserve = its weight over the sum
    of the weights that count (0 = the group is off). Two groups count only while they have something to do
    (COUNTED_WEIGHTS): the location profiles while a location has a profile or a mark, Towns and Buildings while
    something is ticked on its tab; otherwise their part would be held back from the other groups."""
    parts = ["\n# ---- Rule group weights (country scope; 0 = off) ----\n\n"]
    for group, default in config.weights:
        parts.append(_default_value(f"pp_cplan_{group}_w", f"pp_cplan_w_{group}", default,
                                    f"Country scope: the {group} group's weight, 0..{WEIGHT_STEPS}."))
    parts.append(
        "# Country scope: the location profiles' weight counts only while a location of the country has a profile or a\n"
        "# mark (pp_lprof_group_n, pp_location_profiles_generated.txt).\n"
        "pp_cplan_profiles_cw = {\n\tvalue = pp_cplan_profiles_w\n\tmultiply = pp_lprof_group_n\n}\n"
        "# Country scope: the Towns and Buildings weight counts only while that group has something to do: a public\n"
        "# building is ticked or an upgrade is switched on (pp_cplan_country_active, pp_construction_plan_country.txt).\n"
        "pp_cplan_country_cw = {\n\tvalue = 0\n\tif = {\n\t\tlimit = { pp_cplan_country_active > 0 }\n"
        "\t\tvalue = pp_cplan_country_w\n\t}\n}\n"
        "# Country scope: the sum of the weights that count.\npp_cplan_w_total = {\n\tvalue = 0\n"
        + "".join(f"\tadd = {counted_weight(group)}\n" for group in GROUPS)
        + "}\n"
    )
    for group in GROUPS:
        weight = counted_weight(group)
        parts.append(
            f"# Country scope: the {group} group's part of the new gold, in % (the window; in gold: pp_cplan_purse_new_"
            f"{GROUP_WHY[group]}).\n"
            f"pp_cplan_part_{group} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ pp_cplan_w_total > 0 }}\n"
            f"\t\tvalue = {weight}\n\t\tmultiply = 100\n\t\tdivide = pp_cplan_w_total\n\t}}\n}}\n"
        )
    return "".join(parts)


# ---- Budgets that save (Jan 2026-11-10: "allocate a construction budget for each of the branches, and the budget
# cannot go below the floor we already set ... all of this needs to happen under the hood") ----
# Every rule group has a purse on the country: the gold it has saved (pp_cplan_purse_<why>, + 100). The pass never
# offers the whole gold above the reserve anew: at its start the gold that is in no purse yet is shared among the
# groups that count by their weights, a group that does not count gives its purse back, and when the purses together
# are more than the gold above the reserve (the player or a war spent it) they all shrink alike. A construction is paid
# from the purse of the group that starts it and must fit in it. The first thing a group wants and cannot pay for is
# what it saves for (pp_cplan_save_*_<why>); from then on it builds nothing more in the pass. At the end a group that
# ran and saves for nothing hands what is left of its purse to the groups that do save, by their weights.
# The arithmetic sits in script values of the state as it stands (render_purse_values), so it can be evaluated offline
# (tests/test_construction_plan_budget.py); the two effects read all of them first and write afterwards.
PURSE = "pp_cplan_purse"  # country variable pp_cplan_purse_<why>, + 100
PURSE_IN = "pp_cplan_in"  # country variable pp_cplan_in_<why>, + 100: the gold the group received for this pass
PURSE_HAND = "pp_cplan_hand"  # country variable pp_cplan_hand_<why>, + 100: handed on to it at the end of the last pass
SAVE_COST = "pp_cplan_save_cost"  # country variable pp_cplan_save_cost_<why>, + 100: set = the group saves
# pp_cplan_save_<x>_<why>: what it saves for (rank: a town / city upgrade; rv / rs: the reason value and step the
# construction carries into the ledger when the purse can pay for it between two looks)
SAVE_VARS = ("cost", "loc", "type", "rank", "rv", "rs")
NOW = "pp_cplan_now"  # country variable pp_cplan_now_<why>: the group looked in this pass (cleared at each pass's start)


def purse_value(group: str) -> str:
    """Country script value: the gold the group has saved."""
    return f"{PURSE}_n_{GROUP_WHY[group]}"


def _readout(name: str, var: str) -> str:
    return (f"{name} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
            f"\t\tvalue = var:{var}\n\t\tsubtract = 100\n\t}}\n}}\n")


def render_purse_values() -> str:
    """The purses' arithmetic (country scope), each a function of the state as it stands:

    * the pass's start: ``pp_cplan_purse_next_<why>`` = what the purse holds after the start (kept, shrunk when the
      purses exceed the gold above the reserve, plus its part of the gold in no purse), ``pp_cplan_purse_new_<why>`` =
      that part;
    * the pass's end: ``pp_cplan_hand_next_<why>`` = the purse after the hand-on (a group that ran and saves for nothing
      gives all it has, a group that saves gets its part by weight; nothing moves while no group saves),
      ``pp_cplan_hand_get_<why>`` = what it gets."""
    whys = [(group, GROUP_WHY[group], counted_weight(group)) for group in GROUPS]
    parts = [
        "\n# ---- Budgets that save (country scope; pp_cplan_purses_fill, pp_cplan_purses_hand_on) ----\n"
        "# pp_cplan_purse_<why> (+ 100): the gold a rule group has saved. The values below are functions of the state as\n"
        "# it stands; the two effects read them all before they write.\n\n"
        "# The gold above the reserve the purses may hold.\n"
        "pp_cplan_purse_free = {\n\tvalue = pp_cplan_free_gold\n\tmin = 0\n}\n"
    ]
    for group, why, weight in whys:
        parts.append(f"\n# {group} ({why})\n")
        parts.append(_readout(f"{PURSE}_n_{why}", f"{PURSE}_{why}"))
        parts.append(_readout(f"{PURSE_IN}_n_{why}", f"{PURSE_IN}_{why}"))
        parts.append(_readout(f"{PURSE_HAND}_n_{why}", f"{PURSE_HAND}_{why}"))
        parts.append(_readout(f"{SAVE_COST}_n_{why}", f"{SAVE_COST}_{why}"))
        # the window: 1 / 2 when it saves for a town / city upgrade, 0 for a building. Only Towns and Buildings sets
        # the variable (in game 2026-11-10: "pp_cplan_save_rank_103 is used but is never set" for the other five)
        if group == "country":
            parts.append(_readout(f"pp_cplan_save_rank_n_{why}", f"pp_cplan_save_rank_{why}"))
        else:
            parts.append(f"pp_cplan_save_rank_n_{why} = {{ value = 0 }}\n")
        parts.append(
            f"# what it keeps at the pass's start: nothing while it does not count (its weight 0, or nothing to do)\n"
            f"{PURSE}_kept_{why} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ {weight} > 0 }}\n"
            f"\t\tvalue = {PURSE}_n_{why}\n\t}}\n}}\n"
            f"# 1 while it saves for something (the last pass could not pay for what it wanted next)\n"
            f"pp_cplan_saves_{why} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{\n\t\t\thas_variable = {SAVE_COST}_{why}\n"
            f"\t\t\t{weight} > 0\n\t\t}}\n"
            f"\t\tvalue = 1\n\t}}\n}}\n"
            f"# 1 when it looked in this pass and saves for nothing: it hands on what it has\n"
            f"pp_cplan_gives_{why} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{\n\t\t\thas_variable = {NOW}_{why}\n"
            f"\t\t\tNOT = {{ has_variable = {SAVE_COST}_{why} }}\n\t\t}}\n\t\tvalue = 1\n\t}}\n}}\n"
        )
    parts.append(
        "\n# The pass's start.\n# What the purses hold together, without the groups that do not count.\n"
        f"{PURSE}_held = {{\n\tvalue = 0\n" + "".join(f"\tadd = {PURSE}_kept_{why}\n" for _, why, _ in whys) + "}\n"
        "# The gold above the reserve that is in no purse yet (0 when the purses hold more than there is).\n"
        f"{PURSE}_rest = {{\n\tvalue = {PURSE}_free\n\tsubtract = {PURSE}_held\n\tmin = 0\n}}\n"
    )
    for group, why, weight in whys:
        parts.append(
            f"# {group}: its part of the gold in no purse, and its purse after the pass's start (shrunk like every purse\n"
            f"# when they hold more than the gold above the reserve)\n"
            f"{PURSE}_new_{why} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ pp_cplan_w_total > 0 }}\n"
            f"\t\tvalue = {PURSE}_rest\n\t\tmultiply = {weight}\n\t\tdivide = pp_cplan_w_total\n\t}}\n}}\n"
            f"{PURSE}_next_{why} = {{\n\tvalue = {PURSE}_kept_{why}\n\tif = {{\n"
            f"\t\tlimit = {{ {PURSE}_held > {PURSE}_free }}\n"
            f"\t\tmultiply = {PURSE}_free\n\t\tdivide = {PURSE}_held\n\t}}\n\tadd = {PURSE}_new_{why}\n}}\n"
        )
    parts.append(
        "\n# The pass's end.\n# The gold of the groups that hand on, and the weights of the groups that save.\n"
        "pp_cplan_hand_pool = {\n\tvalue = 0\n"
        + "".join(f"\tadd = {{ value = {PURSE}_n_{why} multiply = pp_cplan_gives_{why} }}\n" for _, why, _ in whys)
        + "}\npp_cplan_hand_weights = {\n\tvalue = 0\n"
        + "".join(f"\tadd = {{ value = {weight} multiply = pp_cplan_saves_{why} }}\n" for _, why, weight in whys)
        + "}\n"
    )
    for group, why, weight in whys:
        parts.append(
            f"# {group}: what it gets from the groups that hand on, and its purse after the hand-on\n"
            f"pp_cplan_hand_get_{why} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{\n\t\t\tpp_cplan_saves_{why} > 0\n"
            f"\t\t\tpp_cplan_hand_weights > 0\n\t\t}}\n\t\tvalue = pp_cplan_hand_pool\n\t\tmultiply = {weight}\n"
            f"\t\tdivide = pp_cplan_hand_weights\n\t}}\n}}\n"
            f"pp_cplan_hand_next_{why} = {{\n\tvalue = {PURSE}_n_{why}\n\tif = {{\n"
            f"\t\tlimit = {{\n\t\t\tpp_cplan_gives_{why} > 0\n\t\t\tpp_cplan_hand_weights > 0\n\t\t}}\n\t\tvalue = 0\n\t}}\n"
            f"\tadd = pp_cplan_hand_get_{why}\n}}\n"
        )
    return "".join(parts)


def render_purse_effects() -> str:
    """The two effects that move the purses (country scope): every new amount is read first (temporary values), then
    written, so one group's change never reaches another's sum."""
    whys = [GROUP_WHY[group] for group in GROUPS]
    fill = []
    for why in whys:
        fill.append(f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_np_{why} value = {PURSE}_next_{why} }}\n"
                    f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_ni_{why} value = {{ value = {PURSE}_new_{why} "
                    f"add = {PURSE_HAND}_n_{why} }} }}\n")
    for why in whys:
        fill.append(f"\tset_variable = {{ name = {PURSE}_{why} value = {{ value = scope:pp_cplan_np_{why} add = 100 }} }}\n"
                    f"\tset_variable = {{ name = {PURSE_IN}_{why} value = {{ value = scope:pp_cplan_ni_{why} add = 100 }} }}\n"
                    f"\tremove_variable = {PURSE_HAND}_{why}\n")
    # what a group saves for stays until its next look; a group that no longer counts lets go of it
    for group in GROUPS:
        fill.append(f"\tif = {{\n\t\tlimit = {{ NOT = {{ {counted_weight(group)} > 0 }} }}\n"
                    f"\t\tpp_cplan_save_clear = {{ why = {GROUP_WHY[group]} }}\n"
                    + ("\t\tremove_variable = pp_cplan_save_rank_107\n" if group == "country" else "") + "\t}\n")
    hand = []
    for why in whys:
        hand.append(f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_np_{why} value = pp_cplan_hand_next_{why} }}\n"
                    f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_ni_{why} value = pp_cplan_hand_get_{why} }}\n")
    for why in whys:
        hand.append(f"\tset_variable = {{ name = {PURSE}_{why} value = {{ value = scope:pp_cplan_np_{why} add = 100 }} }}\n"
                    f"\tset_variable = {{ name = {PURSE_HAND}_{why} value = {{ value = scope:pp_cplan_ni_{why} add = 100 }} }}\n")
    return (
        "\n# ---- Budgets that save (pp_cplan_run; the amounts are script values, pp_cplan_purse_next_<why> ...) ----\n\n"
        "# Country scope, at the start of the pass: a group that does not count gives its purse back, the purses shrink\n"
        "# alike when they hold more than the gold above the reserve, and the gold in no purse yet is shared by the\n"
        "# weights. pp_cplan_in_<why> keeps what the group received for this pass (its part and what was handed on to it\n"
        "# at the end of the last pass): the business group counts its time to save by it. What each group saved for\n"
        "# starts afresh: the pass finds it again.\n"
        "pp_cplan_purses_fill = {\n" + "".join(fill) + "}\n\n"
        "# Country scope, at the end of the pass: every group that ran and saves for nothing hands what is left of its\n"
        "# purse to the groups that do save, by their weights (next month's money). While no group saves, nothing moves.\n"
        "pp_cplan_purses_hand_on = {\n" + "".join(hand) + "}\n"
    )


def render_weight_gui() -> str:
    """One weight bar per rule group: - and + (vanilla's slider buttons), a gold bar of WEIGHT_STEPS steps whose every
    step sets the weight when clicked, the group's part in % and the gold it has saved (its purse; the text key is
    construction_plan_detail's). A real slider cannot be used: its value only reaches the engine's own functions,
    never a script."""

    def call(group: str, extra: str) -> str:
        return (f"[GetScriptedGui('pp_cplan_weight').Execute(GuiScope.SetRoot(GetPlayer.MakeScope)"
                f".AddScope('pp_key', MakeScopeFlag('{group}')){extra}.End)]")

    out = [HEADER, "\ntypes PPConstructionPlanWeights\n{\n"]
    for group in GROUPS:
        value = f"GetPlayer.MakeScope.ScriptValue('pp_cplan_{group}_w')"
        down = call(group, ".AddScope('pp_dir', MakeScopeFlag('down'))")
        up = call(group, ".AddScope('pp_dir', MakeScopeFlag('up'))")
        zones = "".join(
            "\t\t\tbutton = {\n"
            f"\t\t\t\tposition = {{ {(n - 1) * SEGMENT} 0 }}\n"
            f"\t\t\t\tsize = {{ {SEGMENT} 14 }}\n"
            "\t\t\t\ttooltip = \"PP_CPLAN_WEIGHT_TT\"\n"
            f"\t\t\t\tonclick = \"{call(group, f".AddScope('pp_n', MakeScopeFlag('w{n}'))")}\"\n"
            "\t\t\t}\n"
            for n in range(1, WEIGHT_STEPS + 1)
        )
        out.append(
            f"\t# the {group} group\n"
            f"\ttype pp_cplan_weight_bar_{group} = hbox {{\n"
            "\t\tspacing = 4\n"
            "\t\tbutton_square_minus = {\n\t\t\tsize = { 15 15 }\n\t\t\ttooltip = \"PP_CPLAN_WEIGHT_TT\"\n"
            f"\t\t\tonclick = \"{down}\"\n\t\t}}\n"
            "\t\twidget = {\n"
            f"\t\t\tsize = {{ {SEGMENT * WEIGHT_STEPS} 14 }}\n"
            "\t\t\tprogressbar_framed = {\n\t\t\t\tsize = { 100% 100% }\n\t\t\t\tusing = progress_bar_goldish\n"
            f"\t\t\t\tmin = 0\n\t\t\t\tmax = {WEIGHT_STEPS}\n\t\t\t\tvalue = \"[FixedPointToFloat({value})]\"\n\t\t\t}}\n"
            + zones
            + "\t\t}\n"
            "\t\tbutton_square_plus = {\n\t\t\tsize = { 15 15 }\n\t\t\ttooltip = \"PP_CPLAN_WEIGHT_TT\"\n"
            f"\t\t\tonclick = \"{up}\"\n\t\t}}\n"
            "\t\ttext_single = {\n"
            f"\t\t\traw_text = \"[GetPlayer.MakeScope.ScriptValue('pp_cplan_part_{group}')|0]%\"\n"
            "\t\t\ttooltip = \"PP_CPLAN_SHARE_TT\"\n\t\t\tminimumsize = { 44 -1 }\n\t\t\tmaximumsize = { 44 -1 }\n"
            "\t\t\talign = right|nobaseline\n\t\t}\n"
            "\t\t# what the group has saved (its purse)\n"
            "\t\ttext_single = {\n"
            f"\t\t\ttext = \"PP_CPLAN_D_PURSE_{group.upper()}\"\n"
            f"\t\t\ttooltip = \"PP_CPLAN_PURSE_TT\"\n\t\t\tminimumsize = {{ {PURSE_WIDTH} -1 }}\n"
            f"\t\t\tmaximumsize = {{ {PURSE_WIDTH} -1 }}\n"
            "\t\t\talign = right|nobaseline\n\t\t}\n"
            "\t}\n\n"
        )
    out.append("}\n")
    return "".join(out)


# ---- The window's detail panes (Jan 2026-11-09: "how much investment is missing, what was built and why") ----
# Per rule group (by its construction code, GROUP_WHY) the pass keeps on the country, until the next pass: that it ran,
# the gold it could spend, the gold it spent, the constructions it started, the gold and the number of the constructions
# it wanted that waited for gold, its situation (SITUATION), and the last HISTORY_MONTHS passes' gold wanted and spent.
# The rules never read any of it. (What the rules DO keep from pass to pass, the purses and what a group saves for,
# is render_purse_values' state.) had = the purse the group started the pass with; goods = things it wanted that the
# market lacks the construction goods for; limited = things the market limit held back (render_market).
GROUP_NUMBERS = {"had": "dhad", "spent": "dspent", "started": "dn", "wait": "dwait", "waitn": "dwn",
                 "goods": "dgo", "limited": "dml"}
SITUATION: dict[str, tuple[tuple[str, int], ...]] = {
    # name, start value (+ 100; a running minimum starts high)
    "food": (("provinces", 100), ("famine", 100), ("hungry", 100), ("granary", 100), ("grange", 100)),
    "logistics": (("below", 100), ("lowest", 1099)),
    "improve": (("over", 100), ("fullest", 100)),
    # skipped: 1 when the group had neither gold saved nor gold coming in and did not look (pp_cplan_group_business)
    "business": (("sites", 100), ("best", 1099), ("skipped", 100)),
    "profiles": (("locs", 100), *((f"st{n}", 100) for n in range(1, 11))),  # the rule states, location_profiles.STATES
    "country": (),  # gold had, spent and waiting are enough; its own numbers are construction_plan_country.py's
}


def render_stats_effects() -> str:
    """The bookkeeping for the detail panes. A rule group looks only a few times a year (LOOKS), so its numbers, its
    list of constructions and its situation stay until its next look (pp_cplan_stats_reset_<why>, called by
    pp_cplan_group_start); pp_cplan_pass_reset forgets at each pass's start who looked in the last one
    (pp_cplan_now_<why>); the gold a group wanted and spent in a pass in which it looked goes into the history at the
    pass's end (pp_cplan_history_push: the oldest month drops out, a month without a look shows nothing), and
    switching the plan on clears the history (pp_cplan_history_clear)."""
    resets, now, push, clear = [], [], [], []
    for group in GROUPS:
        why = GROUP_WHY[group]
        rank = "\t\tremove_variable = pp_cplan_log_rank\n" if group == "country" else ""
        resets.append(
            f"\n# Country scope: the {group} group looks: what its last look left for the window is gone (its list of\n"
            f"# constructions and their entries on the locations, its numbers, its situation).\n"
            f"pp_cplan_stats_reset_{why} = {{\n"
            f"\tevery_in_list = {{\n\t\tvariable = pp_cplan_log_{why}\n\t\tpp_cplan_log_clear = {{ why = {why} }}\n{rank}\t}}\n"
            f"\tclear_variable_list = pp_cplan_log_{why}\n"
            # only Towns and Buildings can save for a town or city upgrade (no other group ever sets the variable)
            + ("\tremove_variable = pp_cplan_save_rank_107\n" if group == "country" else "")
            + "".join(f"\tset_variable = {{ name = pp_cplan_{var}_{why} value = 100 }}\n" for var in GROUP_NUMBERS.values())
            + "".join(f"\tset_variable = {{ name = pp_cplan_ds_{group}_{name} value = {start} }}\n"
                      for name, start in SITUATION[group])
            + "}\n")
        now.append(f"\tremove_variable = {NOW}_{why}\n")
        push.append(f"\t# {group}\n")
        for kind in ("hn", "hs"):
            push += [f"\tpp_cplan_copy_num = {{ from = pp_cplan_{kind}_{why}_{k - 1} to = pp_cplan_{kind}_{why}_{k} }}\n"
                     for k in range(HISTORY_MONTHS, 1, -1)]
            clear += [f"\tremove_variable = pp_cplan_{kind}_{why}_{k}\n" for k in range(1, HISTORY_MONTHS + 1)]
        push.append(
            f"\tif = {{\n\t\tlimit = {{ has_variable = {NOW}_{why} }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_hn_{why}_1 value = {{ value = var:pp_cplan_dspent_{why} "
            f"add = var:pp_cplan_dwait_{why} subtract = 100 }} }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_hs_{why}_1 value = var:pp_cplan_dspent_{why} }}\n\t}}\n"
            f"\telse = {{\n\t\tset_variable = {{ name = pp_cplan_hn_{why}_1 value = 100 }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_hs_{why}_1 value = 100 }}\n\t}}\n")
    return (
        "\n# ---- The window's detail panes (rules never read these) ----\n"
        + "".join(resets)
        + "\n# Country scope, at the start of pp_cplan_run: nobody has looked in this pass yet.\n"
        "pp_cplan_pass_reset = {\n" + "".join(now) + "}\n\n"
        f"# Country scope, at the end of pp_cplan_run: for a rule group that looked in this pass its gold wanted (spent +\n"
        f"# waiting for gold) and spent become month 1 of the history (nothing for a group that did not look), the older\n"
        f"# months move up one, month {HISTORY_MONTHS} drops out.\n"
        "pp_cplan_history_push = {\n" + "".join(push) + "}\n\n"
        "# Country scope: the history is gone (the plan was switched on).\npp_cplan_history_clear = {\n" + "".join(clear) + "}\n"
    )


def render_stats_values() -> str:
    """The detail panes' readouts (country scope): pp_cplan_d_<group>_<number> (GROUP_NUMBERS, need = spent + wait,
    ran = 1 / 0), pp_cplan_d_<group>_<situation>, and the chart: pp_cplan_h_<group>_need_<k> / _spent_<k> (gold, k = 1
    the last month), _needp_<k> / _spentp_<k> (% of the largest month wanted, the bars), _max, _sum_need, _sum_spent."""

    def readout(name: str, var: str) -> str:
        return (f"{name} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
                f"\t\tvalue = var:{var}\n\t\tsubtract = 100\n\t}}\n}}\n")

    parts = ["\n# ---- The window's detail panes (country scope; pp_cplan_stats_reset_<why>, pp_cplan_history_push) ----\n"]
    for group in GROUPS:
        why = GROUP_WHY[group]
        prefix = f"pp_cplan_d_{group}"
        parts.append(f"\n# {group} (construction code {why})\n")
        parts.append(f"{prefix}_ran = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ has_variable = pp_cplan_dran_{why} }}\n"
                     f"\t\tvalue = 1\n\t}}\n}}\n")
        parts += [readout(f"{prefix}_{number}", f"pp_cplan_{var}_{why}") for number, var in GROUP_NUMBERS.items()]
        parts.append(f"{prefix}_need = {{\n\tvalue = {prefix}_spent\n\tadd = {prefix}_wait\n}}\n")
        parts += [readout(f"{prefix}_{name}", f"pp_cplan_ds_{group}_{name}") for name, _ in SITUATION[group]]
        chart = f"pp_cplan_h_{group}"
        for k in range(1, HISTORY_MONTHS + 1):
            parts.append(readout(f"{chart}_need_{k}", f"pp_cplan_hn_{why}_{k}"))
            parts.append(readout(f"{chart}_spent_{k}", f"pp_cplan_hs_{why}_{k}"))
        months = range(1, HISTORY_MONTHS + 1)
        parts.append(f"{chart}_max = {{\n\tvalue = 1\n" + "".join(f"\tmin = {chart}_need_{k}\n" for k in months) + "}\n")
        for k in months:
            for kind in ("need", "spent"):
                parts.append(f"{chart}_{kind}p_{k} = {{\n\tvalue = {chart}_{kind}_{k}\n\tmultiply = 100\n"
                             f"\tdivide = {chart}_max\n}}\n")
        for kind in ("need", "spent"):
            parts.append(f"{chart}_sum_{kind} = {{\n\tvalue = 0\n"
                         + "".join(f"\tadd = {chart}_{kind}_{k}\n" for k in months) + "}\n")
    return "".join(parts)


def render_values(config: Config, demands: dict[str, dict[str, float]] | None = None,
                  bounds: tuple[float, float] = (0.5, 2.5)) -> str:
    parts = [HEADER, "\n# ---- Global settings with their defaults ([construction_plan]; the window's lines) ----\n\n"]
    parts.append(_default_value("pp_cplan_reserve_gold", "pp_cplan_reserve", config.reserve_gold,
                                "Country scope: the gold reserve in gold; the plan starts nothing that would spend below it."))
    parts.append(_default_value("pp_cplan_access_pct", "pp_cplan_access", config.access_threshold,
                                "Country scope: the logistics line, market access in %."))
    parts.append(_default_value("pp_cplan_improve_pct", "pp_cplan_imp", config.improve_fill_pct,
                                "Country scope: improvements where population reaches this % of a location's capacity."))
    parts.append(_default_value("pp_cplan_business_years", "pp_cplan_biz", config.business_years,
                                "Country scope: the business line, payback of a level in years."))
    parts.append(render_weight_values(config))
    parts.append(
        "# Country scope: the improvement line as a share of capacity (location_population_percentage).\n"
        "pp_cplan_improve_line = {\n\tvalue = pp_cplan_improve_pct\n\tdivide = 100\n}\n"
        "# Country scope: the business line as the yearly return a level must reach, in % of its cost (100 / years).\n"
        "pp_cplan_business_min_roi = {\n\tvalue = 100\n\tdivide = { value = pp_cplan_business_years min = 1 }\n}\n"
    )
    parts.append(
        "\n# ---- Script time: the business group's sites ([construction_plan] business_sites / _cycle_months / _tries) ----\n"
        "# Country scope: the sites whose business pick the pass refreshes: a fixed few, or as many as it takes to see\n"
        "# every location the country ever numbered (pp_cplan_seq_n) within the cycle.\n"
        "pp_cplan_bz_window = {\n\tvalue = 0\n\tif = {\n\t\tlimit = { has_variable = pp_cplan_seq_n }\n"
        f"\t\tvalue = var:pp_cplan_seq_n\n\t\tsubtract = 100\n\t\tdivide = {_num(business_refresh_passes(config))}\n\t}}\n"
        f"\tmin = {config.business_sites}\n}}\n"
        "# Any scope: the stored picks a look of the business group tries to build, best first.\n"
        f"pp_cplan_bz_tries = {{ value = {config.business_tries} }}\n"
        "# Country scope: what the rule groups started and spent at their last looks (the window's summary).\n"
        "pp_cplan_all_started = {\n\tvalue = 0\n"
        + "".join(f"\tadd = pp_cplan_d_{group}_started\n" for group in GROUPS)
        + "}\npp_cplan_all_spent = {\n\tvalue = 0\n"
        + "".join(f"\tadd = pp_cplan_d_{group}_spent\n" for group in GROUPS)
        + "}\n"
    )
    parts.append(_constant(
        "pp_cplan_market_share", config.business_market_share / 100,
        "Any scope: the market limit ([construction_plan] business_market_share): the share of a market's monthly demand "
        "for a good that the levels under construction of that good's makers may add up to."))
    parts.append("\n# ---- Food rule numbers ([construction_plan]; no window line) ----\n\n")
    for name, value, comment in (
        ("pp_cplan_hungry_months", config.hungry_months,
         "Province scope: hungry = a normal year leaves less than this many months in the store a year from now."),
        ("pp_cplan_famine_months", config.famine_months, "Any scope: the famine line, months in the store a year from now."),
        ("pp_cplan_granary_cap", config.granary_capacity_months,
         "Any scope: a Granary while the store can hold fewer months of consumption than this."),
        ("pp_cplan_granary_fill", config.granary_fill_pct, "Any scope: a Granary only while the store is at least this full, in %."),
        ("pp_cplan_grange_surplus", config.grange_surplus_pct,
         "Any scope: a Grange where a full store still gains this % of consumption a month."),
        ("pp_cplan_yard_payback", config.yard_payback_years,
         "Any scope: Victualling Yard levels while they pay back within this many years."),
        ("pp_cplan_tavern_victuals", config.tavern_victuals, "Any scope: victuals a Tavern's market must hold."),
        ("pp_cplan_farm_sites", config.farm_sites_per_province, "Any scope: locations tried per province for a staple food maker."),
    ):
        parts.append(_constant(name, value, comment))
    if demands is not None:
        parts.append(render_price_factors(demands, bounds))
    return "".join(parts)


# ---------------------------------------------------------------------------------------------------------------------
# scripted effects


ROOM = "pp_cplan_room_{key}"
NO_ROOM_LIMIT = 1000     # a type without max_levels: no level limit the plan knows of


def _room(name: str) -> str:
    """A level of ``name`` fits under its max level here. ``can_build_building`` in a location checks the potential,
    allow and the country, NOT the max level (2026-11-13, Jan's Venice game: the plan started Drainage Ditches in
    Treviso at a cap of 0.68 and a Cookshop in Karpathos at 0.7, both 0 levels; the engine checks the max level again
    when a construction finishes and cancelled each one, the gold spent lost). The engine's building_type_max_level
    trigger reads 0 for every type (the Construction Manager framework's in-game tests), so the plan reads each type's
    own max_levels (pp_cplan_room_<type>, render_room)."""
    return f"{ROOM.format(key=name)} >= 1"


def _can_build(name: str, costs: dict[str, BuildingCost]) -> str:
    """The vanilla can-build check, room under the max level, the construction goods in this market, and no level of
    it under construction here (the engine stalls a construction whose goods the market lacks; tested 2026-11-06,
    Edinburgh masonry)."""
    demand = costs.get(name, BuildingCost(0.0, DEFAULT_DEMAND, "std")).demand
    return (f"location_and_owner_can_build = {{ building_type = {name} }} {_room(name)} pp_cplan_goods_here_{demand} = yes "
            f"NOT = {{ any_buildings_in_location = {{ building_type = building_type:{name} building_levels_under_construction > 0 }} }}")


def _can_site(name: str) -> str:
    """_can_build without the construction goods: the pickers ask for the goods apart, so a thing the market lacks the
    goods for is counted for the window (pp_cplan_note_goods) instead of vanishing (in game 2026-11-10: a Library
    needs books, a town glass, and nothing happened with no reason shown)."""
    return (f"location_and_owner_can_build = {{ building_type = {name} }} {_room(name)} "
            f"NOT = {{ any_buildings_in_location = {{ building_type = building_type:{name} building_levels_under_construction > 0 }} }}")


def max_level_bodies(database: dict[str, tuple[dict[str, str], str]]) -> dict[str, str]:
    """Building type -> the body of a script value that gives its max level here: ``value = <number or named value>``,
    or the lines of its ``max_levels = { ... }`` block (the last top-level max_levels after the load order wins);
    a type without max_levels gets NO_ROOM_LIMIT."""
    pattern = re.compile(r"\bmax_levels\s*=\s*(\{|[A-Za-z0-9_.\-]+)|\{|\}")
    bodies: dict[str, str] = {}
    for name, (_keys, body) in database.items():
        last, depth = None, 0
        for match in pattern.finditer(body):
            if match.group(1) is not None:
                if depth == 0:
                    last = match
                if match.group(1) == "{":
                    depth += 1
            elif match.group(0) == "{":
                depth += 1
            else:
                depth -= 1
        if last is None:
            bodies[name] = f"\tvalue = {NO_ROOM_LIMIT}"
        elif last.group(1) != "{":
            bodies[name] = f"\tvalue = {last.group(1)}"
        else:
            start, depth = last.end(), 1
            for index in range(start, len(body)):
                depth += {"{": 1, "}": -1}.get(body[index], 0)
                if depth == 0:
                    break
            else:
                raise ValueError(f"max_levels of {name}: unbalanced block")
            lines = [line.strip() for line in body[start:index].splitlines() if line.strip()]
            bodies[name] = "\n".join("\t" + line for line in lines)
    return bodies


def render_room(database: dict[str, tuple[dict[str, str], str]]) -> tuple[str, str]:
    """Values and the trigger of the max-level check (``_room``): per building type the levels still free under its
    max level here (its own max_levels minus its standing levels; the engine floors the max level, so a value of 1 or
    more is one whole level), and ``pp_cplan_no_room`` for the one construct path, which gets its type as
    scope:pp_cplan_btype (businesses, Towns and Buildings, location profiles)."""
    bodies = max_level_bodies(database)
    values = ["\n# ---- Room under the max level (location scope): the type's own max_levels minus its standing levels ----\n"
              "# (can_build_building does not check the max level; the engine cancels a construction over it when it\n"
              "# finishes, 2026-11-13). A max_levels block is its own value (pp_cplan_lvcap_<type>), so its tooltip rows\n"
              "# stay its own; a type without max_levels (only DLC buildings) is never named (no DLC, no type to link).\n"]
    unlimited = f"\tvalue = {NO_ROOM_LIMIT}"
    for name in sorted(bodies):
        body = bodies[name]
        if body == unlimited:
            values.append(f"{ROOM.format(key=name)} = {{\n{body}\n}}\n")
            continue
        if "\n" in body:
            values.append(f"pp_cplan_lvcap_{name} = {{\n{body}\n}}\n")
            body = f"\tvalue = pp_cplan_lvcap_{name}"
        values.append(f"{ROOM.format(key=name)} = {{\n{body}\n"
                      f"\tsubtract = \"location_building_level(building_type:{name})\"\n}}\n")
    limited = [name for name in sorted(bodies) if bodies[name] != unlimited]
    trigger = ("\n# Location scope, scope:pp_cplan_btype set: no further level of that building type fits under its max level\n"
               "# here (pp_cplan_construct_scoped never starts one: the engine would cancel it when it finishes).\n"
               "pp_cplan_no_room = {\n\tOR = {\n"
               + "".join(f"\t\tAND = {{ scope:pp_cplan_btype = building_type:{name} {ROOM.format(key=name)} < 1 }}\n"
                         for name in limited)
               + "\t}\n}\n")
    return "".join(values), trigger


def _goods_here(name: str, costs: dict[str, BuildingCost]) -> str:
    demand = costs.get(name, BuildingCost(0.0, DEFAULT_DEMAND, "std")).demand
    return f"pp_cplan_goods_here_{demand} = yes"


def _first_that_can(buildings: tuple[str, ...], costs: dict[str, BuildingCost], build, why: int) -> str:
    """The body of a "first that can be built" picker (location scope): the first of ``buildings`` that can be built
    here and whose construction goods the market holds gets ``build(name)``, as before. One that can be built but
    lacks its goods is passed over as before (the next may still build: a Carrier Inn where the River Boatmen's Yard
    lacks naval supplies); when none is built, the rule group ``why`` counts one thing held back for construction
    goods. No more can-build checks than the old chain made."""
    parts = ["\tsave_temporary_scope_value_as = { name = pp_cplan_done value = 0 }\n"
             "\tsave_temporary_scope_value_as = { name = pp_cplan_ng value = 0 }\n"]
    for name in buildings:
        parts.append(
            f"\tif = {{\n\t\tlimit = {{ scope:pp_cplan_done < 0.5 {_can_site(name)} }}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ {_goods_here(name, costs)} }}\n"
            "\t\t\tsave_temporary_scope_value_as = { name = pp_cplan_done value = 1 }\n"
            f"\t\t\t{build(name)}\n\t\t}}\n"
            "\t\telse = {\n\t\t\tsave_temporary_scope_value_as = { name = pp_cplan_ng value = 1 }\n\t\t}\n\t}\n"
        )
    parts.append("\tif = {\n\t\tlimit = { scope:pp_cplan_done < 0.5 scope:pp_cplan_ng > 0.5 }\n"
                 f"\t\tpp_cplan_note_goods = {{ why = {why} }}\n\t}}\n")
    return "".join(parts)


def _method_value(name: str, recipe: Recipe) -> str:
    """A script value: one level's monthly profit of this method at the location's market prices and output."""
    lines = [f"{name} = {{", "\tvalue = 0"]
    if recipe.produced:
        lines.append(
            f"\tadd = {{ value = \"market.market_price(goods:{recipe.produced})\" "
            f"multiply = {{ value = modifier:local_{recipe.produced}_output_modifier add = 1 min = 0 }} "
            f"multiply = {_num(recipe.output)} }}"
        )
    for good, amount in recipe.inputs:
        lines.append(f"\tsubtract = {{ value = \"market.market_price(goods:{good})\" multiply = {_num(amount)} }}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_improvements(improvements: list[tuple[str, float]], costs: dict[str, BuildingCost]) -> tuple[str, str]:
    """Values and the picker of the improvements rule (Jan 2026-11-08): where people fill the owner's share of a
    location's capacity, the improvement that adds the most capacity per gold (its raw_modifier capacity per level over
    its price at the levels standing: cheap and much first)."""
    values = [
        "\n# ---- Improvements (location scope): capacity a level adds per 1,000 gold of its price here ----\n"
        "# (base price x (1 + increase_per_level_cost x the levels standing); the location's build efficiency and the\n"
        "# construction goods are the same for every improvement here)\n"
    ]
    effects = [
        "\n# Location scope: one level of the improvement that adds the most capacity per gold here (pp_cplan_imp_<key>),\n"
        "# among those that can be built; a standing older tier is replaced once its successor is researched. One the\n"
        "# market lacks the construction goods for is passed over; when nothing else is picked the location counts as\n"
        "# held back for construction goods (scope:pp_cplan_ng).\n"
        "pp_cplan_try_improve_here = {\n"
        "\tset_variable = { name = pp_cplan_best value = 0.001 }\n"
        "\tset_variable = { name = pp_cplan_pick value = 100 }\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_ng value = 0 }\n"
    ]
    for number, (key, land) in enumerate(improvements, 101):
        ipl = costs.get(key, BuildingCost(0.0, DEFAULT_DEMAND, "std")).ipl
        values.append(
            f"pp_cplan_imp_{key} = {{\n\tvalue = {_num(land * 1000)}\n\tdivide = {{\n"
            f"\t\tvalue = \"location_building_level(building_type:{key})\"\n\t\tmultiply = {_num(ipl)}\n\t\tadd = 1\n"
            f"\t\tmultiply = building_type:{key}.building_base_cost_in_gold\n\t\tmin = 1\n\t}}\n}}\n"
        )
        effects.append(
            f"\tif = {{\n\t\tlimit = {{ {_can_site(key)} pp_cplan_imp_{key} > var:pp_cplan_best }}\n"
            f"\t\tif = {{\n\t\t\tlimit = {{ {_goods_here(key, costs)} }}\n"
            f"\t\t\tset_variable = {{ name = pp_cplan_best value = pp_cplan_imp_{key} }}\n"
            f"\t\t\tset_variable = {{ name = pp_cplan_pick value = {number} }}\n\t\t}}\n"
            "\t\telse = {\n\t\t\tsave_temporary_scope_value_as = { name = pp_cplan_ng value = 1 }\n\t\t}\n\t}\n"
        )
    for number, (key, _land) in enumerate(improvements, 101):
        effects.append(
            f"\tif = {{\n\t\tlimit = {{ var:pp_cplan_pick > {number - 0.5:g} var:pp_cplan_pick < {number + 0.5:g} }}\n"
            f"\t\tpp_cplan_construct = {{ type = {key} why = {WHY_IMPROVE} }}\n\t}}\n"
        )
    effects.append(
        "\tif = {\n\t\tlimit = { var:pp_cplan_pick < 100.5 scope:pp_cplan_ng > 0.5 }\n"
        f"\t\tpp_cplan_note_goods = {{ why = {WHY_IMPROVE} }}\n\t}}\n"
        "\tremove_variable = pp_cplan_best\n\tremove_variable = pp_cplan_pick\n}\n")
    return "".join(values), "".join(effects)


def render_baseline_values(config: Config, farm_lines: dict[str, list[str]],
                           recipes: dict[str, list[list[Recipe]]], harvest: dict[str, dict[str, float]],
                           peasant_rate: float, access_amounts: dict[str, float],
                           costs: dict[str, BuildingCost]) -> str:
    """Values of the baseline rules: the harvest and access blacklists and the farm payback estimates."""
    parts = ["\n# ---- Baseline rules: what is taken out (Jan 2026-11-08: no history, a blacklist) ----\n\n"]
    # this year's harvest
    parts.append(
        "# Location scope: the food one unit of peasants eats more (bad harvest) or less (good harvest) a month this year:\n"
        "# the peasant food consumption of the location's Variable Harvest modifier x the peasants' food per head\n"
        f"# ({_num(peasant_rate)}). 0 in a normal year.\n"
        "pp_cplan_harvest_rate = {\n\tvalue = 0\n"
    )
    first = True
    for sub, severities in sorted(harvest.items()):
        parts.append(f"\t{'if' if first else 'else_if'} = {{\n\t\tlimit = {{ sub_continent = sub_continent:{sub} }}\n")
        inner = True
        for severity in HARVEST_SEVERITIES:
            if severity not in severities:
                continue
            parts.append(
                f"\t\t{'if' if inner else 'else_if'} = {{ limit = {{ has_location_modifier = pp_harvest_{sub}_{severity} }} "
                f"value = {_num(severities[severity] * peasant_rate)} }}\n"
            )
            inner = False
        parts.append("\t}\n")
        first = False
    parts.append("}\n\n")
    # market access
    parts.append(
        "# Location scope: market access without the event modifiers of [construction_plan] access_blacklist.\n"
        "pp_cplan_access_normal = {\n\tvalue = market_access\n"
        + "".join(
            f"\tif = {{ limit = {{ has_location_modifier = {name} }} subtract = {_num(amount)} }}\n"
            for name, amount in sorted(access_amounts.items())
        )
        + "}\n\n"
    )
    # farms: profit estimates per method, slot, tier; payback per line
    parts.append(
        "# ---- Farms: which line pays back fastest here (location scope, its market) ----\n"
        "# A level's monthly profit at this market's prices and this location's output: each slot's best method\n"
        "# (production efficiency, staffing and market access left out: the same for every line here). Its yearly\n"
        "# return in % of the tier's base price (pp_cplan_farm_roi_<tier>); a line's return is that of its highest tier\n"
        "# that can be built here (a standing older tier is replaced once its successor is researched).\n\n"
    )
    for line, tiers in farm_lines.items():
        for tier in tiers:
            slots = recipes.get(tier, [])
            slot_names = []
            for s_index, slot in enumerate(slots, 1):
                producing = [m for m in slot if m.produced or m.inputs]
                method_names = []
                for m_index, recipe in enumerate(producing, 1):
                    name = f"pp_cplan_fm_{tier}_{s_index}_{m_index}"
                    parts.append(_method_value(name, recipe))
                    method_names.append(name)
                if not method_names:
                    continue
                slot_name = f"pp_cplan_fs_{tier}_{s_index}"
                floor = len(producing) < len(slot)  # a method without goods (0) is the slot's other choice
                body = [f"{slot_name} = {{", f"\tvalue = {method_names[0]}"]
                body += [f"\tmin = {other}" for other in method_names[1:]]  # min = x floors at x: the best method
                if floor:
                    body.append("\tmin = 0")
                parts.append("\n".join(body) + "\n}\n")
                slot_names.append(slot_name)
            parts.append(
                f"pp_cplan_farm_est_{tier} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ market ?= {{ always = yes }} }}\n"
                + "".join(f"\t\tadd = {name}\n" for name in slot_names)
                + "\t}\n}\n"
                f"pp_cplan_farm_roi_{tier} = {{\n\tvalue = pp_cplan_farm_est_{tier}\n\tmultiply = 1200\n"
                f"\tdivide = {{ value = building_type:{tier}.building_base_cost_in_gold min = 1 }}\n}}\n\n"
            )
        parts.append(f"# Location scope: the {line} line's return here (0 where no tier can be built).\n"
                     f"pp_cplan_farm_line_roi_{line} = {{\n\tvalue = 0\n")
        for position, tier in enumerate(reversed(tiers)):
            parts.append(
                f"\t{'if' if position == 0 else 'else_if'} = {{\n\t\tlimit = {{ {_can_build(tier, costs)} }}\n"
                f"\t\tvalue = pp_cplan_farm_roi_{tier}\n\t}}\n"
            )
        parts.append("}\n")
    lines = list(farm_lines)
    parts.append(
        "# Location scope: the best line's return here (the farm sites' order).\n"
        "pp_cplan_farm_best_roi = {\n\tvalue = 0\n"
        + "".join(f"\tmin = pp_cplan_farm_line_roi_{line}\n" for line in lines)
        + "}\n"
    )
    return "".join(parts)


def _cost_data(cost: BuildingCost) -> str:
    """Effect lines (location scope) that set the cost data of a known building type for pp_cplan_est_*."""
    return (
        f"save_temporary_scope_value_as = {{ name = pp_cplan_ipl value = {_num(cost.ipl)} }} "
        f"save_temporary_scope_value_as = {{ name = pp_cplan_pf value = pp_cplan_cd_{cost.demand} }} "
        f"save_temporary_scope_value_as = {{ name = pp_cplan_ef value = pp_cplan_eff_{cost.category} }}"
    )


def render_btype_data(costs: dict[str, BuildingCost]) -> str:
    """pp_cplan_btype_data: the cost data of scope:pp_cplan_btype (a building type held in a variable), grouped so the
    lookup tests every type once per field."""
    parts = [
        "\n# Location scope, scope:pp_cplan_btype set: the build cost data of that building type (increase per level,\n"
        "# the price factor of its construction goods here, its efficiency term here) as temporary values for\n"
        "# pp_cplan_est_cost / pp_cplan_est_payback_years.\n"
        "pp_cplan_btype_data = {\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_ipl value = 0 }\n"
    ]
    by_ipl: dict[float, list[str]] = {}
    by_demand: dict[str, list[str]] = {}
    by_category: dict[str, list[str]] = {}
    for name, cost in sorted(costs.items()):
        if cost.ipl:
            by_ipl.setdefault(cost.ipl, []).append(name)
        if cost.demand != DEFAULT_DEMAND:
            by_demand.setdefault(cost.demand, []).append(name)
        if cost.category != "std":
            by_category.setdefault(cost.category, []).append(name)

    def chain(groups: dict, setter) -> None:
        first = True
        for key in sorted(groups, key=str):
            names = groups[key]
            tests = " ".join(f"scope:pp_cplan_btype = building_type:{name}" for name in names)
            parts.append(f"\t{'if' if first else 'else_if'} = {{\n\t\tlimit = {{ OR = {{ {tests} }} }}\n\t\t{setter(key)}\n\t}}\n")
            first = False

    chain(by_ipl, lambda ipl: f"save_temporary_scope_value_as = {{ name = pp_cplan_ipl value = {_num(ipl)} }}")
    parts.append(f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_pf value = pp_cplan_cd_{DEFAULT_DEMAND} }}\n")
    parts.append("\tsave_temporary_scope_value_as = { name = pp_cplan_gok value = 1 }\n"
                 f"\tif = {{ limit = {{ NOT = {{ pp_cplan_goods_here_{DEFAULT_DEMAND} = yes }} }} "
                 "save_temporary_scope_value_as = { name = pp_cplan_gok value = 0 } }\n")
    chain(by_demand, lambda demand: (
        f"save_temporary_scope_value_as = {{ name = pp_cplan_pf value = pp_cplan_cd_{demand} }} "
        "save_temporary_scope_value_as = { name = pp_cplan_gok value = 1 } "
        f"if = {{ limit = {{ NOT = {{ pp_cplan_goods_here_{demand} = yes }} }} "
        "save_temporary_scope_value_as = { name = pp_cplan_gok value = 0 } }"))
    parts.append("\tsave_temporary_scope_value_as = { name = pp_cplan_ef value = pp_cplan_eff_std }\n")
    chain(by_category, lambda category: f"save_temporary_scope_value_as = {{ name = pp_cplan_ef value = pp_cplan_eff_{category} }}")
    parts.append("}\n")
    return "".join(parts)


def render_effects(config: Config, farm_lines: dict[str, list[str]],
                   costs: dict[str, BuildingCost] | None = None) -> str:
    costs = costs or {}

    def can(name: str) -> str:
        return _can_build(name, costs)

    parts = [HEADER]
    # --- farm picker
    parts.append(
        "\n# Location scope (owned by scope:pp_cplan_country). Builds a level of the staple food line (crop farms, orchards,\n"
        "# fisheries, herds, forest villages) that pays back fastest here (pp_cplan_farm_line_roi_<line>: the market's\n"
        "# prices, the location's output), at its highest tier that can be built; none where no line makes a profit (a\n"
        "# building that loses money lays off its workers and makes no food).\n"
        "pp_cplan_try_farm_here = {\n"
        "\tset_variable = { name = pp_cplan_best value = 0.001 }\n"
        "\tset_variable = { name = pp_cplan_pick value = 100 }\n"
    )
    for number, line in enumerate(farm_lines, 101):
        parts.append(
            f"\tif = {{\n\t\tlimit = {{ pp_cplan_farm_line_roi_{line} > var:pp_cplan_best }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_best value = pp_cplan_farm_line_roi_{line} }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_pick value = {number} }}\n\t}}\n"
        )
    for number, (line, tiers) in enumerate(farm_lines.items(), 101):
        parts.append(f"\tif = {{\n\t\tlimit = {{ var:pp_cplan_pick > {number - 0.5:g} var:pp_cplan_pick < {number + 0.5:g} }}\n")
        for position, tier in enumerate(reversed(tiers)):
            parts.append(
                f"\t\t{'if' if position == 0 else 'else_if'} = {{\n\t\t\tlimit = {{ {can(tier)} }}\n"
                f"\t\t\tpp_cplan_construct_food = {{ type = {tier} }}\n\t\t}}\n"
            )
        parts.append("\t}\n")
    parts.append("\tremove_variable = pp_cplan_best\n\tremove_variable = pp_cplan_pick\n}\n")

    # --- Victualling Yard
    parts.append(
        "\n# Location scope: a Victualling Yard level here: the next level of a standing Yard while it pays back within the\n"
        "# food rule's line (pp_cplan_yard_payback), a first level where victuals cost at least their default price here.\n"
        "pp_cplan_try_yard_here = {\n"
    )
    for position, building in enumerate(config.yards):
        parts.append(
            f"\t{'if' if position == 0 else 'else_if'} = {{\n\t\tlimit = {{ {_can_site(building)} }}\n"
            f"\t\tbuilding_type:{building} = {{ save_scope_as = pp_cplan_btype }}\n"
            "\t\tpp_cplan_btype_data = yes\n"
            "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\tOR = {\n"
            "\t\t\t\t\tAND = {\n\t\t\t\t\t\tpp_cplan_bt_levels > 0.5\n"
            "\t\t\t\t\t\tpp_cplan_est_payback_years <= pp_cplan_yard_payback\n\t\t\t\t\t}\n"
            "\t\t\t\t\tAND = {\n\t\t\t\t\t\tpp_cplan_bt_levels < 0.5\n\t\t\t\t\t\tpp_cplan_victuals_price_ratio >= 1\n\t\t\t\t\t}\n"
            "\t\t\t\t}\n\t\t\t}\n"
            f"\t\t\tif = {{\n\t\t\t\tlimit = {{ {_goods_here(building, costs)} }}\n"
            f"\t\t\t\tpp_cplan_construct_food = {{ type = {building} }}\n\t\t\t}}\n"
            f"\t\t\telse = {{\n\t\t\t\tpp_cplan_note_goods = {{ why = {WHY_FOOD} }}\n\t\t\t}}\n\t\t}}\n\t}}\n"
        )
    parts.append("}\n")

    # --- capital food buildings
    for name, buildings, comment in (
        ("pp_cplan_try_kitchen_here", config.kitchens, "a kitchen level (the province's Cookshop budget is its max level)"),
        ("pp_cplan_try_tavern_here", config.taverns, "a Tavern level"),
        ("pp_cplan_try_granary_here", config.granaries, "a Granary level"),
        ("pp_cplan_try_grange_here", config.granges, "a Grange level"),
    ):
        parts.append(f"\n# Location scope (the province capital): {comment}, first that can be built (one the market lacks\n"
                     f"# the construction goods for is counted for the window, pp_cplan_note_goods).\n{name} = {{\n")
        parts.append(_first_that_can(tuple(buildings), costs,
                                     lambda building: f"pp_cplan_construct_food = {{ type = {building} }}", WHY_FOOD))
        parts.append("}\n")

    # --- logistics
    parts.append("\n# Location scope: the first logistics building that can be built here ([construction_plan] logistics_order;\n"
                 "# one the market lacks the construction goods for is counted for the window).\n"
                 "pp_cplan_try_logistics_here = {\n")
    parts.append(_first_that_can(tuple(config.logistics_order), costs,
                                 lambda building: f"pp_cplan_construct = {{ type = {building} why = {WHY_LOGISTICS} }}",
                                 WHY_LOGISTICS))
    parts.append("}\n")

    if costs:
        parts.append(render_btype_data(costs))

    flags = sorted({*GROUPS, "reserve", "reserve_big", "access_line", "improve_line", "business_line", "up", "down"}
                   | {f"w{n}" for n in range(1, WEIGHT_STEPS + 1)})
    parts.append(
        "\n# Any scope, never run (pp_cplan_run calls it under always = no): declares the flags the window passes, so the\n"
        "# script check logs no 'used but never set' line for them.\npp_cplan_declare_flags = {\n"
        + "".join(f"\tset_variable = {{ name = pp_cplan_flag value = flag:{flag} }}\n" for flag in flags)
        + "}\n"
    )
    return "".join(parts)


def _business_method(name: str, recipe: Recipe, harvest_goods: set[str]) -> str:
    """A script value: one level's monthly profit of this method at the location's market prices and its output, this
    year's Variable Harvest taken out (scope:pp_cplan_hv_<good>, set by pp_cplan_business_harvest)."""
    lines = [f"{name} = {{", "\tvalue = 0"]
    if recipe.produced:
        good = recipe.produced
        normal = f" subtract = scope:pp_cplan_hv_{good}" if good in harvest_goods else ""
        lines.append(
            f"\tadd = {{ value = \"market.market_price(goods:{good})\" "
            f"multiply = {{ value = modifier:local_{good}_output_modifier add = 1{normal} min = 0 }} "
            f"multiply = {_num(recipe.output)} }}"
        )
    for good, amount in recipe.inputs:
        lines.append(f"\tsubtract = {{ value = \"market.market_price(goods:{good})\" multiply = {_num(amount)} }}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_business(businesses: dict[str, str], recipes: dict[str, list[list[Recipe]]],
                    costs: dict[str, BuildingCost], harvest: dict[str, dict[str, dict[str, float]]],
                    categories: dict[str, str], profile_categories: tuple[str, ...],
                    staff: dict[str, tuple[str, float]] | None = None) -> tuple[str, str]:
    """Values and effects of the business rule (Jan 2026-11-09): every building that makes goods, wherever a level pays
    back within the player's line, shortest payback first. A level's monthly profit = each slot's best method at the
    market's prices and the location's output with this year's Variable Harvest taken out; the same for a new building
    and for one more level, so the two compare. Its yearly return = profit x 12 over the level's build cost (the
    engine's formula), in %."""
    harvest_goods = sorted({good for severities in harvest.values() for goods in severities.values() for good in goods})
    hv = set(harvest_goods)
    values = [
        "\n# ---- Businesses (location scope, its market): a level's monthly profit and yearly return ----\n"
        "# pp_cplan_bm_<type>_<slot>_<method>: one method's profit (goods made at the market's price x the location's\n"
        "# output without this year's harvest, minus its inputs at the market's prices); pp_cplan_bs_*: the slot's best;\n"
        "# pp_cplan_bz_est_<type>: the level's profit; pp_cplan_bz_roi_<type>: x 12 over its build cost, in %\n"
        "# (scope:pp_cplan_btype and the cost data set by pp_cplan_business_pick).\n\n"
    ]
    effects = []
    # this year's harvest, taken out of the goods output
    effects.append(
        "\n# Location scope: this year's Variable Harvest per good (its local output modifier, 0 in a normal year) as\n"
        "# scope:pp_cplan_hv_<good>; the business estimates take it out.\npp_cplan_business_harvest = {\n"
        + "".join(f"\tsave_temporary_scope_value_as = {{ name = pp_cplan_hv_{good} value = 0 }}\n" for good in harvest_goods)
    )
    first = True
    for sub_name, severities in sorted(harvest.items()):
        effects.append(f"\t{'if' if first else 'else_if'} = {{\n\t\tlimit = {{ sub_continent = sub_continent:{sub_name} }}\n")
        inner = True
        for severity in HARVEST_SEVERITIES:
            goods = severities.get(severity)
            if goods is None:
                continue
            body = " ".join(f"save_temporary_scope_value_as = {{ name = pp_cplan_hv_{good} value = {_num(amount)} }}"
                            for good, amount in sorted(goods.items()))
            effects.append(f"\t\t{'if' if inner else 'else_if'} = {{ limit = {{ has_location_modifier = pp_harvest_{sub_name}_{severity} }} {body} }}\n")
            inner = False
        effects.append("\t}\n")
        first = False
    effects.append("}\n")

    names = [name for name in businesses if recipes.get(name)]
    for name in names:
        slot_names = []
        for s_index, slot in enumerate(recipes[name], 1):
            producing = [m for m in slot if m.produced or m.inputs]
            method_names = []
            for m_index, recipe in enumerate(producing, 1):
                method = f"pp_cplan_bm_{name}_{s_index}_{m_index}"
                values.append(_business_method(method, recipe, hv))
                method_names.append(method)
            if not method_names:
                continue
            slot_name = f"pp_cplan_bs_{name}_{s_index}"
            body = [f"{slot_name} = {{", f"\tvalue = {method_names[0]}"]
            body += [f"\tmin = {other}" for other in method_names[1:]]  # min = x floors at x: the best method
            if len(producing) < len(slot):
                body.append("\tmin = 0")  # a method without goods is the slot's other choice
            values.append("\n".join(body) + "\n}\n")
            slot_names.append(slot_name)
        values.append(
            f"pp_cplan_bz_est_{name} = {{\n\tvalue = 0\n" + "".join(f"\tadd = {s}\n" for s in slot_names) + "}\n"
            f"pp_cplan_bz_roi_{name} = {{\n\tvalue = pp_cplan_bz_est_{name}\n\tmultiply = 1200\n"
            "\tdivide = { value = pp_cplan_est_cost min = 0.01 }\n}\n\n"
        )

    # the country's buildable types, once a month
    effects.append(
        "\n# Country scope: marks every business type the country can build now (pp_cplan_bz_<type>; the country's part of the\n"
        "# can-build check, once a pass instead of once per location), and clears the marks after the pass.\n"
        "pp_cplan_business_types = {\n"
        + "".join(f"\tif = {{ limit = {{ can_build_building = building_type:{name} }} set_variable = {{ name = pp_cplan_bz_{name} value = yes }} }}\n"
                  for name in names)
        + "}\npp_cplan_business_types_clear = {\n"
        + "".join(f"\tremove_variable = pp_cplan_bz_{name}\n" for name in names)
        + "}\n"
    )
    # the pick per location
    effects.append(
        "\n# Location scope (a business site of scope:pp_cplan_country): the business with the best yearly return here that\n"
        "# reaches the owner's line (pp_cplan_business_min_roi = 100 / years), as pp_cplan_bz_pick (a building type),\n"
        "# pp_cplan_bz_roi (its return, %) and pp_cplan_bz_cost (the level's cost); none where none does. A candidate: the\n"
        "# country can build it, so can this location (allow, potential), a level fits under its max level here\n"
        "# (pp_cplan_room_<type>: can_build_building does not check it), a level finds its workers here\n"
        "# (pp_cplan_staff), no level of it here is closed (the player or the game's Close and Open automation found it\n"
        "# does not pay), and a profile here leaves its good and building category to the plan. A candidate that would be\n"
        "# the best so far is taken only when the market holds its construction goods and has room for its good\n"
        "# (pp_cplan_business_take: the market limit, pp_cplan_market_room), so the site moves on to its next best\n"
        "# business instead of sitting idle; a site that passed one over for either reason is counted for the window\n"
        "# (scope:pp_cplan_bz_go / _ml).\n"
        "pp_cplan_business_pick = {\n"
        "\tpp_cplan_business_harvest = yes\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_free_peasants value = pp_cplan_free_peasants_here }\n"
        "\tremove_variable = pp_cplan_bz_pick\n"
        "\tremove_variable = pp_cplan_bz_cost\n"
        "\tset_variable = { name = pp_cplan_bz_roi value = scope:pp_cplan_country.pp_cplan_business_min_roi }\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_bz_go value = 0 }\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_bz_ml value = 0 }\n"
    )
    for name in names:
        cost = costs.get(name, BuildingCost(0.0, DEFAULT_DEMAND, "std"))
        good = businesses[name]
        profile = f"\t\t\tNOT = {{ pp_lprof_has_good = {{ g = {good} }} }}\n"
        if categories.get(name) in profile_categories:
            profile += f"\t\t\tNOT = {{ pp_lprof_has_category = {{ c = {categories[name]} }} }}\n"
        workers = staff_check((staff or {}).get(name))
        effects.append(
            "\tif = {\n\t\tlimit = {\n"
            f"\t\t\tscope:pp_cplan_country = {{ has_variable = pp_cplan_bz_{name} }}\n"
            + (f"\t\t\t{workers}\n" if workers else "")
            + f"\t\t\tcan_build_building = building_type:{name}\n"
            + f"\t\t\t{_room(name)}\n"
            + profile
            + f"\t\t\tNOT = {{ any_buildings_in_location = {{ building_type = building_type:{name} building_level > 0 is_opened = no }} }}\n"
            "\t\t}\n"
            f"\t\tbuilding_type:{name} = {{ save_scope_as = pp_cplan_btype }}\n"
            f"\t\t{_cost_data(cost)}\n"
            f"\t\tsave_temporary_scope_value_as = {{ name = pp_cplan_r value = pp_cplan_bz_roi_{name} }}\n"
            "\t\tif = {\n\t\t\tlimit = { scope:pp_cplan_r > var:pp_cplan_bz_roi }\n"
            f"\t\t\tpp_cplan_business_take = {{ g = {good} out = {_num(main_output(recipes[name], good))} "
            f"demand = {cost.demand} }}\n\t\t}}\n\t}}\n"
        )
    effects.append(
        "\tif = {\n\t\tlimit = { NOT = { has_variable = pp_cplan_bz_pick } }\n\t\tremove_variable = pp_cplan_bz_roi\n\t}\n"
        "\tif = {\n\t\tlimit = { scope:pp_cplan_bz_go > 0.5 }\n"
        f"\t\tpp_cplan_note_goods = {{ why = {WHY_BUSINESS} }}\n\t}}\n"
        "\tif = {\n\t\tlimit = { scope:pp_cplan_bz_ml > 0.5 }\n"
        f"\t\tpp_cplan_note_market = {{ why = {WHY_BUSINESS} }}\n\t}}\n}}\n")
    return "".join(values), "".join(effects)


# ---- The market limit (Jan 2026-11-10: "if it detects that some building is profitable, like horses, it spams 500
# buildings of that type, which will likely crash the market") ----
# A level of a building whose main good is a market good starts only while, in the location's market, the output of
# that good under construction (every level under construction there of the buildings whose main good it is, whoever
# started them, at their recipe's output a level) plus this level's stays within [construction_plan]
# business_market_share % of the market's monthly demand for the good; with nothing of the good under construction one
# level is always allowed. ONE place asks, for everything that builds a business type: pp_cplan_construct_scoped
# (through the dispatch pp_cplan_market_do) for the rule groups of MARKET_LIMITED, and the business pick with the same
# trigger so a site moves on to its next best good. "Under construction" is counted once per market and good per pass,
# only when a pick needs it (pp_cplan_market_load), kept on the market's centre location (market.location;
# pp_cplan_uc_<good>, + 100: a market scope holds no variables, in game 2026-11-10), raised when the plan starts a
# level, and cleared at the pass's end (the country's list pp_cplan_markets of those centres).
# the Businesses group and the Locations group's profile rules; a location's marks are forced and pass the limit by
# (scope:pp_cplan_forced, pp_cplan_construct_scoped)
MARKET_LIMITED = ("business", "profiles")


def main_output(slots: list[list[Recipe]], good: str) -> float:
    """One level's monthly output of ``good``: in every slot the method that makes the most of it (the business
    estimate's recipes; the location's output modifiers left out)."""
    return sum(max((m.output for m in slot if m.produced == good), default=0.0) for slot in slots)


def market_outputs(businesses: dict[str, str], recipes: dict[str, list[list[Recipe]]]) -> dict[str, dict[str, float]]:
    """good -> building type -> one level's output of the good, for every business type that makes its main good."""
    found: dict[str, dict[str, float]] = {}
    for name, good in sorted(businesses.items()):
        output = main_output(recipes.get(name, []), good)
        if output > 0:
            found.setdefault(good, {})[name] = output
    return found


BUSINESS_BLOCKS = 64  # lists of the business order's blocks; the last one takes every number past them


def render_business_blocks(block: int) -> str:
    """The business refresh without a walk over the country (in game 2026-11-10: that walk was half the refresh's
    script time): every numbered location is on the list of its block of ``block`` numbers of the order
    (pp_cplan_bzb_<n> on the country), and a pass reads only the lists its numbers (scope:pp_cplan_from, exclusive, to
    scope:pp_cplan_to) fall in."""
    walk = [
        "\n# ---- Script time: the business order in blocks ----\n\n"
        "# Country scope, in pp_cplan_business_refresh (scope:pp_cplan_from / _to: this pass's numbers of the order, + 100):\n"
        f"# the lists of the blocks of {block} numbers they fall in, and of those the locations whose turn it is and that\n"
        "# are still the country's.\n"
        "pp_cplan_business_walk = {\n"
    ]
    place = [
        "\n# Location scope, once, when the location got its number (pp_cplan_seq, + 100): on the list of its block.\n"
        "pp_cplan_business_block = {\n\tsave_temporary_scope_as = pp_cplan_numbered\n"
    ]
    for n in range(1, BUSINESS_BLOCKS + 1):
        low, high = 100 + (n - 1) * block, 100 + n * block
        last = n == BUSINESS_BLOCKS
        within = f"scope:pp_cplan_to > {low}" if last else f"scope:pp_cplan_from < {high} scope:pp_cplan_to > {low}"
        walk.append(
            f"\tif = {{\n\t\tlimit = {{ {within} }}\n"
            f"\t\tevery_in_list = {{\n\t\t\tvariable = pp_cplan_bzb_{n}\n"
            "\t\t\tlimit = { pp_cplan_business_turn = yes owner ?= scope:pp_cplan_country }\n"
            "\t\t\tpp_cplan_business_turn_here = yes\n\t\t}\n\t}\n"
        )
        add = (f"scope:pp_cplan_country = {{ add_to_variable_list = {{ name = pp_cplan_bzb_{n} "
               "target = scope:pp_cplan_numbered } }")
        if last:
            place.append(f"\telse = {{\n\t\t{add}\n\t}}\n")
        else:
            place.append(f"\t{'if' if n == 1 else 'else_if'} = {{\n\t\tlimit = {{ var:pp_cplan_seq <= {high} }}\n"
                         f"\t\t{add}\n\t}}\n")
    walk.append("}\n")
    place.append("}\n")
    return "".join(walk) + "".join(place)


def render_market(outputs: dict[str, dict[str, float]]) -> tuple[str, str, str]:
    """The market limit's generated parts: values, effects, triggers."""
    values = [
        "\n# ---- The market limit (construction_plan.py render_market) ----\n"
        "# pp_cplan_uc_here_<good> (location scope): the monthly output of the good the levels under construction here\n"
        "# will add (the buildings whose main good it is, at their recipe's output a level);\n"
        "# pp_cplan_uc_market_<good> (market scope): the same over the market's locations with a construction;\n"
        "# pp_cplan_mroom_<good> (the market's centre location): the output of the good that may still start = the\n"
        "# market's monthly demand x pp_cplan_market_share minus what is under construction (pp_cplan_uc_<good>, + 100,\n"
        "# kept on that location for the pass by pp_cplan_market_load; a market scope holds no variables).\n\n"
    ]
    for good, types in sorted(outputs.items()):
        by_output: dict[float, list[str]] = {}
        for name, output in sorted(types.items()):
            by_output.setdefault(output, []).append(name)
        values.append(f"pp_cplan_uc_here_{good} = {{\n\tvalue = 0\n")
        for output, names in sorted(by_output.items()):
            tests = " ".join(f"building_type = building_type:{name}" for name in names)
            which = f"OR = {{ {tests} }}" if len(names) > 1 else tests
            values.append(
                "\tevery_buildings_in_location = {\n"
                f"\t\tlimit = {{ building_levels_under_construction > 0 {which} }}\n"
                f"\t\tadd = {{ value = building_levels_under_construction multiply = {_num(output)} }}\n\t}}\n"
            )
        values.append(
            "}\n"
            f"pp_cplan_uc_market_{good} = {{\n\tvalue = 0\n\tevery_location_in_market = {{\n"
            f"\t\tlimit = {{ num_civil_constructions > 0 }}\n\t\tadd = pp_cplan_uc_here_{good}\n\t}}\n}}\n"
            f"pp_cplan_mroom_{good} = {{\n\tvalue = \"market.goods_demand_in_market(goods:{good})\"\n"
            "\tmultiply = pp_cplan_market_share\n"
            f"\tif = {{\n\t\tlimit = {{ has_variable = pp_cplan_uc_{good} }}\n"
            f"\t\tsubtract = {{ value = var:pp_cplan_uc_{good} subtract = 100 }}\n\t}}\n}}\n"
        )
    groups: dict[tuple[str, float], list[str]] = {}
    for good, types in sorted(outputs.items()):
        for name, output in sorted(types.items()):
            groups.setdefault((good, output), []).append(name)
    effects = [
        "\n# ---- The market limit ----\n\n"
        "# Location scope, scope:pp_cplan_btype set: for a business type, the market limit's step $do$ with the type's main\n"
        "# good and one level's output of it: gate (pp_cplan_market_gate_good: scope:pp_cplan_mok = 0 where the market has\n"
        "# no room) or add (pp_cplan_market_add_good: a level was started). Other building types: nothing.\n"
        "pp_cplan_market_do = {\n"
    ]
    for position, ((good, output), names) in enumerate(sorted(groups.items())):
        tests = " ".join(f"scope:pp_cplan_btype = building_type:{name}" for name in names)
        effects.append(
            f"\t{'if' if position == 0 else 'else_if'} = {{\n\t\tlimit = {{ OR = {{ {tests} }} }}\n"
            f"\t\tpp_cplan_market_$do$_good = {{ g = {good} out = {_num(output)} }}\n\t}}\n"
        )
    effects.append(
        "}\n\n# A market's centre location, at the end of the pass: what the pass counted for its market is gone.\n"
        "pp_cplan_market_clear = {\n\tremove_variable = pp_cplan_uc_counted\n"
        + "".join(f"\tremove_variable = pp_cplan_uc_{good}\n" for good in sorted(outputs))
        + "}\n"
        "\n# Building scope, in pp_cplan_market_load's one walk over a market (scope:pp_cplan_this_market = its centre,\n"
        "# scope:pp_cplan_uc_levels = this building's levels under construction): a business type adds its levels x one\n"
        "# level's output to its main good's count there. Other building types: nothing.\n"
        "pp_cplan_market_count_building = {\n"
        + "".join(
            f"\t{'if' if position == 0 else 'else_if'} = {{\n\t\tlimit = {{ "
            + (f"OR = {{ {' '.join(f'building_type = building_type:{name}' for name in names)} }}" if len(names) > 1
               else f"building_type = building_type:{names[0]}")
            + f" }}\n\t\tscope:pp_cplan_this_market = {{ pp_cplan_market_count_add = {{ g = {good} out = {_num(output)} }} }}\n\t}}\n"
            for position, ((good, output), names) in enumerate(sorted(groups.items())))
        + "}\n"
    )
    triggers = [
        "\n# Any scope: the market limit holds for the constructions of the rule group with this code (the Businesses\n"
        "# group and profile rules; a location's marks are forced: scope:pp_cplan_forced; the food rule builds for hunger,\n"
        "# the others no business types of their own).\n"
    ]
    limited = {GROUP_WHY[group] for group in MARKET_LIMITED}
    for group in GROUPS:
        why = GROUP_WHY[group]
        triggers.append(f"pp_cplan_limits_market_{why} = {{\n\talways = {'yes' if why in limited else 'no'}\n}}\n")
    return "".join(values), "".join(effects), "".join(triggers)


def render_triggers(demands: dict[str, dict[str, float]] | None = None,
                    food_buildings: list[str] | None = None, goods_months: int = 12) -> str:
    parts = [HEADER]
    if demands is not None:
        parts.append(
            f"\n# Location scope: the location's market holds {goods_months} months of one construction's draw of every\n"
            "# construction good of the demand (the engine stalls a construction whose market lacks its goods: \"Lack of\n"
            "# access to goods\"). One month's draw was too little: in the test world (2026-11-08) four River Boatmen's\n"
            "# Yards started on 0.65 naval supplies in Burgos and stood still for a year.\n"
        )
        for key in sorted(demands):
            tests = " ".join(f"\"stockpile_in_market(goods:{good})\" >= {_num(amount * goods_months)}"
                             for good, amount in sorted(demands[key].items()))
            body = f"\tmarket ?= {{ {tests} }}\n" if tests else "\talways = yes\n"
            parts.append(f"pp_cplan_goods_here_{key} = {{\n{body}}}\n")
    if food_buildings:
        parts.append(
            "\n# Location scope: a building the food rule builds has a level under construction here (the rule waits for it).\n"
            "pp_cplan_food_queued = {\n\tany_buildings_in_location = {\n\t\tbuilding_levels_under_construction > 0\n\t\tOR = {\n"
            + "".join(f"\t\t\tbuilding_type = building_type:{name}\n" for name in food_buildings)
            + "\t\t}\n\t}\n}\n"
        )
    return "".join(parts)


# ---------------------------------------------------------------------------------------------------------------------


def _write(path: Path, text: str, write: bool) -> bool:
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    if old == text:
        return False
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return True


def apply(repo: Path, project: Path, mod_root: Path, vanilla_root: Path, write: bool = True) -> Result:
    config = load_config(project)
    result = Result()
    database = _database(mod_root, vanilla_root, BUILDING_TYPES)
    costs, demands = building_costs(mod_root, vanilla_root, database)
    known = set(costs)
    result.buildings = costs
    result.demands = demands
    bounds = price_impact_bounds(mod_root, vanilla_root)

    table = crop_farms.load_crop_table(repo)
    farm_goods_by_building = crop_farms.crop_building_goods(table)
    lines: dict[str, list[str]] = {}
    for building in crop_farms.crop_buildings(table):
        line = building.split("_", 1)[0]
        lines.setdefault(line, []).append(building)
    farm_goods = {line: farm_goods_by_building[tiers[0]] for line, tiers in lines.items()}
    result.farm_lines = lines
    result.logistics = list(config.logistics_order)

    short = market_short_weight.apply(project, mod_root, vanilla_root, write=False)
    # the hunger rule's candidates: crop farm lines and every other staple food maker (orchards, fisheries, herds,
    # forest villages), one bucket ranked by payback (Jan 2026-11-08)
    food_lines, _ = staple_food_lines(repo, mod_root, lines, farm_goods, short.main_good,
                                      set(config.kitchens) | set(config.taverns))
    result.food_lines = food_lines
    food_buildings = [b for tiers in food_lines.values() for b in tiers]

    # improvements (Jan 2026-11-08): every building with a World Builder cap that adds capacity (arable_land_bar)
    from prosper_or_perish_constructor import arable_land_bar
    improvements = [(b.key, b.land) for b in arable_land_bar.model(mod_root, vanilla_root / "game").improvements]
    result.improvements = [key for key, _ in improvements]
    improve_values, improve_effects = render_improvements(improvements, costs)
    room_values, room_triggers = render_room(database)

    # businesses (Jan 2026-11-09): every producer of a market good, without the other rules' own buildings
    own = set(config.kitchens) | set(config.taverns) | set(config.granaries) | set(config.granges) | set(config.yards)
    own |= set(config.logistics_order) | set(result.improvements)
    result.businesses = {building: good for building, good in sorted(short.main_good.items())
                         if good not in config.hidden_goods and building not in own}
    categories = {name: database[name][0].get("category", "") for name in result.businesses if name in database}
    result.staff = staffing(database, script_value_numbers(mod_root, vanilla_root))
    result.pop_types = sorted(_database(mod_root, vanilla_root, POP_TYPES))
    recipes = built_recipes(database, list(result.businesses))
    business_values, business_effects = render_business(
        result.businesses, recipes, costs, harvest_outputs(mod_root),
        categories, config.profile_categories, result.staff)
    # the market limit (2026-11-10): one level's output of its main good per business type
    result.market_outputs = market_outputs(result.businesses, recipes)
    market_values, market_effects, market_triggers = render_market(result.market_outputs)
    market_effects = render_business_blocks(config.business_sites) + market_effects  # (the business order in blocks)

    from prosper_or_perish_constructor import construction_plan_detail  # imports this module

    wanted = food_buildings + list(config.kitchens) + list(config.taverns) + result.improvements
    wanted += list(config.granaries) + list(config.granges) + list(config.yards) + list(config.logistics_order)
    wanted += list(result.businesses)
    result.missing = sorted({name for name in wanted if name not in known})

    texts = {
        mod_root / VALUES: render_values(config, demands, bounds)
        + render_baseline_values(
            config, food_lines, farm_recipes(repo, food_buildings),
            harvest_rates(mod_root), peasant_food_consumption(mod_root, vanilla_root),
            access_modifier_amounts(mod_root, vanilla_root, config.access_blacklist), costs,
        )
        + improve_values + business_values + market_values + render_idle_values(result.pop_types)
        + render_purse_values() + render_stats_values() + room_values,
        mod_root / EFFECTS: render_effects(config, food_lines, costs) + improve_effects + business_effects
        + market_effects + render_purse_effects() + render_stats_effects(),
        # the hunger steps wait for what they start (staple food makers, Taverns); kitchens are built anyway and must
        # not hold farms back for the year a Cookshop takes (seen in game 2026-11-08)
        mod_root / TRIGGERS: render_triggers(demands, food_buildings + list(config.taverns),
                                             config.construction_goods_months) + market_triggers + render_looks(config)
        + room_triggers,
        mod_root / WEIGHT_GUI: render_weight_gui(),
        # the window's detail panes (Jan 2026-11-09): a cog per rule group, the numbers render_stats_values gives
        mod_root / construction_plan_detail.DETAIL_GUI: construction_plan_detail.render_gui(),
        mod_root / construction_plan_detail.DETAIL_LOC: construction_plan_detail.render_loc(),
    }
    for path, text in texts.items():
        if _write(path, text, write):
            result.files_changed += 1
    return result
