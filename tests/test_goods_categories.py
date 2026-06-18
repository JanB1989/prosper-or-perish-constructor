from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
import re
import tomllib

from eu5gameparser.domain.goods import load_goods_data
from prosper_or_perish_constructor.goods_categories import (
    GOODS_CATEGORY_SCALING_RELATIVE,
    CostScalingBand,
    format_scaled_cost,
    load_good_category_costs,
    load_increase_per_level_cost_band,
    scale_increase_per_level_cost,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
GOODS_CATEGORIES = ROOT / "config" / "goods_categories.csv"
GOODS_CATEGORY_SCALING = ROOT / GOODS_CATEGORY_SCALING_RELATIVE
ALLOWED_CATEGORIES = {
    "farming",
    "forestry",
    "gathering",
    "hunting",
    "manufactured",
    "mining",
}
ALLOWED_SUBCATEGORIES = {
    "farming": {
        "animal_husbandry",
        "apiary",
        "industrial_crops",
        "plant_fibers",
        "spices",
        "staple_crops",
        "stimulants",
        "sweeteners",
        "tree_crops",
    },
    "forestry": {"timber"},
    "gathering": {
        "aquatic_resources",
        "earth_materials",
        "medicinals",
        "surface_minerals",
        "wild_luxuries",
    },
    "hunting": {"animal_products", "wild_food"},
    "manufactured": {
        "beverages",
        "books_and_paper",
        "coerced_labor",
        "construction_materials",
        "industrial_inputs",
        "luxury_crafts",
        "metal_goods",
        "military_goods",
        "naval_goods",
        "prepared_food",
        "textiles_and_leather",
    },
    "mining": {
        "construction_stone",
        "fuel",
        "industrial_minerals",
        "metal_ores",
        "precious_minerals",
    },
}


def test_goods_categories_csv_covers_every_loaded_good_once() -> None:
    rows = _goods_category_rows()
    goods = _loaded_goods()
    loaded_names = {str(row["name"]) for row in goods}
    configured_names = [row["good"] for row in rows]

    assert len(configured_names) == len(set(configured_names))
    assert set(configured_names) == loaded_names
    assert {row["category"] for row in rows} <= ALLOWED_CATEGORIES
    assert all(row["subcategory"] in ALLOWED_SUBCATEGORIES[row["category"]] for row in rows)


def test_goods_categories_increase_per_level_cost_is_normalized() -> None:
    rows = _goods_category_rows()
    cost_by_subcategory: dict[tuple[str, str], str] = {}

    for row in rows:
        raw = row["increase_per_level_cost"]
        assert re.fullmatch(r"(0|1)\.\d{2}", raw)
        value = Decimal(raw)
        assert Decimal("0.00") <= value <= Decimal("1.00")
        assert value % Decimal("0.05") == Decimal("0.00")

        key = (row["category"], row["subcategory"])
        if key in cost_by_subcategory:
            assert cost_by_subcategory[key] == raw
        else:
            cost_by_subcategory[key] = raw


def test_goods_categories_increase_per_level_cost_scaling_config() -> None:
    band = load_increase_per_level_cost_band(GOODS_CATEGORY_SCALING)

    assert band == CostScalingBand(minimum=Decimal("0.05"), maximum=Decimal("0.30"))
    assert format_scaled_cost(scale_increase_per_level_cost(Decimal("0.00"), band)) == "0.05"
    assert format_scaled_cost(scale_increase_per_level_cost(Decimal("1.00"), band)) == "0.30"
    assert format_scaled_cost(scale_increase_per_level_cost(Decimal("0.45"), band)) == "0.16"


def test_goods_categories_scaled_costs_stay_in_configured_band() -> None:
    band = load_increase_per_level_cost_band(GOODS_CATEGORY_SCALING)
    costs = load_good_category_costs(GOODS_CATEGORIES, band)

    assert costs
    for cost in costs.values():
        assert band.minimum <= cost.scaled_cost <= band.maximum
        assert cost.scaled_cost_text == format_scaled_cost(cost.scaled_cost)


def test_goods_categories_increase_per_level_cost_explanations_are_brief() -> None:
    rows = _goods_category_rows()

    for row in rows:
        explanation = row["increase_per_level_cost_explanation"]
        assert explanation
        assert len(explanation) <= 120
        assert "\n" not in explanation
        assert "," not in explanation


def test_goods_categories_csv_is_sorted_by_category_subcategory_then_good() -> None:
    rows = _goods_category_rows()

    assert rows == sorted(rows, key=lambda row: (row["category"], row["subcategory"], row["good"]))


def test_goods_categories_match_current_raw_methods_and_manufactured_goods() -> None:
    configured = {row["good"]: row["category"] for row in _goods_category_rows()}

    for good in _loaded_goods():
        name = str(good["name"])
        if good.get("category") == "raw_material":
            assert configured[name] == good.get("method")
        elif good.get("category") == "produced":
            assert configured[name] == "manufactured"
        else:
            raise AssertionError(f"Unhandled parser goods category for {name}: {good.get('category')}")


def _goods_category_rows() -> list[dict[str, str]]:
    expected_fieldnames = [
        "good",
        "category",
        "subcategory",
        "increase_per_level_cost",
        "increase_per_level_cost_explanation",
    ]
    with GOODS_CATEGORIES.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == expected_fieldnames
        rows = list(reader)
    assert rows
    assert all(list(row) == expected_fieldnames for row in rows)
    assert all(
        row["good"]
        and row["category"]
        and row["subcategory"]
        and row["increase_per_level_cost"]
        and row["increase_per_level_cost_explanation"]
        for row in rows
    )
    return rows


def _loaded_goods() -> list[dict[str, object]]:
    raw = tomllib.loads(PROJECT.read_text(encoding="utf-8-sig"))
    parser = raw.get("parser", {})
    profile = str(parser.get("profile", "constructor"))
    load_order = ROOT / str(parser.get("load_order", "constructor.load_order.toml"))
    return load_goods_data(profile=profile, load_order_path=load_order).goods.to_dicts()
