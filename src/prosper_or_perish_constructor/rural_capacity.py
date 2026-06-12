"""Shared rural-capacity constants used by generators and tests."""

from __future__ import annotations


LAND_FARM_BUILDINGS = (
    "farming_village",
    "farming_village_rotations",
    "model_farm",
    "fruit_orchard",
    "pomological_orchard",
    "sheep_farms",
    "enclosed_sheep_walks",
    "horse_breeders",
    "elephant_kraal",
    "fiber_crops_farm",
    "cotton_plantation",
    "cotton_farm",
    "sugar_plantation",
    "sugarcane_farm",
    "tobacco_plantation",
    "tobacco_farm",
    "dye_plantation",
    "chili_plantation",
    "clove_grove",
    "cocoa_grove",
    "coffee_grove",
    "incense_grove",
    "pepper_garden",
    "saffron_croft",
    "sericulture_farm",
    "simplers_grove",
    "tea_garden",
    "vineyard_estate",
)
FISH_CAP_BUILDINGS = (
    "fishing_village",
    "ocean_fishery",
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
def farm_capacity_modifier_for_building(building: str) -> str:
    return f"farm_capacity_from_{building}"
