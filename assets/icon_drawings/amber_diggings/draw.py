"""Amber Diggings (amber_diggings): a shored pit down to the blue earth, a windlass over it, baskets of amber.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/amber_diggings/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/amber_diggings

Identity: the amber_collector's reed roof, sand and wicker baskets of glowing amber, grown into a works. The dark
blue-grey earth that holds the amber lies in a big spoil bank with lumps showing in it, a plank-shored pit in the
middle shows the same blue band behind its boards, and a heavy timber windlass with a rope and a full tub stands over
the pit. Tier 1: more structure and equipment where tier 0 has a hut and a scoop net on the beach.

Local helpers: ``amber``, ``amber_heap``, ``thatch``, ``pebbles``, ``rim_darken``, ``basket_of_amber`` (from
amber_collector), ``planks`` (horizontal shoring boards), ``post`` (squared timber), ``clods`` (blue earth lumps).
"""

import math

import numpy as np
from PIL import Image, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 37
REFS = ("clay_pit", "sand_pit", "stone_quarry", "amber_collector")

GOLD = ((255, 204, 84), (222, 124, 18), (112, 40, 4))
ORANGE = ((252, 170, 56), (200, 84, 12), (96, 28, 4))
HONEY = ((255, 222, 120), (232, 150, 36), (128, 60, 8))
COGNAC = ((240, 132, 44), (158, 50, 10), (72, 18, 4))
AMBERS = ((GOLD, 0.4), (ORANGE, 0.25), (HONEY, 0.2), (COGNAC, 0.15))

SAND = ("#e0c690", "#b08a52")
BLUE = ("#7c8fa0", "#2e3e4c")  # the blue earth, lit and in shadow
BLUE_DEEP = ("#55687a", "#1e2a36")
WOOD = ((166, 124, 82), (88, 62, 38))


# ---------------------------------------------------------------- helpers
def pick(ic: Icon, weights) -> tuple:
    r = ic.random.random()
    for pal, w in weights:
        r -= w
        if r <= 0:
            return pal
    return weights[-1][0]


