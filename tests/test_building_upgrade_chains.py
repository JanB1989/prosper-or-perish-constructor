from __future__ import annotations

import json
from pathlib import Path
import re

import polars as pl
import yaml

from eu5gameparser.domain.eu5 import load_eu5_data
from eu5_mod_orchestrator.config import load_project_config


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
LABELING_BASELINE = (
    ROOT.parent / "ProsperOrPerishLabelingPipeline" / "base_data" / "locations_with_raw_material.parquet"
)
ADVANCES_PATH = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "advances"
    / "pp_local_resource_productivity_advances.txt"
)
PROSPERITY_ADVANCES_PATH = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "advances"
    / "pp_prosperity_advances_adjustments.txt"
)
FISHING_ADVANCES_PATH = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "advances"
    / "pp_fishing_village.txt"
)
GAME_START_PATH = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "on_action"
    / "pp_game_start.txt"
)
BUILDING_TYPES_ROOT = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "in_game"
    / "common"
    / "building_types"
)
LOCALIZATION_ROOT = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "main_menu"
    / "localization"
    / "english"
)
LOCATION_MODIFIER_ADJUSTMENTS_PATH = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "main_menu"
    / "common"
    / "static_modifiers"
    / "pp_location_modifier_adjustments.txt"
)
RAW_MATERIAL_OUTPUT_TO_RGO_ADVANCES = {
    "arabia_felix": 0.10,
    "otm_lord_of_bungo": 0.10,
    "sba_multiple_shugo": 0.10,
    "cultivate_the_land": 0.05,
    "llama_michis": 0.10,
    "por_estimulate_rural_areas": 0.10,
    "hyanyak_system": 0.10,
    "wealth_of_mesoamerica": 0.10,
    "free_subjects": 0.10,
    "gra_modernized_economy": 0.20,
    "bur_rich_soil_of_burgundy": 0.20,
    "neapolitan_industrialization": 0.20,
    "produktplakatet": 0.10,
    "tre_trapezuntine_endurance": 0.10,
}

EXPECTED_CHAINS = {
    "alum_quarry": [
        ("alum_quarry", "advanced_mining"),
        ("alum_works", "green_vitriol"),
    ],
    "coal_mine": [
        ("coal_mine", None),
        ("coal_mine_improved", "coal_improvements_absolutism"),
        ("coal_mine_revolutions", "coal_improvements_revolutions"),
    ],
    "mercury_mine": [
        ("cinnabar_pit", None),
        ("quicksilver_retort", "pan_amalgamation_advance"),
    ],
    "copper_mine": [
        ("copper_mine", None),
        ("copper_mine_adit", "new_currency_demands"),
    ],
    "silver_mine": [
        ("silver_mine", None),
        ("silver_mine_improved", "saiger_process_discovery"),
    ],
    "lead_mine": [
        ("lead_mine", None),
        ("lead_mine_bole_smelting", "bole_smelting"),
        ("lead_mine_cupola_smelting", "cupola_smelting"),
    ],
    "marble_quarry": [
        ("marble_quarry", None),
        ("marble_saw_yard", "renaissance_sculptures"),
    ],
    "tin_mine": [
        ("tin_streamworks", None),
        ("tin_stamping_mill", "new_currency_demands"),
    ],
    "gold_mine": [
        ("gold_diggings", None),
        ("gold_stamp_mill", "pan_amalgamation_advance"),
    ],
    "gem_mine": [
        ("gem_gravel_pit", None),
        ("gem_sluice", "foreign_mining_techniques"),
    ],
    "iron_mine": [
        ("iron_mine", None),
        ("iron_mine_improved", "rgo_size_advance_discovery"),
        ("iron_mine_deep", "slitting_mills"),
    ],
    "bog_iron_smelter": [
        ("bog_iron_smelter", None),
        ("bog_iron_smelter_blast_furnace", "blast_furnace"),
        ("bog_iron_smelter_coke_blast_furnace", "coke_blast_furnace"),
    ],
    "cookery": [
        ("cookery", None),
        ("victualling_yard", "food_advance_absolutism"),
    ],
}

ADDED_MINE_BUILDING_GOODS = {
    "alum_quarry": "alum",
    "coal_mine": "coal",
    "coal_mine_improved": "coal",
    "coal_mine_revolutions": "coal",
    "cinnabar_pit": "mercury",
    "quicksilver_retort": "mercury",
    "copper_mine": "copper",
    "copper_mine_adit": "copper",
    "gem_gravel_pit": "gems",
    "gem_sluice": "gems",
    "gold_diggings": "goods_gold",
    "gold_stamp_mill": "goods_gold",
    "iron_mine": "iron",
    "iron_mine_improved": "iron",
    "iron_mine_deep": "iron",
    "silver_mine": "silver",
    "silver_mine_improved": "silver",
    "lead_mine": "lead",
    "lead_mine_bole_smelting": "lead",
    "lead_mine_cupola_smelting": "lead",
    "marble_quarry": "marble",
    "marble_saw_yard": "marble",
    "salt_mine": "salt",
    "salt_mine_improved": "salt",
    "tin_streamworks": "tin",
    "tin_stamping_mill": "tin",
    "stone_quarry_improved": "stone",
}
ADDED_MINE_BUILDING_TAG = "pp_mine_building"

DEACTIVATED_MINING_VILLAGE_BLUEPRINTS = {
    "buildings/mining_village.yml",
    "buildings/mining_village_blast_furnace.yml",
    "buildings/mining_village_slitting_mills.yml",
    "buildings/mining_village_coke_blast_furnace.yml",
    "buildings/mining_village_hot_blast_furnace.yml",
}
GAME_START_DIRECT_RGO_BUILDINGS = {
    "alum_quarry",
    "coal_mine",
    "copper_mine",
    "gem_gravel_pit",
    "gold_diggings",
    "iron_mine",
    "lead_mine",
    "marble_quarry",
    "cinnabar_pit",
    "salt_collector",
    "salt_mine",
    "inland_saltworks",
    "silver_mine",
    "saltpeter_beds",
    "tin_streamworks",
}
GAME_START_CAPACITY_BUILDING_GATES = {
    "fiber_crops_farm": "farm_capacity",
    "fishing_village": "fish_capacity",
    "forest_village": "forest_capacity",
    "horse_breeders": "farm_capacity",
    "lumber_mill": "forest_capacity",
    "ocean_fishery": "fish_capacity",
}
GAME_START_DISABLED_CAPACITY_STARTUP_BUILDINGS = {"farming_village", "fruit_orchard", "sheep_farms"}
RAW_MATERIAL_BASE_PRODUCERS = {
    "horse_breeders": ("horses", "pp_horse_breeders_base_horses"),
    "sand_pit": ("sand", "pp_sand_pit_base_sand"),
    "stone_quarry": ("stone", "pp_stone_quarry_base_stone"),
    "incense_grove": ("incense", "pp_incense_grove_base_incense"),
    "fiber_crops_farm": ("fiber_crops", "pp_fiber_crops_farm_base_fiber_crops"),
    "ivory_hunting_camp": ("ivory", "pp_ivory_hunting_camp_base_ivory"),
    "salt_collector": ("salt", "pp_coastal_saltern_base_salt"),
    "salt_mine": ("salt", "pp_salt_mine_base_salt"),
    "inland_saltworks": ("salt", "pp_inland_saltworks_base_salt"),
    "saltpeter_beds": ("saltpeter", "pp_saltpeter_beds_base_saltpeter"),
    "vineyard_estate": ("wine", "pp_vineyard_estate_base_wine"),
    "cotton_plantation": ("cotton", "pp_cotton_plantation_base_cotton"),
    "cotton_farm": ("cotton", "pp_cotton_farm_base_cotton"),
    "sugar_plantation": ("sugar", "pp_sugar_plantation_base_sugar"),
    "sugarcane_farm": ("sugar", "pp_sugarcane_farm_base_sugar"),
    "tobacco_plantation": ("tobacco", "pp_tobacco_plantation_base_tobacco"),
    "tobacco_farm": ("tobacco", "pp_tobacco_farm_base_tobacco"),
}
SLAVE_PLANTATION_REPLACEMENTS = {
    "cotton_plantation": "cotton",
    "sugar_plantation": "sugar",
    "tobacco_plantation": "tobacco",
}
NON_SLAVE_CROP_FARMS = {
    "cotton_farm": {
        "good": "cotton",
        "base_method": "pp_cotton_farm_base_cotton",
        "worked_method": "pp_cotton_farm_gin_house",
        "inputs": {
            "lumber": "0.093",
            "fiber_crops": "0.040",
            "tools": "0.011",
        },
        "removed_inputs": {"leather", "slaves_goods"},
    },
    "sugarcane_farm": {
        "good": "sugar",
        "base_method": "pp_sugarcane_farm_base_sugar",
        "worked_method": "pp_sugarcane_farm_boiling_house",
        "inputs": {
            "lumber": "0.083",
            "pottery": "0.100",
            "tools": "0.010",
        },
        "removed_inputs": {"coal", "slaves_goods"},
    },
    "tobacco_farm": {
        "good": "tobacco",
        "base_method": "pp_tobacco_farm_base_tobacco",
        "worked_method": "pp_tobacco_farm_curing_barns",
        "inputs": {
            "lumber": "0.117",
            "fiber_crops": "0.017",
            "tools": "0.015",
        },
        "removed_inputs": {"pottery", "slaves_goods"},
    },
}
RAW_PROCESSOR_EXCLUSIONS = {
    "perfumery": "incense",
    "saltpeter_guild": "saltpeter",
    "saltpeter_workshop": "saltpeter",
    "putrefaction_works": "saltpeter",
    "putrefaction_mill": "saltpeter",
}
PM_PRECISION_RE = re.compile(
    r"^\s*(?P<key>[A-Za-z][A-Za-z0-9_]*)\s*=\s*(?P<value>-?\d+\.\d{4,})\b"
)
PM_PRECISION_SKIP_KEYS = {"debug_max_profit"}

