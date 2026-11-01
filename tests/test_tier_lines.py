from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from eu5gameparser.domain.availability import annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data

from prosper_or_perish_constructor import tier_lines

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
LINES = {
    "alum_quarry", "cinnabar_pit", "clay_pit", "coal_mine", "cocoa_grove", "coffee_grove", "copper_mine", "cotton_farm",
    "fiber_crops_farm", "gem_gravel_pit", "gold_diggings", "horse_breeders", "inland_saltworks", "iron_mine", "lead_mine",
    "lumber_mill", "marble_quarry", "pepper_garden", "saffron_croft", "salt_mine", "sand_pit", "sericulture_farm",
    "silver_mine", "stone_quarry", "sugarcane_farm", "tea_garden", "tin_streamworks", "tobacco_farm",
}


@pytest.fixture(scope="module")
def tiers() -> dict[str, tier_lines.Tier]:
    return {tier.tag: tier for tier in tier_lines.plan(ROOT, PROJECT)}


@pytest.fixture(scope="module")
def compiled() -> dict[str, dict]:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    annotated = annotate_building_data_availability(data.building_data, data.advancements)
    return {row["name"]: row for row in annotated.buildings.to_dicts()}


def test_price_rule_stays_inside_its_bounds() -> None:
    config = tier_lines.load_config(PROJECT)
    assert tier_lines.tier_price(0.1, None, config) == 75
    assert tier_lines.tier_price(0.55, None, config) == 100
    assert tier_lines.tier_price(2.0, None, config) == 100
    assert tier_lines.tier_price(0.1, 75, config) == 125  # 112.5 rounds up
    assert tier_lines.tier_price(0.77, 100, config) == 150
    assert tier_lines.tier_price(1.3, 100, config) == 200
    assert tier_lines.tier_price(9.0, 100, config) == 200


def test_scope_is_the_raw_material_lines_and_the_extras(tiers: dict[str, tier_lines.Tier]) -> None:
    overrides = tier_lines.load_config(PROJECT).price_overrides
    assert {tier.line for tier in tiers.values()} - set(overrides) == LINES
    assert not {"charcoal_maker", "bog_iron_smelter", "wheat_farm", "cloth_guild"} & set(tiers)


@pytest.mark.parametrize(("line", "prices"), [
    (("iron_mine", "iron_mine_improved", "iron_mine_deep"), (100, 150, 225)),
    (("coal_mine", "coal_mine_improved", "coal_mine_revolutions"), (100, 200, 300)),
    (("lead_mine", "lead_mine_bole_smelting", "lead_mine_cupola_smelting"), (75, 125, 200)),
    (("lumber_mill", "water_sawmill", "lumber_mill_improved"), (100, 150, 225)),
    (("clay_pit", "clay_washmill"), (75, 125)),
    (("tea_garden", "tea_sorting_garden"), (100, 200)),
])
def test_ladders(tiers: dict[str, tier_lines.Tier], line: tuple[str, ...], prices: tuple[int, ...]) -> None:
    assert tuple(tiers[tag].price for tag in line) == prices


def test_compiled_buildings_carry_the_plan(tiers: dict[str, tier_lines.Tier], compiled: dict[str, dict]) -> None:
    for tag, tier in tiers.items():
        assert compiled[tag]["price"] == f"pp_{tag}_price", tag
        assert compiled[tag]["effective_price_gold"] == tier.price, tag
        if tier.deepens:
            assert compiled[tag]["max_levels"] == tier_lines.cap_name(tier.tier), tag


def test_upper_tiers_replace_every_older_tier(compiled: dict[str, dict]) -> None:
    assert set(compiled["iron_mine_deep"]["obsolete_buildings"]) == {"iron_mine_improved", "iron_mine"}
    assert set(compiled["iron_mine_improved"]["obsolete_buildings"]) == {"iron_mine"}
    assert set(compiled["lumber_mill_improved"]["obsolete_buildings"]) == {"water_sawmill", "lumber_mill"}


def test_depth_caps_keep_the_base_tier_on_the_rural_cap(compiled: dict[str, dict]) -> None:
    assert compiled["iron_mine"]["max_levels"] == tier_lines.BASE_CAP
    assert compiled["iron_mine_improved"]["max_levels"] == "pp_rural_building_cap_tier_1"
    assert compiled["iron_mine_deep"]["max_levels"] == "pp_rural_building_cap_tier_2"
    text = (MOD / tier_lines.CAPS_OUTPUT).read_text(encoding="utf-8-sig")
    assert text.count(f'desc = "{tier_lines.DEPTH_ROW}"') == 2
    assert re.search(r"pp_rural_building_cap_tier_2_depth = \{\n\tvalue = rural_building_cap\n\tmultiply = 0\.5\n", text)


def test_level_bonus_is_scaled_from_the_blueprint(tiers: dict[str, tier_lines.Tier]) -> None:
    assert tiers["iron_mine_deep"].bonus == (("iron", Decimal("0.035")),)
    text = (MOD / "in_game/common/building_types/zz_pp_iron_mine_improved_deep.txt").read_text(encoding="utf-8-sig")
    assert "local_iron_output_modifier = 0.02625" in text


def test_price_keys_are_defined_once() -> None:
    prices = MOD / "in_game/common/prices"
    ours = set(re.findall(r"(?m)^(pp_\w+_price)\s*=", (prices / tier_lines.PRICES_OUTPUT.name).read_text(encoding="utf-8-sig")))
    for path in prices.glob("*.txt"):
        if path.name != tier_lines.PRICES_OUTPUT.name:
            assert not ours & set(re.findall(r"(?m)^(?:[A-Z_]+:)?(pp_\w+_price)\s*=", path.read_text(encoding="utf-8-sig"))), path


def test_rewrite_gives_the_same_body_on_a_second_run() -> None:
    config = tier_lines.load_config(PROJECT)
    body = (
        "\nincrease_per_level_cost = 0.19\nmax_levels = rural_building_cap\nobsolete = b\n"
        "modifier = {\n    local_iron_output_modifier = 0.035\n    local_population_growth = -0.00015\n}\n"
    )
    tier = tier_lines.Tier(tag="c", line="a", tier=2, price=225, previous="b", older=("a",), deepens=True,
                           bonus=(("iron", Decimal("0.035")),))
    once = tier_lines.rewrite(body, tier, config)
    assert tier_lines.rewrite(once, tier, config) == once
    assert "price = pp_c_price\n" in once and "max_levels = pp_rural_building_cap_tier_2\n" in once
    assert "obsolete = b\nobsolete = a\n" in once and "local_iron_output_modifier = 0.02625\n" in once
