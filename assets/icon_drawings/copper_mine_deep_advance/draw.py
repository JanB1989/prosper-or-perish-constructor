"""Reverberatory Copper Smelting (advance pp_reverberatory_copper): a still life of what the advance is about. A low brick
furnace vault with iron buckstays, its arched door open on a white-hot hearth and a pool of molten copper, an iron rabble
leaning into the fire, green ore on the left and a stack of finished copper cakes on the right.

Advance icons are still lifes without the building icons' black outline (vanilla efficient_mining, debt_and_loans).
The DDS goes where the game reads advance icons, in the size the interface pass wants. Run from the constructor:

  uv run python assets/icon_drawings/copper_mine_deep_advance/draw.py [--preview <png>]

Local helpers: ``bricks`` (lead_mine_cupola_smelting), ``cake`` (copper_mine_deep), ``tint``, ``union``, ``flame``.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.dds import encode_dds, fit
from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.finalize import grade, soften

SEED = 37
SIDE = 256  # interface_dds.ADVANCE_MAX_SIDE
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "mod/pp/main_menu/gfx/interface/advance/copper_mine_deep.dds"

MAL = "#62b08e"  # malachite, lit
MAL_DARK = "#1c4a3a"
CU = "#d07a44"  # native copper, lit
CU_DARK = "#5a2614"
BRICK = ("#b06a4c", "#5a3024")
IRON = (40, 38, 42)
IRON_LT = (130, 128, 134)
EDGE = (24, 14, 10, 235)


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def bricks(ic: Icon, mask: Image.Image, box, colors=BRICK, course: float = 34, brick: float = 84) -> None:
    """Brickwork inside ``mask``: per-brick tone, dark mortar courses, stagger."""
    x0, y0, x1, y1 = box
    ic.fill(mask, colors[0], colors[1], (x0, x1), vertical=False, noise=0.2, chroma=0.06)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    for k, y in enumerate(np.arange(y0, y1, course)):
        off = (k % 2) * brick / 2
        for x in np.arange(x0 - brick + off, x1, brick):
            t = rnd(-1, 1)
            d.rectangle((x + 3, y + 3, x + brick - 3, y + course - 3),
                        fill=(20, 8, 4, int(-t * 70)) if t < 0 else (255, 220, 190, int(t * 44)))
            d.line([(x, y), (x, y + course)], fill=(44, 26, 18, 170), width=5)
        d.line([(x0, y), (x1, y)], fill=(44, 26, 18, 180), width=5)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), mask)
    ic.image.alpha_composite(clip)


def flame(ic: Icon, cx, base, w, h, lean=0.0, clip=None) -> None:
    """Tongue of flame; the brighter inner tongue sits low in the outer one."""
    for (c1, c2), sw, sh in ((("#ffb648", "#d2481a"), 1.0, 1.0), (("#fff4c8", "#ffb84c"), 0.52, 0.64)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        m = ic.poly_mask(left + right[::-1])
        ic.fill(ic.intersect(m, clip) if clip is not None else m, c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def cake(ic: Icon, cx: float, cy: float, rx: float, h: float = 40) -> None:
    """Finished copper cake: a flat round disc seen from above, bright dished top, dark rim."""
    ry = rx * 0.38
    side = union(ic.mask("ellipse", (cx - rx, cy - ry + h, cx + rx, cy + ry + h)),
                 ic.mask("rectangle", (cx - rx, cy, cx + rx, cy + h)))
    ic.fill(side, "#c26430", "#54220e", (cx - rx, cx + rx), vertical=False, noise=0.12)
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry + h, cx + rx, cy + ry + h), 0, 180, fill=EDGE, width=6))
    for x in (cx - rx, cx + rx):
        ic.line([(x, cy), (x, cy + h)], 6, EDGE)
    top = ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    ic.fill(top, "#ffb878", "#c86a30", radial=(cx - rx * 0.35, cy - ry * 0.35, rx * 1.5), noise=0.14, chroma=0.05)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.66, cy - ry * 0.62, cx + rx * 0.66, cy + ry * 0.66)), top, (96, 40, 20), 0.3, 6)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.46, cy - ry * 0.36, cx + rx * 0.2, cy + ry * 0.2)), top, (255, 232, 200), 0.5, 7)
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(48, 24, 12, 225), width=6))


def furnace(ic: Icon) -> None:
    """A low brick vault with buckstays; its arched door shows the white-hot hearth and the molten copper pool."""
    X0, X1, TOP, BASE = 112, 912, 92, 800
    body = union(ic.mask("rectangle", (X0, TOP + 230, X1, BASE)),
                 ic.mask("chord", (X0, TOP, X1, TOP + 460), start=180, end=360))
    bricks(ic, body, (X0, TOP, X1, BASE))
    tint(ic, ic.mask("rectangle", (X0 + 520, TOP, X1 + 40, BASE)), body, (0, 0, 0), 0.4, 40)  # away from the light
    tint(ic, ic.mask("chord", (X0 + 20, TOP + 8, X1 - 120, TOP + 300), start=190, end=300), body, (255, 228, 196), 0.28, 16)
    tint(ic, ic.mask("rectangle", (X0, TOP, X1, TOP + 90)), body, (24, 16, 12), 0.35, 24)  # soot on the crown

    # the door: a ring of arch bricks around the fire, fire behind, pool at the bottom
    DX0, DX1, DTOP, DBASE = 272, 736, 300, 772
    ring = union(ic.mask("ellipse", (DX0 - 48, DTOP - 48, DX1 + 48, DTOP + (DX1 - DX0) + 48)),
                 ic.mask("rectangle", (DX0 - 48, DTOP + (DX1 - DX0) / 2, DX1 + 48, DBASE)))
    door = union(ic.mask("ellipse", (DX0, DTOP, DX1, DTOP + (DX1 - DX0))),
                 ic.mask("rectangle", (DX0, DTOP + (DX1 - DX0) / 2, DX1, DBASE)))
    tint(ic, ring, body, (255, 120, 40), 0.42, 46)  # the bricks catch the glow
    ic.fill(ImageChops.subtract(ring, door), "#c88a64", "#6a3a26", (DX0, DX1), vertical=False, noise=0.2)
    cx = (DX0 + DX1) / 2
    cy = DTOP + (DX1 - DX0) / 2
    for a in np.linspace(math.pi, 2 * math.pi, 12):  # voussoir joints
        ic.line([(cx + math.cos(a) * 232, cy + math.sin(a) * 232), (cx + math.cos(a) * 280, cy + math.sin(a) * 280)], 5, (44, 24, 16, 200))
    ic.fill(door, "#fff0b4", "#a82e0c", radial=(cx, 640, 330), noise=0.1, chroma=0.04)
    tint(ic, ic.mask("ellipse", (DX0 - 30, DTOP - 60, DX1 + 30, DTOP + 150)), door, (40, 8, 2), 0.55, 30)  # dark roof of the hearth
    for fx, w, h, lean in ((330, 100, 190, 70), (430, 128, 270, 90), (548, 120, 250, 96), (654, 96, 170, 60)):
        flame(ic, fx, 706, w, h, lean, door)
    # molten copper pool across the hearth
    pool = ic.mask("ellipse", (DX0 + 8, 664, DX1 - 8, 776))
    pool = ic.intersect(pool, door)
    ic.fill(pool, "#fff2c0", "#f0701c", radial=(cx - 30, 704, 240), noise=0.08, chroma=0.03)
    for a, b, w, col in (((330, 716), (500, 706), 8, (255, 252, 226, 220)), ((540, 736), (668, 726), 6, (255, 244, 200, 190)), ((400, 748), (520, 742), 5, (214, 92, 28, 170))):
        ic.line([a, b], w, col)
    ic.overlay(lambda d: d.arc((DX0, DTOP, DX1, DTOP + (DX1 - DX0)), 180, 360, fill=EDGE, width=9))
    for x in (DX0, DX1):
        ic.line([(x, cy), (x, DBASE)], 9, EDGE)
    ic.line([(DX0 - 60, DBASE), (DX1 + 60, DBASE)], 22, (42, 40, 44))  # iron sill
    ic.line([(DX0 - 60, DBASE - 7), (DX1 + 60, DBASE - 7)], 5, (150, 110, 84, 200))

    # buckstays and the tie rod hold the vault together
    for x, top in ((168, 322), (864, 322)):
        ic.line([(x, top), (x, BASE + 6)], 28, IRON)
        ic.line([(x - 8, top + 6), (x - 8, BASE)], 6, IRON_LT)
        ic.ellipse((x - 20, top - 16, x + 20, top + 24), "#5a585c", "#232124", edge=4)
    ic.overlay(lambda d: d.arc((X0, TOP, X1, TOP + 460), 180, 360, fill=EDGE, width=7))
    ic.line([(X0, TOP + 230), (X0, BASE)], 7, EDGE)
    ic.line([(X1, TOP + 230), (X1, BASE)], 7, EDGE)


def tapping(ic: Icon) -> None:
    """Molten copper runs from the sill down a clay channel into a round sand mould, where a new cake glows."""
    ic.shade(ic.mask("ellipse", (340, 864, 620, 990)), (8, 6, 4), 0.5, blur=12)
    bed = ic.mask("ellipse", (352, 852, 610, 972))
    ic.fill(bed, "#a88e6a", "#4e3c28", radial=(440, 880, 240), noise=0.34, chroma=0.05)
    ic.overlay(lambda d: d.ellipse((352, 852, 610, 972), outline=EDGE, width=6))
    hot = ic.mask("ellipse", (392, 870, 570, 952))
    ic.fill(hot, "#fff3c4", "#ee6a18", radial=(480, 908, 104), noise=0.08, chroma=0.03)
    ic.line([(420, 910), (486, 892)], 7, (255, 254, 232, 220))
    ic.overlay(lambda d: d.ellipse((392, 870, 570, 952), outline=(120, 40, 12, 230), width=5))
    # the channel and the stream in it, over the sill
    ic.line([(500, 772), (488, 888)], 46, (46, 30, 22))
    ic.line([(500, 772), (488, 888)], 34, (120, 88, 66))
    ic.line([(500, 766), (488, 892)], 18, (252, 150, 56))
    ic.line([(497, 770), (487, 888)], 7, (255, 244, 196))


def rabble(ic: Icon) -> None:
    """The iron rake that stirs the charge, leaning into the fire from the lower left."""
    a, b = (66, 842), (438, 610)
    ic.line([a, b], 26, (24, 20, 22))
    ic.line([a, b], 16, (92, 88, 94))
    ic.line([(a[0] + 2, a[1] - 7), (b[0] + 2, b[1] - 7)], 5, (176, 174, 180, 210))
    ic.line([(438, 610), (466, 660)], 28, (40, 26, 22))  # the rake's head, glowing at the tip
    ic.line([(446, 624), (462, 652)], 12, (255, 170, 80))


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.94
    ic.grade["gamma"] = 0.86
    ic.shade(ic.mask("ellipse", (40, 770, 990, 980)), (10, 8, 6), 0.55, blur=26)
    furnace(ic)
    tapping(ic)
    rabble(ic)
    # green ore on the left, copper cakes on the right
    ic.shade(ic.mask("ellipse", (12, 880, 360, 1000)), (8, 6, 4), 0.5, blur=14)
    for x, y, r, cu in ((150, 800, 62, 0), (72, 856, 68, 0), (226, 846, 66, 0), (140, 880, 74, 1), (300, 906, 62, 0),
                        (52, 930, 64, 0), (192, 948, 74, 0), (306, 966, 50, 1), (110, 976, 48, 0)):
        if cu:
            ic.chunk(x, y, r, CU, CU_DARK, (255, 206, 158))
        else:
            ic.chunk(x, y, r, MAL, MAL_DARK, (214, 255, 230))
    ic.shade(ic.mask("ellipse", (560, 880, 1010, 1000)), (8, 6, 4), 0.5, blur=14)
    for x, y, r in ((706, 916, 100), (880, 922, 108)):
        cake(ic, x, y, r)
    cake(ic, 794, 852, 104)
    cake(ic, 802, 786, 94)


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
