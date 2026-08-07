from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_asia_anchor_closure_does_not_promote_observed_population_to_capacity() -> None:
    packet_path = (
        ROOT
        / "research"
        / "population_capacity"
        / "evidence_packets"
        / "asia_mideast_anchor_closure.json"
    )
    crosswalk_path = (
        ROOT
        / "research"
        / "population_capacity"
        / "crosswalks"
        / "asia_mideast_anchor_closure.json"
    )
    packets = json.loads(packet_path.read_text(encoding="utf-8"))["records"]
    crosswalks = json.loads(crosswalk_path.read_text(encoding="utf-8"))["crosswalks"]
    assert len(packets) == 3
    assert len(crosswalks) == 3
    assert {row["anchor_id"] for row in packets} == {
        "korea_gyeongsangdojiriji_1432_aggregate",
        "korea_jinju_mok_1432_population",
        "korea_gyeongju_bu_1432_population",
    }
    for packet, crosswalk in zip(packets, crosswalks, strict=True):
        assert packet["status"] == "blocked"
        assert packet["role"] == "validation_only"
        assert packet["saturation_central"] is None
        assert packet["local_food_central"] is None
        assert packet["coverage_fraction"] == 0.0
        assert crosswalk["crosswalk_status"] == "unresolved"
        assert crosswalk["coverage_fraction"] == 0.0
