"""Stored-food effect carrier (EU5 1.4): one province modifier per whole month of stored food.

EU5 1.4 deleted the engine-scaled static modifier ``positive_province_food_growth``. Its per-stored-year effects,
growth included, come back through this carrier; the engine's own storage growth term is off
(``NPop.FOOD_STORAGE_POP_GROWTH = 0`` in pp_defines_adjustments.txt), so growth from stored food is the
``local_population_growth`` of the Stored Food modifier:

- ``pp_food_store_<s>`` ("Stored Food: s months", s = 0 to the 24-month cap): since 2026-10-03 one province modifier
  per whole month, so a province carries exactly one and it shows with its true values in the location view's
  province modifier list (Jan: one food storage modifier in its rightful place; the size-scaled carriers did not show
  their scaled values). Step s holds every stored-food effect at that store, worked out exactly and rounded once to
  five decimals (``step_payload``): ``[stored_food.per_year]`` x s / 12 (growth, prosperity, migration, devastation
  recovery), the store lever, ``[stored_food.low]`` x the years short of ``pivot_months`` or ``[stored_food.full]``
  x the years above (the Grange's Surplus Sales), and the store curve ``[stored_food.curve]`` (2026-10-03, Jan's farm
  trade-off): the Province Food output of every maker follows ``province_food_share`` (its output as a share of the
  output at an empty store, linear between the knots, 0 at the pivot) and every staple food's output (``staple_foods.py``:
  staple crops, animals and fruits, 2026-10-04) follows its factor x that line (``staple_per_province_food``, own
  factors in ``staple_per_province_food_by_good``), so every staple food maker feeds the province while its store is
  low and sends its goods to market while it is full. The pivot step carries no lever or curve line, so no country
  base value belongs to the lever.
- the province-scope scripted effect ``pp_refresh_stored_food``: works out the province's consumption once (the
  location loop is the expensive part) and the stored months from it. The step is the months rounded to the nearest
  whole month (half rounds up), re-picked only when the store moved more than half a month + ``deadband_months``
  away from the carried step, so a store on a boundary does not flip. A province nobody eats in carries no step. The
  stored months themselves stay in ``pp_stored_food_months`` (re-set past the deadband) for the AI weights; variables
  carry +100 (a variable at 0 counts as unset); a province never refreshed starts below every store.
- old saves: the scaled version (2026-10-01..03: ``pp_stored_food``, ``pp_low_stores``, ``pp_full_stores``) and the
  whole-month tier version (2026-10-01, ``pp_stored_food_tier_<t>``) stay defined without effects so saves load; the
  first refresh removes them.
- display helpers (view only, location scope): ``pp_stored_food_years`` (the carried step's months / 12) and
  ``pp_province_food_storage_growth`` (its growth); the location view's Stored Food chip scales each Stored Food
  effect by the years (location_status.py).
- ``pp_stored_food_staple_line`` (location scope): the crop line of the carried step; the crop farms'
  ``ai_construct_weight`` takes it out of the crop output modifier it reads as land quality (crop_farms.py).

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
CURVE_SECTION = "curve"
FOOD_KEY = "local_local_food_output_modifier"    # Province Food output of every maker (the store curve's main line)
STAPLE_LINE_VALUE = "pp_stored_food_staple_line"  # location scope: the carried step's crop line (crop farm AI weights)
MODIFIER = "pp_stored_food"
LOW_MODIFIER = "pp_low_stores"
FULL_MODIFIER = "pp_full_stores"
STAPLE_KEY = "staple_output"   # in [stored_food.low] / [stored_food.full]: one line per provisioned good
REFRESH_EFFECT = "pp_refresh_stored_food"
MONTHS_VALUE = "pp_stored_food_province_months"
CONSUMPTION_VALUE = "pp_stored_food_province_consumption"
SIZE_VARIABLE = "pp_stored_food_months"         # stored months + 100 (AI weights: pp_location_stored_months)
STEP_PREFIX = "pp_food_store_"                  # pp_food_store_0 .. pp_food_store_24
STEP_VARIABLE = "pp_food_store_step"            # carried step + 100
STEP_LOCAL = "pp_food_store_new"
STEP_CHANGE_LOCAL = "pp_food_store_change"
STEPS = 24                                      # the cap: NEconomy.GROWTH_FROM_FOOD_MULTIPLIER_MAX x 12 months
NO_STEP = 99                                    # a province nobody eats in: no step
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
# The scaled version (2026-10-01..03): one modifier at size = stored years plus Low / Full Stores.
LEGACY_SCALED = ("pp_stored_food", "pp_low_stores", "pp_full_stores")

STATIC_MODIFIERS = Path("in_game/common/static_modifiers/pp_stored_food.txt")
SCRIPT_VALUES = Path("in_game/common/script_values/pp_stored_food.txt")
SCRIPTED_EFFECTS = Path("in_game/common/scripted_effects/pp_stored_food.txt")
LOCALIZATION = Path("main_menu/localization/english/pp_stored_food_l_english.yml")
GENERATED_FILES = (STATIC_MODIFIERS, SCRIPT_VALUES, SCRIPTED_EFFECTS, LOCALIZATION)
# The engine draws a static modifier with gfx/interface/icons/modifiers/<key>.dds (vanilla: overpopulation, looted) and
# falls back to a generic icon; each step gets the location view's Stored Food chip icon.
STEP_ICONS = Path("main_menu/gfx/interface/icons/modifiers")
STEP_ICON_SOURCE = Path("main_menu/gfx/interface/icons/flat_icons/trade_market/food_stockpile.dds")
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
STEP_VALUE = "pp_stored_food_step"               # the carried step, -1 without one (the location view's food chip)

HEADER = "# Generated by ppc build from [stored_food] in constructor.toml (stored_food.py); do not edit by hand.\n"

# Player-facing plain text (generated static-modifier descriptions take no concept links); no balance numbers, the
# modifier tooltip shows them.
DESCRIPTION = (
    "The food this province holds in storage, counted in months of its own consumption. Full stores let its people grow "
    "faster, and they help the province recover from devastation, draw settlers and prosper. While the store is low, "
    "food is worth more here: the farms, flocks, fisheries and orchards keep more of their harvest to feed the province, "
    "the taverns serve more and the granges find little to pack. While it is full, food is worth less: they send more of "
    "their staple foods to market and the surplus is left to the granges. The effects follow the store month by month, "
    "up to a cap."
)
LEGACY_DESCRIPTION = "Replaced by the Stored Food modifier at the province's next monthly update."


@dataclass(frozen=True)
class StoredFoodConfig:
    deadband_months: float
    per_year: tuple[tuple[str, float], ...]
    pivot_months: float = 12.0
    low: tuple[tuple[str, float], ...] = ()    # Low Stores: per year short of the pivot, staple lines expanded
    full: tuple[tuple[str, float], ...] = ()   # Full Stores: per year above the pivot, staple lines expanded
    # the store curve ([stored_food.curve]): (months, Province Food output as a share of the output at an empty store)
    food_curve: tuple[tuple[float, float], ...] = ()
    staple_factor: float = 0.0                 # a staple food's line = this x the Province Food line (the crop farm goods)
    staple_goods: tuple[str, ...] = ()         # the staple foods (staple_foods.py), every one on the curve
    staple_factor_by_good: tuple[tuple[str, float], ...] = ()   # goods with their own factor (fish, fruit, game, wool)

    def factor(self, good: str) -> float:
        """The store curve factor of a staple food: its own, else ``staple_factor``."""
        return dict(self.staple_factor_by_good).get(good, self.staple_factor)


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
    food_curve, staple_factor, staple_goods_, by_good = _curve(section.get(CURVE_SECTION, {}), pivot,
                                                               f"{project}: [{CONFIG_SECTION}.{CURVE_SECTION}]")
    return StoredFoodConfig(
        deadband_months=deadband,
        per_year=per_year,
        pivot_months=pivot,
        low=_lever_payload(section.get("low", {}), f"{project}: [{CONFIG_SECTION}.low]"),
        full=_lever_payload(section.get("full", {}), f"{project}: [{CONFIG_SECTION}.full]"),
        food_curve=food_curve,
        staple_factor=staple_factor,
        staple_goods=staple_goods_,
        staple_factor_by_good=by_good,
    )


def _curve(
    table: object, pivot: float, where: str
) -> tuple[tuple[tuple[float, float], ...], float, tuple[str, ...], tuple[tuple[str, float], ...]]:
    """``[stored_food.curve]``: the knots of ``province_food_share`` (stored months -> Province Food output as a share
    of the output at an empty store), ``staple_per_province_food`` (every staple food's factor) and
    ``staple_per_province_food_by_good`` (goods with their own). The goods are the staple foods (``staple_foods.py``,
    the ``staple_group`` column of config/goods_categories.csv), never a list of the curve's own. Empty: no curve."""
    from prosper_or_perish_constructor import staple_foods

    if not isinstance(table, dict):
        raise ValueError(f"{where} must be a table")
    if not table:
        return (), 0.0, (), ()
    shares = table.get("province_food_share")
    if not isinstance(shares, dict) or len(shares) < 2:
        raise ValueError(f"{where} province_food_share needs at least two knots (stored months = share)")
    knots = tuple(sorted((float(months), float(share)) for months, share in shares.items()))
    if knots[0][0] != 0 or knots[-1][0] != STEPS:
        raise ValueError(f"{where} province_food_share must run from 0 to {STEPS} stored months")
    if any(share <= 0 for _, share in knots) or any(b[1] > a[1] for a, b in zip(knots, knots[1:])):
        raise ValueError(f"{where} province_food_share must be positive and never rise with the store")
    if not knots[0][0] < pivot < knots[-1][0]:
        raise ValueError(f"{where} the pivot ({pivot} months) must lie inside the curve")
    if "staple_goods" in table:
        raise ValueError(f"{where} staple_goods is gone: the curve takes every staple food (staple_group column of "
                         "config/goods_categories.csv)")
    factor = float(table.get("staple_per_province_food", 0.0))
    goods = staple_foods.staple_foods() if factor else ()
    own = table.get("staple_per_province_food_by_good", {})
    if not isinstance(own, dict):
        raise ValueError(f"{where} staple_per_province_food_by_good must be a table (good = factor)")
    unknown = sorted(set(own) - set(goods))
    if unknown:
        raise ValueError(f"{where} staple_per_province_food_by_good names goods that are not staple foods: {unknown}")
    by_good = tuple((str(good), float(value)) for good, value in own.items())
    if any(value * factor <= 0 for _, value in by_good):
        raise ValueError(f"{where} staple_per_province_food_by_good must have the sign of staple_per_province_food")
    return knots, factor, goods, by_good


def _curve_share(config: StoredFoodConfig, months: Decimal) -> Decimal:
    """The curve's Province Food share at ``months`` (linear between the knots, flat beyond the ends)."""
    knots = [(Decimal(repr(m)), Decimal(repr(s))) for m, s in config.food_curve]
    if months <= knots[0][0]:
        return knots[0][1]
    for (m0, s0), (m1, s1) in zip(knots, knots[1:]):
        if months <= m1:
            return s0 + (s1 - s0) * (months - m0) / (m1 - m0)
    return knots[-1][1]


def curve_lines(config: StoredFoodConfig, months: float | Decimal) -> dict[str, Decimal]:
    """The store curve at ``months`` stored, exact: the Province Food output line (the share over the pivot's share,
    minus 1: 0 at the pivot) and each staple food's line (its factor x the Province Food line)."""
    if not config.food_curve:
        return {}
    months = Decimal(repr(float(months))) if not isinstance(months, Decimal) else months
    food = _curve_share(config, months) / _curve_share(config, Decimal(repr(config.pivot_months))) - 1
    lines = {FOOD_KEY: food}
    if config.staple_factor:
        lines.update({f"local_{good}_output_modifier": Decimal(repr(config.factor(good))) * food
                      for good in config.staple_goods})
    return lines


def province_food_line(config: StoredFoodConfig, months: float) -> float:
    """Province Food output line of the store curve at ``months`` (0 at the pivot; 0 without a curve)."""
    return float(curve_lines(config, months).get(FOOD_KEY, 0))


def staple_line(config: StoredFoodConfig, months: float, good: str | None = None) -> float:
    """A staple food's line of the store curve at ``months`` (0 without one); without ``good`` the line of
    ``staple_factor`` (every crop farm good)."""
    factor = config.factor(good) if good else config.staple_factor
    return float(Decimal(repr(factor)) * Decimal(repr(province_food_line(config, months))))


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


def step_name(step: int) -> str:
    return f"{STEP_PREFIX}{step}"


def step_payload(config: StoredFoodConfig, step: int) -> dict[str, float]:
    """The Stored Food modifier at ``step`` whole stored months: Stored Food x step / 12, plus Low Stores x the years
    short of the pivot or Full Stores x the years above it, plus the store curve at ``step`` months. Every line is
    worked out exactly (Decimal) and rounded once to five decimals; lines that round to 0 are left out, so the pivot
    step carries no store-lever or curve line at all."""
    if not 0 <= step <= STEPS:
        raise ValueError(f"step {step} outside 0..{STEPS}")
    pivot = Decimal(repr(config.pivot_months))
    months = Decimal(step)
    total: dict[str, Decimal] = {}

    def add(lines: tuple[tuple[str, float], ...], years: Decimal) -> None:
        for key, value in lines:
            total[key] = total.get(key, Decimal(0)) + Decimal(repr(value)) * years

    add(config.per_year, months / MONTHS_PER_YEAR)
    if months < pivot:
        add(config.low, (pivot - months) / MONTHS_PER_YEAR)
    elif months > pivot:
        add(config.full, (months - pivot) / MONTHS_PER_YEAR)
    for key, value in curve_lines(config, months).items():
        total[key] = total.get(key, Decimal(0)) + value
    quantum = Decimal(1).scaleb(-DECIMALS)
    out = {}
    for key, value in total.items():
        rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
        if rounded != 0:
            out[key] = float(rounded)
    return out


def step_label(step: int) -> str:
    if step == 0:
        return "almost empty"
    return "1 month" if step == 1 else f"{step} months"


def render_static_modifiers(config: StoredFoodConfig) -> str:
    pivot = format_value(config.pivot_months)
    lines = [
        HEADER,
        "# Stored Food (2026-10-03): one province modifier per whole month of stored food, 0 to the 24-month cap, so the",
        "# province carries exactly one and it shows with its true values in the location view's province modifier list.",
        "# Each step holds every stored-food effect at that store: Stored Food ([stored_food.per_year], growth included;",
        "# the engine's storage growth term is off, NPop.FOOD_STORAGE_POP_GROWTH = 0) x months / 12, the store lever:",
        f"# Low Stores ([stored_food.low]) x the years short of {pivot} months, Full Stores ([stored_food.full]) x the years",
        "# above, and the store curve ([stored_food.curve]): Province Food output of every maker by stored month, and the",
        "# crop farm goods' output moving the other way (farms feed a lean province, sell from a full one).",
        "# pp_refresh_stored_food picks the step: the stored months rounded to the nearest whole month, kept while",
        "# the store stays within half a month plus the deadband of it. Values are rounded once, to five decimals.",
    ]
    for step in range(STEPS + 1):
        lines += [f"{step_name(step)} = {{", "\tgame_data = { category = province }"]
        lines += [f"\t{key} = {format_value(value)}" for key, value in step_payload(config, step).items()]
        lines.append("}")
    lines += [
        "",
        "# Old saves: the names of the earlier versions stay defined, without effects, so those saves load;",
        "# pp_refresh_stored_food removes them at the province's first refresh (scaled modifiers 2026-10-01..03,",
        "# whole-month tiers 2026-10-01).",
    ]
    lines += [f"{name} = {{ game_data = {{ category = province }} }}" for name in LEGACY_SCALED]
    lines += [f"{legacy_name(t)} = {{ game_data = {{ category = province }} }}" for t in range(1, LEGACY_TIERS + 1)]
    return "\n".join(lines) + "\n"


def render_script_values(config: StoredFoodConfig) -> str:
    offset = VARIABLE_OFFSET
    return (
        f"{HEADER}\n"
        "# Location scope (display only): the stored years of the Stored Food step the province carries (its whole months\n"
        f"# / 12; {STEP_VARIABLE} holds the step + {offset}). 0 without one.\n"
        f"{YEARS_VALUE} = {{\n"
        "\tvalue = 0\n"
        "\tprovince ?= {\n"
        "\t\tif = {\n"
        f"\t\t\tlimit = {{ has_variable = {STEP_VARIABLE} var:{STEP_VARIABLE} > {format_value(offset - 0.5)} }}\n"
        f"\t\t\tadd = var:{STEP_VARIABLE}\n"
        f"\t\t\tsubtract = {offset}\n"
        "\t\t}\n"
        "\t}\n"
        f"\tdivide = {MONTHS_PER_YEAR}\n"
        "\tmin = 0\n"
        "}\n"
        "\n"
        "# Location scope (display only): the Stored Food step (pp_food_store_<s>) the province carries, -1 without one; the\n"
        "# location view's food chip shows that step modifier itself.\n"
        f"{STEP_VALUE} = {{\n"
        "\tvalue = -1\n"
        "\tprovince ?= {\n"
        "\t\tif = {\n"
        f"\t\t\tlimit = {{ has_variable = {STEP_VARIABLE} var:{STEP_VARIABLE} > {format_value(offset - 0.5)} }}\n"
        f"\t\t\tadd = var:{STEP_VARIABLE}\n"
        f"\t\t\tsubtract = {format_value(offset - 1)}\n"
        "\t\t}\n"
        "\t}\n"
        "}\n"
        "\n"
        f"# Location scope (display only): yearly population growth from the province's Stored Food step, its {GROWTH_KEY}.\n"
        f"# It is part of modifier:{GROWTH_KEY}; the engine adds no storage term of its own.\n"
        f"{GROWTH_VALUE} = {{\n"
        f"\tvalue = {YEARS_VALUE}\n"
        f"\tmultiply = {format_value(growth_per_year(config))}\n"
        "}\n"
        + render_staple_line_value(config)
    )


def staple_line_by_step(config: StoredFoodConfig) -> list[float]:
    """The crop line each step modifier carries (as written, five decimals; 0 at the pivot or without a curve): the line
    of the crop farm goods, which share ``staple_factor`` (the crop farms' AI weight reads it for every crop)."""
    from prosper_or_perish_constructor import provisioning

    if not config.staple_goods:
        return [0.0] * (STEPS + 1)
    farm_goods = tuple(dict.fromkeys(provisioning.CROP_FARM_GOODS.values()))
    own = sorted(good for good in farm_goods if config.factor(good) != config.staple_factor)
    if own:
        raise ValueError(f"the crop farm goods share one store curve factor (pp_stored_food_staple_line); own: {own}")
    key = f"local_{farm_goods[0]}_output_modifier"
    return [step_payload(config, step).get(key, 0.0) for step in range(STEPS + 1)]


def render_staple_line_value(config: StoredFoodConfig) -> str:
    """Location scope: the staple goods' crop line of the Stored Food step the province carries, 0 without a step.
    One branch per step (``var:x = n`` compares scopes, so only < ranges), the values exactly as the steps carry them."""
    offset = VARIABLE_OFFSET
    lines = [
        "",
        "# Location scope: the crop line of the Stored Food step the province carries ([stored_food.curve], the same value",
        "# as the step's local_<staple>_output_modifier); 0 without a step. The crop farms' ai_construct_weight takes it out",
        "# of the crop output modifier it reads as land quality (crop_farms.py): the store is not the land.",
        f"{STAPLE_LINE_VALUE} = {{",
        "\tvalue = 0",
        "\tprovince ?= {",
        "\t\tif = {",
        f"\t\t\tlimit = {{ has_variable = {STEP_VARIABLE} var:{STEP_VARIABLE} > {format_value(offset - 0.5)} }}",
    ]
    values = staple_line_by_step(config)
    for step, value in enumerate(values):
        if step < STEPS:
            keyword = "if" if step == 0 else "else_if"
            lines.append(f"\t\t\t{keyword} = {{ limit = {{ var:{STEP_VARIABLE} < {format_value(offset + step + 0.5)} }} "
                         f"add = {format_value(value)} }}")
        else:
            lines.append(f"\t\t\telse = {{ add = {format_value(value)} }}")
    lines += ["\t\t}", "\t}", "}"]
    return "\n".join(lines) + "\n"


def _remove_steps(indent: str) -> list[str]:
    return [f"{indent}if = {{ limit = {{ has_province_modifier = {step_name(s)} }} remove_province_modifier = {step_name(s)} }}"
            for s in range(STEPS + 1)]


def render_scripted_effects(config: StoredFoodConfig) -> str:
    offset = VARIABLE_OFFSET
    high = format_value(offset + config.deadband_months)
    low = format_value(offset - config.deadband_months)
    zero = format_value(offset + EPSILON)
    step_high = format_value(offset + 0.5 + config.deadband_months)
    step_low = format_value(offset - 0.5 - config.deadband_months)
    lines = [
        HEADER,
        "# Province scope. Keeps the province on the Stored Food step of its store: the stored months rounded to the nearest",
        f"# whole month (half a month rounds up), re-picked only when the store moved more than half a month + {format_value(config.deadband_months)}",
        "# away from the carried step, so a store sitting on a boundary does not flip back and forth. The consumption (a loop",
        "# over the province's locations) is worked out once. A province nobody eats in carries no step.",
        f"# {SIZE_VARIABLE} keeps the stored months themselves (re-set when they moved by more than {format_value(config.deadband_months)}) for",
        f"# the AI weights and displays that read pp_location_stored_months; {STEP_VARIABLE} keeps the carried step.",
        f"# Variables and locals carry + {offset} (a variable at 0 counts as unset); `var:x = n` compares scopes, so only < / >",
        f"# ranges are used. A province never refreshed starts at {UNSET_VALUE}, below every store, so its first refresh applies;",
        f"# {NO_STEP} marks a province without a step.",
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
        "\t# old saves: the scaled modifiers (2026-10-01..03) and the single-modifier version's months",
    ]
    for name in LEGACY_SCALED:
        lines.append(f"\tif = {{ limit = {{ has_province_modifier = {name} }} remove_province_modifier = {name} }}")
    lines += [
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
        "\t# the stored months (AI weights, displays)",
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
        f"\t\tset_variable = {{ name = {SIZE_VARIABLE} value = local_var:{TARGET_LOCAL} }}",
        "\t}",
        "\t# the Stored Food step",
        "\tif = {",
        f"\t\tlimit = {{ NOT = {{ has_variable = {STEP_VARIABLE} }} }}",
        f"\t\tset_variable = {{ name = {STEP_VARIABLE} value = {UNSET_VALUE} }}",
        "\t}",
        "\tif = {",
        f"\t\tlimit = {{ local_var:{CONSUMPTION_LOCAL} > {offset} }}",
        f"\t\tset_local_variable = {{ name = {STEP_CHANGE_LOCAL} value = {{ value = local_var:{TARGET_LOCAL} "
        f"subtract = var:{STEP_VARIABLE} add = {offset} }} }}",
        "\t\tif = {",
        f"\t\t\tlimit = {{ OR = {{ local_var:{STEP_CHANGE_LOCAL} > {step_high} local_var:{STEP_CHANGE_LOCAL} < {step_low} }} }}",
        f"\t\t\tset_local_variable = {{ name = {STEP_LOCAL} value = {{ value = local_var:{TARGET_LOCAL} add = 0.5 floor = yes "
        f"max = {offset + STEPS} }} }}",
    ]
    lines += _remove_steps("\t\t\t")
    for step in range(STEPS + 1):
        if step < STEPS:
            keyword = "if" if step == 0 else "else_if"
            lines.append(f"\t\t\t{keyword} = {{ limit = {{ local_var:{STEP_LOCAL} < {format_value(offset + step + 0.5)} }} "
                         f"add_province_modifier = {{ modifier = {step_name(step)} }} }}")
        else:
            lines.append(f"\t\t\telse = {{ add_province_modifier = {{ modifier = {step_name(step)} }} }}")
    lines += [
        f"\t\t\tset_variable = {{ name = {STEP_VARIABLE} value = local_var:{STEP_LOCAL} }}",
        "\t\t}",
        "\t}",
        "\t# nobody eats here: no step",
        "\telse_if = {",
        f"\t\tlimit = {{ var:{STEP_VARIABLE} > {format_value(NO_STEP + 0.5)} }}",
    ]
    lines += _remove_steps("\t\t")
    lines += [
        f"\t\tset_variable = {{ name = {STEP_VARIABLE} value = {NO_STEP} }}",
        "\t}",
    ]
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_localization(config: StoredFoodConfig) -> str:
    lines = ["l_english:", f"  {HEADER.strip()}"]
    for step in range(STEPS + 1):
        lines.append(f'  STATIC_MODIFIER_NAME_{step_name(step)}: "Stored Food: {step_label(step)}"')
        lines.append(f'  STATIC_MODIFIER_DESC_{step_name(step)}: "{DESCRIPTION}"')
    for name in LEGACY_SCALED:
        lines.append(f'  STATIC_MODIFIER_NAME_{name}: "Stored Food"')
        lines.append(f'  STATIC_MODIFIER_DESC_{name}: "{LEGACY_DESCRIPTION}"')
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


def step_icon(step: int) -> Path:
    return STEP_ICONS / f"{step_name(step)}.dds"


def apply(project: Path, mod_root: Path, *, write: bool = True, vanilla_game: Path | None = None) -> StoredFoodResult:
    """Write (or with ``write=False`` only compare) the generated stored-food files, UTF-8 with BOM, and delete the
    tier version's files. With ``vanilla_game`` (the folder holding main_menu/) each step modifier also gets the
    food stockpile icon as its own icon file."""
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
    if vanilla_game is not None:
        icon = (vanilla_game / STEP_ICON_SOURCE).read_bytes()
        for step in range(STEPS + 1):
            path = mod_root / step_icon(step)
            if path.is_file() and path.read_bytes() == icon:
                continue
            changed.append(step_icon(step))
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(icon)
    for relative in LEGACY_FILES:
        path = mod_root / relative
        if path.is_file():
            changed.append(relative)
            if write:
                path.unlink()
    return StoredFoodResult(files_changed=len(changed), changed=tuple(changed))