DEACTIVATED_BOG_IRON_BLUEPRINTS = {
    "buildings/bog_iron_smelter_slitting_mills.yml",
    "buildings/bog_iron_smelter_hot_blast_furnace.yml",
}
SALT_MINE_TOPOGRAPHIES = {"hills", "mountains", "plateau"}
SALT_MINE_CLIMATES = {"continental", "mediterranean", "oceanic"}
SALT_MINE_VEGETATION = {"farmland", "forest", "grasslands", "woods"}
SALT_MINE_MODIFIERS = {"sahara_salt_mines_base", "turda_salt_mines_base"}
SALT_MINE_DIRECT_LOCATIONS = {
    "cardona",
    "chicaquicha",
    "dina",
    "dinkot",
    "hallein",
    "khewra",
    "khushab",
    "salzburg",
    "wieliczka",
}
SALT_MINE_EXCLUDED_LOCATIONS = {"anana", "hall", "moutiers", "salins_les_bains"}
SALT_MINE_EXCLUDED_REGIONS = {
    "south_china_region",
    "tibet_region",
    "west_china_region",
    "xinjiang_region",
}


def _load_blueprint(key: str) -> dict:
    with (BLUEPRINT_ROOT / "buildings" / f"{key}.yml").open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    assert isinstance(raw, dict)
    return raw


def _body_custom_tags(body: str) -> set[str]:
    match = re.search(r"^\s*custom_tags\s*=\s*\{(?P<tags>[^}]*)\}", body, flags=re.M)
    if match is None:
        return set()
    return set(match.group("tags").split())


def _obsolete_entries(body: str) -> list[str]:
    return re.findall(r"^\s*obsolete\s*=\s*([A-Za-z0-9_]+)\s*$", body, flags=re.M)


