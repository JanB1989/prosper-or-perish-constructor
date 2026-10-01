from pathlib import Path

from prosper_or_perish_constructor import gui_compat
from prosper_or_perish_constructor.food_storage_gui import (
    format_gui_fixed_point,
    load_food_storage_max_months,
)


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
FOOD_STORAGE_MAX_MONTHS = format_gui_fixed_point(
    load_food_storage_max_months(
        profile="constructor",
        load_order_path=ROOT / "constructor.load_order.toml",
    )
)
FOOD_STORAGE_DIVISOR = f"'(CFixedPoint){FOOD_STORAGE_MAX_MONTHS}'"
LOCATION_FOOD_TOOLTIP = (
    MOD_ROOT / "in_game" / "gui" / "shared" / "zz_pp_location_food_tooltip_absolute_sources.gui"
)
LOCATION_WINDOW = MOD_ROOT / "in_game" / "gui" / "location_window.gui"
PROVINCE_TOOLTIPS = MOD_ROOT / "in_game" / "gui" / "shared" / "province_tooltips.gui"
FOOD_STORAGE_LOCALIZATION = (
    MOD_ROOT
    / "main_menu"
    / "localization"
    / "english"
    / "pp_food_storage_l_english.yml"
)
ADDITIONAL_FOOD_INDICATOR_FILES = (
    ("attribute_columns/province.gui", 3, 3),
    ("food_production_lateralview.gui", 2, 2),
    ("location_production_lateralview.gui", 4, 4),
    ("selected_market_view.gui", 6, 2),
    ("town_rights.gui", 2, 2),
)


def test_location_food_tooltip_rows_add_up_to_food_production() -> None:
    """The engine's source list (Location.GetFoodSources) counts a building's food modifier for one level only and
    skips modifier-only buildings and RGO levels; the tooltip rebuilds the production rows from food_production."""
    assert LOCATION_FOOD_TOOLTIP.exists()
    text = LOCATION_FOOD_TOOLTIP.read_text(encoding="utf-8-sig")
    values = (MOD_ROOT / "in_game" / "common" / "script_values" / "pp_food_tooltip_values.txt").read_text(encoding="utf-8-sig")
    loc = (MOD_ROOT / "main_menu" / "localization" / "english" / "pp_food_tooltip_l_english.yml").read_text(encoding="utf-8-sig")

    assert "template location_food_tooltip" in text
    assert "[Location.GetFoodSources]" not in text
    for key in ("pp_food_tooltip_production", "pp_food_tooltip_subsistence", "pp_food_tooltip_modifiers"):
        assert f"ScriptValue('{key}')" in text or f"ScriptValue('{key}')" in loc
        assert f"{key} = {{" in values
    assert "value = food_production" in values
    assert "unemployed_pops_of_pop_type_in_location(pop_type:peasants)" in values
    assert "unemployed_pops_of_pop_type_in_location(pop_type:slaves)" in values
    assert "value = modifier:local_monthly_food" in values
    assert "Location.GetModifierValue('local_monthly_food')" in text
    assert "Location.GetFoodsOutputModifiers" in text
    assert "Location.GetFoodDecayInfo" in text
    for key in ("PP_FOOD_TOOLTIP_PRODUCTION_TITLE", "PP_FOOD_TOOLTIP_SUBSISTENCE", "PP_FOOD_TOOLTIP_MODIFIERS", "PP_FOOD_TOOLTIP_GOODS"):
        assert key in text and f" {key}:" in loc


def test_province_food_indicator_uses_stored_food_months() -> None:
    assert LOCATION_WINDOW.exists()

    text = LOCATION_WINDOW.read_text(encoding="utf-8-sig")
    location_months = (
        "FixedPointToFloat(Divide_CFixedPoint("
        "LocationView.GetLocation.MakeScope.ScriptValue("
        f"'pp_province_food_storage_months'), {FOOD_STORAGE_DIVISOR}))"
    )
    selection_months = (
        "FixedPointToFloat(Divide_CFixedPoint("
        "LocationViewSelectProvince.Parent.GetLocation.MakeScope.ScriptValue("
        f"'pp_province_food_storage_months'), {FOOD_STORAGE_DIVISOR}))"
    )

    assert f'value = "[{location_months}]"' in text
    assert f'value = "[Subtract_float(\'(float)1.0\', {location_months})]"' in text
    assert f'value = "[{selection_months}]"' in text
    assert f'value = "[Subtract_float(\'(float)1.0\', {selection_months})]"' in text
    assert "Province.GetFoodCapacityPercent" not in text


def test_province_tooltip_food_indicators_use_stored_food_months() -> None:
    assert PROVINCE_TOOLTIPS.exists()

    text = PROVINCE_TOOLTIPS.read_text(encoding="utf-8-sig")
    stored_months = (
        "FixedPointToFloat(Divide_CFixedPoint("
        "Province.GetCapital.MakeScope.ScriptValue("
        f"'pp_province_food_storage_months'), {FOOD_STORAGE_DIVISOR}))"
    )

    assert text.count(f'value = "[{stored_months}]"') == 2
    assert (
        text.count(f'value = "[Subtract_float(\'(float)1.0\', {stored_months})]"') == 2
    )
    assert "Province.GetFoodCapacityPercent" not in text


def _without_protected_copies(text: str) -> str:
    """The gauges are counted on the original types; gui_compat repeats them in pp_ copies."""
    for types in gui_compat.PROTECTED.values():
        for name in types:
            span = gui_compat._type_span(text, gui_compat.PREFIX + name)
            if span:
                text = text[: span[0]] + text[span[1]:]
    return text


def test_all_remaining_food_indicators_use_stored_food_months() -> None:
    gui_root = MOD_ROOT / "in_game" / "gui"

    for relative_path, expected_modifier_refs, expected_ratio_refs in (
        ADDITIONAL_FOOD_INDICATOR_FILES
    ):
        path = gui_root / relative_path
        assert path.exists()

        text = _without_protected_copies(path.read_text(encoding="utf-8-sig"))
        assert text.count("pp_province_food_storage_months") == expected_modifier_refs
        assert text.count(FOOD_STORAGE_DIVISOR) == expected_ratio_refs

    province_columns = (gui_root / "attribute_columns" / "province.gui").read_text(
        encoding="utf-8-sig"
    )
    assert (
        "Divide_CFixedPoint("
        "InteractionTarget.GetProvince.GetCapital.MakeScope.ScriptValue("
        f"'pp_province_food_storage_months'), {FOOD_STORAGE_DIVISOR})|2%"
    ) in province_columns

    stale_files = [
        path
        for path in gui_root.rglob("*.gui")
        if "GetFoodCapacityPercent" in path.read_text(encoding="utf-8-sig")
    ]
    assert stale_files == []

    # EU5 1.4 dropped the stored-food modifier: the months are a location-scope script value, never a modifier
    modifier_reads = [
        path
        for path in gui_root.rglob("*.gui")
        if "GetModifierValueFixed('pp_province_food_storage_months')" in path.read_text(encoding="utf-8-sig")
    ]
    assert modifier_reads == []


def test_food_storage_tooltip_uses_configured_maximum_months() -> None:
    assert FOOD_STORAGE_LOCALIZATION.exists()

    text = FOOD_STORAGE_LOCALIZATION.read_text(encoding="utf-8-sig")
    assert "EFFECTS_FROM_STORAGE" in text
    assert f"maximum of #Y {FOOD_STORAGE_MAX_MONTHS}#! Months" in text
    assert "maximum of #Y 120#! Months" not in text
