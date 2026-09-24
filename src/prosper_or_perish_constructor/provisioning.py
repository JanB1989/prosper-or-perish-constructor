"""The Provisioning slot of calorie-producing buildings (replaces the former "Household Food" victuals slot).

Every building that grows or catches a calorie good gets one slot with two methods, the choice the AI makes by profit:

- ``pp_<b>_provision`` (listed first, the default at game start): buys the building's own good back and turns it into
  Province Food (``local_food``). At the Province Food floor price it earns a thin margin by design; it pays while the province
  store is low and the good is cheap.
- ``pp_<b>_sell_surplus``: a no-input dummy that produces ``province_food_sales`` ("Surplus Sales"), whose output
  modifier grows with the stored province food (0x while the store is empty). It pays the fuller the store is.

Amounts scale with the building's size, measured by its base output: ``M = base_output / reference_base_output``,
where ``base_output`` is the output of the first slot-0 method that produces the building's own good.

- input  = ``input_per_level * M / good_price``  (the same gold of the good per level whatever its price)
- output = ``input_per_level * food_per_gold * M`` (so Province Food per gold of the good is the same for every good:
  a price-1 good gives ``food_per_gold`` food per unit; livestock at 1.5 gives input 0.053 M, output still 0.96 M)
- sell   = ``sell_per_level * M``

All amounts are rounded half up to 3 decimals and never fall below 0.001. The constants live in
``[building_scaling]`` of ``constructor.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import tomllib
from typing import Any


CONFIG_SECTION = "building_scaling"
INPUT_PER_LEVEL_FIELD = "provision_input_per_level"
FOOD_PER_GOLD_FIELD = "provision_food_per_gold"
SELL_PER_LEVEL_FIELD = "sell_surplus_per_level"
REFERENCE_BASE_OUTPUT_FIELD = "provisioning_reference_base_output"
DEFAULT_PROJECT = Path(__file__).resolve().parents[2] / "constructor.toml"
CROP_TABLE = Path(__file__).resolve().parents[2] / "config" / "crop_farms.toml"

PROVINCE_FOOD_GOOD = "local_food"
SURPLUS_SALES_GOOD = "province_food_sales"
SLOT_LABEL = "Provisioning"
SELL_LABEL = "Sell the Surplus"
SELL_DESC = (
    "The household sells what the province does not need. It pays more the fuller the province store is, "
    "and nothing while it is empty."
)

def _crop_table(path: Path = CROP_TABLE) -> dict[str, Any]:
    """``config/crop_farms.toml``, read straight from the table (``crop_farms.py`` imports this module)."""
    return tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def _crop_farm_goods(raw: dict[str, Any]) -> dict[str, str]:
    """Building -> good of the crop farm chains (``<stem>_<tier suffix>``, chain order)."""
    suffixes = raw.get("general", {}).get("tier_suffix", {})
    tiers = sorted(suffixes, key=int)
    return {f"{crop['stem']}_{suffixes[tier]}": str(crop["good"]) for crop in raw.get("crops", []) for tier in tiers}


_CROP_TABLE = _crop_table()
CROP_FARM_GOODS: dict[str, str] = _crop_farm_goods(_CROP_TABLE)
CROP_FARM_FAMILY_GOODS: dict[str, str] = {f"{crop['stem']}_farm": str(crop["good"]) for crop in _CROP_TABLE.get("crops", [])}

# The good each calorie family provisions with, keyed by blueprint `upgrade_chain.family` (crop chains: `<stem>_farm`).
PROVISIONED_GOOD_BY_FAMILY: dict[str, str] = {
    "fishing_village": "fish",
    "ocean_fishery": "fish",
    "fruit_orchard": "fruit",
    "forest_village": "wild_game",
    **CROP_FARM_FAMILY_GOODS,
}

# Buildings with a Provisioning slot, in a stable order; the crop farms follow the fisheries, orchards and forest villages.
PROVISIONED_GOOD_BY_BUILDING: dict[str, str] = {
    "fishing_village": "fish",
    "net_curing_yard": "fish",
    "ocean_fishery": "fish",
    "drift_net_fishery": "fish",
    "offshore_fishery": "fish",
    "fruit_orchard": "fruit",
    "nursery_orchard": "fruit",
    "pomological_orchard": "fruit",
    "forest_village": "wild_game",
    "managed_forest_village": "wild_game",
    **CROP_FARM_GOODS,
}
PROVISIONING_BUILDINGS: tuple[str, ...] = tuple(PROVISIONED_GOOD_BY_BUILDING)

# Market price of a provisioned good where it is not 1 (the Provision input is the same gold of the good per level).
PROVISIONED_GOOD_PRICES: dict[str, Decimal] = {"livestock": Decimal("1.5")}


def provisioned_good_price(good: str) -> Decimal:
    return PROVISIONED_GOOD_PRICES.get(good, Decimal("1"))

# Player-facing words per good: (method-name label, noun in the description).
GOOD_WORDS: dict[str, tuple[str, str]] = {
    "fish": ("Fish", "catch"),
    "fruit": ("Fruit", "fruit"),
    "wild_game": ("Game", "game"),
}

_STEP = Decimal("0.001")


@dataclass(frozen=True)
class ProvisioningConfig:
    input_per_level: Decimal = Decimal("0.08")
    food_per_gold: Decimal = Decimal("12")
    sell_per_level: Decimal = Decimal("0.005")
    reference_base_output: Decimal = Decimal("0.06")


@dataclass(frozen=True)
class ProvisioningAmounts:
    input: Decimal
    output: Decimal
    sell: Decimal


def load_provisioning_config(project: Path = DEFAULT_PROJECT) -> ProvisioningConfig:
    raw = tomllib.loads(project.read_text(encoding="utf-8-sig"))
    section = raw.get(CONFIG_SECTION, {})
    if not isinstance(section, dict):
        raise ValueError(f"{project}: [{CONFIG_SECTION}] must be a table")
    default = ProvisioningConfig()
    values: dict[str, Decimal] = {}
    for attribute, field_name in (
        ("input_per_level", INPUT_PER_LEVEL_FIELD),
        ("food_per_gold", FOOD_PER_GOLD_FIELD),
        ("sell_per_level", SELL_PER_LEVEL_FIELD),
        ("reference_base_output", REFERENCE_BASE_OUTPUT_FIELD),
    ):
        value = _decimal(section.get(field_name, getattr(default, attribute)), f"{CONFIG_SECTION}.{field_name}")
        if value <= 0:
            raise ValueError(f"{project}: {CONFIG_SECTION}.{field_name} must be positive")
        values[attribute] = value
    return ProvisioningConfig(**values)


def provisioned_good(building_key: str, family: str | None = None) -> str | None:
    """The good a building provisions with: its own entry, else its upgrade-chain family's, else None."""
    if building_key in PROVISIONED_GOOD_BY_BUILDING:
        return PROVISIONED_GOOD_BY_BUILDING[building_key]
    if family is not None:
        return PROVISIONED_GOOD_BY_FAMILY.get(family)
    return PROVISIONED_GOOD_BY_FAMILY.get(building_key)


