"""Water access of every land location, read from the mod's own map with the rules the game scripts use.

The engine makes a location ``is_coastal`` when it borders a sea zone (``sea_zones`` in default.map); the navigable
river channels are sea zones too (region ``pp_navigation_region``), and so are the navigable lakes. The mod's location
view and gates split that into three exclusive states:

- sea coast: borders a passable sea zone that is neither a river channel nor lake water (topography ``lakes``,
  ``high_lakes``, ``salt_pans``) - the same rule as the scripted trigger ``pp_is_sea_coast``; impassable sea
  (``ocean_wasteland``, the frozen Arctic) gives no water access at all;
- waterway: coastal, but only through river channels or navigable lakes;
- inland: not coastal.

The sea-coast set places the Sea Coast modifier (``pp_wb_coastal``), so modifier, trigger and view never disagree.
Verified in game 2026-09-27: 4,415 sea coast, 1,283 waterway, 15,195 inland among the ownable land locations.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

LAKE_TOPOGRAPHIES = ("lakes", "high_lakes", "salt_pans")
# impassable sea (frozen Arctic) does not make a location coastal; the river falls use it too
IMPASSABLE_WATER = ("ocean_wasteland",)
NAVIGATION_PREFIX = "pp_nav_"
MAP_DIR = Path("in_game/map_data")
CACHE_RELATIVE_PATH = Path("artifacts/data/worldbuilder/water_access.json")
CHUNK_ROWS = 512


def _block_tokens(text: str, name: str) -> list[str]:
    match = re.search(rf"^{name}\s*=\s*\{{(.*?)^\}}", text, flags=re.M | re.S)
    if not match:
        raise ValueError(f"default.map: no {name} block")
    body = "\n".join(line.split("#", 1)[0] for line in match.group(1).splitlines())
    return body.split()


def _named_colors(dirs: list[Path]) -> dict[int, str]:
    colors: dict[int, str] = {}
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.txt")):
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*([0-9A-Fa-f]{1,6})\b", line)   # leading zeros are dropped
                if m:
                    colors[int(m.group(2), 16)] = m.group(1)
    return colors


def _topographies(templates: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in templates.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*\{.*?\btopography\s*=\s*([A-Za-z0-9_]+)", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _adjacent_pairs(png: Path) -> set[tuple[int, int]]:
    """Unordered colour pairs of 4-neighbour pixels (the map does not wrap)."""
    import numpy as np
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    pairs: set[tuple[int, int]] = set()
    with Image.open(png) as image:
        image = image.convert("RGB")
        width, height = image.size
        previous_last_row = None
        for y0 in range(0, height, CHUNK_ROWS):
            chunk = np.asarray(image.crop((0, y0, width, min(height, y0 + CHUNK_ROWS))), dtype=np.int64)
            packed = (chunk[:, :, 0] << 16) | (chunk[:, :, 1] << 8) | chunk[:, :, 2]
            if previous_last_row is not None:
                packed_with_seam = np.vstack([previous_last_row[None, :], packed])
            else:
                packed_with_seam = packed
            for a, b in ((packed[:, :-1], packed[:, 1:]), (packed_with_seam[:-1, :], packed_with_seam[1:, :])):
                differ = a != b
                lo = np.minimum(a[differ], b[differ])
                hi = np.maximum(a[differ], b[differ])
                for code in np.unique((lo << 24) | hi).tolist():
                    pairs.add((code >> 24, code & 0xFFFFFF))
            previous_last_row = packed[-1, :]
    return pairs


def _inputs(mod_root: Path, vanilla_root: Path) -> dict[str, Path]:
    game = Path(vanilla_root) / "game"
    return {
        "png": mod_root / MAP_DIR / "locations.png",
        "default_map": mod_root / MAP_DIR / "default.map",
        "templates": mod_root / MAP_DIR / "location_templates.txt",
        "mod_names": mod_root / MAP_DIR / "named_locations",
        "vanilla_names": game / MAP_DIR / "named_locations",
    }


def _fingerprint(paths: dict[str, Path]) -> str:
    h = hashlib.sha256()
    for key in sorted(paths):
        p = paths[key]
        files = sorted(p.glob("*.txt")) if p.is_dir() else [p]
        for f in files:
            h.update(f.name.encode())
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def compute(mod_root: Path, vanilla_root: Path) -> dict[str, str]:
    """Land location tag -> 'sea_coast' | 'waterway' for every location that borders a sea zone (inland ones absent)."""
    paths = _inputs(Path(mod_root), Path(vanilla_root))
    default_map = paths["default_map"].read_text(encoding="utf-8-sig", errors="replace")
    sea_zones = set(_block_tokens(default_map, "sea_zones"))
    lakes = set(_block_tokens(default_map, "lakes"))
    topography = _topographies(paths["templates"])
    colors = _named_colors([paths["vanilla_names"], paths["mod_names"]])
    passable = {t for t in sea_zones if topography.get(t) not in IMPASSABLE_WATER}
    sea = {t for t in passable if not t.startswith(NAVIGATION_PREFIX) and topography.get(t) not in LAKE_TOPOGRAPHIES}
    water = sea_zones | lakes
    state: dict[str, str] = {}
    for a, b in _adjacent_pairs(paths["png"]):
        ta, tb = colors.get(a), colors.get(b)
        if not ta or not tb:
            continue
        for land, other in ((ta, tb), (tb, ta)):
            if land in water or other not in passable:
                continue
            if other in sea:
                state[land] = "sea_coast"
            else:
                state.setdefault(land, "waterway")
    return state


def load(repo: Path, mod_root: Path, vanilla_root: Path) -> dict[str, str]:
    """``compute`` with a cache keyed on the map files (the pixel scan takes about half a minute)."""
    paths = _inputs(Path(mod_root), Path(vanilla_root))
    key = _fingerprint(paths)
    cache = Path(repo) / CACHE_RELATIVE_PATH
    if cache.is_file():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("fingerprint") == key:
            return dict(data["state"])
    state = compute(mod_root, vanilla_root)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fingerprint": key, "state": dict(sorted(state.items()))}, indent=0) + "\n", encoding="utf-8")
    return state


def sea_coast(state: dict[str, str]) -> set[str]:
    return {tag for tag, value in state.items() if value == "sea_coast"}


# --- location view: Water Access and Port chips ------------------------------------------------------------------

_LOC = "LocationView.GetLocation"
_FRAME = f'background = {{ texture = "[GetClimateFrame({_LOC}.GetClimate)]" }}'
SEA_ICON = "gfx/interface/icons/location_icons/coastal.dds"
WATERWAY_ICON = "gfx/interface/topography/pp_river_channel.dds"
INLAND_ICON = "gfx/interface/icons/location_icons/inland.dds"
PORT_ICON = "gfx/interface/icons/modifier_types/natural_harbor_suitability.dds"
IS_SEA = f"EqualTo_string({_LOC}.Custom('pp_water_access'), Localize('PP_WATER_SEA_COAST'))"
IS_WATERWAY = f"EqualTo_string({_LOC}.Custom('pp_water_access'), Localize('PP_WATER_WATERWAY'))"
IS_INLAND = f"EqualTo_string({_LOC}.Custom('pp_water_access'), Localize('PP_WATER_INLAND'))"
ALSO_RIVER = f"EqualTo_string({_LOC}.Custom('pp_water_access_river_note'), Localize('PP_WATER_ALSO_RIVER'))"
CUSTOM_LOC_PATH = Path("in_game/common/customizable_localization/pp_water_access.txt")
SCRIPT_VALUES_PATH = Path("in_game/common/script_values/pp_water_access.txt")   # retired: the Port chip reads the modifier
LOCALIZATION_PATH = Path("main_menu/localization/english/pp_water_access_l_english.yml")
_COAST_CHIP = re.compile(r'widget = \{\s*name = "ha1300_native_coast".*?(?=widget = \{\s*name = "ha1300_native_river")', re.S)
# vanilla's natural harbour pie next to the river and sound toll icons; the Port chip carries its tooltip now
_HARBOR_PIE = re.compile(r'# NATURAL HABOUR\s*widget = \{.*?(?=# (?:RIVER MODIFIER|SOUND TOLL))', re.S)
_SOIL_CHIP = 'widget = { name = "ha1300_native_soil"'
# vanilla's natural harbour ring around the Port icon on the coast: green = harbour suitability, red = the rest
_SUITABILITY = f"FixedPointToFloat({_LOC}.GetModifierValueFixed('harbor_suitability'))"
_PIE = "gfx/interface/pie_charts/pie_chart_alpha_80.dds"
_HARBOR_RING = (
    f'piechart = {{ name = "pp_port_harbor_ring" visible = "[{_LOC}.IsCoastal]" size = {{ 100% 100% }} parentanchor = center '
    f"using = bg_circle using = piechart_angles using = bg_circle_piechart "
    f'icon = {{ texture = "{_PIE}" size = {{ 97% 97% }} parentanchor = center color = {{ 0 0 0 1 }} }} '
    f'pieslice_no_highlight = {{ texture = "{_PIE}" value = "[{_SUITABILITY}]" color = {{ 0.3 0.8 0.3 1 }} alpha = 0.8 }} '
    f'pieslice_no_highlight = {{ texture = "{_PIE}" value = "[Max_float(Subtract_float(\'(float)1.0\', {_SUITABILITY}), \'(float)0\')]" '
    f"color = {{ 0.8 0.3 0.3 1 }} alpha = 0.8 }} }}"
)


def _icons(size: str, extra: str = "") -> str:
    return " ".join(f'icon = {{ {size} texture = "{tex}" visible = "[{gate}]" {extra}}}'
                    for tex, gate in ((SEA_ICON, IS_SEA), (WATERWAY_ICON, IS_WATERWAY), (INLAND_ICON, IS_INLAND)))


def water_access_chip() -> str:
    return f'''widget = {{
        name = "pp_water_access"
        size = {{ 30 30 }}
        datacontext = "[{_LOC}]"
        tooltipwidget = {{
        ContextualTooltipType = {{
            blockoverride "title_text" {{ text = "[{_LOC}.Custom('pp_water_access')]" }}
            blockoverride "concept_link" {{ visible = yes text = "[coastal|E]" }}
            blockoverride "title_icon" {{
                widget = {{ using = tooltip_title_icon_size {_FRAME} {_icons("using = tooltip_title_icon_size")} }}
            }}
            blockoverride "tooltip_content" {{
                TooltipTextBlock = {{ blockoverride "text" {{ text = "[{_LOC}.Custom('pp_water_access_help')]" }} }}
                TooltipTextBlock = {{ visible = "[{ALSO_RIVER}]" blockoverride "text" {{ text = "PP_WATER_ALSO_RIVER" }} }}
                TooltipStringPairList = {{ visible = "[{_LOC}.IsCoastal]" textcontext = "[ShowModifierEffect('coastal')]" }}
                pp_attribute_view_coast = {{}}
            }}
        }}
    }}
        {_FRAME}
        {_icons("size = { 30 30 }")}
    }}
widget = {{
        name = "pp_port"
        size = {{ 30 30 }}
        datacontext = "[{_LOC}]"
        tooltipwidget = {{
        ContextualTooltipType = {{
            blockoverride "title_text" {{ text = "[SelectLocalization({_LOC}.HasPort, 'PP_PORT', 'PP_NO_PORT')]" }}
            blockoverride "concept_link" {{ visible = yes text = "[port|E]" }}
            blockoverride "title_icon" {{
                widget = {{ using = tooltip_title_icon_size {_FRAME} icon = {{ using = tooltip_title_icon_size texture = "{PORT_ICON}" }} }}
            }}
            blockoverride "title_button" {{
                mapmode_tooltip_button = {{ datacontext = "[GetMapMode('natural_harbor_suitability')]" }}
            }}
            blockoverride "tooltip_content" {{
                TooltipTextBlock = {{ blockoverride "text" {{ text = "[SelectLocalization({_LOC}.HasPort, 'PP_PORT_HELP', 'PP_NO_PORT_HELP')]" }} }}
                TooltipTextBlock = {{ visible = "[{_LOC}.IsCoastal]" blockoverride "text" {{ text = "PP_PORT_HARBOR" }} }}
                TooltipStringPairList = {{
                    visible = "[{_LOC}.IsCoastal]"
                    blockoverride "block_title" {{ text = "HARBOR_SUITABILITY_DESC" }}
                    textcontext = "[Location.GetDescriptionFor('harbor_suitability')]"
                }}
                TooltipStringPairList = {{
                    visible = "[{_LOC}.IsCoastal]"
                    blockoverride "block_title" {{ text = "HARBOR_SUITABILITY_IMPACT" }}
                    textcontext = "[Location.GetHarborCapacityImpactInfo]"
                }}
            }}
        }}
    }}
        {_FRAME}
        {_HARBOR_RING}
        icon = {{ size = {{ 20 20 }} parentanchor = center texture = "{PORT_ICON}" visible = "[And({_LOC}.IsCoastal, {_LOC}.HasPort)]" }}
        icon = {{ size = {{ 20 20 }} parentanchor = center texture = "{PORT_ICON}" alpha = 0.4 visible = "[And({_LOC}.IsCoastal, Not({_LOC}.HasPort))]" }}
        icon = {{ size = {{ 30 30 }} texture = "{PORT_ICON}" alpha = 0.3 visible = "[Not({_LOC}.IsCoastal)]" }}
    }}
'''


_TOPOGRAPHY_MODE = "topography = {\n\tcolor_mode = topography\n"


def topography_map_mode_without_rivers(text: str) -> str:
    """The Topography map mode without the river surfaces.

    The navigable river channels are locations painted along the vanilla river lines, so the engine's river surface is
    drawn over them and hides their map colour (Navigable River, Shallows, Falls). Without the river surfaces the
    channels show their own colours; the other rivers stay visible in every other map mode and on the River chip."""
    text = text.replace("\r\n", "\n")
    if text.count(_TOPOGRAPHY_MODE) != 1:
        raise ValueError("map_modes.txt: expected 1 Topography map mode block")
    return text.replace(_TOPOGRAPHY_MODE, _TOPOGRAPHY_MODE + "\tenable_rivers = no\n")


def water_access_chips(text: str) -> str:
    """Replace the World Builder's coast chip (engine is_coastal: Coastal / Inland) by the Water Access chip (Inland /
    Waterway / Sea Coast) and a Port chip; both sit after the river and lake chips. Vanilla's natural harbour pie goes:
    the Port chip's tooltip carries the harbour suitability, harbour capacity and its effects."""
    found = len(_COAST_CHIP.findall(text))
    if found != 1:
        raise ValueError(f"location_window.gui: expected 1 World Builder coast chip, found {found}")
    if text.count(_SOIL_CHIP) != 1:
        raise ValueError("location_window.gui: expected 1 soil chip anchor for the water access chips")
    pies = len(_HARBOR_PIE.findall(text))
    if pies != 1:
        raise ValueError(f"location_window.gui: expected 1 vanilla natural harbour widget, found {pies}")
    text = _HARBOR_PIE.sub("", _COAST_CHIP.sub("", text))
    return text.replace(_SOIL_CHIP, water_access_chip() + _SOIL_CHIP)


