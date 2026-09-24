from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest
from eu5_building_pipeline.generator import render_advancements
from eu5_building_pipeline.template import load_template

from prosper_or_perish_constructor import crop_farms, provisioning, yaml_io
from prosper_or_perish_constructor.location_baseline import load_current_location_frame
from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ADVANCES_ROOT = MOD_ROOT / "in_game" / "common" / "advances"
FARMING_CAPACITY_VALUES = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_farming_capacity.txt"
ENGLISH_LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english"
# The land farms after the crop chains, unchanged by the crop farm split.
LAND_FARM_TAIL = (
    "fruit_orchard",
    "nursery_orchard",
    "pomological_orchard",
    "sheep_farms",
    "hurdled_sheepcotes",
    "enclosed_sheep_walks",
    "horse_breeders",
    "stud_farm",
    "elephant_kraal",
    "fiber_crops_farm",
    "fiber_dressing_yard",
    "cotton_plantation",
    "cotton_farm",
    "market_cotton_farm",
    "sugar_plantation",
    "sugarcane_farm",
    "trapiche_sugarcane_farm",
    "tobacco_plantation",
    "tobacco_farm",
    "market_tobacco_farm",
    "dye_plantation",
    "chili_plantation",
    "clove_grove",
    "cocoa_grove",
    "managed_cocoa_grove",
    "coffee_grove",
    "terraced_coffee_grove",
    "incense_grove",
    "pepper_garden",
    "managed_pepper_garden",
    "saffron_croft",
    "saffron_kiln_croft",
    "sericulture_farm",
    "regulated_sericulture_farm",
    "simplers_grove",
    "tea_garden",
    "tea_sorting_garden",
    "vineyard_estate",
)


@pytest.fixture(scope="module")
def table() -> crop_farms.CropTable:
    return crop_farms.load_crop_table(ROOT)


def _blueprint(key: str) -> dict:
    return yaml_io.safe_load((BLUEPRINTS / f"{key}.yml").read_text(encoding="utf-8-sig"))


def _block(body: str, name: str) -> str | None:
    """The text of the first top-level `name = { ... }` block of a body, braces matched."""
    match = re.search(rf"(?m)^{re.escape(name)}\s*=\s*\{{", body)
    if match is None:
        return None
    depth = 0
    for index in range(match.end() - 1, len(body)):
        depth += {"{": 1, "}": -1}.get(body[index], 0)
        if depth == 0:
            return body[match.start() : index + 1]
    raise AssertionError(f"unclosed {name} block")


def test_rgo_unlock_derivation_uses_per_good_region_threshold() -> None:
    rows = [
        {"raw_material": "rice", "macro_region": "alpha", "region": "alpha_1"},
        {"raw_material": "rice", "macro_region": "alpha", "region": "alpha_2"},
        {"raw_material": "rice", "macro_region": "alpha", "region": "alpha_3"},
        {"raw_material": "maize", "macro_region": "alpha", "region": "alpha_4"},
        {"raw_material": "wheat", "macro_region": "alpha", "region": "alpha_5"},
        {"raw_material": None, "macro_region": "alpha", "region": "alpha_sea"},
        {"raw_material": "rice", "macro_region": "beta", "region": "beta_1"},
        {"raw_material": "maize", "macro_region": "beta", "region": "beta_2"},
        {"raw_material": "maize", "macro_region": "beta", "region": "beta_3"},
    ]

    gates = {
        gate.good: gate
        for gate in crop_farms.derive_rgo_unlock_gates(pl.DataFrame(rows), goods=("rice", "maize"), threshold=0.60)
    }

    assert gates["rice"].subcontinents == ("alpha",)
    assert gates["rice"].regions == ("beta_1",)
    assert gates["maize"].subcontinents == ("beta",)
    assert gates["maize"].regions == ("alpha_4",)


