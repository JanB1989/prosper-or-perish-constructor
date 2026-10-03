"""The Provisioning slot of calorie-producing buildings (replaces the former "Household Food" victuals slot).

Every building that grows or catches a calorie good gets one slot with one method:

- ``pp_<b>_provision``: buys the building's own good back and turns it into Province Food (``local_food``). It always
  runs. The province store moves what it yields: Province Food output is higher while the store is low and lower
  while it is full (Low Stores / Full Stores, ``stored_food.py``), and above the pivot the same land yields more of
  its good for the market instead. At the Province Food floor price it earns a thin margin by design.

Until 2026-10-02 the slot also held ``pp_<b>_sell_surplus`` (a no-input dummy producing Surplus Sales that the AI
switched to at a full store); the store lever replaced that switch. ``legacy_sell_method`` names it so tooling can
remove what is left of it.

Fisheries, orchards and forest villages: the AI's profit-margin check reads the building's Market gate leg, which comes
after this slot (``production_gate.py``): Provision buys the building's own good back, so gating on it made the AI
stop building exactly when the good was dear.

Crop farms (farm v3, 2026-10-02): Provision buys only a token of the crop (``crop_input_gold``) and makes a fixed
Province Food amount per level (``crop_food_per_level``). The farm sells nearly all its crop, and Provision's margin
(Province Food / a token of crop) stays far above the AI's threshold at any crop price, so it is the farm's gate and
the farm has no Market leg; the AI's price response is the farm's ``ai_construct_weight`` (``crop_farms.py``).
Farm trade-off (2026-10-03): a tier with ``tier_province_food_share`` in the crop table makes that share of its food
per level at 12 stored months as Province Food and keeps the rest as flat food (``crop_food_split``; the total is the
plain Provision + the tier's age flat food), so more of its food follows the store.

Amounts scale with the building's size, measured by its base output: ``M = base_output / reference_base_output``,
where ``base_output`` is the output of the first slot-0 method that produces the building's own good.

- input  = ``input_per_level * M / good_price``  (the same gold of the good per level whatever its price)
- output = ``input_per_level * food_per_gold * M`` (so Province Food per gold of the good is the same for every good:
  a price-1 good gives ``food_per_gold`` food per unit; livestock at 1.5 gives input 0.053 M, output still 0.96 M)
- crop farms: input = ``crop_input_gold * M / good_price``, output = ``crop_food_per_level * M``

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
CROP_INPUT_GOLD_FIELD = "crop_provision_input_gold"
CROP_FOOD_PER_LEVEL_FIELD = "crop_provision_food_per_level"
REFERENCE_BASE_OUTPUT_FIELD = "provisioning_reference_base_output"
DEFAULT_PROJECT = Path(__file__).resolve().parents[2] / "constructor.toml"
CROP_TABLE = Path(__file__).resolve().parents[2] / "config" / "crop_farms.toml"

PROVINCE_FOOD_GOOD = "local_food"
SLOT_LABEL = "Provisioning"
PROVISION_DESC = (
    "The household buys its own {noun} back and cooks for the province. The lower the province store is, the more "
    "food it makes of it."
)

def _crop_table(path: Path = CROP_TABLE) -> dict[str, Any]:
    """``config/crop_farms.toml``, read straight from the table (``crop_farms.py`` imports this module)."""
    return tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def _crop_farm_goods(raw: dict[str, Any]) -> dict[str, str]:
    """Building -> good of the crop farm chains (``<stem>_<tier suffix>``, chain order)."""
    suffixes = raw.get("general", {}).get("tier_suffix", {})
    tiers = sorted(suffixes, key=int)
    return {f"{crop['stem']}_{suffixes[tier]}": str(crop["good"]) for crop in raw.get("crops", []) for tier in tiers}


def _crop_farm_tiers(raw: dict[str, Any]) -> dict[str, int]:
    """Building -> tier of the crop farm chains."""
    suffixes = raw.get("general", {}).get("tier_suffix", {})
    return {f"{crop['stem']}_{suffix}": int(tier) for crop in raw.get("crops", []) for tier, suffix in suffixes.items()}


_CROP_TABLE = _crop_table()
CROP_FARM_GOODS: dict[str, str] = _crop_farm_goods(_CROP_TABLE)
CROP_FARM_TIERS: dict[str, int] = _crop_farm_tiers(_CROP_TABLE)
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
    reference_base_output: Decimal = Decimal("0.06")
    crop_input_gold: Decimal = Decimal("0.01")
    crop_food_per_level: Decimal = Decimal("1.5")


@dataclass(frozen=True)
class ProvisioningAmounts:
    input: Decimal
    output: Decimal


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
        ("reference_base_output", REFERENCE_BASE_OUTPUT_FIELD),
        ("crop_input_gold", CROP_INPUT_GOLD_FIELD),
        ("crop_food_per_level", CROP_FOOD_PER_LEVEL_FIELD),
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
    )


def crop_provisioning_amounts(
    base_output: Decimal | float | str,
    good_price: Decimal | float | str = 1,
    config: ProvisioningConfig | None = None,
) -> ProvisioningAmounts:
    """A crop farm's Provision: a token of the crop in, a fixed Province Food amount per level out."""
    config = config or load_provisioning_config()
    base = _decimal(base_output, "base_output")
    price = _decimal(good_price, "good_price")
    if base <= 0 or price <= 0:
        raise ValueError(f"base_output and good_price must be positive: {base}, {price}")
    scale = base / config.reference_base_output
    return ProvisioningAmounts(
        input=round_amount(config.crop_input_gold * scale / price),
        output=round_amount(config.crop_food_per_level * scale),
    )


