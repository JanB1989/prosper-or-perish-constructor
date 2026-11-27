"""Institution spread on estate literacy (2026-11-27, Jan).

Every spread channel reads the receiving location's literacy. The mod replaces vanilla's values so they read the upper
classes' literacy (hidden location modifiers written by the pop types) times a rank factor, and the after-embrace
channel of every institution reads a script value instead of vanilla's flat 2. The institution files are same-path
copies of vanilla with only that line changed; a game update that changes them fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "mod" / "pp" / "in_game" / "common"
SPREAD = COMMON / "script_values" / "pp_institution_spread.txt"
OLD = "spread_scale_on_control_if_owner_embraced = 2"
NEW = "spread_scale_on_control_if_owner_embraced = pp_institution_control_spread # PP (vanilla 2)"


@pytest.fixture(scope="module")
def vanilla() -> Path:
    return LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game" / "in_game" / "common"


def _blocks(path: Path) -> dict[str, CList]:
    return {e.key: e.value for e in parse_file(path).entries if isinstance(e.value, CList)}


def _text(path: Path, key: str) -> str:
    """The block ``key = { ... }`` of a script file as one line: comments stripped, whitespace collapsed."""
    import re

    raw = re.sub(r"#.*", "", path.read_text(encoding="utf-8-sig"))
    start = re.search(rf"(?m)^{re.escape(key)} = \{{", raw)
    assert start, key
    depth, i = 0, start.end() - 1
    while True:
        depth += {"{": 1, "}": -1}.get(raw[i], 0)
        i += 1
        if depth == 0:
            break
    return " ".join(raw[start.end() - 1:i].split())


def test_every_vanilla_channel_value_is_replaced(vanilla) -> None:
    original = _blocks(vanilla / "script_values" / "institution_spread.txt")
    mine = _blocks(SPREAD)
    source = vanilla / "script_values" / "institution_spread.txt"
    for key in original:
        block = _text(source, key)
        if "average_location_literacy" not in block:
            assert f"REPLACE:{key}" not in mine, key   # the flat market-centre value stays vanilla
            continue
        copy = _text(SPREAD, f"REPLACE:{key}")
        assert "average_location_literacy" not in copy, key
        reads = "pp_institution_reading" if key.startswith("institution_trade_spread_value") else "pp_institution_literacy"
        # vanilla's value with only the literacy read exchanged: the coefficients are vanilla's
        assert copy == block.replace("average_location_literacy", reads), key


def test_reading_and_rank_factor() -> None:
    reading = _text(SPREAD, "pp_institution_reading")
    # all people as the base and the fallback; the estates only where their numbers read something
    assert reading.startswith("{ value = average_location_literacy if = { limit = { pp_upper_class_literate > 0 }")
    assert "multiply = 0.2" in reading and "divide = pp_upper_class_share" in reading and "multiply = 80" in reading
    for estate in ("nobles", "clergy", "burghers"):
        assert f"modifier:local_pp_{estate}_share" in _text(SPREAD, "pp_upper_class_share")
        assert f"modifier:local_pp_{estate}_literacy" in _text(SPREAD, "pp_upper_class_literate")
    factors = [float(x) for x in re.findall(r"value = ([0-9.]+)", _text(SPREAD, "pp_institution_rank_factor"))]
    assert factors == [0.1, 0.6, 1.5]   # rural settlement < town < city and megalopolis
    control = _text(SPREAD, "pp_institution_control_spread")
    assert control == "{ value = pp_institution_reading multiply = 0.006 max = 0.3 }"
    types = (ROOT / "mod/pp/main_menu/common/modifier_type_definitions/pp_school_modifier_types.txt").read_text(
        encoding="utf-8-sig")
    for estate in ("nobles", "clergy", "burghers"):
        for kind in ("literacy", "share"):
            assert f"local_pp_{estate}_{kind} = {{" in types


def test_institution_files_are_vanilla_with_one_line_changed(vanilla) -> None:
    sources = sorted(p for p in (vanilla / "institution").glob("*.txt") if p.name != "readme.txt")
    copies = sorted((COMMON / "institution").glob("*.txt"))
    assert [p.name for p in copies] == [p.name for p in sources]
    changed = 0
    for source in sources:
        original = source.read_text(encoding="utf-8-sig")
        changed += original.count(OLD)
        assert (COMMON / "institution" / source.name).read_text(encoding="utf-8-sig") == original.replace(OLD, NEW)
        assert "spread_scale_on_control_if_owner_embraced" not in original.replace(OLD, "")
    assert changed >= 12
