"""Compare experimental population-capacity formulas on current labeling scores.

This analysis rebuilds raw per-good MMR from accepted labeling runs, broadcasts
those scores to current location templates, and writes only ignored analysis
artifacts.  It never writes generated mod files.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from statistics import mean

import polars as pl

from mod_injector.__main__ import _apply_location_template_overlay_from_config
from mod_injector.broadcast import (
    broadcast_to_locations,
    compute_mmr_table,
    keep_scores_for_raw_material_rows,
)
from mod_injector.config import ModInjectorConfig, load_mod_injector_config
from mod_injector.readiness import check_good_readiness
from mod_injector.validation import check_hash_broadcast_consistency
from prosper_or_perish_constructor.population_capacity_experiments import (
    MODEL_NAMES,
    model_comparison_frame,
    rank_matched_capacities,
)
from prosper_or_perish_population_capacity.config import load_pipeline_config
from prosper_or_perish_population_capacity.calibration import (
    evaluate_saturation_anchors,
    load_saturation_anchors,
)
from prosper_or_perish_population_capacity.staple_capacity import (
    StapleCapacityConfig,
    staple_capacity_rows,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELING_CONFIG = ROOT / "labeling_output_modifiers.yaml"
DEFAULT_POPULATION_CAPACITY_CONFIG = ROOT / "population_capacity.toml"
DEFAULT_SATURATION_ANCHORS = ROOT / "population_capacity_saturation_anchors.toml"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "data" / "population_capacity" / "model_comparison"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
DEPLOYED_MODIFIERS = (
    MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifiers.txt"
)
CANDIDATE_MODELS = tuple(model for model in MODEL_NAMES if model != "current")
SCOPE_COLUMNS = ("region", "super_region")
ANCHOR_SCOPE_COLUMNS = ("province", "area", "region", "super_region", "macro_region")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_LABELING_CONFIG)
    parser.add_argument(
        "--population-capacity-config",
        type=Path,
        default=DEFAULT_POPULATION_CAPACITY_CONFIG,
    )
    parser.add_argument("--anchors", type=Path, default=DEFAULT_SATURATION_ANCHORS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    config = load_mod_injector_config(args.config)
    if config.baseline_parquet is None:
        raise ValueError("labeling config has no baseline_parquet")
    capacity_config_path = config.population_capacity_config_path or args.population_capacity_config
    capacity_config = load_pipeline_config(capacity_config_path)
    scale = StapleCapacityConfig(
        capacity_min=capacity_config.capacity_scale.minimum,
        capacity_max=capacity_config.capacity_scale.maximum,
    )

    print("Rebuilding accepted labeling MMR scores (analysis only)...")
    scores, baseline, source_status = _build_score_frame(config)
    print(f"Scored rows: {scores.height:,}; locations: {scores['location_tag'].n_unique():,}")

    comparison = model_comparison_frame(
        scores,
        capacity_min=scale.capacity_min,
        capacity_max=scale.capacity_max,
    )
    _assert_production_formula_parity(scores, comparison, scale)
    comparison = _add_rank_matched_capacities(comparison)
    scope_frame = baseline.select("location_tag", *ANCHOR_SCOPE_COLUMNS).unique(subset=["location_tag"])
    comparison = comparison.join(scope_frame, on="location_tag", how="left")

    deployed_parity = _deployed_parity_rows(comparison)
    global_stats = _global_stats(comparison)
    scope_stats = _scope_stats(comparison)
    driver_counts = _driver_counts(comparison)
    anchor_stats = _anchor_stats(comparison, args.anchors)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scores.write_parquet(output_dir / "source_mmr_scores.parquet")
    comparison.write_parquet(output_dir / "location_model_comparison.parquet")
    source_status.write_csv(output_dir / "source_status.csv")
    global_stats.write_csv(output_dir / "global_stats.csv")
    scope_stats.write_csv(output_dir / "scope_stats.csv")
    driver_counts.write_csv(output_dir / "driver_counts.csv")
    anchor_stats.write_csv(output_dir / "anchor_stats.csv")
    pl.DataFrame(deployed_parity).write_csv(output_dir / "deployed_parity.csv")
    report = _render_report(
        global_stats=global_stats,
        scope_stats=scope_stats,
        driver_counts=driver_counts,
        source_status=source_status,
        deployed_parity=deployed_parity,
        anchor_stats=anchor_stats,
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")

    parity = deployed_parity[0]
    print("Production formula parity: PASS")
    print(
        "Deployed modifier parity: "
        f"{parity['matching']:,} matching; {parity['mismatched']:,} mismatched; "
        f"{parity['missing_from_deployed']:,} missing from deployed"
    )
    print(f"Report written: {output_dir / 'report.md'}")
    print(f"Scope statistics written: {output_dir / 'scope_stats.csv'}")
    return 0


def _build_score_frame(
    config: ModInjectorConfig,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    baseline = pl.read_parquet(config.baseline_parquet)
    baseline, allowed_unactivated_by_good = _apply_location_template_overlay_from_config(config, baseline)
    frames: list[pl.DataFrame] = []
    status_rows: list[dict[str, object]] = []

    for spec in config.goods:
        if not spec.enabled:
            status_rows.append(
                {"good": spec.trade_good, "status": "disabled", "score_rows": 0, "mmr_players": 0}
            )
            continue
        readiness = check_good_readiness(
            trade_good=spec.trade_good,
            evaluator_config=spec.evaluator_config,
            baseline=baseline,
            allowed_unactivated_tags=allowed_unactivated_by_good.get(spec.trade_good, set()),
        )
        if not readiness.ready:
            status_rows.append(
                {
                    "good": spec.trade_good,
                    "status": f"not_ready: {readiness.reason}",
                    "score_rows": 0,
                    "mmr_players": 0,
                }
            )
            print(f"  SKIP {spec.trade_good}: {readiness.reason}")
            continue

        mmr_table = compute_mmr_table(spec.evaluator_config, baseline=baseline)
        broadcast = broadcast_to_locations(baseline, spec.evaluator_config, mmr_table)
        check_hash_broadcast_consistency(broadcast)
        broadcast = keep_scores_for_raw_material_rows(broadcast)
        frame = broadcast.select(
            "location_tag",
            pl.lit(spec.trade_good).alias("good"),
            "mmr",
        )
        frames.append(frame)
        score_rows = int(frame["mmr"].is_not_null().sum())
        status_rows.append(
            {
                "good": spec.trade_good,
                "status": "ready",
                "score_rows": score_rows,
                "mmr_players": mmr_table.height,
            }
        )
        print(f"  OK {spec.trade_good}: {score_rows:,} location scores")

    if not frames:
        raise ValueError("no ready labeling goods produced scores")
    return pl.concat(frames, how="diagonal"), baseline, pl.DataFrame(status_rows)


def _assert_production_formula_parity(
    scores: pl.DataFrame,
    comparison: pl.DataFrame,
    config: StapleCapacityConfig,
) -> None:
    production = {
        str(row["location_tag"]): int(row["local_population_capacity"])
        for row in staple_capacity_rows(scores, config=config)
    }
    experimental = {
        str(row["location_tag"]): int(row["current_capacity"])
        for row in comparison.select("location_tag", "current_capacity").to_dicts()
    }
    if production != experimental:
        differing = sorted(
            tag for tag in set(production) | set(experimental) if production.get(tag) != experimental.get(tag)
        )
        raise AssertionError(
            "experiment current model diverges from production formula for "
            f"{len(differing)} locations; first={differing[:5]}"
        )


def _add_rank_matched_capacities(frame: pl.DataFrame) -> pl.DataFrame:
    locations = frame["location_tag"].to_list()
    reference = frame["current_capacity"].to_list()
    columns = [pl.col("current_capacity").alias("current_rank_matched_capacity")]
    for model in CANDIDATE_MODELS:
        matched = rank_matched_capacities(locations, frame[f"{model}_score"].to_list(), reference)
        columns.append(pl.Series(f"{model}_rank_matched_capacity", matched, dtype=pl.Int64))
    return frame.with_columns(columns)


def _deployed_parity_rows(frame: pl.DataFrame) -> list[dict[str, object]]:
    deployed = _load_deployed_capacities(DEPLOYED_MODIFIERS)
    rebuilt = {
        str(row["location_tag"]): int(row["current_capacity"])
        for row in frame.select("location_tag", "current_capacity").to_dicts()
    }
    common = set(deployed) & set(rebuilt)
    matching = sum(deployed[tag] == rebuilt[tag] for tag in common)
    return [
        {
            "deployed_locations": len(deployed),
            "rebuilt_locations": len(rebuilt),
            "matching": matching,
            "mismatched": len(common) - matching,
            "missing_from_deployed": len(set(rebuilt) - set(deployed)),
            "extra_in_deployed": len(set(deployed) - set(rebuilt)),
        }
    ]


def _load_deployed_capacities(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    block = re.compile(r"^pp_loc_([a-z0-9_]+)\s*=\s*\{")
    capacity = re.compile(r"^\s*local_population_capacity\s*=\s*(-?\d+)\s*$")
    out: dict[str, int] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if match := block.match(line):
            current = match.group(1)
            continue
        if current is not None and (match := capacity.match(line)):
            out[current] = int(match.group(1))
            continue
        if current is not None and line.strip() == "}":
            current = None
    return out


def _global_stats(frame: pl.DataFrame) -> pl.DataFrame:
    current = [int(value) for value in frame["current_capacity"].to_list()]
    rows: list[dict[str, object]] = []
    for model in MODEL_NAMES:
        raw = [int(value) for value in frame[f"{model}_capacity"].to_list()]
        matched = [int(value) for value in frame[f"{model}_rank_matched_capacity"].to_list()]
        rows.append(
            {
                "model": model,
                "locations": len(raw),
                "raw_mean": round(mean(raw), 4),
                "raw_median": _quantile(raw, 0.50),
                "raw_p10": _quantile(raw, 0.10),
                "raw_p90": _quantile(raw, 0.90),
                "raw_min": min(raw),
                "raw_max": max(raw),
                "raw_total": sum(raw),
                "raw_delta_mean": round(mean(raw) - mean(current), 4),
                "raw_mean_absolute_change": round(mean(abs(a - b) for a, b in zip(raw, current)), 4),
                "rank_matched_mean_absolute_change": round(
                    mean(abs(a - b) for a, b in zip(matched, current)), 4
                ),
                "spearman_vs_current": round(
                    _pearson(_average_ranks(raw), _average_ranks(current)), 6
                ),
            }
        )
    return pl.DataFrame(rows)


def _scope_stats(frame: pl.DataFrame) -> pl.DataFrame:
    outputs: list[pl.DataFrame] = []
    for scope_column in SCOPE_COLUMNS:
        scoped = frame.with_columns(pl.col(scope_column).fill_null("unknown").alias(scope_column))
        reference = scoped.group_by(scope_column).agg(
            pl.len().alias("locations"),
            pl.col("current_capacity").mean().alias("reference_mean"),
            pl.col("current_capacity").sum().alias("reference_total"),
        )
        for model in MODEL_NAMES:
            for variant, capacity_column in (
                ("raw", f"{model}_capacity"),
                ("rank_matched", f"{model}_rank_matched_capacity"),
            ):
                stats = (
                    scoped.group_by(scope_column)
                    .agg(
                        pl.col(capacity_column).mean().alias("mean_capacity"),
                        pl.col(capacity_column).median().alias("median_capacity"),
                        pl.col(capacity_column).quantile(0.10, interpolation="linear").alias("p10"),
                        pl.col(capacity_column).quantile(0.90, interpolation="linear").alias("p90"),
                        pl.col(capacity_column).sum().alias("total_capacity"),
                    )
                    .join(reference, on=scope_column, how="left")
                    .with_columns(
                        pl.lit(scope_column).alias("scope_type"),
                        pl.col(scope_column).alias("scope"),
                        pl.lit(model).alias("model"),
                        pl.lit(variant).alias("variant"),
                        (pl.col("mean_capacity") - pl.col("reference_mean")).alias("delta_mean"),
                        (pl.col("total_capacity") - pl.col("reference_total")).alias("delta_total"),
                        (
                            (pl.col("total_capacity") - pl.col("reference_total"))
                            / pl.col("reference_total")
                            * 100.0
                        ).alias("delta_total_percent"),
                    )
                    .select(
                        "scope_type",
                        "scope",
                        "model",
                        "variant",
                        "locations",
                        "mean_capacity",
                        "median_capacity",
                        "p10",
                        "p90",
                        "total_capacity",
                        "delta_mean",
                        "delta_total",
                        "delta_total_percent",
                    )
                )
                outputs.append(stats)
    return pl.concat(outputs, how="vertical").sort("scope_type", "scope", "model", "variant")


def _driver_counts(frame: pl.DataFrame) -> pl.DataFrame:
    outputs: list[pl.DataFrame] = []
    for model in MODEL_NAMES:
        driver = f"{model}_driver"
        global_counts = (
            frame.group_by(driver)
            .agg(pl.len().alias("locations"))
            .with_columns(
                pl.lit("global").alias("scope_type"),
                pl.lit("global").alias("scope"),
                pl.lit(model).alias("model"),
                pl.col(driver).alias("driver"),
                (pl.col("locations") / frame.height).alias("share"),
            )
            .select("scope_type", "scope", "model", "driver", "locations", "share")
        )
        outputs.append(global_counts)
        super_counts = (
            frame.with_columns(pl.col("super_region").fill_null("unknown"))
            .group_by("super_region", driver)
            .agg(pl.len().alias("locations"))
            .with_columns(
                pl.col("locations").sum().over("super_region").alias("scope_locations")
            )
            .with_columns(
                pl.lit("super_region").alias("scope_type"),
                pl.col("super_region").alias("scope"),
                pl.lit(model).alias("model"),
                pl.col(driver).alias("driver"),
                (pl.col("locations") / pl.col("scope_locations")).alias("share"),
            )
            .select("scope_type", "scope", "model", "driver", "locations", "share")
        )
        outputs.append(super_counts)
    return pl.concat(outputs, how="vertical").sort(
        "scope_type", "scope", "model", "locations", descending=[False, False, False, True]
    )


def _anchor_stats(frame: pl.DataFrame, anchors_path: Path) -> pl.DataFrame:
    anchors = load_saturation_anchors(anchors_path)
    rows: list[dict[str, object]] = []
    for model in MODEL_NAMES:
        for variant, capacity_column in (
            ("raw", f"{model}_capacity"),
            ("rank_matched", f"{model}_rank_matched_capacity"),
        ):
            capacity_frame = frame.select(
                "location_tag",
                *ANCHOR_SCOPE_COLUMNS,
                pl.col(capacity_column).alias("local_population_capacity"),
            )
            for row in evaluate_saturation_anchors(anchors, capacity_frame):
                rows.append({"model": model, "variant": variant, **row})
    return pl.DataFrame(rows).sort("model", "variant", "id")


def _render_report(
    *,
    global_stats: pl.DataFrame,
    scope_stats: pl.DataFrame,
    driver_counts: pl.DataFrame,
    source_status: pl.DataFrame,
    deployed_parity: list[dict[str, object]],
    anchor_stats: pl.DataFrame,
) -> str:
    lines = [
        "# Population-capacity model comparison",
        "",
        "Analysis only: no generated mod files were written.",
        "",
        "## Models",
        "",
        "- `current`: deployed piecewise staple formula.",
        "- `current_plus_rescue`: current score, floored by pastoral, fishing, horticultural, and foraging pathways.",
        "- `smooth_support`: smooth crop score plus diminishing livestock/fish/regional support.",
        "- `regime_paths`: maximum of crop, pastoral, fishing, horticultural, and foraging pathways.",
        "- `tiered_top3`: calorie-tier weights followed by an 82%/13%/5% top-three blend.",
        "",
        "`rank_matched` assigns the current global capacity distribution according to each candidate's",
        "location ranking. Its regional deltas therefore show redistribution rather than global inflation",
        "or deflation.",
        "",
        "## Source and parity checks",
        "",
        f"- Ready goods: {source_status.filter(pl.col('status') == 'ready').height}/{source_status.height}",
        "- Reimplemented current formula: exact parity with the production function.",
    ]
    parity = deployed_parity[0]
    lines.append(
        "- Deployed static modifiers: "
        f"{parity['matching']} matching, {parity['mismatched']} mismatched, "
        f"{parity['missing_from_deployed']} missing, {parity['extra_in_deployed']} extra."
    )
    lines.extend(
        [
            "",
            "## Global raw distributions",
            "",
            _markdown_table(
                global_stats,
                (
                    "model",
                    "raw_mean",
                    "raw_median",
                    "raw_p10",
                    "raw_p90",
                    "raw_delta_mean",
                    "raw_mean_absolute_change",
                    "rank_matched_mean_absolute_change",
                    "spearman_vs_current",
                ),
            ),
        ]
    )

    anchor_summary = (
        anchor_stats.filter(pl.col("training_constraint"))
        .group_by("model", "variant")
        .agg(
            (pl.col("status") == "pass").sum().alias("pass"),
            (pl.col("status") == "below_mean_floor").sum().alias("below_mean_floor"),
            (pl.col("status") == "below_median_floor").sum().alias("below_median_floor"),
        )
        .sort("model", "variant")
    )
    lines.extend(
        [
            "",
            "## Saturation-anchor checks",
            "",
            "These are floor constraints, so raw global inflation can improve them without improving spatial ranking.",
            "",
            _markdown_table(
                anchor_summary,
                ("model", "variant", "pass", "below_mean_floor", "below_median_floor"),
            ),
        ]
    )

    global_drivers = driver_counts.filter(pl.col("scope_type") == "global")
    lines.extend(["", "## Dominant drivers", ""])
    for model in CANDIDATE_MODELS:
        top = global_drivers.filter(pl.col("model") == model).sort("locations", descending=True).head(8)
        lines.extend([f"### {model}", "", _markdown_table(top, ("driver", "locations", "share")), ""])

    lines.extend(["## Largest rank-matched super-region shifts", ""])
    for model in CANDIDATE_MODELS:
        rows = scope_stats.filter(
            (pl.col("scope_type") == "super_region")
            & (pl.col("variant") == "rank_matched")
            & (pl.col("model") == model)
        )
        selected = pl.concat(
            [rows.sort("delta_mean", descending=True).head(6), rows.sort("delta_mean").head(6)],
            how="vertical",
        ).unique(subset=["scope"], keep="first")
        lines.extend(
            [
                f"### {model}",
                "",
                _markdown_table(
                    selected.sort("delta_mean", descending=True),
                    ("scope", "locations", "mean_capacity", "delta_mean", "delta_total_percent"),
                ),
                "",
            ]
        )

    lines.extend(["## Largest rank-matched region shifts", ""])
    for model in CANDIDATE_MODELS:
        rows = scope_stats.filter(
            (pl.col("scope_type") == "region")
            & (pl.col("variant") == "rank_matched")
            & (pl.col("model") == model)
        )
        selected = pl.concat(
            [rows.sort("delta_mean", descending=True).head(10), rows.sort("delta_mean").head(10)],
            how="vertical",
        ).unique(subset=["scope"], keep="first")
        lines.extend(
            [
                f"### {model}",
                "",
                _markdown_table(
                    selected.sort("delta_mean", descending=True),
                    ("scope", "locations", "mean_capacity", "delta_mean", "delta_total_percent"),
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _markdown_table(frame: pl.DataFrame, columns: tuple[str, ...]) -> str:
    rows = frame.select(*columns).to_dicts()
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    body = []
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                value = f"{value:.4f}"
            values.append(str(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body])


def _quantile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _average_ranks(values: list[int]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = (start + end - 1) / 2.0
        for position in range(start, end):
            ranks[order[position]] = average_rank
        start = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    if left_scale == 0.0 or right_scale == 0.0:
        return 0.0
    return numerator / (left_scale * right_scale)


if __name__ == "__main__":
    raise SystemExit(main())
