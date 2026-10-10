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
from prosper_or_perish_constructor.staple_foods import GROUPS, goods_in_group, staple_foods
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
    "food": ("# ---- Food ----", "# ---- Food Production ----", ("game_concept_pp_staple_foods_desc",)),
    "food_production": ("# ---- Food Production ----", "# ---- Food Consumption ----", ("game_concept_pp_staple_foods_desc",)),
    "labor": ("# ---- Labor ----", "# ---- Variable Harvests ----", ()),
    "logistics": ("# ---- Logistics (Market Access) ----", "# ---- Farming/Fishing/Forest Capacities ----",
                  ("game_concept_supported_building_levels_desc",)),
}
# Retired player-facing names of the population capacity and its states (renamed to Arable Land 2026-10-10).
# "Farmland Vegetation" and lower-case "farmland" (the vegetation type, prose about fields) stay.
OLD_LAND_NAMES = re.compile(r"Subsistence Land|subsistence land|Free Land|Overpopulation|Location Potential|Settled Land"
                            r"|\bFarmland\b(?! Vegetation)|\[pp_farmland\|e\]|\[pp_arable_land\|e\]|pp_settled_land")
_CONCEPT_LINK = re.compile(r"\[(\w+)\|[eE]\]|\[Concept\('(\w+)'")
# a hoverable game link: a named object ([ShowGoodsName('x')|e], [ShowModifier('x')], ...) or a concept
_LINK = re.compile(r"\[(?:Show\w+\('\w+'\)(?:\|[eE])?|\w+\|[eE]|Concept\('\w+',\s*'[^']+'\)\|[eE])\]")
# the layers that make a banner's scene (settlements, workshops, temples, docks, forts); no two banners share one
SCENE_LAYERS = ("settlement1", "settlement2", "factories", "religious_buildings", "dock", "fortifications")


def _card(name: str) -> str:
    first, following, _ = CARDS[name]
    text = EUROPEDIA.read_text(encoding="utf-8-sig")
    start = text.index(first)
    return text[start:text.index(following, start)]


def _block_end(text: str, start: int) -> int:
    """The index just past the brace that closes the block whose content starts at start."""
    depth = 1
    while depth:
        depth += {"{": 1, "}": -1}.get(text[start], 0)
        start += 1
    return start


def _blocks(text: str, opener: str) -> list[tuple[int, int]]:
    """(start, end) of every block opened by the regex opener (which ends in an opening brace)."""
    return [(m.start(), _block_end(text, m.end())) for m in re.finditer(opener, text)]


def _cut(text: str, spans: list[tuple[int, int]]) -> str:
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    return text


def _live_lines(card: str) -> list[tuple[int, int]]:
    """The hboxes of the live lines (the mechanic in the player's own game)."""
    spans = []
    for m in re.finditer(r'visible = "\[GetPlayer\.IsValid\]"', card):
        start = card.rindex("hbox = {", 0, m.start())
        spans.append((start, _block_end(card, start + len("hbox = {"))))
    return spans


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
    """The card's own texts, the link captions written in its GUI (raw_text) and the concepts it links (the harvest's
    per-area modifier lists are generated)."""
    mod = _loc(MOD_ROOT)
    keys = set(re.findall(r'(?:text|tooltip) = "(\w+)"', _card(name))) | set(CARDS[name][2])
    texts = {k: mod[k] for k in keys if k in mod}
    for i, raw in enumerate(re.findall(r'raw_text = "([^"]*\[[^"]*)"', _card(name))):
        texts[f"raw_text#{i}"] = raw
    return texts


def _texture_exists(texture: str) -> bool:
    roots = [_vanilla() / r for r in ("main_menu", "in_game", "loading_screen")] + [MOD_ROOT / r for r in ("main_menu", "in_game")]
    return any((root / texture).is_file() for root in roots)


