from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
import yaml
from eu5_building_pipeline.generator import render_advancements
from eu5_building_pipeline.template import load_template
from eu5gameparser.domain.availability import annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data

from prosper_or_perish_constructor.farming_village_unlocks import (
    GAME_START_AGE,
    check_blueprint_advancements,
    derive_rgo_unlock_gates,
    effective_rgo_unlock_config,
    load_current_location_frame,
    load_location_potential_frame,
    load_rgo_unlock_config,
    load_start_location_frame,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
LOAD_ORDER = ROOT / "constructor.load_order.toml"
FARMING_VILLAGE_BLUEPRINT = ROOT / "blueprints" / "accepted" / "buildings" / "farming_village.yml"
FARMING_VILLAGE_ADVANCES = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "advances"
    / "pp_farming_village.txt"
)


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
        for gate in derive_rgo_unlock_gates(
            pl.DataFrame(rows),
            goods=("rice", "maize"),
            threshold=0.60,
        )
    }

    assert gates["rice"].subcontinents == ("alpha",)
    assert gates["rice"].regions == ("beta_1",)
    assert gates["maize"].subcontinents == ("beta",)
    assert gates["maize"].regions == ("alpha_4",)


def test_start_location_frame_joins_game_start_population() -> None:
    geography = load_current_location_frame(ROOT, PROJECT)
    locations = load_start_location_frame(ROOT, PROJECT)

    assert "population_peasants" in locations.columns
    assert "total_population" in locations.columns
    assert "local_population_capacity" in locations.columns
    assert "location_potential_modifier" in locations.columns
    assert locations.height == geography.height
    assert set(geography["location_tag"].to_list()) == set(locations["location_tag"].to_list())

    ebstorf = locations.filter(pl.col("location_tag") == "ebstorf")
    assert ebstorf.height == 1
    assert float(ebstorf["total_population"].item()) > 0.0
    assert ebstorf["location_potential_modifier"].item() == "pp_loc_ebstorf"
    assert float(ebstorf["local_population_capacity"].item()) > 0.0


def test_location_potential_frame_maps_alias_keys() -> None:
    potential = load_location_potential_frame(ROOT, PROJECT)
    washita = potential.filter(pl.col("location_tag") == "washita")
    if washita.is_empty():
        pytest.skip("washita not present in current Location Potential table")
    assert washita["location_potential_modifier"].item() == "pp_loc_washita_pp"


def test_current_location_data_derives_expected_farming_village_gates() -> None:
    config = load_rgo_unlock_config(PROJECT)
    gates = {
        gate.good: gate
        for gate in derive_rgo_unlock_gates(
            load_current_location_frame(ROOT, PROJECT),
            goods=[item.good for item in config.goods],
            threshold=config.threshold,
        )
    }

    assert config.threshold == pytest.approx(0.60)
    assert tuple(item.good for item in config.goods) == ("rice", "maize", "potato", "olives")
    assert gates["rice"].subcontinents == (
        "east_asia",
        "middle_east",
        "south_asia",
        "south_east_asia",
        "west_africa",
    )
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
    assert gates["olives"].regions == (
        "balkan_region",
        "france_region",
        "iberia_region",
        "italy_region",
    )


def test_farming_village_blueprint_advancements_match_generated_unlocks() -> None:
    check = check_blueprint_advancements(ROOT, PROJECT)

    assert check.ok, check.unified_diff()


def test_early_upgrade_crop_methods_are_added_to_crop_unlocks_dynamically() -> None:
    config = load_rgo_unlock_config(PROJECT)
    effective_config = effective_rgo_unlock_config(ROOT, config)
    general_age_by_good = {item.good: item.general_age for item in config.goods}
    data = load_eu5_data(profile="constructor", load_order_path=LOAD_ORDER)
    availability = annotate_building_data_availability(data.building_data, data.advancements)
    upgrade_buildings = _farming_village_family_buildings(include_base=False)

    configured_methods = {item.good: set(item.methods) for item in config.goods}
    effective_methods = {item.good: set(item.methods) for item in effective_config.goods}
    expected_additions = {item.good: set[str]() for item in config.goods}
    for row in availability.production_methods.filter(
        pl.col("building").is_in(upgrade_buildings)
        & pl.col("produced").is_in(list(general_age_by_good))
    ).to_dicts():
        produced = row["produced"]
        building_age = row.get("building_unlock_age")
        if building_age is not None and _age_index(building_age) < _age_index(general_age_by_good[produced]):
            expected_additions[produced].add(row["name"])

    additions = {
        good: effective_methods[good] - configured_methods[good]
        for good in effective_methods
    }

    assert additions == expected_additions


def test_generated_mod_advances_match_farming_village_blueprint() -> None:
    rendered = render_advancements(load_template(FARMING_VILLAGE_BLUEPRINT)).strip()
    generated = FARMING_VILLAGE_ADVANCES.read_text(encoding="utf-8-sig")

    assert rendered in generated


