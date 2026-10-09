"""Build the three arable-land state icons (location view land chip, Europedia, concepts) from vanilla icon parts.

Each icon is the land and its people: vanilla land plates (fresh green, plain, dry brown), the peasants (few, more, a
crowd) and vanilla's strength chevrons (two green, one green, two red). Rerun after a game update:

    uv run python tools/build_arable_land_icons.py                  # write the DDS into the mod
    uv run python tools/build_arable_land_icons.py --preview X.png  # also a sheet at full and chip size
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance

from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
ICONS_DIR = "gfx/interface/icons/pp_arable_land"   # under the mod's main_menu: abundant.dds, available.dds, overused.dds
SIZE = 128


def _load(icons: Path, rel: str, size: int) -> Image.Image:
    with Image.open(icons / rel) as source:
        return source.convert("RGBA").resize((size, size), Image.LANCZOS)


def _tint(im: Image.Image, rgb: tuple[int, int, int], amount: float) -> Image.Image:
    """Shift the colour toward ``rgb``, keeping the shading and the alpha."""
    lum = im.convert("L")
    colour = Image.merge("RGB", tuple(lum.point(lambda v, c=c: int(v * c / 255)) for c in rgb))
    mixed = Image.blend(im.convert("RGB"), colour, amount)
    mixed.putalpha(im.getchannel("A"))
    return mixed


def _icon(land: Image.Image, people: list[tuple[Image.Image, tuple[int, int]]], arrow: tuple[Image.Image, tuple[int, int]]) -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(land, (SIZE - land.width, 0))
    for im, pos in people:
        canvas.alpha_composite(im, pos)
    canvas.alpha_composite(*arrow)
    return canvas


def icons(interface_icons: Path) -> dict[str, Image.Image]:
    load = lambda rel, size: _load(interface_icons, rel, size)  # noqa: E731
    lush = ImageEnhance.Color(_tint(load("location_icons/terrain.dds", 108), (110, 200, 70), 0.55)).enhance(1.3)
    plain = load("location_icons/terrain.dds", 100)
    dry = _tint(load("map_modes/area.dds", 84), (190, 120, 60), 0.35)
    return {
        "abundant": _icon(lush, [(load("pops/peasants.dds", 44), (2, 82))],
                          (load("text_icons/arrow_bonus_tier_2.dds", 62), (66, 66))),
        "available": _icon(plain, [(load("pops/peasants.dds", 64), (0, 62))],
                           (load("text_icons/arrow_bonus_tier_1.dds", 62), (66, 70))),
        "overused": _icon(dry, [(load("location_icons/population.dds", 74), (30, 46)), (load("pops/peasants.dds", 74), (-6, 54))],
                          (load("text_icons/arrow_malus_tier_2.dds", 62), (66, 66))),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write a preview sheet (full size and chip size)")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    built = icons(vanilla_root(ROOT, ROOT / "constructor.toml") / "game/main_menu/gfx/interface/icons")
    if args.preview:
        sheet = Image.new("RGBA", (3 * 150 + 3 * 50, 150), (52, 60, 74, 255))
        for i, im in enumerate(built.values()):
            sheet.alpha_composite(im, (i * 150 + 10, 10))
            sheet.alpha_composite(im.resize((30, 30), Image.LANCZOS), (450 + i * 50 + 10, 60))
        sheet.save(args.preview)
    if not args.no_write:
        target = MOD / "main_menu" / ICONS_DIR
        target.mkdir(parents=True, exist_ok=True)
        for name, im in built.items():
            im.save(target / f"{name}.dds", format="DDS", pixel_format="DXT5")
            print((target / f"{name}.dds").relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
