"""Build a modern, country-level FAOSTAT yield-risk validation layer.

FAOSTAT is used here only for relative interannual-risk diagnostics.  It is
not a 1337 yield source, a historical cropland source, a population target, or
an imputation source.  Country statistics are attached to EU5 locations by a
deterministic Natural Earth centroid crosswalk and all coverage gaps remain
explicit.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import zipfile

import numpy as np
import polars as pl
from pyogrio.raw import read as ogr_read
from shapely import from_wkb, points
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/data/population_capacity/physical_validation/interannual_sources/wave28"
FAOSTAT_ZIP = OUT / "faostat_production_crops_livestock_normalized.zip"
NE_ZIP = OUT / "ne_110m_admin_0_countries.zip"
GEOMETRY = ROOT / "artifacts/data/population_capacity/location_geometry_calibrated.parquet"

ITEM_FAMILY = {
    "Wheat": "wheat",
    "Rice": "rice",
    "Maize (corn)": "maize",
    "Barley": "barley",
    "Rye": "rye",
    "Oats": "oats",
    "Sorghum": "sorghum",
    "Millet": "millet",
    "Potatoes": "potato",
    "Cassava, fresh": "cassava",
    "Yams": "yam",
    "Sweet potatoes": "sweet_potato",
    "Bananas": "banana",
    "Plantains and cooking bananas": "plantain",
    "Beans, dry": "beans",
    "Chick peas, dry": "chickpeas",
    "Lentils, dry": "lentils",
    "Groundnuts, excluding shelled": "groundnuts",
}
MIN_VALID_YEARS = 10


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise_m49(expr: pl.Expr) -> pl.Expr:
    return expr.cast(pl.String).str.replace_all("'", "").str.zfill(3)


def build_country_polygons() -> pl.DataFrame:
    meta, _, geometries, fields = ogr_read(
        NE_ZIP,
        columns=["ISO_A3", "ISO_N3", "NAME", "CONTINENT"],
        force_2d=True,
    )
    names = list(meta["fields"])
    values = {name: fields[index] for index, name in enumerate(names)}
    polygons = from_wkb(geometries)
    return pl.DataFrame(
        {
            "iso_a3": values["ISO_A3"].astype(str),
            "iso_n3": values["ISO_N3"].astype(str),
            "country_name": values["NAME"].astype(str),
            "continent": values["CONTINENT"].astype(str),
            "geometry": polygons,
        }
    )


def build_location_crosswalk() -> pl.DataFrame:
    locations = pl.read_parquet(GEOMETRY).select(
        [
            "location_tag",
            "super_region",
            "calibrated_lon",
            "calibrated_lat",
            "area_jacobian_km2",
        ]
    )
    polygons = build_country_polygons()
    tree = STRtree(polygons["geometry"].to_list())
    lon = locations["calibrated_lon"].to_numpy()
    lat = locations["calibrated_lat"].to_numpy()
    valid = np.isfinite(lon) & np.isfinite(lat)
    country_index = np.full(len(locations), -1, dtype=np.int32)
    if valid.any():
        sample_indices = np.flatnonzero(valid)
        matches = tree.query(points(lon[valid], lat[valid]), predicate="within")
        for sample_index, polygon_index in zip(matches[0], matches[1], strict=False):
            if country_index[sample_indices[sample_index]] < 0:
                country_index[sample_indices[sample_index]] = int(polygon_index)
    country_iso_n3 = np.array(polygons["iso_n3"].to_list(), dtype=object)
    country_name = np.array(polygons["country_name"].to_list(), dtype=object)
    country_continent = np.array(polygons["continent"].to_list(), dtype=object)
    out = locations.with_columns(
        pl.Series(
            "iso_n3",
            np.where(country_index >= 0, country_iso_n3[np.maximum(country_index, 0)], None),
        ),
        pl.Series(
            "country_name",
            np.where(country_index >= 0, country_name[np.maximum(country_index, 0)], None),
        ),
        pl.Series(
            "country_continent",
            np.where(country_index >= 0, country_continent[np.maximum(country_index, 0)], None),
        ),
    )
    return out.with_columns(
        pl.when(pl.col("iso_n3").is_not_null())
        .then(pl.col("iso_n3").str.replace_all("-99", ""))
        .otherwise(None)
        .alias("iso_n3")
    )


def load_faostat_yields() -> pl.DataFrame:
    items = list(ITEM_FAMILY)
    with zipfile.ZipFile(FAOSTAT_ZIP) as archive:
        with archive.open("Production_Crops_Livestock_E_All_Data_(Normalized).csv") as source:
            frame = pl.read_csv(
                source,
                columns=[
                    "Area Code",
                    "Area Code (M49)",
                    "Area",
                    "Item",
                    "Element",
                    "Year",
                    "Unit",
                    "Value",
                    "Flag",
                ],
                schema_overrides={"Value": pl.Float64},
                infer_schema_length=10_000,
            )
    return (
        frame.filter(
            (pl.col("Element") == "Yield")
            & (pl.col("Unit") == "kg/ha")
            & pl.col("Item").is_in(items)
            & (pl.col("Value") >= 0.0)
        )
        .with_columns(
            _normalise_m49(pl.col("Area Code (M49)")).alias("iso_n3"),
            pl.col("Item").replace(ITEM_FAMILY).alias("crop_family"),
            pl.col("Year").cast(pl.Int32),
            pl.col("Value").cast(pl.Float64),
            pl.col("Flag").fill_null("").alias("faostat_flag"),
        )
        .select(
            [
                "iso_n3",
                "Area",
                "Item",
                "crop_family",
                "Year",
                "Value",
                "faostat_flag",
            ]
        )
    )


def build_country_risk(yields: pl.DataFrame) -> pl.DataFrame:
    positive = pl.col("Value") > 0.0
    return (
        yields.group_by(["iso_n3", "Area", "Item", "crop_family"])
        .agg(
            pl.len().alias("reported_year_count"),
            pl.col("Year").filter(positive).min().alias("year_start"),
            pl.col("Year").filter(positive).max().alias("year_end"),
            pl.col("Value").filter(positive).count().alias("valid_positive_year_count"),
            pl.col("Value").filter(positive).mean().alias("yield_mean_kg_ha"),
            pl.col("Value").filter(positive).std().alias("yield_std_kg_ha"),
            pl.col("Value").filter(positive).quantile(0.10).alias("yield_p10_kg_ha"),
            pl.col("Value").filter(positive).quantile(0.50).alias("yield_p50_kg_ha"),
            pl.col("Value").filter(positive).quantile(0.90).alias("yield_p90_kg_ha"),
            pl.col("faostat_flag")
            .filter(positive)
            .is_in(["E", "I", "X"])
            .mean()
            .alias("estimated_or_imputed_fraction"),
        )
        .with_columns(
            pl.when(pl.col("yield_mean_kg_ha") > 0)
            .then(pl.col("yield_std_kg_ha") / pl.col("yield_mean_kg_ha"))
            .otherwise(None)
            .alias("coefficient_of_variation"),
            pl.when(pl.col("yield_p50_kg_ha") > 0)
            .then(pl.col("yield_p10_kg_ha") / pl.col("yield_p50_kg_ha"))
            .otherwise(None)
            .alias("lower_tail_ratio_p10_p50"),
        )
        .with_columns(
            pl.when(pl.col("valid_positive_year_count") >= MIN_VALID_YEARS)
            .then(pl.lit("resolved_modern_relative_risk"))
            .otherwise(pl.lit("insufficient_annual_coverage"))
            .alias("label_state")
        )
    )


def build_superregion_report(
    locations: pl.DataFrame, country_risk: pl.DataFrame
) -> pl.DataFrame:
    joined = locations.join(country_risk, on="iso_n3", how="left")
    resolved = joined.filter(pl.col("label_state") == "resolved_modern_relative_risk")
    return (
        resolved.group_by(["super_region", "Item", "crop_family"])
        .agg(
            pl.len().alias("mapped_location_count"),
            pl.col("area_jacobian_km2").sum().alias("mapped_area_km2"),
            pl.col("yield_p10_kg_ha").mean().alias("area_location_mean_p10_kg_ha"),
            pl.col("yield_p50_kg_ha").mean().alias("area_location_mean_p50_kg_ha"),
            pl.col("yield_p90_kg_ha").mean().alias("area_location_mean_p90_kg_ha"),
            pl.col("coefficient_of_variation").mean().alias("mean_country_cv"),
            pl.col("lower_tail_ratio_p10_p50").mean().alias("mean_country_lower_tail_ratio"),
            pl.col("estimated_or_imputed_fraction").mean().alias("mean_estimated_or_imputed_fraction"),
        )
        .sort(["super_region", "Item"])
    )


def main() -> None:
    locations = build_location_crosswalk()
    yields = load_faostat_yields()
    country_risk = build_country_risk(yields)
    superregion = build_superregion_report(locations, country_risk)
    item_frame = pl.DataFrame(
        {
            "Item": list(ITEM_FAMILY),
            "crop_family": list(ITEM_FAMILY.values()),
        }
    )
    location_risk = (
        locations.join(item_frame, how="cross")
        .join(country_risk, on=["iso_n3", "Item", "crop_family"], how="left")
        .with_columns(
            pl.when(pl.col("iso_n3").is_null())
            .then(pl.lit("unmapped_country"))
            .when(pl.col("label_state").is_null())
            .then(pl.lit("missing_country_item_series"))
            .otherwise(pl.col("label_state"))
            .alias("label_state")
        )
    )

    crosswalk_path = OUT / "faostat_location_country_crosswalk_wave28.csv"
    country_path = OUT / "faostat_country_crop_risk_wave28.csv"
    superregion_path = OUT / "faostat_superregion_crop_risk_wave28.csv"
    location_path = OUT / "faostat_location_crop_risk_wave28.csv"
    coverage_path = OUT / "faostat_location_crop_risk_coverage_wave28.csv"
    locations.write_csv(crosswalk_path)
    country_risk.write_csv(country_path)
    superregion.write_csv(superregion_path)
    location_risk.write_csv(location_path)

    mapped = locations.filter(pl.col("iso_n3").is_not_null())
    resolved = location_risk.filter(pl.col("label_state") == "resolved_modern_relative_risk")
    resolved_location_count = resolved.select("location_tag").n_unique()
    coverage_by_item = (
        location_risk.group_by(["Item", "crop_family"])
        .agg(
            pl.len().alias("location_item_rows"),
            pl.col("location_tag").n_unique().alias("location_count"),
            pl.col("location_tag")
            .filter(pl.col("label_state") == "resolved_modern_relative_risk")
            .n_unique()
            .alias("resolved_location_count"),
            pl.col("location_tag")
            .filter(pl.col("label_state") == "unmapped_country")
            .n_unique()
            .alias("unmapped_country_location_count"),
            pl.col("location_tag")
            .filter(pl.col("label_state") == "missing_country_item_series")
            .n_unique()
            .alias("missing_country_item_location_count"),
            pl.col("location_tag")
            .filter(pl.col("label_state") == "insufficient_annual_coverage")
            .n_unique()
            .alias("insufficient_annual_coverage_location_count"),
        )
        .with_columns(
            (pl.col("resolved_location_count") / pl.col("location_count")).alias(
                "resolved_location_fraction"
            )
        )
        .sort("Item")
    )
    coverage_by_item.write_csv(coverage_path)
    manifest = {
        "schema_version": "population_capacity_faostat_interannual_risk_mapping_v1",
        "source": {
            "provider": "FAO FAOSTAT",
            "domain": "Production: Crops and livestock products",
            "url": "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip",
            "bulk_sha256": _sha256(FAOSTAT_ZIP),
            "natural_earth_url": "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip",
            "natural_earth_sha256": _sha256(NE_ZIP),
            "license_note": "FAOSTAT terms apply; Natural Earth is public domain.",
        },
        "coverage": {
            "location_count": locations.height,
            "country_mapped_location_count": mapped.height,
            "country_mapped_fraction": mapped.height / locations.height if locations.height else 0.0,
            "resolved_risk_location_count": resolved_location_count,
            "resolved_risk_fraction": resolved_location_count / locations.height if locations.height else 0.0,
            "country_risk_rows": country_risk.height,
            "superregion_rows": superregion.height,
            "staple_items": sorted(ITEM_FAMILY),
            "modern_year_window": [int(yields["Year"].min()), int(yields["Year"].max())],
            "minimum_valid_years": MIN_VALID_YEARS,
        },
        "mapping": {
            "method": "EU5 calibrated centroid within Natural Earth 110m country polygon; country statistics are joined by ISO numeric M49 code.",
            "unmapped_policy": "Locations with no finite centroid or no containing country remain null and are never filled.",
            "country_boundary_limit": "110m boundaries are a coarse modern validation crosswalk, not historical 1337 borders.",
        },
        "semantics": {
            "yield_unit": "kg/ha",
            "risk_statistics": "modern country-level annual yield p10/p50/p90, coefficient of variation, and p10/p50 lower-tail ratio",
            "flags": "Estimated, imputed, or mixed-series flags are reported as estimated_or_imputed_fraction; no rows are silently discarded except non-yield elements and non-positive values for positive-yield risk statistics.",
            "historical_1337_target": False,
            "population_target": False,
            "starting_population_or_trade_used": False,
        },
        "outputs": {
            "crosswalk": str(crosswalk_path.relative_to(ROOT)),
            "crosswalk_sha256": _sha256(crosswalk_path),
            "country_risk": str(country_path.relative_to(ROOT)),
            "country_risk_sha256": _sha256(country_path),
            "superregion_risk": str(superregion_path.relative_to(ROOT)),
            "superregion_risk_sha256": _sha256(superregion_path),
            "location_risk": str(location_path.relative_to(ROOT)),
            "location_risk_sha256": _sha256(location_path),
            "coverage_by_item": str(coverage_path.relative_to(ROOT)),
            "coverage_by_item_sha256": _sha256(coverage_path),
        },
        "coverage_by_item": coverage_by_item.to_dicts(),
        "acceptance": {
            "modern_relative_risk_validation_available": True,
            "global_location_risk_closed": bool(resolved.height == locations.height),
            "historical_1100_1500_risk_target_available": False,
            "mechanistic_p10_p90_gate_unblocked": False,
            "training_target_allowed": False,
            "validation_allowed": True,
            "blocking_gaps": [
                "FAOSTAT begins in the modern statistical era and cannot calibrate 1337 absolute yields or historical technology.",
                "Country centroids and modern country boundaries do not provide historical 1337 local-food boundaries.",
                "FAOSTAT annual yields mix reporting, estimation, and technology changes; use flag fractions and crop-specific trends as diagnostics only.",
                "A global, machine-readable annual 1100-1500 harvest-yield panel with mapped local boundaries remains unavailable.",
            ],
        },
    }
    manifest_path = OUT / "faostat_risk_mapping_manifest_wave28.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
