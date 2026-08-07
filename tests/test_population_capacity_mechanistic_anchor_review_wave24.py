from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave24_anchor_review_blocks_scale_promotion_and_deployment() -> None:
    path = ROOT / "research/population_capacity/diagnostics/mechanistic_anchor_review_wave24.json"
    review = json.loads(path.read_text(encoding="utf-8"))
    assert review["status"] == "superseded"
    assert review["superseded_by"] == "mechanistic_anchor_review_wave25.json"
    assert review["summary"]["vetted_interval_anchor_count"] == 3
    assert review["summary"]["vetted_lower_bound_count"] == 24
    assert review["summary"]["direct_lower_bound_failure_count"] == 1
    assert review["summary"]["pipeline_reported_lower_bound_failure_count"] == 0
    assert review["acceptance_conclusion"]["promote_any_interval_to_scale_anchor"] is False
    assert review["acceptance_conclusion"]["deployment_allowed"] is False


def test_wave24_review_catches_hokoham_and_greater_angkor_diagnostics() -> None:
    path = ROOT / "research/population_capacity/diagnostics/mechanistic_anchor_review_wave24.json"
    review = json.loads(path.read_text(encoding="utf-8"))
    rows = {row["anchor_id"]: row for row in review["vetted_lower_bound_rows"]}
    assert rows["hohokam_lower_salt_1150_1450_capacity_lower_bound"]["quality"] == "severe_overprediction"
    assert rows["greater_angkor_1181_1300_population_lower_bound_wave5"]["pass"] is False
