"""Literate peasants farm better (2026-11-28, Jan): the peasants' literacy_impact adds 10 (thousand people) of arable
land and cuts peasant food by 30 % at full literacy, and writes the same land into a marker the land bars read.

The engine applies a pop type's literacy_impact to its location at the type's average literacy (0..1) and only takes
location modifiers there (private notes literacy_ai_149.md 7.1/7.2); capacity stays a flat sum (no percentage anywhere).
"""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp"
POPS = MOD / "in_game" / "common" / "pop_types" / "pp_pop_adjustments.txt"
TYPES = MOD / "main_menu" / "common" / "modifier_type_definitions" / "pp_school_modifier_types.txt"
LOC = MOD / "main_menu" / "localization" / "english" / "pp_schools_l_english.yml"
CAPACITY = ("local_population_capacity", "local_population_capacity_modifier", "total_population_capacity_modifier")


def _blocks(path: Path) -> dict[str, CList]:
    return {str(e.key): e.value for e in parse_file(path).entries if isinstance(e.value, CList)}


def _impact(block: CList, name: str) -> dict[str, float]:
    found = block.first(name)
    return {str(e.key): float(str(e.value)) for e in found.entries} if isinstance(found, CList) else {}


def test_peasants_literacy_impact_carries_land_and_food() -> None:
    peasants = _blocks(POPS)["REPLACE:peasants"]
    impact = _impact(peasants, "literacy_impact")
    assert impact["local_population_capacity"] == 10
    assert impact["local_peasants_food_consumption"] == -0.3
    # the land bars' marker is the same land (the bars cannot read a pop type's share of the capacity)
    assert impact["local_pp_literate_peasant_land"] == impact["local_population_capacity"]
    # no percentage capacity: it would multiply negative sums and break the land bars
    assert not {"local_population_capacity_modifier", "total_population_capacity_modifier"} & set(impact)


def test_no_other_pop_type_carries_capacity() -> None:
    for key, block in _blocks(POPS).items():
        for part in ("literacy_impact", "pop_percentage_impact"):
            lines = set(_impact(block, part))
            if key == "REPLACE:peasants" and part == "literacy_impact":
                lines -= {"local_population_capacity", "local_pp_literate_peasant_land"}
            assert not lines & set(CAPACITY), (key, part)
            assert "local_pp_literate_peasant_land" not in lines, (key, part)


def test_marker_is_a_location_modifier_with_a_text() -> None:
    text = re.sub(r"#[^\n]*", "", TYPES.read_text(encoding="utf-8-sig"))
    block = re.search(r"local_pp_literate_peasant_land = \{(.*?)\n\}", text, re.S).group(1)
    assert "category = location" in block and "percent" not in block
    loc = LOC.read_text(encoding="utf-8-sig")
    assert "  MODIFIER_TYPE_NAME_local_pp_literate_peasant_land:" in loc
    assert "  MODIFIER_TYPE_DESC_local_pp_literate_peasant_land:" in loc
    # the Village School text says what literate peasants do, without numbers (test_schools.test_texts)
    school = re.search(r'pp_village_school_desc: "([^"]*)"', loc).group(1)
    assert "need less food" in school
