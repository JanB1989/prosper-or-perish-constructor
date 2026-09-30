"""Production gate: the one production method that decides the AI's "too low profit margin" check.

When the AI weighs building a production building it walks the building's production-method slots (the
``possible_production_methods`` group first, then every ``unique_production_methods`` block in file order) and, inside
a slot, the methods in listed order. A slot with one method is always looked at; in a slot with more, a method is
looked at only while it is allowed and the local market supplies all its inputs. Every method it looks at that has an
output good overwrites one margin (revenue / input cost at market prices); below ``NAI.AI_BUILDING_PROFIT_THRESHOLD``
(vanilla 1.2, read from the mod's defines) the building gets no build utility. So exactly one method gates the build: the last one looked at that has an output.
(docs/ai_building_rulebook.md, section 2.4i.)

A method locked behind an unresearched advance counts as not allowed; with no margin written the gate reads 0.
Method order changes nothing else about the build decision (the profit estimate takes each slot's best method).

Every enabled blueprint with a producing unique method names that method::

    gate_method: pp_wheat_farm_market_sales

Gate leg (``[production_gate.leg]``, 2026-09-30): a building with a market main good (``main_good``) ends in a one-method
slot ``pp_<building>_market_sales`` that makes a little of that good for a floor-pinned dummy at ``leg.margin``. It is
always read, so the check follows the main good's market price for new buildings and new levels alike, whatever is
researched or supplied. ``apply`` adds, updates or drops the leg (body block, slot list, localization, evaluation
allow rules) and flags it; buildings without a market good, storage-leg gates and ``strategic_goods`` keep the rule
below. The old Provision gate bought the building's own crop, so the AI stopped building farms when the crop was dear.

``ppc gate apply`` rewrites the body so the flagged method gates: its slot becomes the last unique block and the method
is listed last in it. Everything else is ordered by importance, bottom = most important:

- slots: base slots at the top (every producing method pays only ``base_inputs``, e.g. ``*_base``), then the other
  slots by their highest output value at base prices, the dynamic slots (a method produces one of ``dynamic_goods``: the
  storage legs Surplus Sales and Scarcity Premium, the Provisioning switch) at the bottom, the flagged slot last;
- methods: output-less methods first (idle choices never gate), then by output value, the flagged method last.

Ties keep the file order. Methods never move between slots, amounts never change (the leg is written whole). The slot labels
(``<building>_slot_<n>``), the ``production_method_slots`` list and ``# slot <n>`` comments follow their slot. A
blueprint without the flag gets the method the same order puts last (``apply`` writes it, ``check`` reports it).
``ppc gate check`` reports missing or invalid flags and blueprints whose order differs; ``ppc build`` prints it.
The crop farm generator (``crop_farms.py``) renders the same order through ``order_mapping``.
"""

from __future__ import annotations

import csv
import json
import math
import re
import tomllib
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import yaml_io

CONFIG_SECTION = "production_gate"
FLAG = "gate_method"
BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
REPORT_RELATIVE_PATH = Path("artifacts/data/production_gate/gate.csv")
METHOD_KEYS = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "no_upkeep", "ai_will_do"}
UNIQUE = "unique_production_methods"
POSSIBLE = "possible_production_methods"

_HEADER_RE = re.compile(r"^\s*(?P<key>[A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{")
_SLOT_COMMENT_RE = re.compile(r"(?i)\b(slot) (\d+)\b")
_TOP_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z_0-9]*):(?:\s|$)")


class GateError(ValueError):
    """A blueprint body the gate pass cannot rewrite safely."""


# ---------------------------------------------------------------- config


@dataclass(frozen=True)
class LegConfig:
    """[production_gate.leg]: the gate leg, a one-method last slot that makes a little of the building's main good."""

    margin: float = 1.0  # revenue / input cost at base prices
    value: float = 0.01  # output worth this much gold per level at base prices
    input: str = "offset"  # a floor-pinned dummy good: the leg's cost never moves
    slot_label: str = "Market"
    method_name: str = "Market Sales"
    method_desc: str = "A few hands carry a small share of the produce straight to market. It pays only while the goods fetch a good price."


@dataclass(frozen=True)
class GateConfig:
    threshold: float = 1.2
    dynamic_goods: frozenset[str] = frozenset({"province_food_sales", "province_food_purchase"})
    base_inputs: frozenset[str] = frozenset({"manual_labor"})
    price_overrides: Mapping[str, float] = field(default_factory=dict)
    pinned_goods: frozenset[str] = frozenset({"local_food", "offset", "logistics"})
    strategic_goods: frozenset[str] = frozenset()
    leg: LegConfig | None = None


THRESHOLD_DEFINE = "AI_BUILDING_PROFIT_THRESHOLD"
DEFINES_RELATIVE = Path("loading_screen/common/defines")


def load_threshold(project: Path, fallback: float = 1.2) -> float:
    """``NAI.AI_BUILDING_PROFIT_THRESHOLD`` as the game loads it: the compiled mod's defines, else vanilla's, else
    ``fallback`` (the [production_gate] threshold)."""
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    repo = project.parent
    roots = [repo / str((raw.get("project") or {}).get("mod_root", "mod")) / DEFINES_RELATIVE]
    try:
        from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

        vanilla = Path(vanilla_root(repo, project))
        roots += [vanilla / DEFINES_RELATIVE, vanilla / "game" / DEFINES_RELATIVE]
    except Exception:  # noqa: BLE001 - no load order (test repos): the mod's defines and the fallback remain
        pass
    pattern = re.compile(rf"^\s*{THRESHOLD_DEFINE}\s*=\s*(-?[0-9.]+)", re.MULTILINE)
    for root in roots:
        if not root.is_dir():
            continue
        values = [float(m.group(1)) for path in sorted(root.glob("*.txt")) for m in pattern.finditer(_read(path))]
        if values:
            return values[-1]  # files load in name order; the last value wins
    return fallback


def load_config(project: Path) -> GateConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION) or {}
    evaluation = raw.get("blueprint_evaluation") or {}
    default = GateConfig()
    leg = section.get("leg")
    return GateConfig(
        threshold=load_threshold(project, float(section.get("threshold", default.threshold))),
        dynamic_goods=frozenset(str(g) for g in section.get("dynamic_goods", default.dynamic_goods)),
        base_inputs=frozenset(str(g) for g in evaluation.get("base_method_input_goods", default.base_inputs)),
        price_overrides={str(k): float(v) for k, v in dict(evaluation.get("price_overrides") or {}).items()},
        pinned_goods=frozenset(str(g) for g in section.get("pinned_goods", default.pinned_goods)),
        strategic_goods=frozenset(str(g) for g in section.get("strategic_goods", default.strategic_goods)),
        leg=LegConfig(**{k: (float(v) if k in {"margin", "value"} else str(v)) for k, v in dict(leg).items()}) if isinstance(leg, dict) else None,
    )


