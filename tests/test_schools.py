"""Schools (literacy rework 2026-11-25, Jan): literacy is earned through local buildings.

The Village School (clergy) gives peasants, laborers and soldiers their literacy cap, the Trade School (burghers) the
burghers'; three advances inside institution trees unlock them and a level; the Library keeps only the upper classes'
cap; clergy literacy teaches, peasant literacy brings estate power, laborer literacy no production efficiency.
Checks the hand-written files (building_types/pp_school_buildings.txt and friends) against vanilla.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
COMMON = MOD / "in_game" / "common"
SCHOOLS = COMMON / "building_types" / "pp_school_buildings.txt"
VALUES = COMMON / "script_values" / "pp_school_values.txt"
TRIGGERS = COMMON / "scripted_triggers" / "pp_school_triggers.txt"
ADVANCES = COMMON / "advances" / "pp_school_advances.txt"
METHODS = COMMON / "production_methods" / "pp_culture_maintenance_adjustments.txt"
CULTURE = COMMON / "building_types" / "pp_culture_building_adjustments.txt"
POPS = COMMON / "pop_types" / "pp_pop_adjustments.txt"
RIGHTS = COMMON / "town_rights" / "pp_specialization_town_rights.txt"
LOC = MOD / "main_menu" / "localization" / "english" / "pp_schools_l_english.yml"


def _blocks(path: Path) -> dict[str, CList]:
    return {e.key: e.value for e in parse_file(path).entries if isinstance(e.value, CList)}


def _values(block: CList) -> dict[str, object]:
    return {e.key: e.value for e in block.entries}


def _num(value: object) -> float:
    return float(str(value))


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game" / "in_game" / "common"


@pytest.fixture(scope="module")
def schools() -> dict[str, CList]:
    return _blocks(SCHOOLS)


SCHOOL_RULES = {
    "pp_village_school": {
        "pop_type": "clergy",
        "max_levels": "pp_village_school_max_level",
        "ranks": {"rural_settlement", "town", "city", "megalopolis"},
        "modifier": {
            "local_peasants_max_literacy": 10, "local_laborers_max_literacy": 10, "local_soldiers_max_literacy": 10,
            "local_monthly_literacy": 0.01, "local_pop_promotion_speed": 0.002,
        },
        "method": "pp_village_school_maintenance",
        "upkeep": {"beeswax": 0.03, "clay": 0.1, "manual_labor": 0.5},
        "weight": "pp_village_school_ai_weight",
    },
    "pp_trade_school": {
        "pop_type": "burghers",
        "max_levels": "pp_trade_school_max_level",
        "ranks": {"town", "city", "megalopolis"},
        "modifier": {
            "local_burghers_max_literacy": 10, "local_monthly_literacy": 0.01, "local_burghers_desired_pop": 0.3,
        },
        "method": "pp_trade_school_maintenance",
        "upkeep": {"books": 0.15, "beeswax": 0.05, "manual_labor": 0.5},
        "weight": "pp_trade_school_ai_weight",
    },
}


@pytest.mark.parametrize("key", sorted(SCHOOL_RULES))
def test_school_buildings(schools, key) -> None:
    rule = SCHOOL_RULES[key]
    body = _values(schools[key])
    assert body["pop_type"] == rule["pop_type"]
    assert body["max_levels"] == rule["max_levels"]
    # open to the estate whose people work there (an estate pays only for buildings of its own pop type)
    assert body["forbidden_for_estates"] is False
    assert {r for r in ("rural_settlement", "town", "city", "megalopolis") if body.get(r) is True} == rule["ranks"]
    # never an owner- or capital-dependent location_potential (the engine re-checks it on owner change)
    assert "location_potential" not in body
    assert {k: _num(v) for k, v in _values(body["modifier"]).items()} == rule["modifier"]
    assert [str(i) for i in body["possible_production_methods"].items] == [rule["method"]]
    assert rule["weight"] in str(body["ai_construct_weight"])
    # small staff: below the Library's cultural_employment (0.1)
    assert body["employment_size"] in {"religious_building_employment", "small_burgher_employment"}


@pytest.mark.parametrize("key", sorted(SCHOOL_RULES))
def test_school_upkeep_is_one_method(key) -> None:
    rule = SCHOOL_RULES[key]
    method = _values(_blocks(METHODS)[rule["method"]])
    goods = {k: _num(v) for k, v in method.items() if k not in {"icon_type", "icon", "category"}}
    assert goods == rule["upkeep"]
    assert method["category"] == "building_maintenance"
    assert not {"paper", "lumber"} & set(goods)


def test_school_caps_and_weights() -> None:
    values = _blocks(VALUES)
    village = values["pp_village_school_max_level"]
    rows = [_values(e.value) for e in village.entries if e.key == "add"]
    # base, Printing Press, Common Schooling (owner modifier), education policy: 1 + 1 + 1 + 1 at most
    assert [r["desc"] for r in rows] == [
        "BUILDING_LEVEL_BASE", "PP_BUILDING_LEVEL_PRINTING_PRESS", "BUILDING_LEVEL_FROM_OWNER_MODIFIERS",
        "PP_BUILDING_LEVEL_EDUCATION_POLICY",
    ]
    assert [str(r["value"]) for r in rows] == [
        "1", "this.pp_village_school_printing_press_level", "scope:owner.modifier:pp_village_school_levels",
        "this.pp_village_school_education_level",
    ]
    assert "printing_press_advance" in str(values["pp_village_school_printing_press_level"])
    assert "pp_educates_the_masses" in str(values["pp_village_school_education_level"])
    trade = [_values(e.value) for e in values["pp_trade_school_max_level"].entries if e.key == "add"]
    assert [str(r["value"]) for r in trade] == ["1", "this.pp_trade_school_specialization_level"]
    assert "pp_has_specialization_town_rights" in str(values["pp_trade_school_specialization_level"])

    def weight(key):
        v = _values(values[key])
        return str(v["value"]), _num(v["multiply"]), _num(v["add"]), _num(v["max"])

    assert weight("pp_village_school_ai_weight") == ("population", 2, 30, 150)
    assert weight("pp_trade_school_ai_weight") == ("num_pop_type:burghers", 10, 30, 150)


def test_specialization_trigger_names_every_specialization_right() -> None:
    """The trigger has to name each right (no engine trigger for "any specialization right"): it must list exactly the
    mod's own specialization rights, charter and rights tier."""
    rights = {k for k, v in _blocks(RIGHTS).items() if ":" not in k and _values(v).get("is_specialization") is True}
    trigger = _blocks(TRIGGERS)["pp_has_specialization_town_rights"]
    named = {str(e.value).split(":", 1)[1] for e in _values(trigger)["OR"].entries if e.key == "has_town_rights"}
    assert len(rights) == 37
    assert named == rights


