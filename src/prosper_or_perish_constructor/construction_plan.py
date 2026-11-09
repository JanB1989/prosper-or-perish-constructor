"""Construction Plan (branch player-construction-manager, 2026-11-06, Jan): player-only construction rules.

The player sets the rules once in the Construction Plan window (two tabs since 2026-11-09, Jan: Global settings and
Location profiles); a monthly pass for countries with ``is_ai = no`` starts the constructions with
``construct_building`` (a normal, paid construction). The AI never runs it. Global settings: the plan on or off, a gold
reserve in gold, and five rule groups (the location profiles and the four below), each with a weight: its part of the
gold above the reserve is its weight over the sum of the weights (0 = off; Jan 2026-11-09), and the four below with
one line each:

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

Location Profiles (``location_profiles.py``) are the only per-location layer: a profile takes from these groups only
what it sets.

Payback is the one money number (Jan: cost and profit alone say nothing across buildings): a level's build cost over
its monthly profit. The cost follows the engine's own formula, calibrated in game on 158 constructions (all within
1 %): base x (1 + increase_per_level_cost x levels) / max(0.5, 1 + build efficiency) x the construction goods' price
factor (each good's price / default clamped to 1 + MIN/MAX_PRICE_IMPACT, averaged by amount; vanilla
default_construct_building when a building names none). The same cost keeps the gold reserve: no construction starts
that would take the treasury below it.

The engine (monthly pass, window, settings) is hand-written in the mod (``pp_construction_plan*.txt``,
``pp_construction_plan.gui``). This module writes the parts that follow the mod's buildings, goods and the
``[construction_plan]`` settings, so they stay in step with every rebalance:

* ``scripted_effects/pp_construction_plan_generated.txt``: the farm, logistics, improvement and business pickers and
  the building cost data lookup;
* ``script_values/pp_construction_plan_generated.txt``: the defaults, the rule groups' weights and parts, farm and
  business profit estimates, the construction goods price factors and the baseline rules' blacklists;
* ``scripted_triggers/pp_construction_plan_generated.txt``: the construction goods and food queue checks;
* ``gui/pp_construction_plan_weights.gui``: the weight bar of each rule group.

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
# the rule groups with a weight (their order in the window); a weight runs 0 (off) .. WEIGHT_STEPS
GROUPS = ("profiles", "food", "logistics", "improve", "business")
# the rule groups' construction codes (pp_cplan_construct_scoped's why; the pass keeps its numbers per code)
GROUP_WHY = {"food": 101, "logistics": 102, "business": 103, "profiles": 105, "improve": 106}
HISTORY_MONTHS = 12  # months the window's chart shows
WEIGHT_STEPS = 10
SEGMENT = 14  # px of one weight step in the bar
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
        profile_categories=tuple(whole.get(PROFILE_CATEGORIES_KEY, {}).get("categories", ())),
        weights=_weights(data["weights"]),
    )


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


def render_weight_values(config: Config) -> str:
    """The rule groups' weights (Jan 2026-11-09): a group's part of the gold above the reserve = its weight over the sum
    of the weights that count (0 = the group is off; the location profiles count only while a location has one)."""
    parts = ["\n# ---- Rule group weights (country scope; 0 = off) ----\n\n"]
    for group, default in config.weights:
        parts.append(_default_value(f"pp_cplan_{group}_w", f"pp_cplan_w_{group}", default,
                                    f"Country scope: the {group} group's weight, 0..{WEIGHT_STEPS}."))
    parts.append(
        "# Country scope: the location profiles' weight counts only while a location of the country has a profile.\n"
        "pp_cplan_profiles_cw = {\n\tvalue = pp_cplan_profiles_w\n\tmultiply = pp_lprof_group_n\n}\n"
        "# Country scope: the sum of the weights that count.\npp_cplan_w_total = {\n\tvalue = pp_cplan_profiles_cw\n"
        + "".join(f"\tadd = pp_cplan_{group}_w\n" for group in GROUPS if group != "profiles")
        + "}\n"
    )
    for group in GROUPS:
        weight = "pp_cplan_profiles_cw" if group == "profiles" else f"pp_cplan_{group}_w"
        parts.append(
            f"# Country scope: the {group} group's part of the budget, in % (the window) and in gold (the pass).\n"
            f"pp_cplan_part_{group} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ pp_cplan_w_total > 0 }}\n"
            f"\t\tvalue = {weight}\n\t\tmultiply = 100\n\t\tdivide = pp_cplan_w_total\n\t}}\n}}\n"
            f"pp_cplan_share_{group} = {{\n\tvalue = 0\n\tif = {{\n\t\tlimit = {{ pp_cplan_w_total > 0 }}\n"
            f"\t\tvalue = pp_cplan_pot_n\n\t\tmultiply = {weight}\n\t\tdivide = pp_cplan_w_total\n\t}}\n}}\n"
        )
    return "".join(parts)


def render_weight_gui() -> str:
    """One weight bar per rule group: - and + (vanilla's slider buttons), a gold bar of WEIGHT_STEPS steps whose every
    step sets the weight when clicked, and the group's part in %. A real slider cannot be used: its value only reaches
    the engine's own functions, never a script."""

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
            "\t}\n\n"
        )
    out.append("}\n")
    return "".join(out)


