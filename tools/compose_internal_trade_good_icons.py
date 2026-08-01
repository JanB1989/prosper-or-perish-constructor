from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets" / "icons" / "trade_goods"
ILLUSTRATION_OUTPUT_DIR = OUTPUT_DIR / "illustrations"
ILLUSTRATION_SIZE = (1080, 440)

ICON_SOURCES = {
    "local_food": ROOT / "assets" / "icons" / "province_food_market" / "sources" / "local_food.png",
    "manual_labor_cost": ROOT / "assets" / "icons" / "manual_labor_cost" / "sources" / "employees.png",
    "offset": ROOT / "assets" / "icons" / "offset" / "sources" / "balance.png",
}
ILLUSTRATION_SOURCES = {
    "local_food": ROOT / "assets" / "icons" / "local_food" / "sources" / "local_food_illustration.png",
}


def _centered_icon_illustration(icon: Image.Image) -> Image.Image:
    illustration = Image.new("RGBA", ILLUSTRATION_SIZE, (0, 0, 0, 0))
    artwork = icon.resize((400, 400), Image.Resampling.LANCZOS)
    position = (
        (ILLUSTRATION_SIZE[0] - artwork.width) // 2,
        (ILLUSTRATION_SIZE[1] - artwork.height) // 2,
    )
    illustration.alpha_composite(artwork, position)
    return illustration


def _local_food_illustration(source: Image.Image) -> Image.Image:
    return ImageOps.fit(
        source,
        ILLUSTRATION_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.45),
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ILLUSTRATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for good, source_path in ICON_SOURCES.items():
        icon = Image.open(source_path).convert("RGBA")
        filename = f"icon_goods_{good}.png"
        icon.save(OUTPUT_DIR / filename)

        if good == "local_food":
            source = Image.open(ILLUSTRATION_SOURCES[good]).convert("RGBA")
            illustration = _local_food_illustration(source)
        else:
            illustration = _centered_icon_illustration(icon)
        illustration.save(ILLUSTRATION_OUTPUT_DIR / filename)


if __name__ == "__main__":
    main()
