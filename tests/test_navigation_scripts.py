"""Vanilla scripts that route fleets over the open sea must not be able to pick a navigable river channel.

The channels are sea zones, so river banks are is_coastal and hold ports. A vanilla find_route to such a location
has no sea route and fails at run time (the Chinese treasure voyage: "Failed to fetch variable for
'chinese_treasure_next_location' due to not being set"). These tests fail when a vanilla file that routes or spawns
fleets is not handled in [worldbuilder.navigation_scripts], when a patch no longer applies to the current vanilla
file, and when the built mod lacks the patched copy or the trigger it uses.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from prosper_or_perish_constructor.worldbuilder import navigation_scripts as ns
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"


def _config():
    raw = tomllib.loads(PROJECT.read_text(encoding="utf-8"))
    return ns.load(raw["worldbuilder"].get("navigation_scripts")), raw["worldbuilder"]["compat"]["vanilla_files"]


@pytest.fixture(scope="module")
def vanilla():
    root = vanilla_root(REPO, PROJECT)
    if not (root / "game/in_game/events").is_dir():
        pytest.skip(f"vanilla files not available at {root}")
    return root


def test_every_vanilla_fleet_script_is_patched_or_reviewed(vanilla):
    cfg, _ = _config()
    assert ns.unlisted(vanilla, cfg) == {}


def test_every_vanilla_sea_route_is_patched(vanilla):
    cfg, _ = _config()
    assert ns.unpatched_routing(vanilla, cfg) == {}, "a file with find_route may only be reviewed if routing cannot pick a river bank; patch it"


def test_listed_files_still_exist_and_patches_still_apply(vanilla):
    cfg, _ = _config()
    for rel in cfg.listed:
        assert (vanilla / "game" / rel).is_file(), f"{rel} no longer exists in vanilla; drop it from the list"
    for rel, replacements in cfg.patches.items():
        ns.patch_text((vanilla / "game" / rel).read_text(encoding="utf-8-sig"), replacements, rel)


def test_built_mod_carries_the_patched_copies_and_the_trigger():
    cfg, _ = _config()
    trigger = (MOD / ns.TRIGGER_RELATIVE_PATH).read_text(encoding="utf-8-sig")
    assert "pp_is_sea_coast = {" in trigger and f"region = region:{ns.NAVIGATION_REGION}" in trigger
    for rel, replacements in cfg.patches.items():
        text = (MOD / rel).read_text(encoding="utf-8-sig")
        assert text.startswith(ns.HEADER), f"{rel} is not the patched copy; run ppc worldbuilder apply"
        for r in replacements:
            assert text.count(r.replace) == r.count, f"{rel}: patch missing"


def test_mod_scripts_route_only_to_sea_coasts():
    """The mod's own scripts: every find_route target selection uses pp_is_sea_coast (none use find_route today)."""
    cfg, _ = _config()
    for path in (MOD / "in_game").rglob("*.txt"):
        rel = path.relative_to(MOD).as_posix()
        if rel in cfg.patches:
            continue
        code = "\n".join(line.split("#", 1)[0] for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines())
        if re.search(r"\bfind_route\b", code):
            assert "pp_is_sea_coast" in code, f"{rel} routes fleets without pp_is_sea_coast"


def test_navigation_channels_sit_in_the_trigger_region():
    """pp_is_sea_coast tells channels from the sea by their region; every pp_nav tile must be in it."""
    text = (MOD / "in_game/map_data/definitions.txt").read_text(encoding="utf-8-sig")
    start = text.index(f"{ns.NAVIGATION_REGION} = {{")
    depth, i = 0, text.index("{", start)
    for i in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            break
    inside = set(re.findall(r"\bpp_nav_\d+\b", text[start:i]))
    everywhere = set(re.findall(r"\bpp_nav_\d+\b", text))
    assert everywhere and inside == everywhere


def test_patch_text_fails_loudly_when_vanilla_changes():
    r = [ns.Replacement("limit = { is_coastal = yes }", "limit = { is_coastal = yes pp_is_sea_coast = yes }", 1)]
    assert "pp_is_sea_coast" in ns.patch_text("x = { limit = { is_coastal = yes } }", r, "f.txt")
    with pytest.raises(ValueError, match="vanilla changed"):
        ns.patch_text("x = { limit = { is_coastal = no } }", r, "f.txt")


def test_patch_goes_on_top_of_the_widened_copy(tmp_path):
    from prosper_or_perish_constructor.worldbuilder import compat

    rel = "in_game/events/x.txt"
    vanilla = tmp_path / "vanilla"
    (vanilla / "game/in_game/events").mkdir(parents=True)
    (vanilla / "game" / rel).write_text("a = { limit = { is_coastal = yes } climate = arid }\n")
    mod = tmp_path / "mod"
    (mod / "in_game/events").mkdir(parents=True)
    (mod / rel).write_text("﻿" + compat.HEADER + "\na = { limit = { is_coastal = yes } OR = { climate = arid climate = desert } }\n")
    cfg = ns.ScriptsConfig({rel: [ns.Replacement("limit = { is_coastal = yes }", "limit = { pp_is_sea_coast = yes }", 1)]}, {})
    ns.write(vanilla, mod, tmp_path, cfg, [rel])
    out = (mod / rel).read_text(encoding="utf-8-sig")
    assert "pp_is_sea_coast = yes" in out and "climate = desert" in out
