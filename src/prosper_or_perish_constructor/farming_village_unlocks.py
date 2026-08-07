"""Data-driven farming-village RGO production-method unlocks."""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.availability import AGE_ORDER
from goods_labeler.location_templates import (
    apply_location_template_overlay,
    load_current_location_templates,
)


BLUEPRINT_RELATIVE_PATH = Path("blueprints/accepted/buildings/farming_village.yml")
CONFIG_SECTION = "farming_village_rgo_unlocks"
GAME_START_AGE = "age_1_traditions"
GAME_START_REQUIRES = "agriculture_advance"
AI_WEIGHT = 50
AGE_INDEX = {age: index for index, age in enumerate(AGE_ORDER)}
LOCATION_POTENTIAL_MODIFIER_PREFIX = "pp_loc_"
LOCATION_POTENTIAL_MODIFIER_RELATIVE = Path(
    "main_menu/common/static_modifiers/pp_location_modifiers.txt"
)
# Final deployed modifier keys for tags that collide with other tokens.
LOCATION_POTENTIAL_MODIFIER_ALIASES = {
    "pp_loc_washita": "pp_loc_washita_pp",
}
# Precomputed game-start demographics + development (food-building startup output).
DERIVED_START_LOCATIONS_RELATIVE = Path(
    "artifacts/data/food_building_startup/derived_food_balance_by_location.parquet"
)


@dataclass(frozen=True)
class RgoUnlockGood:
    good: str
    methods: tuple[str, ...]
    general_age: str
    general_requires: str


@dataclass(frozen=True)
class RgoUnlockConfig:
    goods: tuple[RgoUnlockGood, ...]
    threshold: float


@dataclass(frozen=True)
class RgoUnlockGate:
    good: str
    subcontinents: tuple[str, ...]
    regions: tuple[str, ...]


@dataclass(frozen=True)
class BlueprintCheck:
    current: str
    expected: str

    @property
    def ok(self) -> bool:
        return self.current == self.expected

    def unified_diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.current.splitlines(keepends=True),
                self.expected.splitlines(keepends=True),
                fromfile="current farming_village.yml advancements",
                tofile="expected farming_village.yml advancements",
            )
        )


def load_rgo_unlock_config(project: Path) -> RgoUnlockConfig:
    with project.open("rb") as handle:
        raw = tomllib.load(handle)
    section = _mapping(raw.get(CONFIG_SECTION), CONFIG_SECTION)

    goods = _string_list(section.get("goods"), f"{CONFIG_SECTION}.goods")
    threshold = _float(section.get("subcontinent_region_threshold"), f"{CONFIG_SECTION}.subcontinent_region_threshold")
    methods = _mapping(section.get("methods"), f"{CONFIG_SECTION}.methods")
    general_unlocks = _mapping(section.get("general_unlocks"), f"{CONFIG_SECTION}.general_unlocks")

    configs: list[RgoUnlockGood] = []
    for good in goods:
        unlock = _mapping(general_unlocks.get(good), f"{CONFIG_SECTION}.general_unlocks.{good}")
        configs.append(
            RgoUnlockGood(
                good=good,
                methods=tuple(_string_list(methods.get(good), f"{CONFIG_SECTION}.methods.{good}")),
                general_age=_string(unlock.get("age"), f"{CONFIG_SECTION}.general_unlocks.{good}.age"),
                general_requires=_string(unlock.get("requires"), f"{CONFIG_SECTION}.general_unlocks.{good}.requires"),
            )
        )
    return RgoUnlockConfig(goods=tuple(configs), threshold=threshold)


def load_current_location_frame(repo: Path, project: Path) -> pl.DataFrame:
    project_config = _load_project_config(project)
    labeling_config_path = _resolve_repo_path(repo, _mapping(project_config.get("labeling"), "labeling").get("config"))
    if labeling_config_path is None:
        raise ValueError(f"{project}: missing [labeling].config")
    with labeling_config_path.open("r", encoding="utf-8") as handle:
        labeling_config = yaml.safe_load(handle)
    labeling_config = _mapping(labeling_config, str(labeling_config_path))

    baseline = _resolve_config_path(
        labeling_config_path.parent,
        labeling_config.get("baseline_parquet"),
        f"{labeling_config_path}: baseline_parquet",
    )
    load_order = _resolve_config_path(
        repo,
        labeling_config.get("location_templates_load_order") or "constructor.load_order.toml",
        f"{labeling_config_path}: location_templates_load_order",
    )

    frame = pl.read_parquet(baseline)
    templates, _source = load_current_location_templates(load_order_path=load_order)
    return apply_location_template_overlay(frame, templates)


