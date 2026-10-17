"""Generate the noble investment scripts: nobles with surplus gold build peasant and labourer buildings.

The engine lets an estate keep one planned project and start it from its own treasury (docs/ai_building_rulebook.md,
section 3). How it picks that plan is not known, and in practice the nobles build land improvements, masons and
granaries, hardly ever the farms, mines and workshops that make goods. This pulse adds that on top: once a month (spread
over the month), a country whose nobles hold more gold than a reserve plus the price of the building looks for

* a building worked by peasants or labourers that makes a market good, researched by the country,
* in a location whose market is short of that good (demand above supply),
* with free hands (unemployed population) and `can_build_building`, no construction under way and no noble investment
  in the last LOCATION_COOLDOWN_DAYS,

and has the nobles build the most profitable one with `construct_estate_building` (the estate pays and owns it).

Profit is worked out per level at the location's market prices, method by method: for every production-method block
the best method the country can run (output x price x (1 + the location's output modifier for that good) - inputs x
prices; methods behind an `allow` are skipped, methods unlocked by an advance need it), summed over the blocks. Wages
are inputs in PP (manual labour), so this is the building's real profit. A building must make money and earn at least
AI_BUILDING_PROFIT_MARGIN_THRESHOLD x its input cost (the AI's own margin); the best one wins. The first version ranked
by the main good's price alone and kept building masons that lost money on dear stone and labour (2026-10-16).

The nobles must hold the reserve plus the price times ESTATE_MAX_PRICE_MULTIPLIER (what an estate pays for its own
builds); both defines are read from pp_defines_adjustments.txt.

Candidates come from the built mod's building types: pop_type peasants or laborers, a main market good (the good of the
one-method Market Sales slot, else the first good priced in ai_construct_weight), not forbidden_for_estates, not
is_special, methods in unique_production_methods. Re-run after building or advance changes:

    uv run --no-project python scripts/generate_noble_investment.py --vanilla "<EU5 install>/game"
"""

from __future__ import annotations

import argparse
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
BUILDING_TYPES = MOD_ROOT / "in_game" / "common" / "building_types"
EFFECTS_PATH = MOD_ROOT / "in_game" / "common" / "scripted_effects" / "pp_noble_investment_effects.txt"
VALUES_PATH = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_noble_investment_values.txt"
DEFINES_PATH = MOD_ROOT / "loading_screen" / "common" / "defines" / "pp_defines_adjustments.txt"
MODIFIER_TYPES = Path("main_menu") / "common" / "modifier_type_definitions"
ADVANCES = Path("in_game") / "common" / "advances"
GOODS = Path("in_game") / "common" / "goods"

POP_TYPES = ("peasants", "laborers")
# Ranking weight per pop type: score = profit x weight. Nobles prefer peasant buildings (user rule, 2026-10-16; at
# default prices the median peasant building makes 1.16 gold per level, the median labourer one 0.64, but labour yards
# and model farms reach 4-14 and won every pick). The profit and margin checks are unchanged.
POP_PRIORITY = {"peasants": 3.0, "laborers": 1.0}
# Farms and other Province Food makers fill the province store first, so for them a province holding less than this
# many months of food counts as a shortage too (the mod's own food urgency line, pp_food_urgency_weight). With the market
# test alone nobles built no farms where the market had a grain surplus (Austria 1384: wheat 47 supply / 41 demand).
FOOD_STORE_MONTHS = 12
# Blueprint footprint classes built without any shortage (user rule 2026-10-17: mines regardless of shortage); profit,
# research, free hands and the location rules still apply.
NO_SHORTAGE_FOOTPRINTS = {"mining"}
# Mines whose blueprint has another footprint (user rule 2026-10-17: gold diggings are mines; the stamp mill is their
# upgrade, which replaces the diggings).
NO_SHORTAGE_BUILDINGS = {"gold_diggings", "gold_stamp_mill"}
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
# Buildings the nobles never invest in, whatever they earn (user rules).
EXCLUDED_BUILDINGS = {
    "market_village": "2026-10-17: nobles must not build market villages (36 of 39 noble ones in a 1550 save were ours)",
}
# Gold the nobles keep for themselves (loans to the crown, their own engine plan, which starts from 50 gold); only gold
# above this plus what the building costs them counts as surplus.
RESERVE_GOLD = 150
# Free hands needed in the location (people; one level of most PP buildings employs 1,000-1,250).
MIN_UNEMPLOYED = 1000
# A good counts as short when market demand > this x supply; 1.0 unless listed (masonry: user rule, 2026-10-16).
SHORTAGE_RATIO = {"masonry": 0.8}
DEFAULT_SHORTAGE_RATIO = 1.0
# Days before the country looks again: after a build, and after a search that found nothing.
BUILD_COOLDOWN_DAYS = 90
IDLE_COOLDOWN_DAYS = 180
# Days a location is left alone after the nobles invested there: construction takes about a year, and the shortage that
# made the building pay lasts until it produces, so without this the same building was stacked 3-4 times (2026-10-16).
LOCATION_COOLDOWN_DAYS = 730
# Method keys that make a method conditional; such methods are left out of the profit (the script cannot test them).
CONDITION_KEYS = ("allow", "potential", "location_allow")
# Block profit before any method was looked at; a block whose methods are all unavailable adds nothing.
NO_METHOD = -1000000
# Debug instrumentation (variables counting the builds per country, location and world). Off in the shipped mod (no test
# hooks in normal play); set True for a measuring run.
DEBUG = False


