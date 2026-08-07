from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REGISTRY = (
    REPO
    / "research"
    / "population_capacity"
    / "physical_evidence"
    / "terrestrial_tsetse_scientific_registry.json"
)


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_registry_forbids_modern_proxy_and_regional_multiplier_leakage() -> None:
    registry = _registry()
    policy = registry["policy"]
    assert policy["modern_proxy_is_historical_truth"] is False
    assert policy["unresolved_effect_is_applied"] is False
    assert policy["starting_population_is_predictor_or_target"] is False
    assert policy["regional_multiplier_is_allowed"] is False


def test_dated_npp_alignment_has_four_models_and_explicit_sensitivity_semantics() -> None:
    registry = _registry()
    npp = next(
        row
        for row in registry["resolved_components"]
        if row["component_id"] == "terrestrial_npp_period_alignment"
    )
    assert len(npp["models"]) == 4
    assert len(set(npp["models"])) == 4
    assert npp["state"] == "source_contract_and_sample_alignment_built"
    assert "calibrated probability" in npp["forbidden_use"]
    assert "population target" in npp["forbidden_use"]
    assert any(source["source_id"] == "pmip4_past1000_design" for source in npp["sources"])
    built = npp["built_artifact"]
    assert built["rows"] == 1_339_456
    assert built["locations"] == 20_929
    assert built["unresolved_land_samples"] == 0
    assert built["minimum_valid_models_per_land_sample"] >= 2
    assert built["maximum_used_fallback_distance_km"] <= 250.0
    assert len(built["sha256"]) == 64


def test_tsetse_fallback_is_complete_hashed_and_directionally_validated() -> None:
    registry = _registry()
    tsetse = next(
        row
        for row in registry["resolved_components"]
        if row["component_id"] == "tsetse_600bp_physiological_potential"
    )
    assert tsetse["state"] == "closed_as_lineage_clean_physical_fallback"
    assert "production penalty" in tsetse["forbidden_use"]
    assert "exactly 1.0" in tsetse["effect_policy"]
    built = tsetse["built_artifact"]
    assert built["rows"] == 20_929
    assert built["locations"] == 20_929
    assert built["sample_rows"] == 1_339_456
    assert built["unresolved_numeric_rows"] == 0
    assert built["modern_validation_roc_auc"] >= 0.55
    assert (
        built["modern_detection_mean_exposure"]
        > built["modern_explicit_non_detection_mean_exposure"]
    )
    assert len(built["sha256"]) == 64
    assert len(built["audit_sha256"]) == 64
    assert len(built["source_manifest_sha256"]) == 64


def test_forbidden_or_modern_tsetse_predictors_are_explicitly_rejected() -> None:
    rejected = {
        row["source_family"]: row["state"]
        for row in _registry()["rejected_predictors"]
    }
    assert rejected["PMIP4 past1000 treeFrac/grassFrac/shrubFrac"] == (
        "rejected_forbidden_population_lineage"
    )
    assert rejected["EU5 vegetation and macro-region names"] == (
        "rejected_game_authored_or_geographic_predictor"
    )
    assert rejected["FAO 1990-2020 tsetse atlas"] == "validation_only"


def test_tsetse_gate_allows_training_only_with_neutral_applied_effects() -> None:
    gate = _registry()["training_gate"]
    assert gate["tsetse_physical_feature_training_ready"] is True
    assert gate["training_ready_under_noop_policy"] is True
    assert gate["tsetse_can_close_as_applied_effect_now"] is False
    assert gate["draft_manure_can_close_as_applied_feedback_now"] is False
    assert "exactly 1.0" in gate["required_behavior_until_resolved"]
