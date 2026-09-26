"""Hiring Fair (rural_daywork_yard): an open thatched village work shed with its tool rack and a hiring booth.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/rural_daywork_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/rural_daywork_yard

Identity: field tools (a scythe leaning on the left post with its blade hanging past the eave, a
hay fork on the right) against the dark open front of a low golden-thatched work shed, and a small
plank hiring booth with a faded canvas awning where the day's ale is poured; a green bough on a
pole marks the fair. Supporting props: harvest sheaves (Harvest Gangs), a heap of straw, a cart
wheel and straw inside the shed. No people.
Labour-yard family helpers (shared by rural_daywork_yard, hired_labor_yard, slave_labor_yard):
``union``, ``tint``, ``paste_clipped``, ``shingles``, ``timber``, ``planks`` (from the victualling
yard), ``thatch``, ``hay`` (from the tavern), ``weeds`` (from the road wardens' yard), plus new
``earth`` (trampled yard strip), ``haft`` (round tool handle), ``steel`` (forged blade) and the
tool heads ``scythe``, ``rake``, ``fork``; local: ``sheaf``, ``jug``, ``cup``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("market_village", "farming_village", "free_village", "tools_workshop")

BASE = 884  # foot of the shed and booth
GROUND = 930  # front edge of the trampled yard
SX0, SX1 = 50, 636  # shed front posts
SEAVE, SRIDGE = 520, 196
BX0, BX1 = 680, 952  # hiring booth
IRON = (40, 38, 36)


# ---------------------------------------------------------------- helpers (labour-yard family finish)
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


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, soft course shadow. Returns the mask."""
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
    paste_clipped(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    if edge:
        ic.outline(pts, edge)
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> Image.Image:
    """Squared beam as a polygon: lit upper/left half, darker other half, a lit arris. Returns the mask."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (abs(ny) < 1e-6 and nx < 0):
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def planks(ic: Icon, pts, c1="#86603e", c2="#4e3522", board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def thatch(ic: Icon, pts, c1, c2, course: float = 44) -> Image.Image:
    """Thatched roof plane: straw strands down the slope, layered courses with a dark underside,
    weathered blotches. Returns the mask."""
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
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    paste_clipped(ic, lay, m)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(12):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 190), (150, 96, 34), (96, 66, 30)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    return m


def hay(ic: Icon, pts, strands: int = 220) -> Image.Image:
    """Loose hay/straw: golden mass lit top-left, dark underside, many straw strokes."""
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
    return m


def weeds(ic: Icon, x: float, y: float, w: float, hang: bool = False, tall: float = 1.0) -> None:
    """Tuft of grass and weeds."""
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(int(w / 4)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 36) * tall
        down = hang and R.random() < 0.5
        tip = (bx + R.uniform(-12, 12), y + (h * 0.9 if down else -h))
        col = (R.randint(92, 132), R.randint(108, 138), R.randint(48, 66), 235)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)


def earth(ic: Icon, x0, x1, top, bottom, c=("#9c8462", "#6a5438")) -> Image.Image:
    """Trampled yard: a thin strip of earth seen from above, clods and footprints, a darker lip."""
    pts = [(x0 + 30, top), (x1 - 30, top), (x1, bottom), (x0, bottom)]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (top, bottom), noise=0.3, chroma=0.08)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    R = ic.random
    for _ in range(int((x1 - x0) / 3)):
        x, y = R.uniform(x0, x1), R.uniform(top + 2, bottom - 2)
        r = R.uniform(3, 8)
        d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(54, 40, 26, 110) if R.random() < 0.55 else
                  (238, 222, 190, 80))
    paste_clipped(ic, lay, m)
    tint(ic, ic.mask("rectangle", (0, bottom - 12, ic.size, bottom)), m, (20, 12, 6), 0.35, 5)
    ic.outline(pts, 5, (40, 28, 18, 190))
    return m


def haft(ic: Icon, base, top, width: float = 18, wood=("#94724c", "#4e3820")) -> None:
    """Round tool handle, weathered mid-brown, lit on its left edge, darker right, a grime band near the grip."""
    (x0, y0), (x1, y1) = base, top
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L  # normal pointing to the right of the handle
    if nx < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], (min(x0, x1) - h, max(x0, x1) + h), vertical=False, noise=0.12)
    right = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(right), m), (30, 16, 6), 0.35)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (240, 214, 170, 70))
    grip = [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f) for f in (0.55, 0.7)]
    ic.line(grip, int(width), (60, 40, 22, 60))
    ic.outline(pts, 4, (40, 26, 14, 190))


def steel(ic: Icon, pts, edge_pts=None, c=("#b4b2ac", "#4c4a48")) -> Image.Image:
    """Forged iron blade: lit top-left to dark, a bright honed edge along ``edge_pts``. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c[0], c[1], radial=(min(xs), min(ys), max(max(xs) - min(xs), max(ys) - min(ys)) * 1.1), noise=0.1,
            chroma=0.03)
    for _ in range(3):  # rust and hammer marks
        x, y = ic.random.uniform(min(xs), max(xs)), ic.random.uniform(min(ys), max(ys))
        tint(ic, ic.mask("ellipse", (x - 14, y - 8, x + 14, y + 8)), m, (110, 60, 30), 0.25, 5)
    if edge_pts:
        ic.line(edge_pts, 5, (236, 234, 226, 200))
    ic.outline(pts, 4, (30, 28, 28, 210))
    return m


