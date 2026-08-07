"""Regression checks for the wave-29 Awaji/Wakasa register revalidation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "research/population_capacity/evidence_packets/asia_japan_register_revalidation_wave29.json"
CROSSWALK = ROOT / "research/population_capacity/crosswalks/asia_japan_register_revalidation_wave29.json"
DIAGNOSTIC = ROOT / "research/population_capacity/diagnostics/asia_japan_register_revalidation_wave29.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_awaji_register_floor_is_mappable_and_not_an_upper_target() -> None:
    records = {row["anchor_id"]: row for row in _load(PACKET)["records"]}
    awaji = records["japan_awaji_1280_local_food_floor_revalidation_wave29"]

    assert awaji["status"] == "vetted"
    assert awaji["role"] == "lower_bound"
    assert awaji["population_low"] == 14631
    assert awaji["capacity_low"] == 14631
    assert awaji["saturation_low"] is None
    assert awaji["local_food_low"] == 0.75
    assert "bracketed 20,483" in awaji["interval_semantics"]
    assert "Table 1.3" in awaji["citation_details"][0]


def test_wakasa_is_retained_without_a_corrupt_substitute_boundary() -> None:
    records = {row["anchor_id"]: row for row in _load(PACKET)["records"]}
    wakasa = records["japan_wakasa_1280_local_food_floor_revalidation_wave29"]

    assert wakasa["status"] == "validation_only"
    assert wakasa["role"] == "validation_only"
    assert wakasa["population_low"] == 14215
    assert wakasa["crosswalk_status"] == "unresolved"
    assert wakasa["eu5_selector"]["include"] == ["location_tag=__unmapped_wakasa_revalidation_wave29__"]


def test_wave29_crosswalk_and_gate_dispositions_are_explicit() -> None:
    rows = {row["anchor_id"]: row for row in _load(CROSSWALK)["crosswalks"]}
    awaji = rows["japan_awaji_1280_local_food_floor_revalidation_wave29"]
    wakasa = rows["japan_wakasa_1280_local_food_floor_revalidation_wave29"]

    assert awaji["resolution_class"] == "mapped"
    assert awaji["coverage_fraction"] == 0.95
    assert wakasa["resolution_class"] == "validation_only"
    assert wakasa["coverage_fraction"] == 0.0

    gate = _load(DIAGNOSTIC)["quality_gate"]
    assert gate["new_two_sided_anchor_groups"] == 0
    assert gate["new_vetted_one_sided_anchor_groups"] == 1
    assert gate["promoted"] == ["japan_awaji_1280_local_food_floor_revalidation_wave29"]
