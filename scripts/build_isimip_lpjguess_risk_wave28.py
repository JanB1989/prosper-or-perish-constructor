"""Map independent ISIMIP2a LPJ-GUESS rice runs and compare with CLM-Crop.

LPJ-GUESS and CLM-Crop are both modern/default-management simulations. Their
spread is therefore a model/forcing uncertainty diagnostic, not a 1337 yield
label and not a population target.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import polars as pl
from netCDF4 import Dataset


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave28"
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"
FILES = {
    "rainfed": OUT / "isimip_lpjguess_princeton_rice_rainfed_1971_2012.nc4",
    "full_irrigation": OUT / "isimip_lpjguess_princeton_rice_fullirr_1971_2012.nc4",
}
CLM_REPORT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave27/isimip_rice_superregion_annual_wave27.csv"


def correlation(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan"), float("nan")
    pearson = float(np.corrcoef(a, b)[0, 1])
    rank_a = np.argsort(np.argsort(a))
    rank_b = np.argsort(np.argsort(b))
    spearman = float(np.corrcoef(rank_a, rank_b)[0, 1])
    return pearson, spearman


def main() -> None:
    locations = pl.read_parquet(LOCATIONS).select(
        ["location_tag", "super_region", "area_km2", "calibrated_lon", "calibrated_lat"]
    )
    lon = np.asarray(locations["calibrated_lon"], dtype=float)
    lat = np.asarray(locations["calibrated_lat"], dtype=float)
    area = np.asarray(locations["area_km2"], dtype=float)
    group = np.asarray(locations["super_region"])
    groups = sorted(set(group.tolist()))
    arrays: dict[str, np.ndarray] = {}
    grid_metadata: dict[str, float] = {}
    years = np.arange(1971, 2013)
    for mode, path in FILES.items():
        with Dataset(str(path)) as dataset:
            glon = np.asarray(dataset.variables["lon"][:], dtype=float)
            glat = np.asarray(dataset.variables["lat"][:], dtype=float)
            lon_index = np.abs(glon[:, None] - lon[None, :]).argmin(axis=0)
            lat_index = np.abs(glat[:, None] - lat[None, :]).argmin(axis=0)
            variable = next(dataset.variables[name] for name in dataset.variables if name.startswith("yield-"))
            # Read the contiguous 42-year field once, then apply NumPy
            # nearest-grid indexing.  netCDF4's two-vector fancy indexing
            # performs one hyperslab per point and is prohibitively slow for
            # 20,929 locations.
            full_field = np.asarray(variable[:], dtype=float)
            values = full_field[:, lat_index, lon_index]
            fill = getattr(variable, "_FillValue", None)
            if fill is not None:
                values[np.isclose(values, float(fill))] = np.nan
            values[~np.isfinite(values) | (values < 0)] = np.nan
            arrays[mode] = values
            grid_metadata = {
                "lon_grid_min": float(glon.min()),
                "lon_grid_max": float(glon.max()),
                "lat_grid_min": float(glat.min()),
                "lat_grid_max": float(glat.max()),
                "grid_resolution_deg": 0.5,
            }

    rows: list[dict[str, object]] = []
    for mode, values in arrays.items():
        for index, year in enumerate(years):
            for region in groups:
                mask = group == region
                weights = area[mask]
                sample = values[index, mask]
                valid = np.isfinite(sample)
                valid_weights = weights[valid]
                valid_values = sample[valid]
                total_area = float(weights.sum())
                valid_area = float(valid_weights.sum()) if valid.any() else 0.0
                if valid.any():
                    mean = float(np.average(valid_values, weights=valid_weights))
                    std = float(np.sqrt(np.average((valid_values - mean) ** 2, weights=valid_weights)))
                    median = float(np.median(valid_values))
                else:
                    mean = std = median = float("nan")
                rows.append(
                    {
                        "dataset": "ISIMIP2a_LPJ-GUESS_Princeton",
                        "crop": "rice",
                        "water_mode": mode,
                        "year": int(year),
                        "super_region": region,
                        "location_count": int(mask.sum()),
                        "valid_location_count": int(valid.sum()),
                        "total_area_km2": total_area,
                        "valid_area_km2": valid_area,
                        "valid_area_fraction": valid_area / total_area if total_area else 0.0,
                        "yield_t_ha_area_weighted_mean": mean,
                        "yield_t_ha_area_weighted_std": std,
                        "yield_t_ha_area_weighted_median": median,
                        "unit": "t_ha_per_growing_season",
                    }
                )
    report_path = OUT / "isimip_lpjguess_rice_superregion_annual_wave28.csv"
    pl.DataFrame(rows).write_csv(report_path)

    contrasts: list[dict[str, object]] = []
    for index, year in enumerate(years):
        difference = arrays["full_irrigation"][index] - arrays["rainfed"][index]
        paired = np.isfinite(arrays["full_irrigation"][index]) & np.isfinite(arrays["rainfed"][index])
        for region in groups:
            mask = (group == region) & paired
            weights = area[mask]
            values = difference[mask]
            if values.size:
                mean = float(np.average(values, weights=weights))
                median = float(np.median(values))
                fraction = float(weights.sum() / area[group == region].sum())
            else:
                mean = median = float("nan")
                fraction = 0.0
            contrasts.append(
                {
                    "dataset": "ISIMIP2a_LPJ-GUESS_Princeton",
                    "crop": "rice",
                    "year": int(year),
                    "super_region": region,
                    "paired_valid_area_fraction": fraction,
                    "irrigation_yield_increment_t_ha_mean": mean,
                    "irrigation_yield_increment_t_ha_median": median,
                    "unit": "t_ha_per_growing_season",
                }
            )
    contrast_path = OUT / "isimip_lpjguess_rice_irrigation_contrast_wave28.csv"
    pl.DataFrame(contrasts).write_csv(contrast_path)

    # Compare LPJ-GUESS and CLM-Crop over their 1980-2012 overlap.  The
    # comparison intentionally keeps forcing/model disagreement visible.
    clm = pl.read_csv(CLM_REPORT)
    lpj = pl.DataFrame(rows).filter(pl.col("year").is_between(1980, 2012))
    skill_rows: list[dict[str, object]] = []
    for mode in ("rainfed", "full_irrigation"):
        a = lpj.filter(pl.col("water_mode") == mode)
        b = clm.filter(pl.col("water_mode") == mode)
        for region in groups:
            left = a.filter(pl.col("super_region") == region).select(
                ["year", "yield_t_ha_area_weighted_mean", "valid_area_fraction"]
            )
            right = b.filter(pl.col("super_region") == region).select(
                ["year", "yield_t_ha_area_weighted_mean", "valid_area_fraction"]
            )
            joined = left.join(right, on="year", suffix="_clm").sort("year")
            finite = joined.filter(
                pl.col("yield_t_ha_area_weighted_mean").is_finite()
                & pl.col("yield_t_ha_area_weighted_mean_clm").is_finite()
            )
            lpj_values = finite["yield_t_ha_area_weighted_mean"].to_numpy()
            clm_values = finite["yield_t_ha_area_weighted_mean_clm"].to_numpy()
            if len(lpj_values):
                lpj_anom = lpj_values - np.median(lpj_values)
                clm_anom = clm_values - np.median(clm_values)
                pearson, spearman = correlation(lpj_anom, clm_anom)
                # A model can legitimately report zero rice yield outside its
                # own crop mask.  Do not turn those mask differences into an
                # infinite parameter-spread ratio; report the productive
                # overlap count and leave the ratio unresolved when neither
                # model has a comparable positive yield.
                productive = (lpj_values > 0.1) & (clm_values > 0.1)
                if productive.any():
                    spread_ratio = float(
                        np.median(lpj_values[productive] / clm_values[productive])
                    )
                else:
                    spread_ratio = float("nan")
                lpj_cov = float(finite["valid_area_fraction"].min())
                clm_cov = float(finite["valid_area_fraction_clm"].min())
                productive_count = int(productive.sum())
            else:
                pearson = spearman = spread_ratio = float("nan")
                lpj_cov = clm_cov = 0.0
                productive_count = 0
            skill_rows.append(
                {
                    "source_a": "ISIMIP2a_LPJ-GUESS_Princeton",
                    "source_b": "ISIMIP2a_CLM-Crop_WATCH_WFDEI",
                    "crop": "rice",
                    "water_mode": mode,
                    "super_region": region,
                    "year_start": 1980,
                    "year_end": 2012,
                    "overlap_year_count": int(len(lpj_values)),
                    "min_lpj_valid_area_fraction": lpj_cov,
                    "min_clm_valid_area_fraction": clm_cov,
                    "productive_overlap_year_count_threshold_0p1_t_ha": productive_count,
                    "pearson_anomaly_correlation": pearson,
                    "spearman_anomaly_correlation": spearman,
                    "median_lpj_to_clm_yield_ratio": spread_ratio,
                    "interpretation": "Modern model/forcing spread only; not a 1337 yield target or population-capacity label.",
                }
            )
    skill_path = OUT / "isimip_lpjguess_clm_rice_skill_wave28.csv"
    pl.DataFrame(skill_rows).write_csv(skill_path)

    manifest = {
        "schema_version": "population_capacity_isimip_lpjguess_uncertainty_mapping_v1",
        "source": {
            "dataset_doi": "https://doi.org/10.48364/ISIMIP.729341",
            "repository_model_page": "https://www.isimip.org/impactmodels/details/79/",
            "protocol": "https://www.isimip.org/documents/648/ISIMIP2a_protocol_230302_agriculture.pdf",
            "model": "LPJ-GUESS",
            "climate_forcing": "Princeton PGMFD v2.1",
            "years": [1971, 2012],
            "crop": "rice",
            "modes": ["rainfed", "full_irrigation"],
            "grid_resolution_deg": 0.5,
        },
        "coverage": {
            "location_count": len(locations),
            "super_regions": groups,
            "annual_report_rows": len(rows),
            "paired_contrast_rows": len(contrasts),
            "model_skill_rows": len(skill_rows),
            "mapping_method": "nearest 0.5-degree grid center from calibrated EU5 centroid; area_km2-weighted summaries",
        },
        "semantics": {
            "unit": "dry matter t ha-1 per growing season",
            "modern_default_management": True,
            "1337_technology": False,
            "parameter_uncertainty": "LPJ-GUESS versus CLM-Crop spread combines crop-model, climate-forcing, and management differences; it is carried as uncertainty metadata only.",
            "training_target_allowed": False,
            "validation_allowed": True,
        },
        "files": {},
        "acceptance": {
            "independent_global_crop_model_acquired": True,
            "paired_rainfed_and_full_irrigation": True,
            "model_spread_mapped_to_all_locations": True,
            "1337_absolute_yield_parameter_calibration_closed": False,
            "mechanistic_p10_p90_gate_unblocked": False,
            "blocking_gaps": [
                "The LPJ-GUESS/CLM-Crop comparison is modern and default-management, not 1337 technology.",
                "Model spread conflates forcing, crop model, and management differences; it cannot be interpreted as a pure parameter posterior.",
                "No full multi-model, multi-crop, 1100-1500 annual simulation ensemble with exact EU5 physical labels is available.",
            ],
        },
    }
    for mode, path in FILES.items():
        manifest["files"][mode] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    for name, path in {
        "annual_report": report_path,
        "irrigation_contrast": contrast_path,
        "model_skill": skill_path,
    }.items():
        manifest["files"][name] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    manifest_path = OUT / "isimip_lpjguess_uncertainty_manifest_wave28.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
