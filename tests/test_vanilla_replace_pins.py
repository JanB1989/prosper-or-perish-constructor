from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList, Value
from eu5gameparser.load_order import LoadOrderConfig
from prosper_or_perish_constructor.vanilla_pins import (
    PINS_PATH,
    current_pins,
    load_pins,
    pin_problems,
    replaced_blocks,
    vanilla_blocks,
    write_pins,
)


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "pp"
LOAD_ORDER = ROOT / "constructor.load_order.toml"
PRIVILEGES = "in_game/common/estate_privileges"
# The only replaced blocks allowed a different societal value move from vanilla; each is a decision, not a stale copy.
DELIBERATE_SOCIETAL_VALUE_MOVES = {
    (PRIVILEGES, "building_roads_rights"),  # the burghers no longer drag coastal countries towards land
    (PRIVILEGES, "noble_sponsored_navy"),  # the naval push raised from minor to a full monthly move
    ("in_game/common/laws", "maritime_law"),  # impressment and trade-route protection also push towards naval
}


@cache
def _game_root() -> Path:
    return LoadOrderConfig.load(LOAD_ORDER).vanilla_root / "game"


def _societal_value_moves(value: Value) -> Counter[tuple[str, str]]:
    moves: Counter[tuple[str, str]] = Counter()
    if isinstance(value, CList):
        for entry in value.entries:
            if entry.key.startswith("monthly_towards_"):
                moves[(entry.key, str(entry.value))] += 1
            moves += _societal_value_moves(entry.value)
        for item in value.items:
            moves += _societal_value_moves(item)
    return moves


def test_replaced_vanilla_blocks_match_the_reviewed_text() -> None:
    problems = pin_problems(current_pins(MOD_ROOT, _game_root()), load_pins(ROOT / PINS_PATH))
    assert not problems, "\n".join(
        ["Port each changed block into the mod's copy, then run `ppc vanilla-pins record`:", *problems]
    )


def test_replaces_keep_vanilla_societal_value_moves() -> None:
    # The pins only see vanilla changes from the day they were recorded; this compares the mod's copies with vanilla
    # today, so a move that went stale before then shows too (agricultural_cultivation: serfdom where vanilla has land).
    replaced = replaced_blocks(MOD_ROOT)
    vanilla = vanilla_blocks(_game_root(), (folder for folder, _ in replaced))
    differing = {
        block
        for block, entry in replaced.items()
        if _societal_value_moves(entry.value)
        != sum((_societal_value_moves(part.value) for part in vanilla.get(block, ())), Counter())
    }
    assert differing == DELIBERATE_SOCIETAL_VALUE_MOVES


def test_a_vanilla_change_to_a_replaced_block_fails_its_pin(tmp_path: Path) -> None:
    mod_file = tmp_path / "mod" / "in_game" / "common" / "government_reforms" / "pp_reforms.txt"
    game_file = tmp_path / "game" / "in_game" / "common" / "government_reforms" / "common.txt"
    pins_file = tmp_path / "pins.csv"
    mod_file.parent.mkdir(parents=True)
    game_file.parent.mkdir(parents=True)
    mod_file.write_text(
        "REPLACE:reform_a = { years = 2 }\nTRY_REPLACE:reform_b = { years = 3 }\nreform_c = { years = 4 }\n",
        encoding="utf-8",
    )
    game_file.write_text(
        "reform_a = { x = serfdom }\nreform_b = { years = 3 }\nreform_c = { years = 4 }\n",
        encoding="utf-8",
    )
    mod_root, game_root = tmp_path / "mod", tmp_path / "game"

    write_pins(pins_file, current_pins(mod_root, game_root))
    assert not pin_problems(current_pins(mod_root, game_root), load_pins(pins_file))

    # Comments and spacing are not a change; a value is, and the plain mod block reform_c is not pinned at all.
    game_file.write_text(
        "# note\nreform_a = {\n\tx = serfdom\n}\nreform_b = { years = 3 }\nreform_c = { years = 5 }\n",
        encoding="utf-8",
    )
    assert not pin_problems(current_pins(mod_root, game_root), load_pins(pins_file))
    game_file.write_text("reform_a = { x = land }\nreform_b = { years = 3 }\n", encoding="utf-8")
    problems = pin_problems(current_pins(mod_root, game_root), load_pins(pins_file))
    assert len(problems) == 1 and "government_reforms/reform_a: vanilla block changed" in problems[0]