CUSTOM_LOCALIZATION = """﻿# Generated by ppc worldbuilder (coast.py); do not edit by hand.
pp_water_access = {
\ttype = location
\ttext = { localization_key = PP_WATER_SEA_COAST trigger = { pp_is_sea_coast = yes } }
\ttext = { localization_key = PP_WATER_WATERWAY trigger = { is_coastal = yes } }
\ttext = { localization_key = PP_WATER_INLAND fallback = yes }
}
pp_water_access_help = {
\ttype = location
\ttext = { localization_key = PP_WATER_SEA_COAST_HELP trigger = { pp_is_sea_coast = yes } }
\ttext = { localization_key = PP_WATER_WATERWAY_HELP trigger = { is_coastal = yes } }
\ttext = { localization_key = PP_WATER_INLAND_HELP fallback = yes }
}
pp_water_access_river_note = {
\ttype = location
\ttext = { localization_key = PP_WATER_ALSO_RIVER trigger = { pp_is_sea_coast = yes any_neighbor_location = { region = region:pp_navigation_region } } }
\ttext = { localization_key = PP_WATER_NO_NOTE fallback = yes }
}
"""

LOCALIZATION = f"""﻿l_english:
 PP_WATER_SEA_COAST: "Sea Coast"
 PP_WATER_WATERWAY: "Waterway"
 PP_WATER_INLAND: "Inland"
 PP_WATER_SEA_COAST_HELP: "This location borders the open sea. It gets the coastal effects and the sea-coast effects listed below."
 PP_WATER_WATERWAY_HELP: "This location borders a navigable river or lake, but not the sea. Boats reach it, so it gets the coastal effects listed below, but none of the sea coast's."
 PP_WATER_INLAND_HELP: "This location has no navigable water. Rivers flowing through it and lakes are shown on their own chips."
 PP_WATER_ALSO_RIVER: "It also borders a navigable river."
 PP_WATER_NO_NOTE: ""
 PP_PORT: "Port"
 PP_NO_PORT: "No Port"
 PP_PORT_HELP: "Ships can dock, be built and be repaired here."
 PP_NO_PORT_HELP: "No ship can dock here, even where the location borders navigable water."
 PP_PORT_HARBOR: "[natural_harbor_suitability_with_icon|e]: [Location.GetModifierValueFixed('natural_harbor_suitability')|0%]"
"""