def gate_prices(prices: Mapping[str, float], config: GateConfig) -> dict[str, float]:
    """Base prices as the blueprint evaluation reads them: default market prices with the evaluation overrides."""
    return {**prices, **config.price_overrides}


def load_prices(repo: Path, project: Path, config: GateConfig | None = None) -> dict[str, float]:
    from prosper_or_perish_constructor import production_labour

    return gate_prices(production_labour.load_prices(repo, project), config or load_config(project))


# ---------------------------------------------------------------- body model


@dataclass(frozen=True)
class Method:
    name: str
    produced: str | None
    output: float | None
    inputs: Mapping[str, float]  # numeric input lines, zero amounts included

    @property
    def has_output(self) -> bool:
        return self.produced is not None

    def value(self, prices: Mapping[str, float]) -> float:
        if self.produced is None or not self.output:
            return 0.0
        return float(self.output) * float(prices.get(self.produced, 0.0))

    def cost(self, prices: Mapping[str, float]) -> float:
        return sum(amount * float(prices.get(good, 0.0)) for good, amount in self.inputs.items() if amount > 0)

    def margin(self, prices: Mapping[str, float]) -> float:
        """Revenue / input cost at base prices, as the AI's gate reads it (input cost floored at 0.001)."""
        return self.value(prices) / max(self.cost(prices), 0.001)


@dataclass(frozen=True)
class Slot:
    methods: tuple[Method, ...]

    def names(self) -> list[str]:
        return [m.name for m in self.methods]


def body_slots(body: str, source: Path | str = "<body>") -> tuple[list[Slot], bool]:
    """(unique slots in file order, whether a possible_production_methods group exists)."""
    block = parse_text(f"x = {{\n{body}\n}}\n", Path(str(source))).entries[0].value
    if not isinstance(block, CList):
        return [], False
    slots: list[Slot] = []
    for group in block.values(UNIQUE):
        if not isinstance(group, CList):
            continue
        methods: list[Method] = []
        for entry in group.entries:
            if not isinstance(entry.value, CList):
                continue
            inputs: dict[str, float] = {}
            for item in entry.value.entries:
                if item.key in METHOD_KEYS or isinstance(item.value, CList):
                    continue
                number = _number(item.value)
                if number is not None:
                    inputs[item.key] = number
            produced = entry.value.first("produced")
            methods.append(
                Method(
                    name=entry.key,
                    produced=str(produced) if produced is not None and not isinstance(produced, CList) else None,
                    output=_number(entry.value.first("output")),
                    inputs=inputs,
                )
            )
        slots.append(Slot(tuple(methods)))
    has_possible = any(True for _ in block.values(POSSIBLE))
    return slots, has_possible


def is_production(slots: Sequence[Slot]) -> bool:
    return any(m.has_output for slot in slots for m in slot.methods)


# ---------------------------------------------------------------- importance


def slot_class(slot: Slot, config: GateConfig) -> int:
    """0 = base slot, 1 = ordinary, 2 = dynamic (reacts to the province store or the market)."""
    producing = [m for m in slot.methods if m.has_output]
    if any(m.produced in config.dynamic_goods for m in producing):
        return 2
    if producing and all(set(g for g, a in m.inputs.items() if a > 0) <= config.base_inputs for m in producing):
        return 0
    return 1


def slot_key(slot: Slot, config: GateConfig, prices: Mapping[str, float]) -> tuple[int, float]:
    return slot_class(slot, config), max((m.value(prices) for m in slot.methods), default=0.0)


def method_key(method: Method, prices: Mapping[str, float]) -> tuple[int, float]:
    return (1 if method.has_output else 0), method.value(prices)


def suggest_gate(slots: Sequence[Slot], config: GateConfig, prices: Mapping[str, float]) -> str | None:
    """The method the importance order puts last: in the most important slot, the most important method with an
    output. In a dynamic slot a method that buys its inputs (Provision, Scarcity Premium) beats a no-input dummy
    (Sell the Surplus), because the dummy earns nothing at an empty store."""
    candidates = [i for i, slot in enumerate(slots) if any(m.has_output for m in slot.methods)]
    if not candidates:
        return None
    best = max(candidates, key=lambda i: (slot_key(slots[i], config, prices), i))
    slot = slots[best]
    dynamic = slot_class(slot, config) == 2
    ranked = [
        (m.has_output, dynamic and any(g not in config.base_inputs and a > 0 for g, a in m.inputs.items()), m.value(prices), i)
        for i, m in enumerate(slot.methods)
    ]
    return slot.methods[max(ranked)[3]].name


# ---------------------------------------------------------------- the gate leg


LEG_SUFFIX = "_market_sales"


def leg_name(building: str) -> str:
    return f"pp_{building}{LEG_SUFFIX}"


def is_leg(method: str) -> bool:
    return method.startswith("pp_") and method.endswith(LEG_SUFFIX)


def without_legs(slots: Sequence[Slot]) -> list[Slot]:
    return [slot for slot in slots if not any(is_leg(m.name) for m in slot.methods)]


def main_good(slots: Sequence[Slot], config: GateConfig, prices: Mapping[str, float]) -> str | None:
    """The market good the building exists to make: its base method's good (a one-method slot paying only base inputs),
    else the good of its most valuable producing method. Floor-pinned dummies and storage-leg goods never count."""
    def signal(method: Method) -> bool:
        return (
            method.has_output
            and not is_leg(method.name)
            and method.produced not in config.pinned_goods
            and method.produced not in config.dynamic_goods
        )

    base = [
        m
        for slot in slots
        if len(slot.methods) == 1
        for m in slot.methods
        if signal(m) and {g for g, a in m.inputs.items() if a > 0} <= config.base_inputs
    ]
    pool = base or [m for slot in slots for m in slot.methods if signal(m)]
    if not pool:
        return None
    return max(pool, key=lambda m: m.value(prices)).produced  # ties: the first


@dataclass(frozen=True)
class Leg:
    name: str
    good: str
    output: float
    input: str
    amount: float

    def method(self) -> Method:
        return Method(self.name, self.good, self.output, {self.input: self.amount})

    def body_lines(self, header: str, method: str, inner: str) -> list[str]:
        return [
            f"{header}{UNIQUE} = {{",
            f"{method}{self.name} = {{",
            f"{inner}{self.input} = {_amount_text(self.amount)}",
            f"{inner}produced = {self.good}",
            f"{inner}output = {_amount_text(self.output)}",
            f"{inner}category = building_maintenance",
            f"{method}}}",
            f"{header}}}",
        ]


