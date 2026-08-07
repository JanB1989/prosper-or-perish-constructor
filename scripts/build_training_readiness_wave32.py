"""Publish the post-wave32 readiness snapshot without changing any gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "population_capacity"
SOURCE = RESEARCH / "diagnostics" / "training_readiness_wave31.json"
OUTPUT = RESEARCH / "diagnostics" / "training_readiness_wave32.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report = _load(SOURCE)
    lower_bounds_path = RESEARCH / "diagnostics" / "global_in_period_lower_bound_registry_wave32.json"
    soil_path = RESEARCH / "diagnostics" / "shared_soil_fallow_cross_system_audit_wave32.json"
    pages2k_path = RESEARCH / "model_reviews" / "pages2k_uncertainty_audit_wave32.json"
    euromed2k_path = RESEARCH / "model_reviews" / "euromed2k_uncertainty_audit_wave32.json"
    crosswalk_path = ROOT / "artifacts" / "data" / "population_capacity" / "current_capacity_map" / "crosswalk_audit.json"
    lower_bounds = _load(lower_bounds_path)
    soil = _load(soil_path)
    pages2k = _load(pages2k_path)
    euromed2k = _load(euromed2k_path)
    crosswalk = _load(crosswalk_path)

    report["schema_version"] = "population_capacity_training_readiness_v4"
    report["report_id"] = "training_readiness_wave32"
    report["evidence_wave32"] = {
        "new_vetted_lower_bounds": lower_bounds["summary"]["records"],
        "new_scale_anchors": lower_bounds["summary"]["new_scale_anchors"],
        "lower_bound_audit_sha256": _hash(lower_bounds_path),
        "crosswalk": {
            "path": "artifacts/data/population_capacity/current_capacity_map/crosswalk_audit.json",
            "crosswalk_complete": crosswalk.get("crosswalk_complete"),
            "all_mappings_resolved": crosswalk.get("all_mappings_resolved"),
            "unresolved_validation_records": crosswalk.get("unresolved_mapping_rows", 0),
            "training_required_unresolved_records": crosswalk.get("unresolved_required_rows", 0),
            "audit_sha256": _hash(crosswalk_path),
        },
        "shared_soil_fallow": {
            "path": "research/population_capacity/diagnostics/shared_soil_fallow_cross_system_audit_wave32.json",
            "systems": sorted(soil.get("systems", {}).keys()),
            "rapa_baseline_p50": soil.get("scenario_results", {}).get("rapa_nui", {}).get("baseline", {}).get("capacity_people_p50"),
            "rapa_shared_physics_p50": soil.get("scenario_results", {}).get("rapa_nui", {}).get("shared_nutrient_fallow", {}).get("capacity_people_p50"),
            "production_ready": soil.get("interpretation", {}).get("status") == "production_ready",
            "audit_sha256": _hash(soil_path),
        },
        "pages2k": {
            "path": "research/population_capacity/model_reviews/pages2k_uncertainty_audit_wave32.json",
            "active_1337_records": pages2k.get("target_year_record_count"),
            "records_spanning_1100_1500": pages2k.get("window_spanning_record_count"),
            "validation_only": pages2k.get("training_target_allowed") is False,
            "audit_sha256": _hash(pages2k_path),
        },
        "euromed2k": {
            "path": "research/population_capacity/model_reviews/euromed2k_uncertainty_audit_wave32.json",
            "valid_cells_at_1337": euromed2k.get("valid_grid_cells_at_target"),
            "years_1100_1500": euromed2k.get("window_year_count"),
            "validation_only": euromed2k.get("training_target_allowed") is False,
            "audit_sha256": _hash(euromed2k_path),
        },
    }
    report["remaining_acceptance_blockers"] = sorted(set(report["remaining_acceptance_blockers"] + [
        "wave32 climate reconstructions validate covariance only and do not provide absolute 1337 yields",
        "wave32 nutrient/fallow cross-system evidence is diagnostic until a global nutrient-stock implementation is validated",
    ]))
    report["deployment"]["acceptance_allowed"] = False
    report["deployment"]["normalization_applied"] = False
    report["deployment"]["rendered_static_modifier"] = False
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
