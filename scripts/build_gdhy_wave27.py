"""Map GDHY annual global crop yields to EU5 locations for validation only.

GDHY is a modern (1981-2016) satellite/FAO-aligned yield estimate.  This
script deliberately emits relative-risk/coverage diagnostics and never writes
a population-capacity target or performs 1337 technology imputation.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile
import hashlib
import json

import numpy as np
import polars as pl
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave27/gdhy_v1.2_v1.3_20190128.zip"
OUT = SOURCE.parent
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"
CROPS = ("maize_major", "rice_major", "wheat_winter", "soybean")
YEARS = range(1981, 2017)


def _nearest_indices(lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon360 = np.mod(lon, 360.0)
    return (
        np.clip(np.rint((lon360 - 0.25) / 0.5).astype(int), 0, 719),
        np.clip(np.rint((lat + 89.75) / 0.5).astype(int), 0, 359),
    )


def main() -> None:
    locations = pl.read_parquet(LOCATIONS).select(
        ["location_tag", "super_region", "area_km2", "calibrated_lon", "calibrated_lat"]
    )
    lon = np.asarray(locations["calibrated_lon"], dtype=float)
    lat = np.asarray(locations["calibrated_lat"], dtype=float)
    area = np.asarray(locations["area_km2"], dtype=float)
    super_region = np.asarray(locations["super_region"])
    lon_index, lat_index = _nearest_indices(lon, lat)
    regions = sorted(set(super_region.tolist()))

    crosswalk = pl.DataFrame(
        {
            "location_tag": locations["location_tag"],
            "super_region": locations["super_region"],
            "calibrated_lon": locations["calibrated_lon"],
            "calibrated_lat": locations["calibrated_lat"],
            "gdhy_grid_lon": 0.25 + 0.5 * lon_index,
            "gdhy_grid_lat": -89.75 + 0.5 * lat_index,
            "grid_lon_index": lon_index,
            "grid_lat_index": lat_index,
            "area_km2": locations["area_km2"],
        }
    )
    crosswalk.write_parquet(OUT / "gdhy_location_grid_crosswalk_wave27.parquet")

    rows: list[dict[str, object]] = []
    with ZipFile(SOURCE) as archive:
        for crop in CROPS:
            for year in YEARS:
                raw = archive.read(f"{crop}/yield_{year}.nc4")
                # netCDF4 is unavailable for BytesIO in the constructor runtime;
                # use a short-lived file and close it before the next member.
                with NamedTemporaryFile(suffix=".nc4") as temporary:
                    temporary.write(raw)
                    temporary.flush()
                    dataset = xr.open_dataset(temporary.name, engine="netcdf4")
                    values = np.asarray(dataset["var"].values[lat_index, lon_index], dtype=float)
                    dataset.close()
                values[~np.isfinite(values)] = np.nan
                for group in regions:
                    mask = super_region == group
                    weights = area[mask]
                    sample = values[mask]
                    valid = np.isfinite(sample) & (sample >= 0)
                    valid_weights = weights[valid]
                    valid_values = sample[valid]
                    total_area = float(weights.sum())
                    valid_area = float(valid_weights.sum()) if valid.any() else 0.0
                    if valid.any():
                        mean = float(np.average(valid_values, weights=valid_weights))
                        std = float(np.sqrt(np.average((valid_values - mean) ** 2, weights=valid_weights)))
                        order = np.argsort(valid_values)
                        sorted_values = valid_values[order]
                        cumulative = np.cumsum(valid_weights[order]) / valid_weights.sum()
                        p10, p50, p90 = [float(np.interp(q, cumulative, sorted_values)) for q in (0.1, 0.5, 0.9)]
                    else:
                        mean = std = p10 = p50 = p90 = float("nan")
                    rows.append(
                        {
                            "dataset": "GDHYv1.2+v1.3",
                            "crop": crop,
                            "year": year,
                            "super_region": group,
                            "location_count": int(mask.sum()),
                            "valid_location_count": int(valid.sum()),
                            "total_area_km2": total_area,
                            "valid_area_km2": valid_area,
                            "valid_area_fraction": valid_area / total_area if total_area else 0.0,
                            "yield_t_ha_area_weighted_mean": mean,
                            "yield_t_ha_area_weighted_std": std,
                            "yield_t_ha_area_weighted_p10": p10,
                            "yield_t_ha_area_weighted_p50": p50,
                            "yield_t_ha_area_weighted_p90": p90,
                            "unit": "t_ha",
                        }
                    )
    pl.DataFrame(rows).write_csv(OUT / "gdhy_superregion_annual_wave27.csv")

    manifest = {
        "schema_version": "population_capacity_gdhy_interannual_mapping_v1",
        "source_zip": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_size_bytes": SOURCE.stat().st_size,
        "location_count": len(locations),
        "location_map_rows": len(crosswalk),
        "report_rows": len(rows),
        "crops": list(CROPS),
        "years": [1981, 2016],
        "grid_resolution_deg": 0.5,
        "grid_center_convention": "lon 0.25+0.5*i, lat -89.75+0.5*j",
        "map_method": "nearest grid-cell center from calibrated EU5 centroid; calibrated area_km2 weights super-region summaries",
        "source_semantics": "Satellite vegetation-index estimates aligned to FAO country yields; modern observed/estimated yields, not 1337 attainable yields",
        "training_target_allowed": False,
        "validity_policy": "Modern climate-to-yield skill and variance validation only; no absolute 1337 labels or population targets.",
        "files": {},
    }
    for filename in ("gdhy_location_grid_crosswalk_wave27.parquet", "gdhy_superregion_annual_wave27.csv"):
        path = OUT / filename
        manifest["files"][filename] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    (OUT / "gdhy_mapping_manifest_wave27.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
