"""Slave Gang Barracks (slave_labor_yard): a long, low barrack block behind a sharpened-log stockade.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/slave_labor_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/slave_labor_yard

Identity: a long grim barrack block of grey rubble under a heavy dark stone-slab roof with a row
of small barred windows, shut in by a stockade of sharpened logs with a barred plank gate; iron
shackles hang from a hook on the gatepost. Sober, not lurid: no people, no whips, no blood.
Supporting props: ration sacks and a water butt by the gate. Labour-yard family helpers (shared
by rural_daywork_yard, hired_labor_yard, slave_labor_yard): ``union``, ``tint``, ``paste_clipped``,
``shingles``, ``timber``, ``planks``, ``weeds``, ``earth`` (from the hiring fair), ``stones``,
``sack`` (porters' hall); local: ``logs``, ``shackles``, ``butt``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 3
REFS = ("barracks", "stockade", "slave_market", "slave_center")

BASE = 880  # foot of the barrack walls (hidden behind the stockade)
GROUND = 932  # front edge of the yard
BX0, BX1 = 64, 960  # barrack walls
EAVE, RIDGE = 470, 318
PTOP = 640  # tips of the stockade logs
GX0, GX1 = 432, 610  # gate
IRON = (38, 36, 36)


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


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar where every block is a form: tone variation, lit top-left edge, shadowed
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
    paste_clipped(ic, lay, m)


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack: slumped round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        y = base - h * 0.42 + s * h * 0.42
        if s > 0.6:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    for f in (-0.18, 0.12):
        ic.line([(cx + w * f, base - h * 0.78), (cx + w * f * 1.6, base - h * 0.2)], 3, (70, 58, 40, 90))
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.14, base - h * 0.8), (nx - w * 0.1, base - h * 1.02), (nx - w * 0.2, base - h * 1.12),
            (nx + w * 0.02, base - h * 1.08), (nx + w * 0.2, base - h * 1.14), (nx + w * 0.12, base - h * 1.0),
            (nx + w * 0.15, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.1, w * 0.5), noise=0.14)
    ic.outline(neck, 3, (60, 48, 32, 150))
    ic.line([(nx - w * 0.13, base - h * 0.96), (nx + w * 0.13, base - h * 0.95)], 6, (96, 72, 44))
    ic.outline(pts, 4, (56, 44, 30, 160))



# ---------------------------------------------------------------- local helpers
def logs(ic: Icon, x0, x1, top, base, jag: float = 26) -> Image.Image:
    """Palisade of round, sharpened logs: each lit on its left, bark streaks, a darker foot, tips of
    uneven height. Returns the mask."""
    R = ic.random
    whole = Image.new("L", (ic.size, ic.size), 0)
    x = x0
    while x < x1:
        w = R.uniform(40, 52)
        xa, xb = x, min(x + w, x1)
        t = top + R.uniform(-jag, jag * 0.6)
        mid = (xa + xb) / 2 + R.uniform(-3, 3)
        pts = [(xa, base), (xa, t + 26), (mid, t), (xb, t + 24), (xb, base)]
        m = ic.poly_mask(pts)
        tone = R.uniform(0.86, 1.08)
        c1 = tuple(int(v * tone) for v in (152, 108, 66))
        c2 = tuple(int(v * tone) for v in (60, 38, 20))
        ic.fill(m, c1, c2, (xa, xb + 6), vertical=False, noise=0.2)

        def bark(d: ImageDraw.ImageDraw, xa=xa, xb=xb, t=t) -> None:
            for _ in range(5):
                bx = R.uniform(xa + 4, xb - 4)
                by = R.uniform(t + 30, base - 40)
                d.line([(bx, by), (bx + R.uniform(-2, 2), by + R.uniform(30, 90))], fill=(34, 22, 14, 110), width=3)
            d.line([(xa + 6, t + 30), (xa + 6, base)], fill=(255, 236, 200, 60), width=4)

        ic.overlay(bark, m)
        tip = ic.poly_mask([(xa, t + 26), (mid, t), (xb, t + 24), (xb, t + 40), (xa, t + 42)])
        tint(ic, tip, m, (220, 190, 150), 0.25)  # fresh-cut point, paler
        ic.outline(pts, 4, (36, 24, 16, 200))
        whole = ImageChops.lighter(whole, m)
        x += w - 2
    tint(ic, ic.mask("rectangle", (x0, base - 70, x1, base)), whole, (30, 32, 18), 0.3, 18)
    return whole


def shackles(ic: Icon, hx, hy, k: float = 1.4) -> None:
    """Pair of open iron shackles hanging on a hook from a short chain."""
    ln = lambda pts, w, col=IRON: ic.line([(hx + x * k, hy + y * k) for x, y in pts], int(w * k), col)  # noqa: E731
    ln([(-10, -10), (14, 0), (10, 18)], 8)
    y, x = 18, 10
    for i in range(5):
        cx, cy = hx + x * k, hy + y * k
        if i % 2:
            ic.draw.ellipse((cx - 5 * k, cy - 10 * k, cx + 5 * k, cy + 10 * k), outline=IRON + (255,), width=int(4 * k))
        else:
            ic.draw.ellipse((cx - 9 * k, cy - 6 * k, cx + 9 * k, cy + 6 * k), outline=IRON + (255,), width=int(4 * k))
        ic.overlay(lambda d, cx=cx, cy=cy: d.arc((cx - 7 * k, cy - 7 * k, cx + 7 * k, cy + 7 * k), 190, 260,
                                                 fill=(170, 164, 156, 150), width=3))
        y += 16
        x += (-1) ** i * 3
    ex, ey = x, y - 16
    for dx in (-34, 34):  # the two cuffs on short chains
        cx, cy = ex + dx, ey + 44
        ln([(ex, ey + 8), (ex + dx * 0.5, ey + 22), (cx, cy - 22)], 6)
        X, Y = hx + cx * k, hy + cy * k
        r = 22 * k
        ic.draw.ellipse((X - r, Y - r * 0.92, X + r, Y + r * 0.92), outline=IRON + (255,), width=int(10 * k))
        ic.overlay(lambda d, X=X, Y=Y, r=r: d.arc((X - r + 3, Y - r * 0.92 + 3, X + r - 3, Y + r * 0.92 - 3), 190, 280,
                                                  fill=(176, 170, 160, 170), width=4))
        ic.draw.rectangle((X - 6 * k, Y + r * 0.8, X + 6 * k, Y + r * 0.8 + 12 * k), fill=IRON + (255,))


def butt(ic: Icon, x0, y0, x1, y1) -> None:
    """Weathered water butt: dark staves, two hoops, a dipper hanging on the rim."""
    w, h = x1 - x0, y1 - y0
    pts = [(x0, y0), (x1, y0), (x1 - w * 0.04, y1), (x0 + w * 0.04, y1)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#8a6a4a", "#3a2818", (x0 + w * 0.1, x1), vertical=False, noise=0.16)
    ic.overlay(lambda d: [d.line([(x0 + w * f, y0 + 6), (x0 + w * f, y1 - 4)], fill=(40, 26, 14, 110), width=3)
                          for f in (0.22, 0.44, 0.66, 0.86)], m)
    for f in (0.2, 0.8):
        ic.line([(x0 - 3, y0 + h * f), (x1 + 3, y0 + h * f)], 10, (52, 50, 48))
    ic.fill(ic.mask("ellipse", (x0 - 2, y0 - 14, x1 + 2, y0 + 14)), "#6a5038", "#3a2818", noise=0.12)
    ic.fill(ic.mask("ellipse", (x0 + 8, y0 - 8, x1 - 8, y0 + 8)), "#4a5a5c", "#1e2628", noise=0.08)
    ic.outline(pts, 4, (36, 24, 14, 200))
    ic.line([(x1 - 20, y0 - 6), (x1 + 20, y0 + 40)], 8, (110, 84, 56))
    ic.fill(ic.mask("ellipse", (x1 + 8, y0 + 34, x1 + 40, y0 + 56)), "#8a6a4a", "#3a2818", noise=0.1)


# ---------------------------------------------------------------- parts
def barrack(ic: Icon) -> None:
    """The long barrack block: grey rubble walls, heavy slab roof, small barred windows, two squat
    chimneys, no ornament."""
    # chimneys behind the ridge
    for cx in (270, 740):
        box = (cx - 34, RIDGE - 78, cx + 34, RIDGE + 20)
        stones(ic, box, "#8e887c", "#56524a", course=24, moss=0.0)
        tint(ic, ic.mask("rectangle", (cx, box[1], box[2], box[3])), ic.mask("rectangle", box), (0, 0, 0), 0.3, 6)
        ic.outline([(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])], 4)
        ic.rect((box[0] - 8, box[1] - 10, box[2] + 8, box[1] + 8), "#7a756c", "#4a4640", edge=4)
    # walls
    wall = ic.mask("rectangle", (BX0, EAVE, BX1, BASE))
    stones(ic, (BX0, EAVE, BX1, BASE), "#8a8378", "#524d46", course=34, moss=0.08)
    tint(ic, ic.mask("rectangle", (BX0, EAVE, BX1, EAVE + 70)), wall, (0, 0, 0), 0.5, 14)
    streaks = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(streaks)
    for _ in range(26):
        x = ic.random.uniform(BX0 + 10, BX1 - 10)
        y = ic.random.uniform(EAVE + 20, EAVE + 120)
        sd.line([(x, y), (x + ic.random.uniform(-3, 3), y + ic.random.uniform(60, 200))], fill=255,
                width=int(ic.random.uniform(6, 14)))
    tint(ic, streaks, wall, (40, 34, 26), 0.25, 5)
    tint(ic, ic.mask("rectangle", (BX1 - 200, EAVE, BX1, BASE)), wall, (0, 0, 0), 0.22, 50)
    # small barred windows set high, one to a bay, a little off the grid
    xs = np.linspace(BX0 + 70, BX1 - 70, 9)
    for i, x in enumerate(xs):
        x += ic.random.uniform(-8, 8)
        y0 = 540 + ic.random.uniform(-4, 4)
        x0, x1, y1 = x - 22, x + 22, y0 + 50
        ic.rect((x0 - 8, y0 - 8, x1 + 8, y1 + 8), "#8a8478", "#56524a", edge=3)
        ic.rect((x0, y0, x1, y1), "#1e1c1c", "#0c0a0a", noise=0.05, edge=0)
        for f in (0.28, 0.5, 0.72):
            ic.line([(x0 + (x1 - x0) * f, y0), (x0 + (x1 - x0) * f, y1)], 5, (74, 70, 66))
        tint(ic, ic.mask("rectangle", (x0 - 8, y1 + 8, x1 + 16, y1 + 40)), wall, (30, 24, 18), 0.3, 6)
    ic.outline([(BX0, EAVE), (BX1, EAVE), (BX1, BASE), (BX0, BASE)], 5)
    # heavy, low-pitched roof of dark stone slabs
    roof = [(BX0 - 40, EAVE + 14), (BX0 + 70, RIDGE), (BX1 - 70, RIDGE - 4), (BX1 + 40, EAVE + 14)]
    rm = shingles(ic, roof, "#76685a", "#382e28", course=30, stagger=58, edge=7)
    tint(ic, ic.poly_mask([(BX0 - 40, RIDGE), (360, RIDGE), (300, EAVE + 14), (BX0 - 40, EAVE + 14)]), rm,
         (230, 220, 200), 0.12, 40)
    tint(ic, ic.poly_mask([(640, RIDGE), (BX1 + 40, RIDGE), (BX1 + 40, EAVE + 14), (700, EAVE + 14)]), rm, (0, 0, 0),
         0.2, 40)
    for _ in range(8):  # lichen and soot on the slabs
        x, y = ic.random.uniform(BX0, BX1), ic.random.uniform(RIDGE + 20, EAVE)
        tint(ic, ic.mask("ellipse", (x - 60, y - 18, x + 60, y + 18)), rm,
             ic.random.choice([(120, 124, 80), (20, 18, 16)]), 0.2, 12)
    ic.line([(BX0 + 68, RIDGE - 2), (BX1 - 68, RIDGE - 6)], 14, (50, 46, 42))
    ic.line([(BX0 + 68, RIDGE - 6), (BX1 - 68, RIDGE - 10)], 4, (190, 184, 170, 100))
    tint(ic, ic.mask("rectangle", (BX0, EAVE + 14, BX1, EAVE + 50)), None, (0, 0, 0), 0.35, 10)


def stockade(ic: Icon) -> None:
    """Sharpened-log stockade across the front with a barred plank gate and the shackles."""
    tint(ic, ic.mask("rectangle", (20, PTOP - 20, 1004, PTOP + 40)), None, (0, 0, 0), 0.3, 20)  # shadow on the wall
    logs(ic, 16, GX0 - 26, PTOP, GROUND - 6, jag=34)
    logs(ic, GX1 + 26, 1008, PTOP + 6, GROUND - 6, jag=34)
    # ribbands pegged across the logs
    for y in (PTOP + 90, GROUND - 90):
        timber(ic, (16, y), (GX0 - 26, y + 4), 18, "#7a5a3c", "#44301e")
        timber(ic, (GX1 + 26, y + 2), (1008, y - 2), 18, "#7a5a3c", "#44301e")
    # gate: heavy posts, a lintel and a barred plank leaf
    gm = planks(ic, [(GX0, PTOP + 30), (GX1, PTOP + 30), (GX1, GROUND - 6), (GX0, GROUND - 6)], "#8a7052", "#4a3826",
                board=30)
    tint(ic, ic.mask("rectangle", (GX0, PTOP + 30, GX1, PTOP + 80)), gm, (0, 0, 0), 0.35, 12)
    for y in (PTOP + 70, 836):
        timber(ic, (GX0, y), (GX1, y), 20, "#7a5c3e", "#44301e")
    timber(ic, (GX0 + 10, 830), (GX1 - 10, PTOP + 76), 18, "#7a5c3e", "#44301e")
    for x in (GX0 + 24, GX1 - 24):  # iron straps and studs
        for y in (PTOP + 100, 790, 880):
            ic.draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=IRON + (255,))
    # locking bar across the leaf in iron staples
    ic.rect((GX0 - 14, 752, GX1 + 14, 774), "#5a5652", "#2a2826", edge=4)
    for x in (GX0 + 6, GX1 - 6):
        ic.rect((x - 8, 744, x + 8, 782), "#3a3836", "#1e1c1c", edge=3)
    ic.outline([(GX0, PTOP + 30), (GX1, PTOP + 30), (GX1, GROUND - 6), (GX0, GROUND - 6)], 5)
    for x in (GX0 - 13, GX1 + 13):
        timber(ic, (x, GROUND - 4), (x, PTOP - 30), 34, "#8a6a48", "#4a3220")
        ic.poly([(x - 18, PTOP - 30), (x, PTOP - 56), (x + 18, PTOP - 30)], "#9a7a58", "#5a4028", edge=4)
    timber(ic, (GX0 - 40, PTOP - 4), (GX1 + 40, PTOP - 8), 26, "#8e6c48", "#4e3522")
    tint(ic, ic.mask("rectangle", (GX0, PTOP + 6, GX1, PTOP + 40)), None, (0, 0, 0), 0.35, 8)
    shackles(ic, GX1 + 42, PTOP + 40)


def props(ic: Icon) -> None:
    """Ration sacks and a water butt outside the stockade, left of the gate."""
    tint(ic, ic.mask("ellipse", (180, 900, 420, 944)), None, (0, 0, 0), 0.4, 12)
    butt(ic, 318, 812, 396, 934)
    sack(ic, 236, 936, 104, 110, c=("#b8aa8a", "#6a5e48"))
    sack(ic, 170, 938, 92, 86, c=("#aa9a7a", "#5e5240"), lean=0.4)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    earth(ic, 8, 1016, BASE - 10, GROUND + 10, c=("#8e7e66", "#5e5040"))
    barrack(ic)
    stockade(ic)
    props(ic)
    for x in (60, 700, 980):
        weeds(ic, x, GROUND - 4, 34, tall=0.8)
