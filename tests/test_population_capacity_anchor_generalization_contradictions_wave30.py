"""Regression gate for exact-boundary high-capacity validation contradictions."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "research/population_capacity/diagnostics/anchor_generalization_contradiction_audit_wave30.json"
BENCHMARK = ROOT / "artifacts/data/population_capacity/benchmark_audit/benchmark_audit.csv"
MODEL_SELECTION = ROOT / "artifacts/data/population_capacity/current_capacity_map/model_selection.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exact_rapa_nui_holdout_failure_is_explicit_and_not_reclassified() -> None:
    diagnostic = _load(DIAGNOSTIC)
    contradiction = diagnostic["hard_exact_boundary_contradictions"][0]

    assert contradiction["anchor_id"] == "rapa_nui_food_limits"
    assert contradiction["boundary_status"] == "exact"
    assert contradiction["aggregate_interval_status"] == "fail"
    assert contradiction["ratio_to_interval_central"] > 3.0
    assert diagnostic["gate_effect"]["new_training_targets"] == 0
    assert diagnostic["gate_effect"]["scientific_acceptance_blocked"] is True


def test_current_benchmark_audit_matches_the_recorded_rapa_nui_contradiction() -> None:
    rows = {row["anchor_id"]: row for row in csv.DictReader(BENCHMARK.open(encoding="utf-8"))}
    row = rows["rapa_nui_food_limits"]

    assert row["role"] == "validation_only"
    assert row["boundary_overlap_status"] == "exact"
    assert row["crosswalk_status"] == "exact"
    assert row["aggregate_interval_status"] == "fail"
    assert float(row["predicted_capacity"]) > float(row["capacity_high"])
    assert float(row["aggregate_interval_ratio_to_central"]) > 3.0


def test_model_selection_does_not_claim_scientific_acceptance() -> None:
    selection = _load(MODEL_SELECTION)

    assert selection["scientific_acceptance_complete"] is False
    assert selection["deployment_status"] == "provisional"
    assert selection["physical_invariant_failures"] == []
