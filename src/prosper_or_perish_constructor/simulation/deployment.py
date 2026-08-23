"""Compile the population simulation's year-0 state into EU5 game data."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor.simulation.capacity_model import (
    BASE_POPULATION_CAPACITY_COLUMN,
    INFRASTRUCTURE_POPULATION_CAPACITY_COLUMN,
    IRRIGATION_LEVELS_COLUMN,
)
from prosper_or_perish_constructor.simulation.profile import (
    GENERATED_IRRIGATION_LEVELS_COLUMN,
    START_COUNTRY_TAG_COLUMN,
    SimulationProfile,
    load_population_simulation_profile,
    prepare_population_simulation_state,
    _generated_infrastructure_levels_column,
)
from prosper_or_perish_population_capacity.merge import load_collection, profile_from


GENERATED_MARKER = (
    "# Generated from population_capacity_simulation.toml by the constructor; "
    "do not edit by hand."
)
LOCATION_COUNT = 20_929
LOCATION_TAG_RE = re.compile(r"^[A-Za-z0-9_:.+-]+$")
LOCATION_MODIFIER_ALIASES = {"washita": "pp_loc_washita_pp"}
DEVELOPMENT_SELECTOR_COLUMNS = (
    "province",
    "area",
    "region",
    "location_rank",
    "climate",
    "topography",
    "vegetation",
)
DEVELOPMENT_WEIGHTED_SELECTOR_KEYS = frozenset(
    {"base", "coastal", "river", "road"}
)


@dataclass(frozen=True)
class PopulationDeploymentResult:
    profile: SimulationProfile
    capacity_table_path: Path
    development_setup_path: Path
    irrigation_setup_path: Path
    manifest_path: Path
    location_count: int
    irrigation_locations: int
    irrigation_levels: int
    starting_capacity_values: tuple[int, ...]
    changed_paths: tuple[Path, ...]


@dataclass(frozen=True)
class DevelopmentSetupCompilation:
    rows: tuple[tuple[str, float], ...]
    coefficient_decimals: int
    selector_collision_keys: tuple[str, ...]
    maximum_effective_error: float


def build_population_simulation_deployment(
    *,
    repo: Path,
    project: Path,
    profile_path: Path,
) -> PopulationDeploymentResult:
    """Write the one canonical capacity/development/irrigation deployment."""

    profile = load_population_simulation_profile(profile_path, repo=repo)
    state, _context, preparation = prepare_population_simulation_state(
        repo,
        project,
        profile,
    )
    state = state.sort("location_tag")
    if state.height != LOCATION_COUNT or state["location_tag"].n_unique() != state.height:
        raise ValueError(
            f"population deployment covers {state.height} unique-location rows; "
            f"expected {LOCATION_COUNT}"
        )
    invalid_tags = [
        str(tag)
        for tag in state["location_tag"].to_list()
        if not LOCATION_TAG_RE.fullmatch(str(tag))
    ]
    if invalid_tags:
        raise ValueError(f"population deployment contains invalid location tags: {invalid_tags[:8]}")

    capacity_rows = [
        {
            "location_tag": str(row["location_tag"]),
            "population_capacity": int(row["deployed_static_population_capacity"]),
        }
        for row in state.select(
            "location_tag",
            "deployed_static_population_capacity",
        ).to_dicts()
    ]
    development_rows = [
        (str(row["location_tag"]), float(row["development"]))
        for row in state.select("location_tag", "development").to_dicts()
    ]
    infrastructure_rows: list[tuple[str, str, str, int]] = []
    for building in profile.infrastructure_capacity_per_level:
        column = _generated_infrastructure_levels_column(building)
        infrastructure_rows.extend(
            (
                building,
                str(row["location_tag"]),
                str(row[START_COUNTRY_TAG_COLUMN]),
                int(row[column]),
            )
            for row in state.filter(pl.col(column) > 0).select(
                "location_tag",
                START_COUNTRY_TAG_COLUMN,
                column,
            ).to_dicts()
        )
    missing_owners = [
        tag for _building, tag, owner, _level in infrastructure_rows if not owner
    ]
    if missing_owners:
        raise ValueError(
            "generated irrigation placements require game-start owners: "
            f"{missing_owners[:8]}"
        )
    starting_capacity = profile.capacity_formula.evaluate(
        base_capacity=state[BASE_POPULATION_CAPACITY_COLUMN].to_numpy(),
        development=state["development"].to_numpy(),
        infrastructure_capacity=state[
            INFRASTRUCTURE_POPULATION_CAPACITY_COLUMN
        ].to_numpy(),
    )
    starting_capacity_values = tuple(
        int(math.ceil(float(value) - 1e-12)) for value in starting_capacity
    )

    capacity_text = _render_capacity_csv(capacity_rows)
    development_compilation = _compile_development_setup_rows(
        development_rows,
        state=state,
        target_decimals=profile.deployment_development_decimals,
    )
    development_text = _render_development_setup(
        list(development_compilation.rows),
        decimals=development_compilation.coefficient_decimals,
    )
    irrigation_text = _render_infrastructure_setup(infrastructure_rows)
    changed: list[Path] = []
    for path, text in (
        (profile.deployment_population_capacity_table_path, capacity_text),
        (profile.deployment_development_setup_path, development_text),
        (profile.deployment_irrigation_setup_path, irrigation_text),
    ):
        if _write_if_changed(path, text):
            changed.append(path)

    formula = profile.capacity_formula
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "source_profile": str(profile.path.relative_to(repo)),
        "location_count": state.height,
        "starting_population_is_capacity_input": False,
        "capacity_table": str(profile.deployment_population_capacity_table_path.relative_to(repo)),
        "capacity_table_sha256": _sha256_text(capacity_text),
        "development_setup": str(profile.deployment_development_setup_path.relative_to(repo)),
        "development_setup_sha256": _sha256_text(development_text),
        "irrigation_setup": str(profile.deployment_irrigation_setup_path.relative_to(repo)),
        "irrigation_setup_sha256": _sha256_text(irrigation_text),
        "development": {
            "decimals": profile.deployment_development_decimals,
            "setup_coefficient_decimals": (
                development_compilation.coefficient_decimals
            ),
            "selector_collision_keys": list(
                development_compilation.selector_collision_keys
            ),
            "maximum_effective_error": (
                development_compilation.maximum_effective_error
            ),
            "minimum": float(state["development"].min()),
            "mean": float(state["development"].mean()),
            "maximum": float(state["development"].max()),
            "absolute_capacity_per_point": 0.0,
            "relative_capacity_per_point": formula.development_relative,
        },
        "infrastructure": {
            "generated_locations": len(infrastructure_rows),
            "generated_levels": sum(
                level for _building, _tag, _owner, level in infrastructure_rows
            ),
            "capacity_per_level": dict(profile.infrastructure_capacity_per_level),
            "placement": preparation.get("infrastructure", {}),
        },
        "irrigation": {
            "generated_locations": sum(
                building == "irrigation_systems"
                for building, _tag, _owner, _level in infrastructure_rows
            ),
            "generated_levels": sum(
                level
                for building, _tag, _owner, level in infrastructure_rows
                if building == "irrigation_systems"
            ),
            "total_starting_locations": int(
                state.filter(pl.col(IRRIGATION_LEVELS_COLUMN) > 0).height
            ),
            "total_starting_levels": int(state[IRRIGATION_LEVELS_COLUMN].sum()),
            "absolute_capacity_per_level": profile.infrastructure_capacity_per_level[
                "irrigation_systems"
            ],
            "relative_capacity_per_level": 0.0,
            **preparation.get("irrigation", {}),
        },
        "static_capacity": {
            "minimum": int(state["deployed_static_population_capacity"].min()),
            "mean": float(state["deployed_static_population_capacity"].mean()),
            "maximum": int(state["deployed_static_population_capacity"].max()),
            "gaez_zero_development_fraction": profile.gaez_zero_development_fraction,
            "physical_density_reference_people_per_km2": (
                profile.physical_density_reference_people_per_km2
            ),
            "physical_density_elasticity": profile.physical_density_elasticity,
            "location_area_exponent": profile.location_area_exponent,
            "minimum_final_capacity": formula.minimum_capacity,
        },
        "starting_capacity": {
            "minimum": min(starting_capacity_values),
            "mean": sum(starting_capacity_values) / len(starting_capacity_values),
            "maximum": max(starting_capacity_values),
        },
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if _write_if_changed(profile.deployment_manifest_path, manifest_text):
        changed.append(profile.deployment_manifest_path)
    return PopulationDeploymentResult(
        profile=profile,
        capacity_table_path=profile.deployment_population_capacity_table_path,
        development_setup_path=profile.deployment_development_setup_path,
        irrigation_setup_path=profile.deployment_irrigation_setup_path,
        manifest_path=profile.deployment_manifest_path,
        location_count=state.height,
        irrigation_locations=sum(
            building == "irrigation_systems"
            for building, _tag, _owner, _level in infrastructure_rows
        ),
        irrigation_levels=sum(
            level
            for building, _tag, _owner, level in infrastructure_rows
            if building == "irrigation_systems"
        ),
        starting_capacity_values=starting_capacity_values,
        changed_paths=tuple(changed),
    )


def verify_population_simulation_deployment(
    *,
    repo: Path,
    project: Path,
    profile_path: Path,
    location_modifiers_path: Path,
) -> dict[str, Any]:
    """Verify generated setup files and parser-visible modifier coefficients."""

    profile = load_population_simulation_profile(profile_path, repo=repo)
    manifest_path = profile.deployment_manifest_path
    if not manifest_path.is_file():
        raise ValueError(f"population deployment manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files = (
        (
            profile.deployment_population_capacity_table_path,
            "capacity_table_sha256",
        ),
        (profile.deployment_development_setup_path, "development_setup_sha256"),
        (profile.deployment_irrigation_setup_path, "irrigation_setup_sha256"),
    )
    for path, hash_key in expected_files:
        if not path.is_file():
            raise ValueError(f"population deployment output is missing: {path}")
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != manifest.get(hash_key):
            raise ValueError(f"population deployment checksum mismatch: {path}")

    with profile.deployment_population_capacity_table_path.open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        capacity_rows = list(csv.DictReader(handle))
    if len(capacity_rows) != LOCATION_COUNT:
        raise ValueError(
            f"population capacity compiler table has {len(capacity_rows)} rows; "
            f"expected {LOCATION_COUNT}"
        )
    expected_capacity = {
        str(row["location_tag"]).lower(): int(row["population_capacity"])
        for row in capacity_rows
    }
    rendered_capacity = _parsed_location_capacity(location_modifiers_path)
    mismatches = [
        tag
        for tag, value in expected_capacity.items()
        if rendered_capacity.get(tag) != value
    ]
    if mismatches or len(rendered_capacity) != len(expected_capacity):
        raise ValueError(
            "compiled location modifiers do not match the profile capacity table; "
            f"mismatches={mismatches[:8]}, rendered={len(rendered_capacity)}, "
            f"expected={len(expected_capacity)}"
        )

    development_count = _verify_development_setup(
        profile.deployment_development_setup_path
    )
    irrigation_locations, irrigation_levels = _verify_irrigation_setup(
        profile.deployment_irrigation_setup_path
    )
    if development_count != int(manifest["location_count"]):
        raise ValueError("generated development setup location count does not match manifest")
    expected_irrigation = manifest["irrigation"]
    if irrigation_locations != int(expected_irrigation["generated_locations"]):
        raise ValueError("generated irrigation location count does not match manifest")
    if irrigation_levels != int(expected_irrigation["generated_levels"]):
        raise ValueError("generated irrigation level total does not match manifest")
    development_manifest = dict(manifest.get("development") or {})
    maximum_effective_error = float(
        development_manifest.get("maximum_effective_error") or 0.0
    )
    target_decimals = int(development_manifest.get("decimals") or 0)
    if maximum_effective_error > 0.5 * 10.0 ** (-target_decimals) + 1e-12:
        raise ValueError(
            "generated development selector compensation exceeds target precision"
        )
    _verify_dynamic_capacity_modifiers(profile, project)
    _verify_capacity_pressure_modifiers(profile)
    return {
        "status": "verified",
        "locations": len(expected_capacity),
        "development_locations": development_count,
        "development_selector_collision_keys": list(
            development_manifest.get("selector_collision_keys") or []
        ),
        "development_maximum_effective_error": maximum_effective_error,
        "irrigation_locations": irrigation_locations,
        "irrigation_levels": irrigation_levels,
        "capacity_min": min(expected_capacity.values()),
        "capacity_max": max(expected_capacity.values()),
    }


def _compile_development_setup_rows(
    rows: list[tuple[str, float]],
    *,
    state: pl.DataFrame,
    target_decimals: int,
) -> DevelopmentSetupCompilation:
    """Compile exact location targets through EU5's shared setup-key namespace.

    The ``development`` setup block accepts bare location, province, area,
    region, rank, climate, topography, and vegetation keys and adds every
    matching selector. A location such as ``qingchi`` therefore collides with
    the province of the same name. EU5 does not use numeric location IDs in
    this table, so solve the small collision system and emit coefficients whose
    combined in-game values reproduce the intended per-location targets.
    """

    if target_decimals < 0 or target_decimals > 6:
        raise ValueError("development target decimals must be between zero and six")
    tags = [tag for tag, _value in rows]
    if len(tags) != len(set(tags)):
        raise ValueError("development setup contains duplicate location tags")
    weighted_collisions = sorted(set(tags) & DEVELOPMENT_WEIGHTED_SELECTOR_KEYS)
    if weighted_collisions:
        raise ValueError(
            "development location tags collide with weighted setup selectors: "
            f"{weighted_collisions}"
        )
    if "location_tag" not in state.columns:
        raise ValueError("development selector state is missing location_tag")
    state_by_tag = state.select(
        "location_tag",
        *[
            column
            for column in DEVELOPMENT_SELECTOR_COLUMNS
            if column in state.columns
        ],
    )
    if state_by_tag["location_tag"].n_unique() != state_by_tag.height:
        raise ValueError("development selector state contains duplicate location tags")
    missing = sorted(set(tags) - set(state_by_tag["location_tag"].to_list()))
    if missing:
        raise ValueError(
            "development selector state is missing generated locations: "
            f"{missing[:8]}"
        )
    state_by_tag = pl.DataFrame({"location_tag": tags}).join(
        state_by_tag,
        on="location_tag",
        how="left",
    )
    tag_set = set(tags)
    collision_keys: set[str] = set()
    selector_columns = [
        column
        for column in DEVELOPMENT_SELECTOR_COLUMNS
        if column in state_by_tag.columns
    ]
    for column in selector_columns:
        collision_keys.update(
            tag_set
            & {
                str(value)
                for value in state_by_tag[column].drop_nulls().unique().to_list()
            }
        )
    ordered_collisions = tuple(sorted(collision_keys))
    if not ordered_collisions:
        return DevelopmentSetupCompilation(
            rows=tuple(rows),
            coefficient_decimals=target_decimals,
            selector_collision_keys=(),
            maximum_effective_error=0.0,
        )

    tag_index = {tag: index for index, tag in enumerate(tags)}
    target = np.asarray([value for _tag, value in rows], dtype=np.float64)
    selector_effect = np.zeros(
        (len(rows), len(ordered_collisions)),
        dtype=np.float64,
    )
    for column in selector_columns:
        values = state_by_tag[column].to_numpy()
        for collision_index, key in enumerate(ordered_collisions):
            selector_effect[:, collision_index] += values == key
    collision_row_indices = np.asarray(
        [tag_index[key] for key in ordered_collisions],
        dtype=np.int64,
    )
    collision_system = (
        np.eye(len(ordered_collisions), dtype=np.float64)
        + selector_effect[collision_row_indices, :]
    )
    collision_targets = target[collision_row_indices]
    collision_coefficients, _residuals, rank, _singular = np.linalg.lstsq(
        collision_system,
        collision_targets,
        rcond=None,
    )
    if rank != len(ordered_collisions) or not np.allclose(
        collision_system @ collision_coefficients,
        collision_targets,
        atol=1e-10,
        rtol=0.0,
    ):
        raise ValueError(
            "development selector collisions cannot be represented uniquely: "
            f"{list(ordered_collisions)}"
        )
    coefficients = target - selector_effect @ collision_coefficients
    if not np.isfinite(coefficients).all():
        raise ValueError("development selector compilation produced non-finite values")

    allowed_error = 0.5 * 10.0 ** (-target_decimals)
    compiled: np.ndarray | None = None
    maximum_error = math.inf
    coefficient_decimals = target_decimals
    for decimals in range(target_decimals, 7):
        candidate = np.round(coefficients, decimals=decimals)
        effective = (
            candidate
            + selector_effect @ candidate[collision_row_indices]
        )
        error = float(np.max(np.abs(effective - target)))
        if error <= allowed_error + 1e-12:
            compiled = candidate
            maximum_error = error
            coefficient_decimals = decimals
            break
    if compiled is None:
        raise ValueError(
            "development selector collisions exceed target precision after compilation"
        )
    return DevelopmentSetupCompilation(
        rows=tuple(
            (tag, float(compiled[index]))
            for index, tag in enumerate(tags)
        ),
        coefficient_decimals=coefficient_decimals,
        selector_collision_keys=ordered_collisions,
        maximum_effective_error=maximum_error,
    )


def _render_capacity_csv(rows: list[dict[str, int | str]]) -> str:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=("location_tag", "population_capacity"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _render_development_setup(
    rows: list[tuple[str, float]],
    *,
    decimals: int,
) -> str:
    lines = [GENERATED_MARKER, "development = {", "\tbase = 0"]
    for tag, value in rows:
        lines.append(f"\t{tag} = {value:.{decimals}f}")
    lines.extend(("}", ""))
    return "\n".join(lines)


def _render_infrastructure_setup(rows: list[tuple[str, str, str, int]]) -> str:
    lines = [GENERATED_MARKER, "building_manager = {"]
    for building, tag, owner, level in rows:
        lines.append(
            f"\t{building} = {{ "
            f"tag = {owner} level = {level} location = {tag} "
            "}"
        )
    lines.extend(("}", ""))
    return "\n".join(lines)


def _parsed_location_capacity(path: Path) -> dict[str, int]:
    document = parse_file(path)
    out: dict[str, int] = {}
    aliases = {value: key for key, value in LOCATION_MODIFIER_ALIASES.items()}
    for entry in document.entries:
        key = str(entry.key)
        if not key.startswith("pp_loc_") or not isinstance(entry.value, CList):
            continue
        tag = aliases.get(key, key.removeprefix("pp_loc_")).lower()
        values = entry.value.values("local_population_capacity")
        if values:
            out[tag] = int(float(values[-1]))
    return out


def _verify_development_setup(path: Path) -> int:
    document = parse_file(path)
    blocks = [value for value in document.values("development") if isinstance(value, CList)]
    if len(blocks) != 1:
        raise ValueError("generated development setup must contain exactly one development block")
    block = blocks[0]
    base_values = block.values("base")
    if len(base_values) != 1 or float(base_values[0]) != 0.0:
        raise ValueError("generated development setup base must be zero")
    return sum(1 for entry in block.entries if str(entry.key) != "base")


def _verify_irrigation_setup(path: Path) -> tuple[int, int]:
    document = parse_file(path)
    locations = 0
    levels = 0
    for manager in document.values("building_manager"):
        if not isinstance(manager, CList):
            continue
        for entry in manager.entries:
            if str(entry.key) != "irrigation_systems" or not isinstance(entry.value, CList):
                continue
            if not str(entry.value.first("tag") or ""):
                raise ValueError("generated irrigation placement is missing an owner tag")
            if not str(entry.value.first("location") or ""):
                raise ValueError("generated irrigation placement is missing a location")
            level = int(entry.value.first("level") or 0)
            if level <= 0:
                raise ValueError("generated irrigation placement levels must be positive")
            locations += 1
            levels += level
    return locations, levels


def _verify_dynamic_capacity_modifiers(
    profile: SimulationProfile,
    project: Path,
) -> None:
    parsed_profile = profile_from(profile.parser_profile, profile.load_order_path)
    static_modifiers = load_collection(parsed_profile, "static_modifiers")
    development = _collection_block(static_modifiers.entries, "development")
    if development is None:
        raise ValueError("parsed development static modifier is missing")
    formula = profile.capacity_formula
    _require_modifier_value(
        development,
        "local_population_capacity",
        0.0,
        "development",
    )
    _require_modifier_value(
        development,
        "local_population_capacity_modifier",
        formula.development_relative,
        "development",
    )

    buildings = load_collection(parsed_profile, "building_types")
    for building, expected in profile.infrastructure_capacity_per_level.items():
        definition = _collection_block(buildings.entries, building)
        if definition is None:
            raise ValueError(f"parsed infrastructure building is missing: {building}")
        modifier_blocks = [
            value
            for value in definition.values("raw_modifier")
            if isinstance(value, CList)
        ]
        if not modifier_blocks:
            raise ValueError(f"{building} raw_modifier is missing")
        _require_modifier_value(
            modifier_blocks[-1],
            "local_population_capacity",
            expected,
            building,
        )
        observed_relative = _last_numeric(
            modifier_blocks[-1],
            "local_population_capacity_modifier",
            default=0.0,
        )
        if not math.isclose(observed_relative, 0.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(
                f"{building} must not add a relative population-capacity modifier"
            )


def _verify_capacity_pressure_modifiers(profile: SimulationProfile) -> None:
    """Require the simulated food-pressure coefficients to match parsed game data."""

    parsed_profile = profile_from(profile.parser_profile, profile.load_order_path)
    static_modifiers = load_collection(parsed_profile, "static_modifiers")
    expected = {
        "abundant_free_land": (
            profile.abundant_peasant_food_consumption,
            profile.abundant_monthly_food,
        ),
        "available_free_land": (
            profile.available_peasant_food_consumption,
            profile.available_monthly_food,
        ),
        "overpopulation": (profile.overpopulation_peasant_food_consumption, 0.0),
    }
    for key, (consumption, monthly_food) in expected.items():
        block = _collection_block(static_modifiers.entries, key)
        if block is None:
            raise ValueError(f"parsed {key} static modifier is missing")
        _require_modifier_value(
            block,
            "local_peasants_food_consumption",
            consumption,
            key,
        )
        observed_food = _last_numeric(block, "local_monthly_food", default=0.0)
        if not math.isclose(
            observed_food,
            monthly_food,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"{key} local_monthly_food={observed_food:g} does not match "
                f"profile value {monthly_food:g}"
            )


def _collection_block(entries: Any, key: str) -> CList | None:
    result = None
    for entry in entries:
        if str(entry.key).split(":", 1)[-1] == key and isinstance(entry.value, CList):
            result = entry.value
    return result


def _require_modifier_value(
    block: CList,
    key: str,
    expected: float,
    label: str,
) -> None:
    observed = _last_numeric(block, key)
    if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(
            f"{label} {key}={observed:g} does not match profile value {expected:g}"
        )


def _last_numeric(block: CList, key: str, *, default: float | None = None) -> float:
    values = block.values(key)
    if not values:
        if default is not None:
            return default
        raise ValueError(f"parsed modifier is missing {key}")
    return float(values[-1])


def _write_if_changed(path: Path, text: str) -> bool:
    encoded = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return True


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
