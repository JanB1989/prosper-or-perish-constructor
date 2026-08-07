"""Semantic and coverage contracts for the wave-27 global skill layers."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "research/population_capacity/physical_validation/global_interannual_skill_wave27.json"
ACTIVE_REGISTRY = ROOT / "research/population_capacity/physical_validation/interannual_yield_skill_registry_wave27.json"
CONFIG = ROOT / "population_capacity.toml"


def test_global_skill_sources_cannot_become_1337_capacity_targets() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))

    assert record["decision"]["in_period_global_machine_readable_annual_absolute_yield_source"] is False
    assert record["decision"]["modern_source_as_1337_target"] is False
    assert record["decision"]["training_population_targets_added"] == 0
    assert record["global_closure"]["modern_relative_skill_layer_closed"] is True
    assert record["global_closure"]["1337_compatible_historical_annual_observation_coverage"] is False

    for source in record["sources"]:
        assert source["training_target_allowed"] is False
        assert source["validation_allowed"] is True


def test_gdhy_mapping_is_full_location_but_explicitly_missing_aware() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    gdhy = next(item for item in record["sources"] if item["source_id"].startswith("gdhy_"))
    mapping = gdhy["mapping"]

    assert mapping["location_rows"] == 20929
    assert mapping["superregion_report_rows"] == 864  # 4 crops x 36 years x 6 map groups
    assert mapping["positive_coverage_rows"] + mapping["zero_coverage_rows"] == 864
    assert "never filled" in mapping["coverage_warning"]


def test_isimip_pairs_rainfed_and_full_irrigation_without_averaging_engines() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    isimip = next(item for item in record["sources"] if item["source_id"].startswith("isimip2a_"))
    mapping = isimip["mapping"]
    contrast = isimip["skill_and_uncertainty_conversion"]

    assert set(isimip["coverage"]["water_modes"]) == {"rainfed", "full_irrigation"}
    assert mapping["paired_contrast_rows"] == 165  # 33 years x 5 land super-regions
    assert "same grid cell and year" in contrast["water_mode_contrast"]
    assert "not averaged with GDHY" in contrast["model_disagreement_policy"]


def test_wave27_active_registry_is_structurally_resolved_but_acceptance_blocked() -> None:
    registry = json.loads(ACTIVE_REGISTRY.read_text(encoding="utf-8"))
    config = CONFIG.read_text(encoding="utf-8")

    assert registry["schema_version"] == "population-capacity-physical-validation-v1"
    assert registry["status"] == "blocked"
    assert registry["acceptance"]["spatial_skill_layers_acquired"] is True
    assert registry["acceptance"]["annual_risk_gate_unblocked"] is False
    assert registry["acceptance"]["absolute_1337_yield_parameter_calibration_closed"] is False
    assert "interannual_yield_skill_registry_wave27.json" in config

    assert {source["source_id"] for source in registry["sources"]} == {
        "gdhy_v1_2_v1_3_global_1981_2016",
        "isimip2a_clm_crop_watch_wfdei_rice_1980_2012",
    }
    for source in registry["sources"]:
        assert source["acquisition"]["metadata_verified"] is True
        assert source["acquisition"]["raw_data_downloaded_into_constructor"] is True
        assert source["model_role"].endswith("validation") or "validation" in source["model_role"]
        assert source.get("disallowed_uses")
