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
from prosper_or_perish_population_capacity.config import COLLECTIONS, load_pipeline_config
from prosper_or_perish_population_capacity.extraction import STATIC_MODIFIER_BLOCK
from prosper_or_perish_population_capacity.geometry_calibration import fit_transform, load_control_points
from prosper_or_perish_population_capacity.merge import load_collection, profile_from
from prosper_or_perish_population_capacity.render import planned_population_capacity_writes


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
LABELING_ROOT = ROOT.parent / "ProsperOrPerishLabelingPipeline"
LABELING_BASELINE = LABELING_ROOT / "base_data" / "locations_with_raw_material.parquet"
LOCATION_MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifiers.txt"
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
    assert config.calibration.historical_population_policy == "saturation_anchors_only"
    assert config.calibration.saturation_anchors == "population_capacity_saturation_anchors.toml"
    assert config.calibration.land_potential_sources == ("gaez_v4", "hyde", "archaeoglobe")
    assert "flatland" not in config.set_values.get("topography", {})
    assert config.set_values["topography"]["mountains"]["local_population_capacity_modifier"] == 0.5
    assert config.set_values["climates"]["continental"]["local_population_capacity_modifier"] == -0.5
    assert "province_capital" not in config.set_values["static_modifiers"]
    assert config.feature_capacity_adjustments.enabled is False
    assert config.feature_capacity_adjustments.removed_values["topography"]["flatland"]["local_population_capacity"] == 88
    assert config.feature_capacity_adjustments.vanilla_values["vegetation"]["farmland"]["local_population_capacity"] == 100
    assert config.whole_blocks["static_modifiers"]["available_free_land"]["local_monthly_food"] == 3
    assert config.whole_blocks["static_modifiers"]["abundant_free_land"]["local_monthly_food"] == 6
    assert config.whole_blocks["static_modifiers"]["overpopulation"]["cap_maximum_population_growth_at_zero"] is True
    assert "[values." not in config_text
    assert "[capacity_effects." not in config_text
    assert "[inject_values." not in config_text
    assert "[replace_static_modifiers." not in config_text


def test_free_land_effects_cover_all_labeled_goods() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    labeled_goods = _labeler_goods()

    for effect in ("available_free_land", "abundant_free_land"):
        modifiers = config.whole_blocks["static_modifiers"][effect]
        missing = [
            good
            for good in labeled_goods
            if f"local_{good}_output_modifier" not in modifiers
        ]

        assert not missing


def test_free_land_effects_order_plants_before_animal_products() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    labeled_goods = _labeler_goods()
    plant_goods = tuple(good for good in labeled_goods if good not in ANIMAL_PRODUCT_GOODS)

    for effect in ("available_free_land", "abundant_free_land"):
        output_keys = [
            key
            for key in config.whole_blocks["static_modifiers"][effect]
            if key.startswith("local_") and key.endswith("_output_modifier")
        ]
        positions = {key: index for index, key in enumerate(output_keys)}
        last_plant = max(positions[f"local_{good}_output_modifier"] for good in plant_goods)
        first_animal = min(positions[f"local_{good}_output_modifier"] for good in ANIMAL_PRODUCT_GOODS)

        assert last_plant < first_animal


def test_population_capacity_config_plans_managed_outputs() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    paths = {write.path.relative_to(MOD_ROOT).as_posix() for write in planned_population_capacity_writes(config, MOD_ROOT)}

    assert "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt" in paths
    assert "in_game/common/topography/pp_population_capacity_topography.txt" not in paths
    assert "main_menu/common/static_modifiers/pp_population_capacity_static_modifiers.txt" not in paths


