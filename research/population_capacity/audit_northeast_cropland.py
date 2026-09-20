"""Compare an independently published land reconstruction on its own footprint.

uv run --with pyshp --with openpyxl python research/population_capacity/audit_northeast_cropland.py

Jia et al.'s medieval land estimates use population and must not validate a
demographic fit. Aggregate their source polygons; never distribute their
province-wide percentages as measured local cropland.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import openpyxl
import polars as pl
from pyproj import CRS, Transformer
import shapefile
from shapely import covers, points
from shapely.geometry import shape
from shapely.ops import transform

from prosper_or_perish_constructor.simulation.cache import fingerprint
from prosper_or_perish_constructor.simulation.physical_support import restrict_to_accessible_land


ROOT = Path(__file__).resolve().parents[2]


def run() -> dict:
    source = ROOT / "artifacts/data/population_capacity/repair_sources/jia_2024_northeast_v2"
    metadata = json.loads((source / "metadata.json").read_text())
    by_url = {record["download_url"]: record for record in metadata["files"]}
    acquisition = json.loads((ROOT / "research/population_capacity/repair_source_manifest.json").read_text())
    for record in acquisition["sources"]:
        if record["url"] in by_url and record["id"].startswith("jia_2024_northeast_v2/"):
            downloaded = ROOT / record["path"]
            expected = by_url[record["url"]]
            if (downloaded.stat().st_size != expected["size"] or
                    hashlib.md5(downloaded.read_bytes()).hexdigest() != expected["computed_md5"]):
                raise ValueError(f"source checksum mismatch: {downloaded}")

    workbook = openpyxl.load_workbook(source / "fractions.xlsx", read_only=True, data_only=True)
    observations = []
    for year in (1000, 1100, 1200, 1300, 1400, 1500, 1600):
        records = list(workbook[str(year)].values)
        if records[0][4] != f"{year}_Fraction (%)":
            raise ValueError("unrecognized source units")
        for identifier, chinese_name, name, area, percent in records[1:]:
            if not 0 <= percent <= 100 or area <= 0:
                raise ValueError("invalid source area/fraction")
            observations.append({"source_year": year, "source_name": name,
                "source_name_chinese": chinese_name, "source_id": identifier,
                "source_area_km2": area, "source_cropland_percent": percent,
                "source_cropland_km2": area * percent / 100})
    workbook.close()

    # Compare 1300 with the current LUH2 1300 land evidence. Later observations
    # remain dated progression context and do not enter this starting map.
    reader = shapefile.Reader(str(source / "1300.shp"))
    transform_crs = Transformer.from_crs(CRS.from_wkt((source / "1300.prj").read_text()),
                                         "EPSG:4326", always_xy=True)
    polygons = [(record.as_dict(), transform(transform_crs.transform, shape(geometry.__geo_interface__)))
                for record, geometry in zip(reader.records(), reader.shapes(), strict=True)]
    sample_path = ROOT / "artifacts/data/population_capacity/geometry_land_contract_candidate_v1/full/game_authoritative_physical_samples.parquet"
    prepared_path = ROOT / "artifacts/data/population_simulation/prepared_sources.parquet"
    prepared = pl.read_parquet(prepared_path)
    current = restrict_to_accessible_land(prepared, open_land_access_fraction=.02)
    minx, miny, maxx, maxy = reader.bbox
    samples = pl.read_parquet(sample_path).filter(
        pl.col("physical_sample_lon").is_between(minx - .01, maxx + .01)
        & pl.col("physical_sample_lat").is_between(miny - .01, maxy + .01))
    samples = samples.join(current.select("location_tag", "area_km2", "cropland_fraction_1300",
        "inherited_cultivated_land_km2", "baseline_open_cultivation_km2", "crop_fallow_block_km2"),
        on="location_tag", how="left", validate="m:1")
    if samples["area_km2"].null_count():
        raise ValueError("missing canonical location evidence")
    if not np.allclose(samples["area_km2"], samples["exact_location_area_km2"], rtol=1e-9):
        raise ValueError("source and canonical physical geometry disagree")
    coordinates = points(samples["physical_sample_lon"].to_numpy(), samples["physical_sample_lat"].to_numpy())
    matched = np.zeros(samples.height, dtype=np.int32)
    comparisons, mappings = [], []
    for attributes, polygon in polygons:
        mask = covers(polygon, coordinates)
        matched += mask
        subset = samples.filter(pl.Series(mask))
        record = next(row.copy() for row in observations
                      if row["source_year"] == 1300 and row["source_name"] == attributes["Name_Eng"])
        if not np.isclose(record["source_area_km2"], attributes["Area"]):
            raise ValueError("source workbook and geometry identifiers disagree")
        weight = subset["represented_area_km2"]
        record["matched_canonical_land_km2"] = weight.sum()
        record["mapped_land_to_source_area_ratio"] = weight.sum() / record["source_area_km2"]
        record["luh2_cropland_km2"] = (weight * subset["cropland_fraction_1300"]).sum()
        for name in ("inherited_cultivated_land_km2", "baseline_open_cultivation_km2", "crop_fallow_block_km2"):
            record["candidate_" + name] = (weight * subset[name] / subset["area_km2"]).sum()
        comparisons.append(record)
        mappings.append(subset.group_by("location_tag").agg(pl.col("represented_area_km2").sum())
                        .with_columns(pl.lit(record["source_name"]).alias("source_name")))
    if (matched > 1).any():
        raise ValueError("historical provincial polygons overlap at a canonical sample")

    output = source / "audit"
    output.mkdir(exist_ok=True)
    pl.DataFrame(observations).write_csv(output / "dated_observations.csv")
    pl.DataFrame(comparisons).write_csv(output / "starting_land_comparison.csv")
    pl.concat(mappings).write_csv(output / "source_to_location_overlap.csv")
    manifest = {"accepted": False, "source_doi": metadata["doi"], "license": metadata["license"],
        "comparison_years": {"source": 1300, "luh2": 1300, "game_scenario": 1337},
        "source_population_dependent": True, "independent_demographic_validation": False,
        "baseline_open_land_access_fraction": .02,
        "units": "source percentages divided by 100; hectares are not present in this workbook",
        "spatial_method": "CGCS2000 polygons transformed to WGS84, intersected with canonical physical sample points and their additive represented land areas",
        "limitations": ["Medieval cropland is reconstructed partly from household, garrison and population records",
            "Provincial percentages are not local field observations and are never assigned to location capacity",
            "Author polygons include water; canonical samples represent land only; mapped area ratio is reported",
            "Source cropland excludes unrecorded temporary use and fallow, while model crop/fallow block can include both",
            "Canonical land use is uniform within each location for this overlap audit",
            "1300 is close to, but not identical with, the 1337 starting scenario",
            "Historical warfare and abandonment are not represented by the peaceful game experiments"],
        "fingerprint": fingerprint([Path(__file__), source / "fractions.xlsx", source / "1300.shp",
            source / "1300.dbf", source / "1300.prj", sample_path, prepared_path,
            ROOT / "src/prosper_or_perish_constructor/simulation/physical_support.py"], {"open_access": .02}),
        "comparison": comparisons}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"output": str(output), "source_years": 7, "comparison": comparisons, "accepted": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
