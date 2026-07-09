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
from prosper_or_perish_constructor import food_building_startup as food_startup


def test_food_startup_plan_uses_pop_consumption_and_dynamic_victuals_food(tmp_path: Path) -> None:
    savegame, parser = _write_food_startup_tables(
        tmp_path,
        cookery_employment=1.25,
        market_employment=0.75,
    )
    config = _food_startup_config(tmp_path, savegame, parser)

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
    worker_metadata = {
        row["building"]: (row["worker_pop_type"], row["employment_size"])
        for row in result.building_outputs.to_dicts()
    }
    assert worker_metadata == {
        "cookery": ("laborers", 1.25),
        "victuals_market": ("laborers", 0.75),
    }

    planned = {
        row["building"]: row
        for row in result.building_plan.to_dicts()
    }
    assert (planned["cookery"]["location_slug"], planned["cookery"]["levels"]) == ("alpha", 2)
    assert (planned["victuals_market"]["location_slug"], planned["victuals_market"]["levels"]) == ("alpha", 1)
    assert planned["cookery"]["worker_peasant_requirement"] == 2.5
    assert planned["victuals_market"]["worker_peasant_requirement"] == 0.75
    assert result.summary["planned_worker_peasant_requirement"] == 3.25


def test_food_startup_plan_omits_unstaffable_levels(tmp_path: Path) -> None:
    savegame, parser = _write_food_startup_tables(
        tmp_path,
        alpha_peasants=3.25,
        beta_peasants=0.0,
        cookery_employment=1.0,
    )
    config = _food_startup_config(tmp_path, savegame, parser, include_market=False)

    result = build_food_startup_plan(config)

    planned = result.building_plan.to_dicts()
    assert len(planned) == 1
    assert planned[0]["building"] == "cookery"
    assert planned[0]["location_slug"] == "alpha"
    assert planned[0]["levels"] == 1
    assert planned[0]["worker_peasant_requirement"] == 1.0
    assert planned[0]["available_peasants_before"] == 3.25
    assert planned[0]["remaining_peasants_after"] == 2.25
    assert result.summary["planned_worker_peasant_requirement"] == 1.0


def test_compiler_startup_plan_omits_unstaffable_non_food_levels(tmp_path: Path) -> None:
    savegame, parser = _write_food_startup_tables(
        tmp_path,
        alpha_peasants=3.0,
        alpha_total_population=40.0,
        alpha_development=20.0,
        alpha_raw_material="iron",
        extra_buildings=[
            {
                "name": "iron_mine",
                "pop_type": "laborers",
                "employment_size": 0.75,
                "employment_size_key": "",
            }
        ],
    )
    config = _food_startup_config(tmp_path, savegame, parser, include_market=False)

    result = build_food_startup_plan(config)

    planned = result.building_plan.filter(pl.col("building") == "iron_mine").to_dicts()
    assert len(planned) == 1
    row = planned[0]
    assert row["startup_source"] == "rgo_startup"
    assert row["location_slug"] == "alpha"
    assert row["target_level"] == 2
    assert row["levels"] == 1
    assert row["worker_pop_type"] == "laborers"
    assert row["employment_size"] == 0.75
    assert row["worker_peasant_requirement"] == 0.75
    assert row["available_peasants_before"] == 3.0
    assert row["remaining_peasants_after"] == 2.25


def test_startup_plan_uses_unemployed_peasants_not_tribal_or_employed_peasants(tmp_path: Path) -> None:
    savegame, parser = _write_food_startup_tables(
        tmp_path,
        alpha_peasants=5.0,
        alpha_unemployed_peasants=0.0,
        alpha_tribesmen=35.0,
        alpha_laborers=0.0,
        alpha_total_population=40.0,
        alpha_development=20.0,
        alpha_raw_material="iron",
        extra_buildings=[
            {
                "name": "iron_mine",
                "pop_type": "laborers",
                "employment_size": 1.0,
                "employment_size_key": "",
            }
        ],
    )
    config = _food_startup_config(tmp_path, savegame, parser, include_market=False)

    result = build_food_startup_plan(config)

    assert result.building_plan.filter(pl.col("building") == "iron_mine").is_empty()
    assert result.summary["planned_worker_peasant_requirement"] == 0.0


