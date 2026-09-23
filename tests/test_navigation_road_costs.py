import json
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder.navigation import road_costs

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def state(overrides):
    handover = {"navigable": {"movement_cost": -0.35, "market_access": -0.5}, "barrier": {"movement_cost": 2.0, "market_access": 3.0}}
    return {"manifest": {"config": {"road_costs": handover}}, "settings": {"road_costs": overrides}}


def test_constructor_overrides_market_access_and_keeps_handover_movement_cost():
    costs = road_costs(state({"barrier": {"market_access": 2.0}}))
    assert costs["barrier"] == {"movement_cost": 2.0, "market_access": 2.0}
    assert costs["navigable"] == {"movement_cost": -0.35, "market_access": -0.5}


def test_unknown_cost_profile_is_rejected():
    with pytest.raises(ValueError, match="Unknown navigation road cost profile"):
        road_costs(state({"rapids": {"market_access": 1.0}}))


def test_navigable_river_beats_coast_beats_small_river_beats_land():
    defines = (MOD / "loading_screen/common/defines/pp_defines_adjustments.txt").read_text(encoding="utf-8-sig")
    value = lambda key: float(defines.split(f"{key} = ", 1)[1].split()[0])
    land, sea = value("MARKET_BASE_DISTANCE_FACTOR"), value("MARKET_SEA_DISTANCE_FACTOR")
    costs = json.loads((ROOT / "config/river_navigation.json").read_text())["road_costs"]
    step = {name: sea * (1 + cost["market_access"]) for name, cost in costs.items()}
    assert step["improved"] < step["navigable"] < sea < value("MARKET_OPEN_SEA_DISTANCE_FACTOR")
    assert value("MARKET_OPEN_SEA_DISTANCE_FACTOR") <= value("MARKET_DOWNSTREAM_FACTOR") < value("MARKET_UPSTREAM_FACTOR") < 1
    assert step["navigable"] < step["difficult"] < step["improvable"] < step["barrier"] <= 1
    assert land >= 0.005
