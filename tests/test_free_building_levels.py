from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from polars.testing import assert_frame_equal
from eu5gameparser.load_order import DataProfile, GameLayer
from PIL import Image

from prosper_or_perish_constructor.free_building_levels import (
    COMPILE_BUILDING_TYPES_RELATIVE,
    COMPILE_CLIMATE_RELATIVE,
    COMPILE_LOCATION_RANKS_RELATIVE,
    COMPILE_STATIC_MODIFIERS_RELATIVE,
    COMPILE_TOPOGRAPHY_RELATIVE,
    COMPILE_VEGETATION_RELATIVE,
    FREE_BUILDING_LEVELS_MODIFIER_KEY,
    build_game_start_location_frame,
    audit_compile_modifier_baselines,
    compile_free_building_level_modifiers,
    compute_free_building_levels,
    compute_local_build_buildings_efficiency,
    compute_local_construction_speed,
    contribution_category_summary,
    contribution_factor_group_summary,
    contribution_value_summary,
    enrich_locations_with_game_start_data,
    explain_development_components,
    extract_river_levels_from_maps,
    google_sheet_browser_url,
    load_country_capitals,
    load_development_weights,
    load_free_building_level_weights,
    load_location_ranks,
    load_market_centers,
    load_port_locations,
    load_road_locations,
    load_modifier_baseline_resolver,
    load_road_type_levels,
    local_output_neutralizer_updates,
    LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN,
    LOCAL_CONSTRUCTION_SPEED_COLUMN,
    local_free_building_levels_sheet_csv_path,
    parse_free_building_level_sheet,
    parse_free_building_level_weights_csv,
    public_google_sheet_csv_url,
    read_local_free_building_level_sheet_csv,
    round_numeric_columns,
    validate_sheet_values_against_game_sources,
    write_local_free_building_level_sheet_copy,
)


def test_tidy_weights_csv_parses_flag_rows_and_efficiency_column(tmp_path: Path) -> None:
    csv_text = (
        "# comment line\n"
        "section,factor,value,free_building_levels,local_build_buildings_efficiency,local_construction_speed\n"
        "fixed,topography,flatland,1.5,,\n"
        "fixed,vegetation,woods,-2,,\n"
        "fixed,climate,oceanic,2,0.02,0.02\n"
        "fixed,river_level,5,3,0.25,0.25\n"
        "fixed,is_port,true,0,\n"
        "dynamic,location_rank,city,2,\n"
        "dynamic,road_level,1,1.25,\n"
        "dynamic,market_center,true,7,\n"
        "dynamic,province_capital,true,4,\n"
        "dynamic,development,per_point,0.2,\n"
    )
    csv_path = tmp_path / "weights.csv"
    csv_path.write_text(csv_text, encoding="utf-8")

    weights = parse_free_building_level_weights_csv(csv_path)

    rows = {
        (row["factor"], row["value"]): row
        for row in weights.to_dicts()
    }
    assert rows[("topography", "flatland")]["free_building_levels"] == 1.5
    assert rows[("vegetation", "woods")]["free_building_levels"] == -2
    assert rows[("climate", "oceanic")]["free_building_levels"] == 2
    assert rows[("climate", "oceanic")][LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN] == 0.02
    assert rows[("climate", "oceanic")][LOCAL_CONSTRUCTION_SPEED_COLUMN] == 0.02
    assert rows[("river_level", "5")]["free_building_levels"] == 3
    assert rows[("river_level", "5")][LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN] == 0.25
    assert rows[("river_level", "5")][LOCAL_CONSTRUCTION_SPEED_COLUMN] == 0.25
    assert rows[("province_capital", "true")]["free_building_levels"] == 4
    assert rows[("is_port", "true")]["free_building_levels"] == 0
    assert rows[("is_port", "true")][LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN] is None
    assert rows[("location_rank", "city")]["free_building_levels"] == 2
    assert rows[("road_level", "1")]["free_building_levels"] == 1.25
    assert rows[("market_center", "true")]["free_building_levels"] == 7
    assert rows[("development", "per_point")]["free_building_levels"] == 0.2


def test_tidy_weights_csv_accepts_decimal_commas(tmp_path: Path) -> None:
    csv_text = (
        "section,factor,value,free_building_levels,local_build_buildings_efficiency,local_construction_speed\n"
        'fixed,topography,flatland,"20,00",,\n'
        'fixed,vegetation,desert,"0,00",,\n'
        'fixed,river_level,0,"3,00","1,50","1,50"\n'
        'dynamic,province_capital,true,"20,00",,\n'
    )
    csv_path = tmp_path / "weights.csv"
    csv_path.write_text(csv_text, encoding="utf-8")

    weights = parse_free_building_level_weights_csv(csv_path)
    rows = {
        (row["factor"], row["value"]): row
        for row in weights.to_dicts()
    }

    assert rows[("topography", "flatland")]["free_building_levels"] == 20.0
    assert rows[("vegetation", "desert")]["free_building_levels"] == 0.0
    assert rows[("river_level", "0")]["free_building_levels"] == 3.0
    assert rows[("river_level", "0")][LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN] == 1.5
    assert rows[("river_level", "0")][LOCAL_CONSTRUCTION_SPEED_COLUMN] == 1.5
    assert rows[("province_capital", "true")]["free_building_levels"] == 20.0


