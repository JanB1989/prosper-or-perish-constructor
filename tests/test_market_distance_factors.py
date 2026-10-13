from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def _defines():
    defines = (MOD / "loading_screen/common/defines/pp_defines_adjustments.txt").read_text(encoding="utf-8-sig")
    return lambda key: float(defines.split(f"{key} = ", 1)[1].split()[0])


def test_river_channel_beats_open_sea_beats_downstream_river_beats_land():
    value = _defines()
    # a channel step costs a sea step (the channels carry no roads since 2026-10-13)
    assert value("MARKET_SEA_DISTANCE_FACTOR") < value("MARKET_OPEN_SEA_DISTANCE_FACTOR")
    assert value("MARKET_OPEN_SEA_DISTANCE_FACTOR") <= value("MARKET_DOWNSTREAM_FACTOR") < value("MARKET_UPSTREAM_FACTOR") < 1
    assert value("MARKET_BASE_DISTANCE_FACTOR") >= 0.005


def test_market_access_model_uses_the_mod_values():
    from prosper_or_perish_constructor.worldbuilder import market_access as ma

    value = _defines()
    assert ma.PARAMS["sea"] == ma.PARAMS["lake"] == value("MARKET_SEA_DISTANCE_FACTOR")
    assert ma.PARAMS["open"] == ma.PARAMS["lake_sea"] == value("MARKET_OPEN_SEA_DISTANCE_FACTOR")
    assert ma.PARAMS["down"] == value("MARKET_DOWNSTREAM_FACTOR") and ma.PARAMS["up"] == value("MARKET_UPSTREAM_FACTOR")
    assert not [road for road in ma.ROAD_MARKET_ACCESS if road.startswith("pp_navigation_")]
