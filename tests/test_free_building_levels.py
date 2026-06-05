from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
from eu5gameparser.load_order import DataProfile, GameLayer
from PIL import Image

from prosper_or_perish_constructor.free_building_levels import (
    build_game_start_location_frame,
    compute_free_building_levels,
    contribution_category_summary,
    contribution_factor_group_summary,
    contribution_value_summary,
    enrich_locations_with_game_start_data,
    explain_development_components,
    extract_river_levels_from_maps,
    google_sheet_browser_url,
    load_country_capitals,
    load_development_weights,
    load_location_ranks,
    load_market_centers,
    load_port_locations,
    load_road_locations,
    load_road_type_levels,
    parse_google_sheet_csv_text,
    parse_free_building_level_sheet,
    public_google_sheet_csv_url,
    round_numeric_columns,
    validate_sheet_values_against_game_sources,
)


def test_parse_free_building_level_sheet_flattens_flag_columns() -> None:
    values = [
        ["FIXED / GEOGRAPHIC FACTORS"],
        [
            "topography",
            "free_building_levels",
            "vegetation",
            "free_building_levels",
            "river_level",
            "free_building_levels",
            "fixed_flag",
            "free_building_levels",
        ],
        ["flatland", "1.5", "woods", "-2", 5, "3", "is_port", ""],
        ["", "", "", "", "", "", "is_port", ""],
        ["DYNAMIC FACTORS"],
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
        ["city", "2", 1, "1.25", "market_center", "7", "per_point", "0.2"],
        ["", "", "", "", "province_capital", "4", "", ""],
    ]

    weights = parse_free_building_level_sheet(values)

    rows = {
        (row["factor"], row["value"]): row["free_building_levels"]
        for row in weights.to_dicts()
    }
    assert rows[("topography", "flatland")] == 1.5
    assert rows[("vegetation", "woods")] == -2
    assert rows[("river_level", "5")] == 3
    assert rows[("province_capital", "true")] == 4
    assert rows[("is_port", "true")] == 0
    assert rows[("location_rank", "city")] == 2
    assert rows[("road_level", "1")] == 1.25
    assert rows[("market_center", "true")] == 7
    assert rows[("development", "per_point")] == 0.2


def test_public_csv_shape_and_decimal_commas_parse_like_google_export() -> None:
    csv_text = (
        "FIXED / GEOGRAPHIC FACTORS,,,,,,,\n"
        "topography,free_building_levels,vegetation,free_building_levels,"
        "river_level,free_building_levels,fixed_flag,free_building_levels\n"
        'flatland,"20,00",desert,"0,00",0,"3,00",is_port,"20,00"\n'
        "DYNAMIC FACTORS,,,,,,,\n"
        "location_rank,free_building_levels,road_level,free_building_levels,"
        "dynamic_flag,free_building_levels,development,free_building_levels\n"
        'town,"20,00",1,"10,00",province_capital,"20,00",per_point,"0,50"\n'
    )

    weights = parse_free_building_level_sheet(parse_google_sheet_csv_text(csv_text))
    rows = {
        (row["factor"], row["value"]): row["free_building_levels"]
        for row in weights.to_dicts()
    }

    assert rows[("topography", "flatland")] == 20.0
    assert rows[("vegetation", "desert")] == 0.0
    assert rows[("river_level", "0")] == 3.0
    assert rows[("province_capital", "true")] == 20.0


def test_public_sheet_links_point_at_free_building_levels_tab() -> None:
    assert "gid=602606501" in google_sheet_browser_url()
    assert "gid=602606501" in public_google_sheet_csv_url()
    assert "format=csv" in public_google_sheet_csv_url()


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
    (common / "location_ranks").mkdir(parents=True)
    (common / "road_types").mkdir(parents=True)
    (common / "topography" / "00_default.txt").write_text("flatland={} hills={}", encoding="utf-8")
    (common / "vegetation" / "00_default.txt").write_text("woods={} forest={}", encoding="utf-8")
    (common / "location_ranks" / "00_default.txt").write_text("city={} rural_settlement={}", encoding="utf-8")
    (common / "road_types" / "00_generic.txt").write_text("gravel_road={ level=1 } railroad={ level=4 }", encoding="utf-8")

    weights = pl.DataFrame(
        [
            {"factor": "topography", "value": "flatland", "free_building_levels": 1.0},
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
                "river_level",
                "free_building_levels",
                "fixed_flag",
                "free_building_levels",
            ],
            ["flatland", "1", "grasslands", "2", "5", "3", "is_port", "5"],
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
    assert scored_alpha["free_building_levels"] == 58
    assert "free_building_levels" in result.frame.columns
    assert "location_value_missing_weight" in set(result.diagnostics["diagnostic"].to_list())

    categories = contribution_category_summary(result.frame)
    category_rows = {row["factor"]: row for row in categories.to_dicts()}
    assert category_rows["development"]["total_contribution"] == 18.5
    assert category_rows["development"]["nonzero_locations"] == 2
    assert sum(row["total_contribution"] for row in categories.to_dicts()) == result.frame["free_building_levels"].sum()

    groups = contribution_factor_group_summary(result.frame)
    group_rows = {row["factor_group"]: row for row in groups.to_dicts()}
    assert group_rows["fixed"]["total_contribution"] == 11
    assert group_rows["dynamic"]["total_contribution"] == 52.5

    splits = contribution_value_summary(result.frame)
    split_rows = {
        (row["factor"], row["value"]): row
        for row in splits.to_dicts()
    }
    assert split_rows[("topography", "flatland")]["total_contribution"] == 1
    assert split_rows[("topography", "hills")]["total_contribution"] == 0
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
    raw = json.loads(notebook.read_text(encoding="utf-8"))

    assert raw["nbformat"] == 4
    sources = "\n".join(
        "".join(cell.get("source", []))
        for cell in raw["cells"]
    )
    assert "read_public_google_sheet_values" in sources
    assert "Open the source Google Sheet" in sources
    assert "Log in & load sheet" not in sources
    assert "load_free_building_level_location_frame" in sources
    assert "compute_free_building_levels" in sources
    assert "contribution_category_summary" in sources
    assert "contribution_factor_group_summary" in sources
    assert "contribution_value_summary" in sources
    assert 'value_contributions.sort("absolute_contribution", descending=True).select(impact_columns)' in sources
    assert '.sort("absolute_contribution", descending=True)\n            .select(impact_columns)' in sources


def _fixture_profile(root: Path) -> DataProfile:
    return DataProfile(
        name="fixture",
        layers=(GameLayer(id="vanilla", name="Vanilla", root=root, kind="vanilla"),),
    )


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
