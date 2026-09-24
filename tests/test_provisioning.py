from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from prosper_or_perish_constructor import provisioning as pv


PROJECT = Path(__file__).resolve().parents[1] / "constructor.toml"
CONFIG = pv.ProvisioningConfig()


def test_amounts_scale_with_base_output_and_round_to_three_decimals() -> None:
    amounts = pv.provisioning_amounts("0.05", config=CONFIG)   # fishing village: M = 0.05 / 0.06

    assert amounts == pv.ProvisioningAmounts(input=Decimal("0.067"), output=Decimal("0.800"), sell=Decimal("0.004"))
    assert pv.provisioning_amounts("0.06", config=CONFIG) == pv.ProvisioningAmounts(
        Decimal("0.080"), Decimal("0.960"), Decimal("0.005")
    )
    assert pv.provisioning_amounts("0.09", config=CONFIG).sell == Decimal("0.008")   # 0.0075 rounds half up


def test_a_dearer_good_takes_less_input_for_the_same_food() -> None:
    cheap = pv.provisioning_amounts("0.06", config=CONFIG)
    dear = pv.provisioning_amounts("0.06", good_price="1.5", config=CONFIG)

    assert dear.input == Decimal("0.053")
    assert dear.output == cheap.output and dear.sell == cheap.sell


def test_amounts_never_fall_below_the_smallest_step() -> None:
    assert pv.provisioning_amounts("0.001", config=CONFIG).sell == Decimal("0.001")


def test_config_is_read_from_constructor_toml() -> None:
    assert pv.load_provisioning_config(PROJECT) == CONFIG


def test_render_slot_lists_provision_first_without_labour() -> None:
    amounts = pv.provisioning_amounts("0.05", config=CONFIG)

    assert pv.render_slot("fishing_village", "fish", amounts, indent="    ") == (
        "    unique_production_methods = {\n"
        "        pp_fishing_village_provision = {\n"
        "            fish = 0.067\n"
        "            produced = local_food\n"
        "            output = 0.8\n"
        "            debug_max_profit = 0\n"
        "            category = building_maintenance\n"
        "        }\n"
        "        pp_fishing_village_sell_surplus = {\n"
        "            produced = province_food_sales\n"
        "            output = 0.004\n"
        "            category = building_maintenance\n"
        "        }\n"
        "    }"
    )


def test_slot_localization_names_the_good_and_the_slot() -> None:
    entries = pv.slot_localization("forest_village", "wild_game", "slot_2")

    assert set(entries) == {
        "forest_village_slot_2",
        "pp_forest_village_provision",
        "pp_forest_village_provision_desc",
        "pp_forest_village_sell_surplus",
        "pp_forest_village_sell_surplus_desc",
    }
    assert entries["forest_village_slot_2"] == "Provisioning"
    assert entries["pp_forest_village_provision"] == "Provision with Game"
    assert "buys its own game back" in entries["pp_forest_village_provision_desc"]
    assert entries["pp_forest_village_sell_surplus"] == "Sell the Surplus"
    assert pv.slot_localization("fishing_village", "fish")["pp_fishing_village_provision"] == "Provision with Fish"
    assert "fishing_village_slot_4" not in pv.slot_localization("fishing_village", "fish")


def test_provisioned_good_falls_back_to_the_upgrade_chain_family() -> None:
    assert pv.provisioned_good("net_curing_yard") == "fish"
    assert pv.provisioned_good("some_new_orchard", family="fruit_orchard") == "fruit"
    assert pv.provisioned_good("iron_mine") is None


def test_evaluation_rules_cover_both_methods() -> None:
    rules = pv.evaluation_rules("fruit_orchard")

    assert set(rules) == {"pp_fruit_orchard_provision", "pp_fruit_orchard_sell_surplus"}
    assert set(rules["pp_fruit_orchard_provision"]["allow_rules"]) == {"profit_percent", "input_throughput", "output_throughput"}
    assert set(rules["pp_fruit_orchard_sell_surplus"]["allow_rules"]) == {"base_output_per_1k"}
