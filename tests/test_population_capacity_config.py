import re
import tomllib
import csv
import hashlib
import json
from pathlib import Path

import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_population_capacity.analysis import (
    capacity_effect_inventory,
    current_modifier_maps,
)
from prosper_or_perish_population_capacity.benchmarks import (
    audit_population_benchmarks,
    load_population_benchmarks,
)
from prosper_or_perish_population_capacity.config import load_pipeline_config
from prosper_or_perish_population_capacity.extraction import STATIC_MODIFIER_BLOCK
from prosper_or_perish_population_capacity.geometry_calibration import fit_transform, load_control_points
from prosper_or_perish_population_capacity.merge import load_collection, profile_from
from prosper_or_perish_population_capacity.render import write_population_capacity_files


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
LABELING_ROOT = ROOT.parent / "ProsperOrPerishLabelingPipeline"
LABELING_BASELINE = LABELING_ROOT / "base_data" / "locations_with_raw_material.parquet"
LOCATION_MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifiers.txt"
APPLY_LOCATION_MODIFIERS = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_apply_location_modifiers.txt"
GAME_START = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_game_start.txt"
CAPACITY_PRESSURE_EFFECTS = (
    MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_capacity_pressure_effects.txt"
)
LOCATION_MODIFIER_LOCALIZATION = (
    MOD_ROOT / "main_menu" / "localization" / "english" / "pp_location_modifiers_l_english.yml"
)
EUROPEDIA_LOCALIZATION = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_europedia_l_english.yml"
LOCATION_POTENTIAL_CONCEPT = (
    MOD_ROOT / "main_menu" / "common" / "game_concepts" / "pp_location_potential.txt"
)
POPULATION_BENCHMARKS = ROOT / "population_capacity_benchmarks.toml"
ACCEPTED_CAPACITY = ROOT / "data" / "population_capacity" / "accepted_capacity.csv"
PROFILE_CAPACITY = ROOT / "data" / "population_capacity" / "population_capacity.csv"
CONTROL_POINTS = ROOT / "population_capacity_control_points.csv"
CAPACITY_EFFECT_BLOCKS = (
    "TRY_REPLACE:available_free_land",
    "TRY_REPLACE:abundant_free_land",
    "TRY_REPLACE:overpopulation",
)
ANIMAL_PRODUCT_GOODS = (
    "beeswax",
    "elephants",
    "fish",
    "fur",
    "horses",
    "ivory",
    "livestock",
    "silk",
    "wild_game",
    "wool",
)
NON_IRRIGATED_PLANT_GOODS = ("lumber",)
MANAGED_CAPACITY_EFFECT_FILE = "pp_capacity_pressure_effects.txt"
BENCHMARK_GROUPS = (
    "province",
    "region",
    "area",
    "super_region",
    "macro_region",
    "climate",
    "topography",
    "vegetation",
)


