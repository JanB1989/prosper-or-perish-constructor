from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research" / "population_capacity" / "diagnostics" / "training_readiness_wave31.json"


def test_readiness_report_distinguishes_training_from_acceptance() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["training_allowed"] is True
    assert report["deployment"]["acceptance_allowed"] is False
    assert report["deployment"]["normalization_applied"] is False
    assert report["physical_closure"]["locations"] == 20_929
    assert report["physical_closure"]["required_crop_mode_engine_rows"] == 1_925_468
    assert report["physical_closure"]["primary_unresolved_required_labels"] == 0
    assert report["fit_and_generalization"]["selected_candidate"] == "mechanistic"
    assert report["fit_and_generalization"]["grouped_interval_pass_rate"] == 1.0
    assert report["fit_and_generalization"]["grouped_lower_bound_pass_rate"] == 1.0
    assert report["status"] == "trained_but_not_acceptance_ready"
    assert report["remaining_acceptance_blockers"]


def test_readiness_report_carries_current_source_hashes() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["physical_closure"]["label_hash_matches_closure"] is True
    assert report["input_artifacts"]["label_audit_sha256"]
    assert report["input_artifacts"]["closure_manifest_sha256"]
    assert report["input_artifacts"]["generalization_audit_sha256"]
