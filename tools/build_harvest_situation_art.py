"""Build the art of the Variable Harvests situation (harvest_situation): its panel picture and its icon.

- Panel picture: the harvest card's fat year, lean year farmland (tools/build_europedia_banners.py, banner "harvest";
  the cut holds the turn from the sunlit harvest into the storm) cut to
  vanilla's situation picture size, 1080 x 440 (shown about 540 x 220 at the top of the situation panel,
  in_game/gui/panels/situation/harvest_situation.gui). Without it the panel showed vanilla's default picture, a
  burning town.
- Icon: vanilla's weather icon (the Variable Harvests concept icon) copied to the situation's own icon name, so the
  situation list and the panel header show it instead of vanilla's default hourglass.

Rerun after a game update:

    uv run python tools/build_harvest_situation_art.py                 # write both into the mod
    uv run python tools/build_harvest_situation_art.py --preview DIR   # also a PNG of the picture to look at
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
PICTURE = "gfx/interface/illustrations/situation/harvest_situation.dds"   # under the mod's main_menu, like vanilla's
ICON = "gfx/interface/icons/situations/harvest_situation.dds"             # under the mod's in_game, like the welcome icon
ICON_SOURCE = "game/main_menu/gfx/interface/icons/alerts_icons/weather_system.dds"
SIZE = (1080, 440)
# the part of the 2900 x 500 banner the picture shows: the same aspect as SIZE, two farmsteads, sun turning to storm
CROP_LEFT = 1080


def _banners():
    spec = importlib.util.spec_from_file_location("build_europedia_banners", ROOT / "tools/build_europedia_banners.py")
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool   # its dataclasses look themselves up there
    spec.loader.exec_module(tool)
    return tool


def picture(vanilla: Path) -> Image.Image:
    tool = _banners()
    wide = tool.banner(vanilla / tool.INTERFACE, "harvest")
    width = round(wide.height * SIZE[0] / SIZE[1])
    return wide.crop((CROP_LEFT, 0, CROP_LEFT + width, wide.height)).resize(SIZE, Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write a PNG of the picture into this folder")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    vanilla = vanilla_root(ROOT, ROOT / "constructor.toml")
    image = picture(vanilla)
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(args.preview / "harvest_situation.png")
    if not args.no_write:
        target = MOD / "main_menu" / PICTURE
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="DDS", pixel_format="DXT5")
        print(target.relative_to(ROOT))
        icon = MOD / "in_game" / ICON
        icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(vanilla / ICON_SOURCE, icon)
        print(icon.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
