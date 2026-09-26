"""Permanent Way Depot (permanent_way_depot): tier 3 of the road chain, a wagonway maintenance depot.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/permanent_way_depot/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/permanent_way_depot

Identity: the road band has become a wagonway: iron rails in chairs on timber sleepers bedded in
grey ballast, with a loaded chaldron wagon on flanged wheels. Behind stand a long brick wagon shed
with a slate roof, ridge louvre and arched doors, a criss-cross crib of spare sleepers and a stack
of rails on bearers. The largest and most industrial tier: brick and slate after the rubble lodge,
the stone shed and the works house.
Helpers: shared road-family block (``stones``, ``thatch``, ``timber``, ``planks``, ``weeds``,
``mound``, ``pole``), ``shingles`` and ``bricks`` (victualling_yard); new ``track``, ``wagon``,
``crib`` (sleeper stack) and ``rail_stack``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 29
REFS = ("construction_center", "market_warehouse", "roads", "iron_foundry")

RT, RB, RF = 800, 900, 936  # track bed: back edge, front edge, foot of the ballast shoulder
IRON = (44, 42, 40)
RAIL_FAR, RAIL_NEAR = RT + 30, RB - 30  # rail head heights
SLEEPER = ("#86664a", "#4a3624")

# ---------------------------------------------------------------- helpers (road-family finish)
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


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


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
    for _ in range(10):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> Image.Image:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it. Returns the mask."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
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


def mound(ic: Icon, x0: float, x1: float, base: float, top: float, body=("#a89a84", "#5a5044"),
          pebble: float = 9, density: float = 1.0, peb_col=((236, 226, 206), (40, 34, 28))) -> Image.Image:
    """Heap of loose material (gravel, sand, broken stone, ballast): lumpy crest, radial light from
    the upper left, shadowed right flank, a scatter of lit/dark pebbles. Returns the mask."""
    R = ic.random
    cx = (x0 + x1) / 2 + (x1 - x0) * 0.06
    ts = np.linspace(0, 1, 40)
    pts = []
    for t in ts:
        x = x0 + (x1 - x0) * t
        u = (x - cx) / ((x1 - x0) / 2)
        y = base - (base - top) * max(0.0, 1 - abs(u) ** 1.6) ** 0.9
        pts.append((x, y + R.uniform(-5, 5) * (1 - abs(u))))
    pts += [(x1, base), (x0, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, body[0], body[1], radial=(cx - (x1 - x0) * 0.25, top, (x1 - x0) * 0.85), noise=0.3, chroma=0.08)
    tint(ic, ic.mask("ellipse", (cx, top, x1 + 80, base + 60)), m, (10, 8, 6), 0.3, 30)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    n = int((x1 - x0) * (base - top) / (pebble * pebble * 2.2) * density)
    lit, dk = peb_col
    for _ in range(n):
        x = R.uniform(x0, x1)
        y = R.uniform(top, base)
        r = pebble * R.uniform(0.6, 1.3)
        a = R.randint(70, 150)
        d.ellipse((x - r, y - r * 0.75, x + r, y + r * 0.75), fill=(*dk, a))
        d.ellipse((x - r * 0.8, y - r * 0.85, x + r * 0.5, y + r * 0.2), fill=(*lit, int(a * 0.8)))
    paste_clipped(ic, lay, m)
    ic.outline(pts, 5, (40, 30, 22, 190))
    return m


def pole(ic: Icon, p0, p1, width: float, bands=("#b35a42", "#d8ccb2"), n: int = 7) -> None:
    """Barrier pole painted in bands, shaded as a round spar (lit upper edge, dark underside)."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    for i in range(n):
        a, b = i / n, (i + 1) / n
        q = [(x0 + ux * L * a - nx * h, y0 + uy * L * a - ny * h), (x0 + ux * L * b - nx * h, y0 + uy * L * b - ny * h),
             (x0 + ux * L * b + nx * h, y0 + uy * L * b + ny * h), (x0 + ux * L * a + nx * h, y0 + uy * L * a + ny * h)]
        c = bands[i % 2]
        ic.fill(ic.poly_mask(q), c, tuple(int(v * 0.8) for v in bytes.fromhex(c[1:])), noise=0.2)
    full = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(full)
    under = [(x0, y0), (x1, y1), full[2], full[3]]
    tint(ic, ic.poly_mask(under), m, (20, 10, 6), 0.4)
    ic.line([(x0 - nx * h * 0.5, y0 - ny * h * 0.5), (x1 - nx * h * 0.5, y1 - ny * h * 0.5)], 4, (255, 240, 215, 90))
    ic.outline(full, 4, (40, 26, 16, 190))


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7,
             vary: float = 1.0, hues=()) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, soft course shadow; ``vary``
    scales the per-tile tone, ``hues`` are extra slate colours given to a share of tiles. Returns the mask."""
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
            if hues and ic.random.random() < 0.3:
                td.polygon(q, fill=tuple(ic.random.choice(hues)) + (int(rnd(40, 80)),))
            td.polygon(q, fill=(20, 10, 6, int(min(255, -t * 60 * vary))) if t < 0 else
                       (255, 236, 210, int(min(255, t * 40 * vary))))
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


def bricks(ic: Icon, m: Image.Image, box, base="#94604a", dark="#5c3a2c", course: float = 17, length: float = 40) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            if ic.random.random() < 0.07:  # over-burnt header
                col = (40, 22, 18, 90)
            else:
                col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(196, 176, 150, 38), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(196, 176, 150, 46), width=3)
        d.line([(x0, y + course + 2), (x1, y + course + 2)], fill=(24, 12, 8, 50), width=2)
        y += course
        k += 1
    paste_clipped(ic, lay, m)


def rail(ic: Icon, x0: float, x1: float, y: float, web: float = 16) -> None:
    """Iron rail seen from the side and a little above: bright worn head, dark web, shadow below."""
    tint(ic, ic.mask("rectangle", (x0, y + web - 2, x1, y + web + 12)), None, (0, 0, 0), 0.45, 5)
    ic.fill(ic.mask("rectangle", (x0, y, x1, y + web)), "#5a5652", "#262422", (y, y + web), noise=0.12)
    ic.fill(ic.mask("rectangle", (x0, y - 5, x1, y + 3)), "#96928a", "#66625c", (y - 5, y + 3), noise=0.1)
    ic.line([(x0 + 4, y - 3), (x1 - 4, y - 3)], 2, (226, 222, 212, 170))  # one thin worn highlight
    tint(ic, ic.mask("rectangle", (x0, y + 3, x1, y + web)), None, (110, 60, 30), 0.25, 4)  # rust on the web
    ic.line([(x0, y - 6), (x1, y - 6)], 3, (40, 30, 24, 200))
    ic.line([(x0, y + web), (x1, y + web)], 3, (30, 24, 20, 200))


def track(ic: Icon) -> None:
    """Wagonway: ballast bed, sleepers running into depth, cast chairs, two rails; ballast shoulder."""
    top = [(40, RT), (984, RT), (1010, RB), (14, RB)]
    m = ic.poly_mask(top)
    ic.fill(m, "#6c655a", "#443e36", (RT, RB), noise=0.3, chroma=0.06)
    R = ic.random

    def grit(clip, n, lo=2, hi=6):
        lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for _ in range(n):
            x, y = R.uniform(10, 1014), R.uniform(RT, RF)
            r = R.uniform(lo, hi)
            d.ellipse((x - r, y - r * 0.75, x + r, y + r * 0.75), fill=(34, 30, 26, 150))
            d.ellipse((x - r * 0.8, y - r * 0.85, x + r * 0.4, y + r * 0.1), fill=(226, 220, 206, 130))
        paste_clipped(ic, lay, clip)

    grit(m, 700)
    xs = list(np.arange(40, 1000, 64))
    for x in xs:  # sleepers into depth, regular spacing, warm lit top face, dark gap each side
        lean = (x - 512) * 0.03
        q = [(x - 17 - lean, RT + 10), (x + 17 - lean, RT + 10), (x + 23 + lean * 0.3, RB - 8), (x - 23 + lean * 0.3, RB - 8)]
        tint(ic, ic.poly_mask([(p[0] + 10, p[1]) for p in q]), m, (0, 0, 0), 0.45, 4)  # dark gap to the right
        sm = ic.poly_mask(q)
        ic.fill(sm, "#b08a60", "#6e5034", (RT, RB), noise=0.2, chroma=0.05)
        tint(ic, ic.poly_mask([q[1], q[2], ((q[2][0] + q[3][0]) / 2 + 10, RB - 8), ((q[1][0] + q[0][0]) / 2 + 8, RT + 10)]),
             sm, (0, 0, 0), 0.22)
        ic.line([q[0], q[3]], 3, (255, 230, 196, 110))
        ic.outline(q, 3, (36, 24, 14, 190))
    tint(ic, ic.mask("rectangle", (0, RT, 1024, RT + 14)), m, (0, 0, 0), 0.3, 6)
    # chairs under each rail
    for x in xs:
        for y, w in ((RAIL_FAR, 26), (RAIL_NEAR, 34)):
            lean = (x - 512) * 0.03 * ((y - RT) / (RB - RT))
            ic.rect((x - w / 2 - lean * 0.3, y - 4, x + w / 2 - lean * 0.3, y + 22), "#4e4a46", "#262422", edge=3)
    rail(ic, 30, 994, RAIL_FAR, 13)
    rail(ic, 16, 1008, RAIL_NEAR, 17)
    # ballast shoulder
    face = [(14, RB), (1010, RB), (1002, RF), (22, RF)]
    fm = ic.poly_mask(face)
    ic.fill(fm, "#6e665a", "#443e36", (RB, RF), noise=0.3)
    grit(fm, 300, 3, 7)
    tint(ic, ic.mask("rectangle", (0, RB, 1024, RB + 10)), fm, (0, 0, 0), 0.3, 4)
    ic.outline(top[:2] + [top[2], (1002, RF), (22, RF), top[3]], 6)


def shed(ic: Icon) -> None:
    """Long brick wagon shed: slate roof with a ridge louvre, brick pilasters, two arched doors (one
    with its boarded leaves swung open), stone plinth."""
    x0, x1, eave, ridge, base = 24, 600, 466, 304, RT + 4
    # ridge louvre (smoke vent) standing up from the ridge as the silhouette accent
    lx0, lx1 = 240, 384
    ic.rect((lx0, 222, lx1, 312), "#3a3632", "#1e1c1a", edge=5)
    for y in (236, 256, 276, 296):
        ic.line([(lx0 + 6, y), (lx1 - 6, y + 4)], 7, (96, 92, 86))
    ic.poly([(lx0 - 22, 230), (lx1 + 22, 230), (lx1 - 6, 186), (lx0 + 6, 186)], "#6a7088", "#383a4e", edge=5)
    tint(ic, ic.mask("ellipse", (lx0 - 10, 180, lx1 + 30, 234)), None, (14, 12, 12), 0.3, 12)  # soot on the cap
    roof = [(x0 - 40, eave + 10), (x1 + 40, eave + 10), (x1 - 20, ridge), (x0 + 20, ridge)]
    rm = shingles(ic, roof, "#76809a", "#2e3242", course=26, stagger=34, edge=0, vary=1.9,
                  hues=((110, 96, 120), (92, 110, 104), (130, 136, 150), (60, 64, 80)))
    tint(ic, ic.mask("rectangle", (x0 - 50, ridge, x1 + 50, ridge + 60)), rm, (236, 240, 248), 0.12, 30)  # lit upper slope
    tint(ic, ic.mask("rectangle", (x0 - 50, eave - 40, x1 + 50, eave + 12)), rm, (16, 14, 12), 0.34, 16)  # weathered eaves
    for _ in range(5):  # damp and lichen streaks near the eaves
        sx = ic.random.uniform(x0, x1)
        tint(ic, ic.mask("ellipse", (sx - 40, eave - 50, sx + 40, eave + 6)), rm,
             ic.random.choice([(20, 18, 16), (96, 104, 70)]), 0.2, 12)
    tint(ic, ic.mask("ellipse", (lx0 - 70, ridge - 20, lx1 + 90, ridge + 80)), rm, (18, 16, 16), 0.42, 22)  # soot round the louvre
    tint(ic, ic.mask("rectangle", (x1 - 200, ridge, x1 + 60, eave + 20)), rm, (0, 0, 0), 0.22, 44)
    ic.outline(roof, 7)
    ic.rect((x0 + 14, ridge - 14, lx0 - 4, ridge + 4), "#5a5e66", "#34363c", edge=5)
    ic.rect((lx1 + 4, ridge - 14, x1 - 14, ridge + 4), "#5a5e66", "#34363c", edge=5)
    wall = ic.mask("rectangle", (x0, eave + 10, x1, base))
    bricks(ic, wall, (x0, eave + 10, x1, base), "#c26446", "#743822")
    tint(ic, ic.mask("rectangle", (x1 - 180, eave, x1 + 20, base)), wall, (10, 4, 2), 0.28, 50)
    tint(ic, ic.mask("rectangle", (x0, base - 90, x1, base)), wall, (30, 28, 16), 0.3, 24)
    for px in (x0, 200, 400, x1 - 30):  # brick pilasters, lit left edge
        pm = ic.mask("rectangle", (px, eave + 10, px + 30, base))
        tint(ic, pm, None, (255, 220, 190), 0.12)
        ic.line([(px + 2, eave + 14), (px + 2, base)], 3, (255, 230, 200, 90))
        ic.line([(px + 29, eave + 14), (px + 29, base)], 4, (30, 16, 10, 140))
    stones(ic, (x0, base - 44, x1, base), "#a09482", "#665c4e", course=44, moss=0.1)
    ic.outline([(x0, eave + 10), (x1, eave + 10), (x1, base), (x0, base)], 6)
    tint(ic, ic.mask("rectangle", (x0, eave + 10, x1, eave + 60)), wall, (0, 0, 0), 0.5, 12)
    for dx0, dx1, open_leaf in ((244, 376, True), (436, 568, False)):  # arched doors
        w = dx1 - dx0
        dy0 = 560
        arch = union(ic.mask("ellipse", (dx0 - 18, dy0 - 18, dx1 + 18, dy0 + w + 18)),
                     ic.mask("rectangle", (dx0 - 18, dy0 + w / 2, dx1 + 18, base)))
        ic.fill(arch, "#c6b8a0", "#8a7c66", (dy0 - 18, base), noise=0.16)
        op = union(ic.mask("ellipse", (dx0, dy0, dx1, dy0 + w)), ic.mask("rectangle", (dx0, dy0 + w / 2, dx1, base)))
        ic.fill(op, "#2a2018", "#0e0a07", (dy0, base), noise=0.1)
        tint(ic, ic.mask("rectangle", (dx0, dy0, dx1, dy0 + 80)), op, (0, 0, 0), 0.5, 16)
        if open_leaf:
            # the open leaf, swung back against the wall: arched top like the doorway, planks, lit edge
            lw = 74
            arc = [(dx0 - 18 - lw * t, dy0 + w / 2 + 6 - 56 * math.sin(math.pi / 2 * t) ** 0.8)
                   for t in np.linspace(0, 1, 12)]
            leaf = arc + [(dx0 - 18 - lw, base - 4), (dx0 - 18, base)]
            tint(ic, ic.poly_mask([(p[0] - 14, p[1] + 6) for p in leaf]), None, (0, 0, 0), 0.4, 8)
            planks(ic, leaf, "#94704c", "#4e3824", board=18)
            lm = ic.poly_mask(leaf)
            tint(ic, ic.mask("rectangle", (dx0 - 18 - lw * 0.4, dy0, dx0 - 16, base)), lm, (0, 0, 0), 0.3, 10)
            for hy in (dy0 + w / 2 + 40, base - 60):  # iron strap hinges
                ic.line([(dx0 - 20, hy), (dx0 - 18 - lw * 0.8, hy)], 7, IRON)
            ic.line([(dx0 - 16 - lw, arc[-1][1] + 6), (dx0 - 16 - lw, base - 4)], 5, (255, 232, 196, 170))  # lit edge
            ic.outline(leaf, 4, (40, 26, 16, 200))
        else:
            planks(ic, [(dx0 + 4, dy0 + w / 2), (dx1 - 4, dy0 + w / 2), (dx1 - 4, base), (dx0 + 4, base)], "#6e5a44",
                   "#3a2e22", board=w / 5)
            with ic.clipped(op):
                timber(ic, (dx0, dy0 + w / 2 + 40), (dx1, base - 20), 12, "#6a543e", "#3a2e22")
                timber(ic, (dx0, dy0 + w / 2 + 16), (dx1, dy0 + w / 2 + 16), 14, "#6a543e", "#3a2e22")
            ic.overlay(lambda d: d.line([((dx0 + dx1) / 2, dy0 + w / 2), ((dx0 + dx1) / 2, base)], fill=(20, 12, 6, 200), width=5))
    for wx in (62, 108):  # small windows between the pilasters
        ic.window(wx, 590, wx + 36, 650)


def crib(ic: Icon, x0: float, x1: float, base: float, layers: int, th: float = 30) -> None:
    """Crib of spare sleepers (log-cabin stack): dark creosoted baulks, alternating a side-on
    layer across the full width (overhanging) and a layer of end-on squares with open gaps between
    them where the background shows through; spare rails with a lit I-profile end on top."""
    top = base - layers * th
    tint(ic, ic.mask("ellipse", (x0 - 40, base - 20, x1 + 70, base + 22)), None, (0, 0, 0), 0.5, 10)
    R = ic.random
    for k in range(layers):
        y1 = base - k * th
        y0 = y1 - th
        if k % 2 == 1:  # side-on sleeper across the crib, overhanging both ends
            q = [(x0 - 20, y0 + 1), (x1 + 20, y0 + 1), (x1 + 20, y1 - 1), (x0 - 20, y1 - 1)]
            qm = ic.poly_mask(q)
            ic.fill(qm, "#5e4432", "#2c1e14", (y0, y1), noise=0.24, chroma=0.05)
            ic.line([(x0 - 16, y0 + 5), (x1 + 16, y0 + 5)], 4, (214, 170, 120, 120))  # warm lit top arris
            for _ in range(3):  # grain and checks along the baulk
                gx = R.uniform(x0, x1 - 60)
                ic.line([(gx, y0 + th * R.uniform(0.4, 0.7)), (gx + R.uniform(40, 90), y0 + th * R.uniform(0.4, 0.7))], 2,
                        (20, 12, 6, 130))
            tint(ic, ic.mask("rectangle", (x1 - 50, y0, x1 + 24, y1)), qm, (0, 0, 0), 0.3, 8)
            ic.outline(q, 3, (26, 16, 10, 220))
        else:  # end-on sleepers: squares of end grain with open gaps between them
            for ex in (x0 + 2, (x0 + x1) / 2 - 20, x1 - 42):
                ex += R.uniform(-2, 2)
                b = (ex, y0 + 2, ex + 40, y1 - 1)
                bm = ic.mask("rectangle", b)
                ic.fill(bm, "#7a5a40", "#3e2a1c", (b[1], b[3]), noise=0.2)
                ic.overlay(lambda d, b=b: [d.arc((b[0] + 6 + i * 5, b[1] + 6 + i * 4, b[2] - 6 - i * 5, b[3] + 8 - i * 3),
                                                 190, 350, fill=(40, 26, 16, 140), width=2) for i in range(2)], bm)
                ic.line([(b[0] + 12, b[1] + 4), (b[0] + 20, b[3] - 6)], 2, (24, 14, 8, 170))  # end check
                ic.line([(b[0] + 2, b[3] - 2), (b[0] + 2, b[1] + 2), (b[2] - 2, b[1] + 2)], 3, (220, 180, 132, 130))
                ic.outline([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], 3, (26, 16, 10, 220))
    # spare rails across the top, ends overhanging, the left end showing the I-profile in the light
    for j, (dx, lift) in enumerate(((-6, 0), (14, 13), (-16, 26))):
        y = top - 8 - lift
        xa, xb = x0 - 44 + dx, x1 + 36 + dx
        rail(ic, xa, xb, y, 12)
        ex = xa - 2
        prof = [(ex - 11, y - 6), (ex + 11, y - 6), (ex + 11, y + 2), (ex + 4, y + 2), (ex + 4, y + 6), (ex + 14, y + 8),
                (ex + 14, y + 13), (ex - 14, y + 13), (ex - 14, y + 8), (ex - 4, y + 6), (ex - 4, y + 2), (ex - 11, y + 2)]
        ic.poly(prof, "#dcd8ce", "#8e8a82", edge=0)
        ic.outline(prof, 3, (30, 26, 22, 230))
    tint(ic, ic.mask("rectangle", ((x0 + x1) / 2 + 20, top - 40, x1 + 40, base)), None, (0, 0, 0), 0.14, 24)


def ballast_spread(ic: Icon, x0: float, x1: float, base: float, h: float) -> None:
    """Low, long spread of ballast along the far side: flat crest, gentle ends, a wide shovel
    lying on it."""
    R = ic.random
    pts = []
    for t in np.linspace(0, 1, 40):
        x = x0 + (x1 - x0) * t
        e = min(t / 0.22, (1 - t) / 0.16, 1.0)
        pts.append((x, base - h * (math.sin(e * math.pi / 2) ** 1.2) + R.uniform(-4, 4) * e))
    pts += [(x1, base), (x0, base)]
    tint(ic, ic.mask("ellipse", (x0 - 20, base - 20, x1 + 20, base + 20)), None, (0, 0, 0), 0.45, 10)
    m = ic.poly_mask(pts)
    ic.fill(m, "#9a9284", "#48443c", (base - h, base + 10), noise=0.3, chroma=0.05)
    tint(ic, ic.mask("rectangle", (x0 - 10, base - h - 10, x1 + 10, base - h + 18)), m, (255, 250, 236), 0.2, 8)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(int((x1 - x0) * h / 90)):
        x, y = R.uniform(x0, x1), R.uniform(base - h, base)
        r = R.uniform(5, 9)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(30, 28, 24, 130))
        d.ellipse((x - r * 0.8, y - r * 0.8, x + r * 0.4, y + r * 0.1), fill=(232, 226, 212, 120))
    paste_clipped(ic, lay, m)
    tint(ic, ic.mask("rectangle", (x0 - 10, base - 26, x1 + 10, base + 10)), m, (0, 0, 0), 0.35, 8)
    ic.outline(pts, 5, (40, 30, 22, 190))
    # ballast shovel lying along the crest
    timber(ic, (x0 + 40, base - h - 4), (x0 + 150, base - h + 6), 11, "#a07a54", "#5a3e26")
    ic.poly([(x0 + 150, base - h - 10), (x0 + 196, base - h - 4), (x0 + 194, base - h + 22), (x0 + 150, base - h + 18)],
            "#7a766e", "#3c3a36", edge=4)


def rail_stack(ic: Icon, x0: float, x1: float, base: float, layers: int = 4) -> None:
    """Stack of new rails on timber bearers: each layer shows the near rail and the heads of the
    rails behind it."""
    tint(ic, ic.mask("ellipse", (x0 - 20, base - 16, x1 + 40, base + 18)), None, (0, 0, 0), 0.45, 10)
    y = base
    for k in range(layers):
        for bx in (x0 + 20, x1 - 50):
            ic.rect((bx, y - 18, bx + 34, y), "#8a6a4c", "#4e3826", edge=3)
        y -= 18
        for j, dy in enumerate((-14, -7, 0)):
            rail(ic, x0 + 6 - j * 2, x1 - j * 2, y - 16 + dy, 12)
        y -= 20
    tint(ic, ic.mask("rectangle", ((x0 + x1) / 2, y - 20, x1 + 20, base)), None, (0, 0, 0), 0.18, 20)


def wheel(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Cast-iron flanged wagon wheel with spokes, shaded as a disc."""
    ic.fill(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), "#6a6662", "#2a2826", radial=(cx - r * 0.5, cy - r * 0.6, r * 2.2), noise=0.14)
    ri = r * 0.72
    ic.fill(ic.mask("ellipse", (cx - ri, cy - ri, cx + ri, cy + ri)), "#3a3634", "#1c1a18", noise=0.1)
    for a in np.linspace(0, math.pi * 2, 7)[:-1] + 0.3:
        ic.line([(cx, cy), (cx + math.cos(a) * ri, cy + math.sin(a) * ri)], 9, (86, 82, 78))
    ic.draw.ellipse((cx - r * 0.22, cy - r * 0.22, cx + r * 0.22, cy + r * 0.22), fill=(96, 92, 86, 255))
    ic.overlay(lambda d: d.arc((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), 190, 280, fill=(210, 204, 194, 150), width=4))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(30, 24, 20, 220), width=5))


