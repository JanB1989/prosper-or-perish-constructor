from __future__ import annotations

import json
import tomllib
from pathlib import Path

from prosper_or_perish_population_capacity.benchmarks import load_population_benchmarks
from prosper_or_perish_population_capacity.evidence_packets import load_evidence_packets


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research" / "population_capacity" / "diagnostics" / "global_in_period_lower_bound_registry_wave32.json"


def test_wave32_lower_bound_audit_has_vetted_local_food_records_and_no_forbidden_fields() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["summary"] == {
        "records": 2,
        "vetted_lower_bounds": 2,
        "new_independent_source_families": 1,
        "new_scale_anchors": 0,
        "starting_population_or_hyde_or_rgo_predictors": 0,
        "unresolved_mapping_records": 0,
        "remaining_action": "Use both only as one-sided aggregate tests; exact historical polygon reconstruction is still required before either can become a two-sided scale anchor.",
    }
    forbidden = {
        "starting_population",
        "eu5_start_population",
        "hyde_population",
        "hyde_cropland",
        "rgo_output_modifier",
        "trade_imports",
    }
    assert not forbidden.intersection(audit)
    records = {row["anchor_id"]: row for row in audit["records"]}
    assert records["great_zimbabwe_1300_1450_population_lower_bound_wave32"]["population_floor_people"] == 10_000
    assert records["upper_mantaro_wanka_ii_1350_1450_population_lower_bound_wave32"]["population_floor_people"] == 61_000
    for row in records.values():
        assert row["role"] == "lower_bound"
        assert row["review_status"] == "vetted"
        assert row["mapping"]["containment_coverage_fraction"] == 1.0
        assert row["sources"]
        low, central, high = row["local_food_share_interval"]
        assert 0.0 <= low <= central <= high <= 1.0
        assert row["decision"].startswith("retain_vetted_lower_bound")


def test_wave32_records_are_loaded_from_existing_vetted_packets_and_crosswalks() -> None:
    packet_root = ROOT / "research" / "population_capacity" / "evidence_packets"
    packets, issues, _ = load_evidence_packets(packet_root)
    assert not issues
    by_id = {row["anchor_id"]: row for row in packets}
    assert by_id["great_zimbabwe_1300_1450_population_lower_bound_wave16"]["role"] == "lower_bound"
    assert by_id["upper_mantaro_wanka_ii_1350_1450_population_lower_bound"]["role"] == "lower_bound"
    assert by_id["great_zimbabwe_1300_1450_population_lower_bound_wave16"]["coverage_fraction"] == 1.0
    assert by_id["upper_mantaro_wanka_ii_1350_1450_population_lower_bound"]["coverage_fraction"] == 1.0


def test_wave32_toml_entries_are_one_sided_vetted_tests_and_never_scale_anchors() -> None:
    registry = ROOT / "population_capacity_benchmarks.toml"
    benchmarks = load_population_benchmarks(registry)
    by_id = {row.anchor_id: row for row in benchmarks}
    great = by_id["great_zimbabwe_1300_1450_population_lower_bound_wave32"]
    mantaro = by_id["upper_mantaro_wanka_ii_1350_1450_population_lower_bound_wave32"]
    for row in (great, mantaro):
        assert row.role == "lower_bound"
        assert row.validation_test == "lower_bound"
        assert row.review_status == "vetted"
        assert row.trains_scale is False
        assert row.direct_capacity_low is not None
        assert row.direct_capacity_central is None
        assert row.direct_capacity_high is None
        assert row.saturation_low is None
        assert row.saturation_central is None
        assert row.saturation_high is None
        assert row.boundary_overlap_status == "exact"
        assert row.crosswalk_status == "exact"
        assert row.local_food_interval_complete
    assert great.capacity_low == 10_000
    assert mantaro.capacity_low == 61_000
    assert great.source_family_independence == "shared"
    assert mantaro.source_family_independence == "independent"

