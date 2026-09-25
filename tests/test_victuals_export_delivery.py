from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def _read(relative: str) -> str:
    return (MOD_ROOT / relative).read_text(encoding="utf-8-sig")


def test_export_market_counts_its_victuals_in_the_tally_good() -> None:
    """A negative input never adds goods to a market, so the export also demands 1 tally per level:
    the tally's market demand is the export volume the monthly delivery reads."""
    building = _read("in_game/common/building_types/zz_pp_victuals_market.txt")
    method = re.search(r"pp_province_food_to_market = \{(.*?)\}", building, re.S)
    assert method, "export method missing"
    body = method.group(1)
    victuals = float(re.search(r"victuals = (-?[0-9.]+)", body).group(1))
    tally = float(re.search(r"export_tally = ([0-9.]+)", body).group(1))
    assert victuals == -3.0
    assert tally == 1.0

    values = _read("in_game/common/script_values/pp_victuals_export_delivery_values.txt")
    assert '"goods_demand_in_market(goods:export_tally)"' in values
    per_tally = float(re.search(r"pp_victuals_export_victuals_per_tally = ([0-9.]+)", values).group(1))
    assert per_tally * tally == -victuals


def test_monthly_pulse_delivers_export_victuals() -> None:
    effect = _read("in_game/common/scripted_effects/pp_victuals_export_delivery.txt")
    assert "every_market_in_world" in effect
    assert "goods = goods:victuals" in effect
    assert "amount = pp_victuals_export_delivery_amount" in effect

    on_action = _read("in_game/common/on_action/pp_market_food_price_extremes.txt")
    assert "pp_victuals_export_delivery_on_weather_pulse" in on_action
    assert "pp_deliver_victuals_exports = yes" in on_action


def test_tally_good_is_a_cheap_always_supplied_dummy() -> None:
    good = _read("in_game/common/goods/pp_goods_export_tally.txt")
    assert "default_market_price = 0.1" in good
    assert "base_production = 1000.0" in good
    assert "goods_export_tally" in _read("main_menu/common/named_colors/pp_export_tally_colors.txt")
    assert "export_tally:" in _read("main_menu/localization/english/pp_export_tally_l_english.yml")
    for sub in ("", "illustrations/"):
        assert (MOD_ROOT / f"main_menu/gfx/interface/icons/trade_goods/{sub}icon_goods_export_tally.dds").is_file()


def test_export_shares_the_farms_surplus_sales_good() -> None:
    """The export storage leg pays on province_food_sales (constant -1); its fixed cost sets the 18-month break-even."""
    building = _read("in_game/common/building_types/zz_pp_victuals_market.txt")
    assert "produced = province_food_sales" in building
    assert "offset = 24.9" in building
    assert "local_province_food_sales_output_modifier = -0.3" in building
    assert "export_sales" not in building
    assert not (MOD_ROOT / "in_game/common/goods/pp_goods_export_sales.txt").exists()
    for rel in (
        "in_game/common/auto_modifiers/pp_country_base_values.txt",
        "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt",
        "main_menu/localization/english/pp_goods_l_english.yml",
    ):
        assert "export_sales" not in _read(rel), rel
