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
    "food_consumption": ("# ---- Food Consumption ----", "# ---- New Trade Goods (Victuals) ----",
                         ("game_concept_pp_staple_foods_desc", "game_concept_pp_food_storage_desc")),
    "labor": ("# ---- Labor ----", "# ---- Variable Harvests ----", ()),
    "logistics": ("# ---- Logistics (Market Access) ----", "# ---- Farming/Fishing/Forest Capacities ----",
                  ("game_concept_supported_building_levels_desc",)),
    "trade_goods": ("# ---- New Trade Goods (Victuals) ----", "# ---- Logistics (Market Access) ----",
                    ("game_concept_pp_staple_foods_desc", "game_concept_pp_labor_desc", "game_concept_pp_building_limits_desc")),
    "rural_capacities": ("# ---- Farming/Fishing/Forest Capacities ----", "# ---- Labor ----",
                         ("game_concept_pp_fish_capacity_desc", "game_concept_pp_forest_capacity_desc")),
    "population_growth": ("# ---- Population Growth ----", "# ---- Buildings in Location (Other Changes) ----",
                          ("game_concept_pp_food_storage_desc", "game_concept_pp_overused_arable_land_desc")),
}
# Retired player-facing names of the population capacity and its states (renamed to Arable Land 2026-10-10).
# "Farmland Vegetation" and lower-case "farmland" (the vegetation type, prose about fields) stay.
OLD_LAND_NAMES = re.compile(r"Subsistence Land|subsistence land|Free Land|Overpopulation|Location Potential|Settled Land"
                            r"|\bFarmland\b(?! Vegetation)|\[pp_farmland\|e\]|\[pp_arable_land\|e\]|pp_settled_land")
_CONCEPT_LINK = re.compile(r"\[(\w+)\|[eE]\]|\[Concept\('(\w+)'")
# a hoverable game link: a named object ([ShowGoodsName('x')|e], [ShowModifier('x')], ...) or a concept
_LINK = re.compile(r"\[(?:Show\w+\('\w+'\)(?:\|[eE])?|\w+\|[eE]|Concept\('\w+',\s*'[^']+'\)\|[eE])\]")


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


@cache
def _building_blocks() -> dict[str, str]:
    """Building key -> its top-level block(s) in the mod's building files, comments dropped (what the game loads)."""
    opener = re.compile(r"(?m)^[ \t]*(?:[A-Z_]+:)?(\w+)\s*=\s*\{")
    blocks: dict[str, str] = {}
    for path in sorted((MOD_ROOT / "in_game/common/building_types").glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        pos = 0
        while m := opener.search(text, pos):
            pos = _block_end(text, m.end())
            blocks[m.group(1)] = blocks.get(m.group(1), "") + text[m.end():pos]
    return blocks


def _entries(name: str) -> dict[str, str]:
    """Entry title key -> the entry's icon column."""
    card = _card(name)
    entries = {}
    for start, end in _blocks(card, r'blockoverride "entry_icons" \{'):
        title = re.match(r'\s*blockoverride "entry_title" \{ text = "(\w+)" \}', card[end:]).group(1)
        entries[title] = card[start:end]
    return entries


def test_trade_goods_bookkeeping_goods_are_the_dummy_goods():
    """The New Trade Goods card's bookkeeping entries show exactly the dummy goods: the floor-pinned and store-following
    goods of [production_gate] that feed nobody, each with its own goods file in the mod and made or bought by a
    building."""
    gate = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))["production_gate"]
    buildings = "\n".join(_building_blocks().values())
    dummies = set()
    for good in {*gate["pinned_goods"], *gate["dynamic_goods"]}:
        path = MOD_ROOT / "in_game/common/goods" / f"pp_goods_{good}.txt"
        if not path.is_file() or re.search(r"(?m)^\s*food\s*=\s*[1-9]", path.read_text(encoding="utf-8-sig")):
            continue   # Province Food is real food
        if re.search(rf"(?m)^\s*(?:produced\s*=\s*{good}|{good}\s*=\s*[\d.]+)\s*$", buildings):
            dummies.add(good)
    shown = {good for title, icons in _entries("trade_goods").items() if title.startswith("PP_EU_GOODS_DUMMY_")
             for good in re.findall(r"ShowGoodsName\('(\w+)'\)", icons)}
    assert dummies and shown == dummies


