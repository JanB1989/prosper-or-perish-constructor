"""Stored-food effect carriers (EU5 1.4): province modifiers scaled by the province's stored food.

EU5 1.4 deleted the engine-scaled static modifier ``positive_province_food_growth``. Its per-stored-year effects,
growth included, come back through these carriers; the engine's own storage growth term is off
(``NPop.FOOD_STORAGE_POP_GROWTH = 0`` in pp_defines_adjustments.txt), so growth from stored food is the
``local_population_growth`` of the Stored Food modifier:

- ``pp_stored_food`` ("Stored Food") carries the payload of one stored year (``[stored_food.per_year]`` in
  constructor.toml: growth, prosperity, migration, devastation recovery); it is applied with ``size`` = stored years
  (stored months / 12, 0 to the 24-month cap of ``pp_stored_food_province_months``).
- the store lever (2026-10-02): ``pp_low_stores`` ("Low Stores", ``[stored_food.low]``) is applied with ``size`` =
  the years the store is short of ``pivot_months``, ``pp_full_stores`` ("Full Stores", ``[stored_food.full]``) with
  the years above it. They move the Province Food output (worth more while the store is low, less while it is full),
  the staple output (``staple_output`` = one line per good a Provisioning method buys) and the Grange's Surplus
  Sales. At the pivot neither is applied, so no country base value belongs to the lever.
  Every payload is per year because per-month values would need six decimals, which EU5 1.4 rejects.
- the province-scope scripted effect ``pp_refresh_stored_food``: works out the province's consumption once (the
  location loop is the expensive part), the stored months from it, and re-applies the modifiers only when the months
  moved by more than ``deadband_months`` since the last refresh or the store emptied. The applied months are kept in
  a province variable (+100 offset: a variable at 0 counts as unset; locals use the same offset); a province that
  was never refreshed gets a value below every store, so its first refresh always applies.
- old saves: the whole-month tier version (2026-10-01) left one ``pp_stored_food_tier_<t>`` modifier and its
  variables on each province; their names stay defined without effects (``LEGACY_TIERS``) so saves load, and the
  first refresh removes them. The single-modifier version kept its months in ``pp_stored_food_size``; the first
  refresh drops it, which also applies Low / Full Stores to those provinces.
- display helpers (view only, location scope): ``pp_stored_food_years`` (the stored years the modifier is applied at)
  and ``pp_province_food_storage_growth`` (its growth); the location view's Stored Food chip scales each effect by
  the years (location_status.py). Low Stores and Full Stores show in the province modifier list beside it.

The refresh runs from ``in_game/common/on_action/pp_stored_food.txt`` (monthly country pulse, staggered over the month)
and once at game start (pp_game_start.txt). ``ppc build`` / ``ppc sync`` write the generated files in their finalize
step and delete the tier version's files; ``check`` reports files that differ from the configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
import tomllib

CONFIG_SECTION = "stored_food"
MODIFIER = "pp_stored_food"
LOW_MODIFIER = "pp_low_stores"
FULL_MODIFIER = "pp_full_stores"
STAPLE_KEY = "staple_output"   # in [stored_food.low] / [stored_food.full]: one line per provisioned good
REFRESH_EFFECT = "pp_refresh_stored_food"
MONTHS_VALUE = "pp_stored_food_province_months"
CONSUMPTION_VALUE = "pp_stored_food_province_consumption"
SIZE_VARIABLE = "pp_stored_food_months"         # applied months + 100
OLD_SIZE_VARIABLE = "pp_stored_food_size"       # the single-modifier version's variable (2026-10-01), dropped once
UNSET_VALUE = 50                                # "never refreshed": below every store (0 months = 100)
CONSUMPTION_LOCAL = "pp_stored_food_consumption"
TARGET_LOCAL = "pp_stored_food_target"
CHANGE_LOCAL = "pp_stored_food_change"
VARIABLE_OFFSET = 100
DECIMALS = 5   # EU5 1.4 rejects six-decimal static-modifier values ("Badly read script value")
MONTHS_PER_YEAR = 12
CAP_MONTHS = "{ value = define:NEconomy|GROWTH_FROM_FOOD_MULTIPLIER_MAX multiply = 12 }"
EPSILON = 0.00001   # the engine's fixed-point step

# The whole-month tier version (2026-10-01): modifier names and variables old saves still carry.
LEGACY_TIERS = 24
LEGACY_PREFIX = "pp_stored_food_tier_"
LEGACY_VARIABLES = ("pp_stored_food_tier", "pp_stored_food_tier_next", "pp_stored_food_tier_change")

STATIC_MODIFIERS = Path("in_game/common/static_modifiers/pp_stored_food.txt")
SCRIPT_VALUES = Path("in_game/common/script_values/pp_stored_food.txt")
SCRIPTED_EFFECTS = Path("in_game/common/scripted_effects/pp_stored_food.txt")
LOCALIZATION = Path("main_menu/localization/english/pp_stored_food_l_english.yml")
GENERATED_FILES = (STATIC_MODIFIERS, SCRIPT_VALUES, SCRIPTED_EFFECTS, LOCALIZATION)
LEGACY_FILES = (
    Path("in_game/common/static_modifiers/pp_stored_food_tiers.txt"),
    Path("in_game/common/script_values/pp_stored_food_tiers.txt"),
    Path("in_game/common/scripted_effects/pp_stored_food_tiers.txt"),
    Path("in_game/common/customizable_localization/pp_stored_food_tiers.txt"),
    Path("main_menu/localization/english/pp_stored_food_tiers_l_english.yml"),
)

GROWTH_KEY = "local_population_growth"
GROWTH_VALUE = "pp_province_food_storage_growth"
YEARS_VALUE = "pp_stored_food_years"

HEADER = "# Generated by ppc build from [stored_food] in constructor.toml (stored_food.py); do not edit by hand.\n"

# Player-facing plain text (generated static-modifier descriptions take no concept links); no balance numbers, the
# modifier tooltip shows them.
DESCRIPTION = (
    "The food this province holds in storage, counted in its own consumption. Full stores let its people grow faster, "
    "and they help the province recover from devastation, draw settlers and prosper. The effects grow with the store "
    "up to a cap and follow it from month to month."
)
LOW_NAME = "Low Stores"
LOW_DESCRIPTION = (
    "The province holds less food than a year of its own needs. Food is worth more here, so farms, cookshops and "
    "taverns cook and serve more of it, and the grange finds little surplus to sell. The effects grow as the store "
    "empties."
)
FULL_NAME = "Full Stores"
FULL_DESCRIPTION = (
    "The province holds more food than a year of its own needs. Food is worth less here, so cooking and serving slow "
    "down; the land sends more of its staples to market and the grange sells the surplus. The effects grow as the "
    "store fills, up to a cap."
)
LEGACY_DESCRIPTION = "Replaced by the Stored Food modifier at the province's next monthly update."


@dataclass(frozen=True)
class StoredFoodConfig:
    deadband_months: float
    per_year: tuple[tuple[str, float], ...]
    pivot_months: float = 12.0
    low: tuple[tuple[str, float], ...] = ()    # Low Stores: per year short of the pivot, staple lines expanded
    full: tuple[tuple[str, float], ...] = ()   # Full Stores: per year above the pivot, staple lines expanded


@dataclass(frozen=True)
class StoredFoodResult:
    files_changed: int
    changed: tuple[Path, ...]


def load_config(project: Path) -> StoredFoodConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION)
    if not isinstance(section, dict) or not isinstance(section.get("per_year"), dict):
        raise ValueError(f"{project}: [{CONFIG_SECTION}] with a [{CONFIG_SECTION}.per_year] table is required")
    deadband = float(section.get("deadband_months", 0.05))
    if not 0 <= deadband < 1:
        raise ValueError(f"{project}: [{CONFIG_SECTION}] deadband_months must be in [0, 1)")
    per_year = tuple((str(key), float(value)) for key, value in section["per_year"].items())
    if not per_year:
        raise ValueError(f"{project}: [{CONFIG_SECTION}.per_year] is empty")
    pivot = float(section.get("pivot_months", 12))
    if not 0 < pivot < 24:
        raise ValueError(f"{project}: [{CONFIG_SECTION}] pivot_months must be between 0 and 24")
    return StoredFoodConfig(
        deadband_months=deadband,
        per_year=per_year,
        pivot_months=pivot,
        low=_lever_payload(section.get("low", {}), f"{project}: [{CONFIG_SECTION}.low]"),
        full=_lever_payload(section.get("full", {}), f"{project}: [{CONFIG_SECTION}.full]"),
    )


def staple_goods() -> tuple[str, ...]:
    """The goods the Provisioning methods buy back (provisioning.py), each once, in building order."""
    from prosper_or_perish_constructor import provisioning

    return tuple(dict.fromkeys(provisioning.PROVISIONED_GOOD_BY_BUILDING.values()))


def _lever_payload(table: object, where: str) -> tuple[tuple[str, float], ...]:
    """A Low / Full Stores table as modifier lines: ``staple_output`` becomes one line per provisioned good (none at 0)."""
    if not isinstance(table, dict):
        raise ValueError(f"{where} must be a table")
    lines: list[tuple[str, float]] = []
    for key, value in table.items():
        if str(key) == STAPLE_KEY:
            if float(value) != 0:
                lines += [(f"local_{good}_output_modifier", float(value)) for good in staple_goods()]
        else:
            lines.append((str(key), float(value)))
    return tuple(lines)


def _rounded(lines: tuple[tuple[str, float], ...]) -> dict[str, float]:
    quantum = Decimal(1).scaleb(-DECIMALS)
    return {key: float(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP)) for key, value in lines}


def payload(config: StoredFoodConfig) -> dict[str, float]:
    """The Stored Food modifier's effects (one stored year), rounded to five decimals."""
    return _rounded(config.per_year)


