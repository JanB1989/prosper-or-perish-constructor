"""Production labour: every producing production method pays part of its input cost in ``manual_labor``.

Each enabled blueprint with producing methods carries a ``labour`` tag::

    labour:
      class: craft_medieval          # default for the building's producing methods
      methods:                       # per-method overrides (optional)
        pp_brewery_base: base

``[production_labour.classes]`` in constructor.toml maps a class to

- a number: the labour share of the method's total input cost at base prices (labour at its price floor),
- ``{ output_share = x }``: labour worth ``x`` of the method's output at base prices (methods without goods inputs),
- ``"keep"``: the method is left as it is (it already carried labour, or it is a technical method).

``ppc labour apply`` rewrites the method bodies in the accepted blueprints. For a share class the total input cost stays
the same: goods under ``min_good_share`` of the cost and the cheapest goods beyond ``max_goods`` are dropped, labour
takes the class share and the remaining goods scale to fill the rest. Amounts are rounded to readable steps (see ``nice``);
labour absorbs the goods' rounding. Zero-amount goods lines are left alone.
A method already within ``tolerance`` of its class is not touched, so apply is stable. ``ppc labour check`` reports
untagged methods, unknown classes and methods off their class; ``ppc build`` prints the check.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
import math
from pathlib import Path
import re
import tomllib
from typing import Any


from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from prosper_or_perish_constructor import yaml_io

CONFIG_SECTION = "production_labour"
KEEP = "keep"
BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted")
MANIFEST_RELATIVE = Path("blueprints/buildings.manifest.yml")
REPORT_RELATIVE_PATH = Path("artifacts/data/production_labour/labour.csv")
METHOD_KEYS = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "no_upkeep", "ai_will_do"}

_NUMBER_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][A-Za-z_0-9]*)\s*=\s*(?P<value>-?[0-9]*\.?[0-9]+)(?P<tail>[ \t]*(?:#.*)?)$")


@dataclass(frozen=True)
class LabourClass:
    name: str
    share: float | None = None  # labour share of the total input cost
    output_share: float | None = None  # labour worth this share of the output
    keep: bool = False


@dataclass(frozen=True)
class LabourConfig:
    good: str
    price_floor_share: float
    tolerance: float
    min_good_share: float
    max_goods: int
    classes: dict[str, LabourClass]


@dataclass(frozen=True)
class Method:
    blueprint: Path
    building: str
    name: str
    inputs: dict[str, float]  # every numeric input line, zero amounts and labour included
    produced: str | None
    output: float | None


@dataclass
class Plan:
    method: Method
    labour_class: str
    cost: float
    share_before: float | None
    share_after: float | None
    amounts: dict[str, float]  # new amounts of the positive goods (labour included); dropped goods are absent
    dropped: list[str] = field(default_factory=list)
    changed: bool = False
    problem: str | None = None


@dataclass
class LabourResult:
    plans: list[Plan] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    files_changed: int = 0

    @property
    def changed(self) -> list[Plan]:
        return [plan for plan in self.plans if plan.changed]


# ---------------------------------------------------------------- config and data


def load_config(project: Path) -> LabourConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION)
    if not isinstance(section, dict) or not isinstance(section.get("classes"), dict):
        raise ValueError(f"{project}: [{CONFIG_SECTION}] with a [{CONFIG_SECTION}.classes] table is required")
    classes: dict[str, LabourClass] = {}
    for name, value in section["classes"].items():
        if value == KEEP:
            classes[name] = LabourClass(name, keep=True)
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < 1:
            classes[name] = LabourClass(name, share=float(value))
        elif isinstance(value, dict) and isinstance(value.get("output_share"), (int, float)):
            classes[name] = LabourClass(name, output_share=float(value["output_share"]))
        else:
            raise ValueError(
                f"{project}: {CONFIG_SECTION}.classes.{name} must be a share in [0, 1), {{ output_share = x }} or \"keep\", got {value!r}"
            )
    return LabourConfig(
        good=str(section.get("good", "manual_labor")),
        price_floor_share=float(section.get("price_floor_share", 0.2)),
        tolerance=float(section.get("tolerance", 0.02)),
        min_good_share=float(section.get("min_good_share", 0.05)),
        max_goods=int(section.get("max_goods", 4)),
        classes=classes,
    )


def load_prices(repo: Path, project: Path) -> dict[str, float]:
    """Good -> default market price, parsed from the configured load order (vanilla plus the compiled mod)."""
    from eu5gameparser.domain.goods import load_goods_data

    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    parser = raw.get("parser") or {}
    load_order = repo / str(parser.get("load_order", "constructor.load_order.toml"))
    goods = load_goods_data(profile=str(parser.get("profile", "constructor")), load_order_path=load_order).goods
    return {
        str(row["name"]): float(row["default_market_price"])
        for row in goods.select("name", "default_market_price").to_dicts()
        if row["default_market_price"] is not None
    }


def enabled_blueprints(repo: Path) -> list[Path]:
    manifest = yaml_io.safe_load((repo / MANIFEST_RELATIVE).read_text(encoding="utf-8-sig")) or {}
    enabled = manifest.get("enabled") or {}
    return [repo / BLUEPRINT_ROOT_RELATIVE / entry for entry, on in enabled.items() if on and str(entry).startswith("buildings/")]


def blueprint_methods(path: Path) -> list[Method]:
    """Every production method in the blueprint body, in order."""
    data = yaml_io.safe_load(_read(path)) or {}
    building = data.get("building") if isinstance(data.get("building"), dict) else {}
    key = str(building.get("key") or data.get("tag") or path.stem)
    body = building.get("body") or ""
    if not body.strip():
        return []
    block = parse_text(f"x = {{\n{body}\n}}\n", path).entries[0].value
    methods: list[Method] = []
    for group in block.values("unique_production_methods") if isinstance(block, CList) else []:
        if not isinstance(group, CList):
            continue
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
                    blueprint=path,
                    building=key,
                    name=entry.key,
                    inputs=inputs,
                    produced=str(produced) if produced is not None and not isinstance(produced, CList) else None,
                    output=_number(entry.value.first("output")),
                )
            )
    return methods


def blueprint_tag(path: Path) -> tuple[str | None, dict[str, str]]:
    """(default class, per-method classes) of the blueprint's ``labour`` tag."""
    data = yaml_io.safe_load(_read(path)) or {}
    tag = data.get("labour")
    if tag is None:
        return None, {}
    if isinstance(tag, str):
        return tag, {}
    if not isinstance(tag, dict):
        raise ValueError(f"{path.name}: labour must be a class name or a mapping with class/methods")
    methods = tag.get("methods") or {}
    return (str(tag["class"]) if tag.get("class") else None), {str(k): str(v) for k, v in methods.items()}