def test_legacy_sheet_layout_still_parses_for_programmatic_fixtures() -> None:
    weights = parse_free_building_level_sheet(
        [
            ["FIXED / GEOGRAPHIC FACTORS"],
            ["topography", "free_building_levels", "fixed_flag", "free_building_levels"],
            ["flatland", "1.5", "is_port", ""],
            ["DYNAMIC FACTORS"],
            ["dynamic_flag", "free_building_levels", "development", "free_building_levels"],
            ["province_capital", "4", "per_point", "0.2"],
        ]
    )

    rows = {
        (row["factor"], row["value"]): row["free_building_levels"]
        for row in weights.to_dicts()
    }
    assert rows[("topography", "flatland")] == 1.5
    assert rows[("is_port", "true")] == 0
    assert rows[("province_capital", "true")] == 4
    assert rows[("development", "per_point")] == 0.2


def test_public_sheet_links_point_at_free_building_levels_tab() -> None:
    assert "gid=602606501" in google_sheet_browser_url()
    assert "gid=602606501" in public_google_sheet_csv_url()
    assert "format=csv" in public_google_sheet_csv_url()


def test_committed_local_free_building_levels_copy_loads_via_polars() -> None:
    repo = Path(__file__).resolve().parents[1]
    csv_path = local_free_building_levels_sheet_csv_path(repo)
    assert csv_path.is_file()

    weights = read_local_free_building_level_sheet_csv(repo=repo)

    assert weights.height == 43
    assert weights.filter(pl.col("factor") == "capital")["free_building_levels"].item() == 15.0
    assert (
        weights.filter(pl.col("factor") == "location_rank")["free_building_levels"].unique().sort().to_list()
        == [30.0, 40.0, 50.0, 70.0]
    )
    assert weights.filter(pl.col("factor") == "river_level", pl.col("value") == "0").is_empty()
    worst_static = (
        weights.filter(pl.col("factor") == "topography", pl.col("value") == "mountains")[
            "free_building_levels"
        ].item()
        + weights.filter(pl.col("factor") == "vegetation", pl.col("value") == "desert")[
            "free_building_levels"
        ].item()
        + weights.filter(pl.col("factor") == "climate", pl.col("value") == "arctic")[
            "free_building_levels"
        ].item()
    )
    assert worst_static == -75.0
    best_static = (
        weights.filter(pl.col("factor") == "topography", pl.col("value") == "flatland")[
            "free_building_levels"
        ].item()
        + weights.filter(pl.col("factor") == "vegetation", pl.col("value") == "farmland")[
            "free_building_levels"
        ].item()
        + weights.filter(pl.col("factor") == "river_level", pl.col("value") == "5")[
            "free_building_levels"
        ].item()
        + weights.filter(pl.col("factor") == "is_port", pl.col("value") == "true")[
            "free_building_levels"
        ].item()
        + weights.filter(pl.col("factor") == "climate", pl.col("value") == "mediterranean")[
            "free_building_levels"
        ].item()
    )
    assert best_static == 48.0
    assert weights.filter(pl.col("factor") == "topography").height == 7
    assert weights.filter(pl.col("factor") == "climate").height == 8
    fixed_efficiency = weights.filter(
        pl.col("factor").is_in(["topography", "vegetation", "climate", "river_level", "is_port"])
    )
    assert fixed_efficiency.height == 28
    assert fixed_efficiency[LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN].null_count() == 3
    assert fixed_efficiency.filter(pl.col(LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN).is_not_null()).height == 25
    assert (
        fixed_efficiency.filter(pl.col("factor") == "topography", pl.col("value") == "mountains")[
            LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN
        ].item()
        == -0.35
    )
    assert (
        fixed_efficiency.filter(pl.col("factor") == "climate", pl.col("value") == "arctic")[
            LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN
        ].item()
        == -0.1
    )
    assert (
        fixed_efficiency.filter(pl.col("factor") == "is_port", pl.col("value") == "true")[
            LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN
        ].item()
        == 0.15
    )
    fixed_construction_speed = weights.filter(
        pl.col(LOCAL_CONSTRUCTION_SPEED_COLUMN).is_not_null()
    )
    assert fixed_construction_speed.height == 29
    assert (
        fixed_construction_speed.filter(pl.col("factor") == "topography", pl.col("value") == "mountains")[
            LOCAL_CONSTRUCTION_SPEED_COLUMN
        ].item()
        == -0.35
    )
    efficiency_pairs = {
        (row["factor"], row["value"]): row[LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN]
        for row in weights.filter(pl.col(LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN).is_not_null()).to_dicts()
    }
    construction_pairs = {
        (row["factor"], row["value"]): row[LOCAL_CONSTRUCTION_SPEED_COLUMN]
        for row in weights.filter(pl.col(LOCAL_CONSTRUCTION_SPEED_COLUMN).is_not_null()).to_dicts()
    }
    assert efficiency_pairs == construction_pairs
    assert_frame_equal(load_free_building_level_weights(repo), weights)


