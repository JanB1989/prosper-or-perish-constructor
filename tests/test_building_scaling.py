from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re

from eu5_building_pipeline.template import load_template
from eu5_mod_orchestrator.blueprints import enabled_manifest_entries
from eu5_mod_orchestrator.config import load_project_config
from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.domain.pop_types import load_pop_type_data
from prosper_or_perish_constructor.building_scaling import (
    apply_increase_per_level_cost_multiplier,
    format_increase_per_level_cost,
    load_building_scaling_config,
    scaled_increase_per_level_cost_text,
)
from prosper_or_perish_constructor import provisioning, yaml_io


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "constructor.toml"
BUILDING_BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"
MANIFEST = ROOT / "blueprints" / "buildings.manifest.yml"
METHOD_KEYS = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "no_upkeep", "ai_will_do"}


def test_building_scaling_config_loads_provisioning_constants() -> None:
    config = load_building_scaling_config(PROJECT)
    provision = provisioning.load_provisioning_config(PROJECT)

    assert provision.input_per_level == Decimal("0.08")
    assert provision.food_per_gold == Decimal("12")
    assert provision.sell_per_level == Decimal("0.005")
    assert provision.reference_base_output == Decimal("0.06")
    assert config.increase_per_level_cost_multiplier == Decimal("0.75")
    assert config.burgher_building_employment_size == Decimal("0.3")


def test_burgher_buildings_do_not_exceed_configured_employment_baseline() -> None:
    scaling = load_building_scaling_config(PROJECT)
    offenders: list[str] = []
    baseline_count = 0

    for entry in enabled_manifest_entries(
        yaml_io.safe_load(MANIFEST.read_text(encoding="utf-8")).get("enabled", []),
        source=MANIFEST,
    ):
        template = load_template(ROOT / "blueprints" / "accepted" / entry)
        block = _building_block(template.key, template.building_body)
        pop_type_values = block.values("pop_type")
        if not pop_type_values or str(pop_type_values[-1]) != "burghers":
            continue
        employment_size = Decimal(str(_last_value(block, "employment_size")))
        if employment_size == scaling.burgher_building_employment_size:
            baseline_count += 1
        if employment_size > scaling.burgher_building_employment_size:
            offenders.append(
                f"{template.key}: employment_size={employment_size} "
                f"> burgher baseline {scaling.burgher_building_employment_size}"
            )

    assert baseline_count > 0
    assert not offenders


def test_increase_per_level_cost_multiplier_rounds_to_two_decimals() -> None:
    assert scaled_increase_per_level_cost_text(Decimal("0.13"), Decimal("0.75")) == "0.10"
    assert scaled_increase_per_level_cost_text(Decimal("0.30"), Decimal("0.75")) == "0.23"
    assert format_increase_per_level_cost(Decimal("0.225")) == "0.23"


