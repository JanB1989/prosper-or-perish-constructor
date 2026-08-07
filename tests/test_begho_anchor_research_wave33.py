from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import (
    load_crosswalk_proposals,
    load_evidence_packets,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "research" / "population_capacity" / "evidence_packets" / "africa_begho_local_food_pressure_research_wave33.json"
CROSSWALK = ROOT / "research" / "population_capacity" / "crosswalks" / "africa_begho_local_food_pressure_research_wave33.json"
AUDIT = ROOT / "research" / "population_capacity" / "diagnostics" / "anchor_search_wave33_begho.json"


def test_begho_pass_is_closed_as_a_rejection_not_a_training_label() -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    record = packet["records"][0]
    assert record["anchor_id"] == "begho_1400_1500_urban_population_rejection_wave33"
    assert record["population_low"] == 5_000
    assert record["population_high"] == 10_000
    assert record["year_start"] == 1100
    assert record["year_end"] == 1500
    assert record["status"] == "rejected"
    assert record["role"] == "validation_only"
    assert record["coverage_fraction"] == 0.0
    assert record["local_food_low"] is None
    assert record["saturation_low"] is None
    assert record["capacity_low"] is None
    assert any("peak_population_date" in flag for flag in record["shock_flags"])
    serialized = json.dumps(record)
    assert "starting_population" not in serialized
    assert "hyde_population" not in serialized
    assert "rgo_output_modifier" not in serialized


def test_begho_packet_and_crosswalk_are_visible_to_append_only_audits() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, _ = load_evidence_packets(packet_root)
    assert not issues
    record = next(row for row in packets if row["anchor_id"] == "begho_1400_1500_urban_population_rejection_wave33")
    assert record["source_family"] == "begho_west_african_trade_archaeology"
    assert record["status"] == "rejected"

    proposals, _ = load_crosswalk_proposals(ROOT / "research" / "population_capacity" / "crosswalks")
    proposal = proposals["begho_1400_1500_urban_population_rejection_wave33"]
    assert proposal["crosswalk_status"] == "unresolved"
    assert proposal["coverage_fraction"] == 0.0
    assert proposal["mapped_area_km2"] == 7728.677992
    assert proposal["candidate_role"] == "validation_only"


def test_begho_is_not_added_to_the_canonical_training_registry() -> None:
    registry_text = (ROOT / "population_capacity_benchmarks.toml").read_text(encoding="utf-8")
    assert "begho_1400_1500_urban_population_rejection_wave33" not in registry_text


def test_begho_search_audit_closes_every_promotion_gate_explicitly() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["decision"]["status"] == "rejected"
    assert audit["decision"]["promote_to_two_sided_target"] is False
    assert audit["decision"]["promote_to_lower_bound"] is False
    assert audit["decision"]["promote_to_scale_anchor"] is False
    assert audit["evidence"]["date_compatibility"]["status"] == "fail_for_1337_scale"
    assert audit["evidence"]["population_semantics"]["interval_people"] == [5000, 7500, 10000]
    assert audit["evidence"]["boundary"]["coverage_fraction"] == 0.0
    assert audit["forbidden_fields_consulted"] == []
