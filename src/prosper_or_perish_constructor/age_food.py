"""Food relief by age (2026-10-03, Jan: age 2 stays tough, age 3 brings decent relief, later ages keep the progression).

One table, ``[age_food]`` in constructor.toml, sets per age:

- ``flat_food``: the ``local_monthly_food`` per staffed level of every farming building of that age;
- ``throughput``: a factor on the building's production methods (every good in and out, labour included; the
  Provision amounts follow the scaled base output, the gate leg stays as it is), against the recipe as balanced before
  this table existed (1.0 = unchanged). Each blueprint records the factor applied (``age_food_throughput``), so a new
  value rescales from the current one;
- ``advance`` / ``global_food_decay``: the age's food advance carries this change of the country's food decay (the
  base is 0.015 a month: vanilla 0.005 + PP 0.01). Province decay = stock x (local + global food decay) /
  max(1, 1 + the province's summed local_food_preservation_efficiency_modifier), EU5 1.4.

Crop farm tiers take the age of their tier advance and are rendered by ``crop_farms.py`` from this table; the other
farming buildings are listed under ``[age_food.buildings]`` and rewritten by ``ppc age-food apply`` (``check`` reports
what is off). ``upgrade_weight`` is the AI weight a farming upgrade gets where its predecessor (``obsolete``) stands:
the engine scores a building replacing its predecessor without the profit gate but with a near-zero upgrade utility
(AI_UPGRADE_BUILDING_UTILITY 0.001), so without it the AI barely upgrades (farmsteads 19 % by 1550, run b033350e).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from prosper_or_perish_constructor import provisioning, yaml_io

CONFIG_SECTION = "age_food"
APPLIED_KEY = "age_food_throughput"
ADVANCES_FILE = Path("in_game/common/advances/pp_prosperity_advances_adjustments.txt")
MOD_FOLDER = "Prosper or Perish (Population Growth & Food Rework)"
BLUEPRINTS = Path("blueprints/accepted/buildings")
# non-goods keys of a production method
METHOD_KEYS = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "no_upkeep", "ai_will_do"}
INCOME_OFFSET = 10


@dataclass(frozen=True)
class Age:
    name: str
    flat_food: float
    throughput: float
    advance: str | None = None
    global_food_decay: float = 0.0


@dataclass(frozen=True)
class AgeFoodConfig:
    ages: dict[str, Age]
    buildings: dict[str, str] = field(default_factory=dict)   # building -> age
    upgrade_weight: float = 0.0

    def age(self, name: str) -> Age:
        if name not in self.ages:
            raise ValueError(f"[{CONFIG_SECTION}] has no age {name!r}")
        return self.ages[name]


def load_config(project: Path) -> AgeFoodConfig:
    raw = tomllib.loads(Path(project).read_text(encoding="utf-8-sig")).get(CONFIG_SECTION)
    if not isinstance(raw, dict):
        return AgeFoodConfig(ages={})
    ages = {}
    for name, spec in raw.items():
        if not (isinstance(spec, dict) and name.startswith("age_")):
            continue
        ages[name] = Age(name, float(spec["flat_food"]), float(spec.get("throughput", 1.0)),
                         str(spec["advance"]) if spec.get("advance") else None, float(spec.get("global_food_decay", 0.0)))
    buildings = {str(k): str(v) for k, v in dict(raw.get("buildings", {})).items()}
    config = AgeFoodConfig(ages=ages, buildings=buildings, upgrade_weight=float(raw.get("upgrade_weight", 0.0)))
    for building, age in buildings.items():
        config.age(age)
    return config


def num(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def scaled(value: float, factor: float) -> float:
    """A goods amount times ``factor``, rounded like the blueprints: 3 decimals below 1, 2 from 1, 1 from 10."""
    v = value * factor
    digits = 3 if abs(v) < 1 else 2 if abs(v) < 10 else 1
    return round(v, digits)


def upgrade_weight_lines(predecessor: str, weight: float, indent: str = "\t") -> list[str]:
    """``ai_construct_weight`` of a farming upgrade: ``weight`` where its predecessor stands, divided by the owner's
    income like the farm weight, plus the flat capital food term. Used by buildings without a weight of their own."""
    step = "    " if indent.startswith(" ") else "\t"
    return [
        f"{indent}# AI (age_food.py): build the upgrade where its predecessor stands; the engine scores a replacement",
        f"{indent}# with a near-zero upgrade utility, so the weight carries it",
        f"{indent}ai_construct_weight = {{",
        f"{indent}{step}value = 0",
        f"{indent}{step}if = {{ limit = {{ has_building = building_type:{predecessor} }} add = {num(weight)} }}",
        f"{indent}{step}divide = {{ value = scope:owner.monthly_income_total add = {INCOME_OFFSET} }}",
        f"{indent}{step}# the AI builds up food in its capital province (pp_capital_food_weight, flat)",
        f"{indent}{step}add = pp_capital_food_weight",
        f"{indent}}}",
    ]


def throughput_allow_rules(age: str, factor: float) -> dict[str, str]:
    """Blueprint-evaluation allow reasons for a recipe scaled above the age throughput band."""
    # plain YAML scalar: no leading bracket, no ": "
    reason = f"Food relief of {age} (age_food.py, throughput x{num(factor)}) raises output per worker on purpose."
    return {"input_throughput": reason, "output_throughput": reason}


def _set_evaluation(text: str, age: str, factor: float, ratio: float) -> str:
    """Building-level throughput allow reasons (replaced when ours, kept when the blueprint has its own) and building
    throughput bands scaled by ``ratio``."""
    rules = throughput_allow_rules(age, factor)
    ev = re.search(r"(?m)^evaluation:\n", text)
    if ev is None:
        return text.rstrip("\n") + "\nevaluation:\n  allow_rules:\n" + "".join(f"    {k}: {v}\n" for k, v in rules.items())
    head = re.search(r"(?m)^  allow_rules:\n((?:    .*\n)*)", text[ev.end():])
    if head is None:
        insert = "  allow_rules:\n" + "".join(f"    {k}: {v}\n" for k, v in rules.items())
        text = text[: ev.end()] + insert + text[ev.end():]
    else:
        start, end = ev.end() + head.start(1), ev.end() + head.end(1)
        lines = [line for line in text[start:end].splitlines(keepends=True)]
        for key, reason in rules.items():
            own = [i for i, line in enumerate(lines) if line.startswith(f"    {key}:")]
            if not own:
                lines.append(f"    {key}: {reason}\n")
            elif "(age_food.py" in lines[own[0]]:
                lines[own[0]] = f"    {key}: {reason}\n"
        text = text[:start] + "".join(lines) + text[end:]
    if abs(ratio - 1.0) > 1e-9:
        tail = text[ev.end():]
        tail = re.sub(r"(?m)^(    (?:input|output)_gold_per_1k:\n      (?:max|min): )([\d.]+)",
                      lambda m: f"{m.group(1)}{num(round(float(m.group(2)) * ratio, 2))}", tail)
        text = text[: ev.end()] + tail
    return text


# ------------------------------------------------------------------------------------------------ blueprint rewrite
_METHOD = re.compile(r"(?ms)^(?P<ind>[ \t]*)(?P<key>pp_[a-z0-9_]+) = \{\n(?P<body>.*?)\n[ \t]*\}")


def _parse(body: str) -> dict[str, str]:
    out = {}
    for line in body.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = (s.strip() for s in line.split("=", 1))
            out[k] = v
    return out


def _is_number(text: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", text))


@dataclass
class Change:
    building: str
    what: list[str] = field(default_factory=list)


def rewrite_building(text: str, building: str, age: Age, upgrade_weight: float) -> tuple[str, list[str]]:
    """The blueprint text with the age's throughput and flat food applied; returns (text, changes)."""
    data = yaml_io.safe_load(text) or {}
    applied = float(data.get(APPLIED_KEY, 1.0))
    ratio = age.throughput / applied
    changes: list[str] = []
    provision = provisioning.provision_method(building)
    leg = f"pp_{building}_market_sales"
    good = provisioning.provisioned_good(building)

    if abs(ratio - 1.0) > 1e-9:
        def repl(m: re.Match) -> str:
            key = m.group("key")
            if key in (provision, leg) or not key.startswith(f"pp_{building}_"):
                return m.group(0)
            lines = m.group("body").split("\n")
            out = []
            for line in lines:
                mm = re.match(r"^(?P<lead>[ \t]*)(?P<k>[a-z_0-9]+) = (?P<v>-?\d+(?:\.\d+)?)(?P<rest>.*)$", line)
                if mm and (mm.group("k") not in METHOD_KEYS or mm.group("k") == "output"):
                    line = f"{mm.group('lead')}{mm.group('k')} = {num(scaled(float(mm.group('v')), ratio))}{mm.group('rest')}"
                out.append(line)
            return f"{m.group('ind')}{key} = {{\n" + "\n".join(out) + "\n" + m.group(0).rsplit("\n", 1)[1]

        new = _METHOD.sub(repl, text)
        if new != text:
            changes.append(f"throughput {num(applied)} -> {num(age.throughput)}")
            text = new
        # the Provision amounts follow the scaled base output (slot 0's first method)
        data = yaml_io.safe_load(text) or {}
        slots = data["building"]["production_method_slots"]
        base_key = slots[0]["methods"][0]
        base = next((_parse(m.group("body")) for m in _METHOD.finditer(text) if m.group("key") == base_key), {})
        if good and _is_number(base.get("output", "")):
            amounts = provisioning.building_amounts(building, Decimal(base["output"]),
                                                    good_price=provisioning.provisioned_good_price(good))

            def prov(m: re.Match) -> str:
                if m.group("key") != provision:
                    return m.group(0)
                body = re.sub(rf"(?m)^([ \t]*){good} = [\d.]+", lambda x: f"{x.group(1)}{good} = {provisioning.format_amount(amounts.input)}", m.group("body"))
                body = re.sub(r"(?m)^([ \t]*)output = [\d.]+", lambda x: f"{x.group(1)}output = {provisioning.format_amount(amounts.output)}", body)
                return f"{m.group('ind')}{m.group('key')} = {{\n{body}\n" + m.group(0).rsplit("\n", 1)[1]

            text = _METHOD.sub(prov, text)
        text = _set_applied(text, age.throughput)
    if abs(age.throughput - 1.0) > 1e-9 or abs(ratio - 1.0) > 1e-9:
        new = _set_evaluation(text, age.name, age.throughput, ratio)
        if new != text and abs(ratio - 1.0) <= 1e-9:
            changes.append("evaluation allow reasons")
        text = new

    flat = re.search(r"(?m)^([ \t]*)local_monthly_food = (-?[\d.]+)", text)
    if flat and abs(float(flat.group(2)) - age.flat_food) > 1e-9:
        text = text[: flat.start(2)] + num(age.flat_food) + text[flat.end(2):]
        changes.append(f"flat food {flat.group(2)} -> {num(age.flat_food)}")

    predecessor = re.search(r"(?m)^[ \t]*obsolete = ([a-z_0-9]+)", text)
    if predecessor and upgrade_weight and "ai_construct_weight" not in text:
        anchor = re.search(r"(?m)^([ \t]*)obsolete = [a-z_0-9]+\n", text)
        lines = upgrade_weight_lines(predecessor.group(1), upgrade_weight, indent=anchor.group(1))
        text = text[: anchor.end()] + "\n".join(lines) + "\n" + text[anchor.end():]
        changes.append(f"upgrade weight {num(upgrade_weight)} where {predecessor.group(1)} stands")
    return text, changes


