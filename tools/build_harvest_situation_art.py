"""Build the art of the mod's situations: the Variable Harvests panel picture and icon, the welcome panel picture.

- Panel picture: the Variable Harvests painting (assets/europedia_paintings/harvest.jpg, the harvest card's banner:
  harvesters binding sheaves while a storm front rolls in) cut to
  vanilla's situation picture size, 1080 x 440 (shown about 540 x 220 at the top of the situation panel,
  in_game/gui/panels/situation/harvest_situation.gui). Without it the panel showed vanilla's default picture, a
  burning town.
- Icon: vanilla's weather icon (the Variable Harvests concept icon) copied to the situation's own icon name, so the
  situation list and the panel header show it instead of vanilla's default hourglass.
- Welcome picture (pp_mod_welcome_situation): the Population Growth painting (a growing West African town), cut the
  same way for in_game/gui/panels/situation/pp_mod_welcome_situation.gui. Its icon is hand-kept.

Rerun after a game update:

    uv run python tools/build_harvest_situation_art.py                 # write all into the mod
    uv run python tools/build_harvest_situation_art.py --preview DIR   # also PNGs of the pictures to look at
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

from PIL import Image

from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
PICTURE = "gfx/interface/illustrations/situation/{}.dds"   # under the mod's main_menu, like vanilla's
ICON = "gfx/interface/icons/situations/harvest_situation.dds"   # under the mod's in_game, like the welcome icon
ICON_SOURCE = "game/main_menu/gfx/interface/icons/alerts_icons/weather_system.dds"
SIZE = (1080, 440)
# situation key: (painting, where the picture starts in it; full height, the same aspect as SIZE)
PICTURES = {
    "harvest_situation": ("harvest", 160),          # the storm, the harvesters, the cart
    "pp_mod_welcome_situation": ("population_growth", 200),   # the builders, the market women, the town behind
}


def _banners():
    spec = importlib.util.spec_from_file_location("build_europedia_banners", ROOT / "tools/build_europedia_banners.py")
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool
    spec.loader.exec_module(tool)
    return tool


def picture(key: str = "harvest_situation") -> Image.Image:
    painting, left = PICTURES[key]
    full = _banners().painting(painting)
    width = round(full.height * SIZE[0] / SIZE[1])
    return full.crop((left, 0, left + width, full.height)).resize(SIZE, Image.LANCZOS).convert("RGBA")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write a PNG of the picture into this folder")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    vanilla = vanilla_root(ROOT, ROOT / "constructor.toml")
    for key in PICTURES:
        image = picture(key)
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(args.preview / f"{key}.png")
        if not args.no_write:
            target = MOD / "main_menu" / PICTURE.format(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format="DDS", pixel_format="DXT5")
            print(target.relative_to(ROOT))
    if not args.no_write:
        icon = MOD / "in_game" / ICON
        icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(vanilla / ICON_SOURCE, icon)
        print(icon.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