def test_write_local_free_building_level_sheet_copy_round_trip(tmp_path: Path) -> None:
    weights = load_free_building_level_weights(Path(__file__).resolve().parents[1])
    csv_path, parquet_path = write_local_free_building_level_sheet_copy(
        tmp_path,
        weights,
    )

    assert csv_path.is_file()
    assert parquet_path.is_file()
    assert_frame_equal(load_free_building_level_weights(tmp_path), weights)


def test_round_numeric_columns_keeps_notebook_tables_to_two_decimals() -> None:
    frame = pl.DataFrame(
        {
            "name": ["alpha"],
            "score": [1.2345],
            "locations": [3],
        }
    )

    rounded = round_numeric_columns(frame)

    assert rounded["score"].item() == 1.23
    assert rounded["locations"].item() == 3


def test_setup_start_parsers_read_game_start_sources(tmp_path: Path) -> None:
    profile = _fixture_profile(tmp_path)
    start = tmp_path / "game" / "main_menu" / "setup" / "start"
    start.mkdir(parents=True)
    (start / "07_cities_and_buildings.txt").write_text(
        "locations={ alpha={ rank=city } beta={ rank=town } }",
        encoding="utf-8",
    )
    (start / "03_markets.txt").write_text(
        "market_manager={ add_market=alpha add_market=gamma }",
        encoding="utf-8",
    )
    (start / "09_roads.txt").write_text(
        "road_network={ alpha=beta beta=gamma }",
        encoding="utf-8",
    )
    (start / "10_countries.txt").write_text(
        "countries={ TST={ capital=beta nested={ capital=gamma } } }",
        encoding="utf-8",
    )
    (start / "14_development.txt").write_text(
        "development={ base=-2 river=0.5 road=2 city=5 alpha=3 }",
        encoding="utf-8",
    )
    map_data = tmp_path / "game" / "in_game" / "map_data"
    map_data.mkdir(parents=True)
    (map_data / "ports.csv").write_text(
        "LandProvince;SeaZone;x;y;\nalpha;sea;1;2;x\n",
        encoding="utf-8",
    )
    road_types = tmp_path / "game" / "in_game" / "common" / "road_types"
    road_types.mkdir(parents=True)
    (road_types / "00_generic.txt").write_text(
        "gravel_road={ level=1 } paved_road={ level=2 } modern_road={ level=3 } railroad={ level=4 }",
        encoding="utf-8",
    )

    assert load_location_ranks(profile) == {"alpha": "city", "beta": "town"}
    assert load_market_centers(profile) == {"alpha", "gamma"}
    assert load_road_locations(profile) == {"alpha", "beta", "gamma"}
    assert load_country_capitals(profile) == {"beta", "gamma"}
    assert load_development_weights(profile) == {"base": -2, "river": 0.5, "road": 2, "city": 5, "alpha": 3}
    assert load_port_locations(profile) == {"alpha"}
    assert load_road_type_levels(profile) == {
        "gravel_road": 1,
        "paved_road": 2,
        "modern_road": 3,
        "railroad": 4,
    }


