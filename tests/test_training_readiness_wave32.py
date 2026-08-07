from __future__ import annotations

import json
from pathlib import Path


REPORT = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "population_capacity"
    / "diagnostics"
    / "training_readiness_wave32.json"
)


def test_wave32_readiness_includes_new_evidence_without_unlocking_deployment() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["training_allowed"] is True
    assert report["deployment"]["acceptance_allowed"] is False
    wave32 = report["evidence_wave32"]
    assert wave32["new_vetted_lower_bounds"] == 2
    assert wave32["new_scale_anchors"] == 0
    assert wave32["crosswalk"]["crosswalk_complete"] is True
    assert wave32["crosswalk"]["training_required_unresolved_records"] == 0
    assert wave32["pages2k"]["active_1337_records"] == 291
    assert wave32["pages2k"]["records_spanning_1100_1500"] == 204
    assert wave32["euromed2k"]["valid_cells_at_1337"] == 61
    assert wave32["shared_soil_fallow"]["rapa_baseline_p50"] == 34236
    assert wave32["shared_soil_fallow"]["rapa_shared_physics_p50"] == 7705
    assert report["remaining_acceptance_blockers"]