def load_start_location_frame(repo: Path, project: Path | None = None) -> pl.DataFrame:
    """Overlaid location geography plus game-start population and Location Potential.

    Joins:
    - ``population_*``, ``total_population``, ``unemployed_peasants``, ``location_rank``,
      and ``development`` from the food-startup artifact
      (``artifacts/data/food_building_startup/derived_food_balance_by_location.parquet``);
      falls back to a live ``_load_start_locations`` parse only if that file is missing
    - ``prosperity`` fixed at ``0.0`` for now
    - per-location ``pp_loc_*`` Location Potential static modifiers
      (``local_population_capacity``, ``local_*_output_modifier``, …)
    - ``food`` stocked at the growth-cap limit
      (``food_consumption * GROWTH_FROM_FOOD_MULTIPLIER_MAX * 12``; consumption itself
      is derived and not kept on the returned frame)

    Tick-derived modifiers (food growth / rank sums) are not persisted.
    """
    project_path = project or repo / "constructor.toml"
    from prosper_or_perish_constructor.simulation.food import (
        attach_peasant_employment_state,
        compute_location_food_consumption,
        initialize_location_food_at_cap,
    )
    from prosper_or_perish_constructor.simulation.modifiers import (
        load_growth_cap_years,
        load_pop_food_rates,
    )
    from prosper_or_perish_constructor.simulation.tick import finalize_location_state

    geography = load_current_location_frame(repo, project_path)
    start = _load_start_demographics_frame(repo)
    pop_columns = [
        column
        for column in start.columns
        if column.startswith("population_") or column in {"total_population", "unemployed_peasants"}
    ]
    start_select = [pl.col("location_tag"), *pop_columns]
    if "development" in start.columns:
        start_select.append(pl.col("development"))
    if "location_rank" in start.columns:
        start_select.append(pl.col("location_rank"))
    joined = geography.join(
        start.select(start_select),
        on="location_tag",
        how="left",
    ).with_columns(
        [pl.col(column).fill_null(0.0).cast(pl.Float64).alias(column) for column in pop_columns]
    )
    if "development" in joined.columns:
        joined = joined.with_columns(pl.col("development").fill_null(0.0).cast(pl.Float64))
    else:
        joined = joined.with_columns(pl.lit(0.0).alias("development"))
    # Game-start prosperity is flat 0 for now (setup overrides ignored).
    joined = joined.with_columns(pl.lit(0.0).alias("prosperity"))

    potential = load_location_potential_frame(repo, project_path)
    joined = joined.join(potential, on="location_tag", how="left")

    load_order_path = repo / "constructor.load_order.toml"
    pop_food_rates = load_pop_food_rates(profile="constructor", load_order_path=load_order_path)
    growth_cap_years = load_growth_cap_years(profile="constructor", load_order_path=load_order_path)
    with_consumption = compute_location_food_consumption(joined, pop_food_rates)
    with_food = initialize_location_food_at_cap(with_consumption, growth_cap_years=growth_cap_years)
    with_employment = attach_peasant_employment_state(with_food)
    return finalize_location_state(with_employment)


def _load_start_demographics_frame(repo: Path) -> pl.DataFrame:
    """Load start pops / rank / development from the food-startup artifact when present."""
    artifact = repo / DERIVED_START_LOCATIONS_RELATIVE
    if artifact.is_file():
        frame = pl.read_parquet(artifact)
        if "slug" not in frame.columns:
            raise ValueError(f"{artifact}: missing slug column")
        if "development" not in frame.columns:
            raise ValueError(f"{artifact}: missing development column")
        if "location_rank" in frame.columns:
            rank_expr = pl.col("location_rank")
        elif "rank" in frame.columns:
            rank_expr = pl.col("rank")
        else:
            rank_expr = pl.lit(None).cast(pl.String)
        pop_columns = [
            column
            for column in frame.columns
            if column.startswith("population_") or column in {"total_population", "unemployed_peasants"}
        ]
        return frame.select(
            pl.col("slug").alias("location_tag"),
            pl.col("development").cast(pl.Float64),
            rank_expr.cast(pl.String).alias("location_rank"),
            *[pl.col(column).cast(pl.Float64) for column in pop_columns],
        )

    # Fallback for checkouts without the generated artifact.
    from prosper_or_perish_constructor.food_building_startup import load_food_startup_config
    from prosper_or_perish_constructor import food_building_startup as food_startup

    start = food_startup._load_start_locations(load_food_startup_config(repo))
    pop_columns = [
        column
        for column in start.columns
        if column.startswith("population_") or column in {"total_population", "unemployed_peasants"}
    ]
    if "rank" in start.columns:
        rank_expr = pl.col("rank").alias("location_rank")
    elif "location_rank" in start.columns:
        rank_expr = pl.col("location_rank")
    else:
        rank_expr = pl.lit(None).cast(pl.String).alias("location_rank")
    select_cols: list[pl.Expr | str] = [pl.col("slug").alias("location_tag"), *pop_columns, rank_expr]
    if "development" in start.columns:
        select_cols.append(pl.col("development").cast(pl.Float64))
    return start.select(select_cols)


