from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REGISTRY = (
    REPO
    / "research"
    / "population_capacity"
    / "physical_evidence"
    / "terrestrial_food_training_registry.json"
)


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_terrestrial_training_registry_forbids_proxy_and_geography_leakage() -> None:
    policy = _registry()["policy"]
    assert policy["potential_grazer_biomass_is_observed_domestic_herd"] is False
    assert policy["ethnographic_population_is_training_target"] is False
    assert policy["structural_model_envelope_is_probability_interval"] is False
    assert policy["raw_region_names_are_predictors"] is False
    assert policy["unmodeled_feed_or_crop_residue_is_credited"] is False


def test_terrestrial_training_registry_resolves_three_exhaustive_domains() -> None:
    registry = _registry()
    domains = registry["technology_domains"]
    assert [row["domain_id"] for row in domains] == [
        "old_world_grazing_domesticates",
        "andean_grazing_camelids",
        "no_compatible_grazing_domesticate_by_1337",
    ]
    assert domains[-1]["selector"] == "all remaining EU5 locations"
    assert domains[-1]["conversion"] == "structural zero"
    assert "no credit" in domains[-1]["notes"]
    for domain in domains:
        assert domain["sources"]
        assert all(source["url"].startswith("https://") for source in domain["sources"])


def test_joint_probability_is_deferred_to_admissible_anchor_calibration() -> None:
    registry = _registry()
    gate = registry["training_gate"]
    assert gate["pretraining_probability_interval_required"] is False
    assert gate["final_interval_coverage_required_before_acceptance"] is True
    assert "aggregate anchor" in gate["reason_probability_interval_is_deferred"]
    semantics = registry["model_semantics"]
    assert "ordered" in semantics["uncertainty_before_training"]
    assert "held-out" in semantics["uncertainty_after_training"]


def test_unmodeled_external_effects_are_explicit_no_credit_channels() -> None:
    external = _registry()["external_effects"]
    assert set(external) == {
        "tsetse",
        "draft_power",
        "manure",
        "crop_residues",
        "pigs_and_poultry",
    }
    assert "no penalty" in external["tsetse"]
    assert "no yield credit" in external["draft_power"]
    assert "no yield credit" in external["manure"]
    assert "excluded" in external["crop_residues"]
    assert "zero applied calorie credit" in external["pigs_and_poultry"]


def test_global_herd_search_rejects_modern_and_population_backcast_labels() -> None:
    search = {
        row["source_id"]: row
        for row in _registry()["herd_composition_evidence_search"]
    }
    assert search["zooarchnet"]["disposition"] == "case-level validation only"
    assert search["dplace_ethnographic_atlas"]["disposition"] == "out-of-period validation only"
    assert search["glw3_2010"]["disposition"] == "rejected as historical label"
    assert search["hyde_or_population_backcast_livestock"]["disposition"] == "denylisted"
    assert "2010" in search["glw3_2010"]["reason"]
    assert "population" in search["hyde_or_population_backcast_livestock"]["reason"]
