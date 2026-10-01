"""The mod's GUI only overrides blocks the game's widget types have, and only calls data functions the game knows.

EU5 1.4 renamed the content block of `TooltipScrolledContentSection` (`scrollarea_content` -> `section_content`); the
game dropped the old override without a log line and the location view's land and harvest chips showed empty effect
lists. These tests read the current game files, so they fail after the next such change instead of in game.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache
from pathlib import Path

from eu5gameparser.load_order import LoadOrderConfig

from prosper_or_perish_constructor import gui_blocks, location_status, stored_food

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
PROJECT = ROOT / "constructor.toml"
WINDOW = MOD_ROOT / "in_game/gui/location_window.gui"
ATTRIBUTE_TOOLTIPS = MOD_ROOT / "in_game/gui/shared/pp_attribute_tooltips.gui"
STATUS_LOC = MOD_ROOT / "main_menu/localization/english/pp_location_status_l_english.yml"
# Empty overrides of a block 1.4's button_regular no longer has: no-ops on the Prosper or Perish Europedia page's
# filter buttons (hand-kept window, tools/port_vanilla_gui.py), harmless.
KNOWN_NO_OPS = {("encyclopedia_lateralview.gui", "button_regular", "background")}


@cache
def _vanilla() -> Path:
    return LoadOrderConfig.load(ROOT / "constructor.load_order.toml").vanilla_root / "game"


@cache
def _index() -> gui_blocks.TypeIndex:
    return gui_blocks.type_index(gui_blocks.game_gui_roots(_vanilla(), MOD_ROOT))


@cache
def _vanilla_dead() -> frozenset[tuple[str, str]]:
    """Overrides vanilla itself leaves dead (or that this reader cannot resolve): not the mod's doing."""
    dead: Counter[tuple[str, str]] = Counter()
    for root in gui_blocks.game_gui_roots(_vanilla()):
        for path in root.rglob("*.gui"):
            dead += gui_blocks.dead_overrides(path.read_text(encoding="utf-8-sig", errors="replace"), _index())
    return frozenset(dead)


def _status_row() -> str:
    text = WINDOW.read_text(encoding="utf-8-sig")
    start = text.index("# PP STATUS CHIPS")
    return text[start:text.index("# BOTTOM CONDITIONS", start)]


_SCROLL_13 = """types T {
    type TooltipScrolledContentSection = scrollarea {
        block "block_scrollarea" { maximumsize = { -1 600 } }
        scrollwidget = { block "scrollarea_content" { TooltipContentSection = {} } }
    }
    type TooltipContentSection = vbox { block "section_content" {} }
}"""
_SCROLL_14 = """types T {
    type TooltipScrolledContentSection = scrollvbox {
        block "block_scrollarea" { maximumsize = { -1 600 } }
        using = scroll_setup
        block "section_content" {}
    }
    type TooltipContentSection = vbox { block "section_content" {} }
    type Derived = TooltipContentSection { }
}
template scroll_setup { block "scrollbar_setup" {} }"""
_USE_13 = (
    'widget = { TooltipScrolledContentSection = { blockoverride "block_scrollarea" { maximumsize = { -1 420 } } '
    'blockoverride "scrollarea_content" { TooltipContentSection = { blockoverride "section_content" { text = "x" } } } } }'
)


def test_a_renamed_block_is_reported_where_the_old_one_was_overridden():
    old, new = gui_blocks.TypeIndex(), gui_blocks.TypeIndex()
    old.add(_SCROLL_13)
    new.add(_SCROLL_14)
    assert not gui_blocks.dead_overrides(_USE_13, old)
    assert gui_blocks.dead_overrides(_USE_13, new) == Counter({("TooltipScrolledContentSection", "scrollarea_content"): 1})
    # blocks come from the type, its templates and its base type; an override may sit inside plain child widgets
    assert {"block_scrollarea", "section_content", "scrollbar_setup"} <= new.blocks("TooltipScrolledContentSection")
    assert new.blocks("Derived") == {"section_content"} and new.blocks("vbox") is None
    nested = 'TooltipScrolledContentSection = { widget = { blockoverride "scrollbar_setup" {} } }'
    assert not gui_blocks.dead_overrides(nested, new)
    # the chip generator's scroll section fits the 1.4 shape
    assert not gui_blocks.dead_overrides(location_status._scrolled('text = "x"'), new)


