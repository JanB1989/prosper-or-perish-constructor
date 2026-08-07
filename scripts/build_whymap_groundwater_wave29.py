"""Build a cited, conservative groundwater-access feature for 1337 capacity.

WHYMAP is a present-day hydrogeological inventory, not a historical irrigation
or population map.  This script therefore uses it only as a physical aquifer
and recharge-class input, and gates it by a separately vetted pre-1337
technology selector.  It never uses observed irrigated area, HYDE, or starting
population.  Locations without a matching historical technology remain an
explicit ``not_historically_available`` zero; a missing aquifer match for a
vetted system is unresolved and blocks the groundwater contract.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import polars as pl
import requests
from shapely.geometry import Point, shape
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "artifacts/data/population_capacity"
GEOMETRY = ARTIFACT_ROOT / "location_geometry_calibrated.parquet"
SAMPLES = ARTIFACT_ROOT / "location_sample_points.parquet"
REGISTRY = ROOT / "population_capacity_technology_registry.toml"
GROUNDWATER_DIR = ARTIFACT_ROOT / "groundwater_whymap_wave29"
RAW_GEOJSON = GROUNDWATER_DIR / "whymap_groundwater.geojson"
LABELS = GROUNDWATER_DIR / "groundwater_access.parquet"
AUDIT = GROUNDWATER_DIR / "groundwater_access_audit.json"
RECEIPT = GROUNDWATER_DIR / "whymap_source_receipt.json"

QUERY_URL = (
    "https://services.bgr.de/arcgis/rest/services/grundwasser/"
    "whymap_rgwb/MapServer/5/query"
)
SOURCE_URL = "https://services.bgr.de/arcgis/rest/services/grundwasser/whymap_rgwb/MapServer/5"

# Conservative annual recharge envelopes in WHYMAP's own displayed units.
# The lower/upper values are category bounds, not fitted parameters.
RECHARGE_BOUNDS_MM: dict[str, tuple[float, float, float]] = {
    "very high (> 300)": (300.0, 500.0, 800.0),
    "very high - high (> 100)": (100.0, 200.0, 400.0),
    "high (100 - 300)": (100.0, 200.0, 300.0),
    "medium (20 - 100)": (20.0, 60.0, 100.0),
    "medium - very low (< 100)": (2.0, 20.0, 100.0),
    "low (2 - 20)": (2.0, 10.0, 20.0),
    "low - very low (< 20)": (0.2, 5.0, 20.0),
    "very low (< 2)": (0.1, 1.0, 2.0),
}

# A low-input crop water requirement used only to convert the source's
# recharge-depth category into a water-budget ceiling.  It is deliberately
# broad and is reported in the audit; crop-specific demand remains in the
# hydrology allocator.
REFERENCE_CROP_WATER_MM = 800.0
CONVEYANCE_EFFICIENCY = (0.36, 0.48, 0.57)
AQUIFER_ACCESS_FACTOR = {
    "major groundwater basin": 1.0,
    "complex hydrogeological structures": 0.75,
    "local and shallow aquifers": 0.50,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_whymap() -> tuple[list[dict[str, Any]], str]:
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = requests.get(
            QUERY_URL,
            params={
                "where": "1=1",
                "outFields": "OBJECTID,HYGEO2,ICE,CONTINENT,aquif_type,recharge",
                "returnGeometry": "true",
                "outSR": "4326",
                "resultRecordCount": 2000,
                "resultOffset": offset,
                "f": "geojson",
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("features") or []
        features.extend(batch)
        if len(batch) < 2000:
            break
        offset += len(batch)
    if not features:
        raise RuntimeError("WHYMAP returned no groundwater polygons")
    return features, response.url


def _technology_selectors() -> list[dict[str, Any]]:
    registry = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    parameter_modes = {
        str(row.get("parameter_set_id")): set(row.get("water_modes") or ())
        for row in registry.get("technology_parameter_sets", [])
        if isinstance(row, dict)
    }
    selectors: list[dict[str, Any]] = []
    for system in registry.get("systems", []):
        if not isinstance(system, dict) or system.get("review_status") != "vetted_technology":
            continue
        parameter_id = str(system.get("parameter_set_id") or "")
        if not parameter_modes.get(parameter_id, set()).intersection({"groundwater", "spring"}):
            continue
        for include in system.get("include") or []:
            text = str(include)
            if "=" not in text:
                continue
            key, values = text.split("=", 1)
            selectors.append(
                {
                    "system_id": str(system.get("system_id")),
                    "parameter_set_id": parameter_id,
                    "key": key.strip(),
                    "values": {value.strip() for value in values.split("|") if value.strip()},
                }
            )
    if not selectors:
        raise RuntimeError("technology registry contains no vetted groundwater/spring selectors")
    return selectors


def _selector_for_row(row: dict[str, Any], selectors: list[dict[str, Any]]) -> dict[str, Any] | None:
    for selector in selectors:
        if str(row.get(selector["key"]) or "") in selector["values"]:
            return selector
    return None


def _recharge_bounds(value: str | None) -> tuple[float, float, float] | None:
    if value is None:
        return None
    value = str(value).strip().lower()
    if value in RECHARGE_BOUNDS_MM:
        return RECHARGE_BOUNDS_MM[value]
    # The source occasionally varies whitespace or uses a Unicode minus.
    normalized = re.sub(r"\s+", " ", value.replace("−", "-")).strip()
    return RECHARGE_BOUNDS_MM.get(normalized)


def _fraction_envelope(aquifer_type: str | None, recharge: str | None) -> tuple[float, float, float] | None:
    bounds = _recharge_bounds(recharge)
    if bounds is None:
        return None
    factor = AQUIFER_ACCESS_FACTOR.get(str(aquifer_type or ""), 0.0)
    if factor <= 0.0:
        return None
    values = [
        recharge_mm * efficiency * factor / REFERENCE_CROP_WATER_MM
        for recharge_mm, efficiency in zip(bounds, CONVEYANCE_EFFICIENCY, strict=True)
    ]
    # This is a physical water-budget ceiling, not an irrigated-area target.
    return tuple(max(0.0, min(0.25, value)) for value in values)  # type: ignore[return-value]


def _map_samples(features: list[dict[str, Any]], selectors: list[dict[str, Any]]) -> pl.DataFrame:
    geometry = pl.read_parquet(GEOMETRY)
    samples = pl.read_parquet(SAMPLES)
    location_rows = {
        row["location_tag"]: row
        for row in geometry.select(
            "location_tag", "area", "macro_region", "region", "province", "super_region"
        ).iter_rows(named=True)
    }
    polygons = [shape(feature["geometry"]) for feature in features if feature.get("geometry")]
    properties = [feature.get("properties") or {} for feature in features if feature.get("geometry")]
    tree = STRtree(polygons)
    sample_rows: list[dict[str, Any]] = []
    for row in samples.select("location_tag", "sample_index", "calibrated_lon", "calibrated_lat", "sample_weight").iter_rows(named=True):
        location = location_rows[str(row["location_tag"])]
        selector = _selector_for_row(location, selectors)
        prop: dict[str, Any] | None = None
        nearest_fallback = False
        if selector is not None:
            point = Point(float(row["calibrated_lon"]), float(row["calibrated_lat"]))
            # STRtree predicates are evaluated with the query geometry as the
            # left operand.  ``covers`` would therefore test point-covers-
            # polygon, which is the inverse of what we need.  Query the
            # bounding candidates and apply the polygon predicate explicitly.
            matches = tree.query(point)
            for match in matches:
                polygon = polygons[int(match)]
                if polygon.covers(point) or polygon.intersects(point):
                    prop = properties[int(match)]
                    break
            if prop is None:
                # A handful of EU5 footprint samples lie exactly on a WHYMAP
                # polygon seam.  A nearest polygon within 0.5 degrees is an
                # explicit spatial physical fallback, not an imputed value;
                # farther samples remain unresolved.
                nearest = int(tree.nearest(point))
                nearest_distance = polygons[nearest].distance(point)
                if nearest_distance <= 0.5:
                    prop = properties[nearest]
                    nearest_fallback = True
        fractions = _fraction_envelope(
            None if prop is None else prop.get("aquif_type"),
            None if prop is None else prop.get("recharge"),
        )
        if selector is None:
            state = "not_historically_available"
            reason = "no_vetted_pre1337_groundwater_or_spring_system_for_location"
        elif prop is None:
            state = "missing"
            reason = "vetted_groundwater_system_has_no_whymap_aquifer_match"
        elif fractions is None:
            state = "suspect_zero"
            reason = "whymap_recharge_or_aquifer_semantics_unresolved"
        else:
            state = "physical_fallback"
            reason = (
                "whymap_nearest_polygon_plus_vetted_pre1337_technology"
                if nearest_fallback
                else "whymap_aquifer_recharge_class_plus_vetted_pre1337_technology"
            )
        sample_rows.append(
            {
                "location_tag": row["location_tag"],
                "sample_index": int(row["sample_index"]),
                "sample_weight": float(row["sample_weight"]),
                "groundwater_fraction_p10": None if fractions is None else fractions[0],
                "groundwater_fraction_p50": None if fractions is None else fractions[1],
                "groundwater_fraction_p90": None if fractions is None else fractions[2],
                "groundwater_label_state": state,
                "groundwater_reason_code": reason,
                "groundwater_technology_id": None if selector is None else selector["system_id"],
                "groundwater_parameter_set_id": None if selector is None else selector["parameter_set_id"],
                "groundwater_aquifer_type": None if prop is None else prop.get("aquif_type"),
                "groundwater_recharge_class": None if prop is None else prop.get("recharge"),
            }
        )
    # Early rows are often non-eligible locations with null technology fields;
    # scan the complete list so a later vetted selector does not force a null
    # column to the wrong inferred dtype.
    samples_frame = pl.DataFrame(sample_rows, infer_schema_length=None)
    # Weighted quantiles are unnecessary for this conservative envelope: the
    # footprint's feasible fraction is the weighted mean of physical source
    # ceilings, with monotone quantile projection after aggregation.
    output = (
        samples_frame.with_columns(pl.col("sample_weight").clip(0.0, 1.0).alias("_weight"))
        .group_by("location_tag")
        .agg(
            pl.col("sample_weight").sum().alias("sample_weight_sum"),
            pl.col("groundwater_fraction_p10").fill_null(0.0).mul(pl.col("_weight")).sum().alias("groundwater_fraction_p10"),
            pl.col("groundwater_fraction_p50").fill_null(0.0).mul(pl.col("_weight")).sum().alias("groundwater_fraction_p50"),
            pl.col("groundwater_fraction_p90").fill_null(0.0).mul(pl.col("_weight")).sum().alias("groundwater_fraction_p90"),
            pl.col("groundwater_label_state").unique().sort().str.join("|").alias("groundwater_label_state"),
            pl.col("groundwater_reason_code").unique().sort().str.join("|").alias("groundwater_reason_code"),
            pl.col("groundwater_technology_id").drop_nulls().unique().sort().str.join("|").alias("groundwater_technology_id"),
            pl.col("groundwater_parameter_set_id").drop_nulls().unique().sort().str.join("|").alias("groundwater_parameter_set_id"),
            pl.col("groundwater_aquifer_type").drop_nulls().unique().sort().str.join("|").alias("groundwater_aquifer_type"),
            pl.col("groundwater_recharge_class").drop_nulls().unique().sort().str.join("|").alias("groundwater_recharge_class"),
        )
        .with_columns(
            pl.col("groundwater_fraction_p10").clip(0.0, 1.0),
            pl.col("groundwater_fraction_p50").clip(0.0, 1.0),
            pl.col("groundwater_fraction_p90").clip(0.0, 1.0),
        )
    )
    expected = set(geometry["location_tag"].to_list())
    actual = set(output["location_tag"].to_list())
    if expected != actual:
        raise RuntimeError(f"groundwater footprint aggregation changed location universe: missing={len(expected-actual)} extra={len(actual-expected)}")
    return output


def _merge_irrigation(groundwater: pl.DataFrame) -> Path:
    surface_path = ARTIFACT_ROOT / "irrigation_feasibility.parquet"
    output_path = GROUNDWATER_DIR / "irrigation_feasibility_with_groundwater.parquet"
    surface = pl.read_parquet(surface_path)
    required = {"location_tag", "irrigable_fraction_p10", "irrigable_fraction_p50", "irrigable_fraction_p90"}
    if required.difference(surface.columns):
        raise RuntimeError("surface irrigation artifact is missing required fraction columns")
    merged = surface.join(
        groundwater.select(
            "location_tag", "groundwater_fraction_p10", "groundwater_fraction_p50", "groundwater_fraction_p90", "groundwater_label_state", "groundwater_reason_code"
        ),
        on="location_tag",
        how="left",
        validate="1:1",
    )
    merged = merged.with_columns(
        pl.max_horizontal("irrigable_fraction_p10", "groundwater_fraction_p10").alias("irrigable_fraction_p10"),
        pl.max_horizontal("irrigable_fraction_p50", "groundwater_fraction_p50").alias("irrigable_fraction_p50"),
        pl.max_horizontal("irrigable_fraction_p90", "groundwater_fraction_p90").alias("irrigable_fraction_p90"),
    ).with_columns(
        pl.max_horizontal("irrigable_fraction_p10", "irrigable_fraction_p50", "irrigable_fraction_p90").alias("_max"),
    ).drop("_max")
    source_hash = hashlib.sha256(
        ("surface=" + _sha256(surface_path) + ";whymap=" + _sha256(RAW_GEOJSON) + ";registry=" + _sha256(REGISTRY)).encode("ascii")
    ).hexdigest()
    merged = merged.with_columns(
        pl.lit(source_hash).alias("irrigation_source_hash"),
        pl.when(pl.col("groundwater_label_state").str.contains("physical_fallback"))
        .then(pl.lit("surface_or_vetted_groundwater_physical_fallback"))
        .otherwise(pl.col("reason_code").fill_null("hydrology_cell_crop_max_area"))
        .alias("reason_code"),
    ).drop(
        "groundwater_fraction_p10", "groundwater_fraction_p50", "groundwater_fraction_p90", "groundwater_label_state", "groundwater_reason_code"
    )
    merged.write_parquet(output_path)
    return output_path


def main() -> None:
    GROUNDWATER_DIR.mkdir(parents=True, exist_ok=True)
    features, request_url = _download_whymap()
    raw = {"type": "FeatureCollection", "features": features}
    RAW_GEOJSON.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    selectors = _technology_selectors()
    labels = _map_samples(features, selectors)
    labels = labels.with_columns(
        pl.lit(_sha256(RAW_GEOJSON)).alias("groundwater_source_hash"),
        pl.lit(SOURCE_URL).alias("groundwater_source_id"),
        pl.lit("whymap_groundwater_wave29").alias("groundwater_label_version"),
    )
    labels.write_parquet(LABELS)
    merged_path = _merge_irrigation(labels)
    state_counts = {
        str(row["groundwater_label_state"]): int(row["locations"])
        for row in labels.group_by("groundwater_label_state").agg(pl.len().alias("locations")).iter_rows(named=True)
    }
    missing = labels.filter(pl.col("groundwater_label_state").str.contains("missing|suspect_zero")).height
    audit = {
        "schema_version": "groundwater_access_audit_wave29_v1",
        "source_url": SOURCE_URL,
        "query_url": request_url,
        "raw_geojson_sha256": _sha256(RAW_GEOJSON),
        "labels_sha256": _sha256(LABELS),
        "merged_irrigation_sha256": _sha256(merged_path),
        "technology_registry_sha256": _sha256(REGISTRY),
        "whymap_feature_count": len(features),
        "location_count": labels.height,
        "state_counts": state_counts,
        "unresolved_required_locations": missing,
        "source_semantics": "hydrogeological aquifer/recharge class; not modern irrigated area, population, or historical discharge",
        "groundwater_contract_closed": missing == 0 and labels.height == pl.read_parquet(GEOMETRY, columns=["location_tag"]).height,
        "merged_surface_groundwater_policy": "location fraction is max(surface feasible fraction, groundwater water-budget ceiling); no additive double count",
        "reference_crop_water_mm": REFERENCE_CROP_WATER_MM,
        "conveyance_efficiency_envelope": CONVEYANCE_EFFICIENCY,
    }
    RECEIPT.write_text(
        json.dumps({"source_url": SOURCE_URL, "query_url": request_url, "feature_count": len(features), "sha256": audit["raw_geojson_sha256"]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
