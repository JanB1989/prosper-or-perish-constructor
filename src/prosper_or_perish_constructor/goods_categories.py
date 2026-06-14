from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
import tomllib
from typing import Any

import polars as pl
import yaml
from eu5_building_pipeline.template import load_template
from eu5gameparser.domain.buildings import load_building_data


GOODS_CATEGORIES_RELATIVE = Path("config/goods_categories.csv")
GOODS_CATEGORY_SCALING_RELATIVE = Path("config/goods_category_scaling.toml")
BUILDING_BLUEPRINT_MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
BUILDING_BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
INCREASE_PER_LEVEL_COST_FIELD = "increase_per_level_cost"
INCREASE_PER_LEVEL_COST_EXPLANATION_FIELD = "increase_per_level_cost_explanation"


@dataclass(frozen=True)
class CostScalingBand:
    minimum: Decimal
    maximum: Decimal


@dataclass(frozen=True)
class GoodCategoryCost:
    good: str
    normalized_cost: Decimal
    scaled_cost: Decimal
    scaled_cost_text: str


@dataclass(frozen=True)
class ProducedGoodCandidate:
    building: str
    method: str
    good: str
    output: float
    output_value: float


@dataclass(frozen=True)
class BuildingIncreaseCostAssignment:
    building: str
    main_good: str
    method: str
    output_value: float
    normalized_cost: Decimal
    scaled_cost: Decimal
    scaled_cost_text: str
    blueprint_path: Path | None


def load_increase_per_level_cost_band(
    path: Path,
    *,
    field: str = INCREASE_PER_LEVEL_COST_FIELD,
) -> CostScalingBand:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    section = raw.get(field)
    if not isinstance(section, dict):
        raise ValueError(f"{path}: missing [{field}] section")

    minimum = _decimal_config_value(section.get("min"), f"{field}.min")
    maximum = _decimal_config_value(section.get("max"), f"{field}.max")
    if minimum < 0 or maximum > 1 or minimum >= maximum:
        raise ValueError(f"{path}: expected 0 <= {field}.min < {field}.max <= 1")
    return CostScalingBand(minimum=minimum, maximum=maximum)


def load_good_category_costs(csv_path: Path, band: CostScalingBand) -> dict[str, GoodCategoryCost]:
    costs: dict[str, GoodCategoryCost] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            good = row["good"]
            normalized = Decimal(row[INCREASE_PER_LEVEL_COST_FIELD])
            scaled = scale_increase_per_level_cost(normalized, band)
            costs[good] = GoodCategoryCost(
                good=good,
                normalized_cost=normalized,
                scaled_cost=scaled,
                scaled_cost_text=format_scaled_cost(scaled),
            )
    return costs


def scale_increase_per_level_cost(normalized_cost: Decimal, band: CostScalingBand) -> Decimal:
    if normalized_cost < 0 or normalized_cost > 1:
        raise ValueError(f"normalized cost must be between 0 and 1: {normalized_cost}")
    return band.minimum + normalized_cost * (band.maximum - band.minimum)


