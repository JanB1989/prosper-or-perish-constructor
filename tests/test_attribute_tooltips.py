"""Geography chip tooltips: effects first, goods output as an icon table after (view only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder import attribute_tooltips as tt

_TEMPLATES = """\
template Topography_tooltip {
    ContextualTooltipType = {
        blockoverride "title_text" { text = "MAP_TT_TOPOGRAPHY_TITLE" }
        blockoverride "tooltip_content" {
            TooltipDebugTextBlock = { blockoverride "text" { debug_text = "[Topography.GetDebugText]" } }
            TooltipBlockList = {
                ontextcontextchanged = "[SetBlockListFromTextContext(PdxGuiWidget.AccessSelf)]"
                textcontext = "[Topography.GetTooltip]"
            }
            TooltipFlavorTextBlock = { blockoverride "text" { text = "[Topography.GetDesc]" } }
        }
    }
}

template Climate_tooltip {
    ContextualTooltipType = {
        blockoverride "title_icon" {
            icon = {
                # size = { 30 30 }
                texture = "[GetClimateIcon(Climate.Self)]"
            }
        }
        blockoverride "tooltip_content" {
            TooltipStringPairList = { textcontext = "[Climate.GetTooltip]" }
        }
    }
}

template Vegetation_tooltip {
    ContextualTooltipType = {
        blockoverride "tooltip_content" {
            TooltipStringPairList = { textcontext = "[Vegetation.GetTooltip]" }
            TooltipFlavorTextBlock = { blockoverride "text" { text = "[Vegetation.GetDesc]" } }
        }
    }
}
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("﻿" + text, encoding="utf-8")


@pytest.fixture
def trees(tmp_path: Path) -> tuple[Path, Path]:
    vanilla, mod = tmp_path / "vanilla", tmp_path / "mod"
    game = vanilla / "game"
    _write(game / "in_game/common/goods/00_raw.txt", "wheat = { method = farming }\ntea = { method = farming }\nlumber = { }\n")
    _write(game / "in_game/common/vegetation/00_default.txt", (
        "forest = {\n\tcolor = terrain_forest\n\tmovement_cost = 1.25\n\tdefender = 1\n\tlocation_modifier = {\n"
        "\t\tlocal_population_capacity = 25\n\t\tlocal_road_building_time = 0.5\n\t\tlocal_wheat_output_modifier = 0.1\n"
        "\t\tblocks_vision_from_land = yes\n\t}\n\tdebug_color = rgb { 1 2 3 } # comment { with braces\n}\n"
        "sparse = {\n\tmovement_cost = 1.0\n\tlocation_modifier = { local_population_capacity = 10 }\n}\n"
    ))
    _write(game / "in_game/common/climates/00_default.txt", "arid = {\n\twinter = mild\n\tlocation_modifier = { local_food_decay = 0.002 }\n}\n")
    _write(game / "in_game/common/topography/00_default.txt", "flatland = {\n\tmovement_cost = 1\n}\n")
    _write(game / "main_menu/common/static_modifiers/location.txt", "river_flowing_through_1 = {\n\tlocal_supply_limit_modifier = 0.05\n}\n")
    _write(game / "main_menu/localization/english/terrains_l_english.yml", (
        'l_english:\n TERRAIN_MOVEMENT_COST: "Movement Cost for [units|e]: $VALUE|-=%V$"\n'
        ' TERRAIN_ATTACKER_PENALTY: "Attacker Penalty in [combat|e]: $VALUE|-=$"\n'
        ' CLIMATE_TT_WINTER: "[winter_level_max|e]: [ShowModifier(\'winter_$MAX$\')]"\n'
    ))
    _write(game / tt.VANILLA_TOOLTIPS.relative_to("game"), _TEMPLATES)
    # the mod: World Builder class rows as injects, the World Builder static modifiers
    _write(mod / "in_game/common/vegetation/pp_wb_attribute_rows.txt", (
        "TRY_INJECT:forest = {\n\tlocation_modifier = {\n\t\tlocal_population_capacity = -25\n\t\tlocal_tea_output_modifier = 0.18\n"
        "\t\tlocal_wheat_output_modifier = -0.14\n\t\tlocal_rgo_output_modifier = 0.05\n\t}\n}\n"
        "TRY_INJECT:sparse = {\n\tlocation_modifier = { local_population_capacity = -8 local_lumber_output_modifier = -0.03 }\n}\n"
    ))
    _write(mod / "main_menu/common/static_modifiers/pp_wb_attribute_modifiers.txt", (
        "pp_wb_fertility_high = {\n\tgame_data = { category = location }\n\tlocal_population_capacity = 3.8\n\tlocal_wheat_output_modifier = 0.03\n}\n"
        "pp_wb_soil_loam = {\n\tgame_data = { category = location }\n\tlocal_tea_output_modifier = 0.05\n}\n"
        "pp_wb_coastal = {\n\tgame_data = { category = location }\n\tlocal_lumber_output_modifier = 0.07\n}\n"
        "pp_wb_lake = {\n\tgame_data = { category = location }\n\tlocal_defensive = 0.1\n}\n"
    ))
    return vanilla, mod


