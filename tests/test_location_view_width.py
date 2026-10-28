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
WINDOW = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "in_game" / "gui" / "location_window.gui"


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
