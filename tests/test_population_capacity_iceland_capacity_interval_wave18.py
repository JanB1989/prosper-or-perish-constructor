from __future__ import annotations

import json
from pathlib import Path

from prosper_or_perish_population_capacity.evidence_packets import (
    load_crosswalk_proposals,
    load_evidence_packets,
)


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_ID = "iceland_1290_1330_natural_capacity_interval_wave18"


def test_iceland_interval_anchor_is_independent_and_denylisted_fields_are_absent() -> None:
    packet_path = ROOT / "research" / "population_capacity" / "evidence_packets" / "europe_iceland_capacity_interval_wave18.json"
    raw = json.loads(packet_path.read_text(encoding="utf-8"))
    record = raw["records"][0]
    assert record["anchor_id"] == ANCHOR_ID
    assert record["role"] == "interval_anchor"
    assert record["status"] == "vetted"
    assert record["capacity_low"] == 40000
    assert record["capacity_high"] == 80000
    assert record["coverage_fraction"] == 1.0
    assert record["source_family"] == "iceland_preindustrial_environmental_carrying_capacity"
    assert record["source_family"] not in {"english_demographic_and_manorial_reconstructions", "artois_agrarian_yield_and_crisis_1100_1350"}
    forbidden = {
        "starting_population",
        "eu5_start_population",
        "hyde_population",
        "hyde_cropland",
        "rgo_output_modifier",
        "trade_imports",
    }
    assert not forbidden.intersection(record)
    assert len(record["sources"]) >= 3
    assert any("10.1016/j.scitotenv.2006.08.013" in source for source in record["sources"])


def test_iceland_interval_anchor_loads_with_exact_crosswalk() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, _ = load_evidence_packets(packet_root)
    assert not issues
    matching = [packet for packet in packets if packet.get("anchor_id") == ANCHOR_ID]
    assert len(matching) == 1
    proposals, _ = load_crosswalk_proposals(ROOT / "research" / "population_capacity" / "crosswalks")
    crosswalk = proposals[ANCHOR_ID]
    assert crosswalk["matched_location_count"] == 21
    assert crosswalk["coverage_fraction"] == 1.0
    assert crosswalk["crosswalk_status"] == "exact"
    assert crosswalk["eu5_selector"]["include"] == ["area=iceland_area"]
