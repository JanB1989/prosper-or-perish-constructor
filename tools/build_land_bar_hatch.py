"""Build the hatches the location view's capacity bar lays over its parts past the capacity (arable_land_bar.py).

Both are diagonal stripes (2026-10-27, Jan): the land the farms hold is the arable land's green with dark brown stripes
(the land is there, the farms take it), the possible improvements the faded green with bright green stripes (land not
there yet). Each a seamless 32 px tile, drawn tiled at texture density 2 (stripes every 8 px along each axis). Rerun
after changing them:

    uv run python tools/build_land_bar_hatch.py                  # write the DDS into the mod
    uv run python tools/build_land_bar_hatch.py --preview X.png  # also both on their bar parts, enlarged
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from eu5_building_pipeline.dds import write_game_dds

from prosper_or_perish_constructor.arable_land_bar import ALPHA, HATCHES
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
TILE = 32
PERIOD = 16          # texture px between stripes along each axis (divides TILE: the tile repeats seamlessly)
STRIPE = 6           # stripe width along each axis, texture px
SUPERSAMPLE = 8
# bar part -> stripe colour and opacity
STRIPES = {"farms": ((62, 38, 18), 0.85), "room": ((128, 196, 76), 0.9)}
TRACK = (34, 38, 46)  # the empty bar under a faded part, roughly


def hatch(colour: tuple[int, int, int], opacity: float) -> Image.Image:
    """Diagonal stripes (x + y within STRIPE of a multiple of PERIOD), anti-aliased by supersampling."""
    size = TILE * SUPERSAMPLE
    big = Image.new("L", (size, size), 0)
    px = big.load()
    for y in range(size):
        for x in range(size):
            if ((x + y) / SUPERSAMPLE) % PERIOD < STRIPE:
                px[x, y] = 255
    alpha = big.resize((TILE, TILE), Image.BOX).point(lambda a: round(a * opacity))
    tile = Image.new("RGBA", (TILE, TILE), (*colour, 0))
    tile.putalpha(alpha)
    return tile


def preview(tiles: dict[str, Image.Image], path: Path) -> None:
    """Each tile repeated over its bar part (texture density 2: one GUI px = two texture px), side by side, enlarged."""
    width, height = 120, 18
    with Image.open(vanilla_root(ROOT, ROOT / "constructor.toml") / "game/main_menu/gfx/interface/progressbars/"
                    "progress_bar_green_alt.dds") as source:
        green = source.convert("RGBA").resize((width * 2, height * 2), Image.LANCZOS)
    sheet = Image.new("RGBA", (green.width * (len(tiles) + 1), green.height), (*TRACK, 255))
    sheet.alpha_composite(green, (0, 0))
    for i, (part, tile) in enumerate(tiles.items(), start=1):
        base = green.copy()
        if part in ALPHA:
            base.putalpha(base.getchannel("A").point(lambda a: round(a * ALPHA[part])))
        stripes = Image.new("RGBA", green.size)
        for x in range(0, green.width, TILE):
            for y in range(0, green.height, TILE):
                stripes.alpha_composite(tile, (x, y))
        sheet.alpha_composite(Image.alpha_composite(base, stripes), (green.width * i, 0))
    sheet.resize((sheet.width * 3 // 2, sheet.height * 3 // 2), Image.LANCZOS).save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write the tiles on their bar parts")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    tiles = {part: hatch(*STRIPES[part]) for part in HATCHES}
    if args.preview:
        preview(tiles, args.preview)
    if not args.no_write:
        for part, tile in tiles.items():
            target = MOD / "main_menu" / HATCHES[part]
            write_game_dds(tile, target)   # DXT5 + full mips (eu5_building_pipeline.dds)
            print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
