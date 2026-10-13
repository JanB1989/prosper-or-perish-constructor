"""Buildings the mod replaces keep vanilla's graphical_tags (EU5 1.4.1 factory_small/medium/large, palace)."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BUILDING_TYPES = Path("in_game/common/building_types")
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"

_BLOCK = re.compile(r"^((?:TRY_)?(?:REPLACE|INJECT)(?:_OR_CREATE)?:)?([A-Za-z0-9_]+)\s*=\s*\{", re.M)
_TAGS = re.compile(r"graphical_tags\s*=\s*\{([^}]*)\}")


def _blocks(text: str):
    for match in _BLOCK.finditer(text):
        depth, i = 0, match.end() - 1
        while i < len(text):
            char = text[i]
            if char == "#":
                i = text.find("\n", i)
                if i < 0:
                    break
                continue
            depth += char == "{"
            depth -= char == "}"
            if depth == 0:
                break
            i += 1
        yield match.group(1) or "", match.group(2), text[match.start() : i + 1]


@cache
def _vanilla_tags() -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for path in sorted((vanilla_root(ROOT, PROJECT) / "game" / BUILDING_TYPES).glob("*.txt")):
        for prefix, name, body in _blocks(path.read_text(encoding="utf-8-sig")):
            match = _TAGS.search(body)
            if not prefix and match:
                tags[name] = match.group(1).split()
    return tags


def test_replaced_vanilla_buildings_keep_vanilla_graphical_tags() -> None:
    vanilla = _vanilla_tags()
    assert vanilla, "no vanilla graphical_tags found"
    wrong = []
    for path in sorted((MOD_ROOT / BUILDING_TYPES).glob("*.txt")):
        for prefix, name, body in _blocks(path.read_text(encoding="utf-8-sig")):
            if "REPLACE" not in prefix or name not in vanilla:
                continue
            match = _TAGS.search(body)
            have = match.group(1).split() if match else []
            if have != vanilla[name]:
                wrong.append(f"{path.name}: {name} has {have}, vanilla {vanilla[name]}")
    assert not wrong, "\n".join(wrong)
