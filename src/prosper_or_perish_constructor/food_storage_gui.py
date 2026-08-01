"""Compile province-food GUI ratios from the configured food-growth cap."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path


CONSTRUCTOR_PROFILE = "constructor"
CONSTRUCTOR_LOAD_ORDER = Path("constructor.load_order.toml")
GROWTH_CAP_DEFINE_GROUP = "NEconomy"
GROWTH_CAP_DEFINE_KEY = "GROWTH_FROM_FOOD_MULTIPLIER_MAX"
MONTHS_PER_YEAR = 12
FOOD_STORAGE_MONTHS_MODIFIER = "pp_province_food_storage_months"
FOOD_STORAGE_LOCALIZATION = Path(
    "main_menu/localization/english/pp_food_storage_l_english.yml"
)
FOOD_STORAGE_MAP_MODE = Path(
    "in_game/gfx/map/map_modes/pp_food_map_modes.txt"
)
FOOD_STORAGE_MAP_SCALE_NAMES = (
    "low",
    "moderate",
    "high",
    "max",
    "step",
)
FOOD_STORAGE_MAP_SCALE_RE = re.compile(
    r"^(@pp_province_food_storage_months_"
    r"(?P<name>low|moderate|high|max|step)\s*=\s*)"
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?P<suffix>[ \t]*(?:#[^\r\n]*)?)(?P<carriage_return>\r?)$",
    flags=re.MULTILINE,
)
FOOD_STORAGE_GUI_DIVISOR_COUNTS = (
    (Path("in_game/gui/attribute_columns/province.gui"), 3),
    (Path("in_game/gui/expansion_lateralview.gui"), 2),
    (Path("in_game/gui/food_production_lateralview.gui"), 2),
    (Path("in_game/gui/location_production_lateralview.gui"), 4),
    (Path("in_game/gui/location_window.gui"), 4),
    (Path("in_game/gui/selected_market_view.gui"), 2),
    (Path("in_game/gui/shared/province_tooltips.gui"), 4),
)
FOOD_STORAGE_GUI_DIVISOR_RE = re.compile(
    rf"(Divide_CFixedPoint\([^\r\n]*GetModifierValueFixed\("
    rf"'{FOOD_STORAGE_MONTHS_MODIFIER}'\), '\(CFixedPoint\))"
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"('\))"
)


@dataclass(frozen=True)
class FoodStorageGuiCompileResult:
    skipped: bool
    max_years: float | None
    max_months: float | None
    divisor_literal: str | None
    files_changed: int
    replacements: int
    localization_changed: bool
    map_mode_changed: bool


def load_food_storage_max_months(
    *,
    profile: str,
    load_order_path: Path,
) -> float:
    from eu5gameparser.domain.defines import load_define_data

    define_data = load_define_data(profile=profile, load_order_path=load_order_path)
    max_years = define_data.numeric_value(
        GROWTH_CAP_DEFINE_GROUP,
        GROWTH_CAP_DEFINE_KEY,
    )
    if max_years is None:
        raise SystemExit(
            f"Missing parsed define {GROWTH_CAP_DEFINE_GROUP}.{GROWTH_CAP_DEFINE_KEY}."
        )

    numeric_years = float(max_years)
    if not math.isfinite(numeric_years) or numeric_years <= 0:
        raise SystemExit(
            f"{GROWTH_CAP_DEFINE_GROUP}.{GROWTH_CAP_DEFINE_KEY} must be greater "
            f"than zero; got {max_years!r}."
        )
    return numeric_years * MONTHS_PER_YEAR


def format_gui_fixed_point(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError(f"GUI fixed-point value must be finite; got {value!r}.")
    if value.is_integer():
        return str(int(value))
    return format(value, ".15g")


def compile_food_storage_gui(
    *,
    repo: Path,
    mod_root: Path,
    profile: str = CONSTRUCTOR_PROFILE,
    load_order_path: Path | None = None,
) -> FoodStorageGuiCompileResult:
    targets = [
        (mod_root / relative_path, expected_divisors)
        for relative_path, expected_divisors in FOOD_STORAGE_GUI_DIVISOR_COUNTS
    ]
    existing_targets = [path for path, _ in targets if path.is_file()]
    if not existing_targets:
        return FoodStorageGuiCompileResult(
            skipped=True,
            max_years=None,
            max_months=None,
            divisor_literal=None,
            files_changed=0,
            replacements=0,
            localization_changed=False,
            map_mode_changed=False,
        )

    missing_targets = [path for path, _ in targets if not path.is_file()]
    if missing_targets:
        missing = "\n".join(f"- {path}" for path in missing_targets)
        raise SystemExit(
            "Cannot compile province-food GUI ratios because some required "
            f"overrides are missing:\n{missing}"
        )

    resolved_load_order = load_order_path or repo / CONSTRUCTOR_LOAD_ORDER
    max_months = load_food_storage_max_months(
        profile=profile,
        load_order_path=resolved_load_order,
    )
    max_years = max_months / MONTHS_PER_YEAR
    divisor_literal = format_gui_fixed_point(max_months)
    map_scale = food_storage_map_scale(max_months)
    map_scale_literals = {
        name: format_gui_fixed_point(value)
        for name, value in map_scale.items()
    }

    files_changed = 0
    replacements = 0
    for path, expected_divisors in targets:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            text = handle.read()
        updated, replacement_count = FOOD_STORAGE_GUI_DIVISOR_RE.subn(
            rf"\g<1>{divisor_literal}\g<2>",
            text,
        )
        if replacement_count != expected_divisors:
            raise SystemExit(
                f"Expected {expected_divisors} stored-food GUI divisors in "
                f"{path}, found {replacement_count}."
            )
        replacements += replacement_count
        if updated == text:
            continue
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write(updated)
        files_changed += 1

    map_mode_path = mod_root / FOOD_STORAGE_MAP_MODE
    if not map_mode_path.is_file():
        raise SystemExit(
            "Cannot compile province-food map scale because its map-mode "
            f"override is missing:\n- {map_mode_path}"
        )
    with map_mode_path.open("r", encoding="utf-8-sig", newline="") as handle:
        map_mode = handle.read()
    found_scale_names: set[str] = set()

    def replace_map_scale(match: re.Match[str]) -> str:
        name = match.group("name")
        found_scale_names.add(name)
        return (
            f"{match.group(1)}{map_scale_literals[name]}"
            f"{match.group('suffix')}{match.group('carriage_return')}"
        )

    updated_map_mode = FOOD_STORAGE_MAP_SCALE_RE.sub(
        replace_map_scale,
        map_mode,
    )
    missing_scale_names = set(FOOD_STORAGE_MAP_SCALE_NAMES) - found_scale_names
    if missing_scale_names:
        missing = ", ".join(sorted(missing_scale_names))
        raise SystemExit(
            "Cannot compile province-food map scale because these constants "
            f"are missing from {map_mode_path}: {missing}"
        )
    map_mode_changed = updated_map_mode != map_mode
    if map_mode_changed:
        with map_mode_path.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write(updated_map_mode)

    localization_path = mod_root / FOOD_STORAGE_LOCALIZATION
    localization = render_food_storage_localization(map_scale_literals)
    localization_path.parent.mkdir(parents=True, exist_ok=True)
    localization_changed = True
    if localization_path.is_file():
        with localization_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            localization_changed = handle.read() != localization
    if localization_changed:
        with localization_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            handle.write(localization)

    return FoodStorageGuiCompileResult(
        skipped=False,
        max_years=max_years,
        max_months=max_months,
        divisor_literal=divisor_literal,
        files_changed=files_changed,
        replacements=replacements,
        localization_changed=localization_changed,
        map_mode_changed=map_mode_changed,
    )


def food_storage_map_scale(max_months: float) -> dict[str, float]:
    if not math.isfinite(max_months) or max_months <= 0:
        raise ValueError(
            f"Food-storage map maximum must be greater than zero; got {max_months!r}."
        )
    step = max_months / 4
    return {
        "low": step,
        "moderate": step * 2,
        "high": step * 3,
        "max": max_months,
        "step": step,
    }


def render_food_storage_localization(map_scale: dict[str, str]) -> str:
    return (
        "l_english:\n"
        "  # Generated by ppc finalize from "
        f"{GROWTH_CAP_DEFINE_GROUP}.{GROWTH_CAP_DEFINE_KEY}.\n"
        '  EFFECTS_FROM_STORAGE: "The [population|e] of this [province|e] '
        "consumes $TOTAL_POP_CONSUMPTION|+=$@food! every #Y 12#! Months. "
        "Every #Y 12#! Months of stored [food] will apply a bonus, up to a "
        f"maximum of #Y {map_scale['max']}#! Months.\\n\\nEffects From $VAL|G$ "
        'Months of Stored Food:\\n"\n'
        '  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_NONE: "0 months"\n'
        "  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_LOW: "
        f'"{map_scale["low"]} months"\n'
        "  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_MODERATE: "
        f'"{map_scale["moderate"]} months"\n'
        "  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_HIGH: "
        f'"{map_scale["high"]} months"\n'
        "  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_MAX: "
        f'"{map_scale["max"]}+ months"\n'
        "  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_STRIPED: "
        '"Maximum food-growth bonus reached"\n'
        "  MAPMODE_PP_POSITIVE_PROVINCE_FOOD_GROWTH_STARVING: "
        '"Province is starving"\n'
    )