def provisioning_amounts(
    base_output: Decimal | float | str,
    good_price: Decimal | float | str = 1,
    config: ProvisioningConfig | None = None,
) -> ProvisioningAmounts:
    config = config or load_provisioning_config()
    base = _decimal(base_output, "base_output")
    price = _decimal(good_price, "good_price")
    if base <= 0:
        raise ValueError(f"base_output must be positive: {base}")
    if price <= 0:
        raise ValueError(f"good_price must be positive: {price}")
    scale = base / config.reference_base_output
    return ProvisioningAmounts(
        input=round_amount(config.input_per_level * scale / price),
        output=round_amount(config.input_per_level * config.food_per_gold * scale),
        sell=round_amount(config.sell_per_level * scale),
    )


def round_amount(value: Decimal) -> Decimal:
    return max(value.quantize(_STEP, rounding=ROUND_HALF_UP), _STEP)


def format_amount(value: Decimal) -> str:
    text = format(value.quantize(_STEP, rounding=ROUND_HALF_UP).normalize(), "f")
    return text


def provision_method(building_key: str) -> str:
    return f"pp_{building_key}_provision"


def sell_method(building_key: str) -> str:
    return f"pp_{building_key}_sell_surplus"


def slot_methods(building_key: str) -> tuple[str, str]:
    return provision_method(building_key), sell_method(building_key)


def render_slot(building_key: str, good: str, amounts: ProvisioningAmounts, indent: str = "") -> str:
    """The `unique_production_methods` block, 4-space indented below ``indent``, without a trailing newline."""
    lines = [
        "unique_production_methods = {",
        f"    {provision_method(building_key)} = {{",
        f"        {good} = {format_amount(amounts.input)}",
        f"        produced = {PROVINCE_FOOD_GOOD}",
        f"        output = {format_amount(amounts.output)}",
        "        debug_max_profit = 0",
        "        category = building_maintenance",
        "    }",
        f"    {sell_method(building_key)} = {{",
        f"        produced = {SURPLUS_SALES_GOOD}",
        f"        output = {format_amount(amounts.sell)}",
        "        category = building_maintenance",
        "    }",
        "}",
    ]
    return "\n".join(f"{indent}{line}" for line in lines)


def slot_localization(building_key: str, good: str, slot_name: str | None = None) -> dict[str, str]:
    """Method names and descriptions; with ``slot_name`` also the slot label key ``<b>_<slot_name>``."""
    label, noun = GOOD_WORDS.get(good, (good.replace("_", " ").title(), good.replace("_", " ")))
    entries: dict[str, str] = {}
    if slot_name is not None:
        entries[f"{building_key}_{slot_name}"] = SLOT_LABEL
    entries[provision_method(building_key)] = f"Provision with {label}"
    entries[f"{provision_method(building_key)}_desc"] = (
        f"The household buys its own {noun} back and cooks for the province. "
        "Worth it while the province store is low and the good is cheap."
    )
    entries[sell_method(building_key)] = SELL_LABEL
    entries[f"{sell_method(building_key)}_desc"] = SELL_DESC
    return entries


def evaluation_rules(building_key: str) -> dict[str, dict[str, Any]]:
    """Per-method `evaluation.production_methods` entries (allow rules) for the two Provisioning methods."""
    return {
        provision_method(building_key): {
            "allow_rules": {
                "profit_percent": (
                    "Provisioning is balanced at the Province Food floor (12 food per gold of crop); the storage signal decides the switch."
                ),
                "input_throughput": "Existing accepted input scale predates the global employment throughput baseline.",
                "output_throughput": "Existing accepted output scale predates the global employment throughput baseline.",
            }
        },
        sell_method(building_key): {
            "allow_rules": {
                "base_output_per_1k": "Sell the Surplus is a no-input dummy signal, not a production line.",
            }
        },
    }


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError(f"{name} must be a number")
    else:
        result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result