def test_population_capacity_config_loads() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    config_text = (ROOT / "population_capacity.toml").read_text(encoding="utf-8")

    assert config.generated_label == "Prosper or Perish"
    assert config.managed_write_mode == "mod_root"
    assert config.capacity_scale.minimum == 10
    assert config.capacity_scale.maximum == 100
    assert config.capacity_scale.deployment_mode == "raw"
    assert config.capacity_scale.people_per_game_population_unit == 1000
    assert config.calibration.historical_population_policy == "evidence_registry_only"
    assert config.calibration.saturation_anchors is None
    assert config.calibration.land_potential_sources == (
        "gaez_v5",
        "gaez_v4",
        "chelsa_trace21k",
        "archaeoglobe_technology_only",
    )
    assert config.carrying_capacity.benchmarks == "population_capacity_benchmarks.toml"
    assert config.carrying_capacity.area_benchmarks == "population_capacity_area_benchmarks.toml"
    assert config.carrying_capacity.calibrated_geometry.endswith(
        "geometry_land_contract_candidate_v1/location_geometry_candidate.parquet"
    )
    assert config.carrying_capacity.sample_points.endswith(
        "geometry_land_contract_candidate_v1/full/game_authoritative_physical_samples.parquet"
    )
    assert config.carrying_capacity.sample_points_audit.endswith(
        "game_authoritative_sample_acceptance_audit.json"
    )
    assert config.carrying_capacity.geometry_resolution_audit.endswith(
        "game_authoritative_coordinate_resolution.json"
    )
    assert config.carrying_capacity.crop_mode_labels.endswith("crop_mode_labels.parquet")
    assert config.carrying_capacity.crop_history_registry == (
        "population_capacity_crop_history_registry.toml"
    )
    assert config.carrying_capacity.crop_history_evidence == (
        "population_capacity_crop_history_evidence.csv"
    )
    assert config.carrying_capacity.pyaez_climate_inputs.endswith(
        "pyaez_1337/all_samples/climate_inputs_600bp.parquet"
    )
    assert config.carrying_capacity.irrigation_feasibility.endswith(
        "groundwater_whymap_wave29/irrigation_feasibility_with_groundwater.parquet"
    )
    assert config.carrying_capacity.fisheries_labels.endswith("fisheries_location_labels.parquet")
    assert config.carrying_capacity.terrestrial_labels.endswith(
        "terrestrial_food_location_labels.parquet"
    )
    assert config.carrying_capacity.terrestrial_audit.endswith(
        "terrestrial_food_physics_audit.json"
    )
    assert config.carrying_capacity.tsetse_labels.endswith(
        "tsetse_production_location_labels.parquet"
    )
    assert config.carrying_capacity.tsetse_audit.endswith(
        "tsetse_production_audit.json"
    )
    assert config.carrying_capacity.tsetse_source_root.endswith(
        "terrestrial_subsistence_sources/tsetse"
    )
    assert config.carrying_capacity.fisheries_audit.endswith("fisheries_label_audit.json")
    assert config.carrying_capacity.fisheries_source_root.endswith("fisheries_sources")
    assert config.carrying_capacity.hydrology_source_root.endswith("hydrology_sources/hydrology")
    assert config.carrying_capacity.technology_registry == "population_capacity_technology_registry.toml"
    assert config.carrying_capacity.accepted_table == "data/population_capacity/accepted_capacity.csv"
    assert config.carrying_capacity.population_capacity_table == "data/population_capacity/population_capacity.csv"
    assert config.set_values == {}
    assert config.whole_blocks == {}
    assert config.feature_capacity_adjustments.enabled is False
    assert config.feature_capacity_adjustments.removed_values == {}
    assert config.feature_capacity_adjustments.vanilla_values == {}
    assert "[set_values." not in config_text
    assert "[whole_blocks." not in config_text
    assert "[feature_capacity_adjustments" not in config_text
    assert "[values." not in config_text
    assert "[capacity_effects." not in config_text
    assert "[inject_values." not in config_text
    assert "[replace_static_modifiers." not in config_text


