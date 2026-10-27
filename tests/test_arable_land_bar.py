"""The population and capacity bars of the location view (arable_land_bar.py, 2026-10-27).

Population = townsfolk + subsistence peasants; capacity = the townsfolk's own room + the arable land left (land +
improvements - farms), as total_population (+1 per person) and unemployed_peasants (-1 per subsistence peasant) make it.
The farm land and the improvements are read from the building types the game loads.
"""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import arable_land_bar as alb

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
WINDOW = MOD_ROOT / "in_game/gui/location_window.gui"
STATIC = MOD_ROOT / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt"


def _game() -> Path | None:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    return game_root(vanilla_root(ROOT, ROOT / "constructor.toml"))


def test_generated_files_are_current():
    assert (MOD_ROOT / alb.SCRIPT_VALUES).read_text(encoding="utf-8") == alb.render_script_values(alb.model(MOD_ROOT, _game()))
    assert (MOD_ROOT / alb.LOCALIZATION).read_text(encoding="utf-8") == alb.render_localization()


def test_farms_read_their_counters_and_improvements_add_land():
    m = alb.model(MOD_ROOT, None)
    assert len(m.improvements) >= 10 and all(b.land > 0 for b in m.improvements)
    assert len(m.farms) >= 40 and all(b.counter and b.counter.startswith("pp_levels_") for b in m.farms)
    assert all(b.land < 0 for b in m.farms + m.reserved)


def _block(text: str, name: str) -> str:
    start = text.index(f"TRY_REPLACE:{name} = {{")
    return text[start:alb._block_end(text, text.index("{", start)) + 1]


def test_capacity_is_everyone_but_the_subsistence_peasants():
    text = STATIC.read_text(encoding="utf-8-sig")
    assert re.search(r"(?m)^\s*local_population_capacity = 1\s*$", _block(text, "total_population"))
    assert re.search(r"(?m)^\s*local_population_capacity = -1\s*$", _block(text, "unemployed_peasants"))


def test_window_has_the_panel_under_the_scene_with_balanced_braces():
    text = WINDOW.read_text(encoding="utf-8-sig")
    assert text.count('name = "pp_arable_land_bar"') == 1
    assert text.index("# SCENE") < text.index('name = "pp_arable_land_bar"')
    assert text.count("{") == text.count("}")
    start = text.rindex("vbox = {", 0, text.index('name = "pp_arable_land_bar"'))
    panel = text[start:alb._block_end(text, text.index("{", start)) + 1]
    bars = re.findall(r"progressbar = \{[^\n]*", panel)
    assert len(bars) == 10 and all("min = 0 max = 1 value = " in bar for bar in bars)   # without them 0..100
    assert not re.search(r'value = "\[\(float\)', panel)                               # a literal is no data call
    used = set(re.findall(r"ScriptValue\('(pp_land_bar_\w+)'\)", text + alb.render_localization()))
    defined = set(re.findall(r"(?m)^(pp_land_bar_\w+) = \{", (MOD_ROOT / alb.SCRIPT_VALUES).read_text(encoding="utf-8")))
    assert used and used <= defined
    keys = set(re.findall(r'text = "(PP_LAND_BAR_\w+)"', panel)) | set(re.findall(r'tooltip = "(PP_LAND_BAR_\w+)"', panel))
    assert keys <= set(alb.LOC_TEXT)
