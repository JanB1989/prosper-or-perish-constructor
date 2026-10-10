"""Draw the icon of the Navigable Rivers map mode: a small sailing boat on vanilla's Rivers map mode icon.

The map mode picker reads `gfx/interface/icons/map_modes/<map mode>.dds` (main_menu), and the game concept of the same
key (pp_navigable_rivers, the Europedia card) points its texture there too. The boat is drawn here at 4x and scaled
down, so it stays readable at the picker's size and does not copy any other art.

Rerun after a game update:

    uv run python tools/build_navigable_rivers_icon.py                 # write the DDS into the mod
    uv run python tools/build_navigable_rivers_icon.py --preview DIR   # also a PNG to look at
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from prosper_or_perish_constructor.worldbuilder.navigation_map_modes import MAP_MODE
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
ICON = f"main_menu/gfx/interface/icons/map_modes/{MAP_MODE}.dds"
SOURCE = "game/main_menu/gfx/interface/icons/map_modes/rivers.dds"
SIZE = 128
SCALE = 4
OUTLINE = (30, 20, 12, 255)


def boat() -> Image.Image:
    """Hull, mast, a square sail with two reef lines and a red pennant, on a transparent 128 px canvas."""
    image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def at(points):
        return [(x * SCALE, y * SCALE) for x, y in points]

    draw.polygon(at([(40, 78), (96, 78), (88, 92), (48, 92)]), fill=(120, 78, 40, 255), outline=OUTLINE, width=3 * SCALE)
    draw.line(at([(44, 84), (92, 84)]), fill=(90, 58, 30, 255), width=2 * SCALE)
    draw.line(at([(68, 30), (68, 79)]), fill=OUTLINE, width=3 * SCALE)
    draw.polygon(at([(52, 36), (84, 36), (86, 70), (50, 70)]), fill=(236, 222, 186, 255), outline=OUTLINE, width=3 * SCALE)
    draw.line(at([(52, 47), (84, 47)]), fill=(200, 180, 140, 255), width=2 * SCALE)
    draw.line(at([(51, 58), (85, 58)]), fill=(200, 180, 140, 255), width=2 * SCALE)
    draw.polygon(at([(68, 30), (80, 33), (68, 36)]), fill=(170, 40, 35, 255), outline=OUTLINE)
    return image.resize((SIZE, SIZE), Image.LANCZOS)


def icon(vanilla: Path) -> Image.Image:
    with Image.open(vanilla / SOURCE) as source:
        out = source.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    ship = boat()
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    shadow.putalpha(ship.split()[3].point(lambda a: int(a * 0.5)).filter(ImageFilter.GaussianBlur(2)))
    out.alpha_composite(shadow, (2, 3))
    out.alpha_composite(ship, (-4, -8))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write a PNG of the icon into this folder")
    args = parser.parse_args(argv)
    image = icon(vanilla_root(ROOT, ROOT / "constructor.toml"))
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        image.save(args.preview / f"{MAP_MODE}.png")
    target = MOD / ICON
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="DDS", pixel_format="DXT5")
    print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
