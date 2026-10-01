"""Setup buildings must pass their gates and ownership while the game validates the start setup."""
import re
from pathlib import Path
from types import SimpleNamespace

import polars as pl

from prosper_or_perish_constructor.worldbuilder.buildings import gate_trigger, trigger_for
from prosper_or_perish_constructor.worldbuilder.start_placement import load_owners

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


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
    assert trigger_for(contract, "river_level", "3") == "pp_wb_river_size_3 = yes"
    assert trigger_for(contract, "river_level", "0", gate=True) == "has_river = no"


def test_geography_sync_ships_the_map_ports_and_adjacencies(tmp_path):
    import json

    from prosper_or_perish_constructor.worldbuilder.geography import export_files

    files = ["in_game/map_data/ports.csv", "in_game/map_data/adjacencies.csv", "soil_assignments.csv", "in_game/map_data/default.map"]
    (tmp_path / "ha1300-build.json").write_text(json.dumps({"files": {f: "x" for f in files}}))
    assert export_files(tmp_path) == ["in_game/map_data/adjacencies.csv", "in_game/map_data/default.map", "in_game/map_data/ports.csv"]


def test_capitals_and_pop_countries_do_not_own_land(tmp_path):
    start = tmp_path / "mod/main_menu/setup/1337"
    start.mkdir(parents=True)
    (start / "10_countries.txt").write_text(
        "countries = { countries = {\n"
        " AAA = { own_control_core = { a1 a2 } capital = a1 }\n"
        " TRB = { type = pop add_pops_from_locations = { t1 } capital = t1 }\n"
        " GON = { our_cores_conquered_by_others = { g1 } capital = g1 }\n"
        "} }\n")
    assert load_owners(tmp_path / "vanilla", tmp_path / "mod") == {"a1": "AAA", "a2": "AAA"}


def _river_profile(tmp_path, key: str, value: str):
    """Vanilla river block, the World Builder TRY_REPLACE and a later hand-authored TRY_INJECT of the same line."""
    from eu5gameparser.load_order import DataProfile, GameLayer

    vanilla = tmp_path / "vanilla/game/main_menu/common/static_modifiers"
    mod = tmp_path / "mod/main_menu/common/static_modifiers"
    vanilla.mkdir(parents=True)
    mod.mkdir(parents=True)
    block = f"river_flowing_through_1 = {{ {key} = {value} }}\n"
    (vanilla / "location.txt").write_text(block, encoding="utf-8")
    (mod / "pp_00_wb_river_modifiers.txt").write_text("TRY_REPLACE:" + block, encoding="utf-8")
    (mod / "pp_location_modifier_adjustments.txt").write_text("TRY_INJECT:" + block, encoding="utf-8")
    return DataProfile(name="constructor", layers=(
        GameLayer(id="vanilla", name="Vanilla", root=tmp_path / "vanilla", kind="vanilla"),
        GameLayer(id="constructor", name="Mod", root=tmp_path / "mod", kind="mod"),
    ))


def test_an_inject_into_a_replaced_block_is_ignored_like_the_engine_does(tmp_path):
    # The generated river REPLACE folds in the hand-authored INJECT; counting both doubled every river's fish
    # capacity and put 1,900 starting fishing villages one level above the engine's max. Rules reads the parser's
    # merge, which drops the inject.
    from eu5gameparser.load_order import load_merged_directory

    profile = _river_profile(tmp_path, "fish_capacity_from_river_size", "1")
    merged = {e.key: e.value for e in load_merged_directory(profile, "static_modifiers", scope="main_menu").entries}
    assert merged["river_flowing_through_1"].values("fish_capacity_from_river_size") == [1]


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
    from prosper_or_perish_constructor.worldbuilder.start_simulation import Simulation, unguarded_topup_rows, write_topup

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
    potential = rules.buildings["fishing_village"].values("location_potential")[0]
    write_topup(topup, {"inland": "AAA", "bank": "AAA"}, tmp_path, base={("bank", "fishing_village"): 1},
                potentials={"fishing_village": potential})
    path = tmp_path / "in_game/common/scripted_effects/pp_start_river_topup.txt"
    text = path.read_text(encoding="utf-8-sig")
    # each level only where the engine allows it at game start: the potential copy and the live max level
    assert (" location:bank = { if = { limit = { pp_start_topup_fishing_village_potential = yes } if = { limit = { "
            "building_type_max_level = { building_type = building_type:fishing_village value >= 2 } } "
            "change_building_level_in_location = { building = building_type:fishing_village value = 1 } } } }") in text
    assert text.count("value >= 1 }") == 1 and text.count("value >= 2 }") == 2   # inland: from 0 to 2
    assert unguarded_topup_rows(path) == []
    triggers = (tmp_path / "in_game/common/scripted_triggers/pp_start_river_topup_potentials.txt").read_text(encoding="utf-8-sig")
    assert "pp_start_topup_fishing_village_potential = {\n\tOR = {\n\t\thas_river = yes\n\t\tis_coastal = yes\n\t}\n}" in triggers