def test_startup_locations_use_parser_start_data_when_load_order_exists(tmp_path: Path, monkeypatch) -> None:
    savegame, parser = _write_food_startup_tables(
        tmp_path,
        alpha_peasants=100.0,
        alpha_unemployed_peasants=100.0,
        alpha_tribesmen=0.0,
        alpha_raw_material="iron",
    )
    config = _food_startup_config(tmp_path, savegame, parser, include_market=False)
    _write_start_file_fixture(tmp_path, config.load_order)
    monkeypatch.setattr(
        food_startup,
        "_load_static_location_frame",
        lambda _config: pl.DataFrame(
            [
                {
                    "location_id": 1,
                    "slug": "alpha",
                    "province": "alpha_province",
                    "region": "r1",
                    "macro_region": "m1",
                    "super_region": "s1",
                    "development": 20.0,
                    "rank": "rural_settlement",
                    "raw_material": "iron",
                }
            ]
        ),
    )

    locations = food_startup._load_locations(config)

    row = locations.row(0, named=True)
    assert row["slug"] == "alpha"
    assert row["country_tag"] == "AAA"
    assert row["population_peasants"] == 0.0
    assert row["population_tribesmen"] == 21.0
    assert row["unemployed_peasants"] == 0.0


def test_startup_plan_reserves_town_setup_worker_shortfalls_before_food_levels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    savegame, parser = _write_food_startup_tables(
        tmp_path,
        alpha_raw_material="wheat",
        extra_buildings=[
            {
                "name": "mason",
                "pop_type": "laborers",
                "employment_size": 1.0,
                "employment_size_key": "",
            },
            {
                "name": "marketplace",
                "pop_type": "burghers",
                "employment_size": None,
                "employment_size_key": "trade_employment",
            },
        ],
    )
    config = _food_startup_config(tmp_path, savegame, parser, include_market=False)
    _write_town_setup_reservation_fixture(tmp_path, config.load_order)
    monkeypatch.setattr(
        food_startup,
        "_load_static_location_frame",
        lambda _config: pl.DataFrame(
            [
                {
                    "location_id": 1,
                    "slug": "alpha",
                    "province": "alpha_province",
                    "region": "r1",
                    "macro_region": "m1",
                    "super_region": "s1",
                    "development": 9.0,
                    "rank": "town",
                    "location_rank": "town",
                    "raw_material": "wheat",
                }
            ]
        ),
    )

    buildings = food_startup._load_buildings(config)
    marketplace = buildings.filter(pl.col("name") == "marketplace").row(0, named=True)
    existing = food_startup._load_existing_buildings(config)
    result = build_food_startup_plan(config)

    assert marketplace["employment_size"] == 0.1
    assert existing[("alpha", "mason")] == 3.0
    assert existing[("alpha", "marketplace")] == 5.0
    assert result.province_food.row(0, named=True)["food_shortfall"] > 0.0
    assert result.building_plan.filter(pl.col("building") == "cookery").is_empty()
    assert result.summary["planned_worker_peasant_requirement"] == 0.0


def test_render_food_startup_effect_splits_workers_without_runtime_guards() -> None:
    plan = pl.DataFrame(
        [
            {
                "building": "cookery",
                "location_slug": "alpha",
                "levels": 2,
                "worker_pop_type": "laborers",
                "employment_size": 0.5,
                "coverage_group": "supply",
                "province": 1,
                "location_id": 1,
                "worker_peasant_requirement": 1.0,
                "available_peasants_before": 10.0,
                "remaining_peasants_after": 9.0,
                "food_per_level": 20.0,
                "estimated_food_added": 40.0,
                "province_food_consumption": 100.0,
                "target_food": 50.0,
                "needed_food_before": 50.0,
                "placement": "highest_population",
                "province_capital": True,
                "location_rank": "town",
                "total_population": 9.0,
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
    assert text.count("split_pop = {") == 2
    assert text.count("construct_building = {") == 2
    assert "size = 0.5" in text
    assert "type = pop_type:laborers" in text
    assert "building_type = building_type:cookery" in text
    assert "instant = yes" in text
    assert "cost_multiplier = 0" in text
    assert "if = {" not in text
    assert "has_owner = yes" not in text
    assert "num_pop_type" not in text
    assert "location_building_level" not in text
    assert "NOT = { has_building" not in text


def _write_food_startup_tables(
    tmp_path: Path,
    *,
    alpha_peasants: float = 80.0,
    beta_peasants: float = 50.0,
    alpha_unemployed_peasants: float | None = None,
    beta_unemployed_peasants: float | None = None,
    alpha_total_population: float = 9.0,
    beta_total_population: float = 5.0,
    alpha_development: float = 10.0,
    beta_development: float = 15.0,
    alpha_raw_material: str = "wheat",
    beta_raw_material: str = "fish",
    alpha_laborers: float = 20.0,
    beta_laborers: float = 0.0,
    alpha_tribesmen: float = 0.0,
    beta_tribesmen: float = 0.0,
    cookery_employment: float = 1.0,
    market_employment: float = 0.5,
    extra_buildings: list[dict[str, object]] | None = None,
) -> tuple[Path, Path]:
    savegame = tmp_path / "savegame"
    parser = tmp_path / "parser"
    savegame.mkdir()
    parser.mkdir()
    if alpha_unemployed_peasants is None:
        alpha_unemployed_peasants = alpha_peasants
    if beta_unemployed_peasants is None:
        beta_unemployed_peasants = beta_peasants
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
                "development": alpha_development,
                "total_population": alpha_total_population,
                "rank": "town",
                "raw_material": alpha_raw_material,
                "food_consumption": 9999.0,
                "population_peasants": alpha_peasants,
                "population_laborers": alpha_laborers,
                "population_tribesmen": alpha_tribesmen,
                "unemployed_peasants": alpha_unemployed_peasants,
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
                "development": beta_development,
                "total_population": beta_total_population,
                "rank": "rural_settlement",
                "raw_material": beta_raw_material,
                "food_consumption": 8888.0,
                "population_peasants": beta_peasants,
                "population_laborers": beta_laborers,
                "population_tribesmen": beta_tribesmen,
                "unemployed_peasants": beta_unemployed_peasants,
            },
        ]
    ).write_parquet(savegame / "locations.parquet")
    pl.DataFrame(
        [
            {"name": "peasants", "pop_food_consumption": 1.0},
            {"name": "laborers", "pop_food_consumption": 2.0},
            {"name": "burghers", "pop_food_consumption": 2.0},
        ]
    ).write_parquet(parser / "pop_types.parquet")
    pl.DataFrame([{"name": "victuals", "food": 10.0}]).write_parquet(parser / "goods.parquet")
    building_rows = [
        {
            "name": "cookery",
            "pop_type": "laborers",
            "employment_size": cookery_employment,
            "employment_size_key": "",
        },
        {
            "name": "victuals_market",
            "pop_type": "laborers",
            "employment_size": market_employment,
            "employment_size_key": "",
        },
    ]
    if extra_buildings:
        building_rows.extend(extra_buildings)
    pl.DataFrame(building_rows).write_parquet(parser / "buildings.parquet")
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
    return savegame, parser


