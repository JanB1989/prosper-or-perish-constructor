"""Reckoning Schools (advance icon pp_reckoning_schools_advance): a still life of what the abacus schools taught. An
open merchant's ledger kept in Hindu-Arabic figures, debit on the left page and credit on the right (Dare / Avere,
dated 1494, the year Pacioli printed double entry), lies on a counting board ruled for reckoning with counters, a few
brass counters on its lines and a small stack beside them; a goose quill stands in a pewter inkwell behind.

Advance icons are still lifes without the building icons' black outline (vanilla efficient_mining, debt_and_loans),
256 px, transparent; the game cuts their lower corners round (``advance_icon_mask``), so the foot stays narrow. The
DDS goes where the game reads advance icons. Run from the constructor:

  uv run python assets/icon_drawings/pp_reckoning_schools_advance/draw.py [--preview <png>] [--png <png>]

Flat objects are painted from above on their own layer and tipped into view with a perspective warp (``tip``), then
turned into place (``put``); front objects shade the ones behind (``cast``). Local helpers: ``ledger``,
``counting_board``, ``counter``, ``inkwell``, ``quill``, ``grain``, ``bevel``, ``text_block``.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from eu5_building_pipeline.dds import encode_dds, fit
from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.finalize import grade, rim, soften

SEED = 61
SIDE = 256  # interface_dds.ADVANCE_MAX_SIDE
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "mod/pp/main_menu/gfx/interface/advance/pp_reckoning_schools_advance.dds"
SERIF = ("/usr/share/fonts/opentype/urw-base35/P052-Roman.otf", "/usr/share/fonts/opentype/urw-base35/C059-Roman.otf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
ITALIC = ("/usr/share/fonts/opentype/urw-base35/P052-Italic.otf", "/usr/share/fonts/opentype/urw-base35/C059-Italic.otf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")
INK = (52, 32, 18)
RED = (160, 44, 30)
EDGE = (36, 22, 12, 230)
BRASS = ("#f4d280", "#7a4e14")


def font(paths, size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- layers
def layer(seed: int) -> Icon:
    """A fresh canvas for one object, drawn around the canvas centre."""
    return Icon(seed=seed)


def tip(img: Image.Image, src, dst) -> Image.Image:
    """Perspective warp: the quad ``src`` of ``img`` lands on the quad ``dst``."""
    rows = []
    for (xs, ys), (xd, yd) in zip(src, dst):
        rows.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd])
        rows.append([0, 0, 0, xd, yd, 1, -ys * xd, -ys * yd])
    coeffs = np.linalg.solve(np.array(rows, float), np.array(src, float).reshape(8))
    return img.transform(img.size, Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)


def put(ic: Icon, img: Image.Image, degrees: float, at) -> Image.Image:
    placed = img.rotate(degrees, resample=Image.BICUBIC, center=(512, 512), translate=(at[0] - 512, at[1] - 512))
    ic.image.alpha_composite(placed)
    return placed


def turned(img: Image.Image, degrees: float, at) -> Image.Image:
    return img.rotate(degrees, resample=Image.BICUBIC, center=(512, 512), translate=(at[0] - 512, at[1] - 512))


def cast(ic: Icon, placed: Image.Image, dx: float, dy: float, blur: float, alpha: float) -> None:
    """Shadow of an object that is about to be laid on top, falling onto what is already there."""
    m = ImageChops.offset(placed.getchannel("A"), int(dx), int(dy))
    ic.shade(m, (12, 6, 2), alpha, blur=blur)


def grain(ic: Icon, mask: Image.Image, box, vertical: bool = True, strength: int = 60, step: float = 7) -> None:
    """Wood grain: long wavy fibres along the board."""
    x0, y0, x1, y1 = box
    rnd = ic.random.uniform

    def paint(d):
        if vertical:
            x = x0
            while x < x1:
                ph, amp = rnd(0, 6.3), rnd(2, 7)
                pts = [(x + amp * math.sin(ph + y / rnd(60, 120)), y) for y in np.arange(y0, y1 + 10, 10)]
                a = int(rnd(0.3, 1) * strength)
                d.line(pts, fill=(40, 22, 10, a) if ic.random.random() < 0.7 else (255, 236, 200, a // 2), width=2)
                x += step * rnd(0.6, 1.4)
        else:
            y = y0
            while y < y1:
                ph, amp = rnd(0, 6.3), rnd(2, 7)
                pts = [(x, y + amp * math.sin(ph + x / rnd(60, 120))) for x in np.arange(x0, x1 + 10, 10)]
                a = int(rnd(0.3, 1) * strength)
                d.line(pts, fill=(40, 22, 10, a) if ic.random.random() < 0.7 else (255, 236, 200, a // 2), width=2)
                y += step * rnd(0.6, 1.4)

    ic.overlay(paint, mask)


def bevel(ic: Icon, mask: Image.Image, width: int = 12, lit: float = 0.35, dark: float = 0.45) -> None:
    """Rounded edge on a flat object: light along the upper left rim, shade along the lower right rim."""
    inner = mask.filter(ImageFilter.MinFilter(width | 1))
    ring = ImageChops.subtract(mask, inner)
    up = ImageChops.subtract(ring, ImageChops.offset(ring, -width // 2, -width // 2))
    down = ImageChops.subtract(ring, ImageChops.offset(ring, width // 2, width // 2))
    ic.shade(ic.intersect(up, mask), (255, 238, 206), lit, blur=2)
    ic.shade(ic.intersect(down, mask), (14, 8, 4), dark, blur=2)


def text_block(size, lines, blur: float = 0.6) -> Image.Image:
    """Text on a transparent sheet: ``lines`` = [(x, y, text, font, colour, anchor), ...]."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, text, f, col, anchor in lines:
        d.text((x, y), text, font=f, fill=col, anchor=anchor)
    return img.filter(ImageFilter.GaussianBlur(blur)) if blur else img


