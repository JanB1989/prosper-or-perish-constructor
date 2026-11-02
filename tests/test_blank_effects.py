"""Nothing the player can look at comes out blank in game, whatever emptied it (blank_effects.py)."""

from __future__ import annotations

from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import LoadOrderConfig, load_merged_directory, load_profile
from prosper_or_perish_constructor.blank_effects import (
    ZEUS_OMEN_LINES,
    UNLOCK_COLLECTIONS,
    card_lines,
    dead_modifier_blocks,
    empty_advances,
    is_dead_block,
)

ROOT = Path(__file__).resolve().parents[1]
LOAD_ORDER = ROOT / "constructor.load_order.toml"
MOD_ROOT = ROOT / "mod" / "pp"


def test_no_advance_shows_a_bare_title_in_game() -> None:
    empty = empty_advances(LOAD_ORDER)
    assert not empty, f"{len(empty)} advances have nothing on their card:\n" + "\n".join(empty)


def test_no_modifier_block_comes_to_nothing() -> None:
    dead = dead_modifier_blocks(LOAD_ORDER)
    assert not dead, f"{len(dead)} modifier blocks show nothing in game:\n" + "\n".join(dead)


def test_card_lines_list_what_the_game_lists() -> None:
    values = {"zeroed_food": 0.0, "live_value": 0.05, "a_formula": float("nan")}
    known = {"real_building"}

    def lines(body: str) -> list[str]:
        advance = parse_text(f"x = {{ age = age_1_traditions requires = y icon = z {body} }}").entries[0].value
        return list(card_lines(advance, values, lambda key, target: key not in UNLOCK_COLLECTIONS or target in known))

    assert lines("") == []
    assert lines("potential = { has_or_had_tag = SMO } allow_children = no") == []
    assert lines("global_monthly_food_modifier = zeroed_food") == []     # Tamed Steppes: vanilla's line, valued 0 by the mod
    assert lines("discipline = 0.05 discipline = -0.05") == []           # an inject cancels the vanilla line
    assert lines("discipline = 0") == []
    assert lines("discipline = no_such_value") == []
    assert lines("unlock_building = removed_building") == []
    assert lines("can_colonize = no") == []
    assert lines("modifier_while_progressing = { discipline = 0.05 }") == []
    assert lines("discipline = 0.05") == ["discipline"]
    assert lines("discipline = live_value") == ["discipline"]
    assert lines("discipline = a_formula") == ["discipline"]
    assert lines("fort_limit_modifier = @fort_limit_modifier_increase") == ["fort_limit_modifier"]
    assert lines("global_monthly_food_modifier = zeroed_food discipline = 0.05") == ["discipline"]
    assert lines("unlock_building = real_building") == ["unlock_building"]
    assert lines("unlock_policy = not_a_checked_collection") == ["unlock_policy"]
    assert lines("can_colonize = yes") == ["can_colonize"]
    assert lines("pure_tooltip_entry = some_text_tt") == ["pure_tooltip_entry"]


def test_dead_blocks_are_the_ones_where_all_that_is_written_comes_to_nothing() -> None:
    values = {"zeroed_food": 0.0, "live_value": 0.05, "a_formula": float("nan")}
    types = {"food", "discipline", "can_raid"}

    def dead(body: str) -> bool:
        block = parse_text(f"x = {{ {body} }}").entries[0].value
        assert isinstance(block, CList)
        return is_dead_block(block, values, types)

    assert dead("food = zeroed_food")                                    # Green Thumb, Freyr
    assert dead("scale = { value = 2 add = 1 } food = zeroed_food")      # Zeus's omen: the scale is no line
    assert dead("discipline = 0.05 discipline = -0.05")
    assert dead("food = no_such_value")
    assert dead("can_raid = no")
    assert not dead("")                                                  # empty on purpose: nothing was written
    assert not dead("factor = 0")                                        # a chance block: no modifier type
    assert not dead("food = zeroed_food discipline = 0.05")
    assert not dead("food = live_value")
    assert not dead("food = a_formula")
    assert not dead("food = @a_constant")
    assert not dead("can_raid = yes")


def test_tooltip_lines_of_the_mods_advances_have_text() -> None:
    english = MOD_ROOT / "main_menu" / "localization" / "english"
    text = "\n".join(path.read_text(encoding="utf-8-sig") for path in english.glob("*.yml"))
    advances = load_merged_directory(load_profile("constructor", LOAD_ORDER), "advances", scope="in_game").entries
    missing = sorted(
        f"{entry.key}: {tooltip}"
        for entry in advances
        for tooltip in map(str, entry.value.values("pure_tooltip_entry"))
        if tooltip.startswith("pp_") and f" {tooltip}:" not in text
    )
    assert not missing, "\n".join(missing)


def test_the_hellenism_copy_is_vanillas_file_plus_zeus_omen_lines() -> None:
    """A same-path copy replaces vanilla's file: a game update that changes it fails here, then copy it again."""
    relative = Path("in_game/common/gods/hellenism.txt")
    vanilla = (LoadOrderConfig.load(LOAD_ORDER).vanilla_root / "game" / relative).read_bytes()
    assert (MOD_ROOT / relative).read_bytes().replace(ZEUS_OMEN_LINES, b"") == vanilla
