"""Build the Europedia card banners (2x resolution DDS; the card shows them at 1450 x 250, pp_europedia_style.gui).

Vanilla has no harvest picture wider than 1080 px, which looks soft stretched over a 1450 px card. The banner is
composed instead: a wide landscape from the location view's panorama layers (2654 px, sharp), graded to late summer,
with the vanilla wheat-harvest painting in the middle at its own resolution, fading into the landscape at the sides
and the top. Rerun after a game update:

    uv run python tools/build_europedia_banners.py             # write the DDS into the mod
    uv run python tools/build_europedia_banners.py --preview X.png   # also a 1x PNG to look at
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
BANNER = "gfx/interface/illustrations/pp_europedia/banner_harvest.dds"   # under the mod's main_menu
W, H = 2900, 500
INTERFACE = "game/main_menu/gfx/interface"
# back to front, as the location view stacks them (offset in the file name: _d<x>x<y>)
PANORAMA = (
    "illustrations/location/sky/sky_regular_metadata_os2654x440_d0x0.dds",
    "illustrations/location/topology/hills/hills_metadata_os2654x440_d0x15.dds",
    "illustrations/location/ground3/continental/continental_grassland_ground3_metadata_os2654x440_d0x66.dds",
    "illustrations/location/ground3/farmlands_metadata_os2654x440_d0x102.dds",
    "illustrations/location/settlement1/north_german/rural/north_german_rural11_metadata_os2654x440_d0x92.dds",
    "illustrations/location/ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds",
)
PAINTING = "icons/trade_goods/illustrations/icon_goods_wheat.dds"
PANO_SCALE = 1.76      # x the banner height: puts the panorama's horizon level with the painting's
PANO_TOP = 0           # rows cut from the scaled panorama's top
CROP = (300, 40)       # px cut off the scaled painting left / right (the left sheaf would fade into a ghost)
FADE = (200, 150)      # px over which the painting fades into the landscape at the left / right
TOP_FADE = 150         # px over which its sky fades into the landscape's


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _ramp(length: int, start: int, end: int = 0) -> Image.Image:
    """A 1-px line mask: 0 at the edges, 255 inside, smoothstep over ``start`` / ``end`` px (0: no fade)."""
    line = Image.new("L", (length, 1))
    line.putdata([int(255 * _smooth(min(i / start if start else 1.0, (length - 1 - i) / end if end else 1.0)))
                  for i in range(length)])
    return line


def panorama(interface: Path) -> Image.Image:
    pano = Image.new("RGBA", (2654, 440), (0, 0, 0, 0))
    for rel in PANORAMA:
        x, y = map(int, re.search(r"_d(\d+)x(\d+)\.dds$", rel).groups())
        with Image.open(interface / rel) as layer:
            pano.alpha_composite(layer.convert("RGBA"), (x, y))
    scale = H / 440 * PANO_SCALE
    pano = pano.resize((round(2654 * scale), round(440 * scale)), Image.LANCZOS)
    left = (pano.width - W) // 2
    return pano.crop((left, PANO_TOP, left + W, PANO_TOP + H)).convert("RGB")


def late_summer(im: Image.Image) -> Image.Image:
    """Fields toward ripe straw below the horizon, a warm cast over all; the sky keeps its blue."""
    lum = im.convert("L")
    straw = Image.merge("RGB", (lum.point(lambda v: min(255, int(v * 1.32 + 18))),
                                lum.point(lambda v: min(255, int(v * 1.08 + 8))),
                                lum.point(lambda v: int(v * 0.55))))
    ground = Image.linear_gradient("L").resize((W, H)).point(lambda v: max(0, min(255, (v - 40) * 3)))
    out = Image.composite(Image.blend(im, straw, 0.62), im, ground)
    out = Image.blend(out, ImageChops.multiply(out, Image.new("RGB", (W, H), (255, 214, 150))), 0.35)
    return ImageEnhance.Contrast(out).enhance(1.05)


def painting(interface: Path) -> Image.Image:
    with Image.open(interface / PAINTING) as source:
        paint = source.convert("RGBA")
    paint = paint.resize((round(paint.width * H / paint.height), H), Image.LANCZOS)
    paint = paint.crop((CROP[0], 0, paint.width - CROP[1], H))
    sides = _ramp(paint.width, *FADE).resize(paint.size)
    top = _ramp(paint.height, TOP_FADE).rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT).resize(paint.size)
    paint.putalpha(ImageChops.multiply(paint.getchannel("A"), ImageChops.multiply(sides, top)))
    return paint


def banner(interface: Path) -> Image.Image:
    out = late_summer(panorama(interface)).convert("RGBA")
    paint = painting(interface)
    out.alpha_composite(paint, ((W - paint.width) // 2, 0))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write a 1x PNG here")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    interface = vanilla_root(ROOT, ROOT / "constructor.toml") / INTERFACE
    image = banner(interface)
    if args.preview:
        image.resize((W // 2, H // 2), Image.LANCZOS).save(args.preview)
    if not args.no_write:
        target = MOD / "main_menu" / BANNER
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="DDS", pixel_format="DXT5")
        print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
