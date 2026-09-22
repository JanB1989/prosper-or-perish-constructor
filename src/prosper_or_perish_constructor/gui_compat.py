"""Keep the mod's modified GUI types when other mods re-declare the vanilla ones.

GUI types are global: a later mod that declares a type of the same name replaces the mod's version everywhere.
The Community Mod Framework (CMF) re-declares every vanilla type of the windows it extracts (for example
``location_card`` from location_window.gui) and loads after this mod in a normal playset, so the population
capacity readout and the stored-food view fell back to vanilla. File names do not help: across mods the engine
loads GUI files in mod order, not by path.

Each protected type is therefore copied under a ``pp_`` name next to its definition and the mod's own windows
instantiate the copy. The original keeps its name because vanilla windows the mod does not ship use it too.
``strip`` removes the copies (run before the food-storage GUI compile, which counts its gauge lines per file) and
``protect`` writes them again from the current definitions (run after it).
"""

from __future__ import annotations

import re
from pathlib import Path

GUI = Path("in_game/gui")
# definition file -> {type: files whose instances use the mod's copy}
PROTECTED: dict[str, dict[str, tuple[str, ...]]] = {
    "location_window.gui": {"location_card": ("location_window.gui", "location_production_lateralview.gui")},
    "food_production_lateralview.gui": {"food_production_province": ("food_production_lateralview.gui",)},
}
PREFIX = "pp_"


def _type_span(text: str, name: str) -> tuple[int, int] | None:
    m = re.search(rf"(?m)^[ \t]*type[ \t]+{name}[ \t]*=[ \t]*\w+[ \t]*\{{", text)
    if not m:
        return None
    depth = 0
    quoted = comment = False
    for i in range(text.index("{", m.start()), len(text)):
        c = text[i]
        if comment:
            comment = c != "\n"
        elif quoted:
            quoted = c != '"'
        elif c == "#":
            comment = True
        elif c == '"':
            quoted = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return m.start(), i + 1
    raise ValueError(f"unbalanced type {name}")


def _instances(text: str, old: str, new: str) -> tuple[str, int]:
    return re.subn(rf"(?m)^([ \t]*){old}([ \t]*=[ \t]*\{{)", rf"\g<1>{new}\g<2>", text)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _write(path: Path, text: str) -> None:
    path.write_text("﻿" + text, encoding="utf-8", newline="")


def strip(mod_root: Path) -> None:
    """Remove the copies and point the instances back at the original types."""
    for definition, types in PROTECTED.items():
        for name, users in types.items():
            for user in {definition, *users}:
                path = mod_root / GUI / user
                if not path.is_file():
                    continue
                text = _read(path)
                span = _type_span(text, PREFIX + name)
                if span:
                    # protect() inserted exactly "\n\n" + the copy (which starts with the line's indentation)
                    start = text.rfind("\n", 0, span[0]) + 1
                    if text[start - 2:start] == "\n\n":
                        start -= 2
                    text = text[:start] + text[span[1]:]
                text, _ = _instances(text, PREFIX + name, name)
                _write(path, text)


def protect(mod_root: Path) -> dict[str, int]:
    """Copy each protected type under the pp_ name and let the mod's windows use it."""
    strip(mod_root)
    report: dict[str, int] = {}
    for definition, types in PROTECTED.items():
        path = mod_root / GUI / definition
        if not path.is_file():
            continue
        text = _read(path)
        for name in types:
            span = _type_span(text, name)
            if not span:
                raise ValueError(f"{definition}: type {name} not found")
            line_start = text.rfind("\n", 0, span[0]) + 1
            block = text[line_start:span[1]]
            copy = re.sub(rf"type([ \t]+){name}\b", rf"type\g<1>{PREFIX}{name}", block, count=1)
            text = text[: span[1]] + "\n\n" + copy + text[span[1]:]
        _write(path, text)
        for name, users in types.items():
            count = 0
            for user in users:
                user_path = mod_root / GUI / user
                user_text, n = _instances(_read(user_path), name, PREFIX + name)
                _write(user_path, user_text)
                count += n
            if not count:
                raise ValueError(f"no instance of {name} found in {users}")
            report[name] = count
    return report
