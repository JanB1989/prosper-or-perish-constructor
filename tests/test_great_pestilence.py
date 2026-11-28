"""The Great Pestilence spreads better and kills more (2026-11-27, Jan: "make it more deadly, make it spread easier ...
we want it to be harder").

The mod's copy (diseases/pp_great_pestilence.txt, TRY_REPLACE) keeps every vanilla line except the rough-terrain
numbers (no road and mountains, desert or jungle: R0 x0.25 -> x0.5, spread threshold 0.85 -> 0.60, stagnation x3 ->
x2), the mortality {0.75 0.9} -> {0.85 0.92} (milder since 2026-11-28, Jan; x0.75, x1.5 and {0.9 0.95} the day before
took the Americas to 12 M, run bd7d9616) and the mod's migration line, which an inject would miss in a replaced
block. No resistance leak, as in vanilla: the game reads that value without a location, so it cannot be limited to the
Americas (the first version tried and wrote a script error on every read). Each vanilla number is pinned here too, so a
game update that moves one fails and asks for a review (AGENTS.md "Great Pestilence").
"""

from __future__ import annotations

import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.serializer import render_value
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "pp" / "in_game/common/diseases"
GAME = LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"
VANILLA = GAME / "in_game/common/diseases/great_pestilence.txt"

ROUGH_R0 = "r0[0]/if[3]/multiply[0]"
ROUGH_THRESHOLD = "location_spread_threshold[0]/if[0]/value[0]"
FLAT_THRESHOLD = "location_spread_threshold[0]/else[0]/value[0]"
ROUGH_STAGNATION = "location_stagnation_chance[0]/if[1]/multiply[0]"
# leaf: (vanilla, mod)
CHANGED = {
    ROUGH_R0: ("= 0.25", "= 0.5"),
    ROUGH_THRESHOLD: ("= 0.85", "= 0.60"),
    ROUGH_STAGNATION: ("= 3", "= 2"),
    "mortality_rate[0]/item[0]": ("0.75", "0.85"),
    "mortality_rate[0]/item[1]": ("0.9", "0.92"),
}
ADDED = {
    "location_modifier[0]/local_migration_attraction[0]": "= -1.5",
}


def _block(path: Path, key: str) -> CList:
    blocks = [e.value for e in parse_file(path).entries if e.key == key]
    assert len(blocks) == 1, (path, key, len(blocks))
    return blocks[0]


def _leaves(node: CList, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    seen: dict[str, int] = {}
    for entry in node.entries:
        index = seen.get(entry.key, 0)
        seen[entry.key] = index + 1
        path = f"{prefix}{entry.key}[{index}]"
        if isinstance(entry.value, CList):
            out.update(_leaves(entry.value, path + "/"))
            for k, item in enumerate(entry.value.items):
                out[f"{path}/item[{k}]"] = render_value(item)
        else:
            out[path] = f"{entry.op} {render_value(entry.value)}"
    return out


def _is_rough_terrain_limit(block: CList) -> bool:
    text = render_value(block.first("limit"))
    return all(token in text for token in ("num_roads", "mountains", "desert", "jungle"))


def test_changed_numbers_against_vanilla() -> None:
    own = _leaves(_block(MOD / "pp_great_pestilence.txt", "TRY_REPLACE:great_pestilence"))
    old = _leaves(_block(VANILLA, "great_pestilence"))
    assert set(own) == set(old) | set(ADDED), set(own) ^ (set(old) | set(ADDED))
    for leaf, (vanilla, mod) in CHANGED.items():
        assert old[leaf] == vanilla, (leaf, old[leaf])
        assert float(own[leaf].split()[-1]) == float(mod.split()[-1]), (leaf, own[leaf])
    for leaf, value in ADDED.items():
        assert own[leaf] == value, (leaf, own[leaf])
    for leaf, value in old.items():
        if leaf not in CHANGED:
            assert own[leaf] == value, (leaf, own[leaf], value)
    # the flat-terrain threshold is the rough one now
    assert float(own[ROUGH_THRESHOLD].split()[-1]) == float(own[FLAT_THRESHOLD].split()[-1])


def test_the_changed_ifs_are_the_rough_terrain_ones() -> None:
    old = _block(VANILLA, "great_pestilence")
    assert _is_rough_terrain_limit(old.first("r0").values("if")[3])
    assert _is_rough_terrain_limit(old.first("location_spread_threshold").values("if")[0])
    assert _is_rough_terrain_limit(old.first("location_stagnation_chance").values("if")[1])
    assert not old.values("monthly_resistance_reduction")  # vanilla: no leak


def test_old_world_stays_shielded() -> None:
    """Outside the Americas vanilla multiplies R0 by 0 and stagnates at once; nothing leaks, so the Old World's setup
    resistance (1.0, setup 19_diseases.txt) stays."""
    own = _block(MOD / "pp_great_pestilence.txt", "TRY_REPLACE:great_pestilence")
    assert not own.values("monthly_resistance_reduction")  # read without a location: it cannot be America-only
    r0_last = own.first("r0").values("if")[4]
    assert "continent:america" in render_value(r0_last.first("limit")) and float(r0_last.first("multiply")) == 0
    stag_last = own.first("location_stagnation_chance").values("if")[-1]
    assert "continent:america" in render_value(stag_last.first("limit")) and float(stag_last.first("value")) == 1
    setup = (GAME / "main_menu/setup/1337/19_diseases.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"add_disease_resistance\s*=\s*\{\s*type\s*=\s*great_pestilence\s+resistance\s*=\s*1\.0\b", setup)


def test_no_inject_into_the_replaced_block() -> None:
    for path in sorted(MOD.glob("*.txt")):
        for entry in parse_file(path).entries:
            assert entry.key != "TRY_INJECT:great_pestilence" and entry.key != "INJECT:great_pestilence", path.name
