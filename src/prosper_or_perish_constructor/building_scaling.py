from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import tomllib
from typing import Any


CONFIG_SECTION = "building_scaling"
WORKER_VICTUALS_FOOD_NEED_RATIO_FIELD = "worker_victuals_food_need_ratio"


@dataclass(frozen=True)
class BuildingScalingConfig:
    worker_victuals_food_need_ratio: Decimal


def load_building_scaling_config(path: Path) -> BuildingScalingConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION, {})
    if not isinstance(section, dict):
        raise ValueError(f"{path}: [{CONFIG_SECTION}] must be a table")

    ratio = _decimal_config_value(
        section.get(WORKER_VICTUALS_FOOD_NEED_RATIO_FIELD, "1.0"),
        f"{CONFIG_SECTION}.{WORKER_VICTUALS_FOOD_NEED_RATIO_FIELD}",
    )
    if ratio < 0:
        raise ValueError(
            f"{path}: {CONFIG_SECTION}.{WORKER_VICTUALS_FOOD_NEED_RATIO_FIELD} must be non-negative"
        )
    return BuildingScalingConfig(worker_victuals_food_need_ratio=ratio)


def worker_victuals_output_amount(
    *,
    employment_size: Decimal,
    pop_food_consumption: Decimal,
    victuals_food: Decimal,
    food_need_ratio: Decimal,
) -> Decimal:
    if employment_size < 0:
        raise ValueError(f"employment_size must be non-negative: {employment_size}")
    if pop_food_consumption < 0:
        raise ValueError(f"pop_food_consumption must be non-negative: {pop_food_consumption}")
    if victuals_food <= 0:
        raise ValueError(f"victuals_food must be positive: {victuals_food}")
    if food_need_ratio < 0:
        raise ValueError(f"food_need_ratio must be non-negative: {food_need_ratio}")
    return employment_size * pop_food_consumption * food_need_ratio / victuals_food


def format_output_amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _decimal_config_value(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError(f"{name} must be a number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result
