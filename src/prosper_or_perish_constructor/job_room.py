"""Job room: a production building's room for its workers' class follows its staffing (2026-11-27, Jan).

The engine counts a building's jobs (employment_size x level) in its pop type's equilibrium whether the jobs are
offered or not: a building that laid its workers off, or that never found any, still lets people promote into the
class, and they sit idle (run b18a10d6, 1837: 1.5 M burghers and 15.9 M laborers unemployed next to unfilled jobs in
open buildings). Jan: "If a building is full, it should give ... just what its employment size is. But if it's empty,
it should give not what its employment size is ... I want surplus to demote."

Two lines per level do that, both for the building's own pop type and both the size of its jobs E:

    raw_modifier = { local_<pop>_desired_pop = -E }   # x input fulfilment
    modifier     = { local_<pop>_desired_pop =  E }   # x input fulfilment x staffing

Jobs and flat desired pop go into one sum in the engine, so the building's room is E x (1 - f + f x staffing), f the
average input fulfilment of its method slots: E when fully staffed, E x staffing when its inputs are supplied, and
never more than E. A new building opens no room of its own; it hires from the spare room the location already has
(the location ranks give burghers and laborers flat room) and brings its own room in as it fills. The AI counts both
lines in full, so they cancel in its score, and it values burgher and laborer room at zero anyway.

A closed building applies neither block and keeps all its jobs in the equilibrium, which is why production buildings
cannot be closed any more (building_shutdown.py). Read from the 1.4.9 code and private notes, not tested in game.

Written at finalize, after the employment cut (it reads the final employment_size), into every blueprint building
with a goods output whose pop type is in ``[job_room] pop_types``, except food makers: buildings that make a staple
food, Province Food or victuals, and the Construction Plan's kitchens, taverns, granaries, granges and yards (Jan:
they are supposed to hire and fire with the store), and ``[job_room] not_buildings``. The lines carry a marker comment;
a building that leaves the set loses them again. A line of the same key the building already has in that block is
folded into ours (the engine would otherwise see the key twice) and comes back when ours goes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import re
import tomllib

from prosper_or_perish_constructor import building_footprint as bf
from prosper_or_perish_constructor import building_shutdown as bs

CONFIG_SECTION = "job_room"
MARKER = "# job_room"
BLOCKS = (("raw_modifier", -1), ("modifier", 1))  # block -> sign of the line
FOOD_GOODS = ("local_food", "victuals")  # beside the staple foods

_POP_RE = re.compile(r"^[ \t]*pop_type\s*=\s*(?P<pop>[A-Za-z_0-9]+)", re.MULTILINE)
_EMPLOYMENT_RE = re.compile(r"^[ \t]*employment_size\s*=\s*(?P<value>[^\s#{}]+)", re.MULTILINE)
_MARKED_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>local_[a-z_0-9]+_desired_pop)\s*=\s*\S+[ \t]*#\s*job_room(?:[ \t]+base[ \t]+(?P<base>-?[0-9.]+))?[^\n]*\n?",
    re.MULTILINE,
)
_PRODUCED_GOOD_RE = re.compile(r"(?<![A-Za-z_0-9])produced\s*=\s*(?P<good>[A-Za-z_0-9]+)")


@dataclass(frozen=True)
class Config:
    pop_types: frozenset[str]
    not_buildings: frozenset[str]


@dataclass
class Result:
    written: list[str] = field(default_factory=list)
    food: list[str] = field(default_factory=list)
    other_pop: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    files_changed: int = 0


def load_config(project: Path) -> Config:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig")).get(CONFIG_SECTION)
    if not isinstance(raw, dict) or not isinstance(raw.get("pop_types"), list):
        raise ValueError(f"{project}: [{CONFIG_SECTION}] needs pop_types (a list of pop types)")
    return Config(frozenset(raw["pop_types"]), frozenset(raw.get("not_buildings", [])))


def food_goods() -> frozenset[str]:
    from prosper_or_perish_constructor.staple_foods import staple_foods

    return frozenset(staple_foods()) | frozenset(FOOD_GOODS)


def shared_method_goods(vanilla_root: Path, mod_root: Path) -> dict[str, frozenset[str]]:
    """Shared production method name -> the goods it produces."""
    out: dict[str, frozenset[str]] = {}
    for folder in bs.PRODUCTION_METHOD_DIRS:
        for path in [*bf.vanilla_files(vanilla_root, folder), *sorted((mod_root / folder).glob("*.txt"))]:
            text = bf._read(path)
            for block in bf.blocks(path, text):
                out[block.key] = frozenset(m.group("good") for m in _PRODUCED_GOOD_RE.finditer(text[block.open + 1: block.close]))
    return out


def produced_goods(body: str, shared: dict[str, frozenset[str]]) -> frozenset[str]:
    goods = {m.group("good") for m in _PRODUCED_GOOD_RE.finditer(body)}
    for match in bs._METHOD_LIST_RE.finditer(body):
        for name in re.findall(r"[A-Za-z_0-9]+", match.group("body")):
            goods |= shared.get(name, frozenset())
    return frozenset(goods)


def plan_food_buildings(project: Path) -> frozenset[str]:
    """The Construction Plan's kitchens, taverns, granaries, granges and yards."""
    from prosper_or_perish_constructor import construction_plan as cp

    config = cp.load_config(project)
    return frozenset(config.kitchens) | frozenset(config.taverns) | frozenset(config.granaries) | frozenset(config.granges) | frozenset(config.yards)


