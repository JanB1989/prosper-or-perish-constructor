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


def test_an_inject_into_a_replaced_block_is_ignored_like_the_engine_does(tmp_path):
    # The generated river REPLACE folds in the hand-authored INJECT; counting both doubled every river's fish
    # capacity and put 1,900 starting fishing villages one level above the engine's max.
    from eu5gameparser.clausewitz.parser import parse_file

    from prosper_or_perish_constructor.worldbuilder.start_rules import engine_value

    path = tmp_path / "pp_00_wb_river_modifiers.txt"
    path.write_text("TRY_REPLACE:river_flowing_through_1 = {\n\tfish_capacity_from_river_size = 1\n}\n")
    line = parse_file(path).entries[0].location.line
    folded = parse_file(path).entries[0].value
    record = lambda mode, file="", at=0: SimpleNamespace(mode=mode, file=file, line=at)
    entry = SimpleNamespace(key="river_flowing_through_1", value="merged",
                            source_history=(record("CREATE"), record("TRY_REPLACE", str(path), line), record("TRY_INJECT")))
    assert engine_value(entry).values("fish_capacity_from_river_size") == folded.values("fish_capacity_from_river_size")
    plain = SimpleNamespace(key="k", value="merged", source_history=(record("CREATE"), record("TRY_INJECT")))
    assert engine_value(plain) == "merged"


def test_the_setup_attribute_modifiers_reach_the_start_placement():
    # Field management caps test pp_wb_fertility_* (low fertility: -3 levels); the placement must see them.
    from prosper_or_perish_constructor.worldbuilder.modifiers import setup_modifier_keys

    attrs = pl.DataFrame({"location_tag": ["orkney", "inland"], "fertility": ["low", "None"], "soil_type": ["loam", "sand"],
                          "is_coastal": ["true", "False"], "is_adjacent_to_lake": ["False", "True"]})
    assert setup_modifier_keys(SimpleNamespace(location_attributes=attrs)) == {
        "orkney": ["pp_wb_fertility_low", "pp_wb_soil_loam", "pp_wb_coastal"],
        "inland": ["pp_wb_soil_sand", "pp_wb_lake"],
    }


def test_setup_rows_failing_rank_or_potential_are_dropped_unless_unresolved():
    from collections import Counter

    from eu5gameparser.clausewitz.parser import parse_text

    from prosper_or_perish_constructor.worldbuilder.start_rules import Rules
    from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation

    rules = Rules.__new__(Rules)
    rules.triggers, rules.values = {}, {}
    rules.buildings = {e.key: e.value for e in parse_text(
        "tar_kiln = { rural_settlement = yes location_potential = { vegetation = forest } }\n"
        "pottery_guild = { town = yes }\n"
        "cathedral = { rural_settlement = setup_only }\n"
        "town_hall = { rural_settlement = yes location_potential = { this = c:HSA.capital } }\n").entries}
    ctx = {"location_tag": "beteta", "location_rank": "rural_settlement", "vegetation": "sparse"}
    sim = SimpleNamespace(rules=rules, locations={"beteta": {}}, trimmed=[], ctx=lambda tag: ctx,
                          counts={"beteta": Counter(tar_kiln=4, pottery_guild=1, cathedral=1, town_hall=1)})
    Simulation.drop_invalid(sim)
    assert sim.counts["beteta"] == Counter(tar_kiln=0, pottery_guild=0, cathedral=1, town_hall=1)


def test_the_river_share_of_starting_buildings_moves_to_game_start(tmp_path):
    # The engine drops some navigation bank remnants from its river sizes at setup (Mechelen, Hanyang), so the
    # setup keeps only what holds without a river and pp_start_river_topup adds the rest.
    from collections import Counter

    from eu5gameparser.clausewitz.parser import parse_text

    from prosper_or_perish_constructor.worldbuilder.start_rules import Rules
    from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation, write_topup

    def block(text):
        return {e.key: e.value for e in parse_text(text).entries}

    rules = Rules.__new__(Rules)
    rules.triggers, rules.unsupported = {}, Counter()
    rules.values = block("fish_cap = { value = modifier:fish_capacity_from_river_size add = 1 }")
    rules.statics = block("river_flowing_through_1 = { fish_capacity_from_river_size = 1 }")
    rules.buildings = block("fishing_village = { location_potential = { OR = { has_river = yes is_coastal = yes } } max_levels = fish_cap }")
    river = {"has_river": True, "static_modifiers": {"river_flowing_through_1"}, "modifiers": {"fish_capacity_from_river_size": 1.0}}
    ctxs = {"inland": {**river, "is_coastal": False}, "bank": {**river, "is_coastal": True}}
    sim = SimpleNamespace(rules=rules, locations=ctxs, ctx=lambda tag: ctxs[tag],
                          counts={"inland": Counter(fishing_village=2), "bank": Counter(fishing_village=2)})

    topup = Simulation.river_topup(sim)

    assert topup == {("inland", "fishing_village"): 2, ("bank", "fishing_village"): 1}
    write_topup(topup, {"inland": "AAA", "bank": "AAA"}, tmp_path)
    text = (tmp_path / "in_game/common/scripted_effects/pp_start_river_topup.txt").read_text(encoding="utf-8-sig")
    assert " location:bank = { change_building_level_in_location = { building = building_type:fishing_village value = 1 } }" in text