def _managed_building_output_paths_by_key() -> dict[str, Path]:
    paths_by_key: dict[str, Path] = {}
    for path in sorted(BUILDING_TYPES_ROOT.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for key in re.findall(r"^# >>> eu5-building-pipeline:([a-z0-9_]+):building$", text, flags=re.M):
            if key in paths_by_key:
                raise AssertionError(f"duplicate managed building output for {key}: {paths_by_key[key]} and {path}")
            paths_by_key[key] = path
    return paths_by_key


def _has_salt_mine_marker(row: dict) -> bool:
    modifier = str(row.get("modifier") or "")
    if any(marker in modifier for marker in SALT_MINE_MODIFIERS):
        return True
    if row.get("location_tag") in SALT_MINE_DIRECT_LOCATIONS:
        return True
    if row.get("location_tag") in SALT_MINE_EXCLUDED_LOCATIONS:
        return False
    if row.get("region") in SALT_MINE_EXCLUDED_REGIONS:
        return False
    return (
        row.get("topography") in SALT_MINE_TOPOGRAPHIES
        and row.get("climate") in SALT_MINE_CLIMATES
        and row.get("vegetation") in SALT_MINE_VEGETATION
    )


def _salt_location_families(row: dict) -> list[str]:
    raw_salt = row.get("raw_material") == "salt"
    coastal = row.get("is_coastal") is True
    mine_marker = _has_salt_mine_marker(row)

    families: list[str] = []
    if raw_salt and coastal:
        families.append("coastal_saltern")
    if raw_salt and not coastal and mine_marker:
        families.append("salt_mine")
    if raw_salt and not coastal and not mine_marker:
        families.append("inland_saltworks")
    return families


def _advance_block(advance: str, text: str) -> str:
    match = re.search(
        rf"(?:(?:REPLACE|TRY_INJECT):)?{re.escape(advance)}\s*=\s*\{{(?P<body>.*?)\n\}}",
        text,
        flags=re.S,
    )
    assert match is not None, f"{advance} block missing"
    return match.group("body")


def _active_advancement_modifiers() -> dict[str, dict[str, float]]:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    rows = data.advancements.to_dicts()
    return {row["name"]: json.loads(row.get("modifiers") or "{}") for row in rows}


def _production_method_precision_offenders(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    depth = 0
    production_method_depths: list[int] = []
    offenders: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if re.search(r"\bunique_production_methods\s*=\s*\{", line):
            production_method_depths.append(depth + line.count("{") - line.count("}"))
        if production_method_depths:
            match = PM_PRECISION_RE.match(line)
            if match and match.group("key") not in PM_PRECISION_SKIP_KEYS:
                relative = path.relative_to(ROOT)
                offenders.append(f"{relative}:{line_number}: {line.strip()}")
        depth += line.count("{") - line.count("}")
        while production_method_depths and depth < production_method_depths[-1]:
            production_method_depths.pop()

    return offenders


def _base_production_method_input_offenders(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    offenders: list[str] = []

    for index, line in enumerate(lines):
        match = re.match(
            r"\s*(?P<method>pp_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_base_[A-Za-z0-9_]+)\s*=\s*\{\s*$",
            line,
        )
        if match is None:
            continue
        method = match.group("method")
        if method.endswith("_base_maintenance"):
            continue
        block_lines: list[str] = []
        depth = line.count("{") - line.count("}")
        for block_line in lines[index + 1 :]:
            depth += block_line.count("{") - block_line.count("}")
            if depth < 1:
                break
            block_lines.append(block_line)
        for block_line in block_lines:
            key_match = re.match(r"\s*(?P<key>[A-Za-z][A-Za-z0-9_]*)\s*=", block_line)
            if key_match and key_match.group("key") not in {"produced", "output", "category"}:
                relative = path.relative_to(ROOT)
                offenders.append(f"{relative}:{index + 1}: {method} has input {key_match.group('key')}")

    return offenders


def _production_method_has_inputs_or_outputs(row: dict) -> bool:
    return bool(row["input_goods"]) or (row["produced"] is not None and row["output"] is not None)


def _matching_brace_index(text: str, opening_index: int) -> int:
    depth = 0
    for index in range(opening_index, len(text)):
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError(f"unclosed script block starting at {opening_index}")


def _iter_script_blocks(text: str, name: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(name)}\s*=\s*\{{")
    position = 0
    while match := pattern.search(text, position):
        opening_index = text.find("{", match.start(), match.end())
        closing_index = _matching_brace_index(text, opening_index)
        blocks.append((match.start(), closing_index + 1, text[match.start() : closing_index + 1]))
        position = match.end()
    return blocks


def _first_script_block(text: str, name: str) -> str:
    blocks = _iter_script_blocks(text, name)
    assert blocks, f"{name} block missing"
    return blocks[0][2]


def _normalized_first_script_block(text: str, name: str) -> str:
    blocks = _iter_script_blocks(text, name)
    if not blocks:
        return "<none>"
    assert len(blocks) == 1, f"expected one {name} block, found {len(blocks)}"
    lines = []
    for line in blocks[0][2].splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            lines.append(re.sub(r"\s+", " ", stripped))
    return "\n".join(lines)


def _enclosing_script_block(
    blocks: list[tuple[int, int, str]], position: int, name: str
) -> tuple[int, int, str]:
    candidates = [block for block in blocks if block[0] <= position < block[1]]
    assert candidates, f"{name} block missing around character {position}"
    return min(candidates, key=lambda block: block[1] - block[0])


def _script_line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def test_metal_building_upgrade_chains_are_explicit_and_unlockable() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    advances = "\n".join(
        (
            ADVANCES_PATH.read_text(encoding="utf-8"),
            PROSPERITY_ADVANCES_PATH.read_text(encoding="utf-8"),
        )
    )

    for family, chain in EXPECTED_CHAINS.items():
        for tier, (key, unlock_advance) in enumerate(chain):
            raw = _load_blueprint(key)

            assert f"buildings/{key}.yml" in enabled
            assert raw["tag"] == key
            assert raw["building"]["key"] == key

            upgrade_chain = raw.get("upgrade_chain")
            assert upgrade_chain == {
                "family": family,
                "tier": tier,
                "previous": chain[tier - 1][0] if tier > 0 else None,
                "next": chain[tier + 1][0] if tier + 1 < len(chain) else None,
                "unlock_advance": unlock_advance,
            }

            body = raw["building"]["body"]
            obsolete_entries = _obsolete_entries(body)
            if tier == 0:
                assert obsolete_entries == []
            else:
                assert obsolete_entries == [chain[tier - 1][0]]
                assert "icon" in raw, f"{key} must provide its own icon"
                assert raw["icon"]["output_dds"] == f"{key}.dds"

            if unlock_advance is not None:
                block = _advance_block(unlock_advance, advances)
                assert re.search(rf"^\s*unlock_building\s*=\s*{re.escape(key)}\s*$", block, flags=re.M)


def test_ocean_fishery_upgrade_chain_is_explicit_and_globally_unlockable() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    advances = FISHING_ADVANCES_PATH.read_text(encoding="utf-8")

    chain = [
        ("ocean_fishery", None),
        ("offshore_fishery", "pp_herring_buss"),
    ]
    for tier, (key, unlock_advance) in enumerate(chain):
        raw = _load_blueprint(key)

        assert f"buildings/{key}.yml" in enabled
        assert raw["tag"] == key
        assert raw["building"]["key"] == key
        assert raw.get("upgrade_chain") == {
            "family": "ocean_fishery",
            "tier": tier,
            "previous": chain[tier - 1][0] if tier > 0 else None,
            "next": chain[tier + 1][0] if tier + 1 < len(chain) else None,
            "unlock_advance": unlock_advance,
        }

    offshore_body = _load_blueprint("offshore_fishery")["building"]["body"]
    assert re.search(r"^\s*obsolete\s*=\s*ocean_fishery\s*$", offshore_body, flags=re.M)
    assert re.search(r"location_potential\s*=\s*\{\s*is_coastal\s*=\s*yes\s*\}", offshore_body)

    herring_block = _advance_block("pp_herring_buss", advances)
    assert re.search(r"^\s*unlock_building\s*=\s*offshore_fishery\s*$", herring_block, flags=re.M)
    assert "potential =" not in herring_block

    distant_water_block = _advance_block("pp_distant_water_fishing", advances)
    assert re.search(
        r"^\s*unlock_production_method\s*=\s*pp_offshore_fishery_distant_water_schooners\s*$",
        distant_water_block,
        flags=re.M,
    )
    assert "potential =" not in distant_water_block

    steam_block = _advance_block("pp_steam_trawling", advances)
    assert re.search(
        r"^\s*unlock_production_method\s*=\s*pp_offshore_fishery_steam_trawlers\s*$",
        steam_block,
        flags=re.M,
    )
    assert "potential =" not in steam_block


def test_offshore_fishery_output_tuning_and_evaluation_bands_are_locked() -> None:
    raw = _load_blueprint("offshore_fishery")
    body = raw["building"]["body"]
    expected_outputs = {
        "pp_offshore_fishery_herring_busses": "1.133",
        "pp_offshore_fishery_distant_water_schooners": "1.340",
        "pp_offshore_fishery_steam_trawlers": "1.32",
    }

    for method, output in expected_outputs.items():
        assert re.search(
            rf"{method}\s*=\s*\{{.*?\bproduced\s*=\s*fish\b.*?\boutput\s*=\s*{re.escape(output)}\b",
            body,
            flags=re.S,
        )

    assert raw["evaluation"]["bands"] == {
        "output_gold_per_1k": {"max": 1.42},
        "amortization_months": {"max": 900},
    }


def test_salt_production_families_are_explicit_and_unlockable() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    advances = ADVANCES_PATH.read_text(encoding="utf-8")

    assert "buildings/salt_collector.yml" not in enabled
    coastal = _load_blueprint("coastal_saltern")
    assert coastal["building"]["key"] == "salt_collector"
    assert coastal["building"]["mode"] == "REPLACE"

    expected_chains = {
        "salt_mine": [
            ("salt_mine", None),
            ("salt_mine_improved", "rgo_size_advance_discovery"),
        ],
        "inland_saltworks": [
            ("inland_saltworks", None),
            ("engineered_brine_saltworks", "pp_engineered_brine_saltworks"),
        ],
    }
    for family, chain in expected_chains.items():
        for tier, (key, unlock_advance) in enumerate(chain):
            raw = _load_blueprint(key)
            assert f"buildings/{key}.yml" in enabled
            assert raw["tag"] == key
            assert raw["building"]["key"] == key
            assert raw.get("upgrade_chain") == {
                "family": family,
                "tier": tier,
                "previous": chain[tier - 1][0] if tier > 0 else None,
                "next": chain[tier + 1][0] if tier + 1 < len(chain) else None,
                "unlock_advance": unlock_advance,
            }

            body = raw["building"]["body"]
            if tier == 0:
                assert "obsolete =" not in body
            else:
                previous = chain[tier - 1][0]
                assert re.search(rf"^\s*obsolete\s*=\s*{re.escape(previous)}\s*$", body, flags=re.M)
                assert raw["icon"]["output_dds"] == f"{key}.dds"

    rgo_size_discovery = _advance_block("rgo_size_advance_discovery", advances)
    assert re.search(
        r"^\s*unlock_building\s*=\s*salt_mine_improved\s*$",
        rgo_size_discovery,
        flags=re.M,
    )

    engineered = _load_blueprint("engineered_brine_saltworks")
    advancements = engineered.get("advancements")
    assert isinstance(advancements, list)
    advancement = next(item for item in advancements if item["key"] == "pp_engineered_brine_saltworks")
    assert re.search(r"^\s*requires\s*=\s*manufactories_advance\s*$", advancement["body"], flags=re.M)
    assert re.search(r"^\s*unlock_building\s*=\s*engineered_brine_saltworks\s*$", advancement["body"], flags=re.M)

    coal = _advance_block("coal_improvements_absolutism", advances)
    assert re.search(
        r"^\s*unlock_production_method\s*=\s*pp_engineered_brine_saltworks_mineral_fired_pans\s*$",
        coal,
        flags=re.M,
    )


def test_salt_building_location_potentials_are_mutually_exclusive() -> None:
    bodies = {
        key: _load_blueprint(key)["building"]["body"]
        for key in (
            "coastal_saltern",
            "salt_mine",
            "salt_mine_improved",
            "inland_saltworks",
            "engineered_brine_saltworks",
        )
    }
    combined = "\n".join(bodies.values())

    assert "vegetation = desert" not in combined
    assert re.search(
        r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:salt\s*is_coastal\s*=\s*yes\s*\}",
        bodies["coastal_saltern"],
    )
    for key in ("salt_mine", "salt_mine_improved"):
        body = bodies[key]
        assert "raw_material = goods:salt" in body
        assert "NOT = { is_coastal = yes }" in body
        assert "topography = salt_pans" not in body
        for topography in SALT_MINE_TOPOGRAPHIES:
            assert f"topography = {topography}" in body
        for climate in SALT_MINE_CLIMATES:
            assert f"climate = {climate}" in body
        for vegetation in SALT_MINE_VEGETATION:
            assert f"vegetation = {vegetation}" in body
        for modifier in SALT_MINE_MODIFIERS:
            assert f"has_location_modifier = {modifier}" in body
        for location in SALT_MINE_DIRECT_LOCATIONS | SALT_MINE_EXCLUDED_LOCATIONS:
            assert f"this = location:{location}" in body
        for region in SALT_MINE_EXCLUDED_REGIONS:
            assert f"region = region:{region}" in body

    for key in ("inland_saltworks", "engineered_brine_saltworks"):
        body = bodies[key]
        assert "NOT = { is_coastal = yes }" in body
        assert "raw_material = goods:salt" in body
        assert "topography = salt_pans" not in body
        for modifier in SALT_MINE_MODIFIERS:
            assert f"has_location_modifier = {modifier}" in body
        for location in SALT_MINE_DIRECT_LOCATIONS | SALT_MINE_EXCLUDED_LOCATIONS:
            assert f"this = location:{location}" in body
        for region in SALT_MINE_EXCLUDED_REGIONS:
            assert f"region = region:{region}" in body


def test_salt_location_split_matches_current_location_data() -> None:
    baseline = pl.read_parquet(LABELING_BASELINE).select(
        [
            "location_tag",
            "region",
            "is_coastal",
            "topography",
            "vegetation",
            "climate",
            "raw_material",
            "modifier",
        ]
    )
    salt_rows = baseline.filter(pl.col("raw_material") == "salt").to_dicts()

    counts = {"coastal_saltern": 0, "salt_mine": 0, "inland_saltworks": 0}
    offenders: list[str] = []
    for row in salt_rows:
        families = _salt_location_families(row)
        if len(families) != 1:
            offenders.append(f"{row['location_tag']}: {families}")
            continue
        counts[families[0]] += 1

    assert offenders == []
    assert counts == {"coastal_saltern": 233, "salt_mine": 31, "inland_saltworks": 148}

    rows_by_location = {row["location_tag"]: row for row in salt_rows}
    expected_mines = {
        "cardona",
        "chicaquicha",
        "hallein",
        "taghaza",
        "taoudenni",
        "turda",
        "wieliczka",
    }
    expected_inland_saltworks = {
        "anana",
        "hall",
        "luneburg",
        "makgadikgadi",
        "nantwich",
        "salins_les_bains",
        "sambhar",
        "uyuni",
        "worcester",
        "xiexian",
    }
    for location in expected_mines:
        assert _salt_location_families(rows_by_location[location]) == ["salt_mine"]
    for location in expected_inland_saltworks:
        assert _salt_location_families(rows_by_location[location]) == ["inland_saltworks"]

    generic_coastal = baseline.filter(
        (pl.col("raw_material").fill_null("") != "salt")
        & pl.col("is_coastal")
        & (pl.col("topography").fill_null("") != "salt_pans")
    ).head(500)
    generic_desert = baseline.filter(
        (pl.col("raw_material").fill_null("") != "salt")
        & (pl.col("vegetation") == "desert")
        & (pl.col("topography").fill_null("") != "salt_pans")
    ).head(500)
    assert all(_salt_location_families(row) == [] for row in generic_coastal.to_dicts())
    assert all(_salt_location_families(row) == [] for row in generic_desert.to_dicts())
    assert _salt_location_families(
        {
            "raw_material": None,
            "is_coastal": False,
            "topography": "salt_pans",
            "modifier": None,
        }
    ) == []


def test_clay_sand_and_stone_quarry_upgrade_chains_are_explicit_and_unlockable() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    expected_chains = {
        "clay_pit": [
            ("clay_pit", None),
            ("clay_washmill", "pp_clay_washmill"),
        ],
        "sand_pit": [
            ("sand_pit", None),
            ("sand_washery", "pp_sand_washery"),
        ],
        "stone_quarry": [
            ("stone_quarry", None),
            ("stone_quarry_improved", "pp_stone_quarry_improvements"),
        ],
    }

    for family, chain in expected_chains.items():
        for tier, (key, unlock_advance) in enumerate(chain):
            raw = _load_blueprint(key)

            assert f"buildings/{key}.yml" in enabled
            assert raw["tag"] == key
            assert raw["building"]["key"] == key
            assert raw.get("upgrade_chain") == {
                "family": family,
                "tier": tier,
                "previous": chain[tier - 1][0] if tier > 0 else None,
                "next": chain[tier + 1][0] if tier + 1 < len(chain) else None,
                "unlock_advance": unlock_advance,
            }

            body = raw["building"]["body"]
            if tier == 0:
                assert "obsolete =" not in body
            else:
                obsolete_entries = _obsolete_entries(body)
                assert obsolete_entries == [chain[tier - 1][0]]
                assert raw["icon"]["output_dds"] == f"{key}.dds"
                advancements = raw.get("advancements")
                assert isinstance(advancements, list)
                advancement = next(item for item in advancements if item["key"] == unlock_advance)
                assert re.search(rf"^\s*unlock_building\s*=\s*{re.escape(key)}\s*$", advancement["body"], flags=re.M)


def test_lumber_mill_upgrade_chain_is_explicit_and_unlockable() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    chain = [
        ("lumber_mill", None),
        ("water_sawmill", "lumber_improvements_reformation"),
        ("lumber_mill_improved", "lumber_improvements_absolutism"),
    ]

    for tier, (key, unlock_advance) in enumerate(chain):
        raw = _load_blueprint(key)

        assert f"buildings/{key}.yml" in enabled
        assert raw["tag"] == key
        assert raw["building"]["key"] == key
        assert raw.get("upgrade_chain") == {
            "family": "lumber_mill",
            "tier": tier,
            "previous": chain[tier - 1][0] if tier > 0 else None,
            "next": chain[tier + 1][0] if tier + 1 < len(chain) else None,
            "unlock_advance": unlock_advance,
        }

        body = raw["building"]["body"]
        if tier == 0:
            assert "obsolete =" not in body
        else:
            obsolete_entries = _obsolete_entries(body)
            assert obsolete_entries == [chain[tier - 1][0]]
            assert raw["icon"]["output_dds"] == f"{key}.dds"
            advancements = raw.get("advancements")
            assert isinstance(advancements, list)
            advancement = next(item for item in advancements if item["key"].split(":")[-1] == unlock_advance)
            assert re.search(rf"^\s*unlock_building\s*=\s*{re.escape(key)}\s*$", advancement["body"], flags=re.M)


def test_rural_food_building_upgrade_chains_are_explicit() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    assert _load_blueprint("fishing_village").get("upgrade_chain") is None
    expected_chains = {
        "sheep_farms": [
            ("sheep_farms", None),
            ("enclosed_sheep_walks", "pp_enclosed_sheep_walks"),
        ],
        "farming_village": [
            ("farming_village", None),
            ("farming_village_rotations", "pp_farming_village_rotations"),
            ("model_farm", "pp_model_farm"),
        ],
        "forest_village": [
            ("forest_village", None),
            ("managed_forest_village", "pp_managed_forest_village"),
        ],
        "fruit_orchard": [
            ("fruit_orchard", None),
            ("pomological_orchard", "pp_pomological_orchard"),
        ],
    }

    for family, chain in expected_chains.items():
        for tier, (key, unlock_advance) in enumerate(chain):
            raw = _load_blueprint(key)

            assert f"buildings/{key}.yml" in enabled
            assert raw["tag"] == key
            assert raw["building"]["key"] == key
            assert raw.get("upgrade_chain") == {
                "family": family,
                "tier": tier,
                "previous": chain[tier - 1][0] if tier > 0 else None,
                "next": chain[tier + 1][0] if tier + 1 < len(chain) else None,
                "unlock_advance": unlock_advance,
            }

            body = raw["building"]["body"]
            if tier == 0:
                assert "obsolete =" not in body
            else:
                previous = chain[tier - 1][0]
                assert re.search(rf"^\s*obsolete\s*=\s*{re.escape(previous)}\s*$", body, flags=re.M)


def test_blueprint_upgrade_successors_load_after_obsolete_predecessors() -> None:
    config = load_project_config(ROOT / "constructor.toml")
    mod_root = BUILDING_TYPES_ROOT.parents[2]
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = {
        (BLUEPRINT_ROOT / entry).stem
        for entry in manifest["enabled"]
        if str(entry).startswith("buildings/")
    }
    blueprints = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted((BLUEPRINT_ROOT / "buildings").glob("*.yml"))
        if path.stem in enabled
    }
    actual_paths_by_building_key = _managed_building_output_paths_by_key()

    offenders: list[str] = []
    for key, raw in blueprints.items():
        building_key = raw["building"]["key"]
        output_tag = raw.get("output_tag", raw["tag"])
        expected_path = mod_root / config.building_outputs.building_types.format(
            prefix=config.building_outputs.prefix,
            tag=output_tag,
            key=building_key,
        )
        actual_path = actual_paths_by_building_key.get(building_key)
        if actual_path != expected_path:
            offenders.append(f"{key}: expected generated building output {expected_path}, found {actual_path}")

        legacy_path = mod_root / config.building_outputs.building_types.format(
            prefix=config.building_outputs.prefix,
            tag=raw["tag"],
            key=building_key,
        )
        if output_tag != raw["tag"] and legacy_path.exists():
            offenders.append(f"{key}: stale tag-named managed output still exists: {legacy_path}")

        upgrade_chain = raw.get("upgrade_chain")
        if not upgrade_chain or upgrade_chain.get("previous") is None:
            continue

        previous = upgrade_chain["previous"]
        if previous not in blueprints:
            continue

        previous_building_key = blueprints[previous]["building"]["key"]
        previous_path = actual_paths_by_building_key.get(previous_building_key)
        current_path = actual_paths_by_building_key.get(building_key)
        if previous_path is None or current_path is None:
            continue
        previous_sort_key = previous_path.relative_to(mod_root).as_posix()
        current_sort_key = current_path.relative_to(mod_root).as_posix()
        if previous_sort_key >= current_sort_key:
            offenders.append(f"{key}: {current_path} loads before {previous}: {previous_path}")

    assert not offenders, "\n".join(offenders)


def test_accepted_building_upgrade_chains_obsolete_only_direct_predecessor() -> None:
    offenders: list[str] = []
    for path in sorted((BLUEPRINT_ROOT / "buildings").glob("*.yml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)

        upgrade_chain = raw.get("upgrade_chain")
        if not upgrade_chain:
            continue

        body = raw["building"]["body"]
        previous = upgrade_chain.get("previous")
        expected = [] if previous is None else [previous]
        actual = _obsolete_entries(body)
        if actual == expected:
            continue

        key = raw.get("tag", path.stem)
        offenders.append(f"{key}: expected obsolete {expected}, found {actual}")

    assert not offenders


def test_enabled_upgrade_chain_location_requirements_match_initial_building() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = {
        (BLUEPRINT_ROOT / entry).stem
        for entry in manifest["enabled"]
        if str(entry).startswith("buildings/")
    }
    blueprints = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        for path in sorted((BLUEPRINT_ROOT / "buildings").glob("*.yml"))
        if path.stem in enabled
    }
    chains: dict[str, list[tuple[int, str]]] = {}
    for key, raw in blueprints.items():
        upgrade_chain = raw.get("upgrade_chain")
        if upgrade_chain:
            chains.setdefault(upgrade_chain["family"], []).append((upgrade_chain["tier"], key))

    offenders: list[str] = []
    generated_paths_by_key = _managed_building_output_paths_by_key()
    for family, members in sorted(chains.items()):
        members = sorted(members)
        initial_tier, initial_key = members[0]
        if initial_tier != 0:
            offenders.append(f"{family}: first enabled tier is {initial_tier} ({initial_key}), expected 0")
            continue
        initial_body = blueprints[initial_key]["building"]["body"]
        initial_requirement = _normalized_first_script_block(initial_body, "location_potential")
        initial_building_key = blueprints[initial_key]["building"]["key"]
        initial_generated_path = generated_paths_by_key.get(initial_building_key)
        if initial_generated_path is None:
            offenders.append(f"{family}: missing generated building output for {initial_building_key}")
            continue
        initial_generated_requirement = _normalized_first_script_block(
            initial_generated_path.read_text(encoding="utf-8-sig"),
            "location_potential",
        )
        for tier, key in members[1:]:
            body = blueprints[key]["building"]["body"]
            requirement = _normalized_first_script_block(body, "location_potential")
            if requirement != initial_requirement:
                offenders.append(
                    f"{family}: {key} tier {tier} location_potential differs from initial {initial_key}"
                )
            building_key = blueprints[key]["building"]["key"]
            generated_path = generated_paths_by_key.get(building_key)
            if generated_path is None:
                offenders.append(f"{family}: missing generated building output for {building_key}")
                continue
            generated_requirement = _normalized_first_script_block(
                generated_path.read_text(encoding="utf-8-sig"),
                "location_potential",
            )
            if generated_requirement != initial_generated_requirement:
                offenders.append(
                    f"{family}: generated {building_key} tier {tier} location_potential "
                    f"differs from initial {initial_building_key}"
                )

    assert not offenders, "\n".join(offenders)


def test_manpower_building_blueprints_do_not_copy_invalid_owner_culture_gate() -> None:
    for key in ("armory", "training_fields", "barracks", "regimental_camp", "conscription_center"):
        body = _load_blueprint(key)["building"]["body"]

        assert "has_primary_or_accepted_culture" not in body
        assert "prev.dominant_culture" not in body
        assert "prev.location.dominant_culture" not in body


def test_game_start_never_places_offshore_fishery_directly_and_culls_invalid_locations() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")

    assert "construct_building = {\n\t\t\t\t\t\tbuilding_type = building_type:offshore_fishery" not in text
    assert re.search(
        r"building_type\s*=\s*building_type:offshore_fishery.*?NOT\s*=\s*\{\s*is_coastal\s*=\s*yes\s*\}.*?"
        r"building\s*=\s*building_type:offshore_fishery",
        text,
        flags=re.S,
    )


def test_game_start_restores_lake_adjacency_modifier() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")
    modifier_text = LOCATION_MODIFIER_ADJUSTMENTS_PATH.read_text(encoding="utf-8-sig")
    localization_text = (LOCALIZATION_ROOT / "pp_building_adjustments_l_english.yml").read_text(
        encoding="utf-8-sig"
    )

    assert re.search(r"on_game_start\s*=\s*\{.*?pp_apply_adjacent_to_lake_modifier", text, flags=re.S)
    assert "pp_apply_adjacent_to_lake_modifier = {" in text
    assert "limit = { is_adjacent_to_lake = yes }" in text
    assert "modifier = is_adjacent_to_lake" in text
    assert "has_location_modifier = is_adjacent_to_lake" in text
    assert "remove_location_modifier = is_adjacent_to_lake" in text
    assert "modifier = adjacent_to_lake" not in text
    assert "has_location_modifier = adjacent_to_lake" not in text
    assert "remove_location_modifier = adjacent_to_lake" not in text
    assert re.search(r"^is_adjacent_to_lake\s*=\s*\{.*?category\s*=\s*location", modifier_text, flags=re.S | re.M)
    assert "STATIC_MODIFIER_NAME_is_adjacent_to_lake" in localization_text


def test_game_start_direct_rgo_construction_checks_buildability() -> None:
    lines = GAME_START_PATH.read_text(encoding="utf-8-sig").splitlines()
    offenders: list[str] = []

    for index, line in enumerate(lines):
        match = re.match(r"\s*building_type\s*=\s*building_type:([A-Za-z0-9_]+)\s*$", line)
        if not match or match.group(1) not in GAME_START_DIRECT_RGO_BUILDINGS:
            continue
        if index == 0 or not re.match(r"\s*construct_building\s*=\s*\{\s*$", lines[index - 1]):
            continue
        building = match.group(1)
        guard = f"can_build_building = building_type:{building}"
        if guard not in "\n".join(lines[max(0, index - 24) : index]):
            offenders.append(f"{building} near line {index + 1}")

    assert not offenders


def test_game_start_capacity_construction_checks_capacity_and_existing_buildings() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")
    game_start = _first_script_block(text, "pp_game_start_effect")
    if_blocks = _iter_script_blocks(game_start, "if")
    offenders: list[str] = []
    seen: set[str] = set()

    for start, _, construct_block in _iter_script_blocks(game_start, "construct_building"):
        match = re.search(r"\bbuilding_type\s*=\s*building_type:([A-Za-z0-9_]+)\b", construct_block)
        assert match is not None
        building = match.group(1)
        capacity = GAME_START_CAPACITY_BUILDING_GATES.get(building)
        if capacity is None:
            continue

        seen.add(building)
        _, _, if_block = _enclosing_script_block(if_blocks, start, "if")
        limit_block = _first_script_block(if_block, "limit")
        line = _script_line_number(game_start, start)
        checks = {
            "can_build_building": rf"\bcan_build_building\s*=\s*building_type:{re.escape(building)}\b",
            "capacity": rf"\b{re.escape(capacity)}\s*>\s*0\b",
            "not existing": rf"NOT\s*=\s*\{{\s*has_building\s*=\s*building_type:{re.escape(building)}\s*\}}",
        }
        for name, pattern in checks.items():
            if not re.search(pattern, limit_block, flags=re.S):
                offenders.append(f"{building} line {line}: missing {name}")

    assert seen == set(GAME_START_CAPACITY_BUILDING_GATES)
    assert not offenders


def test_game_start_capacity_levelups_are_single_guarded_steps() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")
    game_start = _first_script_block(text, "pp_game_start_effect")
    if_blocks = _iter_script_blocks(game_start, "if")
    offenders: list[str] = []
    seen: set[str] = set()

    for start, _, action_block in _iter_script_blocks(game_start, "change_building_level_in_location"):
        match = re.search(r"\bbuilding\s*=\s*building_type:([A-Za-z0-9_]+)\b", action_block)
        assert match is not None
        building = match.group(1)
        capacity = GAME_START_CAPACITY_BUILDING_GATES.get(building)
        if capacity is None:
            continue

        _, _, if_block = _enclosing_script_block(if_blocks, start, "if")
        limit_block = _first_script_block(if_block, "limit")
        if "value < 2" not in limit_block:
            continue

        seen.add(building)
        line = _script_line_number(game_start, start)
        checks = {
            "can_build_building": rf"\bcan_build_building\s*=\s*building_type:{re.escape(building)}\b",
            "capacity": rf"\b{re.escape(capacity)}\s*>\s*0\b",
            "single step": r"\bvalue\s*=\s*1\b",
        }
        for name, pattern in checks.items():
            search_space = action_block if name == "single step" else limit_block
            if not re.search(pattern, search_space, flags=re.S):
                offenders.append(f"{building} line {line}: missing {name}")
        if re.search(r"\bvalue\s*=\s*\{", action_block):
            offenders.append(f"{building} line {line}: computes a multi-level jump")

    assert seen
    assert not offenders


def test_game_start_does_not_add_farming_village_or_sheep_farm_levels() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")
    game_start = _first_script_block(text, "pp_game_start_effect")
    offenders: list[str] = []

    for start, _, construct_block in _iter_script_blocks(game_start, "construct_building"):
        match = re.search(r"\bbuilding_type\s*=\s*building_type:([A-Za-z0-9_]+)\b", construct_block)
        if match is None or match.group(1) not in GAME_START_DISABLED_CAPACITY_STARTUP_BUILDINGS:
            continue
        offenders.append(f"{match.group(1)} construct near line {_script_line_number(game_start, start)}")

    for start, _, action_block in _iter_script_blocks(game_start, "change_building_level_in_location"):
        match = re.search(r"\bbuilding\s*=\s*building_type:([A-Za-z0-9_]+)\b", action_block)
        if match is None or match.group(1) not in GAME_START_DISABLED_CAPACITY_STARTUP_BUILDINGS:
            continue
        offenders.append(f"{match.group(1)} level-up near line {_script_line_number(game_start, start)}")

    assert not offenders


def test_game_start_invalid_building_cleanup_matches_current_potentials() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")
    on_game_start = _first_script_block(text, "on_game_start")
    assert on_game_start.index("pp_remove_invalid_fiber_and_stud_farms") < on_game_start.index(
        "pp_game_start_effect"
    )

    fiber_and_stud_cleanup = _first_script_block(text, "pp_remove_invalid_fiber_and_stud_farms")
    assert "building_type:fiber_crops_farm" in fiber_and_stud_cleanup
    assert "pp_fiber_crops_farm_location_potential = yes" in fiber_and_stud_cleanup
    assert "building_type:horse_breeders" in fiber_and_stud_cleanup
    assert "pp_horse_breeders_location_potential = yes" in fiber_and_stud_cleanup
    assert "can_build_building" not in fiber_and_stud_cleanup

    cleanup = _first_script_block(text, "pp_remove_invalid_buildings")

    assert "building_type:granary" not in cleanup

    cleanup_ifs = _iter_script_blocks(cleanup, "if")
    fruit_orchard_block = next(
        block
        for _, _, block in cleanup_ifs
        if "building_type:fruit_orchard" in block and "change_building_level_in_location" in block
    )
    fruit_orchard_limit = _first_script_block(fruit_orchard_block, "limit")
    assert "pp_fruit_orchard_location_potential = yes" in fruit_orchard_limit
    assert "pp_vanilla_start_fruit_orchard_location" not in fruit_orchard_limit

    fishing_village_block = next(
        block
        for _, _, block in cleanup_ifs
        if "building_type:fishing_village" in block and "change_building_level_in_location" in block
    )
    fishing_village_limit = _first_script_block(fishing_village_block, "limit")
    assert "is_coastal = yes" in fishing_village_limit


def test_building_production_method_quantities_use_at_most_three_decimals() -> None:
    offenders: list[str] = []
    paths = sorted((BLUEPRINT_ROOT / "buildings").glob("*.yml")) + sorted(BUILDING_TYPES_ROOT.glob("*.txt"))
    for path in paths:
        offenders.extend(_production_method_precision_offenders(path))

    assert not offenders


def test_base_production_methods_are_output_only() -> None:
    offenders: list[str] = []
    paths = sorted((BLUEPRINT_ROOT / "buildings").glob("*.yml")) + sorted(BUILDING_TYPES_ROOT.glob("*.txt"))
    for path in paths:
        offenders.extend(_base_production_method_input_offenders(path))

    assert not offenders


def test_non_base_production_method_slots_have_inputs_or_outputs() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    groups: dict[tuple[str, int], list[dict]] = {}
    for row in data.building_data.production_methods.select(
        [
            "name",
            "building",
            "produced",
            "output",
            "input_goods",
            "source_kind",
            "source_layer",
            "source_file",
            "source_line",
            "production_method_group_index",
        ]
    ).to_dicts():
        group_index = row["production_method_group_index"]
        building = row["building"]
        if row["source_kind"] != "inline" or row["source_layer"] != "constructor":
            continue
        if not isinstance(building, str) or not isinstance(group_index, int) or group_index == 0:
            continue
        groups.setdefault((building, group_index), []).append(row)

    offenders: list[str] = []
    for (building, group_index), rows in sorted(groups.items()):
        if any(_production_method_has_inputs_or_outputs(row) for row in rows):
            continue
        methods = ", ".join(str(row["name"]) for row in rows)
        locations = ", ".join(
            f"{Path(str(row['source_file'])).relative_to(ROOT)}:{row['source_line']}"
            for row in rows
        )
        offenders.append(f"{building} slot {group_index}: {methods} ({locations})")

    assert offenders == []


def test_target_raw_material_producers_have_no_input_base_methods() -> None:
    data = load_eu5_data(profile="constructor", load_order_path=ROOT / "constructor.load_order.toml")
    methods = {
        row["name"]: row
        for row in data.building_data.production_methods.select(
            ["name", "building", "produced", "input_goods"]
        ).to_dicts()
    }

    for building, (good, method) in RAW_MATERIAL_BASE_PRODUCERS.items():
        assert method in methods
        row = methods[method]
        assert row["building"] == building
        assert row["produced"] == good
        assert row["input_goods"] == []


def test_slave_plantation_replacements_keep_colonial_rgo_gate_and_farm_capacity() -> None:
    for building, good in SLAVE_PLANTATION_REPLACEMENTS.items():
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]

        assert blueprint["building"]["mode"] == "REPLACE"
        assert f"raw_material = goods:{good}" in body
        assert "is_overseas_for_owner = yes" in body
        assert "owner ?= { is_colonial_subject = yes }" in body
        assert "pop_type = slaves" in body
        assert "slaves_goods" in body
        assert f"max_levels = farm_capacity_max_{building}" in body
        assert "farm_capacity > 0" not in body


def test_non_slave_crop_farms_are_default_rgo_laborer_buildings() -> None:
    for building, expected in NON_SLAVE_CROP_FARMS.items():
        blueprint = _load_blueprint(building)
        body = blueprint["building"]["body"]
        good = expected["good"]
        base_method = expected["base_method"]
        worked_method = expected["worked_method"]

        assert blueprint["building"]["mode"] == "CREATE"
        assert blueprint["building"]["source"] == "pp_new_buildings.txt"
        assert "pop_type = laborers" in body
        assert f"max_levels = farm_capacity_max_{building}" in body
        assert "farm_capacity > 0" not in body
        assert re.search(
            rf"location_potential\s*=\s*\{{\s*raw_material\s*=\s*goods:{good}\s*\}}",
            body,
        )
        assert "slaves_goods" not in body
        assert "is_overseas_for_owner" not in body
        assert "is_colonial_subject" not in body
        assert "plantation_buildings_advance" not in body
        assert re.search(
            rf"{base_method}\s*=\s*\{{.*?\bproduced\s*=\s*{good}\b.*?\boutput\s*=\s*0\.040\b",
            body,
            flags=re.S,
        )
        assert re.search(
            rf"{worked_method}\s*=\s*\{{.*?\bproduced\s*=\s*{good}\b.*?\boutput\s*=\s*0\.089\b",
            body,
            flags=re.S,
        )
        worked_match = re.search(rf"{worked_method}\s*=\s*\{{(?P<block>.*?)\n    \}}", body, flags=re.S)
        assert worked_match
        worked_block = worked_match.group("block")
        for input_good, amount in expected["inputs"].items():
            assert re.search(rf"\b{input_good}\s*=\s*{re.escape(amount)}\b", worked_block)
        for removed_input in expected["removed_inputs"]:
            assert removed_input not in worked_block

        evaluation = blueprint["evaluation"]
        assert set(evaluation["allow_rules"]) == {
            "input_throughput",
            "output_throughput",
            "amortization_months",
        }
        assert (
            evaluation["production_methods"][base_method]["allow_rules"].keys()
            == {"base_output_per_1k"}
        )
        assert evaluation["production_methods"][worked_method]["production_efficiency"] == 1.05


def test_raw_processor_replacements_exclude_matching_raw_materials() -> None:
    for building, good in RAW_PROCESSOR_EXCLUSIONS.items():
        body = _load_blueprint(building)["building"]["body"]
        assert "location_potential = {" in body
        assert f"raw_material = goods:{good}" in body
        assert re.search(rf"NOT\s*=\s*\{{\s*raw_material\s*=\s*goods:{good}\s*\}}", body)


def test_game_start_routes_raw_saltpeter_to_niter_beds() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8-sig")
    saltpeter_windows = []
    for match in re.finditer(r"raw_material\s*=\s*goods:saltpeter", text):
        window = text[match.start() : match.start() + 600]
        if "construct_building" in window:
            saltpeter_windows.append(window)

    assert saltpeter_windows
    assert all("building_type = building_type:saltpeter_beds" in window for window in saltpeter_windows)
    assert all("building_type = building_type:saltpeter_guild" not in window for window in saltpeter_windows)
    assert "unlock_building = saltpeter_beds" in ADVANCES_PATH.read_text(encoding="utf-8-sig")


def test_mining_village_chain_is_deactivated() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    advances = ADVANCES_PATH.read_text(encoding="utf-8")

    assert DEACTIVATED_MINING_VILLAGE_BLUEPRINTS.isdisjoint(enabled)
    assert "unlock_building = mining_village" not in advances


def test_old_bog_iron_extra_tiers_are_deactivated() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    advances = ADVANCES_PATH.read_text(encoding="utf-8")

    assert DEACTIVATED_BOG_IRON_BLUEPRINTS.isdisjoint(enabled)
    assert "unlock_building = bog_iron_smelter_slitting_mills" not in advances
    assert "unlock_building = bog_iron_smelter_hot_blast_furnace" not in advances


def test_coal_mine_tiers_are_coal_deposit_only() -> None:
    for key in ("coal_mine", "coal_mine_improved", "coal_mine_revolutions"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:coal\s*\}", body)


def test_alum_quarry_tiers_are_alum_deposit_only() -> None:
    for key in ("alum_quarry", "alum_works"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:alum\s*\}", body)


def test_mercury_mine_tiers_are_mercury_deposit_only() -> None:
    for key in ("cinnabar_pit", "quicksilver_retort"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:mercury\s*\}", body)


def test_later_alum_modifier_advances_do_not_unlock_alum_buildings() -> None:
    advances = ADVANCES_PATH.read_text(encoding="utf-8")
    for advance in ("shared_products_procedures", "ostentatious_clothing"):
        assert f"REPLACE:{advance}" not in advances


def test_raw_material_output_advances_convert_to_rgo_size() -> None:
    modifiers_by_advance = _active_advancement_modifiers()
    positive_raw_material_output = {
        advance: modifiers["global_raw_material_output"]
        for advance, modifiers in modifiers_by_advance.items()
        if modifiers.get("global_raw_material_output", 0.0) > 0.0
    }

    assert positive_raw_material_output == {}

    for advance, expected_value in RAW_MATERIAL_OUTPUT_TO_RGO_ADVANCES.items():
        modifiers = modifiers_by_advance[advance]
        assert abs(modifiers.get("global_raw_material_output", 0.0)) < 0.000000001
        assert modifiers.get("global_max_rgo_size_modifier") == expected_value


def test_added_mine_buildings_are_tagged_and_have_site_modifiers() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    tagged_buildings: set[str] = set()

    for entry in enabled:
        if not str(entry).startswith("buildings/"):
            continue
        key = Path(str(entry)).stem
        body = _load_blueprint(key)["building"]["body"]
        if ADDED_MINE_BUILDING_TAG in _body_custom_tags(body):
            tagged_buildings.add(key)

    assert tagged_buildings == set(ADDED_MINE_BUILDING_GOODS)

    for building, good in ADDED_MINE_BUILDING_GOODS.items():
        raw = _load_blueprint(building)
        body = raw["building"]["body"]
        assert raw["building"]["mode"] == "CREATE"
        assert f"buildings/{building}.yml" in enabled
        assert ADDED_MINE_BUILDING_TAG in _body_custom_tags(body)
        assert re.search(r"^\s*local_population_growth\s*=\s*-0\.0002\s*$", body, flags=re.M)
        assert re.search(r"^\s*local_migration_attraction\s*=\s*0\.010\s*$", body, flags=re.M)
        assert re.search(rf"^\s*local_{good}_output_modifier\s*=\s*0\.025\s*$", body, flags=re.M)


def test_iron_mine_tiers_are_iron_deposit_only() -> None:
    for key in ("iron_mine", "iron_mine_improved", "iron_mine_deep"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:iron\s*\}", body)


def test_silver_mine_tiers_are_silver_deposit_only_and_have_unique_icons() -> None:
    for key in ("silver_mine", "silver_mine_improved"):
        raw = _load_blueprint(key)
        body = raw["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:silver\s*\}", body)
        assert raw["icon"]["output_dds"] == f"{key}.dds"


def test_lead_mine_tiers_are_lead_deposit_only_and_have_unique_icons() -> None:
    for key in ("lead_mine", "lead_mine_bole_smelting", "lead_mine_cupola_smelting"):
        raw = _load_blueprint(key)
        body = raw["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:lead\s*\}", body)
        assert raw["icon"]["output_dds"] == f"{key}.dds"


def test_lead_and_coal_late_modifier_advances_unlock_buildings_instead_of_global_output() -> None:
    advances = ADVANCES_PATH.read_text(encoding="utf-8")
    expected_unlocks = {
        "bole_smelting": "lead_mine_bole_smelting",
        "cupola_smelting": "lead_mine_cupola_smelting",
        "coal_improvements_revolutions": "coal_mine_revolutions",
    }

    for advance, building in expected_unlocks.items():
        block = _advance_block(advance, advances)
        assert re.search(rf"^\s*unlock_building\s*=\s*{building}\s*$", block, flags=re.M)
        assert not re.search(r"global_(lead|coal)_output_modifier\s*=", block)


def test_tin_mine_tiers_are_tin_deposit_only_and_have_unique_icons() -> None:
    for key in ("tin_streamworks", "tin_stamping_mill"):
        raw = _load_blueprint(key)
        body = raw["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:tin\s*\}", body)
        assert raw["icon"]["output_dds"] == f"{key}.dds"


def test_copper_mine_tiers_are_copper_deposit_only() -> None:
    for key in ("copper_mine", "copper_mine_adit"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:copper\s*\}", body)


def test_gold_mine_tiers_are_gold_deposit_only() -> None:
    for key in ("gold_diggings", "gold_stamp_mill"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:goods_gold\s*\}", body)


def test_gem_mine_tiers_are_gem_deposit_only_and_have_unique_icons() -> None:
    for key in ("gem_gravel_pit", "gem_sluice"):
        raw = _load_blueprint(key)
        body = raw["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:gems\s*\}", body)
        assert raw["icon"]["output_dds"] == f"{key}.dds"


def test_marble_quarry_tiers_are_marble_deposit_only_and_have_unique_icons() -> None:
    for key in ("marble_quarry", "marble_saw_yard"):
        raw = _load_blueprint(key)
        body = raw["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:marble\s*\}", body)
        assert raw["icon"]["output_dds"] == f"{key}.dds"


def test_manifest_uses_dedicated_gold_mines_not_mining_village() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])

    assert "buildings/gold_diggings.yml" in enabled
    assert "buildings/gold_stamp_mill.yml" in enabled
    assert all("mining_village" not in entry for entry in enabled)


def test_manifest_uses_dedicated_tin_mines_not_mining_village() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])

    assert "buildings/tin_streamworks.yml" in enabled
    assert "buildings/tin_stamping_mill.yml" in enabled
    assert all("mining_village" not in entry for entry in enabled)


