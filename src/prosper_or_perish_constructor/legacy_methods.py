"""Legacy methods: an upgrade never takes a recipe away (2026-10-04, Jan).

The vanilla manufacturing lines (guild -> workshop -> manufactory -> mill or factory, linked by ``obsolete``) drop the
older tiers' recipes on upgrade: stone, copper and bronze tools stop at the guild, every beer grain but wheat at the
workshop. Once the next tier is researched the old one can no longer be built, so an economy built on the old inputs
could not grow. Every tier of a line in ``[legacy_methods.lines]`` therefore keeps the recipes of the tiers below it
as legacy methods ``pp_<building>_legacy_<origin method>``, at lower throughput than its own methods:

- A recipe is the goods set of a method (manual labour aside). Walking up the line slot by slot, a recipe of the tier
  below is covered when the tier has an own method in the matching slot that needs no other goods (a subset) and no
  advance the recipe does not need; otherwise it is carried up. A carried recipe is dropped when another carried recipe
  of the slot needs fewer goods, no other advance and has at least its share; recipes with the same goods merge.
- Share: an own method's value / the most valuable own method of its slot (vanilla's own ratios: stone tools are 25 %
  of iron in the guild); a carried recipe keeps its origin share x ``decay`` per tier it moves up.
- Amounts: output worth share x the slot's most valuable own method (the reference); inputs are the origin method's
  (goods and labour) scaled so the legacy method keeps the reference's margin: the same profit per gold, less per
  level. The AI's method switcher picks the best profit per level among methods whose inputs are in the market, so
  the contemporary method wins wherever its goods exist. Category and debug_max_profit follow the reference.
- Slots: each slot of the tier below is matched to the slot of this tier with the most goods in common (ties and no
  overlap: the slot of the same rank by value).
- Unlocks: a recipe locked behind an advance stays locked (``TRY_INJECT:<advance>`` unlock lines in the blueprint's
  advancements).
- Icon: the origin method's own icon lines, else vanilla's icon of the origin method. Localization: vanilla's name of
  the origin method (or the origin blueprint's) + ``label_suffix``, and ``desc`` with the origin building.

``ppc legacy apply`` writes the legacy methods (body, production_method_slots, localization, evaluation allow rules,
advancement unlocks) and removes stale ones; ``ppc legacy check`` reports what apply would change. The labour pass
skips legacy methods (their labour comes from the origin), the gate pass lists them after the building's own methods
(a slot's first method is what new buildings run). Order after editing recipes: ``ppc labour apply``,
``ppc legacy apply``, ``ppc logistics apply``, ``ppc gate apply``.
"""

from __future__ import annotations

import csv
import re
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import yaml_io
from prosper_or_perish_constructor.production_gate import (
    LEGACY_INFIX,
    UNIQUE,
    _body_region,
    _child_block,
    _indent,
    _key_in,
    _spans,
    _top_key_line,
    _value_end,
    _yaml_scalar,
    is_leg,
    is_legacy,
    legacy_name,
)
from prosper_or_perish_constructor.production_labour import GOODS_STEPS, LABOUR_STEPS, format_amount, nice

CONFIG_SECTION = "legacy_methods"
BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted/buildings")
MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
REPORT_RELATIVE_PATH = Path("artifacts/data/legacy_methods/legacy.csv")
LABOUR_GOOD = "manual_labor"
METHOD_KEYS = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "no_upkeep", "ai_will_do", "icon", "icon_type"}
COPIED_KEYS = ("debug_max_profit", "category")
INJECT = "TRY_INJECT:"
_PREFIXES = ("TRY_INJECT:", "INJECT:", "REPLACE:", "TRY_REPLACE:", "REPLACE_OR_CREATE:", "INJECT_OR_CREATE:")
_UNLOCK_RE = re.compile(r"^\s*unlock_production_method\s*=\s*(?P<method>[A-Za-z_0-9]+)\s*$")

ALLOW_RULES = {
    "profit_percent": "Legacy method: an older recipe carried up the upgrade line on purpose, at the contemporary "
    "method's margin and a smaller output.",
    "input_throughput": "Legacy method: lower throughput than the contemporary method on purpose, so it runs only where "
    "the contemporary inputs are missing.",
    "output_throughput": "Legacy method: lower throughput than the contemporary method on purpose, so it runs only where "
    "the contemporary inputs are missing.",
}


class LegacyError(ValueError):
    """A line or blueprint the legacy pass cannot plan or rewrite safely."""


# ---------------------------------------------------------------- config


