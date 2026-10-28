"""Every modifier type the mod defines has an icon entry; without one the engine logs "Missing Icon for Modifier"."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "main_menu" / "common"
TOP_LEVEL = re.compile(r"^([A-Za-z_][\w.]*)\s*=\s*\{", re.M)
COMMENT = re.compile(r"#[^\n]*")


def _names(folder: str) -> set[str]:
    names = set()
    for path in (COMMON / folder).glob("*.txt"):
        names.update(TOP_LEVEL.findall(COMMENT.sub("", path.read_text(encoding="utf-8-sig"))))
    return names


def test_every_modifier_type_has_an_icon():
    types = _names("modifier_type_definitions")
    assert types
    assert sorted(types - _names("modifier_icons")) == []