LEG_STEP = Decimal("0.001")  # method quantities keep at most three decimals


def _leg_amounts(value: float, price: float, margin: float, input_price: float) -> tuple[float, float]:
    """(output, input amount) in steps of 0.001, output worth ``value`` to twice that at base prices, picked so the
    rounded amounts hold ``margin`` as closely as the step allows."""
    low = max(1, math.ceil(value / price / float(LEG_STEP) - 1e-9))
    high = max(low, math.ceil(2 * value / price / float(LEG_STEP) - 1e-9))
    best: tuple[float, Decimal, Decimal] | None = None
    for k in range(low, high + 1):
        output = LEG_STEP * k
        amount = max((output * Decimal(str(price)) / Decimal(str(margin * input_price))).quantize(LEG_STEP, rounding=ROUND_HALF_UP), LEG_STEP)
        error = abs(float(output) * price / (float(amount) * input_price) - margin)
        if best is None or error < best[0] - 1e-12:
            best = (error, output, amount)
    return float(best[1]), float(best[2])


def _amount_text(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def plan_leg(building: str, slots: Sequence[Slot], flag: str | None, config: GateConfig, prices: Mapping[str, float]) -> Leg | None:
    """The gate leg the building should carry, or None.

    The AI's margin check reads the last method it looks at that has an output. A one-method slot is always looked at
    (no research, potential, allow or input check), so a leg as the last slot decides the check for new buildings and new
    levels alike: its margin is (1 + output modifiers) x the main good's market price / its base price x ``leg.margin``.
    None for buildings without a market good (services, floor-pinned dummies), whose main good the AI never gates
    (``strategic_goods``: ai_rgo_expansion_priority > 0), and deliberate storage gates (a flag on a storage-leg good)."""
    if config.leg is None:
        return None
    real = without_legs(slots)
    if flag and not is_leg(flag):
        where = locate(real, flag)
        if where is not None and real[where[0]].methods[where[1]].produced in config.dynamic_goods:
            return None
    good = main_good(real, config, prices)
    if good is None or good in config.strategic_goods:
        return None
    price = float(prices.get(good, 0.0))
    input_price = float(prices.get(config.leg.input, 0.0))
    if price <= 0 or input_price <= 0:
        raise GateError(f"{building}: no base price for {good if price <= 0 else config.leg.input}")
    output, amount = _leg_amounts(config.leg.value, price, config.leg.margin, input_price)
    return Leg(leg_name(building), good, output, config.leg.input, amount)


def leg_in_place(slots: Sequence[Slot], leg: Leg | None) -> bool:
    """The body carries exactly this leg (or none when ``leg`` is None) as a one-method slot."""
    legs = [(i, slot) for i, slot in enumerate(slots) if any(is_leg(m.name) for m in slot.methods)]
    if leg is None:
        return not legs
    return len(legs) == 1 and legs[0][1].methods == (leg.method(),)


def slots_with_leg(slots: Sequence[Slot], leg: Leg | None) -> list[Slot]:
    return without_legs(slots) + ([Slot((leg.method(),))] if leg else [])


def edit_leg_body(body: str, leg: Leg | None) -> str:
    """Drop every leg slot of the body and, with ``leg``, append it after the last unique_production_methods block."""
    lines = body.split("\n")
    blocks = _spans(lines)
    for block in reversed(blocks):
        names = [_HEADER_RE.match(lines[c.header]).group("key") for c in block.children]
        if names and all(is_leg(n) for n in names):
            start = block.start
            if start > 0 and not lines[start - 1].strip():
                start -= 1
            del lines[start : block.end + 1]
    if leg is None:
        return "\n".join(lines)
    blocks = _spans(lines)
    if not blocks:
        raise GateError("no unique_production_methods block to put the gate leg after")
    last = blocks[-1]
    header = re.match(r"^\s*", lines[last.header]).group(0)
    child = last.children[0] if last.children else None
    method = re.match(r"^\s*", lines[child.header]).group(0) if child else header + "    "
    if child and child.end > child.header and len(re.match(r"^\s*", lines[child.header + 1]).group(0)) > len(method):
        inner = re.match(r"^\s*", lines[child.header + 1]).group(0)
    else:
        inner = method + (method[len(header):] or "    ")
    lines[last.end + 1 : last.end + 1] = leg.body_lines(header, method, inner)
    return "\n".join(lines)


@dataclass(frozen=True)
class Order:
    slots: tuple[int, ...]  # old slot index per new position
    methods: tuple[tuple[int, ...], ...]  # per OLD slot index: old method index per new position

    def is_identity(self) -> bool:
        return self.slots == tuple(range(len(self.slots))) and all(
            m == tuple(range(len(m))) for m in self.methods
        )


def locate(slots: Sequence[Slot], method: str) -> tuple[int, int] | None:
    for s, slot in enumerate(slots):
        for m, candidate in enumerate(slot.methods):
            if candidate.name == method:
                return s, m
    return None


def plan_order(slots: Sequence[Slot], gate: str, config: GateConfig, prices: Mapping[str, float]) -> Order:
    where = locate(slots, gate)
    if where is None:
        raise GateError(f"{FLAG} {gate} is not a unique production method of the building")
    gate_slot, gate_method = where
    others = [i for i in range(len(slots)) if i != gate_slot]
    others.sort(key=lambda i: slot_key(slots[i], config, prices))  # stable: ties keep the file order
    methods: list[tuple[int, ...]] = []
    for s, slot in enumerate(slots):
        order = sorted(range(len(slot.methods)), key=lambda m: method_key(slot.methods[m], prices))
        if s == gate_slot:
            order = [m for m in order if m != gate_method] + [gate_method]
        methods.append(tuple(order))
    return Order(tuple(others + [gate_slot]), tuple(methods))


def ordered_slots(slots: Sequence[Slot], order: Order) -> list[Slot]:
    return [Slot(tuple(slots[s].methods[m] for m in order.methods[s])) for s in order.slots]


def gate_problems(slots: Sequence[Slot], gate: str | None, has_possible: bool) -> list[str]:
    """Structural problems of a flag against a body (the pytest reads these too)."""
    if not gate:
        return [f"no {FLAG}"]
    where = locate(slots, gate)
    if where is None:
        return [f"{FLAG} {gate} is not a unique production method of the building"]
    problems: list[str] = []
    method = slots[where[0]].methods[where[1]]
    if not method.has_output:
        problems.append(f"{FLAG} {gate} has no output good, so it never sets the margin")
    if has_possible:
        problems.append("a building with both possible and unique production methods is not supported by the gate pass")
    if where[0] != len(slots) - 1:
        problems.append(f"{gate} is in slot {where[0]}, not in the last slot ({len(slots) - 1})")
    if where[1] != len(slots[where[0]].methods) - 1:
        problems.append(f"{gate} is not listed last in its slot")
    return problems


# ---------------------------------------------------------------- body text rewriting


@dataclass
class _Span:
    start: int  # first line, attached comments included
    header: int  # the `x = {` line
    end: int  # the closing line
    children: list["_Span"] = field(default_factory=list)


def _code(line: str) -> str:
    """The line without its comment (a `#` outside quotes)."""
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


def _attach(lines: Sequence[str], header: int, floor: int) -> int:
    """First line of the comment run directly above ``header`` (no blank line between), not above ``floor``."""
    start = header
    while start - 1 >= floor and lines[start - 1].strip().startswith("#"):
        start -= 1
    return start


def _spans(lines: Sequence[str]) -> list[_Span]:
    """The unique_production_methods blocks of a body (depth 0) with their methods (depth 1)."""
    blocks: list[_Span] = []
    depth = 0
    i = 0
    floor = 0
    while i < len(lines):
        line = lines[i]
        match = _HEADER_RE.match(line) if depth == 0 else None
        if match and match.group("key") == UNIQUE:
            if _delta(line) != 1:
                raise GateError(f"line {i + 1}: a unique_production_methods block must open on its own line")
            block = _Span(_attach(lines, i, floor), i, -1)
            inner = 1
            j = i + 1
            inner_floor = j
            while j < len(lines):
                row = lines[j]
                if inner == 1 and row.strip() and not row.strip().startswith("#"):
                    head = _HEADER_RE.match(row)
                    if head is None:
                        if row.strip() == "}":
                            block.end = j
                            break
                        raise GateError(f"line {j + 1}: unexpected line in a unique_production_methods block: {row.strip()}")
                    start = _attach(lines, j, inner_floor)
                    level = 1 + _delta(row)
                    k = j
                    while level > 1:
                        k += 1
                        if k >= len(lines):
                            raise GateError(f"line {j + 1}: method {head.group('key')} does not close")
                        level += _delta(lines[k])
                    if level < 1:
                        raise GateError(f"line {k + 1}: the block closes on the method's last line")
                    block.children.append(_Span(start, j, k))
                    j = k + 1
                    inner_floor = j
                    continue
                inner += _delta(row)
                if inner == 0:
                    block.end = j
                    break
                j += 1
            if block.end < 0:
                raise GateError(f"line {i + 1}: unique_production_methods block does not close")
            blocks.append(block)
            i = block.end + 1
            floor = i
            continue
        depth += _delta(line)
        i += 1
    return blocks


def _renumber(lines: Sequence[str], old: int, new: int) -> list[str]:
    if old == new:
        return list(lines)
    return [_SLOT_COMMENT_RE.sub(lambda m: f"{m.group(1)} {new}" if int(m.group(2)) == old else m.group(0), line) for line in lines]


def reorder_body_lines(lines: Sequence[str], order: Order) -> list[str]:
    """The body lines with the unique blocks and their methods in ``order``; everything else stays in place."""
    blocks = _spans(lines)
    if len(blocks) != len(order.slots):
        raise GateError(f"found {len(blocks)} unique_production_methods blocks, expected {len(order.slots)}")
    out: list[str] = []
    cursor = 0
    for position, old in enumerate(order.slots):
        target = blocks[position]
        out.extend(lines[cursor : target.start])
        source = blocks[old]
        out.extend(_renumber(lines[source.start : source.header], old, position))
        methods = source.children
        if len(methods) != len(order.methods[old]):
            raise GateError(f"slot {old}: found {len(methods)} methods, expected {len(order.methods[old])}")
        inner = source.header
        for spot, method_index in enumerate(order.methods[old]):
            out.extend(lines[inner : methods[spot].start])
            chosen = methods[method_index]
            out.extend(lines[chosen.start : chosen.end + 1])
            inner = methods[spot].end + 1
        out.extend(lines[inner : source.end + 1])
        cursor = target.end + 1
    out.extend(lines[cursor:])
    return out


def reorder_body(body: str, order: Order) -> str:
    return "\n".join(reorder_body_lines(body.split("\n"), order))


# ---------------------------------------------------------------- blueprint text editing


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _top_key_line(lines: Sequence[str], key: str) -> int | None:
    return next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)


