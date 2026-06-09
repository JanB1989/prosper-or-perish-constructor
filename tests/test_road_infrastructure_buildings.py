from __future__ import annotations

from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ROAD_TYPES = MOD_ROOT / "in_game" / "common" / "road_types" / "pp_road_infrastructure_rebalance.txt"
ROAD_DEMANDS = MOD_ROOT / "in_game" / "common" / "goods_demand" / "pp_road_infrastructure_demands.txt"
GAME_START = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_game_start.txt"
ROAD_STARTUP = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_road_infrastructure_startup.txt"
FOOD_STARTUP = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_food_building_startup_generated.txt"

ROAD_BUILDINGS = {
    "road_wardens_yard": {
        "road": "gravel_road",
        "advance": "road_building",
        "previous": None,
        "next": "paviors_yard",
        "pop_type": "peasants",
        "employment": "0.5",
        "upkeep": 1.5,
        "road_keeps": {"movement_cost": "-0.08", "market_access": "-0.03", "pop_movement": "0.07"},
        "building_gets": {
            "movement_cost": "-0.17",
            "local_market_access": "0.07",
            "local_migration_speed_modifier": "0.13",
        },
    },
    "paviors_yard": {
        "road": "paved_road",
        "advance": "paved_road_advance",
        "previous": "road_wardens_yard",
        "next": "macadam_works",
        "pop_type": "laborers",
        "employment": "0.75",
        "upkeep": 3.0,
        "road_keeps": {
            "movement_cost": "-0.10",
            "market_access": "-0.07",
            "pop_movement": "0.10",
            "proximity": "1.5",
        },
        "building_gets": {
            "movement_cost": "-0.20",
            "local_market_access": "0.13",
            "local_migration_speed_modifier": "0.20",
            "local_proximity_source": "3.5",
        },
    },
    "macadam_works": {
        "road": "modern_road",
        "advance": "modern_road_advance",
        "previous": "paviors_yard",
        "next": "permanent_way_depot",
        "pop_type": "laborers",
        "employment": "1.0",
        "upkeep": 8.0,
        "road_keeps": {
            "movement_cost": "-0.12",
            "market_access": "-0.10",
            "pop_movement": "0.13",
            "proximity": "3.5",
        },
        "building_gets": {
            "movement_cost": "-0.23",
            "local_market_access": "0.20",
            "local_migration_speed_modifier": "0.27",
            "local_proximity_source": "6.5",
        },
    },
    "permanent_way_depot": {
        "road": "railroad",
        "advance": "railroad_advance",
        "method_unlock": "pp_permanent_way_depot_maintenance",
        "previous": "macadam_works",
        "next": None,
        "pop_type": "laborers",
        "employment": "1.5",
        "upkeep": 20.0,
        "road_keeps": {
            "movement_cost": "-0.27",
            "market_access": "-0.13",
            "pop_movement": "0.20",
            "proximity": "5",
        },
        "building_gets": {
            "movement_cost": "-0.53",
            "local_market_access": "0.27",
            "local_migration_speed_modifier": "0.40",
            "local_proximity_source": "10",
        },
    },
}

GOOD_PRICES = {
    "coal": 2.0,
    "horses": 3.0,
    "lumber": 1.5,
    "masonry": 1.0,
    "paper": 2.0,
    "sand": 0.5,
    "steel": 5.0,
    "tools": 3.0,
    "victuals": 2.5,
}


def _load_blueprint(building: str) -> dict:
    return yaml.safe_load((BLUEPRINT_ROOT / f"{building}.yml").read_text(encoding="utf-8"))


def _field(body: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*([^\s#]+)", body, flags=re.M)
    assert match is not None, f"missing {key}"
    return match.group(1)


def _road_block(road: str) -> str:
    text = ROAD_TYPES.read_text(encoding="utf-8-sig")
    match = re.search(rf"REPLACE:{re.escape(road)}\s*=\s*\{{(?P<body>.*?)\n\}}", text, flags=re.S)
    assert match is not None, f"missing road override for {road}"
    return match.group("body")


def _goods_total(body: str) -> float:
    total = 0.0
    for good, amount in re.findall(r"^\s*([A-Za-z0-9_]+)\s*=\s*([0-9.]+)\s*$", body, flags=re.M):
        if good == "category":
            continue
        total += GOOD_PRICES[good] * float(amount)
    return total


def test_road_infrastructure_blueprints_are_manifested_and_one_level_infrastructure() -> None:
    enabled = set(yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))["enabled"])

    for building, expected in ROAD_BUILDINGS.items():
        assert f"buildings/{building}.yml" in enabled
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]

        assert blueprint["building"]["mode"] == "CREATE"
        assert blueprint["upgrade_chain"]["family"] == "road_infrastructure"
        assert blueprint["upgrade_chain"]["previous"] == expected["previous"]
        assert blueprint["upgrade_chain"]["next"] == expected["next"]
        assert f"max_levels = 1" in body
        assert f"pop_type = {expected['pop_type']}" in body
        assert f"employment_size = {expected['employment']}" in body
        assert "category = infrastructure_category" in body
        assert "custom_tags = { pp_logistics_infrastructure_priority }" in body
        assert blueprint["prices"][0]["body"].strip() == "{gold = 50}"

        if expected["previous"] is None:
            assert "obsolete =" not in body
        else:
            assert f"obsolete = {expected['previous']}" in body