def test_sheet_value_validation_uses_game_source_names(tmp_path: Path) -> None:
    repo = tmp_path
    project = repo / "constructor.toml"
    project.write_text(
        '[parser]\nload_order = "constructor.load_order.toml"\nprofile = "fixture"\n',
        encoding="utf-8",
    )
    (repo / "constructor.load_order.toml").write_text(
        f'[paths]\nvanilla_root = "{(tmp_path / "game").as_posix()}"\n[profiles]\nfixture = ["vanilla"]\n',
        encoding="utf-8",
    )
    common = tmp_path / "game" / "game" / "in_game" / "common"
    (common / "topography").mkdir(parents=True)
    (common / "vegetation").mkdir(parents=True)
    (common / "climates").mkdir(parents=True)
    (common / "location_ranks").mkdir(parents=True)
    (common / "road_types").mkdir(parents=True)
    (common / "topography" / "00_default.txt").write_text("flatland={} hills={}", encoding="utf-8")
    (common / "vegetation" / "00_default.txt").write_text("woods={} forest={}", encoding="utf-8")
    (common / "climates" / "00_default.txt").write_text("oceanic={} continental={}", encoding="utf-8")
    (common / "location_ranks" / "00_default.txt").write_text("city={} rural_settlement={}", encoding="utf-8")
    (common / "road_types" / "00_generic.txt").write_text("gravel_road={ level=1 } railroad={ level=4 }", encoding="utf-8")

    weights = pl.DataFrame(
        [
            {"factor": "topography", "value": "flatland", "free_building_levels": 1.0},
            {"factor": "climate", "value": "oceanic", "free_building_levels": 1.0},
            {"factor": "climate", "value": "martian", "free_building_levels": 1.0},
            {"factor": "road_level", "value": "4", "free_building_levels": 1.0},
            {"factor": "road_level", "value": "5", "free_building_levels": 1.0},
        ]
    )
    locations = _base_locations().with_columns(
        pl.lit("city").alias("location_rank"),
        pl.lit(1).alias("road_level"),
        pl.lit(False).alias("province_capital"),
        pl.lit(False).alias("is_port"),
        pl.lit(False).alias("market_center"),
        pl.lit(False).alias("capital"),
        pl.lit(False).alias("naval_governor"),
        pl.lit(False).alias("local_governor"),
    )

    validation = validate_sheet_values_against_game_sources(weights, locations, repo=repo, project=project)
    rows = {(row["factor"], row["value"]): row for row in validation.to_dicts()}

    assert rows[("topography", "flatland")]["status"] == "ok"
    assert rows[("climate", "oceanic")]["status"] == "ok"
    assert rows[("climate", "martian")]["status"] == "mismatch"
    assert rows[("road_level", "4")]["status"] == "ok"
    assert rows[("road_level", "5")]["status"] == "mismatch"


def test_extract_river_levels_from_maps_uses_palette_and_has_river(tmp_path: Path) -> None:
    locations = pl.DataFrame(
        [
            {"location_tag": "alpha", "named_location_hex": "ff0000", "has_river": True},
            {"location_tag": "beta", "named_location_hex": "00ff00", "has_river": False},
            {"location_tag": "gamma", "named_location_hex": "0000ff", "has_river": True},
        ]
    )
    location_pixels = np.array(
        [
            [[255, 0, 0], [0, 255, 0]],
            [[0, 0, 255], [0, 0, 255]],
        ],
        dtype=np.uint8,
    )
    locations_png = tmp_path / "locations.png"
    Image.fromarray(location_pixels, "RGB").save(locations_png)

    river_pixels = np.array([[5, 4], [255, 255]], dtype=np.uint8)
    rivers = Image.fromarray(river_pixels, "P")
    palette = [0] * 768
    for index, rgb in {4: (0, 200, 255), 5: (0, 150, 255), 255: (255, 255, 255)}.items():
        palette[index * 3 : index * 3 + 3] = list(rgb)
    rivers.putpalette(palette)
    rivers_png = tmp_path / "rivers.png"
    rivers.save(rivers_png)

    levels = extract_river_levels_from_maps(
        locations,
        locations_png_path=locations_png,
        rivers_png_path=rivers_png,
        chunk_rows=1,
    )

    assert {row["location_tag"]: row["river_level"] for row in levels.to_dicts()} == {
        "alpha": 5,
        "beta": 0,
        "gamma": 1,
    }


