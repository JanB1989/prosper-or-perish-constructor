"""The staple foods: one list (2026-10-04, Jan) and every mechanic that reads it.

Staple crops, staple animals and staple fruits (the ``staple_group`` column of config/goods_categories.csv). Every
building that makes one provisions the province (so the store curve moves it), counts toward the Cookshop cap and is
staffed with the food makers; the store curve, the logistics bulk shares and the crop allocation read the same list.
"""

from __future__ import annotations

import re
import statistics
import tomllib
from pathlib import Path

import pytest
import yaml

from prosper_or_perish_constructor import logistics, provisioning, staple_foods, stored_food
from prosper_or_perish_constructor.worldbuilder import crop_allocation

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BLUEPRINTS = ROOT / "blueprints/accepted/buildings"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"


def _body(name: str) -> str:
    raw = yaml.safe_load((BLUEPRINTS / f"{name}.yml").read_text(encoding="utf-8-sig"))
    return (raw.get("building") or {}).get("body") or ""


def _slots(body: str) -> list[dict[str, dict[str, object]]]:
    """The unique_production_methods blocks of a building body: method -> {good: amount, produced, output}."""
    slots = []
    for match in re.finditer(r"unique_production_methods = \{", body):
        i, depth = match.end(), 1
        while depth:
            depth += (body[i] == "{") - (body[i] == "}")
            i += 1
        methods = {}
        for method in re.finditer(r"(\w+) = \{([^{}]*)\}", body[match.end():i - 1]):
            values: dict[str, object] = {k: float(v) for k, v in re.findall(r"(\w+) = ([\d.]+)", method.group(2))}
            produced = re.search(r"produced = (\w+)", method.group(2))
            values["produced"] = produced.group(1) if produced else None
            methods[method.group(1)] = values
        slots.append(methods)
    return slots


def _staple_makers() -> dict[str, str]:
    """Accepted blueprint -> the staple food it makes (from its methods' outputs)."""
    staples = set(staple_foods.staple_foods())
    makers = {}
    for path in sorted(BLUEPRINTS.glob("*.yml")):
        made = set(re.findall(r"produced = (\w+)", _body(path.stem))) & staples
        if made:
            assert len(made) == 1, (path.stem, made)
            makers[path.stem] = made.pop()
    return makers


def test_one_list_in_three_groups() -> None:
    assert staple_foods.goods_in_group("crops") == ("legumes", "maize", "millet", "potato", "rice", "wheat")
    assert set(staple_foods.goods_in_group("animals")) == {"livestock", "fish", "wild_game", "wool"}
    assert set(staple_foods.goods_in_group("fruits")) == {"fruit", "olives"}
    assert len(staple_foods.staple_foods()) == 12
    # the category columns stay as they are: the staple crops are also the staple_crops subcategory
    assert {g for g in staple_foods.staple_foods() if staple_foods.staple_group(g) == "crops"} == set(
        staple_foods.goods_in_group("crops"))


def test_every_staple_food_maker_provisions_counts_and_is_staffed_as_food() -> None:
    makers = _staple_makers()
    assert set(makers) == set(provisioning.PROVISIONING_BUILDINGS)
    for building, good in makers.items():
        body = _body(building)
        assert provisioning.provisioned_good(building) == good, building
        assert provisioning.provision_method(building) in body, building
        assert "pp_staple_food_priority" in body, building
    # the Provision goods are staple foods
    assert set(provisioning.PROVISIONED_GOOD_BY_BUILDING.values()) == set(staple_foods.staple_foods())


def test_every_staple_food_is_on_the_store_curve() -> None:
    config = stored_food.load_config(PROJECT)
    assert config.staple_goods == staple_foods.staple_foods()
    lines = stored_food.curve_lines(config, 0)
    for good in config.staple_goods:
        assert float(lines[f"local_{good}_output_modifier"]) < 0, good   # a low store keeps the food at home
    raw = tomllib.loads(PROJECT.read_text(encoding="utf-8"))
    assert "staple_goods" not in raw["stored_food"]["curve"]


