"""A building that an advance unlocks never needs an institution on top (Jan, 2026-10-19: "if a building is researched,
it shouldn't need some other unrelated institution"). History: the 2026-10-06 trade-building gates (Printing Press /
Global Trade on merchants' quarters, trading hub, customs house, grand marketplace, stock exchange, commerce centre,
clearing house, entrepot) left researched buildings unbuildable for up to an age; removed 2026-10-18/19.

Checks every building type the game loads (vanilla in_game/common plus the built mod; a mod file of the same name
shadows vanilla's) against every advance's unlock_building, including scripted triggers used in the build rules."""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game/common"
GATES = ("allow", "location_potential", "country_potential")
INSTITUTION = re.compile(r"has_embraced_institution|institution:\w+")


def _blocks(text: str) -> dict[str, str]:
    """The ``name = { ... }`` blocks at the outermost brace depth of ``text`` (comments stripped; the mod's built
    files write fields at column 0, so depth, not indentation); REPLACE:/INJECT: prefixes dropped, repeats joined."""
    text = re.sub(r"#[^\n]*", "", text)
    out: dict[str, str] = {}
    opener = re.compile(r"((?:[A-Z_]+:)?[A-Za-z0-9_]+)\s*=\s*\{")
    i, depth = 0, 0
    while i < len(text):
        if depth == 0:
            m = opener.match(text, i)
            if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "_:")):
                level, j = 0, m.end() - 1
                for j in range(m.end() - 1, len(text)):
                    level += {"{": 1, "}": -1}.get(text[j], 0)
                    if level == 0:
                        break
                name = m.group(1).split(":")[-1]
                out[name] = out.get(name, "") + "\n" + text[m.end():j]
                i = j + 1
                continue
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return out


def _files(folder: str) -> dict[str, str]:
    vanilla = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game/in_game/common"
    files = {p.name: p for p in sorted((vanilla / folder).glob("*.txt"))}
    files.update({p.name: p for p in sorted((MOD / folder).glob("*.txt"))})
    return {name: path.read_text(encoding="utf-8-sig", errors="replace") for name, path in files.items()}


def test_researched_buildings_need_no_institution():
    unlocked = {b for text in _files("advances").values() for body in _blocks(text).values()
                for b in re.findall(r"\bunlock_building\s*=\s*(\w+)", body)}
    triggers = {name: body for text in _files("scripted_triggers").values() for name, body in _blocks(text).items()}
    gated = set()
    for text in _files("building_types").values():
        for building, body in _blocks(text).items():
            if building not in unlocked:
                continue
            for field, gate in _blocks(body).items():
                if field not in GATES:
                    continue
                called = [triggers[t] for t in re.findall(r"\b(\w+)\s*=\s*yes", gate) if t in triggers]
                if INSTITUTION.search(gate) or any(INSTITUTION.search(c) for c in called):
                    gated.add(f"{building}.{field}")
    assert not gated, f"researched buildings gated on an institution: {sorted(gated)}"
    assert len(unlocked) > 150   # the scan sees vanilla's and the mod's unlocks