def test_set_values_are_written_in_place_for_dynamic_config() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    managed_names = _managed_set_value_output_names(config)

    for collection, objects in config.set_values.items():
        for object_key, modifiers in objects.items():
            owner = _single_non_managed_owner(collection, object_key, managed_names)
            block = _object_block(owner, object_key)
            assert block is not None, f"missing owner block for {collection}.{object_key}"
            for raw_key, expected_value in modifiers.items():
                values = _values_at_path(block, _configured_path(collection, raw_key))
                assert values == [expected_value], f"{collection}.{object_key}.{raw_key} is not set exactly"

    development = _object_block(_single_non_managed_owner("static_modifiers", "development", managed_names), "development")
    assert development is not None
    assert _last_value(development, "local_supply_limit_modifier") == 0.02
    assert _last_value(development, "local_migration_attraction") == 0.0025


def test_set_values_do_not_generate_managed_patch_blocks() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")

    for collection, objects in config.set_values.items():
        output = config.outputs.get(collection)
        if not output:
            continue
        path = MOD_ROOT / output
        assert not path.exists(), f"{output} must not be generated for set_values"
        if path.exists():
            text = path.read_text(encoding="utf-8-sig")
            for object_key in objects:
                assert f"TRY_INJECT:{object_key}" not in text


def test_configured_static_modifier_capacity_offsets_neutralize_vanilla_sum() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    maps = current_modifier_maps(profile)

    for object_key, modifiers in config.set_values["static_modifiers"].items():
        for modifier_key, expected_value in modifiers.items():
            assert expected_value < 0
            assert maps["static_modifiers"][object_key][modifier_key] == 0


def test_development_set_value_preserves_non_population_static_modifier_values() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    development = _entry_block(static_modifiers.entries, "development")

    assert development is not None
    assert _last_value(development, "local_population_capacity") is None
    assert _last_value(development, "local_distance_from_capital_speed_propagation") == 0.005
    assert _last_value(development, "local_supply_limit_modifier") == 0.02
    assert _last_value(development, "blockade_force_required") == 0.01
    assert _last_value(development, "local_migration_attraction") == 0.0025


def test_river_flowing_through_set_value_resolves_to_configured_modifier() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    maps = current_modifier_maps(profile)

    assert maps["static_modifiers"]["river_flowing_through"]["local_population_capacity_modifier"] == 0
    assert "local_population_capacity" not in maps["static_modifiers"]["river_flowing_through"]
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
            "river_flowing_through": ("local_population_capacity_modifier",),
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
            "building_levels": ("local_population_capacity",),
            "total_population": ("local_population_capacity",),
            "development": ("local_population_capacity",),
            "province_capital": ("local_population_capacity",),
            "river_flowing_through": ("local_population_capacity",),
            "adjacent_to_lake": ("local_population_capacity",),
        },
    }
    for collection, objects in expected_absent.items():
        for object_key, modifier_keys in objects.items():
            object_map = maps.get(collection, {}).get(object_key, {})
            for modifier_key in modifier_keys:
                assert modifier_key not in object_map


def test_configured_capacity_pressure_effects_are_merged_by_parser() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    impacts = capacity_effect_inventory(profile)

    for effect_key in ("available_free_land", "abundant_free_land", "overpopulation"):
        for modifier_key, expected_value in config.whole_blocks["static_modifiers"][effect_key].items():
            assert any(
                impact.effect_key == effect_key
                and impact.path == f"{effect_key}.{modifier_key}"
                and impact.value == _config_scalar_text(expected_value)
                and Path(impact.source_file).name == MANAGED_CAPACITY_EFFECT_FILE
                and impact.source_mode == "TRY_REPLACE"
                for impact in impacts
            ), f"missing merged capacity-pressure effect replacement for {effect_key}.{modifier_key}"


def test_whole_blocks_are_only_in_managed_replacement_file() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    managed_path = MOD_ROOT / config.outputs["capacity_effects"]
    managed_text = managed_path.read_text(encoding="utf-8-sig")
    whole_blocks = config.whole_blocks["static_modifiers"]

    for object_key, modifiers in whole_blocks.items():
        assert managed_text.count(f"TRY_REPLACE:{object_key}") == 1
        for modifier_key, expected_value in modifiers.items():
            assert f"{modifier_key} = {_config_scalar_text(expected_value)}" in managed_text
        for path in (MOD_ROOT / "main_menu" / "common" / "static_modifiers").glob("*.txt"):
            if path.name == managed_path.name:
                continue
            assert not _file_has_object(path, object_key), f"{object_key} is patched outside managed whole-block file"


