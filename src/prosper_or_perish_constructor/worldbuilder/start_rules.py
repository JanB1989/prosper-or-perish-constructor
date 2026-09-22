"""Conservative offline evaluation of the actual game-start caps and gates.

Unknown syntax fails closed and is reported. Engine-only RGO size and market
access use zero lower bounds; this may underplace buildings, never grants room.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import yaml
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile


class Unresolved(ValueError):
    pass


def first(node, key, default=None):
    return next(iter(node.values(key)), default) if isinstance(node, CList) else default


def entries(node):
    # The parser represents the game's safe-equality '?=' as an anonymous entry
    # with the left-hand identifier in items. Treat that as ordinary equality.
    pending = iter(node.items)
    for entry in node.entries:
        key = next(pending, "?") if entry.key == "?" else entry.key
        yield key, entry.op, entry.value


class Rules:
    def __init__(self, repo, project):
        import tomllib

        cfg = tomllib.loads(project.read_text())
        order = repo / cfg.get("parser", {}).get(
            "load_order", "constructor.load_order.toml"
        )
        profile = load_profile("constructor", load_order_path=order)

        def merged(name, scope="in_game"):
            return {
                e.key: e.value
                for e in load_merged_directory(
                    profile, name, scope=scope, include_scalars=True
                ).entries
            }

        self.values = merged("script_values", "main_menu") | merged("script_values")
        self.triggers = merged("scripted_triggers")
        self.buildings = merged("building_types")
        self.statics = merged("static_modifiers", "main_menu") | merged(
            "static_modifiers"
        )
        self.towns = merged("town_setups")
        self.ranks = merged("location_ranks")
        self.goods = merged("goods")
        # Location classes carry local_monthly_food_modifier rows (vanilla plus the mod's cancelling injects).
        self.classes = {
            "climate": merged("climates"),
            "vegetation": merged("vegetation"),
            "topography": merged("topography"),
        }
        from eu5gameparser.clausewitz.parser import parse_file

        # Defines merge per namespace/key, unlike ordinary common databases.
        # The generic directory merger replaces repeated NLocation blocks.
        defines = {}
        paths = {}
        for layer in profile.layers:
            base = layer.root / "game" if layer.kind == "vanilla" else layer.root
            for path in sorted((base / "loading_screen/common/defines").glob("*.txt")):
                paths[path.name] = path
        for name, path in sorted(paths.items()):
            for group in parse_file(path).entries:
                if isinstance(group.value, CList):
                    for entry in group.value.entries:
                        defines[group.key, entry.key] = entry.value
        self.subsistence = float(defines["NLocation", "SUBSISTENCE_AGRICULTURE"])
        self.unsupported = Counter()
        self.footprint_classes = cfg["building_footprint"]["classes"]
        self.footprints = {}
        enabled = yaml.safe_load(
            (repo / "blueprints/buildings.manifest.yml").read_text()
        )["enabled"]
        # Accepted blueprints are authoritative before the normal render step.
        for path in sorted((repo / "blueprints/accepted/buildings").glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
            b = data.get("building", {})
            self.footprints[b.get("key", path.stem)] = data.get("footprint")
            if (
                enabled.get("buildings/" + path.name)
                and b.get("mode") in ("CREATE", "REPLACE")
                and b.get("body")
                and b.get("key")
            ):
                self.buildings[b["key"]] = CList(
                    entries=parse_text(b["body"]).entries, items=[]
                )

    def value(self, value, ctx, depth=0):
        if depth > 40:
            raise Unresolved("recursive scripted value")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, CList):
            result = 0.0
            matched = False
            for key, _, v in entries(value):
                if key in ("desc", "limit"):
                    continue
                if key in ("if", "else_if", "else"):
                    if key == "if":
                        matched = False
                    active = (key == "if" or not matched) and (
                        key == "else" or self.test(first(v, "limit"), ctx, depth + 1)
                    )
                    if active:
                        result = self._ops(v, ctx, result, depth + 1)
                        matched = True
                    continue
                result = self.op(key, v, ctx, result, depth + 1)
            return result
        key = str(value)
        if key in ctx:
            return float(ctx[key])
        if key.startswith("modifier:"):
            return float(ctx.get("modifiers", {}).get(key[9:], 0))
        if key.startswith(("owner.modifier:", "scope:owner.modifier:")):
            return 0.0
        if key.startswith("var:"):
            return float(ctx.get("variables", {}).get(key[4:], 0))
        match = re.fullmatch(r"location_building_level\(building_type:(\w+)\)", key)
        if match:
            return float(ctx.get("buildings", {}).get(match[1], 0))
        if key == "total_building_levels":
            return sum(ctx.get("buildings", {}).values())
        if key in self.values:
            return self.value(self.values[key], ctx, depth + 1)
        raise Unresolved("value " + key)

    def _ops(self, node, ctx, result, depth):
        # Keep the accumulator when entering a conditional script-value block.
        matched = False
        for key, _, v in entries(node):
            if key in ("limit", "desc"):
                continue
            if key in ("if", "else_if", "else"):
                if key == "if":
                    matched = False
                active = (key == "if" or not matched) and (
                    key == "else" or self.test(first(v, "limit"), ctx, depth + 1)
                )
                if active:
                    result = self._ops(v, ctx, result, depth + 1)
                    matched = True
            else:
                result = self.op(key, v, ctx, result, depth + 1)
        return result

    def op(self, key, v, ctx, result, depth):
        if key == "floor":
            return math.floor(result + 1e-9)
        if key == "ceiling":
            return math.ceil(result - 1e-9)
        if key == "round":
            return round(result)
        n = self.value(v, ctx, depth)
        if key == "value":
            return n
        if key == "add":
            return result + n
        if key == "subtract":
            return result - n
        if key == "multiply":
            return result * n
        if key == "divide":
            if not n:
                raise Unresolved("division by zero")
            return result / n
        if key == "min":
            return max(result, n)  # EU5: lower bound
        if key == "max":
            return min(result, n)
        raise Unresolved("operation " + key)

    def test(self, node, ctx, depth=0):
        if node is None:
            return True
        if depth > 40:
            raise Unresolved("recursive trigger")
        if not isinstance(node, CList):
            raise Unresolved("non-block trigger")

        def single(key, op, v):
            if key == "text":
                return True
            if key in ("AND", "limit", "custom_tooltip"):
                return self.test(v, ctx, depth + 1)
            if key == "OR":
                return any(single(*e) for e in entries(v))
            if key == "NOT":
                return not self.test(v, ctx, depth + 1)
            if key == "NOR":
                return not any(single(*e) for e in entries(v))
            if key == "always":
                return bool(v)
            if key in self.triggers:
                trigger = self.triggers[key]
                if isinstance(v, CList):
                    from eu5gameparser.clausewitz.serializer import render_value

                    text = render_value(trigger)
                    for arg in v.entries:
                        text = text.replace("$" + arg.key + "$", str(arg.value))
                    trigger = parse_text("trigger = " + text).entries[0].value
                return self.test(trigger, ctx, depth + 1) == bool(v)
            if key == "any_neighbor_location":
                return any(self.test(v, n, depth + 1) for n in ctx.get("neighbors", []))
            if key == "has_variable":
                return str(v) in ctx.get("variables", {})
            if key == "has_building":
                return ctx.get("buildings", {}).get(str(v).split(":")[-1], 0) > 0
            if key == "has_location_modifier":
                return str(v) in ctx.get("static_modifiers", set())
            if key == "has_town_rights":
                return str(v).split(":")[-1] in ctx.get("town_rights", set())
            if key == "exists":
                return str(v) == "owner" and bool(ctx.get("owner"))
            if key == "owner":
                # No assumed country technologies or event flags at the start.
                return self.test(
                    v,
                    {"variables": {}, "buildings": {}, "has_advance": False},
                    depth + 1,
                )
            if key == "has_advance":
                return False
            if key == "current_age":
                return str(v).split(":")[-1] == "age_1_traditions"
            if key == "current_age_or_later":
                return first(v, "age") == "age_1_traditions"
            if key == "this":
                return ctx.get("location_tag") == str(v).split(":")[-1]
            if key in ctx and not isinstance(v, CList):
                actual = ctx[key]
                expected = str(v).split(":")[-1] if isinstance(v, str) else v
            elif key.startswith(("modifier:", "var:", "owner.modifier:")):
                actual = self.value(key, ctx, depth + 1)
                expected = self.value(v, ctx, depth + 1)
            else:
                raise Unresolved("trigger " + key)
            if op == "=":
                return actual == expected
            if op == "!=":
                return actual != expected
            if op == ">":
                return actual > expected
            if op == ">=":
                return actual >= expected
            if op == "<":
                return actual < expected
            if op == "<=":
                return actual <= expected
            raise Unresolved("comparison " + op)

        return all(single(*entry) for entry in entries(node))

    def cap(self, key, ctx, *, gates=True):
        try:
            body = self.buildings[key]
            if gates:
                if (
                    first(body, ctx.get("location_rank", "rural_settlement"), False)
                    is not True
                ):
                    return 0
                if not self.test(first(body, "location_potential"), ctx):
                    return 0
                if not self.test(first(body, "allow"), ctx):
                    return 0
            value = first(body, "max_levels")
            if value is None:
                raise Unresolved("missing max_levels")
            result = self.value(value, ctx)
            if ctx.get("initializing") and key in (
                "victuals_market",
                "victuals_market_import",
            ):
                # Navigation state variables are seeded by on_game_start, after
                # setup buildings: do not spend that extra room prematurely.
                result = min(result, self.value(value, {**ctx, "neighbors": []}))
            return max(0, math.floor(result + 1e-8))
        except (Unresolved, KeyError) as exc:
            self.unsupported[f"{key}: {exc}"] += 1
            return 0

    def number(self, key, field, default=0):
        body = self.buildings.get(key)
        value = first(body, field, default)
        return (
            self.value(value, {})
            if not isinstance(value, str) or value in self.values
            else value
        )

    def modifiers(self, key, section="modifier"):
        body = self.buildings.get(key)
        result = defaultdict(float)
        for block in body.values(section) if body else []:
            if not isinstance(block, CList):
                continue
            for entry in block.entries:
                if isinstance(entry.value, (int, float)):
                    result[entry.key] += entry.value
        if section == "raw_modifier" and key in self.footprints:
            share = self.footprint_classes.get(self.footprints[key], "ignore")
            if share != "ignore":
                from decimal import Decimal

                from prosper_or_perish_constructor.building_footprint import (
                    capacity_per_level,
                )

                result["local_population_capacity"] = float(
                    capacity_per_level(
                        Decimal(str(share)),
                        Decimal(str(self.number(key, "employment_size", 0))),
                    )
                )
        return dict(result)

    def numbers(self, key):
        return {
            "employment_size": float(self.number(key, "employment_size", 0)),
            "pop_type": self.number(key, "pop_type", "laborers"),
            "local_monthly_food": self.modifiers(key).get("local_monthly_food", 0),
        }

    def victuals_pop_factors(self, good="victuals"):
        """Monthly demand per 1,000 pops of each type from the good's ``demand_add`` x ``demand_multiply``
        (the game's nominal demand; the start config scales it to what the market actually shows)."""
        body = getattr(self, "goods", {}).get(good)
        adds, mults = {}, {}
        for block in body.values("demand_add") if isinstance(body, CList) else []:
            if isinstance(block, CList):
                adds.update({e.key: float(e.value) for e in block.entries if isinstance(e.value, (int, float))})
        for block in body.values("demand_multiply") if isinstance(body, CList) else []:
            if isinstance(block, CList):
                mults.update({e.key: float(e.value) for e in block.entries if isinstance(e.value, (int, float))})
        return {kind: add * mults.get(kind, 1.0) for kind, add in adds.items()}

    def food_modifier(self, rank, classes):
        """Sum of ``local_monthly_food_modifier`` from the rank and the location's classes
        (``{"climate": key, "vegetation": key, "topography": key}``); scales all local food, subsistence included."""

        def rows(body, section):
            total = 0.0
            for block in body.values(section) if isinstance(body, CList) else []:
                if isinstance(block, CList):
                    for entry in block.entries:
                        if entry.key == "local_monthly_food_modifier" and isinstance(entry.value, (int, float)):
                            total += float(entry.value)
            return total

        total = rows(getattr(self, "ranks", {}).get(rank), "rank_modifier")
        for kind, key in (classes or {}).items():
            if key:
                total += rows(getattr(self, "classes", {}).get(kind, {}).get(str(key)), "location_modifier")
        return total