@dataclass(frozen=True)
class LegacyConfig:
    decay: float
    label_suffix: str
    desc: str  # "{origin}" stands for the origin building's name
    lines: dict[str, tuple[str, ...]]


def load_config(project: Path) -> LegacyConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION)
    if not isinstance(section, dict) or not isinstance(section.get("lines"), dict):
        raise LegacyError(f"{project}: [{CONFIG_SECTION}] with a [{CONFIG_SECTION}.lines] table is required")
    decay = float(section.get("decay", 0.75))
    if not 0 < decay < 1:
        raise LegacyError(f"[{CONFIG_SECTION}] decay must be in (0, 1), got {decay}")
    lines = {str(name): tuple(str(b) for b in tiers) for name, tiers in section["lines"].items()}
    for name, tiers in lines.items():
        if len(tiers) < 2 or len(set(tiers)) != len(tiers):
            raise LegacyError(f"[{CONFIG_SECTION}.lines] {name} needs two or more distinct buildings")
    return LegacyConfig(
        decay=decay,
        label_suffix=str(section.get("label_suffix", "(Old Ways)")),
        desc=str(section.get("desc", "An older way of working, kept from the {origin}.")),
        lines=lines,
    )


def line_buildings(config: LegacyConfig) -> set[str]:
    return {b for tiers in config.lines.values() for b in tiers}


# ---------------------------------------------------------------- blueprint model


@dataclass(frozen=True)
class MethodData:
    name: str
    produced: str | None
    output: float | None
    inputs: Mapping[str, float]  # positive input amounts, labour included, in file order
    scalars: Mapping[str, str]  # other top-level scalars (category, debug_max_profit, icon_type, icon)
    blocks: tuple[str, ...]  # keys of nested blocks (potential, allow, ...)

    @property
    def goods(self) -> frozenset[str]:
        return frozenset(g for g in self.inputs if g != LABOUR_GOOD)

    def value(self, prices: Mapping[str, float]) -> float:
        if not self.produced or not self.output:
            return 0.0
        return float(self.output) * float(prices.get(self.produced, 0.0))

    def cost(self, prices: Mapping[str, float]) -> float:
        return sum(a * float(prices.get(g, 0.0)) for g, a in self.inputs.items())


@dataclass
class Tier:
    building: str
    path: Path
    data: dict[str, Any]
    slots: list[list[MethodData]]  # every unique slot in body order, legs included
    unlocks: dict[str, frozenset[str]]  # method -> advances (base names) whose advancement entries unlock it

    def real_slots(self) -> list[int]:
        """Body indices of the producing slots that are not the gate leg."""
        return [
            i
            for i, slot in enumerate(self.slots)
            if slot and not any(is_leg(m.name) for m in slot) and any(m.produced for m in slot)
        ]

    def own(self, slot: int) -> list[MethodData]:
        return [m for m in self.slots[slot] if not is_legacy(m.name) and m.produced]

    def method(self, name: str) -> MethodData:
        for slot in self.slots:
            for m in slot:
                if m.name == name:
                    return m
        raise LegacyError(f"{self.building}: no method {name}")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (CList, bool)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_body(body: str, source: Path | str = "<body>") -> list[list[MethodData]]:
    block = parse_text(f"x = {{\n{body}\n}}\n", Path(str(source))).entries[0].value
    slots: list[list[MethodData]] = []
    if not isinstance(block, CList):
        return slots
    for group in block.values(UNIQUE):
        if not isinstance(group, CList):
            continue
        methods: list[MethodData] = []
        for entry in group.entries:
            if not isinstance(entry.value, CList):
                continue
            inputs: dict[str, float] = {}
            scalars: dict[str, str] = {}
            blocks: list[str] = []
            produced: str | None = None
            output: float | None = None
            for item in entry.value.entries:
                if isinstance(item.value, CList):
                    blocks.append(str(item.key))
                elif item.key == "produced":
                    produced = str(item.value)
                elif item.key == "output":
                    output = _number(item.value)
                elif item.key in METHOD_KEYS:
                    scalars[str(item.key)] = str(item.value)
                else:
                    number = _number(item.value)
                    if number is not None and number > 0:
                        inputs[str(item.key)] = number
            methods.append(MethodData(str(entry.key), produced, output, inputs, scalars, tuple(blocks)))
        slots.append(methods)
    return slots


