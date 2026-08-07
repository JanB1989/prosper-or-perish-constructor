"""Contracts for Wave31 banana/cassava/taro water-response closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research/population_capacity/physical_validation/crop_water_gap_wave31.json"
CONFIG = ROOT / "population_capacity.toml"
WAVE31 = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave31"


def test_registry_distinguishes_static_water_response_from_annual_risk() -> None:
    record = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert record["target_year"] == 1337
    assert record["gaez_static_source"]["location_rows"] == 20_929 * 6
    assert record["gaez_static_source"]["rainfed_management_code"] == "LRLM"
    assert record["gaez_static_source"]["irrigated_management_code"] == "LILM"
    assert record["gaez_static_source"]["unit"] == "kg dry matter/ha"
    assert record["cassava_interannual_source"]["location_rows"] == 20_929 * 4
    assert record["acceptance"]["banana_static_water_response_closed"] is True
    assert record["acceptance"]["taro_static_water_response_closed"] is True
    assert record["acceptance"]["cassava_modern_interannual_risk_bridge_closed"] is True
    assert record["acceptance"]["banana_modern_interannual_risk_bridge_closed"] is False
    assert record["acceptance"]["taro_modern_interannual_risk_bridge_closed"] is False
    assert record["acceptance"]["training_unblocked"] is False


def test_config_points_to_wave31_registry() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert 'crop_water_gap_registry = "research/population_capacity/physical_validation/crop_water_gap_wave31.json"' in text


def test_gaez_static_matrix_is_complete_and_paired_without_imputation() -> None:
    path = WAVE31 / "gaez_tropical_static_water_response_location_wave31.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    assert rows.height == 20_929 * 6
    assert rows.select(["location_tag", "crop", "water_mode"]).unique().height == rows.height
    assert sorted(rows.group_by(["crop", "water_mode"]).len()["len"].to_list()) == [20_929] * 6
    assert set(rows["water_mode"].unique().to_list()) == {"rainfed", "irrigated"}
    assert set(rows["label_state"].unique().to_list()).issubset(
        {"resolved_gaez_static_water_response", "observed_structural_zero"}
    )
    assert rows.filter(pl.col("label_state") == "resolved_gaez_static_water_response").height > 0
    assert rows.filter(pl.col("label_state") == "observed_structural_zero").height > 0
    assert set(rows["annual_risk_available"].unique().to_list()) == {False}
    assert set(rows["training_target_allowed"].unique().to_list()) == {False}
    assert set(rows["population_target"].unique().to_list()) == {False}
    finite = rows.filter(pl.col("yield_p10_kg_dm_ha").is_finite())
    assert finite.filter(pl.col("yield_p10_kg_dm_ha") > pl.col("yield_p50_kg_dm_ha")).height == 0
    assert finite.filter(pl.col("yield_p50_kg_dm_ha") > pl.col("yield_p90_kg_dm_ha")).height == 0


def test_cassava_interannual_matrix_has_explicit_model_water_modes() -> None:
    path = WAVE31 / "isimip_cassava_location_risk_wave31.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    assert rows.height == 20_929 * 4
    assert rows.select(["location_tag", "model_id", "water_mode"]).unique().height == rows.height
    assert rows["year_start"].unique().to_list() == [1971]
    assert rows["year_end"].unique().to_list() == [2010]
    assert set(rows["water_mode"].unique().to_list()) == {"rainfed", "full_irrigation"}
    assert set(rows["training_target_allowed"].unique().to_list()) == {False}
    assert set(rows["population_target"].unique().to_list()) == {False}
    assert rows.filter(pl.col("yield_p10_t_ha").is_finite() & (pl.col("yield_p10_t_ha") > pl.col("yield_p50_t_ha"))).height == 0
    assert rows.filter(pl.col("yield_p50_t_ha").is_finite() & (pl.col("yield_p50_t_ha") > pl.col("yield_p90_t_ha"))).height == 0


def test_banana_taro_availability_audit_has_no_silent_model_fallback() -> None:
    path = WAVE31 / "isimip_banana_taro_availability_audit_wave31.json"
    if not path.exists():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) == 16
    assert {row["crop"] for row in rows} == {"banana", "taro"}
    assert {row["water_mode"] for row in rows} == {"rainfed", "full_irrigation"}
    assert all(row["http_status"] == 404 for row in rows)


def test_wave31_artifact_hashes_are_reproducible() -> None:
    manifest_path = WAVE31 / "crop_water_gap_manifest_wave31.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == registry["artifacts"]["manifest_sha256"]
    for key in (
        "gaez_static_location",
        "gaez_static_pair",
        "cassava_location_risk",
        "cassava_superregion_risk",
        "cassava_model_spread",
    ):
        path = ROOT / manifest["outputs"][key]
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["outputs"][f"{key}_sha256"]
    availability = ROOT / manifest["banana_taro_isimip_availability"]["audit"]
    assert hashlib.sha256(availability.read_bytes()).hexdigest() == manifest["banana_taro_isimip_availability"]["audit_sha256"]
