from __future__ import annotations

from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import load_crosswalk_proposals, load_evidence_packets


ROOT = Path(__file__).resolve().parents[1]
PACKET_ID = "mallorca_1301_1420_morabeti_validation_wave32"


def test_mallorca_morabeti_is_a_mapped_hostile_validation_case_not_a_target() -> None:
    packets, issues, _ = load_evidence_packets(ROOT / "research/population_capacity/evidence_packets")
    selected = [packet for packet in packets if packet.get("anchor_id") == PACKET_ID]
    assert len(selected) == 1
    assert PACKET_ID not in issues
    packet = selected[0]
    assert packet["status"] == "validation_only"
    assert packet["role"] == "validation_only"
    assert packet["capacity_low"] is None
    assert packet["eu5_selector"]["include"] == ["location_tag=manacor|palma|pollensa"]
    assert "tax-threshold" in " ".join(packet["shock_flags"])
    assert packet["trade_dependence"] == "high_wheat_import_dependence"


def test_mallorca_crosswalk_matches_island_area_and_keeps_imports_out() -> None:
    proposals, _ = load_crosswalk_proposals(ROOT / "research/population_capacity/crosswalks")
    assert PACKET_ID in proposals
    crosswalk = proposals[PACKET_ID]
    assert crosswalk["status"] == "validation_only"
    assert crosswalk["candidate_role"] == "validation_only"
    assert crosswalk["matched_location_count"] == 3
    assert crosswalk["coverage_fraction"] == 0.99
    assert abs(crosswalk["mapped_area_km2"] - 3689.696154) < 1e-6
    assert crosswalk["current_frame_diagnostic"]["capacity_people_p50"] == 126847
    assert crosswalk["current_frame_diagnostic"]["crop_capacity_people_p50"] == 119315
    assert "imported-grain target" in crosswalk["current_frame_diagnostic"]["use"]


def test_mallorca_sources_cover_fiscal_food_and_trade_independently() -> None:
    packets, _, _ = load_evidence_packets(ROOT / "research/population_capacity/evidence_packets")
    packet = next(packet for packet in packets if packet.get("anchor_id") == PACKET_ID)
    source_text = " ".join(packet["sources"])
    assert "3989/aem.2008.v38.i1.64" in source_text
    assert "1344/Svmma2014.3.17" in source_text
    assert "1017/S0212610900010004" in source_text
