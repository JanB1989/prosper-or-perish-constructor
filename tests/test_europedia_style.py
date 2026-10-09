"""The Europedia card style (in_game/gui/shared/pp_europedia_style.gui) and the cards built with it.

The cards are hand-kept GUI and localization the game only checks when it draws them, so these tests read the files the
game loads: every texture, localization key, concept link, modifier link and data function a card uses exists, the
cards carry no numbers (they live in the linked tooltips), and the rows of goods or buildings follow their sources.
"""

from __future__ import annotations

import re
import tomllib
from functools import cache
from pathlib import Path

import pytest

from prosper_or_perish_constructor import location_status
from scripts.generate_variable_harvests import exempt_goods
from test_gui_blocks import _calls, _vanilla

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
STYLE = MOD_ROOT / "in_game/gui/shared/pp_europedia_style.gui"
GENERATED = MOD_ROOT / location_status.EUROPEDIA_HARVEST_GUI
EUROPEDIA = MOD_ROOT / "in_game/gui/encyclopedia_lateralview.gui"
HARVEST_LOC = MOD_ROOT / location_status.HARVEST_LOCALIZATION
CONFIG = ROOT / "variable_harvests.toml"
SEVERITIES = ("abysmal", "very_poor", "poor", "good", "very_good", "bountiful")
# card -> (first line, the next card's first line, concept descriptions the card's links open)
CARDS = {
    "harvest": ("# ---- Variable Harvests ----", "# ---- Arable Land ----",
                tuple(f"game_concept_{s}_harvest_desc" for s in (*SEVERITIES, "average"))),
    "arable_land": ("# ---- Arable Land ----", "# ---- Population Growth ----",
                    ("game_concept_pp_population_capacity_desc", "game_concept_pp_overused_arable_land_desc",
                     "game_concept_pp_abundant_free_land_desc", "game_concept_pp_available_free_land_desc")),
}
# Retired player-facing names of the population capacity and its states (renamed to Arable Land 2026-10-10).
# "Farmland Vegetation" and lower-case "farmland" (the vegetation type, prose about fields) stay.
OLD_LAND_NAMES = re.compile(r"Subsistence Land|subsistence land|Free Land|Overpopulation|Location Potential|Settled Land"
                            r"|\bFarmland\b(?! Vegetation)|\[pp_farmland\|e\]|\[pp_arable_land\|e\]|pp_settled_land")
_CONCEPT_LINK = re.compile(r"\[(\w+)\|[eE]\]|\[Concept\('(\w+)'")


def _card(name: str) -> str:
    first, following, _ = CARDS[name]
    text = EUROPEDIA.read_text(encoding="utf-8-sig")
    start = text.index(first)
    return text[start:text.index(following, start)]


@cache
def _loc(root: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for path in sorted((root / "main_menu/localization/english").rglob("*.yml")):
        for key, value in re.findall(r'(?m)^\s*([A-Za-z0-9_.\-]+):\d*\s*"(.*)"\s*$', path.read_text(encoding="utf-8-sig", errors="replace")):
            keys[key] = value
    return keys


def _all_loc() -> dict[str, str]:
    return {**_loc(_vanilla()), **_loc(MOD_ROOT)}


def _card_loc(name: str) -> dict[str, str]:
    """The card's own texts and the concepts it links (the harvest's per-area modifier lists are generated)."""
    mod = _loc(MOD_ROOT)
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _card(name))) | set(CARDS[name][2])
    return {k: mod[k] for k in keys if k in mod}


def _texture_exists(texture: str) -> bool:
    roots = [_vanilla() / r for r in ("main_menu", "in_game", "loading_screen")] + [MOD_ROOT / r for r in ("main_menu", "in_game")]
    return any((root / texture).is_file() for root in roots)


def _concepts() -> set[str]:
    concepts = set()
    for root in (_vanilla(), MOD_ROOT):
        for path in (root / "main_menu/common/game_concepts").glob("*.txt"):
            concepts |= set(re.findall(r"(?m)^(\w+)\s*=\s*\{", path.read_text(encoding="utf-8-sig", errors="replace")))
    return concepts


@pytest.mark.parametrize("name", CARDS)
def test_every_texture_exists(name):
    used = set()
    for text in (STYLE.read_text(encoding="utf-8-sig"), GENERATED.read_text(encoding="utf-8-sig"), _card(name)):
        used |= set(re.findall(r'texture = "(gfx/[^"]+)"', text))
    missing = sorted(t for t in used if not _texture_exists(t))
    assert used and not missing


@pytest.mark.parametrize("name", CARDS)
def test_banners_are_double_size(name):
    """Banners are drawn at 1450 x 250 from 2900 x 500 pictures (tools/build_europedia_banners.py)."""
    from PIL import Image

    banners = set(re.findall(r'texture = "(gfx/interface/illustrations/pp_europedia/[^"]+)"', _card(name)))
    assert len(banners) == 1
    for banner in banners:
        with Image.open(MOD_ROOT / "main_menu" / banner) as image:
            assert image.size == (2900, 500), banner


@pytest.mark.parametrize("name", CARDS)
def test_every_text_key_exists(name):
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _card(name))) | set(CARDS[name][2])
    missing = sorted(keys - set(_all_loc()))
    assert keys and not missing


@pytest.mark.parametrize("name", CARDS)
def test_card_types_are_defined(name):
    defined = set(re.findall(r"type (pp_eu_\w+) =", STYLE.read_text(encoding="utf-8-sig") + GENERATED.read_text(encoding="utf-8-sig")))
    used = set(re.findall(r"\b(pp_eu_\w+) = \{", _card(name)))
    assert used and used <= defined