def amber(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Translucent amber lumps (x, y, r, palette) in one blended layer: dark rim, body, a glowing core
    offset away from the light (light passes through), a sharp glint at the upper left."""
    rnd = ic.random
    shapes = []
    for x, y, r, pal in items:
        base = ic.jitter(0, 0, r, r * rnd.uniform(0.7, 0.9), rnd.randint(10, 14), 0.1)
        shapes.append((x, y, r, pal, base))

    def paint(d):
        for x, y, r, (lit, mid, dk), base in shapes:
            def at(k, dx=0.0, dy=0.0, base=base, x=x, y=y):
                return [(x + dx + px * k, y + dy + py * k) for px, py in base]

            d.polygon(at(1.0), fill=dk + (255,))
            d.polygon(at(0.9, -r * 0.03, -r * 0.05), fill=mid + (255,))
            glow = tuple(int((a + b) / 2) for a, b in zip(mid, lit))
            d.polygon(at(0.68, r * 0.1, r * 0.08), fill=glow + (240,))
            d.polygon(at(0.4, r * 0.18, r * 0.14), fill=lit + (235,))
            g = max(r * 0.11, 2.5)
            gx, gy = x - r * 0.42, y - r * 0.32
            d.ellipse((gx - g * 1.5, gy - g * 0.8, gx + g * 1.5, gy + g * 0.8), fill=(255, 246, 214, 200))
            pts = at(1.0)
            d.line(pts + [pts[0]], fill=(80, 34, 6, 110), width=2)

    ic.overlay(paint, clip)


def amber_heap(ic: Icon, cx: float, top: float, base: float, hw: float, n: int, r: tuple[float, float]) -> None:
    """Dome of amber lumps between ``top`` and ``base``, back rows first."""
    rnd = ic.random
    dome = [(cx + hw * u, base - (base - top) * 0.86 * math.sqrt(max(0.0, 1 - u * u)) ** 0.8)
            for u in np.linspace(-1, 1, 20)]
    dm = ic.poly_mask(dome)
    ic.fill(dm, "#d27a22", "#6a2808", radial=(cx - hw * 0.3, top, (base - top) * 1.6), noise=0.3)
    items = []
    for _ in range(n):
        u = rnd.uniform(-1, 1)
        h = math.sqrt(max(0.0, 1 - u * u))
        y = base - (base - top) * h * 0.92 * rnd.uniform(0.0, 1.0) ** 0.4
        items.append((cx + u * hw * 0.96, y, rnd.uniform(*r), pick(ic, AMBERS)))
    items.sort(key=lambda it: it[1])
    amber(ic, items)


def basket_of_amber(ic: Icon, x0, y0, x1, y1, heap_top, n, r) -> None:
    w = x1 - x0
    ic.shade(ic.mask("ellipse", (x0 - 20, y1 - 22, x1 + 40, y1 + 22)), (50, 34, 16), 0.5, blur=10)
    ic.fill(ic.mask("ellipse", (x0 - 2, y0 - 22, x1 + 2, y0 + 22)), "#3a220c", "#1e1206")
    amber_heap(ic, (x0 + x1) / 2, heap_top, y0 + 14, w * 0.47, n, r)
    ic.basket(x0, y0, x1, y1, colors=("#94703e", "#4a3218"))
    ic.line([(x0 + 2, y0), (x1 - 2, y0)], 14, (104, 76, 44))
    ic.line([(x0 + 2, y0 - 4), (x1 - 2, y0 - 4)], 4, (190, 156, 104, 170))


def thatch(ic: Icon, ridge, eave, c=("#bca46e", "#62502e")) -> None:
    """Reed roof plane seen from above: stalk strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.3, 0.55, 0.8, 1.0]
    for k in reversed(range(len(courses) - 1)):
        f0, f1 = courses[k], courses[k + 1] + (0.05 if k < len(courses) - 2 else 0)
        n = 20
        low = []
        for j in range(n + 1):
            t = j / n
            p = rl + (rr - rl) * t + ((el + (er - el) * t) - (rl + (rr - rl) * t)) * min(f1, 1.0)
            low.append((p[0] + rnd.uniform(-4, 4), p[1] + (rnd.uniform(-3, 7) if f1 < 1 else 0)))
        up = [tuple(rl + (el - rl) * f0 + np.array([-40, -4])), tuple(rr + (er - rr) * f0 + np.array([40, -4]))]
        band = ic.intersect(ic.poly_mask(up + low[::-1]), m)
        y0 = (rl + (el - rl) * f0)[1]
        y1 = max(p[1] for p in low)
        if f1 < 1:
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 22) for x, y in low[::-1]])), (30, 24, 12), 0.45,
                     blur=6)
        tint = rnd.uniform(0.9, 1.06)
        ic.fill(band, tuple(int(v * tint) for v in rgb(c[0])), tuple(int(v * tint) for v in rgb(c[1])),
                (y0 - 10, y1 + 30), noise=0.32, chroma=0.12)

        def straw(dr, y0=y0, low=low):
            for _ in range(170):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (226, 214, 170, 80) if rnd.random() < 0.5 else (50, 42, 24, 85)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 22 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#7a6c48", "#443a22", (min(p[1] for p in eave), max(p[1] for p in eave) + 28),
            noise=0.35)
    ic.line([tuple(p) for p in ridge], 20, (92, 80, 54))
    ic.line([tuple(p) for p in ridge], 7, (150, 136, 100, 170))


def pebbles(ic: Icon, items) -> None:
    """Small stones (x, y, r): lit top, dark underside, a contact shadow."""
    for x, y, r in items:
        ic.shade(ic.mask("ellipse", (x - r * 1.2, y, x + r * 1.5, y + r * 0.9)), (40, 28, 14), 0.45, blur=3)
        tone = ic.random.uniform(0.8, 1.15)
        c1 = tuple(int(min(255, v * tone)) for v in (176, 168, 150))
        c2 = tuple(int(v * tone) for v in (84, 76, 66))
        pts = ic.jitter(x, y, r, r * 0.66, 10, 0.12)
        ic.fill(ic.poly_mask(pts), c1, c2, radial=(x - r * 0.5, y - r * 0.6, r * 1.8), noise=0.2)
        ic.outline(pts, 2, (50, 40, 30, 160))


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