def test_definitions_sum_injects_and_ignore_injects_into_replaced_blocks(tmp_path):
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    first.write_text("x = { location_modifier = { local_a = 1 local_b = 0.5 } movement_cost = 1.1 }\nTRY_REPLACE:y = { local_c = 1 }\n", encoding="utf-8")
    second.write_text("TRY_INJECT:x = { location_modifier = { local_a = -1 local_b = 0.25 } movement_cost = 1.5 }\nTRY_INJECT:y = { local_c = 2 }\nTRY_INJECT:z = { local_d = 1 }\n", encoding="utf-8")
    defs = tt.definitions([first, second])
    assert set(defs) == {"x"}   # a TRY_REPLACE or TRY_INJECT of an unknown block creates nothing
    assert tt.modifier_lines(defs["x"], "location_modifier") == {"local_b": "0.75"}   # cancelled lines drop out
    assert tt.scalars(defs["x"])["movement_cost"] == "1.5"
    base = tmp_path / "0.txt"
    base.write_text("y = { local_c = 5 }\n", encoding="utf-8")
    replaced = tt.definitions([base, first, second])
    assert tt.modifier_lines(replaced["y"]) == {"local_c": "1"}   # the inject after the replacement is ignored


def test_goods_split_off_best_first_and_other_output_keys_stay():
    effects, goods = tt.split_goods({"local_tea_output_modifier": "0.18", "local_rgo_output_modifier": "0.05", "local_wheat_output_modifier": "-0.14", "local_lumber_output_modifier": "0.18"}, {"tea", "wheat", "lumber"})
    assert effects == {"local_rgo_output_modifier": "0.05"}
    assert goods == [("lumber", 0.18), ("tea", 0.18), ("wheat", -0.14)]


def test_values_follow_the_localization_flags():
    assert tt.format_value(0.18, "+=%") == "#P +18%#!"
    assert tt.format_value(-0.14, "+=%") == "#N -14%#!"
    assert tt.format_value(0.25, "-=%V") == "#N +25%#!"   # a cost: positive is bad
    assert tt.format_value(1, "-=") == "#N +1#!"
    assert tt.format_value(0.125, "%") == "12.5%"


def test_terrain_lines_word_the_engine_fields_with_vanilla_localization():
    loc = {"TERRAIN_MOVEMENT_COST": "Move: $VALUE|-=%V$", "TERRAIN_ATTACKER_PENALTY": "Attacker: $VALUE|-=$", tt.WINTER_KEY: "Winter: [ShowModifier('winter_$MAX$')]", "TERRAIN_BLOCKS_IN_WINTER": "Blocked."}
    lines = tt.terrain_lines({"winter": "severe", "movement_cost": "1.5", "defender": "0", "blocked_in_winter": "yes"}, loc)
    assert lines == ["Winter: [ShowModifier('winter_severe')]", "Move: #N +50%#!", "Blocked."]
    assert tt.terrain_lines({"movement_cost": "1.0"}, loc) == []   # normal ground says nothing


