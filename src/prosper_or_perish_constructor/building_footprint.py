"""Building footprint: every building returns a share of its employment as flat population capacity.

Each accepted blueprint carries ``footprint: <class>``. ``[building_footprint.classes]`` in constructor.toml maps a class to
the share of one level's employment that the building houses on its own ground (``"ignore"`` leaves the building alone:
farms that take land, buildings that set their own capacity). ``ppc build`` and ``ppc sync`` write
``raw_modifier = { local_population_capacity = share x employment }`` (rounded to whole people) into the block that owns
the building in the compiled mod, after the blueprints are rendered:

- the rendered blueprint (REPLACE/CREATE, or an INJECT for vanilla buildings the mod does not otherwise change; INJECT
  adds to the vanilla definition),
- the hand-authored REPLACE for buildings the mod replaces by hand (their blueprint is disabled and only carries the tag).

``raw_modifier`` is not scaled by staffing, so the capacity stands whether or not the building is filled. A negative
share takes land away, like a farm.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
import re
import tomllib

import yaml

CONFIG_SECTION = "building_footprint"
IGNORE = "ignore"
CAPACITY_KEY = "local_population_capacity"
BLUEPRINT_ROOT_RELATIVE = Path("blueprints/accepted/buildings")
BUILDING_TYPES_RELATIVE = Path("in_game/common/building_types")
VANILLA_BUILDING_TYPES_RELATIVE = Path("game/in_game/common/building_types")
SCRIPT_VALUE_DIRS = (Path("main_menu/common/script_values"), Path("in_game/common/script_values"))
REPORT_RELATIVE_PATH = Path("artifacts/data/building_footprint/footprint.csv")
PEOPLE_STEP = Decimal("0.001")  # 1 capacity unit = 1,000 people

_TOP_RE = re.compile(r"^(?:(?P<mode>[A-Z_]+):)?(?P<key>[A-Za-z_0-9]+)\s*=\s*\{", re.MULTILINE)
_RAW_RE = re.compile(r"^(?P<indent>[ \t]*)raw_modifier\s*=\s*\{", re.MULTILINE)
_CAPACITY_LINE_RE = re.compile(rf"^[ \t]*{CAPACITY_KEY}\s*=\s*\S+[^\n]*\n?", re.MULTILINE)
_EMPLOYMENT_RE = re.compile(r"^[ \t]*employment_size\s*=\s*(?P<value>[^\s#{}]+)", re.MULTILINE)
_SCRIPT_VALUE_RE = re.compile(r"^(?:[A-Z_]+:)?(?P<key>[a-z_0-9]+)\s*=\s*(?P<value>-?[0-9.]+)\s*(?:#.*)?$", re.MULTILINE)
_INJECT_MODES = {"INJECT", "TRY_INJECT", "INJECT_OR_CREATE"}


@dataclass(frozen=True)
class FootprintConfig:
    shares: dict[str, Decimal | None]  # class -> share of employment, None = ignore


@dataclass(frozen=True)
class Block:
    path: Path
    mode: str
    key: str
    open: int  # index of the block's "{"
    close: int  # index of the matching "}"


@dataclass
class FootprintResult:
    buildings_written: int = 0
    buildings_ignored: int = 0
    files_changed: int = 0
    not_in_mod: list[str] = field(default_factory=list)
    rows: list[dict[str, object]] = field(default_factory=list)


def load_config(project: Path) -> FootprintConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION)
    if not isinstance(section, dict) or not isinstance(section.get("classes"), dict):
        raise ValueError(f"{project}: [{CONFIG_SECTION}.classes] must be a table of class = share | \"ignore\"")
    shares: dict[str, Decimal | None] = {}
    for name, value in section["classes"].items():
        if value == IGNORE:
            shares[name] = None
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            shares[name] = Decimal(str(value))
        else:
            raise ValueError(f"{project}: {CONFIG_SECTION}.classes.{name} must be a number or \"ignore\", got {value!r}")
    return FootprintConfig(shares=shares)


def blueprint_classes(repo: Path) -> dict[str, tuple[str, Path]]:
    """Building key -> (footprint class, blueprint path) for every accepted blueprint, enabled or not."""
    out: dict[str, tuple[str, Path]] = {}
    for path in sorted((repo / BLUEPRINT_ROOT_RELATIVE).glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        building = data.get("building") if isinstance(data.get("building"), dict) else {}
        key = str(building.get("key") or data.get("tag") or path.stem)
        out[key] = (str(data.get("footprint") or ""), path)
    return out


def validate(repo: Path, config: FootprintConfig, vanilla_root: Path | None) -> list[str]:
    """Every blueprint has a configured class; every vanilla building has a blueprint."""
    errors: list[str] = []
    classes = blueprint_classes(repo)
    for key, (name, path) in sorted(classes.items()):
        if not name:
            errors.append(f"{path.name}: no footprint class")
        elif name not in config.shares:
            errors.append(f"{path.name}: footprint class {name!r} is not in [{CONFIG_SECTION}.classes]")
    if vanilla_root is not None:
        for key in sorted(set(vanilla_definitions(vanilla_root)) - set(classes)):
            errors.append(f"vanilla building {key} has no blueprint (add one with a footprint class)")
    return errors


def capacity_per_level(share: Decimal, employment: Decimal) -> Decimal:
    """Capacity units per level, rounded to whole people."""
    return (share * employment).quantize(PEOPLE_STEP, rounding=ROUND_HALF_UP)


def format_units(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", "0"} else text


def apply(repo: Path, mod_root: Path, project: Path, vanilla_root: Path) -> FootprintResult:
    config = load_config(project)
    errors = validate(repo, config, vanilla_root)
    if errors:
        raise ValueError("building footprint:\n" + "\n".join(f"- {e}" for e in errors))
    values = script_values(vanilla_root, mod_root)
    vanilla = vanilla_definitions(vanilla_root)
    owners = owner_blocks(mod_root, vanilla_root)
    shadowed = [
        f"{block.path.name}: INJECT:{block.key} is ignored by the engine because the mod also defines {block.key} in {owners[block.key].path.name}"
        f" (disable its blueprint; the footprint is written into the definition)"
        for block in _inject_blocks(mod_root, vanilla_root)
        if owners[block.key].mode not in _INJECT_MODES and block.path.name.startswith("zz_pp_")
    ]
    if shadowed:
        raise ValueError("building footprint:\n" + "\n".join(f"- {s}" for s in shadowed))
    result = FootprintResult()
    edits: dict[Path, list[tuple[Block, str]]] = {}
    unresolved: list[str] = []
    for key, (name, path) in sorted(blueprint_classes(repo).items()):
        share = config.shares[name]
        if share is None:
            result.buildings_ignored += 1
            continue
        block = owners.get(key)
        if block is None:
            result.not_in_mod.append(key)
            continue
        text = _read(block.path)
        raw_employment = _employment(text[block.open + 1: block.close]) or _employment(vanilla.get(key, ""))
        employment = _resolve(raw_employment, values)
        if employment is None:
            unresolved.append(f"{key}: employment_size {raw_employment or '(none)'}")
            continue
        value = capacity_per_level(share, employment)
        edits.setdefault(block.path, []).append((block, format_units(value)))
        result.buildings_written += 1
        result.rows.append({
            "building": key, "footprint": name, "share": format_units(share), "employment": format_units(employment),
            "capacity_per_level": format_units(value), "people_per_level": int(value * 1000),
            "owner": block.path.name, "owner_mode": block.mode or "CREATE", "blueprint": path.name,
        })
    if unresolved:
        raise ValueError("building footprint: employment not resolvable:\n" + "\n".join(f"- {u}" for u in unresolved))
    for path, items in edits.items():
        text = _read(path)
        # from the end of the file so earlier offsets stay valid
        for block, value in sorted(items, key=lambda item: -item[0].open):
            body = text[block.open + 1: block.close]
            text = text[: block.open + 1] + set_capacity(body, value) + text[block.close:]
        if text != _read(path):
            path.write_text(text, encoding="utf-8-sig", newline="\n")
            result.files_changed += 1
    _write_report(repo / REPORT_RELATIVE_PATH, result.rows)
    return result


# ---------------------------------------------------------------- block editing


def set_capacity(body: str, value: str) -> str:
    """Set ``local_population_capacity`` in the body's top-level raw_modifier (one line, first block; created if absent)."""
    raws = [m for m in _RAW_RE.finditer(body) if m.end() - 1 in _depth_zero_opens(body)]
    if not raws:
        indent = _body_indent(body)
        block = f"{indent}raw_modifier = {{\n{indent}{_step(indent)}{CAPACITY_KEY} = {value}\n{indent}}}\n"
        head = body.rstrip(" \t")
        return head + ("" if head.endswith("\n") else "\n") + block
    pairs = _brace_pairs(body)
    # drop the key from every top-level raw_modifier (from the end), then set it in the first
    for match in reversed(raws):
        open_, close = match.end() - 1, pairs[match.end() - 1]
        inner = _CAPACITY_LINE_RE.sub("", body[open_ + 1: close])
        body = body[: open_ + 1] + inner + body[close:]
    first = raws[0]
    indent = first.group("indent")
    line = f"\n{indent}{_step(indent)}{CAPACITY_KEY} = {value}"
    open_ = first.end() - 1
    close = _brace_pairs(body)[open_]
    inner = body[open_ + 1: close]
    if not inner.strip():
        return body[: open_ + 1] + line + f"\n{indent}" + body[close:]
    return body[: open_ + 1] + line + inner + body[close:]