def planks(ic: Icon, x0, y0, x1, y1, h: float, c=("#a8825c", "#5e4228"), gap: float = 0.0) -> None:
    """Horizontal shoring boards: per-board tone, dark joints, a little grain."""
    rnd = ic.random
    y = y0
    while y < y1:
        bh = min(h * rnd.uniform(0.85, 1.15), y1 - y)
        t = rnd.uniform(0.78, 1.12)
        c1 = tuple(int(min(255, v * t)) for v in rgb(c[0]))
        c2 = tuple(int(v * t) for v in rgb(c[1]))
        ic.rect((x0, y, x1, y + bh - gap), c1, c2, edge=0, noise=0.2)

        def grain(d, y=y, bh=bh):
            for _ in range(5):
                gy = rnd.uniform(y + 3, y + bh - 3)
                gx = rnd.uniform(x0, x1 - 40)
                d.line([(gx, gy), (gx + rnd.uniform(30, 110), gy + rnd.uniform(-2, 2))], fill=(40, 28, 16, 70), width=2)

        ic.overlay(grain, ic.mask("rectangle", (x0, y, x1, y + bh)))
        ic.line([(x0, y + bh - gap), (x1, y + bh - gap + rnd.uniform(-2, 2))], 4, (34, 24, 14, 200))
        y += bh


