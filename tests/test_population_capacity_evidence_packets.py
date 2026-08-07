from __future__ import annotations

from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import (
    load_crosswalk_proposals,
    load_evidence_packets,
)


ROOT = Path(__file__).resolve().parents[1]


def test_research_packets_are_closed_and_denylisted_fields_are_absent() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, hashes = load_evidence_packets(packet_root)
    assert len(hashes) >= 4
    assert len(packets) >= 50
    assert not issues
    forbidden = {
        "starting_population",
        "eu5_start_population",
        "hyde_population",
        "hyde_cropland",
        "rgo_output_modifier",
        "trade_imports",
    }
    assert not any(forbidden.intersection(packet) for packet in packets)
    assert {packet["super_region"] for packet in packets} >= {
        "Europe",
        "Asia",
        "Africa",
        "America/Oceania",
    }


def test_every_researched_packet_has_a_crosswalk_proposal() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, _ = load_evidence_packets(packet_root)
    proposals, hashes = load_crosswalk_proposals(ROOT / "research" / "population_capacity" / "crosswalks")
    assert not issues
    assert len(hashes) >= 4
    assert {packet["anchor_id"] for packet in packets}.issubset(proposals)