def test_education_policies_exist(vanilla) -> None:
    law = _blocks(vanilla / "laws" / "01_common.txt")["education_masses_law"]
    policies = {e.key for e in law.entries if isinstance(e.value, CList)} - {"potential", "allow"}
    named = {str(e.value) for e in _values(_blocks(TRIGGERS)["pp_educates_the_masses"])["OR"].entries}
    assert named <= policies
    assert "uneducated_masses_education" not in named


ADVANCE_RULES = {
    # key: (age, parent = the institution's root advance, institution, unlock, ai weight)
    "pp_village_schools_advance": ("age_2_renaissance", "renaissance_advance", "renaissance", "pp_village_school", 200),
    "pp_reckoning_schools_advance": ("age_2_renaissance", "banking_advance", "banking", "pp_trade_school", 150),
    "pp_common_schooling_advance": ("age_4_reformation", "confessionalism_advance", "confessionalism", None, 150),
}


@pytest.mark.parametrize("key", sorted(ADVANCE_RULES))
def test_school_advances_sit_in_institution_trees(vanilla, key) -> None:
    age, parent, institution, unlock, ai = ADVANCE_RULES[key]
    body = _values(_blocks(ADVANCES)[key])
    assert body["age"] == age
    assert body["requires"] == parent
    assert body.get("unlock_building") == unlock
    assert _num(_values(body["ai_weight"])["add"]) == ai
    # the parent is the institution's root: depth 0 and the embraced-institution gate, as in vanilla
    roots = {}
    for path in sorted((vanilla / "advances").glob("0_age_of_*.txt")):
        roots.update(_blocks(path))
    root = _values(roots[parent])
    assert str(root["depth"]) == "0"
    assert f"institution:{institution}" in str(root["allow"])
    if unlock is None:
        assert _num(body["pp_village_school_levels"]) == 1