def _concepts() -> set[str]:
    """Every concept name and alias (`pop = { alias = { pops } }` links as [pops|e] too)."""
    concepts = set()
    for root in (_vanilla(), MOD_ROOT):
        for path in (root / "main_menu/common/game_concepts").glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            concepts |= set(re.findall(r"(?m)^(\w+)\s*=\s*\{", text))
            concepts |= {a for aliases in re.findall(r"\balias\s*=\s*\{([^}]*)\}", text) for a in aliases.split()}
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
    """Numbers live behind the links (modifier and concept tooltips), never in the text. Live values the game fills
    in (`[...]` data functions, e.g. the capital's months of food) are not written numbers."""
    for key, value in _card_loc(name).items():
        assert not re.search(r"\d", re.sub(r"\[[^\[\]]*\]", "", value)), key


@pytest.mark.parametrize("name", CARDS)
def test_concept_links_resolve(name):
    links = {a or b for value in _card_loc(name).values() for a, b in _CONCEPT_LINK.findall(value)}
    assert links and not sorted(links - _concepts())


@pytest.mark.parametrize("name", CARDS)
def test_embedded_keys_resolve(name):
    embedded = {k for value in _card_loc(name).values() for k in re.findall(r"\$(\w+)\$", value)}
    assert not sorted(embedded - set(_all_loc()))


@pytest.mark.parametrize("name", CARDS)
def test_named_goods_buildings_and_pops_exist(name):
    """[ShowGoodsName('x')], [ShowBuildingTypeName('x')], [ShowPopTypeName('x')] and the terrain names name real keys
    (a typo shows raw); [ShowModifier('x')] names a real static modifier."""
    texts = _card_loc(name).values()
    named = {k for value in texts for k in re.findall(
        r"Show(?:GoodsName|BuildingTypeName|PopTypeName|TopographyName|VegetationName|ClimateName)\('(\w+)'\)", value)}
    assert not sorted(named - set(_all_loc()))
    modifiers = {k for value in texts for k in re.findall(r"ShowModifier\('(\w+)'\)", value)}
    assert not sorted(k for k in modifiers if f"STATIC_MODIFIER_NAME_{k}" not in _all_loc())


@pytest.mark.parametrize("name", CARDS)
def test_every_icon_carries_a_link(name):
    """Every icon on a card names what it shows with a hoverable game link (Jan, 2026-10-10): each pp_eu_item its
    caption, each pp_eu_step its step_link, each scale step its label. Only the header, the banner, the section
    headings, the arrows and the live line stand without one."""
    card = _card(name)
    body = card[card.index("pp_eu_lead"):]
    items = _blocks(body, r"\bpp_eu_item = \{")
    for start, end in items:
        link = re.search(r'blockoverride "item_link" \{ raw_text = "([^"]*)" \}', body[start:end])
        assert link and _LINK.search(link.group(1)), body[start:end][:160]
    steps = _blocks(body, r"\bpp_eu_step = \{")
    for start, end in steps:
        link = re.search(r'blockoverride "step_link" \{ pp_eu_link = \{ raw_text = "([^"]*)" \} \}', body[start:end])
        assert link and _LINK.search(link.group(1)), body[start:end][:160]
    scales = _blocks(body, r"\bpp_eu_scale_step = \{")
    for start, end in scales:
        label = re.search(r'blockoverride "scale_label" \{ text = "(\w+)" \}', body[start:end]).group(1)
        assert _LINK.search(_all_loc()[label]), label
    rest = _cut(body, _live_lines(body) + items + steps + scales)
    rest = re.sub(r'blockoverride "section_icon" \{[^}]*\}', "", rest)
    assert "pp_eu_goods =" not in rest and "pp_eu_icon =" not in rest
    assert not re.search(r"texture = ", rest), rest[rest.find("texture = ") - 200:][:300]


@pytest.mark.parametrize("name", CARDS)
def test_data_functions_exist_in_the_game(name):
    used = _calls(_card(name)) | _calls(GENERATED.read_text(encoding="utf-8-sig"))
    used |= {fn for value in _card_loc(name).values() for fn in _calls(value)}
    vanilla = set()
    for path in [*_vanilla().glob("*/gui/**/*.gui"), *_vanilla().glob("main_menu/localization/english/**/*.yml")]:
        vanilla |= _calls(path.read_text(encoding="utf-8-sig", errors="replace"))
    assert used
    if "[GetPlayer.IsValid]" in _card(name):   # the live line reads the player's capital
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
    """Row label -> the goods or buildings its items name, in order (a row may wrap into several lines)."""
    card = _card(name)
    rows = {}
    for m in re.finditer(r'blockoverride "row_label" \{ text = "(\w+)" \}\s*blockoverride "row_goods" \{', card):
        body = card[m.end():_block_end(card, m.end())]
        rows[m.group(1)] = re.findall(r"Show(?:GoodsName|BuildingTypeName)\('(\w+)'\)", body)
    return rows


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


