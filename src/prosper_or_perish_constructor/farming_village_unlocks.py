"""Data-driven farming-village RGO production-method unlocks."""

from __future__ import annotations

import difflib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import polars as pl
import yaml
from goods_labeler.location_templates import (
    apply_location_template_overlay,
    load_current_location_templates,
)


BLUEPRINT_RELATIVE_PATH = Path("blueprints/accepted/buildings/farming_village.yml")
CONFIG_SECTION = "farming_village_rgo_unlocks"
GAME_START_AGE = "age_1_traditions"
GAME_START_REQUIRES = "agriculture_advance"
AI_WEIGHT = 50


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
    config = load_rgo_unlock_config(project)
    locations = load_current_location_frame(repo, project)
    gates = derive_rgo_unlock_gates(locations, [item.good for item in config.goods], config.threshold)
    return render_blueprint_advancement_section(config, gates)


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
