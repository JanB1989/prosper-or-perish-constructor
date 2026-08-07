"""Cross-system checks for the Wave32 nutrient/fallow physical diagnostic."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "research/population_capacity/diagnostics/shared_soil_fallow_cross_system_audit_wave32.json"


def _load() -> dict:
    return json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))


def test_controls_and_independent_systems_are_present() -> None:
    diagnostic = _load()
    results = diagnostic["scenario_results"]

    for system in ("rapa_nui", "england", "iceland", "peten", "zarma_sahel", "hawaii"):
        assert results[system]["baseline"]["location_count"] > 0

    # The shared physical rule resolves the held-out Rapa Nui contradiction,
    # remains inside England/Iceland controls, and is directionally consistent
    # with the independently estimated Petén interval.  Petén is not promoted.
    for system in ("rapa_nui", "england", "iceland", "peten"):
        assert diagnostic["interval_results"][system]["inside_interval"] is True
    assert diagnostic["interval_results"]["peten"]["training_eligible"] is False


def test_crop_only_rule_is_monotone_without_scaling_other_food_systems() -> None:
    diagnostic = _load()
    results = diagnostic["scenario_results"]

    for system, scenarios in results.items():
        baseline = scenarios["baseline"]["capacity_people_p50"]
        moderate = scenarios["shared_nutrient_fallow"]["capacity_people_p50"]
        strict = scenarios["shared_nutrient_fallow_strict"]["capacity_people_p50"]
        assert strict <= moderate <= baseline
        if scenarios["baseline"]["weighted_crop_retention_p50"]:
            assert scenarios["baseline"]["weighted_crop_retention_p50"] == 1.0
            assert 0.0 < scenarios["shared_nutrient_fallow"]["weighted_crop_retention_p50"] <= 1.0

    # Iceland has no crop contribution in the current frame; a crop-only
    # nutrient/fallow rule must leave it unchanged.
    assert results["iceland"]["baseline"]["capacity_people_p50"] == results["iceland"]["shared_nutrient_fallow"]["capacity_people_p50"]


def test_source_backed_process_numbers_are_recorded_and_not_targets() -> None:
    diagnostic = _load()
    sources = {row["source_family"]: row for row in diagnostic["source_evidence"]}

    assert "peten_milpa_fallow" in sources
    assert "sahel_nutrient_fallow" in sources
    assert "hawaii_prehistoric_nutrient_depletion" in sources
    assert "125/300" in diagnostic["scenario_definition"]["dryland_ratio"]
    assert diagnostic["systems"]["zarma_sahel"]["role"] == "physical_process_validation_only"
    assert diagnostic["systems"]["hawaii"]["role"] == "physical_process_validation_only"
    assert diagnostic["systems"]["peten"]["role"] == "validation_only_boundary_review"
    assert diagnostic["interpretation"]["status"] == "diagnostic_only_not_production_ready"


def test_mapping_and_non_goals_are_explicit() -> None:
    diagnostic = _load()
    mapped = {row["field"]: row for row in diagnostic["mapped_physical_features"]}

    for field in ("soil_quality", "chelsa_annual_precipitation", "allocated_crop_fraction", "allocated_fallow_fraction", "area_km2"):
        assert mapped[field]["coverage_fraction"] == 1.0
        assert mapped[field]["forbidden_training_fields"] is False

    assert diagnostic["peten_mapping"]["coverage_status"].startswith("boundary_not_exact")
    hard_non_goals = diagnostic["scenario_definition"]["hard_non_goals"]
    assert "no anchor-specific multiplier" in hard_non_goals
    assert "no starting-population/HYDE/RGO/trade predictor" in hard_non_goals
    assert "no observed historical cropland share" in hard_non_goals


def test_global_production_blockers_are_not_hidden() -> None:
    diagnostic = _load()
    blockers = diagnostic["interpretation"]["production_blockers"]

    assert any("nutrient stock" in blocker for blocker in blockers)
    assert any("rock-garden" in blocker or "fallow" in blocker for blocker in blockers)
    assert any("crop-family" in blocker for blocker in blockers)
    assert any("out-of-period" in blocker for blocker in blockers)