def _child_block(lines: Sequence[str], parent: int) -> tuple[int, int, int] | None:
    """(first, end exclusive, child indent) of the mapping under the top-level line ``parent``."""
    first = parent + 1
    end = first
    while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > 0 or lines[end].startswith("#")):
        end += 1
    child = next((_indent(lines[i]) for i in range(first, end) if lines[i].strip() and not lines[i].strip().startswith("#")), None)
    return None if child is None else (first, end, child)


def _key_in(lines: Sequence[str], lo: int, hi: int, indent: int, key: str) -> int | None:
    pattern = re.compile(rf"^ {{{indent}}}{re.escape(key)}:(?:\s|$)")
    return next((i for i in range(lo, hi) if pattern.match(lines[i])), None)


def _value_end(lines: Sequence[str], key_line: int, hi: int, *, sequence: bool = False) -> int:
    """End (exclusive) of the value lines of the key at ``key_line`` (block scalar, mapping or sequence)."""
    indent = _indent(lines[key_line])
    end = key_line + 1
    while end < hi:
        line = lines[end]
        if line.strip() and _indent(line) <= indent and not (sequence and _indent(line) == indent and line.lstrip().startswith("- ")):
            break
        end += 1
    while end - 1 > key_line and not lines[end - 1].strip():
        end -= 1  # trailing blank lines belong to what follows
    return end


def _body_region(lines: Sequence[str]) -> tuple[int, int, int]:
    """(first content line, end exclusive, content indent) of building.body."""
    building = _top_key_line(lines, "building")
    block = _child_block(lines, building) if building is not None else None
    if block is None:
        raise GateError("no building mapping")
    first, end, child = block
    key = _key_in(lines, first, end, child, "body")
    if key is None or not re.search(r":\s*\|", lines[key]):
        raise GateError("building.body is not a literal block")
    header = lines[key]
    indicator = re.search(r"\|(\d)?", header)
    stop = _value_end(lines, key, end)
    content = [i for i in range(key + 1, stop) if lines[i].strip()]
    if not content:
        raise GateError("building.body is empty")
    indent = child + int(indicator.group(1)) if indicator and indicator.group(1) else _indent(lines[content[0]])
    return key + 1, stop, indent