def load_location_potential_frame(repo: Path, project: Path | None = None) -> pl.DataFrame:
    """Wide frame of Location Potential ``pp_loc_*`` modifiers keyed by ``location_tag``."""
    from eu5gameparser.clausewitz.parser import parse_file
    from eu5gameparser.clausewitz.syntax import CList

    project_path = project or repo / "constructor.toml"
    path = _location_potential_modifiers_path(repo, project_path)
    document = parse_file(path)
    alias_to_canonical = {
        alias: canonical for canonical, alias in LOCATION_POTENTIAL_MODIFIER_ALIASES.items()
    }
    rows: list[dict[str, Any]] = []
    for entry in document.entries:
        key = str(entry.key)
        if not key.startswith(LOCATION_POTENTIAL_MODIFIER_PREFIX):
            continue
        if not isinstance(entry.value, CList):
            continue
        canonical_key = alias_to_canonical.get(key, key)
        location_tag = canonical_key.removeprefix(LOCATION_POTENTIAL_MODIFIER_PREFIX)
        row: dict[str, Any] = {
            "location_tag": location_tag,
            "location_potential_modifier": key,
        }
        for child in entry.value.entries:
            if isinstance(child.value, bool) or not isinstance(child.value, int | float):
                continue
            row[str(child.key)] = float(child.value)
        rows.append(row)
    if not rows:
        return pl.DataFrame({"location_tag": pl.Series([], dtype=pl.String)})
    return pl.DataFrame(rows)


def _location_potential_modifiers_path(repo: Path, project: Path) -> Path:
    project_config = _load_project_config(project)
    mod_root = _resolve_repo_path(
        repo,
        _mapping(project_config.get("project"), "project").get("mod_root"),
    )
    if mod_root is None:
        raise ValueError(f"{project}: missing [project].mod_root")
    path = mod_root / LOCATION_POTENTIAL_MODIFIER_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"Location Potential modifiers not found: {path}")
    return path


def derive_rgo_unlock_gates(
    locations: pl.DataFrame,
    goods: Sequence[str],
    threshold: float,
) -> tuple[RgoUnlockGate, ...]:
    _require_columns(locations, ("raw_material", "region", "macro_region"))
    rgo_regions = _rgo_region_frame(locations)
    totals = {
        str(row["macro_region"]): int(row["total_regions"])
        for row in rgo_regions.select("macro_region", "region")
        .unique()
        .group_by("macro_region")
        .len()
        .rename({"len": "total_regions"})
        .to_dicts()
    }

    gates: list[RgoUnlockGate] = []
    for good in goods:
        good_regions = (
            rgo_regions.filter(pl.col("raw_material") == good)
            .select("macro_region", "region")
            .unique()
        )
        subcontinents: list[str] = []
        regions: list[str] = []
        for macro_region in sorted(str(value) for value in good_regions["macro_region"].unique().to_list()):
            macro_regions = sorted(
                str(value)
                for value in good_regions.filter(pl.col("macro_region") == macro_region)["region"].unique().to_list()
            )
            total = totals.get(macro_region, 0)
            if total > 0 and len(macro_regions) / total >= threshold:
                subcontinents.append(macro_region)
            else:
                regions.extend(macro_regions)
        gates.append(
            RgoUnlockGate(
                good=good,
                subcontinents=tuple(sorted(subcontinents)),
                regions=tuple(sorted(regions)),
            )
        )
    return tuple(gates)


def expected_blueprint_advancement_section(repo: Path, project: Path) -> str:
    config = effective_rgo_unlock_config(repo, load_rgo_unlock_config(project))
    locations = load_current_location_frame(repo, project)
    gates = derive_rgo_unlock_gates(locations, [item.good for item in config.goods], config.threshold)
    return render_blueprint_advancement_section(config, gates)