def wagon(ic: Icon, x0: float, x1: float) -> None:
    """Chaldron wagon on the near rail: splayed boarded body with iron straps, heaped with ballast,
    long brake lever, flanged wheels."""
    r = 56
    cy = RAIL_NEAR - r + 2
    bot, top = cy - 8, cy - 190
    tint(ic, ic.mask("ellipse", (x0 - 10, RAIL_NEAR - 8, x1 + 60, RAIL_NEAR + 26)), None, (0, 0, 0), 0.45, 8)
    body = [(x0 - 24, top), (x1 + 24, top), (x1 - 16, bot), (x0 + 16, bot)]
    mound(ic, x0 - 10, x1 + 10, top + 6, top - 56, body=("#9a9284", "#4e4a42"), pebble=9,
          peb_col=((236, 230, 216), (30, 28, 24)))
    planks(ic, body, "#9a6e48", "#4e3420", board=400)
    ic.overlay(lambda d: [d.line([(x0 - 20 + (y - top) * 0.3, y), (x1 + 20 - (y - top) * 0.3, y)], fill=(40, 26, 14, 150), width=3)
                          for y in np.linspace(top + 32, bot - 10, 4)], ic.poly_mask(body))
    for f in (0.2, 0.8):  # iron straps
        xa = x0 - 24 + (x1 - x0 + 48) * f
        xb = x0 + 16 + (x1 - x0 - 32) * f
        timber(ic, (xa, top + 2), (xb, bot - 2), 12, "#5a5654", "#2e2c2a")
    tint(ic, ic.poly_mask([((x0 + x1) / 2 + 30, top), (x1 + 30, top), (x1, bot), ((x0 + x1) / 2, bot)]), ic.poly_mask(body),
         (0, 0, 0), 0.3, 16)
    ic.line([(x0 - 24, top + 3), (x1 + 24, top + 3)], 4, (255, 226, 190, 90))
    ic.outline(body, 5)
    timber(ic, (x0 - 10, bot + 4), (x1 + 10, bot + 4), 20, "#7a5a3e", "#44301e")  # sole bar
    wheel(ic, x0 + 44, cy, r)
    wheel(ic, x1 - 44, cy, r)
    timber(ic, (x1 - 30, bot - 6), (x1 + 40, top + 20), 10, "#8a6a4c", "#4a3424")  # brake lever
    ic.draw.ellipse((x1 - 30, bot - 20, x1 - 10, bot), fill=IRON + (255,))


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 1.0
    shed(ic)
    ballast_spread(ic, 846, 1016, RT + 12, 104)
    crib(ic, 640, 836, RT + 8, 7)
    track(ic)
    tint(ic, ic.mask("rectangle", (20, RT - 6, 605, RT + 20)), None, (0, 0, 0), 0.35, 8)
    wagon(ic, 404, 634)
