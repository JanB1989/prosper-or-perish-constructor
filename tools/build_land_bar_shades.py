"""Build the location view's own bar shades (arable_land_bar.py SHADES) from vanilla's bars.

2026-10-27, Jan: the townsfolk a neutral grey (vanilla's grey bar reads blue); the land the farms use a plain brownish
green (stripes were convoluted). Both are vanilla's bars recoloured in HSV, so they keep the bars' shading. Rerun after
changing them:

    uv run python tools/build_land_bar_shades.py                  # write the DDS into the mod
    uv run python tools/build_land_bar_shades.py --preview X.png  # also each vanilla bar and its shade, enlarged
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from eu5_building_pipeline.dds import write_game_dds

from prosper_or_perish_constructor.arable_land_bar import SHADES
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
BARS = "game/main_menu/gfx/interface/progressbars"
# bar part -> (vanilla bar, hue it takes on PIL's 0..255 scale or None to keep it, saturation factor, value factor);
# vanilla's green sits at hue ~74, its grey at ~146 with saturation ~69
RECOLOUR = {
    "townsfolk": ("progress_bar_grey_alt", None, 0.1, 0.85),
    "farms": ("progress_bar_green_alt", 50, 0.7, 0.75),
}


def recolour(bar: Image.Image, hue: int | None, saturation: float, value: float) -> Image.Image:
    h, s, v = bar.convert("RGB").convert("HSV").split()
    if hue is not None:
        h = h.point(lambda _: hue)
    s = s.point(lambda x: min(255, round(x * saturation)))
    v = v.point(lambda x: min(255, round(x * value)))
    shade = Image.merge("HSV", (h, s, v)).convert("RGBA")
    shade.putalpha(bar.getchannel("A"))
    return shade


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write each vanilla bar and its shade side by side")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    bars = vanilla_root(ROOT, ROOT / "constructor.toml") / BARS
    shown: list[Image.Image] = []
    for part, target in SHADES.items():
        source, *recipe = RECOLOUR[part]
        with Image.open(bars / f"{source}.dds") as raw:
            bar = raw.convert("RGBA")
        shade = recolour(bar, *recipe)
        shown += [bar, shade]
        if not args.no_write:
            write_game_dds(shade, MOD / "main_menu" / target)   # DXT5 + full mips (eu5_building_pipeline.dds)
            print((MOD / "main_menu" / target).relative_to(ROOT))
    if args.preview:
        width, height = 240, 36
        sheet = Image.new("RGBA", (width * len(shown), height), (34, 38, 46, 255))
        for i, im in enumerate(shown):
            sheet.alpha_composite(im.resize((width, height), Image.LANCZOS), (width * i, 0))
        sheet.save(args.preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