def _tool_frame(base, length, lean):
    """Top of a leaning handle and a helper turning local head points (x across, y down the handle)."""
    a = math.radians(lean)
    top = (base[0] + length * math.sin(a), base[1] - length * math.cos(a))
    return top, (lambda pts: Icon.rotate(pts, top, lean))


def scythe(ic: Icon, base, length, lean=0.0, flip=False, reach=270.0) -> None:
    """Scythe stood on its heel: long snath with a hand peg, curved blade at the top sweeping sideways."""
    top, turn = _tool_frame(base, length, lean)
    s = -1 if flip else 1
    haft(ic, base, top, 26, ("#8e6c46", "#4a3420"))
    peg = turn([(0, length * 0.42), (s * 40, length * 0.40)])
    ic.line(peg, 12, (60, 40, 22))
    ic.line(peg, 7, (180, 146, 100))
    ts = np.linspace(0, 1, 18)
    back = [(s * (-8 - reach * t), 1.3 * (-8 + 24 * t * t - 34 * math.sin(math.pi * t) * 0.6)) for t in ts]
    edge = [(s * (-8 - reach * t), 1.3 * (30 - 10 * t + 20 * t * t - 20 * math.sin(math.pi * t) * 0.6 + 8 * t)) for t in ts]
    edge[-1] = back[-1]
    blade = turn(back + edge[::-1])
    steel(ic, blade, turn(edge[2:-1]))
    ic.fill(ic.poly_mask(turn([(-14, -12), (14, -12), (14, 40), (-14, 40)])), "#5a5654", "#2a2826", noise=0.08)


def rake(ic: Icon, base, length, lean=0.0, width=150, teeth=9) -> None:
    """Wooden hay rake: long handle, a head bar across the top with a row of pegs, two bracing bows."""
    top, turn = _tool_frame(base, length, lean)
    haft(ic, base, top, 24)
    for i in range(teeth):
        x = -width / 2 + 10 + (width - 20) * i / (teeth - 1)
        tooth = turn([(x, -18), (x, -62)])
        ic.line(tooth, 17, (54, 36, 20))
        ic.line(tooth, 10, (206, 176, 128))
    bar = turn([(-width / 2, -20), (width / 2, -20), (width / 2, 10), (-width / 2, 10)])
    bm = ic.poly_mask(bar)
    ic.fill(bm, "#c09a68", "#6e4e2c", noise=0.14)
    tint(ic, ic.poly_mask(turn([(-width / 2, 0), (width / 2, 0), (width / 2, 10), (-width / 2, 10)])), bm, (20, 10, 4),
         0.35)
    ic.outline(bar, 4, (40, 26, 14, 190))


def fork(ic: Icon, base, length, lean=0.0) -> None:
    """Hay fork with three long iron tines on a socket."""
    top, turn = _tool_frame(base, length, lean)
    haft(ic, base, top, 24)
    ic.fill(ic.poly_mask(turn([(-15, 0), (15, 0), (10, 50), (-10, 50)])), "#5c5856", "#2a2826", noise=0.08)
    cross = turn([(-50, -8), (-32, -2), (0, 0), (32, -2), (50, -8)])
    ic.line(cross, 18, (36, 34, 32))
    for x in (-48, 0, 48):
        tine = turn([(x, -4), (x * 1.05, -70), (x * 1.08, -140)])
        ic.line(tine, 15, (34, 32, 30))
        ic.line(tine, 5, (176, 174, 166, 180))


