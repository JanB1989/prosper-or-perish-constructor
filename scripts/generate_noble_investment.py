"""Generate the noble investment scripts: nobles with surplus gold build peasant and labourer buildings.

The engine lets an estate keep one planned project and start it from its own treasury (docs/ai_building_rulebook.md,
section 3). How it picks that plan is not known, and in practice the nobles build land improvements, masons and
granaries, hardly ever the farms, mines and workshops that make goods. This pulse adds that on top: once a month (spread
over the month), a country whose nobles hold more gold than a reserve plus the price of the building looks for

* a building worked by peasants or labourers that makes a market good,
* in a location whose market is short of that good (demand above supply),
* with free hands (unemployed population) and `can_build_building`,

and has the nobles build the most profitable one with `construct_estate_building` (the estate pays and owns it).

Profit is ranked the way the AI's own gate leg judges it (AGENTS.md "Production Gate"): the main good's market price
over its default price, times (1 + the location's output modifier for that good) when the game has one. PP methods are
balanced near break-even at default prices, so this margin orders buildings by profit across goods. A candidate must
beat the AI's own threshold (AI_BUILDING_PROFIT_MARGIN_THRESHOLD), and the nobles must hold the reserve plus the price
times ESTATE_MAX_PRICE_MULTIPLIER (what an estate pays for its own builds); both defines are read from
pp_defines_adjustments.txt.

Candidates come from the built mod's building types: pop_type peasants or laborers, a main market good (the good of the
one-method Market Sales slot, else the first good priced in ai_construct_weight), not forbidden_for_estates, not
is_special. Re-run after building changes:

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

POP_TYPES = ("peasants", "laborers")
# Gold the nobles keep for themselves (loans to the crown, their own engine plan, which starts from 50 gold); only gold
# above this plus what the building costs them counts as surplus.
RESERVE_GOLD = 150
# Free hands needed in the location (people; one level of most PP buildings employs 1,000-1,250).
MIN_UNEMPLOYED = 1000
# Days before the country looks again: after a build, and after a search that found nothing.
BUILD_COOLDOWN_DAYS = 90
IDLE_COOLDOWN_DAYS = 180
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
class Candidate:
    building: str
    pop_type: str
    good: str
    output_modifier: str | None


def top_level_blocks(text: str) -> list[tuple[str, str]]:
    """Top-level `name = { ... }` blocks of a Paradox script file, comments removed."""
    text = re.sub(r"#[^\n]*", "", text)
    blocks: list[tuple[str, str]] = []
    depth, name, start = 0, None, 0
    for match in re.finditer(r"[{}]|^([\w:]+)\s*=\s*(?=\{)", text, re.M):
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


def building_definitions(folder: Path) -> dict[str, str]:
    """Building key -> body as the game loads it: files in name order, later definitions win."""
    definitions: dict[str, str] = {}
    for path in sorted(folder.glob("*.txt")):
        for name, body in top_level_blocks(path.read_text(encoding="utf-8-sig", errors="replace")):
            key = name.split(":")[-1]
            if name.startswith(("INJECT:", "TRY_INJECT:")):
                if key in definitions:
                    definitions[key] += body
                continue
            if "pop_type" in body:
                definitions[key] = body
    return definitions


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


def modifier_names(game_roots: list[Path]) -> set[str]:
    names: set[str] = set()
    for root in game_roots:
        for path in sorted((root / MODIFIER_TYPES).glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            names.update(re.findall(r"^(\w+)\s*=\s*\{", text, re.M))
    return names


def candidates(definitions: dict[str, str], modifiers: set[str]) -> list[Candidate]:
    found = []
    for building, body in sorted(definitions.items()):
        pop_type = field(body, "pop_type")
        good = main_good(body)
        if pop_type not in POP_TYPES or good is None:
            continue
        if field(body, "forbidden_for_estates") == "yes" or field(body, "is_special") == "yes":
            continue
        modifier = f"local_{good}_output_modifier"
        found.append(Candidate(building, pop_type, good, modifier if modifier in modifiers else None))
    return found


def margin(candidate: Candidate, indent: str) -> str:
    """Script value (location scope): the main good's price over its default price, with the local output bonus."""
    good = candidate.good
    lines = [
        f'{indent}value = "market.market_price(goods:{good})"',
        f'{indent}divide = "default_price(goods:{good})"',
    ]
    if candidate.output_modifier:
        lines.append(f"{indent}multiply = {{ value = 1 add = modifier:{candidate.output_modifier} }}")
    return "\n".join(lines)


