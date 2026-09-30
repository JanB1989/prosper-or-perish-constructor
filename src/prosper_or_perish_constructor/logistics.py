"""Logistics: the buildings that carry goods to the market produce the ``logistics`` good and raise market access.

Each logistics blueprint carries a ``logistics`` tag::

    logistics:
      class: overland        # a class of [logistics.classes] in constructor.toml
      bulky_scale: 1.5       # optional multiplier on the class's bulky-goods cut (default 1)

``ppc logistics apply`` rewrites the tagged accepted blueprints so that, per level,

- every production method costs ``input_cost`` gold at base prices (default market prices with the
  ``[blueprint_evaluation.price_overrides]``: manual labour and the floor-pinned dummy goods at 1 gold); each good keeps
  its share of the cost, goods are rounded to readable steps and manual labour absorbs the rounding;
- every method produces ``logistics``: ``input_cost x class output``, the last method of the slot (the improved one, the
  gate method) ``input_cost x (class output + improved_method_bonus)``;
- ``raw_modifier`` holds only ``local_market_access`` (not scaled by staffing: a staffed or demanding building keeps
  its market access);
- ``modifier`` holds the bulky-goods output cut (class cut x bulky_scale, half on ``bulky_half_goods``) and the flavour
  lines;
- ``allow`` gains ``market_access < gate_max_market_access`` and ``total_building_levels >= gate_min_building_levels``
  (other conditions stay);
- ``increase_per_level_cost`` comes from the class, ``pop_type`` and ``employment_size`` from the section.

The rewrite is a fixed point: a second apply changes nothing. ``ppc logistics check`` reports blueprints apply would
change and problems (unknown classes, untagged buildings that produce logistics, unpriced inputs); ``ppc build`` prints
it. Run it after ``ppc labour apply`` (which sets the manual-labour share) and before ``ppc gate apply``.

The overland buildings split the map into zones (``pp_logistics_zone_*`` scripted triggers, geography only);
``zone_membership`` evaluates those triggers over every location for the check and the tests.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
import math
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping, Sequence

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import yaml_io
from prosper_or_perish_constructor.production_labour import GOODS_STEPS, format_amount, nice

CONFIG_SECTION = "logistics"
TAG = "logistics"
BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
REPORT_RELATIVE_PATH = Path("artifacts/data/logistics/logistics.csv")
ZONE_TRIGGERS_RELATIVE = Path("in_game/common/scripted_triggers/pp_logistics_zone_triggers.txt")
ZONE_PREFIX = "pp_logistics_zone_"
ZONE_ANY = "pp_logistics_zone_any"
METHOD_KEYS = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "no_upkeep", "ai_will_do"}
COST_TOLERANCE = 0.01  # gold: a method within this of input_cost is on target
INDENT = "  "

_HEADER_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][A-Za-z_0-9:]*)\s*=\s*\{")
_SCALAR_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][A-Za-z_0-9]*)\s*=\s*(?P<value>[^\s{}#]+)(?P<tail>[ \t]*(?:#.*)?)$")
_ALLOW_OWN_RE = re.compile(r"^\s*(market_access|total_building_levels)\s*[<>=!]")


# ---------------------------------------------------------------- config


@dataclass(frozen=True)
class LogisticsClass:
    name: str
    output: float  # output as a multiple of the input cost
    bulky_cut: float  # per level, on every bulky good's local output
    increase_per_level_cost: float


@dataclass(frozen=True)
class LogisticsConfig:
    good: str
    input_cost: float
    market_access: float
    gate_max_market_access: float
    gate_min_building_levels: int
    improved_method_bonus: float
    bulky_goods: tuple[str, ...]
    bulky_half_goods: tuple[str, ...]
    flavour: tuple[tuple[str, float], ...]
    pop_type: str
    employment_size: float
    classes: dict[str, LogisticsClass]


def load_config(project: Path) -> LogisticsConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION)
    if not isinstance(section, dict) or not isinstance(section.get("classes"), dict):
        raise ValueError(f"{project}: [{CONFIG_SECTION}] with a [{CONFIG_SECTION}.classes] table is required")
    classes: dict[str, LogisticsClass] = {}
    for name, value in section["classes"].items():
        if not isinstance(value, dict) or not {"output", "bulky_cut", "increase_per_level_cost"} <= set(value):
            raise ValueError(f"{project}: {CONFIG_SECTION}.classes.{name} needs output, bulky_cut and increase_per_level_cost")
        classes[name] = LogisticsClass(
            name, float(value["output"]), float(value["bulky_cut"]), float(value["increase_per_level_cost"])
        )
    flavour = section.get("flavour") or {}
    return LogisticsConfig(
        good=str(section.get("good", "logistics")),
        input_cost=float(section["input_cost"]),
        market_access=float(section["market_access"]),
        gate_max_market_access=float(section["gate_max_market_access"]),
        gate_min_building_levels=int(section["gate_min_building_levels"]),
        improved_method_bonus=float(section.get("improved_method_bonus", 0.0)),
        bulky_goods=tuple(str(g) for g in section.get("bulky_goods", ())),
        bulky_half_goods=tuple(str(g) for g in section.get("bulky_half_goods", ())),
        flavour=tuple((str(k), float(v)) for k, v in flavour.items()),
        pop_type=str(section.get("pop_type", "laborers")),
        employment_size=float(section.get("employment_size", 1)),
        classes=classes,
    )


def load_prices(repo: Path, project: Path) -> dict[str, float]:
    """Base prices as the blueprint evaluation and the gate read them (manual labour and floor goods at 1 gold)."""
    from prosper_or_perish_constructor import production_gate

    return production_gate.load_prices(repo, project)


# ---------------------------------------------------------------- blueprints


def enabled_blueprints(repo: Path) -> list[Path]:
    manifest = yaml_io.safe_load((repo / MANIFEST_RELATIVE).read_text(encoding="utf-8-sig")) or {}
    enabled = manifest.get("enabled") or {}
    return [repo / BLUEPRINT_ROOT_RELATIVE / entry for entry, on in enabled.items() if on and str(entry).startswith("buildings/")]


@dataclass(frozen=True)
class Tag:
    cls: str
    bulky_scale: float = 1.0


def blueprint_tag(data: Mapping[str, Any], name: str) -> Tag | None:
    tag = data.get(TAG)
    if tag is None:
        return None
    if isinstance(tag, str):
        return Tag(tag)
    if not isinstance(tag, dict) or not tag.get("class"):
        raise ValueError(f"{name}: {TAG} must be a class name or a mapping with class (and bulky_scale)")
    return Tag(str(tag["class"]), float(tag.get("bulky_scale", 1.0)))


# ---------------------------------------------------------------- body text model


def _code(line: str) -> str:
    quoted = False
    for i, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            return line[:i]
    return line


def _delta(line: str) -> int:
    code = re.sub(r'"[^"]*"', "", _code(line))
    return code.count("{") - code.count("}")


def _block_end(lines: Sequence[str], start: int) -> int:
    """Index of the line closing the block that opens on ``start``."""
    depth = 0
    for i in range(start, len(lines)):
        depth += _delta(lines[i])
        if depth <= 0:
            return i
    raise ValueError(f"line {start + 1}: block does not close")


def _top_blocks(lines: Sequence[str], key: str) -> list[tuple[int, int]]:
    """(start, end) of every depth-0 ``key = {`` block."""
    out: list[tuple[int, int]] = []
    depth = 0
    i = 0
    while i < len(lines):
        match = _HEADER_RE.match(lines[i]) if depth == 0 else None
        if match and match.group("key") == key:
            end = _block_end(lines, i)
            out.append((i, end))
            i = end + 1
            continue
        depth += _delta(lines[i])
        i += 1
    return out


def _top_scalar(lines: Sequence[str], key: str) -> int | None:
    depth = 0
    for i, line in enumerate(lines):
        if depth == 0:
            match = _SCALAR_RE.match(line)
            if match and match.group("key") == key:
                return i
        depth += _delta(line)
    return None


def _inner_lines(lines: Sequence[str], start: int, end: int) -> list[str]:
    """The lines between a block's braces (a one-line block yields its inner text as one line)."""
    if start == end:
        inner = _code(lines[start]).split("{", 1)[1].rsplit("}", 1)[0].strip()
        return [inner] if inner else []
    return list(lines[start + 1 : end])


@dataclass
class MethodText:
    name: str
    start: int  # header line
    end: int  # closing line
    inputs: dict[str, float]  # positive goods lines, in file order
    produced: str | None
    output: float | None


def _methods(lines: Sequence[str]) -> list[list[MethodText]]:
    """Slots (unique_production_methods blocks) with their methods."""
    slots: list[list[MethodText]] = []
    for start, end in _top_blocks(lines, "unique_production_methods"):
        methods: list[MethodText] = []
        i = start + 1
        while i < end:
            match = _HEADER_RE.match(lines[i])
            if not match:
                i += 1
                continue
            m_end = _block_end(lines, i)
            inputs: dict[str, float] = {}
            produced: str | None = None
            output: float | None = None
            depth = 0
            for row in lines[i + 1 : m_end]:
                if depth == 0:
                    scalar = _SCALAR_RE.match(row)
                    if scalar:
                        key, value = scalar.group("key"), scalar.group("value")
                        if key == "produced":
                            produced = value
                        elif key == "output":
                            output = _number(value)
                        elif key not in METHOD_KEYS and (_number(value) or 0) > 0:
                            inputs[key] = float(value)
                depth += _delta(row)
            methods.append(MethodText(match.group("key"), i, m_end, inputs, produced, output))
            i = m_end + 1
        slots.append(methods)
    return slots


# ---------------------------------------------------------------- planning


@dataclass
class MethodPlan:
    name: str
    cost_before: float
    amounts: dict[str, float]
    cost: float
    output: float
    improved: bool
    labour: float


@dataclass
class Plan:
    blueprint: Path
    building: str
    tag: Tag
    methods: list[MethodPlan] = field(default_factory=list)
    modifier: list[tuple[str, float]] = field(default_factory=list)
    increase_per_level_cost: float = 0.0
    new_text: str | None = None  # the rewritten blueprint text
    changed: bool = False
    problems: list[str] = field(default_factory=list)


@dataclass
class LogisticsResult:
    plans: list[Plan] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    files_changed: int = 0

    @property
    def changed(self) -> list[Plan]:
        return [p for p in self.plans if p.changed]


LABOUR_GOOD = "manual_labor"


def scale_inputs(inputs: Mapping[str, float], prices: Mapping[str, float], target: float, labour_good: str = LABOUR_GOOD) -> dict[str, float]:
    """Scale ``inputs`` so they cost ``target`` at ``prices``; each good keeps its share. Goods round to readable steps
    (two decimals, three below 0.1) and manual labour absorbs the rounding to 0.01."""
    cost = sum(a * prices[g] for g, a in inputs.items())
    if cost <= 0:
        return dict(inputs)
    factor = target / cost
    labour_price = prices.get(labour_good, 1.0)
    out: dict[str, float] = {}
    for good, amount in inputs.items():
        if good == labour_good:
            continue
        out[good] = nice(amount * factor, GOODS_STEPS)
    if labour_good in inputs:
        rest = target - sum(a * prices[g] for g, a in out.items())
        exact = max(rest, 0.0) / labour_price
        out[labour_good] = float((Decimal(str(exact)) / Decimal("0.01")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("0.01"))
        out = {g: out[g] for g in inputs}  # file order
    return out


def plan_modifier(config: LogisticsConfig, cls: LogisticsClass, bulky_scale: float) -> list[tuple[str, float]]:
    cut = cls.bulky_cut * bulky_scale
    lines = [(f"local_{good}_output_modifier", -_round(cut)) for good in config.bulky_goods]
    lines += [(f"local_{good}_output_modifier", -_round(cut / 2)) for good in config.bulky_half_goods]
    lines += list(config.flavour)
    return lines


def plan_blueprint(path: Path, config: LogisticsConfig, prices: Mapping[str, float]) -> Plan | None:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    data = yaml_io.safe_load(text) or {}
    tag = blueprint_tag(data, path.name)
    if tag is None:
        return None
    building = data.get("building") if isinstance(data.get("building"), dict) else {}
    plan = Plan(path, str(building.get("key") or data.get("tag") or path.stem), tag)
    cls = config.classes.get(tag.cls)
    if cls is None:
        plan.problems.append(f"{TAG} class {tag.cls!r} is not in [{CONFIG_SECTION}.classes]")
        return plan
    body = str(building.get("body") or "")
    if not body.strip():
        plan.problems.append("building.body is empty")
        return plan
    try:
        new_body, plan = _rewrite_body(body, plan, cls, config, prices)
    except ValueError as exc:
        plan.problems.append(str(exc))
        return plan
    plan.increase_per_level_cost = cls.increase_per_level_cost
    if new_body != body:
        from prosper_or_perish_constructor.production_gate import _body_region

        lines = text.split("\n")
        first, stop, indent = _body_region(lines)
        body_lines = new_body.split("\n")
        lines[first:stop] = [(" " * indent + line) if line.strip() else "" for line in body_lines]
        plan.new_text = "\n".join(lines)
        plan.changed = True
    return plan


def _rewrite_body(body: str, plan: Plan, cls: LogisticsClass, config: LogisticsConfig, prices: Mapping[str, float]) -> tuple[str, Plan]:
    lines = body.split("\n")
    slots = _methods(lines)
    if len(slots) != 1 or not slots[0]:
        raise ValueError(f"expected one unique_production_methods slot with methods, found {len(slots)}")
    if _top_blocks(lines, "possible_production_methods"):
        raise ValueError("logistics buildings keep their methods in unique_production_methods only")
    methods = slots[0]
    for index, method in enumerate(methods):
        missing = [g for g in method.inputs if g not in prices]
        if missing:
            raise ValueError(f"{method.name}: unpriced inputs {', '.join(missing)}")
        if not method.inputs:
            raise ValueError(f"{method.name}: no goods inputs to scale")
        improved = index == len(methods) - 1 and len(methods) > 1
        amounts = scale_inputs(method.inputs, prices, config.input_cost)
        output = round(config.input_cost * (cls.output + (config.improved_method_bonus if improved else 0.0)), 4)
        plan.methods.append(
            MethodPlan(
                name=method.name,
                cost_before=sum(a * prices[g] for g, a in method.inputs.items()),
                amounts=amounts,
                cost=sum(a * prices[g] for g, a in amounts.items()),
                output=output,
                improved=improved,
                labour=amounts.get(LABOUR_GOOD, 0.0),
            )
        )
    plan.modifier = plan_modifier(config, cls, plan.tag.bulky_scale)

    # methods, bottom up so line numbers stay valid
    for method, target in sorted(zip(methods, plan.methods), key=lambda pair: -pair[0].start):
        lines[method.start : method.end + 1] = _method_block(lines[method.start : method.end + 1], target, config.good)

    lines = _set_block(lines, "raw_modifier", [f"local_market_access = {format_amount(config.market_access)}"])
    lines = _set_block(lines, "modifier", [f"{key} = {format_amount(value)}" for key, value in plan.modifier])
    lines = _merge_allow(lines, config)
    lines = _set_scalar(lines, "increase_per_level_cost", f"{cls.increase_per_level_cost:.2f}", after="max_levels")
    lines = _set_scalar(lines, "pop_type", config.pop_type, after="increase_per_level_cost")
    lines = _set_scalar(lines, "employment_size", format_amount(config.employment_size), after="pop_type")
    return "\n".join(lines), plan


def _method_block(block: list[str], target: MethodPlan, good: str) -> list[str]:
    header = block[0]
    inner = block[1:-1]
    indent = next((row[: len(row) - len(row.lstrip())] for row in inner if row.strip()), None)
    if indent is None:
        indent = header[: len(header) - len(header.lstrip())] + INDENT
    goods: list[str] = []
    rest: list[str] = []
    seen: set[str] = set()
    depth = 0
    for row in inner:
        at_top = depth == 0
        depth += _delta(row)
        scalar = _SCALAR_RE.match(row) if at_top else None
        key = scalar.group("key") if scalar else None
        if key in {"produced", "output"}:
            continue
        if key in target.amounts:
            goods.append(f"{scalar.group('indent')}{key} = {format_amount(target.amounts[key])}{scalar.group('tail')}")
            seen.add(key)
            continue
        rest.append(row)
    goods += [f"{indent}{g} = {format_amount(a)}" for g, a in target.amounts.items() if g not in seen]
    produced = [f"{indent}produced = {good}", f"{indent}output = {format_amount(target.output)}"]
    return [header, *goods, *produced, *rest, block[-1]]


def _set_block(lines: list[str], key: str, inner: list[str]) -> list[str]:
    block = [f"{key} = {{", *[f"{INDENT}{row}" for row in inner], "}"]
    spans = _top_blocks(lines, key)
    if spans:
        start, end = spans[0]
        out = lines[:start] + block + lines[end + 1 :]
        for s, e in reversed(_top_blocks(out, key)[1:]):  # a second block of the same key would add to the first
            del out[s : e + 1]
        return out
    at = len(lines)
    while at > 0 and not lines[at - 1].strip():
        at -= 1
    return lines[:at] + ["", *block] + lines[at:]


def _merge_allow(lines: list[str], config: LogisticsConfig) -> list[str]:
    own = [
        f"market_access < {format_amount(config.gate_max_market_access)}",
        f"total_building_levels >= {config.gate_min_building_levels}",
    ]
    spans = _top_blocks(lines, "allow")
    if spans:
        start, end = spans[0]
        kept = [row for row in _inner_lines(lines, start, end) if not _ALLOW_OWN_RE.match(row)]
        kept = [row if start != end else f"{INDENT}{row}" for row in kept]
        return lines[:start] + ["allow = {", *kept, *[f"{INDENT}{row}" for row in own], "}"] + lines[end + 1 :]
    anchor = _top_blocks(lines, "location_potential")
    at = anchor[0][1] + 1 if anchor else next((s for s, _ in _top_blocks(lines, "unique_production_methods")), len(lines))
    return lines[:at] + ["allow = {", *[f"{INDENT}{row}" for row in own], "}"] + lines[at:]


def _set_scalar(lines: list[str], key: str, value: str, *, after: str) -> list[str]:
    at = _top_scalar(lines, key)
    if at is not None:
        match = _SCALAR_RE.match(lines[at])
        lines[at] = f"{match.group('indent')}{key} = {value}{match.group('tail')}"
        return lines
    anchor = _top_scalar(lines, after)
    position = anchor + 1 if anchor is not None else 0
    return lines[:position] + [f"{key} = {value}"] + lines[position:]


# ---------------------------------------------------------------- repo pass


def plan_all(repo: Path, config: LogisticsConfig, prices: Mapping[str, float]) -> LogisticsResult:
    result = LogisticsResult()
    for path in enabled_blueprints(repo):
        if not path.is_file():
            continue
        try:
            plan = plan_blueprint(path, config, prices)
        except ValueError as exc:
            result.problems.append(f"{path.name}: {exc}")
            continue
        if plan is None:
            text = path.read_text(encoding="utf-8-sig")
            if re.search(rf"^\s*produced\s*=\s*{re.escape(config.good)}\s*$", text, re.MULTILINE):
                result.problems.append(f"{path.name}: produces {config.good} without a {TAG} tag")
            continue
        result.plans.append(plan)
        result.problems.extend(f"{path.name}: {p}" for p in plan.problems)
    for good in (*config.bulky_goods, *config.bulky_half_goods):
        if good not in prices:
            result.problems.append(f"[{CONFIG_SECTION}] bulky good {good!r} is not a trade good")
    return result


def apply(repo: Path, project: Path, prices: Mapping[str, float] | None = None, *, write: bool = True) -> LogisticsResult:
    config = load_config(project)
    prices = dict(prices) if prices is not None else load_prices(repo, project)
    if config.good not in prices:
        raise ValueError(f"[{CONFIG_SECTION}] good {config.good!r} is not a trade good of the load order")
    result = plan_all(repo, config, prices)
    if write and not result.problems:
        for plan in result.changed:
            raw = plan.blueprint.read_bytes()
            bom = raw.startswith(b"\xef\xbb\xbf")
            crlf = b"\r\n" in raw
            new = plan.new_text.replace("\n", "\r\n") if crlf else plan.new_text
            plan.blueprint.write_text(("﻿" if bom else "") + new, encoding="utf-8", newline="")
            result.files_changed += 1
        again = plan_all(repo, config, prices)
        if again.changed:
            raise ValueError(f"logistics apply is not stable: {[p.blueprint.name for p in again.changed]}")
        write_report(repo / REPORT_RELATIVE_PATH, again.plans, prices)
        for plan, fresh in zip(result.plans, again.plans):
            fresh.changed = plan.changed
        result.plans = again.plans
    return result


def write_report(path: Path, plans: Sequence[Plan], prices: Mapping[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["building", "class", "method", "improved", "input_cost", "labour", "output", "profit", "increase_per_level_cost", "goods", "blueprint"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for plan in plans:
            for method in plan.methods:
                writer.writerow({
                    "building": plan.building,
                    "class": plan.tag.cls,
                    "method": method.name,
                    "improved": method.improved,
                    "input_cost": round(method.cost, 3),
                    "labour": format_amount(method.labour),
                    "output": format_amount(method.output),
                    "profit": round(method.output * prices.get("logistics", 1.0) - method.cost, 3),
                    "increase_per_level_cost": plan.increase_per_level_cost,
                    "goods": " ".join(f"{g}={format_amount(a)}" for g, a in method.amounts.items() if g != LABOUR_GOOD),
                    "blueprint": plan.blueprint.name,
                })


# ---------------------------------------------------------------- zones


@dataclass(frozen=True)
class Location:
    tag: str
    climate: str
    topography: str
    vegetation: str
    area: str | None
    region: str | None
    sub_continent: str | None
    continent: str | None


def load_locations(repo: Path, project: Path) -> list[Location]:
    """Every land location of the World Builder handover with its game geography (area, region, sub-continent)."""
    from eu5gameparser.savegame.hierarchy import load_location_hierarchy

    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    handover = (repo / str((raw.get("worldbuilder") or {}).get("handover", "../EU5WorldBuilder/artifacts/handover/latest"))).resolve()
    parser = raw.get("parser") or {}
    hierarchy = load_location_hierarchy(
        str(parser.get("profile", "constructor")), repo / str(parser.get("load_order", "constructor.load_order.toml"))
    )
    out: list[Location] = []
    with (handover / "location_attributes.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            where = hierarchy.get(row["location_tag"]) or {}
            out.append(
                Location(
                    row["location_tag"], row["climate"], row["topography"], row["vegetation"],
                    where.get("area"), where.get("region"), where.get("macro_region"), where.get("super_region"),
                )
            )
    return out


def load_zone_triggers(path: Path) -> dict[str, CList]:
    return {entry.key: entry.value for entry in parse_file(path).entries if isinstance(entry.value, CList)}


_GEOGRAPHY = {"area": "area", "region": "region", "sub_continent": "sub_continent", "continent": "continent"}


def evaluate(block: CList, location: Location, triggers: Mapping[str, CList]) -> bool:
    """All entries of ``block`` hold (the implicit AND of a trigger block)."""
    return all(_holds(entry.key, entry.value, location, triggers) for entry in block.entries)


def _holds(key: str, value: Any, location: Location, triggers: Mapping[str, CList]) -> bool:
    if key == "AND":
        return evaluate(value, location, triggers)
    if key == "OR":
        return any(_holds(e.key, e.value, location, triggers) for e in value.entries)
    if key == "NOT":
        return not evaluate(value, location, triggers)
    if key == "NOR":
        return not any(_holds(e.key, e.value, location, triggers) for e in value.entries)
    if key in {"climate", "topography", "vegetation"}:
        return getattr(location, key) == str(value)
    if key in _GEOGRAPHY:
        text = str(value)
        prefix = f"{_GEOGRAPHY[key]}:"
        if not text.startswith(prefix):
            raise ValueError(f"{key} = {text}: expected {prefix}<name>")
        return getattr(location, key) == text[len(prefix):]
    if key in triggers:
        result = evaluate(triggers[key], location, triggers)
        return result if str(value) in {"yes", "True", "true"} else not result
    raise ValueError(f"zone trigger key {key!r} is not supported (geography only)")


def zone_membership(locations: Sequence[Location], triggers: Mapping[str, CList]) -> dict[str, list[str]]:
    """Zone trigger name -> locations inside it (``pp_logistics_zone_any`` excluded)."""
    zones = [name for name in triggers if name.startswith(ZONE_PREFIX) and name != ZONE_ANY]
    return {zone: [loc.tag for loc in locations if evaluate(triggers[zone], loc, triggers)] for zone in zones}


# ---------------------------------------------------------------- helpers


def _round(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
