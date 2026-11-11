"""The location view is one width: its header (title, arrows, close button) and its body line up.

A child row wider than the panel spills out past the header (the panel's widget does not grow with its content), so
every fixed-width row must fit the view's width minus the content margins (Jan, 2026-10-28: the population bars' row
with the land state beside it pushed the body ~25 px past the header, more or less by location).
"""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import arable_land_bar, location_status, location_view

ROOT = Path(__file__).resolve().parents[1]
WINDOW = ROOT / "mod" / "pp" / "in_game" / "gui" / "location_window.gui"


def _bar_block(text: str) -> str:
    start = text.index('name = "pp_arable_land_bar"')
    return text[start : text.index("PP_LAND_BAR_TOWNSFOLK", text.rindex('name = "pp_land_bar_state_'))]


def test_the_view_has_its_width():
    text = WINDOW.read_text(encoding="utf-8-sig")
    assert f'widgetid = "location_window"\n\tsize = {{ {location_view.WINDOW_WIDTH} 100% }}' in text


def test_the_bars_row_fits_the_view():
    text = WINDOW.read_text(encoding="utf-8-sig")
    block = _bar_block(text)
    bars = arable_land_bar.LABEL_WIDTH + 8 + arable_land_bar.BAR_WIDTH
    assert f"size = {{ {bars} " in block
    chips = [int(w) for w in re.findall(r'name = "pp_land_bar_state_\w+"\s*\n\s*size = \{ (\d+) \d+ \}', block)]
    assert chips, "land state chips not found beside the bars"
    texts = re.findall(r'\|0%\]" fontsize = 14 default_format = "#yellow_titles" '
                       r"minimumsize = \{ (\d+) -1 \} maximumsize = \{ (\d+) -1 \}", block)
    assert texts and all(int(a) == int(b) == location_status.STATE_TEXT_WIDTH for a, b in texts)
    # widest case: margins, the bars, the spacing before and after the expand, the chip, its spacing, its strength
    row = (2 * arable_land_bar.ROW_MARGIN + bars + 2 * arable_land_bar.ROW_SPACING
           + max(chips) + 4 + location_status.STATE_TEXT_WIDTH)
    assert row <= location_view.WINDOW_WIDTH - location_view.CONTENT_MARGINS


def _first_int(pattern: str, text: str) -> int:
    found = re.search(pattern, text)
    assert found, f"not found in the location window: {pattern}"
    return int(found.group(1))


def test_the_queue_buttons_sit_in_one_row_clear_of_the_status_card_and_the_bars():
    # 2026-11-11 (Jan, Krakow): vanilla stacks the construction queue buttons up from the scene's bottom-right corner;
    # two of them covered the status card (Stored Food, harvest) right of the IO row and sat on the population bars
    text = WINDOW.read_text(encoding="utf-8-sig")
    assert "size = { 62 220 }" not in text and "bottomtotop" not in text[text.index("# SCENE"):text.index("# TABS")]
    assert text.count(f'name = "{location_view.QUEUE_ROW}"') == 1
    start = text.index(f'name = "{location_view.QUEUE_ROW}"')
    block = text[start:text.index("# PP: population and capacity bars", start)]
    assert re.search(r"\bhbox = \{\s*\n\s*righttoleft = yes\b", block) and "vbox = {" not in block
    assert block.count("location_queue_button = {") == location_view.QUEUE_BUTTONS

    found = re.search(r"position = \{ -(\d+) (\d+) \}\s*\n\s*size = \{ (\d+) (\d+) \}", block)
    assert found, "the queue row has no fixed position and size"
    margin, top, width, height = map(int, found.groups())
    spacing = _first_int(r"righttoleft = yes\s*\n\s*spacing = (\d+)", block)
    button = re.search(r"type location_queue_button = header_button_left \{\s*\n\s*size = \{ (\d+) (\d+) \}", text)
    assert button, "vanilla's queue button type not found"
    button_w, button_h = map(int, button.groups())
    buttons = location_view.QUEUE_BUTTONS
    # one row holds every queue's button side by side, and the row fits the scene
    assert height == button_h and width >= buttons * button_w + (buttons - 1) * spacing
    assert margin + width <= location_view.WINDOW_WIDTH - location_view.CONTENT_MARGINS

    # vertically: under the condition icons' band (top left, full width), above the occupation banner (centred), the
    # status card (top of the IO row, which sits on the geography band at the bottom) and so the population bars
    scene = _first_int(r"# SCENE\s*\n\s*widget = \{\s*\n\s*layoutpolicy_horizontal = expanding\s*\n\s*size = \{ -1 (\d+) \}", text)
    band = _first_int(rf'name = "{location_view.MODIFIER_ROW}"\s*\n\s*parentanchor = top\|left\s*\n\s*size = \{{ 100% (\d+) \}}', text)
    banner = _first_int(r"parentanchor = center\s*\n\s*size = \{ 100% (\d+) \}\s*\n\s*datacontext = \"\[LocationView\.GetLocation\]\"\s*\n"
                        r"\s*visible = \"\[Location\.IsOccupied\]\"", text)
    io_row = _first_int(r"# IOs & PERIPHORA\s*\n\s*widget = \{\s*\n\s*layoutpolicy_horizontal = expanding\s*\n\s*size = \{-1 (\d+)\}", text)
    geography = _first_int(r'name = "ha1300_native_geography_row"\s*\n\s*layoutpolicy_horizontal = expanding\s*\n'
                           r"\s*maximumsize = \{ -1 (\d+) \}", text)
    card = text.index('name = "pp_location_status_row"')
    assert text.index("# IOs & PERIPHORA") < card < text.index("# BOTTOM CONDITIONS")
    status_top = scene - geography - io_row
    assert band <= top and top + height <= (scene - banner) // 2 and top + height <= status_top


def test_the_queue_row_patch_needs_vanillas_column_once():
    import pytest

    text = WINDOW.read_text(encoding="utf-8-sig")
    with pytest.raises(ValueError, match="construction queue column"):
        location_view.queue_buttons_in_a_row(text)   # the shipped window has the row already
