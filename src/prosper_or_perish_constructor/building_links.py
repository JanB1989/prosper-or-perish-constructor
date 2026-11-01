"""Building names in player text are links (Jan, 2026-10-24): hovering a building's name shows the building.

A building in localization is ``[ShowBuildingTypeName('<key>')|e]``. Slot titles, price labels, method names and
descriptions were imported or written with typed names ("Beer Workshop Work", "Incamisana Price", "... shares the land
with Marled Fields"); ``apply`` rewrites every localization entry of the accepted blueprints, the source of the
rendered localization, except a building's own name entry (key = a building key): the blueprint's own typed name (its
game name or its key in words, "Cloth Manufactory") becomes its link, and so does any other building's game name. A
game name two buildings share (Caravanserai, Academy of Sciences) is left for a hand link; so is a multi-line entry
(``apply`` raises). ``typed_names`` is the check the tests run on the built mod (tests/test_building_links.py).

    uv run python -m prosper_or_perish_constructor.building_links [--check]
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from prosper_or_perish_constructor import yaml_io

ROOT = Path(__file__).resolve().parents[2]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
BLUEPRINTS = Path("blueprints/accepted/buildings")
_DEFINITION = re.compile(r"^(?:[A-Z_]+:)?(\w+)\s*=\s*\{", re.MULTILINE)
_ENTRY = re.compile(r'^\s*([\w.]+):\d*\s*"(.*)"\s*$')
_LINKS = re.compile(r"\[[^\]]*\]|\$[^$]*\$")   # links, scripted text and $references$ are not typed names


def link(key: str) -> str:
    return f"[ShowBuildingTypeName('{key}')|e]"


def words(key: str) -> str:
    """A key in words, as the imported labels wrote it: cloth_manufactory -> Cloth Manufactory."""
    return " ".join(part.capitalize() for part in key.split("_") if part)


def building_keys(roots: Iterable[Path]) -> set[str]:
    keys: set[str] = set()
    for root in roots:
        for path in (Path(root) / "in_game/common/building_types").glob("*.txt"):
            keys.update(_DEFINITION.findall(path.read_text(encoding="utf-8-sig")))
    return keys


def building_names(vanilla_game: Path, mod_root: Path) -> dict[str, str]:
    """Building key -> its English game name (the mod's text over vanilla's), for names that are plain text."""
    keys = building_keys([vanilla_game, mod_root])
    loc: dict[str, str] = {}
    for folder in (vanilla_game / "main_menu/localization/english", mod_root / "main_menu/localization/english",
                   mod_root / "main_menu/localization/replace/english"):
        for path in sorted(folder.rglob("*.yml")):
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if (entry := _ENTRY.match(line)) and entry[1] in keys:
                    loc[entry[1]] = entry[2]
    return {key: text for key, text in loc.items() if text and "$" not in text and "[" not in text}


def _pattern(names: Iterable[str]) -> re.Pattern[str]:
    alternatives = sorted({n for n in names if n}, key=len, reverse=True)   # longest first: Brewery Mill before Brewery
    return re.compile(r"(?<![\w'])(" + "|".join(map(re.escape, alternatives)) + r")(?![\w'])")


def typed_names(text: str, building: str | None, names: Mapping[str, str]) -> list[str]:
    """Building names typed as plain text in ``text``: any building's game name, and ``building``'s own key in words."""
    own = [names.get(building, ""), words(building)] if building else []
    return _pattern([*names.values(), *own]).findall(_LINKS.sub(" ", text))


def linked(text: str, building: str | None, names: Mapping[str, str]) -> str:
    """``text`` with every typed building name replaced by its link; ``building``'s own name (game name or key in
    words) links to it. A game name two buildings share is left alone (which one it means is unknown)."""
    by_name: dict[str, str | None] = {}
    for key, name in names.items():
        by_name[name] = None if name in by_name and by_name[name] != key else key
    if building:
        by_name[words(building)] = by_name[names.get(building, words(building))] = building
    pattern = _pattern(by_name)
    parts = re.split(r"(\[[^\]]*\]|\$[^$]*\$)", text)   # odd parts are links, kept as they are
    for index in range(0, len(parts), 2):
        parts[index] = pattern.sub(lambda m: link(by_name[m[1]]) if by_name[m[1]] else m[1], parts[index])
    return "".join(parts)


def _scalar(text: str) -> str:
    return json.dumps(text, ensure_ascii=False) if text.startswith("[") or ": " in text or "#" in text else text


def _entries_block(lines: list[str]) -> range:
    """The line numbers of the ``localization: entries:`` mapping (top-level ``localization``)."""
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "localization:"), None)
    if start is None:
        return range(0)
    entries = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "entries:"), None)
    if entries is None:
        return range(0)
    indent = len(lines[entries]) - len(lines[entries].lstrip())
    end = entries + 1
    while end < len(lines) and (not lines[end].strip() or len(lines[end]) - len(lines[end].lstrip()) > indent):
        end += 1
    return range(entries + 1, end)


def apply(repo: Path, names: Mapping[str, str], *, write: bool = True) -> list[str]:
    """Link the typed building names in every localization entry of every accepted blueprint (slot titles, price
    labels, method names, descriptions), except a building's own name entry; the changed keys."""
    changed: list[str] = []
    for path in sorted((repo / BLUEPRINTS).glob("*.yml")):
        text = path.read_bytes().decode("utf-8")   # line endings kept as they are (some blueprints are CRLF)
        data = yaml_io.safe_load(text) or {}
        building = str((data.get("building") or {}).get("key") or "")
        entries = (data.get("localization") or {}).get("entries") or {}
        if not building or not isinstance(entries, dict):
            continue
        lines = text.splitlines(keepends=True)
        block = _entries_block(lines)
        updated: dict[str, str] = {}
        for key, value in entries.items():
            if key == building or key in names or not isinstance(value, str):
                continue   # a building's own name is plain text
            new = linked(value, building, names)
            if new == value:
                continue
            line = re.compile(rf"^(?P<indent>\s+){re.escape(key)}:\s.*$")
            for index in block:
                if (m := line.match(lines[index].rstrip("\r\n"))):
                    if (yaml_io.safe_load(lines[index]) or {}).get(key) != value:
                        raise ValueError(f"{path.name}: {key} is not on one line; link it by hand")
                    ending = lines[index][len(lines[index].rstrip("\r\n")):]
                    lines[index] = f"{m['indent']}{key}: {_scalar(new)}{ending}"
                    break
            else:
                raise ValueError(f"{path.name}: {key} is not on one line; link it by hand")
            updated[key] = new
        if not updated:
            continue
        written = ((yaml_io.safe_load("".join(lines)) or {}).get("localization") or {}).get("entries") or {}
        if bad := [key for key, new in updated.items() if written.get(key) != new]:
            raise ValueError(f"{path.name}: {', '.join(bad)} would not read back as written; link by hand")
        changed.extend(updated)
        if write:
            path.write_bytes("".join(lines).encode("utf-8"))
    return changed


def main(argv: list[str]) -> int:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    names = building_names(game_root(vanilla_root(ROOT, ROOT / "constructor.toml")), MOD_ROOT)
    changed = apply(ROOT, names, write="--check" not in argv)
    print(f"building links: {len(changed)} blueprint texts {'to link' if '--check' in argv else 'linked'}")
    return 1 if changed and "--check" in argv else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
