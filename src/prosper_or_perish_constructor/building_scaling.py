from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
import tomllib
from typing import Any

import yaml
from eu5_building_pipeline.template import load_template
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList


CONFIG_SECTION = "building_scaling"
WORKER_VICTUALS_FOOD_NEED_RATIO_FIELD = "worker_victuals_food_need_ratio"
INCREASE_PER_LEVEL_COST_MULTIPLIER_FIELD = "increase_per_level_cost_multiplier"
BURGHER_BUILDING_EMPLOYMENT_SIZE_FIELD = "burgher_building_employment_size"
BUILDING_BLUEPRINT_MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
BUILDING_BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
BUILDING_TYPES_RELATIVE = Path("in_game/common/building_types")
EMPLOYMENT_SIZE_STEP = Decimal("0.05")


@dataclass(frozen=True)
class BuildingScalingConfig:
    worker_victuals_food_need_ratio: Decimal
    increase_per_level_cost_multiplier: Decimal
    burgher_building_employment_size: Decimal


@dataclass(frozen=True)
class IncreasePerLevelCostScalingResult:
    multiplier: Decimal
    files_changed: int
    entries_scaled: int


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
    increase_cost_multiplier = _decimal_config_value(
        section.get(INCREASE_PER_LEVEL_COST_MULTIPLIER_FIELD, "1.0"),
        f"{CONFIG_SECTION}.{INCREASE_PER_LEVEL_COST_MULTIPLIER_FIELD}",
    )
    if increase_cost_multiplier < 0:
        raise ValueError(
            f"{path}: {CONFIG_SECTION}.{INCREASE_PER_LEVEL_COST_MULTIPLIER_FIELD} must be non-negative"
        )
    burgher_employment_size = _decimal_config_value(
        section.get(BURGHER_BUILDING_EMPLOYMENT_SIZE_FIELD, "1.0"),
        f"{CONFIG_SECTION}.{BURGHER_BUILDING_EMPLOYMENT_SIZE_FIELD}",
    )
    if burgher_employment_size <= 0:
        raise ValueError(
            f"{path}: {CONFIG_SECTION}.{BURGHER_BUILDING_EMPLOYMENT_SIZE_FIELD} must be positive"
        )
    if not _is_employment_step(burgher_employment_size):
        raise ValueError(
            f"{path}: {CONFIG_SECTION}.{BURGHER_BUILDING_EMPLOYMENT_SIZE_FIELD} "
            f"must be a multiple of {EMPLOYMENT_SIZE_STEP}"
        )
    return BuildingScalingConfig(
        worker_victuals_food_need_ratio=ratio,
        increase_per_level_cost_multiplier=increase_cost_multiplier,
        burgher_building_employment_size=burgher_employment_size,
    )


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


def scaled_increase_per_level_cost_text(value: Decimal, multiplier: Decimal) -> str:
    return format_increase_per_level_cost(value * multiplier)


def format_increase_per_level_cost(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def apply_increase_per_level_cost_multiplier(
    repo: Path,
    mod_root: Path,
    project: Path,
) -> IncreasePerLevelCostScalingResult:
    config = load_building_scaling_config(project)
    source_costs = _accepted_blueprint_increase_per_level_costs(repo)
    compiled_costs = {
        building: scaled_increase_per_level_cost_text(
            cost,
            config.increase_per_level_cost_multiplier,
        )
        for building, cost in source_costs.items()
    }

    building_types = mod_root / BUILDING_TYPES_RELATIVE
    if not building_types.is_dir():
        return IncreasePerLevelCostScalingResult(
            multiplier=config.increase_per_level_cost_multiplier,
            files_changed=0,
            entries_scaled=0,
        )

    files_changed = 0
    entries_scaled = 0
    for path in sorted(building_types.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        updated, changed = _set_compiled_increase_per_level_costs(text, compiled_costs)
        if updated != text:
            path.write_text(updated, encoding="utf-8-sig")
            files_changed += 1
        entries_scaled += changed

    return IncreasePerLevelCostScalingResult(
        multiplier=config.increase_per_level_cost_multiplier,
        files_changed=files_changed,
        entries_scaled=entries_scaled,
    )


def _decimal_config_value(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError(f"{name} must be a number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _is_employment_step(value: Decimal) -> bool:
    ratio = value / EMPLOYMENT_SIZE_STEP
    return ratio == ratio.to_integral_value()


def _accepted_blueprint_increase_per_level_costs(repo: Path) -> dict[str, Decimal]:
    manifest_path = repo / BUILDING_BLUEPRINT_MANIFEST_RELATIVE
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    enabled = raw.get("enabled") if isinstance(raw, dict) else None
    if not isinstance(enabled, list):
        raise ValueError(f"{manifest_path}: expected enabled list")

    costs: dict[str, Decimal] = {}
    for entry in enabled:
        path = repo / BUILDING_BLUEPRINT_ROOT_RELATIVE / Path(str(entry))
        template = load_template(path)
        cost = _template_increase_per_level_cost(template.key, template.building_body)
        if cost is not None:
            costs[template.key] = cost
    return costs


def _template_increase_per_level_cost(building: str, body: str) -> Decimal | None:
    parsed = parse_text(f"{building} = {{\n{body}\n}}\n")
    block = parsed.entries[0].value
    if not isinstance(block, CList):
        raise ValueError(f"{building}: expected building body block")
    values = block.values("increase_per_level_cost")
    if not values:
        return None
    return Decimal(str(values[-1]))


def _set_compiled_increase_per_level_costs(
    text: str,
    compiled_costs: dict[str, str],
) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    depth = 0
    current_key: str | None = None
    changed = 0

    for index, line in enumerate(lines):
        content, ending = _split_line_ending(line)
        code = _clausewitz_code(content)
        if depth == 0:
            match = re.match(r"^\ufeff?\s*(?P<key>[A-Za-z0-9_:.]+)\s*=\s*\{", code)
            current_key = None if match is None else match.group("key").split(":", 1)[-1]

        if depth == 1 and current_key in compiled_costs:
            match = re.match(
                r"^(?P<indent>[ \t]*)increase_per_level_cost\s*=\s*"
                r"(?P<value>[+-]?(?:\d+(?:\.\d+)?|\.\d+))(?P<suffix>[ \t]*(?:#.*)?)$",
                content,
            )
            if match is not None:
                replacement = (
                    f"{match.group('indent')}increase_per_level_cost = "
                    f"{compiled_costs[current_key]}{match.group('suffix')}{ending}"
                )
                if replacement != line:
                    lines[index] = replacement
                changed += 1

        depth += code.count("{") - code.count("}")
        if depth <= 0:
            depth = 0
            current_key = None

    return "".join(lines), changed


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _clausewitz_code(line: str) -> str:
    in_quote = False
    for index, char in enumerate(line):
        if char == '"':
            in_quote = not in_quote
        elif char == "#" and not in_quote:
            return line[:index]
    return line
