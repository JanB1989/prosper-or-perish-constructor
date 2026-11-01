"""Buildings that only a DLC folder defines (game/dlc/<folder>/, e.g. Across the Pillars) are governed like every
vanilla building: each has an enabled accepted blueprint with a footprint class. Its blueprint and every block the
compiled mod writes for it use a skip-if-missing mode (TRY_INJECT / TRY_REPLACE), so the mod stays safe for players
whose install has no such DLC folder."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from prosper_or_perish_constructor import building_footprint as fp
from prosper_or_perish_constructor import yaml_io
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"
MANIFEST = REPO / "blueprints/buildings.manifest.yml"
ACROSS_THE_PILLARS = {
    "tali_a_watchtower", "library_cordoba", "thagr_fort", "saqaliba_barracks", "qadi_office", "saharan_trade_house",
    "madinat_al_zahra", "palazzo_ajutamicristo", "italian_court_building",
}


@pytest.fixture(scope="module")
def dlc_buildings() -> set[str]:
    root = vanilla_root(REPO, REPO / "constructor.toml")
    if not (root / "game/dlc").is_dir():
        pytest.skip("no game/dlc folder in the configured install")
    return fp.dlc_only_buildings(root)


def test_the_dlc_buildings_are_read(dlc_buildings: set[str]) -> None:
    if not (vanilla_root(REPO, REPO / "constructor.toml") / "game/dlc/D009_across_the_pillars").is_dir():
        pytest.skip("Across the Pillars folder not installed")
    assert ACROSS_THE_PILLARS <= dlc_buildings


def test_every_dlc_building_has_an_enabled_blueprint_in_a_try_mode(dlc_buildings: set[str]) -> None:
    classes = fp.blueprint_classes(REPO)
    config = fp.load_config(REPO / "constructor.toml")
    enabled = (yaml_io.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}).get("enabled") or {}
    problems = []
    for key in sorted(dlc_buildings):
        if key not in classes:
            problems.append(f"{key}: no accepted blueprint")
            continue
        footprint, path = classes[key]
        if enabled.get(f"buildings/{path.name}") is not True:
            problems.append(f"{path.name}: not enabled in buildings.manifest.yml")
        if footprint not in config.shares:
            problems.append(f"{path.name}: footprint class {footprint!r} is not configured")
        if (mode := fp.blueprint_mode(path)) not in fp.DLC_SAFE_MODES:
            problems.append(f"{path.name}: mode {mode}, must be one of {sorted(fp.DLC_SAFE_MODES)}")
    assert problems == []


def test_the_compiled_mod_touches_dlc_buildings_only_in_try_blocks(dlc_buildings: set[str]) -> None:
    folder = MOD / fp.BUILDING_TYPES_RELATIVE
    if not folder.is_dir():
        pytest.skip("built mod not available")
    seen, unsafe = set(), []
    for path in sorted(folder.glob("*.txt")):
        for block in fp.blocks(path):
            if block.key in dlc_buildings:
                seen.add(block.key)
                if block.mode not in fp.DLC_SAFE_MODES:
                    unsafe.append(f"{path.name}: {block.mode or 'CREATE'}:{block.key}")
    assert unsafe == []
    assert seen == dlc_buildings, "run ppc build: every DLC building's blueprint renders a TRY_ block"


def test_the_try_blocks_name_no_dlc_only_building_outside_their_own_block(dlc_buildings: set[str]) -> None:
    """A DLC key inside a non-DLC block (a link, a list) would fail at load without the DLC."""
    folder = MOD / fp.BUILDING_TYPES_RELATIVE
    if not folder.is_dir():
        pytest.skip("built mod not available")
    pattern = re.compile(r"(?<![A-Za-z0-9_:])(" + "|".join(sorted(dlc_buildings)) + r")(?![A-Za-z0-9_])")
    offenders = []
    for path in sorted(folder.glob("*.txt")):
        text = fp._read(path)
        own = [(b.open, b.close) for b in fp.blocks(path, text) if b.key in dlc_buildings]
        for match in pattern.finditer(re.sub(r"#[^\n]*", lambda m: " " * len(m.group(0)), text)):
            if not any(open_ <= match.start() <= close for open_, close in own):
                offenders.append(f"{path.name}: {match.group(1)}")
    assert offenders == []
