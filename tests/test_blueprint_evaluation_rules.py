from __future__ import annotations

from pathlib import Path

import yaml

from eu5_mod_orchestrator.adapters.building_pipeline import evaluate_building_blueprint_data
from eu5_mod_orchestrator.adapters.parser import (
    load_balance_prices,
    load_global_building_unlock_ages,
    load_global_unlock_ages,
    load_raw_material_goods,
    load_script_values,
)
from eu5_mod_orchestrator.config import load_project_config


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"


def test_accepted_blueprints_have_no_unallowed_evaluation_rule_violations() -> None:
    config = load_project_config(ROOT / "constructor.toml")
    price_by_good = load_balance_prices(profile=config.profile, load_order_path=config.load_order_path)
    raw_material_goods = load_raw_material_goods(profile=config.profile, load_order_path=config.load_order_path)
    global_unlock_age_by_method = load_global_unlock_ages(
        profile=config.profile,
        load_order_path=config.load_order_path,
    )
    global_unlock_age_by_building = load_global_building_unlock_ages(
        profile=config.profile,
        load_order_path=config.load_order_path,
    )
    script_values = load_script_values(profile=config.profile, load_order_path=config.load_order_path)
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled_blueprints = [
        config.accepted_blueprints_dir / entry
        for entry in manifest["enabled"]
    ]

    violations: list[str] = []
    for blueprint in enabled_blueprints:
        evaluation = evaluate_building_blueprint_data(
            blueprint,
            config,
            price_by_good=price_by_good,
            raw_material_goods=raw_material_goods,
            script_values=script_values,
            global_unlock_age_by_method=global_unlock_age_by_method,
            global_unlock_age_by_building=global_unlock_age_by_building,
        )
        violations.extend(f"{blueprint.relative_to(ROOT)}: {violation}" for violation in evaluation.violations)

    assert violations == []
