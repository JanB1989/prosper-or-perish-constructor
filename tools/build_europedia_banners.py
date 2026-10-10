"""Build the Europedia card banners from painted pictures (2900 x 500 DDS, shown at 1450 x 250, pp_europedia_style.gui).

Every banner is a painting of its page's topic in the style of the game's loading screens (Jan, 2026-10-10: no more
stitched landscapes, a picture of what the page is about). The paintings are in assets/europedia_paintings/ (see its
README for where they come from and how to add one); this tool cuts the banner strip out of each and writes the DDS:

- labor: porters and day labourers hired at a Hanseatic quay;
- logistics: barges and a camel caravan at a river landing below an Ottoman market town;
- harvest: harvesters binding sheaves while a storm front rolls in (Variable Harvests);
- arable_land: villagers clearing forest, pulling stumps, draining and ploughing new fields;
- food: grain carried into a South Asian town's great storehouse and counted;
- food_production: rice paddies, fishermen and a village kitchen in an East Asian valley;
- food_consumption: an Aztec market feast, nobles served on the terrace;
- rural_capacities: woodcutters, net menders and boats on a Norwegian fjord coast;
- trade_goods: a Portuguese victualling yard, casks and biscuit rolled aboard (New Trade Goods);
- population_growth: a growing Ashanti town, new houses, a crowded market, newcomers.

    uv run python tools/build_europedia_banners.py                    # write every banner into the mod
    uv run python tools/build_europedia_banners.py labor --preview DIR
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
PAINTINGS_DIR = ROOT / "assets/europedia_paintings"
BANNERS_DIR = "gfx/interface/illustrations/pp_europedia"   # under the mod's main_menu
W, H = 2900, 500

# banner -> the row of its painting where the strip starts (the strip is the painting's full width, W:H tall), set by
# eye so the faces and the subject stay in frame
PAINTINGS: dict[str, int] = {
    "labor": 150,
    "logistics": 165,
    "harvest": 60,          # high enough to keep the storm front over the fields
    "arable_land": 110,
    "food": 165,
    "food_production": 165,
    "food_consumption": 165,
    "rural_capacities": 165,
    "trade_goods": 165,
    "population_growth": 165,
}


def painting(name: str) -> Image.Image:
    with Image.open(PAINTINGS_DIR / f"{name}.jpg") as source:
        return source.convert("RGB")


def banner(name: str) -> Image.Image:
    """The banner strip of a painting at the stored size, lightly sharpened after the upscale."""
    image = painting(name)
    top = PAINTINGS[name]
    height = round(image.width * H / W)
    if top + height > image.height:
        raise ValueError(f"{name}: the strip from row {top} runs past the painting ({image.height} rows)")
    strip = image.crop((0, top, image.width, top + height)).resize((W, H), Image.LANCZOS)
    return strip.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2)).convert("RGBA")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write 1x PNGs into this folder")
    parser.add_argument("--no-write", action="store_true", help="only the previews")
    parser.add_argument("names", nargs="*", help="banners to build (default: all)")
    args = parser.parse_args(argv)
    for name in args.names or PAINTINGS:
        image = banner(name)
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