def define(name: str) -> float:
    """A define from the mod's defines file: estates pay ESTATE_MAX_PRICE_MULTIPLIER x the price of their own builds,
    and the minimum margin is the AI's own AI_BUILDING_PROFIT_MARGIN_THRESHOLD."""
    match = re.search(rf"^\s*{name}\s*=\s*([\d.]+)", DEFINES_PATH.read_text(encoding="utf-8-sig"), re.M)
    if match is None:
        raise SystemExit(f"{name} not found in {DEFINES_PATH.relative_to(ROOT)}")
    return float(match.group(1))


@dataclass(frozen=True)
class Method:
    name: str
    produced: str | None
    output: float
    inputs: tuple[tuple[str, float], ...]
    # Advances that unlock the method (any one will do); empty = always available.
    advances: tuple[str, ...] = ()


@dataclass(frozen=True)
class Candidate:
    building: str
    pop_type: str
    good: str
    # Production-method blocks (each a slot: the building runs one method of each).
    blocks: tuple[tuple[Method, ...], ...] = ()
    # Advances that unlock the building (any one will do); empty = available from the start.
    advances: tuple[str, ...] = ()
    # False for buildings built regardless of shortage (NO_SHORTAGE_FOOTPRINTS).
    needs_shortage: bool = True

    @property
    def makes_province_food(self) -> bool:
        return any(method.produced == "local_food" for block in self.blocks for method in block)


def top_level_blocks(text: str) -> list[tuple[str, str]]:
    """`name = { ... }` blocks at the outermost level of a Paradox script text, comments removed."""
    text = re.sub(r"#[^\n]*", "", text)
    blocks: list[tuple[str, str]] = []
    depth, name, start = 0, None, 0
    for match in re.finditer(r"[{}]|^[ \t]*([\w:]+)\s*=\s*(?=\{)", text, re.M):
        if match.group(1) is not None:
            if depth == 0:
                name, start = match.group(1), match.end()
            continue
        if match.group(0) == "{":
            depth += 1
            continue
        depth -= 1
        if depth == 0 and name:
            blocks.append((name, text[start : match.end()]))
            name = None
    return blocks


def inner(body: str) -> str:
    """A block's text without its own braces."""
    return body.strip()[1:-1]


def load_definitions(folders: list[Path], keep=lambda body: True) -> dict[str, str]:
    """Key -> body after the game's load order: folders in order, files in name order; a plain or REPLACE definition
    replaces, INJECT adds to an existing one."""
    bodies: dict[str, str] = {}
    for folder in folders:
        for path in sorted(folder.glob("*.txt")):
            for name, body in top_level_blocks(path.read_text(encoding="utf-8-sig", errors="replace")):
                key = name.split(":")[-1]
                if name.startswith(("INJECT:", "TRY_INJECT:")):
                    if key in bodies:
                        bodies[key] = bodies[key][:-1] + inner(body) + "}"
                    continue
                if keep(body):
                    bodies[key] = body
    return bodies


