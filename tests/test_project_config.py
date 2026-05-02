from pathlib import Path

from eu5_mod_orchestrator.blueprints import accepted_blueprint_files, validate_blueprint_file
from eu5_mod_orchestrator.config import load_project_config
from mod_injector.config import load_mod_injector_config


ROOT = Path(__file__).resolve().parents[1]


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
