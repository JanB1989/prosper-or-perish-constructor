"""Build the Europedia card banners (2x resolution DDS; the card shows them at 1450 x 250, pp_europedia_style.gui).

Vanilla has no topic picture wider than 1080 px, which looks soft stretched over a 1450 px card. Each banner is a wide
landscape from the location view's panorama layers instead (2654 px, sharp), graded to its topic:

- harvest: farmland under a late-summer grade (Variable Harvests);
- arable_land: forest on the left giving way to cleared fields and farmsteads on the right (Arable Land);
- food: a market town among its fields on a river (Food);
- food_production: farmsteads among their fields above a fishing coast (Food Production).

Rerun after a game update:

    uv run python tools/build_europedia_banners.py                   # write every banner into the mod
    uv run python tools/build_europedia_banners.py --preview DIR     # also 1x PNGs to look at
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageEnhance

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
        Layer("ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds"),
    ), _late_summer),
    "arable_land": Banner((
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_metadata_os2654x440_d0x15.dds"),
        Layer("ground3/continental/continental_forest_ground3_metadata_os2654x440_d0x62.dds"),
        Layer("ground3/continental/continental_grassland_ground3_metadata_os2654x440_d0x66.dds", (950, 1500)),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds", (1000, 1550)),
        Layer("settlement1/north_german/rural/north_german_rural11_metadata_os2654x440_d0x92.dds", (1000, 1200)),
        Layer("ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds"),
    ), _natural),
    "food": Banner((
        Layer("sky/sky_regular_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_metadata_os2654x440_d0x15.dds"),
        Layer("ground3/continental/continental_grassland_ground3_metadata_os2654x440_d0x66.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds"),
        Layer("settlement2/north_german/town/north_german_town2_metadata_os2654x440_d0x54.dds"),
        Layer("settlement1/north_german/town/north_german_town1_metadata_os2654x440_d0x106.dds"),
        Layer("water/river/river_metadata_os2654x440_d0x190.dds"),
        Layer("ground1/continental/continental_grassland_ground1_metadata_os2654x440_d0x310.dds"),
    ), _natural),
    "food_production": Banner((
        Layer("sky/sky_regular2_metadata_os2654x440_d0x0.dds"),
        Layer("topology/hills/hills_metadata_os2654x440_d0x15.dds"),
        Layer("ground3/oceanic/oceanic_grassland_ground3_metadata_os2654x440_d0x68.dds"),
        Layer("ground3/farmlands_metadata_os2654x440_d0x102.dds"),
        Layer("settlement1/north_german/rural/north_german_rural11_metadata_os2654x440_d0x92.dds"),
        Layer("water/river_ocean/river_ocean_metadata_os2654x440_d0x208.dds"),
        Layer("ground1/oceanic/oceanic_grassland_ground1_metadata_os2654x440_d0x288.dds"),
    ), _natural, pano_scale=1.4),
}


def _layer(interface: Path, layer: Layer) -> Image.Image:
    x, y = map(int, re.search(r"_d(\d+)x(\d+)(?:_t)?\.dds$", layer.path).groups())
    canvas = Image.new("RGBA", (2654, 440), (0, 0, 0, 0))
    with Image.open(interface / LOCATION / layer.path) as source:
        canvas.alpha_composite(source.convert("RGBA"), (x + layer.dx, y))
    if layer.fade_left:
        start, end = layer.fade_left
        ramp = Image.new("L", (2654, 1))
        ramp.putdata([0 if i < start else 255 if i > end else int(255 * (i - start) / (end - start)) for i in range(2654)])
        canvas.putalpha(ImageChops.multiply(canvas.getchannel("A"), ramp.resize((2654, 440))))
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
