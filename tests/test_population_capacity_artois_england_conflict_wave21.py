from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = (
    ROOT
    / "research"
    / "population_capacity"
    / "model_reviews"
    / "artois_england_conflict_wave21.json"
)


def test_artois_conflict_review_is_append_only_and_keeps_anchor() -> None:
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))

    assert review["schema_version"] == "population_capacity_anchor_conflict_review_v1"
    assert review["append_only"] is True
    assert review["active_model_mutation"] is False
    assert review["decision"]["retain_as_two_sided_interval_anchor"] is True
    assert review["decision"]["downgrade_to_validation_only"] is False
    assert review["decision"]["use_as_global_scale_anchor"] is False

    artois = review["model_snapshot"]["artois"]
    assert artois["mechanistic_unscaled_density_people_per_km2"] >= 169.5
    assert artois["mechanistic_unscaled_density_people_per_km2"] <= 254.2
    assert artois["soil_quality_counts"] == {"soil_good": 8}
    assert artois["scale_interval_to_cover_published_capacity"][0] > 0.8

    england = review["model_snapshot"]["england"]
    assert england["soil_quality_counts"]["soil_poor"] > 0
    assert england["soil_quality_counts"]["soil_average"] > 0
    assert england["scale_interval_to_cover_demographic_anchor"][1] < 0.35


def test_artois_conflict_review_cites_independent_historical_evidence() -> None:
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    evidence = review["historical_evidence"]
    assert len(evidence) >= 4
    urls = {item["url"] for item in evidence}
    assert "https://books.openedition.org/septentrion/122270?lang=en" in urls
    assert "https://books.openedition.org/septentrion/168200" in urls
    assert any("pure.aber.ac.uk" in url for url in urls)
    assert all(item["model_implication"] for item in evidence)


def test_artois_food_dependence_is_sensitivity_not_imported_food_correction() -> None:
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    dependence = review["food_dependence_assessment"]

    assert dependence["long_distance_imported_calories_required"] == (
        "not demonstrated by the cited sources"
    )
    low, high = dependence["recommended_local_food_interval_for_sensitivity"]
    assert 0.0 < low < high <= 1.0
    assert "Artois-specific multiplier" in review["decision"]["required_model_change"]