def test_crop_history_registry_is_checksum_pinned_and_covers_every_modeled_crop() -> None:
    registry_path = ROOT / "population_capacity_crop_history_registry.toml"
    evidence_path = ROOT / "population_capacity_crop_history_evidence.csv"
    domains_path = ROOT / "population_capacity_crop_history_domains.geojson"
    mapping_path = ROOT / "population_capacity_crop_history_location_mapping.csv"
    mapping_audit_path = ROOT / "population_capacity_crop_history_mapping_audit.json"
    with registry_path.open("rb") as handle:
        registry = tomllib.load(handle)
    assert registry["schema_version"] == "crop_history_registry_v2"
    assert registry["evidence"]["sha256"] == hashlib.sha256(
        evidence_path.read_bytes()
    ).hexdigest()
    assert registry["domains"]["sha256"] == hashlib.sha256(
        domains_path.read_bytes()
    ).hexdigest()
    assert registry["mapping"]["sha256"] == hashlib.sha256(
        mapping_path.read_bytes()
    ).hexdigest()
    assert registry["mapping"]["audit_sha256"] == hashlib.sha256(
        mapping_audit_path.read_bytes()
    ).hexdigest()
    crops = {row["crop"] for row in registry["crop"]}
    assert len(crops) == 23
    with evidence_path.open("r", encoding="utf-8", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    assert {row["crop"] for row in evidence}.issubset(crops)
    assert not any(
        row["source_id"] == "milla_crop_origins_v1_2020" for row in evidence
    )
    direct_maize = [
        row
        for row in evidence
        if row["source_id"] == "van_etten_hijmans_maize_2010"
        and row["evidence_state"] == "known_available"
    ]
    assert len(direct_maize) == 100
    puruha = [row for row in evidence if row["source_id"] == "aguirre_merino_puruha_2025"]
    assert len(puruha) == 6
    kuk = [row for row in evidence if row["source_id"] == "unesco_kuk_nomination_2007"]
    assert len(kuk) == 3
    assert {row["crop"] for row in kuk} == {"banana", "taro", "yam"}
    assert {row["evidence_state"] for row in kuk} == {"known_available"}
    assert all(float(row["coordinate_uncertainty_km"]) >= 0.0 for row in evidence)
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        mapping = list(csv.DictReader(handle))
    assert len(mapping) == len(evidence)
    assert {row["evidence_id"] for row in mapping} == {
        row["evidence_id"] for row in evidence
    }
    assert {row["coordinate_transform_sha256"] for row in mapping} == {
        registry["mapping"]["coordinate_transform_sha256"]
    }
    excluded_mapping = [row for row in mapping if not row["location_tag"]]
    assert len(excluded_mapping) == 17
    assert {row["mapping_state"] for row in excluded_mapping} == {
        "excluded_non_location_evidence"
    }
    assert all(row["exclusion_reason_code"] for row in excluded_mapping)
    domains = json.loads(domains_path.read_text(encoding="utf-8"))
    assert domains["boundary_source_sha256"] == registry["domains"][
        "boundary_object_sha256"
    ]
    domain_crops = {
        feature["properties"]["domain_id"]: set(feature["properties"]["crops"])
        for feature in domains["features"]
    }
    assert domain_crops["post_1492_old_world_staples"] == {
        "cassava",
        "maize",
        "white_potato",
    }
    assert domain_crops["post_1493_old_world_phaseolus"] == {"phaseolus_bean"}
    assert domain_crops["post_1492_eurasia_africa_sweet_potato"] == {
        "sweet_potato"
    }
    assert domain_crops["post_1492_new_world_soybean_banana"] == {
        "banana",
        "soybean",
    }
    assert {row["evidence_state"] for row in evidence}.issubset(
        {"known_available", "known_unavailable", "uncertain", "unresolved"}
    )
def test_free_land_effects_cover_all_labeled_goods() -> None:
    labeled_goods = _labeler_goods()

    for effect in ("available_free_land", "abundant_free_land"):
        block = _object_block(CAPACITY_PRESSURE_EFFECTS, effect)
        assert block is not None
        missing = [
            good
            for good in labeled_goods
            if _last_value(block, f"local_{good}_output_modifier") is None
        ]

        assert not missing


def test_free_land_effects_order_plants_before_animal_products() -> None:
    labeled_goods = _labeler_goods()
    plant_goods = tuple(good for good in labeled_goods if good not in ANIMAL_PRODUCT_GOODS)

    for effect in ("available_free_land", "abundant_free_land"):
        block = _object_block(CAPACITY_PRESSURE_EFFECTS, effect)
        assert block is not None
        output_keys = [
            entry.key
            for entry in block.entries
            if entry.key.startswith("local_") and entry.key.endswith("_output_modifier")
        ]
        positions = {key: index for index, key in enumerate(output_keys)}
        last_plant = max(positions[f"local_{good}_output_modifier"] for good in plant_goods)
        first_animal = min(positions[f"local_{good}_output_modifier"] for good in ANIMAL_PRODUCT_GOODS)

        assert last_plant < first_animal


def test_free_land_effects_use_uniform_output_values() -> None:
    expected_values = {
        "available_free_land": 0.30,
        "abundant_free_land": 0.40,
    }

    for effect, expected_value in expected_values.items():
        block = _object_block(CAPACITY_PRESSURE_EFFECTS, effect)
        assert block is not None
        output_values = {
            entry.key: entry.value
            for entry in block.entries
            if entry.key.startswith("local_") and entry.key.endswith("_output_modifier")
        }

        assert output_values
        assert set(output_values.values()) == {expected_value}


def test_irrigation_systems_use_capacity_instead_of_crop_output_bonuses() -> None:
    blueprint_text = (ROOT / "blueprints" / "accepted" / "buildings" / "irrigation_systems.yml").read_text(
        encoding="utf-8"
    )
    irrigated_plant_goods = tuple(
        good
        for good in _labeler_goods()
        if good not in ANIMAL_PRODUCT_GOODS and good not in NON_IRRIGATED_PLANT_GOODS
    )
    present = [
        good
        for good in irrigated_plant_goods
        if f"local_{good}_output_modifier" in blueprint_text
    ]

    assert not present
    profile = tomllib.loads(
        (ROOT / "population_capacity_simulation.toml").read_text(encoding="utf-8")
    )
    expected = profile["infrastructure"]["capacity_per_level"][
        "irrigation_systems"
    ]
    assert f"local_population_capacity = {expected}" in blueprint_text


def test_irrigation_maintenance_is_not_tool_focused() -> None:
    obsolete_goods_demand_patch = (
        MOD_ROOT / "in_game" / "common" / "goods_demand" / "pp_irrigation_maintenance_adjustment.txt"
    )
    building_text = (
        MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_irrigation_systems.txt"
    ).read_text(encoding="utf-8-sig")
    localization_text = (
        MOD_ROOT / "main_menu" / "localization" / "english" / "pp_irrigation_systems_l_english.yml"
    ).read_text(encoding="utf-8-sig")

    assert not obsolete_goods_demand_patch.exists()
    assert "REPLACE:irrigation_systems" in building_text
    assert "unique_production_methods = {" in building_text
    assert "pp_irrigation_maintenance = {" in building_text
    assert not re.search(r"^\s*irrigation_maintenance\s*=", building_text, flags=re.MULTILINE)
    assert re.search(r"^\s*stone\s*=\s*0\.15\s*$", building_text, flags=re.MULTILINE)
    assert re.search(r"^\s*lumber\s*=\s*0\.05\s*$", building_text, flags=re.MULTILINE)
    assert re.search(r"^\s*tools\s*=\s*0\.025\s*$", building_text, flags=re.MULTILINE)
    assert re.search(r'^\s*irrigation_systems_slot_0: "Maintenance"\s*$', localization_text, flags=re.MULTILINE)
    assert re.search(
        r'^\s*pp_irrigation_maintenance: "Irrigation Maintenance"\s*$',
        localization_text,
        flags=re.MULTILINE,
    )
    assert not re.search(r"^\s*irrigation_maintenance:", localization_text, flags=re.MULTILINE)


def test_population_capacity_config_no_longer_patches_static_mod_files() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")

    assert write_population_capacity_files(config, MOD_ROOT, dry_run=True) == []


def test_location_potential_help_localization_is_shared() -> None:
    location_modifier_text = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    modifier_text = LOCATION_MODIFIER_LOCALIZATION.read_text(encoding="utf-8-sig")
    europedia_text = EUROPEDIA_LOCALIZATION.read_text(encoding="utf-8-sig")
    concept_text = LOCATION_POTENTIAL_CONCEPT.read_text(encoding="utf-8-sig")
    modifier_keys = {
        f"pp_loc_{location_tag}"
        for location_tag in _location_modifier_blocks(location_modifier_text)
    }
    name_keys = set(re.findall(r"^\s*STATIC_MODIFIER_NAME_(pp_loc_\S+):", modifier_text, flags=re.MULTILINE))
    desc_keys = set(re.findall(r"^\s*STATIC_MODIFIER_DESC_(pp_loc_\S+):", modifier_text, flags=re.MULTILINE))

    assert re.search(
        r'^\s*pp_location_potential_modifier_name: "\[pp_location_potential\|e\]"$',
        modifier_text,
        flags=re.MULTILINE,
    )
    assert re.search(
        r'^\s*pp_location_potential_modifier_desc: "Population capacity and local output modifiers for this location are calculated from \[pp_location_potential\|e\]\."$',
        modifier_text,
        flags=re.MULTILINE,
    )
    assert "[pp_location_potential|e]" in modifier_text
    assert "pp_location_modifiers_title:" not in modifier_text
    assert "pp_location_modifiers_title_desc:" not in modifier_text
    assert 'STATIC_MODIFIER_NAME_pp_loc_sant_feliu: "$pp_location_potential_modifier_name$"' in modifier_text
    assert 'STATIC_MODIFIER_DESC_pp_loc_sant_feliu: "$pp_location_potential_modifier_desc$"' in modifier_text
    assert name_keys == modifier_keys
    assert desc_keys == modifier_keys
    assert re.search(r"^pp_loc_washita_pp\s*=\s*\{", location_modifier_text, flags=re.MULTILINE)
    assert not re.search(r"^pp_loc_washita\s*=\s*\{", location_modifier_text, flags=re.MULTILINE)
    assert 'STATIC_MODIFIER_DESC_pp_loc_washita: "$pp_location_potential_modifier_desc$"' not in modifier_text
    assert 'STATIC_MODIFIER_DESC_pp_loc_washita_pp: "$pp_location_potential_modifier_desc$"' in modifier_text
    apply_location_text = APPLY_LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    game_start_text = GAME_START.read_text(encoding="utf-8-sig")
    assert "modifier = pp_loc_washita_pp" in apply_location_text
    assert re.search(r"^on_game_start\s*=\s*\{", apply_location_text, flags=re.MULTILINE)
    assert re.search(r"^pp_apply_location_modifiers\s*=\s*\{", apply_location_text, flags=re.MULTILINE)
    assert re.search(r"(?m)^\s*pp_apply_location_modifiers\s*$", apply_location_text)
    assert re.search(r"(?m)^\s*pp_apply_location_modifiers\s*$", game_start_text)

    assert re.search(r"^pp_location_potential\s*=\s*\{", concept_text, flags=re.MULTILINE)
    assert 'game_concept_pp_location_potential: "Location Potential"' in europedia_text
    assert "game_concept_pp_location_potential_desc:" in europedia_text
    assert europedia_text.count("game_concept_pp_location_potential:") == 1
    assert europedia_text.count("game_concept_pp_location_potential_desc:") == 1

    required_terms = (
        "before Development and Irrigation Systems improve it",
        "Topography",
        "Vegetation",
        "Calibrated land area and latitude",
        "Low-input rainfed crop yields",
        "Pasture, livestock, fisheries, wild foods, and apiary products",
        "HYDE historical rainfed land-use evidence",
        "Food imports and the game's starting population are not counted",
        "Development and Irrigation Systems increase this baseline separately",
    )
    missing = [term for term in required_terms if term not in europedia_text]

    assert not missing


def test_development_modifier_preserves_population_and_other_static_values() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    development = _entry_block(static_modifiers.entries, "development")

    assert development is not None
    assert _last_value(development, "local_population_capacity") == 0
    assert _last_value(development, "local_population_capacity_modifier") == 0.00125
    assert _last_value(development, "local_distance_from_capital_speed_propagation") == 0.005
    assert _last_value(development, "local_supply_limit_modifier") == 0.02
    assert _last_value(development, "blockade_force_required") == 0.01
    assert _last_value(development, "local_migration_attraction") == 0.0025


def test_river_flowing_through_modifiers_neutralize_capacity_and_food_bonuses() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    maps = current_modifier_maps(profile)
    expected_fish_capacity = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}
    expected_farm_capacity = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}
    expected_irrigation_capacity = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    obsolete_modifier = "fish_" "natural_capacity_modifier"

    for size in range(1, 6):
        key = f"river_flowing_through_{size}"
        block = _entry_block(static_modifiers.entries, key)

        assert block is not None
        assert maps["static_modifiers"][key]["local_population_capacity_modifier"] == 0
        assert not block.values(obsolete_modifier)
        assert not block.values("fish_capacity")
        assert sum(block.values("fish_capacity_from_river_size")) == expected_fish_capacity[size]
        assert not block.values("farm_capacity")
        assert sum(block.values("farm_capacity_from_river_size")) == expected_farm_capacity[size]
        assert sum(block.values("irrigant_cap_modifier")) == expected_irrigation_capacity[size]
        assert sum(block.values("local_monthly_food_modifier")) == 0
        assert "local_population_capacity" not in maps["static_modifiers"][key]

    assert maps["static_modifiers"]["province_capital"]["local_population_capacity_modifier"] == 0.05
    assert maps["static_modifiers"]["capital"]["local_population_capacity_modifier"] == 0.1


