"""Tavern (tavern): roadside coaching inn with a hanging tankard sign and an attached stable wing.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/tavern/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/tavern

Identity: a big foaming tankard hanging from an iron bracket off the inn's corner, a long thatched
inn with a jettied, half-timbered guest-room floor over a stone taproom, and the stable wing with a
hay loft and a horse looking over the half door (rooms and stables for armies on the march).
Supporting props: casks by the taproom door, a water trough and a heap of hay. Painterly helpers
``union``, ``tint``, ``stones``, ``shingles`` are copied from the Cookshop so the food family shares
one finish; new local helpers: ``thatch``, ``planks``, ``cask``, ``tankard``, ``horse_head``, ``hay``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 7
REFS = ("pirate_tavern", "caravan_stop", "sergeantry", "market_village")

BASE = 900
L, R = 176, 636  # inn walls
EAVE, RIDGE = 444, 208
BAND = 640  # jetty line between the timber-framed guest floor and the stone taproom
SX0, SX1 = 628, 972  # stable wing walls
SEAVE, SAPEX = 612, 410
SCX = (SX0 + SX1) / 2
IRON = (34, 31, 30)


# ---------------------------------------------------------------- helpers (shared with the Cookshop)
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.8, 1.15)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.2, 2.5)
            j = lambda: rnd(-3, 3)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(96, 104, 60, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 55)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(30, 22, 16, shadow), width=5)
            x += w
        y += h
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = min(ys), 0
    while y < max(ys):
        off = (k % 2) * stagger / 2 + rnd(-6, 6)
        x = min(xs) - stagger + off
        while x < max(xs):
            w = stagger * rnd(0.85, 1.15)
            q = [(x + 2, y + 2), (x + w - 2, y + 2), (x + w - 2, y + course), (x + 2, y + course)]
            t = rnd(-1, 1)
            td.polygon(q, fill=(20, 10, 6, int(-t * 60)) if t < 0 else (255, 236, 210, int(t * 40)))
            td.line([(x + w - 2, y + 6), (x + w - 2, y + course - 2)], fill=(40, 22, 14, 90), width=3)
            x += w
        yl = y + course + rnd(-2, 2)
        td.line([(0, yl - 4), (ic.size, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (ic.size, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


# ---------------------------------------------------------------- helpers (new for the Tavern)
def thatch(ic: Icon, pts, c1, c2, course: float = 44) -> Image.Image:
    """Thatched roof plane: straw strands running down the slope, layered courses with a dark
    underside and a lit combed lip, weathered blotches. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.24, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    shadow = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y = min(ys) + rnd(0, course * 0.4)
    while y < max(ys) + course:
        for _ in range(int((max(xs) - min(xs)) / 3)):
            x = rnd(min(xs), max(xs))
            ln = rnd(course * 0.4, course * 1.2)
            t = rnd(-1, 1)
            col = (255, 236, 196, int(t * 60)) if t > 0 else (30, 18, 8, int(-t * 70))
            y0 = y + rnd(-course * 0.3, course * 0.4)
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        # course edge: broken into short irregular segments, never one continuous wave
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(12):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    return m


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap on the right of each board."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    x = x0 - rnd(0, board)
    while x < x1:
        w = board * rnd(0.8, 1.2)
        t = rnd(-1, 1)
        d.rectangle((x, y0, x + w, y1), fill=(24, 14, 8, int(-t * 60)) if t < 0 else (255, 240, 214, int(t * 36)))
        for _ in range(3):
            gx = x + rnd(4, w - 4)
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    clip2 = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip2.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip2)


