"""Setup buildings must pass their gates and ownership while the game validates the start setup."""
from types import SimpleNamespace

import polars as pl

from prosper_or_perish_constructor.worldbuilder.buildings import gate_trigger, trigger_for
from prosper_or_perish_constructor.worldbuilder.start_placement import load_owners


def _contract(tmp_path, navigation=True):
    if navigation:
        (tmp_path / "navigation").mkdir()
        (tmp_path / "navigation/manifest.json").write_text("{}")
    rows = pl.DataFrame(schema={"attribute": pl.Utf8, "value": pl.Utf8, "game_key": pl.Utf8})
    return SimpleNamespace(root=tmp_path, attribute_rows=rows)


def test_gates_use_the_native_river_trigger_but_caps_keep_river_sizes(tmp_path):
    contract = _contract(tmp_path)
    gate = gate_trigger(contract, [{"river_level": ["1", "2", "3", "4", "5"]}, {"is_coastal": ["True"]}])
    assert gate == ["OR = {", "\thas_river = yes", "\thas_location_modifier = pp_wb_coastal", "}"]
    assert trigger_for(contract, "river_level", "3") == "pp_navigation_river_level_3 = yes"
    assert trigger_for(contract, "river_level", "0", gate=True) == "has_river = no"


def test_geography_sync_ships_the_map_ports_and_adjacencies(tmp_path):
    import json

    from prosper_or_perish_constructor.worldbuilder.geography import export_files

    files = ["in_game/map_data/ports.csv", "in_game/map_data/adjacencies.csv", "soil_assignments.csv", "in_game/map_data/default.map"]
    (tmp_path / "ha1300-build.json").write_text(json.dumps({"files": {f: "x" for f in files}}))
    assert export_files(tmp_path) == ["in_game/map_data/adjacencies.csv", "in_game/map_data/default.map", "in_game/map_data/ports.csv"]


def test_capitals_and_pop_countries_do_not_own_land(tmp_path):
    start = tmp_path / "mod/main_menu/setup/start"
    start.mkdir(parents=True)
    (start / "10_countries.txt").write_text(
        "countries = { countries = {\n"
        " AAA = { own_control_core = { a1 a2 } capital = a1 }\n"
        " TRB = { type = pop add_pops_from_locations = { t1 } capital = t1 }\n"
        " GON = { our_cores_conquered_by_others = { g1 } capital = g1 }\n"
        "} }\n")
    assert load_owners(tmp_path / "vanilla", tmp_path / "mod") == {"a1": "AAA", "a2": "AAA"}