# ---- The window's detail panes (Jan 2026-11-09: "how much investment is missing, what was built and why") ----
# Per rule group (by its construction code, GROUP_WHY) the pass keeps on the country, until the next pass: that it ran,
# the gold it could spend, the gold it spent, the constructions it started, the gold and the number of the constructions
# it wanted that waited for gold, its situation (SITUATION), and the last HISTORY_MONTHS passes' gold wanted and spent.
# The rules never read any of it.
GROUP_NUMBERS = {"had": "dhad", "spent": "dspent", "started": "dn", "wait": "dwait", "waitn": "dwn"}
SITUATION: dict[str, tuple[tuple[str, int], ...]] = {
    # name, start value (+ 100; a running minimum starts high)
    "food": (("provinces", 100), ("famine", 100), ("hungry", 100), ("granary", 100), ("grange", 100)),
    "logistics": (("below", 100), ("lowest", 1099)),
    "improve": (("over", 100), ("fullest", 100)),
    "business": (("sites", 100), ("best", 1099)),
    "profiles": (("locs", 100), *((f"st{n}", 100) for n in range(1, 10))),
}


def render_stats_effects() -> str:
    """The pass's bookkeeping for the detail panes: the numbers start afresh each pass (pp_cplan_stats_reset), the
    pass's gold wanted and spent go into the history at its end (pp_cplan_history_push: the oldest month drops out),
    and switching the plan on clears the history (pp_cplan_history_clear)."""
    reset, push, clear = [], [], []
    for group in GROUPS:
        why = GROUP_WHY[group]
        reset.append(f"\t# {group}\n\tremove_variable = pp_cplan_dran_{why}\n\tclear_variable_list = pp_cplan_log_{why}\n")
        reset += [f"\tset_variable = {{ name = pp_cplan_{var}_{why} value = 100 }}\n" for var in GROUP_NUMBERS.values()]
        reset += [f"\tset_variable = {{ name = pp_cplan_ds_{group}_{name} value = {start} }}\n"
                  for name, start in SITUATION[group]]
        push.append(f"\t# {group}\n")
        for kind in ("hn", "hs"):
            push += [f"\tpp_cplan_copy_num = {{ from = pp_cplan_{kind}_{why}_{k - 1} to = pp_cplan_{kind}_{why}_{k} }}\n"
                     for k in range(HISTORY_MONTHS, 1, -1)]
            clear += [f"\tremove_variable = pp_cplan_{kind}_{why}_{k}\n" for k in range(1, HISTORY_MONTHS + 1)]
        push.append(f"\tset_variable = {{ name = pp_cplan_hn_{why}_1 value = {{ value = var:pp_cplan_dspent_{why} "
                    f"add = var:pp_cplan_dwait_{why} subtract = 100 }} }}\n")
        push.append(f"\tset_variable = {{ name = pp_cplan_hs_{why}_1 value = var:pp_cplan_dspent_{why} }}\n")
    return (
        "\n# ---- The window's detail panes (rules never read these) ----\n\n"
        "# Country scope, at the start of pp_cplan_run: every rule group's numbers start afresh (+ 100; the running\n"
        "# minimums high).\npp_cplan_stats_reset = {\n" + "".join(reset) + "}\n\n"
        f"# Country scope, at the end of pp_cplan_run: the pass's gold wanted (spent + waiting for gold) and spent per rule\n"
        f"# group become month 1 of the history, the older months move up one, month {HISTORY_MONTHS} drops out.\n"
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

    parts = ["\n# ---- The window's detail panes (country scope; pp_cplan_stats_reset, pp_cplan_history_push) ----\n"]
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


def _can_build(name: str, costs: dict[str, BuildingCost]) -> str:
    """The vanilla can-build check, the construction goods in this market, and no level of it under construction
    here (the engine stalls a construction whose goods the market lacks; tested 2026-11-06, Edinburgh masonry)."""
    demand = costs.get(name, BuildingCost(0.0, DEFAULT_DEMAND, "std")).demand
    return (f"location_and_owner_can_build = {{ building_type = {name} }} pp_cplan_goods_here_{demand} = yes "
            f"NOT = {{ any_buildings_in_location = {{ building_type = building_type:{name} building_levels_under_construction > 0 }} }}")


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
        "# among those that can be built; a standing older tier is replaced once its successor is researched.\n"
        "pp_cplan_try_improve_here = {\n"
        "\tset_variable = { name = pp_cplan_best value = 0.001 }\n"
        "\tset_variable = { name = pp_cplan_pick value = 100 }\n"
    ]
    for number, (key, land) in enumerate(improvements, 101):
        ipl = costs.get(key, BuildingCost(0.0, DEFAULT_DEMAND, "std")).ipl
        values.append(
            f"pp_cplan_imp_{key} = {{\n\tvalue = {_num(land * 1000)}\n\tdivide = {{\n"
            f"\t\tvalue = \"location_building_level(building_type:{key})\"\n\t\tmultiply = {_num(ipl)}\n\t\tadd = 1\n"
            f"\t\tmultiply = building_type:{key}.building_base_cost_in_gold\n\t\tmin = 1\n\t}}\n}}\n"
        )
        effects.append(
            f"\tif = {{\n\t\tlimit = {{ {_can_build(key, costs)} pp_cplan_imp_{key} > var:pp_cplan_best }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_best value = pp_cplan_imp_{key} }}\n"
            f"\t\tset_variable = {{ name = pp_cplan_pick value = {number} }}\n\t}}\n"
        )
    for number, (key, _land) in enumerate(improvements, 101):
        effects.append(
            f"\tif = {{\n\t\tlimit = {{ var:pp_cplan_pick > {number - 0.5:g} var:pp_cplan_pick < {number + 0.5:g} }}\n"
            f"\t\tpp_cplan_construct = {{ type = {key} why = {WHY_IMPROVE} }}\n\t}}\n"
        )
    effects.append("\tremove_variable = pp_cplan_best\n\tremove_variable = pp_cplan_pick\n}\n")
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
            f"\t{'if' if position == 0 else 'else_if'} = {{\n\t\tlimit = {{ {can(building)} }}\n"
            f"\t\tbuilding_type:{building} = {{ save_scope_as = pp_cplan_btype }}\n"
            "\t\tpp_cplan_btype_data = yes\n"
            "\t\tif = {\n\t\t\tlimit = {\n\t\t\t\tOR = {\n"
            "\t\t\t\t\tAND = {\n\t\t\t\t\t\tpp_cplan_bt_levels > 0.5\n"
            "\t\t\t\t\t\tpp_cplan_est_payback_years <= pp_cplan_yard_payback\n\t\t\t\t\t}\n"
            "\t\t\t\t\tAND = {\n\t\t\t\t\t\tpp_cplan_bt_levels < 0.5\n\t\t\t\t\t\tpp_cplan_victuals_price_ratio >= 1\n\t\t\t\t\t}\n"
            "\t\t\t\t}\n\t\t\t}\n"
            f"\t\t\tpp_cplan_construct_food = {{ type = {building} }}\n\t\t}}\n\t}}\n"
        )
    parts.append("}\n")

    # --- capital food buildings
    for name, buildings, comment in (
        ("pp_cplan_try_kitchen_here", config.kitchens, "a kitchen level (the province's Cookshop budget is its max level)"),
        ("pp_cplan_try_tavern_here", config.taverns, "a Tavern level"),
        ("pp_cplan_try_granary_here", config.granaries, "a Granary level"),
        ("pp_cplan_try_grange_here", config.granges, "a Grange level"),
    ):
        parts.append(f"\n# Location scope (the province capital): {comment}, first that can be built.\n{name} = {{\n")
        for position, building in enumerate(buildings):
            keyword = "if" if position == 0 else "else_if"
            parts.append(
                f"\t{keyword} = {{\n\t\tlimit = {{ {can(building)} }}\n"
                f"\t\tpp_cplan_construct_food = {{ type = {building} }}\n\t}}\n"
            )
        parts.append("}\n")

    # --- logistics
    parts.append("\n# Location scope: the first logistics building that can be built here ([construction_plan] logistics_order).\n"
                 "pp_cplan_try_logistics_here = {\n")
    for position, building in enumerate(config.logistics_order):
        keyword = "if" if position == 0 else "else_if"
        parts.append(
            f"\t{keyword} = {{\n\t\tlimit = {{ {can(building)} }}\n"
            f"\t\tpp_cplan_construct = {{ type = {building} why = {WHY_LOGISTICS} }}\n\t}}\n"
        )
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
        "# reaches the owner's line (pp_cplan_business_min_roi = 100 / years), as pp_cplan_bz_pick (a building type) and\n"
        "# pp_cplan_bz_roi (its return, %); neither where none does. A candidate: the country can build it, so can this\n"
        "# location (max level, allow, potential), a level finds its workers here (pp_cplan_staff), the market holds its\n"
        "# construction goods, no level of it here is closed (the player or the game's Close and Open automation found\n"
        "# it does not pay), and a profile here leaves its good and building category to the plan.\n"
        "pp_cplan_business_pick = {\n"
        "\tpp_cplan_business_harvest = yes\n"
        "\tsave_temporary_scope_value_as = { name = pp_cplan_free_peasants value = pp_cplan_free_peasants_here }\n"
        "\tremove_variable = pp_cplan_bz_pick\n"
        "\tset_variable = { name = pp_cplan_bz_roi value = scope:pp_cplan_country.pp_cplan_business_min_roi }\n"
    )
    for name in names:
        cost = costs.get(name, BuildingCost(0.0, DEFAULT_DEMAND, "std"))
        profile = f"\t\t\tNOT = {{ pp_lprof_has_good = {{ g = {businesses[name]} }} }}\n"
        if categories.get(name) in profile_categories:
            profile += f"\t\t\tNOT = {{ pp_lprof_has_category = {{ c = {categories[name]} }} }}\n"
        workers = staff_check((staff or {}).get(name))
        effects.append(
            "\tif = {\n\t\tlimit = {\n"
            f"\t\t\tscope:pp_cplan_country = {{ has_variable = pp_cplan_bz_{name} }}\n"
            + (f"\t\t\t{workers}\n" if workers else "")
            + f"\t\t\tcan_build_building = building_type:{name}\n"
            + profile
            + f"\t\t\tpp_cplan_goods_here_{cost.demand} = yes\n"
            f"\t\t\tNOT = {{ any_buildings_in_location = {{ building_type = building_type:{name} building_level > 0 is_opened = no }} }}\n"
            "\t\t}\n"
            f"\t\tbuilding_type:{name} = {{ save_scope_as = pp_cplan_btype }}\n"
            f"\t\t{_cost_data(cost)}\n"
            f"\t\tsave_temporary_scope_value_as = {{ name = pp_cplan_r value = pp_cplan_bz_roi_{name} }}\n"
            "\t\tif = {\n\t\t\tlimit = { scope:pp_cplan_r > var:pp_cplan_bz_roi }\n"
            "\t\t\tset_variable = { name = pp_cplan_bz_roi value = scope:pp_cplan_r }\n"
            f"\t\t\tset_variable = {{ name = pp_cplan_bz_pick value = building_type:{name} }}\n\t\t}}\n\t}}\n"
        )
    effects.append("\tif = {\n\t\tlimit = { NOT = { has_variable = pp_cplan_bz_pick } }\n\t\tremove_variable = pp_cplan_bz_roi\n\t}\n}\n")
    return "".join(values), "".join(effects)


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

    # businesses (Jan 2026-11-09): every producer of a market good, without the other rules' own buildings
    own = set(config.kitchens) | set(config.taverns) | set(config.granaries) | set(config.granges) | set(config.yards)
    own |= set(config.logistics_order) | set(result.improvements)
    result.businesses = {building: good for building, good in sorted(short.main_good.items())
                         if good not in config.hidden_goods and building not in own}
    categories = {name: database[name][0].get("category", "") for name in result.businesses if name in database}
    result.staff = staffing(database, script_value_numbers(mod_root, vanilla_root))
    business_values, business_effects = render_business(
        result.businesses, built_recipes(database, list(result.businesses)), costs, harvest_outputs(mod_root),
        categories, config.profile_categories, result.staff)

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
        + improve_values + business_values + render_stats_values(),
        mod_root / EFFECTS: render_effects(config, food_lines, costs) + improve_effects + business_effects
        + render_stats_effects(),
        # the hunger steps wait for what they start (staple food makers, Taverns); kitchens are built anyway and must
        # not hold farms back for the year a Cookshop takes (seen in game 2026-11-08)
        mod_root / TRIGGERS: render_triggers(demands, food_buildings + list(config.taverns),
                                             config.construction_goods_months),
        mod_root / WEIGHT_GUI: render_weight_gui(),
        # the window's detail panes (Jan 2026-11-09): a cog per rule group, the numbers render_stats_values gives
        mod_root / construction_plan_detail.DETAIL_GUI: construction_plan_detail.render_gui(),
        mod_root / construction_plan_detail.DETAIL_LOC: construction_plan_detail.render_loc(),
    }
    for path, text in texts.items():
        if _write(path, text, write):
            result.files_changed += 1
    return result