# ---------------------------------------------------------------- local props
def sheaf(ic: Icon, cx, base, h, lean=0.0) -> None:
    """Bound sheaf of grain standing on its butt: flared stalk foot, a straw tie, a fan of bearded ears."""
    R = ic.random
    tie_y = base - h * 0.46
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    stalks = []
    for i in range(34):
        t = (i + R.uniform(-0.3, 0.3)) / 33 - 0.5
        foot = (cx + t * h * 0.46, base - R.uniform(0, 6))
        waist = (cx + t * h * 0.14 + lean * 0.3, tie_y)
        tip = (cx + t * h * 0.62 + lean + R.uniform(-6, 6), base - h * (0.98 - 0.22 * abs(t) * 2) + R.uniform(-8, 8))
        stalks.append((foot, waist, tip, t))
    for foot, waist, tip, t in stalks:  # dark stalks behind, lit ones in front
        col = (200, 164, 90) if t < 0.1 else (150, 112, 52)
        d.line([foot, waist, tip], fill=(70, 50, 20, 255), width=9, joint="curve")
        d.line([foot, waist, tip], fill=col + (255,), width=5, joint="curve")
    for foot, waist, tip, t in stalks:
        a = math.atan2(tip[1] - waist[1], tip[0] - waist[0])
        ex, ey = tip[0] + math.cos(a) * 10, tip[1] + math.sin(a) * 10
        ear = [(tip[0] + math.cos(a + s) * r, tip[1] + math.sin(a + s) * r) for s, r in ((1.6, 7), (0, 30), (-1.6, 7), (math.pi, 4))]
        lit = t < 0.15
        d.polygon(ear, fill=(222, 186, 108, 255) if lit else (166, 124, 58, 255), outline=(70, 50, 20, 255))
        d.line([(ex, ey), (ex + math.cos(a) * 16, ey + math.sin(a) * 16)], fill=(210, 180, 120, 160), width=2)
    ic.image.alpha_composite(lay)
    band = [(cx - h * 0.1 + lean * 0.3, tie_y - 10), (cx + h * 0.1 + lean * 0.3, tie_y - 8),
            (cx + h * 0.1 + lean * 0.3, tie_y + 8), (cx - h * 0.1 + lean * 0.3, tie_y + 10)]
    ic.poly(band, "#b08a4c", "#5e4420", edge=3)
    tint(ic, ic.mask("rectangle", (cx, tie_y - h * 0.6, cx + h * 0.5, base)), None, (20, 10, 0), 0.22, 14)


def jug(ic: Icon, cx, base, h) -> None:
    """Stoneware ale jug: round belly, narrow neck, strap handle, salt-glaze highlight."""
    w = h * 0.7
    ss = np.linspace(0, 1, 24)
    hw = np.interp(ss, [0, 0.18, 0.3, 0.6, 0.9, 1.0], [0.22, 0.2, 0.3, 0.5, 0.42, 0.36]) * w
    pts = [(cx - v, base - h + h * s) for s, v in zip(ss, hw)] + [(cx + v, base - h + h * s) for s, v in zip(ss[::-1], hw[::-1])]
    handle = [(cx + w * 0.2, base - h * 0.9), (cx + w * 0.62, base - h * 0.8), (cx + w * 0.62, base - h * 0.45),
              (cx + w * 0.44, base - h * 0.35)]
    ic.line(handle, 14, (60, 44, 30))
    ic.line(handle, 8, (150, 120, 90))
    m = ic.poly_mask(pts)
    ic.fill(m, "#b49a78", "#4a3a2a", radial=(cx - w * 0.3, base - h * 0.6, w * 1.1), noise=0.12)
    ic.fill(ic.intersect(m, ic.mask("rectangle", (cx - w, base - h, cx + w, base - h * 0.5))), "#8a6a4c", "#4a3424",
            noise=0.12)
    tint(ic, ic.mask("ellipse", (cx - w * 0.36, base - h * 0.5, cx - w * 0.16, base - h * 0.22)), m, (255, 246, 226),
         0.4, 4)
    ic.outline(pts, 4, (40, 28, 18, 190))


