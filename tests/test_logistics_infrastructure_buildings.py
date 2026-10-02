import re
from pathlib import Path

from eu5gameparser.clausewitz.syntax import CList
from eu5gameparser.load_order import load_merged_directory, load_profile
from prosper_or_perish_constructor import yaml_io


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
BLUEPRINTS = ROOT / "blueprints" / "accepted" / "buildings"
RIVER_BLUEPRINT = BLUEPRINTS / "river_boatmen_yard.yml"
# building -> (logistics class, max_levels, rank flags)
LOGISTICS_BUILDINGS = {
    "river_boatmen_yard": ("river", "pp_river_boatmen_yard_max_level", {"rural_settlement", "town", "city", "megalopolis"}),
    "coastal_shipping_office": ("coastal", "pp_coastal_shipping_office_max_level", {"town", "city", "megalopolis"}),
    "transport_office": ("urban", "100", {"town", "city", "megalopolis"}),
    "carrier_inn": ("overland", "100", {"rural_settlement", "town"}),
    "pp_caravanserai": ("overland", "100", {"rural_settlement", "town"}),
    "pp_oasis_caravan_station": ("overland", "100", {"rural_settlement", "town"}),
    "pp_yam_station": ("overland", "100", {"rural_settlement", "town"}),
    "pp_banjara_tanda": ("overland", "100", {"rural_settlement", "town"}),
    "pp_llama_caravan_post": ("overland", "100", {"rural_settlement", "town"}),
}
BULKY_SCALE = {"pp_caravanserai": 1.5, "pp_oasis_caravan_station": 1.5, "pp_llama_caravan_post": 1.5, "pp_banjara_tanda": 0.5}
LOGISTICS_CAPS = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_logistics_building_caps.txt"
LOCATION_MODIFIERS = MOD_ROOT / "main_menu" / "common" / "static_modifiers" / "pp_location_modifier_adjustments.txt"
BUILDING_CAP_TYPES = MOD_ROOT / "main_menu" / "common" / "modifier_type_definitions" / "pp_building_cap_modifiers.txt"
BUILDING_CAP_ICONS = MOD_ROOT / "main_menu" / "common" / "modifier_icons" / "pp_building_cap_modifier_icons.txt"
BUILDING_ADJUSTMENTS_LOC = MOD_ROOT / "main_menu" / "localization" / "english" / "pp_building_adjustments_l_english.yml"
CONSTRUCTION_DEMANDS = MOD_ROOT / "in_game" / "common" / "goods_demand" / "pp_logistics_infrastructure_construction.txt"
MARKET_VILLAGE_MARKET_ACCESS_BLUEPRINT = BLUEPRINTS / "market_village_market_access.yml"
MARKET_VILLAGE_MARKET_ACCESS_RENDERED = MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_market_village_market_access.txt"
VICTUALLING_YARD_BLUEPRINT = BLUEPRINTS / "victualling_yard.yml"
TAVERN_BLUEPRINT = BLUEPRINTS / "tavern.yml"
VICTUALLING_YARD_RENDERED = MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_victualling_yard.txt"
TAVERN_RENDERED = MOD_ROOT / "in_game" / "common" / "building_types" / "zz_pp_tavern.txt"
EMPLOYMENT_PRIORITIES = MOD_ROOT / "in_game" / "common" / "script_values" / "pp_employment_priority.txt"
LOGISTICS_PRIORITY_GROUPS = (  # 2026-10-01: above every other employment priority
    ("pp_river_logistics_priority", 80000000),
    ("pp_coastal_logistics_priority", 70000000),
    ("pp_city_logistics_priority", 60000000),
    ("pp_rural_logistics_priority", 50000000),
)
EMPLOYMENT_SYSTEMS = MOD_ROOT / "in_game" / "common" / "employment_systems" / "pp_food_security_priorities.txt"
PRIORITY_TAG = {
    "river_boatmen_yard": "pp_river_logistics_priority",
    "coastal_shipping_office": "pp_coastal_logistics_priority",
    "transport_office": "pp_city_logistics_priority",
}


def _blueprint(building: str) -> dict:
    return yaml_io.safe_load((BLUEPRINTS / f"{building}.yml").read_text(encoding="utf-8"))