def test_trade_goods_victuals_users_follow_the_buildings():
    """The victuals rows show every building whose methods buy victuals (the Tavern has its own step): armies and
    fleets = the military and naval ones, carriers = those making logistics, work crews = the rest. The pops row shows
    the pops the victuals goods file gives a demand, most per head first."""
    users = {k: b for k, b in _building_blocks().items() if re.search(r"(?m)^\s*victuals\s*=\s*[\d.]+", b)}
    military = {k for k, b in users.items() if re.search(r"(?m)^\s*category\s*=\s*(?:military|naval)_category\b", b)}
    carriers = {k for k, b in users.items() if re.search(r"(?m)^\s*produced\s*=\s*logistics\b", b)}
    rows = _rows("trade_goods")
    assert "tavern" in users and "ShowBuildingTypeName('tavern')" in _card("trade_goods")
    assert military and set(rows["PP_EU_GOODS_MILITARY_ROW"]) == military
    assert carriers and set(rows["PP_EU_GOODS_CARRIERS_ROW"]) == carriers
    assert set(rows["PP_EU_GOODS_CREWS_ROW"]) == set(users) - military - carriers - {"tavern"}
    card = _card("trade_goods")
    m = re.search(r'blockoverride "row_label" \{ text = "PP_EU_GOODS_POPS_ROW" \}\s*blockoverride "row_goods" \{', card)
    pops = re.findall(r"ShowPopTypeName\('(\w+)'\)", card[m.end():_block_end(card, m.end())])
    goods = (MOD_ROOT / "in_game/common/goods/pp_goods_victuals.txt").read_text(encoding="utf-8-sig")

    def table(name: str) -> dict[str, float]:
        body = re.search(rf"{name}\s*=\s*\{{([^}}]*)\}}", goods).group(1)
        return {pop: float(value) for pop, value in re.findall(r"(\w+)\s*=\s*([\d.]+)", body)}

    assert sorted(pops) == sorted(p for p, v in table("demand_add").items() if v > 0)
    multiply = table("demand_multiply")
    assert pops == sorted(pops, key=lambda p: -multiply[p])   # "nobles most"


def test_trade_goods_odd_methods_exist():
    """The odd-looking methods the card names are in the buildings it shows: the Market slot's Market Sales (offset in,
    the main good out), Provisioning (a token of the crop in, Province Food out), meals sold for offset, and the
    replaced building's recipes kept as Old Ways."""
    blocks, loc = _building_blocks(), _loc(MOD_ROOT)

    def method(building: str, key: str) -> str:
        m = re.search(rf"\b{key}\s*=\s*\{{", blocks[building])
        return blocks[building][m.end():_block_end(blocks[building], m.end())]

    market = method("tools_workshop", "pp_tools_workshop_market_sales")
    assert re.search(r"(?m)^\s*offset\s*=", market) and re.search(r"produced\s*=\s*tools\b", market)
    assert loc["pp_tools_workshop_market_sales"] == "Market Sales"
    provision = method("wheat_farm", "pp_wheat_farm_provision")
    assert re.search(r"(?m)^\s*wheat\s*=", provision) and re.search(r"produced\s*=\s*local_food\b", provision)
    assert loc["pp_wheat_farm_provision"] == "Provision with Wheat"
    for kitchen in ("cookshop", "public_kitchen"):
        assert re.search(r"produced\s*=\s*offset\b", blocks[kitchen]), kitchen
    old = re.findall(r"\b(pp_tools_workshop_legacy_\w+_tools_guild_\w+)\s*=\s*\{", blocks["tools_workshop"])
    assert old and all(loc[key].endswith("(Old Ways)") for key in old)


