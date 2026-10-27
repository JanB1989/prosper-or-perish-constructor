"""Build the two green shades of the location view's capacity bar past the capacity (arable_land_bar.py).

Three greens on one bar (2026-10-27, Jan: stripes and an empty slot were convoluted): the arable land left is vanilla's
green bar; the land the farms use is a darker green turned towards olive; the land improvements could still add is a
lighter, paler green. Both are vanilla's green bar recoloured in HSV, so they keep its shading. Rerun after changing
them:

    uv run python tools/build_land_bar_shades.py                  # write the DDS into the mod
    uv run python tools/build_land_bar_shades.py --preview X.png  # also the three greens side by side, enlarged
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
SOURCE = "game/main_menu/gfx/interface/progressbars/progress_bar_green_alt.dds"
# bar part -> (hue it takes, PIL's 0..255 scale; vanilla's green sits at ~74), saturation factor, value factor
RECOLOUR = {"farms": (52, 0.9, 0.95), "room": (74, 0.55, 1.25)}


def recolour(green: Image.Image, hue: int, saturation: float, value: float) -> Image.Image:
    h, s, v = green.convert("RGB").convert("HSV").split()
    h = h.point(lambda _: hue)
    s = s.point(lambda x: min(255, round(x * saturation)))
    v = v.point(lambda x: min(255, round(x * value)))
    shade = Image.merge("HSV", (h, s, v)).convert("RGBA")
    shade.putalpha(green.getchannel("A"))
    return shade


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write the three greens side by side")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    with Image.open(vanilla_root(ROOT, ROOT / "constructor.toml") / SOURCE) as source:
        green = source.convert("RGBA")
    shades = {part: recolour(green, *RECOLOUR[part]) for part in SHADES}
    if args.preview:
        width, height = 240, 36
        shown = [green, shades["farms"], shades["room"]]
        sheet = Image.new("RGBA", (width * len(shown), height), (34, 38, 46, 255))
        for i, im in enumerate(shown):
            sheet.alpha_composite(im.resize((width, height), Image.LANCZOS), (width * i, 0))
        sheet.save(args.preview)
    if not args.no_write:
        for part, shade in shades.items():
            target = MOD / "main_menu" / SHADES[part]
            write_game_dds(shade, target)   # DXT5 + full mips (eu5_building_pipeline.dds)
            print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