def test_population_capacity_set_values_have_no_managed_patch_files() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")

    for collection in config.set_values:
        output = config.outputs.get(collection)
        if output:
            assert not (MOD_ROOT / output).exists()


def test_capacity_pressure_effects_are_managed_only() -> None:
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
    capacities = _generated_location_capacities()

    assert len(capacities) > 20_000
    assert min(capacities.values()) >= 0
    assert max(capacities.values()) <= 120
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
    assert by_id["nile_lower_egypt"]["status"] == "pass"
    assert by_id["lower_yangtze_jiangnan"]["status"] == "pass"
    assert by_id["bengal_delta_core"]["status"] == "pass"
    assert by_id["trade_city_population_exclusion"]["training_constraint"] is False
    assert by_id["trade_city_population_exclusion"]["status"] == "excluded"
    assert by_id["java_core"]["locations"] > 0


def test_location_geometry_inputs_are_available_for_external_target_mapping() -> None:
    baseline = pl.read_parquet(LABELING_BASELINE)
    map_data = ROOT / "constructor.load_order.toml"
    locations_png = Path("C:/Games/steamapps/common/Europa Universalis V/game/in_game/map_data/locations.png")

    assert map_data.exists()
    assert locations_png.exists()
    assert baseline["named_location_hex"].n_unique() == baseline["location_tag"].n_unique()
    assert baseline["location_size"].min() > 0
    assert {"soil_quality", "has_river", "is_adjacent_to_lake"}.issubset(baseline.columns)


def test_population_capacity_control_points_match_known_locations_and_fit_existing_geometry() -> None:
    control_points = load_control_points(CONTROL_POINTS)
    baseline = pl.read_parquet(LABELING_BASELINE)
    missing = control_points.join(baseline.select("location_tag"), on="location_tag", how="anti")

    assert control_points.height >= 60
    assert missing.is_empty()

    geometry_path = ROOT / "artifacts" / "data" / "population_capacity" / "location_geometry.parquet"
    if not geometry_path.exists():
        return
    geometry = pl.read_parquet(geometry_path)
    _transform, residuals = fit_transform(geometry, control_points)

    assert residuals["residual_degrees"].median() <= 2.5
    assert residuals["residual_degrees"].quantile(0.95) <= 6.0
    for tag in ("paris", "cairo", "constantinople", "hangzhou", "kyoto", "daha", "tenochtitlan", "quito"):
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


def _managed_set_value_output_names(config) -> set[str]:
    return {
        Path(config.outputs[collection]).name
        for collection in config.set_values
        if collection in config.outputs
    }


def _single_non_managed_owner(collection: str, object_key: str, managed_names: set[str]) -> Path:
    directory = MOD_ROOT / _collection_relative_dir(collection)
    owners = [
        path
        for path in sorted(directory.glob("*.txt"))
        if path.name not in managed_names and _file_has_object(path, object_key)
    ]
    assert len(owners) == 1, f"expected one owner for {collection}.{object_key}, found {owners}"
    return owners[0]


def _collection_relative_dir(collection: str) -> Path:
    if collection == "static_modifiers":
        return Path("main_menu/common/static_modifiers")
    return Path("in_game/common") / COLLECTIONS[collection].relative_dir


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


def _configured_path(collection: str, raw_key: str) -> tuple[str, ...]:
    path = tuple(raw_key.split("."))
    if len(path) > 1:
        return path
    nested_path = COLLECTIONS.get(collection).nested_path if collection in COLLECTIONS else ()
    return (*nested_path, raw_key)


def _values_at_path(block: CList, path: tuple[str, ...]):
    current = block
    for key in path[:-1]:
        nested = _last_value(current, key)
        assert isinstance(nested, CList), f"missing nested block {'.'.join(path)}"
        current = nested
    return current.values(path[-1])


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
