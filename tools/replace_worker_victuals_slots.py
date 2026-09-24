"""Replace the "Household Food" worker-victuals slot of calorie buildings with the Provisioning slot.

Idempotent: a rerun re-renders the Provisioning slot from the current config (amounts follow `[building_scaling]`) and
changes nothing when it is already current. The blueprints are hand-formatted, so they are edited textually (labour
methods, production-method slot list, the `unique_production_methods` block in the body, localization entries and the
per-method evaluation allow rules); nothing is round-tripped through a YAML dumper.

    uv run python tools/replace_worker_victuals_slots.py [--check]
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import re
import sys

import yaml
from eu5_building_pipeline.template import load_template
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_constructor import provisioning as pv

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"


def base_output(building: str, good: str, body: str, slot_0: tuple[str, ...]) -> Decimal:
    """Output of the first slot-0 method that produces the building's own good."""
    parsed = parse_text(f"{building} = {{\n{body}\n}}\n")
    block = parsed.entries[0].value
    assert isinstance(block, CList)
    methods: dict[str, dict[str, object]] = {}
    for group in block.values("unique_production_methods"):
        if isinstance(group, CList):
            for entry in group.entries:
                if isinstance(entry.value, CList):
                    methods[str(entry.key)] = {str(item.key): item.value for item in entry.value.entries}
    for name in slot_0:
        method = methods.get(name, {})
        if str(method.get("produced")) == good:
            return Decimal(str(method["output"]))
    raise ValueError(f"{building}: no slot-0 method produces {good}")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _scalar(value: str) -> str:
    return yaml.safe_dump({"k": value}, width=10_000, allow_unicode=True).rstrip("\n")[len("k: "):]


def _section(lines: list[str], path: tuple[str, ...]) -> tuple[int, int, int] | None:
    """(header index, first child index, end index exclusive) of the nested mapping at ``path``."""
    start, end, indent, header = 0, len(lines), -1, -1
    for key in path:
        child = 0 if indent < 0 else _child_indent(lines, start, end)
        pattern = re.compile(rf"^ {{{child}}}{re.escape(key)}:\s*$")
        found = next((i for i in range(start, end) if pattern.match(lines[i])), None)
        if found is None:
            return None
        header, indent = found, child
        start = end = found + 1
        while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > indent):
            end += 1
        while end > start and not lines[end - 1].strip():
            end -= 1
    return header, start, end


def _child_indent(lines: list[str], start: int, end: int) -> int:
    for index in range(start, end):
        if lines[index].strip():
            return _indent(lines[index])
    return 0


def _replace_entries(lines: list[str], path: tuple[str, ...], names: set[str], new: list[str]) -> list[str]:
    """Drop the child entries named ``names`` (with their nested lines) and put ``new`` where the first one was."""
    section = _section(lines, path)
    if section is None:
        raise ValueError(f"missing section {'.'.join(path)}")
    _, start, end = section
    child = _child_indent(lines, start, end)
    out = lines[:start]
    position: int | None = None
    index = start
    while index < end:
        line = lines[index]
        match = re.match(rf"^ {{{child}}}([A-Za-z0-9_.:-]+):", line)
        if match and _indent(line) == child and match.group(1) in names:
            if position is None:
                position = len(out)
            index += 1
            while index < end and (not lines[index].strip() or _indent(lines[index]) > child):
                index += 1
            continue
        out.append(line)
        index += 1
    if position is None:
        position = len(out)
    body = [" " * child + item for item in new]
    return out[:position] + body + out[position:] + lines[end:]


def _replace_body_block(lines: list[str], building: str, rendered: pv.ProvisioningAmounts, good: str) -> list[str]:
    markers = (f"pp_{building}_worker_victuals", pv.provision_method(building))
    index = 0
    while index < len(lines):
        match = re.match(r"^( *)unique_production_methods\s*=\s*\{\s*$", lines[index])
        if not match:
            index += 1
            continue
        depth, end = 0, index
        for end in range(index, len(lines)):
            code = lines[end].split("#", 1)[0]
            depth += code.count("{") - code.count("}")
            if depth == 0:
                break
        block = "\n".join(lines[index : end + 1])
        if any(re.search(rf"\b{re.escape(marker)}\s*=", block) for marker in markers):
            slot = pv.render_slot(building, good, rendered, indent=match.group(1)).split("\n")
            return lines[:index] + slot + lines[end + 1 :]
        index = end + 1
    raise ValueError(f"{building}: no worker-victuals or provisioning block in the body")


