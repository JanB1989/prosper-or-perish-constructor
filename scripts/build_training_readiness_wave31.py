"""Build the current population-capacity training/acceptance readiness report.

This is deliberately a reporting step.  It does not relax any acceptance gate,
modify labels, normalize capacities, or render game modifiers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "data" / "population_capacity"
RESEARCH = ROOT / "research" / "population_capacity"
OUT = RESEARCH / "diagnostics" / "training_readiness_wave31.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    label_audit = _load(ARTIFACTS / "label_audit" / "label_audit.json")
    closure = _load(ARTIFACTS / "current_capacity_map" / "physical_closure_manifest.json")
    selection = _load(ARTIFACTS / "current_capacity_map" / "model_selection.json")
    generalization = _load(ARTIFACTS / "current_capacity_map" / "generalization_audit.json")
    evidence = _load(ARTIFACTS / "current_capacity_map" / "evidence_registry.json")
    crop_gap = _load(RESEARCH / "physical_validation" / "crop_water_gap_wave31.json")
    uncertainty = _load(RESEARCH / "model_reviews" / "uncertainty_evidence_audit_wave31.json")
    rapa = _load(RESEARCH / "diagnostics" / "anchor_generalization_contradiction_audit_wave31.json")
    nutrient = _load(RESEARCH / "diagnostics" / "rapa_nui_shared_nutrient_sensitivity_wave31.json")

    crop_audit = label_audit
    grouped_evidence = generalization.get("evidence_merge", {})
    candidates = pl.read_parquet(ARTIFACTS / "current_capacity_map" / "location_candidates.parquet")
    mechanistic_p50 = int(candidates.get_column("capacity_people_p50").sum())

    closure_labels = closure.get("source_hashes", {}).get("crop_modes", "")
    label_hash = label_audit.get("labels_sha256", "")
    blockers: list[str] = []
    if not closure.get("training_allowed"):
        blockers.append("physical_closure_not_ready")
    if int(crop_audit.get("unresolved_required_labels", 1)) != 0:
        blockers.append("unresolved_required_crop_labels")
    if not crop_gap.get("acceptance", {}).get("training_unblocked", False):
        blockers.extend(crop_gap.get("acceptance", {}).get("blocking_gaps", []))
    if not uncertainty.get("p10_p50_p90_capacity_propagation_ready", False):
        blockers.extend(uncertainty.get("issues", []))
        blockers.append("historical_global_1100_1500_absolute_tail_not_closed")
    if rapa.get("rapa_nui_food_limits", {}).get("status") == "fail":
        blockers.append("held_out_rapa_nui_food_limit_requires_shared_physical_explanation")

    report = {
        "schema_version": "population_capacity_training_readiness_v3",
        "report_id": "training_readiness_wave31",
        "created_on": "2026-08-04",
        "status": "trained_but_not_acceptance_ready" if blockers else "acceptance_ready",
        "training_allowed": bool(closure.get("training_allowed") and grouped_evidence.get("mechanistic_training_ready", False)),
        "physical_closure": {
            "locations": closure.get("location_count"),
            "required_crop_mode_engine_rows": crop_audit.get("matrix_rows"),
            "primary_unresolved_required_labels": crop_audit.get("primary_unresolved_required_labels"),
            "challenger_unresolved_required_labels": crop_audit.get("challenger_unresolved_required_labels"),
            "source_completeness": crop_audit.get("source_completeness"),
            "primary_source_fraction": crop_audit.get("primary_source_fraction"),
            "productive_mode_coverage": crop_audit.get("productive_mode_coverage"),
            "exact_pyaez_rows": crop_audit.get("challenger_exact_rows"),
            "same_geography_physical_fallback_rows": crop_audit.get("challenger_fallback_rows"),
            "label_audit_hash": crop_audit.get("labels_sha256"),
            "physical_closure_manifest_hash": closure.get("manifest_sha256"),
            "label_hash_matches_closure": bool(label_hash and closure_labels and label_hash == closure_labels),
        },
        "evidence_and_mapping": {
            "packet_count": grouped_evidence.get("packet_count"),
            "training_eligible_groups": grouped_evidence.get("training_eligible_count"),
            "two_sided_interval_groups": grouped_evidence.get("two_sided_interval_count"),
            "lower_bound_groups": grouped_evidence.get("lower_bound_count"),
            "source_families": grouped_evidence.get("source_family_count"),
            "super_regions": grouped_evidence.get("super_region_count"),
            "training_blockers": grouped_evidence.get("training_blockers", []),
        },
        "fit_and_generalization": {
            "selected_candidate": generalization.get("selected_candidate"),
            "mechanistic_global_capacity_people_p50": mechanistic_p50,
            "grouped_holdout_scored_rows": generalization.get("grouped_holdout_artifact", {}).get("selected_summary", {}).get("scored_rows"),
            "grouped_interval_pass_rate": generalization.get("grouped_holdout_artifact", {}).get("selected_summary", {}).get("interval_pass_rate"),
            "grouped_lower_bound_pass_rate": generalization.get("grouped_holdout_artifact", {}).get("selected_summary", {}).get("lower_bound_pass_rate"),
            "generalization_complete": generalization.get("generalization_complete"),
            "learned_challenger_status": selection.get("learned_model_status"),
        },
        "independent_physical_validation": {
            "crop_water_gap": {
                "path": "research/population_capacity/physical_validation/crop_water_gap_wave31.json",
                "gaez_static_water_response_closed": all(crop_gap.get("acceptance", {}).get(key, False) for key in (
                    "banana_static_water_response_closed",
                    "cassava_static_water_response_closed",
                    "taro_static_water_response_closed",
                )),
                "cassava_modern_interannual_risk_bridge_closed": crop_gap.get("acceptance", {}).get("cassava_modern_interannual_risk_bridge_closed"),
                "banana_taro_annual_risk_closed": bool(crop_gap.get("acceptance", {}).get("banana_modern_interannual_risk_bridge_closed") and crop_gap.get("acceptance", {}).get("taro_modern_interannual_risk_bridge_closed")),
            },
            "uncertainty_evidence": {
                "path": "research/population_capacity/model_reviews/uncertainty_evidence_audit_wave31.json",
                "source_rows": uncertainty.get("source_count"),
                "absolute_1337_training_sources": uncertainty.get("absolute_1337_training_source_count"),
                "independent_risk_validation_complete": uncertainty.get("independent_risk_validation_complete"),
                "p10_p50_p90_capacity_propagation_ready": uncertainty.get("p10_p50_p90_capacity_propagation_ready"),
            },
            "rapa_nui_validation": {
                "predicted_p50": rapa.get("rapa_nui_food_limits", {}).get("current_predicted_capacity_people_p50"),
                "interval": rapa.get("rapa_nui_food_limits", {}).get("capacity_interval_people"),
                "status": rapa.get("rapa_nui_food_limits", {}).get("status"),
                "shared_nutrient_sensitivity_p50": nutrient.get("scenario_summaries", {}).get("rapa_nui", {}).get("shared_combined", {}).get("capacity_people_p50"),
                "role": "held_out_validation_only",
            },
        },
        "remaining_acceptance_blockers": sorted(set(str(value) for value in blockers)),
        "deployment": {
            "acceptance_allowed": False,
            "normalization_applied": False,
            "rendered_static_modifier": False,
            "legacy_modifiers_unchanged": True,
        },
        "input_artifacts": {
            "label_audit_sha256": _sha256(ARTIFACTS / "label_audit" / "label_audit.json"),
            "closure_manifest_sha256": _sha256(ARTIFACTS / "current_capacity_map" / "physical_closure_manifest.json"),
            "model_selection_sha256": _sha256(ARTIFACTS / "current_capacity_map" / "model_selection.json"),
            "generalization_audit_sha256": _sha256(ARTIFACTS / "current_capacity_map" / "generalization_audit.json"),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
