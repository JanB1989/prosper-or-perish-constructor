"""Derived notebook tables and QGIS-compatible simulation rasters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl
import rasterio
from rasterio.transform import from_origin

from prosper_or_perish_constructor.savegame_maps import (
    SavegameMapAssets,
    paint_location_metric_raster,
)


GEOTIFF_NODATA = np.float32(-3.4028235e38)

SIMULATION_METRICS = {
    "Total population": "total_population",
    "Population change": "population_change",
    "Development": "development",
    "Development change": "development_change",
    "Prosperity": "prosperity",
    "Population capacity": "population_capacity",
    "Capacity fill": "capacity_fill",
    "Startup irrigation levels": "irrigation_systems_levels",
}


@dataclass(frozen=True)
class SimulationGeoTiffResult:
    path: Path
    metric: str
    width: int
    height: int
    mapped_locations: int
    mapped_pixels: int
    nodata: float


def prepare_simulation_analysis_state(
    starting_locations: pl.DataFrame,
    current_locations: pl.DataFrame,
) -> pl.DataFrame:
    """Attach comparable start values, deltas, and capacity fill."""

    current = current_locations
    if "population_capacity" not in current.columns:
        if "local_population_capacity" in current.columns:
            current = current.with_columns(
                pl.col("local_population_capacity").alias("population_capacity")
            )
        else:
            raise ValueError(
                "location state has no effective population capacity; initialize it "
                "through Simulation so absolute values and relative modifiers are applied"
            )

    starting = starting_locations.select(
        "location_tag",
        pl.col("development").alias("starting_development"),
        pl.col("total_population").alias("starting_population"),
    ).unique("location_tag")
    return (
        current.join(starting, on="location_tag", how="left")
        .with_columns(
            (pl.col("development") - pl.col("starting_development")).alias(
                "development_change"
            ),
            (pl.col("total_population") - pl.col("starting_population")).alias(
                "population_change"
            ),
            pl.when(pl.col("population_capacity") > 0.0)
            .then(pl.col("total_population") / pl.col("population_capacity"))
            .otherwise(None)
            .alias("capacity_fill"),
        )
    )


def macro_region_statistics(frame: pl.DataFrame, metric: str) -> pl.DataFrame:
    """Return ordinary location-level descriptive statistics by macro-region."""

    required = {"macro_region", metric}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            f"macro-region statistics are missing columns: {', '.join(sorted(missing))}"
        )
    values = frame.select(
        "macro_region",
        pl.when(pl.col(metric).cast(pl.Float64).is_finite())
        .then(pl.col(metric).cast(pl.Float64))
        .otherwise(None)
        .alias("value"),
    ).filter(pl.col("macro_region").is_not_null())
    return (
        values.group_by("macro_region")
        .agg(
            pl.col("value").count().alias("count"),
            pl.col("value").min().alias("min"),
            pl.col("value").max().alias("max"),
            pl.col("value").mean().alias("mean"),
            pl.col("value").median().alias("median"),
            pl.col("value").std(ddof=1).alias("std_dev"),
            pl.col("value").sum().alias("sum"),
        )
        .sort("macro_region")
    )


def write_simulation_metric_geotiff(
    frame: pl.DataFrame,
    *,
    metric: str,
    assets: SavegameMapAssets,
    output_path: Path,
    simulation_years: int,
    start_year: int = 1337,
) -> SimulationGeoTiffResult:
    """Paint one numeric location metric onto the EU5 location raster.

    The TIFF uses exact EU5 location pixels and an explicit game-pixel affine
    transform. It is directly readable and styleable in QGIS, but intentionally
    has no geographic CRS: assigning EPSG:4326 would falsely imply that the
    game's nonlinear map projection is a regular longitude/latitude grid.
    """

    required = {"location_tag", metric}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            f"simulation GeoTIFF is missing columns: {', '.join(sorted(missing))}"
        )
    painted = paint_location_metric_raster(
        assets,
        frame,
        value_column=metric,
        nodata=float(GEOTIFF_NODATA),
    )
    raster = painted.values

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    height, width = raster.shape
    options: dict[str, object] = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "nodata": float(GEOTIFF_NODATA),
        "transform": from_origin(0.0, float(height), 1.0, 1.0),
        "compress": "deflate",
        "predictor": 3,
    }
    if width >= 256 and height >= 256:
        options.update(tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(output_path, "w", **options) as destination:
        destination.write(raster, 1)
        destination.set_band_description(1, metric)
        destination.update_tags(
            coordinate_space="EU5 game-map pixels",
            metric=metric,
            simulation_years=str(int(simulation_years)),
            simulation_start_year=str(int(start_year)),
            simulation_end_year=str(int(start_year + simulation_years)),
            source_locations_png=str(assets.locations_png_path),
        )

    return SimulationGeoTiffResult(
        path=output_path,
        metric=metric,
        width=width,
        height=height,
        mapped_locations=painted.mapped_locations,
        mapped_pixels=painted.mapped_pixels,
        nodata=float(GEOTIFF_NODATA),
    )
