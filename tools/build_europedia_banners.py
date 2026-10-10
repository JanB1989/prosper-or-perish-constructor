"""Build the Europedia card banners (2x resolution DDS; the card shows them at 1450 x 250, pp_europedia_style.gui).

Vanilla has no topic picture wider than 1080 px, which looks soft stretched over a 1450 px card. Each banner is a wide
landscape from the location view's panorama layers instead (2654 px, sharp), graded to its topic:

- harvest: fat year, lean year: one farmland turning from a sunlit golden harvest on the left into a lean year under
  a rainstorm on the right (Variable Harvests);
- arable_land: forest under mountains giving way to cleared fields and longhouses on the right (Arable Land);
- food: a Deccan town with its domed stores among its fields on a plateau (Food);
- food_production: rice paddies and a temple town in wet lowland (Food Production);
- labor: from the fields to the mills: villages among their fields on the left, a mill town smoking at dusk on the
  right (Labor);
- logistics: the river to market: barges at a wharf, hamlets along the bank, then a walled city with its great mosque
  and river port, on a hot afternoon (Logistics (Market Access));
- population_growth: an Ashanti town spreading into its fields and farm compounds before the rainforest, in a golden
  morning haze (Population Growth);
- trade_goods: an East Asian harbour city on a bay under mountains, junks at its quays (New Trade Goods);
- food_consumption: a crowded Aztec city round its great temple in a dry highland basin under twin volcanoes (Food
  Consumption);
- rural_capacities: a fishing harbour and a net shed on a northern firth below conifer forest and heath, in a cool
  light (Rural Capacities).

Every card gets its own landscape (Jan, 2026-10-10): a culture, climate and scene no other banner uses.

Rerun after a game update:

    uv run python tools/build_europedia_banners.py                   # write every banner into the mod
    uv run python tools/build_europedia_banners.py --preview DIR     # also 1x PNGs to look at
"""

from __future__ import annotations

import argparse
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
BANNERS_DIR = "gfx/interface/illustrations/pp_europedia"   # under the mod's main_menu
W, H = 2900, 500
INTERFACE = "game/main_menu/gfx/interface"
LOCATION = "illustrations/location/"
PANO_SCALE = 1.76      # x the banner height: the middle of the panorama, horizon about a quarter down


@dataclass(frozen=True)
class Layer:
    path: str                                  # under illustrations/location/, offset in the name: _d<x>x<y>
    fade_left: tuple[int, int] | None = None   # fade the layer out toward the left between these x (2654 canvas)
    dx: int = 0                                # move the layer sideways (2654 canvas), e.g. a dock into the crop
    dy: int = 0                                # move it down (a sprite onto its ground or water)
    window: tuple[int, int, int, int] | None = None   # keep it only between these x: fade in a..b, out c..d
    scale: float = 1.0                         # grow a sprite about its foot (a mill brought into the foreground)
    mirror: bool = False                       # flip it, so a settlement strip does not repeat its neighbour
    alpha: float = 1.0                         # opacity (e.g. a thin haze)


def _late_summer(im: Image.Image) -> Image.Image:
    """Fields toward ripe straw below the horizon, a warm cast over all; the sky keeps its blue."""
    lum = im.convert("L")
    straw = Image.merge("RGB", (lum.point(lambda v: min(255, int(v * 1.32 + 18))),
                                lum.point(lambda v: min(255, int(v * 1.08 + 8))),
                                lum.point(lambda v: int(v * 0.55))))
    ground = Image.linear_gradient("L").resize((W, H)).point(lambda v: max(0, min(255, (v - 40) * 3)))
    out = Image.composite(Image.blend(im, straw, 0.62), im, ground)
    out = Image.blend(out, ImageChops.multiply(out, Image.new("RGB", (W, H), (255, 214, 150))), 0.35)
    return ImageEnhance.Contrast(out).enhance(1.05)


