"""Regression checks for the bounded wave-28 Greenland anchor review."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "research/population_capacity/evidence_packets/global_anchor_revalidation_wave28.json"
CROSSWALK = ROOT / "research/population_capacity/crosswalks/global_anchor_revalidation_wave28.json"
DIAGNOSTIC = ROOT / "research/population_capacity/diagnostics/global_anchor_revalidation_wave28.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_greenland_observed_interval_is_not_misused_as_capacity() -> None:
    packet = _load(PACKET)
    record = packet["records"][0]

    assert record["anchor_id"] == "greenland_norse_1290_1340_revalidation_wave28"
    assert record["status"] == "validation_only"
    assert record["role"] == "validation_only"
    assert (record["population_low"], record["population_central"], record["population_high"]) == (1400, 1800, 2200)
    assert record["capacity_low"] is None
    assert record["capacity_central"] is None
    assert record["capacity_high"] is None
    assert record["local_food_central"] is None
    assert "not a local-food capacity interval" in record["interval_semantics"]


def test_greenland_crosswalk_is_explicitly_unmapped_and_non_training() -> None:
    crosswalk = _load(CROSSWALK)["crosswalks"][0]

    assert crosswalk["matched_location_count"] == 0
    assert crosswalk["coverage_fraction"] == 0.0
    assert crosswalk["crosswalk_status"] == "unresolved"
    assert crosswalk["resolution_class"] == "validation_only"
    assert crosswalk["resolution_reason_code"] == "historical_settlement_polygon_and_eu5_intersection_missing"


def test_wave28_gate_does_not_promote_greenland() -> None:
    diagnostic = _load(DIAGNOSTIC)
    gate = diagnostic["quality_gate"]

    assert gate["new_two_sided_anchor_groups"] == 0
    assert gate["new_vetted_one_sided_anchor_groups"] == 0
    assert gate["promoted"] is False
    assert diagnostic["next_research_queue"]