def low_payload(config: StoredFoodConfig) -> dict[str, float]:
    """The Low Stores modifier's effects (one year short of the pivot), rounded to five decimals."""
    return _rounded(config.low)


def full_payload(config: StoredFoodConfig) -> dict[str, float]:
    """The Full Stores modifier's effects (one year above the pivot), rounded to five decimals."""
    return _rounded(config.full)


def format_value(value: float) -> str:
    text = f"{value:.{DECIMALS}f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return "0.0" if text in {"-0.0", "0.0"} else text


def legacy_name(tier: int) -> str:
    return f"{LEGACY_PREFIX}{tier}"


def growth_per_year(config: StoredFoodConfig) -> float:
    """The payload's population growth per stored year (0 when the payload has none)."""
    return dict(config.per_year).get(GROWTH_KEY, 0.0)


def render_static_modifiers(config: StoredFoodConfig) -> str:
    lines = [
        HEADER,
        "# Stored Food (EU5 1.4 carrier of the 1.3 stored-food effects, growth included; the engine's storage growth term",
        "# is off, NPop.FOOD_STORAGE_POP_GROWTH = 0): the effects of one stored year. pp_refresh_stored_food applies it",
        "# with size = the province's stored years (0 to the 2-year cap), so the effects follow the store continuously.",
        f"{MODIFIER} = {{",
        "\tgame_data = { category = province }",
    ]
    lines += [f"\t{key} = {format_value(value)}" for key, value in payload(config).items()]
    pivot = format_value(config.pivot_months)
    lines += [
        "}",
        "",
        f"# Store lever. Low Stores: the effects of one year short of {pivot} stored months, applied with size = the years",
        "# short (1 at an empty store). Province Food is worth more, so everything that makes it runs harder; the Grange's",
        "# Surplus Sales dry up.",
        f"{LOW_MODIFIER} = {{",
        "\tgame_data = { category = province }",
    ]
    lines += [f"\t{key} = {format_value(value)}" for key, value in low_payload(config).items()]
    lines += [
        "}",
        "",
        f"# Full Stores: the effects of one year above {pivot} stored months, applied with size = the years above (1 at the",
        "# 24-month cap). Province Food is worth less, the land yields more of its staples for the market, and the Grange",
        "# sells the surplus.",
        f"{FULL_MODIFIER} = {{",
        "\tgame_data = { category = province }",
    ]
    lines += [f"\t{key} = {format_value(value)}" for key, value in full_payload(config).items()]
    lines += [
        "}",
        "",
        "# Old saves (whole-month tiers, 2026-10-01): the names stay defined, without effects, so those saves load;",
        "# pp_refresh_stored_food removes them at the province's first refresh.",
    ]
    lines += [f"{legacy_name(t)} = {{ game_data = {{ category = province }} }}" for t in range(1, LEGACY_TIERS + 1)]
    return "\n".join(lines) + "\n"


