"""Status chips at the top of the location view (stored food, land pressure, harvest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_status, stored_food

MOD_ROOT = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
PROJECT = Path(__file__).resolve().parents[1] / "constructor.toml"
HARVESTS = location_status.Harvests(
    keys=["pp_harvest_x_abysmal", "pp_harvest_x_very_good", "pp_harvest_y_poor", "pp_harvest_y_bountiful"],
    regions={"western_europe": ["r1", "r2"], "pacific_islands": ["r3"]},
    names={"western_europe": "Region X"},
)


def _window() -> str:
    return "hbox = {\n\t\t\t\t\t\t\tbutton = {}\n\t\t\t\t\t\t\texpand = {}\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t\t# BOTTOM CONDITIONS\n"


def test_harvest_keys_regions_and_states_come_from_the_harvest_files():
    text = "pp_harvest_x_abysmal = {\n}\npp_harvest_x_very_good = {\n}\n# pp_harvest_z_good = {\npp_other = {\n}\n"
    assert location_status.harvest_modifiers(text) == ["pp_harvest_x_abysmal", "pp_harvest_x_very_good"]
    effects = (
        "region:r1 = {\n\t\tpp_roll_region_harvest_for_good_shock = { subcontinent = x }\n\t}\n"
        "region:r1 = {\n\t\tpp_roll_region_harvest_for_bad_shock = { subcontinent = x }\n\t}\n"
        "region:r3 = {\n\t\tpp_roll_region_harvest_for_good_shock = { subcontinent = y }\n\t}\n"
    )
    assert location_status.harvest_regions(effects) == {"x": ["r1"], "y": ["r3"]}
    names = '  STATIC_MODIFIER_NAME_pp_harvest_south_east_asia_abysmal: "Failed Harvest: South East Asia"\n'
    assert location_status.harvest_region_names(names) == {"south_east_asia": "South East Asia"}
    assert [location_status.severity(k) for k in HARVESTS.keys] == ["abysmal", "very_good", "poor", "bountiful"]

    loc = location_status.custom_localization(HARVESTS)
    assert "localization_key = STATIC_MODIFIER_NAME_pp_harvest_y_poor trigger = { has_location_modifier = pp_harvest_y_poor }" in loc
    good = next(line for line in loc.splitlines() if "PP_HARVEST_TREND_GOOD" in line)
    assert "pp_harvest_x_very_good" in good and "pp_harvest_y_bountiful" in good and "poor" not in good and "abysmal" not in good
    # average years still name the region; the crop follows region membership, not the modifier
    assert "localization_key = PP_HARVEST_AVERAGE_WESTERN_EUROPE trigger = { OR = { region ?= region:r1 region ?= region:r2 } }" in loc
    assert "localization_key = PP_HARVEST_REGION_PACIFIC_ISLANDS trigger = { OR = { region ?= region:r3 } }" in loc
    assert "localization_key = PP_HARVEST_SEVERITY_VERY_GOOD trigger = { OR = { has_location_modifier = pp_harvest_x_very_good } }" in loc
    assert loc.count("fallback = yes") == 4 and loc.count("{") == loc.count("}")
    generated = location_status.harvest_localization(HARVESTS)
    assert 'PP_HARVEST_AVERAGE_WESTERN_EUROPE: "Average Harvest: Region X"' in generated
    assert 'PP_HARVEST_REGION_PACIFIC_ISLANDS: "Pacific Islands"' in generated   # fallback name when the loc has none


def test_harvest_chip_layers_crop_in_a_severity_frame_with_a_signed_badge():
    chip = location_status.harvest_chip(HARVESTS)
    assert chip.count("{") == chip.count("}")
    # crop per region (twice: chip and title icon), wheat outside every region
    assert chip.count("icon_goods_wine.dds") == 2 and chip.count("icon_goods_fish.dds") == 2
    assert chip.count("PP_HARVEST_REGION_WESTERN_EUROPE')") == 2
    assert chip.count("icon_goods_wheat.dds") == 2 and chip.count("PP_HARVEST_REGION_NONE')") == 2
    # round frames only: the neutral brown one under a recoloured one per severity, no square tints or climate frame
    assert chip.count("climate/brown_frame.dds") == 2 and "GetClimateFrame" not in chip and "gfx/interface/colors/" not in chip
    for sev in location_status.SEVERITY_COLOURS:
        assert chip.count(f"pp_harvest/frame_{sev}.dds") == 2
    # one badge per severity, in the stored-food chip's number box
    assert chip.count("using = bg_number_container_bckg") == 6
    assert 'raw_text = "#R -3#!"' in chip and 'raw_text = "#G +2#!"' in chip
    badge = next(line for line in chip.splitlines() if "#R -3#!" in line)
    assert "PP_HARVEST_SEVERITY_ABYSMAL" in badge and "position = { 13 18 }" in badge
    assert "pp_attribute_view_harvest = {}" in chip and "TooltipScrolledContentSection" in chip
    assert "pp_attribute_view_harvest" not in location_status.harvest_chip(location_status.Harvests(keys=[], regions={}, names={}))


def test_harvest_frames_ship_with_the_mod():
    for sev in location_status.SEVERITY_COLOURS:
        assert (MOD_ROOT / "in_game" / location_status.HARVEST_FRAMES.format(severity=sev)).is_file()


def test_status_row_sits_after_the_top_row_spacer_with_exclusive_states():
    out = location_status.add_status_row(_window(), HARVESTS)
    assert out.index("expand = {}") < out.index('name = "pp_location_status_row"') < out.index("# BOTTOM CONDITIONS")
    assert out.count("{") - out.count("}") == _window().count("{") - _window().count("}")
    # outside the button row's hbox, pinned to the top-right corner (mirrors the bottom-left geography card)
    assert "expand = {}\n\t\t\t\t\t\t}\n\t\t\t\t\t\t# PP STATUS CHIPS" in out and "parentanchor = right|top" in out
    names = re.findall(r'name = "(pp_status_\w+)"', out)
    assert names == ["pp_status_food_stored", "pp_status_food_starving", "pp_status_land_overpopulation", "pp_status_land_abundant",
                     "pp_status_land_available", "pp_status_land_settled", "pp_status_harvest"]
    # each harvest view is gated on its own modifier's name
    assert location_status.harvest_gate("pp_harvest_y_bountiful") == "EqualTo_string(LocationView.GetLocation.Custom('pp_harvest_state'), Localize('STATIC_MODIFIER_NAME_pp_harvest_y_bountiful'))"
    assert "positive_province_food_growth" not in out   # EU5 1.4: no stored-food modifier, the chip reads script values
    assert "ScriptValue('pp_province_food_storage_months')" in out
    for key in ("province_starving", "overpopulation", "abundant_free_land", "available_free_land"):
        assert f"ShowModifierEffect('{key}')" in out
    with pytest.raises(ValueError, match="status chips"):
        location_status.add_status_row(_window() + _window(), HARVESTS)


def test_land_rows_show_scaled_values_largest_first_in_a_scroll_area():
    pressure = (
        "TRY_REPLACE:overpopulation = {\n\tgame_data = {\n\t\tcategory = location\n\t}\n\tpp_land_overpopulation = 1\n"
        "\tcap_maximum_population_growth_at_zero = no\n\tlocal_migration_attraction = -0.25\n\tlocal_peasants_food_consumption = 0.5 # note\n"
        "\t# local_population_growth = -0.0015\n\tlocal_population_growth = 0\n}\n"
        "TRY_REPLACE:abundant_free_land = {\n\tlocal_migration_attraction = 2\n\tlocal_wheat_output_modifier = 0.40\n"
        "\tlocal_rice_output_modifier = 0.40\n\tlocal_fish_output_modifier = 0.40\n}\n"
        "TRY_REPLACE:available_free_land = {\n\tlocal_migration_attraction = 1\n}\n"
    )
    types = location_status.modifier_types([
        "local_migration_attraction={\n\tgame_data={\n\t\tcategory=location\n\t}\n}\n"
        "local_peasants_food_consumption={\n\tcolor=bad\n\tpercent=yes\n}\nlocal_wheat_output_modifier={\n\tpercent=yes\n}\n"
        "local_rice_output_modifier={\n\tpercent=yes\n}\nlocal_fish_output_modifier={\n\tpercent=yes\n}\n"
    ])
    rows = location_status.land_effect_rows(pressure, types)
    over = rows["overpopulation"]
    assert over.startswith("TooltipScrolledContentSection = {") and "maximumsize = { -1 420 }" in over
    assert over.count("{") == over.count("}")
    # zeros, "no" flags, comments and the marker are dropped; the food line (50 points) comes before migration (0.25)
    assert "cap_maximum" not in over and "local_population_growth" not in over and "ShowModifierTypeName('pp_land_" not in over
    assert over.index("local_peasants_food_consumption") < over.index("local_migration_attraction")
    assert "Multiply_CFixedPoint(LocationView.GetLocation.GetModifierValueFixed('pp_land_overpopulation'), '(CFixedPoint)0.5')|1%-]" in over
    assert "'(CFixedPoint)-0.25')|2+]" in over
    # three goods outputs with one value collapse into one line, and 40 points outrank a flat 2
    abundant = rows["abundant_free_land"]
    assert abundant.count("PP_LAND_CHIP_GOODS_OUTPUT") == 1 and "local_rice_output_modifier" not in abundant
    assert abundant.index("PP_LAND_CHIP_GOODS_OUTPUT") < abundant.index("local_migration_attraction")
    # ... with the affected goods as icons under it, in file order
    icons = re.findall(r"trade_goods/icon_goods_(\w+)\.dds", abundant)
    assert icons == ["wheat", "rice", "fish"] and "[ShowGoodsName('rice')]" in abundant and abundant.count("{") == abundant.count("}")
    out = location_status.status_row(HARVESTS, rows)
    assert out.count("TooltipScrolledContentSection") == 4 and "ShowModifierEffect('overpopulation')" not in out


def test_mod_files_carry_the_markers_types_and_localization():
    pressure = (MOD_ROOT / "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt").read_text(encoding="utf-8-sig")
    types = (MOD_ROOT / "main_menu/common/modifier_type_definitions/pp_location_status_modifier_types.txt").read_text(encoding="utf-8-sig")
    loc = (MOD_ROOT / "main_menu/localization/english/pp_location_status_l_english.yml").read_text(encoding="utf-8-sig")
    for name, marker in (("abundant_free_land", "pp_land_abundant"), ("available_free_land", "pp_land_available"), ("overpopulation", "pp_land_overpopulation")):
        block = pressure[pressure.index(f"TRY_REPLACE:{name} = {{"):]
        block = block[:block.index("\n}\n")]
        assert f"\t{marker} = 1\n" in block
        assert f"\n{marker}={{" in types and f"MODIFIER_TYPE_NAME_{marker}:" in loc
    gui = location_status.status_row(HARVESTS, stored_rows=location_status.load_stored_food_rows(MOD_ROOT, None, stored_food.load_config(PROJECT).per_year))
    used = set(re.findall(r'"(PP_[A-Z_]+)"', gui)) | set(re.findall(r"Localize\('(PP_[A-Z_]+)'\)", gui))
    used |= set(re.findall(r"localization_key = (PP_[A-Z_]+)", location_status.custom_localization(HARVESTS)))
    loc += location_status.harvest_localization(HARVESTS)
    loc += (MOD_ROOT / stored_food.LOCALIZATION).read_text(encoding="utf-8-sig")
    missing = sorted(key for key in used if f"\n  {key}:" not in loc)
    assert not missing


def test_stored_food_chip_shows_the_province_step_modifier():
    # 2026-10-03 (Jan): one Stored Food modifier per province at a time, so the chip shows that modifier itself: one
    # ShowModifierEffect block per step, visible only on the step the province carries, and a plain line without one
    per_year = stored_food.load_config(PROJECT).per_year
    rows = location_status.load_stored_food_rows(MOD_ROOT, None, per_year)
    out = location_status.add_status_row(_window(), HARVESTS, stored_rows=rows)
    chip = out[out.index('name = "pp_status_food_stored"'):out.index('name = "pp_status_food_starving"')]
    step = "LocationView.GetLocation.MakeScope.ScriptValue('pp_stored_food_step')"
    assert location_status.stored_food_step() == step
    assert chip.index('text = "PP_FOOD_CHIP_STORED"') < chip.index("ShowModifierEffect(")
    for s in range(stored_food.STEPS + 1):
        name = stored_food.step_name(s)
        assert chip.count(f"ShowModifierEffect('{name}')") == 1
        assert (f"And(GreaterThan_CFixedPoint({step}, '(CFixedPoint){s - 0.5}'), "
                f"Not(GreaterThan_CFixedPoint({step}, '(CFixedPoint){s + 0.5}')))") in chip
    assert chip.count("ShowModifierEffect(") == stored_food.STEPS + 1
    assert f"Not(GreaterThan_CFixedPoint({step}, '(CFixedPoint)-0.5'))" in chip and '"PP_FOOD_CHIP_NO_TIER"' in chip
    assert "ShowModifierTypeName(" not in chip   # no lines rebuilt from the config
    # the step value reads the carried step variable: -1 without one, the step itself otherwise
    values = stored_food.render_script_values(stored_food.load_config(PROJECT))
    block = values[values.index("pp_stored_food_step = {"):]
    block = block[:block.index("\n}\n")]
    assert "value = -1" in block and "add = var:pp_food_store_step" in block and "subtract = 99" in block
    # the months badge reads the fixed script value; the tooltip shows a decimal
    assert "ScriptValue('pp_province_food_storage_months')|0]" in chip
    loc = (MOD_ROOT / "main_menu/localization/english/pp_location_status_l_english.yml").read_text(encoding="utf-8-sig")
    stored = next(line for line in loc.splitlines() if line.startswith("  PP_FOOD_CHIP_STORED:"))
    assert "ScriptValue('pp_province_food_storage_months')|1]" in stored
    assert not re.search(r"\d", stored.split(":", 1)[1].replace("|1]", "]"))   # no balance numbers
    assert "\n  PP_FOOD_CHIP_NO_TIER:" in loc
    # the deployed location view carries the same rows (generated by the geography sync)
    window = (MOD_ROOT / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    assert window.count("ShowModifierEffect('pp_food_store_") == stored_food.STEPS + 1
    assert "pp_stored_food_tier" not in window and "pp_stored_food_low_years" not in window


def test_province_modifier_list_shows_the_stored_food_step():
    # 2026-10-03: one Stored Food step modifier with its true values; the list shows it like any province modifier
    window = (MOD_ROOT / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    assert "STATIC_MODIFIER_NAME_pp_stored_food" not in window
    assert "ScriptValue('pp_stored_food_years'), '(CFixedPoint)0'), '(int32)1', '(int32)0'))" not in window
    assert not hasattr(location_status, "hide_stored_food_modifier")


def test_condition_icons_sit_at_the_top_left_of_the_scene():
    # 2026-10-03 (Jan): the bottom row is full with the geography chips, so vanilla's condition icons (winter, disease,
    # location and province modifiers, Stored Food among them) ran past the window's edge; they get their own top-left row
    from prosper_or_perish_constructor.worldbuilder import geography

    scene = (
        "\t\t\t\tvbox = {\n\t\t\t\t\texpand = {}\n\t\t\t\t\t# IOs & PERIPHORA\n\t\t\t\t\twidget = {}\n"
        "\t\t\t\t\t# BOTTOM CONDITIONS\n\t\t\t\t\thbox = {\n\t\t\t\t\t\thbox = { widget = { name = \"chip\" } }\n"
        "\t\t\t\t\t\twidget = {\n\t\t\t\t\t\t\tusing = layoutpolicy_expanding\n\t\t\t\t\t\t\thbox = {\n"
        "\t\t\t\t\t\t\t\t# SOUND TOLL\n\t\t\t\t\t\t\t\ticon = { name = \"toll\" }\n"
        "\t\t\t\t\t\t\t\t# Province timed modifiers\n\t\t\t\t\t\t\t\twidget = { name = \"province\" }\n"
        "\t\t\t\t\t\t\t\texpand = {}\n\t\t\t\t\t\t\t}\n\t\t\t\t\t\t}\n\t\t\t\t\t\texpand = {}\n\t\t\t\t\t}\n"
        "\t\t\t\t}\n\t\t\t\twidget = { name = \"queue\" parentanchor = top|right }\n"
    )
    out = geography.move_modifier_row(scene)
    assert out.count("{") == out.count("}") and out.count("# SOUND TOLL") == 1
    bottom = out[out.index("# BOTTOM CONDITIONS"):out.index(f'name = "{geography.MODIFIER_ROW}"')]
    assert 'name = "chip"' in bottom and "SOUND TOLL" not in bottom and "layoutpolicy_expanding" not in bottom
    # a sibling of the scene's row stack, before the queue buttons, pinned top left
    row = out[out.index(f'name = "{geography.MODIFIER_ROW}"'):out.index('name = "queue"')]
    assert "parentanchor = top|left" in row and 'name = "province"' in row
    assert "size = { 100% 40 }" in row   # the band spans the scene (in game a fixed 460 px left a step of bright sky)
    assert "\t\t\t\t}\n\t\t\t\t# PP: the condition icons" in out
    with pytest.raises(ValueError, match="modifier row"):
        geography.move_modifier_row(scene + scene)

    # the shipped window: the icons left the bottom row and the queue buttons keep the top-right corner
    window = (MOD_ROOT / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    assert window.count(f'name = "{geography.MODIFIER_ROW}"') == 1


def test_every_location_and_province_modifier_gets_its_own_icon():
    # 2026-10-05 (Jan): vanilla folds two or more modifiers into a count; the top-left row has room for every icon
    from prosper_or_perish_constructor.worldbuilder import geography

    def vanilla(model: str, concept: str) -> str:
        return (f'widget = {{\n\tsize = {{ 45 26 }}\n\tvisible = "[GreaterThan_int32(GetDataModelSize({model}), \'(int32)0\')]"\n'
                f'\tflowcontainer = {{ datamodel = "[{model}]" item = {{ timed_modifier_icon = {{ text = "[{concept}|e]" }} }} }}\n'
                f'\tflowcontainer = {{ text_single = {{ text = "[GetDataModelSize({model})]" }} }}\n}}\n')

    loc, prov = "LocationView.GetLocation.GetTimedModifiers", "LocationView.GetLocation.GetProvince.GetTimedModifiers"
    row = ("hbox = {\n\t# Location timed modifiers\n\t" + vanilla(loc, "location_modifier").replace("\n", "\n\t")
           + "# Province timed modifiers\n\t" + vanilla(prov, "province_modifier").replace("\n", "\n\t") + "expand = {}\n}\n")
    out = geography.show_every_timed_modifier(row)
    assert out.count("{") == out.count("}") and "GetDataModelSize" not in out
    for model, concept in ((loc, "location_modifier"), (prov, "province_modifier")):
        assert f'visible = "[DataModelHasItems({model})]"\n\t\tdatamodel = "[{model}]"' in out
        assert f'text = "[{concept}|e]"' in out
    with pytest.raises(ValueError, match="Location timed modifiers"):
        geography.show_every_timed_modifier(row + row)

    window = (MOD_ROOT / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    top = window[window.index(f'name = "{geography.MODIFIER_ROW}"'):]
    for model in (loc, prov):
        assert f"DataModelHasItems({model})" in top and f"GetDataModelSize({model})" not in window
    row_at = window.index(f'name = "{geography.MODIFIER_ROW}"')
    assert window.index("# BOTTOM CONDITIONS") < row_at < window.index("# SOUND TOLL") < window.index("# Province timed modifiers")
    assert window.index("# Province timed modifiers") < window.index("size = { 62 220 }")