def _base(key: str) -> str:
    for prefix in _PREFIXES:
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def blueprint_unlocks(data: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {}
    for entry in data.get("advancements") or []:
        if not isinstance(entry, dict):
            continue
        for line in str(entry.get("body") or "").splitlines():
            match = _UNLOCK_RE.match(line)
            if match:
                out.setdefault(match.group("method"), set()).add(_base(str(entry.get("key"))))
    return {k: frozenset(v) for k, v in out.items()}


def load_tier(repo: Path, building: str) -> Tier:
    path = repo / BLUEPRINT_ROOT_RELATIVE / f"{building}.yml"
    if not path.is_file():
        raise LegacyError(f"{building}: no blueprint {path.relative_to(repo)}")
    data = yaml_io.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    body = str((data.get("building") or {}).get("body") or "")
    return Tier(building, path, data, parse_body(body, path), blueprint_unlocks(data))


def obsolete_of(tier: Tier) -> str | None:
    body = str((tier.data.get("building") or {}).get("body") or "")
    match = re.search(r"^\s*obsolete\s*=\s*([A-Za-z_0-9]+)", body, re.MULTILINE)
    return match.group(1) if match else None


# ---------------------------------------------------------------- planning


@dataclass(frozen=True)
class Recipe:
    goods: frozenset[str]
    origin: str  # origin building
    method: str  # origin method
    share: float  # share at the origin tier
    steps: int  # tiers moved up from the origin
    unlocks: frozenset[str]

    def share_at(self, decay: float) -> float:
        return self.share * decay**self.steps


@dataclass
class LegacyMethod:
    building: str
    slot: int  # body index of the slot
    name: str
    recipe: Recipe
    share: float
    produced: str
    output: float
    amounts: dict[str, float]  # goods then labour, rounded
    scalars: dict[str, str]  # copied category / debug_max_profit of the reference
    icon: tuple[str, str] | None
    reference: str
    label: str
    desc: str

    def value(self, prices: Mapping[str, float]) -> float:
        return self.output * float(prices.get(self.produced, 0.0))

    def cost(self, prices: Mapping[str, float]) -> float:
        return sum(a * float(prices.get(g, 0.0)) for g, a in self.amounts.items())


@dataclass
class TierPlan:
    tier: Tier
    line: str
    index: int
    methods: list[LegacyMethod] = field(default_factory=list)
    new_text: str | None = None
    changed: bool = False
    problems: list[str] = field(default_factory=list)


@dataclass
class LegacyResult:
    plans: list[TierPlan] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    files_changed: int = 0

    @property
    def changed(self) -> list[TierPlan]:
        return [p for p in self.plans if p.changed]

    @property
    def methods(self) -> list[LegacyMethod]:
        return [m for p in self.plans for m in p.methods]


def covered(goods: frozenset[str], unlocks: frozenset[str], own: Sequence[MethodData], own_unlocks: Mapping[str, frozenset[str]]) -> bool:
    """An own method runs on these goods (needs no other good) whenever the recipe can run (no other advance)."""
    return any(m.goods <= goods and own_unlocks.get(m.name, frozenset()) <= unlocks for m in own)


def map_slots(below: Tier, tier: Tier, prices: Mapping[str, float]) -> dict[int, int]:
    """Body slot of ``below`` -> body slot of ``tier``: most goods in common, then the same rank by value."""
    def ranks(t: Tier) -> dict[int, int]:
        order = sorted(t.real_slots(), key=lambda s: max((m.value(prices) for m in t.own(s)), default=0.0))
        return {s: r for r, s in enumerate(order)}

    def goods(t: Tier, s: int) -> frozenset[str]:
        return frozenset().union(*[m.goods for m in t.own(s)]) if t.own(s) else frozenset()

    rank_below, rank_tier = ranks(below), ranks(tier)
    out: dict[int, int] = {}
    for s in below.real_slots():
        mine = goods(below, s)

        def score(t: int) -> tuple[float, int]:
            theirs = goods(tier, t)
            union = mine | theirs
            jaccard = len(mine & theirs) / len(union) if union else 0.0
            scaled = rank_below[s] * (len(rank_tier) - 1) / max(len(rank_below) - 1, 1)
            return jaccard, -abs(rank_tier[t] - round(scaled))

        out[s] = max(tier.real_slots(), key=score)
    return out


def own_recipes(tier: Tier, slot: int, prices: Mapping[str, float]) -> dict[frozenset[str], Recipe]:
    own = tier.own(slot)
    top = max((m.value(prices) for m in own), default=0.0)
    out: dict[frozenset[str], Recipe] = {}
    for m in own:
        if not m.goods or top <= 0:
            continue
        recipe = Recipe(m.goods, tier.building, m.name, m.value(prices) / top, 0, tier.unlocks.get(m.name, frozenset()))
        if m.goods not in out or recipe.share > out[m.goods].share:
            out[m.goods] = recipe
    return out


def carry(incoming: Sequence[Recipe], tier: Tier, slot: int, decay: float) -> list[Recipe]:
    """The recipes this slot keeps as legacy methods (one tier further up each)."""
    own = tier.own(slot)
    best: dict[frozenset[str], Recipe] = {}
    for recipe in incoming:
        if not recipe.goods or covered(recipe.goods, recipe.unlocks, own, tier.unlocks):
            continue
        moved = replace(recipe, steps=recipe.steps + 1)
        held = best.get(moved.goods)
        if held is None or moved.share_at(decay) > held.share_at(decay) + 1e-12:
            best[moved.goods] = moved
    recipes = list(best.values())
    kept: list[Recipe] = []
    for r in recipes:
        dominated = any(
            o is not r
            and o.goods < r.goods
            and o.unlocks <= r.unlocks
            and o.share_at(decay) >= r.share_at(decay) - 1e-12
            for o in recipes
        )
        if not dominated:
            kept.append(r)
    return sorted(kept, key=lambda r: (r.origin, r.method))


@dataclass(frozen=True)
class Names:
    """Vanilla localization and icons for names, descriptions and icons of legacy methods."""

    loc: Mapping[str, str]
    icons: Mapping[tuple[str, str], tuple[str, str]]


def plan_line(
    line: str,
    tiers: Sequence[Tier],
    config: LegacyConfig,
    prices: Mapping[str, float],
    names: Names,
) -> list[TierPlan]:
    plans = [TierPlan(tier, line, i) for i, tier in enumerate(tiers)]
    by_building = {t.building: t for t in tiers}
    previous: dict[int, list[Recipe]] = {}
    for i, tier in enumerate(tiers):
        plan = plans[i]
        if i > 0 and obsolete_of(tier) != tiers[i - 1].building:
            plan.problems.append(f"{tier.building}: obsolete = {obsolete_of(tier)}, expected {tiers[i - 1].building} ({line} line)")
        incoming: dict[int, list[Recipe]] = {s: [] for s in tier.real_slots()}
        if i > 0:
            for s_below, s_here in map_slots(tiers[i - 1], tier, prices).items():
                incoming[s_here].extend(previous.get(s_below, []))
        current: dict[int, list[Recipe]] = {}
        for s in tier.real_slots():
            own = own_recipes(tier, s, prices)
            legacy = carry(incoming[s], tier, s, config.decay)
            current[s] = [*own.values(), *legacy]
            reference = max(tier.own(s), key=lambda m: m.value(prices), default=None)
            if legacy and reference is None:
                plan.problems.append(f"{tier.building}: slot {s} has no own producing method to scale old recipes by")
                continue
            for recipe in legacy:
                try:
                    plan.methods.append(legacy_method(tier, s, recipe, reference, by_building[recipe.origin], config, prices, names))
                except LegacyError as exc:
                    plan.problems.append(str(exc))
        previous = current
    return plans


def legacy_method(
    tier: Tier,
    slot: int,
    recipe: Recipe,
    reference: MethodData,
    origin_tier: Tier,
    config: LegacyConfig,
    prices: Mapping[str, float],
    names: Names,
) -> LegacyMethod:
    origin = origin_tier.method(recipe.method)
    if origin.blocks:
        raise LegacyError(f"{origin_tier.building}: {origin.name} has {', '.join(origin.blocks)} blocks; legacy copies need plain methods")
    missing = [g for g in (*origin.inputs, reference.produced) if g not in prices]
    if missing:
        raise LegacyError(f"{tier.building}: unpriced goods {', '.join(sorted(set(missing)))}")
    share = recipe.share_at(config.decay)
    produced = str(origin.produced)
    value = share * reference.value(prices)
    margin = reference.value(prices) / max(reference.cost(prices), 0.001)
    cost = value / margin
    factor = cost / origin.cost(prices)
    amounts = {
        g: nice(a * factor, LABOUR_STEPS if g == LABOUR_GOOD else GOODS_STEPS)
        for g, a in sorted(origin.inputs.items(), key=lambda item: item[0] == LABOUR_GOOD)
    }
    output = nice(value / float(prices[produced]), GOODS_STEPS)
    stem = recipe.method.removeprefix(f"pp_{recipe.origin}_")
    icon = None
    if "icon_type" in origin.scalars and "icon" in origin.scalars:
        icon = (origin.scalars["icon_type"], origin.scalars["icon"])
    elif (recipe.origin, stem) in names.icons:
        icon = names.icons[(recipe.origin, stem)]
    if stem in names.loc:
        base_label = f"${stem}$"
    else:
        entries = ((origin_tier.data.get("localization") or {}).get("entries")) or {}
        base_label = str(entries.get(recipe.method) or stem.replace("_", " ").title())
    return LegacyMethod(
        building=tier.building,
        slot=slot,
        name=legacy_name(tier.building, stem),
        recipe=recipe,
        share=share,
        produced=produced,
        output=output,
        amounts=amounts,
        scalars={k: reference.scalars[k] for k in COPIED_KEYS if k in reference.scalars},
        icon=icon,
        reference=reference.name,
        label=f"{base_label} {config.label_suffix}".strip(),
        desc=config.desc.replace("{origin}", f"${recipe.origin}$"),
    )


# ---------------------------------------------------------------- text editing


def _method_lines(method: LegacyMethod, method_pad: str, inner_pad: str) -> list[str]:
    rows = [f"{method_pad}{method.name} = {{"]
    if method.icon:
        rows += [f"{inner_pad}icon_type = {method.icon[0]}", f"{inner_pad}icon = {method.icon[1]}"]
    rows += [f"{inner_pad}{g} = {format_amount(a)}" for g, a in method.amounts.items()]
    rows += [f"{inner_pad}produced = {method.produced}", f"{inner_pad}output = {format_amount(method.output)}"]
    rows += [f"{inner_pad}{k} = {v}" for k, v in method.scalars.items()]
    rows.append(f"{method_pad}}}")
    return rows


def rewrite_body(body: str, methods: Sequence[LegacyMethod], prices: Mapping[str, float]) -> str:
    """The body with every legacy method removed and ``methods`` appended to their slots (ascending value, the gate's
    order for legacy methods)."""
    lines = body.split("\n")
    blocks = _spans(lines)
    by_slot: dict[int, list[LegacyMethod]] = {}
    for m in methods:
        if m.slot >= len(blocks):
            raise LegacyError(f"{m.building}: slot {m.slot} is not in the body")
        by_slot.setdefault(m.slot, []).append(m)
    for index in reversed(range(len(blocks))):
        block = blocks[index]
        children = block.children
        sample = children[0] if children else None
        header_pad = re.match(r"^\s*", lines[block.header]).group(0)
        method_pad = re.match(r"^\s*", lines[sample.header]).group(0) if sample else header_pad + "    "
        inner_pad = method_pad + (method_pad[len(header_pad):] or "    ")
        if sample is not None:
            row = next((r for r in lines[sample.header + 1 : sample.end] if r.strip()), None)
            if row is not None:
                inner_pad = re.match(r"^\s*", row).group(0)
        new = [
            row
            for m in sorted(by_slot.get(index, []), key=lambda m: m.value(prices))
            for row in _method_lines(m, method_pad, inner_pad)
        ]
        lines[block.end:block.end] = new
        for child in reversed(children):
            name = re.match(r"^\s*([A-Za-z_0-9]+)", lines[child.header]).group(1)
            if is_legacy(name):
                del lines[child.start : child.end + 1]
    return "\n".join(lines)


def _set_body(lines: list[str], body: str) -> list[str]:
    first, stop, indent = _body_region(lines)
    return lines[:first] + [(" " * indent + row) if row.strip() else "" for row in body.split("\n")] + lines[stop:]


def _set_slot_list(lines: list[str], slots: Sequence[Sequence[str]]) -> list[str]:
    """``building.production_method_slots`` method lists as ``slots`` (slot names kept)."""
    building = _top_key_line(lines, "building")
    block = _child_block(lines, building) if building is not None else None
    if block is None:
        raise LegacyError("no building mapping")
    lo, hi, child = block
    key = _key_in(lines, lo, hi, child, "production_method_slots")
    if key is None:
        raise LegacyError("no building.production_method_slots")
    end = _value_end(lines, key, hi, sequence=True)
    current = lines[key + 1 : end]
    entries = (yaml_io.safe_load("x:\n" + "\n".join(current)) or {}).get("x") or []
    if len(entries) != len(slots):
        raise LegacyError(f"production_method_slots lists {len(entries)} slots, the body has {len(slots)}")
    if [list(e.get("methods") or []) for e in entries] == [list(s) for s in slots]:
        return lines
    dash = next((_indent(l) for l in current if l.lstrip().startswith("- ")), child)
    methods_indent = next((_indent(l) for l in current if l.strip().startswith("methods:")), dash + 2)
    item_indent = next((_indent(l) for l in current if l.lstrip().startswith("- ") and _indent(l) > dash), methods_indent)
    out: list[str] = []
    for entry, names in zip(entries, slots):
        out.append(" " * dash + f"- name: {entry.get('name')}")
        out.append(" " * methods_indent + "methods:")
        out.extend(" " * item_indent + f"- {name}" for name in names)
    return lines[: key + 1] + out + lines[end:]


def _set_localization(lines: list[str], building: str, methods: Sequence[LegacyMethod]) -> list[str]:
    loc = _top_key_line(lines, "localization")
    block = _child_block(lines, loc) if loc is not None else None
    if block is None:
        if not methods:
            return lines
        raise LegacyError("no localization mapping")
    lo, hi, child = block
    key = _key_in(lines, lo, hi, child, "entries")
    if key is None:
        raise LegacyError("no localization.entries")
    end = _value_end(lines, key, hi)
    indent = next((_indent(lines[i]) for i in range(key + 1, end) if lines[i].strip()), _indent(lines[key]) + 2)
    prefix = f"pp_{building}{LEGACY_INFIX}"
    kept = [row for row in lines[key + 1 : end] if not row.strip().startswith(prefix)]
    want: list[str] = []
    for m in sorted(methods, key=lambda m: m.name):
        want.append(" " * indent + f"{m.name}: {_yaml_scalar(m.label)}")
        want.append(" " * indent + f"{m.name}_desc: {_yaml_scalar(m.desc)}")
    return lines[: key + 1] + kept + want + lines[end:]


def _set_evaluation(lines: list[str], building: str, methods: Sequence[LegacyMethod]) -> list[str]:
    prefix = f"pp_{building}{LEGACY_INFIX}"
    top = _top_key_line(lines, "evaluation")
    if top is None:
        if not methods:
            return lines
        while lines and not lines[-1].strip():
            lines.pop()
        lines = lines + ["evaluation:", "  production_methods:"]
        top = len(lines) - 2
    block = _child_block(lines, top)
    if block is None:
        lines = lines[: top + 1] + ["  production_methods:"] + lines[top + 1 :]
        block = _child_block(lines, top)
    lo, hi, child = block
    key = _key_in(lines, lo, hi, child, "production_methods")
    if key is None:
        if not methods:
            return lines
        at = _value_end(lines, top, hi)
        lines = lines[:at] + [" " * child + "production_methods:"] + lines[at:]
        key, hi = at, hi + 1
    end = _value_end(lines, key, hi)
    step = next((_indent(lines[i]) - child for i in range(key + 1, end) if lines[i].strip()), 2) or 2
    pad = " " * (child + step)
    # drop every legacy entry, then write the wanted ones at the end of production_methods
    i = key + 1
    while i < end:
        row = lines[i]
        if _indent(row) == child + step and row.strip().startswith(prefix):
            stop = _value_end(lines, i, end)
            del lines[i:stop]
            end -= stop - i
            continue
        i += 1
    want: list[str] = []
    for m in sorted(methods, key=lambda m: m.name):
        want += [f"{pad}{m.name}:", f"{pad}{' ' * step}allow_rules:"]
        want += [f"{pad}{' ' * (2 * step)}{rule}: {_yaml_scalar(text)}" for rule, text in ALLOW_RULES.items()]
    return lines[:end] + want + lines[end:]


def _advancement_entries(data: Mapping[str, Any], building: str, methods: Sequence[LegacyMethod]) -> list[dict[str, str]]:
    prefix = f"pp_{building}{LEGACY_INFIX}"
    entries: list[dict[str, str]] = []
    for entry in data.get("advancements") or []:
        if not isinstance(entry, dict) or set(entry) - {"key", "body"}:
            raise LegacyError("advancements entries other than {key, body} are not supported by the legacy pass")
        rows = [
            row
            for row in str(entry.get("body") or "").split("\n")
            if not ((m := _UNLOCK_RE.match(row)) and m.group("method").startswith(prefix))
        ]
        body = "\n".join(rows).strip("\n")
        if body.strip():
            entries.append({"key": str(entry["key"]), "body": body})
    for m in sorted(methods, key=lambda m: m.name):
        for advance in sorted(m.recipe.unlocks):
            line = f"unlock_production_method = {m.name}"
            target = next((e for e in entries if _base(e["key"]) == advance), None)
            if target is None:
                entries.append({"key": f"{INJECT}{advance}", "body": line})
            else:
                target["body"] = target["body"] + "\n" + line
    return entries


def _set_advancements(lines: list[str], data: Mapping[str, Any], building: str, methods: Sequence[LegacyMethod]) -> list[str]:
    entries = _advancement_entries(data, building, methods)
    current = [{"key": str(e.get("key")), "body": str(e.get("body") or "").strip("\n")} for e in (data.get("advancements") or [])]
    if entries == current:
        return lines
    rendered: list[str] = []
    if entries:
        rendered.append("advancements:")
        for entry in entries:
            rendered += [f"- key: {entry['key']}", "  body: |-"]
            rendered += [f"    {row}" if row.strip() else "" for row in entry["body"].split("\n")]
    top = _top_key_line(lines, "advancements")
    if top is not None:
        end = _value_end(lines, top, len(lines), sequence=True)
        while end < len(lines) and lines[end].startswith(("- ", "  ")):
            end += 1
        return lines[:top] + rendered + lines[end:]
    anchor = _top_key_line(lines, "localization")
    at = anchor if anchor is not None else len(lines)
    return lines[:at] + rendered + lines[at:]


def render_blueprint(plan: TierPlan, prices: Mapping[str, float]) -> str:
    tier = plan.tier
    raw = tier.path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    lines = raw.split("\n")
    body = str((tier.data.get("building") or {}).get("body") or "")
    new_body = rewrite_body(body, plan.methods, prices)
    if new_body.rstrip("\n") != body.rstrip("\n"):
        lines = _set_body(lines, new_body.rstrip("\n"))  # the literal block's own final newline is not a body line
    slots = [[m.name for m in slot] for slot in parse_body(new_body, tier.path)]
    lines = _set_slot_list(lines, slots)
    lines = _set_advancements(lines, tier.data, tier.building, plan.methods)
    lines = _set_localization(lines, tier.building, plan.methods)
    lines = _set_evaluation(lines, tier.building, plan.methods)
    return "\n".join(lines)


# ---------------------------------------------------------------- repo pass


def load_names(repo: Path, project: Path) -> Names:
    from prosper_or_perish_constructor.method_icons import vanilla_icons
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    root = Path(vanilla_root(repo, project))  # the install root (game/... below it)
    icons, _ = vanilla_icons(root)
    loc: dict[str, str] = {}
    folder = root / "game/main_menu/localization/english"
    pattern = re.compile(r'^\s*(?P<key>[A-Za-z_0-9.]+):\d*\s*"(?P<value>.*)"\s*$')
    for path in sorted(folder.glob("*.yml")) if folder.is_dir() else []:
        for row in path.read_text(encoding="utf-8-sig").splitlines():
            match = pattern.match(row)
            if match:
                loc.setdefault(match.group("key"), match.group("value"))
    return Names(loc, icons)


def load_prices(repo: Path, project: Path) -> dict[str, float]:
    from prosper_or_perish_constructor.production_gate import load_prices as gate_prices

    return gate_prices(repo, project)


def plan_all(repo: Path, config: LegacyConfig, prices: Mapping[str, float], names: Names) -> LegacyResult:
    result = LegacyResult()
    manifest = yaml_io.safe_load((repo / MANIFEST_RELATIVE).read_text(encoding="utf-8-sig")) or {}
    enabled = {str(k) for k, v in (manifest.get("enabled") or {}).items() if v}
    seen: dict[str, str] = {}
    for line, buildings in config.lines.items():
        try:
            tiers = [load_tier(repo, b) for b in buildings]
        except LegacyError as exc:
            result.problems.append(f"{line}: {exc}")
            continue
        for b in buildings:
            if b in seen:
                result.problems.append(f"{b} is in the {seen[b]} and the {line} line")
            seen[b] = line
            if f"buildings/{b}.yml" not in enabled:
                result.problems.append(f"{line}: {b} is not enabled in the buildings manifest")
        for plan in plan_line(line, tiers, config, prices, names):
            result.plans.append(plan)
            if plan.problems:
                result.problems.extend(f"{plan.tier.path.name}: {p}" for p in plan.problems)
                continue
            try:
                text = render_blueprint(plan, prices)
            except (LegacyError, ValueError) as exc:
                result.problems.append(f"{plan.tier.path.name}: {exc}")
                continue
            current = plan.tier.path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
            if text != current:
                plan.new_text = text
                plan.changed = True
    # legacy methods outside the lines (a building dropped from a line keeps none)
    listed = line_buildings(config)
    stray = re.compile(rf"^\s*pp_[A-Za-z_0-9]+{LEGACY_INFIX}[A-Za-z_0-9]+\s*=\s*\{{", re.MULTILINE)
    for path in sorted((repo / BLUEPRINT_ROOT_RELATIVE).glob("*.yml")):
        if path.stem not in listed and stray.search(path.read_text(encoding="utf-8-sig")):
            result.problems.append(f"{path.name}: legacy methods in a building that is in no [{CONFIG_SECTION}.lines] line")
    return result


def apply(repo: Path, project: Path, prices: Mapping[str, float] | None = None, *, write: bool = True) -> LegacyResult:
    config = load_config(project)
    prices = dict(prices) if prices is not None else load_prices(repo, project)
    names = load_names(repo, project)
    result = plan_all(repo, config, prices, names)
    if write and not result.problems:
        for plan in result.changed:
            raw = plan.tier.path.read_bytes()
            bom = raw.startswith(b"\xef\xbb\xbf")
            crlf = b"\r\n" in raw
            text = plan.new_text.replace("\n", "\r\n") if crlf else plan.new_text
            plan.tier.path.write_text(("\ufeff" if bom else "") + text, encoding="utf-8", newline="")
            result.files_changed += 1
        again = plan_all(repo, config, prices, names)
        if again.problems or again.changed:
            raise LegacyError(
                f"legacy apply is not stable: {again.problems or [p.tier.path.name for p in again.changed]}"
            )
        write_report(repo / REPORT_RELATIVE_PATH, again, prices)
        for plan, fresh in zip(result.plans, again.plans):
            fresh.changed = plan.changed
        result.plans = again.plans
    return result


def write_report(path: Path, result: LegacyResult, prices: Mapping[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["line", "building", "method", "origin", "origin_method", "steps", "share", "produced", "output", "value",
              "cost", "margin", "reference", "unlocks", "goods"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for plan in result.plans:
            for m in plan.methods:
                cost = m.cost(prices)
                writer.writerow({
                    "line": plan.line,
                    "building": m.building,
                    "method": m.name,
                    "origin": m.recipe.origin,
                    "origin_method": m.recipe.method,
                    "steps": m.recipe.steps,
                    "share": round(m.share, 4),
                    "produced": m.produced,
                    "output": format_amount(m.output),
                    "value": round(m.value(prices), 4),
                    "cost": round(cost, 4),
                    "margin": round(m.value(prices) / cost, 3) if cost else "",
                    "reference": m.reference,
                    "unlocks": " ".join(sorted(m.recipe.unlocks)),
                    "goods": " ".join(f"{g}={format_amount(a)}" for g, a in m.amounts.items()),
                })


# ---------------------------------------------------------------- checks the tests share


def lost_recipes(repo: Path, config: LegacyConfig, prices: Mapping[str, float]) -> list[str]:
    """Every recipe of a tier (own or legacy) that the next tier of its line can no longer run: no own method on a
    subset of its goods (and no other advance) and no legacy method with the same goods."""
    out: list[str] = []
    for line, buildings in config.lines.items():
        tiers = [load_tier(repo, b) for b in buildings]
        for below, tier in zip(tiers, tiers[1:]):
            mapping = map_slots(below, tier, prices)
            for s_below, s_here in mapping.items():
                here = [m for m in tier.slots[s_here] if m.produced]
                own = [m for m in here if not is_legacy(m.name)]
                legacy = {m.goods for m in here if is_legacy(m.name)}
                for m in below.slots[s_below]:
                    if not m.produced or not m.goods:
                        continue
                    unlocks = below.unlocks.get(m.name, frozenset())
                    if covered(m.goods, unlocks, own, tier.unlocks):
                        continue
                    if m.goods in legacy or any(g < m.goods for g in legacy):
                        continue
                    out.append(f"{line}: {below.building} -> {tier.building} loses {m.name} ({', '.join(sorted(m.goods))})")
    return out


def method_ratio(repo: Path, config: LegacyConfig, prices: Mapping[str, float]) -> list[tuple[str, str, float, float]]:
    """(building, legacy method, value / reference value, margin / reference margin) of every legacy method."""
    out = []
    for buildings in config.lines.values():
        for b in buildings:
            tier = load_tier(repo, b)
            for s in tier.real_slots():
                own = tier.own(s)
                if not own:
                    continue
                ref = max(own, key=lambda m: m.value(prices))
                ref_margin = ref.value(prices) / ref.cost(prices)
                for m in tier.slots[s]:
                    if is_legacy(m.name):
                        out.append((b, m.name, m.value(prices) / ref.value(prices), (m.value(prices) / m.cost(prices)) / ref_margin))
    return out
