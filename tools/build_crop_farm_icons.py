"""Compose the 32 crop farm building icons: 8 crop chains x 4 tiers.

Each icon is a tier background (farm village, farmstead, rotations, model farm) fitted to ~480 px, with the crop's
trade-good badge on a medallion in the bottom-right corner. The medallion ring carries the tier colour (none, bronze,
silver, gold), so every (tier, crop) pair reads apart even though the backgrounds repeat across crops.

Usage:
    uv run python tools/build_crop_farm_icons.py                  # compose PNGs + contact sheet
    uv run python tools/build_crop_farm_icons.py --import-sources # first copy the source art into the repo
    uv run python tools/build_crop_farm_icons.py --check          # verify outputs: 512x512 RGBA, pairwise unique

The sources live in assets/icons/crop_farms/sources/ so the repo owns them. --import-sources converts the vanilla art
(read from the vanilla root in constructor.load_order[.local].toml) and copies the repo tier backgrounds; a hand-painted
replacement for any source can be dropped into that folder under the same name. Same inputs give the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import tomllib

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "assets/icons/crop_farms/sources"
ICONS = ROOT / "blueprints/accepted/assets/icons"
SHEET = ROOT / "docs/images/crop_farm_icons.png"

SIZE = 512
BACKGROUND_SIZE = 480
BADGE_SIZE = 200
MEDALLION = 228  # medallion diameter behind the badge
MARGIN = 6  # medallion distance from the canvas edge
SUPERSAMPLE = 4

# stem -> trade-good badge
STEMS = {
    "wheat": "wheat",
    "rice": "rice",
    "millet": "millet",
    "maize": "maize",
    "legume": "legumes",
    "potato": "potato",
    "olive": "olives",
    "cattle": "livestock",
}
# (key suffix, background source, ring colour or None)
TIERS = (
    ("farm", "farming_village.png", None),
    ("farmstead", "husbandry_farmstead.png", (176, 110, 58)),  # bronze
    ("rotations", "farming_village_rotations.png", (196, 204, 212)),  # silver
    ("model_farm", "model_farm.png", (226, 182, 62)),  # gold
)
SHEET_CELL = 128


def keys() -> list[str]:
    return [f"{stem}_{suffix}" for stem in STEMS for suffix, _, _ in TIERS]


# --- source import -------------------------------------------------------------------------------------------------


def _vanilla_root() -> Path:
    for name in ("constructor.load_order.local.toml", "constructor.load_order.toml"):
        path = ROOT / name
        if not path.exists():
            continue
        value = tomllib.loads(path.read_text(encoding="utf-8")).get("paths", {}).get("vanilla_root")
        if isinstance(value, str):
            if len(value) > 2 and value[1] == ":":  # Windows drive path -> WSL mount
                value = f"/mnt/{value[0].lower()}/{value[3:].replace(chr(92), '/')}"
            return Path(value)
    raise SystemExit("no [paths] vanilla_root in constructor.load_order(.local).toml")


def import_sources() -> None:
    SOURCES.mkdir(parents=True, exist_ok=True)
    icons = _vanilla_root() / "game/main_menu/gfx/interface/icons"
    vanilla = {"farming_village.png": icons / "buildings/farming_village.dds"}
    for good in STEMS.values():
        vanilla[f"icon_goods_{good}.png"] = icons / f"trade_goods/icon_goods_{good}.dds"
    for name, path in vanilla.items():
        with Image.open(path) as image:
            image.convert("RGBA").save(SOURCES / name)
        print(f"imported {path} -> {(SOURCES / name).relative_to(ROOT)}")
    for _, name, ring in TIERS:
        if ring is None:
            continue
        path = ICONS / name
        with Image.open(path) as image:
            image.convert("RGBA").save(SOURCES / name)
        print(f"imported {path.relative_to(ROOT)} -> {(SOURCES / name).relative_to(ROOT)}")


# --- composition ---------------------------------------------------------------------------------------------------


def _load(name: str) -> Image.Image:
    with Image.open(SOURCES / name) as image:
        return image.convert("RGBA")


def _fit(image: Image.Image, size: int) -> Image.Image:
    """Crop to the opaque box and scale the longest side to `size` (up or down)."""
    image = image.crop(image.getbbox())
    scale = size / max(image.size)
    target = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(target, Image.Resampling.LANCZOS)


def _shadow(image: Image.Image, blur: int, opacity: int) -> Image.Image:
    """A soft drop shadow like vanilla's icon art (same idea as tools/build_land_potential_icon.py)."""
    alpha = image.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * opacity // 255)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow.putalpha(alpha)
    return shadow


