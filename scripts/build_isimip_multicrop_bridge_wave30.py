"""Build a crop-specific interannual-risk bridge from ISIMIP2a.

The bridge uses two independent ISIMIP2a global crop models (LPJ-GUESS and
LPJmL), four staple crops, and rain-fed/full-irrigation runs.  It is mapped to
all EU5 location centroids without regional or global filling.  The output is
an uncertainty/diagnostic layer only: ISIMIP explicitly cautions that model
absolute yields are not calibrated observations, so these records cannot be
used as 1337 population labels or as a historical scale anchor.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.request import urlretrieve

import numpy as np
import polars as pl
from netCDF4 import Dataset, num2date


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave30"
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"


DOI = "https://doi.org/10.48364/ISIMIP.729341"
REPOSITORY = "https://data.isimip.org/10.48364/ISIMIP.729341"
PROTOCOL = "https://www.isimip.org/documents/329/ISIMIP2a__Agriculture_crop_modelling.pdf"
CAVEAT_URL = "https://www.isimip.org/outputdata/caveats-fast-track/"


@dataclass(frozen=True)
class Source:
    model_id: str
    model_label: str
    model_dir: str
    filename_prefix: str
    crop: str
    crop_code: str
    water_mode: str
    mode_code: str

    @property
    def filename(self) -> str:
        return (
            f"{self.filename_prefix}_gswp3_nobc_hist_co2_yield-"
            f"{self.crop_code}-{self.mode_code}-default_global_annual_1971_2010.nc4"
        )

    @property
    def download_url(self) -> str:
        return (
            f"https://files.isimip.org/ISIMIP2a/OutputData/agriculture/"
            f"{self.model_dir}/gswp3/historical/{self.filename}"
        )

    @property
    def path(self) -> Path:
        return OUT / self.filename


CROPS = (("maize", "mai"), ("wheat", "whe"), ("rice", "ric"), ("soy", "soy"))
MODES = (("rainfed", "noirr"), ("full_irrigation", "firr"))
MODELS = (
    ("lpj_guess", "LPJ-GUESS", "LPJ-GUESS", "lpj-guess"),
    ("lpjml", "LPJmL", "LPJmL", "lpjml"),
)
SOURCES = tuple(
    Source(model_id, model_label, model_dir, prefix, crop, crop_code, water_mode, mode_code)
    for model_id, model_label, model_dir, prefix in MODELS
    for crop, crop_code in CROPS
    for water_mode, mode_code in MODES
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_source(source: Source) -> None:
    if source.path.exists():
        return
    OUT.mkdir(parents=True, exist_ok=True)
    partial = source.path.with_suffix(source.path.suffix + ".partial")
    urlretrieve(source.download_url, partial)
    partial.replace(source.path)


def as_float(values: Any) -> np.ndarray:
    if np.ma.isMaskedArray(values):
        return np.asarray(values.filled(np.nan), dtype=float)
    return np.asarray(values, dtype=float)


def quantile(values: np.ndarray, q: float) -> float:
    finite = values[np.isfinite(values)]
    return float(np.quantile(finite, q)) if finite.size else float("nan")


def read_source(source: Source, lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    with Dataset(str(source.path)) as dataset:
        glon = as_float(dataset.variables["lon"][:])
        glat = as_float(dataset.variables["lat"][:])
        time_var = dataset.variables["time"]
        # ISIMIP encodes the 1971-2010 annual axis as "years since
        # 1901-1-1"; use the declared calendar rather than treating 70..109
        # as literal AD years.
        time_values = as_float(time_var[:])
        time_units = getattr(time_var, "units", None)
        if time_units and time_units.lower().startswith("years since"):
            base_match = re.search(r"years since\s+(\d{3,4})", time_units.lower())
            if not base_match:
                raise ValueError(f"cannot parse ISIMIP time units {time_units!r}")
            years = int(base_match.group(1)) + np.rint(time_values).astype(int)
        elif time_units:
            dates = num2date(
                time_values,
                units=time_units,
                calendar=getattr(time_var, "calendar", "standard"),
                only_use_cftime_datetimes=False,
            )
            years = np.asarray([int(date.year) for date in dates], dtype=int)
        else:
            years = np.rint(time_values).astype(int)
        variable_names = [name for name in dataset.variables if name.startswith("yield-")]
        if not variable_names:
            raise ValueError(f"no yield variable in {source.path}; variables={list(dataset.variables)}")
        variable = dataset.variables[variable_names[0]]
        field = as_float(variable[:])
        if field.ndim != 3:
            raise ValueError(f"expected time-lat-lon yield field, got {variable.dimensions} in {source.path}")
        in_domain = (
            np.isfinite(lon)
            & np.isfinite(lat)
            & (lon >= float(np.nanmin(glon)))
            & (lon <= float(np.nanmax(glon)))
            & (lat >= float(np.nanmin(glat)))
            & (lat <= float(np.nanmax(glat)))
        )
        lon_index = np.abs(glon[:, None] - lon[None, :]).argmin(axis=0)
        lat_index = np.abs(glat[:, None] - lat[None, :]).argmin(axis=0)
        values = field[:, lat_index, lon_index]
        values[~np.isfinite(values)] = np.nan
        # Keep valid physical zeros.  Only impossible numeric overflow is
        # treated as missing; nodata is already masked above.
        values[(values < -1e3) | (values > 1e3)] = np.nan
        metadata = {
            "grid_lat_count": int(glat.size),
            "grid_lon_count": int(glon.size),
            "grid_lat_min": float(glat.min()),
            "grid_lat_max": float(glat.max()),
            "grid_lon_min": float(glon.min()),
            "grid_lon_max": float(glon.max()),
            "grid_resolution_lat_deg": float(np.nanmedian(np.abs(np.diff(glat)))) if glat.size > 1 else None,
            "grid_resolution_lon_deg": float(np.nanmedian(np.abs(np.diff(glon)))) if glon.size > 1 else None,
        }
    values[:, ~in_domain] = np.nan
    return years, values, {"in_domain": in_domain, **metadata}


def source_rows(source: Source, locations: pl.DataFrame, values: np.ndarray, years: np.ndarray, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(locations.height):
        sample = values[:, i]
        valid = np.isfinite(sample)
        state = (
            "resolved_modern_model_yield_risk"
            if metadata["in_domain"][i] and valid.sum() >= 20
            else "outside_source_domain"
            if not metadata["in_domain"][i]
            else "insufficient_valid_years"
        )
        rows.append(
            {
                "location_tag": locations["location_tag"][i],
                "super_region": locations["super_region"][i],
                "calibrated_lon": float(locations["calibrated_lon"][i]),
                "calibrated_lat": float(locations["calibrated_lat"][i]),
                "area_km2": float(locations["area_km2"][i]),
                "model_id": source.model_id,
                "model": source.model_label,
                "crop": source.crop,
                "water_mode": source.water_mode,
                "source_id": f"{source.model_id}_{source.crop}_{source.water_mode}",
                "year_start": int(years.min()) if years.size else None,
                "year_end": int(years.max()) if years.size else None,
                "valid_year_count": int(valid.sum()),
                "coverage_fraction": float(valid.mean()) if valid.size else 0.0,
                "yield_p10_t_ha": quantile(sample, 0.10),
                "yield_p50_t_ha": quantile(sample, 0.50),
                "yield_p90_t_ha": quantile(sample, 0.90),
                "lower_tail_ratio_p10_p50": (
                    float(quantile(sample, 0.10) / quantile(sample, 0.50))
                    if valid.any() and quantile(sample, 0.50) > 0
                    else float("nan")
                ),
                "zero_yield_year_fraction": float(np.mean(sample[valid] == 0)) if valid.any() else float("nan"),
                "label_state": state,
                "reason_code": "no_imputation" if state == "resolved_modern_model_yield_risk" else state,
                "absolute_1337_yield": False,
                "training_target_allowed": False,
                "population_target": False,
            }
        )
    return rows


def superregion_rows(source: Source, locations: pl.DataFrame, values: np.ndarray, years: np.ndarray) -> list[dict[str, Any]]:
    groups = locations["super_region"].unique().sort().to_list()
    regions = locations["super_region"].to_numpy()
    area = locations["area_km2"].to_numpy().astype(float)
    rows: list[dict[str, Any]] = []
    for group in groups:
        members = np.flatnonzero(regions == group)
        valid = np.isfinite(values[:, members])
        flattened = values[:, members][valid]
        total_area = float(area[members].sum())
        valid_area = np.where(valid, area[members][None, :], 0.0).sum()
        rows.append(
            {
                "model_id": source.model_id,
                "model": source.model_label,
                "crop": source.crop,
                "water_mode": source.water_mode,
                "source_id": f"{source.model_id}_{source.crop}_{source.water_mode}",
                "super_region": group,
                "location_count": int(members.size),
                "resolved_location_count": int(np.any(valid, axis=0).sum()),
                "total_area_km2": total_area,
                "valid_area_fraction": float(valid_area / (total_area * len(years))) if total_area and years.size else 0.0,
                "year_start": int(years.min()) if years.size else None,
                "year_end": int(years.max()) if years.size else None,
                "valid_value_count": int(flattened.size),
                "yield_p10_t_ha": quantile(flattened, 0.10),
                "yield_p50_t_ha": quantile(flattened, 0.50),
                "yield_p90_t_ha": quantile(flattened, 0.90),
                "training_target_allowed": False,
                "population_target": False,
            }
        )
    return rows


def paired_model_rows(location_rows: pl.DataFrame) -> pl.DataFrame:
    selected = location_rows.select(
        ["location_tag", "super_region", "crop", "water_mode", "model_id", "yield_p10_t_ha", "yield_p50_t_ha", "yield_p90_t_ha", "label_state"]
    )
    left = selected.filter(pl.col("model_id") == "lpj_guess").drop("model_id").rename(
        {c: f"{c}_lpj_guess" for c in ["yield_p10_t_ha", "yield_p50_t_ha", "yield_p90_t_ha", "label_state"]}
    )
    right = selected.filter(pl.col("model_id") == "lpjml").drop("model_id").rename(
        {c: f"{c}_lpjml" for c in ["yield_p10_t_ha", "yield_p50_t_ha", "yield_p90_t_ha", "label_state"]}
    )
    paired = left.join(right, on=["location_tag", "super_region", "crop", "water_mode"], how="left")
    return paired.with_columns(
        [
            pl.when((pl.col("yield_p50_t_ha_lpj_guess") > 0) & (pl.col("yield_p50_t_ha_lpjml") > 0))
            .then(pl.col("yield_p50_t_ha_lpj_guess") / pl.col("yield_p50_t_ha_lpjml"))
            .otherwise(None)
            .alias("model_p50_ratio_lpj_guess_to_lpjml"),
            pl.when(pl.col("yield_p50_t_ha_lpj_guess").is_finite() & pl.col("yield_p50_t_ha_lpjml").is_finite())
            .then((pl.col("yield_p50_t_ha_lpj_guess") - pl.col("yield_p50_t_ha_lpjml")).abs())
            .otherwise(None)
            .alias("model_p50_absolute_difference_t_ha"),
            pl.lit("model_spread_only_not_1337_yield_target").alias("interpretation"),
            pl.lit(False).alias("training_target_allowed"),
            pl.lit(False).alias("population_target"),
        ]
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    locations = pl.read_parquet(LOCATIONS).select(
        ["location_tag", "super_region", "area_km2", "calibrated_lon", "calibrated_lat"]
    )
    if locations.height != 20_929:
        raise ValueError(f"expected 20,929 EU5 locations, found {locations.height}")
    lon = locations["calibrated_lon"].to_numpy().astype(float)
    lat = locations["calibrated_lat"].to_numpy().astype(float)
    location_rows_all: list[dict[str, Any]] = []
    super_rows_all: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    for source in SOURCES:
        ensure_source(source)
        years, values, metadata = read_source(source, lon, lat)
        location_rows_all.extend(source_rows(source, locations, values, years, metadata))
        super_rows_all.extend(superregion_rows(source, locations, values, years))
        state_counts: dict[str, int] = {}
        for row in source_rows(source, locations, values, years, metadata):
            state_counts[row["label_state"]] = state_counts.get(row["label_state"], 0) + 1
        source_records.append(
            {
                "source_id": f"{source.model_id}_{source.crop}_{source.water_mode}",
                "model_id": source.model_id,
                "model": source.model_label,
                "crop": source.crop,
                "water_mode": source.water_mode,
                "file_name": source.filename,
                "download_url": source.download_url,
                "sha256": sha256(source.path),
                "years": [int(years.min()), int(years.max())] if years.size else [],
                "grid": {key: value for key, value in metadata.items() if key != "in_domain"},
                "mapped_location_count": int(metadata["in_domain"].sum()),
                "label_state_counts": state_counts,
                "unit": "dry matter t ha-1 per growing season",
                "training_target_allowed": False,
                "population_target": False,
                "absolute_1337_yield": False,
            }
        )

    location_path = OUT / "isimip_multicrop_location_risk_wave30.csv"
    super_path = OUT / "isimip_multicrop_superregion_risk_wave30.csv"
    location_df = pl.DataFrame(location_rows_all)
    location_df.write_csv(location_path)
    pl.DataFrame(super_rows_all).write_csv(super_path)
    paired_path = OUT / "isimip_multicrop_model_spread_wave30.csv"
    paired = paired_model_rows(location_df)
    paired.write_csv(paired_path)

    manifest: dict[str, Any] = {
        "schema_version": "population_capacity_isimip_multicrop_bridge_v1",
        "target_year": 1337,
        "source_period": [1971, 2010],
        "source_doi": DOI,
        "repository": REPOSITORY,
        "protocol": PROTOCOL,
        "caveat": CAVEAT_URL,
        "models": [label for _, label, _, _ in MODELS],
        "crops": [crop for crop, _ in CROPS],
        "water_modes": [mode for mode, _ in MODES],
        "sources": source_records,
        "coverage": {
            "location_count": locations.height,
            "location_matrix_rows": len(location_rows_all),
            "expected_location_matrix_rows": 20_929 * len(SOURCES),
            "superregion_rows": len(super_rows_all),
            "paired_model_rows": paired.height,
            "mapping_method": "nearest native 0.5-degree grid point to calibrated EU5 centroid; no cross-source, regional, or global imputation",
        },
        "semantics": {
            "modern_historical_weather_model_runs": True,
            "absolute_1337_yield": False,
            "historical_crop_yield_label": False,
            "population_target": False,
            "zero_is_preserved": True,
            "model_spread_is_uncertainty_metadata": True,
            "ISIMIP_absolute_yield_caveat": "LPJ-GUESS and LPJmL absolute yields are model outputs and are not calibrated historical observations; use relative variability/model spread only.",
        },
        "acceptance": {
            "all_required_location_model_crop_mode_rows_present": len(location_rows_all) == 20_929 * len(SOURCES),
            "global_absolute_1337_yield_closed": False,
            "crop_specific_interannual_risk_bridge_available": True,
            "parameter_uncertainty_closed": False,
            "training_unblocked": False,
            "blocking_gaps": [
                "ISIMIP runs are modern model simulations (1971-2010), not 1337 yield observations.",
                "Absolute yields are not calibrated observations; only relative tails and model disagreement are retained.",
                "The bridge does not resolve historical management, cultivar, soil depletion, or 1337 technology effects.",
            ],
        },
        "outputs": {
            "location_risk": str(location_path.relative_to(ROOT)),
            "superregion_risk": str(super_path.relative_to(ROOT)),
            "model_spread": str(paired_path.relative_to(ROOT)),
            "location_risk_sha256": sha256(location_path),
            "superregion_risk_sha256": sha256(super_path),
            "model_spread_sha256": sha256(paired_path),
        },
    }
    manifest_path = OUT / "isimip_multicrop_bridge_manifest_wave30.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "location_rows": len(location_rows_all), "paired_rows": paired.height}, indent=2))


if __name__ == "__main__":
    main()
