from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave25_is_the_active_canonical_anchor_review() -> None:
    review = json.loads(
        (ROOT / "research/population_capacity/diagnostics/mechanistic_anchor_review_wave25.json").read_text(
            encoding="utf-8"
        )
    )
    assert review["status"] == "active"
    assert review["supersedes"] == "mechanistic_anchor_review_wave24.json"
    assert review["direct_frozen_gate"]["passed"] is False
    assert review["direct_frozen_gate"]["failed_lower_bound_anchor_ids"] == [
        "greater_angkor_1181_1300_population_lower_bound_wave5"
    ]
    assert review["grouped_holdout"]["frozen_vs_grouped_mismatch_rows"] == 0
    assert review["acceptance_conclusion"]["deployment_allowed"] is False
