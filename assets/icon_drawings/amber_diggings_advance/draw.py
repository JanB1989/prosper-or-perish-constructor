"""Amber Regale (advance pp_amber_diggings): a still life of what the diggings are for. A big clear lump of amber with an
insect caught in it, on a clod of the blue earth, an iron-shod spade behind, small lumps at the foot.

Advance icons are still lifes without the building icons' black outline (vanilla efficient_mining, debt_and_loans).
The DDS goes where the game reads advance icons, in the size the interface pass wants. Run from the constructor:

  uv run python assets/icon_drawings/amber_diggings_advance/draw.py [--preview <png>]

Local helpers: ``lump`` (a smooth, glowing take on amber_collector's amber), ``insect``, ``spade``, ``clod``.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from eu5_building_pipeline.dds import encode_dds, fit
from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.finalize import grade, soften

SEED = 41
SIDE = 256  # interface_dds.ADVANCE_MAX_SIDE
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "mod/pp/main_menu/gfx/interface/advance/amber_diggings.dds"

GOLD = ((255, 204, 84), (222, 124, 18), (112, 40, 4))
ORANGE = ((252, 170, 56), (200, 84, 12), (96, 28, 4))
HONEY = ((255, 222, 120), (232, 150, 36), (128, 60, 8))


def rounded(ic: Icon, pts) -> Image.Image:
    """Polygon mask with its corners melted, so a lump has no facets."""
    soft = ic.poly_mask(pts).filter(ImageFilter.GaussianBlur(14))
    return soft.point(lambda v: 255 if v > 128 else 0).filter(ImageFilter.GaussianBlur(1.2))


def lump(ic: Icon, cx: float, cy: float, r: float, pal) -> Image.Image:
    """A translucent lump: dark rim, a body glowing away from the light, a pale crescent where light leaves it, a soft
    gloss at the upper left. Returns the body mask, for what is caught inside."""
    lit, mid, dark = pal
    pts = ic.jitter(cx, cy, r, r * 0.84, 20, 0.07)
    rim = rounded(ic, pts)
    ic.fill(rim, dark, tuple(int(v * 0.6) for v in dark), radial=(cx, cy, r * 1.2), noise=0.1)
    body = rim.filter(ImageFilter.MinFilter(int(max(3, r * 0.06)) | 1)).filter(ImageFilter.GaussianBlur(2))
    ic.fill(body, lit, tuple(int(a * 0.55 + b * 0.45) for a, b in zip(mid, dark)), radial=(cx + r * 0.2, cy + r * 0.24, r * 1.05), noise=0.12)
    # light leaving the far side
    glow = ic.mask("ellipse", (cx - r * 0.2, cy + r * 0.28, cx + r * 0.86, cy + r * 0.78))
    ic.shade(ic.intersect(glow, body), lit, 0.55, blur=r * 0.08)
    # gloss
    gloss = ic.mask("ellipse", (cx - r * 0.72, cy - r * 0.62, cx - r * 0.08, cy - r * 0.26))
    ic.shade(ic.intersect(gloss, body), (255, 250, 232), 0.75, blur=r * 0.05)
    return body


def insect(ic: Icon, x: float, y: float, s: float, clip: Image.Image) -> None:
    """A small fly caught in the resin: dark body, legs, two pale wings."""
    def paint(d):
        for dx, dy in ((-1.1, -0.9), (-1.3, 0.1), (-0.9, 1.0), (1.0, -1.0), (1.3, 0.0), (0.9, 1.1)):
            d.line([(x, y), (x + dx * s * 0.8, y + dy * s * 0.5), (x + dx * s * 1.2, y + dy * s * 0.9)], fill=(50, 22, 6, 225), width=4)
        d.ellipse((x - s * 0.34, y - s * 0.72, x + s * 0.34, y + s * 0.72), fill=(44, 20, 6, 245))
        d.ellipse((x - s * 0.26, y - s * 1.08, x + s * 0.26, y - s * 0.62), fill=(36, 16, 4, 245))
        d.polygon([(x + s * 0.1, y - s * 0.34), (x + s * 1.2, y - s * 0.7), (x + s * 1.1, y + s * 0.1)], fill=(255, 236, 190, 135))
        d.polygon([(x - s * 0.1, y - s * 0.34), (x - s * 1.2, y - s * 0.7), (x - s * 1.1, y + s * 0.1)], fill=(255, 236, 190, 135))

    ic.overlay(paint, clip)


def spade(ic: Icon) -> None:
    """A spade standing behind the clod, blade up, shod with iron."""
    foot, top = np.array((540.0, 700.0)), np.array((770.0, 250.0))
    d = (top - foot) / np.linalg.norm(top - foot)
    n = np.array([-d[1], d[0]])
    ic.line([tuple(foot), tuple(top)], 36, (40, 26, 14))
    ic.line([tuple(foot), tuple(top)], 26, (150, 108, 66))
    ic.line([tuple(foot + n * 6), tuple(top + n * 6)], 8, (204, 164, 112, 190))
    s0 = top - d * 16
    # long narrow blade, rounded to a point: wood above, iron shoe at the working end
    edge = [(-30, 0), (-66, 26), (-74, 120), (-66, 200), (-40, 262), (0, 292), (40, 262), (66, 200), (74, 120), (66, 26), (30, 0)]
    blade = [tuple(s0 + n * a + d * b) for a, b in edge]
    ic.fill(ic.poly_mask(blade), "#a6865c", "#553c20", noise=0.3)
    shoe = [tuple(s0 + n * a + d * b) for a, b in edge if b >= 120]
    ic.fill(ic.poly_mask(shoe), "#b0b4ba", "#4a4f57", noise=0.2)
    ic.line([tuple(s0 - n * 74 + d * 120), tuple(s0 + n * 74 + d * 120)], 6, (30, 30, 34, 220))
    ic.line(blade + [blade[0]], 6, (28, 20, 12, 240))


def clod(ic: Icon) -> None:
    """A wedge of blue earth, broad at the foot, with a soft contact shadow."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (90, 790, 940, 930)), (10, 8, 6), 0.5, blur=26)
    x0, x1, base, top = 100, 924, 878, 470
    cx, hw = (x0 + x1) / 2, (x1 - x0) / 2
    shape = [(x0, base)] + [(cx + hw * u, base - (base - top) * math.sqrt(max(0.0, 1 - u * u)) ** 0.9 * rnd.uniform(0.95, 1.04))
                            for u in np.linspace(-0.98, 0.98, 20)] + [(x1, base)]
    m = ic.poly_mask(shape)
    ic.fill(m, "#8a9cac", "#27343f", radial=(cx - hw * 0.4, top + 20, hw * 1.6), noise=0.42, chroma=0.1)
    rows = []
    for _ in range(46):
        u = rnd.uniform(-1, 1)
        y = base - (base - top) * math.sqrt(max(0.0, 1 - u * u)) * rnd.uniform(0.0, 0.92)
        r = rnd.uniform(26, 52)
        rows.append((cx + u * hw * 0.92, y, r, ic.jitter(0, 0, r, r * 0.72, rnd.randint(7, 9), 0.17), rnd.uniform(0.82, 1.12)))
    rows.sort(key=lambda it: it[1])

    def paint(d):
        for x, y, r, shp, tone in rows:
            d.polygon([(x + px * 1.05 + r * 0.1, y + py * 1.05 + r * 0.15) for px, py in shp], fill=(14, 22, 30, 130))
            d.polygon([(x + px, y + py) for px, py in shp], fill=(int(88 * tone), int(106 * tone), int(122 * tone), 255))
            d.polygon([(x + px * 0.6 - r * 0.2, y + py * 0.6 - r * 0.2) for px, py in shp],
                      fill=(int(136 * tone), int(156 * tone), int(170 * tone), 170))

    ic.overlay(paint, m)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx + hw * 0.15, top + 80, x1 + 90, base + 60))), (10, 16, 22), 0.45, blur=36)
    ic.overlay(lambda d: d.line(shape + [shape[0]], fill=(16, 20, 26, 230), width=5, joint="curve"))


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    ic.grade["gamma"] = 0.82
    spade(ic)
    clod(ic)
    # the big lump sits in the clod's top, its own shadow first
    ic.shade(ic.mask("ellipse", (210, 560, 740, 730)), (8, 8, 10), 0.55, blur=24)
    body = lump(ic, 470, 440, 262, GOLD)
    insect(ic, 494, 452, 70, body)
    lump(ic, 170, 800, 86, ORANGE)
    lump(ic, 812, 786, 92, HONEY)
    lump(ic, 650, 858, 58, GOLD)
    lump(ic, 330, 872, 46, HONEY)


def finished(ic: Icon) -> Image.Image:
    """Colour grade and soften as the building icons get them, no outline, fitted into the vanilla frame."""
    art = soften(grade(ic.image, ic.grade["mute"], ic.grade["gamma"], ic.grade["light"]), ic.grade["soften"])
    art = art.crop(art.getbbox())
    inner = SIDE - 16
    scale = inner / max(art.size)
    art = fit(art, (max(1, round(art.width * scale)), max(1, round(art.height * scale))))
    canvas = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    canvas.alpha_composite(art, ((SIDE - art.width) // 2, (SIDE - art.height) // 2))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", type=Path, help="write a PNG here instead of the DDS")
    args = ap.parse_args()
    ic = Icon(seed=SEED)
    draw(ic)
    image = finished(ic)
    if args.preview:
        sheet = Image.new("RGBA", (SIDE + 90, SIDE + 12), (60, 60, 70, 255))
        sheet.alpha_composite(image, (6, 6))
        sheet.alpha_composite(image.resize((64, 64), Image.LANCZOS), (SIDE + 16, 6))
        sheet.save(args.preview)
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encode_dds(image, "DXT5"))
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