def cask(ic: Icon, x0, y0, x1, y1, wood=("#b07c4e", "#4a2e18")) -> None:
    """Barrel as a form: bulged staves lit from the left, core shadow right, iron hoops, lit head."""
    w, h = x1 - x0, y1 - y0
    bul = w * 0.09
    ts = np.linspace(0, 1, 32)
    pts = [(x0 - bul * math.sin(math.pi * t), y0 + h * t) for t in ts]
    pts += [(x1 + bul * math.sin(math.pi * t), y0 + h * t) for t in ts[::-1]]
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], (x0 + w * 0.15, x1 + bul), vertical=False, noise=0.14)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.55, y0, x1 + bul, y1)), m, (10, 4, 0), 0.35, w * 0.12)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.12, y0, x0 + w * 0.26, y1)), m, (255, 232, 196), 0.22, 6)
    for sx in np.linspace(x0 + w * 0.2, x1 - w * 0.12, 4):
        ic.line([(sx + ic.random.uniform(-3, 3), y0 + 12), (sx, y1 - 6)], 3, (50, 30, 14, 110))
    for f in (0.2, 0.78):
        hy = y0 + h * f
        ic.line([(x0 - bul * 0.7, hy), (x1 + bul * 0.7, hy + 2)], 11, (44, 42, 42))
        ic.line([(x0, hy - 3), (x0 + w * 0.5, hy - 3)], 3, (170, 162, 150, 120))
    head = (x0 - 2, y0 - h * 0.1, x1 + 2, y0 + h * 0.1)
    ic.fill(ic.mask("ellipse", head), "#c89c6c", "#7a5232", radial=(x0 + w * 0.3, y0 - h * 0.08, w * 0.9), noise=0.14)
    ic.overlay(lambda d: d.ellipse(head, outline=(44, 42, 42, 255), width=7))
    ic.line([(x0 + w * 0.3, y0 - h * 0.06), (x0 + w * 0.3, y0 + h * 0.07)], 3, (80, 52, 30, 120))
    ic.outline(pts, 4, (40, 24, 12, 170))


def tankard(ic: Icon, x0, y0, x1, y1) -> None:
    """The inn sign: a big coopered tankard with brass hoops, a D handle and a foaming head."""
    w, h = x1 - x0, y1 - y0
    body = [(x0, y0 + h * 0.12), (x1, y0 + h * 0.12), (x1 - w * 0.04, y1), (x0 + w * 0.04, y1)]
    # handle behind the body on the right
    hx, hy0, hy1 = x1 - 6, y0 + h * 0.26, y0 + h * 0.84
    ring = ic.mask("ellipse", (hx - w * 0.28, hy0, hx + w * 0.42, hy1))
    hole = ic.mask("ellipse", (hx - w * 0.1, hy0 + h * 0.13, hx + w * 0.24, hy1 - h * 0.13))
    ic.fill(ImageChops.subtract(ring, hole), "#9a6a3e", "#3e2412", radial=(hx, hy0, h * 0.7), noise=0.12)
    bm = ic.poly_mask(body)
    ic.fill(bm, "#c48a52", "#4e2c14", (x0 + w * 0.1, x1), vertical=False, noise=0.14)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, y0, x1, y1)), bm, (10, 4, 0), 0.35, 10)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.12, y0, x0 + w * 0.26, y1)), bm, (255, 236, 200), 0.3, 6)
    for f in (0.3, 0.52, 0.74):
        sx = x0 + w * f
        ic.line([(sx, y0 + h * 0.16), (sx, y1 - 4)], 3, (60, 34, 16, 120))
    for f in (0.26, 0.9):
        yy = y0 + h * f
        band = ic.mask("rectangle", (x0 - 4, yy - 9, x1 + 4, yy + 9))
        ic.fill(ic.intersect(band, ic.mask("rectangle", (x0 - 6, 0, x1 + 6, ic.size))), "#d8b060", "#6a4a1c",
                (x0, x1), vertical=False, noise=0.08)
    ic.outline(body, 4, (40, 22, 10, 180))
    # foam spilling over the rim
    foam = [(x0 - 8, y0 + h * 0.2), (x0 - 12, y0 + h * 0.08), (x0 + w * 0.1, y0 - h * 0.02),
            (x0 + w * 0.3, y0 - h * 0.08), (x0 + w * 0.52, y0 - h * 0.04), (x0 + w * 0.74, y0 - h * 0.1),
            (x1 + 6, y0 + h * 0.02), (x1 + 10, y0 + h * 0.16), (x1 - w * 0.2, y0 + h * 0.2),
            (x0 + w * 0.5, y0 + h * 0.17), (x0 + w * 0.2, y0 + h * 0.22)]
    fm = ic.poly_mask(foam)
    ic.fill(fm, "#fbf4e2", "#b8ab92", radial=(x0 + w * 0.2, y0 - h * 0.06, w * 1.1), noise=0.06, chroma=0.02)
    drip = [(x0 + w * 0.08, y0 + h * 0.18), (x0 + w * 0.16, y0 + h * 0.18), (x0 + w * 0.14, y0 + h * 0.34),
            (x0 + w * 0.1, y0 + h * 0.34)]
    ic.fill(ic.poly_mask(drip), "#f2ead6", "#c2b49a", noise=0.05)
    tint(ic, ic.mask("rectangle", (x0, y0 + h * 0.1, x1, y0 + h * 0.24)), fm, (60, 50, 36), 0.3, 6)
    ic.outline(foam, 3, (90, 80, 64, 150))