def _custom_tags(text: str) -> set[str]:
    match = re.search(r"custom_tags\s*=\s*\{\s*(?P<tags>[^}]*)\}", text)
    assert match is not None
    return set(match.group("tags").split())


def _field(body: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*([^\s#]+)", body, flags=re.M)
    assert match is not None, f"missing {key}"
    return match.group(1)


def _block(body: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}\s*=\s*\{{(?P<body>.*?)\n\}}", body, flags=re.S)
    assert match is not None, f"missing {key} block"
    return match.group("body")


def test_river_boatmen_yard_cap_scales_with_river_level() -> None:
    blueprint = RIVER_BLUEPRINT.read_text(encoding="utf-8")
    assert "max_levels = pp_river_boatmen_yard_max_level" in blueprint
    location_potential = blueprint.split("location_potential = {", 1)[1].split("}", 1)[0]
    assert "has_river = yes" in location_potential
    assert "is_adjacent_to_lake = yes" not in location_potential

    cap_value = LOGISTICS_CAPS.read_text(encoding="utf-8")
    assert 'desc = "BUILDING_LEVEL_RIVER_FREIGHT_CAPACITY"' in cap_value
    assert "value = modifier:pp_river_boatmen_yard_cap_modifier" in cap_value
    assert 'min = { desc = "BUILDING_LEVEL_WB_MINIMUM" value = 0 }' in cap_value

    modifiers = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    for river_level in range(1, 6):
        block = re.search(
            rf"TRY_INJECT:river_flowing_through_{river_level} = \{{(?P<body>.*?)\n\}}",
            modifiers,
            flags=re.S,
        )
        assert block is not None
        assert f"pp_river_boatmen_yard_cap_modifier = {river_level * 3}" in block.group("body")

    assert "pp_river_boatmen_yard_cap_modifier" in BUILDING_CAP_TYPES.read_text(encoding="utf-8-sig")
    assert "gfx/interface/icons/buildings/river_boatmen_yard.dds" in BUILDING_CAP_ICONS.read_text(encoding="utf-8-sig")

    localization = BUILDING_ADJUSTMENTS_LOC.read_text(encoding="utf-8-sig")
    assert 'BUILDING_LEVEL_RIVER_FREIGHT_CAPACITY: "From River Size"' in localization
    assert 'MODIFIER_TYPE_NAME_pp_river_boatmen_yard_cap_modifier: "River Freight Capacity"' in localization


def test_coastal_shipping_office_cap_scales_with_natural_harbor() -> None:
    blueprint = (BLUEPRINTS / "coastal_shipping_office.yml").read_text(encoding="utf-8")
    assert "max_levels = pp_coastal_shipping_office_max_level" in blueprint
    assert "is_port = yes" in blueprint

    cap_value = LOGISTICS_CAPS.read_text(encoding="utf-8")
    assert "pp_coastal_shipping_office_max_level" in cap_value
    assert 'desc = "BUILDING_LEVEL_BASE"' in cap_value
    assert "value = 10" in cap_value
    assert 'desc = "BUILDING_LEVEL_NATURAL_HARBOR_SUITABILITY"' in cap_value
    assert "value = modifier:pp_coastal_shipping_office_cap_modifier" in cap_value
    assert 'min = { desc = "BUILDING_LEVEL_WB_MINIMUM" value = 0 }' in cap_value

    modifiers = LOCATION_MODIFIERS.read_text(encoding="utf-8-sig")
    poor = re.search(r"TRY_INJECT:location_template_natural_harbor_suitability_poor = \{(?P<body>.*?)\n\}", modifiers, flags=re.S)
    good = re.search(r"TRY_INJECT:location_template_natural_harbor_suitability_good = \{(?P<body>.*?)\n\}", modifiers, flags=re.S)
    assert poor is not None and good is not None
    assert "pp_coastal_shipping_office_cap_modifier = -20" in poor.group("body")
    assert "pp_coastal_shipping_office_cap_modifier = 10" in good.group("body")


def test_logistics_buildings_are_laborer_buildings_that_never_close() -> None:
    for building, (cls, max_levels, ranks) in LOGISTICS_BUILDINGS.items():
        blueprint = _blueprint(building)
        body = blueprint["building"]["body"]
        assert blueprint["logistics"]["class"] == cls
        assert blueprint["logistics"].get("bulky_scale", 1.0) == BULKY_SCALE.get(building, 1.0)
        assert blueprint["footprint"] == "infrastructure"
        assert blueprint["gate_method"]
        assert "price =" not in body and "prices" not in blueprint
        assert _field(body, "max_levels") == max_levels
        assert _field(body, "pop_type") == "laborers"
        assert _field(body, "employment_size") == "1"
        assert _field(body, "category") == "infrastructure_category"
        assert _field(body, "can_close") == "no"
        assert _field(body, "always_add_demands") == "yes"
        assert _field(body, "ai_forbid_shutdown") == "yes"
        assert "forbidden_for_estates" not in body
        assert "important_for_AI" not in body
        assert {rank for rank in ("rural_settlement", "town", "city", "megalopolis") if f"{rank} = yes" in body} == ranks
        assert _custom_tags(body) == {"pp_logistics", PRIORITY_TAG.get(building, "pp_rural_logistics_priority")}
        assert f"construction_demand = pp_{building.removeprefix('pp_')}_construction" in body
        allow = _block(body, "allow")
        assert "market_access < 0.85" in allow and "total_building_levels >= 15" in allow
        # market access and owner conditions never go into location_potential (the game re-checks it on owner change)
        potential = _block(body, "location_potential") if "location_potential = {" in body else ""
        assert "market_access" not in potential and "owner" not in potential and "development" not in potential
        assert _block(body, "raw_modifier").split() == ["local_market_access", "=", "0.1"]


def test_transport_office_opens_in_cities_and_developed_towns() -> None:
    body = _blueprint("transport_office")["building"]["body"]
    allow = _block(body, "allow")
    assert "NOT = { location_rank = location_rank:town }" in allow
    assert "development >= 10" in allow
    assert "location_potential = {" not in body


def test_logistics_construction_demands_exist_without_negative_goods() -> None:
    text = CONSTRUCTION_DEMANDS.read_text(encoding="utf-8-sig")
    for building in LOGISTICS_BUILDINGS:
        key = f"pp_{building.removeprefix('pp_')}_construction"
        block = re.search(rf"(?m)^{key} = \{{(?P<body>.*?)\n\}}", text, re.S)
        assert block is not None, key
        amounts = [float(v) for v in re.findall(r"=\s*(-?[0-9.]+)", block.group("body"))]
        assert amounts and min(amounts) > 0, key


def test_logistics_building_priorities_rank_above_everything() -> None:
    # 2026-10-01: a short-staffed logistics building loses market access, and at 0 access a location buys no inputs, so
    # logistics are staffed first in every employment system: river > coastal > city > rural, all above food security,
    # education and the capitalism variants' category bonuses together.
    priority_text = EMPLOYMENT_PRIORITIES.read_text(encoding="utf-8-sig")
    assert priority_text.count("limit = { has_tag = pp_logistics }") == 1
    for tag, priority in LOGISTICS_PRIORITY_GROUPS:
        pattern = re.compile(rf"has_tag\s*=\s*{re.escape(tag)}\s*\}}\s*add\s*=\s*{priority}\s*\}}")
        assert pattern.search(priority_text), tag
    values = [priority for _tag, priority in LOGISTICS_PRIORITY_GROUPS]
    assert values == sorted(values, reverse=True)
    others = {int(v) for v in re.findall(r"add = (\d+)", priority_text)} - set(values)
    categories = {int(v) for v in re.findall(r"add = (\d+)", EMPLOYMENT_SYSTEMS.read_text(encoding="utf-8-sig"))}
    # every logistics building is infrastructure_category, so a category bonus lifts all of them alike
    assert min(values) > max(others) + max(categories) + 1000


def test_market_village_market_access_is_neutralized_by_inject_blueprint() -> None:
    blueprint = MARKET_VILLAGE_MARKET_ACCESS_BLUEPRINT.read_text(encoding="utf-8")
    assert "mode: REPLACE" in blueprint
    assert "key: market_village" in blueprint
    assert "local_market_access = -0.005" in blueprint
    assert "unique_production_methods" in blueprint
    assert "pp_market_village_rural_blacksmith" in blueprint

    rendered = MARKET_VILLAGE_MARKET_ACCESS_RENDERED.read_text(encoding="utf-8-sig")
    assert "REPLACE:market_village" in rendered
    assert "local_market_access = -0.005" in rendered
    assert "unique_production_methods" in rendered
    assert "pp_market_village_rural_blacksmith" in rendered

    profile = load_profile("constructor", ROOT / "constructor.load_order.toml")
    merged = load_merged_directory(profile, "building_types")
    market_village = next(entry for entry in merged.entries if entry.key == "market_village")
    assert isinstance(market_village.value, CList)

    total = 0.0
    for modifier in market_village.value.values("modifier"):
        assert isinstance(modifier, CList)
        for entry in modifier.entries:
            if entry.key == "local_market_access":
                assert isinstance(entry.value, int | float)
                total += float(entry.value)

    assert total == 0.0


def test_victuals_trade_templates_split_export_and_import_flows() -> None:
    manifest = yaml_io.safe_load((ROOT / "blueprints/buildings.manifest.yml").read_text())
    assert manifest["enabled"]["buildings/victualling_yard.yml"] is True
    assert manifest["enabled"]["buildings/tavern.yml"] is True
    assert VICTUALLING_YARD_RENDERED.exists()
    yard_texts = tuple(path.read_text(encoding="utf-8-sig") for path in (VICTUALLING_YARD_BLUEPRINT, VICTUALLING_YARD_RENDERED))
    tavern_texts = tuple(path.read_text(encoding="utf-8-sig") for path in (TAVERN_BLUEPRINT, TAVERN_RENDERED))

    # the harbour Victualling Yard packs a little of the store and ships in grain: real victuals, no negative input, no
    # storage leg (its profit follows the victuals and grain prices only), no packing slot (the grain arrives packed)
    assert "victualling_yard: Victualling Yard" in yard_texts[0]
    for text in yard_texts:
        assert "pp_victualling_yard_merchantmen" in text
        assert re.search(r"pp_victualling_yard_merchantmen = \{[^}]*produced = victuals[^}]*output = 0\.268", text, re.S)
        assert re.search(r"pp_victualling_yard_grain_shipment = \{[^}]*wheat = 2\.332[^}]*output = 0\.932", text, re.S)
        # every staple shipment shares the grain numbers (1 gold, 12 food each): food-neutral
        for good in ("rice", "millet", "maize", "legumes", "fish"):
            assert re.search(rf"pp_victualling_yard_{good}_shipment = \{{[^}}]*{good} = 2\.332[^}}]*output = 0\.932", text, re.S)
        assert "surplus_sales" not in text and "province_food_sales" not in text
        assert not re.search(r"\bvictuals = -", text)
        assert "export_tally" not in text
        assert "pp_tavern_serve_victuals" not in text
        for packing in ("loose_stores", "pottery_jars", "coopered_barrels", "tin_cans"):
            assert f"pp_victualling_yard_{packing}" not in text

    assert "tavern: Tavern" in tavern_texts[0]
    for text in tavern_texts:
        assert "pp_tavern_serve_victuals" in text
        # 2026-10-01: the Tavern's food is Serve Victuals' Province Food (follows the victuals it bought), no flat food
        assert re.search(r"pp_tavern_serve_victuals = \{[^}]*produced = local_food[^}]*victuals = 0\.8[^}]*output = 24\.0", text, re.S)
        assert "victuals = 0.8" in text
        # store lever (2026-10-02): no Scarcity Premium slot and no droop; the Tavern earns by the Province Food
        # output of its Serve method, and a working Tavern takes a Grange's Surplus Sales in the location away
        assert "province_food_purchase" not in text and "scarcity_premium" not in text
        assert "local_province_food_sales_output_modifier = -5.0" in text
        assert "pp_victualling_yard_merchantmen" not in text

    for text in yard_texts:
        assert "local_monthly_food = -8.0" in text
        assert "max_levels = victualling_yard_max_level" in text
        assert "local_burghers_estate_power = 0.05" in text
        assert "local_nobles_estate_power" not in text
        assert "local_market_access" not in text

    for text in tavern_texts:
        assert not re.search(r"^\s*local_monthly_food\s*=", text, re.M)   # no flat food line
        assert "max_levels = tavern_max_level" in text
        # towns and larger that are province capitals only (2026-10-01)
        assert "rural_settlement = no" in text
        assert re.search(r"location_potential = \{\s*is_province_capital = yes\s*\}", text)
        assert "local_nobles_estate_power" not in text
        assert "local_peasant_enfranchisment" not in text