def write_runtime(mod_root: Path) -> dict[str, object]:
    for rel, text in ((CUSTOM_LOC_PATH, CUSTOM_LOCALIZATION), (LOCALIZATION_PATH, LOCALIZATION)):
        path = Path(mod_root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    (Path(mod_root) / SCRIPT_VALUES_PATH).unlink(missing_ok=True)
    return {"files": [str(p) for p in (CUSTOM_LOC_PATH, LOCALIZATION_PATH)]}


def cached(repo: Path) -> dict[str, str] | None:
    """The last computed state without re-checking the map (for reports that run after ``ppc worldbuilder apply``)."""
    cache = Path(repo) / CACHE_RELATIVE_PATH
    return dict(json.loads(cache.read_text(encoding="utf-8"))["state"]) if cache.is_file() else None


def with_sea_coast(contract, state: dict[str, str] | None):
    """The contract with its ``is_coastal`` attribute replaced by the map's sea coast.

    The World Builder's flag comes from its own inventory (vanilla coastline, lagoons counted as sea); the game's sea
    coast is what the Sea Coast modifier, the gates and the location view must follow. They differ on a handful of
    locations; every consumer of the contract then sees the game's set."""
    import dataclasses

    import polars as pl

    if state is None or "is_coastal" not in contract.location_attributes.columns:
        return contract
    sea = sorted(sea_coast(state))
    attrs = contract.location_attributes.with_columns(pl.col("location_tag").is_in(sea).cast(pl.String).alias("is_coastal"))
    return dataclasses.replace(contract, location_attributes=attrs)
