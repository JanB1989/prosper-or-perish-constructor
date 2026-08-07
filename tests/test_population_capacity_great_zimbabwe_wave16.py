from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import (
    load_crosswalk_proposals,
    load_evidence_packets,
)


ROOT = Path(__file__).resolve().parents[1]


def test_great_zimbabwe_is_a_conservative_contained_lower_bound() -> None:
    packet_path = (
        ROOT
        / "research"
        / "population_capacity"
        / "evidence_packets"
        / "africa_great_zimbabwe_lower_bound_wave16.json"
    )
    crosswalk_path = (
        ROOT
        / "research"
        / "population_capacity"
        / "crosswalks"
        / "africa_great_zimbabwe_lower_bound_wave16.json"
    )
    packet = json.loads(packet_path.read_text(encoding="utf-8"))["records"][0]
    crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))["crosswalks"][0]

    assert packet["status"] == "vetted"
    assert packet["role"] == "lower_bound"
    assert packet["population_low"] == 10_000
    assert packet["capacity_low"] == 10_000
    assert packet["saturation_central"] is None
    assert packet["coverage_fraction"] == 1.0
    assert packet["crosswalk_status"] == "high"
    assert packet["eu5_selector"] == {"include": ["location_tag=great_zimbabwe"], "exclude": []}
    assert "starting_population" not in json.dumps(packet)
    assert "hyde_population" not in json.dumps(packet)
    assert "rgo_output_modifier" not in json.dumps(packet)

    assert crosswalk["candidate_role"] == "lower_bound"
    assert crosswalk["eu5_selector"] == "location_tag=great_zimbabwe"
    assert crosswalk["area_comparison"]["historical_site_is_contained"] is True
    assert crosswalk["coverage_fraction"] == 1.0
    assert crosswalk["area_comparison"]["area_ratio_historical_to_eu5"] < 0.01


def test_great_zimbabwe_packet_and_crosswalk_are_visible_to_audits() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, _ = load_evidence_packets(packet_root)
    assert not issues
    packet = next(
        row
        for row in packets
        if row["anchor_id"] == "great_zimbabwe_1300_1450_population_lower_bound_wave16"
    )
    assert packet["source_family"] == "great_zimbabwe_unesco_archaeology_ecology"

    proposals, _ = load_crosswalk_proposals(
        ROOT / "research" / "population_capacity" / "crosswalks"
    )
    assert proposals[packet["anchor_id"]]["crosswalk_status"] == "high"