def shortage(good: str) -> str:
    return f'"goods_demand_in_market(goods:{good})" > "goods_supply_in_market(goods:{good})"'


def find_block(index: int, candidate: Candidate) -> str:
    building, good = candidate.building, candidate.good
    return f"""\t# {index}: {building} ({candidate.pop_type}, {good})
\tif = {{
\t\tlimit = {{
\t\t\tscope:pp_noble_investment_nobles = {{
\t\t\t\testate_gold >= {{
\t\t\t\t\tvalue = building_type:{building}.building_base_cost_in_gold
\t\t\t\t\tmultiply = pp_noble_investment_price_multiplier
\t\t\t\t\tadd = pp_noble_investment_reserve
\t\t\t\t}}
\t\t\t}}
\t\t\tany_market_present_in_country = {{ {shortage(good)} }}
\t\t}}
\t\tordered_owned_location = {{
\t\t\tlimit = {{
\t\t\t\texists = market
\t\t\t\tmarket = {{ {shortage(good)} }}
\t\t\t\tpp_unemployed_population >= pp_noble_investment_min_unemployed
\t\t\t\tcan_build_building = building_type:{building}
\t\t\t}}
\t\t\torder_by = {{
{margin(candidate, chr(9) * 4)}
\t\t\t}}
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\tset_local_variable = {{
\t\t\t\tname = pp_noble_investment_score
\t\t\t\tvalue = {{
{margin(candidate, chr(9) * 5)}
\t\t\t\t}}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ local_var:pp_noble_investment_score > local_var:pp_noble_investment_best_score }}
\t\t\t\tset_local_variable = {{ name = pp_noble_investment_best_score value = local_var:pp_noble_investment_score }}
\t\t\t\tset_local_variable = {{ name = pp_noble_investment_best_index value = {index} }}
\t\t\t\tsave_scope_as = pp_noble_investment_location
\t\t\t}}
\t\t}}
\t}}
"""


def build_branch(index: int, candidate: Candidate, first: bool) -> str:
    keyword = "if" if first else "else_if"
    return (
        f"\t{keyword} = {{\n"
        f"\t\tlimit = {{ local_var:pp_noble_investment_best_index = {index} }}\n"
        f"\t\tconstruct_estate_building = {{ building_type = building_type:{candidate.building} "
        f"estate_type = estate_type:nobles_estate }}\n"
        f"\t}}"
    )


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


def render(found: list[Candidate]) -> str:
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
        "\t\tset_local_variable = { name = pp_noble_investment_best_score value = pp_noble_investment_min_margin }",
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
        "# Country scope: the best candidate's index (local_var:pp_noble_investment_best_index), margin and location",
        "# (scope:pp_noble_investment_location). A candidate must beat the current best, which starts at the minimum margin.",
        "pp_noble_investment_find_best = {",
    ]
    out.extend(find_block(index, candidate) for index, candidate in enumerate(found, start=1))
    out += [
        "}",
        "",
        "# Location scope (the chosen location): the nobles start the chosen building there.",
        "pp_noble_investment_build_best = {",
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
            "# Main good price x (1 + local output modifier) over its default price a building must beat",
            "# (AI_BUILDING_PROFIT_MARGIN_THRESHOLD).",
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
    found = candidates(building_definitions(BUILDING_TYPES), modifiers)
    outputs = {EFFECTS_PATH: render(found), VALUES_PATH: render_values()}
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