@pytest.mark.parametrize("name", CARDS)
def test_card_text_has_no_numbers(name):
    """Numbers live behind the links (modifier and concept tooltips), never in the text."""
    for key, value in _card_loc(name).items():
        assert not re.search(r"\d", value), key


@pytest.mark.parametrize("name", CARDS)
def test_concept_links_resolve(name):
    links = {a or b for value in _card_loc(name).values() for a, b in _CONCEPT_LINK.findall(value)}
    assert links and not sorted(links - _concepts())


@pytest.mark.parametrize("name", CARDS)
def test_embedded_keys_resolve(name):
    embedded = {k for value in _card_loc(name).values() for k in re.findall(r"\$(\w+)\$", value)}
    assert not sorted(embedded - set(_all_loc()))


@pytest.mark.parametrize("name", CARDS)
def test_data_functions_exist_in_the_game(name):
    used = _calls(_card(name)) | _calls(GENERATED.read_text(encoding="utf-8-sig"))
    used |= {fn for value in _card_loc(name).values() for fn in _calls(value)}
    vanilla = set()
    for path in [*_vanilla().glob("*/gui/**/*.gui"), *_vanilla().glob("main_menu/localization/english/**/*.yml")]:
        vanilla |= _calls(path.read_text(encoding="utf-8-sig", errors="replace"))
    assert {"GetPlayer", "GetCapital", "IsValid"} <= used
    assert not sorted(used - vanilla)


def test_harvest_modifier_links_cover_every_area():
    embedded = {k for value in _card_loc("harvest").values() for k in re.findall(r"\$(\w+)\$", value)}
    assert {f"PP_HARVEST_BY_AREA_{s.upper()}" for s in SEVERITIES} <= embedded
    harvest = (MOD_ROOT / location_status.HARVEST_MODIFIERS).read_text(encoding="utf-8-sig")
    modifiers = set(location_status.harvest_modifiers(harvest))
    linked = set(re.findall(r"ShowModifier\('(\w+)'\)", HARVEST_LOC.read_text(encoding="utf-8-sig")))
    assert linked == modifiers and len(linked) > 50


def _rows(name: str) -> dict[str, list[str]]:
    rows = re.findall(r'blockoverride "row_label" \{ text = "(\w+)" \}\s*blockoverride "row_goods" \{(.*?)\n\s*\}\n', _card(name), flags=re.DOTALL)
    return {label: re.findall(r'tooltip = "(\w+)"', body) for label, body in rows}


def test_goods_rows_follow_the_harvest_config():
    """Grain = the most sensitive goods, spared = the staple animals the harvests leave alone, and every harvested
    good shows once."""
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    goods = config["goods"]
    spared = set(exempt_goods(config)) & set(goods)
    shown = _rows("harvest")
    assert set(shown) == {"PP_EU_HARVEST_GOODS_GRAIN", "PP_EU_HARVEST_GOODS_CROPS", "PP_EU_HARVEST_GOODS_HARDY", "PP_EU_HARVEST_GOODS_SPARED"}
    every = [g for row in shown.values() for g in row]
    assert sorted(every) == sorted(goods)
    assert set(shown["PP_EU_HARVEST_GOODS_GRAIN"]) == {g for g, c in goods.items() if c["sensitivity"] == "high"}
    assert set(shown["PP_EU_HARVEST_GOODS_SPARED"]) == spared
    assert set(shown["PP_EU_HARVEST_GOODS_CROPS"]) == {g for g, c in goods.items() if c["sensitivity"] == "medium"} - spared


def test_arable_land_improvements_row_shows_land_improvements():
    """The improvements row shows only buildings that add arable land (footprint class capacity_source)."""
    shown = _rows("arable_land")["PP_EU_LAND_IMPROVEMENTS_ROW"]
    sources = {path.stem for path in (ROOT / "blueprints/accepted").rglob("*.yml")
               if re.search(r"(?m)^footprint:\s*capacity_source\s*$", path.read_text(encoding="utf-8"))}
    assert shown and not sorted(set(shown) - sources)


def test_old_land_names_are_gone():
    """No player text uses the retired names: Arable Land; Abundant, Available and Overused Arable Land."""
    found = []
    for path in sorted((MOD_ROOT / "main_menu/localization/english").glob("*.yml")):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("#"):
                continue
            hit = OLD_LAND_NAMES.search(line)
            if hit:
                found.append(f"{path.name}: {hit.group(0)}: {line.strip()[:80]}")
    assert not found, "\n".join(found)


def test_land_state_icons_exist():
    """The chip, the concepts and the card draw the states with tools/build_arable_land_icons.py's icons."""
    for name in ("abundant", "available", "overused"):
        assert (MOD_ROOT / "main_menu" / f"gfx/interface/icons/{location_status.LAND_ICONS}/{name}.dds").is_file()
    status = location_status.status_row(location_status.Harvests())
    assert all(f"{location_status.LAND_ICONS}/{n}.dds" in status for n in ("abundant", "available", "overused"))


def test_capital_medallions_read_the_capital():
    text = GENERATED.read_text(encoding="utf-8-sig")
    assert "LocationView" not in text and "GetPlayer.GetCapital.Custom('pp_harvest_severity')" in text
    land = _card("arable_land")
    for marker in ("pp_land_overpopulation", "pp_land_abundant", "pp_land_available"):
        assert f"GetPlayer.GetCapital.GetModifierValueFixed('{marker}')" in land