def horse_head(ic: Icon, dx: float = 0, dy: float = 0) -> None:
    """Chestnut horse with a white blaze leaning left over the stable's half door."""
    P = lambda pts: [(x + dx, y + dy) for x, y in pts]  # noqa: E731
    neck = P([(800, 700), (846, 722), (884, 770), (900, 850), (800, 860), (796, 800)])
    nm = ic.poly_mask(neck)
    ic.fill(nm, "#8a4c28", "#24100a", (790, 900), vertical=False, noise=0.14)
    tint(ic, ic.mask("rectangle", (840 + dx, 700, 920 + dx, 900)), nm, (0, 0, 0), 0.45, 20)
    mane = P([(790, 690), (812, 698), (850, 716), (884, 756), (900, 800), (880, 780), (848, 744), (812, 718)])
    ic.fill(ic.poly_mask(mane), "#3a2216", "#140a06", noise=0.16)
    # long face in profile looking left: ears, flat forehead and nose, round cheek, soft muzzle
    head = P([(772, 668), (786, 690), (800, 698), (812, 716), (822, 752), (824, 790), (812, 818), (788, 830),
              (756, 840), (722, 846), (704, 840), (694, 822), (696, 804), (710, 780), (734, 748), (756, 718),
              (766, 696)])
    hm = ic.poly_mask(head)
    ic.fill(hm, "#b0703e", "#3a1c0c", radial=(748 + dx, 730 + dy, 140), noise=0.14)
    tint(ic, ic.mask("ellipse", P([(760, 740)])[0] + P([(836, 846)])[0]), hm, (10, 4, 0), 0.45, 14)  # jaw shadow
    tint(ic, ic.mask("ellipse", P([(770, 752)])[0] + P([(812, 800)])[0]), hm, (255, 220, 180), 0.12, 8)  # cheek
    blaze = P([(762, 706), (772, 704), (760, 740), (734, 790), (716, 818), (708, 812), (726, 776), (750, 730)])
    ic.fill(ic.poly_mask(blaze), "#ece2cc", "#b8aa90", noise=0.08)
    muzzle = ic.intersect(hm, ic.mask("ellipse", P([(684, 800)])[0] + P([(752, 860)])[0]))
    tint(ic, muzzle, hm, (46, 30, 24), 0.55, 4)
    nx, ny = 706 + dx, 818 + dy
    ic.draw.ellipse((nx - 5, ny - 7, nx + 5, ny + 5), fill=(24, 14, 10, 255))
    ex, ey = 782 + dx, 730 + dy
    ic.draw.ellipse((ex - 8, ey - 6, ex + 8, ey + 6), fill=(18, 12, 10, 255))
    ic.draw.ellipse((ex - 5, ey - 4, ex - 1, ey - 1), fill=(200, 190, 180, 255))
    ic.line(P([(756, 836), (790, 822)]), 3, (40, 20, 10, 120))  # chin groove
    ear = P([(774, 668), (782, 648), (792, 672), (786, 692)])
    ic.poly(ear, "#9a5c32", "#4a240e", edge=3)
    ic.outline(head, 4, (40, 18, 8, 170))


