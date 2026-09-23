"""Status chips at the top of the location view (stored food, land pressure, harvest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_status

MOD_ROOT = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
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
    for key in ("positive_province_food_growth", "province_starving", "overpopulation", "abundant_free_land", "available_free_land"):
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
    gui = location_status.status_row(HARVESTS)
    used = set(re.findall(r'"(PP_[A-Z_]+)"', gui)) | set(re.findall(r"Localize\('(PP_[A-Z_]+)'\)", gui))
    used |= set(re.findall(r"localization_key = (PP_[A-Z_]+)", location_status.custom_localization(HARVESTS)))
    loc += location_status.harvest_localization(HARVESTS)
    missing = sorted(key for key in used if f"\n  {key}:" not in loc)
    assert not missing