def test_enrich_locations_and_compute_free_building_levels() -> None:
    locations = _base_locations()
    enriched = enrich_locations_with_game_start_data(
        locations,
        ranks={"alpha": "city"},
        market_centers={"alpha"},
        road_locations={"alpha"},
        capitals={"alpha"},
        ports={"alpha"},
        river_levels={"alpha": 5, "beta": 0},
        development_weights={
            "base": -2,
            "coastal": 5,
            "river": 0.5,
            "road": 2,
            "city": 5,
            "flatland": 1,
            "grasslands": 1,
            "oceanic": 1,
            "test_region": 10,
            "test_area": 3,
        },
    )

    alpha = enriched.filter(pl.col("location_tag") == "alpha").to_dicts()[0]
    beta = enriched.filter(pl.col("location_tag") == "beta").to_dicts()[0]
    assert alpha["location_rank"] == "city"
    assert beta["location_rank"] == "rural_settlement"
    assert alpha["market_center"] is True
    assert alpha["capital"] is True
    assert alpha["is_port"] is True
    assert alpha["province_capital"] is True
    assert alpha["road_level"] == 1
    assert alpha["development"] == 26

    development_components = explain_development_components(
        enriched,
        {
            "base": -2,
            "coastal": 5,
            "river": 0.5,
            "road": 2,
            "city": 5,
            "flatland": 1,
            "grasslands": 1,
            "oceanic": 1,
            "test_region": 10,
            "test_area": 3,
        },
    )
    alpha_development = development_components.filter(pl.col("location_tag") == "alpha").to_dicts()[0]
    assert alpha_development["base_development"] == -2
    assert alpha_development["river_development"] == 2.5
    assert alpha_development["road_development"] == 2

    weights = parse_free_building_level_sheet(
        [
            [
                "topography",
                "free_building_levels",
                "vegetation",
                "free_building_levels",
                "climate",
                "free_building_levels",
                "river_level",
                "free_building_levels",
                "fixed_flag",
                "free_building_levels",
            ],
            ["flatland", "1", "grasslands", "2", "oceanic", "4", "5", "3", "is_port", "5"],
            ["", "", "", "", "continental", "-1", "", "", "", ""],
            [
                "location_rank",
                "free_building_levels",
                "road_level",
                "free_building_levels",
                "dynamic_flag",
                "free_building_levels",
                "development",
                "free_building_levels",
            ],
            ["city", "6", "1", "7", "market_center", "8", "per_point", "0.5"],
            ["", "", "", "", "capital", "9", "", ""],
            ["", "", "", "", "province_capital", "4", "", ""],
        ]
    )
    result = compute_free_building_levels(enriched, weights)

    scored_alpha = result.frame.filter(pl.col("location_tag") == "alpha").to_dicts()[0]
    assert scored_alpha["free_building_levels"] == 62
    assert scored_alpha["climate_free_building_levels"] == 4
    assert "free_building_levels" in result.frame.columns
    assert "location_value_missing_weight" in set(result.diagnostics["diagnostic"].to_list())

    categories = contribution_category_summary(result.frame)
    category_rows = {row["factor"]: row for row in categories.to_dicts()}
    assert category_rows["development"]["total_contribution"] == 18.5
    assert category_rows["development"]["nonzero_locations"] == 2
    assert category_rows["climate"]["total_contribution"] == 3
    assert sum(row["total_contribution"] for row in categories.to_dicts()) == result.frame["free_building_levels"].sum()

    groups = contribution_factor_group_summary(result.frame)
    group_rows = {row["factor_group"]: row for row in groups.to_dicts()}
    assert group_rows["fixed"]["total_contribution"] == 14
    assert group_rows["dynamic"]["total_contribution"] == 52.5

    splits = contribution_value_summary(result.frame)
    split_rows = {
        (row["factor"], row["value"]): row
        for row in splits.to_dicts()
    }
    assert split_rows[("topography", "flatland")]["total_contribution"] == 1
    assert split_rows[("topography", "hills")]["total_contribution"] == 0
    assert split_rows[("climate", "oceanic")]["total_contribution"] == 4
    assert split_rows[("climate", "continental")]["total_contribution"] == -1
    assert split_rows[("is_port", "true")]["share_of_factor_total_pct"] == 100
    assert split_rows[("development", "per_point")]["total_contribution"] == 18.5


def test_development_contribution_uses_effective_zero_to_hundred_cap() -> None:
    locations = _base_locations().with_columns(
        pl.when(pl.col("location_tag") == "alpha")
        .then(pl.lit(120.0))
        .otherwise(pl.lit(-10.0))
        .alias("development")
    )
    weights = parse_free_building_level_sheet(
        [
            ["development", "free_building_levels"],
            ["per_point", "0.5"],
        ]
    )

    result = compute_free_building_levels(
        locations.with_columns(
            pl.lit(0).alias("river_level"),
            pl.lit("rural_settlement").alias("location_rank"),
            pl.lit(0).alias("road_level"),
            pl.lit(False).alias("province_capital"),
            pl.lit(False).alias("is_port"),
            pl.lit(False).alias("market_center"),
            pl.lit(False).alias("capital"),
            pl.lit(False).alias("naval_governor"),
            pl.lit(False).alias("local_governor"),
        ),
        weights,
    )

    scores = {
        row["location_tag"]: row["development_free_building_levels"]
        for row in result.frame.select("location_tag", "development_free_building_levels").to_dicts()
    }
    assert scores == {"alpha": 50.0, "beta": 0.0}


def test_build_game_start_location_frame_smoke_with_fixture_maps(tmp_path: Path) -> None:
    profile = _fixture_profile(tmp_path)
    start = tmp_path / "game" / "main_menu" / "setup" / "start"
    start.mkdir(parents=True)
    (start / "07_cities_and_buildings.txt").write_text("locations={ alpha={ rank=city } }", encoding="utf-8")
    (start / "03_markets.txt").write_text("market_manager={ add_market=alpha }", encoding="utf-8")
    (start / "09_roads.txt").write_text("road_network={ alpha=beta }", encoding="utf-8")
    (start / "10_countries.txt").write_text("countries={ TST={ capital=alpha } }", encoding="utf-8")
    (start / "14_development.txt").write_text("development={ base=0 river=1 road=2 city=3 }", encoding="utf-8")

    map_data = tmp_path / "game" / "in_game" / "map_data"
    map_data.mkdir(parents=True)
    (map_data / "ports.csv").write_text("LandProvince;SeaZone;x;y;\nalpha;sea;1;2;x\n", encoding="utf-8")
    Image.fromarray(np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8), "RGB").save(map_data / "locations.png")
    rivers = Image.fromarray(np.array([[5, 255]], dtype=np.uint8), "P")
    rivers.putpalette([0] * 768)
    rivers.save(map_data / "rivers.png")

    enriched = build_game_start_location_frame(_base_locations(), profile=profile)

    assert {"location_rank", "market_center", "road_level", "river_level", "development"} <= set(enriched.columns)
    assert enriched.filter(pl.col("location_tag") == "alpha")["river_level"].item() == 5


