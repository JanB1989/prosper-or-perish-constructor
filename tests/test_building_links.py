"""Every building a player-facing text names is a link (Jan, 2026-10-24): hovering the name shows the building.

A building in localization is ``[ShowBuildingTypeName('<key>')|e]``, never ``$<key>$`` (plain name), never
``[ShowBuildingTypeName('<key>')]`` without ``|e`` and never ``ShowBuildingTypeNameWithNoTooltip``. Concepts are linked
the same way (``[location|e]``); the generators that name buildings or attributes are tested where they are written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import cap_tooltips

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
_DEFINITION = re.compile(r"^(?:[A-Z_]+:)?(\w+)\s*=\s*\{", re.MULTILINE)
_ENTRY = re.compile(r'^\s*([\w.]+):\d*\s*"(.*)"\s*$')
_REFERENCE = re.compile(r"\$(\w+)(?:\|[^$]*)?\$")
_UNLINKED = re.compile(r"ShowBuildingTypeNameWithNoTooltip\(|ShowBuildingTypeName\('\w+'\)\]")


@pytest.fixture(scope="module")
def buildings() -> set[str]:
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    vanilla = cap_tooltips.game_root(vanilla_root(ROOT, ROOT / "constructor.toml"))
    if not (vanilla / "in_game/common/building_types").is_dir():
        pytest.skip("no vanilla game files")
    keys: set[str] = set()
    for root in (vanilla, MOD_ROOT):
        for path in (root / "in_game/common/building_types").glob("*.txt"):
            keys.update(_DEFINITION.findall(path.read_text(encoding="utf-8-sig")))
    return keys


def unlinked(text: str, buildings: set[str]) -> list[str]:
    """The building mentions in one localization string that are not links."""
    return [f"${ref}$" for ref in _REFERENCE.findall(text) if ref in buildings] + _UNLINKED.findall(text)


def test_the_check_finds_every_unlinked_form() -> None:
    known = {"tavern", "granary"}
    assert unlinked("The $tavern$ feeds the town", known) == ["$tavern$"]
    assert unlinked("$tavern|Y$ and [ShowBuildingTypeName('granary')]", known) == ["$tavern$", "ShowBuildingTypeName('granary')]"]
    assert unlinked("[ShowBuildingTypeNameWithNoTooltip('granary')] Max Level", known) == ["ShowBuildingTypeNameWithNoTooltip("]
    assert unlinked("[ShowBuildingTypeName('granary')|e] in this [location|e], $other_key$", known) == []


def test_every_building_named_in_the_mod_text_is_a_link(buildings: set[str]) -> None:
    offenders = []
    for path in sorted(MOD_ROOT.rglob("*.yml")):
        if "english" not in path.parts:
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            entry = _ENTRY.match(line)
            if entry and (found := unlinked(entry[2], buildings)):
                offenders.append(f"{path.name}: {entry[1]}: {', '.join(found)}")
    assert offenders == [], f"{len(offenders)} texts name a building without linking it:\n" + "\n".join(offenders[:30])