def test_increase_per_level_cost_compilation_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path
    project = repo / "constructor.toml"
    blueprint = repo / "blueprints" / "accepted" / "buildings" / "test_market.yml"
    manifest = repo / "blueprints" / "buildings.manifest.yml"
    mod_root = repo / "mod" / "test"
    building_type = mod_root / "in_game" / "common" / "building_types" / "zz_test_market.txt"

    project.write_text(
        "[building_scaling]\n"
        "increase_per_level_cost_multiplier = 0.75\n",
        encoding="utf-8",
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text("enabled:\n- buildings/test_market.yml\n", encoding="utf-8")
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(
        "version: 2\n"
        "tag: test_market\n"
        "building:\n"
        "  key: test_market\n"
        "  mode: CREATE\n"
        "  source: test.txt\n"
        "  production_method_slots: []\n"
        "  possible_production_methods: []\n"
        "  body: |2-\n"
        "    increase_per_level_cost = 0.13\n",
        encoding="utf-8",
    )
    building_type.parent.mkdir(parents=True)
    building_type.write_text(
        "test_market = {\n"
        "\tincrease_per_level_cost = 0.13\n"
        "\tmodifier = {\n"
        "\t\tlocal_monthly_food = 1\n"
        "\t}\n"
        "}\n",
        encoding="utf-8-sig",
    )

    first = apply_increase_per_level_cost_multiplier(repo, mod_root, project)
    second = apply_increase_per_level_cost_multiplier(repo, mod_root, project)

    assert first.entries_scaled == 1
    assert second.entries_scaled == 1
    assert building_type.read_text(encoding="utf-8-sig") == (
        "test_market = {\n"
        "\tincrease_per_level_cost = 0.10\n"
        "\tmodifier = {\n"
        "\t\tlocal_monthly_food = 1\n"
        "\t}\n"
        "}\n"
    )


def test_provisioning_slots_match_configured_amounts() -> None:
    config = provisioning.load_provisioning_config(PROJECT)

    for building in provisioning.PROVISIONING_BUILDINGS:
        template = load_template(BUILDING_BLUEPRINT_ROOT / f"{building}.yml")
        provision, sell = provisioning.slot_methods(building)
        good = provisioning.provisioned_good(building)
        assert good is not None

        slots = [
            slot.methods
            for slot in template.production_method_slots
            if provision in slot.methods or sell in slot.methods
        ]
        assert slots == [(provision, sell)], building

        block = _building_block(template.key, template.building_body)
        amounts = provisioning.provisioning_amounts(
            _base_output(block, template.production_method_slots[0].methods, good),
            good_price=provisioning.provisioned_good_price(good),
            config=config,
        )

        provision_values = _unique_method_values(block, provision)
        provision_inputs = {key: value for key, value in provision_values.items() if key not in METHOD_KEYS}
        assert set(provision_inputs) == {good}, building
        assert Decimal(str(provision_inputs[good])) == amounts.input, building
        assert provision_values["produced"] == "local_food"
        assert Decimal(str(provision_values["output"])) == amounts.output, building

        sell_values = _unique_method_values(block, sell)
        assert {key for key in sell_values if key not in METHOD_KEYS} == set(), building
        assert sell_values["produced"] == "province_food_sales"
        assert Decimal(str(sell_values["output"])) == amounts.sell, building


def test_provisioning_slots_are_limited_to_calorie_buildings() -> None:
    assert _accepted_buildings_with_method_suffix("_sell_surplus") == set(provisioning.PROVISIONING_BUILDINGS)


def test_no_blueprint_keeps_worker_victuals() -> None:
    assert _accepted_buildings_with_method_suffix("_worker_victuals") == set()


def test_provisioning_feeds_at_least_the_workers() -> None:
    """Provision output (Province Food, 1 food each) per level covers most of what the building's own workers eat."""
    for building in provisioning.PROVISIONING_BUILDINGS:
        template = load_template(BUILDING_BLUEPRINT_ROOT / f"{building}.yml")
        block = _building_block(template.key, template.building_body)
        pop_type = str(_last_value(block, "pop_type"))
        employment_size = Decimal(str(_last_value(block, "employment_size")))
        worker_food = employment_size * _pop_food_consumption(pop_type)
        provision = re.search(
            rf"pp_{re.escape(building)}_provision\s*=\s*\{{[^}}]*?output\s*=\s*([0-9.]+)", template.building_body, re.S
        )
        assert provision, building
        assert Decimal(provision.group(1)) >= worker_food * Decimal("0.75"), building

    cookery = load_template(BUILDING_BLUEPRINT_ROOT / "cookery.yml")
    assert "local_monthly_food" not in cookery.building_body  # food comes from the Serve methods now
    serve = re.search(r"pp_cookery_livestock_pottage_serve\s*=\s*\{[^}]*?output\s*=\s*([0-9.]+)", cookery.building_body, re.S)
    assert serve and Decimal(serve.group(1)) >= Decimal("20")


def _building_block(building: str, body: str) -> CList:
    parsed = parse_text(f"{building} = {{\n{body}\n}}\n")
    block = parsed.entries[0].value
    assert isinstance(block, CList)
    return block


def _last_value(block: CList, key: str) -> object:
    values = block.values(key)
    assert values, f"missing {key}"
    return values[-1]


def _last_block(block: CList, key: str) -> CList:
    value = _last_value(block, key)
    assert isinstance(value, CList)
    return value


def _unique_method_values(building: CList, method: str) -> dict[str, object]:
    for group in building.values("unique_production_methods"):
        assert isinstance(group, CList)
        for entry in group.entries:
            if entry.key == method:
                assert isinstance(entry.value, CList)
                return {item.key: item.value for item in entry.value.entries}
    raise AssertionError(f"missing unique production method {method}")


def _pop_food_consumption(pop_type: str) -> Decimal:
    project = load_project_config(PROJECT)
    data = load_pop_type_data(profile=project.profile, load_order_path=project.load_order_path)
    rows = data.pop_types.filter(data.pop_types["name"] == pop_type).select("pop_food_consumption").to_dicts()
    assert rows
    return Decimal(str(rows[0]["pop_food_consumption"]))


def _base_output(block: CList, slot_0: tuple[str, ...], good: str) -> Decimal:
    """Output of the first slot-0 method that produces the building's own good."""
    for method in slot_0:
        values = _unique_method_values(block, method)
        if values.get("produced") == good:
            return Decimal(str(values["output"]))
    raise AssertionError(f"no slot-0 method produces {good}")


def _accepted_buildings_with_method_suffix(suffix: str) -> set[str]:
    manifest = yaml_io.safe_load(MANIFEST.read_text(encoding="utf-8"))
    result: set[str] = set()
    for entry in enabled_manifest_entries(manifest.get("enabled", []), source=MANIFEST):
        template = load_template(ROOT / "blueprints" / "accepted" / entry)
        methods = {
            method
            for slot in template.production_method_slots
            for method in slot.methods
            if method.endswith(suffix)
        }
        if methods:
            result.add(template.key)
    return result