def hay(ic: Icon, pts, strands: int = 220) -> Image.Image:
    """Loose hay: golden mass lit top-left, dark underside, many straw strokes, a few stray stalks."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, "#d6b66c", "#6a5026", radial=(min(xs) + (max(xs) - min(xs)) * 0.3, min(ys), (max(ys) - min(ys)) * 1.4),
            noise=0.22)
    rnd = ic.random.uniform

    def straw(d: ImageDraw.ImageDraw) -> None:
        for _ in range(strands):
            x, y = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
            a = rnd(-0.9, 0.9) + (math.pi if ic.random.random() < 0.5 else 0)
            ln = rnd(14, 40)
            t = rnd(-1, 1)
            col = (255, 240, 180, int(t * 110)) if t > 0 else (50, 34, 10, int(-t * 110))
            d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln * 0.5)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (min(xs), (min(ys) + max(ys)) / 2 + 10, max(xs), max(ys))), m, (30, 16, 4), 0.35, 16)
    for _ in range(10):  # stray stalks sticking out of the silhouette
        i = ic.random.randrange(len(pts))
        x, y = pts[i]
        if y > max(ys) - 20:
            continue
        a = rnd(-2.6, -0.5)
        ic.line([(x, y + 6), (x + math.cos(a) * rnd(14, 26), y + math.sin(a) * rnd(14, 26))], 3, (196, 164, 92))
    return m


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.84

    # ---- chimney at the left end of the ridge (the taproom hearth), a thin wisp only
    cx0, cx1, ctop = 262, 336, 148
    cm = ic.mask("rectangle", (cx0, ctop, cx1, RIDGE + 40))
    stones(ic, (cx0, ctop, cx1, RIDGE + 40), "#a89a86", "#6a5e50", course=28)
    tint(ic, ic.mask("rectangle", (cx0 + 44, ctop, cx1 + 10, RIDGE + 40)), cm, (0, 0, 0), 0.32, 12)
    tint(ic, ic.mask("rectangle", (cx0, ctop, cx1, ctop + 40)), cm, (20, 14, 10), 0.3, 10)
    ic.outline([(cx0, ctop), (cx1, ctop), (cx1, RIDGE + 40), (cx0, RIDGE + 40)], 4)
    ic.poly([(cx0 - 10, ctop - 12), (cx1 + 10, ctop - 12), (cx1 + 10, ctop + 8), (cx0 - 10, ctop + 8)],
            "#b4a894", "#7c7264", edge=4)

    # ---- inn roof: long thatch, slightly sagging ridge
    # hipped thatch: rounded shoulders at both ends, slightly sagging ridge
    lside = [(146 + 94 * (1 - math.cos(t * math.pi / 2)) + 30 * math.sin(t * math.pi),
              EAVE + 16 - (EAVE + 16 - RIDGE) * math.sin(t * math.pi / 2)) for t in np.linspace(0, 1, 14)]
    rside = [(668 - 92 * (1 - math.cos(t * math.pi / 2)) - 30 * math.sin(t * math.pi),
              EAVE + 16 - (EAVE + 16 - RIDGE - 4) * math.sin(t * math.pi / 2)) for t in np.linspace(0, 1, 14)]
    roof = lside + [(410, RIDGE + 8)] + rside[::-1]
    rmask = thatch(ic, roof, "#c09a5a", "#5a3e1e")
    tint(ic, ic.poly_mask([(140, RIDGE), (380, RIDGE), (330, EAVE + 20), (140, EAVE + 20)]), rmask, (255, 228, 176), 0.14, 50)
    tint(ic, ic.mask("rectangle", (140, EAVE - 50, 680, EAVE + 20)), rmask, (30, 16, 4), 0.3, 16)
    tint(ic, ic.poly_mask([(520, RIDGE), (700, RIDGE), (700, EAVE + 20), (560, EAVE + 20)]), rmask, (0, 0, 0), 0.2, 40)
    tint(ic, ic.poly_mask([(cx1, RIDGE + 30), (cx1 + 50, RIDGE + 60), (cx1 + 50, RIDGE + 110), (cx1, RIDGE + 90)]),
         rmask, (0, 0, 0), 0.35, 12)  # chimney shadow on the thatch
    ridge = [(236, RIDGE - 14), (410, RIDGE - 8), (580, RIDGE - 10), (590, RIDGE + 12), (410, RIDGE + 18),
             (228, RIDGE + 12)]
    ic.fill(ic.poly_mask(ridge), "#a08254", "#5a462a", (RIDGE - 16, RIDGE + 18), noise=0.2)
    ic.overlay(lambda d: [d.line([(x, RIDGE - 8), (x + 22, RIDGE + 12)], fill=(60, 42, 22, 120),
                                 width=3) for x in range(244, 572, 34)])
    ic.outline(ridge, 4)
    ic.outline(roof, 6)
    # thick rounded eave of the thatch
    eave = [(138, EAVE - 2), (676, EAVE - 2), (674, EAVE + 26)]
    for x in np.arange(668, 140, -14):  # ragged cut straw ends
        eave.append((x, EAVE + 30 + ic.random.uniform(-5, 6)))
    eave.append((140, EAVE + 26))
    em = ic.poly_mask(eave)
    ic.fill(em, "#9a7c4e", "#3a2a16", (EAVE - 2, EAVE + 34), noise=0.22)
    ic.overlay(lambda d: [d.line([(x, EAVE + 2), (x + ic.random.uniform(-3, 3), EAVE + 30)],
                                 fill=(30, 18, 8, int(ic.random.uniform(40, 130))), width=3)
                          for x in np.arange(142, 672, 7)], em)
    ic.line([(140, EAVE), (674, EAVE)], 5, (230, 204, 150, 90))
    ic.outline(eave, 4)

    # ---- guest-room floor: jettied, half-timbered
    ic.plaster_frame((L, EAVE + 30, R, BAND), posts=(L + 12, 296, 404, 514, R - 12),
                     braces=(((404, BAND), (514, EAVE + 30)), ((514, BAND), (404, EAVE + 30))),
                     wall="#d6c29c", wall_dark="#ac946e")
    upper = ic.mask("rectangle", (L, EAVE + 30, R, BAND))
    for x0, y0, x1, y1 in ((214, 506, 262, 578), (330, 504, 374, 576), (556, 508, 600, 574)):
        ic.window(x0, y0, x1, y1)
        tint(ic, ic.mask("rectangle", (x0 - 10, y1 + 10, x1 + 14, y1 + 26)), upper, (0, 0, 0), 0.25, 6)
    ic.rect((200, 590, 276, 604), "#7a5436", "#4e3420", edge=3)  # flower box sill
    for x in (214, 236, 258):
        ic.fill(ic.mask("ellipse", (x - 12, 574, x + 12, 596)), "#7a8a44", "#3a4a1c", noise=0.2)
    tint(ic, ic.mask("rectangle", (L, EAVE + 30, R, EAVE + 84)), upper, (0, 0, 0), 0.45, 12)
    for _ in range(8):
        x = ic.random.uniform(L, R)
        tint(ic, ic.mask("ellipse", (x - 40, 540, x + 40, 640)), upper, (60, 40, 20), 0.12, 20)

    # ---- stone taproom
    wall = ic.mask("rectangle", (L + 10, BAND, R - 10, BASE))
    stones(ic, (L + 10, BAND, R - 10, BASE), "#a29282", "#685a4c", course=38)
    tint(ic, ic.mask("rectangle", (L, BASE - 90, R, BASE)), wall, (40, 44, 20), 0.22, 24)
    tint(ic, ic.mask("rectangle", (L, BAND, R, BAND + 60)), wall, (0, 0, 0), 0.45, 14)
    ic.rect((L - 14, BAND - 12, R + 12, BAND + 12), "#6e4c32", "#48301f")  # jetty beam
    for x in (L + 20, 300, 420, 540):  # joist ends under the jetty
        ic.rect((x, BAND + 8, x + 18, BAND + 24), "#6a4830", "#3e2818", edge=3)
    ic.outline([(L + 10, BAND), (R - 10, BAND), (R - 10, BASE), (L + 10, BASE)], 5)
    ic.window(224, 700, 290, 790)
    ic.window(510, 700, 570, 790)
    for x0, x1, y in ((214, 300, 790), (500, 580, 790)):
        tint(ic, ic.mask("rectangle", (x0, y + 10, x1 + 10, y + 36)), wall, (0, 0, 0), 0.3, 6)
    # taproom door: arched, stone surround, light spilling onto the step? no: kept dark
    ic.door(360, 716, 450, BASE - 6)
    tint(ic, ic.mask("rectangle", (440, 700, 480, BASE)), wall, (0, 0, 0), 0.25, 10)
    # lantern beside the door
    ic.line([(474, 712), (500, 712)], 6, IRON)
    ic.poly([(484, 716), (504, 716), (508, 748), (480, 748)], "#6a5c3a", "#2e2616", edge=3)
    ic.fill(ic.mask("rectangle", (488, 724, 500, 742)), "#e8b862", "#9a6a2a", noise=0.05)

    # ---- stable wing: gable to the front, boarded walls, hay loft
    gable = [(SX0 + 6, SEAVE), (SX1 - 6, SEAVE), (SCX, SAPEX + 26)]
    gm = ic.poly_mask(gable)
    planks(ic, (SX0, SAPEX, SX1, SEAVE), "#a08262", "#5a4430", board=28, clip=gm)
    tint(ic, ic.mask("rectangle", (SX0, SAPEX, SX1, SAPEX + 150)), gm, (0, 0, 0), 0.35, 20)
    # hay loft door with hay spilling out
    lx0, lx1, ly0, ly1 = SCX - 46, SCX + 44, 500, 596
    ic.rect((lx0 - 12, ly0 - 12, lx1 + 12, ly1 + 6), "#6e4e32", "#43301e", edge=4)
    ic.rect((lx0, ly0, lx1, ly1), "#241810", "#0c0806", noise=0.1, edge=0)
    hay(ic, [(lx0 + 2, ly1), (lx0 + 4, 560), (lx0 + 30, 540), (SCX + 10, 548), (lx1 - 4, 556), (lx1 + 10, ly1 + 4)],
        strands=60)
    ic.line([(SCX, SAPEX + 40), (SCX, ly0 - 12)], 14, (96, 66, 42))  # hoist beam end
    ic.rect((SCX - 16, SAPEX + 50, SCX + 16, SAPEX + 72), "#7a5436", "#4a3220", edge=3)
    # lower walls
    lower = ic.mask("rectangle", (SX0, SEAVE, SX1, BASE))
    planks(ic, (SX0, SEAVE, SX1, BASE), "#94765a", "#4c3826", board=30)
    tint(ic, ic.mask("rectangle", (SX0, BASE - 80, SX1, BASE)), lower, (30, 34, 14), 0.25, 20)
    ic.beam((SX0 + 8, SEAVE), (SX0 + 8, BASE), 22, (98, 68, 44))
    ic.beam((SX1 - 8, SEAVE), (SX1 - 8, BASE), 22, (92, 64, 42))
    ic.beam((SX0, SEAVE + 6), (SX1, SEAVE + 6), 20, (98, 68, 44))
    tint(ic, ic.mask("rectangle", (SX0, SEAVE + 16, SX1, SEAVE + 60)), lower, (0, 0, 0), 0.4, 12)
    # stable doorway: dark stall, horse over the half door, upper leaf swung open
    ox0, ox1, oy0 = 690, 866, 652
    ic.rect((ox0, oy0, ox1, BASE), "#20160e", "#0a0604", noise=0.1, edge=0)
    tint(ic, ic.mask("rectangle", (ox0, oy0, ox1, oy0 + 60)), None, (0, 0, 0), 0.4, 10)
    with ic.clipped(ic.mask("rectangle", (ox0 - 6, oy0, ox1, BASE))):
        horse_head(ic, dx=4, dy=4)
    ic.beam((ox0 - 14, oy0 - 8), (ox1 + 14, oy0 - 8), 24, (104, 72, 46))
    half = ic.mask("rectangle", (ox0, 842, ox1, BASE))
    planks(ic, (ox0, 842, ox1, BASE), "#9a7a52", "#5a4028", board=26, clip=half)
    ic.beam((ox0, 848), (ox1, 848), 12, (84, 58, 36))
    ic.beam((ox0 + 8, 858), (ox1 - 8, 892), 12, (84, 58, 36))
    ic.outline([(ox0, 842), (ox1, 842), (ox1, BASE), (ox0, BASE)], 4)
    tint(ic, ic.mask("rectangle", (ox0, 842, ox1, 870)), half, (0, 0, 0), 0.0 + 0.3, 6)
    leaf = [(ox1 + 6, oy0 + 4), (ox1 + 70, oy0 - 8), (ox1 + 70, 800), (ox1 + 6, 810)]
    lm = ic.poly_mask(leaf)
    planks(ic, (ox1, oy0 - 10, ox1 + 72, 812), "#8a6c48", "#4a3420", board=22, clip=lm)
    tint(ic, lm, lm, (0, 0, 0), 0.2)
    ic.outline(leaf, 4)
    tint(ic, ic.poly_mask([(ox1 + 70, oy0), (ox1 + 96, oy0 + 10), (ox1 + 96, 806), (ox1 + 70, 800)]), lower,
         (0, 0, 0), 0.35, 8)
    ic.outline([(SX0, SEAVE), (SX1, SEAVE), (SX1, BASE), (SX0, BASE)], 5)

    # ---- stable roof: wooden shingles, both verges seen from slightly above
    left = [(SCX, SAPEX - 8), (SX0 - 36, SEAVE - 6), (SX0 - 12, SEAVE + 24), (SCX, SAPEX + 34)]
    right = [(SCX, SAPEX - 8), (SX1 + 36, SEAVE - 6), (SX1 + 12, SEAVE + 24), (SCX, SAPEX + 34)]
    shingles(ic, left, "#8c7a64", "#54483a", course=20, stagger=26, edge=6)
    rm = shingles(ic, right, "#6e604e", "#40362c", course=20, stagger=26, edge=6)
    tint(ic, rm, rm, (0, 0, 0), 0.15)
    ic.beam((SCX - 4, SAPEX - 26), (SCX + 4, SAPEX + 2), 10, (92, 64, 42))  # gable finial
    tint(ic, ic.poly_mask([(SCX, SAPEX + 30), (SX0 - 10, SEAVE + 20), (SX0 + 40, SEAVE + 40), (SCX, SAPEX + 80)]), gm,
         (0, 0, 0), 0.35, 12)

    # ---- the tankard sign on a scrolled iron bracket off the inn's left corner
    by = 560
    ic.line([(L + 2, by), (22, by)], 16, IRON)
    ic.line([(L + 2, by + 90), (96, by + 4)], 12, IRON)
    ic.draw.arc((10, by - 16, 40, by + 14), 90, 360, fill=IRON + (255,), width=8)
    ic.draw.arc((110, by + 6, 150, by + 46), 180, 450, fill=IRON + (255,), width=6)
    tx0, tx1, ty0, ty1 = 24, 158, 634, 808
    for x0, x1 in ((50, 60), (132, 128)):
        ic.line([(x0, by + 6), (x1, ty0 - 4)], 5, (60, 56, 52))
        for y in np.arange(by + 14, ty0 - 6, 14):
            f = (y - by) / (ty0 - by)
            xx = x0 + (x1 - x0) * f
            ic.draw.ellipse((xx - 4, y - 5, xx + 4, y + 5), outline=(80, 74, 68, 255), width=2)
    tankard(ic, tx0, ty0, tx1, ty1)

    # ---- plinth
    stones(ic, (L - 6, BASE - 14, SX1 + 8, BASE + 12), "#867a6a", "#5a5046", course=26, moss=0.0)
    ic.outline([(L - 6, BASE - 14), (SX1 + 8, BASE - 14), (SX1 + 8, BASE + 12), (L - 6, BASE + 12)], 4)

    # ---- props: casks by the taproom door, trough in front of the stable, hay heap at the corner
    tint(ic, ic.mask("ellipse", (470, BASE - 30, 650, BASE + 30)), None, (0, 0, 0), 0.4, 12)
    cask(ic, 486, 806, 566, 928)
    cask(ic, 560, 834, 628, 936, wood=("#a47448", "#44281a"))
    trough = [(630, 870), (790, 870), (780, 934), (640, 934)]
    ic.poly(trough, "#8a6a48", "#48321e", edge=5)
    ic.fill(ic.mask("rectangle", (640, 872, 780, 888)), "#8aa4a8", "#3e5a62", noise=0.08)
    ic.line([(650, 878), (700, 878)], 3, (220, 234, 236, 160))
    ic.line([(630, 870), (790, 870)], 8, (104, 76, 50))
    tint(ic, ic.mask("rectangle", (640, 896, 790, 934)), ic.poly_mask(trough), (0, 0, 0), 0.3, 8)
    mound = [(840 + 180 * t + ic.random.uniform(-4, 4), 944 - 126 * math.sin(math.pi * t) ** 0.55 + ic.random.uniform(-6, 6))
             for t in np.linspace(0, 1, 16)]
    tint(ic, ic.mask("ellipse", (830, 920, 1020, 960)), None, (0, 0, 0), 0.4, 10)
    hay(ic, mound)
