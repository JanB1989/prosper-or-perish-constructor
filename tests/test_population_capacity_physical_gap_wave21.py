from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHYSICAL = ROOT / "research" / "population_capacity" / "physical_evidence"


def _load(name: str) -> dict:
    return json.loads((PHYSICAL / name).read_text(encoding="utf-8"))


def test_angkor_dated_flood_recession_evidence_is_physical_not_a_multiplier() -> None:
    record = _load("asia_greater_angkor_hydraulic_calendar_wave21.json")
    assert record["policy"]["anchor_specific_multiplier"] is False
    assert record["mapped_boundary"]["coverage_fraction"] == 1.0
    features = {item["feature_id"]: item for item in record["feature_records"]}
    recession = features["lower_mekong_flood_recession_rice"]
    assert recession["quantitative_value"]["requires_embankment_or_pond_storage"] is True
    assert recession["quantitative_value"]["requires_canals_or_pumps"] is True
    cycles = features["angkor_crop_cycle_historical_report"]["quantitative_value"]
    assert cycles["reported_crop_cycles_per_year_low"] == 3.0
    assert cycles["reported_crop_cycles_per_year_high"] == 4.0
    analogue = features["angkor_borei_flood_recession_productivity_analogue"]
    assert analogue["role"] == "validation_only"
    assert analogue["quantitative_value"]["support_per_worker"] == 0.5
    assert "flood_recession_land_is_not_double_counted_as_irrigated_or_rainfed_crop_land" in record[
        "implementation_contract"
    ]["required_invariants"]


def test_iceland_fisheries_evidence_separates_access_from_annual_yield() -> None:
    record = _load("europe_iceland_fisheries_local_food_wave21.json")
    assert record["mapped_boundary"]["eu5_location_count"] == 21
    assert record["mapped_boundary"]["coastal_location_count"] == 18
    diag = record["current_eu5_diagnostic"]
    assert diag["marine_label_state_counts"] == {
        "observed_positive": 18,
        "not_historically_available": 3,
    }
    marine = diag["marine_capacity_people"]
    assert marine["p10"] <= marine["p50"] <= marine["p90"]
    combined = diag["combined_fisheries_capacity_people"]
    assert combined["p10"] <= combined["p50"] <= combined["p90"]
    assert diag["mechanistic_components_people_p50"]["marine_capacity"] == marine["p50"]
    assert diag["mechanistic_components_people_p50"]["total_mechanistic"] == 26059
    assert "modern_catch_as_historical_label" not in record["policy"] or record["policy"][
        "modern_catch_as_historical_label"
    ] is False
    assert any(
        item["evidence_id"] == "iceland_high_medieval_cod_production_sites"
        for item in record["evidence_records"]
    )


def test_upper_mantaro_keeps_structural_zeros_and_exposes_broad_crosswalk() -> None:
    record = _load("america_upper_mantaro_crop_crosswalk_wave21.json")
    boundary = record["historical_boundary"]
    assert boundary["mapping_status"] == "high_containment_but_not_exact_boundary"
    assert boundary["published_area_share_of_selector"] < 0.2
    assert boundary["mapping_status"] != "exact"
    rows = {item["location_tag"]: item for item in record["eu5_location_diagnostic"]["rows"]}
    assert rows["tunanmarca"]["historical_feature_alignment"] == "direct_named_settlement"
    assert rows["tunanmarca"]["potato_yield_p50_kg_dm_ha"] > 0
    assert rows["ingapirca"]["potato_yield_p50_kg_dm_ha"] == 0.0
    assert rows["llampqui"]["potato_yield_p50_kg_dm_ha"] == 0.0
    assert rows["ingapirca"]["crop_label_interpretation"].startswith("valid source structural zero")
    assert rows["llampqui"]["crop_label_interpretation"].startswith("valid source structural zero")
    irrigation = next(
        item
        for item in record["feature_records"]
        if item["feature_id"] == "wanka_ii_irrigation_and_drainage"
    )
    assert irrigation["quantitative_value"]["ditch_length_km_low"] == 24.0
    assert irrigation["quantitative_value"]["irrigated_area_ha_low"] == 100.0
    assert irrigation["quantitative_value"]["irrigated_area_ha_high"] == 200.0
    assert record["crosswalk_closure_contract"]["current_status"] == "not_met"
    assert record["crosswalk_closure_contract"]["no_anchor_specific_multiplier"] is True
