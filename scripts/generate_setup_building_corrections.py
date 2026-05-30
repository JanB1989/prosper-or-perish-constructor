"""Generate pre-tick EU5 setup corrections from setup building errors.

This is an offline build helper. It does not create on_action cleanup or any
other in-game script path; it writes static setup data that EU5 loads before a
bookmark is instantiated.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tomllib
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SETUP_RELATIVE_PATH = Path("main_menu/setup/start/07_cities_and_buildings.txt")
TOWN_SETUPS_RELATIVE_PATH = Path("in_game/common/town_setups/00_default.txt")
LOCATION_TEMPLATES_RELATIVE_PATH = Path("in_game/map_data/location_templates.txt")
GENERATED_TOWN_SETUPS_RELATIVE_PATH = Path(
    "in_game/common/town_setups/zz_pp_sanitized_start_town_setups.txt"
)
DEFAULT_LOAD_ORDER = Path("constructor.load_order.toml")
DEFAULT_PROJECT = Path("constructor.toml")
DEFAULT_LOG_SUFFIX = Path(
    "Documents/Paradox Interactive/Europa Universalis V/logs/error.log"
)

INVALID_RE = re.compile(
    r"Location (?P<location>\S+) has an invalid building (?P<building>\S+)"
)
ABOVE_MAX_RE = re.compile(
    r"\]: (?P<building>\S+) in .+? \((?P<location>[^)]+)\) "
    r"is above max level! Current level is (?P<current>-?\d+) "
    r"\(Max is (?P<max>-?\d+)\)"
)
TOP_LEVEL_HASH_RE = re.compile(r"^# Vanilla setup sha256: (?P<hash>[0-9a-f]{64})$", re.MULTILINE)
KEY_BLOCK_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*\{")
TOKEN_RE = re.compile(r"\b(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*(?P<value>[A-Za-z0-9_:.+-]+)")
TOWN_SETUP_RE = re.compile(r"\btown_setup\s*=\s*(?P<key>[A-Za-z0-9_:.+-]+)")
LOCATION_RE = re.compile(r"\blocation\s*=\s*(?P<key>[A-Za-z0-9_:.+-]+)")
LEVEL_RE = re.compile(r"\blevel\s*=\s*(?P<value>-?\d+)")
LOCATION_TEMPLATE_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*\{(?P<body>.*)\}\s*$")

RAW_MATERIAL_STARTUP_BUILDINGS: dict[str, tuple[str, ...]] = {
    "beeswax": ("farming_village",),
    "fruit": ("fruit_orchard",),
    "horses": ("horse_breeders",),
    "legumes": ("farming_village",),
    "livestock": ("farming_village",),
    "lumber": ("lumber_mill",),
    "maize": ("farming_village",),
    "millet": ("farming_village",),
    "olives": ("farming_village",),
    "potato": ("farming_village",),
    "rice": ("farming_village",),
    "wheat": ("farming_village",),
    "wild_game": ("forest_village",),
    "wool": ("sheep_farms",),
    "fish": ("fishing_village",),
}


@dataclass(frozen=True)
class SetupError:
    location: str
    building: str
    kind: str
    current_level: int | None = None
    max_level: int | None = None


@dataclass(frozen=True)
class CombinedProblem:
    location: str
    building: str
    invalid: bool
    current_level: int | None
    max_level: int | None

    @property
    def desired_total(self) -> int:
        if self.invalid:
            return 0
        if self.max_level is None:
            raise ValueError(f"missing max level for {self.location}:{self.building}")
        return max(self.max_level, 0)


@dataclass(frozen=True)
class LineBlock:
    key: str
    start: int
    end: int


@dataclass(frozen=True)
class LocationEntry:
    location: str
    start: int
    end: int
    town_setup: str | None


@dataclass(frozen=True)
class DirectBuildingEntry:
    index: int
    building: str
    location: str
    level: int
    start: int
    end: int


@dataclass(frozen=True)
class TownSetupDefinition:
    key: str
    copy_from: str | None
    levels: OrderedDict[str, int]


@dataclass(frozen=True)
class LocationTemplate:
    key: str
    raw_material: str | None
    vegetation: str | None
    topography: str | None
    climate: str | None


@dataclass
class SetupModel:
    lines: list[str]
    locations: dict[str, LocationEntry]
    direct_entries: list[DirectBuildingEntry]

    @property
    def direct_by_location_building(self) -> dict[tuple[str, str], list[DirectBuildingEntry]]:
        grouped: dict[tuple[str, str], list[DirectBuildingEntry]] = defaultdict(list)
        for entry in self.direct_entries:
            grouped[(entry.location, entry.building)].append(entry)
        return grouped


@dataclass
class CorrectionPlan:
    setup_hash: str
    town_setups_hash: str
    location_templates_hash: str | None
    setup_lines: list[str]
    sanitized_town_setups: OrderedDict[str, OrderedDict[str, int]]
    location_town_setup_updates: dict[str, str]
    location_town_setup_additions: dict[str, str]
    direct_level_updates: dict[int, int | None]
    parsed_error_count: int
    invalid_error_count: int
    above_max_error_count: int
    implicit_startup_corrections: int
    unresolved: list[CombinedProblem]

    @property
    def direct_removed_count(self) -> int:
        return sum(1 for value in self.direct_level_updates.values() if value is None)

    @property
    def direct_clamped_count(self) -> int:
        return sum(1 for value in self.direct_level_updates.values() if value is not None)


class SetupCorrectionError(RuntimeError):
    """Raised when setup errors cannot be resolved to pre-tick setup data."""


def parse_setup_errors(text: str) -> list[SetupError]:
    errors: list[SetupError] = []
    for line in text.splitlines():
        invalid = INVALID_RE.search(line)
        if invalid is not None:
            errors.append(
                SetupError(
                    location=invalid.group("location"),
                    building=invalid.group("building"),
                    kind="invalid",
                )
            )
            continue

        above = ABOVE_MAX_RE.search(line)
        if above is not None:
            errors.append(
                SetupError(
                    location=above.group("location"),
                    building=above.group("building"),
                    kind="above_max",
                    current_level=int(above.group("current")),
                    max_level=int(above.group("max")),
                )
            )
    return errors


def combine_setup_errors(errors: Iterable[SetupError]) -> OrderedDict[tuple[str, str], CombinedProblem]:
    grouped: dict[tuple[str, str], dict[str, int | bool | None]] = {}
    order: list[tuple[str, str]] = []
    for error in errors:
        key = (error.location, error.building)
        if key not in grouped:
            grouped[key] = {
                "invalid": False,
                "current_level": None,
                "max_level": None,
            }
            order.append(key)
        bucket = grouped[key]
        if error.kind == "invalid":
            bucket["invalid"] = True
        elif error.kind == "above_max":
            bucket["current_level"] = max(
                int(bucket["current_level"] or error.current_level or 0),
                int(error.current_level or 0),
            )
            if bucket["max_level"] is None:
                bucket["max_level"] = error.max_level
            elif error.max_level is not None:
                bucket["max_level"] = min(int(bucket["max_level"]), error.max_level)
        else:
            raise ValueError(f"unknown setup error kind: {error.kind}")

    combined: OrderedDict[tuple[str, str], CombinedProblem] = OrderedDict()
    for location, building in order:
        bucket = grouped[(location, building)]
        combined[(location, building)] = CombinedProblem(
            location=location,
            building=building,
            invalid=bool(bucket["invalid"]),
            current_level=(
                int(bucket["current_level"]) if bucket["current_level"] is not None else None
            ),
            max_level=int(bucket["max_level"]) if bucket["max_level"] is not None else None,
        )
    return combined


def parse_setup_model(text: str) -> SetupModel:
    lines = text.splitlines(keepends=True)
    locations_block = _require_single_block(lines, "locations")
    building_manager_block = _require_single_block(lines, "building_manager")

    locations: dict[str, LocationEntry] = {}
    for block in _child_blocks(lines, locations_block.start + 1, locations_block.end - 1):
        block_text = "".join(lines[block.start : block.end])
        town_setup = _first_match(TOWN_SETUP_RE, block_text)
        locations[block.key] = LocationEntry(
            location=block.key,
            start=block.start,
            end=block.end,
            town_setup=town_setup,
        )

    direct_entries: list[DirectBuildingEntry] = []
    for block in _child_blocks(lines, building_manager_block.start + 1, building_manager_block.end - 1):
        block_text = "".join(lines[block.start : block.end])
        location = _first_match(LOCATION_RE, block_text)
        level_text = _first_match(LEVEL_RE, block_text)
        if location is None or level_text is None:
            continue
        direct_entries.append(
            DirectBuildingEntry(
                index=len(direct_entries),
                building=block.key,
                location=location,
                level=int(level_text),
                start=block.start,
                end=block.end,
            )
        )

    return SetupModel(lines=lines, locations=locations, direct_entries=direct_entries)


def parse_town_setups(text: str) -> OrderedDict[str, TownSetupDefinition]:
    lines = text.splitlines(keepends=True)
    definitions: OrderedDict[str, TownSetupDefinition] = OrderedDict()
    for block in _child_blocks(lines, 0, len(lines)):
        copy_from: str | None = None
        levels: OrderedDict[str, int] = OrderedDict()
        for raw_line in lines[block.start + 1 : block.end - 1]:
            line = _code(raw_line).strip()
            if not line:
                continue
            match = TOKEN_RE.match(line)
            if match is None:
                continue
            key = match.group("key")
            value = match.group("value")
            if key == "copy_from":
                copy_from = value
                continue
            try:
                level = int(value)
            except ValueError:
                continue
            levels[key] = levels.get(key, 0) + level
        definitions[block.key] = TownSetupDefinition(block.key, copy_from, levels)
    return definitions


def parse_location_templates(text: str) -> dict[str, LocationTemplate]:
    templates: dict[str, LocationTemplate] = {}
    for raw_line in text.splitlines():
        line = _code(raw_line)
        match = LOCATION_TEMPLATE_RE.match(line)
        if match is None:
            continue
        values = {
            token.group("key"): token.group("value")
            for token in TOKEN_RE.finditer(match.group("body"))
        }
        key = match.group("key")
        templates[key] = LocationTemplate(
            key=key,
            raw_material=values.get("raw_material"),
            vegetation=values.get("vegetation"),
            topography=values.get("topography"),
            climate=values.get("climate"),
        )
    return templates


def expand_town_setup(
    key: str,
    definitions: dict[str, TownSetupDefinition],
    stack: tuple[str, ...] = (),
) -> OrderedDict[str, int]:
    if key in stack:
        chain = " -> ".join((*stack, key))
        raise SetupCorrectionError(f"recursive town_setup copy_from chain: {chain}")
    if key not in definitions:
        raise SetupCorrectionError(f"unknown town_setup: {key}")

    definition = definitions[key]
    expanded: OrderedDict[str, int] = OrderedDict()
    if definition.copy_from is not None:
        expanded.update(expand_town_setup(definition.copy_from, definitions, (*stack, key)))

    for building, level in definition.levels.items():
        if building in expanded:
            expanded[building] += level
        else:
            expanded[building] = level
    return expanded


def build_correction_plan(
    *,
    setup_text: str,
    town_setups_text: str,
    log_text: str,
    location_templates_text: str | None = None,
    buildings: Iterable[str] | None = None,
    direct_building_manager_only: bool = False,
) -> CorrectionPlan:
    setup_hash = _sha256_text(setup_text)
    town_setups_hash = _sha256_text(town_setups_text)
    location_templates_hash = (
        _sha256_text(location_templates_text) if location_templates_text is not None else None
    )
    selected_buildings = frozenset(buildings or ())
    errors = [
        error
        for error in parse_setup_errors(log_text)
        if not selected_buildings or error.building in selected_buildings
    ]
    combined = combine_setup_errors(errors)
    setup = parse_setup_model(setup_text)
    town_setups = parse_town_setups(town_setups_text)
    location_templates = (
        parse_location_templates(location_templates_text)
        if location_templates_text is not None
        else {}
    )
    direct_by_key = setup.direct_by_location_building

    expanded_by_location: dict[str, OrderedDict[str, int]] = {}
    sanitized_town_setups: OrderedDict[str, OrderedDict[str, int]] = OrderedDict()
    town_setup_updates: dict[str, str] = {}
    town_setup_additions: dict[str, str] = {}
    direct_level_updates: dict[int, int | None] = {}
    unresolved: list[CombinedProblem] = []
    implicit_startup_corrections = 0

    for problem in combined.values():
        location_entry = setup.locations.get(problem.location)
        town_levels = _expanded_town_levels(
            location_entry,
            town_setups,
            expanded_by_location,
        )
        town_level = town_levels.get(problem.building, 0) if town_levels is not None else 0
        direct_entries = direct_by_key.get((problem.location, problem.building), [])
        direct_total = sum(entry.level for entry in direct_entries)
        if direct_building_manager_only and direct_total <= 0:
            continue

        if town_level <= 0 and direct_total <= 0:
            if _apply_implicit_startup_correction(
                problem=problem,
                setup=setup,
                town_setups=town_setups,
                location_templates=location_templates,
                sanitized_town_setups=sanitized_town_setups,
                town_setup_updates=town_setup_updates,
                town_setup_additions=town_setup_additions,
            ):
                implicit_startup_corrections += 1
                continue
            unresolved.append(problem)
            continue

        desired_total = problem.desired_total
        new_town_level = min(town_level, max(0, desired_total - direct_total))
        if town_level != new_town_level:
            if location_entry is None or location_entry.town_setup is None:
                unresolved.append(problem)
                continue
            sanitized = sanitized_town_setups.setdefault(
                problem.location,
                OrderedDict(expanded_town_setup_for_location(problem.location, setup, town_setups)),
            )
            _set_or_remove_level(sanitized, problem.building, new_town_level)
            town_setup_updates[problem.location] = sanitized_town_setup_key(problem.location)

        allowed_direct_total = max(0, desired_total - new_town_level)
        if direct_total > allowed_direct_total:
            _apply_direct_level_budget(
                direct_entries,
                allowed_direct_total,
                direct_level_updates,
            )

    return CorrectionPlan(
        setup_hash=setup_hash,
        town_setups_hash=town_setups_hash,
        location_templates_hash=location_templates_hash,
        setup_lines=setup.lines,
        sanitized_town_setups=sanitized_town_setups,
        location_town_setup_updates=town_setup_updates,
        location_town_setup_additions=town_setup_additions,
        direct_level_updates=direct_level_updates,
        parsed_error_count=len(errors),
        invalid_error_count=sum(1 for error in errors if error.kind == "invalid"),
        above_max_error_count=sum(1 for error in errors if error.kind == "above_max"),
        implicit_startup_corrections=implicit_startup_corrections,
        unresolved=unresolved,
    )


def expanded_town_setup_for_location(
    location: str,
    setup: SetupModel,
    town_setups: dict[str, TownSetupDefinition],
) -> OrderedDict[str, int]:
    entry = setup.locations.get(location)
    if entry is None or entry.town_setup is None:
        return OrderedDict()
    return expand_town_setup(entry.town_setup, town_setups)


def render_setup_override(plan: CorrectionPlan, *, source_label: str) -> str:
    if plan.unresolved:
        raise SetupCorrectionError(_format_unresolved(plan.unresolved))

    lines = list(plan.setup_lines)
    setup = parse_setup_model("".join(lines))
    operations: list[tuple[int, int, list[str]]] = []

    for location, generated_key in plan.location_town_setup_updates.items():
        entry = setup.locations[location]
        block_text = "".join(lines[entry.start : entry.end])
        updated = _set_town_setup_in_location_block(block_text, generated_key)
        operations.append((entry.start, entry.end, updated.splitlines(keepends=True)))

    if plan.location_town_setup_additions:
        locations_block = _require_single_block(lines, "locations")
        addition_lines = [
            "\n",
            "\t# Prosper or Perish generated corrections for implicit startup buildings.\n",
        ]
        for location, generated_key in plan.location_town_setup_additions.items():
            addition_lines.append(f"\t{location} = {{ town_setup = {generated_key} }}\n")
        operations.append((locations_block.end - 1, locations_block.end - 1, addition_lines))

    direct_entries = {entry.index: entry for entry in setup.direct_entries}
    for index, new_level in plan.direct_level_updates.items():
        entry = direct_entries[index]
        block_text = "".join(lines[entry.start : entry.end])
        if new_level is None:
            operations.append((entry.start, entry.end, []))
        else:
            updated = LEVEL_RE.sub(f"level = {new_level}", block_text, count=1)
            operations.append((entry.start, entry.end, updated.splitlines(keepends=True)))

    for start, end, replacement in sorted(operations, key=lambda item: item[0], reverse=True):
        lines[start:end] = replacement

    header = [
        "# Generated by scripts/generate_setup_building_corrections.py; do not edit by hand.\n",
        "# Static setup data loaded before the bookmark is instantiated.\n",
        f"# Source log: {source_label}\n",
        f"# Vanilla setup sha256: {plan.setup_hash}\n",
        f"# Vanilla town_setups sha256: {plan.town_setups_hash}\n",
    ]
    if plan.location_templates_hash is not None:
        header.append(f"# Vanilla location_templates sha256: {plan.location_templates_hash}\n")
    header.append("\n")
    return "".join(header + lines)


def render_sanitized_town_setups(plan: CorrectionPlan, *, source_label: str) -> str:
    if plan.unresolved:
        raise SetupCorrectionError(_format_unresolved(plan.unresolved))

    lines = [
        "# Generated by scripts/generate_setup_building_corrections.py; do not edit by hand.\n",
        "# Location-specific town setups used by the generated 07_cities_and_buildings override.\n",
        "# Static setup data loaded before the bookmark is instantiated.\n",
        f"# Source log: {source_label}\n",
        f"# Vanilla setup sha256: {plan.setup_hash}\n",
        f"# Vanilla town_setups sha256: {plan.town_setups_hash}\n",
    ]
    if plan.location_templates_hash is not None:
        lines.append(f"# Vanilla location_templates sha256: {plan.location_templates_hash}\n")
    lines.append("\n")
    for location, levels in plan.sanitized_town_setups.items():
        lines.append(f"{sanitized_town_setup_key(location)} = {{\n")
        for building, level in levels.items():
            if level > 0:
                lines.append(f"\t{building} = {level}\n")
        lines.append("}\n\n")
    return "".join(lines)


def write_generated_files(
    *,
    plan: CorrectionPlan,
    mod_root: Path,
    source_label: str,
    force: bool = False,
) -> tuple[Path, Path | None]:
    setup_output = mod_root / SETUP_RELATIVE_PATH
    town_output = mod_root / GENERATED_TOWN_SETUPS_RELATIVE_PATH
    _guard_generated_file(setup_output, plan.setup_hash, force=force)

    setup_output.parent.mkdir(parents=True, exist_ok=True)
    setup_output.write_text(
        render_setup_override(plan, source_label=source_label),
        encoding="utf-8-sig",
    )
    if not plan.sanitized_town_setups:
        if town_output.exists():
            _guard_generated_file(town_output, plan.setup_hash, force=force)
            town_output.unlink()
        return setup_output, None

    _guard_generated_file(town_output, plan.setup_hash, force=force)
    town_output.parent.mkdir(parents=True, exist_ok=True)
    town_output.write_text(
        render_sanitized_town_setups(plan, source_label=source_label),
        encoding="utf-8-sig",
    )
    return setup_output, town_output


def sanitized_town_setup_key(location: str) -> str:
    safe_location = re.sub(r"[^A-Za-z0-9_]+", "_", location).strip("_")
    return f"pp_setup_sanitized_{safe_location}"


def default_log_path() -> Path | None:
    candidates: list[Path] = []
    for user_dir in Path("/mnt/c/Users").glob("*"):
        if user_dir.is_dir():
            candidates.append(user_dir / DEFAULT_LOG_SUFFIX)
            candidates.append(user_dir / "OneDrive" / DEFAULT_LOG_SUFFIX)
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime_ns)


def resolve_repo(path: Path | None) -> Path:
    if path is not None:
        return path.resolve()
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / DEFAULT_PROJECT).is_file():
            return candidate
    raise SetupCorrectionError("could not find constructor.toml; pass --repo")


def project_mod_root(repo: Path, project: Path) -> Path:
    raw = tomllib.loads(project.read_text(encoding="utf-8"))
    mod_root = raw.get("project", {}).get("mod_root")
    if not isinstance(mod_root, str) or not mod_root:
        raise SetupCorrectionError(f"{project} is missing [project].mod_root")
    return (repo / mod_root).resolve()


def load_order_vanilla_root(repo: Path, load_order: Path) -> Path:
    raw = tomllib.loads(load_order.read_text(encoding="utf-8"))
    value = raw.get("paths", {}).get("vanilla_root")
    if not isinstance(value, str) or not value:
        raise SetupCorrectionError(f"{load_order} is missing [paths].vanilla_root")
    return _resolve_platform_path(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate pre-tick setup building corrections from EU5 setup errors.",
    )
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--load-order", type=Path, default=DEFAULT_LOAD_ORDER)
    parser.add_argument("--vanilla-root", type=Path, default=None)
    parser.add_argument("--mod-root", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="Write generated mod setup files.")
    parser.add_argument("--force", action="store_true", help="Regenerate over stale generated files.")
    parser.add_argument(
        "--building",
        action="append",
        default=[],
        help="Only correct errors for this building. Can be passed more than once.",
    )
    parser.add_argument(
        "--direct-building-manager-only",
        action="store_true",
        help="Only correct placements that resolve to direct building_manager entries.",
    )
    args = parser.parse_args(argv)

    try:
        repo = resolve_repo(args.repo)
        project = args.project if args.project.is_absolute() else repo / args.project
        load_order = args.load_order if args.load_order.is_absolute() else repo / args.load_order
        vanilla_root = (
            args.vanilla_root.resolve()
            if args.vanilla_root is not None
            else load_order_vanilla_root(repo, load_order)
        )
        mod_root = args.mod_root.resolve() if args.mod_root is not None else project_mod_root(repo, project)
        log_path = args.log or default_log_path()
        if log_path is None:
            raise SetupCorrectionError("could not find EU5 error.log; pass --log")

        setup_path = vanilla_root / "game" / SETUP_RELATIVE_PATH
        town_setups_path = vanilla_root / "game" / TOWN_SETUPS_RELATIVE_PATH
        location_templates_path = vanilla_root / "game" / LOCATION_TEMPLATES_RELATIVE_PATH
        plan = build_correction_plan(
            setup_text=setup_path.read_text(encoding="utf-8-sig"),
            town_setups_text=town_setups_path.read_text(encoding="utf-8-sig"),
            location_templates_text=location_templates_path.read_text(encoding="utf-8-sig"),
            log_text=log_path.read_text(encoding="utf-8", errors="replace"),
            buildings=args.building,
            direct_building_manager_only=args.direct_building_manager_only,
        )
        if plan.unresolved:
            raise SetupCorrectionError(_format_unresolved(plan.unresolved))

        print(f"parsed_errors={plan.parsed_error_count}")
        print(f"invalid_building_errors={plan.invalid_error_count}")
        print(f"above_max_errors={plan.above_max_error_count}")
        print(f"sanitized_town_setups={len(plan.sanitized_town_setups)}")
        print(f"location_town_setup_updates={len(plan.location_town_setup_updates)}")
        print(f"location_town_setup_additions={len(plan.location_town_setup_additions)}")
        print(f"implicit_startup_corrections={plan.implicit_startup_corrections}")
        print(f"direct_entries_removed={plan.direct_removed_count}")
        print(f"direct_entries_clamped={plan.direct_clamped_count}")

        if args.write:
            setup_output, town_output = write_generated_files(
                plan=plan,
                mod_root=mod_root,
                source_label=str(log_path),
                force=args.force,
            )
            print(f"wrote={setup_output}")
            if town_output is not None:
                print(f"wrote={town_output}")
            else:
                print(f"skipped_empty={mod_root / GENERATED_TOWN_SETUPS_RELATIVE_PATH}")
        else:
            print("dry_run=yes")
        return 0
    except SetupCorrectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _expanded_town_levels(
    location_entry: LocationEntry | None,
    town_setups: dict[str, TownSetupDefinition],
    cache: dict[str, OrderedDict[str, int]],
) -> OrderedDict[str, int] | None:
    if location_entry is None or location_entry.town_setup is None:
        return None
    if location_entry.location not in cache:
        cache[location_entry.location] = expand_town_setup(location_entry.town_setup, town_setups)
    return cache[location_entry.location]


def _apply_direct_level_budget(
    entries: list[DirectBuildingEntry],
    allowed_total: int,
    direct_level_updates: dict[int, int | None],
) -> None:
    remaining = allowed_total
    for entry in entries:
        if remaining <= 0:
            direct_level_updates[entry.index] = None
            continue
        if entry.level <= remaining:
            remaining -= entry.level
            continue
        direct_level_updates[entry.index] = remaining
        remaining = 0


def _apply_implicit_startup_correction(
    *,
    problem: CombinedProblem,
    setup: SetupModel,
    town_setups: dict[str, TownSetupDefinition],
    location_templates: dict[str, LocationTemplate],
    sanitized_town_setups: OrderedDict[str, OrderedDict[str, int]],
    town_setup_updates: dict[str, str],
    town_setup_additions: dict[str, str],
) -> bool:
    template = location_templates.get(problem.location)
    if template is None or not _matches_implicit_startup_building(problem, template):
        return False

    sanitized = sanitized_town_setups.setdefault(
        problem.location,
        OrderedDict(expanded_town_setup_for_location(problem.location, setup, town_setups)),
    )
    _set_or_remove_level(sanitized, problem.building, problem.desired_total)

    generated_key = sanitized_town_setup_key(problem.location)
    if problem.location in setup.locations:
        town_setup_updates[problem.location] = generated_key
    else:
        town_setup_additions[problem.location] = generated_key
    return True


def _matches_implicit_startup_building(
    problem: CombinedProblem,
    template: LocationTemplate,
) -> bool:
    if template.raw_material is not None:
        candidates = RAW_MATERIAL_STARTUP_BUILDINGS.get(template.raw_material, ())
        if problem.building in candidates:
            return True
    return (
        problem.building == "forest_village"
        and template.vegetation in {"forest", "woods", "jungle"}
    )


def _set_or_remove_level(levels: OrderedDict[str, int], building: str, level: int) -> None:
    if level <= 0:
        levels.pop(building, None)
    elif building in levels:
        levels[building] = level
    else:
        levels[building] = level


def _set_town_setup_in_location_block(block_text: str, generated_key: str) -> str:
    if TOWN_SETUP_RE.search(block_text):
        return TOWN_SETUP_RE.sub(f"town_setup = {generated_key}", block_text, count=1)

    stripped = block_text.rstrip()
    trailing = block_text[len(stripped) :]
    if stripped.endswith("}"):
        return f"{stripped[:-1].rstrip()} town_setup = {generated_key} }}{trailing}"
    raise SetupCorrectionError("location block has no closing brace")


def _guard_generated_file(path: Path, setup_hash: str, *, force: bool) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    match = TOP_LEVEL_HASH_RE.search(text)
    if match is None:
        if force:
            return
        raise SetupCorrectionError(
            f"{path} exists but is not recognized as generated; pass --force to overwrite"
        )
    old_hash = match.group("hash")
    if old_hash != setup_hash and not force:
        raise SetupCorrectionError(
            f"{path} was generated from vanilla setup {old_hash}, current is {setup_hash}; "
            "pass --force after reviewing upstream setup drift"
        )


def _format_unresolved(problems: list[CombinedProblem]) -> str:
    examples = ", ".join(f"{p.location}:{p.building}" for p in problems[:20])
    suffix = "" if len(problems) <= 20 else f", ... +{len(problems) - 20} more"
    return f"unresolved setup building errors ({len(problems)}): {examples}{suffix}"


def _require_single_block(lines: list[str], key: str) -> LineBlock:
    blocks = [block for block in _child_blocks(lines, 0, len(lines)) if block.key == key]
    if len(blocks) != 1:
        raise SetupCorrectionError(f"expected one {key} block, found {len(blocks)}")
    return blocks[0]


def _child_blocks(lines: list[str], start: int, end: int) -> list[LineBlock]:
    blocks: list[LineBlock] = []
    depth = 0
    current_key: str | None = None
    current_start = -1
    for index in range(start, end):
        code = _code(lines[index])
        if current_key is None and depth == 0:
            match = KEY_BLOCK_RE.match(code)
            if match is not None:
                current_key = match.group("key")
                current_start = index
        depth += code.count("{") - code.count("}")
        if current_key is not None and depth == 0:
            blocks.append(LineBlock(current_key, current_start, index + 1))
            current_key = None
            current_start = -1
        if depth < 0:
            raise SetupCorrectionError(f"unbalanced braces near line {index + 1}")
    if current_key is not None or depth != 0:
        raise SetupCorrectionError("unbalanced braces while reading setup blocks")
    return blocks


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return next(iter(match.groupdict().values()))


def _code(line: str) -> str:
    return line.split("#", 1)[0]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_platform_path(value: str) -> Path:
    path = Path(value).expanduser()
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", str(path))
    if match is not None and os.name != "nt":
        drive = match.group(1).lower()
        tail = match.group(2).replace("\\", "/")
        return (Path("/mnt") / drive / tail).resolve()
    return path.resolve()


if __name__ == "__main__":
    raise SystemExit(main())