def _write_start_file_fixture(tmp_path: Path, load_order: Path) -> None:
    vanilla = tmp_path / "vanilla"
    start = vanilla / "game" / "main_menu" / "setup" / "start"
    start.mkdir(parents=True)
    (start / "06_pops.txt").write_text(
        """
locations = {
    alpha = {
        define_pop = { type = tribesmen size = 21 }
    }
}
""".strip(),
        encoding="utf-8",
    )
    (start / "10_countries.txt").write_text(
        """
countries = {
    countries = {
        AAA = {
            own_control_core = { alpha }
        }
    }
}
""".strip(),
        encoding="utf-8",
    )
    load_order.write_text(
        f"""
[paths]
vanilla_root = "{vanilla.as_posix()}"

[profiles]
constructor = ["vanilla"]
""".strip(),
        encoding="utf-8",
    )


def _write_town_setup_reservation_fixture(tmp_path: Path, load_order: Path) -> None:
    vanilla = tmp_path / "vanilla"
    start = vanilla / "game" / "main_menu" / "setup" / "start"
    town_setups = vanilla / "game" / "in_game" / "common" / "town_setups"
    script_values = vanilla / "game" / "main_menu" / "common" / "script_values"
    start.mkdir(parents=True)
    town_setups.mkdir(parents=True)
    script_values.mkdir(parents=True)
    (start / "06_pops.txt").write_text(
        """
locations = {
    alpha = {
        define_pop = { type = peasants size = 3 }
        define_pop = { type = burghers size = 2 }
    }
}
""".strip(),
        encoding="utf-8",
    )
    (start / "07_cities_and_buildings.txt").write_text(
        """
locations = {
    alpha = { rank = town town_setup = pp_test_town }
}

building_manager = {
}
""".strip(),
        encoding="utf-8",
    )
    (start / "10_countries.txt").write_text(
        """
countries = {
    countries = {
        AAA = {
            own_control_core = { alpha }
        }
    }
}
""".strip(),
        encoding="utf-8",
    )
    (town_setups / "00_default.txt").write_text(
        """
pp_test_town = {
    mason = 3
    marketplace = 5
}
""".strip(),
        encoding="utf-8",
    )
    (script_values / "default_values.txt").write_text(
        "trade_employment = 0.1\n",
        encoding="utf-8",
    )
    load_order.write_text(
        f"""
[paths]
vanilla_root = "{vanilla.as_posix()}"

[profiles]
constructor = ["vanilla"]
""".strip(),
        encoding="utf-8",
    )


def _food_startup_config(
    tmp_path: Path,
    savegame: Path,
    parser: Path,
    *,
    include_market: bool = True,
) -> FoodStartupConfig:
    buildings: list[BuildingRule] = [
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
        )
    ]
    if include_market:
        buildings.append(
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
            )
        )
    return FoodStartupConfig(
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
        buildings=tuple(buildings),
    )
