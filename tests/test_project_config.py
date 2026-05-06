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
GOVERNMENT_REFORM_ADJUSTMENTS = (
    MOD_ROOT / "in_game" / "common" / "government_reforms" / "pp_government_reform_adjustments.txt"
)
ESTATE_ADJUSTMENTS = MOD_ROOT / "in_game" / "common" / "estates" / "pp_estate_adjustments.txt"
GOODS_DEMAND = MOD_ROOT / "in_game" / "common" / "goods_demand" / "pp_new_goods_demands.txt"
LAW_ADJUSTMENTS = MOD_ROOT / "in_game" / "common" / "laws" / "pp_law_adjustments.txt"
PRICE_ROOT = MOD_ROOT / "in_game" / "common" / "prices"
MODIFIER_TYPE_DEFINITIONS = MOD_ROOT / "main_menu" / "common" / "modifier_type_definitions"
MODIFIER_ICONS = MOD_ROOT / "main_menu" / "common" / "modifier_icons"
LOCALIZATION_ROOT = MOD_ROOT / "main_menu" / "localization" / "english"


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


def test_powerful_magnates_food_modifier_is_zeroed_by_replacement() -> None:
    parsed = parse_file(GOVERNMENT_REFORM_ADJUSTMENTS)
    entries = {entry.key: entry.value for entry in parsed.entries}

    assert "REPLACE:hun_power_to_magnates" in entries
    assert "TRY_INJECT:hun_power_to_magnates" not in entries
    reform = entries["REPLACE:hun_power_to_magnates"]
    assert isinstance(reform, CList)

    reform_values = _entry_values(reform)
    assert reform_values["age"] == "age_2_renaissance"
    assert reform_values["unique"] is True
    assert reform_values["content_priority"] == 600
    assert "potential" in reform_values
    assert reform_values["years"] == 2

    country_modifier = reform_values["country_modifier"]
    assert isinstance(country_modifier, CList)
    modifier_values = _entry_values(country_modifier)
    assert modifier_values["global_nobles_estate_power"] == 1.0
    assert modifier_values["global_estate_target_satisfaction"] == "medium_permanent_target_satisfaction"
    assert modifier_values["global_monthly_food_modifier"] == 0


def test_dhimmi_satisfaction_uses_small_regional_staple_output_package() -> None:
    parsed = parse_file(ESTATE_ADJUSTMENTS)
    entries = {entry.key: entry.value for entry in parsed.entries}

    assert "TRY_INJECT:dhimmi_estate" in entries
    estate = entries["TRY_INJECT:dhimmi_estate"]
    assert isinstance(estate, CList)

    satisfaction = _entry_values(estate)["satisfaction"]
    assert isinstance(satisfaction, CList)
    modifier_values = _entry_values(satisfaction)

    assert "global_monthly_food_modifier" not in modifier_values
    assert modifier_values == {
        "global_wheat_output_modifier": 0.05,
        "global_rice_output_modifier": 0.05,
        "global_millet_output_modifier": 0.05,
        "global_legumes_output_modifier": 0.05,
        "global_fruit_output_modifier": 0.05,
        "global_olives_output_modifier": 0.05,
    }


def test_inject_targets_exist_in_constructor_load_order() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_root = load_order.vanilla_root
    offenders: list[str] = []

    for relative_common, vanilla_common in (
        (Path("in_game") / "common", vanilla_root / "game" / "in_game" / "common"),
        (Path("main_menu") / "common", vanilla_root / "game" / "main_menu" / "common"),
    ):
        mod_common = MOD_ROOT / relative_common
        for collection_dir in sorted(path for path in mod_common.iterdir() if path.is_dir()):
            collection = collection_dir.relative_to(mod_common)
            existing = _database_keys(vanilla_common / collection)
            if collection == Path("static_modifiers"):
                existing |= _database_keys(vanilla_root / "game" / "main_menu" / "common" / collection)

            for path in sorted(collection_dir.rglob("*.txt")):
                for entry in parse_file(path).entries:
                    if not isinstance(entry.value, CList):
                        continue
                    mode, key = _entry_mode(entry.key)
                    if mode in {"INJECT", "TRY_INJECT"} and key not in existing:
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{entry.location.line} {mode}:{key}"
                        )
                    if mode in {"CREATE", "REPLACE", "REPLACE_OR_CREATE", "INJECT_OR_CREATE"}:
                        existing.add(key)
                    elif mode in {"TRY_REPLACE", "INJECT", "TRY_INJECT"} and key in existing:
                        existing.add(key)

    assert not offenders


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


