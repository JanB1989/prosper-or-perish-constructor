"""Export the subsistence-land artwork to the game's shared capacity icon slots."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/icons/subsistence_land/subsistence_land.png"
ICONS = (
    ROOT
    / "mod/Prosper or Perish (Population Growth & Food Rework)"
    / "main_menu/gfx/interface/icons"
)
TARGETS = (
    "modifier_types/global_population_capacity_modifier.dds",
    "modifier_types/total_population_capacity_modifier.dds",
    "map_modes/pp_population_capacity.dds",
)


def main() -> None:
    with Image.open(SOURCE) as source:
        icon = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    for relative in TARGETS:
        target = ICONS / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        icon.save(target, format="DDS", pixel_format="DXT5")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
