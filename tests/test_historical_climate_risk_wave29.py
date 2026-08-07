"""Regression tests for the public NOAA drought-atlas risk mapping wave."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research/population_capacity/physical_validation/historical_climate_risk_wave29.json"
CONFIG = ROOT / "population_capacity.toml"
WAVE29 = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave29"


def test_registry_is_climate_proxy_only_and_training_blocked() -> None:
    record = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert record["target_year"] == 1337
    assert record["requested_window"] == [1100, 1500]
    assert len(record["sources"]) == 4
    assert record["semantics"]["historical_1337_absolute_yield"] is False
    assert record["semantics"]["population_target"] is False
    assert record["acceptance"]["training_unblocked"] is False
    assert len(record["acceptance"]["blocking_gaps"]) >= 3
    for source in record["sources"]:
        assert source["training_target_allowed"] is False
        assert source["population_target"] is False
        assert source["mapping"]["location_count"] == 20_929
        assert source["download_url"].startswith("https://www.ncei.noaa.gov/")


def test_population_capacity_config_points_to_wave29_registry() -> None:
    assert 'historical_climate_risk_registry = "research/population_capacity/physical_validation/historical_climate_risk_wave29.json"' in CONFIG.read_text(encoding="utf-8")


def test_drought_atlas_rows_cover_every_location_without_imputation() -> None:
    path = WAVE29 / "drought_atlas_location_risk_wave29.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    assert rows.height == 20_929 * 4
    assert rows.select(["location_tag", "source_id"]).unique().height == rows.height
    assert sorted(rows.group_by("source_id").len()["len"].to_list()) == [20_929] * 4
    assert set(rows["training_target_allowed"].unique().to_list()) == {False}
    assert set(rows["population_target"].unique().to_list()) == {False}
    states = set(rows["label_state"].unique().to_list())
    assert "resolved_historical_climate_risk" in states
    assert "outside_source_domain" in states
    # A source-domain gap is represented by a state and NaN risk statistics,
    # never by a nearest-source, regional, or global fill.
    outside = rows.filter(pl.col("label_state") == "outside_source_domain")
    assert outside.select(pl.col("valid_year_count").max()).item() == 0
    assert outside.select(pl.col("p50_pdsi").is_nan().all()).item()


def test_drought_quantiles_are_ordered_and_source_periods_are_explicit() -> None:
    path = WAVE29 / "drought_atlas_location_risk_wave29.csv"
    if not path.exists():
        return
    rows = pl.read_csv(path)
    finite = rows.filter(pl.col("p10_pdsi").is_finite())
    assert finite.filter(pl.col("p10_pdsi") > pl.col("p50_pdsi")).height == 0
    assert finite.filter(pl.col("p50_pdsi") > pl.col("p90_pdsi")).height == 0
    assert rows.filter(pl.col("source_id") == "noaa_sada")["year_start"].unique().to_list() == [1400]
    assert rows.filter(pl.col("source_id") == "noaa_sada")["year_end"].unique().to_list() == [1500]
    assert rows.filter(pl.col("source_id") == "noaa_mada")["year_start"].unique().to_list() == [1300]
    assert rows.filter(pl.col("source_id") == "noaa_mada")["year_end"].unique().to_list() == [1500]


def test_drought_atlas_manifest_hashes_reproduce_when_artifacts_exist() -> None:
    manifest_path = WAVE29 / "drought_atlas_risk_manifest_wave29.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["coverage"]["location_count"] == 20_929
    assert manifest["semantics"]["absolute_1337_yield"] is False
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == registry["artifacts"]["manifest_sha256"]
    for key in ("location_risk", "superregion_risk"):
        path = ROOT / manifest["outputs"][key]
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["outputs"][f"{key}_sha256"]
    for source in manifest["sources"]:
        source_path = ROOT / source["path"]
        assert source_path.exists()
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"]
