from pathlib import Path

from eu5_mod_orchestrator.blueprints import accepted_blueprint_files, validate_blueprint_file
from eu5_mod_orchestrator.config import load_project_config


ROOT = Path(__file__).resolve().parents[1]


def test_constructor_config_loads() -> None:
    config = load_project_config(ROOT / "constructor.toml")

    assert config.name == "Prosper or Perish Constructor"
    assert config.mod_root == ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
    assert config.deploy_target is None
    assert config.accepted_blueprints_dir == ROOT / "blueprints" / "accepted"
    assert config.profile == "constructor"
    assert config.load_order_path == ROOT / "constructor.load_order.toml"


def test_accepted_blueprints_validate() -> None:
    for blueprint in accepted_blueprint_files(ROOT / "blueprints" / "accepted"):
        validate_blueprint_file(blueprint)
