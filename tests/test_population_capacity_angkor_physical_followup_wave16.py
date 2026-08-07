from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_angkor_followup_distinguishes_closed_labels_from_feature_uncertainty() -> None:
    path = (
        ROOT
        / "research"
        / "population_capacity"
        / "anchor_dispositions"
        / "asia_greater_angkor_physical_followup_wave16.json"
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    labels = record["crop_water_label_audit"]
    assert labels["rows"] == labels["cells"] * labels["registered_crop_count"]
    assert labels["unresolved_rows"] == 0
    assert labels["semantic_mismatch_rows"] == 0
    assert labels["suspect_zero_rows"] == 0
    assert labels["required_row_contract_closed"] is True
    assert record["policy"]["observed_historical_cropland_share_as_intrinsic_capacity_predictor"] is False
    assert record["acceptance_effect"]["allow_anchor_specific_multiplier"] is False
    fields = {row["field"]: row for row in record["remaining_scientific_work"]}
    assert fields["seasonal_flood_recession_and_deepwater_rice"]["blocking_for_label_closure"] is False
    assert fields["seasonal_flood_recession_and_deepwater_rice"]["blocking_for_final_uncertainty_acceptance"] is True
