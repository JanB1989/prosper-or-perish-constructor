"""Contracts for the wave-28 uncertainty and historical-risk validation layer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research/population_capacity/physical_validation/uncertainty_validation_wave28.json"
WAVE28 = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave28"


def test_wave28_registry_is_validation_only_and_explicitly_blocked() -> None:
    record = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert record["target_year"] == 1337
    assert record["acceptance"]["modern_global_relative_risk_layer_acquired"] is True
    assert record["acceptance"]["historical_global_1100_1500_annual_absolute_yield_closed"] is False
    assert record["acceptance"]["parameter_uncertainty_closed"] is False
    assert record["acceptance"]["mechanistic_p10_p90_gate_unblocked"] is False
    assert record["acceptance"]["training_target_added"] is False
    assert len(record["acceptance"]["blocking_gaps"]) >= 4
    for source in record["sources"]:
        assert source["training_target_allowed"] is False
        assert isinstance(source["validation_allowed"], bool)
    lpj = next(source for source in record["sources"] if source["source_id"].startswith("isimip2a_lpjguess"))
    assert lpj["mapping"]["location_count"] == 20929
    assert lpj["semantics"]["1337_absolute_yield"] is False
    assert lpj["semantics"]["population_target"] is False


def test_faostat_mapping_has_full_location_item_matrix_when_artifacts_exist() -> None:
    coverage_path = WAVE28 / "faostat_location_crop_risk_coverage_wave28.csv"
    location_path = WAVE28 / "faostat_location_crop_risk_wave28.csv"
    if not coverage_path.exists() or not location_path.exists():
        return
    coverage = pl.read_csv(coverage_path)
    locations = pl.read_csv(location_path)
    assert coverage.height == 18
    assert locations.height == 20929 * 18
    assert coverage["resolved_location_fraction"].min() >= 0.0
    assert coverage["resolved_location_fraction"].max() <= 1.0
    states = set(locations["label_state"].unique().to_list())
    assert "unmapped_country" in states
    assert "missing_country_item_series" in states
    assert "resolved_modern_relative_risk" in states


def test_faostat_manifest_hashes_and_semantics_are_reproducible_when_present() -> None:
    manifest_path = WAVE28 / "faostat_risk_mapping_manifest_wave28.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["coverage"]["location_count"] == 20929
    assert manifest["coverage"]["modern_year_window"] == [1961, 2024]
    assert manifest["semantics"]["historical_1337_target"] is False
    assert manifest["semantics"]["population_target"] is False
    for key in ("crosswalk", "country_risk", "superregion_risk", "location_risk", "coverage_by_item"):
        path = ROOT / manifest["outputs"][key]
        digest_key = f"{key}_sha256"
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["outputs"][digest_key]


def test_historical_risk_manifest_keeps_price_famine_evidence_one_sided() -> None:
    manifest_path = WAVE28 / "historical_risk_validation_manifest_wave28.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["acceptance"]["one_sided_historical_risk_validation_available"] is True
    assert manifest["acceptance"]["absolute_1100_1500_yield_target_available"] is False
    assert manifest["acceptance"]["famine_price_evidence_can_set_capacity"] is False
    clark = next(source for source in manifest["sources"] if source["source_id"].startswith("clark_"))
    stats = clark["semantics"]["reported_risk_statistics"]
    assert stats["price_autocorrelation_1208_1349"] > stats["yield_autocorrelation_1208_1349"]


def test_lpjguess_model_spread_is_explicitly_modern_and_hash_pinned() -> None:
    manifest_path = WAVE28 / "isimip_lpjguess_uncertainty_manifest_wave28.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["coverage"]["location_count"] == 20929
    assert manifest["coverage"]["model_skill_rows"] == 12
    assert manifest["semantics"]["1337_technology"] is False
    assert manifest["semantics"]["training_target_allowed"] is False
    for key in ("rainfed", "full_irrigation"):
        path = ROOT / manifest["files"][key]["path"]
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][key]["sha256"]