def test_static_feature_population_capacity_is_neutralized_in_merged_maps() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    maps = current_modifier_maps(profile)

    expected_zero = {
        "climates": {
            "tropical": ("location_modifier.local_population_capacity_modifier",),
            "subtropical": ("location_modifier.local_population_capacity_modifier",),
            "oceanic": ("location_modifier.local_population_capacity_modifier",),
            "mediterranean": ("location_modifier.local_population_capacity_modifier",),
            "continental": ("location_modifier.local_population_capacity_modifier",),
            "arctic": ("location_modifier.local_population_capacity_modifier",),
        },
        "location_ranks": {
            "city": (
                "rank_modifier.local_population_capacity",
                "rank_modifier.local_population_capacity_modifier",
            ),
            "town": (
                "rank_modifier.local_population_capacity",
                "rank_modifier.local_population_capacity_modifier",
            ),
        },
        "topography": {
            "mountains": ("location_modifier.local_population_capacity_modifier",),
        },
        "vegetation": {
            "desert": ("location_modifier.local_population_capacity",),
            "sparse": ("location_modifier.local_population_capacity",),
            "grasslands": ("location_modifier.local_population_capacity",),
            "farmland": ("location_modifier.local_population_capacity",),
            "woods": ("location_modifier.local_population_capacity",),
            "forest": ("location_modifier.local_population_capacity",),
            "jungle": ("location_modifier.local_population_capacity",),
        },
        "static_modifiers": {
            "river_flowing_through_1": ("local_population_capacity_modifier",),
            "river_flowing_through_2": ("local_population_capacity_modifier",),
            "river_flowing_through_3": ("local_population_capacity_modifier",),
            "river_flowing_through_4": ("local_population_capacity_modifier",),
            "river_flowing_through_5": ("local_population_capacity_modifier",),
        },
    }
    for collection, objects in expected_zero.items():
        for object_key, modifier_keys in objects.items():
            for modifier_key in modifier_keys:
                assert maps[collection][object_key][modifier_key] == 0

    expected_absent = {
        "climates": {
            "tropical": ("location_modifier.local_population_capacity",),
            "subtropical": ("location_modifier.local_population_capacity",),
            "oceanic": ("location_modifier.local_population_capacity",),
            "arid": ("location_modifier.local_population_capacity",),
            "cold_arid": ("location_modifier.local_population_capacity",),
            "mediterranean": ("location_modifier.local_population_capacity",),
            "continental": ("location_modifier.local_population_capacity",),
            "arctic": ("location_modifier.local_population_capacity",),
        },
        "topography": {
            "flatland": ("location_modifier.local_population_capacity",),
            "mountains": ("location_modifier.local_population_capacity",),
            "hills": ("location_modifier.local_population_capacity",),
            "plateau": ("location_modifier.local_population_capacity",),
            "wetlands": ("location_modifier.local_population_capacity",),
            "salt_pans": ("location_modifier.local_population_capacity",),
            "atoll": ("location_modifier.local_population_capacity",),
        },
        "static_modifiers": {
            "coastal": ("local_population_capacity",),
            "total_population": ("local_population_capacity",),
            "province_capital": ("local_population_capacity",),
            "river_flowing_through_1": ("local_population_capacity",),
            "river_flowing_through_2": ("local_population_capacity",),
            "river_flowing_through_3": ("local_population_capacity",),
            "river_flowing_through_4": ("local_population_capacity",),
            "river_flowing_through_5": ("local_population_capacity",),
            "adjacent_to_lake": ("local_population_capacity",),
        },
    }
    for collection, objects in expected_absent.items():
        for object_key, modifier_keys in objects.items():
            object_map = maps.get(collection, {}).get(object_key, {})
            for modifier_key in modifier_keys:
                assert modifier_key not in object_map