def _natural(im: Image.Image) -> Image.Image:
    """The panorama's own colours, a touch warmer and fuller."""
    warm = Image.blend(im, ImageChops.multiply(im, Image.new("RGB", im.size, (255, 236, 200))), 0.12)
    return ImageEnhance.Contrast(ImageEnhance.Color(warm).enhance(1.05)).enhance(1.04)


def _harmattan_morning(im: Image.Image) -> Image.Image:
    """Lush greens under a soft golden morning haze, the distance paler (population_growth)."""
    gold = Image.blend(im, ImageChops.multiply(im, Image.new("RGB", im.size, (255, 226, 170))), 0.30)
    haze = Image.new("RGB", im.size, (246, 228, 196))
    depth = Image.linear_gradient("L").resize(im.size).point(lambda v: max(0, min(255, int((150 - v) * 1.1))))
    out = Image.composite(Image.blend(gold, haze, 0.22), gold, depth)
    return ImageEnhance.Contrast(ImageEnhance.Color(out).enhance(1.12)).enhance(1.05)


def _northern(im: Image.Image) -> Image.Image:
    """A cool northern light: a blue-grey cast, a touch less colour, a little more contrast (rural_capacities)."""
    cool = Image.blend(im, ImageChops.multiply(im, Image.new("RGB", im.size, (200, 222, 255))), 0.22)
    return ImageEnhance.Contrast(ImageEnhance.Color(cool).enhance(0.92)).enhance(1.06)


def _smooth(a: float, b: float, n: int) -> list[float]:
    """n values: 0 before the fraction a, 1 after b, a smoothstep between."""
    out = []
    for i in range(n):
        t = max(0.0, min(1.0, (i / n - a) / (b - a)))
        out.append(t * t * (3 - 2 * t))
    return out


def _mask(values: list[float], size: tuple[int, int], vertical: bool = False) -> Image.Image:
    """An L mask from 0..1 values across the width (or down the height)."""
    line = Image.new("L", (len(values), 1))
    line.putdata([round(255 * max(0.0, min(1.0, v))) for v in values])
    return (line.transpose(Image.ROTATE_270) if vertical else line).resize(size)


def _gradient(stops: list[tuple[float, tuple[int, int, int]]], size: tuple[int, int]) -> Image.Image:
    """A top-to-bottom colour gradient through (fraction, colour) stops."""
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        f = y / (h - 1)
        (f0, c0), (f1, c1) = next((s, e) for s, e in zip(stops, stops[1:]) if s[0] <= f <= e[0])
        t = (f - f0) / max(1e-6, f1 - f0)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(c0, c1)))
    return column.resize(size)


def _glow(size: tuple[int, int], centre: tuple[float, float], radius: tuple[float, float], colour, strength: float) -> Image.Image:
    """A soft light (to screen over the picture): colour fading out from centre over radius (fractions of size)."""
    w, h = size
    # radial_gradient is 0 at the centre and reaches about 180 at the square's edges: fade to 0 before them
    falloff = Image.radial_gradient("L").point(lambda v: round(255 * max(0.0, 1 - v / 176) ** 2))
    spot = falloff.resize((round(2 * radius[0] * w), round(2 * radius[1] * h)))
    mask = Image.new("L", size, 0)
    mask.paste(spot, (round(centre[0] * w - radius[0] * w), round(centre[1] * h - radius[1] * h)))
    mask = mask.point(lambda v: round(v * strength))
    return Image.composite(Image.new("RGB", size, colour), Image.new("RGB", size, (0, 0, 0)), mask)


def _rain(size: tuple[int, int], weight: Image.Image, count: int, seed: int = 7) -> Image.Image:
    """Slanting rain streaks (RGBA), thick where weight (an L mask) is high."""
    w, h = size
    rng = random.Random(seed)
    rain = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(rain)
    for _ in range(count):
        x, y, length = rng.uniform(0, w * 1.1), rng.uniform(-h * 0.2, h), rng.uniform(h * 0.06, h * 0.16)
        draw.line((x, y, x - length * 0.28, y + length), fill=(214, 220, 230, rng.randint(40, 95)), width=rng.choice((1, 1, 2)))
    rain = rain.filter(ImageFilter.GaussianBlur(0.9))
    rain.putalpha(ImageChops.multiply(rain.getchannel("A"), weight))
    return rain