def test_staple_curve_factors_follow_the_crop_farm_balance() -> None:
    """A good's factor is 0.40 x the median over its provisioning buildings of Province Food / (12 x its output value
    at their best methods), over the crop farms' median of the same ratio (constructor.toml [stored_food.curve])."""
    config = stored_food.load_config(PROJECT)
    prices = {good: float(provisioning.provisioned_good_price(good)) for good in config.staple_goods}
    ratios: dict[str, list[float]] = {}
    for building, good in _staple_makers().items():
        food = output = 0.0
        for slot in _slots(_body(building)):
            if provisioning.provision_method(building) in slot:
                food = float(slot[provisioning.provision_method(building)]["output"])
            elif not any(name.endswith("_market_sales") for name in slot):
                output += max(float(m.get("output", 0)) if m.get("produced") == good else 0.0 for m in slot.values())
        ratios.setdefault(good, []).append(food / (12 * output * prices[good]))
    farm_goods = set(provisioning.CROP_FARM_GOODS.values())
    farm_median = statistics.median(r for good in farm_goods for r in ratios[good])
    for good in config.staple_goods:
        rule = config.staple_factor * statistics.median(ratios[good]) / farm_median
        if good in farm_goods:
            assert config.factor(good) == config.staple_factor, good
            assert rule == pytest.approx(config.staple_factor, abs=0.02), good
        else:
            assert config.factor(good) == pytest.approx(rule, abs=0.01), (good, round(rule, 3))


def test_logistics_bulk_shares_cover_every_staple_food() -> None:
    config = logistics.load_config(PROJECT)
    assert {good for good, _ in config.bulky_staples} == set(staple_foods.staple_foods())
    assert all(0 < share <= 1 for _, share in config.bulky_staples)


def test_crop_allocation_reads_the_staple_crops() -> None:
    raw = tomllib.loads(PROJECT.read_text(encoding="utf-8"))
    assert "grains" not in raw["worldbuilder"]["start"]["crops"]
    assert crop_allocation.load_crop_config(raw, ROOT).staple_crops == staple_foods.goods_in_group("crops")


def test_victualling_yard_ships_salt_beef_and_raises_the_cookshop_cap() -> None:
    body = _body("victualling_yard")
    methods = {name: m for slot in _slots(body) for name, m in slot.items()}
    beef = methods["pp_victualling_yard_salt_beef_shipment"]
    grain = methods["pp_victualling_yard_grain_shipment"]
    # the same gold of staple per victual as every other shipment (livestock at 1.5), so it stays food-neutral
    assert beef["livestock"] * float(provisioning.provisioned_good_price("livestock")) == pytest.approx(grain["wheat"], abs=0.002)
    assert beef["output"] == grain["output"]
    # sheep walked to their markets: no wool shipment
    assert not any(m.get("wool") for m in methods.values())
    raw_block = body[body.index("raw_modifier = {"):]
    assert "local_pp_victualling_yard_levels = 1" in raw_block[:raw_block.index("}")]
    caps = (MOD_ROOT / "in_game/common/script_values/pp_building_caps.txt").read_text(encoding="utf-8-sig")
    helper = caps[caps.index("cookshop_max_level_pp_building_level_province_victualling_yards = {"):]
    helper = helper[:helper.index("\n}")]
    assert "value = pp_location_province_victualling_yard_levels" in helper and "multiply = 0.5" in helper
    cap = caps[caps.index("cookshop_max_level = {"):]
    assert "this.cookshop_max_level_pp_building_level_province_victualling_yards" in cap[:cap.index("\n}")]
    values = (MOD_ROOT / "in_game/common/script_values/pp_food_building_values.txt").read_text(encoding="utf-8-sig")
    assert "add = modifier:local_pp_victualling_yard_levels" in values
    types = (MOD_ROOT / "main_menu/common/modifier_type_definitions/pp_food_building_modifier_types.txt").read_text(
        encoding="utf-8-sig")
    assert "local_pp_victualling_yard_levels = {" in types


def test_tavern_level_cost_spares_hungry_provinces() -> None:
    """2026-10-04 (Jan): standing Taverns cost 100 each only from 8 stored months (fading in from 6, where the Common
    Table gate closes), so a hungry capital can add levels while the store is low."""
    body = _body("tavern")
    assert re.search(r'value = "location_building_level\(building_type:tavern\)"\s+multiply = 100\s+'
                     r"multiply = \{ value = pp_location_stored_months subtract = 6 divide = 2 min = 0 max = 1 \}", body)


def test_tavern_veto_starts_at_twelve_months() -> None:
    """2026-10-04 (Jan): no new Tavern level once the province holds 12 months (fading in from 10; was 6 from 4)."""
    body = _body("tavern")
    assert re.search(r"subtract = \{ value = pp_location_stored_months subtract = 10 divide = 2 min = 0 max = 1 "
                     r"multiply = 10000 \}", body)
