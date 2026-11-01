"""The welcome situation panel (in_game/gui/panels/situation/pp_mod_welcome_situation.gui).

The game opens gui/panels/situation/<situation key>.gui when the player clicks a situation. The welcome is an
introduction, one button that opens the Prosper or Perish section of the Europedia and one that dismisses the welcome
(one for players, one for observers); the situation never ends by itself. Hand-kept GUI the game checks only when it draws it, so these tests read the files the game loads.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from prosper_or_perish_constructor import gui_blocks
from test_europedia_style import _all_loc, _loc, _texture_exists
from test_gui_blocks import _calls, _index, _vanilla

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
PANEL = MOD_ROOT / "in_game/gui/panels/situation/pp_mod_welcome_situation.gui"
SITUATION = MOD_ROOT / "in_game/common/situations/pp_mod_welcome_situation.txt"
SCRIPTED_GUI = MOD_ROOT / "in_game/common/scripted_guis/pp_welcome_situation.txt"
EUROPEDIA = MOD_ROOT / "in_game/gui/encyclopedia_lateralview.gui"


def _panel() -> str:
    return PANEL.read_text(encoding="utf-8-sig")


def _panel_loc() -> dict[str, str]:
    mod = _loc(MOD_ROOT)
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _panel())) | {"pp_mod_welcome_situation_desc"}
    return {k: mod[k] for k in keys if k in mod}


def test_panel_is_a_situation_panel_overriding_only_blocks_it_has():
    text = _panel()
    assert text.count("{") == text.count("}")
    assert re.search(r"(?m)^situation_panel = \{", text)
    assert not gui_blocks.dead_overrides(text, _index())
    for block in ("situation_panel_image", "situation_start_date", "situation_subheader_content", "situation_panel_main_content"):
        assert f'blockoverride "{block}"' in text
    assert re.search(r'blockoverride "situation_panel_main_actions" \{\s*\}', text)


def test_every_texture_and_text_key_exists():
    textures = set(re.findall(r'texture = "(gfx/[^"]+)"', _panel()))
    assert textures and not sorted(t for t in textures if not _texture_exists(t))
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _panel()))
    assert {"PP_WELCOME_SIT_LEAD", "PP_WELCOME_SIT_BODY", "PP_WELCOME_SIT_CTA", "PP_WELCOME_SIT_CTA_TT", "PP_WELCOME_SIT_DISMISS",
            "PP_WELCOME_SIT_DISMISS_TT"} <= keys
    assert not sorted(keys - set(_all_loc()))


def test_texts_carry_no_numbers():
    for key, value in _panel_loc().items():
        assert not re.search(r"\d", re.sub(r"\[[^\[\]]*\]", "", value)), key


def test_the_buttons_open_the_prosper_or_perish_section_and_dismiss_the_welcome():
    """The first button opens the Europedia and sets the two variables its PP section reads (shown, all cards); the
    dismiss button ends the welcome and closes the panel. A player's dismiss runs the scripted GUI (a game command,
    synced in multiplayer); the game drops every game command an observer sends (2026-10-24: the click only closed the
    panel), so the observer's own dismiss button runs the same effect through the console."""
    buttons = re.findall(r"button_\w+ = \{", _panel())
    assert len(buttons) == 3
    clicks = re.findall(r'onclick = "\[(.*?)\]"', _panel())
    effect = "end_situation = situation:pp_mod_welcome_situation"
    assert clicks == [
        "OpenLateralView('encyclopedia')",
        "GetVariableSystem.Set('pp_encyclopedia_active', 'yes')",
        "GetVariableSystem.Set('pp_filter', 'all')",
        "GetScriptedGui('pp_dismiss_welcome_situation').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)",
        "LateralView.Close",
        f"ExecuteConsoleCommand('effect {effect}')",
        "LateralView.Close",
    ]
    visible = re.findall(r'visible = "\[(.*?)\]"', _panel())
    assert visible == ["Not(IsPlayerObserver)", "IsPlayerObserver"]
    assert re.search(r"ignoreinvisible = yes", _panel())
    scripted = SCRIPTED_GUI.read_text(encoding="utf-8-sig")
    assert re.search(r"(?m)^pp_dismiss_welcome_situation = \{", scripted)
    assert "scope = country" in scripted
    assert effect in scripted
    europedia = EUROPEDIA.read_text(encoding="utf-8-sig")
    assert "GetVariableSystem.HasValue('pp_encyclopedia_active', 'yes')" in europedia
    assert "GetVariableSystem.HasValue('pp_filter', 'all')" in europedia
    # 'encyclopedia' is the lateral view vanilla's Europedia button opens
    right_panel = (_vanilla() / "in_game/gui/panels/right_panel/right_panel.gui").read_text(encoding="utf-8-sig")
    assert "ToggleLateralView('encyclopedia')" in right_panel


def test_data_functions_exist_in_the_game():
    used = _calls(_panel()) | {fn for value in _panel_loc().values() for fn in _calls(value)}
    assert {"OpenLateralView", "GetVariableSystem", "Set", "ExecuteConsoleCommand"} <= used
    vanilla = set()
    vanilla_text = ""
    for path in _vanilla().glob("*/gui/**/*.gui"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        vanilla |= _calls(text)
        vanilla_text += text
    assert not sorted(used - vanilla)
    # a bare name, which _calls does not collect
    assert "Not(IsPlayerObserver)" in vanilla_text


def test_situation_never_ends_by_itself_and_starts_once():
    """Only the dismiss button ends it (end_situation ignores can_end); it never starts again."""
    text = SITUATION.read_text(encoding="utf-8-sig")
    assert re.search(r"can_end = \{\s*always = no\s*\}", text)
    assert "pp_mod_welcome_situation_completed" not in text
    assert "remove_global_variable = pp_mod_welcome_situation_pending" in text


def test_picture_ships_with_the_mod():
    """tools/build_harvest_situation_art.py: vanilla's situation picture size; the icon is hand-kept."""
    with Image.open(MOD_ROOT / "main_menu/gfx/interface/illustrations/situation/pp_mod_welcome_situation.dds") as image:
        assert image.size == (1080, 440)
    assert (MOD_ROOT / "in_game/gfx/interface/icons/situations/pp_mod_welcome_situation.dds").is_file()