def test_capacity_pressure_effects_are_merged_by_parser() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    impacts = capacity_effect_inventory(profile)

    for effect_key in ("available_free_land", "abundant_free_land", "overpopulation"):
        block = _object_block(CAPACITY_PRESSURE_EFFECTS, effect_key)
        assert block is not None
        for entry in block.entries:
            if entry.key == "game_data":
                continue
            assert any(
                impact.effect_key == effect_key
                and impact.path == f"{effect_key}.{entry.key}"
                and impact.value == _config_scalar_text(entry.value)
                and Path(impact.source_file).name == CAPACITY_PRESSURE_EFFECTS.name
                and impact.source_mode == "TRY_REPLACE"
                for impact in impacts
            ), f"missing merged capacity-pressure effect replacement for {effect_key}.{entry.key}"


def test_capacity_pressure_effects_are_hand_authored_replacements() -> None:
    text = CAPACITY_PRESSURE_EFFECTS.read_text(encoding="utf-8-sig")

    assert "<managed by Prosper or Perish population capacity pipeline>" not in text
    assert "Edit population_capacity.toml, not this file" not in text
    for object_key in ("available_free_land", "abundant_free_land", "overpopulation"):
        assert text.count(f"TRY_REPLACE:{object_key}") == 1
        for path in (MOD_ROOT / "main_menu" / "common" / "static_modifiers").glob("*.txt"):
            if path.name == CAPACITY_PRESSURE_EFFECTS.name:
                continue
            assert not _file_has_object(path, object_key), f"{object_key} is patched outside capacity pressure file"


