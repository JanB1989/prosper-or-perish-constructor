"""Draw the Sea Raid casus belli icon and the Coastal Raid unit ability icons from vanilla icon art.

- `casus_belli/cb_pp_naval_raid.dds` (cb_pp_naval_raid, "Sea Raid"): vanilla's casus belli parchment with the boat on
  waves of `unit_types/maritime_presence` and the privateers' skull and crossbones (`location_icons/privateer`).
- `unit_ability/pp_coastal_raid.dds` (pp_coastal_raid, "Coastal Raid", a toggle): the boat of
  `military_objectives/hunt_navies` with the shackles of `trade_goods/icon_goods_slaves_goods` where vanilla's
  hunt_navies has its arrow (sailors land and carry off captives).
- `unit_ability/not_pp_coastal_raid.dds`: the same with vanilla's red cross from `not_hunt_pirates`. The unit window
  shows a toggle ability's `not_<key>` texture while it is off (`UnitActionItem.GetNotTexture`), `<key>` while it is on.

All three are 128 px DXT5 with a full mip chain, like their vanilla neighbours. The parchment is rebuilt from vanilla's
casus belli icons (per pixel the value most icons share; the few centre pixels every icon covers are filled smoothly),
so no vanilla object shows through.

Rerun after a game update:

    uv run python tools/build_sea_raid_icons.py                 # write the DDS files into the mod
    uv run python tools/build_sea_raid_icons.py --preview DIR   # also PNGs and a sheet next to the vanilla siblings
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

from prosper_or_perish_constructor.good_icons import write_dxt5
from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
ICONS = "main_menu/gfx/interface/icons"
SIZE = 128
TARGETS = {
    "casus_belli/cb_pp_naval_raid": "sea_raid",
    "unit_ability/pp_coastal_raid": "coastal_raid",
    "unit_ability/not_pp_coastal_raid": "not_coastal_raid",
}
SIBLINGS = {
    "casus_belli": ["cb_anti_piracy", "cb_slave_raiding", "naval", "superiority_raiding", "cb_exploration"],
    "unit_ability": ["hunt_pirates", "not_hunt_pirates", "sell_prisoners_into_slavery", "raid_clan_holdings", "scorch_earth"],
}


def _rgba(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def _bbox_crop(image: Image.Image) -> Image.Image:
    box = image.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return image.crop(box) if box else image


def _fit(image: Image.Image, width: int) -> Image.Image:
    """Scale to a given width (aspect kept), on the full-size source for a clean downscale."""
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _component(image: Image.Image, seed: tuple[int, int]) -> Image.Image:
    """Only the connected opaque part of `image` that contains `seed` (drops the other elements of an icon)."""
    rgba = np.asarray(image).copy()
    labels, _ = ndimage.label(rgba[..., 3] > 0)
    keep = labels == labels[seed[1], seed[0]]
    rgba[~keep] = 0
    return _bbox_crop(Image.fromarray(rgba))


def _shadow(layer: Image.Image, opacity: float = 0.45, blur: float = 1.6) -> Image.Image:
    shadow = Image.new("RGBA", layer.size, (20, 12, 6, 255))
    shadow.putalpha(layer.getchannel("A").point(lambda a: int(a * opacity)).filter(ImageFilter.GaussianBlur(blur)))
    return shadow


def _place(canvas: Image.Image, layer: Image.Image, at: tuple[int, int], shadow: bool) -> None:
    sheet = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sheet.alpha_composite(layer, at)
    if shadow:
        canvas.alpha_composite(_shadow(sheet), (1, 2))
    canvas.alpha_composite(sheet)


def parchment(icons: Path) -> Image.Image:
    """Vanilla's casus belli parchment without any object on it."""
    files = [f for f in sorted((icons / "casus_belli").glob("*.dds")) if f.stem not in ("_default", "casus_belli_change")]
    stack = np.stack([np.asarray(_rgba(f), dtype=np.int16) for f in files])
    best = np.zeros(stack.shape[1:], dtype=np.int16)
    count = np.zeros(stack.shape[1:3], dtype=np.int32)
    for layer in stack:
        agree = (np.abs(stack - layer[None]).sum(-1) <= 6).sum(0)
        better = agree > count
        best[better] = layer[better]
        count[better] = agree[better]
    # the centre is covered in nearly every icon: fill it from the surrounding parchment (normalized blur, widening)
    good = count > 6
    out = best.astype(np.float64)
    for sigma in (2, 4, 8, 16):
        weight = ndimage.gaussian_filter(good.astype(np.float64), sigma)
        filled = np.stack([ndimage.gaussian_filter(out[..., c] * good, sigma) for c in range(4)], -1)
        fill = ~good & (weight > 0.25)
        out[fill] = filled[fill] / weight[fill, None]
        good = good | fill
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def red_cross(icons: Path) -> Image.Image:
    """Vanilla's red 'off' cross of the toggle abilities, cut out where not_<ability> differs from <ability>."""
    pairs = [("hunt_pirates", "not_hunt_pirates"), ("drill_army", "not_drill_army"), ("march_to_sound_of_guns", "not_march_to_sound_of_guns")]
    out = np.zeros((SIZE, SIZE, 4), dtype=np.int16)
    under = np.full((SIZE, SIZE), 256, dtype=np.int16)  # alpha of the art below the cross in the chosen pair
    for on, off in pairs:
        base = np.asarray(_rgba(icons / f"unit_ability/{on}.dds"), dtype=np.int16)
        cross = np.asarray(_rgba(icons / f"unit_ability/{off}.dds"), dtype=np.int16)
        differs = np.abs(cross - base).sum(-1) > 24
        better = differs & (base[..., 3] < under)
        out[better] = cross[better]
        under[better] = base[..., 3][better]
    # keep the cross only (its red body and the pixels next to it), not stray compression differences
    red = (out[..., 0] > 120) & (out[..., 1] < 90) & (out[..., 3] > 0)
    labels, n = ndimage.label(red)
    if n:
        sizes = ndimage.sum(red, labels, range(1, n + 1))
        red = labels == (int(np.argmax(sizes)) + 1)
    near = ndimage.binary_dilation(red, iterations=2)
    out[~near] = 0
    return Image.fromarray(out.astype(np.uint8))