def fmt(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in ("-0", "") else text


def _top_block(body: str, name: str) -> tuple[re.Match[str], int, int] | None:
    """The first top-level ``name = { ... }`` of the body: (match, open, close)."""
    zero = bf._depth_zero_opens(body)
    pairs = bf._brace_pairs(body)
    for match in re.finditer(rf"^(?P<indent>[ \t]*){name}\s*=\s*\{{", body, re.MULTILINE):
        if match.end() - 1 in zero:
            return match, match.end() - 1, pairs[match.end() - 1]
    return None


def _clear(body: str, drop_empty: bool) -> str:
    """Take our marked lines out of the top-level modifier blocks: a folded line comes back at its base value. A block
    left empty goes with ``drop_empty`` (the building leaves the set); otherwise it stays where it is, so writing the
    lines again puts them back in the same place whatever later passes appended to the building."""
    for name, _sign in BLOCKS:
        found = _top_block(body, name)
        if found is None:
            continue
        match, open_, close = found
        inner = body[open_ + 1: close]
        if MARKER not in inner:
            continue

        def restore(m: re.Match[str]) -> str:
            return f"{m.group('indent')}{m.group('key')} = {m.group('base')}\n" if m.group("base") is not None else ""

        inner = _MARKED_RE.sub(restore, inner)
        if inner.strip() or not drop_empty:
            body = body[: open_ + 1] + inner + body[close:]
        else:
            end = close + 1 + (body[close + 1: close + 2] == "\n")
            body = body[: match.start()] + body[end:]
    return body


def set_room(body: str, pop: str | None, employment: Decimal | None) -> str:
    """The body with the two job room lines of ``pop`` at ``employment`` (None: without them)."""
    body = _clear(body, drop_empty=pop is None or employment is None)
    if pop is None or employment is None:
        return body
    key = f"local_{pop}_desired_pop"
    own = re.compile(rf"^[ \t]*{key}\s*=\s*(?P<value>-?[0-9.]+)[^\n]*\n?", re.MULTILINE)
    for name, sign in BLOCKS:
        value = employment * sign
        found = _top_block(body, name)
        if found is None:
            indent = bf._body_indent(body)
            block = f"{indent}{name} = {{\n{indent}{bf._step(indent)}{key} = {fmt(value)} {MARKER}\n{indent}}}\n"
            head = body.rstrip(" \t")
            body = head + ("" if head.endswith("\n") or not head else "\n") + block
            continue
        match, open_, close = found
        indent = match.group("indent")
        inner = body[open_ + 1: close]
        note = MARKER
        existing = own.search(inner)
        if existing:
            base = Decimal(existing.group("value"))
            value += base
            note = f"{MARKER} base {fmt(base)}"
            inner = inner[: existing.start()] + inner[existing.end():]
        line = f"\n{indent}{bf._step(indent)}{key} = {fmt(value)} {note}"
        if not inner.strip():
            body = body[: open_ + 1] + line + f"\n{indent}" + body[close:]
        else:
            body = body[: open_ + 1] + line + ("" if inner.startswith("\n") else "\n") + inner + body[close:]
    return body


def targets(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> tuple[dict[str, tuple[str, Decimal]], Result]:
    """Building key -> (pop type, employment per level) for the buildings that carry the lines, and who was left out."""
    config = load_config(project)
    owners = bf.owner_blocks(mod_root, vanilla_root)
    vanilla = bf.vanilla_definitions(vanilla_root)
    values = bf.script_values(vanilla_root, mod_root)
    shared = shared_method_goods(vanilla_root, mod_root)
    food = food_goods()
    plan_food = plan_food_buildings(project)
    result = Result()
    out: dict[str, tuple[str, Decimal]] = {}
    unresolved: list[str] = []
    for key in bs.producers(repo, mod_root, vanilla_root):
        block = owners[key]
        text = bf._read(block.path)
        body = text[block.open + 1: block.close]
        inherited = vanilla.get(key, "") if block.mode in bf._INJECT_MODES else ""
        if key in config.not_buildings:
            result.excluded.append(key)
            continue
        if key in plan_food or produced_goods(body + "\n" + inherited, shared) & food:
            result.food.append(key)
            continue
        tops = bf._depth_zero_text(body) + "\n" + (bf._depth_zero_text(inherited) if inherited else "")
        pop = _POP_RE.search(tops)
        if not pop or pop.group("pop") not in config.pop_types:
            result.other_pop.append(key)
            continue
        size = _EMPLOYMENT_RE.search(tops)
        employment = bf._resolve(size.group("value"), values) if size else None
        if employment is None or employment <= 0:
            unresolved.append(f"{key}: employment_size {size.group('value') if size else '(none)'}")
            continue
        if block.mode in bf._INJECT_MODES:
            unresolved.append(f"{key}: an INJECT cannot add to the vanilla modifier blocks; make the blueprint a REPLACE")
            continue
        out[key] = (pop.group("pop"), employment)
    if unresolved:
        raise ValueError("job room:\n" + "\n".join(f"- {u}" for u in unresolved))
    result.written = sorted(out)
    return out, result


def apply(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> Result:
    wanted, result = targets(repo, mod_root, project, vanilla_root)
    owners = bf.owner_blocks(mod_root, vanilla_root)
    edits: dict[Path, list[tuple[bf.Block, tuple[str, Decimal] | None]]] = {}
    for key, _rule in bs.blueprint_rules(repo).items():
        block = owners.get(key)
        if block is not None and block.mode not in bf._INJECT_MODES:
            edits.setdefault(block.path, []).append((block, wanted.get(key)))
    for path, items in edits.items():
        original = bf._read(path)
        text = original
        for block, target in sorted(items, key=lambda item: -item[0].open):
            body = text[block.open + 1: block.close]
            if target is None and MARKER not in body:
                continue
            new = set_room(body, *(target if target else (None, None)))
            text = text[: block.open + 1] + new + text[block.close:]
        if text != original:
            path.write_text(text, encoding="utf-8-sig", newline="\n")
            result.files_changed += 1
    return result


def check(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> list[str]:
    """Buildings whose compiled definition does not carry exactly the two lines it should (run ppc build / sync)."""
    wanted, _result = targets(repo, mod_root, project, vanilla_root)
    owners = bf.owner_blocks(mod_root, vanilla_root)
    problems: list[str] = []
    for key, _rule in sorted(bs.blueprint_rules(repo).items()):
        block = owners.get(key)
        if block is None or block.mode in bf._INJECT_MODES:
            continue
        text = bf._read(block.path)
        body = text[block.open + 1: block.close]
        target = wanted.get(key)
        if set_room(body, *(target if target else (None, None))) != body:
            problems.append(f"{key}: job room lines not written (run ppc build)")
    return problems


def summary(result: Result) -> str:
    return (
        f"Job room: {len(result.written)} production buildings give room for their class only as far as they are staffed "
        f"({len(result.food)} food makers and {len(result.other_pop)} of other pop types left out"
        + (f", {len(result.excluded)} excluded by name" if result.excluded else "")
        + f"), {result.files_changed} files changed."
    )