def test_population_capacity_config_does_not_own_static_mod_files() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")

    assert config.set_values == {}
    assert config.whole_blocks == {}


def test_capacity_pressure_effects_are_defined_only_in_pressure_file() -> None:
    offenders: list[str] = []
    for path in MOD_ROOT.rglob("*.txt"):
        if path.name == "pp_capacity_pressure_effects.txt":
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for block in CAPACITY_EFFECT_BLOCKS:
            if block in text:
                offenders.append(str(path.relative_to(MOD_ROOT)))
                break

    assert not offenders


def test_generated_location_modifiers_include_one_population_capacity_per_location() -> None:
    text = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    blocks = _location_modifier_blocks(text)

    assert blocks
    for name, body in blocks.items():
        assert body.count("local_population_capacity =") == 1, name


def test_generated_raw_good_output_modifiers_respect_configured_floor() -> None:
    from goods_labeler.location_templates import (
        apply_location_template_overlay,
        load_current_location_templates,
    )

    floor = -0.2
    baseline = pl.read_parquet(LABELING_BASELINE)
    templates, _source = load_current_location_templates(
        load_order_path=ROOT / "constructor.load_order.toml"
    )
    current_locations = apply_location_template_overlay(baseline, templates)
    raw_by_location = {
        str(row["location_tag"]): str(row["raw_material"])
        for row in current_locations.select("location_tag", "raw_material")
        .drop_nulls("raw_material")
        .to_dicts()
    }
    blocks = _location_modifier_blocks(LOCATION_MODIFIERS.read_text(encoding="utf-8-sig"))

    assert raw_by_location["rethymno"] == "saffron"

    rethymno_body = blocks["rethymno"]
    assert re.search(
        r"^\s*local_cotton_output_modifier\s*=\s*-0\.70\s*$",
        rethymno_body,
        flags=re.MULTILINE,
    )
    rethymno_saffron = re.search(
        r"^\s*local_saffron_output_modifier\s*=\s*([-+]?\d+(?:\.\d+)?)\s*$",
        rethymno_body,
        flags=re.MULTILINE,
    )
    assert rethymno_saffron is not None
    assert float(rethymno_saffron.group(1)) >= floor

    checked = 0
    violations: list[str] = []
    for location_tag, raw_material in raw_by_location.items():
        body = blocks.get(location_tag) or blocks.get(f"{location_tag}_pp")
        if body is None:
            continue
        match = re.search(
            rf"^\s*local_{re.escape(raw_material)}_output_modifier\s*=\s*([-+]?\d+(?:\.\d+)?)\s*$",
            body,
            flags=re.MULTILINE,
        )
        if match is None:
            continue
        checked += 1
        value = float(match.group(1))
        if value < floor:
            violations.append(f"{location_tag}:{raw_material}={value}")

    assert checked > 10_000
    assert not violations[:20]


