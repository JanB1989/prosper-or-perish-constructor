"""Recolour the vanilla round location-chip frame into one frame per harvest severity.

The location view's harvest chip (location_status.py) shows the region's crop inside the frame; the frame's colour
says how the harvest went (red, orange, yellow for failed, bad, weak; light green, green, teal for strong, excellent,
exceptional). Average years use vanilla's neutral brown frame. Rerun after changing a colour:

    uv run python tools/build_harvest_frames.py
"""

from pathlib import Path

from PIL import Image, ImageOps

from prosper_or_perish_constructor.location_status import HARVEST_FRAMES, SEVERITY_COLOURS
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
SOURCE = "game/main_menu/gfx/interface/icons/climate/continental_frame.dds"


def recolour(frame: Image.Image, colour: tuple[int, int, int]) -> Image.Image:
    """Keep the frame's shading and ornament, map its mid tones onto the colour."""
    tinted = ImageOps.colorize(ImageOps.grayscale(frame), black=(15, 10, 8), mid=colour, white=(250, 240, 215), midpoint=110, whitepoint=235)
    tinted.putalpha(frame.getchannel("A"))
    return tinted


def main() -> None:
    with Image.open(vanilla_root(ROOT, ROOT / "constructor.toml") / SOURCE) as source:
        frame = source.convert("RGBA")
    for severity, colour in SEVERITY_COLOURS.items():
        target = MOD / "in_game" / HARVEST_FRAMES.format(severity=severity)
        target.parent.mkdir(parents=True, exist_ok=True)
        recolour(frame, colour).save(target, format="DDS", pixel_format="DXT5")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
