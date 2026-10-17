"""A building gated on an embraced institution must not get that institution later than vanilla unlocks it (Jan,
2026-10-18: the entrepot unlocks in the Age of Renaissance but needed Printing Press, an Age of Discovery institution,
so a researched building could not be built for a whole age; the trading hub had the same with Global Trade)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
AGE = re.compile(r"age_(\d+)_")


def _top_blocks(text: str) -> dict[str, str]:
    """Top-level ``name = { ... }`` blocks of a script file (comments stripped)."""
    text = re.sub(r"#[^\n]*", "", text)
    out, i = {}, 0
    for m in re.finditer(r"(?m)^([A-Za-z0-9_]+)\s*=\s*\{", text):
        if m.start() < i:
            continue
        depth, j = 0, m.end() - 1
        for j in range(m.end() - 1, len(text)):
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            if depth == 0:
                break
        out[m.group(1)] = text[m.end():j]
        i = j
    return out


def _ages(folder: Path, key: str) -> dict[str, int]:
    """name (or unlocked building for key unlock_building) -> age number."""
    out: dict[str, int] = {}
    for path in sorted(folder.glob("*.txt")):
        for name, body in _top_blocks(path.read_text(encoding="utf-8-sig")).items():
            age = re.search(r"\bage\s*=\s*(age_\d+_\w+)", body)
            if not age:
                continue
            number = int(AGE.match(age.group(1)).group(1))
            names = [name] if key == "" else re.findall(rf"\b{key}\s*=\s*(\w+)", body)
            for n in names:
                out[n] = min(out.get(n, number), number)
    return out


def test_institution_gates_fit_the_unlock_age():
    common = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game/in_game/common"
    institutions = _ages(common / "institution", "")
    unlocks = _ages(common / "advances", "unlock_building")
    gated = 0
    for path in sorted((ROOT / "blueprints/accepted/buildings").glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        body = re.sub(r"#[^\n]*", "", ((data or {}).get("building") or {}).get("body") or "")
        for institution in re.findall(r"has_embraced_institution\s*=\s*institution:(\w+)", body):
            key = data["building"]["key"]
            if key not in unlocks:
                continue
            gated += 1
            assert institutions[institution] <= unlocks[key], (
                f"{key}: unlocked in age {unlocks[key]}, gate {institution} only in age {institutions[institution]}")
    assert gated >= 7    # the trade buildings