def test_generated_population_capacity_values_stay_in_v1_bounds() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    capacities = _generated_location_capacities()

    assert len(capacities) > 20_000
    if config.capacity_scale.deployment_mode == "normalized":
        assert min(capacities.values()) >= config.capacity_scale.minimum
        assert max(capacities.values()) <= config.capacity_scale.maximum
        assert any(value >= config.capacity_scale.maximum for value in capacities.values())
        assert any(value <= config.capacity_scale.minimum for value in capacities.values())
    else:
        # Raw mode intentionally bypasses the gameplay band and emits the
        # accepted absolute p50 headcount for inspection.
        assert min(capacities.values()) >= 0
        assert max(capacities.values()) > config.capacity_scale.maximum
        assert any(value > config.capacity_scale.maximum for value in capacities.values())


def test_generated_population_capacity_benchmark_rollups_are_available() -> None:
    capacities = _generated_location_capacities()
    capacity_df = pl.DataFrame(
        {
            "location_tag": list(capacities.keys()),
            "local_population_capacity": list(capacities.values()),
        }
    )
    baseline_raw = pl.read_parquet(LABELING_BASELINE)
    baseline = baseline_raw.select(
        [column for column in ("location_tag", *BENCHMARK_GROUPS) if column in baseline_raw.columns]
    )
    joined = baseline.join(capacity_df, on="location_tag", how="inner")

    assert joined.height >= len(capacities) - 20
    for group_key in BENCHMARK_GROUPS:
        grouped = (
            joined.group_by(group_key)
            .agg(
                pl.len().alias("locations"),
                pl.col("local_population_capacity").mean().alias("capacity_mean"),
            )
            .filter(pl.col(group_key).is_not_null())
        )
        assert grouped.height > 0, group_key
        assert grouped["locations"].sum() > 0, group_key


def test_benchmark_registry_documents_training_constraints_and_rejections() -> None:
    benchmarks = load_population_benchmarks(POPULATION_BENCHMARKS)
    by_id = {benchmark.anchor_id: benchmark for benchmark in benchmarks}

    assert len(benchmarks) >= 12
    assert POPULATION_BENCHMARKS.exists()
    assert by_id["england_1290_1315"].role == "scale_anchor"
    assert by_id["england_1290_1315"].review_status == "vetted"
    assert by_id["england_1290_1315"].trains_scale
    assert by_id["england_1290_1315"].capacity_low == 4_400_000
    assert by_id["england_1290_1315"].capacity_high > 6_000_000
    assert by_id["tikopia_food_area_capacity"].role == "validation_only"
    assert by_id["yuan_china_1337"].role == "excluded"
    assert by_id["nile_egypt_1337"].review_status == "rejected"
    assert all(benchmark.sources for benchmark in benchmarks)
    assert [
        benchmark.anchor_id for benchmark in benchmarks if benchmark.trains_scale
    ] == ["england_1290_1315"]


def test_benchmark_registry_maps_every_entry_and_never_trains_exclusions() -> None:
    benchmarks = load_population_benchmarks(POPULATION_BENCHMARKS)
    baseline = pl.read_parquet(LABELING_BASELINE)
    rows = audit_population_benchmarks(benchmarks, baseline)
    by_id = {row["anchor_id"]: row for row in rows}

    unmapped = {row["anchor_id"] for row in rows if row["issues"] == "selector maps no locations"}
    assert unmapped == {
        "medieval_europe_173_cities",
        "tikopia_food_area_capacity",
        "amazon_late_holocene_logistic_pressure",
        "casarabe_llanos_de_mojos_capacity",
    }
    assert by_id["england_1290_1315"]["status"] == "pass"
    assert by_id["yuan_china_1337"]["status"] == "excluded"
    assert by_id["broad_africa_estimates"]["status"] == "excluded"
    assert by_id["tikopia_food_area_capacity"]["status"] == "blocked"