@cache
def _consumption_blocks() -> dict[str, str]:
    """Static modifier or building key -> its block(s) in the mod's static modifier and building files, comments dropped
    (INJECT and REPLACE blocks under the plain key; several blocks of one key joined)."""
    opener = re.compile(r"(?m)^[ \t]*(?:[A-Z_]+:)?(\w+)\s*=\s*\{")
    blocks: dict[str, str] = {}
    folders = ("main_menu/common/static_modifiers", "in_game/common/static_modifiers", "in_game/common/building_types")
    for path in sorted(p for folder in folders for p in (MOD_ROOT / folder).glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        pos = 0
        while m := opener.search(text, pos):
            pos = _block_end(text, m.end())
            blocks[m.group(1)] = blocks.get(m.group(1), "") + text[m.end():pos]
    return blocks


def _eats(key: str, pop: str = "peasants") -> float | None:
    """local_<pop>_food_consumption of a static modifier or building (None when it has none)."""
    found = re.findall(rf"\blocal_{pop}_food_consumption\s*=\s*(-?[\d.]+)", _consumption_blocks().get(key, ""))
    return sum(float(v) for v in found) if found else None


def _row_links(name: str) -> dict[str, list[str]]:
    """Row label -> the link captions of its items, in order."""
    card = _card(name)
    rows = {}
    for m in re.finditer(r'blockoverride "row_label" \{ text = "(\w+)" \}\s*blockoverride "row_goods" \{', card):
        rows[m.group(1)] = re.findall(r'blockoverride "item_link" \{ raw_text = "([^"]*)" \}', card[m.end():_block_end(card, m.end())])
    return rows


def test_food_consumption_scale_follows_the_pop_types():
    """Who Eats How Much shows every pop type that eats from the store, hungriest first (pop_food_consumption in
    pop_types/pp_pop_adjustments.txt); the tribesmen eat nothing from it and the text says so."""
    text = re.sub(r"#[^\n]*", "", (MOD_ROOT / "in_game/common/pop_types/pp_pop_adjustments.txt").read_text(encoding="utf-8-sig"))
    rates = {m.group(1): float(m.group(2)) for m in re.finditer(r"(?:[A-Z_]+:)?(\w+)\s*=\s*\{[^{}]*?\bpop_food_consumption\s*=\s*(-?[\d.]+)", text)}
    card, loc = _card("food_consumption"), _loc(MOD_ROOT)
    labels = [loc[key] for start, end in _blocks(card, r"\bpp_eu_scale_step = \{")
              for key in re.findall(r'blockoverride "scale_label" \{ text = "(\w+)" \}', card[start:end])]
    shown = [re.fullmatch(r"\[ShowPopTypeName\('(\w+)'\)\]", label).group(1) for label in labels]
    assert set(shown) == {pop for pop, rate in rates.items() if rate > 0}
    assert [rates[pop] for pop in shown] == sorted((rates[pop] for pop in shown), reverse=True)
    assert rates["tribesmen"] == 0 and "ShowPopTypeName('tribesmen')" in loc["PP_EU_CONS_WHO_DESC"]


def test_food_consumption_modifiers_point_the_right_way():
    """What the card says raises or lowers consumption does so in the files: winter and prosperity raise every settled
    pop's, negative prosperity (devastation, applied scaled by the negative prosperity) lowers the peasants', the
    peasants' rows and the estate entry point the way their labels say, and the old cheap and expensive food modifiers
    the card leaves out carry no effect."""
    settled = ("nobles", "clergy", "burghers", "laborers", "peasants")
    for key in ("winter_mild", "winter_normal", "winter_severe", "prosperity"):
        assert all((_eats(key, pop) or 0) > 0 for pop in settled), key
    assert (_eats("devastation") or 0) > 0   # x the negative prosperity: the peasants eat less
    harvest = (MOD_ROOT / location_status.HARVEST_MODIFIERS).read_text(encoding="utf-8-sig")
    harvests = location_status.harvest_modifiers(harvest)
    rows = _row_links("food_consumption")
    assert set(rows) == {"PP_EU_CONS_PEASANTS_LESS", "PP_EU_CONS_PEASANTS_MORE"}
    for label, sign in (("PP_EU_CONS_PEASANTS_LESS", -1), ("PP_EU_CONS_PEASANTS_MORE", 1)):
        assert rows[label]
        for link in rows[label]:
            if m := re.fullmatch(r"\[(\w+)_harvest\|e\]", link):
                values = [_eats(key) for key in harvests if location_status.severity(key) == m.group(1)]
            else:
                values = [_eats(re.fullmatch(r"\[Show(?:Modifier|BuildingTypeName)\('(\w+)'\)(?:\|e)?\]", link).group(1))]
            assert values and all(v is not None and v * sign > 0 for v in values), link
    entry = _card("food_consumption")
    assert (_eats("nobles_mansion", "nobles") or 0) > 0 and (_eats("burgher_mansion", "burghers") or 0) > 0
    assert (_eats("peasants_hunting_grounds") or 0) < 0 < (_eats("festival_grounds") or 0)
    assert "nobles_mansion" in entry and "peasants_hunting_grounds" in entry
    for key in ("cheap_food_in_location", "expensive_food_in_location"):
        assert not re.search(r"\w+\s*=\s*-?[\d.]+", re.sub(r"game_data\s*=\s*\{[^}]*\}", "", _consumption_blocks()[key])), key


def test_food_consumption_staple_raw_materials_feed_their_peasants():
    """Where a location's raw material is a staple food its peasants eat less (pp_rgo_bonus_<good>); the cash crops the
    text names make them eat more."""
    bonuses = {good: _eats(f"pp_rgo_bonus_{good}") for good in staple_foods() if f"pp_rgo_bonus_{good}" in _consumption_blocks()}
    assert bonuses and all(v is not None and v < 0 for v in bonuses.values()), bonuses
    assert all((_eats(f"pp_rgo_bonus_{good}") or 0) > 0 for good in ("sugar", "silk", "wine"))


def _rural_row_links(name: str) -> dict[str, list[tuple[str, str]]]:
    """Row label -> (Show function or "concept", key) of every item link in the row, in order."""
    card = _card(name)
    rows = {}
    for m in re.finditer(r'blockoverride "row_label" \{ text = "(\w+)" \}\s*blockoverride "row_goods" \{', card):
        body = card[m.end():_block_end(card, m.end())]
        rows[m.group(1)] = [(fn or "concept", key or concept)
                            for fn, key, concept in re.findall(r"\[(?:Show(\w+)\('(\w+)'\)|(\w+)\|e\])", body)]
    return rows


def _rural_script_value(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8-sig")
    start = text.index(f"{name} = {{") + len(f"{name} = {{")
    return text[start:_block_end(text, start)]


def test_rural_capacities_farm_rows_take_arable_land():
    """The Rural Capacities farm rows show the first tier of every farm that takes arable land
    (rural_capacity.LAND_FARM_BUILDINGS), each in the row of the land one level takes ([worldbuilder.farm_land] in
    constructor.toml: fields, herds the least, plantations the most); its blueprint caps it by the farm capacity and
    records that land."""
    from prosper_or_perish_constructor.rural_capacity import LAND_FARM_BUILDINGS, capacity_max_omitted_buildings_by_building

    blueprints = ROOT / "blueprints/accepted/buildings"
    farm_land = tomllib.loads((ROOT / "constructor.toml").read_text(encoding="utf-8"))["worldbuilder"]["farm_land"]
    land_of = {b: farm_land[cls]["land"] for cls, members in farm_land["classes"].items() for b in members}
    land = {"PP_EU_RURAL_FIELDS_ROW": farm_land["arable"]["land"], "PP_EU_RURAL_HERDS_ROW": farm_land["herd"]["land"],
            "PP_EU_RURAL_PLANTATIONS_ROW": farm_land["plantation"]["land"]}
    assert land["PP_EU_RURAL_HERDS_ROW"] < land["PP_EU_RURAL_FIELDS_ROW"] < land["PP_EU_RURAL_PLANTATIONS_ROW"]
    rows = _rows("rural_capacities")
    omitted = capacity_max_omitted_buildings_by_building(blueprint_root=blueprints, capacity_buildings=LAND_FARM_BUILDINGS)
    assert sorted(b for row in land for b in rows[row]) == sorted(b for b in LAND_FARM_BUILDINGS if omitted[b] == (b,))
    for row, share in land.items():
        for farm in rows[row]:
            assert land_of.get(farm, farm_land["arable"]["land"]) == share, (row, farm)
            text = (blueprints / f"{farm}.yml").read_text(encoding="utf-8")
            assert f"max_levels = farm_capacity_max_{farm}" in text, farm
            assert re.search(rf"local_pp_farmland_used = {share:g}\b", text), farm


def test_rural_capacities_fish_and_forest_rows_follow_their_capacity():
    """The fishing and forest building rows show exactly the buildings those capacities cap (rural_capacity.py, their
    blueprints' max_levels); the rows of what gives or takes capacity show what the script values count."""
    from prosper_or_perish_constructor.rural_capacity import FISH_CAP_BUILDINGS, FOREST_CAP_BUILDINGS

    rows, links = _rows("rural_capacities"), _rural_row_links("rural_capacities")
    for row, prefix, buildings in (("PP_EU_RURAL_FISHERS_ROW", "fish_capacity_max", FISH_CAP_BUILDINGS),
                                   ("PP_EU_RURAL_FORESTERS_ROW", "forest_capacity_max", FOREST_CAP_BUILDINGS)):
        assert rows[row] == list(buildings)
        for building in buildings:
            text = (ROOT / "blueprints/accepted/buildings" / f"{building}.yml").read_text(encoding="utf-8")
            assert f"max_levels = {prefix}_{building}" in text, building
    values = MOD_ROOT / "in_game/common/script_values"
    fish = _rural_script_value(values / "pp_building_capacity_values.txt", "pp_fish_base_capacity_value")
    forest = _rural_script_value(values / "pp_building_capacity_values.txt", "pp_forest_base_capacity_value")
    grounds = links["PP_EU_RURAL_GROUNDS_ROW"]
    assert [k for f, k in grounds if f == "GoodsName"] == re.findall(r"raw_material = goods:(\w+)", fish)
    assert [k for f, k in grounds if f == "TopographyName"] == re.findall(r"topography = (\w+)", fish)
    assert [k for f, k in grounds if f == "concept"] == ["coastal", "lake", "river"]
    assert "pp_is_sea_coast = yes" in fish and "is_adjacent_to_lake = yes" in fish
    assert "modifier:fish_capacity_from_river_size" in _rural_script_value(values / "pp_fishing_capacity.txt", "fish_capacity")
    assert [k for f, k in links["PP_EU_RURAL_WOODLAND_ROW"]] == re.findall(r"vegetation = (\w+)", forest)
    assert {f for f, k in links["PP_EU_RURAL_WOODLAND_ROW"]} == {"VegetationName"}
    assert rows["PP_EU_RURAL_FOREST_RGO_ROW"] == re.findall(r"raw_material = goods:(\w+)", forest)
    assert links["PP_EU_RURAL_CLEARED_ROW"] == [("concept", "location_rank"), ("concept", "building")]
    capacity = _rural_script_value(values / "pp_forest_capacity.txt", "forest_capacity")
    assert "location_rank = location_rank:" in capacity and "total_building_levels" in capacity


def _store_growth() -> dict[int, float]:
    """Stored Food step -> its local_population_growth (pp_stored_food.txt; a step without the line gives none)."""
    text = (MOD_ROOT / "in_game/common/static_modifiers/pp_stored_food.txt").read_text(encoding="utf-8-sig")
    growth = {}
    for step, body in re.findall(r"(?ms)^pp_food_store_(\d+) = \{(.*?)^\}", text):
        line = re.search(r"\blocal_population_growth = (-?[\d.]+)", body)
        growth[int(step)] = float(line.group(1)) if line else 0.0
    return growth


def _rank_growth() -> dict[str, float]:
    """Location rank -> its own local_population_growth: vanilla's rank_modifier plus the mod's TRY_INJECT (the values
    add, as the rank file's 'vanilla X: net Y' notes say)."""
    ranks = ("rural_settlement", "town", "city", "megalopolis")
    growth = dict.fromkeys(ranks, 0.0)
    sources = ((_vanilla() / "in_game/common/location_ranks/00_default.txt", r"(?m)^({})\s*=\s*\{{"),
               (MOD_ROOT / "in_game/common/location_ranks/pp_location_rank_adjustments.txt", r"(?m)^TRY_INJECT:({})\s*=\s*\{{"))
    for path, opener in sources:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for m in re.finditer(opener.format("|".join(ranks)), text):
            block = text[m.end():_block_end(text, m.end())]
            growth[m.group(1)] += sum(float(v) for v in re.findall(r"\blocal_population_growth = (-?[\d.]+)", block))
    return growth


def test_population_growth_scale_follows_the_store():
    """The growth scale shows real Stored Food steps (pp_stored_food.txt), worst to best: starving, the almost empty
    store (step 0), the steps where the store's growth just makes up for the decline rural settlements and towns and
    cities carry of their own (their location rank), a step where every settlement grows and the full store (the
    last step). The card's text says the store's growth only rises and that rural settlements turn first."""
    loc = _loc(MOD_ROOT)
    labels = re.findall(r'blockoverride "scale_label" \{ text = "(\w+)" \}', _card("population_growth"))
    shown = [re.search(r"ShowModifier\('(\w+)'\)", loc[label]).group(1) for label in labels]
    assert shown[0] == "province_starving"
    empty, rural, towns, grows, full = (int(m.removeprefix("pp_food_store_")) for m in shown[1:])
    growth = _store_growth()
    assert sorted(growth) == list(range(len(growth)))
    assert [growth[s] for s in sorted(growth)] == sorted(growth.values())
    assert empty == 0 and growth[empty] == 0 and full == max(growth)
    decline = _rank_growth()
    assert decline["town"] == decline["city"] == decline["megalopolis"] < decline["rural_settlement"] < 0
    for step, rank in ((rural, "rural_settlement"), (towns, "town")):
        assert abs(growth[step] + decline[rank]) < 1e-9 and growth[step - 1] + decline[rank] < 0, step
    assert empty < rural < towns < grows < full
    assert growth[grows] + decline["town"] > 0
    starving = (MOD_ROOT / "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt").read_text(encoding="utf-8-sig")
    block = re.search(r"(?s)TRY_REPLACE:province_starving = \{(.*?)\n\}", starving).group(1)
    assert float(re.search(r"\blocal_population_growth = (-?[\d.]+)", block).group(1)) < decline["town"]


def test_banners_are_paintings_of_their_own():
    """Every card's banner is cut from its own painting (assets/europedia_paintings, Jan 2026-10-10: a picture of the
    page's topic in the loading screens' style, no stitched landscapes), and every strip fits its painting."""
    import importlib.util

    from PIL import Image

    banners = [re.search(r'texture = "(gfx/interface/illustrations/pp_europedia/[^"]+)"', _card(n)).group(1) for n in CARDS]
    assert len(set(banners)) == len(banners)
    spec = importlib.util.spec_from_file_location("build_europedia_banners", ROOT / "tools/build_europedia_banners.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert {Path(b).stem.removeprefix("banner_") for b in banners} <= set(tool.PAINTINGS)
    for name, top in tool.PAINTINGS.items():
        with Image.open(tool.PAINTINGS_DIR / f"{name}.jpg") as painting:
            assert painting.width >= 1450, name   # sharp at the card's width
            assert top + round(painting.width * tool.H / tool.W) <= painting.height, name


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
