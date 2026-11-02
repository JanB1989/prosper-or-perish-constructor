"""Every advance shows something on its card: a bare title in game is a bug, whatever emptied it.

What counts is the merged advance with the mod's script values, the way the game lists it. The copies of a modifier add
up and a line that comes to 0 is not listed, so a vanilla advance whose only line is a food value the mod zeroes
(``vanilla_food_productivity.py``), or one an inject cancels, comes out empty while no file looks wrong. There is no
exception list: an advance that only gates something (a decision, a building through ``country_potential``) says so
with a ``pure_tooltip_entry``. ``ppc build`` and ``ppc sync`` stop on an empty advance, tests/test_advance_tree.py too.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from functools import cache
from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList, Value
from eu5gameparser.load_order import LoadOrderConfig, load_merged_directory, load_profile

from prosper_or_perish_constructor.vanilla_food_productivity import script_values

PROFILE = "constructor"
# Keys of an advance that are not modifiers. Of these only `pure_tooltip_entry` is an effect line; what
# `modifier_while_progressing` gives ends with the research.
STRUCTURAL_KEYS = {
    "age", "icon", "requires", "for", "research_cost", "depth", "potential", "allow", "ai_weight",
    "starting_technology_level", "in_tree_of", "government", "country_type", "content_priority",
    "ai_preference_tags", "allow_children", "modifier_while_progressing", "pure_tooltip_entry",
}
# unlock_* key -> collection holding its targets. Other unlock_* keys count as effect lines unchecked.
UNLOCK_COLLECTIONS = {
    "unlock_building": "building_types",
    "unlock_unit": "unit_types",
    "unlock_government_reform": "government_reforms",
    "unlock_cabinet_action": "cabinet_actions",
    "unlock_estate_privilege": "estate_privileges",
    "unlock_town_rights": "town_rights",
    "unlock_levy": "levies",
    "unlock_road_type": "road_types",
    "unlock_subject_type": "subject_types",
    "unlock_casus_belli": "casus_belli",
    "unlock_law": "laws",
}


def card_lines(advance: CList, values: Mapping[str, float], exists: Callable[[str, str], bool]) -> Iterator[str]:
    """The effect lines of an advance's card, modifiers first. ``values``: script values with the mod loaded (NaN = a
    formula); ``exists(unlock key, target)``: whether an unlock reaches anything, asked only when the modifiers show none."""
    totals: dict[str, float] = defaultdict(float)
    rest: list[tuple[str, Value]] = []
    for item in advance.entries:
        if item.key == "pure_tooltip_entry":
            rest.append((item.key, item.value))
        elif item.key not in STRUCTURAL_KEYS:
            value = item.value
            if isinstance(value, str) and value in values and values[value] == values[value]:
                value = values[value]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[item.key] += float(value)
            else:
                rest.append((item.key, item.value))
    yield from (key for key, total in totals.items() if abs(total) > 1e-9)
    for key, value in rest:
        if isinstance(value, CList):
            shown = bool(value.entries or value.items)
        elif key == "pure_tooltip_entry":
            shown = True
        elif key.startswith("unlock_"):
            shown = exists(key, str(value))
        elif isinstance(value, bool) or str(value) in ("yes", "no"):
            shown = value is True or value == "yes"
        else:   # a formula, an @constant of its file; any other name is no value the game can read
            shown = str(value).startswith("@") or str(value) in values
        if shown:
            yield key


def _unlock_targets(load_order_path: Path) -> Callable[[str, str], bool]:
    profile = load_profile(PROFILE, load_order_path)

    @cache
    def keys(collection: str) -> frozenset[str]:
        return frozenset(entry.key for entry in load_merged_directory(profile, collection, scope="in_game").entries)

    @cache
    def methods() -> frozenset[str]:
        found = set(keys("production_methods"))
        for building in load_merged_directory(profile, "building_types", scope="in_game").entries:
            if isinstance(building.value, CList):
                for slot in building.value.values("unique_production_methods"):
                    if isinstance(slot, CList):
                        found.update(method.key for method in slot.entries)
        return frozenset(found)

    def exists(key: str, target: str) -> bool:
        if key == "unlock_production_method":
            return target in methods()
        return key not in UNLOCK_COLLECTIONS or target in keys(UNLOCK_COLLECTIONS[key])

    return exists


def empty_advances(load_order_path: Path) -> list[str]:
    """One line per advance that shows a bare title in game: its key, file and what is written in it."""
    config = LoadOrderConfig.load(load_order_path)
    values = script_values(config.vanilla_root / "game", config.layer(PROFILE).root)
    exists = _unlock_targets(load_order_path)
    empty: list[str] = []
    for entry in load_merged_directory(load_profile(PROFILE, load_order_path), "advances", scope="in_game").entries:
        if isinstance(entry.value, CList) and next(card_lines(entry.value, values, exists), None) is None:
            written = [f"{item.key} = {item.value}" for item in entry.value.entries if item.key not in STRUCTURAL_KEYS]
            empty.append(f"{entry.key} ({Path(entry.source_file).name}): {', '.join(written) or 'no effect line'}")
    return sorted(empty)
