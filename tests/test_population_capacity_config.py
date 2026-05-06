import re
from pathlib import Path

import polars as pl
from eu5gameparser.clausewitz.parser import parse_file
from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_population_capacity.analysis import (
    capacity_effect_inventory,
    current_modifier_maps,
)
from prosper_or_perish_population_capacity.calibration import (
    evaluate_saturation_anchors,
    load_generated_capacity_frame,
    load_saturation_anchors,
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
SATURATION_ANCHORS = ROOT / "population_capacity_saturation_anchors.toml"
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
    assert config.capacity_scale.minimum == 4
    assert config.capacity_scale.maximum == 100
    assert config.calibration.historical_population_policy == "saturation_anchors_only"
    assert config.calibration.saturation_anchors == "population_capacity_saturation_anchors.toml"
    assert config.calibration.land_potential_sources == ("gaez_v4", "hyde", "archaeoglobe")
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


def test_irrigation_systems_cover_all_irrigated_plant_goods() -> None:
    blueprint_text = (ROOT / "blueprints" / "accepted" / "buildings" / "irrigation_systems.yml").read_text(
        encoding="utf-8"
    )
    irrigated_plant_goods = tuple(
        good
        for good in _labeler_goods()
        if good not in ANIMAL_PRODUCT_GOODS and good not in NON_IRRIGATED_PLANT_GOODS
    )
    missing = [
        good
        for good in irrigated_plant_goods
        if f"local_{good}_output_modifier" not in blueprint_text
    ]

    assert not missing


def test_irrigation_maintenance_is_not_tool_focused() -> None:
    obsolete_goods_demand_patch = (
        MOD_ROOT / "in_game" / "common" / "goods_demand" / "pp_irrigation_maintenance_adjustment.txt"
    )
    building_text = (
        MOD_ROOT / "in_game" / "common" / "building_types" / "pp_irrigation_systems.txt"
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
    assert "modifier = pp_loc_washita_pp" in APPLY_LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")

    assert re.search(r"^pp_location_potential\s*=\s*\{", concept_text, flags=re.MULTILINE)
    assert 'game_concept_pp_location_potential: "Location Potential"' in europedia_text
    assert "game_concept_pp_location_potential_desc:" in europedia_text
    assert europedia_text.count("game_concept_pp_location_potential:") == 1
    assert europedia_text.count("game_concept_pp_location_potential_desc:") == 1

    required_terms = (
        "Topography",
        "Climate",
        "Vegetation",
        "River access",
        "Lake access",
        "Coastal access",
        "Location RGO",
        "#T Out-of-game maps and evidence:#!",
        "$BULLET$ Soil data",
        "GAEZ crop potential and suitability maps",
        "HYDE historical population coverage",
        "Freshwater food support maps",
        "Marine food support maps",
        "Livestock food support maps",
        "Plant food support maps",
        "Wild subsistence support maps",
        "Land-use confidence maps",
        "Water confidence maps",
        "The modelling and pipeline for this are in the GitHub repo",
    )
    missing = [term for term in required_terms if term not in europedia_text]

    assert not missing


def test_development_modifier_preserves_population_and_other_static_values() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    development = _entry_block(static_modifiers.entries, "development")

    assert development is not None
    assert _last_value(development, "local_population_capacity") == 0.25
    assert _last_value(development, "local_population_capacity_modifier") == 0.02
    assert _last_value(development, "local_distance_from_capital_speed_propagation") == 0.005
    assert _last_value(development, "local_supply_limit_modifier") == 0.02
    assert _last_value(development, "blockade_force_required") == 0.01
    assert _last_value(development, "local_migration_attraction") == 0.0025


def test_building_levels_modifier_adds_population_capacity() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    building_levels = _entry_block(static_modifiers.entries, "building_levels")

    assert building_levels is not None
    assert _last_value(building_levels, "local_population_capacity") == 0.1
    assert _last_value(building_levels, "local_road_building_time") == 0.01
    assert _last_value(building_levels, "local_build_new_buildings_cost") == 0.05


def test_river_flowing_through_modifiers_neutralize_capacity_and_food_bonuses() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    maps = current_modifier_maps(profile)

    for size in range(1, 6):
        key = f"river_flowing_through_{size}"
        block = _entry_block(static_modifiers.entries, key)

        assert block is not None
        assert maps["static_modifiers"][key]["local_population_capacity_modifier"] == 0
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


def test_generated_population_capacity_values_stay_in_v1_bounds() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    capacities = _generated_location_capacities()

    assert len(capacities) > 20_000
    assert min(capacities.values()) >= config.capacity_scale.minimum
    assert max(capacities.values()) <= config.capacity_scale.maximum
    assert any(value >= 100 for value in capacities.values())
    assert any(value <= 10 for value in capacities.values())


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


def test_saturation_anchor_dataset_loads_and_documents_initial_training_constraints() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    anchors = load_saturation_anchors(ROOT / config.calibration.saturation_anchors)
    by_id = {anchor.id: anchor for anchor in anchors}

    assert len(anchors) >= 10
    assert SATURATION_ANCHORS.exists()
    assert by_id["nile_lower_egypt"].scope == "area"
    assert by_id["nile_lower_egypt"].key == "lower_egypt_area"
    assert by_id["bengal_delta_core"].use_role == "scale_anchor"
    assert by_id["java_core"].capacity_mean_floor == 75
    assert by_id["trade_city_population_exclusion"].confidence == "excluded"
    assert all(anchor.population_or_density_estimate for anchor in anchors)
    assert all(anchor.sources for anchor in anchors)


def test_saturation_anchor_report_covers_game_scopes_without_training_on_exclusions() -> None:
    anchors = load_saturation_anchors(SATURATION_ANCHORS)
    capacity_frame = load_generated_capacity_frame(LOCATION_MODIFIERS, baseline_path=LABELING_BASELINE)
    rows = evaluate_saturation_anchors(anchors, capacity_frame)
    by_id = {row["id"]: row for row in rows}

    assert not [row for row in rows if row["status"] == "missing_scope_members"]
    assert by_id["nile_lower_egypt"]["status"] == "below_mean_floor"
    assert by_id["lower_yangtze_jiangnan"]["status"] == "below_mean_floor"
    assert by_id["bengal_delta_core"]["status"] == "below_mean_floor"
    assert by_id["trade_city_population_exclusion"]["training_constraint"] is False
    assert by_id["trade_city_population_exclusion"]["status"] == "excluded"
    assert by_id["java_core"]["locations"] > 0


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
