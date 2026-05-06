from pathlib import Path

from eu5_building_pipeline.template import load_template
from eu5gameparser.clausewitz.parser import parse_file, parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.availability import annotate_building_data_availability
from eu5gameparser.domain.eu5 import load_eu5_data
from eu5gameparser.load_order import LoadOrderConfig
from eu5_mod_orchestrator.blueprints import accepted_blueprint_files, validate_blueprint_file
from eu5_mod_orchestrator.config import load_project_config
from mod_injector.config import load_mod_injector_config


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ESTATE_PRIVILEGE_ADJUSTMENTS = (
    MOD_ROOT / "in_game" / "common" / "estate_privileges" / "pp_estate_privilege_adjustments.txt"
)


def test_constructor_config_loads() -> None:
    config = load_project_config(ROOT / "constructor.toml")

    assert config.name == "Prosper or Perish Constructor"
    assert config.mod_root == ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    if (ROOT / "constructor.local.toml").exists():
        assert config.deploy_target is not None
    else:
        assert config.deploy_target is None
    assert config.accepted_blueprints_dir == ROOT / "blueprints" / "accepted"
    assert config.profile == "constructor"
    assert config.load_order_path == ROOT / "constructor.load_order.toml"
    assert config.building_outputs.prefix == "pp_"
    assert config.building_artifact_dir == ROOT / "artifacts" / "data" / "buildings"
    assert config.savegame_artifact_dir == ROOT / "artifacts" / "data" / "savegame"
    assert config.graph_dir == ROOT / "graphs"
    assert config.labeling is not None
    assert config.labeling.enabled is True
    assert config.labeling.config_path == ROOT / "labeling_output_modifiers.yaml"
    assert config.labeling.modifier_prefix == "pp"
    assert config.labeling.generated_label == "Prosper or Perish"
    assert config.labeling.managed_write_mode == "mod_root"
    assert config.population_capacity is not None
    assert config.population_capacity.enabled is True
    assert config.population_capacity.config_path == ROOT / "population_capacity.toml"
    assert config.population_capacity.generated_label == "Prosper or Perish"
    assert config.population_capacity.managed_write_mode == "mod_root"
    assert config.blueprint_evaluation.raw_input_efficiency_per_good == 0.05
    assert config.blueprint_evaluation.profit_percent_min == -0.30
    assert config.blueprint_evaluation.profit_percent_max == 0.30
    assert config.blueprint_evaluation.base_output_per_1k_min == 0.07
    assert config.blueprint_evaluation.base_output_per_1k_max == 0.15
    assert config.blueprint_evaluation.throughput_gold_per_1k["laborers"] == 1.5
    assert config.blueprint_evaluation.age_throughput_growth == 0.15
    assert config.blueprint_evaluation.throughput_tolerance == 0.30
    assert config.blueprint_evaluation.amortization_months_min == 120.0
    assert config.blueprint_evaluation.amortization_months_max == 360.0
    assert config.blueprint_evaluation.employment_size_constants == {}


def test_accepted_blueprints_validate() -> None:
    for blueprint in accepted_blueprint_files(ROOT / "blueprints" / "accepted"):
        validate_blueprint_file(blueprint)


def test_replaced_buildings_do_not_reuse_vanilla_unique_method_names() -> None:
    vanilla_methods_by_building = _vanilla_unique_methods_by_building()
    offenders = []

    for blueprint in accepted_blueprint_files(ROOT / "blueprints" / "accepted"):
        template = load_template(blueprint)
        if template.mode != "REPLACE":
            continue
        vanilla_methods = vanilla_methods_by_building.get(template.key)
        if not vanilla_methods:
            continue
        rendered = parse_text(
            f"{template.key} = {{\n{template.building_body}\n}}\n",
            path=blueprint,
        )
        unique_methods = _unique_production_method_names(rendered.entries[0].value)
        reused = sorted(unique_methods & vanilla_methods)
        if reused:
            offenders.append(f"{blueprint.relative_to(ROOT)}: {', '.join(reused)}")

    assert not offenders


