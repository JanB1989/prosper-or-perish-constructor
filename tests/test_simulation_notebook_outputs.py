from pathlib import Path

import numpy as np
import polars as pl
import pytest
import rasterio

from prosper_or_perish_constructor.savegame_maps import SavegameMapAssets
from prosper_or_perish_constructor.simulation.notebook_outputs import (
    GEOTIFF_NODATA,
    macro_region_statistics,
    prepare_simulation_analysis_state,
    write_simulation_metric_geotiff,
)


def test_prepare_simulation_analysis_state_adds_start_values_and_deltas() -> None:
    starting = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["p1", "p2"],
            "development": [10.0, 20.0],
            "total_population": [100.0, 200.0],
            "food": [5.0, 10.0],
        }
    )
    current = pl.DataFrame(
        {
            "location_tag": ["a", "b"],
            "province": ["p1", "p2"],
            "development": [12.0, 19.0],
            "total_population": [120.0, 180.0],
            "food": [5.0, 10.0],
            "local_population_capacity": [300.0, 225.0],
            "deployed_static_population_capacity": [240.0, 0.0],
        }
    )

    result = prepare_simulation_analysis_state(starting, current).sort("location_tag")

    assert result["starting_development"].to_list() == [10.0, 20.0]
    assert result["development_change"].to_list() == [2.0, -1.0]
    assert result["starting_population"].to_list() == [100.0, 200.0]
    assert result["population_change"].to_list() == [20.0, -20.0]
    assert result["population_capacity"].to_list() == [300.0, 225.0]
    assert result["capacity_fill"].to_list() == [0.4, 0.8]
    assert result["province_food_storage_change"].to_list() == [0.0, 0.0]


def test_prepare_simulation_analysis_state_broadcasts_latest_province_food_change() -> None:
    starting = pl.DataFrame(
        {
            "location_tag": ["a", "b", "c"],
            "province": ["p1", "p1", "p2"],
            "development": [10.0, 20.0, 30.0],
            "total_population": [100.0, 200.0, 300.0],
            "food": [10.0, 20.0, 30.0],
        }
    )
    previous = starting.with_columns(pl.col("food").alias("food"))
    current = starting.with_columns(
        pl.Series("food", [13.0, 22.0, 26.0]),
        pl.lit(500.0).alias("population_capacity"),
    )

    result = prepare_simulation_analysis_state(
        starting,
        current,
        food_change_from_locations=previous,
        food_change_to_locations=current,
    ).sort("location_tag")

    assert result["province_food_storage_change"].to_list() == [5.0, 5.0, -4.0]


def test_macro_region_statistics_returns_ordinary_descriptive_statistics() -> None:
    frame = pl.DataFrame(
        {
            "macro_region": ["east", "west", "west", "west"],
            "metric": [10.0, 1.0, 2.0, 3.0],
        }
    )

    result = macro_region_statistics(frame, "metric")
    west = result.filter(pl.col("macro_region") == "west").row(0, named=True)

    assert west["count"] == 3
    assert west["min"] == 1.0
    assert west["max"] == 3.0
    assert west["mean"] == 2.0
    assert west["median"] == 2.0
    assert west["std_dev"] == pytest.approx(1.0)
    assert west["sum"] == 6.0


def test_macro_region_statistics_can_count_one_value_per_province() -> None:
    frame = pl.DataFrame(
        {
            "macro_region": ["west", "west", "west"],
            "province": ["p1", "p1", "p2"],
            "metric": [5.0, 5.0, -2.0],
        }
    )

    west = macro_region_statistics(
        frame,
        "metric",
        unit_column="province",
    ).row(0, named=True)

    assert west["count"] == 2
    assert west["sum"] == 3.0


def test_write_simulation_metric_geotiff_reuses_eu5_location_raster(
    tmp_path: Path,
) -> None:
    colors = np.array(
        [
            [0x010203, 0x010203, 0],
            [0x040506, 0x040506, 0x010203],
        ],
        dtype=np.uint32,
    )
    assets = SavegameMapAssets(
        locations_png_path=tmp_path / "locations.png",
        baseline_path=tmp_path / "baseline.parquet",
        geometry_cache_path=None,
        geometry=pl.DataFrame(),
        packed_locations=colors,
        map_width=3,
        map_height=2,
        source_width=3,
        source_height=2,
        scale_x=1.0,
        scale_y=1.0,
        prepared_geometry=pl.DataFrame(
            {
                "location_tag": ["a", "b"],
                "map_color_int": [0x010203, 0x040506],
            }
        ),
    )
    frame = pl.DataFrame(
        {"location_tag": ["a", "b"], "total_population": [2.5, 7.0]}
    )
    output = tmp_path / "simulation.tif"

    result = write_simulation_metric_geotiff(
        frame,
        metric="total_population",
        assets=assets,
        output_path=output,
        simulation_years=500,
        start_year=1337,
    )

    assert result.mapped_locations == 2
    assert result.mapped_pixels == 5
    with rasterio.open(output) as source:
        raster = source.read(1)
        assert source.crs is None
        assert source.descriptions == ("total_population",)
        assert source.tags()["coordinate_space"] == "EU5 game-map pixels"
        assert source.tags()["simulation_end_year"] == "1837"
    np.testing.assert_array_equal(
        raster,
        np.array(
            [
                [2.5, 2.5, GEOTIFF_NODATA],
                [7.0, 7.0, 2.5],
            ],
            dtype=np.float32,
        ),
    )
