"""[age_food]: food relief by age (age_food.py, crop_farms.py)."""

from __future__ import annotations

import re
from pathlib import Path

from prosper_or_perish_constructor import age_food, yaml_io

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
ADVANCES = ROOT / "mod" / age_food.MOD_FOLDER / age_food.ADVANCES_FILE
AGE_ORDER = ["age_1_traditions", "age_2_renaissance", "age_3_discovery", "age_4_reformation", "age_5_absolutism"]


def test_blueprints_and_advances_follow_the_table() -> None:
    assert age_food.apply(ROOT, PROJECT, write=False) == []


def test_relief_never_falls_with_the_age() -> None:
    config = age_food.load_config(PROJECT)
    ages = [config.age(name) for name in AGE_ORDER]
    for earlier, later in zip(ages, ages[1:]):
        assert later.flat_food >= earlier.flat_food
        assert later.throughput >= earlier.throughput
    assert all(age.global_food_decay <= 0 for age in ages)   # decay only falls (base 0.015)
    assert sum(age.global_food_decay for age in ages) > -0.015
    assert config.upgrade_weight > 0


def test_food_advances_carry_their_decay_cut() -> None:
    config = age_food.load_config(PROJECT)
    text = ADVANCES.read_text(encoding="utf-8-sig")
    for age in config.ages.values():
        if not age.advance:
            continue
        block = re.search(rf"(?ms)^TRY_INJECT:{age.advance} = \{{\n(.*?)^\}}", text).group(1)
        lines = re.findall(r"(?m)^\tglobal_food_decay = (-?[\d.]+)", block)
        assert lines == ([age_food.num(age.global_food_decay)] if age.global_food_decay else [])


def test_listed_buildings_take_their_age() -> None:
    config = age_food.load_config(PROJECT)
    for building, age_name in config.buildings.items():
        age = config.age(age_name)
        data = yaml_io.safe_load((BLUEPRINTS / f"{building}.yml").read_text(encoding="utf-8"))
        assert float(data.get(age_food.APPLIED_KEY, 1.0)) == age.throughput
        body = data["building"]["body"]
        assert re.search(rf"(?m)^\s*local_monthly_food = {re.escape(age_food.num(age.flat_food))}\s*$", body)
        predecessor = re.search(r"(?m)^\s*obsolete = ([a-z_0-9]+)", body)
        if predecessor:
            assert f"has_building = building_type:{predecessor.group(1)}" in body


def test_rewrite_is_idempotent_and_rescales_from_the_applied_factor() -> None:
    config = age_food.load_config(PROJECT)
    building = "pomological_orchard"
    text = (BLUEPRINTS / f"{building}.yml").read_text(encoding="utf-8")
    age = config.age(config.buildings[building])
    assert age_food.rewrite_building(text, building, age, config.upgrade_weight)[1] == []
    doubled = age_food.Age(age.name, age.flat_food, age.throughput * 2)
    new, what = age_food.rewrite_building(text, building, doubled, config.upgrade_weight)
    assert any("throughput" in item for item in what)
    assert yaml_io.safe_load(new)[age_food.APPLIED_KEY] == age.throughput * 2
