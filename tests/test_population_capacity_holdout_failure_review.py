from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_holdout_failure_review_is_explicit_and_does_not_downgrade_valid_floors() -> None:
    path = (
        ROOT
        / "research"
        / "population_capacity"
        / "research_dispositions"
        / "holdout_lower_bound_failure_review_wave15.json"
    )
    review = json.loads(path.read_text(encoding="utf-8"))
    assert review["policy"]["do_not_weaken_lower_bound_gate"] is True
    assert review["aggregate_decision"]["misclassified_unique_anchors"] == 0
    assert review["aggregate_decision"]["downgraded_unique_anchors"] == 0
    records = {row["anchor_id"]: row for row in review["records"]}
    assert len(records) == 5
    assert records["greater_angkor_1181_1300_population_lower_bound_wave5"]["disposition"] == "retain_lower_bound"
    assert records["iceland_preindustrial_biomass_capacity_floor_wave3"]["disposition"] == "retain_lower_bound_and_block_on_area_repair"
    assert records["upper_mantaro_wanka_ii_1350_1450_population_lower_bound"]["disposition"] == "retain_lower_bound"
    for record in records.values():
        assert record["lower_bound_people"] > 0
        assert 0 < record["predicted_to_floor_ratio"] < 1
        assert len(record["primary_sources"]) >= 2
        assert record["boundary"]["coverage_fraction"] >= 0.95
