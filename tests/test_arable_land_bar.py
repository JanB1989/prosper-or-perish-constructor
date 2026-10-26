"""The Arable Land bar of the location view (arable_land_bar.py, 2026-10-26).

Land = natural + improvements (+ room for improvements in grey); use = farms + reserved grounds + subsistence peasants.
The natural land is the remainder of the flat capacity, so every capacity row the bar splits off must be read from the
files the game loads.
"""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import arable_land_bar as alb

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
WINDOW = MOD_ROOT / "in_game/gui/location_window.gui"


def _model() -> alb.Model:
    return alb.model(MOD_ROOT, None)


def test_generated_files_are_current():
    assert (MOD_ROOT / alb.SCRIPT_VALUES).read_text(encoding="utf-8") == alb.render_script_values(alb.model(MOD_ROOT, _game()))
    assert (MOD_ROOT / alb.LOCALIZATION).read_text(encoding="utf-8") == alb.render_localization()


def _game() -> Path | None:
    from prosper_or_perish_constructor.cap_tooltips import game_root
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

    return game_root(vanilla_root(ROOT, ROOT / "constructor.toml"))


def test_every_improvement_belongs_to_one_cap_and_farms_read_their_counters():
    m = _model()
    assert len(m.improvements) >= 10
    members = [b.key for unit in m.units for b in unit.members]
    assert sorted(members) == sorted(b.key for b in m.improvements)
    assert all(unit.equation.startswith("pp_wb_cap_") and unit.limit for unit in m.units)
    assert len(m.farms) >= 40 and all(b.counter and b.counter.startswith("pp_levels_") for b in m.farms)
    assert all(b.land < 0 for b in m.farms + m.reserved)
    assert {b.key for b in m.housing}.isdisjoint(b.key for b in m.improvements)


def test_potentials_keep_question_mark_operators_and_skip_comments():
    text = 'REPLACE:a = {\n location_potential = {\n  dominant_culture ?= culture:x # note }\n  has_river = yes\n }\n}\nb = { x = 1 }\n'
    assert alb.potentials(text) == {"a": "dominant_culture ?= culture:x has_river = yes"}


def test_room_takes_the_best_allowed_member_and_clamps_to_the_cap():
    unit = alb.CapUnit("pp_wb_cap_group_shared", 15, [
        alb.Building("plain", 5.0), alb.Building("niche", 7.5, potential="has_river = yes")])
    text = alb._room(unit)
    assert "value = pp_wb_cap_group_shared\n\tmax = 15\n" in text
    assert text.index("subtract = \"location_building_level(building_type:plain)\"") < text.index("min = 0")
    assert "if = { limit = { has_river = yes } value = 7.5 }\n\telse = { value = 5 }" in text


def test_window_has_the_panel_under_the_scene_with_balanced_braces():
    text = WINDOW.read_text(encoding="utf-8-sig")
    assert text.count('name = "pp_arable_land_bar"') == 1
    assert text.index("# SCENE") < text.index('name = "pp_arable_land_bar"')
    assert text.count("{") == text.count("}")
    start = text.rindex("vbox = {", 0, text.index('name = "pp_arable_land_bar"'))
    panel = text[start:alb._block_end(text, text.index("{", start)) + 1]
    bars = re.findall(r"progressbar = \{[^\n]*", panel)
    assert len(bars) == 13 and all("min = 0 max = 1 value = " in bar for bar in bars)   # without them 0..100
    assert not re.search(r'value = "\[\(float\)', panel)                                # a literal is no data call
    used = set(re.findall(r"ScriptValue\('(pp_land_bar_\w+)'\)", text))
    defined = set(re.findall(r"(?m)^(pp_land_bar_\w+) = \{", (MOD_ROOT / alb.SCRIPT_VALUES).read_text(encoding="utf-8")))
    assert used and used <= defined
    keys = set(re.findall(r'text = "(PP_LAND_BAR_\w+)"', text)) | set(re.findall(r'tooltip = "(PP_LAND_BAR_\w+)"', text))
    assert keys <= set(alb.LOC_TEXT)