def cup(ic: Icon, cx, base, h) -> None:
    w = h * 0.8
    pts = [(cx - w / 2, base - h), (cx + w / 2, base - h), (cx + w * 0.4, base), (cx - w * 0.4, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#a47c52", "#4e3420", (cx - w / 2, cx + w / 2), vertical=False, noise=0.12)
    ic.fill(ic.mask("ellipse", (cx - w / 2, base - h - 7, cx + w / 2, base - h + 7)), "#3a2616", "#1e140c", noise=0.05)
    ic.outline(pts, 3, (40, 26, 14, 190))


# ---------------------------------------------------------------- parts
def shed(ic: Icon) -> None:
    """Low open-fronted work shed: broad hipped thatch on three rough posts, a dark interior with
    straw and a cart wheel."""
    inner = [(SX0 + 10, SEAVE + 10), (SX1 - 10, SEAVE + 10), (SX1 - 10, BASE), (SX0 + 10, BASE)]
    planks(ic, inner, "#3a2c20", "#1a120c", board=34)
    im = ic.poly_mask(inner)
    tint(ic, ic.mask("rectangle", (SX0, SEAVE, SX1, SEAVE + 200)), im, (0, 0, 0), 0.7, 30)
    hay(ic, [(SX0 + 20, BASE), (SX0 + 40, 810), (130, 776), (210, 770), (270, 800), (300, BASE)], strands=90)
    tint(ic, ic.mask("rectangle", (SX0, 740, 320, BASE)), None, (0, 0, 0), 0.5, 10)
    cx, cy, r = 470, 800, 80
    ring = ImageChops.subtract(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)),
                               ic.mask("ellipse", (cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8)))
    for i in range(8):
        a = i * math.pi / 4 + 0.2
        ic.line([(cx, cy), (cx + math.cos(a) * r * 0.85, cy + math.sin(a) * r * 0.85)], 9, (60, 44, 30))
    ic.fill(ring, "#5a4230", "#2a1e14", radial=(cx - r * 0.6, cy - r * 0.6, r * 2), noise=0.14)
    ic.draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=(50, 36, 24, 255))
    tint(ic, ic.mask("rectangle", (380, SEAVE, SX1, BASE)), None, (0, 0, 0), 0.3, 20)

    for x, lean in ((SX0 + 10, -3), (SX1 - 10, 3)):
        timber(ic, (x, BASE), (x + lean, SEAVE + 10), 34, "#8a6644", "#4a3220")
    timber(ic, (SX0 - 14, SEAVE + 26), (SX1 + 14, SEAVE + 22), 28, "#8e6a46", "#4e3522")
    for x, s in ((SX0 + 10, 1), (SX1 - 10, -1)):  # knee braces
        timber(ic, (x + s * 70, SEAVE + 32), (x + s * 8, SEAVE + 100), 16, "#7e5c3c", "#4a3220")

    # broad hipped thatch: gently rounded hips, a slightly sagging ridge
    E = SEAVE + 34
    ts = np.linspace(0, 1, 16)
    lside = [(6 + 170 * t + 14 * math.sin(math.pi * t), E - (E - SRIDGE) * (1 - (1 - t) ** 1.6)) for t in ts]
    rside = [(682 - 176 * t - 14 * math.sin(math.pi * t), E - (E - SRIDGE - 4) * (1 - (1 - t) ** 1.6)) for t in ts]
    roof = lside + [(344, SRIDGE + 8)] + rside[::-1]
    rm = thatch(ic, roof, "#d8a04e", "#7a4414", course=40)
    tint(ic, rm, rm, (206, 128, 50), 0.14)  # sun-bleached golden straw
    tint(ic, ic.poly_mask([(0, SRIDGE), (260, SRIDGE), (200, E), (0, E)]), rm, (255, 222, 150), 0.16, 50)
    tint(ic, ic.poly_mask([(440, SRIDGE), (700, SRIDGE), (700, E), (500, E)]), rm, (20, 8, 0), 0.3, 40)
    tint(ic, ic.mask("rectangle", (0, SRIDGE, 700, SRIDGE + 56)), rm, (30, 14, 2), 0.38, 16)  # under the ridge
    tint(ic, ic.mask("rectangle", (0, E - 60, 700, E)), rm, (30, 14, 2), 0.34, 18)  # the eave rolls under
    for _ in range(3):  # a little moss on the old thatch
        x, y = ic.random.uniform(80, 600), ic.random.uniform(SRIDGE + 50, SEAVE)
        tint(ic, ic.mask("ellipse", (x - 50, y - 18, x + 50, y + 18)), rm, (96, 90, 40), 0.1, 14)
    ridge = [(186, SRIDGE - 4), (344, SRIDGE + 2), (500, SRIDGE - 2), (506, SRIDGE + 14), (344, SRIDGE + 18),
             (180, SRIDGE + 14)]
    ic.fill(ic.poly_mask(ridge), "#a47c40", "#5a3c18", (SRIDGE - 14, SRIDGE + 20), noise=0.2)
    ic.overlay(lambda d: [d.line([(x, SRIDGE - 6), (x + 22, SRIDGE + 14)], fill=(60, 42, 22, 120), width=3)
                          for x in range(190, 496, 30)], ic.poly_mask(ridge))
    ic.outline(ridge, 4)
    ic.outline(roof, 6)
    eave = [(4, E - 12), (684, E - 16), (682, E + 12)]
    for x in np.arange(674, 6, -14):
        eave.append((x, E + 16 + ic.random.uniform(-5, 6)))
    eave.append((6, E + 12))
    em = ic.poly_mask(eave)
    ic.fill(em, "#8e6632", "#2e1c0a", (E - 16, E + 20), noise=0.22)
    ic.overlay(lambda d: [d.line([(x, E - 10), (x + ic.random.uniform(-3, 3), E + 16)],
                                 fill=(30, 18, 8, int(ic.random.uniform(40, 130))), width=3)
                          for x in np.arange(8, 680, 7)], em)
    ic.line([(6, E - 12), (682, E - 15)], 5, (230, 204, 150, 90))
    ic.outline(eave, 4)
    tint(ic, ic.mask("rectangle", (SX0, E + 16, SX1, E + 90)), None, (0, 0, 0), 0.4, 14)