def _rules(values="", statics="", buildings="", triggers=""):
    from collections import Counter

    from eu5gameparser.clausewitz.parser import parse_text

    from prosper_or_perish_constructor.worldbuilder.start_rules import Rules

    def block(text):
        return {e.key: e.value for e in parse_text(text).entries}

    rules = Rules.__new__(Rules)
    rules.unsupported = Counter()
    rules.values, rules.statics, rules.buildings, rules.triggers = block(values), block(statics), block(buildings), block(triggers)
    return rules


def _test(rules, text, ctx):
    from eu5gameparser.clausewitz.parser import parse_text

    return rules.test(parse_text(f"t = {{ {text} }}").entries[0].value, ctx)


def test_the_engine_river_statics_are_invisible_to_has_location_modifier_but_count_as_values():
    # EU5 (verified 2026-09-30): has_location_modifier does not see the engine's own river_flowing_through_N, so a cap
    # row tested that way was missing in game wherever the engine traced the river (Yangtze irrigated fields 8 levels,
    # 14 Taverns 1 level above max at the EU5 1.4 start). The caps read the size as a modifier value instead.
    from prosper_or_perish_constructor.worldbuilder.buildings import river_size_trigger

    rules = _rules(triggers="pp_wb_river_size_5 = { modifier:irrigant_cap_modifier > 4.5 modifier:irrigant_cap_modifier < 5.5 }")
    ctx = {"static_modifiers": {"river_flowing_through_5", "pp_wb_soil_loam"}, "engine_modifiers": {"river_flowing_through_5"},
           "modifiers": {"irrigant_cap_modifier": 5.0}}
    assert not _test(rules, "has_location_modifier = river_flowing_through_5", ctx)
    assert _test(rules, "has_location_modifier = pp_wb_soil_loam", ctx)   # setup-placed modifiers are visible
    assert river_size_trigger(5) == "pp_wb_river_size_5 = yes" and _test(rules, river_size_trigger(5), ctx)


