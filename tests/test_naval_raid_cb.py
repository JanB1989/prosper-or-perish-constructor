"""The Sea Raid casus belli (2026-10-23) and the files that hang on it stay wired together.

The casus belli points at the PP war goal (vanilla's naval superiority type, which ticks from blockades); the peace
treaties and the Coastal Raid navy ability only work in a war of that casus belli; the treaties create relations
defined next to them; every key the player sees has English localization.
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
RAID_EFFECT_FILE = COMMON / "scripted_effects" / "pp_coastal_raid_effects.txt"
TARGET_TRIGGER_FILE = COMMON / "scripted_triggers" / "pp_naval_raid_triggers.txt"
LOC_FILE = MOD / "main_menu" / "localization" / "english" / "pp_naval_raid_l_english.yml"
CB = "cb_pp_naval_raid"
# Its treaty is gone (2026-10-23, Jan: same as vanilla war reparations); kept so saves that hold one still load.
RELATIONS_KEPT_FOR_SAVES = {"pp_sea_tribute"}


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


def test_casus_belli_only_targets_coasts_next_to_our_privateers() -> None:
    cb = _blocks(CB_FILE)[CB]
    for check in ("create_enabled", "declare_enabled"):
        assert "pp_naval_raid_target_trigger" in [entry.key for entry in cb.first(check).entries], check
    trigger = _text(TARGET_TRIGGER_FILE)
    assert "pp_naval_raid_target_trigger = {" in trigger
    assert "any_privateer_from_country" in trigger and "owner ?= scope:target" in trigger


def test_treaties_and_ability_need_a_war_of_the_casus_belli() -> None:
    treaties = _blocks(TREATY_FILE)
    assert set(treaties) == {"pp_peace_open_harbours", "pp_peace_sack_market"}
    for name, treaty in treaties.items():
        potential = treaty.first("potential")
        assert isinstance(potential, CList), name
        assert f"casus_belli:{CB}" in _text(TREATY_FILE).split(f"{name} = {{", 1)[1].split("cost = {", 1)[0], name
    ability = _blocks(ABILITY_FILE)["pp_coastal_raid"]
    assert ability.first("toggle") is True
    assert f"in_war_of_casus_belli = casus_belli:{CB}" in _text(ABILITY_FILE)
    for hook in ("start_effect", "on_entering_location"):
        assert [entry.key for entry in ability.first(hook).entries] == ["pp_coastal_raid_effect"], hook
    effect = _text(RAID_EFFECT_FILE)
    assert "pp_coastal_raid_effect = {" in effect
    assert f"casus_belli ?= casus_belli:{CB}" in effect


def test_treaties_create_the_relations_defined_with_them() -> None:
    relations = set(_blocks(RELATION_FILE))
    created = set(re.findall(r"type = relation_type:([a-z_]+)", _text(TREATY_FILE)))
    assert created == {"pp_open_harbours"}
    assert relations == created | RELATIONS_KEPT_FOR_SAVES


def test_every_player_facing_key_has_english_text() -> None:
    _blocks(ABILITY_FILE)  # parses
    keys = _loc_keys()
    wanted = {CB, f"{CB}_desc", "war_goal_pp_naval_raid", "war_goal_pp_naval_raid_desc", "PP_NAVAL_RAID_WAR_NAME"}
    for treaty in _blocks(TREATY_FILE):
        wanted |= {treaty, f"{treaty}_desc", f"{treaty}_entry", f"{treaty}_entry_short"}
    for relation in _blocks(RELATION_FILE):
        wanted |= {f"{relation}_relation", f"{relation}_relation_desc"}
    wanted |= {"pp_coastal_raid", "pp_coastal_raid_desc", "pp_coastal_raid_cta"}
    for path in (TREATY_FILE, ABILITY_FILE, TARGET_TRIGGER_FILE):
        wanted |= set(re.findall(r'(?:text|name|none_available_msg_key|desc) = "?((?:pp|PP)_[A-Za-z_]+)', _text(path)))
    assert sorted(wanted - keys) == []
