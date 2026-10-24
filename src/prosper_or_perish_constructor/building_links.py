"""Building names in player text are links (Jan, 2026-10-24): hovering a building's name shows the building.

A building in localization is ``[ShowBuildingTypeName('<key>')|e]``. Slot titles and price labels were imported as
typed names ("Beer Workshop Work", "Incamisana Price"); ``apply`` rewrites them in the accepted blueprints, the
source of the rendered localization: the building's own typed name (its game name or its key in words, "Cloth
Manufactory") becomes its link, and so does any other building's game name. ``typed_names`` is the check the tests run
on the built mod (tests/test_building_links.py).

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


def labels(key: str, entries: Mapping[str, object], prices: Iterable[str]) -> list[str]:
    """The slot titles (``<key>_slot_<n>``) and price labels of one blueprint's building."""
    wanted = set(prices)
    return [k for k in entries if re.fullmatch(rf"{re.escape(key)}_slot_\d+", k) or k in wanted]


def _scalar(text: str) -> str:
    return json.dumps(text, ensure_ascii=False) if text.startswith("[") or ": " in text or "#" in text else text


def apply(repo: Path, names: Mapping[str, str], *, write: bool = True) -> list[str]:
    """Link the typed building names in every accepted blueprint's slot titles and price labels; the changed keys."""
    changed: list[str] = []
    for path in sorted((repo / BLUEPRINTS).glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        data = yaml_io.safe_load(text) or {}
        building = str((data.get("building") or {}).get("key") or "")
        entries = (data.get("localization") or {}).get("entries") or {}
        prices = [str(p.get("key")) for p in data.get("prices") or [] if isinstance(p, dict)]
        if not building or not isinstance(entries, dict):
            continue
        lines = text.splitlines(keepends=True)
        for key in labels(building, entries, prices):
            old = str(entries[key])
            new = linked(old, building, names)
            if new == old:
                continue
            line = re.compile(rf"^(?P<indent>\s+){re.escape(key)}:\s.*$")
            for index, current in enumerate(lines):
                if (m := line.match(current.rstrip("\n"))):
                    lines[index] = f"{m['indent']}{key}: {_scalar(new)}\n"
                    break
            else:
                raise ValueError(f"{path.name}: {key} is not on one line; link it by hand")
            changed.append(key)
        if write and "".join(lines) != text:
            path.write_text("".join(lines), encoding="utf-8")
    return changed


def main(argv: list[str]) -> int:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    names = building_names(game_root(vanilla_root(ROOT, ROOT / "constructor.toml")), MOD_ROOT)
    changed = apply(ROOT, names, write="--check" not in argv)
    print(f"building links: {len(changed)} slot titles and price labels {'to link' if '--check' in argv else 'linked'}")
    return 1 if changed and "--check" in argv else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
