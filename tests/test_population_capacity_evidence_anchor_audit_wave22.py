"""Regression checks for the append-only evidence/anchor audit."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research/population_capacity/diagnostics/evidence_anchor_registry_audit_wave22.json"


def _audit() -> dict:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def test_audit_is_append_only_and_required_crosswalks_are_closed() -> None:
    audit = _audit()
    assert audit["append_only"] is True
    assert audit["central_registry_mutated"] is False
    assert audit["pre_fit_status"]["research_contract_complete"] is True
    assert audit["pre_fit_status"]["crosswalk_complete"] is True
    assert audit["registry_counts"]["training_eligible_count"] == 28
    assert audit["registry_counts"]["unresolved_required_crosswalk_rows"] == 0


def test_audit_does_not_claim_final_scientific_acceptance() -> None:
    audit = _audit()
    assert audit["post_fit_status"]["scientific_acceptance_complete"] is False
    assert audit["post_fit_status"]["deployment_status"] == "provisional"
    blockers = " ".join(audit["remaining_acceptance_blockers"])
    assert "crop_capacity_scenario_propagation_complete=false" in blockers
    assert "joint_capacity_uncertainty_complete=false" in blockers


def test_audit_keeps_lower_bounds_one_sided_and_caveated() -> None:
    audit = _audit()
    assert audit["recommendations"]["promote"] == []
    assert audit["recommendations"]["downgrade_to_validation_or_containment_only"]
    assert "all lower_bound records" in audit["recommendations"]["do_not_use_as_global_scale"]
    assert audit["independence_audit"]["effective_holdout_source_family_groups"] == 17