def post(ic: Icon, p0, p1, w: float, c=WOOD) -> None:
    """Squared timber from p0 to p1: lit left face, dark right face, black-brown edges."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([-d[1], d[0]])
    if n[0] > 0:
        n = -n  # n points towards the light, left
    h = w / 2
    body = [tuple(p0 + n * h), tuple(p1 + n * h), tuple(p1 - n * h), tuple(p0 - n * h)]
    lit = [tuple(p0 + n * h), tuple(p1 + n * h), tuple(p1 - n * h * 0.1), tuple(p0 - n * h * 0.1)]
    ic.fill(ic.poly_mask(body), c[1], (c[1][0] * 0.7, c[1][1] * 0.7, c[1][2] * 0.7), noise=0.25)
    ic.fill(ic.poly_mask(lit), c[0], c[1], noise=0.28)
    ic.outline(body, 4)


def clods(ic: Icon, x0, x1, base, top, n: int, r: tuple[float, float], clip: Image.Image | None = None) -> None:
    """Blue earth lumps over a bank between base and top, back ones first: a soft shade under each, a body, a lit
    top-left, no drawn edge, so the bank reads as wet clay and not as scales."""
    rnd = ic.random
    cx, hw = (x0 + x1) / 2, (x1 - x0) / 2
    rows = []
    for _ in range(n):
        u = rnd.uniform(-1, 1)
        h = math.sqrt(max(0.0, 1 - u * u))
        y = base - (base - top) * h * rnd.uniform(0.0, 0.96)
        rr = rnd.uniform(*r)
        rows.append((cx + u * hw * 0.94, y, rr, ic.jitter(0, 0, rr, rr * 0.72, rnd.randint(7, 9), 0.17), rnd.uniform(0.82, 1.14)))
    rows.sort(key=lambda it: it[1])

    def paint(d):
        for x, y, rr, shape, tone in rows:
            d.polygon([(x + px * 1.06 + rr * 0.1, y + py * 1.06 + rr * 0.16) for px, py in shape], fill=(16, 24, 32, 150))
            d.polygon([(x + px, y + py) for px, py in shape], fill=(int(82 * tone), int(100 * tone), int(116 * tone), 255))
            d.polygon([(x + px * 0.62 - rr * 0.18, y + py * 0.62 - rr * 0.18) for px, py in shape],
                      fill=(int(128 * tone), int(148 * tone), int(162 * tone), 190))

    ic.overlay(paint, clip)


# ---------------------------------------------------------------- scene
def ground(ic: Icon) -> None:
    rnd = ic.random
    back = [(x, 586 + rnd.uniform(-10, 8)) for x in np.linspace(26, 998, 14)]
    front = [(x, 812 + 18 * math.sin(x / 130) + rnd.uniform(-6, 6)) for x in np.linspace(1006, 18, 22)]
    pts = back + front
    m = ic.poly_mask(pts)
    ic.fill(m, SAND[0], SAND[1], (586, 830), noise=0.24, chroma=0.12)

    def grit(d):
        for _ in range(60):
            x, y = rnd.uniform(40, 990), rnd.uniform(600, 800)
            L = rnd.uniform(30, 70)
            d.arc((x, y - 6, x + L, y + 6), 200, 340, fill=(255, 246, 220, 60), width=3)
            d.arc((x + 4, y - 2, x + L + 4, y + 10), 200, 340, fill=(80, 60, 30, 55), width=3)
        for _ in range(70):  # spilled blue earth and shell grit
            x, y = rnd.uniform(40, 990), rnd.uniform(610, 800)
            r = rnd.uniform(3, 8)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6),
                      fill=(70, 88, 104, 170) if rnd.random() < 0.65 else (236, 228, 210, 150))

    ic.overlay(grit, m)
    ic.outline(pts, 4)


def shed(ic: Icon) -> None:
    """Open sorting shed behind the bank: posts, a dark interior, the family's tall reed roof."""
    rnd = ic.random
    x0, x1, y0, y1 = 60, 372, 330, 600
    ic.rect((x0, y0, x1, y1), "#3a3024", "#1c1610", edge=4)
    for x in (x0 + 14, 216, x1 - 14):
        post(ic, (x, y1), (x, y0 - 6), 26)
    # sorting table with amber glowing in the dark
    ic.rect((110, 470, 330, 490), "#8a6a48", "#50391f", edge=3)
    amber(ic, [(150, 458, 14, GOLD), (190, 462, 11, ORANGE), (232, 456, 13, HONEY), (276, 460, 12, GOLD)])
    ridge = [(120, 92), (216, 82), (312, 90)]
    eave = [(x, 352 + rnd.uniform(-5, 6)) for x in np.linspace(14, 418, 16)]
    thatch(ic, ridge, eave)
    ic.shade(ic.poly_mask([(250, 76), (450, 76), (450, 390), (290, 390)]), alpha=0.16, blur=36)
    ic.shade(ic.mask("rectangle", (x0, y0 + 20, x1, y0 + 80)), alpha=0.5, blur=12)


def spoil_bank(ic: Icon) -> None:
    """The blue earth thrown out of the pit, with amber showing in it."""
    x0, x1, base, top = 14, 456, 786, 482
    cx, hw = (x0 + x1) / 2, (x1 - x0) / 2
    rnd = ic.random
    shape = [(x0, base)] + [(cx + hw * u, base - (base - top) * math.sqrt(max(0.0, 1 - u * u)) ** 0.75 * rnd.uniform(0.96, 1.03))
                            for u in np.linspace(-0.97, 0.97, 22)] + [(x1, base)]
    ic.shade(ic.mask("ellipse", (x0 - 10, base - 30, x1 + 60, base + 26)), (40, 30, 18), 0.5, blur=12)
    m = ic.poly_mask(shape)
    ic.fill(m, BLUE[0], BLUE[1], radial=(cx - hw * 0.45, top, hw * 1.7), noise=0.4, chroma=0.1)
    clods(ic, x0, x1, base + 10, top - 6, 90, (14, 30), m)
    ic.outline(shape, 5)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx + hw * 0.2, top + 60, x1 + 60, base + 40))), (14, 20, 28), 0.42, blur=26)
    amber(ic, [(112, 668, 17, GOLD), (176, 612, 14, HONEY), (250, 690, 18, ORANGE), (214, 566, 12, GOLD), (312, 626, 15, GOLD),
               (92, 730, 13, COGNAC), (352, 714, 14, HONEY), (284, 744, 12, GOLD), (168, 744, 15, GOLD)], m)


