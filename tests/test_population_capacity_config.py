from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList

from prosper_or_perish_population_capacity.analysis import (
    capacity_effect_inventory,
    population_modifier_inventory,
)
from prosper_or_perish_population_capacity.config import load_pipeline_config
from prosper_or_perish_population_capacity.merge import load_collection, profile_from
from prosper_or_perish_population_capacity.render import planned_population_capacity_writes


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
LABELING_ROOT = ROOT.parent / "ProsperOrPerishLabelingPipeline"
POPULATION_CAPACITY_KEYS = (
    "global_population_capacity_modifier",
    "local_population_capacity_modifier",
    "local_population_capacity",
)
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
MANAGED_STATIC_MODIFIER_FILE = "pp_population_capacity_static_modifiers.txt"
MANAGED_CAPACITY_EFFECT_FILE = "pp_capacity_pressure_effects.txt"


def test_population_capacity_config_loads() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    config_text = (ROOT / "population_capacity.toml").read_text(encoding="utf-8")

    assert config.generated_label == "Prosper or Perish"
    assert config.managed_write_mode == "mod_root"
    assert config.injected_values["topography"]["flatland"]["local_population_capacity"] == 88
    assert config.injected_values["climates"]["continental"]["local_population_capacity_modifier"] == -0.5
    assert config.replaced_static_modifiers["available_free_land"]["local_monthly_food"] == 3
    assert config.replaced_static_modifiers["abundant_free_land"]["local_monthly_food"] == 6
    assert config.replaced_static_modifiers["overpopulation"]["cap_maximum_population_growth_at_zero"] is True
    assert "[values." not in config_text
    assert "[capacity_effects." not in config_text


def test_free_land_effects_cover_all_labeled_goods() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    labeled_goods = _labeler_goods()

    for effect in ("available_free_land", "abundant_free_land"):
        modifiers = config.replaced_static_modifiers[effect]
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
            for key in config.replaced_static_modifiers[effect]
            if key.startswith("local_") and key.endswith("_output_modifier")
        ]
        positions = {key: index for index, key in enumerate(output_keys)}
        last_plant = max(positions[f"local_{good}_output_modifier"] for good in plant_goods)
        first_animal = min(positions[f"local_{good}_output_modifier"] for good in ANIMAL_PRODUCT_GOODS)

        assert last_plant < first_animal


def test_population_capacity_config_plans_managed_outputs() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    paths = {write.path.relative_to(MOD_ROOT).as_posix() for write in planned_population_capacity_writes(config, MOD_ROOT)}

    assert "in_game/common/topography/pp_population_capacity_topography.txt" in paths
    assert "main_menu/common/static_modifiers/pp_population_capacity_static_modifiers.txt" in paths
    assert "main_menu/common/static_modifiers/pp_capacity_pressure_effects.txt" in paths


def test_configured_static_modifier_values_are_merged_by_parser() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    impacts = population_modifier_inventory(profile)

    for object_key, modifiers in config.injected_values["static_modifiers"].items():
        for modifier_key, expected_value in modifiers.items():
            assert any(
                impact.collection == "static_modifiers"
                and impact.object_key == object_key
                and impact.modifier_key == modifier_key
                and impact.value == expected_value
                and Path(impact.source_file).name == MANAGED_STATIC_MODIFIER_FILE
                and impact.source_mode == "TRY_INJECT"
                for impact in impacts
            ), f"missing merged static modifier injection for {object_key}.{modifier_key}"


def test_development_injection_preserves_non_population_static_modifier_values() -> None:
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    static_modifiers = load_collection(profile, "static_modifiers")
    development = _entry_block(static_modifiers.entries, "development")

    assert development is not None
    assert _last_value(development, "local_population_capacity") == 2
    assert _last_value(development, "local_distance_from_capital_speed_propagation") == 0.005
    assert _last_value(development, "local_supply_limit_modifier") == 0.02
    assert _last_value(development, "blockade_force_required") == 0.01
    assert _last_value(development, "local_migration_attraction") == 0.0025


def test_configured_capacity_pressure_effects_are_merged_by_parser() -> None:
    config = load_pipeline_config(ROOT / "population_capacity.toml")
    profile = profile_from("constructor", ROOT / "constructor.load_order.toml")
    impacts = capacity_effect_inventory(profile)

    for effect_key in ("available_free_land", "abundant_free_land", "overpopulation"):
        for modifier_key, expected_value in config.replaced_static_modifiers[effect_key].items():
            assert any(
                impact.effect_key == effect_key
                and impact.path == f"{effect_key}.{modifier_key}"
                and impact.value == _config_scalar_text(expected_value)
                and Path(impact.source_file).name == MANAGED_CAPACITY_EFFECT_FILE
                and impact.source_mode == "TRY_REPLACE"
                for impact in impacts
            ), f"missing merged capacity-pressure effect replacement for {effect_key}.{modifier_key}"


def test_population_capacity_txt_modifiers_are_managed_only() -> None:
    offenders: list[str] = []
    for path in MOD_ROOT.rglob("*.txt"):
        if path.name.startswith("pp_population_capacity_"):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for key in POPULATION_CAPACITY_KEYS:
            if key in text:
                offenders.append(str(path.relative_to(MOD_ROOT)))
                break

    assert not offenders


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


def _labeler_goods() -> tuple[str, ...]:
    evaluator_root = LABELING_ROOT / "GoodsEvaluator"
    return tuple(
        sorted(
            path.name
            for path in evaluator_root.iterdir()
            if path.is_dir() and (path / "config.yaml").exists()
        )
    )


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
