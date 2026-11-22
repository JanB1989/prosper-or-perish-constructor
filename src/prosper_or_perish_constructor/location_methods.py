"""Production methods tied to a location: ``location_allow`` (2026-11-22, Jan; tested in game the same day).

A unique production method with ``location_allow = { <trigger> }`` (location scope) may only run in a location where the
trigger holds. The game checks it when a building is created (a new building, an upgrade, the game start), when the AI
values a building, when the player picks a method and when the AI's method switch moves a building; a running building
is never checked again, so a gate names only what never changes (soil, climate, vegetation, topography, river, coast).
A new, upgraded or game-start building takes in every slot the best allowed method whose inputs are in the market, else
the allowed method with the largest output, else the slot's first method.

Rules for the blueprints (``tests/test_location_gated_methods.py``, docs/mod_authoring_rules.md "Location-gated
methods"):

- the gated method has a slot of its own: an ungated method without goods or output listed first, the gated method
  second, nothing else (the AI's switch picks one favourite per slot whatever the gate, so a gated method in a shared
  slot froze every building outside the gate);
- never the building's gate slot (the Market leg) and never alone in a slot (a one-method slot runs without any check);
- every building that replaces it (``obsolete``) carries a method with the same gate;
- the gated method pays where it runs at the labour price the game sees (a losing method is left only slowly);
- no script sets a production method (``set_production_method`` ignores the gate and the building stays there);
- for a gate of several conditions the method's description says where it works (the game's tooltip names one failed
  condition, but an ``OR`` only says the requirements are not met).

The calculators that read recipes outside the game count a gated method only where its gate holds (``holds``: start
market stock) or leave it out (tier prices, Old Ways copies, the gate pass's base slots and main good, the
Construction Plan's market limit); the Construction Plan's business estimate wraps the method's profit in its gate.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

GATE = "location_allow"
BUILDING_TYPES = Path("in_game/common/building_types")
_TOKEN = re.compile(r"([A-Za-z0-9_:.@\-]+)\s*\??=\s*\{|\{|\}")
_CLASS_PREFIX = re.compile(r"^ha1300_(?:climate|veg|topo)_")
CLASS_KEYS = ("climate", "vegetation", "topography")
FLAG_KEYS = ("has_river", "is_coastal", "is_adjacent_to_lake")


class Unreadable(ValueError):
    """A gate condition the offline evaluation does not know."""


def gates_in_text(text: str) -> dict[str, str]:
    """Method name -> the inner text of its ``location_allow`` block (comments dropped, whitespace collapsed), for every
    method of a building file or blueprint body."""
    code = re.sub(r"#[^\n]*", "", text)
    stack: list[tuple[str | None, int]] = []
    found: dict[str, str] = {}
    for match in _TOKEN.finditer(code):
        if match.group(1):
            stack.append((match.group(1), match.end()))
        elif match.group(0) == "{":
            stack.append((None, match.end()))
        elif stack:
            key, start = stack.pop()
            if key == GATE and stack and stack[-1][0]:
                found[stack[-1][0]] = " ".join(code[start:match.start()].split())
    return found


def building_type_files(repo: Path, project: Path) -> list[Path]:
    """The building type files the game loads: vanilla and its DLC folders, then the compiled mod."""
    import tomllib

    from prosper_or_perish_constructor.building_footprint import vanilla_files
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    mod_root = repo / str((raw.get("project") or {}).get("mod_root", "mod"))
    return [*vanilla_files(vanilla_root(repo, project), BUILDING_TYPES), *sorted((mod_root / BUILDING_TYPES).glob("*.txt"))]


def game_gates(paths: Iterable[Path]) -> dict[str, str]:
    """Method name -> gate text over these files (later files win, as the game's REPLACE and INJECT copies do)."""
    found: dict[str, str] = {}
    for path in paths:
        found.update(gates_in_text(path.read_text(encoding="utf-8-sig")))
    return found


def gated_method_names(profile: str, load_order_path: Path) -> frozenset[str]:
    """The location-gated unique methods of the building types a load order merges (for the reports that read the
    parser's method tables, which carry no gate: they leave these out, as if outside every gate)."""
    from eu5gameparser.load_order import load_merged_directory, load_profile

    merged = load_merged_directory(load_profile(profile, load_order_path=load_order_path), "building_types")
    names: set[str] = set()
    for building in merged.entries:
        if not isinstance(building.value, CList):
            continue
        for group in building.value.values("unique_production_methods"):
            if isinstance(group, CList):
                names.update(m.key for m in group.entries if isinstance(m.value, CList) and m.value.first(GATE) is not None)
    return frozenset(names)


@lru_cache(maxsize=None)
def parse_gate(text: str) -> CList:
    return parse_text(f"gate = {{ {text} }}\n").entries[0].value


def _entries(node: CList) -> Iterator[tuple[str, Any]]:
    # the parser keeps a safe-equality ``key ?= value`` as an entry named "?" with the key in ``items``
    pending = iter(node.items)
    for entry in node.entries:
        yield (next(pending, "?") if entry.key == "?" else entry.key), entry.value


def class_name(value: Any) -> str:
    """A climate, vegetation or topography key as the World Builder names its class (``ha1300_veg_mixed_forest`` ->
    ``mixed_forest``; vanilla keys stay)."""
    return _CLASS_PREFIX.sub("", str(value))


def holds(gate: str | CList, facts: Mapping[str, Any]) -> bool:
    """Whether the gate holds for a location. ``facts``: ``climate`` / ``vegetation`` / ``topography`` (World Builder class
    names), ``has_river`` / ``is_coastal`` / ``is_adjacent_to_lake`` (bools), ``modifiers`` (the location's setup
    modifiers, e.g. ``pp_wb_soil_peat``) and ``market_goods`` (the goods its market produces; None when unknown).
    Raises ``Unreadable`` for any other condition."""
    node = parse_gate(gate) if isinstance(gate, str) else gate
    return all(_single(key, value, facts) for key, value in _entries(node))


def _single(key: str, value: Any, facts: Mapping[str, Any]) -> bool:
    upper = key.upper()
    if upper == "AND" and isinstance(value, CList):
        return holds(value, facts)
    if upper == "OR" and isinstance(value, CList):
        return any(_single(k, v, facts) for k, v in _entries(value))
    if upper == "NOT" and isinstance(value, CList):
        return not holds(value, facts)
    if upper == "NOR" and isinstance(value, CList):
        return not any(_single(k, v, facts) for k, v in _entries(value))
    if key in CLASS_KEYS:
        return class_name(value) == facts.get(key)
    if key in FLAG_KEYS:
        return bool(facts.get(key)) == (value is True or str(value) == "yes")
    if key == "has_location_modifier":
        return str(value) in facts.get("modifiers", ())
    if key == "market" and isinstance(value, CList):
        if facts.get("market_goods") is None:
            raise Unreadable("market")
        return holds(value, facts)
    if key in ("is_produced_in_market", "is_produced_in_location_market"):
        goods = facts.get("market_goods")
        if goods is None:
            raise Unreadable(key)
        return str(value).split(":")[-1] in goods
    raise Unreadable(key)


def allowed(gate: str | None, facts: Mapping[str, Any]) -> bool:
    """An ungated method runs everywhere; a gated one where its gate holds (a condition the evaluation cannot read
    counts as not allowed)."""
    if gate is None:
        return True
    try:
        return holds(gate, facts)
    except Unreadable:
        return False


def attribute_facts(row: Mapping[str, str]) -> dict[str, Any]:
    """A location's facts from its World Builder ``location_attributes.csv`` row (the setup gives every location its
    ``pp_wb_soil_<soil>`` and ``pp_wb_fertility_<fertility>`` modifiers)."""
    modifiers = {f"pp_wb_soil_{row['soil_type']}"} if row.get("soil_type") else set()
    if row.get("fertility"):
        modifiers.add(f"pp_wb_fertility_{row['fertility']}")
    return {
        "climate": row.get("climate") or None,
        "vegetation": row.get("vegetation") or None,
        "topography": row.get("topography") or None,
        "has_river": int(float(row.get("river_level") or 0)) > 0,
        "is_coastal": str(row.get("is_coastal", "")).lower() == "true",
        "is_adjacent_to_lake": str(row.get("is_adjacent_to_lake", "")).lower() == "true",
        "modifiers": frozenset(modifiers),
    }