def test_land_owning_farmers_is_a_full_privilege_replacement() -> None:
    parsed = parse_file(ESTATE_PRIVILEGE_ADJUSTMENTS)
    entries = {entry.key: entry.value for entry in parsed.entries}

    assert "TRY_REPLACE:land_owning_farmers" in entries
    assert "TRY_INJECT:land_owning_farmers" not in entries
    privilege = entries["TRY_REPLACE:land_owning_farmers"]
    assert isinstance(privilege, CList)

    privilege_values = _entry_values(privilege)
    assert privilege_values["estate"] == "peasants_estate"
    assert privilege_values["content_priority"] == 200
    assert "potential" in privilege_values
    assert "can_revoke" in privilege_values

    country_modifier = privilege_values["country_modifier"]
    assert isinstance(country_modifier, CList)
    modifier_values = _entry_values(country_modifier)
    assert "global_monthly_food_modifier" not in modifier_values
    assert modifier_values["levy_combat_efficiency_modifier"] == 0.05
    assert modifier_values["global_population_capacity_modifier"] == 0.05
    assert modifier_values["global_wheat_output_modifier"] == 0.05
    assert modifier_values["global_fish_output_modifier"] == 0.05
    assert modifier_values["global_millet_output_modifier"] == 0.05
    assert modifier_values["global_peasants_estate_power"] == 0.5


def test_constructor_building_methods_are_resolved_and_unique() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")

    assert data.building_data.duplicate_production_methods.is_empty()
    assert data.building_data.unresolved_production_methods.is_empty()
    assert data.building_data.warnings == []


def test_cookery_building_line_has_resolved_prices() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    buildings = {row["name"]: row for row in data.building_data.buildings.to_dicts()}

    assert buildings["cookery"]["price"] == "pp_cookery_price"
    assert buildings["cookery"]["price_gold"] == 150.0
    assert buildings["victualling_yard"]["price"] == "pp_victualling_yard_price"
    assert buildings["victualling_yard"]["price_gold"] == 225.0


def test_farming_village_uses_baseline_building_price() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    annotated = annotate_building_data_availability(data.building_data, data.advancements)
    buildings = {row["name"]: row for row in annotated.buildings.to_dicts()}

    farming_village = buildings["farming_village"]
    assert farming_village["price"] is None
    assert farming_village["effective_price"] == "p_building_age_1_traditions"
    assert farming_village["effective_price_gold"] == 50.0
    assert farming_village["price_kind"] == "baseline_age"


def test_labeling_output_modifier_config_loads_explicit_goods() -> None:
    cfg = load_mod_injector_config(ROOT / "labeling_output_modifiers.yaml")

    assert cfg.defaults["null_productivity"] == -0.6
    assert cfg.defaults["scale_args"] == {"output_min": -0.6, "output_max": 0.4}
    assert [g.trade_good for g in cfg.goods] == [
        "beeswax",
        "chili",
        "cloves",
        "cocoa",
        "coffee",
        "cotton",
        "dyes",
        "elephants",
        "fiber_crops",
        "fish",
        "fruit",
        "fur",
        "horses",
        "incense",
        "ivory",
        "legumes",
        "livestock",
        "lumber",
        "maize",
        "medicaments",
        "millet",
        "olives",
        "pepper",
        "potato",
        "rice",
        "saffron",
        "silk",
        "sugar",
        "tea",
        "tobacco",
        "wheat",
        "wild_game",
        "wine",
        "wool",
    ]
    assert all(g.enabled for g in cfg.goods)


def _vanilla_unique_methods_by_building() -> dict[str, set[str]]:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    building_dir = load_order.vanilla_root / "game" / "in_game" / "common" / "building_types"
    result: dict[str, set[str]] = {}
    for path in sorted(building_dir.glob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                methods = _unique_production_method_names(entry.value)
                if methods:
                    result[entry.key] = methods
    return result


def _entry_values(block: CList) -> dict[str, object]:
    return {entry.key: entry.value for entry in block.entries}


def _unique_production_method_names(block: CList) -> set[str]:
    names: set[str] = set()
    for value in block.values("unique_production_methods"):
        if isinstance(value, CList):
            names.update(entry.key for entry in value.entries)
    return names
