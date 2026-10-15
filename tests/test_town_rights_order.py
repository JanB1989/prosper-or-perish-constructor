"""A town right's `upgrades_to` must name a right that is already loaded.

The engine reads `upgrades_to` as a key reference while it loads the database, so a right defined later (in the same
file or a later file) fails with "Failed to read key reference" in error.log and the charter never upgrades (EU5 1.4.1,
2026-10-15: all 17 specialization charters pointed forward to their rights).
"""

from __future__ import annotations

import re
from pathlib import Path

TOWN_RIGHTS = (
    Path(__file__).resolve().parents[1]
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "town_rights"
)

_TOP_KEY = re.compile(r"^(?:REPLACE:|INJECT:|TRY_INJECT:|REPLACE_OR_CREATE:)?([A-Za-z_]\w*)\s*=\s*\{", re.MULTILINE)
_UPGRADES_TO = re.compile(r"^\s*upgrades_to\s*=\s*(\w+)", re.MULTILINE)


def test_upgrades_to_names_a_right_loaded_before():
    loaded: set[str] = set()
    forward: list[str] = []
    for path in sorted(TOWN_RIGHTS.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        keys = [(m.start(), m.group(1)) for m in _TOP_KEY.finditer(text)]
        for (start, key), nxt in zip(keys, [*keys[1:], (len(text), None)]):
            for target in _UPGRADES_TO.findall(text[start : nxt[0]]):
                # vanilla rights load from the game's own files; only PP's own targets can point forward
                if target.startswith("pp_") and target not in loaded:
                    forward.append(f"{path.name}: {key} -> {target}")
            loaded.add(key)
    assert not forward, forward


def test_every_specialization_charter_upgrades_to_its_rights():
    text = (TOWN_RIGHTS / "pp_specialization_town_rights.txt").read_text(encoding="utf-8-sig")
    charters = re.findall(r"^(pp_\w+)_charter = \{", text, re.MULTILINE)
    assert len(charters) == 17
    for good in charters:
        assert re.search(rf"^{good}_charter = \{{\s*is_specialization = yes\s*upgrades_to = {good}_rights\b", text, re.MULTILINE)
