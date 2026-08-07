from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import load_crosswalk_proposals, load_evidence_packets


ROOT = Path(__file__).resolve().parents[1]
PACKET_ID = "tuscany_florentine_dominions_1427_catasto_validation_wave32"


def test_tuscany_catasto_packet_is_mapped_but_not_promoted() -> None:
    packets, issues, _ = load_evidence_packets(ROOT / "research/population_capacity/evidence_packets")
    selected = [packet for packet in packets if packet.get("anchor_id") == PACKET_ID]
    assert len(selected) == 1
    assert PACKET_ID not in issues
    packet = selected[0]
    assert packet["status"] == "validation_only"
    assert packet["role"] == "validation_only"
    assert packet["capacity_low"] is None
    assert packet["capacity_high"] is None
    assert packet["eu5_selector"]["exclude"] == ["location_tag=florence"]
    assert any("land abandonment" in item for item in packet["shock_flags"])
    assert "no population interval" in packet["interval_semantics"].lower()


def test_tuscany_catasto_crosswalk_declares_approximate_area_and_city_exclusion() -> None:
    proposals, _ = load_crosswalk_proposals(ROOT / "research/population_capacity/crosswalks")
    assert PACKET_ID in proposals
    crosswalk = proposals[PACKET_ID]
    assert crosswalk["status"] == "validation_only"
    assert crosswalk["candidate_role"] == "validation_only"
    assert crosswalk["boundary_overlap_status"] == "approximate"
    assert crosswalk["coverage_fraction"] is None
    assert crosswalk["eu5_selector"]["exclude"] == ["location_tag=florence"]
    assert "no population or capacity aggregate is rescaled" in crosswalk["resolution_method"].lower()
    assert crosswalk["current_frame_diagnostic"]["capacity_people_p50"] == 1620975
    assert crosswalk["current_frame_diagnostic"]["crop_capacity_people_p50"] == 1615538


def test_tuscany_catasto_packet_keeps_city_and_contado_semantics_separate() -> None:
    packets, _, _ = load_evidence_packets(ROOT / "research/population_capacity/evidence_packets")
    packet = next(packet for packet in packets if packet.get("anchor_id") == PACKET_ID)
    text = " ".join(packet["shock_flags"] + packet["notes"].split())
    assert "city" in text.lower()
    assert "contado" in text.lower()
    assert "imported" in text.lower() or "markets" in text.lower()