def pit(ic: Icon) -> None:
    """Plank-shored pit seen from the front: back wall with the blue band, side walls, the rim timbers."""
    bx0, bx1, by = 424, 704, 572   # back edge of the rim
    fx0, fx1, fy = 396, 736, 716   # front edge of the rim
    hole = [(bx0, by), (bx1, by), (fx1, fy), (fx0, fy)]
    ic.fill(ic.poly_mask(hole), "#241c16", "#0c0806", (by, fy), noise=0.15)
    # back wall: sand, then the blue earth with amber in it, boards over the lower part
    wall = (bx0 + 10, by, bx1 - 10, by + 104)
    ic.rect((wall[0], wall[1], wall[2], wall[1] + 26), "#c4a874", "#8c7248", edge=0, noise=0.25)
    ic.rect((wall[0], wall[1] + 26, wall[2], wall[3]), BLUE[0], BLUE_DEEP[1], edge=0, noise=0.35)
    amber(ic, [(bx0 + 58, by + 54, 10, GOLD), (bx0 + 132, by + 44, 12, HONEY), (bx0 + 206, by + 58, 10, ORANGE),
               (bx0 + 240, by + 40, 8, GOLD), (bx0 + 92, by + 74, 8, ORANGE), (bx0 + 176, by + 80, 9, GOLD)],
          ic.mask("rectangle", wall))
    planks(ic, wall[0], by + 84, wall[2], by + 124, 20, ("#8a6a4a", "#4a3420"))
    for x in (bx0 + 74, bx0 + 210):
        ic.rect((x - 9, by + 4, x + 9, by + 124), "#8c6c48", "#4e3820", vertical=False, edge=3)
    ic.shade(ic.mask("rectangle", (wall[0], by + 92, wall[2], fy)), (6, 4, 2), 0.72, blur=14)
    # side walls: darker boards running to the viewer
    for inner, outer in ((bx0, fx0), (bx1, fx1)):
        side = [(inner, by), (outer, fy), (inner + (1 if inner == bx0 else -1) * 22, fy), (inner + (1 if inner == bx0 else -1) * 12, by + 96)]
        ic.fill(ic.poly_mask(side), "#6a5038", "#2c1e12", (by, fy), noise=0.25)
        ic.outline(side, 3, (20, 14, 8, 200))
    ic.shade(ic.poly_mask(hole), (0, 0, 0), 0.22, blur=10)
    # rim timbers
    post(ic, (bx0 - 14, by + 2), (bx1 + 14, by + 2), 24, ((176, 134, 90), (96, 68, 42)))
    post(ic, (bx0 - 6, by), (fx0 - 6, fy + 2), 26)
    post(ic, (bx1 + 6, by), (fx1 + 6, fy + 2), 26)
    post(ic, (fx0 - 26, fy + 10), (fx1 + 26, fy + 10), 36, ((184, 142, 96), (98, 70, 44)))
    # end grain of the front timber
    for x in (fx0 - 26, fx1 + 26):
        ic.ellipse((x - 16, fy - 7, x + 14, fy + 27), "#c4a070", "#7a5a38", edge=3)


