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


def test_every_town_right_of_the_mod_has_its_own_colour():
    """EU5 logs "Town Rights X has same color as Y" for every pair sharing a colour; the town-rights map mode cannot
    tell them apart. Vanilla rights the mod replaces (switched off) get their own colours too (2026-10-15)."""
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    block = re.compile(r"(?ms)^(?:REPLACE:|INJECT:|TRY_INJECT:|REPLACE_OR_CREATE:)?(\w+) = \{(.*?)^\}")
    colour = re.compile(r"(?m)^\tcolor\s*=\s*([^#\n]*)")
    mod: dict[str, str] = {}
    for path in sorted(TOWN_RIGHTS.glob("*.txt")):
        for m in block.finditer(path.read_text(encoding="utf-8-sig")):
            c = colour.search(m[2])
            if c:
                mod[m[1]] = " ".join(c[1].split())
    vanilla: dict[str, str] = {}
    repo = Path(__file__).resolve().parents[1]
    for path in sorted((vanilla_root(repo, repo / "constructor.toml") / "game/in_game/common/town_rights").glob("*.txt")):
        for m in block.finditer(path.read_text(encoding="utf-8-sig")):
            c = colour.search(m[2])
            if c and m[1] not in mod:
                vanilla[m[1]] = " ".join(c[1].split())
    owners: dict[str, list[str]] = {}
    for name, value in {**vanilla, **mod}.items():
        owners.setdefault(value, []).append(name)
    shared = {value: names for value, names in owners.items() if len(names) > 1 and set(names) & set(mod)}
    assert len(vanilla) > 40 and not shared
