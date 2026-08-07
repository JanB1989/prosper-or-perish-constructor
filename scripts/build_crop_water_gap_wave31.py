"""Close the banana/cassava/taro crop-water evidence gap where possible.

Cassava has crop-specific rain-fed/full-irrigation simulations in the official
ISIMIP2a repository, so it receives the same modern interannual-risk bridge as
the other staple crops.  Banana and taro are not present as ISIMIP2a crop
outputs; for those families we retain the paired, same-geography GAEZ v5
LRLM/LILM low-input attainable-yield rasters already sampled for every EU5
location.  That closes the static water-mode response, but not an annual
historical-risk tail.  No rain-fed values are copied into irrigated fields.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import polars as pl


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave31"
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"
SAMPLE_ROOT = ROOT / "artifacts/data/population_capacity/crop_mode_samples/gaez_v5"
SOURCE_MANIFEST = ROOT / "artifacts/data/population_capacity/sources/source_manifest.json"
PYAEZ_BRIDGE = ROOT / "artifacts/data/population_capacity/pyaez_1337/exact_engine_wave30/crop_risk_bridge_coverage.parquet"


def _load_wave30_module() -> Any:
    path = ROOT / "scripts/build_isimip_multicrop_bridge_wave30.py"
    spec = importlib.util.spec_from_file_location("wave30_isimip", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WAVE30 = _load_wave30_module()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return float("nan")
    values = values[valid]
    weights = weights[valid]
    order = np.argsort(values, kind="mergesort")
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights) / weights.sum()
    return float(values[np.searchsorted(cumulative, q, side="left")])


def _static_rows(crop: str, mode: str, locations: pl.DataFrame) -> list[dict[str, Any]]:
    path = SAMPLE_ROOT / f"{crop}_{mode}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    data = pl.read_parquet(path)
    expected_mode = "rainfed" if mode == "rainfed" else "irrigated"
    if set(data["water_mode"].unique().to_list()) != {expected_mode}:
        raise ValueError(f"{path}: water_mode semantics are {data['water_mode'].unique().to_list()}, expected {expected_mode}")
    if data.filter(pl.col("sample_semantic_mismatch")).height:
        raise ValueError(f"{path}: sample semantic mismatch rows present")
    rows: list[dict[str, Any]] = []
    location_keys = locations["location_tag"].to_list()
    grouped = data.partition_by("location_tag", as_dict=True)
    for location_tag in location_keys:
        # Polars represents one-column partition keys as one-tuples in the
        # dictionary form; support both forms for deterministic compatibility.
        sample = grouped.get(location_tag)
        if sample is None:
            sample = grouped.get((location_tag,))
        if sample is None or sample.height == 0:
            rows.append(
                {
                    "location_tag": location_tag,
                    "crop": crop,
                    "water_mode": mode,
                    "sample_count": 0,
                    "valid_sample_count": 0,
                    "valid_sample_fraction": 0.0,
                    "suitable_fraction_area_weighted": float("nan"),
                    "yield_mean_kg_dm_ha": float("nan"),
                    "yield_p10_kg_dm_ha": float("nan"),
                    "yield_p50_kg_dm_ha": float("nan"),
                    "yield_p90_kg_dm_ha": float("nan"),
                    "irrigation_requirement_mm_p50": float("nan"),
                    "crop_variant_set": "[]",
                    "label_state": "missing_sample_footprint",
                    "reason_code": "missing_sample_footprint",
                    "annual_risk_available": False,
                    "training_target_allowed": False,
                    "population_target": False,
                }
            )
            continue
        values = sample["yield_kg_dm_ha"].to_numpy().astype(float)
        weights = sample["sample_weight"].to_numpy().astype(float)
        suitable = sample["suitable_fraction"].to_numpy().astype(float)
        water = sample["gaez_res05_net_irrigation_requirement_mm"].to_numpy().astype(float)
        valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
        valid_weights = weights[valid]
        valid_values = values[valid]
        weight_total = float(valid_weights.sum())
        source_hashes = sample["source_hash"].unique().to_list()
        variants = sorted(str(value) for value in sample["crop_variant"].unique().to_list())
        rows.append(
            {
                "location_tag": location_tag,
                "crop": crop,
                "water_mode": mode,
                "sample_count": sample.height,
                "valid_sample_count": int(valid.sum()),
                "valid_sample_fraction": float(valid.mean()) if valid.size else 0.0,
                "suitable_fraction_area_weighted": float(np.average(suitable[np.isfinite(suitable)], weights=weights[np.isfinite(suitable)])) if np.isfinite(suitable).any() else float("nan"),
                "yield_mean_kg_dm_ha": float(np.average(valid_values, weights=valid_weights)) if valid_values.size else float("nan"),
                "yield_p10_kg_dm_ha": weighted_quantile(values, weights, 0.10),
                "yield_p50_kg_dm_ha": weighted_quantile(values, weights, 0.50),
                "yield_p90_kg_dm_ha": weighted_quantile(values, weights, 0.90),
                "irrigation_requirement_mm_p50": weighted_quantile(water, weights, 0.50),
                "crop_variant_set": json.dumps(variants, separators=(",", ":")),
                "gaez_source_hashes": json.dumps(sorted(str(value) for value in source_hashes), separators=(",", ":")),
                "label_state": (
                    "observed_structural_zero"
                    if valid_values.size and np.all(valid_values == 0)
                    else "resolved_gaez_static_water_response"
                    if valid_values.size
                    else "missing_sample_footprint"
                ),
                "reason_code": "valid_gaez_zero" if valid_values.size and np.all(valid_values == 0) else "paired_gaez_v5_lrlm_lilm_same_geography",
                "annual_risk_available": False,
                "training_target_allowed": False,
                "population_target": False,
            }
        )
    return rows


def _static_pair_rows(rainfed: pl.DataFrame, irrigated: pl.DataFrame) -> pl.DataFrame:
    left = rainfed.rename({column: f"{column}_rainfed" for column in rainfed.columns if column not in {"location_tag", "crop"}})
    right = irrigated.rename({column: f"{column}_irrigated" for column in irrigated.columns if column not in {"location_tag", "crop"}})
    joined = left.join(right, on=["location_tag", "crop"], how="left")
    return joined.with_columns(
        [
            pl.when(pl.col("yield_mean_kg_dm_ha_rainfed").is_finite() & pl.col("yield_mean_kg_dm_ha_irrigated").is_finite())
            .then(pl.col("yield_mean_kg_dm_ha_irrigated") - pl.col("yield_mean_kg_dm_ha_rainfed"))
            .otherwise(None)
            .alias("irrigated_minus_rainfed_kg_dm_ha"),
            pl.when((pl.col("yield_mean_kg_dm_ha_rainfed") > 0) & (pl.col("yield_mean_kg_dm_ha_irrigated") > 0))
            .then(pl.col("yield_mean_kg_dm_ha_irrigated") / pl.col("yield_mean_kg_dm_ha_rainfed"))
            .otherwise(None)
            .alias("irrigated_to_rainfed_ratio"),
            pl.lit("paired_GAEZ_v5_LRLM_LILM_static_not_annual_risk").alias("interpretation"),
            pl.lit(False).alias("annual_risk_available"),
            pl.lit(False).alias("training_target_allowed"),
            pl.lit(False).alias("population_target"),
        ]
    )


def _source_records() -> list[dict[str, Any]]:
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))["sources"]
    records: list[dict[str, Any]] = []
    for crop in ("banana", "cassava", "taro"):
        for mode in ("rainfed", "irrigated"):
            matching = [
                record
                for record in manifest
                if record.get("engine") == "gaez_v5"
                and record.get("crop") == crop
                and record.get("water_mode") == mode
                and record.get("variable") == "RES05-YXX"
                and record.get("unit") == "kg dry matter/ha"
            ]
            if not matching:
                raise RuntimeError(f"no paired GAEZ v5 RES05-YXX source for {crop}/{mode}")
            for record in matching:
                records.append(
                    {
                        "source_id": record["source"],
                        "engine": record["engine"],
                        "crop": crop,
                        "water_mode": mode,
                        "management_code": record["management_code"],
                        "period": record["period"],
                        "climate_source": record["climate_source"],
                        "unit": record["unit"],
                        "nodata_semantics": record["nodata_semantics"],
                        "url": record["url"],
                        "path": record["path"],
                        "sha256": record["sha256"],
                    }
                )
    return records


def _is_available(url: str) -> tuple[int, str]:
    try:
        request = Request(url, method="HEAD")
        with urlopen(request, timeout=20) as response:
            return int(response.status), "available"
    except HTTPError as exc:
        return int(exc.code), "http_error"
    except (URLError, TimeoutError) as exc:
        return 0, f"unreachable:{type(exc).__name__}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    locations = pl.read_parquet(LOCATIONS).select(
        ["location_tag", "super_region", "area_km2", "calibrated_lon", "calibrated_lat"]
    )
    if locations.height != 20_929:
        raise ValueError(f"expected 20,929 EU5 locations, found {locations.height}")

    static_rows: list[dict[str, Any]] = []
    paired_static: list[pl.DataFrame] = []
    static_source_records = _source_records()
    for crop in ("banana", "cassava", "taro"):
        rainfed = pl.DataFrame(_static_rows(crop, "rainfed", locations))
        irrigated = pl.DataFrame(_static_rows(crop, "irrigated", locations))
        static_rows.extend(rainfed.to_dicts())
        static_rows.extend(irrigated.to_dicts())
        paired_static.append(_static_pair_rows(rainfed, irrigated))
    static_df = pl.DataFrame(static_rows)
    static_path = OUT / "gaez_tropical_static_water_response_location_wave31.csv"
    static_df.write_csv(static_path)
    static_pair_df = pl.concat(paired_static, how="diagonal_relaxed")
    static_pair_path = OUT / "gaez_tropical_static_water_response_pair_wave31.csv"
    static_pair_df.write_csv(static_pair_path)

    # Cassava dynamic risk: reuse the audited wave30 ISIMIP reader so its
    # time-axis, nodata, and model semantics cannot diverge between waves.
    lon = locations["calibrated_lon"].to_numpy().astype(float)
    lat = locations["calibrated_lat"].to_numpy().astype(float)
    cassava_sources = []
    cassava_rows: list[dict[str, Any]] = []
    cassava_super_rows: list[dict[str, Any]] = []
    for model_id, model_label, model_dir, prefix in WAVE30.MODELS:
        for water_mode, mode_code in WAVE30.MODES:
            source = WAVE30.Source(model_id, model_label, model_dir, prefix, "cassava", "cas", water_mode, mode_code)
            WAVE30.ensure_source(source)
            years, values, metadata = WAVE30.read_source(source, lon, lat)
            cassava_rows.extend(WAVE30.source_rows(source, locations, values, years, metadata))
            cassava_super_rows.extend(WAVE30.superregion_rows(source, locations, values, years))
            cassava_sources.append(
                {
                    "source_id": f"{model_id}_cassava_{water_mode}",
                    "model": model_label,
                    "crop": "cassava",
                    "water_mode": water_mode,
                    "file_name": source.filename,
                    "download_url": source.download_url,
                    "sha256": sha256(source.path),
                    "years": [int(years.min()), int(years.max())],
                    "unit": "dry matter t ha-1 per growing season",
                    "mapped_location_count": int(metadata["in_domain"].sum()),
                    "training_target_allowed": False,
                    "population_target": False,
                    "absolute_1337_yield": False,
                }
            )
    cassava_df = pl.DataFrame(cassava_rows)
    cassava_path = OUT / "isimip_cassava_location_risk_wave31.csv"
    cassava_df.write_csv(cassava_path)
    cassava_super_path = OUT / "isimip_cassava_superregion_risk_wave31.csv"
    pl.DataFrame(cassava_super_rows).write_csv(cassava_super_path)
    cassava_spread = WAVE30.paired_model_rows(cassava_df)
    cassava_spread_path = OUT / "isimip_cassava_model_spread_wave31.csv"
    cassava_spread.write_csv(cassava_spread_path)

    # Verify the absence of official ISIMIP2a banana/taro files rather than
    # silently treating them as zero or borrowing a different crop.
    availability_checks: list[dict[str, Any]] = []
    for model_id, model_label, model_dir, prefix in WAVE30.MODELS:
        for crop, codes in (("banana", ["ban", "banana"]), ("taro", ["tar", "taro"])):
            for code in codes:
                for water_mode, mode_code in WAVE30.MODES:
                    filename = f"{prefix}_gswp3_nobc_hist_co2_yield-{code}-{mode_code}-default_global_annual_1971_2010.nc4"
                    url = f"https://files.isimip.org/ISIMIP2a/OutputData/agriculture/{model_dir}/gswp3/historical/{filename}"
                    status, state = _is_available(url)
                    availability_checks.append(
                        {
                            "model": model_label,
                            "crop": crop,
                            "candidate_code": code,
                            "water_mode": water_mode,
                            "url": url,
                            "http_status": status,
                            "state": state,
                        }
                    )
    availability_path = OUT / "isimip_banana_taro_availability_audit_wave31.json"
    availability_path.write_text(json.dumps(availability_checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pyaez_states = pl.read_parquet(PYAEZ_BRIDGE).filter(pl.col("crop").is_in(["banana", "cassava", "taro"])).select(["crop", "water_mode", "bridge_state", "blocker"]).to_dicts() if PYAEZ_BRIDGE.exists() else []
    manifest: dict[str, Any] = {
        "schema_version": "population_capacity_crop_water_gap_wave31",
        "target_year": 1337,
        "purpose": "Resolve crop-specific water response without cross-crop or regional imputation.",
        "static_gaez": {
            "location_rows": static_df.height,
            "expected_rows": 20_929 * 6,
            "paired_location_rows": static_pair_df.height,
            "source_records": static_source_records,
            "semantics": "GAEZ v5 RES05-YXX low-input attainable dry-matter yield, paired LRLM rain-fed and LILM irrigated, AgERA5 HIST 1981-2000; static water response only.",
        },
        "cassava_isimip": {
            "location_rows": cassava_df.height,
            "expected_rows": 20_929 * 4,
            "superregion_rows": len(cassava_super_rows),
            "model_spread_rows": cassava_spread.height,
            "source_doi": "https://doi.org/10.48364/ISIMIP.729341",
            "sources": cassava_sources,
            "semantics": "LPJ-GUESS/LPJmL modern 1971-2010 annual yield simulations, crop-specific cassava (cas), rain-fed/full irrigation; relative tails/model spread only.",
        },
        "banana_taro_isimip_availability": {
            "audit": str(availability_path.relative_to(ROOT)),
            "audit_sha256": sha256(availability_path),
            "all_candidate_files_unavailable": all(item["http_status"] == 404 for item in availability_checks),
            "interpretation": "No official ISIMIP2a banana or taro global annual crop-yield files found under tested LPJ-GUESS/LPJmL codes; no synthetic annual risk rows are created.",
        },
        "pyaez_bridge_states": pyaez_states,
        "outputs": {
            "gaez_static_location": str(static_path.relative_to(ROOT)),
            "gaez_static_pair": str(static_pair_path.relative_to(ROOT)),
            "cassava_location_risk": str(cassava_path.relative_to(ROOT)),
            "cassava_superregion_risk": str(cassava_super_path.relative_to(ROOT)),
            "cassava_model_spread": str(cassava_spread_path.relative_to(ROOT)),
            "gaez_static_location_sha256": sha256(static_path),
            "gaez_static_pair_sha256": sha256(static_pair_path),
            "cassava_location_risk_sha256": sha256(cassava_path),
            "cassava_superregion_risk_sha256": sha256(cassava_super_path),
            "cassava_model_spread_sha256": sha256(cassava_spread_path),
        },
        "acceptance": {
            "banana_static_water_response_closed": True,
            "cassava_static_water_response_closed": True,
            "taro_static_water_response_closed": True,
            "cassava_modern_interannual_risk_bridge_closed": True,
            "banana_modern_interannual_risk_bridge_closed": False,
            "taro_modern_interannual_risk_bridge_closed": False,
            "training_unblocked": False,
            "blocking_gaps": [
                "Banana and taro have paired GAEZ water-mode baselines but no official global annual crop-model bridge found in ISIMIP2a.",
                "GAEZ static yields use 1981-2000 AgERA5 climate and cannot establish 1337 interannual tails.",
                "PyAEZ exact engine remains unresolved for banana/cassava/taro according to the existing bridge audit.",
            ],
        },
    }
    manifest_path = OUT / "crop_water_gap_manifest_wave31.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "static_rows": static_df.height, "cassava_rows": cassava_df.height}, indent=2))


if __name__ == "__main__":
    main()
