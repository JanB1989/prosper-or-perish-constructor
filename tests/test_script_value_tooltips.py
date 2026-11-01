"""Script values that show a breakdown (any desc) must describe every top-level operation.

The game lists each top-level operation of such a value in its tooltip; one without a desc shows as a "missing key"
line (2026-10-01, the Tavern's Maximum Level tooltip: bare min / max / floor). Caps use described clamps
(`min = { desc = ... value = 0 }`) and no `floor = yes`: the engine floors max_levels to whole levels itself.
"""
from __future__ import annotations

from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
OPS = {"add", "subtract", "multiply", "divide", "modulo", "min", "max", "floor", "ceiling", "round", "value"}
# same-name copies of vanilla files keep vanilla's own values unchanged
VANILLA_COPIES = {"default_values.txt"}


def _has_desc(value: object) -> bool:
    return isinstance(value, CList) and any(e.key == "desc" or _has_desc(e.value) for e in value.entries)


def _bare_ops(block: CList, named: set[str], path: str = "") -> list[str]:
    out: list[str] = []
    for entry in block.entries:
        if entry.key in ("if", "else_if", "else") and isinstance(entry.value, CList):
            out.extend(_bare_ops(entry.value, named, f"{path}{entry.key}>"))
        elif entry.key in ("add", "value") and not isinstance(entry.value, CList) and str(entry.value) in named:
            continue   # an unlabelled script value flattens: its own rows show here (cap_tooltips.py, seen in game 2026-10-24)
        elif entry.key in OPS and not (
            isinstance(entry.value, CList) and any(e.key == "desc" for e in entry.value.entries)
        ):
            out.append(path + entry.key)
    return out


def test_described_script_values_have_no_missing_key_lines() -> None:
    offenders: list[str] = []
    files = [p for p in sorted(MOD_ROOT.rglob("script_values/*.txt")) if p.name not in VANILLA_COPIES]
    parsed = {path: parse_text(path.read_text(encoding="utf-8-sig")).entries for path in files}
    named = {str(entry.key).split(":")[-1] for entries in parsed.values() for entry in entries}
    for path, entries in parsed.items():
        for entry in entries:
            if isinstance(entry.value, CList) and _has_desc(entry.value):
                bare = _bare_ops(entry.value, named)
                if bare:
                    offenders.append(f"{path.name}: {entry.key} {bare}")
    assert not offenders, "\n".join(offenders[:20])
