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
GAME_START = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_game_start.txt"
ROAD_STARTUP = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_road_infrastructure_startup.txt"
FOOD_STARTUP = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_food_building_startup_generated.txt"

ROAD_BUILDINGS = {
    "road_wardens_yard": {
        "advance": "road_building",
        "previous": None,
        "next": "paviors_yard",
        "pop_type": "peasants",
        "employment": "0.25",
        "upkeep": 1.5,
        "capital_speed": "0.075",
    },
    "paviors_yard": {
        "advance": "paved_road_advance",
        "previous": "road_wardens_yard",
        "next": "macadam_works",
        "pop_type": "laborers",
        "employment": "0.5",
        "upkeep": 3.0,
        "capital_speed": "0.15",
    },
    "macadam_works": {
        "advance": "modern_road_advance",
        "previous": "paviors_yard",
        "next": "permanent_way_depot",
        "pop_type": "laborers",
        "employment": "0.75",
        "upkeep": 8.0,
        "capital_speed": "0.25",
    },
    "permanent_way_depot": {
        "advance": "railroad_advance",
        "method_unlock": "pp_permanent_way_depot_maintenance",
        "previous": "macadam_works",
        "next": None,
        "pop_type": "laborers",
        "employment": "1.5",
        "upkeep": 20.0,
        "capital_speed": "0.40",
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


def _modifier_block(body: str) -> str:
    match = re.search(r"modifier\s*=\s*\{(?P<body>.*?)\n\s*\}", body, flags=re.S)
    assert match is not None, "missing modifier block"
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


def test_road_infrastructure_buildings_require_any_road_and_unlocks() -> None:
    for building, expected in ROAD_BUILDINGS.items():
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]

        assert "num_roads > 0" in body
        assert "has_road_of_type_to" not in body
        assert "type = road_type:" not in body

        expected_body = f"unlock_building = {building}"
        if method_unlock := expected.get("method_unlock"):
            expected_body = f"{expected_body}\nunlock_production_method = {method_unlock}"
        assert blueprint["advancements"] == [{"key": f"TRY_INJECT:{expected['advance']}", "body": expected_body}]


def test_road_infrastructure_modifiers_and_upkeep_targets_are_current() -> None:
    for building, expected in ROAD_BUILDINGS.items():
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]
        method_body = blueprint["production_methods"][0]["body"]
        modifier_body = _modifier_block(body)
        modifier_assignments = re.findall(r"^\s*([A-Za-z0-9_]+)\s*=", modifier_body, flags=re.M)

        assert modifier_assignments == ["local_distance_from_capital_speed_propagation"]
        assert _field(modifier_body, "local_distance_from_capital_speed_propagation") == expected["capital_speed"]
        assert _goods_total(method_body) == pytest.approx(expected["upkeep"])


def test_road_infrastructure_does_not_override_vanilla_roads() -> None:
    assert not ROAD_TYPES.exists()


def test_road_wardens_startup_is_deactivated_and_food_startup_is_untouched() -> None:
    game_start = GAME_START.read_text(encoding="utf-8-sig")
    startup = ROAD_STARTUP.read_text(encoding="utf-8-sig")

    assert "pp_road_infrastructure_startup" not in game_start
    assert "pp_road_infrastructure_startup = {" in startup
    assert "num_roads > 0" in startup
    assert "NOT = { has_building = building_type:road_wardens_yard }" in startup
    assert "building_type = building_type:road_wardens_yard" in startup
    assert "cost_multiplier = 0" in startup
    assert "can_build_building = building_type:road_wardens_yard" not in startup
    assert "road_wardens_yard" not in FOOD_STARTUP.read_text(encoding="utf-8-sig")
