from __future__ import annotations

import csv
import json
import tomllib
from pathlib import Path

from prosper_or_perish_population_capacity.benchmarks import load_population_benchmarks


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research" / "population_capacity" / "diagnostics" / "boundary_crosswalk_resolution_audit_wave32b.json"
LATEST_BENCHMARK_AUDIT = ROOT / "artifacts" / "data" / "population_capacity" / "benchmark_audit" / "benchmark_audit.csv"


def test_every_boundary_unresolved_benchmark_has_an_explicit_wave32b_disposition() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    source_ids: set[str] = set()
    with LATEST_BENCHMARK_AUDIT.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["aggregate_interval_status"] == "boundary_unresolved":
                source_ids.add(row["anchor_id"])
    resolved_ids = {row["anchor_id"] for row in audit["records"]}
    # France was resolved during this wave.  The manifest retains the full
    # 26-record pre-resolution input while the regenerated current audit has
    # 25 remaining unresolved records.
    assert len(source_ids) == 25
    assert source_ids.issubset(resolved_ids)
    assert len(resolved_ids) == 26
    assert audit["summary"]["source_unresolved_record_count_before_wave32b"] == 26
    assert audit["summary"]["remaining_unresolved_record_count"] == len(source_ids)
    assert audit["summary"]["records_classified"] == 26
    assert all(row["decision"] for row in audit["records"])


def test_no_required_training_record_remains_unresolved() -> None:
    registry = load_population_benchmarks(ROOT / "population_capacity_benchmarks.toml")
    required = [row for row in registry if row.trains_scale or row.role == "lower_bound"]
    assert required
    assert all(row.boundary_overlap_status not in {"partial", "approximate", "city_only", "mismatch", "unresolved"} for row in required)
    assert all(row.crosswalk_status not in {"partial", "approximate", "city_only", "mismatch", "unresolved"} for row in required)
    assert all(row.review_status == "vetted" for row in required)
    # The one-sided Wave32 records are the only new lower-bound rows and do
    # not become scale anchors simply because their containment is exact.
    assert not any(row.anchor_id.endswith("wave32") and row.trains_scale for row in required)


def test_france_mapping_is_area_weighted_above_gate_but_evidence_is_still_validation_only() -> None:
    registry = load_population_benchmarks(ROOT / "population_capacity_benchmarks.toml")
    france = next(row for row in registry if row.anchor_id == "france_1328_hearths")
    assert france.boundary_overlap_status == "exact"
    assert france.crosswalk_status == "exact"
    assert france.boundary_confidence == "high"
    assert france.role == "validation_only"
    assert france.review_status == "candidate"
    assert france.trains_scale is False
    text = france.mapped_boundary + " " + france.notes
    assert "96.2057%" in text
    assert "20,049.06" in text


def test_great_zimbabwe_and_angkor_keep_containment_semantics_separate_from_exact_boundaries() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rows = {row["anchor_id"]: row for row in audit["records"]}
    great = rows["great_zimbabwe_site_population"]
    assert great["resolution_class"] == "resolved_containment_only_city_negative_control"
    assert great["training_eligible"] is False
    assert great["area_ratio_historical_to_eu5"] < 0.01
    angkor = rows["greater_angkor_diachronic"]
    assert angkor["resolution_class"] == "retained_validation_area_weighted_precision_separate"
    assert angkor["precision_crosswalk"]["area_weight"] < 0.95
    assert angkor["training_eligible"] is False


def test_resolution_manifest_has_no_forbidden_predictor_fields() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    forbidden = {"eu5_start_population", "hyde_population", "hyde_cropland", "rgo_output_modifier", "trade_imports"}
    serialized = json.dumps(audit)
    assert not any(key in serialized for key in forbidden)
