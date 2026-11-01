"""HTML preview of the location view's Arable Land panel (arable_land_bar.py), for fast design iterations.

Reads the panel from the built ``location_window.gui`` (so the preview follows the generator), draws it with the game's
own bar textures (DDS -> PNG) and fills it with one location of a save:

- buildings and their levels from the save (eu5save), the land per level from ``arable_land_bar.model``;
- the location's land = the World Builder's attribute rows (handover ``location_targets.csv``) + development + the rank's
  capacity; townsfolk = population - unemployed peasants (each brings their own capacity);
- no capacity multiplier unless given (--multiplier): the % sources are gone since 2026-10-27. Whole levels, not the
  engine's input-scaled counters. So the numbers are close, not exact: the game's own figure is printed next to it
  when given (--game-capacity).

The layout is an approximation of the engine's (flex boxes, a serif font): good for judging a design, not pixels.

    uv run python tools/land_bar_preview.py [--location constantinople] [--save NAME] [--game-capacity 207]
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import re
from pathlib import Path

from eu5gameparser.clausewitz.parser import parse_text
from eu5gameparser.clausewitz.syntax import CList
from PIL import Image

from prosper_or_perish_constructor import arable_land_bar as alb

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
GAME = Path.home() / ".cache/eu5-vanilla/game"
HANDOVER = ROOT.parent / "EU5WorldBuilder/artifacts/handover/latest/location_targets.csv"
SAVES = Path("/mnt/c/Users/Anwender/Documents/Paradox Interactive/Europa Universalis V/save games")
OUT = ROOT / "artifacts/land_bar_preview/index.html"
WIDTH = 720


# --- values ------------------------------------------------------------------------------------------------------

def _rank_capacity() -> dict[str, float]:
    """Flat capacity of each location rank's rank_modifier (vanilla plus the mod's injects)."""
    from eu5gameparser.clausewitz.parser import parse_file

    ranks: dict[str, float] = {}
    for path in sorted((GAME / "in_game/common/location_ranks").glob("*.txt")) + sorted((MOD / "in_game/common/location_ranks").glob("*.txt")):
        for entry in parse_file(path).entries:
            if not isinstance(entry.value, CList):
                continue
            kind, key = alb._bare(str(entry.key))
            if kind != "inject":
                ranks[key] = 0.0
            for block in entry.value.values("rank_modifier"):
                if isinstance(block, CList):
                    for item in block.entries:
                        if str(item.key) == alb.CAPACITY and isinstance(item.value, (int, float)):
                            ranks[key] = ranks.get(key, 0.0) + float(item.value)
    return ranks


def save_values(location: str, save: str | None, multiplier: float | None = None) -> dict[str, float]:
    from eu5gameparser.savegame import quick

    import polars as pl

    t = quick.load(save, load_order=ROOT / "constructor.load_order.toml")
    print(f"save: {t.save.name}")
    loc = t.locations.filter(pl.col("slug") == location).row(0, named=True)
    levels: dict[str, float] = {}
    for row in t.buildings.filter(pl.col("location_slug") == location).iter_rows(named=True):
        levels[row["building_type"]] = levels.get(row["building_type"], 0.0) + (row["level"] or 0.0)
    m = alb.model(MOD, GAME)
    improvements = sum(levels.get(b.key, 0) * b.land for b in m.improvements)
    farms = sum(levels.get(b.key, 0) * -b.land for b in m.farms + m.reserved)
    with HANDOVER.open(encoding="utf-8") as handle:
        target = next(r for r in csv.DictReader(handle) if r["location_tag"] == location)
    natural = (float(target["attribute_flat_people"]) / 1000 + (loc["development"] or 0.0)
               + _rank_capacity().get(loc["rank"] or "", 0.0))
    mult = 1.0 if multiplier is None else multiplier       # the capacity % sources are gone (2026-10-27)
    population = loc["total_population"] or 0.0
    subsistence = loc["unemployed_peasants"] or 0.0
    v = {"population": population, "subsistence": subsistence, "townsfolk": max(0.0, population - subsistence),
         "natural": natural * mult, "improvements": improvements * mult, "farms": farms * mult}
    v["townsfolk_room"] = v["townsfolk"] * mult
    v["left"] = v["natural"] + v["improvements"] - v["farms"]
    v["capacity"] = v["townsfolk_room"] + max(0.0, v["left"])
    v["percent"] = population / v["capacity"] * 100 if v["capacity"] else 0.0
    land = v["capacity"] + v["farms"]
    scale = max(land, population, 0.001)
    v.update(f_population=population / scale, f_within=min(population, v["capacity"]) / scale,
             f_townsfolk=v["townsfolk"] / scale, f_townsfolk_room=v["townsfolk_room"] / scale,
             f_capacity=v["capacity"] / scale, f_land=land / scale)
    v["_population"] = population
    return {f"pp_land_bar_{k}" if not k.startswith("_") else k: x for k, x in v.items()}


# --- textures and text -------------------------------------------------------------------------------------------

_TEXTURES: dict[str, str] = {}


def texture(path: str) -> str:
    if path not in _TEXTURES:
        hits = sorted(GAME.glob(f"*/{path}")) + sorted(MOD.glob(f"*/{path}"))
        buffer = io.BytesIO()
        Image.open(hits[-1]).save(buffer, format="PNG")
        _TEXTURES[path] = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    return _TEXTURES[path]


def localization() -> dict[str, str]:
    texts: dict[str, str] = {}
    for root in (GAME, MOD):
        for path in sorted((root / "main_menu/localization").rglob("*_l_english.yml")):
            for key, text in re.findall(r'^\s*([\w.]+):\d*\s*"(.*)"\s*$', path.read_text(encoding="utf-8-sig"), re.M):
                texts[key] = text
    return texts


_DATA = re.compile(r"\[([^\[\]]+?)(?:\|([^\]]*))?\]")


def _number(expr: str, values: dict[str, float]) -> float | None:
    sv = re.search(r"ScriptValue\('(\w+)'\)", expr)
    if sv:
        return values.get(sv.group(1))
    if "GetTotalPopulation" in expr:
        return values.get("_population")
    if "GetPopulationCapacity" in expr:
        return values.get("_game_capacity", values.get("pp_land_bar_capacity"))
    return None


def render_text(text: str, values: dict[str, float], loc: dict[str, str]) -> str:
    def data(match: re.Match[str]) -> str:
        expr, fmt = match.group(1), match.group(2) or ""
        if fmt.upper() == "E":
            name = loc.get(f"game_concept_{expr}", expr.replace("_", " ").title())
            return f'<span class="link">{html.escape(name)}</span>'
        number = _number(expr, values)
        if number is None:
            return f'<span class="missing">[{html.escape(expr)}]</span>'
        if number != number:   # nan: not computed offline
            return "?"
        digits = int(re.sub(r"\D", "", fmt) or 0)
        signed = "+" in fmt
        return f"{number:+.{digits}f}" if signed else f"{number:.{digits}f}"

    out = _DATA.sub(data, html.escape(text, quote=False).replace("\\n", "<br>"))
    out = re.sub(r"#R\s?(.*?)#!", r'<span class="red">\1</span>', out)
    return out


# --- GUI interpreter ---------------------------------------------------------------------------------------------

def _scalar(block: CList, key: str, default=None):
    value = block.first(key)
    return default if isinstance(value, CList) or value is None else value


def _size(block: CList) -> tuple[object, object]:
    value = block.first("size")
    if isinstance(value, CList) and len(value.items) == 2:
        return value.items[0], value.items[1]
    return None, None


def _css_len(value) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text.endswith("%"):
        return text
    if float(text) < 0:
        return None
    return f"{float(text):g}px"


def _value(raw, values: dict[str, float]) -> float:
    text = str(raw)
    try:
        return float(text)
    except ValueError:
        number = _number(text, values)
        return min(max(number or 0.0, 0.0), 1.0)


def progressbar(block: CList, values: dict[str, float]) -> str:
    fill = _value(_scalar(block, "value", 0), values)
    alpha = float(_scalar(block, "alpha", 1))
    invert = _scalar(block, "invertprogress") is True
    cornered = _scalar(block, "spriteType") == "Corneredstretched"
    border = 6 if cornered else 0
    layers = []
    empty = str(_scalar(block, "noprogresstexture", ""))
    if empty and "transparent" not in empty:
        layers.append(f'<div class="bar" style="left:0;width:100%;{_skin(empty, border)}"></div>')
    side = "right" if invert else "left"
    layers.append(f'<div class="bar" style="{side}:0;width:{fill * 100:.2f}%;opacity:{alpha};'
                  f'{_skin(str(_scalar(block, "progresstexture")), border)}"></div>')
    return "".join(layers)


def _skin(path: str, border: int) -> str:
    url = texture(path)
    if border:
        return (f"border-style:solid;border-width:0 {border}px;border-image:url({url}) 0 12 fill / 0 {border}px stretch;"
                "box-sizing:border-box;")
    return f"background:url({url});background-size:100% 100%;"


def element(key: str, block: CList, values: dict[str, float], loc: dict[str, str], parent: str) -> str:
    if key == "expand":
        return '<div style="flex:1"></div>'
    if key == "progressbar":
        return progressbar(block, values)
    style: list[str] = []
    width, height = _size(block)
    expanding = _scalar(block, "layoutpolicy_horizontal") == "expanding"
    if expanding:
        style.append("flex:1;align-self:stretch" if parent == "hbox" else "align-self:stretch")
    if _css_len(width):
        style.append(f"width:{_css_len(width)}")
    if _css_len(height):
        style.append(f"height:{_css_len(height)}")
    if "alpha" in [str(e.key) for e in block.entries] and key != "progressbar":
        style.append(f"opacity:{_scalar(block, 'alpha')}")
    anchor = str(_scalar(block, "parentanchor", ""))
    if anchor and parent == "widget":
        style.append("position:absolute;left:0")
        style.append("bottom:0" if "bottom" in anchor else ("top:50%;transform:translateY(-50%)" if "vcenter" in anchor else "top:0"))
    elif parent == "widget":
        style.append("position:absolute;left:0;top:0")
    tooltip = _scalar(block, "tooltip")
    if key in ("text_single", "text_multi"):
        raw = _scalar(block, "raw_text")
        text = render_text(str(raw), values, loc) if raw is not None else render_text(loc.get(str(_scalar(block, "text")), str(_scalar(block, "text"))), values, loc)
        size = _scalar(block, "fontsize", 14)
        fmt = str(_scalar(block, "default_format", ""))
        cls = "title" if "yellow_titles" in fmt else ""
        style.append(f"font-size:{size}px;white-space:nowrap")
        return f'<span class="{cls}" style="{";".join(style)}">{text}</span>'
    children = "".join(element(str(e.key), e.value, values, loc, key) for e in block.entries
                       if isinstance(e.value, CList) and str(e.key) in ("vbox", "hbox", "widget", "text_single", "text_multi",
                                                                         "progressbar", "expand"))
    if key in ("vbox", "hbox"):
        style.append(f"display:flex;flex-direction:{'column' if key == 'vbox' else 'row'}")
        style.append("align-items:center" if key == "hbox" else "")
        spacing = _scalar(block, "spacing")
        if spacing:
            style.append(f"gap:{spacing}px")
        margin = block.first("margin")
        if isinstance(margin, CList) and len(margin.items) == 2:
            style.append(f"padding:{margin.items[1]}px {margin.items[0]}px")
        background = block.first("background")
        if isinstance(background, CList):
            style.append(f"background:rgba(16,28,48,{_scalar(background, 'alpha', 1)})")
    else:
        style.append("position:relative")
    tip = (f'<div class="tooltip"><div class="tiplabel">tooltip</div>{render_text(loc.get(str(tooltip), str(tooltip)), values, loc)}</div>'
           if tooltip else "")
    return f'<div style="{";".join(s for s in style if s)}">{children}</div>{tip}'


def panel(window: Path) -> CList:
    text = window.read_text(encoding="utf-8-sig")
    name = text.index('name = "pp_arable_land_bar"')
    start = text.rindex("vbox = {", 0, name)
    end = alb._block_end(text, text.index("{", start))
    return parse_text(text[start:end + 1]).entries[0].value


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Arable Land bar preview</title><style>
body{{background:#1b1712;color:#e9e1cf;font-family:Georgia,'Times New Roman',serif;margin:24px}}
.frame{{width:{width}px;border:2px solid #6b5636;box-shadow:0 0 0 4px #2a2118}}
.bar{{position:absolute;top:0;bottom:0}}
.title{{color:#e8c65a}} .link{{color:#78b4e0}} .red{{color:#e05a4a}} .missing{{color:#f0f;}}
.tooltip{{margin:10px 0 0;width:{width}px;max-width:{width}px;background:#15110c;border:1px solid #6b5636;padding:8px 12px;font-size:13px;line-height:1.5}}
.tiplabel{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.5;margin-bottom:4px}}
.note{{font-size:12px;opacity:.6;margin-top:14px;width:{width}px}}
</style></head><body><div class="frame">{panel}</div><div class="note">{note}</div></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--location", default="constantinople")
    parser.add_argument("--save", default=None)
    parser.add_argument("--game-capacity", type=float, default=None, help="the game's Arable Land (K) to compare with")
    parser.add_argument("--multiplier", type=float, default=None,
                        help="the location's capacity multiplier when known from the game (e.g. 1.51 for Constantinople "
                             "1832: improvements 188.7K / 125 units); else estimated from the save")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    values = save_values(args.location, args.save, args.multiplier)
    if args.game_capacity is not None:
        values["_game_capacity"] = args.game_capacity
    loc = localization()
    block = panel(MOD / "in_game/gui/location_window.gui")
    body = element("vbox", block, values, loc, "root")
    note = (f"{args.location}: preview capacity {values['pp_land_bar_capacity']:.1f}K"
            + (f", game {args.game_capacity:.1f}K" if args.game_capacity is not None else "")
            + ". Layout approximated; textures are the game's.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(PAGE.format(width=WIDTH, panel=body, note=html.escape(note)), encoding="utf-8")
    print(note)
    print(args.out)


if __name__ == "__main__":
    main()