def game_folders(game_root: Path, mod_root: Path, sub: Path) -> list[Path]:
    return [game_root / sub, *sorted((game_root / "dlc").glob(f"*/{sub.as_posix()}")), mod_root / sub]


def building_definitions(folder: Path) -> dict[str, str]:
    """Building key -> body as the game loads the mod's building types."""
    return load_definitions([folder], keep=lambda body: "pop_type" in body)


def unlock_map(advances: dict[str, str], key: str) -> dict[str, tuple[str, ...]]:
    """Unlocked thing -> the advances whose `key` (unlock_building, unlock_production_method) names it."""
    unlocks: dict[str, set[str]] = {}
    for advance, body in advances.items():
        for thing in re.findall(rf"\b{key}\s*=\s*(\w+)", body):
            unlocks.setdefault(thing, set()).add(advance)
    return {thing: tuple(sorted(found)) for thing, found in unlocks.items()}


def advance_unlocks(game_root: Path, mod_root: Path, key: str = "unlock_building") -> dict[str, tuple[str, ...]]:
    """Building (or method, with key=unlock_production_method) -> its unlocking advances, vanilla + DLC + mod. In game,
    can_build_building lets the nobles start buildings the country has not researched (2026-10-16 test), so the pulse
    checks has_advance itself."""
    return unlock_map(load_definitions(game_folders(game_root, mod_root, ADVANCES)), key)


def goods_names(game_root: Path, mod_root: Path) -> set[str]:
    return set(load_definitions(game_folders(game_root, mod_root, GOODS)))


def field(body: str, key: str) -> str | None:
    match = re.search(rf"^\s*{key}\s*=\s*(\w+)", body, re.M)
    return match.group(1) if match else None


def main_good(body: str) -> str | None:
    sales = sorted(set(re.findall(r"\w+_market_sales\s*=\s*\{[^{}]*?produced\s*=\s*(\w+)", body, re.S)))
    if len(sales) == 1:
        return sales[0]
    weight = re.search(r"ai_construct_weight\s*=\s*\{(.*)", body, re.S)
    priced = re.findall(r"market_price\(goods:(\w+)\)", weight.group(1)) if weight else []
    return priced[0] if priced else None


def method_blocks(
    body: str, goods: set[str], method_unlocks: dict[str, tuple[str, ...]]
) -> tuple[tuple[Method, ...], ...] | None:
    """The building's unique production-method blocks; None when it uses shared methods (not modelled)."""
    blocks = []
    for name, block in top_level_blocks(inner(body)):
        if name == "possible_production_methods" and inner(block).strip():
            return None
        if name != "unique_production_methods":
            continue
        methods = []
        for method, method_body in top_level_blocks(inner(block)):
            text = inner(method_body)
            if any(re.search(rf"^\s*{key}\s*=", text, re.M) for key in CONDITION_KEYS):
                continue
            produced = field(text, "produced")
            output = re.search(r"^\s*output\s*=\s*([\d.]+)", text, re.M)
            inputs = tuple(
                (good, float(amount))
                for good, amount in re.findall(r"^\s*(\w+)\s*=\s*([\d.]+)", text, re.M)
                if good in goods and float(amount) > 0
            )
            methods.append(
                Method(method, produced, float(output.group(1)) if output else 0.0, inputs, method_unlocks.get(method, ()))
            )
        if methods:
            blocks.append(tuple(methods))
    return tuple(blocks)