def test_free_building_levels_notebook_is_valid_json() -> None:
    notebook = Path(__file__).resolve().parents[1] / "graphs" / "building_capacity" / "free_building_levels_workbench.ipynb"
    raw = json.loads(notebook.read_text(encoding="utf-8-sig"))

    assert raw["nbformat"] == 4
    sources = "\n".join(
        "".join(cell.get("source", []))
        for cell in raw["cells"]
    )
    assert "load_free_building_level_weights" in sources
    assert "LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN" in sources
    assert "LOCAL_CONSTRUCTION_SPEED_COLUMN" in sources
    assert "compute_local_construction_speed" in sources
    assert "free_building_levels_sheet.csv" in sources
    assert "free_building_levels_sheet.csv" in sources
    assert "google_sheet_browser_url" not in sources
    assert "sync_free_building_level_weights_from_google" not in sources
    assert "Log in & load sheet" not in sources
    assert "load_free_building_level_location_frame" in sources
    assert "compute_free_building_levels" in sources
    assert "contribution_category_summary" in sources
    assert "contribution_factor_group_summary" in sources
    assert "contribution_value_summary" in sources
    assert 'value_contributions.sort("absolute_contribution", descending=True).select(impact_columns)' in sources
    assert '.sort("absolute_contribution", descending=True)\n            .select(impact_columns)' in sources


def test_river_level_zero_is_baseline_and_positive_levels_match_old_totals() -> None:
    repo = Path(__file__).resolve().parents[1]
    weights = read_local_free_building_level_sheet_csv(repo=repo)
    location = _base_locations().filter(pl.col("location_tag") == "alpha").with_columns(
        pl.lit("rural_settlement").alias("location_rank"),
        pl.lit(0).alias("road_level"),
        pl.lit(False).alias("province_capital"),
        pl.lit(True).alias("is_port"),
        pl.lit(False).alias("market_center"),
        pl.lit(False).alias("capital"),
        pl.lit(False).alias("naval_governor"),
        pl.lit(False).alias("local_governor"),
        pl.lit(0.0).alias("development"),
    )

    expected_capacity = {0: 47.0, 1: 57.0, 5: 77.0}
    expected_efficiency = {0: -0.13, 1: -0.03, 5: 0.17}
    for river_level, capacity_total in expected_capacity.items():
        frame = location.with_columns(pl.lit(river_level).alias("river_level"))
        capacity = compute_free_building_levels(frame, weights).frame["free_building_levels"].item()
        efficiency = compute_local_build_buildings_efficiency(frame, weights)[
            LOCAL_BUILD_BUILDINGS_EFFICIENCY_COLUMN
        ].item()
        construction_speed = compute_local_construction_speed(frame, weights)[
            LOCAL_CONSTRUCTION_SPEED_COLUMN
        ].item()
        assert capacity == capacity_total
        assert efficiency == pytest.approx(expected_efficiency[river_level])
        assert construction_speed == pytest.approx(expected_efficiency[river_level])


