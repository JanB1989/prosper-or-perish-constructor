"""Every `building_type:<key>` the mod references must be a building that exists without any DLC.

A link to a building that is not in the database logs "Failed to find '<key>' from database for link 'building_type'"
at load, even inside a `has_dlc` limit (the link is resolved when the script is read). EU5 1.4 vanilla's library
`allow` names `library_cordoba`, a building of the unreleased DLC d009_across_the_pillars; the mod's hand-written
REPLACE:library carried that copy over. Buildings that only DLC folders (`game/dlc/...`) define do not count.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"
DEFINITION = re.compile(r"^(?:[A-Z_]+:)?([A-Za-z0-9_]+)\s*=\s*\{", re.M)
REFERENCE = re.compile(r"building_type:([A-Za-z0-9_]+)")


def _text(path: Path) -> str:
    return re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig", errors="replace"))


def test_mod_references_only_buildings_that_exist_without_dlc():
    vanilla = vanilla_root(REPO, REPO / "constructor.toml") / "game/in_game/common/building_types"
    if not vanilla.is_dir() or not (MOD / "in_game/common/building_types").is_dir():
        pytest.skip("vanilla files or built mod not available")
    defined = set()
    for root in (vanilla, MOD / "in_game/common/building_types"):
        for path in root.glob("*.txt"):
            defined.update(DEFINITION.findall(_text(path)))
    unknown = {}
    for path in sorted(MOD.rglob("*.txt")):
        for key in REFERENCE.findall(_text(path)):
            if key not in defined:
                unknown.setdefault(key, str(path.relative_to(MOD)))
    assert unknown == {}
