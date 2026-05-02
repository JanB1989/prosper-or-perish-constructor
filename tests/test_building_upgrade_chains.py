from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
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
LOCALIZATION_ROOT = (
    ROOT
    / "mod"
    / "Prosper or Perish (Population Growth & Food Rework)"
    / "main_menu"
    / "localization"
    / "english"
)

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
        ("lead_mine_improved", "lead_ore_dressing"),
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
        ("iron_mine_improved", "efficient_mining"),
    ],
    "bog_iron_smelter": [
        ("bog_iron_smelter", None),
        ("bog_iron_smelter_blast_furnace", "blast_furnace"),
        ("bog_iron_smelter_slitting_mills", "slitting_mills"),
        ("bog_iron_smelter_coke_blast_furnace", "coke_blast_furnace"),
        ("bog_iron_smelter_hot_blast_furnace", "hot_blast_furnace"),
    ],
    "cookery": [
        ("cookery", None),
        ("victualling_yard", "food_advance_absolutism"),
    ],
}

DEACTIVATED_MINING_VILLAGE_BLUEPRINTS = {
    "buildings/mining_village.yml",
    "buildings/mining_village_blast_furnace.yml",
    "buildings/mining_village_slitting_mills.yml",
    "buildings/mining_village_coke_blast_furnace.yml",
    "buildings/mining_village_hot_blast_furnace.yml",
}


def _load_blueprint(key: str) -> dict:
    with (BLUEPRINT_ROOT / "buildings" / f"{key}.yml").open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    assert isinstance(raw, dict)
    return raw


def _advance_block(advance: str, text: str) -> str:
    match = re.search(
        rf"(?:(?:REPLACE|TRY_INJECT):)?{re.escape(advance)}\s*=\s*\{{(?P<body>.*?)\n\}}",
        text,
        flags=re.S,
    )
    assert match is not None, f"{advance} block missing"
    return match.group("body")


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
            if tier == 0:
                assert "obsolete =" not in body
            else:
                previous = chain[tier - 1][0]
                assert re.search(rf"^\s*obsolete\s*=\s*{re.escape(previous)}\s*$", body, flags=re.M)
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


def test_game_start_never_places_offshore_fishery_directly_and_culls_invalid_locations() -> None:
    text = GAME_START_PATH.read_text(encoding="utf-8")

    assert "construct_building = {\n\t\t\t\t\t\tbuilding_type = building_type:offshore_fishery" not in text
    assert re.search(
        r"building_type\s*=\s*building_type:offshore_fishery.*?NOT\s*=\s*\{\s*is_coastal\s*=\s*yes\s*\}.*?"
        r"building\s*=\s*building_type:offshore_fishery",
        text,
        flags=re.S,
    )


def test_mining_village_chain_is_deactivated() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(manifest["enabled"])
    advances = ADVANCES_PATH.read_text(encoding="utf-8")

    assert DEACTIVATED_MINING_VILLAGE_BLUEPRINTS.isdisjoint(enabled)
    assert "unlock_building = mining_village" not in advances


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


def test_iron_mine_tiers_are_iron_deposit_only() -> None:
    for key in ("iron_mine", "iron_mine_improved"):
        body = _load_blueprint(key)["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:iron\s*\}", body)


def test_silver_mine_tiers_are_silver_deposit_only_and_have_unique_icons() -> None:
    for key in ("silver_mine", "silver_mine_improved"):
        raw = _load_blueprint(key)
        body = raw["building"]["body"]
        assert re.search(r"location_potential\s*=\s*\{\s*raw_material\s*=\s*goods:silver\s*\}", body)
        assert raw["icon"]["output_dds"] == f"{key}.dds"


def test_lead_mine_tiers_are_lead_deposit_only_and_have_unique_icons() -> None:
    for key in ("lead_mine", "lead_mine_bole_smelting", "lead_mine_improved", "lead_mine_cupola_smelting"):
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
    for advance in ("blast_furnace", "slitting_mills", "coke_blast_furnace", "hot_blast_furnace"):
        block = _advance_block(advance, advances)
        assert "unlock_building = iron_mine" not in block
        assert "unlock_building = iron_mine_improved" not in block


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
