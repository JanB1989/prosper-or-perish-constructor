"""Regression checks for the wave-27 anchor revalidation contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "research/population_capacity/evidence_packets/global_anchor_revalidation_wave27.json"
CROSSWALK = ROOT / "research/population_capacity/crosswalks/global_anchor_revalidation_wave27.json"
DIAGNOSTIC = ROOT / "research/population_capacity/diagnostics/global_anchor_revalidation_wave27.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_faroe_floor_is_revalidated_for_imported_grain_and_supersedes_old_floor() -> None:
    packet = _load(PACKET)
    records = {record["anchor_id"]: record for record in packet["records"]}
    faroe = records["faroe_1298_1327_local_support_floor_revalidation_wave27"]

    assert faroe["status"] == "vetted"
    assert faroe["role"] == "lower_bound"
    assert faroe["supersedes_anchor_ids"] == ["faroe_1300_local_support_floor_wave3"]
    assert faroe["local_food_low"] == 0.70
    assert faroe["local_food_central"] == 0.75
    assert faroe["capacity_low"] == 1890
    assert "imported grain" in faroe["interval_semantics"]
    assert faroe["saturation_low"] is None


def test_wave27_does_not_promote_unmapped_or_unsaturated_candidates() -> None:
    packet = _load(PACKET)
    records = packet["records"]

    assert all(
        record["role"] in {"lower_bound", "validation_only", "excluded"}
        for record in records
    )
    assert all(
        record["role"] != "lower_bound"
        or record["crosswalk_status"] in {"high", "exact"}
        for record in records
    )
    assert not any(
        record["role"] == "validation_only" and record["status"] == "vetted"
        for record in records
    )


def test_wave27_crosswalk_declares_faroe_coverage_and_keeps_other_boundaries_unmapped() -> None:
    crosswalk = _load(CROSSWALK)
    rows = {row["anchor_id"]: row for row in crosswalk["crosswalks"]}

    faroe = rows["faroe_1298_1327_local_support_floor_revalidation_wave27"]
    assert faroe["coverage_fraction"] == 0.986
    assert faroe["crosswalk_status"] == "high"
    assert faroe["matched_location_count"] == 1

    for anchor_id in (
        "fayyum_nile_1245_local_capacity_recheck_wave27",
        "japan_kamakura_province_register_recheck_wave27",
        "suzhou_pingjiang_1290_local_intensive_recheck_wave27",
        "lake_titicaca_raised_fields_1000_1400_recheck_wave27",
    ):
        row = rows[anchor_id]
        assert row["coverage_fraction"] == 0.0
        assert row["crosswalk_status"] == "unresolved"
        assert row["candidate_role"] == "validation_only"


def test_wave27_diagnostic_records_exact_gate_and_missing_evidence() -> None:
    diagnostic = _load(DIAGNOSTIC)
    gate = diagnostic["quality_gate"]

    assert gate["new_two_sided_anchor_groups"] == 0
    assert gate["new_vetted_one_sided_anchor_groups"] == 1
    assert gate["faroe_old_floor_superseded"] is True
    assert gate["forbidden_fields_used"] is False
    assert gate["unresolved_required_training_rows"] == 0
    assert diagnostic["next_research_queue"]