def test_bog_iron_smelters_exclude_true_metal_and_coal_deposits() -> None:
    for key, _unlock_advance in EXPECTED_CHAINS["bog_iron_smelter"]:
        body = _load_blueprint(key)["building"]["body"]
        nor_match = re.search(r"NOR\s*=\s*\{(?P<body>.*?)\n\s*\}", body, flags=re.S)
        assert nor_match is not None
        nor_body = nor_match.group("body")
        assert re.search(r"raw_material\s*=\s*goods:iron", nor_body)
        assert re.search(r"raw_material\s*=\s*goods:coal", nor_body)
        assert re.search(r"raw_material\s*=\s*goods:copper", nor_body)
        assert re.search(r"raw_material\s*=\s*goods:gems", nor_body)
        assert re.search(r"raw_material\s*=\s*goods:mercury", nor_body)
        assert re.search(r"raw_material\s*=\s*goods:marble", nor_body)


def test_pan_amalgamation_unlocks_gold_and_mercury_upgrades() -> None:
    advances = ADVANCES_PATH.read_text(encoding="utf-8")
    block = _advance_block("pan_amalgamation_advance", advances)
    assert re.search(r"^\s*unlock_building\s*=\s*gold_stamp_mill\s*$", block, flags=re.M)
    assert re.search(r"^\s*unlock_building\s*=\s*quicksilver_retort\s*$", block, flags=re.M)


