from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tomllib

import numpy as np
import polars as pl
import pytest
import rasterio

from prosper_or_perish_constructor.savegame_maps import SavegameMapAssets

from prosper_or_perish_constructor.simulation.location_capacity_calibration import (
    FORMULA_VERSION,
    LocationCapacityWeights,
    evaluate_location_capacity,
    export_location_capacity_run,
    summarize_location_capacity,
)


def _inputs() -> pl.DataFrame:
    data: dict[str, object] = {
        "location_tag": ["alpha"],
        "area_km2": [100.0],
        "macro_region": ["test"],
        "super_region": ["test"],
        "region": ["test"],
        "province": ["test"],
        "topography": ["flatlands"],
        "vegetation": ["farmland"],
        "calibrated_lon": [0.0],
        "calibrated_lat": [0.0],
        "hyde_cropland_area_km2": [10.0],
        "hyde_pasture_area_km2": [20.0],
        "hyde_irrigated_area_km2": [5.0],
        "starting_population_game_units": [80.0],
        "local_population_capacity": [100.0],
        "tsetse_ecological_exposure": [0.5],
    }
    for quantile, scale in (("p10", 0.5), ("p50", 1.0), ("p90", 2.0)):
        data[f"open_rainfed_capacity_people_{quantile}"] = [1_000.0 * scale]
        data[f"extensive_livestock_capacity_people_{quantile}"] = [200.0 * scale]
        data[f"retained_wild_capacity_people_{quantile}"] = [300.0 * scale]
        data[f"freshwater_capacity_people_{quantile}"] = [400.0 * scale]
        data[f"marine_capacity_people_{quantile}"] = [500.0 * scale]
        data[f"clearing_increment_capacity_people_{quantile}"] = [600.0 * scale]
        data[f"irrigation_increment_capacity_people_{quantile}"] = [700.0 * scale]
    return pl.DataFrame(data)


def _weights() -> LocationCapacityWeights:
    return LocationCapacityWeights(
        development_base=2.0,
        development_crop_points=0.0,
        development_pasture_points=0.0,
        development_relative=0.1,
        clearing_realization=0.5,
        irrigation_scale=2.0,
        irrigation_exponent=1.0,
        tsetse_weight=0.4,
        minimum_capacity_game_units=0.0,
    )


def test_exact_global_formula_and_people_unit_conversion() -> None:
    result = evaluate_location_capacity(
        _inputs(),
        _weights(),
        people_per_game_unit=1_000.0,
    )

    # Base = 1000 + 200*(1-.4*.5) + 300 + 400 + 500 = 2360.
    # Add clearing 300 and irrigation .1*700, then multiply by 1 + .1*2.
    assert result.item(0, "base_location_potential_people") == pytest.approx(2_360.0)
    assert result.item(0, "irrigation_realized_fraction") == pytest.approx(0.1)
    assert result.item(0, "candidate_capacity_people") == pytest.approx(3_276.0)
    assert result.item(0, "candidate_capacity_game_units") == pytest.approx(3.276)
    assert result.item(0, "starting_population_people") == pytest.approx(80_000.0)
    assert result.item(0, "population_fill") == pytest.approx(80_000.0 / 3_276.0)


def test_capacity_controls_are_monotone_in_expected_direction() -> None:
    inputs = _inputs()
    weights = _weights()

    def capacity(candidate: LocationCapacityWeights) -> float:
        return float(
            evaluate_location_capacity(
                inputs,
                candidate,
                people_per_game_unit=1_000.0,
            ).item(0, "candidate_capacity_people")
        )

    baseline = capacity(weights)
    assert capacity(replace(weights, crop_weight=2.0)) > baseline
    assert capacity(replace(weights, clearing_realization=0.8)) > baseline
    assert capacity(replace(weights, irrigation_scale=3.0)) > baseline
    assert capacity(replace(weights, global_relative=-0.1)) < baseline
    assert capacity(replace(weights, tsetse_weight=0.8)) < baseline


def test_starting_population_is_validation_only() -> None:
    first = evaluate_location_capacity(
        _inputs(),
        _weights(),
        people_per_game_unit=1_000.0,
    )
    changed_population = _inputs().with_columns(
        pl.lit(9_999_999.0).alias("starting_population_game_units")
    )
    second = evaluate_location_capacity(
        changed_population,
        _weights(),
        people_per_game_unit=1_000.0,
    )

    assert second["candidate_capacity_people"].to_list() == first[
        "candidate_capacity_people"
    ].to_list()


def test_export_is_hash_addressed_and_round_trips(tmp_path: Path) -> None:
    weights = _weights()
    result = evaluate_location_capacity(
        _inputs(),
        weights,
        people_per_game_unit=1_000.0,
    )
    summary = summarize_location_capacity(result)
    anchors = tmp_path / "existing_anchor.csv"
    pl.DataFrame({"candidate": ["mechanistic"], "anchor_id": ["alpha"]}).write_csv(
        anchors
    )

    prepared_geometry = pl.DataFrame(
        {"location_tag": ["alpha"], "map_color_int": [1]}
    )
    map_assets = SavegameMapAssets(
        locations_png_path=tmp_path / "locations.png",
        baseline_path=tmp_path / "baseline.parquet",
        geometry_cache_path=None,
        geometry=prepared_geometry,
        packed_locations=np.array([[1, 1], [0, 0]], dtype=np.uint32),
        map_width=2,
        map_height=2,
        source_width=2,
        source_height=2,
        scale_x=1.0,
        scale_y=1.0,
        prepared_geometry=prepared_geometry,
    )
    run_dir = export_location_capacity_run(
        result,
        weights,
        output_root=tmp_path / "exports",
        people_per_game_unit=1_000.0,
        summary=summary,
        source_hashes={"test": "b" * 64},
        existing_anchor_results=(anchors,),
        assets=map_assets,
        geotiff_layers=("candidate_capacity_people",),
    )

    assert run_dir.name.startswith("run-")
    assert pl.read_parquet(run_dir / "location_capacity.parquet").equals(result)
    exported_summary = json.loads((run_dir / "summary.json").read_text())
    assert exported_summary["formula_version"] == FORMULA_VERSION
    assert exported_summary["source_hashes"] == {"test": "b" * 64}
    exported_weights = tomllib.loads((run_dir / "weights.toml").read_text())
    assert exported_weights["weights"]["physical_quantile"] == "p50"
    assert pl.read_csv(run_dir / "anchor_results.csv").item(0, "result_scope") == (
        "current_pipeline_evidence"
    )
    with rasterio.open(run_dir / "candidate_capacity_people.tif") as source:
        assert source.shape == (2, 2)
        assert source.descriptions == ("candidate_capacity_people",)
        assert source.tags()["formula_version"] == FORMULA_VERSION
