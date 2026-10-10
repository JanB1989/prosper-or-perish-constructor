"""The Variable Harvests situation panel (in_game/gui/panels/situation/harvest_situation.gui).

The game opens gui/panels/situation/<situation key>.gui when the player clicks a situation; the harvests had none, so
the panel is the mod's own. It is hand-kept GUI the game checks only when it draws it, so these tests read the files
the game loads: blocks, textures, keys, links, data functions and the customizable localizations it compares exist,
its texts carry no numbers (they sit behind the links) and its goods follow the harvest config.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from PIL import Image

from prosper_or_perish_constructor import gui_blocks, location_status
from test_europedia_style import _all_loc, _concepts, _loc, _texture_exists
from test_gui_blocks import _calls, _index, _vanilla

ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
PANEL = MOD_ROOT / "in_game/gui/panels/situation/harvest_situation.gui"
CUSTOM = MOD_ROOT / location_status.CUSTOM_LOCALIZATION
HARVEST_LOC = MOD_ROOT / location_status.HARVEST_LOCALIZATION
CONFIG = ROOT / "variable_harvests.toml"
SEVERITIES = ("abysmal", "very_poor", "poor", "average", "good", "very_good", "bountiful")


def _panel() -> str:
    return PANEL.read_text(encoding="utf-8-sig")


def _panel_loc() -> dict[str, str]:
    """The panel's own texts and the situation's tooltip texts."""
    mod = _loc(MOD_ROOT)
    keys = set(re.findall(r'text = "(\w+)"', _panel())) | {"harvest_situation_desc", "harvest_situation_monthly"}
    return {k: mod[k] for k in keys if k in mod}


def test_panel_is_a_situation_panel_overriding_only_blocks_it_has():
    text = _panel()
    assert text.count("{") == text.count("}")
    assert re.search(r"(?m)^situation_panel = \{", text)
    assert not gui_blocks.dead_overrides(text, _index())
    # vanilla's blocks: picture, start date banner, subheader, main content
    for block in ("situation_panel_image", "situation_start_date", "situation_subheader_content", "situation_panel_main_content"):
        assert f'blockoverride "{block}"' in text


def test_every_texture_and_text_key_exists():
    textures = set(re.findall(r'texture = "(gfx/[^"]+)"', _panel()))
    assert textures and not sorted(t for t in textures if not _texture_exists(t))
    keys = set(re.findall(r'text = "(\w+)"', _panel()))
    assert keys and not sorted(keys - set(_all_loc()))


def test_texts_carry_no_numbers():
    for key, value in _panel_loc().items():
        assert not re.search(r"\d", re.sub(r"\[[^\[\]]*\]", "", value)), key


def test_links_resolve():
    texts = list(_panel_loc().values()) + [HARVEST_LOC.read_text(encoding="utf-8-sig")]
    concepts = {a or b for value in texts for a, b in re.findall(r"\[(\w+)\|[eE]\]|\[Concept\('(\w+)'", value)}
    concepts |= set(re.findall(r'text = "\[(\w+)\|[eE]\]"', _panel()))
    assert {"region", "location", "location_modifier", "pp_variable_harvests", "pp_starvation", "average_harvest"} <= concepts
    assert not sorted(concepts - _concepts())
    named = {k for value in texts for k in re.findall(r"Show(?:GoodsName|PopTypeName)\('(\w+)'\)", value)}
    assert named and not sorted(named - set(_all_loc()))
    modifiers = {k for value in texts for k in re.findall(r"ShowModifier\('(\w+)'\)", value)}
    assert not sorted(k for k in modifiers if f"STATIC_MODIFIER_NAME_{k}" not in _all_loc())


def test_data_functions_exist_in_the_game():
    used = _calls(_panel()) | {fn for value in _panel_loc().values() for fn in _calls(value)}
    used |= _calls(HARVEST_LOC.read_text(encoding="utf-8-sig"))
    assert {"GetPlayer", "GetCapital", "GetProvinces", "Custom", "GetStarvingProvincesAmount", "ShowModifier"} <= used
    vanilla = set()
    for path in [*_vanilla().glob("*/gui/**/*.gui"), *_vanilla().glob("main_menu/localization/english/**/*.yml")]:
        vanilla |= _calls(path.read_text(encoding="utf-8-sig", errors="replace"))
    assert not sorted(used - vanilla)


def test_customizable_localizations_return_what_the_panel_compares_and_shows():
    returns: dict[str, set[str]] = {}
    for block, body in re.findall(r"(?m)^(\w+) = \{(.*?)^\}", CUSTOM.read_text(encoding="utf-8-sig"), flags=re.DOTALL):
        returns[block] = set(re.findall(r"localization_key = (\w+)", body))
    gates = re.findall(r"Custom\('(\w+)'\), Localize\('(\w+)'\)", _panel())
    assert {("pp_harvest_trend", "PP_HARVEST_TREND_BAD"), ("pp_harvest_trend", "PP_HARVEST_TREND_GOOD")} <= set(gates)
    assert not sorted((c, k) for c, k in gates if k not in returns.get(c, set()))
    shown = set(re.findall(r"Custom\('(\w+)'\)", _panel() + "".join(_panel_loc().values())))
    assert "pp_harvest_link" in shown and shown <= set(returns)
    # every harvest modifier has its hover link, every average year names its area, and every text exists
    keys = location_status.harvest_modifiers((MOD_ROOT / location_status.HARVEST_MODIFIERS).read_text(encoding="utf-8-sig"))
    assert len(keys) > 50
    assert {location_status.harvest_link_key(k) for k in keys} <= returns["pp_harvest_link"]
    loc = _loc(MOD_ROOT)
    for key in keys:
        assert loc[location_status.harvest_link_key(key)] == f"[ShowModifier('{key}')]"
    assert all(k in loc for k in returns["pp_harvest_link"])


def test_province_lists_read_the_players_provinces():
    """Lean years first, then good years; average years are left out (each list shows only its trend)."""
    text = _panel()
    lists = re.findall(r'datamodel = "\[GetPlayer\.GetProvinces\]"\s*ignoreinvisible = yes', text)
    assert len(lists) == 2
    assert text.index("PP_HARVEST_TREND_BAD") < text.index("PP_HARVEST_TREND_GOOD")
    assert text.count("[Province.GetCapital.Custom('pp_harvest_link')]") == 2
    assert 'visible = "[GetPlayer.IsValid]"' in text   # observers have no realm


def test_scale_runs_worst_to_best_and_links_each_harvest():
    labels = [k for k in re.findall(r'text = "PP_HARVEST_SIT_SCALE_(\w+)"', _panel()) if k != "DESC"]
    assert labels == [s.upper() for s in SEVERITIES]
    loc = _loc(MOD_ROOT)
    for sev in SEVERITIES:
        assert re.fullmatch(rf"\[Concept\('{sev}_harvest', '\w+'\)\|e\]", loc[f"PP_HARVEST_SIT_SCALE_{sev.upper()}"]), sev
    frames = re.findall(r'texture = "gfx/interface/icons/(pp_harvest/frame_\w+|climate/brown_frame)\.dds"', _panel())
    assert frames == [f"pp_harvest/frame_{s}" if s != "average" else "climate/brown_frame" for s in SEVERITIES]


def test_grain_goods_follow_the_harvest_config():
    """The goods named as swinging the most are the most sensitive ones (variable_harvests.toml)."""
    goods = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["goods"]
    text = _loc(MOD_ROOT)["PP_HARVEST_SIT_CHANGES_DESC"]
    grain = text[text.index("swing the most"):text.index("spared")]
    assert set(re.findall(r"ShowGoodsName\('(\w+)'\)", grain)) == {g for g, c in goods.items() if c["sensitivity"] == "high"}


def test_picture_and_icon_ship_with_the_mod():
    """tools/build_harvest_situation_art.py: vanilla's situation picture size and the weather icon."""
    with Image.open(MOD_ROOT / "main_menu/gfx/interface/illustrations/situation/harvest_situation.dds") as image:
        assert image.size == (1080, 440)
    icon = MOD_ROOT / "in_game/gfx/interface/icons/situations/harvest_situation.dds"
    weather = _vanilla() / "main_menu/gfx/interface/icons/alerts_icons/weather_system.dds"
    assert icon.read_bytes() == weather.read_bytes()