def booth(ic: Icon) -> None:
    """Hiring booth: a small plank stall with a shingled gable, a plain faded awning and a counter with
    the ale jug and cups; a green bough on a pole marks the fair."""
    apex = (BX0 + BX1) / 2
    # fair pole with a bough and ribbons, behind the booth
    px = BX1 - 30
    haft(ic, (px, 600), (px + 4, 300), 14, ("#9a7650", "#5a3e24"))
    ic.foliage(px + 4, 300, 40, "#6a8440", "#2e4420", blobs=11)
    for dx, col in ((-30, (176, 70, 52)), (34, (200, 176, 110))):
        rib = [(px + 4, 330), (px + 4 + dx * 0.6, 380), (px + 4 + dx, 430)]
        ic.line(rib, 14, (50, 30, 20))
        ic.line(rib, 9, col)
    ic.fill(ic.mask("rectangle", (BX0 + 10, 560, BX1 - 10, 730)), "#241a12", "#100a06", noise=0.1)
    ic.line([(BX0 + 14, 634), (BX1 - 14, 634)], 10, (80, 58, 38))
    for x in (730, 770, 880):
        ic.fill(ic.mask("ellipse", (x - 16, 598, x + 16, 632)), "#5a4636", "#2a2018", noise=0.1)
    gable = [(BX0, 560), (BX1, 560), (apex, 452)]
    planks(ic, gable, "#8a6a48", "#4e3824", board=24)
    ic.outline(gable, 4, (40, 26, 16, 170))
    left = [(apex, 428), (BX0 - 34, 568), (BX0 - 18, 590), (apex, 458)]
    right = [(apex, 428), (BX1 + 34, 568), (BX1 + 18, 590), (apex, 458)]
    shingles(ic, left, "#8c7a64", "#54483a", course=20, stagger=26, edge=6)
    rm = shingles(ic, right, "#6e604e", "#40362c", course=20, stagger=26, edge=6)
    tint(ic, rm, rm, (0, 0, 0), 0.15)
    for x in (BX0 + 6, BX1 - 6):
        timber(ic, (x, BASE), (x, 564), 24, "#8a6644", "#4a3220")
    # plain faded canvas awning with a scalloped hem
    ax0, ax1, ay0, ay1 = BX0 - 20, BX1 + 20, 574, 636
    hem = [(ax1, ay1)]
    n = 6
    for i in range(n, 0, -1):
        x = ax0 + (ax1 - ax0) * i / n
        hem += [(x - (ax1 - ax0) / n / 2, ay1 + 30), (x - (ax1 - ax0) / n, ay1)]
    aw = [(BX0 + 4, ay0), (BX1 - 4, ay0)] + hem
    am = ic.poly_mask(aw)
    ic.fill(am, "#8a8a62", "#4e5236", (ay0, ay1 + 30), noise=0.18, chroma=0.06)
    tint(ic, ic.mask("rectangle", (ax0, ay1 - 8, ax1, ay1 + 34)), am, (30, 30, 10), 0.3, 4)
    tint(ic, ic.mask("rectangle", (ax0, ay0, apex - 40, ay1)), am, (255, 244, 210), 0.18, 20)
    ic.outline(aw, 4, (40, 36, 20, 190))
    tint(ic, ic.mask("rectangle", (BX0, ay1 + 20, BX1, ay1 + 90)), None, (0, 0, 0), 0.4, 16)
    front = [(BX0 - 6, 744), (BX1 + 6, 744), (BX1 + 6, BASE), (BX0 - 6, BASE)]
    fm = planks(ic, front, "#9a7852", "#56402a", board=30)
    tint(ic, ic.mask("rectangle", (BX0, BASE - 60, BX1, BASE)), fm, (30, 34, 14), 0.25, 18)
    tint(ic, ic.mask("rectangle", (BX1 - 80, 744, BX1 + 10, BASE)), fm, (0, 0, 0), 0.25, 16)
    ic.outline(front, 5)
    top = [(BX0 - 18, 728), (BX1 + 18, 728), (BX1 + 12, 748), (BX0 - 12, 748)]
    ic.poly(top, "#b48e62", "#6e5034", edge=4)
    jug(ic, 736, 730, 110)
    cup(ic, 798, 730, 34)
    cup(ic, 834, 732, 30)
    ic.fill(ic.mask("ellipse", (870, 694, 920, 732)), "#7a5a3a", "#3a2616", radial=(878, 698, 50), noise=0.14)
    ic.line([(882, 698), (908, 698)], 5, (180, 150, 90))