def format_scaled_cost(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def building_increase_cost_assignments(
    repo: Path,
    project: Path | None = None,
) -> tuple[BuildingIncreaseCostAssignment, ...]:
    project = project or repo / "constructor.toml"
    profile, load_order_path = _project_parser_config(repo, project)
    band = load_increase_per_level_cost_band(repo / GOODS_CATEGORY_SCALING_RELATIVE)
    costs_by_good = load_good_category_costs(repo / GOODS_CATEGORIES_RELATIVE, band)
    building_data = load_building_data(profile=profile, load_order_path=load_order_path)
    candidates_by_building = _produced_good_candidates_by_building(
        building_data.production_methods,
        building_data.buildings,
        set(costs_by_good),
    )
    blueprint_paths_by_building = accepted_blueprint_paths_by_building(repo)

    assignments: list[BuildingIncreaseCostAssignment] = []
    for building, candidates in sorted(candidates_by_building.items()):
        main = max(
            candidates,
            key=lambda item: (item.output_value, item.output, item.good, item.method),
        )
        good_cost = costs_by_good[main.good]
        assignments.append(
            BuildingIncreaseCostAssignment(
                building=building,
                main_good=main.good,
                method=main.method,
                output_value=main.output_value,
                normalized_cost=good_cost.normalized_cost,
                scaled_cost=good_cost.scaled_cost,
                scaled_cost_text=good_cost.scaled_cost_text,
                blueprint_path=blueprint_paths_by_building.get(building),
            )
        )
    return tuple(assignments)


def accepted_blueprint_paths_by_building(repo: Path) -> dict[str, Path]:
    manifest_path = repo / BUILDING_BLUEPRINT_MANIFEST_RELATIVE
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    enabled = raw.get("enabled") if isinstance(raw, dict) else None
    if not isinstance(enabled, list):
        raise ValueError(f"{manifest_path}: expected enabled list")

    paths_by_building: dict[str, Path] = {}
    for entry in enabled:
        relative = Path(str(entry))
        path = repo / BUILDING_BLUEPRINT_ROOT_RELATIVE / relative
        template = load_template(path)
        if template.key in paths_by_building:
            raise ValueError(f"Multiple building blueprints target {template.key}")
        paths_by_building[template.key] = path
    return paths_by_building


def write_building_increase_cost_blueprints(
    repo: Path,
    project: Path | None = None,
) -> tuple[BuildingIncreaseCostAssignment, ...]:
    assignments = building_increase_cost_assignments(repo, project)
    manifest_entries_to_append: list[str] = []

    for assignment in assignments:
        if assignment.blueprint_path is None:
            relative_entry = Path("buildings") / f"{assignment.building}.yml"
            path = repo / BUILDING_BLUEPRINT_ROOT_RELATIVE / relative_entry
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_text_if_changed(path, _new_cost_inject_blueprint(assignment), encoding="utf-8")
            manifest_entries_to_append.append(relative_entry.as_posix())
            continue

        text = _read_text_preserving_newlines(assignment.blueprint_path, encoding="utf-8")
        updated = set_blueprint_body_increase_cost(text, assignment.scaled_cost_text)
        _write_text_if_changed(assignment.blueprint_path, updated, encoding="utf-8")

    if manifest_entries_to_append:
        _append_manifest_entries(repo / BUILDING_BLUEPRINT_MANIFEST_RELATIVE, manifest_entries_to_append)

    return assignments


def set_blueprint_body_increase_cost(text: str, cost: str) -> str:
    match = _body_block_match(text)
    updated_body = _set_raw_body_block_increase_cost(match.group("body"), cost)
    return text[: match.start("body")] + updated_body + text[match.end("body") :]


def set_body_increase_cost(body: str, cost: str) -> str:
    lines = body.splitlines()
    replacement_index: int | None = None
    replacement_indent = ""
    for index, line in enumerate(lines):
        match = re.match(r"^([ \t]*)increase_per_level_cost\s*=", line)
        if match is not None:
            replacement_index = index
            replacement_indent = match.group(1)
            break

    if replacement_index is not None:
        lines[replacement_index] = f"{replacement_indent}increase_per_level_cost = {cost}"
        return "\n".join(lines).rstrip()

    insert_index = _increase_cost_insert_index(lines)
    indent = _top_level_indent(lines)
    lines.insert(insert_index, f"{indent}increase_per_level_cost = {cost}")
    return "\n".join(lines).rstrip()


def _produced_good_candidates_by_building(
    production_methods: pl.DataFrame,
    buildings: pl.DataFrame,
    categorized_goods: set[str],
) -> dict[str, list[ProducedGoodCandidate]]:
    candidates: dict[str, list[ProducedGoodCandidate]] = {}

    for row in (
        production_methods.filter(
            pl.col("building").is_not_null() & pl.col("produced").is_in(list(categorized_goods))
        )
        .select(["building", "name", "produced", "output", "output_value"])
        .to_dicts()
    ):
        _append_candidate(candidates, row["building"], row, row["name"])

    global_methods = {
        row["name"]: row
        for row in production_methods.filter(
            (pl.col("source_kind") == "global") & pl.col("produced").is_in(list(categorized_goods))
        )
        .select(["name", "produced", "output", "output_value"])
        .to_dicts()
    }
    for building in buildings.select(["name", "possible_production_methods"]).to_dicts():
        for method in building["possible_production_methods"]:
            row = global_methods.get(method)
            if row is not None:
                _append_candidate(candidates, building["name"], row, method)

    return candidates


def _append_candidate(
    candidates: dict[str, list[ProducedGoodCandidate]],
    building: Any,
    row: dict[str, Any],
    method: Any,
) -> None:
    output = float(row.get("output") or 0.0)
    output_value = float(row.get("output_value") or 0.0)
    if output <= 0 and output_value <= 0:
        return
    candidates.setdefault(str(building), []).append(
        ProducedGoodCandidate(
            building=str(building),
            method=str(method),
            good=str(row["produced"]),
            output=output,
            output_value=output_value,
        )
    )


def _project_parser_config(repo: Path, project: Path) -> tuple[str, Path]:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    parser = raw.get("parser", {})
    profile = str(parser.get("profile", "constructor"))
    load_order = repo / str(parser.get("load_order", "constructor.load_order.toml"))
    return profile, load_order


def _decimal_config_value(value: Any, name: str) -> Decimal:
    if not isinstance(value, int | float | str):
        raise ValueError(f"Expected numeric config value for {name}")
    return Decimal(str(value))


def _new_cost_inject_blueprint(assignment: BuildingIncreaseCostAssignment) -> str:
    return (
        "version: 2\n"
        f"tag: {assignment.building}\n"
        "building:\n"
        f"  key: {assignment.building}\n"
        "  mode: TRY_INJECT\n"
        "  source: pp_building_cost_scaling.txt\n"
        "  production_method_slots: []\n"
        "  possible_production_methods: []\n"
        "  body: |2-\n"
        f"    increase_per_level_cost = {assignment.scaled_cost_text}\n"
    )


def _extract_blueprint_body(text: str) -> str:
    match = _body_block_match(text)
    body_lines = match.group("body").splitlines()
    return "\n".join(line[4:] if line.startswith("    ") else "" for line in body_lines).rstrip()


def _replace_blueprint_body(text: str, body: str) -> str:
    match = _body_block_match(text)
    replacement = match.group("header") + "\n".join(f"    {line}" for line in body.splitlines()) + "\n"
    return text[: match.start()] + replacement + text[match.end() :]


def _body_block_match(text: str) -> re.Match[str]:
    match = re.search(
        r"(?m)^(?P<header>  body:\s*\|[^\n]*\n)(?P<body>(?:(?:    [^\n]*)?\n)*)",
        text,
    )
    if match is None:
        raise ValueError("Blueprint does not contain building.body block scalar")
    return match


def _set_raw_body_block_increase_cost(body_text: str, cost: str) -> str:
    lines = body_text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in body_text else "\n"

    for index, line in enumerate(lines):
        body_line, ending = _yaml_body_line_content(line)
        match = re.match(r"^([ \t]*)increase_per_level_cost\s*=", body_line)
        if match is not None:
            lines[index] = f"    {match.group(1)}increase_per_level_cost = {cost}{ending or newline}"
            return "".join(lines)

    insert_index = 0
    for index, line in enumerate(lines):
        body_line, _ending = _yaml_body_line_content(line)
        if re.match(r"^[ \t]*is_foreign\s*=", body_line):
            insert_index = index + 1
            break
    else:
        for index, line in enumerate(lines):
            body_line, _ending = _yaml_body_line_content(line)
            if body_line.strip():
                insert_index = index
                break

    indent = _raw_body_top_level_indent(lines)
    lines.insert(insert_index, f"    {indent}increase_per_level_cost = {cost}{newline}")
    return "".join(lines)


def _yaml_body_line_content(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        content = line[:-2]
        ending = "\r\n"
    elif line.endswith("\n"):
        content = line[:-1]
        ending = "\n"
    else:
        content = line
        ending = ""
    if content.startswith("    "):
        return content[4:], ending
    if not content.strip():
        return "", ending
    return content, ending


def _raw_body_top_level_indent(lines: list[str]) -> str:
    for line in lines:
        body_line, _ending = _yaml_body_line_content(line)
        if not body_line.strip():
            continue
        match = re.match(r"^([ \t]*)", body_line)
        indent = "" if match is None else match.group(1)
        return "" if "\t" in indent else indent
    return ""


def _increase_cost_insert_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if re.match(r"^[ \t]*is_foreign\s*=", line):
            return index + 1
    for index, line in enumerate(lines):
        if line.strip():
            return index
    return 0


def _top_level_indent(lines: list[str]) -> str:
    for line in lines:
        if not line.strip():
            continue
        match = re.match(r"^([ \t]*)", line)
        return "" if match is None else match.group(1)
    return ""


def _append_manifest_entries(manifest_path: Path, entries: list[str]) -> None:
    existing = _read_text_preserving_newlines(manifest_path, encoding="utf-8")
    suffix = "" if existing.endswith("\n") else "\n"
    addition = "".join(f"- {entry}\n" for entry in sorted(entries))
    _write_text_if_changed(manifest_path, existing + suffix + addition, encoding="utf-8")


def _write_text_if_changed(path: Path, text: str, *, encoding: str) -> None:
    existing = _read_text_preserving_newlines(path, encoding=encoding) if path.exists() else None
    if existing == text:
        return
    with path.open("w", encoding=encoding, newline="") as handle:
        handle.write(text)


def _read_text_preserving_newlines(path: Path, *, encoding: str) -> str:
    with path.open("r", encoding=encoding, newline="") as handle:
        return handle.read()
