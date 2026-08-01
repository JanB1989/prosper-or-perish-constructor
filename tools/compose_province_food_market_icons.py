from __future__ import annotations

import colorsys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "assets" / "icons" / "province_food_market" / "sources"
OUTPUT_DIR = ROOT / "assets" / "icons" / "trade_goods"
ILLUSTRATION_OUTPUT_DIR = OUTPUT_DIR / "illustrations"
MASTER_SIZE = 512
ILLUSTRATION_SIZE = (1080, 440)


def _open(name: str) -> Image.Image:
    return Image.open(SOURCE_DIR / name).convert("RGBA")


def _trim(image: Image.Image) -> Image.Image:
    alpha_box = image.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError("Source image has no visible pixels")
    return image.crop(alpha_box)


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fitted = _trim(image).copy()
    scale = min(size[0] / fitted.width, size[1] / fitted.height)
    dimensions = (round(fitted.width * scale), round(fitted.height * scale))
    return fitted.resize(dimensions, Image.Resampling.LANCZOS)


def _red_apple(image: Image.Image) -> Image.Image:
    image = image.copy()
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
            is_apple_body = y >= image.height * 0.22 and 0.12 <= hue <= 0.48 and saturation >= 0.18
            if not is_apple_body:
                continue
            new_red, new_green, new_blue = colorsys.hsv_to_rgb(0.0, max(0.62, saturation), value)
            pixels[x, y] = (
                round(new_red * 255),
                round(new_green * 255),
                round(new_blue * 255),
                alpha,
            )
    return image


def _paste_center(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    x = left + (right - left - image.width) // 2
    y = top + (bottom - top - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return x, y


def _paste_badge(canvas: Image.Image, badge: Image.Image, item: Image.Image, position: tuple[int, int]) -> None:
    x = min(position[0] + item.width - badge.width + 6, MASTER_SIZE - badge.width - 8)
    y = min(position[1] + item.height - badge.height + 6, MASTER_SIZE - badge.height - 8)
    canvas.alpha_composite(badge, (x, y))


def _draw_arrow(canvas: Image.Image) -> None:
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    points = [(218, 241), (264, 241), (264, 221), (298, 256), (264, 291), (264, 271), (218, 271)]
    shadow_draw.polygon([(x + 5, y + 6) for x, y in points], fill=(20, 13, 6, 205))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    canvas.alpha_composite(shadow)

    draw = ImageDraw.Draw(canvas)
    draw.polygon(points, fill=(224, 187, 105, 255), outline=(105, 69, 27, 255), width=5)
    draw.line(points + [points[0]], fill=(250, 224, 161, 210), width=2, joint="curve")


def _compose(*, sales: bool) -> Image.Image:
    canvas = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE), (0, 0, 0, 0))
    apple = _fit(_open("local_food.png"), (225, 265))
    victuals = _fit(_open("victuals.png"), (235, 235))
    plus = _fit(_open("goods_positive.png").crop((38, 34, 64, 64)), (74, 74))
    minus = _fit(_open("goods_negative.png").crop((38, 43, 64, 61)), (74, 52))

    if sales:
        left = _red_apple(apple)
        right = victuals
        right_position = _paste_center(canvas, right, (262, 110, 502, 410))
        _paste_center(canvas, left, (10, 110, 250, 410))
        _paste_badge(canvas, plus, right, right_position)
    else:
        left = victuals
        right = apple
        left_position = _paste_center(canvas, left, (10, 110, 250, 410))
        _paste_center(canvas, right, (262, 110, 502, 410))
        _paste_badge(canvas, minus, left, left_position)

    _draw_arrow(canvas)
    return canvas


def _compose_illustration(icon: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", ILLUSTRATION_SIZE, (0, 0, 0, 0))
    artwork = _fit(icon, (960, 400))
    _paste_center(canvas, artwork, (0, 0, *ILLUSTRATION_SIZE))
    return canvas


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ILLUSTRATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "icon_goods_province_food_sales.png": _compose(sales=True),
        "icon_goods_province_food_purchase.png": _compose(sales=False),
    }
    for name, image in outputs.items():
        image.save(OUTPUT_DIR / name)
        _compose_illustration(image).save(ILLUSTRATION_OUTPUT_DIR / name)


if __name__ == "__main__":
    main()