def test_irrigation_technology_registry_is_cited_and_never_encodes_multipliers() -> None:
    path = ROOT / "population_capacity_technology_registry.toml"
    registry = tomllib.loads(path.read_text(encoding="utf-8"))
    systems = registry["systems"]
    by_id = {system["system_id"]: system for system in systems}

    assert registry["target_year"] == 1337
    assert not [key for system in systems for key in system if "multiplier" in key.casefold()]
    assert by_id["nile_basin_gravity_and_basin_irrigation"]["sources"]
    assert by_id["southern_mesopotamian_canal_landscape"]["sources"]
    assert by_id["persian_qanat"]["review_status"] == "vetted_technology"
    assert by_id["indus_and_south_asian_irrigation"]["review_status"] == "vetted_technology"
    assert by_id["indus_and_south_asian_irrigation"]["sources"]
    assert by_id["central_asian_oasis_and_mountain_irrigation"]["review_status"] == "vetted_technology"
    assert by_id["central_asian_oasis_and_mountain_irrigation"]["sources"]
    assert by_id["east_asian_wet_rice_systems"]["review_status"] == "vetted_technology"
    assert by_id["east_asian_wet_rice_systems"]["sources"]
    assert all(system["available_by"] <= 1337 for system in systems)


def test_profile_capacity_table_matches_deployed_values() -> None:
    with PROFILE_CAPACITY.open("r", encoding="utf-8-sig", newline="") as handle:
        profile_rows = list(csv.DictReader(handle))
    deployed = _generated_location_capacities()

    assert len(profile_rows) == 20_929
    normalize = lambda tag: (tag[:-3] if tag.endswith("_pp") else tag).casefold()
    profile_normalized = {
        normalize(str(row["location_tag"])): int(row["population_capacity"])
        for row in profile_rows
    }
    deployed_normalized = {normalize(tag): value for tag, value in deployed.items()}
    assert set(profile_normalized) == set(deployed_normalized)
    assert profile_normalized == deployed_normalized


def test_location_geometry_inputs_are_available_for_external_target_mapping() -> None:
    baseline = pl.read_parquet(LABELING_BASELINE)
    map_data = ROOT / "constructor.load_order.toml"
    locations_png = Path("/mnt/c/Games/steamapps/common/Europa Universalis V/game/in_game/map_data/locations.png")

    assert map_data.exists()
    assert locations_png.exists()
    assert baseline["named_location_hex"].n_unique() == baseline["location_tag"].n_unique()
    assert baseline["location_size"].min() > 0
    assert {"soil_quality", "has_river", "is_adjacent_to_lake"}.issubset(baseline.columns)


def test_population_capacity_control_points_match_known_locations_and_fit_existing_geometry() -> None:
    control_points = load_control_points(CONTROL_POINTS)
    baseline = pl.read_parquet(LABELING_BASELINE)
    missing = control_points.join(baseline.select("location_tag"), on="location_tag", how="anti")

    assert control_points.height >= 150
    assert missing.is_empty()

    geometry_path = ROOT / "artifacts" / "data" / "population_capacity" / "location_geometry.parquet"
    if not geometry_path.exists():
        return
    geometry = pl.read_parquet(geometry_path)
    _transform, residuals = fit_transform(geometry, control_points)

    assert residuals["residual_degrees"].median() <= 2.5
    assert residuals["residual_degrees"].quantile(0.95) <= 6.0
    for tag in (
        "paris",
        "cairo",
        "alexandria",
        "aswan",
        "constantinople",
        "hangzhou",
        "kyoto",
        "daha",
        "tenochtitlan",
        "quito",
    ):
        assert residuals.filter(pl.col("location_tag") == tag)["residual_degrees"].item() <= 6.0


def _labeler_goods() -> tuple[str, ...]:
    evaluator_root = LABELING_ROOT / "GoodsEvaluator"
    return tuple(
        sorted(
            path.name
            for path in evaluator_root.iterdir()
            if path.is_dir() and (path / "config.yaml").exists()
        )
    )


def _location_modifier_blocks(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"^pp_loc_(.+?)\s*=\s*\{", text, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[match.group(1)] = text[match.start() : end]
    return blocks


def _generated_location_capacities() -> dict[str, int]:
    capacities: dict[str, int] = {}
    for name, body in _location_modifier_blocks(LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")).items():
        match = re.search(r"^\s*local_population_capacity\s*=\s*(\d+)\s*$", body, flags=re.MULTILINE)
        assert match is not None, name
        capacities[name] = int(match.group(1))
    return capacities


def _file_has_object(path: Path, object_key: str) -> bool:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return any(
        (match := STATIC_MODIFIER_BLOCK.match(line)) and match.group("key") == object_key
        for line in text.splitlines()
    )


def _object_block(path: Path, object_key: str) -> CList | None:
    for entry in parse_file(path).entries:
        key = entry.key.split(":", 1)[-1]
        if key == object_key and isinstance(entry.value, CList):
            return entry.value
    return None


def _entry_block(entries, key: str) -> CList | None:
    for entry in entries:
        if entry.key == key and isinstance(entry.value, CList):
            return entry.value
    return None


def _last_value(block: CList, key: str):
    values = block.values(key)
    return values[-1] if values else None


def _config_scalar_text(value: str | int | float | bool) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, int | float):
        return f"{value:g}"
    return value