def render_script_values(config: StoredFoodConfig) -> str:
    offset = VARIABLE_OFFSET
    return (
        f"{HEADER}\n"
        "# Location scope (display only): the stored years the province's Stored Food modifier is applied at (its size;\n"
        f"# {SIZE_VARIABLE} holds the applied months + {offset}). 0 without the modifier.\n"
        f"{YEARS_VALUE} = {{\n"
        "\tvalue = 0\n"
        "\tprovince ?= {\n"
        "\t\tif = {\n"
        f"\t\t\tlimit = {{ has_variable = {SIZE_VARIABLE} }}\n"
        f"\t\t\tadd = var:{SIZE_VARIABLE}\n"
        f"\t\t\tsubtract = {offset}\n"
        "\t\t}\n"
        "\t}\n"
        f"\tdivide = {MONTHS_PER_YEAR}\n"
        "\tmin = 0\n"
        "}\n"
        "\n"
        f"# Location scope (display only): yearly population growth from the province's Stored Food modifier, its {GROWTH_KEY}\n"
        f"# at the applied size. It is part of modifier:{GROWTH_KEY}; the engine adds no storage term of its own.\n"
        f"{GROWTH_VALUE} = {{\n"
        f"\tvalue = {YEARS_VALUE}\n"
        f"\tmultiply = {format_value(growth_per_year(config))}\n"
        "}\n"
    )