def test_library_and_university(vanilla) -> None:
    culture = _blocks(CULTURE)
    library = _values(_values(culture["REPLACE:library"])["modifier"])
    assert {k: _num(v) for k, v in library.items()} == {
        "local_cultural_influence": 0.1, "local_nobles_max_literacy": 5, "local_burghers_max_literacy": 5,
        "local_clergy_max_literacy": 5, "local_monthly_literacy": 0.02, "local_institution_growth_modifier": 0.25,
    }
    assert "pp_library_ai_weight" in str(_values(culture["REPLACE:library"])["ai_construct_weight"])
    university = _values(_values(culture["REPLACE:university"])["modifier"])
    assert _num(university["local_monthly_literacy"]) == 0.02


def test_printing_shop_spreads_literacy() -> None:
    shop = _blocks(COMMON / "building_types" / "zz_pp_printing_press_shop.txt")
    body = next(v for k, v in shop.items() if k.endswith("printing_press_shop"))
    assert _num(_values(_values(body)["modifier"])["local_monthly_literacy"]) == 0.005


def test_pop_literacy_impact(vanilla) -> None:
    """Clergy, laborers and peasants are full REPLACE copies, so their literacy_impact is exactly what the mod writes
    (whether an injected block replaces vanilla's or adds to it is not established)."""
    pops = _blocks(POPS)
    impact = {k.split(":", 1)[1]: {e.key: _num(e.value) for e in _values(v)["literacy_impact"].entries}
              for k, v in pops.items() if k.startswith("REPLACE:")}
    assert set(impact) == {"clergy", "laborers", "peasants"}
    assert impact["clergy"] == {"local_pop_conversion_speed_modifier": 0.25,
                                "local_pop_assimilation_speed_modifier": 0.25, "local_monthly_literacy": 0.02}
    # no production efficiency line of vanilla; literate laborers organise and move up a little faster (Jan)
    assert impact["laborers"] == {"local_max_rgo_size_modifier": 0.05, "local_peasants_estate_power": 0.25,
                                  "local_pop_promotion_speed_modifier": 0.25}
    assert impact["peasants"]["local_peasants_estate_power"] == 0.25
    assert impact["peasants"]["local_pop_promotion_speed_modifier"] == 1.0
    # nothing else of vanilla's type lost: every vanilla key outside literacy_impact is in the copy
    original = _blocks(vanilla / "pop_types" / "00_default.txt")
    for key in impact:
        copy = _values(pops[f"REPLACE:{key}"])
        assert {e.key for e in original[key].entries} <= set(copy), key
        assert not [k for k in pops if k.endswith(f":{key}") and not k.startswith("REPLACE:")], key


def test_texts() -> None:
    text = LOC.read_text(encoding="utf-8-sig")
    for key in ("pp_village_school", "pp_trade_school", "pp_village_school_maintenance", "pp_trade_school_maintenance",
                "pp_village_schools_advance", "pp_reckoning_schools_advance", "pp_common_schooling_advance",
                "MODIFIER_TYPE_NAME_pp_village_school_levels", "PP_BUILDING_LEVEL_PRINTING_PRESS",
                "PP_BUILDING_LEVEL_EDUCATION_POLICY", "PP_BUILDING_LEVEL_SPECIALIZATION_RIGHTS"):
        assert f"  {key}:" in text, key
    for key in ("pp_village_school", "pp_trade_school", "pp_village_school_maintenance", "pp_trade_school_maintenance",
                "pp_village_schools_advance", "pp_reckoning_schools_advance", "pp_common_schooling_advance"):
        assert f"  {key}_desc:" in text, key
    assert not any(ch.isdigit() for line in text.splitlines()[1:] for ch in line.split(":", 1)[1]), "no numbers"


def test_average_literacy_research() -> None:
    """Research stays on the country's average literacy (Jan, 2026-11-26); a point is worth 1.2 % (vanilla 1 %),
    and the two other lines of vanilla's block are kept."""
    import re

    text = (MOD / "main_menu/common/static_modifiers/pp_country_modifiers.txt").read_text(encoding="utf-8-sig")
    block = re.search(r"(?s)TRY_REPLACE:average_literacy = \{(.*?)\n\}", text).group(1)
    assert re.search(r"\bresearch_speed_modifier = 1\.2\b", block)
    assert "monthly_towards_innovative = societal_value_monthly_move" in block and "skill_of_new_artists = 0.1" in block

