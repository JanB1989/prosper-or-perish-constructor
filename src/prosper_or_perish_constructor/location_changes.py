"""Constructor-facing location-template change detection and focused relabeling."""

from __future__ import annotations

import json
import random
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import polars as pl

from goods_labeler.location_templates import (
    EvaluatorSpec,
    annotate_location_template_changes,
    apply_location_template_overlay,
    detect_location_template_changes,
    load_current_location_templates,
    run_focused_relabel_for_good,
)
from mod_injector.config import ModInjectorConfig, load_mod_injector_config


@dataclass(frozen=True)
class ConstructorLocationChangeReport:
    """Full report plus paths used to build it."""

    config: ModInjectorConfig
    changes: pl.DataFrame
    field_counts: dict[str, int]
    unmodeled_current_fields: tuple[str, ...]
    location_template_paths: tuple[Path, ...]
    overlaid_baseline: pl.DataFrame


def resolve_labeling_config_path(
    repo: Path,
    project: Path,
    explicit: Path | None = None,
) -> Path:
    """Resolve constructor `[labeling].config`, with an optional CLI override."""
    if explicit is not None:
        return explicit if explicit.is_absolute() else repo / explicit
    with project.open("rb") as handle:
        raw = tomllib.load(handle)
    labeling = raw.get("labeling", {})
    if not isinstance(labeling, dict):
        raise ValueError(f"{project}: [labeling] must be a mapping")
    config = labeling.get("config", "labeling_output_modifiers.yaml")
    return repo / str(config)


def build_location_change_report(
    *,
    repo: Path,
    project: Path,
    config_path: Path | None = None,
) -> ConstructorLocationChangeReport:
    """Load baseline, overlay current templates, and annotate affected relabel targets."""
    resolved_config = resolve_labeling_config_path(repo, project, config_path)
    cfg = load_mod_injector_config(resolved_config)
    if cfg.baseline_parquet is None or not cfg.baseline_parquet.is_file():
        raise FileNotFoundError(f"baseline_parquet not found: {cfg.baseline_parquet}")
    if cfg.location_templates_path is None and cfg.location_templates_load_order is None:
        raise ValueError(
            f"{resolved_config}: set location_templates_load_order or location_templates_path"
        )
    baseline = pl.read_parquet(cfg.baseline_parquet)
    templates, source = load_current_location_templates(
        location_templates_path=cfg.location_templates_path,
        load_order_path=cfg.location_templates_load_order,
        profile=cfg.location_templates_profile,
    )
    report = detect_location_template_changes(baseline, templates)
    overlaid = apply_location_template_overlay(baseline, templates)
    evaluators = [
        EvaluatorSpec(
            trade_good=good.trade_good,
            evaluator_config=good.evaluator_config,
            enabled=good.enabled,
        )
        for good in cfg.goods
    ]
    annotated = annotate_location_template_changes(
        report.changes,
        overlaid_baseline=overlaid,
        evaluators=evaluators,
    )
    return ConstructorLocationChangeReport(
        config=cfg,
        changes=annotated,
        field_counts=report.field_counts,
        unmodeled_current_fields=report.unmodeled_current_fields,
        location_template_paths=source.paths,
        overlaid_baseline=overlaid,
    )


def write_location_change_report(report: ConstructorLocationChangeReport, output: Path) -> Path:
    """Write the report CSV, creating parent directories."""
    output.parent.mkdir(parents=True, exist_ok=True)
    report.changes.write_csv(output)
    return output


def print_location_change_report(
    report: ConstructorLocationChangeReport,
    *,
    output: Path | None = None,
) -> None:
    """Print a compact but complete terminal summary for changed locations."""
    print(
        "location_template_sources="
        f"{','.join(str(path) for path in report.location_template_paths)}"
    )
    print(f"changed_locations={report.changes.height}")
    field_line = ", ".join(
        f"{field}={count}" for field, count in sorted(report.field_counts.items())
    )
    print(f"field_counts={field_line or 'none'}")
    print(
        "raw_material_transitions="
        f"{_format_counts(_raw_material_transition_counts(report.changes))}"
    )
    print(
        "affected_goods_counts="
        f"{_format_counts(_pipe_value_counts(report.changes, 'affected_goods'))}"
    )
    print(
        "labelable_counts="
        f"{_format_counts(_bool_value_counts(report.changes, 'labelable'))}"
    )
    print(
        "relabel_status_counts="
        f"{_format_counts(_value_counts(report.changes, 'relabel_status'))}"
    )
    if report.unmodeled_current_fields:
        print(f"unmodeled_current_fields={','.join(report.unmodeled_current_fields)}")
    if output is not None:
        print(f"report_csv={output}")
    if report.changes.is_empty():
        return
    print(
        "location_tag\tchanged_fields\tchanges\taffected_goods\tlabelable"
        "\trelabel_status\tcanonical_targets\tcanonical_feature_hashes"
    )
    for row in report.changes.sort("location_tag").to_dicts():
        changes = _format_changes(row["changes_json"])
        canonical = _format_canonical_targets(row["canonical_targets_json"])
        hashes = _format_canonical_targets(row["canonical_feature_hashes_json"])
        print(
            f"{row['location_tag']}\t{row['changed_fields']}\t{changes}\t"
            f"{row['affected_goods'] or '-'}\t{row['labelable']}\t"
            f"{row['relabel_status']}\t{canonical or '-'}\t{hashes or '-'}"
        )


