"""Build a mapped, historical drought-risk proxy from public NOAA atlases.

This is deliberately a climate-risk layer, not a crop-yield label.  The four
atlases cover different parts of the world and have different seasons,
reconstruction windows, and spatial support.  We preserve those semantics,
map only EU5 centroids that actually fall inside each source footprint, and
never fill an out-of-domain or invalid value from another source.

The resulting p10/p50/p90 and drought-frequency fields can inform the
mechanistic model's year-to-year reserve and uncertainty.  They cannot be
used as a historical population target without a crop-yield bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

import numpy as np
import polars as pl
from netCDF4 import Dataset


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave29"
LOCATIONS = ROOT / "artifacts/data/population_capacity/current_capacity_map/location_candidates.parquet"


@dataclass(frozen=True)
class Atlas:
    source_id: str
    path: Path
    variable: str
    lat_name: str
    lon_name: str
    time_name: str
    layout: str
    season: str
    period: tuple[int, int]
    citation: str
    url: str
    download_url: str
    longitude_convention: str = "east"


ATLASES = (
    Atlas(
        "noaa_nada_v2",
        OUT / "NADAv2-2008.nc",
        "PDSI",
        "lat",
        "lon",
        "time",
        "time_lat_lon",
        "JJA",
        (0, 2006),
        "Cook et al. (2004), North American Drought Atlas v2",
        "https://www.ncei.noaa.gov/products/paleoclimatology/drought-variability",
        "https://www.ncei.noaa.gov/pub/data/paleo/drought/NAmericanDroughtAtlas.v2/NADAv2-2008.nc",
    ),
    Atlas(
        "noaa_sada",
        OUT / "SADA_t.nc",
        "scpdsi",
        "latitude",
        "longitude",
        "Time",
        "time_lat_lon",
        "DJF (December assigned year)",
        (1400, 2000),
        "Morales et al. (2020), South American Drought Atlas",
        "https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=noaa-recon-30612",
        "https://www.ncei.noaa.gov/pub/data/paleo/drought/SADA/SADA_t.nc",
        "degrees_west_negative",
    ),
    Atlas(
        "noaa_mada",
        ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/MADApdsi.nc",
        "PDSI",
        "lat",
        "lon",
        "time",
        "time_lat_lon",
        "JJA",
        (1300, 2005),
        "Cook et al. (2010), Monsoon Asia Drought Atlas",
        "https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=noaa-recon-10435",
        "https://www.ncei.noaa.gov/pub/data/paleo/treering/reconstructions/asia/cook2010pdsi/MADApdsi.nc",
    ),
    Atlas(
        "noaa_owda",
        ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/owda.nc",
        "pdsi",
        "lat",
        "lon",
        "time",
        "lon_lat_time",
        "JJA",
        (0, 2012),
        "Cook et al. (2015), Old World Drought Atlas",
        "https://repository.library.noaa.gov/view/noaa/28655",
        "https://www.ncei.noaa.gov/pub/data/paleo/treering/reconstructions/europe/owda.nc",
    ),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _ensure_source(atlas: Atlas) -> None:
    """Acquire a missing official source without overwriting an existing file."""

    if atlas.path.exists():
        return
    atlas.path.parent.mkdir(parents=True, exist_ok=True)
    partial = atlas.path.with_suffix(atlas.path.suffix + ".partial")
    urlretrieve(atlas.download_url, partial)
    partial.replace(atlas.path)


def _as_float(values: Any) -> np.ndarray:
    """Read a masked netCDF variable without turning nodata into a value."""

    if np.ma.isMaskedArray(values):
        return np.asarray(values.filled(np.nan), dtype=float)
    return np.asarray(values, dtype=float)


def _time_years(variable: Any) -> np.ndarray:
    values = _as_float(variable[:])
    # NADA/MADA/OWDA encode AD years directly.  The units string on NADA says
    # "years since 0000-1-1" but its values are already the displayed AD year.
    return np.rint(values).astype(int)


def _source_values(atlas: Atlas, lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    with Dataset(str(atlas.path)) as dataset:
        glon = _as_float(dataset.variables[atlas.lon_name][:])
        glat = _as_float(dataset.variables[atlas.lat_name][:])
        years = _time_years(dataset.variables[atlas.time_name])
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
        variable = dataset.variables[atlas.variable]
        field = _as_float(variable[:])
        if atlas.layout == "time_lat_lon":
            values = field[:, lat_index, lon_index]
        elif atlas.layout == "lon_lat_time":
            values = field[lon_index, lat_index, :].T
        else:  # pragma: no cover - protected by the registry
            raise ValueError(f"unknown layout {atlas.layout}")
        # Some NOAA products use NaN fill, while old products use a numeric
        # sentinel.  Preserve physically valid PDSI extremes and remove only
        # non-finite or absurd values outside the index's documented range.
        values[~np.isfinite(values)] = np.nan
        values[(values < -20) | (values > 20)] = np.nan
        # Restrict every source to the requested historical comparison
        # window.  The native period is retained separately in the manifest.
        start, end = max(1100, atlas.period[0]), min(1500, atlas.period[1])
        window = (years >= start) & (years <= end)
        years = years[window]
        values = values[window, :]
        metadata = {
            "grid_lat_count": int(len(glat)),
            "grid_lon_count": int(len(glon)),
            "grid_lat_min": float(np.nanmin(glat)),
            "grid_lat_max": float(np.nanmax(glat)),
            "grid_lon_min": float(np.nanmin(glon)),
            "grid_lon_max": float(np.nanmax(glon)),
            "grid_resolution_lat_deg": float(np.nanmedian(np.abs(np.diff(glat)))) if len(glat) > 1 else None,
            "grid_resolution_lon_deg": float(np.nanmedian(np.abs(np.diff(glon)))) if len(glon) > 1 else None,
        }
    values[:, ~in_domain] = np.nan
    return years, values, {"in_domain": in_domain, **metadata}


def _quantile(values: np.ndarray, q: float) -> float:
    finite = values[np.isfinite(values)]
    return float(np.quantile(finite, q)) if finite.size else float("nan")


def _location_rows(atlas: Atlas, locations: pl.DataFrame) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray, dict[str, Any]]:
    lon = locations["calibrated_lon"].to_numpy().astype(float)
    lat = locations["calibrated_lat"].to_numpy().astype(float)
    years, values, grid = _source_values(atlas, lon, lat)
    rows: list[dict[str, Any]] = []
    for i in range(locations.height):
        sample = values[:, i]
        valid = np.isfinite(sample)
        state = "resolved_historical_climate_risk" if grid["in_domain"][i] and valid.sum() >= 20 else (
            "outside_source_domain" if not grid["in_domain"][i] else "insufficient_valid_years"
        )
        rows.append(
            {
                "location_tag": locations["location_tag"][i],
                "super_region": locations["super_region"][i],
                "calibrated_lon": float(lon[i]),
                "calibrated_lat": float(lat[i]),
                "area_km2": float(locations["area_km2"][i]),
                "source_id": atlas.source_id,
                "season": atlas.season,
                "year_start": int(years.min()) if years.size else None,
                "year_end": int(years.max()) if years.size else None,
                "valid_year_count": int(valid.sum()),
                "coverage_fraction": float(valid.mean()) if valid.size else 0.0,
                "p10_pdsi": _quantile(sample, 0.10),
                "p50_pdsi": _quantile(sample, 0.50),
                "p90_pdsi": _quantile(sample, 0.90),
                "drought_fraction_pdsi_le_minus2": float(np.mean(sample[valid] <= -2)) if valid.any() else float("nan"),
                "severe_drought_fraction_pdsi_le_minus3": float(np.mean(sample[valid] <= -3)) if valid.any() else float("nan"),
                "label_state": state,
                "reason_code": "no_imputation" if state == "resolved_historical_climate_risk" else state,
                "training_target_allowed": False,
                "population_target": False,
            }
        )
    return rows, values, years, grid


def _superregion_rows(atlas: Atlas, locations: pl.DataFrame, values: np.ndarray, years: np.ndarray) -> list[dict[str, Any]]:
    groups = locations["super_region"].unique().sort().to_list()
    area = locations["area_km2"].to_numpy().astype(float)
    region = locations["super_region"].to_numpy()
    rows: list[dict[str, Any]] = []
    for group in groups:
        members = np.flatnonzero(region == group)
        total_area = float(area[members].sum())
        valid = np.isfinite(values[:, members])
        valid_area_by_year = np.where(valid, area[members][None, :], 0.0).sum(axis=1)
        coverage = float(valid_area_by_year.sum() / (total_area * len(years))) if total_area and len(years) else 0.0
        flattened = values[:, members].ravel()
        flattened = flattened[np.isfinite(flattened)]
        rows.append(
            {
                "source_id": atlas.source_id,
                "super_region": group,
                "location_count": int(len(members)),
                "mapped_location_count": int(np.any(valid, axis=0).sum()),
                "total_area_km2": total_area,
                "valid_area_fraction": coverage,
                "year_start": int(years.min()) if years.size else None,
                "year_end": int(years.max()) if years.size else None,
                "valid_year_value_count": int(flattened.size),
                "p10_pdsi": _quantile(flattened, 0.10),
                "p50_pdsi": _quantile(flattened, 0.50),
                "p90_pdsi": _quantile(flattened, 0.90),
                "drought_fraction_pdsi_le_minus2": float(np.mean(flattened <= -2)) if flattened.size else float("nan"),
                "severe_drought_fraction_pdsi_le_minus3": float(np.mean(flattened <= -3)) if flattened.size else float("nan"),
                "label_state": "resolved_historical_climate_risk" if flattened.size else "outside_source_domain",
                "training_target_allowed": False,
                "population_target": False,
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    locations = pl.read_parquet(LOCATIONS).select(
        ["location_tag", "super_region", "area_km2", "calibrated_lon", "calibrated_lat"]
    )
    if locations.height != 20_929:
        raise ValueError(f"expected 20,929 EU5 locations, found {locations.height}")
    location_rows: list[dict[str, Any]] = []
    super_rows: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    for atlas in ATLASES:
        _ensure_source(atlas)
        rows, values, years, grid = _location_rows(atlas, locations)
        location_rows.extend(rows)
        super_rows.extend(_superregion_rows(atlas, locations, values, years))
        state_counts: dict[str, int] = {}
        for row in rows:
            state_counts[row["label_state"]] = state_counts.get(row["label_state"], 0) + 1
        source_records.append(
            {
                "source_id": atlas.source_id,
                "url": atlas.url,
                "download_url": atlas.download_url,
                "citation": atlas.citation,
                "sha256": sha256(atlas.path),
                "path": str(atlas.path.relative_to(ROOT)),
                "variable": atlas.variable,
                "season": atlas.season,
                "native_period": list(atlas.period),
                "target_window": [max(1100, atlas.period[0]), min(1500, atlas.period[1])],
                "grid": {k: v for k, v in grid.items() if k != "in_domain"},
                "mapped_location_count": int(grid["in_domain"].sum()),
                "label_state_counts": state_counts,
                "training_target_allowed": False,
                "population_target": False,
                "interpretation": "historical drought/climate proxy; requires a crop-yield bridge before it can set capacity uncertainty",
            }
        )
    location_path = OUT / "drought_atlas_location_risk_wave29.csv"
    super_path = OUT / "drought_atlas_superregion_risk_wave29.csv"
    pl.DataFrame(location_rows).write_csv(location_path)
    pl.DataFrame(super_rows).write_csv(super_path)
    manifest: dict[str, Any] = {
        "schema_version": "population_capacity_historical_drought_atlas_risk_v1",
        "target_year": 1337,
        "historical_window_requested": [1100, 1500],
        "sources": source_records,
        "coverage": {
            "location_count": locations.height,
            "source_count": len(ATLASES),
            "location_rows": len(location_rows),
            "superregion_rows": len(super_rows),
            "super_regions": locations["super_region"].unique().sort().to_list(),
            "mapping_method": "nearest native atlas grid point to calibrated EU5 centroid; no cross-source or regional imputation",
        },
        "semantics": {
            "absolute_1337_yield": False,
            "historical_crop_yield_label": False,
            "population_target": False,
            "physical_uncertainty_input_candidate": True,
            "source_family_independent": True,
            "native_index": "PDSI/scPDSI; negative values indicate dry conditions",
        },
        "acceptance": {
            "all_required_locations_have_a_climate_record": False,
            "global_historical_crop_yield_risk_closed": False,
            "parameter_uncertainty_closed": False,
            "training_unblocked": False,
            "blocking_gaps": [
                "Drought atlases are climate proxies, not absolute crop-yield observations.",
                "North/South America and Asia/Europe source footprints do not cover all EU5 locations.",
                "A crop-specific response bridge is still required before p10/p90 can be interpreted as yield uncertainty.",
            ],
        },
        "outputs": {
            "location_risk": str(location_path.relative_to(ROOT)),
            "superregion_risk": str(super_path.relative_to(ROOT)),
            "location_risk_sha256": sha256(location_path),
            "superregion_risk_sha256": sha256(super_path),
        },
    }
    manifest_path = OUT / "drought_atlas_risk_manifest_wave29.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "location_rows": len(location_rows), "superregion_rows": len(super_rows)}, indent=2))


if __name__ == "__main__":
    main()