def _step(indent: str) -> str:
    return "\t" if "\t" in indent or not indent else "  "


def _body_indent(body: str) -> str:
    for line in body.splitlines():
        if line.strip() and not line.strip().startswith("#"):
            return line[: len(line) - len(line.lstrip())] or "\t"
    return "\t"


def _brace_pairs(text: str) -> dict[int, int]:
    """Open-brace index -> matching close-brace index, skipping comments and quoted strings."""
    pairs: dict[int, int] = {}
    stack: list[int] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == '"':
            j = text.find('"', i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == "{":
            stack.append(i)
        elif c == "}" and stack:
            pairs[stack.pop()] = i
        i += 1
    return pairs


def _depth_zero_opens(text: str) -> set[int]:
    pairs = _brace_pairs(text)
    tops: set[int] = set()
    end = -1
    for open_ in sorted(pairs):
        if open_ > end:
            tops.add(open_)
            end = pairs[open_]
    return tops


def blocks(path: Path, text: str | None = None) -> list[Block]:
    text = _read(path) if text is None else text
    pairs = _brace_pairs(text)
    tops = _depth_zero_opens(text)
    return [
        Block(path=path, mode=m.group("mode") or "", key=m.group("key"), open=m.end() - 1, close=pairs[m.end() - 1])
        for m in _TOP_RE.finditer(text)
        if m.end() - 1 in tops
    ]


def owner_blocks(mod_root: Path, vanilla_root: Path) -> dict[str, Block]:
    """Building key -> the mod block that carries its footprint: the last definition (REPLACE/CREATE) in load order,
    else the last INJECT. Copies of vanilla files (World Builder compat) are not owners."""
    definitions: dict[str, Block] = {}
    injects: dict[str, Block] = {}
    for block in _mod_blocks(mod_root, vanilla_root):
        (injects if block.mode in _INJECT_MODES else definitions)[block.key] = block
    return {**injects, **definitions}


def _inject_blocks(mod_root: Path, vanilla_root: Path) -> list[Block]:
    return [block for block in _mod_blocks(mod_root, vanilla_root) if block.mode in _INJECT_MODES]


def _mod_blocks(mod_root: Path, vanilla_root: Path) -> list[Block]:
    """Top-level building blocks of the mod's own building_types files, in load order."""
    vanilla_names = {p.name for p in (Path(vanilla_root) / VANILLA_BUILDING_TYPES_RELATIVE).glob("*.txt")}
    return [
        block
        for path in sorted((mod_root / BUILDING_TYPES_RELATIVE).glob("*.txt"))
        if path.name not in vanilla_names
        for block in blocks(path)
    ]


# ---------------------------------------------------------------- vanilla data


def vanilla_definitions(vanilla_root: Path) -> dict[str, str]:
    """Vanilla building key -> definition body."""
    out: dict[str, str] = {}
    for path in sorted((Path(vanilla_root) / VANILLA_BUILDING_TYPES_RELATIVE).glob("*.txt")):
        text = _read(path)
        for block in blocks(path, text):
            if not block.mode:
                out[block.key] = text[block.open + 1: block.close]
    return out


def script_values(vanilla_root: Path, mod_root: Path) -> dict[str, Decimal]:
    """Numeric script values (vanilla, then the mod's overrides)."""
    values: dict[str, Decimal] = {}
    for root in (Path(vanilla_root) / "game", mod_root):
        for folder in SCRIPT_VALUE_DIRS:
            for path in sorted((root / folder).glob("*.txt")):
                for match in _SCRIPT_VALUE_RE.finditer(_read(path)):
                    values[match.group("key")] = Decimal(match.group("value"))
    return values


def _employment(body: str) -> str:
    tops = _depth_zero_text(body)
    match = _EMPLOYMENT_RE.search(tops)
    return match.group("value") if match else ""


def _depth_zero_text(body: str) -> str:
    """The body with every nested block blanked out, so only top-level lines match."""
    pairs = _brace_pairs(body)
    chars = list(body)
    for open_ in _depth_zero_opens(body):
        for i in range(open_ + 1, pairs[open_]):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def _resolve(raw: str, values: dict[str, Decimal]) -> Decimal | None:
    if not raw:
        return None
    try:
        return Decimal(raw)
    except ArithmeticError:
        return values.get(raw)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _write_report(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["building", "footprint", "share", "employment", "capacity_per_level", "people_per_level", "owner", "owner_mode", "blueprint"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
