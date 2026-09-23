"""Compose the Land Potential chip icon: vanilla's terrain plots, a green arrow rising out of them behind a sheaf of
wheat. The sources are vanilla art (location_icons/terrain, trade_goods/icon_goods_wheat, flat_icons/arrow_up)."""

from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "assets/icons/land_potential/sources"
PREVIEW = ROOT / "assets/icons/land_potential/land_potential.png"
TARGET = (
    ROOT
    / "mod/Prosper or Perish (Population Growth & Food Rework)"
    / "main_menu/gfx/interface/icons/location_icons/pp_land_potential.dds"
)
SIZE = 128
# (source, longest side, top-left corner), drawn in order: land, arrow behind the crop, crop
LAYERS = (("terrain.png", 118, (0, 14)), ("arrow_up.png", 80, (52, -2)), ("wheat.png", 80, (8, 6)))


def _fit(image: Image.Image, size: int) -> Image.Image:
    image = image.crop(image.getbbox())
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image


def _shadow(image: Image.Image) -> Image.Image:
    """A soft drop shadow like vanilla's icon art, so the layers separate at chip size."""
    alpha = image.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: v * 150 // 255)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow.putalpha(alpha)
    return shadow


def compose() -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for name, size, (x, y) in LAYERS:
        with Image.open(SOURCES / name) as source:
            layer = _fit(source.convert("RGBA"), size)
        canvas.alpha_composite(_shadow(layer), (x + 3, y + 4))
        canvas.alpha_composite(layer, (x, y))
    return canvas


def main() -> None:
    icon = compose()
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    icon.save(PREVIEW)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    icon.save(TARGET, format="DDS", pixel_format="DXT5")
    print(TARGET.relative_to(ROOT))


if __name__ == "__main__":
    main()