def test_status_chips_override_only_blocks_the_game_types_have():
    row = _status_row()
    assert "scrollarea_content" not in row and row.count('blockoverride "section_content"') == 4
    assert not gui_blocks.dead_overrides(row, _index())
    # the generator itself, with the real land-pressure rows, agrees with the deployed window
    land = location_status.load_land_effect_rows(MOD_ROOT, _vanilla().parent)
    assert land is not None
    stored = location_status.load_stored_food_rows(MOD_ROOT, _vanilla().parent, stored_food.load_config(PROJECT).per_year)
    generated = location_status.status_row(location_status.load_harvests(MOD_ROOT), land, stored)
    assert not gui_blocks.dead_overrides(generated, _index())


def test_mod_gui_files_add_no_dead_overrides_beyond_vanilla():
    vanilla_dead = _vanilla_dead()
    found = []
    for root in gui_blocks.game_gui_roots(MOD_ROOT):
        for path in sorted(root.rglob("*.gui")):
            dead = gui_blocks.dead_overrides(path.read_text(encoding="utf-8-sig", errors="replace"), _index())
            found += [(path.name, t, b, n) for (t, b), n in dead.items()
                      if (t, b) not in vanilla_dead and (path.name, t, b) not in KNOWN_NO_OPS]
    assert not found


def _calls(text: str) -> set[str]:
    """Data-function and property names in the `[...]` expressions of a GUI or localization text."""
    names: set[str] = set()
    for expr in re.findall(r"\[([^\[\]\n]*)\]", text):
        expr = re.sub(r"'[^']*'", "''", expr.split("|")[0])
        names |= set(re.findall(r"([A-Za-z_]\w*)\s*\(", expr)) | set(re.findall(r"\.([A-Za-z_]\w*)", expr))
        names |= set(re.findall(r"^\s*([A-Za-z_]\w*)\s*\.", expr))
    return names


def test_chip_data_functions_exist_in_the_game():
    """Every function the status chips, their texts and the attribute tooltips call is one vanilla's GUI or
    localization calls too (the game has no list of its own; a 1.3 name gone in 1.4 would fail here)."""
    used = _calls(_status_row()) | _calls(STATUS_LOC.read_text(encoding="utf-8-sig"))
    used |= _calls(ATTRIBUTE_TOOLTIPS.read_text(encoding="utf-8-sig"))
    assert {"ShowModifierEffect", "GetModifierValueFixed", "Custom", "ScriptValue", "ShowModifierTypeName"} <= used
    vanilla = set()
    for path in [*_vanilla().glob("*/gui/**/*.gui"), *_vanilla().glob("main_menu/localization/english/**/*.yml")]:
        vanilla |= _calls(path.read_text(encoding="utf-8-sig", errors="replace"))
    assert not sorted(used - vanilla)


def test_chip_gates_match_texts_their_customizable_localization_can_return():
    """Each GUI gate compares a customizable localization with a key that localization returns; the harvest
    keys name static modifiers the mod defines, and the harvest regions exist on the map the game loads."""
    row = _status_row()
    custom = ""
    custom += (MOD_ROOT / "in_game/common/customizable_localization/pp_location_status.txt").read_text(encoding="utf-8-sig")
    returns: dict[str, set[str]] = {}
    for block, body in re.findall(r"(?m)^(\w+) = \{(.*?)^\}", custom, flags=re.DOTALL):
        returns[block] = set(re.findall(r"localization_key = (\w+)", body))
    gates = re.findall(r"Custom\('(\w+)'\), Localize\('(\w+)'\)", row)
    assert gates
    attr = ATTRIBUTE_TOOLTIPS.read_text(encoding="utf-8-sig")
    gates += re.findall(r"Custom\('(pp_harvest_\w+)'\), Localize\('(\w+)'\)", attr)
    unmatched = sorted({(c, k) for c, k in gates if k not in returns.get(c, set())})
    assert not unmatched
    # every gated harvest has a static modifier; at least one harvest view exists per severity and region
    harvest = (MOD_ROOT / location_status.HARVEST_MODIFIERS).read_text(encoding="utf-8-sig")
    keys = set(location_status.harvest_modifiers(harvest))
    named = {k.removeprefix("STATIC_MODIFIER_NAME_") for k in returns["pp_harvest_state"] if k.startswith("STATIC_MODIFIER_NAME_")}
    assert named == keys and len(keys) > 50
    assert {k.removeprefix("STATIC_MODIFIER_NAME_") for _, k in gates if k.startswith("STATIC_MODIFIER_NAME_pp_harvest_")} <= keys
    definitions = MOD_ROOT / "in_game/map_data/definitions.txt"
    if not definitions.is_file():
        definitions = _vanilla() / "in_game/map_data/definitions.txt"
    regions = set(re.findall(r"(?m)^\s*(\w+_region)\s*=\s*\{", definitions.read_text(encoding="utf-8-sig")))
    missing = sorted(set(re.findall(r"region:(\w+)", custom)) - regions)
    assert regions and not missing