def test_current_location_data_derives_expected_crop_gates(table: crop_farms.CropTable) -> None:
    gates = {
        gate.good: gate
        for gate in crop_farms.derive_rgo_unlock_gates(
            load_current_location_frame(ROOT, PROJECT), goods=table.gated_goods, threshold=table.threshold
        )
    }

    assert table.threshold == pytest.approx(0.60)
    assert table.gated_goods == ("rice", "maize", "potato", "olives")
    assert gates["rice"].subcontinents == ("east_asia", "middle_east", "south_asia", "south_east_asia", "west_africa")
    assert gates["rice"].regions == (
        "central_africa_region",
        "egypt_region",
        "great_lakes_region",
        "iberia_region",
        "italy_region",
        "madagascar_region",
        "swahili_coast_region",
        "zimbabwe_region",
    )
    assert gates["maize"].subcontinents == ("north_america", "south_america")
    assert gates["maize"].regions == ()
    assert gates["potato"].subcontinents == ()
    assert gates["potato"].regions == ("andes_region", "colombia_region")
    assert gates["olives"].subcontinents == ("middle_east", "north_africa")
    assert gates["olives"].regions == ("balkan_region", "france_region", "iberia_region", "italy_region")


def test_crop_farm_outputs_are_current() -> None:
    problems = crop_farms.check(ROOT, PROJECT)

    assert problems == [], "\n".join(problems) + "\nRun: uv run ppc crop-farms --write"


def test_crop_buildings_are_the_chains_in_table_order(table: crop_farms.CropTable) -> None:
    buildings = crop_farms.crop_buildings(table)

    assert len(buildings) == 32
    assert buildings[:4] == ("wheat_farm", "wheat_farmstead", "wheat_rotations", "wheat_model_farm")
    assert [crop.stem for crop in table.crops] == ["wheat", "rice", "millet", "maize", "legume", "potato", "olive", "cattle"]
    assert LAND_FARM_BUILDINGS == (*buildings, *LAND_FARM_TAIL)
    assert set(buildings) <= set(provisioning.PROVISIONING_BUILDINGS)
    for building, good in crop_farms.crop_building_goods(table).items():
        assert provisioning.provisioned_good(building) == good


def test_retired_farm_tiers_are_gone_and_farming_village_is_a_tombstone() -> None:
    for key in crop_farms.RETIRED_BLUEPRINTS:
        assert not (BLUEPRINTS / f"{key}.yml").exists()

    tombstone = _blueprint("farming_village")
    body = tombstone["building"]["body"]
    assert tombstone["building"]["mode"] == "REPLACE"
    assert "upgrade_chain" not in tombstone and "advancements" not in tombstone
    assert re.search(r"(?m)^max_levels = 0$", body)
    assert "always = no" in _block(body, "location_potential")
    assert "modifier = {" not in body
    assert [slot["methods"] for slot in tombstone["building"]["production_method_slots"]] == [[crop_farms.TOMBSTONE_METHOD]]


def test_gated_chains_share_their_gates_on_every_tier(table: crop_farms.CropTable) -> None:
    for crop in table.crops:
        bodies = [_blueprint(table.building(crop, tier))["building"]["body"] for tier in crop_farms.TIERS]
        potentials = {_block(body, "location_potential") for body in bodies}
        countries = {_block(body, "country_potential") for body in bodies}

        assert potentials == {f"location_potential = {{\n    pp_{crop.stem}_farm_location_potential = yes\n}}"}
        if crop.gated:
            assert len(countries) == 1
            country = countries.pop()
            assert f"pp_{crop.stem}_native_country = yes" in country
            assert f"has_advance = {table.general_advance(crop)}" in country
        else:
            assert countries == {None}


def test_general_crop_advances_have_configured_age_and_non_native_potential(table: crop_farms.CropTable) -> None:
    for crop in table.crops:
        if not crop.gated:
            continue
        key = table.general_advance(crop)
        spec = table.unlocks["general"][crop.good]
        advancements = {item["key"]: item["body"] for item in _blueprint(table.building(crop, 0)).get("advancements", [])}
        body = advancements[key]

        assert re.search(rf"(?m)^age = {spec['age']}$", body)
        assert re.search(rf"(?m)^requires = {spec['requires']}$", body)
        potential = _block(body, "potential")
        assert "exists = capital" in potential
        assert "NOT = {" in potential and "original_capital ?= {" in potential
        assert "unlock_production_method" not in body and "unlock_building" not in body