def test_road_infrastructure_buildings_require_matching_roads_and_unlocks() -> None:
    for building, expected in ROAD_BUILDINGS.items():
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]

        if building == "road_wardens_yard":
            assert "num_roads > 0" in body
            assert "has_road_of_type_to" not in body
        else:
            assert "has_road_of_type_to" in body
            assert "target = prev" in body
            assert f"type = road_type:{expected['road']}" in body

        expected_body = f"unlock_building = {building}"
        if method_unlock := expected.get("method_unlock"):
            expected_body = f"{expected_body}\nunlock_production_method = {method_unlock}"
        assert blueprint["advancements"] == [{"key": f"TRY_INJECT:{expected['advance']}", "body": expected_body}]


def test_road_infrastructure_modifier_split_and_upkeep_targets_are_rounded() -> None:
    for building, expected in ROAD_BUILDINGS.items():
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]
        method_body = blueprint["production_methods"][0]["body"]
        road_body = _road_block(expected["road"])

        for modifier, value in expected["building_gets"].items():
            assert _field(body, modifier) == value
        for modifier, value in expected["road_keeps"].items():
            assert _field(road_body, modifier) == value

        assert _field(road_body, "maintenance_demand") == "pp_no_road_maintenance"
        assert _goods_total(method_body) == pytest.approx(expected["upkeep"])


def test_road_infrastructure_road_overrides_preserve_vanilla_non_balance_fields() -> None:
    preserved = {
        "gravel_road": {
            "level": "1",
            "build_time_per_unit_distance": "15",
            "price_per_unit_distance": "build_gravel_road",
            "construction_demand": "build_gravel_road_demand",
            "color": "map_gravel_road",
            "spline_style_id": "0",
        },
        "paved_road": {
            "level": "2",
            "build_time_per_unit_distance": "20",
            "price_per_unit_distance": "build_paved_road",
            "construction_demand": "build_paved_road_demand",
            "color": "map_paved_road",
            "spline_style_id": "1",
        },
        "modern_road": {
            "level": "3",
            "build_time_per_unit_distance": "25",
            "price_per_unit_distance": "build_modern_road",
            "construction_demand": "build_modern_road_demand",
            "color": "map_modern_road",
            "spline_style_id": "2",
        },
        "railroad": {
            "level": "4",
            "build_time_per_unit_distance": "50",
            "price_per_unit_distance": "build_railroad",
            "construction_demand": "build_railroad_demand",
            "color": "map_railroad",
            "spline_style_id": "3",
        },
    }

    demand_text = ROAD_DEMANDS.read_text(encoding="utf-8-sig")
    assert re.search(r"pp_no_road_maintenance\s*=\s*\{\s*category\s*=\s*building_maintenance\s*\}", demand_text, flags=re.S)

    for road, fields in preserved.items():
        body = _road_block(road)
        for key, value in fields.items():
            assert _field(body, key) == value


def test_road_wardens_startup_is_registered_and_guarded() -> None:
    game_start = GAME_START.read_text(encoding="utf-8-sig")
    startup = ROAD_STARTUP.read_text(encoding="utf-8-sig")

    assert game_start.index("pp_game_start_effect") < game_start.index("pp_road_infrastructure_startup")
    assert game_start.index("pp_road_infrastructure_startup") < game_start.index("pp_food_building_startup")
    assert "pp_road_infrastructure_startup = {" in startup
    assert "num_roads > 0" in startup
    assert "NOT = { has_building = building_type:road_wardens_yard }" in startup
    assert "building_type = building_type:road_wardens_yard" in startup
    assert "cost_multiplier = 0" in startup
    assert "can_build_building = building_type:road_wardens_yard" not in startup
    assert "road_wardens_yard" not in FOOD_STARTUP.read_text(encoding="utf-8-sig")
