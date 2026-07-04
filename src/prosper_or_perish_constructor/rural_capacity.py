"""Shared rural-capacity constants used by generators and tests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

import yaml


LAND_FARM_BUILDINGS = (
    "farming_village",
    "husbandry_farmstead",
    "farming_village_rotations",
    "model_farm",
    "fruit_orchard",
    "nursery_orchard",
    "pomological_orchard",
    "sheep_farms",
    "hurdled_sheepcotes",
    "enclosed_sheep_walks",
    "horse_breeders",
    "stud_farm",
    "elephant_kraal",
    "fiber_crops_farm",
    "fiber_dressing_yard",
    "cotton_plantation",
    "cotton_farm",
    "market_cotton_farm",
    "sugar_plantation",
    "sugarcane_farm",
    "trapiche_sugarcane_farm",
    "tobacco_plantation",
    "tobacco_farm",
    "market_tobacco_farm",
    "dye_plantation",
    "chili_plantation",
    "clove_grove",
    "cocoa_grove",
    "managed_cocoa_grove",
    "coffee_grove",
    "terraced_coffee_grove",
    "incense_grove",
    "pepper_garden",
    "managed_pepper_garden",
    "saffron_croft",
    "saffron_kiln_croft",
    "sericulture_farm",
    "regulated_sericulture_farm",
    "simplers_grove",
    "tea_garden",
    "tea_sorting_garden",
    "vineyard_estate",
)
FISH_CAP_BUILDINGS = (
    "fishing_village",
    "net_curing_yard",
    "ocean_fishery",
    "drift_net_fishery",
    "offshore_fishery",
)
FOREST_CAP_BUILDINGS = (
    "forest_village",
    "managed_forest_village",
    "lumber_mill",
    "water_sawmill",
    "lumber_mill_improved",
)
FARM_WATER_CONTROL_BUILDINGS = (
    ("irrigation_systems", "0.60"),
    ("bund", "0.60"),
    ("terraces", "0.60"),
    ("polders", "0.60"),
    ("khmer_baray", "0.60"),
    ("aqueduct_system", "2"),
)


def capacity_max_omitted_buildings_by_building(
    *,
    blueprint_root: Path,
    capacity_buildings: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    """Return max-level capacity rows to omit for capacity upgrade chains.

    Every building omits its own capacity-consumption row. Buildings with
    `upgrade_chain` metadata also omit lower tiers in the same chain so direct
    upgrades can convert already-reserved capacity.
    """
    capacity_order = tuple(capacity_buildings)
    capacity_set = set(capacity_order)
    omissions = {building: (building,) for building in capacity_order}
    chains: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for path in sorted(blueprint_root.glob("*.yml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        if not isinstance(raw, Mapping):
            continue
        building = raw.get("building")
        building_key = building.get("key") if isinstance(building, Mapping) else path.stem
        if building_key not in capacity_set:
            continue

        chain = raw.get("upgrade_chain")
        if not isinstance(chain, Mapping):
            continue
        family = chain.get("family")
        tier = chain.get("tier")
        if not isinstance(family, str) or not isinstance(tier, int):
            continue
        chains[family].append((tier, building_key))

    for family, members in chains.items():
        tiers: set[int] = set()
        lower_tiers: list[str] = []
        for tier, building in sorted(members):
            if tier in tiers:
                raise ValueError(f"{family}: duplicate capacity upgrade tier {tier}")
            tiers.add(tier)
            lower_tiers.append(building)
            omissions[building] = tuple(lower_tiers)

    return omissions


def farm_capacity_modifier_for_building(building: str) -> str:
    return f"farm_capacity_from_{building}"
