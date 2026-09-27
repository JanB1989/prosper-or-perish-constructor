"""Water access: three exclusive states (Inland, Waterway, Sea Coast), one definition.

The engine makes every location next to a sea zone is_coastal, and the navigable river channels are sea zones. The
mod splits that into the sea coast (pp_is_sea_coast, the vanilla meaning from before the channels) and the waterway
(river channels and navigable lakes only). coast.py reads the same sets from the map offline; the Sea Coast modifier,
the gates and the location view all follow it. Verified in game 2026-09-27: 4,415 sea coast, 1,283 waterway, 15,195
inland (the frozen Arctic sea gives no access; Ob moved to the waterway with that rule).
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import polars as pl
import pytest

from prosper_or_perish_constructor.worldbuilder import coast
from prosper_or_perish_constructor.worldbuilder import navigation_scripts as ns
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "constructor.toml"
MOD = REPO / "mod/Prosper or Perish (Population Growth & Food Rework)"


def _config():
    raw = tomllib.loads(PROJECT.read_text(encoding="utf-8"))
    return ns.load(raw["worldbuilder"].get("navigation_scripts"))


@pytest.fixture(scope="module")
def vanilla():
    root = vanilla_root(REPO, PROJECT)
    if not (root / "game/in_game/events").is_dir():
        pytest.skip(f"vanilla files not available at {root}")
    return root


def test_contract_coastal_flag_follows_the_map_sea_coast():
    import dataclasses

    @dataclasses.dataclass(frozen=True)
    class Contract:   # the field with_sea_coast touches
        location_attributes: pl.DataFrame

    contract = Contract(pl.DataFrame({"location_tag": ["a", "b", "c"], "is_coastal": ["true", "true", "false"]}))
    out = coast.with_sea_coast(contract, {"a": "sea_coast", "b": "waterway", "c": "sea_coast"})
    assert dict(out.location_attributes.select("location_tag", "is_coastal").iter_rows()) == {"a": "true", "b": "false", "c": "true"}
    assert coast.with_sea_coast(contract, None) is contract


def test_water_access_chip_replaces_the_coast_chip_after_river_and_lake():
    gui = ('widget = {\n        name = "ha1300_native_coast"\n        size = { 30 30 }\n    }\n'
           'widget = {\n        name = "ha1300_native_river"\n    }\n'
           'widget = {\n        name = "ha1300_native_lake"\n    }\n'
           'widget = { name = "ha1300_native_soil" size = { 30 30 }\n}\n'
           'hbox = {\n# NATURAL HABOUR\nwidget = {\n tooltipwidget = { using = HarborCapacity_tooltip }\n}\n\n'
           '# SOUND TOLL\nicon = { size = { 30 30 } }\n}\n')
    out = coast.water_access_chips(gui)
    assert "ha1300_native_coast" not in out
    assert out.index("ha1300_native_lake") < out.index('name = "pp_water_access"') < out.index('name = "pp_port"') < out.index("ha1300_native_soil")
    # the sea-coast effects show only on the sea coast; the engine's coastal effects on both water states
    assert "pp_attribute_view_coast" in out and "ShowModifierEffect('coastal')" in out
    # one Port attribute: vanilla's natural harbour pie is gone, its harbour capacity breakdown sits in the Port tooltip
    assert "HarborCapacity_tooltip" not in out and "# SOUND TOLL" in out
    port = out[out.index('name = "pp_port"'):out.index("ha1300_native_soil")]
    for text in ("PP_PORT_HARBOR", "GetDescriptionFor('harbor_suitability')", "GetHarborCapacityImpactInfo",
                 "GetMapMode('natural_harbor_suitability')"):
        assert text in port
    for tex in (coast.SEA_ICON, coast.WATERWAY_ICON, coast.INLAND_ICON, coast.PORT_ICON):
        assert tex in out
    with pytest.raises(ValueError):
        coast.water_access_chips(out)


def test_custom_localization_splits_the_engine_coast_into_three_states():
    text = coast.CUSTOM_LOCALIZATION
    block = text[text.index("pp_water_access = {"):text.index("pp_water_access_help")]
    assert block.index("pp_is_sea_coast = yes") < block.index("is_coastal = yes") < block.index("fallback = yes")
    for key in ("PP_WATER_SEA_COAST", "PP_WATER_WATERWAY", "PP_WATER_INLAND", "PP_PORT", "PP_NO_PORT", "PP_PORT_HARBOR"):
        assert f" {key}:" in coast.LOCALIZATION


def test_sea_trigger_excludes_channels_lakes_and_frozen_sea():
    for text in ("NOT = { region = region:pp_navigation_region }", "NOT = { topography = lakes }",
                 "NOT = { topography = high_lakes }", "NOT = { topography = salt_pans }", "NOT = { topography = ocean_wasteland }"):
        assert text in ns.TRIGGERS
    assert "pp_is_waterway = {" in ns.TRIGGERS


def test_sea_only_buildings_narrow_their_vanilla_conditions():
    assert ns.sea_only_potential("location_potential = {\n\tis_capital = yes\n\tis_coastal = yes\n}") == "is_capital = yes\n\tpp_is_sea_coast = yes"
    assert ns.sea_only_potential("location_potential = { is_port = yes }") == "is_port = yes pp_is_sea_coast = yes"
    assert "pp_is_sea_coast = yes" in ns.sea_only_potential("location_potential = { region = region:x }")
    assert ns.sea_only_potential("build_time = 5") == "pp_is_sea_coast = yes"


def test_every_vanilla_water_test_is_patched_or_reviewed(vanilla):
    assert ns.unlisted_water(vanilla, _config()) == {}


def test_water_reviews_name_existing_files(vanilla):
    for rel in _config().water_reviewed:
        assert (vanilla / "game" / rel).is_file(), f"{rel} no longer exists in vanilla; drop it from the list"


def test_built_mod_restricts_the_sea_only_buildings():
    cfg = _config()
    text = (MOD / ns.SEA_BUILDINGS_RELATIVE_PATH).read_text(encoding="utf-8-sig")
    for key in cfg.sea_only_buildings:
        block = text[text.index(f"TRY_INJECT:{key} = {{"):]
        block = block[:block.index("\n}")]
        assert "pp_is_sea_coast = yes" in block and "is_coastal" not in block, key


def test_built_location_window_shows_water_access_and_port():
    gui = (MOD / "in_game/gui/location_window.gui").read_text(encoding="utf-8-sig")
    assert 'name = "pp_water_access"' in gui and 'name = "pp_port"' in gui
    assert 'name = "ha1300_native_coast"' not in gui
    assert "# NATURAL HABOUR" not in gui and gui.count("GetHarborCapacityImpactInfo") == 1
    assert not (MOD / coast.SCRIPT_VALUES_PATH).exists()


def test_river_surfaces_do_not_hide_the_channel_colours():
    """The vanilla river surface is drawn over the channel locations (they follow the river lines); the map modes that
    colour the channels by type switch the river surfaces off."""
    vanilla_block = "topography = {\r\n\tcolor_mode = topography\r\n\tsmall_map_names = topography\r\n}\r\n"
    out = coast.topography_map_mode_without_rivers(vanilla_block)
    assert out == "topography = {\n\tcolor_mode = topography\n\tenable_rivers = no\n\tsmall_map_names = topography\n}\n"
    with pytest.raises(ValueError):
        coast.topography_map_mode_without_rivers("political = {\n\tcolor_mode = political\n}\n")
    modes = (MOD / "in_game/gfx/map/map_modes/map_modes.txt").read_text(encoding="utf-8-sig")
    block = modes[modes.index("topography = {\n\tcolor_mode = topography"):]
    assert "\tenable_rivers = no\n" in block[:block.index("\n}")]
    nav = (MOD / "in_game/gfx/map/map_modes/pp_river_navigation.txt").read_text(encoding="utf-8-sig")
    assert "enable_rivers = no" in nav and "enable_rivers = yes" not in nav


def test_channel_topographies_have_their_own_icons_and_map_colours():
    """Navigable River, Shallows and Falls: each its own drawn 64 px icon and a Topography map mode colour that
    differs from the others and from every vanilla sea colour."""
    import json
    import re

    settings = json.loads((REPO / "config/river_navigation.json").read_text(encoding="utf-8"))["topographies"]
    colours = [tuple(spec["map_color"]) for spec in settings.values()]
    assert len(set(colours)) == 3
    text = (MOD / "in_game/common/topography/pp_river_topography.txt").read_text(encoding="utf-8-sig")
    assert "terrain_narrows" not in text and "terrain_ocean_wasteland" not in text
    from PIL import Image

    icons = set()
    for spec in settings.values():
        assert re.search(rf"{spec['key']} = \{{\n\tcolor = rgb \{{ {' '.join(map(str, spec['map_color']))} \}}", text)
        dds = MOD / "main_menu/gfx/interface/topography" / f"{spec['key']}.dds"
        with Image.open(dds) as im:
            assert im.size == (64, 64)
            icons.add(im.convert("RGBA").tobytes())
        assert not (MOD / "in_game/gfx/interface/topography" / f"{spec['key']}.dds").exists()
    assert len(icons) == 3


def test_only_the_rivers_are_water_coloured_in_the_topography_map_mode():
    """Floodplains and Deltas came from the World Builder in teal and blue, the river's own colours; they get land
    colours, and the channel colours keep clear of every land topography colour."""
    import json
    import re

    settings = json.loads((REPO / "config/river_navigation.json").read_text(encoding="utf-8"))
    named = (MOD / "main_menu/common/named_colors/ha1300_topography.txt").read_text(encoding="utf-8-sig")
    land = {k: tuple(map(int, v)) for k, *v in re.findall(r"(\w+)\s*=\s*rgb\s*\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}", named)}
    for name, rgb in settings["land_topography_colors"].items():
        assert land[name] == tuple(rgb)
    import colorsys

    for rgb in land.values():
        hue, _, sat = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        assert not (170 <= hue * 360 <= 240 and sat > 0.2), f"land topography colour {rgb} is water blue"
    for spec in settings["topographies"].values():
        for rgb in land.values():
            assert sum(abs(a - b) for a, b in zip(spec["map_color"], rgb)) > 120, (spec["key"], rgb)


def test_sea_coast_placement_matches_the_offline_map_state():
    """The Sea Coast modifier sits exactly on the map's sea coast (not on the World Builder's old coastline)."""
    import re
    state = coast.cached(REPO)
    if state is None:
        pytest.skip("run ppc worldbuilder apply first")
    setup = (MOD / "main_menu/setup/start/21_pp_wb_attribute_modifiers.txt").read_text(encoding="utf-8-sig")
    placed = set()
    for match in re.finditer(r"(?ms)^\t(\w+) = \{(.*?)^\t\}", setup):
        if 'modifier = "pp_wb_coastal"' in match[2]:
            placed.add(match[1])
    sea = coast.sea_coast(state)
    assert placed and placed <= sea
    assert "rovigo" in placed and "benauges" not in placed and "kalay" not in placed