def render_scripted_effects(config: StoredFoodConfig) -> str:
    offset = VARIABLE_OFFSET
    high = format_value(offset + config.deadband_months)
    low = format_value(offset - config.deadband_months)
    zero = format_value(offset + EPSILON)
    pivot = format_value(offset + config.pivot_months)
    below_pivot = format_value(offset + config.pivot_months - EPSILON)
    above_pivot = format_value(offset + config.pivot_months + EPSILON)
    lines = [
        HEADER,
        "# Province scope. Keeps the province's Stored Food modifier at size = its stored years, and Low Stores / Full Stores",
        f"# at the years the store is below / above {format_value(config.pivot_months)} months. The consumption (a loop over the province's",
        "# locations) is worked out once; the modifiers are re-applied only when the stored months moved by more than",
        f"# {format_value(config.deadband_months)} since the last refresh or the store emptied. Variables and locals carry + {offset} (a variable at 0",
        "# counts as unset); `var:x = n` compares scopes, so only < / > ranges are used. A province that was never refreshed",
        f"# starts at {UNSET_VALUE}, below every store, so its first refresh always applies.",
        f"{REFRESH_EFFECT} = {{",
        "\t# old saves: drop the whole-month tier modifier and its variables once",
        "\tif = {",
        f"\t\tlimit = {{ has_variable = {LEGACY_VARIABLES[0]} }}",
    ]
    for tier in range(1, LEGACY_TIERS + 1):
        name = legacy_name(tier)
        lines.append(f"\t\tif = {{ limit = {{ has_province_modifier = {name} }} remove_province_modifier = {name} }}")
    for variable in LEGACY_VARIABLES:
        lines.append(f"\t\tif = {{ limit = {{ has_variable = {variable} }} remove_variable = {variable} }}")
    lines += [
        "\t}",
        "\t# old saves: the single-modifier version's months; without the new variable the first refresh applies everything",
        f"\tif = {{ limit = {{ has_variable = {OLD_SIZE_VARIABLE} }} remove_variable = {OLD_SIZE_VARIABLE} }}",
        f"\tset_local_variable = {{ name = {CONSUMPTION_LOCAL} value = {{ value = {CONSUMPTION_VALUE} add = {offset} }} }}",
        f"\tset_local_variable = {{ name = {TARGET_LOCAL} value = {offset} }}",
        "\tif = {",
        f"\t\tlimit = {{ local_var:{CONSUMPTION_LOCAL} > {offset} }}",
        "\t\tset_local_variable = {",
        f"\t\t\tname = {TARGET_LOCAL}",
        "\t\t\tvalue = {",
        "\t\t\t\tvalue = province_food",
        f"\t\t\t\tdivide = {{ value = local_var:{CONSUMPTION_LOCAL} subtract = {offset} }}",
        "\t\t\t\tmin = 0",
        f"\t\t\t\tmax = {CAP_MONTHS}",
        f"\t\t\t\tadd = {offset}",
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "\tif = {",
        f"\t\tlimit = {{ NOT = {{ has_variable = {SIZE_VARIABLE} }} }}",
        f"\t\tset_variable = {{ name = {SIZE_VARIABLE} value = {UNSET_VALUE} }}",
        "\t}",
        f"\tset_local_variable = {{ name = {CHANGE_LOCAL} value = {{ value = local_var:{TARGET_LOCAL} "
        f"subtract = var:{SIZE_VARIABLE} add = {offset} }} }}",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\tOR = {",
        f"\t\t\t\tlocal_var:{CHANGE_LOCAL} > {high}",
        f"\t\t\t\tlocal_var:{CHANGE_LOCAL} < {low}",
        f"\t\t\t\tAND = {{ local_var:{TARGET_LOCAL} < {zero} var:{SIZE_VARIABLE} > {zero} }}",
        "\t\t\t}",
        "\t\t}",
    ]
    for name in (MODIFIER, LOW_MODIFIER, FULL_MODIFIER):
        lines.append(f"\t\tif = {{ limit = {{ has_province_modifier = {name} }} remove_province_modifier = {name} }}")
    lines += [
        "\t\tif = {",
        f"\t\t\tlimit = {{ local_var:{TARGET_LOCAL} > {zero} }}",
        f"\t\t\tadd_province_modifier = {{ modifier = {MODIFIER} size = {{ value = local_var:{TARGET_LOCAL} "
        f"subtract = {offset} divide = {MONTHS_PER_YEAR} }} }}",
        "\t\t}",
        "\t\t# the store lever; a province nobody eats in gets neither",
        "\t\tif = {",
        f"\t\t\tlimit = {{ local_var:{CONSUMPTION_LOCAL} > {offset} local_var:{TARGET_LOCAL} < {below_pivot} }}",
        f"\t\t\tadd_province_modifier = {{ modifier = {LOW_MODIFIER} size = {{ value = {pivot} "
        f"subtract = local_var:{TARGET_LOCAL} divide = {MONTHS_PER_YEAR} }} }}",
        "\t\t}",
        "\t\tif = {",
        f"\t\t\tlimit = {{ local_var:{TARGET_LOCAL} > {above_pivot} }}",
        f"\t\t\tadd_province_modifier = {{ modifier = {FULL_MODIFIER} size = {{ value = local_var:{TARGET_LOCAL} "
        f"subtract = {pivot} divide = {MONTHS_PER_YEAR} }} }}",
        "\t\t}",
        f"\t\tset_variable = {{ name = {SIZE_VARIABLE} value = local_var:{TARGET_LOCAL} }}",
        "\t}",
        "}",
    ]
    return "\n".join(lines) + "\n"


def render_localization(config: StoredFoodConfig) -> str:
    lines = ["l_english:", f"  {HEADER.strip()}"]
    lines.append(f'  STATIC_MODIFIER_NAME_{MODIFIER}: "Stored Food"')
    lines.append(f'  STATIC_MODIFIER_DESC_{MODIFIER}: "{DESCRIPTION}"')
    lines.append(f'  STATIC_MODIFIER_NAME_{LOW_MODIFIER}: "{LOW_NAME}"')
    lines.append(f'  STATIC_MODIFIER_DESC_{LOW_MODIFIER}: "{LOW_DESCRIPTION}"')
    lines.append(f'  STATIC_MODIFIER_NAME_{FULL_MODIFIER}: "{FULL_NAME}"')
    lines.append(f'  STATIC_MODIFIER_DESC_{FULL_MODIFIER}: "{FULL_DESCRIPTION}"')
    for tier in range(1, LEGACY_TIERS + 1):
        lines.append(f'  STATIC_MODIFIER_NAME_{legacy_name(tier)}: "Stored Food"')
        lines.append(f'  STATIC_MODIFIER_DESC_{legacy_name(tier)}: "{LEGACY_DESCRIPTION}"')
    return "\n".join(lines) + "\n"


def render(config: StoredFoodConfig) -> dict[Path, str]:
    return {
        STATIC_MODIFIERS: render_static_modifiers(config),
        SCRIPT_VALUES: render_script_values(config),
        SCRIPTED_EFFECTS: render_scripted_effects(config),
        LOCALIZATION: render_localization(config),
    }


def configured_payload(project: Path) -> tuple[tuple[str, float], ...]:
    """The per-stored-year payload ``project`` configures (empty without ``[stored_food]``); the location view uses it."""
    try:
        return load_config(project).per_year
    except (OSError, ValueError, KeyError):
        return ()


def _read(path: Path) -> str | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def apply(project: Path, mod_root: Path, *, write: bool = True) -> StoredFoodResult:
    """Write (or with ``write=False`` only compare) the generated stored-food files, UTF-8 with BOM, and delete the
    tier version's files."""
    config = load_config(project)
    changed: list[Path] = []
    for relative, text in render(config).items():
        path = mod_root / relative
        if _read(path) == text:
            continue
        changed.append(relative)
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                handle.write(text)
    for relative in LEGACY_FILES:
        path = mod_root / relative
        if path.is_file():
            changed.append(relative)
            if write:
                path.unlink()
    return StoredFoodResult(files_changed=len(changed), changed=tuple(changed))