def sea_raid(icons: Path, paper: Image.Image) -> Image.Image:
    canvas = paper.copy()
    boat = _fit(_bbox_crop(_rgba(icons / "unit_types/maritime_presence.dds")), 80)
    skull = _fit(_bbox_crop(_rgba(icons / "location_icons/privateer.dds")), 46)
    _place(canvas, boat, (17, 12), shadow=True)
    _place(canvas, skull, (64, 64), shadow=True)
    return canvas


def coastal_raid(icons: Path) -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    navies = _rgba(icons / "military_objectives/hunt_navies.dds")
    boat = _component(navies, (40, 70))  # the hull; the arrow is a separate piece
    shackles = _fit(_bbox_crop(_rgba(icons / "trade_goods/icon_goods_slaves_goods.dds")), 78)
    _place(canvas, _fit(boat, 96), (0, 2), shadow=False)
    _place(canvas, shackles, (SIZE - shackles.width - 1, SIZE - shackles.height - 3), shadow=True)
    return canvas


def not_coastal_raid(icons: Path, on: Image.Image) -> Image.Image:
    canvas = on.copy()
    canvas.alpha_composite(red_cross(icons))
    return canvas


def icons_for(vanilla_icons: Path) -> dict[str, Image.Image]:
    on = coastal_raid(vanilla_icons)
    return {
        "sea_raid": sea_raid(vanilla_icons, parchment(vanilla_icons)),
        "coastal_raid": on,
        "not_coastal_raid": not_coastal_raid(vanilla_icons, on),
    }


def preview(vanilla_icons: Path, built: dict[str, Image.Image], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, image in built.items():
        image.save(folder / f"{name}.png")
    rows = [
        ([_rgba(vanilla_icons / f"casus_belli/{n}.dds") for n in SIBLINGS["casus_belli"]], [built["sea_raid"]]),
        ([_rgba(vanilla_icons / f"unit_ability/{n}.dds") for n in SIBLINGS["unit_ability"]], [built["coastal_raid"], built["not_coastal_raid"]]),
    ]
    sizes = (128, 64, 40, 28)
    cell = 140
    width = 7 * cell + 10
    sheet = Image.new("RGBA", (width, len(rows) * 2 * cell), (46, 42, 38, 255))
    draw = ImageDraw.Draw(sheet)
    for r, (vanilla, ours) in enumerate(rows):
        y = r * 2 * cell + 6
        for i, image in enumerate(vanilla + ours):
            x = i * cell + 6
            sheet.alpha_composite(image, (x, y))
            if i >= len(vanilla):
                draw.rectangle([x - 3, y - 3, x + 130, y + 130], outline=(230, 190, 90, 255))
            sx = x
            for s in sizes[1:]:
                sheet.alpha_composite(image.resize((s, s), Image.Resampling.LANCZOS), (sx, y + 136))
                sx += s + 4
    sheet.save(folder / "sea_raid_icons_sheet.png")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write PNGs and a sheet next to the vanilla siblings into this folder")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    vanilla_icons = vanilla_root(ROOT, ROOT / "constructor.toml") / "game" / ICONS
    built = icons_for(vanilla_icons)
    if args.preview:
        preview(vanilla_icons, built, args.preview)
    if not args.no_write:
        with tempfile.TemporaryDirectory() as tmp:
            for relative, name in TARGETS.items():
                png = Path(tmp) / f"{name}.png"
                built[name].save(png)
                target = MOD / ICONS / f"{relative}.dds"
                write_dxt5(png, target, (SIZE, SIZE))
                print(target.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
