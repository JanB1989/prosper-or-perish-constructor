"""Contracts for the ISIMIP2a multi-crop interannual-risk bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research/population_capacity/physical_validation/isimip_multicrop_bridge_wave30.json"
CONFIG = ROOT / "population_capacity.toml"
WAVE30 = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave30"


def test_registry_declares_a_modern_validation_bridge_not_a_1337_target() -> None:
    record = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert record["target_year"] == 1337
    assert record["source_window"] == [1971, 2010]
    assert record["coverage"]["location_count"] == 20_929
    assert record["coverage"]["location_model_crop_mode_rows"] == 20_929 * 16
    assert record["semantics"]["absolute_1337_yield"] is False
    assert record["semantics"]["historical_crop_yield_label"] is False
    assert record["semantics"]["population_target"] is False
    assert record["acceptance"]["crop_specific_interannual_risk_bridge_available"] is True
    assert record["acceptance"]["training_unblocked"] is False
    assert len(record["acceptance"]["blocking_gaps"]) >= 3


def test_population_capacity_config_points_to_bridge_registry() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert 'crop_yield_risk_bridge_registry = "research/population_capacity/physical_validation/isimip_multicrop_bridge_wave30.json"' in text


def test_location_matrix_is_complete_and_preserves_explicit_source_states() -> None:
    path = WAVE30 / "isimip_multicrop_location_risk_wave30.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    assert rows.height == 20_929 * 16
    assert rows.select(["location_tag", "model_id", "crop", "water_mode"]).unique().height == rows.height
    assert sorted(rows.group_by("source_id").len()["len"].to_list()) == [20_929] * 16
    assert rows["year_start"].unique().to_list() == [1971]
    assert rows["year_end"].unique().to_list() == [2010]
    assert set(rows["training_target_allowed"].unique().to_list()) == {False}
    assert set(rows["population_target"].unique().to_list()) == {False}
    states = set(rows["label_state"].unique().to_list())
    assert "resolved_modern_model_yield_risk" in states
    assert "insufficient_valid_years" in states
    assert "outside_source_domain" in states


def test_quantiles_and_risk_ratios_are_physical_for_finite_rows() -> None:
    path = WAVE30 / "isimip_multicrop_location_risk_wave30.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    finite = rows.filter(pl.col("yield_p10_t_ha").is_finite())
    assert finite.filter(pl.col("yield_p10_t_ha") > pl.col("yield_p50_t_ha")).height == 0
    assert finite.filter(pl.col("yield_p50_t_ha") > pl.col("yield_p90_t_ha")).height == 0
    assert rows.filter(
        pl.col("zero_yield_year_fraction").is_finite()
        & ((pl.col("zero_yield_year_fraction") < 0) | (pl.col("zero_yield_year_fraction") > 1))
    ).height == 0
    assert rows.filter(
        pl.col("lower_tail_ratio_p10_p50").is_finite()
        & ((pl.col("lower_tail_ratio_p10_p50") < 0) | (pl.col("lower_tail_ratio_p10_p50") > 1))
    ).height == 0


def test_paired_model_spread_is_explicit_and_not_imputed() -> None:
    path = WAVE30 / "isimip_multicrop_model_spread_wave30.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    assert rows.height == 20_929 * 8
    assert rows.select(["location_tag", "crop", "water_mode"]).unique().height == rows.height
    assert rows.filter(pl.col("model_p50_ratio_lpj_guess_to_lpjml").is_finite()).height > 10_000
    assert rows.filter(pl.col("model_p50_absolute_difference_t_ha").is_finite()).height > 10_000
    assert set(rows["training_target_allowed"].unique().to_list()) == {False}
    assert set(rows["population_target"].unique().to_list()) == {False}


def test_manifest_and_source_hashes_are_reproducible_when_artifacts_exist() -> None:
    manifest_path = WAVE30 / "isimip_multicrop_bridge_manifest_wave30.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert manifest["coverage"]["location_count"] == 20_929
    assert manifest["coverage"]["location_matrix_rows"] == 20_929 * 16
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == registry["artifacts"]["manifest_sha256"]
    for key in ("location_risk", "superregion_risk", "model_spread"):
        artifact = ROOT / manifest["outputs"][key]
        assert artifact.exists()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == manifest["outputs"][f"{key}_sha256"]
    for source in manifest["sources"]:
        assert source["download_url"].startswith("https://files.isimip.org/")
        source_path = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave30" / source["file_name"]
        assert source_path.exists()
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"]