def is_labour_method(method: Method, good: str) -> bool:
    """Producing methods, and any method that already pays labour. Methods that produce labour (labour yards) are out."""
    if method.produced == good:
        return False
    producing = method.produced is not None and (method.output or 0) > 0
    return producing or method.inputs.get(good, 0) != 0


# ---------------------------------------------------------------- planning


LABOUR_STEPS = ((10.0, Decimal("0.1")), (1.0, Decimal("0.05")), (0.1, Decimal("0.01")), (0.0, Decimal("0.001")))
GOODS_STEPS = ((10.0, Decimal("0.1")), (0.1, Decimal("0.01")), (0.0, Decimal("0.001")))


def nice(value: float, steps: tuple[tuple[float, Decimal], ...] = LABOUR_STEPS) -> float:
    """Round to a readable step. Labour: 0.1 from 10, 0.05 from 1, 0.01 from 0.1, else 0.001. Goods keep two
    decimals up to 10 (a 0.05 step on a dear good would move several share points onto labour); amounts below 0.1
    keep three, so small by-product methods keep their shares."""
    if value <= 0:
        return 0.0
    step = _step(value, steps)
    rounded = (Decimal(str(value)) / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
    return float(rounded if rounded > 0 else step)


def _step(value: float, steps: tuple[tuple[float, Decimal], ...] = LABOUR_STEPS) -> Decimal:
    return next(step for floor, step in steps if value >= floor)


def _on_target(current: float, target: float, tolerance: float) -> bool:
    """Labour within ``tolerance`` (absolute, in labour units) or one rounding step of the target."""
    return abs(current - target) <= max(tolerance, float(_step(max(target, 1e-9))) + 1e-9)


def plan_method(method: Method, labour_class: LabourClass, config: LabourConfig, prices: dict[str, float]) -> Plan:
    good = config.good
    labour_price = prices.get(good, 5.0) * config.price_floor_share
    goods = {g: a for g, a in method.inputs.items() if g != good and a > 0}
    missing = [g for g in goods if g not in prices]
    labour = method.inputs.get(good, 0.0)
    cost = sum(a * prices.get(g, 0.0) for g, a in goods.items()) + labour * labour_price
    share_before = (labour * labour_price / cost) if cost > 0 else None
    plan = Plan(method, labour_class.name, cost, share_before, share_before, {**goods, **({good: labour} if labour else {})})
    if missing:
        plan.problem = f"unpriced inputs {', '.join(missing)}"
        return plan
    if any(a < 0 for g, a in method.inputs.items() if g in prices) and not labour_class.keep:
        plan.problem = "negative inputs need a keep class"
        return plan
    if labour_class.keep:
        return plan

    if labour_class.output_share is not None:
        if goods:
            plan.problem = f"class {labour_class.name} is for methods without goods inputs"
            return plan
        out_price = prices.get(method.produced or "")
        if out_price is None or not method.output:
            plan.problem = "output_share class on a method without a priced output"
            return plan
        exact = labour_class.output_share * method.output * out_price / labour_price
        if labour and _on_target(labour, exact, 0.0):
            return plan
        target = nice(exact)
        plan.cost = target * labour_price
        plan.share_after = 1.0 if target else None
        plan.amounts = {good: target} if target else {}
        plan.changed = True
        return plan

    share = float(labour_class.share or 0.0)
    if cost <= 0:
        plan.problem = f"class {labour_class.name} needs goods inputs (use an output_share class)"
        return plan
    kept = _kept_goods(goods, prices, config)
    dropped = sorted(set(goods) - set(kept))
    if not dropped and _on_target(labour, share * cost / labour_price, config.tolerance * cost / labour_price):
        return plan
    kept_cost = sum(goods[g] * prices[g] for g in kept)
    factor = (cost * (1 - share)) / kept_cost if kept_cost > 0 else 0.0
    amounts = {g: nice(goods[g] * factor, GOODS_STEPS) for g in kept}
    goods_cost = sum(a * prices[g] for g, a in amounts.items())
    new_labour = nice(max(cost - goods_cost, 0.0) / labour_price)
    if new_labour:
        amounts[good] = new_labour
    current = {**goods, **({good: labour} if labour else {})}
    if amounts.keys() == current.keys() and all(math.isclose(amounts[g], current[g]) for g in amounts):
        return plan  # the rounding's fixed point: rewriting would change nothing
    plan.amounts = amounts
    plan.dropped = dropped
    plan.share_after = new_labour * labour_price / (goods_cost + new_labour * labour_price)
    plan.changed = True
    return plan


def _kept_goods(goods: dict[str, float], prices: dict[str, float], config: LabourConfig) -> list[str]:
    """Goods that stay: the dearest always, the rest while worth ``min_good_share`` of the goods cost (a ratio that
    proportional scaling leaves alone, so apply is stable), at most ``max_goods``."""
    goods_cost = sum(a * prices[g] for g, a in goods.items())
    ranked = sorted(goods, key=lambda g: goods[g] * prices[g], reverse=True)
    kept = [g for i, g in enumerate(ranked) if i == 0 or goods[g] * prices[g] >= config.min_good_share * goods_cost]
    return kept[: max(config.max_goods, 1)]


def plan_all(repo: Path, config: LabourConfig, prices: dict[str, float]) -> LabourResult:
    result = LabourResult()
    for path in enabled_blueprints(repo):
        if not path.is_file():
            continue
        methods = [m for m in blueprint_methods(path) if is_labour_method(m, config.good)]
        if not methods:
            continue
        try:
            default, overrides = blueprint_tag(path)
        except ValueError as exc:
            result.problems.append(str(exc))
            continue
        for extra in sorted(set(overrides) - {m.name for m in blueprint_methods(path)}):
            result.problems.append(f"{path.name}: labour.methods names {extra}, which is not a method of the blueprint")
        for method in methods:
            name = overrides.get(method.name, default)
            if name is None:
                result.problems.append(f"{path.name}: {method.name} has no labour class")
                continue
            labour_class = config.classes.get(name)
            if labour_class is None:
                result.problems.append(f"{path.name}: {method.name}: labour class {name!r} is not in [{CONFIG_SECTION}.classes]")
                continue
            plan = plan_method(method, labour_class, config, prices)
            if plan.problem:
                result.problems.append(f"{path.name}: {method.name}: {plan.problem}")
            result.plans.append(plan)
    return result


# ---------------------------------------------------------------- blueprint editing


def rewrite_method(text: str, method: str, amounts: dict[str, float], good: str, priced: set[str]) -> str:
    """Set the method's positive goods lines (and the labour line) to ``amounts``; goods not in ``amounts`` are removed.

    Zero-amount lines and everything that is not a priced good stay as they are. A new labour line goes after the last
    goods line, or first in the method when it has none.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    header = re.compile(rf"^[ \t]*{re.escape(method)}\s*=\s*\{{\s*(?:#.*)?$")
    starts = [i for i, line in enumerate(lines) if header.match(line)]
    if len(starts) != 1:
        raise ValueError(f"method {method}: expected one '{method} = {{' line, found {len(starts)}")
    start = starts[0]
    depth, end = 0, None
    for i in range(start, len(lines)):
        code = lines[i].split("#", 1)[0]
        depth += code.count("{") - code.count("}")
        if depth == 0:
            end = i
            break
    if end is None or end == start:
        raise ValueError(f"method {method}: the block must open and close on separate lines")
    out: list[str] = lines[: start + 1]
    last_input: int | None = None
    first_entry: int | None = None
    entry_indent: str | None = None
    labour_written = False
    depth = 1
    for i in range(start + 1, end):
        line = lines[i]
        at_top = depth == 1
        depth += line.split("#", 1)[0].count("{") - line.split("#", 1)[0].count("}")
        if at_top and first_entry is None and line.strip() and not line.strip().startswith("#"):
            first_entry = len(out)
            entry_indent = line[: len(line) - len(line.lstrip())]
        match = _NUMBER_LINE_RE.match(line) if at_top else None
        if not match or not (match.group("key") in priced or match.group("key") == good):
            out.append(line)
            continue
        key = match.group("key")
        if float(match.group("value")) == 0 and key != good:
            out.append(line)  # zero-amount goods lines stay
            last_input = len(out) - 1
            continue
        if key not in amounts:
            continue  # dropped
        out.append(f"{match.group('indent')}{key} = {format_amount(amounts[key])}{match.group('tail')}")
        last_input = len(out) - 1
        labour_written |= key == good
    if good in amounts and not labour_written:
        if entry_indent is None:
            head = lines[start]
            entry_indent = head[: len(head) - len(head.lstrip())] + "    "
        at = last_input + 1 if last_input is not None else (first_entry if first_entry is not None else len(out))
        out.insert(at, f"{entry_indent}{good} = {format_amount(amounts[good])}")
    out.extend(lines[end:])
    return newline.join(out)


def format_amount(value: float) -> str:
    text = format(Decimal(str(value)).normalize(), "f")
    return "0" if text in {"-0", "0"} else text


def apply(repo: Path, project: Path, prices: dict[str, float] | None = None, *, write: bool = True) -> LabourResult:
    """Plan (and with ``write`` rewrite) every tagged method. Rounding can leave a small method just off its class
    after one pass, so apply repeats until nothing changes (at most three passes)."""
    config = load_config(project)
    prices = prices if prices is not None else load_prices(repo, project)
    result = _apply_once(repo, config, prices, write=write)
    if not write:
        return result
    changed = {(p.method.blueprint, p.method.name) for p in result.changed}
    dropped = {(p.method.blueprint, p.method.name): set(p.dropped) for p in result.plans}
    for _ in range(2):
        if result.problems or not result.changed:
            break
        result = _apply_once(repo, config, prices, write=True)
        changed |= {(p.method.blueprint, p.method.name) for p in result.changed}
        for p in result.plans:
            dropped.setdefault((p.method.blueprint, p.method.name), set()).update(p.dropped)
    for plan in result.plans:  # report every method any pass rewrote, with every good any pass dropped
        key = (plan.method.blueprint, plan.method.name)
        plan.changed = key in changed
        plan.dropped = sorted(dropped.get(key, ()))
    result.files_changed = len({blueprint for blueprint, _ in changed})
    return result


def _apply_once(repo: Path, config: LabourConfig, prices: dict[str, float], *, write: bool) -> LabourResult:
    result = plan_all(repo, config, prices)
    if result.problems or not write:
        return result
    priced = set(prices)
    by_file: dict[Path, list[Plan]] = {}
    for plan in result.changed:
        by_file.setdefault(plan.method.blueprint, []).append(plan)
    for path, plans in by_file.items():
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        original = raw.decode("utf-8-sig")  # no newline translation: CRLF files stay CRLF
        text = original
        for plan in plans:
            text = rewrite_method(text, plan.method.name, plan.amounts, config.good, priced)
        path.write_text(("﻿" if bom else "") + text, encoding="utf-8", newline="")
        try:
            _verify(path, plans, config.good)
        except ValueError:
            path.write_text(("﻿" if bom else "") + original, encoding="utf-8", newline="")
            raise
        result.files_changed += 1
    write_report(repo / REPORT_RELATIVE_PATH, result.plans, config, prices)
    return result


def write_report(path: Path, plans: list[Plan], config: LabourConfig, prices: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["building", "method", "class", "produced", "input_cost", "labour", "labour_share", "goods", "dropped", "blueprint"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for plan in plans:
            labour = plan.amounts.get(config.good, 0.0)
            writer.writerow({
                "building": plan.method.building,
                "method": plan.method.name,
                "class": plan.labour_class,
                "produced": plan.method.produced or "",
                "input_cost": round(plan.cost, 4),
                "labour": format_amount(labour),
                "labour_share": "" if plan.share_after is None else round(plan.share_after, 4),
                "goods": " ".join(f"{g}={format_amount(a)}" for g, a in plan.amounts.items() if g != config.good),
                "dropped": " ".join(plan.dropped),
                "blueprint": plan.method.blueprint.name,
            })


# ---------------------------------------------------------------- helpers


def _verify(path: Path, plans: list[Plan], good: str) -> None:
    """The rewritten blueprint parses and every planned method carries exactly the planned positive amounts."""
    methods = {m.name: m for m in blueprint_methods(path)}
    for plan in plans:
        method = methods.get(plan.method.name)
        if method is None:
            raise ValueError(f"{path.name}: {plan.method.name} is missing after the rewrite")
        positive = {g: a for g, a in method.inputs.items() if a > 0 and (g in plan.method.inputs or g == good)}
        expected = {g: a for g, a in plan.amounts.items() if a > 0}
        if positive.keys() != expected.keys() or any(not math.isclose(positive[g], expected[g]) for g in expected):
            raise ValueError(f"{path.name}: {plan.method.name} reads back {positive}, planned {expected}")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (CList, bool)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")
