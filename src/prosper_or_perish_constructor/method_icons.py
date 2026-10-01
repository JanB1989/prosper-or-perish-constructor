"""Production method icons (EU5 1.4): every production method names the icon the building view shows for it.

EU5 1.4 gave every vanilla production method an ``icon_type`` (``building_type``, ``goods``, ``game_concept``,
``pop_type``) and an ``icon`` key. The mod's own methods (``pp_*`` unique methods of the blueprints and the hand
overrides, and the mod's global production methods) carry none unless written by hand. This finalize step of
``ppc build`` / ``ppc sync`` fills them in the compiled mod, after the blueprints are rendered:

- a method that renames a vanilla method keeps that method's icon: ``pp_<building>_<vanilla method>`` (or
  ``pp_<vanilla method>``) of a vanilla building, or a global method ``pp_<vanilla global method>``;
- the Market gate leg (``*_market_sales``) shows the good it sells, the Provisioning switch (``*_provision``) the good it
  buys back;
- any other unique method shows its building (``icon_type = building_type``, the vanilla default);
- any other global method shows the good it produces, else its first input good.

Methods that already name an icon are left alone, so a blueprint can set its own. Copies of vanilla files (World
Builder compat) are not touched: they carry vanilla's icons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from prosper_or_perish_constructor.building_footprint import (
    BUILDING_TYPES_RELATIVE,
    VANILLA_BUILDING_TYPES_RELATIVE,
    _brace_pairs,
    _depth_zero_opens,
    _read,
    blocks,
)

PRODUCTION_METHODS_RELATIVE = Path("in_game/common/production_methods")
VANILLA_PRODUCTION_METHODS_RELATIVE = Path("game/in_game/common/production_methods")
ICON_TYPE = "icon_type"
_ENTRY_RE = re.compile(r"(?P<key>[A-Za-z_0-9:]+)\s*=\s*\{")
_SCALAR_RE = re.compile(r"^[ \t]*(?P<key>[A-Za-z_0-9]+)\s*=\s*(?P<value>[^\s{}#]+)", re.MULTILINE)
_NON_GOODS = {"produced", "output", "category", "debug_max_profit", "no_upkeep", "icon", ICON_TYPE}


@dataclass
class MethodIconsResult:
    methods_written: int = 0
    files_changed: int = 0
    by_rule: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Entry:
    key: str
    open: int
    close: int


def child_entries(text: str, open_: int, close: int) -> list[Entry]:
    """``key = { ... }`` entries directly inside the block text[open_..close]."""
    pairs = _brace_pairs(text)
    out: list[Entry] = []
    i = open_ + 1
    while i < close:
        m = _ENTRY_RE.search(text, i, close)
        if m is None:
            break
        brace = m.end() - 1
        # skip matches inside nested blocks we already passed or inside comments
        line_start = text.rfind("\n", 0, m.start()) + 1
        if "#" in text[line_start: m.start()] or brace not in pairs:
            i = m.end()
            continue
        out.append(Entry(key=m.group("key"), open=brace, close=pairs[brace]))
        i = pairs[brace] + 1
    return out


def _flat(body: str) -> dict[str, str]:
    """Top-level scalar ``key = value`` lines of a method body (nested blocks blanked)."""
    pairs = _brace_pairs(body)
    chars = list(body)
    for open_ in _depth_zero_opens(body):
        for i in range(open_ + 1, pairs[open_]):
            if chars[i] != "\n":
                chars[i] = " "
    out: dict[str, str] = {}
    for match in _SCALAR_RE.finditer("".join(chars)):
        out.setdefault(match.group("key"), match.group("value"))
    return out


def _goods(body: str) -> list[str]:
    out = []
    for key, value in _flat(body).items():
        if key in _NON_GOODS:
            continue
        try:
            float(value)
        except ValueError:
            continue
        out.append(key)
    return out


# ---------------------------------------------------------------- vanilla icons


def vanilla_icons(vanilla_root: Path) -> tuple[dict[tuple[str, str], tuple[str, str]], dict[str, tuple[str, str]]]:
    """((building, unique method) -> icon, global method -> icon) from the vanilla files."""
    unique: dict[tuple[str, str], tuple[str, str]] = {}
    for path in sorted((Path(vanilla_root) / VANILLA_BUILDING_TYPES_RELATIVE).glob("*.txt")):
        text = _read(path)
        for block in blocks(path, text):
            for group in child_entries(text, block.open, block.close):
                if group.key != "unique_production_methods":
                    continue
                for method in child_entries(text, group.open, group.close):
                    icon = _icon(text[method.open + 1: method.close])
                    if icon:
                        unique[(block.key, method.key)] = icon
    global_: dict[str, tuple[str, str]] = {}
    for path in sorted((Path(vanilla_root) / VANILLA_PRODUCTION_METHODS_RELATIVE).glob("*.txt")):
        text = _read(path)
        for block in blocks(path, text):
            icon = _icon(text[block.open + 1: block.close])
            if icon and not block.mode:
                global_[block.key] = icon
    return unique, global_


def _icon(body: str) -> tuple[str, str] | None:
    flat = _flat(body)
    if ICON_TYPE in flat and "icon" in flat:
        return flat[ICON_TYPE], flat["icon"]
    return None


# ---------------------------------------------------------------- rules


def unique_method_icon(
    building: str,
    method: str,
    body: str,
    vanilla_unique: dict[tuple[str, str], tuple[str, str]],
    vanilla_global: dict[str, tuple[str, str]],
) -> tuple[tuple[str, str], str]:
    """(icon_type, icon) of a unique method without one, and the rule that chose it."""
    for stem in (method.removeprefix(f"pp_{building}_"), method.removeprefix("pp_"), method):
        if (building, stem) in vanilla_unique:
            return vanilla_unique[(building, stem)], "vanilla"
    for stem in (method.removeprefix("pp_"), method):
        if stem in vanilla_global:
            return vanilla_global[stem], "vanilla"
    flat = _flat(body)
    if method.endswith("_market_sales") and flat.get("produced"):
        return ("goods", flat["produced"]), "market_leg"
    if method.endswith("_provision"):
        goods = _goods(body)
        if goods:
            return ("goods", goods[0]), "provision"
    return ("building_type", building), "building"


def global_method_icon(
    method: str, body: str, vanilla_global: dict[str, tuple[str, str]]
) -> tuple[tuple[str, str], str] | None:
    stem = method.removeprefix("pp_")
    if stem in vanilla_global:
        return vanilla_global[stem], "vanilla"
    flat = _flat(body)
    produced = flat.get("produced")
    if produced:
        return ("goods", produced), "goods"
    goods = _goods(body)
    if goods:
        return ("goods", goods[0]), "goods"
    return None


def insert_icon(text: str, method: Entry, icon: tuple[str, str]) -> str:
    """The text with ``icon_type`` / ``icon`` as the first lines of the method block."""
    line_start = text.rfind("\n", 0, method.open) + 1
    indent = re.match(r"[ \t]*", text[line_start:]).group(0)
    step = "\t" if ("\t" in indent or not indent) else "    "
    inner = indent + step
    body = text[method.open + 1: method.close]
    first = next((line for line in body.split("\n")[1:] if line.strip()), None) if body.startswith("\n") else None
    if first is not None and len(first) - len(first.lstrip()) > len(indent):
        inner = first[: len(first) - len(first.lstrip())]  # follow the body's own indentation
    if not body.strip():
        lines = f"\n{inner}{ICON_TYPE} = {icon[0]}\n{inner}icon = {icon[1]}\n{indent}"
        return text[: method.open + 1] + lines + text[method.close:]
    lines = f"\n{inner}{ICON_TYPE} = {icon[0]}\n{inner}icon = {icon[1]}"
    if not body.startswith("\n"):  # one-line method: put the rest on its own line
        lines += f"\n{inner}"
    return text[: method.open + 1] + lines + body + text[method.close:]


# ---------------------------------------------------------------- apply


def apply(mod_root: Path, vanilla_root: Path) -> MethodIconsResult:
    result = MethodIconsResult()
    vanilla_unique, vanilla_global = vanilla_icons(vanilla_root)
    vanilla_types = {p.name for p in (Path(vanilla_root) / VANILLA_BUILDING_TYPES_RELATIVE).glob("*.txt")}
    for path in sorted((mod_root / BUILDING_TYPES_RELATIVE).glob("*.txt")):
        if path.name in vanilla_types:
            continue
        text = _read(path)
        edits: list[tuple[Entry, tuple[str, str]]] = []
        for block in blocks(path, text):
            for group in child_entries(text, block.open, block.close):
                if group.key != "unique_production_methods":
                    continue
                for method in child_entries(text, group.open, group.close):
                    body = text[method.open + 1: method.close]
                    if ICON_TYPE in _flat(body):
                        continue
                    icon, rule = unique_method_icon(block.key, method.key, body, vanilla_unique, vanilla_global)
                    edits.append((method, icon))
                    result.by_rule[rule] = result.by_rule.get(rule, 0) + 1
        _write(path, text, edits, result)
    vanilla_methods = {p.name for p in (Path(vanilla_root) / VANILLA_PRODUCTION_METHODS_RELATIVE).glob("*.txt")}
    for path in sorted((mod_root / PRODUCTION_METHODS_RELATIVE).glob("*.txt")):
        if path.name in vanilla_methods:
            continue
        text = _read(path)
        edits = []
        for block in blocks(path, text):
            body = text[block.open + 1: block.close]
            if ICON_TYPE in _flat(body) or block.mode in {"INJECT", "TRY_INJECT"}:
                continue
            chosen = global_method_icon(block.key, body, vanilla_global)
            if chosen is None:
                continue
            icon, rule = chosen
            edits.append((Entry(key=block.key, open=block.open, close=block.close), icon))
            result.by_rule[f"global_{rule}"] = result.by_rule.get(f"global_{rule}", 0) + 1
        _write(path, text, edits, result)
    return result


def _write(path: Path, text: str, edits: list[tuple[Entry, tuple[str, str]]], result: MethodIconsResult) -> None:
    if not edits:
        return
    for method, icon in sorted(edits, key=lambda item: -item[0].open):
        text = insert_icon(text, method, icon)
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    result.methods_written += len(edits)
    result.files_changed += 1


def missing(mod_root: Path, vanilla_root: Path) -> list[str]:
    """``file: building.method`` of every mod unique method still without an icon (for checks)."""
    out: list[str] = []
    vanilla_types = {p.name for p in (Path(vanilla_root) / VANILLA_BUILDING_TYPES_RELATIVE).glob("*.txt")}
    for path in sorted((mod_root / BUILDING_TYPES_RELATIVE).glob("*.txt")):
        if path.name in vanilla_types:
            continue
        text = _read(path)
        for block in blocks(path, text):
            for group in child_entries(text, block.open, block.close):
                if group.key != "unique_production_methods":
                    continue
                for method in child_entries(text, group.open, group.close):
                    if ICON_TYPE not in _flat(text[method.open + 1: method.close]):
                        out.append(f"{path.name}: {block.key}.{method.key}")
    return out