def test_the_river_size_triggers_bracket_each_size(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.buildings import RIVER_SIZE_TRIGGERS_PATH, write_river_size_triggers

    write_river_size_triggers(tmp_path)
    rules = _rules(triggers=(tmp_path / RIVER_SIZE_TRIGGERS_PATH).read_text(encoding="utf-8-sig"))
    for size in range(0, 6):
        ctx = {"modifiers": {"irrigant_cap_modifier": float(size)}}
        hits = [n for n in range(1, 6) if _test(rules, f"pp_wb_river_size_{n} = yes", ctx)]
        assert hits == ([size] if size else [])


def test_the_setup_audit_checks_what_holds_without_the_engine_river():
    from collections import Counter

    from prosper_or_perish_constructor.worldbuilder.start_simulation import audit_setup

    rules = _rules(
        values="fish_cap = { value = modifier:fish_capacity_from_river_size add = 1 }",
        statics="river_flowing_through_1 = { fish_capacity_from_river_size = 1 }",
        buildings=("fishing_village = { rural_settlement = yes location_potential = { OR = { has_river = yes is_coastal = yes } } max_levels = fish_cap }\n"
                   "cathedral = { town = yes max_levels = 1 }\n"
                   "palace = { rural_settlement = yes location_potential = { this = c:HSA.capital } max_levels = 1 }\n"),
    )
    river = {"has_river": True, "static_modifiers": {"river_flowing_through_1"}, "engine_modifiers": {"river_flowing_through_1"},
             "modifiers": {"fish_capacity_from_river_size": 1.0}, "location_rank": "rural_settlement"}
    ctxs = {"inland": {**river, "is_coastal": False}, "bank": {**river, "is_coastal": True},
            "dry": {"has_river": False, "is_coastal": True, "static_modifiers": set(), "modifiers": {}, "location_rank": "rural_settlement"}}
    sim = SimpleNamespace(rules=rules, locations={"inland", "bank", "dry"},
                          ctx=lambda tag, counts=None: {**ctxs[tag], "buildings": counts or {}})
    levels = {
        "inland": Counter(fishing_village=1),     # needs the engine's river: invalid where it traces none
        "bank": Counter(fishing_village=2),       # coastal, but its second level needs the river size
        "dry": Counter(fishing_village=1, cathedral=1, palace=1),
        "foreign": Counter(fishing_village=1),    # not owned at the start
    }
    problems = {(r["location"], r["building"]): r["problem"] for r in audit_setup(sim, levels)}
    assert problems == {
        ("inland", "fishing_village"): "invalid building (location_potential)",
        ("bank", "fishing_village"): "above max level",
        ("dry", "fishing_village"): "",
        ("dry", "cathedral"): "invalid building (rank)",
        ("dry", "palace"): "unresolved",          # a country-scoped potential: the engine decides
        ("foreign", "fishing_village"): "unowned location",
    }
    assert rules.unsupported == Counter()        # audit lookups leave the build's unresolved-rule count alone


def test_an_unconditional_topup_level_is_reported(tmp_path):
    from prosper_or_perish_constructor.worldbuilder.start_simulation import unguarded_topup_rows

    path = tmp_path / "topup.txt"
    path.write_text(
        "pp_start_river_topup = {\n"
        " location:a = { change_building_level_in_location = { building = building_type:tavern value = 1 } }\n"
        " location:b = { if = { limit = { building_type_max_level = { building_type = building_type:tavern value >= 1 } } "
        "change_building_level_in_location = { building = building_type:tavern value = 1 } } }\n"
        " location:c = { if = { limit = { pp_start_topup_tavern_potential = yes } if = { limit = { building_type_max_level = "
        "{ building_type = building_type:tavern value >= 1 } } change_building_level_in_location = { building = building_type:tavern value = 1 } } } }\n"
        "}\n", encoding="utf-8")
    assert unguarded_topup_rows(path) == [("a", "tavern"), ("b", "tavern")]


def test_a_potential_copy_reads_back_like_the_original():
    from eu5gameparser.clausewitz.parser import parse_text
    from eu5gameparser.clausewitz.serializer import normalized_value

    from prosper_or_perish_constructor.worldbuilder.start_simulation import render_trigger

    original = parse_text('p = { location_rank ?= location_rank:town OR = { a = yes b >= 2 NOT = { c = no } } '
                          'custom_tooltip = { text = "A b" d = 0.5 } }').entries[0].value
    again = parse_text("t = {\n" + render_trigger(original) + "\n}").entries[0].value
    assert normalized_value(again) == normalized_value(original)


# ------------------------------------------------------------------ the shipped mod

def test_the_shipped_topup_adds_every_level_under_the_engine_checks():
    from eu5gameparser.clausewitz.parser import parse_file

    from prosper_or_perish_constructor.worldbuilder import start_simulation as ss

    topup = MOD_ROOT / ss.TOPUP_PATH
    assert ss.unguarded_topup_rows(topup) == []
    used = set(re.findall(r"(pp_start_topup_\w+_potential) = yes", topup.read_text(encoding="utf-8-sig")))
    defined = {e.key for e in parse_file(MOD_ROOT / ss.TOPUP_POTENTIALS_PATH).entries}
    assert used and used <= defined


def test_no_cap_or_potential_reads_the_river_size_with_has_location_modifier():
    # has_location_modifier sees only script-added modifiers, not the engine's own river statics (pp_navigation_river_level_N
    # is such a test too)
    offenders = [
        path.name
        for folder in ("in_game/common/script_values", "in_game/common/building_types", "main_menu/common/script_values")
        for path in sorted((MOD_ROOT / folder).glob("*.txt"))
        if re.search(r"has_location_modifier = river_flowing_through_|pp_navigation_river_level_", path.read_text(encoding="utf-8-sig"))
    ]
    assert offenders == []


def test_the_river_size_modifier_is_the_river_size_on_the_shipped_statics():
    from eu5gameparser.load_order import load_merged_directory, load_profile

    from prosper_or_perish_constructor.worldbuilder.start_simulation import check_river_size_modifier

    profile = load_profile("constructor", load_order_path=ROOT / "constructor.load_order.toml")
    statics = {}
    for scope in ("main_menu", "in_game"):
        statics.update({e.key: e.value for e in load_merged_directory(profile, "static_modifiers", scope=scope, include_scalars=True).entries})
    assert {f"river_flowing_through_{n}" for n in range(1, 6)} <= set(statics)
    check_river_size_modifier(SimpleNamespace(statics=statics))


def test_the_shipped_setup_passed_the_start_placement_audit():
    # ppc worldbuilder apply audits every setup building it writes (start_simulation.validate_setup) against the
    # start model of the engine and fails on any error the engine would log; the audit must cover the start file.
    from prosper_or_perish_constructor.worldbuilder import start_simulation as ss
    from prosper_or_perish_constructor.worldbuilder.start_placement import START_SETUP_PATH

    table = ROOT / ss.SETUP_AUDIT_RELATIVE_PATH
    if not table.is_file():   # no build in this checkout yet
        return
    audit = pl.read_csv(table, schema_overrides={"problem": pl.String, "cap": pl.Int64}).with_columns(pl.col("problem").fill_null(""))
    errors = audit.filter(~pl.col("problem").is_in(["", "unresolved"]))
    assert errors.height == 0, errors.head(10)
    audited = {(r["location"], r["building"]): r["levels"] for r in audit.iter_rows(named=True)}
    for line in (MOD_ROOT / START_SETUP_PATH).read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(\w+) = \{ tag = \w+ level = (\d+) location = (\w+) \}", line)
        if m:
            assert audited.get((m.group(3), m.group(1)), 0) >= int(m.group(2)), line
