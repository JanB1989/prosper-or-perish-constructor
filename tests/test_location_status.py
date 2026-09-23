"""Status chips at the top of the location view (stored food, land pressure, harvest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_status

MOD_ROOT = Path(__file__).resolve().parents[1] / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
HARVESTS = ["pp_harvest_x_abysmal", "pp_harvest_x_very_good", "pp_harvest_y_poor", "pp_harvest_y_bountiful"]


def _window() -> str:
    return "hbox = {\n\t\t\t\t\t\t\tbutton = {}\n\t\t\t\t\t\t\texpand = {}\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n\t\t\t\t\t# BOTTOM CONDITIONS\n"


def test_harvest_keys_and_trends_come_from_the_modifier_file():
    text = "pp_harvest_x_abysmal = {\n}\npp_harvest_x_very_good = {\n}\n# pp_harvest_z_good = {\npp_other = {\n}\n"
    assert location_status.harvest_modifiers(text) == ["pp_harvest_x_abysmal", "pp_harvest_x_very_good"]
    loc = location_status.custom_localization(HARVESTS)
    assert "localization_key = STATIC_MODIFIER_NAME_pp_harvest_y_poor trigger = { has_location_modifier = pp_harvest_y_poor }" in loc
    good = next(line for line in loc.splitlines() if "PP_HARVEST_TREND_GOOD" in line)
    assert "pp_harvest_x_very_good" in good and "pp_harvest_y_bountiful" in good and "poor" not in good and "abysmal" not in good
    assert loc.count("fallback = yes") == 2 and loc.count("{") == loc.count("}")


def test_status_row_sits_after_the_top_row_spacer_with_exclusive_states():
    out = location_status.add_status_row(_window(), HARVESTS)
    assert out.index("expand = {}") < out.index('name = "pp_location_status_row"') < out.index("# BOTTOM CONDITIONS")
    assert out.count("{") - out.count("}") == _window().count("{") - _window().count("}")
    names = re.findall(r'name = "(pp_status_\w+)"', out)
    assert names == ["pp_status_food_stored", "pp_status_food_starving", "pp_status_land_overpopulation", "pp_status_land_abundant",
                     "pp_status_land_available", "pp_status_land_settled", "pp_status_harvest_good", "pp_status_harvest_bad", "pp_status_harvest_average"]
    # each harvest row is gated on its own modifier's name, in the chip of its trend
    good = out[out.index('"pp_status_harvest_good"'):out.index('"pp_status_harvest_bad"')]
    assert "ShowModifierEffect('pp_harvest_x_very_good')" in good and "pp_harvest_x_abysmal" not in good
    assert "Localize('STATIC_MODIFIER_NAME_pp_harvest_y_bountiful')" in good
    for key in ("positive_province_food_growth", "province_starving", "overpopulation", "abundant_free_land", "available_free_land"):
        assert f"ShowModifierEffect('{key}')" in out
    with pytest.raises(ValueError, match="status chips"):
        location_status.add_status_row(_window() + _window(), HARVESTS)


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
    missing = sorted(key for key in used if f"\n  {key}:" not in loc)
    assert not missing