def _padded(image: Image.Image, pad: int) -> Image.Image:
    """Transparent padding so a blurred shadow is not clipped at the layer edge."""
    canvas = Image.new("RGBA", (image.width + 2 * pad, image.height + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(image, (pad, pad))
    return canvas


def _medallion(ring: tuple[int, int, int] | None) -> Image.Image:
    """Dark disc behind the badge; tier ring in bronze/silver/gold, a thin dark rim for the base tier."""
    big = MEDALLION * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    s = SUPERSAMPLE
    if ring is None:
        draw.ellipse((0, 0, big - 1, big - 1), fill=(38, 30, 22, 200), outline=(20, 15, 10, 230), width=3 * s)
    else:
        dark = tuple(c * 55 // 100 for c in ring)
        light = tuple(min(255, c + (255 - c) * 45 // 100) for c in ring)
        draw.ellipse((0, 0, big - 1, big - 1), fill=(*dark, 255))  # outer rim
        draw.ellipse((2 * s, 2 * s, big - 1 - 2 * s, big - 1 - 2 * s), fill=(*ring, 255))  # ring body
        draw.arc((4 * s, 4 * s, big - 1 - 4 * s, big - 1 - 4 * s), 200, 340, fill=(*light, 255), width=3 * s)  # sheen
        inner = 11 * s
        draw.ellipse((inner - s, inner - s, big - inner + s, big - inner + s), fill=(*dark, 255))  # inner rim
        draw.ellipse((inner, inner, big - inner, big - inner), fill=(38, 30, 22, 215))
    return image.resize((MEDALLION, MEDALLION), Image.Resampling.LANCZOS)


def compose(background: Image.Image, badge: Image.Image, ring: tuple[int, int, int] | None) -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    layer = _fit(background, BACKGROUND_SIZE)
    canvas.alpha_composite(layer, ((SIZE - layer.width) // 2, (SIZE - layer.height) // 2))

    medallion = _medallion(ring)
    mx = my = SIZE - MARGIN - MEDALLION
    pad = 16
    canvas.alpha_composite(_shadow(_padded(medallion, pad), 6, 170), (mx - pad + 4, my - pad + 6))
    canvas.alpha_composite(medallion, (mx, my))

    badge = _fit(badge, BADGE_SIZE)
    bx = mx + (MEDALLION - badge.width) // 2
    by = my + (MEDALLION - badge.height) // 2
    canvas.alpha_composite(_shadow(_padded(badge, pad), 5, 160), (bx - pad + 3, by - pad + 5))
    canvas.alpha_composite(badge, (bx, by))
    return canvas


def build() -> list[Path]:
    missing = [name for name in _source_names() if not (SOURCES / name).exists()]
    if missing:
        raise SystemExit(f"missing sources in {SOURCES.relative_to(ROOT)}: {missing}; run with --import-sources")
    backgrounds = {name: _load(name) for _, name, _ in TIERS}
    written: list[Path] = []
    for stem, good in STEMS.items():
        badge = _load(f"icon_goods_{good}.png")
        for suffix, background, ring in TIERS:
            path = ICONS / f"{stem}_{suffix}.png"
            compose(backgrounds[background], badge, ring).save(path, optimize=False)
            written.append(path)
    _contact_sheet()
    return written


def _source_names() -> list[str]:
    return [name for _, name, _ in TIERS] + [f"icon_goods_{good}.png" for good in STEMS.values()]


def _contact_sheet() -> None:
    """8 columns (crops) x 4 rows (tiers), 128 px cells on the dark UI grey."""
    sheet = Image.new("RGBA", (SHEET_CELL * len(STEMS), SHEET_CELL * len(TIERS)), (37, 44, 48, 255))
    for col, stem in enumerate(STEMS):
        for row, (suffix, _, _) in enumerate(TIERS):
            with Image.open(ICONS / f"{stem}_{suffix}.png") as icon:
                cell = icon.convert("RGBA").resize((SHEET_CELL, SHEET_CELL), Image.Resampling.LANCZOS)
            sheet.alpha_composite(cell, (col * SHEET_CELL, row * SHEET_CELL))
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(SHEET, optimize=False)


# --- check ---------------------------------------------------------------------------------------------------------


def check() -> int:
    """Every icon exists, is 512x512 RGBA, and differs from every other in file bytes and in pixels."""
    problems: list[str] = []
    seen_files: dict[str, str] = {}
    seen_pixels: dict[str, str] = {}
    for key in keys():
        path = ICONS / f"{key}.png"
        if not path.exists():
            problems.append(f"missing {path.relative_to(ROOT)}")
            continue
        with Image.open(path) as image:
            if image.size != (SIZE, SIZE) or image.mode != "RGBA":
                problems.append(f"{key}: {image.size} {image.mode}, expected ({SIZE}, {SIZE}) RGBA")
            pixels = hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen_files:
            problems.append(f"{key}: same file bytes as {seen_files[digest]}")
        if pixels in seen_pixels:
            problems.append(f"{key}: same pixels as {seen_pixels[pixels]}")
        seen_files.setdefault(digest, key)
        seen_pixels.setdefault(pixels, key)
    for problem in problems:
        print(problem)
    print(f"{len(keys())} icons checked, {len(seen_files)} unique files, {len(problems)} problems")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--import-sources", action="store_true", help="copy vanilla/repo source art first")
    parser.add_argument("--check", action="store_true", help="only verify the written icons")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.import_sources:
        import_sources()
    for path in build():
        print(path.relative_to(ROOT))
    print(SHEET.relative_to(ROOT))
    return check()


if __name__ == "__main__":
    sys.exit(main())