def _fat_and_lean(im: Image.Image) -> Image.Image:
    """Variable Harvests: one landscape from a golden year on the left into a lean year under a storm on the right."""
    size = im.size
    fat = ImageChops.screen(_late_summer(im), _glow(size, (0.10, 0.02), (0.45, 0.9), (255, 214, 140), 0.55))
    ashen = ImageChops.multiply(ImageEnhance.Color(im).enhance(0.22), Image.new("RGB", size, (182, 168, 142)))
    sky = ImageEnhance.Brightness(ImageChops.multiply(ImageEnhance.Color(im).enhance(0.3), Image.new("RGB", size, (104, 114, 138)))).enhance(0.62)
    lean = Image.composite(sky, ashen, _mask([1 - v for v in _smooth(0.22, 0.38, size[1])], size, vertical=True))
    lean = ImageEnhance.Contrast(ImageEnhance.Brightness(lean).enhance(0.86)).enhance(1.18)
    storm = _mask(_smooth(0.40, 0.78, size[0]), size)
    out = Image.composite(lean, fat, storm).convert("RGBA")
    out.alpha_composite(_rain(size, storm.point(lambda v: round(v * 0.85)), 2600))
    return out.convert("RGB")


def _mill_dusk(im: Image.Image) -> Image.Image:
    """Labor: evening over a working town, the sky burning low behind the mills, the land in warm shadow."""
    size = im.size
    light = _gradient([(0.0, (150, 140, 186)), (0.20, (236, 180, 150)), (0.34, (255, 196, 138)),
                       (0.42, (226, 186, 150)), (1.0, (196, 160, 132))], size)
    out = ImageChops.multiply(ImageEnhance.Color(im).enhance(0.9), light)
    out = ImageChops.screen(out, _glow(size, (0.78, 0.30), (0.42, 0.34), (255, 140, 60), 0.45))
    out = ImageChops.screen(out, _glow(size, (0.25, 0.28), (0.35, 0.22), (240, 150, 110), 0.25))
    return ImageEnhance.Contrast(ImageEnhance.Brightness(out).enhance(1.12)).enhance(1.10)


def _caravan_afternoon(im: Image.Image) -> Image.Image:
    """Logistics: a hot, bright afternoon, dust hanging over the far side of the river, long warm light."""
    size = im.size
    warm = Image.blend(im, ImageChops.multiply(im, Image.new("RGB", size, (255, 222, 176))), 0.35)
    dust = _mask([1 - v for v in _smooth(0.18, 0.40, size[1])], size, vertical=True).point(lambda v: round(v * 0.45))
    out = Image.composite(Image.new("RGB", size, (236, 206, 160)), warm, dust)
    out = ImageChops.screen(out, _glow(size, (0.92, 0.10), (0.40, 0.8), (255, 200, 130), 0.35))
    return ImageEnhance.Contrast(ImageEnhance.Color(out).enhance(1.08)).enhance(1.08)


@dataclass(frozen=True)
class Banner:
    layers: tuple[Layer, ...]
    grade: Callable[[Image.Image], Image.Image]
    pano_scale: float = PANO_SCALE   # smaller shows more of the panorama (a shore lies low in it)


