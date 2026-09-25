"""The location view's Growth tab (population growth per estate)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor import growth_tab

MOD_ROOT = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
VANILLA_WINDOW = Path.home() / ".cache" / "eu5-vanilla" / "game" / "in_game" / "gui" / "location_window.gui"


def _window() -> str:
    return (
        "\t\t\t\t\tbutton_secondary_tab_alt = {\n"
        "\t\t\t\t\t\tdown = \"[LocationView.Vars.HasValue( 'tab', 'demography' )]\"\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t}\n"
        "\t\t\t\t# DEMOGRAPHY\n"
        "\t\t\t\tvbox = {\n"
        "\t\t\t\t\tvisible = \"[LocationView.Vars.HasValue( 'tab', 'demography' )]\"\n"
        "\t\t\t\t}\n"
    )


def test_tab_button_follows_demography_and_pane_precedes_it():
    merged = growth_tab.add_growth_tab(_window())
    assert merged.count("'tab', 'growth'") == 3   # button on_action, button down, pane visible
    assert merged.index("PP_LOC_VIEW_GROWTH_TAB") > merged.index("'tab', 'demography' )]\"\n\t\t\t\t\t}")
    assert merged.index("# PP GROWTH (growth_tab.py)") < merged.index("# DEMOGRAPHY")
    for block in (growth_tab._TAB_BUTTON, growth_tab._PANE):
        assert block.count("{") == block.count("}")
        assert "{{" not in block and "}}" not in block   # a stray f-string escape broke the window once (2026-09-25)
    for line in growth_tab._PANE.splitlines():
        s = line.strip()
        if s.startswith("visible = ") or s.startswith("datacontext = ") or s.startswith("datamodel = "):
            assert s.endswith(']"') and '= "[' in s, s


def test_rows_show_growth_and_actual_change_apart():
    merged = growth_tab.add_growth_tab(_window())
    assert 'datamodel = "[LocationView.GetPops]"' in merged
    for fn in ("LocationPopItem.GetTotalSize", "LocationPopItem.GetGrowthForUI|Y", "using = LocationPopItem_Breakdown",
               "Location.GetPopGrowth", "PopType.GetKey, '_pop_growth'"):
        assert fn in merged, fn


def test_merge_is_idempotent():
    once = growth_tab.add_growth_tab(_window())
    assert growth_tab.add_growth_tab(once) == once
    assert growth_tab.strip_growth_tab(once) == _window()


def test_anchor_count_is_enforced():
    with pytest.raises(ValueError, match="growth tab"):
        growth_tab.add_growth_tab(_window() + _window())


def test_localization_covers_every_key_the_pane_uses():
    keys = {k for k in growth_tab.LOCALIZATION_TEXT.split() if k.startswith("PP_") and k.endswith(":")}
    used = {f"{k}:" for k in ("PP_LOC_VIEW_GROWTH_TAB", "PP_LOC_VIEW_GROWTH_TAB_TT", "PP_GROWTH_TAB_RATE_TT",
                              "PP_GROWTH_TAB_FREE_LAND_TT")}
    for key in used:
        assert key in keys, key
    for key in ("PP_GROWTH_TAB_LOCATION_GROWTH", "PP_GROWTH_TAB_MIGRATION_ATTRACTION", "PP_GROWTH_TAB_FREE_LAND",
                "PP_GROWTH_TAB_COL_POPS", "PP_GROWTH_TAB_COL_CHANGE", "PP_GROWTH_TAB_COL_RATE",
                "PP_GROWTH_TAB_CHANGE_TT"):
        assert key in growth_tab._PANE and f"{key}:" in keys, key


@pytest.mark.skipif(not VANILLA_WINDOW.is_file(), reason="vanilla mirror not present")
def test_vanilla_window_carries_both_anchors_once():
    text = VANILLA_WINDOW.read_text(encoding="utf-8-sig")
    assert text.count(growth_tab._TAB_ANCHOR) == 1
    assert text.count(growth_tab._PANE_ANCHOR) == 1


def test_built_window_and_localization_carry_the_tab():
    window = MOD_ROOT / "in_game" / "gui" / "location_window.gui"
    loc = MOD_ROOT / growth_tab.LOCALIZATION
    if not window.is_file():
        pytest.skip("mod not built")
    assert "'tab', 'growth'" in window.read_text(encoding="utf-8-sig")
    assert loc.is_file() and "PP_LOC_VIEW_GROWTH_TAB:" in loc.read_text(encoding="utf-8-sig")
