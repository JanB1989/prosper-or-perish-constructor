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
    assert (MOD_ROOT / alb.CONCEPTS).read_text(encoding="utf-8") == alb.render_concepts()


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
    # the -1 per subsistence peasant is script-added (the growth pass applies unemployed_peasants after free land and
    # overpopulation): pp_subsistence_land at size = the idle peasants, refreshed yearly
    assert not re.search(r"(?m)^\s*local_population_capacity", _block(text, "unemployed_peasants"))
    static = (MOD_ROOT / "main_menu/common/static_modifiers/pp_subsistence_land.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"(?m)^\s*local_population_capacity = -1\s*$", static)
    effect = (MOD_ROOT / "in_game/common/scripted_effects/pp_subsistence_land_effects.txt").read_text(encoding="utf-8-sig")
    assert "size = pp_subsistence_peasants" in effect
    # never below 0: the game's idle count goes negative where buildings offer more peasant jobs than there are peasants
    # (Figueira da Foz 1837: -3,258 gave +3,260 Arable Land); the bar and the farm cap read the same floored count
    values = (MOD_ROOT / "in_game/common/script_values/pp_subsistence_peasants.txt").read_text(encoding="utf-8-sig")
    assert re.search(r'pp_subsistence_peasants = \{\s*value = "unemployed_pops_of_pop_type_in_location\(pop_type:peasants\)"'
                     r'\s*min = 0\s*\}', values)
    assert "pp_land_bar_subsistence = { value = pp_subsistence_peasants }" in alb.render_script_values(alb.model(MOD_ROOT, None))
    farm_cap = (MOD_ROOT / "in_game/common/script_values/pp_farming_capacity.txt").read_text(encoding="utf-8-sig")
    assert "subtract = pp_subsistence_peasants" in farm_cap and "unemployed_pops_of_pop_type_in_location" not in farm_cap
    on_action = (MOD_ROOT / "in_game/common/on_action/pp_subsistence_land.txt").read_text(encoding="utf-8-sig")
    # yearly, spread over the year (2026-10-27, Jan: idle peasants move little; a month of refreshes cost 0.02 s)
    assert "yearly_country_pulse" in on_action and "days = { 0 364 }" in on_action and "on_game_start" in on_action
    assert "monthly_country_pulse" not in on_action


def _panel() -> str:
    text = WINDOW.read_text(encoding="utf-8-sig")
    start = text.rindex("vbox = {", 0, text.index('name = "pp_arable_land_bar"'))
    return text[start:alb._block_end(text, text.index("{", start)) + 1]


def test_window_has_the_panel_under_the_scene_with_balanced_braces():
    text = WINDOW.read_text(encoding="utf-8-sig")
    assert text.count('name = "pp_arable_land_bar"') == 1
    assert text.index("# SCENE") < text.index('name = "pp_arable_land_bar"')
    assert text.count("{") == text.count("}")
    panel = _panel()
    # 5 bar parts + 4 legend swatches + 2 tooltips x 7 row swatches (the over row's: yellow under the over mark); every
    # one on 0..1 (without min/max: 0..100)
    assert panel.count("progressbar = {") == 23 == panel.count("min = 0 max = 1 value = ")
    assert not re.search(r'value = "\[\(float\)', panel)                               # a literal is no data call
    used = set(re.findall(r"ScriptValue\('(pp_land_bar_\w+)'\)", text + alb.render_localization()))
    defined = set(re.findall(r"(?m)^(pp_land_bar_\w+) = \{", (MOD_ROOT / alb.SCRIPT_VALUES).read_text(encoding="utf-8")))
    assert used and used <= defined
    keys = set(re.findall(r'text = "(PP_LAND_BAR_\w+)"', panel)) | set(re.findall(r'tooltip = "(PP_LAND_BAR_\w+)"', panel))
    assert keys <= set(alb.LOC_TEXT)
    # every data-bound size is a pixel vector (a bare number or a stretch factor broke the widths in game)
    sizes = re.findall(r'size = "(\[[^"]*\])"', panel)
    assert sizes and all(s.startswith("[ToVector2f(") for s in sizes)
    assert "layoutstretchfactor" not in panel


def test_subsistence_peasants_are_one_part_and_the_ones_over_capacity_are_marked_on_it():
    panel = _panel()
    bars = panel[panel.index('"PP_LAND_BAR_CAPACITY" parentanchor'):]
    track = bars.index("size = { 370 18 }")
    first_track = bars[track:bars.index("size = { 370 18 }", track + 1)]
    # two parts: townsfolk, then every subsistence peasant (population - townsfolk), no separate over part
    assert first_track.count("progressbar = {") == 2 and first_track.count("progress_bar_yellow.dds") == 1
    assert "'pp_land_bar_f_population')), FixedPointToFloat(LocationView.GetLocation.MakeScope.ScriptValue('pp_land_bar_f_townsfolk'))" in first_track
    # the over mark lies over the yellow from the capacity on (spacer = the part within it), red tint and edges
    assert "ScriptValue('pp_land_bar_f_within')), '(float)370'), '(float)0'), '(float)18')]" in first_track
    assert first_track.count("progress_bar_red.dds") == 4 and "alpha" not in first_track.split("progress_bar_yellow")[1]
    column = panel[panel.index("size = { 370 40 }"):panel.index('name = "pp_land_bar_state')]
    assert "progress_bar_red_alt" not in column and '"+[' not in column        # no red block with its own +number
    # its number is in the tooltip, in the population list, only when there are any
    at = panel.index('text = "PP_LAND_BAR_TT_OVER"')
    over_row = panel[panel.rindex("TooltipTableField = {", 0, at):at]
    assert over_row.startswith('TooltipTableField = { blockoverride "visibility" { visible = "[GreaterThan_float(Max_float(Subtract_float(')
    assert over_row.index("progress_bar_yellow.dds") < over_row.index("progress_bar_red.dds")   # swatch: the mark on yellow
    assert at > panel.index('text = "PP_LAND_BAR_TT_TOTAL"')                                    # under the total
    assert "Over the [population_capacity|e]" == alb.LOC_TEXT["PP_LAND_BAR_TT_OVER"]


def test_threshold_lines_cross_both_bars_at_a_tenth_of_the_capacity_and_at_the_capacity():
    panel = _panel()
    column = panel[panel.index("size = { 370 40 }"):panel.index('name = "pp_land_bar_state')]
    lines_at = column.index("position = { 0 -2 }")
    # drawn over the bars (after both tracks) and under the parts' numbers (no line hides a number)
    assert column.index("progress_bar_brown_alt.dds") < lines_at < column.index("ScriptValue('pp_land_bar_townsfolk')|0]K")
    assert alb.ABUNDANT_SHARE == "0.1"
    capacity = "FixedPointToFloat(LocationView.GetLocation.MakeScope.ScriptValue('pp_land_bar_f_capacity'))"
    abundant = f"Multiply_float({capacity}, '(float)0.1')"
    # the first line's centre at a tenth of the capacity, the second's at the capacity, on the bars' 370 px scale
    assert f"Max_float(Subtract_float(Multiply_float({abundant}, '(float)370'), '(float)1.5'), '(float)0')" in column
    assert f"Max_float(Subtract_float(Multiply_float(Subtract_float({capacity}, {abundant}), '(float)370'), '(float)3'), '(float)0')" in column
    # an overlay: positioned from the bars' column, taller than both bars, so it moves nothing
    assert "size = { 100% 44 }" in column and f"visible = \"[GreaterThan_float({capacity}, '(float)0')]\"" in column
    assert column.count("size = { 3 44 }") == 2 and column.count("progress_bar_whiteish.dds") == 2
    assert "tooltip = " not in column


def test_tooltip_ends_with_one_line_per_land_state_shared_with_the_chips():
    tooltip = alb.tooltip_block()
    assert "PP_LAND_BAR_TT_NOTE" not in tooltip and "PP_LAND_BAR_TT_NOTE" not in alb.LOC_TEXT
    status = (MOD_ROOT / "main_menu/localization/english/pp_location_status_l_english.yml").read_text(encoding="utf-8-sig")
    for key, concept, name, chip in alb.LAND_STATES:
        assert (MOD_ROOT / "main_menu" / alb.STATE_ICONS / f"{key}.dds").is_file()
        assert f'texture = "{alb.STATE_ICONS}/{key}.dds"' in tooltip and f'text = "PP_LAND_BAR_TT_DEF_{key.upper()}"' in tooltip
        # a link with the chip's title, then the chip's own one-line definition
        assert alb.LOC_TEXT[f"PP_LAND_BAR_TT_DEF_{key.upper()}"] == f"[Concept('{concept}', '{name}')|e]: ${chip}$"
        assert f'{chip}_TITLE: "{name}"' in status
        assert re.search(rf'(?m)^\s*{chip}: "\[population\|E\] [^"]*\[population_capacity\|e\][^"]*"$', status)
    assert "at most 10% of the [population_capacity|e] and below 10,000 people" in status
    assert tooltip.index("PP_LAND_BAR_TT_DEF_ABUNDANT") > tooltip.index('"PP_LAND_BAR_CAPACITY"')


def test_every_row_label_is_a_concept_link_with_its_own_entry():
    tooltip = alb.tooltip_block()
    rows = re.findall(r'layoutpolicy_horizontal = expanding align = left\|nobaseline text = "(\w+)"', tooltip)
    labels = [key for key in rows if key != "PP_LAND_BAR_TT_TOTAL"]
    assert len(labels) == 7   # townsfolk, subsistence, over | townsfolk, land, improvements, farms
    link = re.compile(r"\[(\w+)\|[eE]\]|\[Concept\('(\w+)', '[^']+'\)\|e\]")
    vanilla = _game()
    known: set[str] = set()   # concept keys and their aliases, the mod's and the game's
    for path in sorted((MOD_ROOT / "main_menu/common/game_concepts").glob("*.txt")) + (
            sorted((vanilla / "main_menu/common/game_concepts").glob("*.txt")) if vanilla else []):
        text = path.read_text(encoding="utf-8-sig")
        known |= set(re.findall(r"(?m)^﻿?(\w+) = \{", text))
        known |= {word for alias in re.findall(r"alias = \{([^}]*)\}", text) for word in alias.split()}
    assert {"pp_townsfolk", "population", "population_capacity", "buildings", "employment"} <= known
    for key in set(labels) | {"PP_LAND_BAR_LAND", "PP_LAND_BAR_POPULATION", "PP_LAND_BAR_CAPACITY"}:
        found = link.findall(alb.LOC_TEXT[key])
        assert found, key
        assert all((a or b) in known for a, b in found), (key, found)
    # the townsfolk are one row in both lists (no "their own room" any more), farms one key for legend and tooltip
    assert "PP_LAND_BAR_TT_TOWNSFOLK_ROOM" not in alb.LOC_TEXT and "PP_LAND_BAR_TT_FARMS" not in alb.LOC_TEXT
    assert "own room" not in alb.render_localization()
    # the legend uses the same linked keys
    legend = alb.gui_block()[alb.gui_block().rindex("tooltipwidget"):]
    assert {"PP_LAND_BAR_TOWNSFOLK", "PP_LAND_BAR_SUBSISTENCE", "PP_LAND_BAR_LAND", "PP_LAND_BAR_FARMS"} <= set(
        re.findall(r'text_single = \{ text = "(\w+)" fontsize = 12', legend))


def test_new_concepts_have_a_family_an_icon_a_name_and_a_short_text():
    concepts = (MOD_ROOT / alb.CONCEPTS).read_text(encoding="utf-8-sig")
    assert concepts == alb.render_concepts().lstrip("﻿")
    loc = alb.render_localization()
    for key, (texture, name, text) in alb.CONCEPT_TEXT.items():
        assert re.search(rf'{key} = \{{\s*family = food\s*texture = "{re.escape(texture)}"\s*\}}', concepts)
        game = _game()
        assert (MOD_ROOT / "main_menu/gfx/interface/icons" / f"{texture}.dds").is_file() or (
            game is not None and (game / "main_menu/gfx/interface/icons" / f"{texture}.dds").is_file()), texture
        assert f'game_concept_{key}: "{name}"' in loc and f'game_concept_{key}_desc: "{text}"' in loc
        # short and technical: one or two sentences, links, no values but the per-person 1
        assert text.count(". ") <= 1 and ("|e]" in text or "|E]" in text)
        assert not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", text).replace(" 1 ", " ").replace(" 1.", "."))
        assert "room" not in text
    # every concept a text names is a link; each text links the concepts it builds on
    links = set(re.findall(r"\[(\w+)\|[eE]\]", " ".join(text for _, _, text in alb.CONCEPT_TEXT.values())))
    assert {"pp_subsistence_peasants", "population_capacity", "employment", "location_rank", "buildings"} <= links