def _set_applied(text: str, value: float) -> str:
    line = f"{APPLIED_KEY}: {num(value)}"
    if re.search(rf"(?m)^{APPLIED_KEY}:", text):
        return re.sub(rf"(?m)^{APPLIED_KEY}:.*$", line, text)
    return re.sub(r"(?m)^(tag: .*)$", lambda m: m.group(1) + "\n" + line, text, count=1)


# ------------------------------------------------------------------------------------------------------ advances
def rewrite_advances(text: str, config: AgeFoodConfig) -> tuple[str, list[str]]:
    """Each age's food advance carries its global_food_decay line (managed; 0 removes it)."""
    changes = []
    for age in config.ages.values():
        if not age.advance:
            continue
        m = re.search(rf"(?ms)^(TRY_INJECT:{age.advance} = \{{\n)(.*?)(^\}})", text)
        if not m:
            raise ValueError(f"{ADVANCES_FILE}: no TRY_INJECT:{age.advance} block")
        body = m.group(2)
        line = re.search(r"(?m)^\tglobal_food_decay = (-?[\d.]+).*\n", body)
        want = age.global_food_decay
        if (line and abs(float(line.group(1)) - want) < 1e-9) or (not line and not want):
            continue
        body = body[: line.start()] + body[line.end():] if line else body
        if want:
            body += f"\tglobal_food_decay = {num(want)}   # [age_food] {age.name} (age_food.py)\n"
        text = text[: m.start(2)] + body + text[m.end(2):]
        changes.append(f"{age.advance}: global_food_decay -> {num(want)}")
    return text, changes


def apply(repo: Path, project: Path, *, write: bool = True) -> list[Change]:
    """Rewrite (or, without ``write``, only report) the listed farming buildings and the age advances."""
    config = load_config(project)
    out: list[Change] = []
    for building, age_name in sorted(config.buildings.items()):
        path = Path(repo) / BLUEPRINTS / f"{building}.yml"
        text = path.read_text(encoding="utf-8")
        new, what = rewrite_building(text, building, config.age(age_name), config.upgrade_weight)
        if what:
            out.append(Change(building, what))
            if write:
                path.write_text(new, encoding="utf-8")
    adv = Path(repo) / "mod" / MOD_FOLDER / ADVANCES_FILE
    # hand-authored file with mixed line endings: keep them as they are
    with adv.open(encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    new, what = rewrite_advances(text, config)
    if what:
        out.append(Change(str(ADVANCES_FILE), what))
        if write:
            with adv.open("w", encoding="utf-8-sig", newline="") as handle:
                handle.write(new)
    return out
