"""Offline evaluation of the mod's location script values, for tests (2026-10-28, Jan: the bars and the farm caps must
be checked by what they compute, not by the shape of the generated text).

``ScriptEval`` reads the script values and scripted triggers the mod writes and evaluates them for a location given as
a plain dict, the way the engine does: an accumulator per block (``value`` sets it; ``add``, ``subtract``,
``multiply``, ``divide``; ``min`` / ``max`` are the lower / upper bound; ``floor``), ``if`` / ``else_if`` / ``else``,
script values by name, ``this.`` links, ``owner ?= { ... }`` and the building list ``every_buildings_in_location``.
Anything else raises ``Unknown``, so a generated file that uses a construct the evaluator does not know fails its test
instead of passing on a guess.

A location context::

    {
        "game": {"population": 49.94, "development": 27.4, "climate": "oceanic", ...},   # game values and classes
        "modifiers": {"local_population_capacity": 59.17, "pp_levels_cattle_farm": 21},  # modifier:<type>
        "location_modifiers": {"pp_wb_fertility_moderate"},                               # has_location_modifier
        "buildings": {"cattle_farm": {"level": 21, "queued": 0}},                         # queued = levels under construction
        "can_build": {"field_management"},                                                 # can_build_building here
        "owner": {"modifiers": {...}, "can_build": {"field_management"}} or None,
    }
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

LEVEL = re.compile(r"location_building_level\(building_type:(\w+)\)")
UNEMPLOYED = re.compile(r"unemployed_pops_of_pop_type_in_location\(pop_type:(\w+)\)")
_REPLACE = ("REPLACE_OR_CREATE:", "TRY_REPLACE:", "REPLACE:")


class Unknown(ValueError):
    """A construct the evaluator does not model."""


def _entries(node: CList):
    """(key, op, value, safe) per entry; ``x ?= { }`` comes out of the parser as key '?' with x in the items."""
    pending = iter(node.items)
    for entry in node.entries:
        if entry.key == "?":
            yield next(pending), "=", entry.value, True
        else:
            yield entry.key, entry.op, entry.value, False


def _read(paths: list[Path]) -> dict[str, CList]:
    found: dict[str, CList] = {}
    for path in paths:
        for entry in parse_file(path).entries:
            key = str(entry.key)
            for prefix in _REPLACE:
                key = key.removeprefix(prefix)
            if isinstance(entry.value, CList):
                found[key] = entry.value
    return found


class ScriptEval:
    def __init__(self, mod_root: Path):
        self.values = _read(sorted((mod_root / "in_game/common/script_values").glob("*.txt")))
        self.triggers = _read(sorted((mod_root / "in_game/common/scripted_triggers").glob("*.txt")))

    # --- values -------------------------------------------------------------------------------------------------

    def value(self, expr: Any, ctx: dict) -> float:
        """A value expression in a scope: a number, a name, a link or a block."""
        if isinstance(expr, bool):
            raise Unknown(f"boolean as value: {expr}")
        if isinstance(expr, (int, float)):
            return float(expr)
        if isinstance(expr, CList):
            return self.block(expr, ctx, 0.0)
        name = str(expr)
        if name.startswith(("this.", "root.")):
            name = name.split(".", 1)[1]
        if name.startswith("modifier:"):
            return float(ctx.get("modifiers", {}).get(name[9:], 0.0))
        match = LEVEL.fullmatch(name)
        if match:
            return float(ctx.get("buildings", {}).get(match[1], {}).get("level", 0.0))
        match = UNEMPLOYED.fullmatch(name)
        if match:
            return float(ctx["game"][f"unemployed_{match[1]}"])
        if name in ctx.get("game", {}):
            return float(ctx["game"][name])
        if name in self.values:
            return self.block(self.values[name], ctx, 0.0)
        raise Unknown(f"value {name}")

    def block(self, node: CList, ctx: dict, result: float) -> float:
        matched = False
        for key, op, v, safe in _entries(node):
            if key in ("desc", "limit"):
                continue
            if key in ("if", "else_if", "else"):
                if key == "if":
                    matched = False
                elif matched:
                    continue
                if key == "else" or self.test(v.first("limit"), ctx):
                    result = self.block(v, ctx, result)
                    matched = True
                continue
            matched = False
            if key == "owner":
                if not safe:
                    raise Unknown("owner = { } in a value (only owner ?= { } is used)")
                if ctx.get("owner") is not None:
                    result = self.block(v, ctx["owner"], result)
                continue
            if key == "every_buildings_in_location":
                for building, state in ctx.get("buildings", {}).items():
                    scope = {"building_type": building, **state}
                    if self.test(v.first("limit"), scope):
                        result = self.block(v, scope, result)
                continue
            result = self.op(key, v, ctx, result)
        return result

    def op(self, key: str, v: Any, ctx: dict, result: float) -> float:
        if key == "floor":
            return float(math.floor(result + 1e-9))
        if key == "ceiling":
            return float(math.ceil(result - 1e-9))
        n = self.value(v, ctx)
        if key == "value":
            return n
        if key == "add":
            return result + n
        if key == "subtract":
            return result - n
        if key == "multiply":
            return result * n
        if key == "divide":
            if n == 0:
                raise Unknown("division by zero")
            return result / n
        if key == "min":
            return max(result, n)      # the engine's min is the lower bound
        if key == "max":
            return min(result, n)
        raise Unknown(f"operation {key}")

    # --- triggers -----------------------------------------------------------------------------------------------

    def test(self, node: Any, ctx: dict) -> bool:
        if node is None:
            return True
        if not isinstance(node, CList):
            raise Unknown(f"trigger block expected, got {node!r}")
        return all(self.single(key, op, v, safe, ctx) for key, op, v, safe in _entries(node))

    def single(self, key: str, op: str, v: Any, safe: bool, ctx: dict) -> bool:
        if key in ("AND", "limit"):
            return self.test(v, ctx)
        if key == "OR":
            return any(self.single(k, o, x, s, ctx) for k, o, x, s in _entries(v))
        if key == "NOT":
            return not self.test(v, ctx)
        if key == "NOR":
            return not any(self.single(k, o, x, s, ctx) for k, o, x, s in _entries(v))
        if key == "owner":
            owner = ctx.get("owner")
            if owner is None:
                if safe:
                    return False
                raise Unknown("owner = { } without an owner")
            return self.test(v, owner)
        if key == "has_building":
            return ctx.get("buildings", {}).get(str(v).split(":")[-1], {}).get("level", 0) > 0
        if key == "can_build_building":
            return str(v).split(":")[-1] in ctx.get("can_build", set())
        if key == "has_location_modifier":
            return str(v) in ctx.get("location_modifiers", set())
        if key == "building_type" and "building_type" in ctx:
            return ctx["building_type"] == str(v).split(":")[-1]
        if key == "building_levels_under_construction" and "building_type" in ctx:
            return self.compare(float(ctx.get("queued", 0)), op, self.value(v, ctx))
        if key in self.triggers:
            wanted = v is True or str(v) == "yes"        # the parser reads yes / no as booleans
            return self.test(self.triggers[key], ctx) == wanted
        if isinstance(ctx.get("game", {}).get(key), str):
            return ctx["game"][key] == str(v).split(":")[-1]
        return self.compare(self.value(key, ctx), op, self.value(v, ctx))

    @staticmethod
    def compare(left: float, op: str, right: float) -> bool:
        if op == "=":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        raise Unknown(f"comparison {op}")