BANNERS: dict[str, Banner] = {
    "harvest": Banner((
        Layer("sky/sky_regular_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_metadata_os2654x440_d0x15.dds"),
        Layer("ground3/continental/continental_grassland_ground3_metadata_os2654x440_d0x66.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds"),
        Layer("settlement1/north_german/rural/north_german_rural11_metadata_os2654x440_d0x92.dds"),
        Layer("fx/location_fx_metadata_os2654x440_d0x180.dds", window=(1200, 1600, 2654, 2654), alpha=0.8),
        Layer("ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds"),
    ), _fat_and_lean),
    "arable_land": Banner((
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/mountains/mountains_metadata_os2654x440_d0x0.dds"),
        Layer("ground3/continental/continental_forest_ground3_metadata_os2654x440_d0x62.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds", (1000, 1500)),
        Layer("settlement1/iroquois/rural/iroquois_rural1_metadata_os2654x440_d190x140.dds", dx=1150),
        Layer("settlement2/iroquois/rural/iroquois_rural2_metadata_os2654x440_d346x108.dds", dx=1250),
        Layer("ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds"),
    ), _natural),
    "food": Banner((
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/plateau/plateau_metadata_os2654x440_d0x62.dds"),
        Layer("ground3/subtropical/subtropical_grassland_ground3_metadata_os2654x440_d0x76.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds"),
        Layer("settlement2/deccan/town/deccan_town2_metadata_os2654x440_d0x44.dds"),
        Layer("settlement1/deccan/town/deccan_town1_metadata_os2654x440_d0x124.dds"),
        Layer("ground1/subtropical/subtropical_grassland_ground1_metadata_os2654x440_d0x288.dds"),
    ), _natural),
    "food_production": Banner((
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_metadata_os2654x440_d0x15.dds"),
        Layer("ground3/subtropical/subtropical_grassland_ground3_metadata_os2654x440_d0x76.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds"),
        Layer("settlement2/asian/rural/asian_rural2_metadata_os2654x440_d100x94.dds"),
        Layer("settlement1/asian/town/asian_town1_metadata_os2654x440_d0x86.dds"),
        Layer("water/river_wetlands/river_wetlands_metadata_os2654x440_d0x108.dds"),
        Layer("ground1/subtropical/subtropical_grassland_ground1_metadata_os2654x440_d0x288.dds"),
    ), _natural),
    "labor": Banner((   # from the fields to the mills: villages on the left, the smoking mill town on the right
        Layer("sky/sky_regular_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_metadata_os2654x440_d0x15.dds"),
        Layer("ground3/continental/continental_grassland_ground3_metadata_os2654x440_d0x66.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds", window=(0, 0, 1250, 1600)),
        Layer("settlement2/north_german/town/north_german_town2_metadata_os2654x440_d0x54.dds", window=(0, 0, 1050, 1300)),
        Layer("settlement2/north_german/city/north_german_city2_metadata_os2654x440_d0x44.dds", window=(1300, 1600, 2654, 2654)),
        Layer("factories/north_german_factory_metadata_os2654x440_d0x35.dds", dx=1440, dy=10, scale=1.15),
        Layer("factories/north_german_factory_metadata_os2654x440_d0x35.dds", dx=1600, dy=2, scale=1.25),
        Layer("factories/north_german_factory_metadata_os2654x440_d0x35.dds", dx=1760, dy=16, scale=1.1),
        Layer("factories/north_german_factory_metadata_os2654x440_d0x35.dds", dx=1890, dy=6, scale=1.3),
        Layer("factories/north_german_factory_metadata_os2654x440_d0x35.dds", dx=2010, dy=12, scale=1.15),
        Layer("settlement1/north_german/city/north_german_city1_metadata_os2654x440_d0x116.dds", window=(1420, 1720, 2654, 2654)),
        Layer("water/river/river_metadata_os2654x440_d0x190.dds"),
        Layer("fx/location_fx_metadata_os2654x440_d0x180.dds", window=(1350, 1650, 2654, 2654), alpha=0.45),
        Layer("ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds"),
    ), _mill_dusk),
    "logistics": Banner((   # the river to market: a wharf with barges, hamlets, then the walled city and its river port
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_arid_metadata_os2654x440_d0x40.dds"),
        Layer("ground3/arid/arid_grassland_ground3_metadata_os2654x440_d0x80.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds", window=(0, 0, 900, 1250), alpha=0.8),
        Layer("settlement1/syrian/rural/syrian_rural1_metadata_os2654x440_d178x144.dds", window=(700, 900, 1250, 1450)),
        Layer("settlement2/syrian/city/syrian_city2_metadata_os2654x440_d0x62.dds", window=(1500, 1610, 2654, 2654)),
        Layer("religious_buildings/syrian/syrian_religious3_metadata_os2654x440_d0x15.dds", dx=1780, dy=40),
        Layer("wall/syrian_wall_metadata_os2654x440_d680x170.dds", dx=760, window=(1500, 1560, 2654, 2654)),
        Layer("settlement1/syrian/city/syrian_city1_metadata_os2654x440_d0x124.dds", window=(1580, 1690, 2654, 2654)),
        Layer("water/river/river_metadata_os2654x440_d0x190.dds"),
        Layer("dock/syrian/syrian_dock1_metadata_os2654x440_d426x140_t.dds", dx=-60, dy=-20),
        Layer("dock/syrian/syrian_dock1_metadata_os2654x440_d426x140_t.dds", dx=520, dy=-14, mirror=True, window=(1000, 1050, 1420, 1470)),
        Layer("dock/syrian/syrian_dock2_metadata_os2654x440_d426x140_t.dds", dx=880, dy=-10),
        Layer("ground1/arid/arid_sparse_ground1_metadata_os2654x440_d0x304.dds"),
    ), _caravan_afternoon, 1.5),
    "population_growth": Banner((
        Layer("sky/sky_regular_metadata_os2654x440_d0x0.dds"),
        Layer("topology/flatlands/flatlands_metadata_os2654x440_d0x60.dds"),
        Layer("ground3/tropical/tropical_jungle_ground3_metadata_os2654x440_d0x58.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds"),
        Layer("settlement2/ashanti/rural/ashanti_rural2_metadata_os2654x440_d250x92.dds"),
        Layer("settlement1/ashanti/rural/ashanti_rural1_metadata_os2654x440_d210x66.dds"),
        Layer("settlement2/ashanti/town/ashanti_town2_metadata_os2654x440_d0x86.dds", (1150, 1450)),
        Layer("religious_buildings/ashanti/ashanti_religious2_metadata_os2654x440_d0x100.dds", dx=1640),
        Layer("settlement1/ashanti/town/ashanti_town1_metadata_os2654x440_d0x106.dds", (1250, 1550)),
        Layer("ground1/tropical/tropical_grassland_ground1_metadata_os2654x440_d0x288.dds"),
    ), _harmattan_morning, 1.6),
    "trade_goods": Banner((
        Layer("sky/sky_regular_metadata_os2654x440_d0x0.dds"),
        Layer("topology/mountains/mountains_metadata_os2654x440_d0x0.dds"),
        Layer("ground3/oceanic/oceanic_woods_ground3_metadata_os2654x440_d0x64.dds"),
        Layer("settlement2/asian/city/asian_city2_metadata_os2654x440_d0x44.dds"),
        Layer("settlement1/asian/city/asian_city1_metadata_os2654x440_d0x132.dds"),
        Layer("water/ocean/ocean_metadata_os2654x440_d0x254.dds"),
        Layer("dock/asian/asian_dock3_metadata_os2654x440_d426x140_t.dds", dx=500),
        Layer("dock/asian/asian_dock2_metadata_os2654x440_d426x140_t.dds", dx=1300),
    ), _natural, 1.12),
    "food_consumption": Banner((
        Layer("sky/sky_regular_metadata_os2654x440_d0x0.dds"),
        Layer("topology/volcano/volcano_metadata_os2654x440_d890x56.dds", dx=-560),
        Layer("topology/volcano/volcano_metadata_os2654x440_d890x56.dds", dx=420),
        Layer("ground3/mediterranean/mediterranean_sparse_ground3_metadata_os2654x440_d0x78.dds"),
        Layer("settlement2/aztec/city/aztec_city2_metadata_os2654x440_d0x70.dds"),
        Layer("religious_buildings/aztec/aztec_religious1_metadata_os2654x440_d0x80.dds", dx=800),
        Layer("religious_buildings/aztec/aztec_religious2_metadata_os2654x440_d0x80.dds", dx=1760),
        Layer("religious_buildings/aztec/aztec_religious3_metadata_os2654x440_d0x60.dds", dx=1225),
        Layer("settlement1/aztec/city/aztec_city1_metadata_os2654x440_d0x116.dds"),
        Layer("ground1/mediterranean/mediterranean_sparse_ground1_metadata_os2654x440_d0x288.dds"),
    ), _natural, 1.6),
    "rural_capacities": Banner((
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/flatlands/flatlands_metadata_os2654x440_d0x60.dds"),
        Layer("ground3/arctic/arctic_forest_ground3_metadata_os2654x440_d0x34.dds"),
        Layer("water/river_ocean/river_ocean_metadata_os2654x440_d0x208.dds"),
        Layer("dock/north_german/north_german_dock1_metadata_os2654x440_d426x140_t.dds", dx=1250),
        Layer("dock/north_german/north_german_dock2_metadata_os2654x440_d426x140_t.dds", dx=150),
    ), _northern, 1.3),
}


