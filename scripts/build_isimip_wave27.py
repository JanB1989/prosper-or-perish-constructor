"""Map the paired ISIMIP2a CLM-Crop rice simulations to EU5 diagnostics.

The files are historical climate/model runs with modern/default management,
not 1337 observations.  Outputs are therefore restricted to relative risk,
water-mode contrast and parameter-uncertainty validation.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import polars as pl
from netCDF4 import Dataset


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave27"
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"
FILES = {
    "rainfed": OUT / "isimip_clm_crop_watch_rice_rainfed_1980_2012.nc4",
    "full_irrigation": OUT / "isimip_clm_crop_watch_rice_fullirr_1980_2012.nc4",
}


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
    years = np.arange(1980, 2013)
    for mode, path in FILES.items():
        with Dataset(str(path)) as dataset:
            glon = np.asarray(dataset.variables["lon"][:], dtype=float)
            glat = np.asarray(dataset.variables["lat"][:], dtype=float)
            lon_index = np.abs(glon[:, None] - lon[None, :]).argmin(axis=0)
            lat_index = np.abs(glat[:, None] - lat[None, :]).argmin(axis=0)
            variable = next(dataset.variables[name] for name in dataset.variables if name.startswith("yield-"))
            values = np.asarray(variable[:], dtype=float)[:, lat_index, lon_index]
            values[~np.isfinite(values)] = np.nan
            fill = getattr(variable, "_FillValue", None)
            if fill is not None:
                values[np.isclose(values, float(fill))] = np.nan
            values[values < 0] = np.nan
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
                        "dataset": "ISIMIP2a_CLM-Crop_WATCH_WFDEI",
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
                        "unit": "t_ha",
                    }
                )
    pl.DataFrame(rows).write_csv(OUT / "isimip_rice_superregion_annual_wave27.csv")

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
                    "dataset": "ISIMIP2a_CLM-Crop_WATCH_WFDEI",
                    "crop": "rice",
                    "year": int(year),
                    "super_region": region,
                    "paired_valid_area_fraction": fraction,
                    "irrigation_yield_increment_t_ha_mean": mean,
                    "irrigation_yield_increment_t_ha_median": median,
                    "unit": "t_ha",
                }
            )
    pl.DataFrame(contrasts).write_csv(OUT / "isimip_rice_irrigation_contrast_wave27.csv")

    manifest = {
        "schema_version": "population_capacity_isimip_interannual_skill_mapping_v1",
        "years": [1980, 2012],
        "location_count": len(locations),
        "super_regions": groups,
        "grid": grid_metadata,
        "map_method": "nearest CLM-Crop 0.5-degree grid center from calibrated EU5 centroid; calibrated area_km2 weights summaries",
        "semantics": {
            "model": "CLM-Crop WATCH, ISIMIP2a/GGCMI historical simulation",
            "crop": "rice",
            "water_modes": ["rainfed", "full_irrigation"],
            "units": "t ha-1 yr-1",
            "technology": "default/present-day model management; not 1337",
            "training_target_allowed": False,
            "allowed_role": "relative crop-risk and water-mode response validation plus parameter diagnostics",
        },
        "files": {},
    }
    for mode, path in FILES.items():
        manifest["files"][mode] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    for filename in ("isimip_rice_superregion_annual_wave27.csv", "isimip_rice_irrigation_contrast_wave27.csv"):
        path = OUT / filename
        manifest["files"][filename] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    (OUT / "isimip_mapping_manifest_wave27.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
