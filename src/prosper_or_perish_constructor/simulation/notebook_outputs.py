"""Derived notebook tables and QGIS-compatible simulation rasters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
    "Maximum population capacity": "theoretical_max_population_capacity",
    "Capacity fill": "capacity_fill",
    "Province food surplus / deficit": "province_food_storage_change",
    "Startup irrigation levels": "irrigation_systems_levels",
}


THEORETICAL_MAX_DEVELOPMENT = 100.0


def attach_theoretical_max_population_capacity(
    frame: pl.DataFrame,
    *,
    capacity_per_level: Mapping[str, float],
    development_relative: float,
    global_relative: float,
) -> pl.DataFrame:
    """Attach the full-buildout population-capacity ceiling for each location.

    The location gates and development-100 maximum levels mirror the resolved
    game definitions. Farming Villages use the simulation profile's accepted
    five-level calibration ceiling because their live game maximum is
    recursively determined by the separate farming-capacity system.
    """

    required = {
        "deployed_static_population_capacity",
        "climate",
        "has_river",
        "is_adjacent_to_lake",
        "is_coastal",
        "raw_material",
        "soil_quality",
        "topography",
        "vegetation",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            "theoretical maximum capacity is missing columns: "
            + ", ".join(sorted(missing))
        )

    positive_supported = {
        "irrigation_systems",
        "bund",
        "terraces",
        "polders",
        "land_clearance",
        "field_drainage",
        "irrigation_reservoirs",
        "qanats",
        "irrigated_rice_paddies",
        "farming_village",
    }
    positive_configured = {
        building
        for building, value in capacity_per_level.items()
        if float(value) > 0.0
    }
    unsupported = positive_configured - positive_supported
    if unsupported:
        raise ValueError(
            "theoretical maximum has no location rule for capacity buildings: "
            + ", ".join(sorted(unsupported))
        )
    missing_effects = positive_supported - set(capacity_per_level)
    if missing_effects:
        raise ValueError(
            "theoretical maximum is missing capacity effects for buildings: "
            + ", ".join(sorted(missing_effects))
        )

    has_river = pl.col("has_river").fill_null(False)
    beside_lake = pl.col("is_adjacent_to_lake").fill_null(False)
    coastal = pl.col("is_coastal").fill_null(False)
    topography = pl.col("topography").cast(pl.String).fill_null("")
    vegetation = pl.col("vegetation").cast(pl.String).fill_null("")
    climate = pl.col("climate").cast(pl.String).fill_null("")
    soil = pl.col("soil_quality").cast(pl.String).fill_null("")
    raw_material = pl.col("raw_material").cast(pl.String).fill_null("")
    usable_soil = ~soil.is_in(["soil_barren", "soil_permafrost"])

    allowed = {
        "irrigation_systems": has_river | beside_lake,
        "bund": has_river | beside_lake,
        "terraces": topography.is_in(["mountains", "plateau", "hills"]),
        "polders": (coastal | beside_lake) & (topography == "wetlands"),
        "land_clearance": (
            vegetation.is_in(["woods", "forest", "jungle"])
            & ~topography.is_in(["mountain_wasteland", "atoll"])
            & usable_soil
        ),
        "field_drainage": (
            (topography == "wetlands")
            & ~coastal
            & ~beside_lake
            & usable_soil
        ),
        "irrigation_reservoirs": (
            ~has_river
            & ~beside_lake
            & climate.is_in(["tropical", "subtropical", "arid", "cold_arid"])
            & topography.is_in(["flatland", "hills", "plateau"])
            & usable_soil
        ),
        "qanats": (
            ~has_river
            & ~beside_lake
            & ~topography.is_in(["wetlands", "atoll", "mountain_wasteland"])
            & climate.is_in(["arid", "cold_arid"])
            & vegetation.is_in(["desert", "sparse"])
            & usable_soil
        ),
        "irrigated_rice_paddies": (
            (raw_material == "rice")
            & topography.is_in(["flatland", "hills", "plateau", "wetlands"])
            & usable_soil
        ),
        "farming_village": (
            raw_material.is_in(
                [
                    "livestock",
                    "wheat",
                    "legumes",
                    "fruit",
                    "millet",
                    "wool",
                    "rice",
                    "beeswax",
                    "maize",
                    "olives",
                    "potato",
                ]
            )
            | (vegetation == "farmland")
        ),
    }
    maximum_levels = {
        # Resolved at development 100 with no owner-specific cap modifier.
        "irrigation_systems": pl.lit(22.0) + pl.when(has_river).then(2.0).otherwise(0.0),
        "bund": pl.lit(12.0),
        "polders": pl.lit(10.0),
        "terraces": pl.lit(1.0),
        # Constructor-owned infrastructure has a fixed five-level ceiling.
        "land_clearance": pl.lit(5.0),
        "field_drainage": pl.lit(5.0),
        "irrigation_reservoirs": pl.lit(5.0),
        "qanats": pl.lit(5.0),
        "irrigated_rice_paddies": pl.lit(5.0),
        "farming_village": pl.lit(5.0),
    }

    level_columns: list[str] = []
    contribution_columns: list[str] = []
    expressions: list[pl.Expr] = []
    for building in sorted(positive_supported):
        level_column = f"theoretical_max_{building}_levels"
        contribution_column = f"theoretical_max_{building}_capacity"
        levels = pl.when(allowed[building]).then(maximum_levels[building]).otherwise(0.0)
        expressions.extend(
            (
                levels.alias(level_column),
                (levels * float(capacity_per_level[building])).alias(
                    contribution_column
                ),
            )
        )
        level_columns.append(level_column)
        contribution_columns.append(contribution_column)

    result = frame.with_columns(expressions).with_columns(
        pl.sum_horizontal(*(pl.col(column) for column in contribution_columns)).alias(
            "theoretical_max_infrastructure_capacity"
        ),
        pl.lit(THEORETICAL_MAX_DEVELOPMENT).alias(
            "theoretical_max_development"
        ),
    )
    relative = max(
        1.0
        + THEORETICAL_MAX_DEVELOPMENT * float(development_relative)
        + float(global_relative),
        0.0,
    )
    return result.with_columns(
        (
            (
                pl.col("deployed_static_population_capacity").cast(pl.Float64)
                + pl.col("theoretical_max_infrastructure_capacity")
            )
            * relative
        ).alias("theoretical_max_population_capacity")
    )


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
    *,
    food_change_from_locations: pl.DataFrame | None = None,
    food_change_to_locations: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Attach comparable start values, deltas, capacity fill, and food balance.

    Province food surplus/deficit is the change in total stored food during the
    latest simulated month. A caller can provide a one-month projection as the
    change target at tick zero while keeping ``current_locations`` untouched.
    The province value is broadcast to its locations for raster painting.
    """

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
        pl.col("deployed_static_population_capacity").alias(
            "starting_location_potential"
        ),
        pl.col("infrastructure_population_capacity").alias(
            "starting_infrastructure_population_capacity"
        ),
        pl.col("local_population_capacity").alias(
            "starting_population_capacity"
        ),
    ).unique("location_tag")
    if (food_change_from_locations is None) != (food_change_to_locations is None):
        raise ValueError(
            "food storage change requires both from-locations and to-locations"
        )
    if food_change_from_locations is None:
        province_food_change = current.select("province").unique().with_columns(
            pl.lit(0.0).alias("province_food_storage_change"),
        )
    else:
        from_province_food = food_change_from_locations.group_by("province").agg(
            pl.col("food").sum().alias("_from_province_food")
        )
        to_province_food = food_change_to_locations.group_by("province").agg(
            pl.col("food").sum().alias("_to_province_food")
        )
        province_food_change = to_province_food.join(
            from_province_food,
            on="province",
            how="left",
        ).select(
            "province",
            (
                pl.col("_to_province_food")
                - pl.col("_from_province_food").fill_null(0.0)
            ).alias("province_food_storage_change"),
        )
    return (
        current.join(starting, on="location_tag", how="left")
        .join(province_food_change, on="province", how="left")
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


def macro_region_statistics(
    frame: pl.DataFrame,
    metric: str,
    *,
    unit_column: str | None = None,
) -> pl.DataFrame:
    """Return ordinary descriptive statistics by macro-region."""

    required = {"macro_region", metric}
    if unit_column is not None:
        required.add(unit_column)
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            f"macro-region statistics are missing columns: {', '.join(sorted(missing))}"
        )
    selections: list[pl.Expr | str] = ["macro_region"]
    if unit_column is not None:
        selections.append(unit_column)
    selections.append(
        pl.when(pl.col(metric).cast(pl.Float64).is_finite())
        .then(pl.col(metric).cast(pl.Float64))
        .otherwise(None)
        .alias("value")
    )
    values = frame.select(selections).filter(pl.col("macro_region").is_not_null())
    if unit_column is not None:
        values = values.unique(["macro_region", unit_column])
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