def test_staple_foods_follow_the_staple_list():
    """The Food card's Staple Foods row and the Staple Foods concept list every staple food (staple_foods.py), the
    concept by group."""
    assert sorted(_rows("food")["PP_EU_FOOD_STAPLES_ROW"]) == sorted(staple_foods())
    desc = _loc(MOD_ROOT)["game_concept_pp_staple_foods_desc"]
    for group in GROUPS:
        line = re.search(rf"#T Staple {group}:#!(.*?)(?:\\n|$)", desc).group(1)
        assert sorted(re.findall(r"ShowGoodsName\('(\w+)'\)", line)) == sorted(goods_in_group(group)), group


def test_staple_food_farms_provision():
    """The farms the Food Production card shows feed their province (a Provisioning method) and the entries show the
    food buildings it explains."""
    card = _card("food_production")
    buildings = {}
    for start, end in _blocks(card, r'blockoverride "entry_icons" \{'):
        title = re.match(r'\s*blockoverride "entry_title" \{ text = "(\w+)" \}', card[end:]).group(1)
        buildings[title] = re.findall(r"ShowBuildingTypeName\('(\w+)'\)", card[start:end])
    blueprints = {path.stem: path for path in (ROOT / "blueprints/accepted").rglob("*.yml")}
    farms = buildings["PP_EU_PROD_FARMS"]
    assert len(farms) >= 3
    for farm in farms:
        assert re.search(rf"\bpp_{farm}_provision\b", blueprints[farm].read_text(encoding="utf-8")), farm
    shown = {key for row in buildings.values() for key in row}
    assert {"cookshop", "public_kitchen", "grange", "victualling_yard", "tavern"} <= shown <= set(blueprints)


def test_logistics_haulage_rows_follow_the_config():
    """The haulage rows show the goods the logistics buildings cut ([logistics] in constructor.toml): the bulky goods,
    the half-cut goods and the bulky staples."""
    logistics = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))["logistics"]
    rows = _rows("logistics")
    assert rows["PP_EU_LOGI_HEAVY_ROW"] == logistics["bulky_goods"]
    assert rows["PP_EU_LOGI_HALF_ROW"] == logistics["bulky_half_goods"]
    assert sorted(rows["PP_EU_LOGI_STAPLES_ROW"]) == sorted(logistics["bulky_staples"])
    cuts = [logistics["bulky_staples"][g] for g in rows["PP_EU_LOGI_STAPLES_ROW"]]
    assert cuts == sorted(cuts, reverse=True)   # bulkiest first


def test_banners_are_distinct():
    """Every card has its own banner and no two banners share a scene layer (Jan, 2026-10-10: distinct pictures)."""
    import importlib.util
    import sys

    banners = [re.search(r'texture = "(gfx/interface/illustrations/pp_europedia/[^"]+)"', _card(n)).group(1) for n in CARDS]
    assert len(set(banners)) == len(banners)
    spec = importlib.util.spec_from_file_location("build_europedia_banners", ROOT / "tools/build_europedia_banners.py")
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool   # its dataclasses look themselves up there
    spec.loader.exec_module(tool)
    assert {Path(b).stem.removeprefix("banner_") for b in banners} <= set(tool.BANNERS)
    seen: dict[str, str] = {}
    for name, banner in tool.BANNERS.items():
        scene = {layer.path for layer in banner.layers if layer.path.split("/")[0] in SCENE_LAYERS}
        assert scene, name
        for path in scene:
            assert path not in seen, f"{name} and {seen.get(path)} share {path}"
            seen[path] = name


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
