"""Regression checks for the shared nutrient/fallow sensitivity diagnostic."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "research/population_capacity/diagnostics/rapa_nui_shared_nutrient_sensitivity_wave31.json"


def _load() -> dict:
    return json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))


def test_shared_nutrient_sensitivity_reduces_rapa_without_breaking_formal_controls() -> None:
    diagnostic = _load()
    benchmark = diagnostic["shared_combined_benchmark"]
    scenarios = diagnostic["scenario_summaries"]

    assert scenarios["rapa_nui"]["baseline"]["capacity_people_p50"] == 34236
    assert scenarios["rapa_nui"]["shared_combined"]["capacity_people_p50"] == 15407
    assert benchmark["rapa_nui"]["inside_interval"] is True
    assert benchmark["england"]["inside_interval"] is True
    assert benchmark["iceland"]["inside_interval"] is True
    assert scenarios["iceland"]["baseline"]["capacity_people_p50"] == scenarios["iceland"]["shared_combined"]["capacity_people_p50"]


def test_sensitivity_is_crop_only_and_monotone_for_the_proposed_shared_rule() -> None:
    diagnostic = _load()
    scenarios = diagnostic["scenario_summaries"]

    for benchmark in ("rapa_nui", "england", "iceland"):
        baseline = scenarios[benchmark]["baseline"]["capacity_people_p50"]
        combined = scenarios[benchmark]["shared_combined"]["capacity_people_p50"]
        strict = scenarios[benchmark]["shared_combined_strict"]["capacity_people_p50"]
        assert strict <= combined <= baseline

    assert diagnostic["feature_proposal"]["status"] == "diagnostic_proposal_only"
    assert "no starting-population or HYDE predictor" in diagnostic["feature_proposal"]["non_goals"]
    assert "no Rapa Nui-specific multiplier" in diagnostic["feature_proposal"]["non_goals"]


def test_feature_proposal_requires_dynamic_nutrient_and_fallow_validation() -> None:
    diagnostic = _load()
    proposal = diagnostic["feature_proposal"]

    assert "Dynamic N/P/K stock balance" in proposal["production_implementation"]
    assert any("fallow" in test for test in diagnostic["next_tests"])
    assert "not ready" in diagnostic["interpretation"]["production_readiness"].lower()


def test_sensitivity_maps_only_physical_soil_and_climate_fields() -> None:
    diagnostic = _load()
    mapped = {row["field"]: row for row in diagnostic["mapped_physical_features"]}

    assert mapped["soil_quality"]["coverage_fraction"] == 1.0
    assert mapped["chelsa_annual_precipitation"]["coverage_fraction"] == 1.0
    assert mapped["chelsa_precipitation_seasonality"]["coverage_fraction"] > 0.99
    assert all("physical" in row["role"] or "climate" in row["resolution"] for row in mapped.values())