def effective_rgo_unlock_config(repo: Path, config: RgoUnlockConfig) -> RgoUnlockConfig:
    additions = _early_descendant_methods(repo, config)
    goods: list[RgoUnlockGood] = []
    for item in config.goods:
        methods = tuple(dict.fromkeys((*item.methods, *additions.get(item.good, ()))))
        goods.append(
            RgoUnlockGood(
                good=item.good,
                methods=methods,
                general_age=item.general_age,
                general_requires=item.general_requires,
            )
        )
    return RgoUnlockConfig(goods=tuple(goods), threshold=config.threshold)


def render_blueprint_advancement_section(
    config: RgoUnlockConfig,
    gates: Sequence[RgoUnlockGate],
) -> str:
    gates_by_good = {gate.good: gate for gate in gates}
    lines = ["advancements:"]
    for item in config.goods:
        gate = gates_by_good[item.good]
        if gate.subcontinents or gate.regions:
            lines.extend(_advance_yaml_lines(_game_start_advance_key(item.good), _game_start_body(item, gate)))
        lines.extend(_advance_yaml_lines(_general_advance_key(item.good), _general_body(item, gate)))
    return "\n".join(lines) + "\n"


def check_blueprint_advancements(repo: Path, project: Path) -> BlueprintCheck:
    blueprint = repo / BLUEPRINT_RELATIVE_PATH
    text = blueprint.read_text(encoding="utf-8-sig")
    return BlueprintCheck(
        current=_current_advancement_section(text),
        expected=expected_blueprint_advancement_section(repo, project),
    )


def write_blueprint_advancements(repo: Path, project: Path) -> bool:
    blueprint = repo / BLUEPRINT_RELATIVE_PATH
    text = blueprint.read_text(encoding="utf-8-sig")
    expected = expected_blueprint_advancement_section(repo, project)
    current = _current_advancement_section(text)
    if current == expected:
        return False
    updated = _replace_advancement_section(text, expected)
    blueprint.write_text(updated, encoding="utf-8-sig")
    return True


def _rgo_region_frame(locations: pl.DataFrame) -> pl.DataFrame:
    return (
        locations.with_columns(
            pl.col("raw_material").cast(pl.String).str.strip_chars().alias("raw_material"),
            pl.col("region").cast(pl.String).str.strip_chars().alias("region"),
            pl.col("macro_region").cast(pl.String).str.strip_chars().alias("macro_region"),
        )
        .filter(
            pl.col("raw_material").is_not_null()
            & (pl.col("raw_material") != "")
            & pl.col("region").is_not_null()
            & (pl.col("region") != "")
            & pl.col("macro_region").is_not_null()
            & (pl.col("macro_region") != "")
        )
        .select("raw_material", "macro_region", "region")
        .unique()
    )


def _early_descendant_methods(repo: Path, config: RgoUnlockConfig) -> dict[str, tuple[str, ...]]:
    additions: dict[str, list[str]] = {item.good: [] for item in config.goods}
    config_by_good = {item.good: item for item in config.goods}
    for path in sorted((repo / "blueprints" / "accepted" / "buildings").glob("*.yml")):
        raw = _load_yaml_mapping(path)
        chain = raw.get("upgrade_chain")
        if not isinstance(chain, Mapping) or chain.get("family") != "farming_village":
            continue
        tier = chain.get("tier")
        if not isinstance(tier, int) or tier <= 0:
            continue
        building_age = _unlock_advance_age(raw, str(chain.get("unlock_advance") or ""))
        if building_age is None:
            continue
        method_goods = _building_production_method_goods(raw, path)
        for good, item in config_by_good.items():
            if _age_index(building_age) >= _age_index(item.general_age):
                continue
            for method, produced in method_goods.items():
                if produced == good and method not in additions[good]:
                    additions[good].append(method)
    return {good: tuple(methods) for good, methods in additions.items()}


def _unlock_advance_age(raw: Mapping[str, Any], unlock_advance: str) -> str | None:
    if not unlock_advance:
        return None
    advancements = raw.get("advancements")
    if not isinstance(advancements, list):
        return None
    for advancement in advancements:
        if not isinstance(advancement, Mapping) or advancement.get("key") != unlock_advance:
            continue
        body = _string(advancement.get("body"), f"advancements.{unlock_advance}.body")
        match = re.search(r"(?m)^\s*age\s*=\s*([A-Za-z0-9_]+)\s*$", body)
        return None if match is None else match.group(1)
    return None