def run_focused_relabel(
    report: ConstructorLocationChangeReport,
    *,
    max_rounds_per_good: int,
    min_target_appearances: int,
    target_sigma_ratio: float,
    goods_filter: set[str] | None = None,
) -> int:
    """Run focused relabeling for every affected good in the report."""
    by_good: dict[str, set[str]] = defaultdict(set)
    for row in report.changes.to_dicts():
        affected_goods = [good for good in str(row["affected_goods"]).split("|") if good]
        for good in affected_goods:
            if goods_filter is not None and good not in goods_filter:
                continue
            by_good[good].add(str(row["location_tag"]))
    if not by_good:
        print("focused_relabel_goods=0")
        return 0

    configs = {good.trade_good: good.evaluator_config for good in report.config.goods if good.enabled}
    failures = 0
    for good in sorted(by_good):
        config = configs.get(good)
        if config is None:
            print(f"[location-changes:{good}] skip=no_enabled_evaluator")
            continue
        result = run_focused_relabel_for_good(
            config,
            target_location_tags=sorted(by_good[good]),
            baseline=report.overlaid_baseline,
            max_rounds=max_rounds_per_good,
            min_target_appearances=min_target_appearances,
            target_sigma_ratio=target_sigma_ratio,
            rng=random.Random(),
        )
        print(
            f"[location-changes:{good}] complete={result.complete} "
            f"rounds={result.rounds_run} targets={len(result.canonical_targets)}"
        )
        if not result.complete:
            failures += 1
    return 0 if failures == 0 else 1


def _format_changes(changes_json: str) -> str:
    try:
        changes = json.loads(changes_json)
    except json.JSONDecodeError:
        return changes_json
    parts = []
    for field in sorted(changes):
        item = changes[field]
        parts.append(f"{field}:{item.get('old')}->{item.get('new')}")
    return ",".join(parts)


def _format_canonical_targets(canonical_targets_json: str) -> str:
    try:
        targets = json.loads(canonical_targets_json)
    except json.JSONDecodeError:
        return canonical_targets_json
    return ",".join(f"{good}:{tag}" for good, tag in sorted(targets.items()))


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _pipe_value_counts(changes: pl.DataFrame, column: str) -> dict[str, int]:
    if changes.is_empty() or column not in changes.columns:
        return {}
    counts: Counter[str] = Counter()
    for value in changes[column].to_list():
        for item in str(value or "").split("|"):
            if item:
                counts[item] += 1
    return dict(counts)


def _value_counts(changes: pl.DataFrame, column: str) -> dict[str, int]:
    if changes.is_empty() or column not in changes.columns:
        return {}
    counts: Counter[str] = Counter()
    for value in changes[column].to_list():
        if value is not None and str(value):
            counts[str(value)] += 1
    return dict(counts)


def _bool_value_counts(changes: pl.DataFrame, column: str) -> dict[str, int]:
    if changes.is_empty() or column not in changes.columns:
        return {}
    counts: Counter[str] = Counter()
    for value in changes[column].to_list():
        counts["true" if bool(value) else "false"] += 1
    return dict(counts)


def _raw_material_transition_counts(changes: pl.DataFrame) -> dict[str, int]:
    if changes.is_empty():
        return {}
    counts: Counter[str] = Counter()
    for row in changes.to_dicts():
        changed_fields = set(str(row.get("changed_fields") or "").split("|"))
        if "raw_material" not in changed_fields:
            continue
        old = str(row.get("old_raw_material") or "-")
        new = str(row.get("new_raw_material") or "-")
        counts[f"{old}->{new}"] += 1
    return dict(counts)
