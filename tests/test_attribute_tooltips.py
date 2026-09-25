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

template location_winter_tooltip {
    ContextualTooltipType = {
        blockoverride "title_text" { text = "[Location.GetWinterName]" }
        blockoverride "tooltip_content" {

            TooltipStringPairList = {
                textcontext = "[Location.GetWinterDetails]"
            }

			TooltipContentSection = {
				using = tooltip_location_alt_content
			}
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
    _write(game / "main_menu/common/static_modifiers/location.txt", (
        "river_flowing_through_1 = {\n\tlocal_supply_limit_modifier = 0.05\n}\n"
        "winter_normal = {\n\tgame_data = { category = location }\n\tlocal_construction_speed = -0.5\n}\n"
    ))
    # winter and harvest lines live in the in_game folder, which loads after main_menu's
    _write(mod / "in_game/common/static_modifiers/pp_food.txt", (
        "TRY_INJECT:winter_normal = {\n\tlocal_wheat_output_modifier = -0.25\n\tlocal_tea_output_modifier = -0.35\n\tlocal_lumber_output_modifier = -0.35\n}\n"
    ))
    _write(mod / "in_game/common/static_modifiers/pp_variable_harvest_modifiers.txt", (
        "pp_harvest_x_poor = {\n\tgame_data = { category = location }\n\tlocal_peasants_food_consumption = 0.1\n"
        "\tlocal_wheat_output_modifier = -0.2\n\tlocal_tea_output_modifier = -0.2\n\tlocal_lumber_output_modifier = -0.2\n}\n"
    ))
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
    # no location files in the fixture: every step and both unsuited lines stay possible
    cells = 3 * (len(range(tt.STEP_MAX, -11, -1)) + len(tt.LOW_LINES))
    assert counts == {"climate": 0, "vegetation": 2, "topography": 0, "fertility": 1, "soil": 1, "coast": 1, "lake": 0, "winter": 1, "harvest": 1, "land_potential_cells": cells}

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
    section = section[:section.index("DataModelRepeatedItem")]   # up to the next value's lazily built section
    assert "ShowModifierEffect('pp_tt_vegetation_forest')" in section and "PP_TT_EXTRAS_VEGETATION_FOREST" in section
    assert section.index("icon_goods_tea.dds") < section.index("icon_goods_wheat.dds")   # best first
    assert 'raw_text = "#P +18%#!"' in section and 'raw_text = "#N -4%#!"' in section    # 0.1 vanilla - 0.14 fit
    assert "Localize('HA1300_FERTILITY_HIGH')" in gui and "Localize('HA1300_SOIL_LOAM_TITLE')" in gui
    assert "LocationView.GetLocation.IsCoastal" in gui and "Localize('HA1300_LAKESIDE')" in gui

    custom = (mod / tt.CUSTOM_LOC_PATH).read_text(encoding="utf-8-sig")
    assert "text = { localization_key = PP_TT_KEY_VEGETATION_FOREST trigger = { vegetation = forest } }" in custom
    assert "trigger = { climate = arid }" in custom and custom.count("fallback = yes") == 4
    assert "text = { localization_key = PP_TT_KEY_WINTER_NORMAL trigger = { winter_level = normal } }" in custom

    loc = (mod / tt.LOCALIZATION_PATH).read_text(encoding="utf-8-sig")
    assert ' PP_TT_KEY_VEGETATION_FOREST: "forest"' in loc and ' PP_TT_GOODS_OUTPUT: "Goods Output"' in loc
    assert ' STATIC_MODIFIER_NAME_pp_tt_vegetation_forest: "$forest$"' in loc
    assert ' PP_TT_EXTRAS_VEGETATION_FOREST: "Movement Cost for [units|e]: #N +25%#!\\nAttacker Penalty in [combat|e]: #N +1#!"' in loc
    assert "PP_TT_EXTRAS_CLIMATE_ARID: \"[winter_level_max|e]: [ShowModifier('winter_mild')]\"" in loc


def test_winter_and_harvest_views_come_from_both_static_modifier_folders(trees):
    vanilla, mod = trees
    tt.write(mod, vanilla)
    modifiers = (mod / tt.MODIFIERS_PATH).read_text(encoding="utf-8-sig")
    assert "pp_tt_winter_normal = {\n\tgame_data = { category = location }\n\tlocal_construction_speed = -0.5\n}" in modifiers
    assert "pp_tt_harvest_x_poor = {\n\tgame_data = { category = location }\n\tlocal_peasants_food_consumption = 0.1\n}" in modifiers
    gui = (mod / tt.GUI_PATH).read_text(encoding="utf-8-sig")
    winter = gui[gui.index("template pp_attribute_tooltip_winter {"):]
    winter = winter[:winter.index("\ntypes ")]
    assert "pp_attribute_view_winter = {}" in winter and "using = tooltip_location_alt_content" in winter
    assert "Custom('pp_tt_winter'), Localize('PP_TT_KEY_NONE'))]\"\n                textcontext = \"[Location.GetWinterDetails]\"" in winter
    harvest = gui[gui.index("type pp_attribute_view_harvest"):]
    # built only in its region, then only at its severity
    region = harvest.index("Select_int32(EqualTo_string(LocationView.GetLocation.Custom('pp_harvest_region'), Localize('PP_HARVEST_REGION_X'))")
    severity = harvest.index("Select_int32(EqualTo_string(LocationView.GetLocation.Custom('pp_harvest_severity'), Localize('PP_HARVEST_SEVERITY_POOR'))")
    assert region < severity < harvest.index("ShowModifierEffect('pp_tt_harvest_x_poor')")
    assert "pp_harvest_state" not in harvest and "visible =" not in harvest
    # the goods share -20%: one row with their icons
    assert 'pp_goods_output_group_row = { blockoverride "group_value" { raw_text = "#N -20%#!" }' in harvest


def test_goods_tables_use_cells_for_own_values_and_rows_for_shared_ones():
    goods = [(f"g{i}", 0.01 * i) for i in range(tt.CELLS_PER_ROW * 2 + 1)]
    table = tt.goods_table(goods)
    assert table.count("pp_goods_output_row") == 3 and table.count("pp_goods_output_cell") == len(goods)
    assert table.count("{") == table.count("}")
    shared = [(f"g{i}", -0.35) for i in range(tt.ICONS_PER_GROUP_ROW + 1)] + [("h", -0.5), ("k", -0.5)]
    table = tt.goods_table(shared)
    assert table.count("pp_goods_output_group_row") == 3 and table.count("icon_goods_") == len(shared)
    assert table.count('raw_text = "#N -35%#!"') == 1 and table.count('raw_text = ""') == 1   # value once per group


def test_land_potential_sums_the_land_attributes(trees):
    vanilla, mod = trees
    tt.write(mod, vanilla)
    values = (mod / tt.SCRIPT_VALUES_PATH).read_text(encoding="utf-8-sig")
    wheat = values[values.index("pp_land_potential_wheat = {"):]
    wheat = wheat[:wheat.index("\n}\n")]
    assert "if = { limit = { vegetation = forest } add = -0.04 }" in wheat
    assert "if = { limit = { has_location_modifier = pp_wb_fertility_high } add = 0.03 }" in wheat
    assert "winter" not in wheat and "harvest" not in wheat   # transient: not land
    lumber = values[values.index("pp_land_potential_lumber = {"):]
    assert "if = { limit = { vegetation = sparse } add = -0.03 }" in lumber and "if = { limit = { has_location_modifier = pp_wb_coastal } add = 0.07 }" in lumber
    assert ("pp_land_potential_step_tea = {\n\tvalue = pp_land_potential_tea\n\tmultiply = 100\n\tround = yes\n"
            "\tdivide = 2\n\tfloor = yes\n\tmin = -11\n\tmax = 20\n}") in values
    assert "pp_land_potential_low_tea = {\n\tvalue = pp_land_potential_tea\n\tmultiply = 100\n\tround = yes\n\tdivide = 5\n\tfloor = yes\n\tmin = -8\n\tmax = -4\n}" in values


def test_land_potential_script_tests_the_most_common_class_first(trees):
    vanilla, mod = trees
    views = tt.build_views(vanilla, mod)
    many_sparse = [{"climate": "arid", "vegetation": "sparse"}] * 3 + [{"climate": "arid", "vegetation": "forest"}]
    values = tt.render_script_values(views, many_sparse)
    tea = values[values.index("pp_land_potential_wheat = {"):]
    assert tea.index("vegetation = forest") > 0   # forest carries wheat; sparse does not, so forest opens the chain
    both = tt.render_script_values({"vegetation": [
        tt.View("vegetation", "a", "", "", {}, [("wheat", 0.1)], trigger="vegetation = a"),
        tt.View("vegetation", "b", "", "", {}, [("wheat", 0.2)], trigger="vegetation = b"),
    ]}, [{"vegetation": "b"}, {"vegetation": "b"}, {"vegetation": "a"}])
    assert both.index("if = { limit = { vegetation = b } add = 0.2 }") < both.index("else_if = { limit = { vegetation = a } add = 0.1 }")


def test_land_potential_tiers_sort_by_step_and_only_hold_steps_that_occur():
    views = {
        "climate": [tt.View("climate", "arid", "", "", {}, [("tea", 0.22), ("wheat", -0.05)], trigger="climate = arid")],
        "vegetation": [tt.View("vegetation", "forest", "", "", {}, [("tea", 0.02), ("wheat", -0.3)], trigger="vegetation = forest")],
    }
    locations = [{"climate": "arid"}, {"climate": "arid", "vegetation": "forest"}]
    occupied = tt.occupied_percents(views, locations)
    assert occupied == {"tea": {22, 24}, "wheat": {-5, -35}}
    assert tt.land_step(-5) == -3 and tt.land_step(-35) == tt.STEP_MIN and tt.land_step(80) == tt.STEP_MAX
    assert [tt.land_low(p) for p in (-20, -21, -25, -26, -35, -36, -90)] == [-4, -5, -5, -6, -7, -8, -8]
    assert tt.tier_steps(tt.TIERS[0]) == list(range(20, 9, -1)) and tt.tier_steps(tt.TIERS[-1]) == []
    assert tt.tier_cells(tt.TIERS[-1], occupied) == [[], [], [("wheat", -7)], []]
    assert [tt.tier_label(t) for t in (tt.TIERS[0], tt.TIERS[2], tt.TIERS[-1])] == ["Excellent: +20% or more", "Fair: 0% to +9%", "Unsuited: -21% or less"]
    chip = tt.land_potential_chip(occupied)
    assert chip.count("{") == chip.count("}")
    assert chip.count("pp_land_potential_cell = {") == 4   # one per occurring pair
    # best step first inside the tier; every tier labelled; the unsuited tier in 5% lines, with values
    assert chip.index("pp_land_potential_step_tea')), '(int32)12')") < chip.index("pp_land_potential_step_tea')), '(int32)11')")
    assert all(f'text = "PP_LAND_TIER_{t.key.upper()}"' in chip for t in tt.TIERS)
    unsuited = chip[chip.index("PP_LAND_TIER_UNSUITED"):]
    # only lines that can hold a good get a row
    assert unsuited.count("hbox = {") == 1 and "ScriptValue('pp_land_potential_low_wheat')), '(int32)-7')" in unsuited
    assert "raw_text = \"[LocationView.GetLocation.MakeScope.ScriptValue('pp_land_potential_wheat')|+=%0]\"" in unsuited
    # a long unsuited line continues on rows of at most ROW_CELLS cells, in the same order
    crowded = {f"g{i:02}": {-22} for i in range(tt.ROW_CELLS + 2)}
    rows = tt.land_tier(tt.TIERS[-1], crowded).split("hbox = {")[1:]
    assert [row.count("pp_land_potential_cell") for row in rows] == [tt.ROW_CELLS, 2]
    assert "'pp_land_potential_low_g06'" in rows[0] and "'pp_land_potential_low_g07'" in rows[1]
    assert "EqualTo_string(LocationView.GetLocation.GetRawMaterial.GetKey, 'wheat')" in chip
    # without location data every value stays possible
    assert tt.occupied_percents(views, [])["tea"] == set(range(-100, 101))


def test_land_potential_chip_uses_its_own_icon_which_ships_with_the_mod():
    chip = tt.land_potential_chip({})
    assert chip.count(f'texture = "{tt.LAND_POTENTIAL_ICON}"') == 2   # chip and tooltip title
    mod = Path(__file__).resolve().parents[1] / "mod/Prosper or Perish (Population Growth & Food Rework)"
    assert (mod / "main_menu" / tt.LAND_POTENTIAL_ICON).is_file()


def test_location_attributes_come_from_the_templates_and_the_setup(tmp_path):
    (tmp_path / tt.LOCATION_TEMPLATES).parent.mkdir(parents=True)
    (tmp_path / tt.LOCATION_TEMPLATES).write_text("paris = { topography = flatland vegetation = farmland climate = oceanic religion = catholic }\nsea_x = { topography = ocean }\n", encoding="utf-8")
    (tmp_path / tt.SETUP_MODIFIERS).parent.mkdir(parents=True)
    (tmp_path / tt.SETUP_MODIFIERS).write_text(
        'locations = {\n\tparis = {\n\t\ttimed_modifiers = {\n\t\t\ttimed_modifiers = {\n'
        '\t\t\t\t{ modifier = "pp_wb_fertility_high" start_date = 1111.1.1 date = 9999.1.1 size = 1 }\n'
        '\t\t\t\t{ modifier = "pp_wb_soil_loam" start_date = 1111.1.1 date = 9999.1.1 size = 1 }\n'
        '\t\t\t\t{ modifier = "pp_wb_coastal" start_date = 1111.1.1 date = 9999.1.1 size = 1 }\n'
        '\t\t\t}\n\t\t}\n\t}\n}\n', encoding="utf-8")
    assert tt.location_attributes(tmp_path) == [{"topography": "flatland", "vegetation": "farmland", "climate": "oceanic", "fertility": "high", "soil": "loam", "coast": "coastal"}]


def test_location_window_chips_use_the_generated_tooltips():
    from prosper_or_perish_constructor.worldbuilder import geography as wb_geography

    gui = (
        "tooltipwidget = { using = Topography_tooltip }\ntooltipwidget = { using = Climate_tooltip }\n"
        "tooltipwidget = { using = Vegetation_tooltip }\ntooltipwidget = { using = RiverModifier_tooltip }\n"
        "tooltipwidget = {\n\tusing = location_winter_tooltip\n}\n"
        'blockoverride "tooltip_content" { TooltipFlavorTextBlock = { blockoverride "text" { text = "[LocationView.GetLocation.Custom(\'ha1300_fertility_desc\')]" } } }\n'
        'blockoverride "tooltip_content" { TooltipTextBlock = { blockoverride "text" { text = "HA1300_LAKE_HELP" } } }\n'
        'x textcontext = "[ShowModifierEffect(\'coastal\')]"\n    } }\n'
    )
    out = wb_geography.add_attribute_effect_rows(gui)
    for attribute in ("topography", "climate", "vegetation"):
        assert f"using = pp_attribute_tooltip_{attribute} }}" in out
    assert "using = pp_attribute_tooltip_winter\n" in out
    assert "using = RiverModifier_tooltip" in out   # rivers carry no goods rows
    assert "pp_attribute_view_fertility = {}" in out and "pp_attribute_view_lake = {}" in out and "pp_attribute_view_coast = {}" in out
    assert "ShowModifierEffect('pp_wb_" not in out and out.count("ShowModifierEffect('coastal')") == 1
    assert out.count("{") - out.count("}") == gui.count("{") - gui.count("}")
    with pytest.raises(ValueError, match="Vegetation_tooltip"):
        wb_geography.add_attribute_effect_rows(gui.replace("using = Vegetation_tooltip", "using = X"))
    chips = wb_geography.add_land_potential_chip("widget = {}\n### IS BLOCKADED by ice\n")
    assert chips == "widget = {}\npp_land_potential_chip = {}\n### IS BLOCKADED by ice\n"