def crop_province_food_share(tier: int, raw: dict[str, Any] | None = None) -> Decimal | None:
    """``tier_province_food_share`` of the crop table: the share of a crop farm tier's food per level at 12 stored
    months (flat food + Provision) that it makes as Province Food; None keeps the plain rule (farm trade-off,
    2026-10-03)."""
    shares = (raw if raw is not None else _CROP_TABLE).get("general", {}).get("tier_province_food_share", {})
    value = shares.get(str(tier))
    if value is None:
        return None
    share = _decimal(value, f"tier_province_food_share.{tier}")
    if not 0 < share <= 1:
        raise ValueError(f"tier_province_food_share.{tier} must be in (0, 1]: {share}")
    return share


def crop_food_split(
    base_output: Decimal | float | str,
    flat_food: Decimal | float | str,
    good_price: Decimal | float | str = 1,
    config: ProvisioningConfig | None = None,
    share: Decimal | None = None,
) -> tuple[ProvisioningAmounts, Decimal]:
    """A crop farm's Provision amounts and its flat food per level. With ``share`` the farm makes that share of its
    food per level at 12 stored months (``flat_food`` + the plain Provision output) as Province Food and keeps the rest
    as flat food: the total stays the same, but more of it follows the store (Province Food earns most at a low store,
    which keeps the late tiers' crews through a poor harvest there)."""
    amounts = crop_provisioning_amounts(base_output, good_price, config)
    flat = _decimal(flat_food, "flat_food")
    if share is None:
        return amounts, flat
    total = flat + amounts.output
    output = round_amount(total * share)
    return ProvisioningAmounts(input=amounts.input, output=output), total - output


def crop_tier_flat_food(tier: int, project: Path = DEFAULT_PROJECT, raw: dict[str, Any] | None = None) -> Decimal:
    """The flat food per level of a crop farm tier before the split: the ``[age_food]`` flat food of the tier's age
    (the farm: age 1; a later tier: its tier advance's age), else the tier's own ``local_monthly_food``
    (``[general.tier_modifier.<tier>]``), as ``crop_farms.render_blueprint`` takes it."""
    from prosper_or_perish_constructor import age_food   # age_food imports this module

    table = raw if raw is not None else _CROP_TABLE
    general = table.get("general", {})
    age = "age_1_traditions" if tier == 0 else str(table["tier_advance"][general["tier_advances"][str(tier)]]["age"])
    ages = age_food.load_config(project).ages
    if age in ages:
        return _decimal(ages[age].flat_food, f"[age_food] {age}.flat_food")
    own = general.get("tier_modifier", {}).get(str(tier), {}).get("local_monthly_food", 0)
    return _decimal(own, f"general.tier_modifier.{tier}.local_monthly_food")


def building_amounts(
    building_key: str,
    base_output: Decimal | float | str,
    good_price: Decimal | float | str = 1,
    config: ProvisioningConfig | None = None,
) -> ProvisioningAmounts:
    """The Provision amounts a building carries: the crop-farm rule for crop farms (with their tier's Province Food
    share), the buy-back rule otherwise."""
    if building_key in CROP_FARM_GOODS:
        tier = CROP_FARM_TIERS[building_key]
        share = crop_province_food_share(tier)
        if share is None:
            return crop_provisioning_amounts(base_output, good_price, config)
        amounts, _ = crop_food_split(base_output, crop_tier_flat_food(tier), good_price, config, share)
        return amounts
    return provisioning_amounts(base_output, good_price, config)


def round_amount(value: Decimal) -> Decimal:
    return max(value.quantize(_STEP, rounding=ROUND_HALF_UP), _STEP)


def format_amount(value: Decimal) -> str:
    text = format(value.quantize(_STEP, rounding=ROUND_HALF_UP).normalize(), "f")
    return text


def provision_method(building_key: str) -> str:
    return f"pp_{building_key}_provision"


def legacy_sell_method(building_key: str) -> str:
    """The former Sell the Surplus method of the slot (removed 2026-10-02 with the store lever)."""
    return f"pp_{building_key}_sell_surplus"


def slot_methods(building_key: str) -> tuple[str, ...]:
    return (provision_method(building_key),)


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
    entries[f"{provision_method(building_key)}_desc"] = PROVISION_DESC.format(noun=noun)
    return entries


def evaluation_rules(building_key: str) -> dict[str, dict[str, Any]]:
    """Per-method `evaluation.production_methods` entries (allow rules) for the Provisioning method."""
    profit = (
        "Provisioning takes a token of the crop and feeds the province; it is the farm's AI gate, so its margin is far above the threshold by design."
        if building_key in CROP_FARM_GOODS
        else "Provisioning is balanced at the Province Food floor (12 food per gold of crop); the province store moves its output."
    )
    return {
        provision_method(building_key): {
            "allow_rules": {
                "profit_percent": profit,
                "input_throughput": "Existing accepted input scale predates the global employment throughput baseline.",
                "output_throughput": "Existing accepted output scale predates the global employment throughput baseline.",
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