def rewrite(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    template = load_template(path)
    building = template.key
    good = pv.provisioned_good(building)
    assert good is not None, building
    slots = template.production_method_slots
    slot_index = next(
        i
        for i, slot in enumerate(slots)
        if any(m.endswith(f"pp_{building}_worker_victuals") or m == pv.provision_method(building) for m in slot.methods)
    )
    slot_name = slots[slot_index].name
    amounts = pv.provisioning_amounts(base_output(building, good, template.building_body, tuple(slots[0].methods)))
    provision, sell = pv.slot_methods(building)
    old_methods = {f"pp_{building}_no_worker_victuals", f"pp_{building}_worker_victuals"}
    all_methods = old_methods | {provision, sell}

    lines = text.split("\n")

    # labour: both Provisioning methods are left as authored
    lines = _replace_entries(lines, ("labour", "methods"), all_methods, [f"{provision}: keep", f"{sell}: keep"])

    # production_method_slots list (outside the body)
    body_start = next(i for i, line in enumerate(lines) if re.match(r"^ *body:\s*\|", line))
    for i in range(body_start):
        lines[i] = re.sub(rf"^(\s*- ){re.escape(f'pp_{building}_no_worker_victuals')}\s*$", rf"\g<1>{provision}", lines[i])
        lines[i] = re.sub(rf"^(\s*- ){re.escape(f'pp_{building}_worker_victuals')}\s*$", rf"\g<1>{sell}", lines[i])

    # the slot block in the body
    lines = _replace_body_block(lines, building, amounts, good)

    # localization
    entries = pv.slot_localization(building, good, slot_name)
    slot_key = f"{building}_{slot_name}"
    slot_label = entries.pop(slot_key)
    loc_names = {n for m in all_methods for n in (m, f"{m}_desc")}
    lines = _replace_entries(lines, ("localization", "entries"), loc_names, [f"{k}: {_scalar(v)}" for k, v in entries.items()])
    loc = _section(lines, ("localization", "entries"))
    assert loc is not None
    for i in range(loc[1], loc[2]):
        match = re.match(rf"^( +){re.escape(slot_key)}:", lines[i])
        if match:
            lines[i] = f"{match.group(1)}{slot_key}: {_scalar(slot_label)}"
            break
    else:
        lines = _replace_entries(lines, ("localization", "entries"), {slot_key}, [f"{slot_key}: {_scalar(slot_label)}"])

    # evaluation allow rules per method
    if _section(lines, ("evaluation", "production_methods")) is not None:
        new: list[str] = []
        for method, config in pv.evaluation_rules(building).items():
            new.append(f"{method}:")
            new.append("  allow_rules:")
            for rule, reason in config["allow_rules"].items():
                new.append(f"    {rule}: {_scalar(reason)}")
        lines = _replace_entries(lines, ("evaluation", "production_methods"), all_methods, new)

    updated = "\n".join(lines)
    if updated != text:
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + updated.encode("utf-8"))
    return text, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report blueprints that are not current, write nothing")
    args = parser.parse_args()
    stale: list[str] = []
    for building in pv.PROVISIONING_BUILDINGS:
        path = BLUEPRINTS / f"{building}.yml"
        original = path.read_bytes()
        before, after = rewrite(path)
        if args.check and before != after:
            path.write_bytes(original)
        if before != after:
            stale.append(building)
        template = load_template(path)
        assert pv.slot_methods(building) in {tuple(slot.methods) for slot in template.production_method_slots}, building
        assert "_worker_victuals" not in path.read_text(encoding="utf-8-sig"), building
    verb = "stale" if args.check else "updated"
    print(f"{len(stale)} {verb}: {', '.join(stale) or '-'}")
    return 1 if args.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