def test_parser_reports_specific_game_start_and_general_fallback_unlocks() -> None:
    config = effective_rgo_unlock_config(ROOT, load_rgo_unlock_config(PROJECT))
    data = load_eu5_data(profile="constructor", load_order_path=LOAD_ORDER)
    default_availability = annotate_building_data_availability(data.building_data, data.advancements)
    specific_availability = annotate_building_data_availability(
        data.building_data,
        data.advancements,
        include_specific_unlocks=True,
    )
    advancements = {row["name"]: row for row in data.advancements.to_dicts()}

    for item in config.goods:
        methods = set(item.methods)
        game_start = advancements[f"pp_{item.good}_farm_advance_game_start"]
        general = advancements[f"pp_{item.good}_farm_advance_general"]

        assert set(game_start["unlock_production_method"]) == methods
        assert game_start["age"] == GAME_START_AGE
        assert game_start["has_potential"] is True
        assert set(general["unlock_production_method"]) == methods
        assert general["age"] == item.general_age
        assert general["has_potential"] is True

        for method in methods:
            default_row = _method_row(default_availability.production_methods, method)
            specific_row = _method_row(specific_availability.production_methods, method)
            building_age = default_row.get("building_unlock_age")
            specific_allowed = _latest_age(GAME_START_AGE, building_age)
            general_allowed = _latest_age(item.general_age, building_age)
            assert default_row["availability_kind"] == "specific_only"
            assert default_row["unlock_age"] == general_allowed
            assert default_row["specific_unlock_age"] == GAME_START_AGE
            assert default_row["effective_availability_kind"] == "specific_only"
            assert default_row["effective_unlock_age"] == specific_allowed
            assert specific_row["effective_availability_kind"] == "specific_only"
            assert specific_row["effective_unlock_age"] == specific_allowed


def test_configured_crop_methods_do_not_bypass_general_crop_unlocks() -> None:
    base_config = load_rgo_unlock_config(PROJECT)
    effective_config = effective_rgo_unlock_config(ROOT, base_config)
    general_age_by_good = {item.good: item.general_age for item in base_config.goods}
    generated_methods_by_good = {item.good: set(item.methods) for item in effective_config.goods}
    data = load_eu5_data(profile="constructor", load_order_path=LOAD_ORDER)
    default_availability = annotate_building_data_availability(data.building_data, data.advancements)
    specific_availability = annotate_building_data_availability(
        data.building_data,
        data.advancements,
        include_specific_unlocks=True,
    )
    offenders: list[str] = []

    for row in specific_availability.production_methods.filter(
        pl.col("building").is_in(_farming_village_family_buildings(include_base=True))
        & pl.col("produced").is_in(list(general_age_by_good))
    ).to_dicts():
        produced = row["produced"]
        general_age = general_age_by_good[produced]
        building_age = row.get("building_unlock_age")
        general_allowed = _latest_age(general_age, building_age)
        effective_age = row["effective_unlock_age"]

        if row["name"] in generated_methods_by_good[produced]:
            default_row = _method_row(default_availability.production_methods, row["name"])
            earliest_allowed = _latest_age(GAME_START_AGE, building_age)
            if row["effective_availability_kind"] != "specific_only":
                offenders.append(f"{row['name']}: not specific_only")
            if effective_age != earliest_allowed:
                offenders.append(f"{row['name']}: effective {effective_age}, expected {earliest_allowed}")
            if default_row["unlock_age"] != general_allowed:
                offenders.append(f"{row['name']}: general {default_row['unlock_age']}, expected {general_allowed}")
        elif _age_index(effective_age) < _age_index(general_allowed):
            offenders.append(f"{row['name']}: effective {effective_age}, expected at least {general_allowed}")

    assert not offenders


def _method_row(methods: pl.DataFrame, name: str) -> dict:
    rows = methods.filter(pl.col("name") == name).to_dicts()
    assert len(rows) == 1
    return rows[0]


def _farming_village_family_buildings(*, include_base: bool) -> tuple[str, ...]:
    buildings: list[str] = []
    for path in sorted((ROOT / "blueprints" / "accepted" / "buildings").glob("*.yml")):
        with path.open("r", encoding="utf-8-sig") as handle:
            raw = yaml.safe_load(handle)
        chain = raw.get("upgrade_chain") if isinstance(raw, dict) else None
        if not isinstance(chain, dict) or chain.get("family") != "farming_village":
            continue
        tier = chain.get("tier")
        if not isinstance(tier, int) or (tier == 0 and not include_base):
            continue
        building = raw.get("building")
        if isinstance(building, dict) and isinstance(building.get("key"), str):
            buildings.append(building["key"])
    return tuple(buildings)


def _latest_age(*ages: str | None) -> str:
    known = [age for age in ages if age is not None]
    assert known
    return max(known, key=_age_index)


def _age_index(age: str) -> int:
    age_order = {
        "age_1_traditions": 1,
        "age_2_renaissance": 2,
        "age_3_discovery": 3,
        "age_4_reformation": 4,
        "age_5_absolutism": 5,
        "age_6_revolutions": 6,
    }
    return age_order[age]
