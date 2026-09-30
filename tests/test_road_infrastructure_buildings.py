from __future__ import annotations

from pathlib import Path

from eu5_mod_orchestrator.blueprints import enabled_manifest_entries
from prosper_or_perish_constructor import yaml_io


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_ROOT = ROOT / "blueprints" / "accepted" / "buildings"
MANIFEST_PATH = ROOT / "blueprints" / "buildings.manifest.yml"
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
ROAD_TYPES = MOD_ROOT / "in_game" / "common" / "road_types" / "pp_road_infrastructure_rebalance.txt"
GAME_START = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_game_start.txt"
ROAD_STARTUP = MOD_ROOT / "in_game" / "common" / "on_action" / "pp_road_infrastructure_startup.txt"

# The road-maintenance chain was switched off on 2026-09-30: the logistics buildings carry market access now.
# The blueprints stay (disabled) for reference; the build emits nothing of them.
ROAD_BUILDINGS = ("road_wardens_yard", "paviors_yard", "macadam_works", "permanent_way_depot")
GAME_TEXT_SUFFIXES = {".txt", ".yml", ".gui"}


def test_road_maintenance_blueprints_are_disabled_but_kept() -> None:
    manifest = yaml_io.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    enabled = set(enabled_manifest_entries(manifest.get("enabled", []), source=MANIFEST_PATH))
    for building in ROAD_BUILDINGS:
        assert manifest["enabled"][f"buildings/{building}.yml"] is False
        assert f"buildings/{building}.yml" not in enabled
        assert (BLUEPRINT_ROOT / f"{building}.yml").is_file()


def test_road_maintenance_buildings_are_not_emitted() -> None:
    names = [f"zz_pp_road_{i}_" for i in range(4)] + [f"pp_road_{i}_" for i in range(4)]
    leftovers = [
        str(path.relative_to(MOD_ROOT))
        for path in MOD_ROOT.rglob("*")
        if path.is_file() and any(path.name.startswith(name) for name in names)
    ]
    assert leftovers == []
    icons = MOD_ROOT / "in_game" / "gfx" / "interface" / "icons" / "buildings"
    assert [b for b in ROAD_BUILDINGS if (icons / f"{b}.dds").exists()] == []

    # no script, advance, price, cost modifier or localization names them any more
    references = []
    for path in MOD_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in GAME_TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for building in (*ROAD_BUILDINGS, "pp_road_maintenance"):
            if building in text:
                references.append(f"{path.relative_to(MOD_ROOT)}: {building}")
    assert references == []


def test_road_infrastructure_does_not_override_vanilla_roads() -> None:
    assert not ROAD_TYPES.exists()


def test_road_wardens_startup_is_deactivated_and_food_startup_is_untouched() -> None:
    game_start = GAME_START.read_text(encoding="utf-8-sig")
    startup = ROAD_STARTUP.read_text(encoding="utf-8-sig")

    assert "pp_road_infrastructure_startup" not in game_start
    assert "pp_road_infrastructure_startup = {" in startup
    assert "construct_building" not in startup
    assert "num_roads > 0" not in startup
    assert "NOT = { has_building = building_type:road_wardens_yard }" not in startup
    assert "building_type = building_type:road_wardens_yard" not in startup
    assert "cost_multiplier = 0" not in startup
    assert "can_build_building = building_type:road_wardens_yard" not in startup