def test_smelting_advances_do_not_unlock_iron_mines() -> None:
    advances = ADVANCES_PATH.read_text(encoding="utf-8")
    for advance in ("blast_furnace", "coke_blast_furnace", "hot_blast_furnace"):
        block = _advance_block(advance, advances)
        assert "unlock_building = iron_mine" not in block
        assert "unlock_building = iron_mine_improved" not in block


def test_slitting_mills_advances_iron_methods_and_deep_mine() -> None:
    advances = ADVANCES_PATH.read_text(encoding="utf-8")
    block = _advance_block("slitting_mills", advances)

    assert re.search(r"^\s*unlock_building\s*=\s*iron_mine_deep\s*$", block, flags=re.M)
    assert re.search(
        r"^\s*unlock_production_method\s*=\s*pp_iron_mine_improved_slitting_dressed_ore\s*$",
        block,
        flags=re.M,
    )
    assert re.search(
        r"^\s*unlock_production_method\s*=\s*pp_bog_iron_smelter_blast_furnace_finery\s*$",
        block,
        flags=re.M,
    )
    assert "unlock_building = bog_iron_smelter" not in block


def test_hot_blast_unlocks_final_bog_iron_method_not_building() -> None:
    advances = ADVANCES_PATH.read_text(encoding="utf-8")
    block = _advance_block("hot_blast_furnace", advances)

    assert re.search(
        r"^\s*unlock_production_method\s*=\s*pp_bog_iron_smelter_hot_blast_refining_maintenance\s*$",
        block,
        flags=re.M,
    )
    assert "unlock_building = bog_iron_smelter_hot_blast_furnace" not in block


def test_charcoal_buildings_exclude_coal_deposits() -> None:
    for key in ("charcoal_maker", "improved_charcoal_maker"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(
            r"location_potential\s*=\s*\{\s*NOT\s*=\s*\{\s*raw_material\s*=\s*goods:coal\s*\}\s*\}",
            body,
        )


def test_marble_output_localization_uses_dedicated_quarry_chain() -> None:
    text = (
        (LOCALIZATION_ROOT / "pp_goods_output_map_modes_l_english.yml").read_text(encoding="utf-8")
        + "\n"
        + (LOCALIZATION_ROOT / "pp_rgo_modifiers_l_english.yml").read_text(encoding="utf-8")
    )

    marble_lines = [line for line in text.splitlines() if "marble" in line.lower()]
    assert any("marble_quarry" in line for line in marble_lines)
    assert any("marble_saw_yard" in line for line in marble_lines)
    assert not any("mining_village" in line for line in marble_lines)