def contour(ob: Icon, alpha: float = 0.85) -> None:
    """Thin dark painted edge round everything on the layer."""
    a = ob.alpha().point(lambda v: 255 if v > 40 else 0)
    ob.shade(ImageChops.subtract(a.filter(ImageFilter.MaxFilter(5)), a), EDGE[:3], alpha, clip=False)


# ---------------------------------------------------------------- objects
ENTRIES_L = (("Pepe", "12", "6", "4"), ("Zafferano", "3", "10", "0"), ("Seta", "31", "0", "8"),
             ("Panni", "7", "15", "0"), ("Allume", "19", "2", "6"), ("Cera", "4", "8", "11"))
ENTRIES_R = (("Contanti", "40", "0", "0"), ("Lana", "16", "12", "6"), ("Cambio", "9", "4", "0"),
             ("Grano", "5", "18", "2"), ("Vino", "2", "11", "9"))


def ledger(ob: Icon) -> None:
    """An open ledger from above: leather boards, two curved pages with dated, ruled entries, a red ribbon."""
    cx, cy = 512, 512
    W, H = 760, 500
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    cover = ob.mask("rounded_rectangle", (x0 - 22, y0 - 16, x1 + 22, y1 + 40), radius=14)
    ob.fill(cover, "#8a4428", "#30120a", radial=(x0, y0, W * 1.1), noise=0.12, chroma=0.06)
    bevel(ob, cover, 10, 0.3, 0.5)
    # page block edges below the open pages (seen from the front once tipped)
    block = ob.mask("rectangle", (x0 + 4, y1 - 6, x1 - 4, y1 + 26))
    ob.fill(block, "#e2d2ae", "#9a8460", noise=0.06)
    ob.overlay(lambda d: [d.line([(x0 + 6, y), (x1 - 6, y)], fill=(120, 100, 70, 150), width=2)
                          for y in np.arange(y1 - 2, y1 + 26, 5)], block)
    ob.shade(ob.intersect(ob.mask("rectangle", (cx - 30, y1 - 6, cx + 30, y1 + 26)), block), (40, 24, 10), 0.5, blur=8)
    fh, fe, fn = font(ITALIC, 40), font(ITALIC, 25), font(SERIF, 26)
    for side in (-1, 1):  # the stacked leaves under each page show at the outer edges
        xa, xb = (x0 - 12, x0 + 6) if side < 0 else (x1 - 6, x1 + 12)
        edge = ob.poly_mask([(xa, y0 - 4), (xb, y0 - 8), (xb, y1 + 22), (xa, y1 + 24)])
        ob.fill(edge, "#e6d6b2", "#9a8460", noise=0.06)
        ob.overlay(lambda d, xa=xa, xb=xb: [d.line([(x, y0), (x, y1 + 20)], fill=(120, 100, 70, 150), width=2)
                                            for x in np.arange(xa + 3, xb, 4)], edge)
    for side in (-1, 1):
        ts = np.linspace(0, 1, 30)
        top = [(cx + side * (6 + (W / 2 - 6) * t), y0 + 26 - 34 * t ** 1.4) for t in ts]
        bot = [(cx + side * (6 + (W / 2 - 6) * t), y1 - 2 * t) for t in ts[::-1]]
        page = ob.poly_mask(top + bot)
        ob.fill(page, "#f6ecd2", "#c9b48a", radial=(cx + side * W * 0.1 - W * 0.2, y0, W * 0.75), noise=0.06, chroma=0.03)
        for _ in range(6):
            x, y, r = cx + side * ob.random.uniform(40, W / 2 - 40), ob.random.uniform(y0 + 40, y1 - 40), ob.random.uniform(14, 40)
            ob.shade(ob.intersect(ob.mask("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8)), page), (160, 120, 70),
                     ob.random.uniform(0.04, 0.1), blur=10)
        pw = int(W / 2 - 40)
        ph = int(H - 40)
        px = int(cx + 26) if side > 0 else int(cx - 26 - pw)
        py = int(y0 + 14)
        rule = (150, 128, 96, 110)
        lines = [(18, 8, "Dare" if side < 0 else "Avere", fh, RED + (230,), "la"),
                 (pw - 14, 14, "1494", fn, INK + (220,), "ra")]
        entries = ENTRIES_L if side < 0 else ENTRIES_R
        for k, (what, lb, s, d) in enumerate(entries):
            y = 76 + k * 58
            lines += [(18, y, what, fe, INK + (220,), "la"), (pw - 118, y, lb, fn, INK + (235,), "ra"),
                      (pw - 66, y, s, fn, INK + (235,), "ra"), (pw - 18, y, d, fn, INK + (235,), "ra")]
        txt = text_block((pw, ph), lines, blur=0.7)
        sheet = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sheet)
        for k in range(8):
            y = 64 + k * 58
            sd.line([(10, y), (pw - 8, y)], fill=rule, width=2)
        for x in (pw - 160, pw - 100, pw - 52):
            sd.line([(x, 60), (x, ph - 30)], fill=RED + (150,), width=3)
        n = len(entries)
        ys = 76 + n * 58 + 6
        sd.line([(pw - 160, ys), (pw - 10, ys)], fill=INK + (200,), width=3)
        sd.line([(pw - 160, ys + 8), (pw - 10, ys + 8)], fill=INK + (200,), width=3)
        sheet.alpha_composite(txt)
        if side < 0:
            sheet.alpha_composite(text_block((pw, ph), [(pw - 118, ys + 14, "79", fn, INK + (235,), "ra"),
                                                        (pw - 66, ys + 14, "3", fn, INK + (235,), "ra"),
                                                        (pw - 18, ys + 14, "5", fn, INK + (235,), "ra")], blur=0.7))
        layer_txt = Image.new("RGBA", (ob.size, ob.size), (0, 0, 0, 0))
        layer_txt.paste(sheet, (px, py))
        ob.image.alpha_composite(Image.composite(layer_txt, Image.new("RGBA", layer_txt.size, (0, 0, 0, 0)), page))
        # the page curls up out of the gutter: shade near the spine, a lit swell beside it
        g = ob.mask("rectangle", (cx - 70, y0 - 20, cx + 70, y1 + 10))
        ob.shade(ob.intersect(g, page), (60, 36, 14), 0.42, blur=26)
        swell = ob.mask("rectangle", (cx + side * 80 - 30, y0, cx + side * 80 + 30, y1))
        ob.shade(ob.intersect(swell, page), (255, 250, 236), 0.18, blur=20)
        ob.overlay(lambda d, p=top + bot: d.line(p + [p[0]], fill=(120, 96, 64, 200), width=3))
    # ribbon out of the gutter
    rib = [(cx + 6, y0 + 30), (cx + 22, y0 + 30), (cx + 40, y1 + 70), (cx + 30, y1 + 90), (cx + 22, y1 + 66)]
    ob.fill(ob.poly_mask(rib), "#c0392a", "#5a120a", noise=0.08)
    contour(ob)


def counting_board(ob: Icon) -> None:
    """A walnut counting board from above: lines for units, tens, hundreds, thousands (the thousands line crossed), a
    middle line for the halves, a raised rim."""
    cx, cy = 512, 512
    W, H = 640, 380
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    outer = ob.mask("rounded_rectangle", (x0, y0, x1, y1), radius=18)
    side = ImageChops.subtract(ImageChops.offset(outer, 0, 22), outer)
    ob.fill(side, "#4a2c16", "#1e1008", noise=0.1)
    ob.fill(outer, "#9a6a40", "#40240e", radial=(x0, y0, W * 1.2), noise=0.12, chroma=0.06)
    grain(ob, outer, (x0, y0, x1, y1), vertical=False, strength=55, step=7)
    bevel(ob, outer, 16, 0.35, 0.45)
    inner = ob.mask("rectangle", (x0 + 28, y0 + 28, x1 - 28, y1 - 28))
    ob.shade(inner, (20, 10, 4), 0.18)

    def lines(d):
        for k in range(5):
            y = y0 + 60 + k * (H - 120) / 4
            d.line([(x0 + 40, y + 2), (x1 - 40, y + 2)], fill=(30, 16, 6, 160), width=4)
            d.line([(x0 + 40, y), (x1 - 40, y)], fill=(232, 210, 170, 210), width=4)
        y = y0 + 60
        for dx in (-14, 14):
            d.line([(x0 + 90 - 14, y - 14), (x0 + 90 + 14, y + 14)], fill=(232, 210, 170, 220), width=4)
            d.line([(x0 + 90 - 14, y + 14), (x0 + 90 + 14, y - 14)], fill=(232, 210, 170, 220), width=4)
        d.line([(cx, y0 + 40), (cx, y1 - 40)], fill=(232, 210, 170, 180), width=4)

    ob.overlay(lines, inner)
    contour(ob)


def counter(ic: Icon, cx, cy, r, h=10, tilt=0.42) -> None:
    """A brass reckoning counter seen from above at an angle: rim, a stamped ring and cross on the face."""
    ry = r * tilt
    body = ImageChops.lighter(ic.mask("ellipse", (cx - r, cy - ry + h, cx + r, cy + ry + h)),
                              ic.mask("rectangle", (cx - r, cy, cx + r, cy + h)))
    ic.fill(body, "#b07c2c", "#4a2c08", (cx - r, cx + r), vertical=False, noise=0.06)
    face = ic.mask("ellipse", (cx - r, cy - ry, cx + r, cy + ry))
    ic.fill(face, BRASS[0], BRASS[1], radial=(cx - r * 0.4, cy - ry * 0.5, r * 1.6), noise=0.06, chroma=0.03)
    ic.overlay(lambda d: d.ellipse((cx - r * 0.72, cy - ry * 0.72, cx + r * 0.72, cy + ry * 0.72),
                                   outline=(120, 76, 20, 200), width=3))
    ic.overlay(lambda d: [d.line([(cx - r * 0.45, cy), (cx + r * 0.45, cy)], fill=(120, 76, 20, 200), width=3),
                          d.line([(cx, cy - ry * 0.45), (cx, cy + ry * 0.45)], fill=(120, 76, 20, 200), width=3)])
    ic.shade(ic.intersect(ic.mask("ellipse", (cx - r * 0.7, cy - ry * 0.9, cx, cy - ry * 0.1)), face), (255, 250, 230),
             0.45, blur=4)
    ic.overlay(lambda d: d.ellipse((cx - r, cy - ry, cx + r, cy + ry), outline=EDGE, width=3))
    ic.overlay(lambda d: d.arc((cx - r, cy - ry + h, cx + r, cy + ry + h), 0, 180, fill=EDGE, width=3))


def inkwell(ic: Icon, cx, base, w, h) -> None:
    """A squat stoneware inkwell in a dark brown glaze: broad body, rounded shoulder, a short collar round the inky
    mouth; a bright glaze highlight and warm light bounced off the ledger."""
    tilt = 0.3
    knots = [(0.0, 0.5), (0.1, 0.5), (0.5, 0.49), (0.7, 0.44), (0.84, 0.32), (0.93, 0.2), (1.0, 0.19)]
    ss = np.linspace(0, 1, 40)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    side = [(cx - v, base - h * s) for s, v in zip(ss, hw)] + [(cx + v, base - h * s) for s, v in zip(ss[::-1], hw[::-1])]
    body = ImageChops.lighter(ic.poly_mask(side), ic.mask("ellipse", (cx - w / 2, base - w * tilt / 2, cx + w / 2,
                                                                      base + w * tilt / 2)))
    ic.fill(body, "#8a5430", "#1c0c04", (cx - w * 0.42, cx + w * 0.5), vertical=False, noise=0.05, chroma=0.03)
    ic.shade(ic.intersect(ic.mask("ellipse", (cx - w * 0.36, base - h * 0.95, cx - w * 0.12, base - h * 0.45)), body),
             (255, 246, 226), 0.65, blur=7)
    ic.shade(ic.intersect(ic.mask("rectangle", (cx + w * 0.3, base - h, cx + w * 0.5, base + 20)), body),
             (220, 140, 70), 0.3, blur=8)  # warm light bounced off the ledger
    collar = (cx - w * 0.2, base - h - w * 0.06, cx + w * 0.2, base - h + w * 0.06)
    ic.fill(ic.mask("ellipse", collar), "#a06a40", "#3a1e0c", radial=(cx - w * 0.08, base - h - 6, w * 0.3), noise=0.05)
    mouth = (cx - w * 0.11, base - h - w * 0.035, cx + w * 0.11, base - h + w * 0.035)
    ic.fill(ic.mask("ellipse", mouth), "#101016", "#040406", noise=0.04)
    ic.overlay(lambda d: d.line(side + [side[0]], fill=EDGE, width=4))
    ic.overlay(lambda d: d.arc((cx - w / 2, base - w * tilt / 2, cx + w / 2, base + w * tilt / 2), 0, 180, fill=EDGE,
                               width=4))
    ic.overlay(lambda d: d.ellipse(collar, outline=EDGE, width=3))


def quill(ic: Icon, nib, tip_pt, width=46) -> None:
    """A goose quill: a broad pale vane, barbs fanning off the shaft, a darker inked nib."""
    nib, tip_pt = np.array(nib, float), np.array(tip_pt, float)
    d = (tip_pt - nib) / np.linalg.norm(tip_pt - nib)
    n = np.array([-d[1], d[0]])
    L = np.linalg.norm(tip_pt - nib)

    def edge(sign, k):
        return [tuple(nib + d * L * t + n * sign * width * k * math.sin(math.pi * (t - 0.24) / 0.8) ** 0.6)
                for t in np.linspace(0.25, 1, 18)]

    vane = [tuple(nib + d * L * 0.22)] + edge(1, 1.0) + edge(-1, 0.42)[::-1]
    vm = ic.poly_mask(vane)
    ic.fill(vm, "#f8f4ea", "#a8a090", radial=(*(nib + d * L * 0.55 + n * width * 0.4), L * 0.55), noise=0.06)

    def barbs(dr):
        for t in np.linspace(0.28, 0.95, 26):
            p = nib + d * L * t
            dr.line([tuple(p), tuple(p + d * L * 0.07 + n * width * 0.95)], fill=(140, 130, 110, 120), width=2)
            dr.line([tuple(p), tuple(p + d * L * 0.06 - n * width * 0.4)], fill=(140, 130, 110, 100), width=2)

    ic.overlay(barbs, vm)
    ic.shade(ic.intersect(ic.poly_mask([tuple(nib + d * L * 0.22)] + edge(-1, 0.42)[::-1] + [tuple(tip_pt)]), vm),
             (60, 54, 44), 0.25, blur=6)
    for k, (cut0, cut1) in enumerate(((0.5, 0.58), (0.72, 0.78))):  # splits in the vane
        p = nib + d * L * cut0
        ic.line([tuple(p + n * width * 0.9), tuple(nib + d * L * cut1 + n * width * 0.2)], 3, (120, 110, 94, 200))
    ic.line([tuple(nib), tuple(tip_pt)], 5, (190, 178, 150))
    ic.line([tuple(nib), tuple(nib + d * L * 0.1)], 7, (40, 30, 22))
    ic.overlay(lambda dr: dr.line(vane + [vane[0]], fill=(80, 72, 60, 200), width=3))


# ---------------------------------------------------------------- composition
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    ic.grade["gamma"] = 0.9
    ic.grade["light"] = 0.12
    # counting board, tipped back and turned, at the back left; counters lie on its lines
    bd = layer(SEED + 1)
    counting_board(bd)
    bsrc = [(192, 322), (832, 322), (832, 724), (192, 724)]
    bdst = [(240, 352), (784, 352), (840, 690), (184, 690)]
    bimg = tip(rim(bd.image, 0.25, 20), bsrc, bdst)
    bdeg, bat = 11, (420, 372)
    put(ic, bimg, bdeg, bat)

    def on_board(u, v):
        """Board coordinates (0..1 across, 0..1 down) to canvas, through the same tip and turn."""
        top = np.array(bdst[0]) + (np.array(bdst[1]) - np.array(bdst[0])) * u
        bot = np.array(bdst[3]) + (np.array(bdst[2]) - np.array(bdst[3])) * u
        p = top + (bot - top) * v - 512
        a = math.radians(-bdeg)
        return (512 + p[0] * math.cos(a) - p[1] * math.sin(a) + bat[0] - 512,
                512 + p[0] * math.sin(a) + p[1] * math.cos(a) + bat[1] - 512)

    lines_v = [(60 + k * 65) / 380 for k in range(5)]  # the board's lines, as fractions of its height
    for u, k in ((0.3, 0), (0.37, 0), (0.6, 0), (0.24, 1), (0.52, 1), (0.71, 1), (0.2, 2), (0.82, 0), (0.28, 3)):
        x, y = on_board(u, lines_v[k] - 0.03)
        counter(ic, x, y, 34, 8)
    # a small stack of counters on the board's left end
    sx, sy = on_board(0.1, 0.72)
    ic.shade(ic.mask("ellipse", (sx - 60, sy - 6, sx + 76, sy + 40)), (10, 6, 2), 0.45, blur=10)
    for k in range(5):
        counter(ic, sx + (k % 2) * 3, sy - k * 13, 44, 11)
    # ledger tipped back less than the board, turned, laid over the board's lower half
    lg = layer(SEED + 2)
    ledger(lg)
    limg = tip(rim(lg.image, 0.2, 20), [(110, 236), (914, 236), (914, 812), (110, 812)],
               [(214, 372), (810, 372), (890, 744), (134, 744)])
    lp = turned(limg, -6, (600, 640))
    cast(ic, lp, 16, 26, 18, 0.55)
    ic.image.alpha_composite(lp)
    # inkwell and quill at the back right
    ic.shade(ic.mask("ellipse", (726, 452, 930, 518)), (10, 6, 2), 0.5, blur=10, clip=False)
    inkwell(ic, 828, 480, 176, 86)
    quill(ic, (820, 402), (944, 70), width=54)


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
    ap.add_argument("--preview", type=Path, help="write a preview sheet here instead of the DDS")
    ap.add_argument("--png", type=Path, help="write the finished 256 px PNG here instead of the DDS")
    args = ap.parse_args()
    ic = Icon(seed=SEED)
    draw(ic)
    image = finished(ic)
    if args.png:
        args.png.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.png)
    if args.preview:
        sheet = Image.new("RGBA", (SIDE + 90, SIDE + 12), (60, 60, 70, 255))
        sheet.alpha_composite(image, (6, 6))
        sheet.alpha_composite(image.resize((64, 64), Image.LANCZOS), (SIDE + 16, 6))
        sheet.save(args.preview)
    if args.png or args.preview:
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encode_dds(image, "DXT5"))
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