def test_compile_free_building_level_modifiers_updates_without_clobbering(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    mod_root = tmp_path / "mod"
    topography_path = mod_root / COMPILE_TOPOGRAPHY_RELATIVE
    vegetation_path = mod_root / COMPILE_VEGETATION_RELATIVE
    climate_path = mod_root / COMPILE_CLIMATE_RELATIVE
    ranks_path = mod_root / COMPILE_LOCATION_RANKS_RELATIVE
    static_path = mod_root / COMPILE_STATIC_MODIFIERS_RELATIVE
    building_types_path = mod_root / COMPILE_BUILDING_TYPES_RELATIVE
    for path in (topography_path, vegetation_path, climate_path, ranks_path, static_path, building_types_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    topography_path.write_text(
        "TRY_INJECT:hills = {\n"
        "\tlocation_modifier = {\n"
        "\t\tlocal_monthly_food_modifier = 0.1\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )
    vegetation_path.write_text(
        "TRY_INJECT:desert = {\n"
        "\tlocation_modifier = {\n"
        "\t\tlocal_population_capacity = -10\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )
    climate_path.write_text(
        "TRY_INJECT:tropical = {\n"
        "\tlocation_modifier = {\n"
        "\t\tlocal_food_decay = 0.004\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )
    ranks_path.write_text(
        "TRY_INJECT:city = {\n"
        "\trank_modifier = {\n"
        "\t\tfree_building_levels = -60\n"
        "\t\tlocal_population_capacity = -100\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )
    static_path.write_text(
        "TRY_INJECT:river_flowing_through_1 = {\n"
        "\tlocal_monthly_food_modifier = -0.05\n"
        "}\n"
        "TRY_REPLACE:development = {\n"
        "\tgame_data = {\n"
        "\t\tcategory = location\n"
        "\t}\n"
        "\tfree_building_levels = 2\n"
        "\tlocal_food_capacity = 10\n"
        "}\n",
        encoding="utf-8",
    )
    building_types_path.write_text(
        "TRY_INJECT:local_governor = {\n"
        "\tmodifier = {\n"
        "\t\tlocal_proximity_source = 80\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )

    compile_free_building_level_modifiers(repo, mod_root)

    topography_text = topography_path.read_text(encoding="utf-8-sig")
    assert "local_monthly_food_modifier = 0.1" in topography_text
    assert "free_building_levels = -10" in topography_text
    assert "local_build_buildings_efficiency = -0.08" in topography_text
    assert "local_construction_speed = -0.08" in topography_text

    vegetation_text = vegetation_path.read_text(encoding="utf-8-sig")
    assert "local_population_capacity = -10" in vegetation_text
    assert "free_building_levels = -25" in vegetation_text

    climate_text = climate_path.read_text(encoding="utf-8-sig")
    assert "local_food_decay = 0.004" in climate_text
    assert "free_building_levels = -5" in climate_text
    assert "local_build_buildings_efficiency = -0.06" in climate_text
    assert "local_construction_speed = -0.06" in climate_text
    assert "TRY_INJECT:arid" in climate_text

    ranks_text = ranks_path.read_text(encoding="utf-8-sig")
    assert "free_building_levels = -50" in ranks_text
    assert "local_population_capacity = -100" in ranks_text
    assert "local_build_buildings_efficiency = -0.3" in ranks_text
    assert "local_construction_speed = -0.55" in ranks_text

    static_text = static_path.read_text(encoding="utf-8-sig")
    assert "local_monthly_food_modifier = -0.05" in static_text
    assert "free_building_levels = 10" in static_text
    assert "local_build_buildings_efficiency = 0.1" in static_text
    assert "local_construction_speed = 0.1" in static_text
    assert "TRY_REPLACE:development" in static_text
    assert "free_building_levels = 0.3" in static_text
    assert "local_food_capacity = 10" in static_text
    assert "TRY_INJECT:is_port" in static_text
    assert "TRY_INJECT:naval_governor" not in static_text
    assert "TRY_INJECT:local_governor" not in static_text

    building_types_text = building_types_path.read_text(encoding="utf-8-sig")
    assert "local_proximity_source = 80" in building_types_text
    assert "free_building_levels = 20" in building_types_text
    assert "free_building_levels = 25" in building_types_text
    assert "TRY_INJECT:naval_governor" in building_types_text
    assert "TRY_INJECT:local_governor" in building_types_text


def test_geography_local_output_neutralizers_match_vanilla_baselines() -> None:
    repo = Path(__file__).resolve().parents[1]
    load_order_path = repo / "constructor.load_order.toml"
    if not load_order_path.is_file():
        pytest.skip("constructor.load_order.toml is unavailable")
    try:
        baselines = load_modifier_baseline_resolver(repo)
    except (FileNotFoundError, OSError):
        pytest.skip("vanilla install is unavailable for geography output neutralizer test")

    mod_root = repo / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    targets = {
        "topography": COMPILE_TOPOGRAPHY_RELATIVE,
        "vegetation": COMPILE_VEGETATION_RELATIVE,
        "climate": COMPILE_CLIMATE_RELATIVE,
    }
    for factor, relative_path in targets.items():
        expected = local_output_neutralizer_updates(
            baselines,
            factor=factor,
            inner_header="location_modifier",
        )
        actual = _compiled_local_output_neutralizers(mod_root / relative_path)
        assert actual == expected


def test_audit_compile_modifier_baselines_covers_compiled_targets() -> None:
    repo = Path(__file__).resolve().parents[1]
    load_order_path = repo / "constructor.load_order.toml"
    if not load_order_path.is_file():
        pytest.skip("constructor.load_order.toml is unavailable")
    try:
        audit = audit_compile_modifier_baselines(repo)
    except (FileNotFoundError, OSError):
        pytest.skip("vanilla install is unavailable for baseline audit")

    compiled = audit.filter(pl.col("compiled_to_mod"))
    assert not compiled.is_empty()
    assert compiled.filter(
        (pl.col("factor") == "location_rank")
        & (pl.col("value") == "megalopolis")
        & (pl.col("modifier_key") == FREE_BUILDING_LEVELS_MODIFIER_KEY)
    )["vanilla_baseline"].item() == pytest.approx(200.0)
    assert compiled.filter(
        (pl.col("factor") == "capital") & (pl.col("modifier_key") == FREE_BUILDING_LEVELS_MODIFIER_KEY)
    )["vanilla_baseline"].item() == pytest.approx(5.0)
    assert compiled.filter(
        (pl.col("factor") == "climate")
        & (pl.col("value") == "arctic")
        & (pl.col("modifier_key") == FREE_BUILDING_LEVELS_MODIFIER_KEY)
    )["entry_exists_in_parser"].item() is True

    governors = compiled.filter(pl.col("factor").is_in(["naval_governor", "local_governor"]))
    assert governors.select("baseline_source").unique().to_series().to_list() == ["building_type"]
    assert governors.select("entry_exists_in_parser").unique().to_series().to_list() == [True]
    assert governors.select("vanilla_baseline").unique().to_series().to_list() == [0.0]

    uncompiled_roads = audit.filter(
        (pl.col("factor") == "road_level") & (~pl.col("compiled_to_mod"))
    )
    assert set(uncompiled_roads.select("value").to_series().to_list()) == {"2", "3", "4"}


def test_modifier_baseline_resolver_reads_vanilla_values() -> None:
    repo = Path(__file__).resolve().parents[1]
    load_order_path = repo / "constructor.load_order.toml"
    if not load_order_path.is_file():
        pytest.skip("constructor.load_order.toml is unavailable")
    try:
        baselines = load_modifier_baseline_resolver(repo)
    except (FileNotFoundError, OSError):
        pytest.skip("vanilla install is unavailable for baseline resolver test")

    assert baselines.baseline(
        source="location_rank",
        block_name="megalopolis",
        inner_header="rank_modifier",
        modifier_key=FREE_BUILDING_LEVELS_MODIFIER_KEY,
    ) == pytest.approx(200.0)
    assert baselines.baseline(
        source="static_modifier",
        block_name="capital",
        inner_header=None,
        modifier_key=FREE_BUILDING_LEVELS_MODIFIER_KEY,
    ) == 5.0
    assert baselines.baseline(
        source="topography",
        block_name="hills",
        inner_header="location_modifier",
        modifier_key=FREE_BUILDING_LEVELS_MODIFIER_KEY,
    ) == 0.0
    assert baselines.baseline(
        source="building_type",
        block_name="local_governor",
        inner_header="modifier",
        modifier_key=FREE_BUILDING_LEVELS_MODIFIER_KEY,
    ) == 0.0
    assert baselines.baseline(
        source="climate",
        block_name="tropical",
        inner_header="location_modifier",
        modifier_key=FREE_BUILDING_LEVELS_MODIFIER_KEY,
    ) == 0.0
    assert "local_governor" in baselines.building_types._by_name
    assert "tropical" in baselines.climates._by_name


def _fixture_profile(root: Path) -> DataProfile:
    return DataProfile(
        name="fixture",
        layers=(GameLayer(id="vanilla", name="Vanilla", root=root, kind="vanilla"),),
    )


def _compiled_local_output_neutralizers(path: Path) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for entry in parse_file(path).entries:
        if not isinstance(entry.value, CList):
            continue
        inner = entry.value.first("location_modifier")
        if not isinstance(inner, CList):
            continue
        values: dict[str, float] = {}
        for modifier in inner.entries:
            if (
                modifier.key.startswith("local_")
                and modifier.key.endswith("_output_modifier")
                and isinstance(modifier.value, int | float)
            ):
                values[modifier.key] = float(modifier.value)
        if values:
            output[entry.key.removeprefix("TRY_INJECT:").removeprefix("TRY_REPLACE:")] = values
    return output


def _base_locations() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "location_id": 1,
                "location_tag": "alpha",
                "province": "test_province",
                "super_region": "test_super",
                "macro_region": "test_macro",
                "region": "test_region",
                "area": "test_area",
                "named_location_hex": "ff0000",
                "is_coastal": True,
                "topography": "flatland",
                "vegetation": "grasslands",
                "climate": "oceanic",
                "raw_material": "wheat",
                "natural_harbor_suitability": 0.5,
                "has_river": True,
            },
            {
                "location_id": 2,
                "location_tag": "beta",
                "province": "test_province",
                "super_region": "test_super",
                "macro_region": "test_macro",
                "region": "test_region",
                "area": "test_area",
                "named_location_hex": "00ff00",
                "is_coastal": False,
                "topography": "hills",
                "vegetation": "woods",
                "climate": "continental",
                "raw_material": "lumber",
                "natural_harbor_suitability": None,
                "has_river": False,
            },
        ]
    )
