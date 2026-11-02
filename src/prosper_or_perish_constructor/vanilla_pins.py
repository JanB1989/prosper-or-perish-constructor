"""Pin every vanilla block the mod replaces whole to the vanilla text last reviewed.

A (TRY_)REPLACE freezes a copy of the vanilla block, so a later vanilla change never reaches the mod by itself, and
`ppc update-audit` only compares vanilla with vanilla: agricultural_cultivation kept monthly_towards_serfdom after vanilla
moved it to land. `config/vanilla_replace_pins.csv` holds the update-audit hash of each replaced vanilla block;
tests/test_vanilla_replace_pins.py fails when one differs, so a game update lists these blocks until they are ported and
recorded again with `ppc vanilla-pins record`.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CEntry

from prosper_or_perish_constructor.update_audit import COMMON_SCOPES, _definition_hash, _entry_mode, _normalized_entry

PINS_PATH = Path("config") / "vanilla_replace_pins.csv"
REPLACE_MODES = {"REPLACE", "TRY_REPLACE"}
DEFINING_MODES = REPLACE_MODES | {"CREATE", "REPLACE_OR_CREATE"}
INJECT_MODES = {"INJECT", "TRY_INJECT", "INJECT_OR_CREATE"}
MISSING = "missing"

type BlockId = tuple[str, str]


def replaced_blocks(mod_root: Path) -> dict[BlockId, CEntry]:
    """The mod's (TRY_)REPLACE blocks by (folder, key), folder like in_game/common/laws."""
    blocks: dict[BlockId, CEntry] = {}
    for scope in COMMON_SCOPES:
        for path in sorted((mod_root / scope / "common").rglob("*.txt")):
            folder = "/".join(path.relative_to(mod_root).parts[:3])
            for entry in parse_file(path).entries:
                mode, key = _entry_mode(entry.key)
                if mode in REPLACE_MODES:
                    blocks[(folder, key)] = entry
    return blocks


def vanilla_blocks(game_root: Path, folders: Iterable[str]) -> dict[BlockId, list[CEntry]]:
    """Vanilla's blocks in these folders, base game then each DLC: a later definition replaces, an inject adds."""
    dlc_root = game_root / "dlc"
    dlcs = sorted(path for path in dlc_root.iterdir() if path.is_dir()) if dlc_root.is_dir() else []
    blocks: dict[BlockId, list[CEntry]] = {}
    for folder in sorted(set(folders)):
        for root in (game_root, *dlcs):
            for path in sorted((root / folder).rglob("*.txt")):
                try:
                    document = parse_file(path)
                except ValueError:
                    continue
                for entry in document.entries:
                    mode, key = _entry_mode(entry.key)
                    if mode in DEFINING_MODES:
                        blocks[(folder, key)] = [entry]
                    elif mode in INJECT_MODES:
                        blocks.setdefault((folder, key), []).append(entry)
    return blocks


def current_pins(mod_root: Path, game_root: Path) -> dict[BlockId, str]:
    """The hash of today's vanilla block for every block the mod replaces (one hash per definition and inject)."""
    replaced = replaced_blocks(mod_root)
    vanilla = vanilla_blocks(game_root, (folder for folder, _ in replaced))
    return {
        block: "+".join(
            _definition_hash(_normalized_entry(entry, mode=_entry_mode(entry.key)[0])) for entry in vanilla.get(block, ())
        )
        or MISSING
        for block in replaced
    }


def load_pins(path: Path) -> dict[BlockId, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {(row["folder"], row["key"]): row["vanilla_hash"] for row in csv.DictReader(handle)}


def write_pins(path: Path, pins: Mapping[BlockId, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("folder", "key", "vanilla_hash"))
        writer.writerows((*block, pins[block]) for block in sorted(pins))


def pin_problems(current: Mapping[BlockId, str], pinned: Mapping[BlockId, str]) -> list[str]:
    """One line per block whose pin no longer holds."""
    problems: list[str] = []
    for block in sorted(current.keys() | pinned.keys()):
        folder, key = block
        now, then = current.get(block), pinned.get(block)
        if then is None:
            problems.append(f"{folder}/{key}: newly replaced, not pinned yet")
        elif now is None:
            problems.append(f"{folder}/{key}: no longer replaced by the mod")
        elif now != then:
            problems.append(f"{folder}/{key}: vanilla block changed ({then} -> {now}), port it into the mod's copy")
    return problems
