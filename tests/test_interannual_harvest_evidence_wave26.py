"""Contract tests for the wave-26 harvest-evidence closure artifact.

The documentary Chinese series is useful for relative harvest-risk validation,
but it is not an absolute yield target.  These tests prevent an ordinal grade
or a broad centroid selector from silently entering model training.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/population_capacity/physical_validation/interannual_harvest_evidence_wave26.json"
CROSSWALK = ROOT / "research/population_capacity/crosswalks/eastern_china_harvest_validation_wave26.json"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_harvest_evidence_does_not_promote_ordinal_sources_to_absolute_targets() -> None:
    evidence = _load(EVIDENCE)

    assert evidence["decision_summary"]["new_open_in_period_absolute_source"] is False
    assert evidence["acceptance"]["no_ordinal_to_absolute_conversion"] is True
    assert evidence["acceptance"]["no_statistical_or_regional_yield_imputation"] is True

    hao = next(item for item in evidence["sources"] if item["source_id"] == "hao_eastern_china_harvest_grades_801_1910")
    assert hao["historical_semantics"]["absolute_yield_kg_per_ha"] is False
    assert hao["training_eligible"] is False
    assert hao["validation_eligible"] is True
    assert hao["source_request_blocker"] is True

    cruz = next(item for item in evidence["sources"] if item["source_id"] == "cruz_intersalar_quinoa_rainfed_1200_1450")
    assert cruz["historical_semantics"]["absolute_yield_kg_per_ha_range"] == [1000, 1500]
    assert cruz["historical_semantics"]["rotation"] == "two-year rain-fed crop/fallow rotation; effective annualized cropped fraction is approximately one half"
    assert cruz["training_eligible"] is False
    assert cruz["validation_eligible"] is True


def test_broad_harvest_centroid_selectors_are_validation_only() -> None:
    crosswalk = _load(CROSSWALK)

    assert crosswalk["mapping_contract"]["exact_historical_boundary"] is False
    assert crosswalk["mapping_contract"]["aggregate_training_target_created"] is False
    assert crosswalk["audit"]["crosswalk_acceptance_for_training"] is False

    selectors = {item["selector_id"]: item for item in crosswalk["selectors"]}
    assert selectors["hao_north_china_plain_approx"]["selected_location_count"] == 504
    assert selectors["hao_jianghuai_approx"]["selected_location_count"] == 180
    assert selectors["hao_jiangnan_approx"]["selected_location_count"] == 392
    assert selectors["tang_shenyang_named_location"]["selected_location_tags"] == ["shenyang"]
    assert selectors["tang_shenyang_named_location"]["coverage_status"] == "named_location_validation_only"
    assert selectors["cruz_intersalar_quinoa_approx"]["selected_location_count"] == 13
    assert selectors["cruz_intersalar_quinoa_approx"]["coverage_status"] == "approximate_physical_validation_only"
