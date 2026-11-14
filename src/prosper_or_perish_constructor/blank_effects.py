"""Nothing the player can look at comes out blank in game, whatever emptied it.

What counts is the merged object with the mod's script values, the way the game lists it. The copies of a modifier add
up and a line that comes to 0 is not listed, so a vanilla object whose only line is a food value the mod zeroes
(``vanilla_food_productivity.py``), or one an inject cancels, comes out empty while no file looks wrong. There is no
exception list. ``ppc build`` and ``ppc sync`` stop on either check, the tests too (tests/test_blank_effects.py).

- ``empty_advances``: an advance with nothing on its card. A ``pure_tooltip_entry`` is no card line: the game prints it
  in the tooltip's header only, the card stays blank and the tooltip lists "None." (Potato Cultivation, 2026-11-14). One
  that only gates something (a decision, a building through ``country_potential``) needs a live line besides it.
- ``dead_modifier_blocks``: a modifier block in every other database folder where something is written and all of it
  comes to nothing. A block left empty on purpose (a REPLACE without lines) is not dead.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterator, Mapping
from functools import cache
from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList, Value
from eu5gameparser.load_order import DataProfile, LoadOrderConfig, load_merged_directory, load_profile

from prosper_or_perish_constructor.vanilla_food_productivity import _InGameStaticModifiersLayer, script_values

PROFILE = "constructor"
# Not modifier objects (scripts hold them by name, the rest is text and art); advances have their own check, a building's
# blocks share one card (tests/test_building_effects.py).
DEAD_BLOCK_SKIPPED_DIRS = {
    "script_values", "modifier_type_definitions", "modifier_icons", "defines", "on_action", "scripted_effects",
    "scripted_triggers", "customizable_localization", "trigger_localization", "coat_of_arms", "persistent_dna",
    "ethnicities", "languages", "advances", "building_types",
}
# Folders whose objects are themselves the modifier block.
BLOCK_OBJECT_DIRS = {"static_modifiers", "auto_modifiers"}
# All that mod/pp/in_game/common/gods/hellenism.txt adds to vanilla's file: the omen sits inside the god, so an inject or
# REPLACE of zeus_god could register it twice (a REPLACE leaves the nested objects of vanilla's block registered).
ZEUS_OMEN_LINES = (
    b"\t\t\t\tglobal_wheat_output_modifier = 0.1\n"
    b"\t\t\t\tglobal_olives_output_modifier = 0.1\n"
)
# Keys of an advance that put nothing on its card. `pure_tooltip_entry` shows in the tooltip's header only; what
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
        if item.key not in STRUCTURAL_KEYS:
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


def is_dead_block(block: CList, values: Mapping[str, float], modifier_types: Collection[str]) -> bool:
    """Modifier lines are written in the block and all of them come to nothing."""
    totals: dict[str, float] = defaultdict(float)
    for item in block.entries:
        if item.key not in modifier_types or isinstance(item.value, CList):
            continue
        value = item.value
        if isinstance(value, str) and value in values and values[value] == values[value]:
            value = values[value]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            totals[item.key] += float(value)
        elif value is True or value == "yes" or str(value).startswith("@") or str(value) in values:
            return False
        else:   # `no`, or a name the game cannot read
            totals[item.key] += 0.0
    return bool(totals) and all(abs(total) <= 1e-9 for total in totals.values())


def _modifier_blocks(value: CList, path: str = "") -> Iterator[tuple[str, CList]]:
    for item in value.entries:
        if isinstance(item.value, CList):
            here = f"{path}/{item.key}" if path else item.key
            if "modifier" in item.key or item.key == "satisfaction":
                yield here, item.value
            yield from _modifier_blocks(item.value, here)


def dead_modifier_blocks(load_order_path: Path) -> list[str]:
    """One line per dead modifier block: its folder, object and block."""
    config = LoadOrderConfig.load(load_order_path)
    vanilla, mod = config.layer("vanilla"), config.layer(PROFILE)
    game = config.vanilla_root / "game"
    values = script_values(game, mod.root)
    profile = DataProfile(PROFILE, (vanilla, mod))
    modifier_types = {
        entry.key for entry in load_merged_directory(profile, "modifier_type_definitions", scope="main_menu").entries
    }
    dead: list[str] = []
    for scope in ("main_menu", "in_game"):
        names: set[str] = set()
        for base in (game / scope / "common", mod.root / scope / "common"):
            if base.is_dir():
                names |= {path.name for path in base.iterdir() if path.is_dir()}
        for directory in sorted(names - DEAD_BLOCK_SKIPPED_DIRS):
            if (scope, directory) == ("in_game", "static_modifiers"):
                continue  # read with the main_menu folder
            layers = profile
            if (scope, directory) == ("main_menu", "static_modifiers"):
                in_game = _InGameStaticModifiersLayer(id=f"{PROFILE}_in_game", name=mod.name, root=mod.root, kind="mod")
                layers = DataProfile(PROFILE, (vanilla, mod, in_game))
            for entry in load_merged_directory(layers, directory, scope=scope).entries:
                if not isinstance(entry.value, CList):
                    continue
                blocks = list(_modifier_blocks(entry.value))
                if directory in BLOCK_OBJECT_DIRS:
                    blocks.append(("", entry.value))
                dead.extend(
                    f"{directory} {entry.key} {path or '(the object)'} ({Path(entry.source_file).name})"
                    for path, block in blocks
                    if is_dead_block(block, values, modifier_types)
                )
    return sorted(dead)
