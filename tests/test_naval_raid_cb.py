"""The Sea Raid casus belli (2026-10-23) and the files that hang on it stay wired together.

The casus belli points at the PP war goal (vanilla's naval superiority type, which ticks from blockades); the three
peace treaties and the Coastal Raid navy ability only work in a war of that casus belli; the treaties create the
relations defined next to them; every key the player sees has English localization.
"""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

MOD = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
COMMON = MOD / "in_game" / "common"
CB_FILE = COMMON / "casus_belli" / "pp_naval_raid_cb.txt"
WARGOAL_FILE = COMMON / "wargoals" / "pp_naval_raid_wargoal.txt"
TREATY_FILE = COMMON / "peace_treaties" / "pp_naval_raid_treaties.txt"
RELATION_FILE = COMMON / "scripted_relations" / "pp_naval_raid_relations.txt"
ABILITY_FILE = COMMON / "unit_abilities" / "pp_coastal_raid.txt"
LOC_FILE = MOD / "main_menu" / "localization" / "english" / "pp_naval_raid_l_english.yml"
CB = "cb_pp_naval_raid"


def _blocks(path: Path) -> dict[str, CList]:
    return {entry.key: entry.value for entry in parse_file(path).entries if isinstance(entry.value, CList)}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _loc_keys() -> set[str]:
    return set(re.findall(r"^ ([A-Za-z0-9_]+):", _text(LOC_FILE), flags=re.MULTILINE))


def test_casus_belli_uses_the_naval_superiority_war_goal() -> None:
    cb = _blocks(CB_FILE)[CB]
    wargoal = _blocks(WARGOAL_FILE)[cb.first("war_goal_type")]
    assert wargoal.first("type") == "naval_superiority"


def test_treaties_and_ability_need_a_war_of_the_casus_belli() -> None:
    treaties = _blocks(TREATY_FILE)
    assert set(treaties) == {"pp_peace_sea_tribute", "pp_peace_open_harbours", "pp_peace_sack_market"}
    for name, treaty in treaties.items():
        potential = treaty.first("potential")
        assert isinstance(potential, CList), name
        assert f"casus_belli:{CB}" in _text(TREATY_FILE).split(f"{name} = {{", 1)[1].split("cost = {", 1)[0], name
    assert f"in_war_of_casus_belli = casus_belli:{CB}" in _text(ABILITY_FILE)


def test_treaties_create_the_relations_defined_with_them() -> None:
    relations = set(_blocks(RELATION_FILE))
    created = set(re.findall(r"type = relation_type:([a-z_]+)", _text(TREATY_FILE)))
    assert created == relations == {"pp_sea_tribute", "pp_open_harbours"}


def test_every_player_facing_key_has_english_text() -> None:
    _blocks(ABILITY_FILE)  # parses
    keys = _loc_keys()
    wanted = {CB, f"{CB}_desc", "war_goal_pp_naval_raid", "war_goal_pp_naval_raid_desc", "PP_NAVAL_RAID_WAR_NAME"}
    for treaty in _blocks(TREATY_FILE):
        wanted |= {treaty, f"{treaty}_desc", f"{treaty}_entry", f"{treaty}_entry_short"}
    for relation in _blocks(RELATION_FILE):
        wanted |= {f"{relation}_relation", f"{relation}_relation_desc"}
    wanted |= {"pp_coastal_raid", "pp_coastal_raid_desc", "pp_coastal_raid_cta"}
    for path in (TREATY_FILE, ABILITY_FILE):
        wanted |= set(re.findall(r'(?:text|name|none_available_msg_key|desc) = "?((?:pp|PP)_[A-Za-z_]+)', _text(path)))
    assert sorted(wanted - keys) == []