def _building_production_method_goods(raw: Mapping[str, Any], path: Path) -> dict[str, str]:
    building = _mapping(raw.get("building"), f"{path}: building")
    body = _string(building.get("body"), f"{path}: building.body")
    document = parse_text("root = {\n" + body + "\n}")
    root = document.entries[0].value
    if not isinstance(root, CList):
        return {}

    produced_by_method: dict[str, str] = {}
    for block in root.values("unique_production_methods"):
        if not isinstance(block, CList):
            continue
        for entry in block.entries:
            if not isinstance(entry.value, CList):
                continue
            produced = entry.value.values("produced")
            if produced:
                produced_by_method[str(entry.key)] = str(produced[0])
    return produced_by_method


def _age_index(age: str) -> int:
    if age not in AGE_INDEX:
        valid = ", ".join(AGE_ORDER)
        raise ValueError(f"Unknown age {age!r}; expected one of: {valid}")
    return AGE_INDEX[age]


def _advance_yaml_lines(key: str, body: str) -> list[str]:
    return [
        f"  - key: {key}",
        "    body: |2-",
        *[f"          {line}" if line else "" for line in body.splitlines()],
    ]


def _game_start_body(item: RgoUnlockGood, gate: RgoUnlockGate) -> str:
    return "\n".join(
        [
            f"age = {GAME_START_AGE}",
            *_unlock_method_lines(item.methods),
            f"requires = {GAME_START_REQUIRES}",
            f"ai_weight = {{ add = {AI_WEIGHT} }}",
            "potential = {",
            "    exists = capital",
            "    original_capital ?= {",
            "        OR = {",
            *_gate_lines(gate, indent="            "),
            "        }",
            "    }",
            "}",
        ]
    )


def _general_body(item: RgoUnlockGood, gate: RgoUnlockGate) -> str:
    lines = [
        f"age = {item.general_age}",
        *_unlock_method_lines(item.methods),
        f"requires = {item.general_requires}",
        f"ai_weight = {{ add = {AI_WEIGHT} }}",
        "potential = {",
        "    exists = capital",
    ]
    if gate.subcontinents or gate.regions:
        lines.extend(
            [
                "    NOT = {",
                "        original_capital ?= {",
                "            OR = {",
                *_gate_lines(gate, indent="                "),
                "            }",
                "        }",
                "    }",
            ]
        )
    lines.append("}")
    return "\n".join(lines)


def _unlock_method_lines(methods: Sequence[str]) -> list[str]:
    return [f"unlock_production_method = {method}" for method in methods]


def _gate_lines(gate: RgoUnlockGate, *, indent: str) -> list[str]:
    return [
        *[f"{indent}sub_continent = sub_continent:{subcontinent}" for subcontinent in gate.subcontinents],
        *[f"{indent}region = region:{region}" for region in gate.regions],
    ]


def _game_start_advance_key(good: str) -> str:
    return f"pp_{good}_farm_advance_game_start"


def _general_advance_key(good: str) -> str:
    return f"pp_{good}_farm_advance_general"


def _current_advancement_section(text: str) -> str:
    match = re.search(r"(?ms)^advancements:\n.*?(?=^localization:\n)", text)
    if match is None:
        raise ValueError("Could not find farming_village.yml advancements section before localization.")
    return match.group(0)


def _replace_advancement_section(text: str, replacement: str) -> str:
    updated, count = re.subn(r"(?ms)^advancements:\n.*?(?=^localization:\n)", replacement, text)
    if count != 1:
        raise ValueError("Could not replace exactly one farming_village.yml advancements section.")
    return updated


def _load_project_config(project: Path) -> dict[str, Any]:
    with project.open("rb") as handle:
        return tomllib.load(handle)


def _load_yaml_mapping(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        raw = yaml.safe_load(handle)
    return _mapping(raw, str(path))


def _resolve_repo_path(repo: Path, value: object) -> Path | None:
    if value is None:
        return None
    path = Path(_string(value, "path"))
    return path if path.is_absolute() else repo / path


def _resolve_config_path(base: Path, value: object, name: str) -> Path:
    path = Path(_string(value, name))
    return path if path.is_absolute() else base / path


def _require_columns(frame: pl.DataFrame, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Location data is missing required columns: {', '.join(missing)}")


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping.")
    return value


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{name} must be a non-empty list of strings.")
    return list(value)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def _float(value: object, name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    result = float(value)
    if result < 0.0 or result > 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return result
