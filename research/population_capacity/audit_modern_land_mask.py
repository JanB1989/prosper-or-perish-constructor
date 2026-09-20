"""Compare modern built-up cover and crop physics at the canonical samples.

Run after acquire_repair_sources.py. This diagnoses a historical extrapolation
problem; it neither replaces soil constraints with climatic yield nor fits K.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl
import rasterio


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "artifacts/data/population_capacity/repair_sources"
SAMPLES = ROOT / "artifacts/data/population_capacity/geometry_land_contract_candidate_v1/full/game_authoritative_physical_samples.parquet"
CROP = ROOT / "artifacts/data/population_capacity/crop_mode_samples/gaez_v5/wheat_rainfed.parquet"
TAGS = ("paris", "wuxian", "cairo", "guenoa", "varanasi", "thanjavur", "moxos", "djenne", "bodo")
LAYERS = {
    "modern_built_percent": "gaez_v5_2020_built_up.tif",
    "wheat_rainfed_climate_yield": "gaez_v5_wheat_climate_rainfed.tif",
    "wheat_irrigated_climate_yield": "gaez_v5_wheat_climate_irrigated.tif",
}


def audit() -> dict:
    samples = pl.read_parquet(SAMPLES).filter(pl.col("location_tag").is_in(TAGS)).select(
        "location_tag", "sample_index", "physical_sample_lon", "physical_sample_lat", "sample_weight")
    if set(samples["location_tag"]) != set(TAGS):
        raise ValueError("diagnostic locations missing from physical geometry")
    coordinates = samples.select("physical_sample_lon", "physical_sample_lat").rows()
    for column, filename in LAYERS.items():
        with rasterio.open(SOURCE / filename) as raster:
            values = np.ma.concatenate(list(raster.sample(coordinates, masked=True))).filled(np.nan)
            # Units and scale have been checked against cached provider metadata.
            if raster.scales != (1.,) or raster.offsets != (0.,):
                raise ValueError(f"unexpected raster scaling: {filename}")
        samples = samples.with_columns(pl.Series(column, values).fill_nan(None))
    samples = samples.join(pl.read_parquet(CROP, columns=["location_tag", "sample_index",
        "yield_kg_dm_ha", "suitable_fraction"]), on=["location_tag", "sample_index"], validate="1:1")
    columns = [*LAYERS, "yield_kg_dm_ha", "suitable_fraction"]
    summary = samples.group_by("location_tag").agg(*[
        expression for column in columns for expression in (
            ((pl.col(column) * pl.col("sample_weight")).sum()
             / pl.col("sample_weight").filter(pl.col(column).is_not_null()).sum()).alias(column),
            pl.col("sample_weight").filter(pl.col(column).is_not_null()).sum().alias(column + "_coverage"),
        )]).sort("location_tag")
    samples.write_parquet(SOURCE / "modern_land_mask_diagnostic_samples.parquet")
    summary.write_csv(SOURCE / "modern_land_mask_diagnostic_locations.csv")
    inputs = [SAMPLES, CROP, Path(__file__), *(SOURCE / name for name in LAYERS.values())]
    payload = {
        "schema_version": 1,
        "role": "source interpretation diagnostic; not a capacity calibration target",
        "interpretation": "Modern built-up cover coincides with some low or zero agro-edaphic yields despite positive climatic yield. This does not isolate all soil, slope, land-mask or climate effects.",
        "limitations": ["GAEZ climatic yield omits edaphic constraints and cannot replace attainable subsistence yield",
                        "sample-point built-up cover and five-arc-minute crop grids have different resolution",
                        "GAEZ 1981–2000 climate and circa-2020 cover are not medieval observations",
                        "no automatic spatial imputation or adjustment has been applied"],
        "units": {"modern_built_percent": "percent of source cell",
                  "wheat_rainfed_climate_yield": "kg dry weight/ha, low input",
                  "wheat_irrigated_climate_yield": "kg dry weight/ha, low input",
                  "yield_kg_dm_ha": "kg dry matter/ha, best occurring suitability class; land-sample weighted mean",
                  "suitable_fraction": "fraction of source grid-cell area"},
        "input_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
        "locations": summary.to_dicts(),
    }
    (SOURCE / "modern_land_mask_diagnostic.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
