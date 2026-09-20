"""Parsers for the vanilla game-start setup (cities and buildings, town setups).

Kept from the retired setup-corrections generator for tests that check the mod's game-start culling against
vanilla's placements. Read-only; nothing here writes mod files.
"""

from __future__ import annotations

import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass


class SetupModelError(RuntimeError):
    pass


KEY_BLOCK_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*\{")
TOKEN_RE = re.compile(r"\b(?P<key>[A-Za-z0-9_:.+-]+)\s*=\s*(?P<value>[A-Za-z0-9_:.+-]+)")
TOWN_SETUP_RE = re.compile(r"\btown_setup\s*=\s*(?P<key>[A-Za-z0-9_:.+-]+)")
LOCATION_RE = re.compile(r"\blocation\s*=\s*(?P<key>[A-Za-z0-9_:.+-]+)")
LEVEL_RE = re.compile(r"\blevel\s*=\s*(?P<value>-?\d+)")


def _require_single_block(lines: list[str], key: str) -> LineBlock:
    blocks = [block for block in _child_blocks(lines, 0, len(lines)) if block.key == key]
    if len(blocks) != 1:
        raise SetupModelError(f"expected one {key} block, found {len(blocks)}")
    return blocks[0]


def _child_blocks(lines: list[str], start: int, end: int) -> list[LineBlock]:
    blocks: list[LineBlock] = []
    depth = 0
    current_key: str | None = None
    current_start = -1
    for index in range(start, end):
        code = _code(lines[index])
        if current_key is None and depth == 0:
            match = KEY_BLOCK_RE.match(code)
            if match is not None:
                current_key = match.group("key")
                current_start = index
        depth += code.count("{") - code.count("}")
        if current_key is not None and depth == 0:
            blocks.append(LineBlock(current_key, current_start, index + 1))
            current_key = None
            current_start = -1
        if depth < 0:
            raise SetupModelError(f"unbalanced braces near line {index + 1}")
    if current_key is not None or depth != 0:
        raise SetupModelError("unbalanced braces while reading setup blocks")
    return blocks


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return next(iter(match.groupdict().values()))


def _code(line: str) -> str:
    return line.split("#", 1)[0]



@dataclass(frozen=True)
class LineBlock:
    key: str
    start: int
    end: int


@dataclass(frozen=True)
class LocationEntry:
    location: str
    start: int
    end: int
    town_setup: str | None


@dataclass(frozen=True)
class DirectBuildingEntry:
    index: int
    building: str
    location: str
    level: int
    start: int
    end: int


@dataclass(frozen=True)
class TownSetupDefinition:
    key: str
    copy_from: str | None
    levels: OrderedDict[str, int]


@dataclass(frozen=True)
class LocationTemplate:
    key: str
    raw_material: str | None
    vegetation: str | None
    topography: str | None
    climate: str | None


@dataclass
class SetupModel:
    lines: list[str]
    locations: dict[str, LocationEntry]
    direct_entries: list[DirectBuildingEntry]

    @property
    def direct_by_location_building(self) -> dict[tuple[str, str], list[DirectBuildingEntry]]:
        grouped: dict[tuple[str, str], list[DirectBuildingEntry]] = defaultdict(list)
        for entry in self.direct_entries:
            grouped[(entry.location, entry.building)].append(entry)
        return grouped



def parse_setup_model(text: str) -> SetupModel:
    lines = text.splitlines(keepends=True)
    locations_block = _require_single_block(lines, "locations")
    building_manager_block = _require_single_block(lines, "building_manager")

    locations: dict[str, LocationEntry] = {}
    for block in _child_blocks(lines, locations_block.start + 1, locations_block.end - 1):
        block_text = "".join(lines[block.start : block.end])
        town_setup = _first_match(TOWN_SETUP_RE, block_text)
        locations[block.key] = LocationEntry(
            location=block.key,
            start=block.start,
            end=block.end,
            town_setup=town_setup,
        )

    direct_entries: list[DirectBuildingEntry] = []
    for block in _child_blocks(lines, building_manager_block.start + 1, building_manager_block.end - 1):
        block_text = "".join(lines[block.start : block.end])
        location = _first_match(LOCATION_RE, block_text)
        level_text = _first_match(LEVEL_RE, block_text)
        if location is None or level_text is None:
            continue
        direct_entries.append(
            DirectBuildingEntry(
                index=len(direct_entries),
                building=block.key,
                location=location,
                level=int(level_text),
                start=block.start,
                end=block.end,
            )
        )

    return SetupModel(lines=lines, locations=locations, direct_entries=direct_entries)



def parse_town_setups(text: str) -> OrderedDict[str, TownSetupDefinition]:
    lines = text.splitlines(keepends=True)
    definitions: OrderedDict[str, TownSetupDefinition] = OrderedDict()
    for block in _child_blocks(lines, 0, len(lines)):
        copy_from: str | None = None
        levels: OrderedDict[str, int] = OrderedDict()
        for raw_line in lines[block.start + 1 : block.end - 1]:
            line = _code(raw_line).strip()
            if not line:
                continue
            match = TOKEN_RE.match(line)
            if match is None:
                continue
            key = match.group("key")
            value = match.group("value")
            if key == "copy_from":
                copy_from = value
                continue
            try:
                level = int(value)
            except ValueError:
                continue
            levels[key] = levels.get(key, 0) + level
        definitions[block.key] = TownSetupDefinition(block.key, copy_from, levels)
    return definitions



def expand_town_setup(
    key: str,
    definitions: dict[str, TownSetupDefinition],
    stack: tuple[str, ...] = (),
) -> OrderedDict[str, int]:
    if key in stack:
        chain = " -> ".join((*stack, key))
        raise SetupModelError(f"recursive town_setup copy_from chain: {chain}")
    if key not in definitions:
        raise SetupModelError(f"unknown town_setup: {key}")

    definition = definitions[key]
    expanded: OrderedDict[str, int] = OrderedDict()
    if definition.copy_from is not None:
        expanded.update(expand_town_setup(definition.copy_from, definitions, (*stack, key)))

    for building, level in definition.levels.items():
        if building in expanded:
            expanded[building] += level
        else:
            expanded[building] = level
    return expanded