def windlass_back(ic: Icon) -> None:
    """Forked posts with braces, the drum with the rope wound on, the crank."""
    lx, rx, top, foot_y = 438, 690, 236, 716
    drum_y = top + 42
    # raking braces behind the posts
    post(ic, (lx - 62, foot_y - 6), (lx - 4, top + 130), 22)
    post(ic, (rx + 62, foot_y - 6), (rx + 4, top + 130), 22)
    post(ic, (lx, foot_y), (lx, top), 34)
    post(ic, (rx, foot_y), (rx, top), 34)
    # forks at the post heads
    for x in (lx, rx):
        ic.rect((x - 20, top - 6, x + 20, top + 16), "#a07a52", "#5e4228", edge=3)
    # drum
    ic.fill(ic.mask("rectangle", (lx - 10, drum_y - 24, rx + 10, drum_y + 24)), "#b08a60", "#4c3620", (drum_y - 24, drum_y + 24), noise=0.3)
    ic.outline([(lx - 10, drum_y - 24), (rx + 10, drum_y - 24), (rx + 10, drum_y + 24), (lx - 10, drum_y + 24)], 4)

    def rope(d):
        for x in np.arange(lx + 70, rx - 70, 9):
            d.line([(x, drum_y - 24), (x + 7, drum_y + 24)], fill=(58, 44, 26, 255), width=7)
            d.line([(x + 1, drum_y - 22), (x + 7, drum_y + 22)], fill=(196, 168, 118, 255), width=4)

    ic.overlay(rope, ic.mask("rectangle", (lx - 10, drum_y - 24, rx + 10, drum_y + 24)))
    # crank at the right end
    ic.line([(rx + 12, drum_y), (rx + 54, drum_y)], 14, (44, 40, 38))
    ic.line([(rx + 54, drum_y - 8), (rx + 54, drum_y + 74)], 14, (44, 40, 38))
    ic.line([(rx + 54, drum_y + 70), (rx + 92, drum_y + 70)], 16, (60, 44, 28))
    ic.line([(rx + 54, drum_y + 70), (rx + 90, drum_y + 70)], 8, (150, 112, 74))


def tub(ic: Icon) -> None:
    """The rope and the tub, hanging over the pit, full of blue earth with amber in it."""
    cx, y0, y1 = 564, 438, 524
    drum_bottom = 236 + 42 + 24
    ic.line([(cx, drum_bottom), (cx, y0 - 30)], 13, (42, 30, 18))
    ic.line([(cx - 1, drum_bottom), (cx - 1, y0 - 30)], 6, (186, 158, 112))
    hw = 62
    ic.overlay(lambda d: d.arc((cx - hw, y0 - 46, cx + hw, y0 + 36), 180, 360, fill=(44, 40, 38, 255), width=8))
    ic.fill(ic.mask("ellipse", (cx - hw, y0 - 16, cx + hw, y0 + 16)), "#55687a", "#222e38")
    clods(ic, cx - hw + 6, cx + hw - 6, y0 + 12, y0 - 26, 14, (11, 17))
    amber(ic, [(cx - 12, y0 - 4, 11, GOLD), (cx + 28, y0 - 14, 9, HONEY)])
    body = [(cx - hw, y0), (cx + hw, y0), (cx + hw * 0.82, y1), (cx - hw * 0.82, y1)]
    ic.poly(body, "#a88056", "#54391f", (cx - hw, cx + hw), vertical=False, noise=0.3)

    def staves(d):
        for u in np.linspace(-0.75, 0.75, 6):
            d.line([(cx + hw * u, y0), (cx + hw * u * 0.82, y1)], fill=(40, 26, 14, 170), width=3)

    ic.overlay(staves, ic.poly_mask(body))
    ic.line([(cx - hw * 0.96, y0 + 18), (cx + hw * 0.96, y0 + 18)], 10, (58, 56, 54))
    ic.line([(cx - hw * 0.87, y1 - 16), (cx + hw * 0.87, y1 - 16)], 10, (58, 56, 54))
    ic.outline(body, 4)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    ground(ic)
    shed(ic)
    windlass_back(ic)
    pit(ic)
    tub(ic)
    spoil_bank(ic)
    pebbles(ic, [(486, 764, 12), (610, 790, 10), (706, 776, 11), (44, 792, 11)])
    basket_of_amber(ic, 752, 552, 992, 768, 370, 130, (20, 30))
    basket_of_amber(ic, 636, 690, 756, 806, 612, 42, (15, 21))
    amber(ic, [(560, 776, 13, GOLD), (786, 790, 12, HONEY), (830, 800, 10, COGNAC), (486, 800, 10, ORANGE)])
    rim_darken(ic)