def rack(ic: Icon) -> None:
    """The hay fork leaning on the right half of the open front, clear of the wheel and straw."""
    tint(ic, ic.mask("ellipse", (500, 904, 640, 948)), None, (0, 0, 0), 0.4, 12)
    fork(ic, (566, 926), 410, 4)


K, AX, AY = 0.86, 1020, 950  # the scene is shrunk towards the right foot to make room for the scythe


def shrink(ic: Icon) -> None:
    """Scale everything drawn so far by ``K`` around (AX, AY), freeing the left of the canvas."""
    n = int(round(ic.size * K))
    small = ic.image.resize((n, n), Image.LANCZOS)
    out = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    out.paste(small, (int(round(AX * (1 - K))), int(round(AY * (1 - K)))))
    ic.image = out
    ic.draw = ImageDraw.Draw(out)


def hung_scythe(ic: Icon) -> None:
    """One scythe leaning on the left front post, its blade hanging sideways past the left eave."""
    base, top = (282, 932), (222, 548)
    L = math.hypot(top[0] - base[0], top[1] - base[1])
    lean = math.degrees(math.asin((top[0] - base[0]) / L))
    tint(ic, ic.mask("ellipse", (236, 916, 330, 946)), None, (0, 0, 0), 0.4, 8)
    scythe(ic, base, L, lean, reach=182)


def front(ic: Icon) -> None:
    """Harvest sheaves at the right corner, a heap of loose straw before the booth."""
    tint(ic, ic.mask("ellipse", (880, 904, 1020, 944)), None, (0, 0, 0), 0.4, 10)
    sheaf(ic, 926, 934, 240, lean=-10)
    sheaf(ic, 986, 938, 200, lean=8)
    straw = [(640 + 220 * t + ic.random.uniform(-4, 4), 936 - 50 * math.sin(math.pi * t) ** 0.6 + ic.random.uniform(-5, 5))
             for t in np.linspace(0, 1, 16)]
    tint(ic, ic.mask("ellipse", (630, 910, 870, 946)), None, (0, 0, 0), 0.35, 10)
    hay(ic, straw, strands=90)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    earth(ic, 8, 1016, BASE - 24, GROUND + 8)
    for x in range(40, 1000, 90):
        weeds(ic, x + ic.random.uniform(-20, 20), BASE - 18, ic.random.uniform(18, 34), tall=0.6)
    shed(ic)
    booth(ic)
    rack(ic)
    front(ic)
    for x in (620, 1004):
        weeds(ic, x, GROUND + 4, 30, tall=0.8)
    shrink(ic)
    hung_scythe(ic)
