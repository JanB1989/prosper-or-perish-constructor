from __future__ import annotations

from pathlib import Path

import polars as pl

from prosper_or_perish_constructor.food_building_startup import (
    BuildingRule,
    FoodStartupConfig,
    OutputRule,
    ProductionSourceRule,
    ScoreRule,
    build_food_startup_plan,
    render_food_startup_effect,
)


def test_food_startup_plan_uses_pop_consumption_and_dynamic_victuals_food(tmp_path: Path) -> None:
    savegame = tmp_path / "savegame"
    parser = tmp_path / "parser"
    savegame.mkdir()
    parser.mkdir()
    pl.DataFrame(
        [
            {
                "location_id": 1,
                "slug": "alpha",
                "owner": 1,
                "owner_country_id": 1,
                "country_tag": "AAA",
                "province": 10,
                "region": "r1",
                "macro_region": "m1",
                "super_region": "s1",
                "development": 10.0,
                "total_population": 100.0,
                "rank": "town",
                "raw_material": "wheat",
                "food_consumption": 9999.0,
                "population_peasants": 80.0,
                "population_laborers": 20.0,
            },
            {
                "location_id": 2,
                "slug": "beta",
                "owner": 1,
                "owner_country_id": 1,
                "country_tag": "AAA",
                "province": 10,
                "region": "r1",
                "macro_region": "m1",
                "super_region": "s1",
                "development": 15.0,
                "total_population": 50.0,
                "rank": "rural_settlement",
                "raw_material": "fish",
                "food_consumption": 8888.0,
                "population_peasants": 50.0,
                "population_laborers": 0.0,
            },
        ]
    ).write_parquet(savegame / "locations.parquet")
    pl.DataFrame(
        [
            {"name": "peasants", "pop_food_consumption": 1.0},
            {"name": "laborers", "pop_food_consumption": 2.0},
        ]
    ).write_parquet(parser / "pop_types.parquet")
    pl.DataFrame([{"name": "victuals", "food": 10.0}]).write_parquet(parser / "goods.parquet")
    pl.DataFrame(
        [
            {
                "name": "pm_cook",
                "produced": "victuals",
                "output": 2.0,
                "input_goods": [],
                "input_amounts": [],
            },
            {
                "name": "pm_market",
                "produced": None,
                "output": None,
                "input_goods": ["victuals"],
                "input_amounts": [3.0],
            },
        ]
    ).write_parquet(parser / "production_methods.parquet")
    config = FoodStartupConfig(
        savegame_dir=savegame,
        parser_artifact_dir=parser,
        output_dir=tmp_path / "out",
        mod_script=None,
        load_order=tmp_path / "load_order.toml",
        profile="constructor",
        unknown_pop_food_consumption=0.0,
        food_consumption_multiplier=1.0,
        include_existing_buildings=False,
        generated_effect="pp_food_building_startup",
        production_sources=(
            ProductionSourceRule(
                key="subsistence_agriculture",
                enabled=True,
                mode="population_per_1000",
                population_column="population_peasants",
                food_per_1000_population=1.0,
            ),
        ),
        buildings=(
            BuildingRule(
                key="cookery",
                enabled=True,
                order=10,
                coverage_group="supply",
                target_food_ratio=1.0,
                target_basis="consumption",
                max_levels_per_province=2,
                max_levels_per_location=2,
                min_province_food_consumption=1,
                placement="highest_population",
                allowed_ranks=("rural_settlement", "town"),
                allowed_regions=(),
                allowed_macro_regions=(),
                allowed_super_regions=(),
                allowed_country_tags=(),
                required_raw_materials=(),
                required_province_raw_materials=("wheat",),
                excluded_raw_materials=(),
                min_location_population=0.0,
                min_location_development=0.0,
                min_province_rural_population_share=0.0,
                max_province_rural_population_share=None,
                min_province_urban_population_share=0.0,
                max_province_urban_population_share=None,
                max_province_peasant_population_share=None,
                min_province_development_per_1000_population=0.0,
                target_scale_min=1.0,
                peasant_share_scale_start=None,
                peasant_share_scale_end=None,
                development_per_1000_scale_start=None,
                development_per_1000_scale_end=None,
                output=OutputRule(
                    mode="production_methods",
                    good="victuals",
                    production_methods=("pm_cook",),
                    multiplier=1.0,
                    estimated_production_efficiency=0.5,
                ),
                score=ScoreRule(population=1.0, development=0.0, province_capital_bonus=0.0),
            ),
            BuildingRule(
                key="victuals_market",
                enabled=True,
                order=20,
                coverage_group="distribution",
                target_food_ratio=1.0,
                target_basis="consumption",
                max_levels_per_province=10,
                max_levels_per_location=1,
                min_province_food_consumption=1,
                placement="province_capital",
                allowed_ranks=("rural_settlement", "town"),
                allowed_regions=(),
                allowed_macro_regions=(),
                allowed_super_regions=(),
                allowed_country_tags=(),
                required_raw_materials=(),
                required_province_raw_materials=(),
                excluded_raw_materials=(),
                min_location_population=0.0,
                min_location_development=0.0,
                min_province_rural_population_share=0.0,
                max_province_rural_population_share=None,
                min_province_urban_population_share=0.0,
                max_province_urban_population_share=None,
                max_province_peasant_population_share=None,
                min_province_development_per_1000_population=0.0,
                target_scale_min=1.0,
                peasant_share_scale_start=None,
                peasant_share_scale_end=None,
                development_per_1000_scale_start=None,
                development_per_1000_scale_end=None,
                output=OutputRule(
                    mode="input_goods_as_food",
                    good="victuals",
                    production_methods=("pm_market",),
                    multiplier=1.0,
                ),
                score=ScoreRule(population=1.0, development=0.0, province_capital_bonus=1000.0),
            ),
        ),
    )

    result = build_food_startup_plan(config)

    assert result.summary["total_food_consumption"] == 170.0
    assert result.summary["total_food_production"] == 130.0
    assert result.summary["total_food_balance"] == -40.0
    demand = {row["slug"]: row["food_consumption"] for row in result.location_demand.to_dicts()}
    assert demand == {"alpha": 120.0, "beta": 50.0}
    production = {row["slug"]: row["food_production"] for row in result.location_food.to_dicts()}
    assert production == {"alpha": 80.0, "beta": 50.0}
    outputs = {row["building"]: row["food_per_level"] for row in result.building_outputs.to_dicts()}
    assert outputs == {"cookery": 30.0, "victuals_market": 30.0}
    efficiencies = {
        row["building"]: row["estimated_production_efficiency"]
        for row in result.building_outputs.to_dicts()
    }
    assert efficiencies == {"cookery": 0.5, "victuals_market": 0.0}
    planned = {
        row["building"]: (row["location_slug"], row["levels"])
        for row in result.building_plan.to_dicts()
    }
    assert planned["cookery"] == ("alpha", 2)
    assert planned["victuals_market"] == ("alpha", 1)


def test_render_food_startup_effect_uses_level_guards() -> None:
    plan = pl.DataFrame(
        [
            {
                "building": "cookery",
                "location_slug": "alpha",
                "levels": 2,
                "coverage_group": "supply",
                "province": 1,
                "location_id": 1,
                "food_per_level": 20.0,
                "estimated_food_added": 40.0,
                "province_food_consumption": 100.0,
                "target_food": 50.0,
                "needed_food_before": 50.0,
                "placement": "highest_population",
                "province_capital": True,
                "location_rank": "town",
                "total_population": 100.0,
                "development": 10.0,
                "region": "r1",
                "macro_region": "m1",
                "super_region": "s1",
                "country_tag": "AAA",
                "raw_material": "wheat",
            }
        ]
    )

    text = render_food_startup_effect(plan, effect_name="pp_food_building_startup")

    assert "pp_food_building_startup = {" in text
    assert "\teffect = {" in text
    assert "location:alpha = {" in text
    assert "building_type = building_type:cookery" in text
    assert "NOT = { has_building = building_type:cookery }" in text
    assert "value < 2" in text
    assert "instant = yes" in text
