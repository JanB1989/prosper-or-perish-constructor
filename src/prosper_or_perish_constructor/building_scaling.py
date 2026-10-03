from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
import tomllib
from typing import Any

from eu5_building_pipeline.template import load_template
from eu5_mod_orchestrator.blueprints import enabled_manifest_entries
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from prosper_or_perish_constructor import yaml_io


CONFIG_SECTION = "building_scaling"
INCREASE_PER_LEVEL_COST_MULTIPLIER_FIELD = "increase_per_level_cost_multiplier"
BURGHER_BUILDING_EMPLOYMENT_SIZE_FIELD = "burgher_building_employment_size"
BUILDING_BLUEPRINT_MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
BUILDING_BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
BUILDING_TYPES_RELATIVE = Path("in_game/common/building_types")
EMPLOYMENT_SIZE_STEP = Decimal("0.05")


@dataclass(frozen=True)
class BuildingScalingConfig:
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
        increase_per_level_cost_multiplier=increase_cost_multiplier,
        burgher_building_employment_size=burgher_employment_size,
    )


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
    if not manifest_path.is_file():
        return {}
    raw = yaml_io.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path}: expected mapping")

    costs: dict[str, Decimal] = {}
    for entry in enabled_manifest_entries(raw.get("enabled", []), source=manifest_path):
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


# ---------------------------------------------------------------------------------------------------- employment cut
EMPLOYMENT_CUT_SECTION = "employment_cut"
# written after the new size; the footprint (building_footprint._employment) reads the reference back from it
EMPLOYMENT_CUT_MARKER = "[building_scaling.employment_cut] reference"
_POP_TYPE_RE = re.compile(r"^[ \t]*pop_type\s*=\s*(?P<pop>\w+)", re.MULTILINE)
_EMPLOYMENT_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)employment_size\s*=\s*(?P<value>[^\s#{}]+)(?P<rest>[^\n]*)$", re.MULTILINE)
_REFERENCE_RE = re.compile(re.escape(EMPLOYMENT_CUT_MARKER) + r"\s+(?P<ref>[0-9.]+)")


@dataclass(frozen=True)
class EmploymentCut:
    reference: Decimal
    employment: Decimal


@dataclass
class EmploymentCutResult:
    buildings: dict[str, int]
    files_changed: int


def load_employment_cut(path: Path) -> dict[str, EmploymentCut]:
    """[building_scaling.employment_cut]: pop type -> (reference employment_size, new employment_size)."""
    raw = tomllib.loads(path.read_text(encoding="utf-8-sig")).get(CONFIG_SECTION, {}).get(EMPLOYMENT_CUT_SECTION, {})
    cuts = {}
    for pop, spec in dict(raw).items():
        cut = EmploymentCut(_decimal_config_value(spec["reference"], f"{pop}.reference"),
                            _decimal_config_value(spec["employment"], f"{pop}.employment"))
        if cut.reference <= 0 or cut.employment <= 0:
            raise ValueError(f"{path}: [{CONFIG_SECTION}.{EMPLOYMENT_CUT_SECTION}] {pop}: sizes must be positive")
        cuts[str(pop)] = cut
    return cuts


def employment_reference(line_rest: str) -> Decimal | None:
    """The reference employment recorded on a cut employment_size line, else None."""
    match = _REFERENCE_RE.search(line_rest)
    return Decimal(match.group("ref")) if match else None


def apply_employment_cut(mod_root: Path, project: Path, vanilla_root: Path) -> EmploymentCutResult:
    """Set employment_size of every mod-defined building (CREATE/REPLACE) of a configured pop type whose size is the
    reference to the cut size, recording the reference on the line. Idempotent: a line that already carries the marker
    is recomputed from its reference. Runs after the footprint, which keeps the reference."""
    from prosper_or_perish_constructor import building_footprint as bf

    cuts = load_employment_cut(project)
    result = EmploymentCutResult(buildings={pop: 0 for pop in cuts}, files_changed=0)
    if not cuts:
        return result
    edits: dict[Path, list[tuple[int, int, str]]] = {}
    for key, block in bf.owner_blocks(mod_root, vanilla_root).items():
        if block.mode in bf._INJECT_MODES:
            continue
        text = bf._read(block.path)
        body = text[block.open + 1: block.close]
        tops = bf._depth_zero_text(body)  # same length as body: nested blocks blanked
        pop = _POP_TYPE_RE.search(tops)
        line = _EMPLOYMENT_LINE_RE.search(tops)
        if not pop or not line or pop.group("pop") not in cuts:
            continue
        cut = cuts[pop.group("pop")]
        rest = body[line.start("rest"): line.end("rest")]
        try:
            current = employment_reference(rest) or Decimal(line.group("value"))
        except ArithmeticError:
            continue  # a script value name: not a plain size
        if current != cut.reference:
            continue
        new_line = f"{line.group('indent')}employment_size = {_fmt_size(cut.employment)}   # {EMPLOYMENT_CUT_MARKER} {_fmt_size(cut.reference)}"
        start = block.open + 1 + line.start()
        end = block.open + 1 + line.end()
        edits.setdefault(block.path, []).append((start, end, new_line))
        result.buildings[pop.group("pop")] += 1
    for path, items in edits.items():
        text = bf._read(path)
        new = text
        for start, end, line in sorted(items, key=lambda item: -item[0]):
            new = new[:start] + line + new[end:]
        if new != text:
            path.write_text(new, encoding="utf-8-sig", newline="\n")
            result.files_changed += 1
    return result


def _fmt_size(value: Decimal) -> str:
    return format(value.normalize(), "f")