def test_native_country_triggers_list_the_derived_gates(table: crop_farms.CropTable) -> None:
    text = (MOD_ROOT / crop_farms.TRIGGERS_RELATIVE_PATH).read_text(encoding="utf-8-sig")
    gates = crop_farms.current_gates(ROOT, PROJECT, table)

    for crop in table.crops:
        trigger = _block(text, crop_farms.location_trigger(crop))
        assert trigger is not None and "is_ownable = yes" in trigger
        top_level_base = re.search(r"(?m)^\tpp_general_farmable_food_location_potential = yes$", trigger) is not None
        assert top_level_base != crop.location_rule_standalone   # cattle carries its own pasture-or-farmable rule
        native = _block(text, crop_farms.native_trigger(crop))
        if not crop.gated:
            assert native is None
            continue
        gate = gates[crop.good]
        assert "original_capital ?= {" in native
        for subcontinent in gate.subcontinents:
            assert f"sub_continent = sub_continent:{subcontinent}" in native
        for region in gate.regions:
            assert f"region = region:{region}" in native


def test_every_crop_farm_has_base_cultivation_and_provisioning_slots(table: crop_farms.CropTable) -> None:
    for crop in table.crops:
        for tier in crop_farms.TIERS:
            building = table.building(crop, tier)
            slots = [slot["methods"] for slot in _blueprint(building)["building"]["production_method_slots"]]

            assert slots[0] == [f"pp_{building}_base"]
            assert slots[1] == [f"pp_{building}_no_cultivation", *(f"pp_{building}_{m.key}" for m in crop.tier_methods(tier))]
            assert slots[-1] == [f"pp_{building}_provision", f"pp_{building}_sell_surplus"]
            assert len(slots) == (4 if crop_farms.has_beekeeping(table, crop, tier) else 3)


def test_tier_advances_unlock_the_tier_of_every_chain(table: crop_farms.CropTable) -> None:
    for tier in (1, 2, 3):
        key = table.tier_advance(tier)
        host = _blueprint(table.building(table.crop("wheat"), tier))
        body = next(item["body"] for item in host["advancements"] if item["key"] == key)

        assert re.findall(r"(?m)^unlock_building = (\w+)$", body) == [table.building(crop, tier) for crop in table.crops]


def test_cultivation_advances_unlock_exactly_the_methods_that_name_them(table: crop_farms.CropTable) -> None:
    advancements = {item["key"]: item["body"] for item in _blueprint("wheat_farm")["advancements"]}
    expected = crop_farms.cultivation_advance_methods(table)

    assert set(expected) == {"pp_heavy_plough", "pp_improved_rotations", "pp_water_lifting"}
    for key, methods in expected.items():
        assert methods
        assert re.findall(r"(?m)^unlock_production_method = (\w+)$", advancements[key]) == methods
    named = {
        f"pp_{table.building(crop, m.tier)}_{m.key}" for crop in table.crops for m in crop.methods if m.advance
    }
    assert named == {method for methods in expected.values() for method in methods}


def test_generated_mod_advances_match_the_crop_blueprints(table: crop_farms.CropTable) -> None:
    for crop in table.crops:
        for tier in crop_farms.TIERS:
            template = load_template(BLUEPRINTS / f"{table.building(crop, tier)}.yml")
            if not template.advancements:
                continue
            generated = (ADVANCES_ROOT / f"pp_{template.output_tag}.txt").read_text(encoding="utf-8-sig")
            assert render_advancements(template).strip() in generated


def test_farm_capacity_tooltip_rows_have_localization() -> None:
    keys = set(re.findall(r'desc = "(BUILDING_LEVEL_FARM_\w+)"', FARMING_CAPACITY_VALUES.read_text(encoding="utf-8-sig")))
    localized: set[str] = set()
    for path in ENGLISH_LOCALIZATION.glob("*.yml"):
        localized.update(re.findall(r"(?m)^\s+(BUILDING_LEVEL_FARM_\w+):", path.read_text(encoding="utf-8-sig")))

    assert keys
    assert {f"BUILDING_LEVEL_FARM_{key.upper()}" for key in crop_farms.crop_buildings(crop_farms.load_crop_table(ROOT))} <= keys
    assert sorted(keys - localized) == []