def test_victuals_pop_demand_uses_scalar_database_value() -> None:
    entries = {entry.key: entry.value for entry in parse_file(GOODS_DEMAND).entries}
    pop_demand = entries["INJECT:pop_demand"]
    assert isinstance(pop_demand, CList)

    values = _entry_values(pop_demand)
    assert values["victuals"] == 1


def test_pp_law_adjustments_use_existing_modifier_types() -> None:
    text = LAW_ADJUSTMENTS.read_text(encoding="utf-8-sig")

    assert "army_infantry_maintenance_cost_modifier" not in text
    assert "trade_efficiency =" not in text
    assert "army_light_infantry_maintenance_cost_modifier = -0.1" in text
    assert "army_heavy_infantry_maintenance_cost_modifier = -0.1" in text
    assert "trade_land_efficiency = small_trade_efficiency_bonus" in text
    assert "trade_sea_efficiency = small_trade_efficiency_bonus" in text


def test_pp_building_prices_have_modifier_type_assets_and_localization() -> None:
    price_keys = {
        key
        for key in _database_keys(PRICE_ROOT)
        if key.startswith("pp_") and key.endswith("_price")
    }
    expected = {f"{price_key}_cost_modifier" for price_key in price_keys}

    modifier_types = _database_keys(MODIFIER_TYPE_DEFINITIONS)
    modifier_icons = _database_keys(MODIFIER_ICONS)
    localization_text = "\n".join(
        path.read_text(encoding="utf-8-sig") for path in sorted(LOCALIZATION_ROOT.glob("*.yml"))
    )

    assert expected
    assert not (expected - modifier_types)
    assert not (expected - modifier_icons)
    assert not [
        key
        for key in sorted(expected)
        if f"MODIFIER_TYPE_DESC_{key}:" not in localization_text
        or f"MODIFIER_TYPE_NAME_{key}:" not in localization_text
    ]


def test_victuals_pop_demand_modifier_type_is_registered() -> None:
    modifier_types = _database_keys(MODIFIER_TYPE_DEFINITIONS)
    localization_text = "\n".join(
        path.read_text(encoding="utf-8-sig") for path in sorted(LOCALIZATION_ROOT.glob("*.yml"))
    )

    assert "global_victuals_pop_demand" in modifier_types
    assert "MODIFIER_TYPE_NAME_global_victuals_pop_demand:" in localization_text
    assert "MODIFIER_TYPE_DESC_global_victuals_pop_demand:" in localization_text


def test_current_megalopolis_buildings_allow_megalopolis() -> None:
    for blueprint_name in ("dock", "fruit_orchard", "irrigation_systems"):
        template = load_template(ROOT / "blueprints" / "accepted" / "buildings" / f"{blueprint_name}.yml")
        rendered = parse_text(
            f"{template.key} = {{\n{template.building_body}\n}}\n",
            path=Path(f"{blueprint_name}.yml"),
        )
        values = _entry_values(rendered.entries[0].value)
        assert values["megalopolis"] is True


def test_victuals_market_construction_and_salt_collector_debug_keys_are_localized() -> None:
    victuals_market = load_template(ROOT / "blueprints" / "accepted" / "buildings" / "victuals_market.yml")
    salt_collector = load_template(ROOT / "blueprints" / "accepted" / "buildings" / "salt_collector.yml")

    assert victuals_market.localization["victuals_market_construction"] == "Victuals Market Construction"

    rendered = parse_text(
        f"{salt_collector.key} = {{\n{salt_collector.building_body}\n}}\n",
        path=Path("salt_collector.yml"),
    )
    body = rendered.entries[0].value
    assert isinstance(body, CList)
    methods = body.values("unique_production_methods")[0]
    assert isinstance(methods, CList)
    maintenance = _entry_values(methods)["pp_salt_collector_maintenance"]
    assert isinstance(maintenance, CList)
    values = _entry_values(maintenance)
    assert values["output"] == 0.3
    assert values["clay"] == 2.0
    assert values["debug_max_profit"] == 0.3


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


def _database_keys(root: Path) -> set[str]:
    if not root.exists():
        return set()
    keys: set[str] = set()
    for path in sorted(root.rglob("*.txt")):
        for entry in parse_file(path).entries:
            if isinstance(entry.value, CList):
                keys.add(_entry_mode(entry.key)[1])
    return keys


def _entry_mode(raw_key: str) -> tuple[str, str]:
    if ":" not in raw_key:
        return "CREATE", raw_key
    mode, key = raw_key.split(":", 1)
    return mode.strip().upper(), key


def _unique_production_method_names(block: CList) -> set[str]:
    names: set[str] = set()
    for value in block.values("unique_production_methods"):
        if isinstance(value, CList):
            names.update(entry.key for entry in value.entries)
    return names
