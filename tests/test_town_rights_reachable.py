"""Every town right the mod can show can actually be had (2026-11-11).

Jan, Grant Urban Rights for Dordrecht: Books Rights "never selectable". The rights tier was unlocked and its potential
held, but the specialization charters and rights asked for ``modifier:local_pp_<good>_line_levels >= N``, a counter the
line's buildings carry in ``raw_modifier``. The engine scales a ``raw_modifier`` by the building's input fulfilment, so
a line short of an input counts under its levels and one without inputs counts 0 (155 of 632 towns with 3+ line levels
in Jan's 1357 save read under 3). Nothing tested what the conditions read. These tests check, for every town right in
load order (vanilla and mod, switched-off and DLC-only rights left out), that it can be reached:

* an ``upgrades_to`` target exists, is not switched off and has an unlocking advance (a target with none counts as
  unlocked from the start, and the engine never grants a right whose upgrade is unlocked: run 43dbb336 had 0 charters);
* every ``unlock_town_rights`` names a right that exists, from an advance that is not switched off;
* the potential/allow of the mod's rights name only keys that exist (town rights, buildings, institutions, goods,
  modifier types, script values) and never read a level counter that sits in a building's ``raw_modifier``;
* the whole-level line values are current, cover every line building and every threshold the rights compare with.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import construction_plan_country as cpc
from prosper_or_perish_constructor import line_level_counts
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
MOD_ROOT = REPO / "mod" / "pp"
MOD_RIGHTS = MOD_ROOT / "in_game" / "common" / "town_rights"
_PREFIX = r"(?:REPLACE_OR_CREATE:|INJECT_OR_CREATE:|TRY_REPLACE:|TRY_INJECT:|REPLACE:|INJECT:)?"


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return vanilla_root(REPO, REPO / "constructor.toml")


@pytest.fixture(scope="module")
def rights(vanilla: Path) -> dict[str, cpc.Right]:
    found, _off, _dlc = cpc.read_rights(MOD_ROOT, vanilla)
    return {right.key: right for right in found}


@pytest.fixture(scope="module")
def all_right_keys(vanilla: Path) -> set[str]:
    return set(cpc.database(MOD_ROOT, vanilla, cpc.TOWN_RIGHTS))


def _names(vanilla: Path, *folders: str) -> set[str]:
    """Top-level keys (blocks and plain values such as ``x = 3``) of these folders, vanilla and mod."""
    names: set[str] = set()
    for folder in folders:
        for path, _dlc in cpc.game_files(MOD_ROOT, vanilla, Path(folder)):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            names.update(re.findall(rf"(?m)^{_PREFIX}([A-Za-z_][\w.]*)\s*=", text))
    return names


def _mod_right_blocks() -> dict[str, str]:
    """The mod's own town rights (potential + allow text, comments stripped)."""
    blocks: dict[str, str] = {}
    for path in sorted(MOD_RIGHTS.glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        for key, body in cpc.cp._blocks(text):
            conditions = cpc.inner_blocks(body, "potential") + cpc.inner_blocks(body, "allow")
            blocks[key.rpartition(":")[2]] = "\n".join(conditions)
    return blocks


def test_every_upgrade_target_exists_and_is_unlocked_by_an_advance(rights: dict[str, cpc.Right]):
    problems = []
    for right in rights.values():
        target = right.upgrades_to
        if target is None:
            continue
        if target not in rights:
            problems.append(f"{right.key} upgrades to {target}, which does not exist or is switched off")
        elif not rights[target].advances:
            # no unlocking advance = unlocked from the start, and the engine never grants a right whose upgrade is
            # unlocked: the base right could never be granted
            problems.append(f"{right.key} upgrades to {target}, which no advance unlocks")
    assert not problems, problems
    assert sum(right.upgrades_to is not None and right.key.startswith("pp_") for right in rights.values()) == 17


def test_every_unlocked_right_exists_and_its_advance_is_on(vanilla: Path, all_right_keys: set[str]):
    advances = cpc.database(MOD_ROOT, vanilla, cpc.ADVANCES)
    problems = []
    for name, entry in advances.items():
        unlocked = [value for body in entry.bodies for value in cpc.top_values(body, "unlock_town_rights")]
        if not unlocked:
            continue
        allow = [block for body in entry.bodies for block in cpc.inner_blocks(body, "allow")]
        potential = [block for body in entry.bodies for block in cpc.inner_blocks(body, "potential")]
        if any(cpc.switched_off((block,)) for block in allow + potential) and any(r.startswith("pp_") for r in unlocked):
            problems.append(f"{name} unlocks {unlocked} but can never be researched")
        problems += [f"{name} unlocks unknown town right {right}" for right in unlocked if right not in all_right_keys]
    assert not problems, problems
    # the specialization rights tier comes with the Printing Press advance
    printing = [v for body in advances["printing_press_advance"].bodies for v in cpc.top_values(body, "unlock_town_rights")]
    assert {f"pp_{good}_rights" for good in line_level_counts.counters(MOD_ROOT)} <= set(printing)


def test_mod_town_right_conditions_name_only_keys_that_exist(vanilla: Path, all_right_keys: set[str]):
    known = {
        "town_rights_type": all_right_keys,
        "building_type": _names(vanilla, "in_game/common/building_types"),
        "institution": _names(vanilla, "in_game/common/institution", "main_menu/common/institution"),
        "goods": _names(vanilla, "in_game/common/goods", "main_menu/common/goods"),
    }
    assert all(known.values()), {k: len(v) for k, v in known.items()}
    modifiers = _names(vanilla, "main_menu/common/modifier_type_definitions")
    values = _names(vanilla, "in_game/common/script_values", "main_menu/common/script_values")
    problems = []
    for key, conditions in _mod_right_blocks().items():
        for kind, name in re.findall(r"\b(town_rights_type|building_type|institution|goods):(\w+)", conditions):
            if name not in known[kind]:
                problems.append(f"{key}: unknown {kind}:{name}")
        for name in re.findall(r"\bmodifier:(\w+)", conditions):
            if name not in modifiers:
                problems.append(f"{key}: unknown modifier type {name}")
        # every PP name a condition compares (either side) must be a script value
        for left, right in re.findall(r"(?m)^\s*([\w.:]+)\s*(?:>=|<=|>|<)\s*([\w.:]+)\s*$", conditions):
            for side in (left, right):
                if side.startswith("pp_") and side not in values:
                    problems.append(f"{key}: compares unknown script value {side}")
    assert not problems, problems


def test_mod_town_rights_never_read_input_scaled_level_counters():
    """A building's raw_modifier is scaled by its input fulfilment: a "1 per level" counter there reads under the
    levels while an input is short and 0 without inputs, so a right gated on it may never open. Count whole levels
    (location_building_level, e.g. line_level_counts.py) instead."""
    from prosper_or_perish_constructor import food_level_counts

    scaled = {f"local_pp_{good}_line_levels" for good in line_level_counts.counters(MOD_ROOT)}
    scaled |= {name for per in food_level_counts.counters(MOD_ROOT).values() for name in per}
    assert len(scaled) >= 17
    problems = [
        f"{key} reads modifier:{name}"
        for key, conditions in _mod_right_blocks().items()
        for name in re.findall(r"\bmodifier:(\w+)", conditions)
        if name in scaled
    ]
    assert not problems, problems


def test_line_level_values_are_current_and_cover_every_threshold():
    found = line_level_counts.counters(MOD_ROOT)
    text, counted = line_level_counts.render(found)
    assert (MOD_ROOT / line_level_counts.OUTPUT).read_text(encoding="utf-8") == text
    assert len(counted) == 17 and all(counted.values())
    assert set(found["books"]) == {"scriptorium", "printing_press_shop", "printing_manufactory", "printing_mill"}
    thresholds = (MOD_ROOT / "in_game/common/script_values/pp_specialization_town_rights_values.txt").read_text(
        encoding="utf-8-sig")
    levels = dict(re.findall(r"(?m)^(pp_\w+)_line_levels = (\d+)$", thresholds))
    blocks = _mod_right_blocks()
    for good in found:
        for tier, design in (("charter", 3), ("rights", 8 if good in {
                "cloth", "leather", "pottery", "glass", "jewelry", "books"} else 5)):
            key = f"pp_{good}_{tier}"
            assert f"{line_level_counts.value_name(good)} >= {key}_line_levels" in blocks[key], key
            assert int(levels[key]) == design, key


def test_render_weights_and_names(tmp_path: Path):
    text, counted = line_level_counts.render({"books": {"scriptorium": 1.0, "printing_mill": 2.0}})
    assert counted == {"books": 2}
    assert "pp_location_books_line_levels = {" in text
    assert 'add = "location_building_level(building_type:scriptorium)"' in text
    assert 'add = { value = "location_building_level(building_type:printing_mill)" multiply = 2 }' in text