def modifier_names(game_roots: list[Path]) -> set[str]:
    names: set[str] = set()
    for root in game_roots:
        for path in sorted((root / MODIFIER_TYPES).glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            names.update(re.findall(r"^(\w+)\s*=\s*\{", text, re.M))
    return names


def blueprint_footprints(folder: Path = BLUEPRINTS) -> dict[str, str]:
    """Building key -> its blueprint's footprint class (top-level `footprint:`)."""
    found = {}
    for path in sorted(folder.glob("*.yml")):
        text = path.read_text(encoding="utf-8-sig")
        footprint = re.search(r"^footprint:\s*(\w+)", text, re.M)
        key = re.search(r"^building:\s*\n(?:\s+.*\n)*?\s+key:\s*(\w+)", text, re.M)
        if footprint and key:
            found[key.group(1)] = footprint.group(1)
    return found


def candidates(
    definitions: dict[str, str],
    goods: set[str],
    unlocks: dict[str, tuple[str, ...]] | None = None,
    method_unlocks: dict[str, tuple[str, ...]] | None = None,
    footprints: dict[str, str] | None = None,
) -> list[Candidate]:
    unlocks, method_unlocks, footprints = unlocks or {}, method_unlocks or {}, footprints or {}
    found = []
    for building, body in sorted(definitions.items()):
        pop_type = field(body, "pop_type")
        good = main_good(body)
        if pop_type not in POP_TYPES or good is None or building in EXCLUDED_BUILDINGS:
            continue
        if field(body, "forbidden_for_estates") == "yes" or field(body, "is_special") == "yes":
            continue
        blocks = method_blocks(body, goods, method_unlocks)
        if not blocks:
            continue
        needs_shortage = footprints.get(building) not in NO_SHORTAGE_FOOTPRINTS and building not in NO_SHORTAGE_BUILDINGS
        found.append(Candidate(building, pop_type, good, blocks, unlocks.get(building, ()), needs_shortage))
    return found


def has_any_advance(advances: tuple[str, ...]) -> str:
    checks = " ".join(f"has_advance = {advance}" for advance in advances)
    return checks if len(advances) == 1 else f"OR = {{ {checks} }}"


def researched(candidate: Candidate) -> str:
    """Country-scope limit lines: the country has an advance that unlocks the building."""
    return f"\t\t\t{has_any_advance(candidate.advances)}\n" if candidate.advances else ""


def price(good: str) -> str:
    return f'"market.market_price(goods:{good})"'


def number(amount: float) -> str:
    return f"{amount:g}"


def method_lines(method: Method, modifiers: set[str], indent: str) -> list[str]:
    """Location scope: the method's revenue and input cost per level into local variables, then keep it when it beats
    the block's best method so far."""
    revenue = "value = 0"
    if method.produced and method.output > 0:
        revenue = f"value = {price(method.produced)} multiply = {number(method.output)}"
        modifier = f"local_{method.produced}_output_modifier"
        if modifier in modifiers:
            revenue += f" multiply = {{ value = 1 add = modifier:{modifier} }}"
    cost = " ".join(
        ["value = 0"] + [f"add = {{ value = {price(good)} multiply = {number(amount)} }}" for good, amount in method.inputs]
    )
    body = [
        f"# {method.name}",
        f"set_local_variable = {{ name = pp_noble_investment_method_revenue value = {{ {revenue} }} }}",
        f"set_local_variable = {{ name = pp_noble_investment_method_cost value = {{ {cost} }} }}",
        "pp_noble_investment_keep_better_method = yes",
    ]
    if not method.advances:
        return [indent + line for line in body]
    return (
        [f"{indent}if = {{", f"{indent}\tlimit = {{ owner = {{ {has_any_advance(method.advances)} }} }}"]
        + [f"{indent}\t{line}" for line in body]
        + [f"{indent}}}"]
    )


def find_block(index: int, candidate: Candidate, modifiers: set[str]) -> str:
    building, good = candidate.building, candidate.good
    indent = "\t" * 3
    profit: list[str] = [
        f"{indent}set_local_variable = {{ name = pp_noble_investment_revenue value = 0 }}",
        f"{indent}set_local_variable = {{ name = pp_noble_investment_cost value = 0 }}",
    ]
    for block in candidate.blocks:
        profit.append(f"{indent}pp_noble_investment_start_block = yes")
        for method in block:
            profit.extend(method_lines(method, modifiers, indent))
        profit.append(f"{indent}pp_noble_investment_add_block = yes")
    priority = number(POP_PRIORITY[candidate.pop_type])
    profit.append(f"{indent}pp_noble_investment_keep_better_location = {{ index = {index} priority = {priority} }}")
    profit_text = "\n".join(profit)
    return f"""\t# {index}: {building} ({candidate.pop_type}, {good})
\tif = {{
\t\tlimit = {{
{researched(candidate)}\t\t\tscope:pp_noble_investment_nobles = {{
\t\t\t\testate_gold >= {{
\t\t\t\t\tvalue = building_type:{building}.building_base_cost_in_gold
\t\t\t\t\tmultiply = pp_noble_investment_price_multiplier
\t\t\t\t\tadd = pp_noble_investment_reserve
\t\t\t\t}}
\t\t\t}}
{country_need(candidate)}
\t\t}}
\t\tevery_owned_location = {{
\t\t\tlimit = {{
\t\t\t\texists = market
{location_need(candidate)}
\t\t\t\tpp_unemployed_population >= pp_noble_investment_min_unemployed
\t\t\t\tnum_civil_constructions < 1
\t\t\t\tNOT = {{ has_variable = pp_noble_investment_recent }}
\t\t\t\tcan_build_building = building_type:{building}
\t\t\t}}
{profit_text}
\t\t}}
\t}}
"""


def country_need(candidate: Candidate) -> str:
    """Country-scope limit line: some market of the country is short of the good (or, for Province Food makers, some
    owned location's province holds less than FOOD_STORE_MONTHS of food)."""
    if not candidate.needs_shortage:
        return "\t\t\t# built regardless of shortage"
    market = f"any_market_present_in_country = {{ {shortage(candidate.good)} }}"
    if not candidate.makes_province_food:
        return f"\t\t\t{market}"
    store = f"any_owned_location = {{ pp_location_stored_months < {FOOD_STORE_MONTHS} }}"
    return f"\t\t\tOR = {{\n\t\t\t\t{market}\n\t\t\t\t{store}\n\t\t\t}}"


def location_need(candidate: Candidate) -> str:
    """Location-scope limit line: its market is short of the good (or its province's food store is low)."""
    if not candidate.needs_shortage:
        return "\t\t\t\t# built regardless of shortage"
    market = f"market = {{ {shortage(candidate.good)} }}"
    if not candidate.makes_province_food:
        return f"\t\t\t\t{market}"
    return f"\t\t\t\tOR = {{\n\t\t\t\t\t{market}\n\t\t\t\t\tpp_location_stored_months < {FOOD_STORE_MONTHS}\n\t\t\t\t}}"


def shortage(good: str) -> str:
    """Market-scope trigger: demand for the good above SHORTAGE_RATIO x supply."""
    ratio = SHORTAGE_RATIO.get(good, DEFAULT_SHORTAGE_RATIO)
    supply = f'"goods_supply_in_market(goods:{good})"'
    if ratio != 1:
        supply = f"{{ value = {supply} multiply = {number(ratio)} }}"
    return f'"goods_demand_in_market(goods:{good})" > {supply}'


def build_branch(index: int, candidate: Candidate, first: bool) -> str:
    keyword = "if" if first else "else_if"
    return (
        f"\t{keyword} = {{\n"
        f"\t\tlimit = {{ local_var:pp_noble_investment_best_index = {index} }}\n"
        f"\t\tconstruct_estate_building = {{ building_type = building_type:{candidate.building} "
        f"estate_type = estate_type:nobles_estate }}\n"
        f"\t}}"
    )


HELPERS = f"""# Location scope helpers for the profit of one building at one location (all in local variables).
# A block starts with no method.
pp_noble_investment_start_block = {{
\tset_local_variable = {{ name = pp_noble_investment_block_profit value = {NO_METHOD} }}
\tset_local_variable = {{ name = pp_noble_investment_block_revenue value = 0 }}
\tset_local_variable = {{ name = pp_noble_investment_block_cost value = 0 }}
}}

# Keep the method just computed when it makes more than the block's best so far.
pp_noble_investment_keep_better_method = {{
\tset_local_variable = {{
\t\tname = pp_noble_investment_method_profit
\t\tvalue = {{ value = local_var:pp_noble_investment_method_revenue subtract = local_var:pp_noble_investment_method_cost }}
\t}}
\tif = {{
\t\tlimit = {{ local_var:pp_noble_investment_method_profit > local_var:pp_noble_investment_block_profit }}
\t\tset_local_variable = {{ name = pp_noble_investment_block_profit value = local_var:pp_noble_investment_method_profit }}
\t\tset_local_variable = {{ name = pp_noble_investment_block_revenue value = local_var:pp_noble_investment_method_revenue }}
\t\tset_local_variable = {{ name = pp_noble_investment_block_cost value = local_var:pp_noble_investment_method_cost }}
\t}}
}}

# Add the block's best method to the building's revenue and input cost.
pp_noble_investment_add_block = {{
\tif = {{
\t\tlimit = {{ local_var:pp_noble_investment_block_profit > {NO_METHOD} }}
\t\tchange_local_variable = {{ name = pp_noble_investment_revenue add = local_var:pp_noble_investment_block_revenue }}
\t\tchange_local_variable = {{ name = pp_noble_investment_cost add = local_var:pp_noble_investment_block_cost }}
\t}}
}}

# The building at this location becomes the best candidate when its score (profit x the pop type's priority) beats the
# best so far (which starts at 0: it must make money) and it earns at least the AI's margin on its inputs.
pp_noble_investment_keep_better_location = {{
\tset_local_variable = {{
\t\tname = pp_noble_investment_profit
\t\tvalue = {{ value = local_var:pp_noble_investment_revenue subtract = local_var:pp_noble_investment_cost }}
\t}}
\tset_local_variable = {{
\t\tname = pp_noble_investment_score
\t\tvalue = {{ value = local_var:pp_noble_investment_profit multiply = $priority$ }}
\t}}
\tif = {{
\t\tlimit = {{
\t\t\tlocal_var:pp_noble_investment_profit > 0
\t\t\tlocal_var:pp_noble_investment_score > local_var:pp_noble_investment_best_score
\t\t\tlocal_var:pp_noble_investment_revenue >= {{
\t\t\t\tvalue = local_var:pp_noble_investment_cost
\t\t\t\tmultiply = pp_noble_investment_min_margin
\t\t\t}}
\t\t}}
\t\tset_local_variable = {{ name = pp_noble_investment_best_score value = local_var:pp_noble_investment_score }}
\t\tset_local_variable = {{ name = pp_noble_investment_best_index value = $index$ }}
\t\tsave_scope_as = pp_noble_investment_location
\t}}
}}
"""

DEBUG_COUNTERS = """\t\tif = {
\t\t\tlimit = { NOT = { has_variable = pp_noble_investment_builds } }
\t\t\tset_variable = { name = pp_noble_investment_builds value = 0 }
\t\t}
\t\tchange_variable = { name = pp_noble_investment_builds add = 1 }
\t\tif = {
\t\t\tlimit = { NOT = { has_global_variable = pp_noble_investment_builds } }
\t\t\tset_global_variable = { name = pp_noble_investment_builds value = 0 }
\t\t}
\t\tchange_global_variable = { name = pp_noble_investment_builds add = 1 }
"""


def render(found: list[Candidate], modifiers: set[str]) -> str:
    out = [
        "﻿# Prosper or Perish - Noble investment: nobles with surplus gold build peasant and labourer buildings for goods",
        "# their markets are short of, the most profitable first.",
        "# Generated by scripts/generate_noble_investment.py from the built mod's building types. Do not edit by hand.",
        f"# {len(found)} candidates.",
        "",
        "# Country scope. Fired by monthly_country_pulse (on_action/pp_noble_investment.txt).",
        "pp_noble_investment_monthly = {",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\tNOT = { has_variable = pp_noble_investment_cooldown }",
        "\t\t\tcountry_has_estate = estate_type:nobles_estate",
        '\t\t\t"estate(estate_type:nobles_estate)" = { estate_gold >= pp_noble_investment_reserve }',
        "\t\t}",
        '\t\t"estate(estate_type:nobles_estate)" = { save_scope_as = pp_noble_investment_nobles }',
        "\t\tset_local_variable = { name = pp_noble_investment_best_score value = 0 }",
        "\t\tset_local_variable = { name = pp_noble_investment_best_index value = 0 }",
        "\t\tpp_noble_investment_find_best = yes",
        "\t\tif = {",
        "\t\t\tlimit = { local_var:pp_noble_investment_best_index > 0 }",
        "\t\t\tscope:pp_noble_investment_location = { pp_noble_investment_build_best = yes }",
        f"\t\t\tset_variable = {{ name = pp_noble_investment_cooldown value = 1 days = {BUILD_COOLDOWN_DAYS} }}",
        "\t\t}",
        "\t\telse = {",
        f"\t\t\tset_variable = {{ name = pp_noble_investment_cooldown value = 1 days = {IDLE_COOLDOWN_DAYS} }}",
        "\t\t}",
        "\t}",
        "}",
        "",
        HELPERS,
        "# Country scope: the most profitable candidate's index (local_var:pp_noble_investment_best_index), its profit per",
        "# level (local_var:pp_noble_investment_best_score) and location (scope:pp_noble_investment_location).",
        "pp_noble_investment_find_best = {",
    ]
    out.extend(find_block(index, candidate, modifiers) for index, candidate in enumerate(found, start=1))
    out += [
        "}",
        "",
        "# Location scope (the chosen location): the nobles start the chosen building there.",
        "pp_noble_investment_build_best = {",
        f"\tset_variable = {{ name = pp_noble_investment_recent value = 1 days = {LOCATION_COOLDOWN_DAYS} }}",
    ]
    out.extend(build_branch(index, candidate, index == 1) for index, candidate in enumerate(found, start=1))
    if DEBUG:
        out += [
            "\tif = {",
            "\t\tlimit = { NOT = { has_variable = pp_noble_investment_builds } }",
            "\t\tset_variable = { name = pp_noble_investment_builds value = 0 }",
            "\t}",
            "\tchange_variable = { name = pp_noble_investment_builds add = 1 }",
            "\towner = {",
            DEBUG_COUNTERS.rstrip("\n"),
            "\t}",
        ]
    out += ["}", ""]
    return "\n".join(out)


def render_values() -> str:
    return "\n".join(
        [
            "﻿# Prosper or Perish - Noble investment thresholds.",
            "# Generated by scripts/generate_noble_investment.py (its constants and pp_defines_adjustments.txt).",
            "# Do not edit by hand.",
            "",
            "# Gold the nobles keep; only gold above this plus what the building costs them is spent.",
            f"pp_noble_investment_reserve = {RESERVE_GOLD}",
            "# Estates pay this times a building's price for their own builds (ESTATE_MAX_PRICE_MULTIPLIER).",
            f"pp_noble_investment_price_multiplier = {define('ESTATE_MAX_PRICE_MULTIPLIER'):g}",
            "# Revenue a building must earn per gold of inputs (AI_BUILDING_PROFIT_MARGIN_THRESHOLD).",
            f"pp_noble_investment_min_margin = {define('AI_BUILDING_PROFIT_MARGIN_THRESHOLD'):g}",
            "# Unemployed people the location needs.",
            f"pp_noble_investment_min_unemployed = {MIN_UNEMPLOYED}",
            "",
        ]
    )


def default_vanilla_root() -> Path | None:
    config = ROOT / "constructor.load_order.toml"
    if not config.exists():
        return None
    raw = tomllib.loads(config.read_text(encoding="utf-8"))["paths"]["vanilla_root"]
    return Path(raw) / "game"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vanilla", type=Path, default=default_vanilla_root(), help="EU5 game/ folder")
    parser.add_argument("--check", action="store_true", help="fail if the generated file is out of date")
    args = parser.parse_args()
    if args.vanilla is None or not (args.vanilla / MODIFIER_TYPES).is_dir():
        raise SystemExit(f"EU5 game folder not found: {args.vanilla} (pass --vanilla <install>/game)")
    modifiers = modifier_names([args.vanilla, MOD_ROOT])
    advances = load_definitions(game_folders(args.vanilla, MOD_ROOT, ADVANCES))
    found = candidates(
        building_definitions(BUILDING_TYPES),
        goods_names(args.vanilla, MOD_ROOT),
        unlock_map(advances, "unlock_building"),
        unlock_map(advances, "unlock_production_method"),
        blueprint_footprints(),
    )
    outputs = {EFFECTS_PATH: render(found, modifiers), VALUES_PATH: render_values()}
    if args.check:
        stale = [p for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
            raise SystemExit(f"out of date: {names}; re-run without --check")
        return
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(found)} candidates -> {EFFECTS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