def test_write_builds_views_that_hold_effects_and_goods_apart(trees):
    vanilla, mod = trees
    counts = tt.write(mod, vanilla)
    assert counts == {"climate": 0, "vegetation": 2, "topography": 0, "fertility": 1, "soil": 1, "coast": 1, "lake": 0}

    modifiers = (mod / tt.MODIFIERS_PATH).read_text(encoding="utf-8-sig")
    forest = modifiers[modifiers.index("pp_tt_vegetation_forest = {"):]
    forest = forest[:forest.index("\n}\n") + 2]
    assert "local_road_building_time = 0.5" in forest and "blocks_vision_from_land = yes" in forest
    assert "local_rgo_output_modifier = 0.05" in forest   # not a good: stays with the effects
    assert "local_population_capacity" not in forest and "_output_modifier = -" not in forest and "tea" not in forest
    assert "pp_tt_fertility_high = {" in modifiers and "pp_tt_soil_loam" not in modifiers   # goods only: no effects list

    gui = (mod / tt.GUI_PATH).read_text(encoding="utf-8-sig")
    assert gui.count("{") == gui.count("}")
    for attribute in ("topography", "climate", "vegetation"):
        assert f"template pp_attribute_tooltip_{attribute} {{" in gui and f"pp_attribute_view_{attribute} = {{}}" in gui
        # the engine list stays for classes the view does not know
        assert f"Custom('pp_tt_{attribute}'), Localize('PP_TT_KEY_NONE'))]\"" in gui
    assert "template Vegetation_tooltip" not in gui and "debug_text = \"[Topography.GetDebugText]\"" in gui
    section = gui[gui.index("Localize('PP_TT_KEY_VEGETATION_FOREST')"):]
    section = section[:section.index("TooltipContentSection")]
    assert "ShowModifierEffect('pp_tt_vegetation_forest')" in section and "PP_TT_EXTRAS_VEGETATION_FOREST" in section
    assert section.index("icon_goods_tea.dds") < section.index("icon_goods_wheat.dds")   # best first
    assert 'raw_text = "#P +18%#!"' in section and 'raw_text = "#N -4%#!"' in section    # 0.1 vanilla - 0.14 fit
    assert "Localize('HA1300_FERTILITY_HIGH')" in gui and "Localize('HA1300_SOIL_LOAM_TITLE')" in gui
    assert "LocationView.GetLocation.IsCoastal" in gui and "Localize('HA1300_LAKESIDE')" in gui

    custom = (mod / tt.CUSTOM_LOC_PATH).read_text(encoding="utf-8-sig")
    assert "text = { localization_key = PP_TT_KEY_VEGETATION_FOREST trigger = { vegetation = forest } }" in custom
    assert "trigger = { climate = arid }" in custom and custom.count("fallback = yes") == 3

    loc = (mod / tt.LOCALIZATION_PATH).read_text(encoding="utf-8-sig")
    assert ' PP_TT_KEY_VEGETATION_FOREST: "forest"' in loc and ' PP_TT_GOODS_OUTPUT: "Goods Output"' in loc
    assert ' STATIC_MODIFIER_NAME_pp_tt_vegetation_forest: "$forest$"' in loc
    assert ' PP_TT_EXTRAS_VEGETATION_FOREST: "Movement Cost for [units|e]: #N +25%#!\\nAttacker Penalty in [combat|e]: #N +1#!"' in loc
    assert "PP_TT_EXTRAS_CLIMATE_ARID: \"[winter_level_max|e]: [ShowModifier('winter_mild')]\"" in loc


def test_goods_tables_wrap_into_rows_of_fixed_cells():
    goods = [(f"g{i}", 0.01 * i) for i in range(tt.CELLS_PER_ROW * 2 + 1)]
    table = tt.goods_table(goods)
    assert table.count("pp_goods_output_row") == 3 and table.count("pp_goods_output_cell") == len(goods)
    assert table.count("{") == table.count("}")


def test_location_window_chips_use_the_generated_tooltips():
    from prosper_or_perish_constructor.worldbuilder import geography as wb_geography

    gui = (
        "tooltipwidget = { using = Topography_tooltip }\ntooltipwidget = { using = Climate_tooltip }\n"
        "tooltipwidget = { using = Vegetation_tooltip }\ntooltipwidget = { using = RiverModifier_tooltip }\n"
        'blockoverride "tooltip_content" { TooltipFlavorTextBlock = { blockoverride "text" { text = "[LocationView.GetLocation.Custom(\'ha1300_fertility_desc\')]" } } }\n'
        'blockoverride "tooltip_content" { TooltipTextBlock = { blockoverride "text" { text = "HA1300_LAKE_HELP" } } }\n'
        'x textcontext = "[ShowModifierEffect(\'coastal\')]"\n    } }\n'
    )
    out = wb_geography.add_attribute_effect_rows(gui)
    for attribute in ("topography", "climate", "vegetation"):
        assert f"using = pp_attribute_tooltip_{attribute} }}" in out
    assert "using = RiverModifier_tooltip" in out   # rivers carry no goods rows
    assert "pp_attribute_view_fertility = {}" in out and "pp_attribute_view_lake = {}" in out and "pp_attribute_view_coast = {}" in out
    assert "ShowModifierEffect('pp_wb_" not in out and out.count("ShowModifierEffect('coastal')") == 1
    assert out.count("{") - out.count("}") == gui.count("{") - gui.count("}")
    with pytest.raises(ValueError, match="Vegetation_tooltip"):
        wb_geography.add_attribute_effect_rows(gui.replace("using = Vegetation_tooltip", "using = X"))
