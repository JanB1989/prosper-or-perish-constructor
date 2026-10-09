"""The Europedia card style (in_game/gui/shared/pp_europedia_style.gui) and the Variable Harvests card built with it.

The card is hand-kept GUI and localization the game only checks when it draws them, so these tests read the files the
game loads: every texture, localization key, concept link, modifier link and data function the card uses exists, the
card carries no numbers (they live in the linked modifiers' tooltips), and its goods rows follow variable_harvests.toml.
"""

from __future__ import annotations

import re
import tomllib
from functools import cache
from pathlib import Path

from prosper_or_perish_constructor import location_status
from scripts.generate_variable_harvests import exempt_goods
from test_gui_blocks import _calls, _vanilla

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
STYLE = MOD_ROOT / "in_game/gui/shared/pp_europedia_style.gui"
GENERATED = MOD_ROOT / location_status.EUROPEDIA_HARVEST_GUI
EUROPEDIA = MOD_ROOT / "in_game/gui/encyclopedia_lateralview.gui"
EUROPEDIA_LOC = MOD_ROOT / "main_menu/localization/english/pp_europedia_l_english.yml"
HARVEST_LOC = MOD_ROOT / location_status.HARVEST_LOCALIZATION
CONFIG = ROOT / "variable_harvests.toml"
SEVERITIES = ("abysmal", "very_poor", "poor", "good", "very_good", "bountiful")


def _card() -> str:
    text = EUROPEDIA.read_text(encoding="utf-8-sig")
    start = text.index("# ---- Variable Harvests ----")
    return text[start:text.index("# ---- Population Capacity ----", start)]


@cache
def _loc(root: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for path in sorted((root / "main_menu/localization/english").rglob("*.yml")):
        for key, value in re.findall(r'(?m)^\s*([A-Za-z0-9_.\-]+):\d*\s*"(.*)"\s*$', path.read_text(encoding="utf-8-sig", errors="replace")):
            keys[key] = value
    return keys


def _all_loc() -> dict[str, str]:
    return {**_loc(_vanilla()), **_loc(MOD_ROOT)}


def _card_loc() -> dict[str, str]:
    """The card's own texts and the harvest concepts it links (the per-area modifier lists are generated)."""
    mod = _loc(MOD_ROOT)
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _card()))
    keys |= {f"game_concept_{s}_harvest_desc" for s in (*SEVERITIES, "average")}
    return {k: mod[k] for k in keys if k in mod}


def _texture_exists(texture: str) -> bool:
    roots = [_vanilla() / r for r in ("main_menu", "in_game", "loading_screen")] + [MOD_ROOT / r for r in ("main_menu", "in_game")]
    return any((root / texture).is_file() for root in roots)


def test_every_texture_exists():
    used = set()
    for text in (STYLE.read_text(encoding="utf-8-sig"), GENERATED.read_text(encoding="utf-8-sig"), _card()):
        used |= set(re.findall(r'texture = "(gfx/[^"]+)"', text))
    missing = sorted(t for t in used if not _texture_exists(t))
    assert used and not missing


def test_every_text_key_exists():
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _card()))
    missing = sorted(keys - set(_all_loc()))
    assert keys and not missing


def test_card_types_are_defined():
    defined = set(re.findall(r"type (pp_eu_\w+) =", STYLE.read_text(encoding="utf-8-sig") + GENERATED.read_text(encoding="utf-8-sig")))
    used = set(re.findall(r"\b(pp_eu_\w+) = \{", _card()))
    assert used and used <= defined


def test_card_text_has_no_numbers():
    """Numbers live behind the links (modifier and concept tooltips), never in the text."""
    for key, value in _card_loc().items():
        assert not re.search(r"\d", value), key


def test_concept_links_resolve():
    concepts = set()
    for root in (_vanilla(), MOD_ROOT):
        for path in (root / "main_menu/common/game_concepts").glob("*.txt"):
            concepts |= set(re.findall(r"(?m)^(\w+)\s*=\s*\{", path.read_text(encoding="utf-8-sig", errors="replace")))
    links = {m for value in _card_loc().values() for m in re.findall(r"\[(\w+)\|[eE]\]", value)}
    assert links and not sorted(links - concepts)


def test_embedded_keys_and_modifier_links_resolve():
    loc = _all_loc()
    texts = list(_card_loc().values())
    embedded = {k for value in texts for k in re.findall(r"\$(\w+)\$", value)}
    assert {f"PP_HARVEST_BY_AREA_{s.upper()}" for s in SEVERITIES} <= embedded
    assert not sorted(embedded - set(loc))
    harvest = (MOD_ROOT / location_status.HARVEST_MODIFIERS).read_text(encoding="utf-8-sig")
    modifiers = set(location_status.harvest_modifiers(harvest))
    linked = set(re.findall(r"ShowModifier\('(\w+)'\)", HARVEST_LOC.read_text(encoding="utf-8-sig")))
    assert linked == modifiers and len(linked) > 50


def test_data_functions_exist_in_the_game():
    used = _calls(_card()) | _calls(GENERATED.read_text(encoding="utf-8-sig"))
    used |= {name for value in _card_loc().values() for name in _calls(value)}
    vanilla = set()
    for path in [*_vanilla().glob("*/gui/**/*.gui"), *_vanilla().glob("main_menu/localization/english/**/*.yml")]:
        vanilla |= _calls(path.read_text(encoding="utf-8-sig", errors="replace"))
    assert {"GetPlayer", "GetCapital", "Custom", "IsValid"} <= used
    assert not sorted(used - vanilla)


def test_goods_rows_follow_the_harvest_config():
    """Grain = the most sensitive goods, spared = the staple animals the harvests leave alone, and every harvested
    good shows once."""
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    goods = config["goods"]
    spared = set(exempt_goods(config)) & set(goods)
    rows = re.findall(r'blockoverride "row_label" \{ text = "(\w+)" \}\s*blockoverride "row_goods" \{(.*?)\n\s*\}\n', _card(), flags=re.DOTALL)
    shown = {label: re.findall(r'tooltip = "(\w+)"', body) for label, body in rows}
    assert set(shown) == {"PP_EU_HARVEST_GOODS_GRAIN", "PP_EU_HARVEST_GOODS_CROPS", "PP_EU_HARVEST_GOODS_HARDY", "PP_EU_HARVEST_GOODS_SPARED"}
    every = [g for row in shown.values() for g in row]
    assert sorted(every) == sorted(goods)
    assert set(shown["PP_EU_HARVEST_GOODS_GRAIN"]) == {g for g, c in goods.items() if c["sensitivity"] == "high"}
    assert set(shown["PP_EU_HARVEST_GOODS_SPARED"]) == spared
    assert set(shown["PP_EU_HARVEST_GOODS_CROPS"]) == {g for g, c in goods.items() if c["sensitivity"] == "medium"} - spared


def test_capital_medallion_reads_the_capital():
    text = GENERATED.read_text(encoding="utf-8-sig")
    assert "LocationView" not in text and "GetPlayer.GetCapital.Custom('pp_harvest_severity')" in text