def _yaml_scalar(text: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9 _()&.,'/-]+", text) and not text.startswith(("-", " ")) and not text.endswith(" "):
        return text
    return json.dumps(text, ensure_ascii=False)


@dataclass
class Rewrite:
    text: str
    changed: bool


def rewrite_blueprint_text(
    text: str,
    building_key: str,
    old_slots: Sequence[Slot],
    order: Order,
    gate: str,
    slot_labels: Mapping[int, str],
) -> Rewrite:
    """Apply ``order`` and the flag to the blueprint text (LF newlines); returns the new text."""
    lines = text.split("\n")
    changed = False

    # ---- flag
    flag_line = _top_key_line(lines, FLAG)
    if flag_line is not None:
        if lines[flag_line].split(":", 1)[1].strip() != gate:
            lines[flag_line] = f"{FLAG}: {gate}"
            changed = True
    else:
        anchor = next(
            (i for i, line in enumerate(lines) if (m := _TOP_KEY_RE.match(line)) and m.group("key") in {"upgrade_chain", "building"}),
            None,
        )
        if anchor is None:
            raise GateError("no building mapping")
        lines.insert(anchor, f"{FLAG}: {gate}")
        changed = True

    if order.is_identity():
        return Rewrite("\n".join(lines), changed)

    # ---- body
    first, stop, indent = _body_region(lines)
    body = [line[indent:] if line.strip() else "" for line in lines[first:stop]]
    new_body = reorder_body_lines(body, order)
    lines[first:stop] = [(" " * indent + line) if line else "" for line in new_body]

    # ---- production_method_slots (the metadata list, when present)
    new_slots = ordered_slots(old_slots, order)
    building = _top_key_line(lines, "building")
    block = _child_block(lines, building) if building is not None else None
    if block is not None:
        lo, hi, child = block
        key = _key_in(lines, lo, hi, child, "production_method_slots")
        if key is not None and lines[key].split(":", 1)[1].strip() == "":
            stop = _value_end(lines, key, hi, sequence=True)
            current = lines[key + 1 : stop]
            listed = yaml_io.safe_load("x:\n" + "\n".join(current)) or {}
            entries = listed.get("x") or []
            if [list(e.get("methods") or []) for e in entries] == [s.names() for s in old_slots]:
                dash = next((_indent(l) for l in current if l.lstrip().startswith("- ")), child)
                methods_indent = next((_indent(l) for l in current if l.strip().startswith("methods:")), dash + 2)
                item_indent = next(
                    (_indent(l) for l in current if l.lstrip().startswith("- ") and _indent(l) > dash),
                    methods_indent,
                )
                names = [str(e.get("name", f"slot_{i}")) for i, e in enumerate(entries)]
                renamed = all(name == f"slot_{i}" for i, name in enumerate(names))
                out: list[str] = []
                for position, old in enumerate(order.slots):
                    name = f"slot_{position}" if renamed else names[old]
                    out.append(" " * dash + f"- name: {name}")
                    out.append(" " * methods_indent + "methods:")
                    out.extend(" " * item_indent + f"- {m}" for m in new_slots[position].names())
                lines[key + 1 : stop] = out

    # ---- slot labels
    loc = _top_key_line(lines, "localization")
    loc_block = _child_block(lines, loc) if loc is not None else None
    if loc_block is not None:
        lo, hi, child = loc_block
        entries_key = _key_in(lines, lo, hi, child, "entries")
        if entries_key is not None:
            stop = _value_end(lines, entries_key, hi)
            pattern = re.compile(rf"^(?P<indent>\s+){re.escape(building_key)}_slot_(?P<index>\d+):(?P<rest>.*)$")
            spots = [i for i in range(entries_key + 1, stop) if pattern.match(lines[i])]
            entry_indent = next(
                (_indent(lines[i]) for i in range(entries_key + 1, stop) if lines[i].strip()),
                _indent(lines[entries_key]) + 2,
            )
            new_position = {old: position for position, old in enumerate(order.slots)}
            new_lines: dict[int, str] = {}
            for i in spots:
                m = pattern.match(lines[i])
                old = int(m.group("index"))
                if old in new_position:
                    new_lines[new_position[old]] = f"{m.group('indent')}{building_key}_slot_{new_position[old]}:{m.group('rest')}"
            for old, position in new_position.items():
                if position not in new_lines and old in slot_labels and old != position:
                    new_lines[position] = " " * entry_indent + f"{building_key}_slot_{position}: {_yaml_scalar(slot_labels[old])}"
            ordered = [new_lines[p] for p in sorted(new_lines)]
            if spots:
                for i in reversed(spots):
                    del lines[i]
                at = spots[0]
            else:
                at = entries_key + 1
            lines[at:at] = ordered
    return Rewrite("\n".join(lines), True)


def edit_leg_text(text: str, building_key: str, leg: Leg | None, config: GateConfig) -> str:
    """Put the gate leg into the blueprint text (LF newlines): the body block after the last unique block, its entry at
    the end of production_method_slots, its slot label and method name/description in localization.entries. Old leg
    slots are dropped first, so this also updates or removes a leg."""
    lines = text.split("\n")

    # ---- body
    first, stop, indent = _body_region(lines)
    body = [line[indent:] if line.strip() else "" for line in lines[first:stop]]
    old_count = len(_spans(body))
    old_legs = {m.name for slot in body_slots("\n".join(body))[0] for m in slot.methods if is_leg(m.name)}
    new_body = edit_leg_body("\n".join(body), leg).split("\n")
    lines[first:stop] = [(" " * indent + line) if line else "" for line in new_body]
    count = len(_spans(new_body))

    # ---- production_method_slots
    building = _top_key_line(lines, "building")
    block = _child_block(lines, building) if building is not None else None
    if block is not None:
        lo, hi, child = block
        key = _key_in(lines, lo, hi, child, "production_method_slots")
        if key is not None and lines[key].split(":", 1)[1].strip() == "":
            end = _value_end(lines, key, hi, sequence=True)
            current = lines[key + 1 : end]
            entries = (yaml_io.safe_load("x:\n" + "\n".join(current)) or {}).get("x") or []
            kept = [e for e in entries if not any(is_leg(str(m)) for m in (e.get("methods") or []))]
            if leg is not None:
                names = [str(e.get("name", "")) for e in kept]
                numbered = all(name == f"slot_{i}" for i, name in enumerate(names))
                kept.append({"name": f"slot_{len(kept)}" if numbered else "market", "methods": [leg.name]})
            dash = next((_indent(l) for l in current if l.lstrip().startswith("- ")), child + 2)
            methods_indent = next((_indent(l) for l in current if l.strip().startswith("methods:")), dash + 2)
            item_indent = next((_indent(l) for l in current if l.lstrip().startswith("- ") and _indent(l) > dash), methods_indent)
            out: list[str] = []
            for entry in kept:
                out.append(" " * dash + f"- name: {entry.get('name')}")
                out.append(" " * methods_indent + "methods:")
                out.extend(" " * item_indent + f"- {m}" for m in entry.get("methods") or [])
            lines[key + 1 : end] = out

    # ---- evaluation allow rules
    _edit_leg_evaluation(lines, sorted(old_legs | {leg_name(building_key)}), leg)

    # ---- localization
    loc = _top_key_line(lines, "localization")
    if loc is None:
        if leg is None:
            return "\n".join(lines)
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["localization:", "  entries:"]
        loc = len(lines) - 2
    loc_block = _child_block(lines, loc)
    if loc_block is None:
        lines.insert(loc + 1, "  entries:")
        loc_block = _child_block(lines, loc)
    lo, hi, child = loc_block
    entries_key = _key_in(lines, lo, hi, child, "entries")
    if entries_key is None:
        lines.insert(hi, " " * child + "entries:")
        entries_key, hi = hi, hi + 1
    end = _value_end(lines, entries_key, hi)
    entry_indent = next((_indent(lines[i]) for i in range(entries_key + 1, end) if lines[i].strip()), _indent(lines[entries_key]) + 2)
    leg_keys = {leg_name(building_key), leg_name(building_key) + "_desc"}
    label = re.compile(rf"^\s*{re.escape(building_key)}_slot_(\d+):")
    drop = []
    for i in range(entries_key + 1, end):
        m = label.match(lines[i])
        key_here = lines[i].strip().split(":", 1)[0]
        if key_here in leg_keys and leg is None:
            drop.append(i)
        elif m and old_count > count and int(m.group(1)) >= count:
            drop.append(i)  # the label of a dropped leg slot
        elif m and leg is not None and int(m.group(1)) == count - 1:
            drop.append(i)  # the leg slot's label is written below
    for i in reversed(drop):
        del lines[i]
        end -= 1
    if leg is not None:
        present = {lines[i].strip().split(":", 1)[0] for i in range(entries_key + 1, end) if lines[i].strip()}
        add = [f"{building_key}_slot_{count - 1}: {_yaml_scalar(config.leg.slot_label)}"]
        if leg.name not in present:
            add.append(f"{leg.name}: {_yaml_scalar(config.leg.method_name)}")
        if leg.name + "_desc" not in present:
            add.append(f"{leg.name}_desc: {_yaml_scalar(config.leg.method_desc)}")
        lines[end:end] = [" " * entry_indent + line for line in add]
    return "\n".join(lines)


LEG_ALLOW_RULES = {
    "profit_percent": "The Market Sales gate leg is balanced at its gate margin, not at a profit band.",
    "input_throughput": "The Market Sales gate leg is a small technical method that only sets the AI margin check.",
    "output_throughput": "The Market Sales gate leg is a small technical method that only sets the AI margin check.",
}


def _edit_leg_evaluation(lines: list[str], names: Sequence[str], leg: Leg | None) -> None:
    """Drop the evaluation.production_methods entries of ``names`` and, with ``leg``, add the leg's allow rules."""
    top = _top_key_line(lines, "evaluation")
    if top is None:
        if leg is None:
            return
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["evaluation:", "  production_methods:"]
        top = len(lines) - 2
    block = _child_block(lines, top)
    if block is None:
        lines.insert(top + 1, "  production_methods:")
        block = _child_block(lines, top)
    lo, hi, child = block
    key = _key_in(lines, lo, hi, child, "production_methods")
    if key is None:
        if leg is None:
            return
        at = _value_end(lines, top, hi)
        lines.insert(at, " " * child + "production_methods:")
        key, hi = at, hi + 1
    end = _value_end(lines, key, hi)
    step = next((_indent(lines[i]) - child for i in range(key + 1, end) if lines[i].strip()), 2) or 2
    for name in names:
        entry = _key_in(lines, key + 1, end, child + step, name)
        if entry is not None:
            stop = _value_end(lines, entry, end)
            del lines[entry:stop]
            end -= stop - entry
    if leg is not None:
        pad = " " * (child + step)
        out = [f"{pad}{leg.name}:", f"{pad}{' ' * step}allow_rules:"]
        out += [f"{pad}{' ' * (2 * step)}{rule}: {_yaml_scalar(text)}" for rule, text in LEG_ALLOW_RULES.items()]
        lines[end:end] = out


def _mapping_leg(blueprint: dict[str, Any], leg: Leg | None, config: GateConfig) -> None:
    """The mapping form of ``edit_leg_text`` (rendered blueprints of the generators)."""
    building = blueprint["building"]
    key = str(building["key"])
    building["body"] = edit_leg_body(str(building["body"]), leg)
    listed = building.get("production_method_slots")
    if listed:
        kept = [e for e in listed if not any(is_leg(str(m)) for m in (e.get("methods") or []))]
        if leg is not None:
            numbered = all(str(e.get("name")) == f"slot_{i}" for i, e in enumerate(kept))
            kept.append({"name": f"slot_{len(kept)}" if numbered else "market", "methods": [leg.name]})
        building["production_method_slots"] = kept
    evaluation = blueprint.get("evaluation")
    per_method = evaluation.get("production_methods") if isinstance(evaluation, dict) else None
    if isinstance(per_method, dict):
        for name in [n for n in per_method if is_leg(str(n))]:
            del per_method[name]
    if leg is None:
        return
    blueprint.setdefault("evaluation", {}).setdefault("production_methods", {})[leg.name] = {"allow_rules": dict(LEG_ALLOW_RULES)}
    slots, _ = body_slots(str(building["body"]), f"{key}.yml")
    localization = blueprint.setdefault("localization", {})
    entries = localization.setdefault("entries", {})
    entries[f"{key}_slot_{len(slots) - 1}"] = config.leg.slot_label
    entries.setdefault(leg.name, config.leg.method_name)
    entries.setdefault(leg.name + "_desc", config.leg.method_desc)


# ---------------------------------------------------------------- the mapping form (generators)


def order_mapping(blueprint: dict[str, Any], config: GateConfig, prices: Mapping[str, float], gate: str | None = None) -> dict[str, Any]:
    """Order a rendered blueprint mapping (body, production_method_slots, slot labels) and set the flag in place.
    ``gate`` defaults to the flag the mapping carries, else the rule's suggestion."""
    building = blueprint["building"]
    key = str(building["key"])
    slots, has_possible = body_slots(str(building["body"]), f"{key}.yml")
    if not is_production(slots):
        return blueprint
    leg = None if has_possible else plan_leg(key, slots, gate or blueprint.get(FLAG), config, prices)
    if not leg_in_place(slots, leg):
        _mapping_leg(blueprint, leg, config)
        slots, has_possible = body_slots(str(building["body"]), f"{key}.yml")
    if leg is not None:
        gate = leg.name
    gate = gate or blueprint.get(FLAG) or suggest_gate(without_legs(slots), config, prices)
    order = plan_order(slots, str(gate), config, prices)
    if has_possible:
        raise GateError(f"{key}: possible and unique production methods together are not supported")
    new_slots = ordered_slots(slots, order)
    building["body"] = reorder_body(str(building["body"]), order)
    if building.get("production_method_slots"):
        building["production_method_slots"] = [
            {"name": f"slot_{i}", "methods": slot.names()} for i, slot in enumerate(new_slots)
        ]
    entries = (blueprint.get("localization") or {}).get("entries")
    if isinstance(entries, dict):
        labels = {i: entries.get(f"{key}_slot_{i}") for i in range(len(slots))}
        spots = [k for k in entries if re.fullmatch(rf"{re.escape(key)}_slot_\d+", k)]
        rebuilt: dict[str, Any] = {}
        placed = False
        for k, v in entries.items():
            if k in spots:
                if not placed:
                    for position, old in enumerate(order.slots):
                        if labels.get(old) is not None:
                            rebuilt[f"{key}_slot_{position}"] = labels[old]
                    placed = True
                continue
            rebuilt[k] = v
        entries.clear()
        entries.update(rebuilt)
    _set_flag(blueprint, str(gate))
    return blueprint


def _set_flag(blueprint: dict[str, Any], gate: str) -> None:
    """Put the flag after the labour tag (before upgrade_chain / building), keeping the other keys in order."""
    if blueprint.get(FLAG) == gate:
        return
    items = [(k, v) for k, v in blueprint.items() if k != FLAG]
    at = next((i for i, (k, _) in enumerate(items) if k in {"upgrade_chain", "building"}), len(items))
    items.insert(at, (FLAG, gate))
    blueprint.clear()
    blueprint.update(items)


# ---------------------------------------------------------------- repo pass


@dataclass
class Plan:
    blueprint: Path
    building: str
    gate: str | None
    flagged: bool  # the blueprint already names the gate
    slots: list[Slot]
    order: Order | None
    gate_margin: float | None = None
    gate_produced: str | None = None
    problems: list[str] = field(default_factory=list)
    leg: Leg | None = None
    leg_edit: bool = False  # the body's leg is missing, stale or unwanted (``slots`` is the body after the edit)

    @property
    def reorders(self) -> bool:
        return self.order is not None and not self.order.is_identity()

    @property
    def pending(self) -> bool:
        return not self.flagged or self.reorders or self.leg_edit


@dataclass
class GateResult:
    plans: list[Plan] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    files_changed: int = 0

    @property
    def pending(self) -> list[Plan]:
        return [p for p in self.plans if p.pending]


def enabled_blueprints(repo: Path) -> list[Path]:
    manifest = yaml_io.safe_load((repo / MANIFEST_RELATIVE).read_text(encoding="utf-8-sig")) or {}
    enabled = manifest.get("enabled") or {}
    return [repo / BLUEPRINT_ROOT_RELATIVE / entry for entry, on in enabled.items() if on and str(entry).startswith("buildings/")]


def blueprint_state(path: Path) -> tuple[dict[str, Any], list[Slot], bool]:
    data = yaml_io.safe_load(_read(path)) or {}
    building = data.get("building") if isinstance(data.get("building"), dict) else {}
    body = str(building.get("body") or "")
    if not body.strip():
        return data, [], False
    slots, has_possible = body_slots(body, path)
    return data, slots, has_possible


def structural_problems(repo: Path) -> dict[str, list[str]]:
    """Blueprint file name -> gate problems of every enabled production blueprint as it stands (no prices needed)."""
    out: dict[str, list[str]] = {}
    for path in enabled_blueprints(repo):
        if not path.is_file():
            continue
        data, slots, has_possible = blueprint_state(path)
        if not is_production(slots):
            continue
        problems = gate_problems(slots, data.get(FLAG), has_possible)
        if problems:
            out[path.name] = problems
    return out


def _leg_metadata_ok(data: Mapping[str, Any], building: str, leg: Leg | None) -> bool:
    """The leg's evaluation allow rules and localization are in the blueprint (nothing to check without a leg)."""
    if leg is None:
        return True
    per_method = ((data.get("evaluation") or {}).get("production_methods")) or {}
    rules = ((per_method.get(leg.name) or {}).get("allow_rules")) or {}
    entries = ((data.get("localization") or {}).get("entries")) or {}
    return dict(rules) == LEG_ALLOW_RULES and leg.name in entries and f"{leg.name}_desc" in entries


def plan_all(repo: Path, config: GateConfig, prices: Mapping[str, float]) -> GateResult:
    result = GateResult()
    for path in enabled_blueprints(repo):
        if not path.is_file():
            continue
        data, slots, has_possible = blueprint_state(path)
        if not is_production(slots):
            if data.get(FLAG):
                result.problems.append(f"{path.name}: {FLAG} on a building without producing unique methods")
            continue
        building = str((data.get("building") or {}).get("key") or data.get("tag") or path.stem)
        flag = str(data[FLAG]) if data.get(FLAG) else None
        try:
            leg = None if has_possible else plan_leg(building, slots, flag, config, prices)
        except GateError as exc:
            result.problems.append(f"{path.name}: {exc}")
            continue
        leg_edit = not leg_in_place(slots, leg) or not _leg_metadata_ok(data, building, leg)
        if leg_edit:
            slots = slots_with_leg(slots, leg)
        if leg is not None:
            gate: str | None = leg.name
        elif flag and not is_leg(flag):
            gate = flag
        else:
            gate = suggest_gate(slots, config, prices)
        plan = Plan(path, building, gate, flag == gate, slots, None, leg=leg, leg_edit=leg_edit)
        result.plans.append(plan)
        if has_possible:
            plan.problems.append("possible and unique production methods together are not supported")
        where = locate(slots, gate) if gate else None
        if where is None:
            plan.problems.append(f"{FLAG} {gate} is not a unique production method of the building")
        else:
            method = slots[where[0]].methods[where[1]]
            if not method.has_output:
                plan.problems.append(f"{FLAG} {gate} has no output good")
            plan.gate_produced = method.produced
            plan.gate_margin = method.margin(prices)
            if not plan.problems:
                plan.order = plan_order(slots, gate, config, prices)
        result.problems.extend(f"{path.name}: {p}" for p in plan.problems)
    return result


def apply(repo: Path, project: Path, prices: Mapping[str, float] | None = None, *, write: bool = True) -> GateResult:
    config = load_config(project)
    prices = prices if prices is not None else load_prices(repo, project, config)
    result = plan_all(repo, config, prices)
    if write and not result.problems:
        vanilla = _vanilla_slot_labels(repo, project, [p for p in result.plans if p.reorders])
        for plan in result.pending:
            _write(plan, vanilla.get(plan.building, {}), config)
            result.files_changed += 1
        write_report(repo / REPORT_RELATIVE_PATH, result, config, prices)
    return result


def _write(plan: Plan, vanilla_labels: Mapping[int, str], config: GateConfig) -> None:
    raw = plan.blueprint.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    original = raw.decode("utf-8-sig")
    crlf = "\r\n" in original
    text = original.replace("\r\n", "\n")
    if plan.leg_edit:
        text = edit_leg_text(text, plan.building, plan.leg, config)
        edited, _ = body_slots(str((yaml_io.safe_load(text) or {})["building"]["body"]), plan.blueprint)
        if edited != plan.slots:
            raise GateError(f"{plan.blueprint.name}: the gate leg edit does not read back as planned")
    data = yaml_io.safe_load(text) or {}
    entries = ((data.get("localization") or {}).get("entries")) or {}
    labels = {i: str(entries.get(f"{plan.building}_slot_{i}") or vanilla_labels.get(i) or "") for i in range(len(plan.slots))}
    labels = {i: v for i, v in labels.items() if v}
    order = plan.order or Order(tuple(range(len(plan.slots))), tuple(tuple(range(len(s.methods))) for s in plan.slots))
    rewrite = rewrite_blueprint_text(text, plan.building, plan.slots, order, str(plan.gate), labels)
    new = rewrite.text.replace("\n", "\r\n") if crlf else rewrite.text
    plan.blueprint.write_text(("\ufeff" if bom else "") + new, encoding="utf-8", newline="")
    try:
        _verify(plan, data, labels)
    except Exception:
        plan.blueprint.write_text(("\ufeff" if bom else "") + original, encoding="utf-8", newline="")
        raise


def _verify(plan: Plan, before: Mapping[str, Any], labels: Mapping[int, str]) -> None:
    """The rewritten blueprint loads, its methods are the same (text for text), in the planned order, and nothing but
    the body order, the slot list, the slot labels and the flag changed."""
    after = yaml_io.safe_load(_read(plan.blueprint)) or {}
    slots, _ = body_slots(str(after["building"]["body"]), plan.blueprint)
    order = plan.order
    expected = ordered_slots(plan.slots, order) if order is not None else plan.slots
    if [s.names() for s in slots] != [s.names() for s in expected] or slots != expected:
        raise GateError(f"{plan.blueprint.name}: the rewritten body does not read back in the planned order")
    old_body = sorted(line.strip() for line in str(before["building"]["body"]).split("\n") if not line.strip().startswith("#"))
    new_body = sorted(line.strip() for line in str(after["building"]["body"]).split("\n") if not line.strip().startswith("#"))
    if old_body != new_body:
        raise GateError(f"{plan.blueprint.name}: the rewrite changed body lines, not only their order")
    if after.get(FLAG) != plan.gate:
        raise GateError(f"{plan.blueprint.name}: {FLAG} reads back {after.get(FLAG)!r}")
    if order is not None:
        entries = (after.get("localization") or {}).get("entries") or {}
        for position, old in enumerate(order.slots):
            if old in labels and str(entries.get(f"{plan.building}_slot_{position}")) != labels[old]:
                raise GateError(f"{plan.blueprint.name}: slot label {position} reads back wrong")
        listed = after["building"].get("production_method_slots")
        if listed and [list(e.get("methods") or []) for e in listed] not in ([s.names() for s in expected], [s.names() for s in plan.slots]):
            raise GateError(f"{plan.blueprint.name}: production_method_slots reads back wrong")
    for key in set(before) | set(after):
        if key in {FLAG, "building", "localization"}:
            continue
        if before.get(key) != after.get(key):
            raise GateError(f"{plan.blueprint.name}: {key} changed")
    for key in set(before.get("building") or {}) | set(after.get("building") or {}):
        if key in {"body", "production_method_slots"}:
            continue
        if (before.get("building") or {}).get(key) != (after.get("building") or {}).get(key):
            raise GateError(f"{plan.blueprint.name}: building.{key} changed")
    slot_key_re = re.compile(rf"{re.escape(plan.building)}_slot_\d+")
    old_entries = {k: v for k, v in (((before.get("localization") or {}).get("entries")) or {}).items() if not slot_key_re.fullmatch(k)}
    new_entries = {k: v for k, v in (((after.get("localization") or {}).get("entries")) or {}).items() if not slot_key_re.fullmatch(k)}
    if old_entries != new_entries:
        raise GateError(f"{plan.blueprint.name}: localization entries other than slot labels changed")


def _vanilla_slot_labels(repo: Path, project: Path, plans: Sequence[Plan]) -> dict[str, dict[int, str]]:
    """Slot labels the game ships for buildings whose blueprint does not name them (REPLACEd vanilla buildings)."""
    wanted = {p.building for p in plans}
    if not wanted:
        return {}
    try:
        from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

        root = Path(vanilla_root(repo, project))
    except Exception:  # noqa: BLE001 - labels are a nicety; the blueprint's own labels still move
        return {}
    folder = next((p for p in (root / "main_menu/localization/english", root / "game/main_menu/localization/english") if p.is_dir()), None)
    if folder is None:
        return {}
    pattern = re.compile(r'^\s*(?P<key>[A-Za-z_0-9]+)_slot_(?P<index>\d+):\d*\s*"(?P<value>.*)"\s*$')
    labels: dict[str, dict[int, str]] = {}
    for path in sorted(folder.glob("*.yml")):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            m = pattern.match(line)
            if m and m.group("key") in wanted:  # a `$other_slot_0$` reference is kept: the game resolves it
                labels.setdefault(m.group("key"), {})[int(m.group("index"))] = m.group("value")
    return labels


def write_report(path: Path, result: GateResult, config: GateConfig, prices: Mapping[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["building", "gate_method", "produced", "base_margin", "below_threshold", "slots", "blueprint"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for plan in result.plans:
            writer.writerow({
                "building": plan.building,
                "gate_method": plan.gate or "",
                "produced": plan.gate_produced or "",
                "base_margin": "" if plan.gate_margin is None else round(plan.gate_margin, 3),
                "below_threshold": "" if plan.gate_margin is None else plan.gate_margin < config.threshold,
                "slots": len(plan.slots),
                "blueprint": plan.blueprint.name,
            })


# ---------------------------------------------------------------- helpers


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (CList, bool)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")
