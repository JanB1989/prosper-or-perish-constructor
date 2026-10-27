"""Build the hatch the location view's capacity bar lays over the land the farms hold (arable_land_bar.py).

The farms' part of the bar is the arable land's green with dark brown diagonal stripes over it (2026-10-27, Jan: the
land is there, the farms hold it): a seamless 32 px tile, drawn tiled at texture density 2 (stripes every 8 px along
each axis). Rerun after changing it:

    uv run python tools/build_land_bar_hatch.py                  # write the DDS into the mod
    uv run python tools/build_land_bar_hatch.py --preview X.png  # also the tile on the green bar, enlarged
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from eu5_building_pipeline.dds import write_game_dds

from prosper_or_perish_constructor.arable_land_bar import HATCH
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
TILE = 32
PERIOD = 16          # texture px between stripes along each axis (divides TILE: the tile repeats seamlessly)
STRIPE = 6           # stripe width along each axis, texture px
COLOUR = (62, 38, 18)
OPACITY = 0.85
SUPERSAMPLE = 8


def hatch() -> Image.Image:
    """Diagonal stripes (x + y within STRIPE of a multiple of PERIOD), anti-aliased by supersampling."""
    size = TILE * SUPERSAMPLE
    big = Image.new("L", (size, size), 0)
    px = big.load()
    for y in range(size):
        for x in range(size):
            if ((x + y) / SUPERSAMPLE) % PERIOD < STRIPE:
                px[x, y] = 255
    alpha = big.resize((TILE, TILE), Image.BOX).point(lambda a: round(a * OPACITY))
    tile = Image.new("RGBA", (TILE, TILE), (*COLOUR, 0))
    tile.putalpha(alpha)
    return tile


def preview(tile: Image.Image, path: Path) -> None:
    """The tile repeated over the vanilla green bar (texture density 2: one GUI px = two texture px), enlarged."""
    width, height = 120, 18
    with Image.open(vanilla_root(ROOT, ROOT / "constructor.toml") / "game/main_menu/gfx/interface/progressbars/"
                    "progress_bar_green_alt.dds") as source:
        green = source.convert("RGBA").resize((width * 2, height * 2), Image.LANCZOS)
    stripes = Image.new("RGBA", green.size)
    for x in range(0, green.width, TILE):
        for y in range(0, green.height, TILE):
            stripes.alpha_composite(tile, (x, y))
    sheet = Image.new("RGBA", (green.width * 2, green.height), (52, 60, 74, 255))
    sheet.alpha_composite(green, (0, 0))
    sheet.alpha_composite(Image.alpha_composite(green, stripes), (green.width, 0))
    sheet.resize((sheet.width * 3 // 2, sheet.height * 3 // 2), Image.LANCZOS).save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write the tile on the green bar")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    tile = hatch()
    if args.preview:
        preview(tile, args.preview)
    if not args.no_write:
        target = MOD / "main_menu" / HATCH
        write_game_dds(tile, target)   # DXT5 + full mips (eu5_building_pipeline.dds)
        print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
