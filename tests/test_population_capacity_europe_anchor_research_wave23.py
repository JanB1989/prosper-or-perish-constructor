from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import (
    load_crosswalk_proposals,
    load_evidence_packets,
)


ROOT = Path(__file__).resolve().parents[1]


def test_europe_wave23_packets_are_valid_and_not_training_anchors() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, _ = load_evidence_packets(packet_root)
    ids = {
        "faroe_1300_population_validation_wave23",
        "flanders_1300_population_validation_wave23",
        "england_norfolk_1290_population_validation_wave23",
        "england_lincolnshire_1290_population_validation_wave23",
        "tuscany_1300_food_trade_validation_wave23",
    }
    selected = {str(packet["anchor_id"]): packet for packet in packets if packet.get("anchor_id") in ids}
    assert set(selected) == ids
    assert not any(anchor_id in issues for anchor_id in ids)
    assert all(packet["role"] in {"validation_only", "excluded"} for packet in selected.values())
    assert all(packet["status"] in {"validation_only", "rejected"} for packet in selected.values())
    assert all(packet["capacity_low"] is None for packet in selected.values())


def test_europe_wave23_crosswalks_exist_and_summary_has_no_new_scale_anchor() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    proposals, _ = load_crosswalk_proposals(ROOT / "research" / "population_capacity" / "crosswalks")
    ids = {
        "faroe_1300_population_validation_wave23",
        "flanders_1300_population_validation_wave23",
        "england_norfolk_1290_population_validation_wave23",
        "england_lincolnshire_1290_population_validation_wave23",
        "tuscany_1300_food_trade_validation_wave23",
    }
    assert ids.issubset(proposals)
    summary = json.loads(
        (ROOT / "research/population_capacity/diagnostics/europe_anchor_research_wave23.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["new_training_eligible_anchor_count"] == 0
    assert summary["new_validation_case_count"] == 3
    assert summary["new_rejected_case_count"] == 1