def _ramp(values: list[float]) -> Image.Image:
    """A 2654 x 440 alpha mask from one 0..1 value per column."""
    ramp = Image.new("L", (2654, 1))
    ramp.putdata([round(255 * max(0.0, min(1.0, v))) for v in values])
    return ramp.resize((2654, 440))


def _layer(interface: Path, layer: Layer) -> Image.Image:
    x, y = map(int, re.search(r"_d(\d+)x(\d+)(?:_t)?\.dds$", layer.path).groups())
    with Image.open(interface / LOCATION / layer.path) as source:
        sprite = source.convert("RGBA")
    if layer.mirror:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
    if layer.scale != 1.0:
        w, h = sprite.size
        sprite = sprite.resize((round(w * layer.scale), round(h * layer.scale)), Image.LANCZOS)
        x, y = x - (sprite.width - w) // 2, y - (sprite.height - h)
    pad = max(sprite.size)   # room for a sprite moved or grown past the canvas edge
    canvas = Image.new("RGBA", (2654 + 2 * pad, 440 + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(sprite, (x + layer.dx + pad, y + layer.dy + pad))
    canvas = canvas.crop((pad, pad, pad + 2654, pad + 440))
    if layer.fade_left:
        start, end = layer.fade_left
        canvas.putalpha(ImageChops.multiply(canvas.getchannel("A"), _ramp([(i - start) / (end - start) for i in range(2654)])))
    if layer.window:
        a, b, c, d = layer.window
        keep = [min((i - a) / max(1, b - a), (d - i) / max(1, d - c)) for i in range(2654)]
        canvas.putalpha(ImageChops.multiply(canvas.getchannel("A"), _ramp(keep)))
    if layer.alpha != 1.0:
        canvas.putalpha(canvas.getchannel("A").point(lambda v: round(v * layer.alpha)))
    return canvas


def banner(interface: Path, name: str) -> Image.Image:
    spec = BANNERS[name]
    pano = Image.new("RGBA", (2654, 440), (0, 0, 0, 0))
    for layer in spec.layers:
        pano.alpha_composite(_layer(interface, layer))
    scale = H / 440 * spec.pano_scale
    pano = pano.resize((round(2654 * scale), round(440 * scale)), Image.LANCZOS)
    left = (pano.width - W) // 2
    return spec.grade(pano.crop((left, 0, left + W, H)).convert("RGB")).convert("RGBA")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write 1x PNGs into this folder")
    parser.add_argument("--no-write", action="store_true", help="only the previews")
    parser.add_argument("names", nargs="*", help="banners to build (default: all)")
    args = parser.parse_args(argv)
    interface = vanilla_root(ROOT, ROOT / "constructor.toml") / INTERFACE
    for name in args.names or BANNERS:
        image = banner(interface, name)
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            image.resize((W // 2, H // 2), Image.LANCZOS).save(args.preview / f"banner_{name}.png")
        if not args.no_write:
            target = MOD / "main_menu" / BANNERS_DIR / f"banner_{name}.dds"
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format="DDS", pixel_format="DXT5")
            print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
