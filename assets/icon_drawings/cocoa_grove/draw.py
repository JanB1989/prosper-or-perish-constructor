"""Cocoa Grove: a cacao tree hung with ribbed pods under a banana shade plant, beans drying on a tray.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/cocoa_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/cocoa_grove

Identity: a slender cacao tree whose trunk and limbs carry big ribbed yellow, orange and red pods
(cauliflory), under a dark crown of long drooping leaves with a bronze new flush; behind it a
banana plant with torn paddle leaves as the grove's shade; on the right a raised drying tray of
dark cocoa beans; a split pod with pale pulp and a whole pod in front.

Local helpers: ``gleaf`` (glossy leaf, from coffee_grove), ``pod`` (ribbed cacao pod shaded as a
form), ``split_pod`` (opened pod lying on the ground, pulp and beans), ``paddle`` (torn banana
leaf), ``cacao_tree`` (trunk, forked limbs, hanging-leaf crown, pods on trunk and limbs),
``scatter`` (grains on a surface in perspective, from coffee_grove).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("fruit_orchard", "sugar_plantation", "tobacco_plantation", "cotton_plantation")

LEAF = ("#4a7432", "#12220a")
FLUSH = ("#a0704a", "#402014")
BANANA = ("#8aa446", "#2c4216")

YELLOW = ((220, 170, 34), (250, 218, 90), (124, 78, 10))
ORANGE = ((218, 112, 26), (248, 166, 66), (112, 42, 8))
RED = ((180, 42, 24), (226, 92, 54), (86, 12, 6))
MAROON = ((136, 34, 36), (184, 72, 60), (62, 12, 12))
UNRIPE = ((132, 158, 50), (184, 204, 96), (58, 76, 18))

BEANS = [((110, 66, 42), (52, 28, 16)), ((94, 54, 36), (44, 22, 12)), ((124, 78, 50), (60, 34, 20)),
         ((80, 46, 32), (38, 20, 12))]


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def darker(cols, f):
    return tuple(tuple(int(min(255, v * f)) for v in rgb(c)) for c in cols)


def gleaf(ic: Icon, base, deg: float, length: float, width: float, colors=LEAF, droop: float = 0.15,
          acc: list | None = None) -> None:
    """Glossy pointed leaf: lit/shadow halves by tone, a pale gloss sliver, faint midrib."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 20)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * math.sin(math.pi * t ** 0.8) * (1 + 0.06 * math.sin(11 * t)) for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], radial=(min(xs), min(ys), length * 1.15), noise=0.18, chroma=0.14)
    lower, nu = (s1, -n) if n[1] > 0 else (s2, n)
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (6, 14, 4), 0.30)
    gloss = [tuple(spine[k] + nu * hw[k] * 0.22) for k in range(3, 13)]
    gloss += [tuple(spine[k] + nu * hw[k] * 0.72) for k in range(12, 2, -1)]
    ic.shade(ic.poly_mask(gloss), (226, 240, 206), 0.26, blur=2)
    ic.line([tuple(p) for p in spine[1:-4]], 3, (150, 176, 110, 90))
    ic.outline(pts, 3, (16, 26, 8, 120))
    if acc is not None:
        acc[0] = union(acc[0], m)


def pod(ic: Icon, top, L: float, W: float, deg: float, pal) -> None:
    """Ribbed cacao pod hanging from ``top`` towards ``deg`` (90 = straight down): blunt at the
    stalk, tapering to a point, five ribs, lit from the upper left with a core shadow and a gloss."""
    mid, lit, dk = pal
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(top, float)
    ts = np.linspace(0, 1, 26)
    spine = [b + d * L * t for t in ts]
    hw = [W / 2 * math.sin(math.pi * min(1.0, 0.12 + t * 0.95) ** 0.95) ** 0.7 for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, lit, dk, radial=(min(xs) + W * 0.15, min(ys) + L * 0.12, L * 1.25), noise=0.18, chroma=0.1)
    ic.shade(m, mid, 0.3)
    # the side away from the light (larger x) carries the core shadow
    far = s1 if n[0] > 0 else s2
    sgn = 1 if n[0] > 0 else -1
    core = [tuple(spine[k] + n * sgn * hw[k] * 0.25) for k in range(len(ts))] + [tuple(p) for p in far[::-1]]
    ic.shade(ic.poly_mask(core), (20, 8, 4), 0.38, blur=5)

    def ribs(dr):
        for u in (-0.72, -0.36, 0.0, 0.36, 0.72):
            groove = [tuple(spine[k] + n * hw[k] * u) for k in range(2, len(ts) - 2)]
            ridge = [tuple(spine[k] + n * hw[k] * (u - 0.16 * sgn)) for k in range(2, len(ts) - 3)]
            dr.line(groove, fill=tuple(int(v * 0.55) for v in dk) + (130,), width=4)
            dr.line(ridge, fill=lit + (90,), width=3)

    ic.overlay(ribs, m)
    g = [tuple(spine[k] - n * sgn * hw[k] * 0.55) for k in range(4, 14)]
    g += [tuple(spine[k] - n * sgn * hw[k] * 0.2) for k in range(13, 3, -1)]
    ic.shade(ic.poly_mask(g), (255, 240, 210), 0.35, blur=3)
    ic.outline(pts, 3, (40, 16, 8, 150))
    stalk = [tuple(b - d * 14), tuple(b + d * 8)]
    ic.line(stalk, 9, (86, 70, 40))


def split_pod(ic: Icon, cx: float, cy: float, L: float, W: float, deg: float, pal) -> None:
    """Opened cacao pod lying on the ground: thick coloured shell, pale pulp packed with beans."""
    mid, lit, dk = pal
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    c = np.array([cx, cy], float)
    ts = np.linspace(-0.5, 0.5, 26)

    def outline(f, g):
        up = [c + d * L * t * f + n * W / 2 * g * math.cos(math.pi * t) ** 0.7 for t in ts]
        lo = [c + d * L * t * f - n * W / 2 * g * math.cos(math.pi * t) ** 0.7 for t in ts[::-1]]
        return [tuple(p) for p in up + lo]

    shell = outline(1.0, 1.0)
    ic.shade(ic.mask("ellipse", (cx - L * 0.55, cy - W * 0.1, cx + L * 0.55, cy + W * 0.75)), alpha=0.45, blur=10,
             clip=False)
    ic.fill(ic.poly_mask(shell), lit, dk, radial=(cx - L * 0.4, cy - W * 0.4, L), noise=0.2)
    ic.outline(shell, 3, (40, 16, 8, 160))
    inner = outline(0.9, 0.72)
    im = ic.poly_mask(inner)
    ic.fill(im, "#efe4cc", "#b8a88a", radial=(cx - L * 0.3, cy - W * 0.3, L * 0.8), noise=0.12)
    ic.shade(ic.intersect(im, ic.mask("rectangle", (0, 0, SIZE, cy - W * 0.12))), (60, 30, 12), 0.35, blur=6)
    beans = []
    for row in (-0.2, 0.2):
        for t in np.linspace(-0.34, 0.34, 6):
            p = c + d * L * t * 0.9 + n * W * row * 0.62 * math.cos(math.pi * t) ** 0.5
            beans.append((p[0], p[1]))

    def paint(dr):
        for x, y in beans:
            r = W * 0.13
            dr.ellipse((x - r * 1.2 + 2, y - r + 3, x + r * 1.2 + 2, y + r + 3), fill=(120, 96, 80, 150))
            dr.ellipse((x - r * 1.2, y - r, x + r * 1.2, y + r), fill=(226, 210, 196, 255))
            dr.ellipse((x - r * 0.8, y - r * 0.7, x + r * 0.1, y - r * 0.05), fill=(252, 246, 236, 220))

    ic.overlay(paint, im)
    ic.outline(inner, 3, (90, 60, 40, 140))


def paddle(ic: Icon, base, deg: float, length: float, width: float, droop: float = 0.3, colors=BANANA,
           tears: int = 5) -> None:
    """Banana leaf: long oblong blade with a pale midrib, fine parallel veins, wind tears and a dry edge."""
    rnd = ic.random
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 24)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * min(1.0, 3.2 * t) * (1 - 0.35 * t ** 3) for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], radial=(min(xs), min(ys), length * 1.1), noise=0.2, chroma=0.14)
    lower = s1 if n[1] > 0 else s2
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (8, 16, 4), 0.32)

    def veins(dr):
        for k in range(2, len(ts) - 1):
            for side in (1, -1):
                p0 = spine[k]
                p1 = spine[min(k + 2, len(ts) - 1)] + n * side * hw[k] * 1.1
                dr.line([tuple(p0), tuple(p1)], fill=(30, 46, 14, 60), width=3)
        for _ in range(tears):
            k = rnd.randint(4, len(ts) - 3)
            side = rnd.choice((1, -1))
            p0 = spine[k] + n * side * hw[k] * 1.05
            p1 = spine[k + 1] + n * side * hw[k] * rnd.uniform(0.15, 0.4)
            dr.line([tuple(p0), tuple(p1)], fill=(20, 26, 10, 220), width=5)

    ic.overlay(veins, m)
    edge = [tuple(p) for p in (s1 if n[1] < 0 else s2)[len(ts) // 2:]]
    ic.line(edge, 7, (150, 128, 70, 110))
    ic.line([tuple(p) for p in spine], 8, (196, 196, 120, 170))
    ic.outline(pts, 3, (20, 30, 8, 130))


def cacao_tree(ic: Icon, x: float, base: float, fork: float, limbs, crown, pods, leaves: int = 80,
               scale: float = 1.0) -> Image.Image:
    """Cacao tree: grey-brown trunk forking into limbs, a dark crown of long hanging leaves with a
    bronze new flush on top, then pods hung on trunk and limbs. Returns the crown mask."""
    rnd = ic.random
    s = scale
    trunk = [(x - 44 * s, base), (x - 28 * s, base - 30 * s), (x - 20 * s, fork), (x + 20 * s, fork - 6 * s),
             (x + 26 * s, base - 30 * s), (x + 46 * s, base)]
    ic.poly(trunk, "#948470", "#3e3228", span=(x - 30 * s, x + 30 * s), vertical=False, noise=0.26, edge=3)
    for _ in range(int(12 * s)):
        yy = rnd.uniform(fork, base - 20)
        xx = x + rnd.uniform(-14, 14) * s
        light = rnd.random() < 0.45
        ic.shade(ic.mask("ellipse", (xx - 7 * s, yy - 14 * s, xx + 7 * s, yy + 14 * s)),
                 (222, 218, 196) if light else (20, 16, 12), 0.22 if light else 0.22, blur=3)
    for ex, ey, w in limbs:
        mx, my = (x + ex) / 2 + (ex - x) * 0.1, (fork + ey) / 2 + 20 * s
        path = [(x, fork + 10 * s), (mx, my), (ex, ey)]
        ic.line(path, int(w * s) + 6, (40, 30, 22, 200))
        ic.line(path, int(w * s), (112, 96, 78))
        ic.line([(p[0] - 4, p[1] - 2) for p in path], max(int(w * s) // 3, 3), (176, 164, 140, 150))
    cx, cy, rx, ry = crown
    mass = blank()
    for _ in range(9):  # lumpy dark inner mass
        u = rnd.uniform(-0.75, 0.75)
        bx, by = cx + u * rx, cy + rnd.uniform(-0.35, 0.3) * ry * (1 - u * u)
        br = ry * rnd.uniform(0.4, 0.55)
        mass = union(mass, ic.poly_mask(ic.jitter(bx, by, br * 1.25, br, 16, 0.1)))
    ic.fill(mass, "#2a4618", "#0a1404", radial=(cx - rx * 0.5, cy - ry, rx * 1.6), noise=0.3)
    acc = [mass]
    # leaf whorls at the twig ends: each a drooping fan of long leaves, laid back to front
    nodes = []
    for _ in range(leaves // 6):
        a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.6
        px, py = cx + math.cos(a) * rx * 0.82 * r, cy + math.sin(a) * ry * 0.72 * r - ry * 0.12
        nodes.append((rnd.random() * 0.6 + 0.4 * (py - cy + ry) / (2 * ry), px, py))
    nodes.sort()
    for depth, px, py in nodes:
        u = (px - cx) / rx
        v = (py - cy) / ry
        f = 0.55 + 0.5 * depth - 0.25 * v
        cols = darker(LEAF, f)
        flush = v < -0.35 and rnd.random() < 0.3
        hang = math.degrees(math.atan2(v * 0.6 + 0.8, u * 0.9))
        k = rnd.randint(5, 7)
        for j in range(k):
            ang = hang + (j / (k - 1) - 0.5) * rnd.uniform(110, 150) + rnd.uniform(-10, 10)
            L = rnd.uniform(70, 112) * s * (0.8 if flush else 1.0)
            c = darker(FLUSH, 0.95 + 0.15 * depth) if flush and j % 2 == 0 else cols
            gleaf(ic, (px, py), ang, L, L * rnd.uniform(0.36, 0.42), c, rnd.uniform(0.2, 0.4), acc)
    m = acc[0]
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 0.4, cy - ry * 0.2, cx + rx * 1.6, cy + ry * 1.6))),
             (6, 12, 4), 0.35, blur=40)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 1.2, cy - ry * 1.3, cx + rx * 0.2, cy - ry * 0.1))),
             (240, 236, 190), 0.12, blur=30)
    for p in pods:
        pod(ic, (p[0], p[1]), *p[2:])
    return m


def scatter(ic: Icon, clip: Image.Image, y0: float, y1: float, x0: float, x1: float, step: float,
            size: float, palettes) -> None:
    """Beans spread over a surface in perspective (smaller towards the back)."""
    rnd = ic.random
    items = []
    y = y0 + 3
    while y < y1:
        s = 0.78 + 0.22 * (y - y0) / (y1 - y0)
        x = x0 + rnd.uniform(0, step)
        while x < x1:
            items.append((x + rnd.uniform(-3, 3), y + rnd.uniform(-2, 2), s, rnd.choice(palettes), rnd.uniform(0, 1)))
            x += step * s * rnd.uniform(0.8, 1.15)
        y += step * 0.62 * s

    def paint(dr):
        for x, yy, s, (mid, dk), r in items:
            w, hh = size * s * (0.9 + 0.3 * r), size * s * 0.62
            dr.ellipse((x - w + 1, yy - hh + 2, x + w + 1, yy + hh + 2), fill=dk + (200,))
            dr.ellipse((x - w, yy - hh, x + w, yy + hh), fill=mid + (255,))
            dr.ellipse((x - w * 0.7, yy - hh * 0.8, x + w * 0.1, yy - hh * 0.1),
                       fill=tuple(min(255, int(v * 1.35)) for v in mid) + (170,))

    ic.overlay(paint, clip)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.62
    ic.grade["mute"] = 0.84

    # ---- banana plant behind on the right: pseudostem and torn paddle leaves (the grove's shade)
    ic.poly([(784, 800), (792, 440), (826, 430), (836, 800)], "#8c9a56", "#3e4a22", span=(784, 836),
            vertical=False, noise=0.3, edge=3)
    for y in (520, 600, 690):
        ic.line([(788, y), (832, y - 18)], 5, (60, 50, 30, 120))
    for deg, L, W, dr in ((-140, 300, 150, 0.55), (-100, 250, 140, 0.35), (-55, 290, 150, 0.5), (-18, 280, 150, 0.75),
                          (190, 260, 140, 0.8)):
        paddle(ic, (810, 440), deg, L, W, dr, tears=9)
    ic.line([(812, 436), (800, 360)], 20, (110, 124, 60))  # furled new leaf
    ic.line([(810, 436), (798, 362)], 7, (180, 190, 110, 150))

    # ---- ground strip
    top = [(20, 936)] + [(x, 910 + rnd.uniform(-12, 10)) for x in np.linspace(80, 960, 12)] + [(1010, 930)]
    ground = top + [(1012, 996), (520, 1006), (18, 998)]
    ic.poly(ground, "#735a3a", "#4a3a26", noise=0.32, edge=3)
    for _ in range(40):  # clods, husks and fallen leaves
        x, y = rnd.uniform(40, 990), rnd.uniform(928, 994)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)), (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)

    # ---- raised drying tray of dark fermented beans, right
    BK, FY = 716, 800
    for x in (560, 780, 992):
        ic.rect((x - 14, FY, x + 14, 936 + rnd.uniform(-4, 4)), "#9a7048", "#4e3420", vertical=False, edge=3)
    ic.shade(ic.mask("ellipse", (520, 916, 1016, 958)), alpha=0.35, blur=10)
    surf = [(576, BK), (988, BK), (1008, FY), (548, FY)]
    S = ic.poly_mask(surf)
    ic.fill(S, "#4a3020", "#3a2416", (BK, FY), noise=0.3)
    scatter(ic, S, BK, FY, 556, 1008, 16, 8, BEANS)
    for y in (738, 760, 782):  # raked furrows
        ic.shade(ic.intersect(S, ic.mask("rectangle", (0, y, SIZE, y + 5))), (20, 10, 4), 0.3, blur=3)
    ic.shade(ic.intersect(S, ic.mask("rectangle", (0, BK, SIZE, BK + 16))), alpha=0.35, blur=6)
    ic.line([(576, BK), (988, BK)], 12, (126, 92, 60))
    ic.line([(576, BK), (548, FY)], 12, (140, 104, 68))
    ic.line([(988, BK), (1008, FY)], 12, (100, 72, 46))
    ic.rect((542, FY, 1012, 838), "#9a7450", "#5e4028", noise=0.2, edge=4)
    for y in (810, 822):
        ic.line([(552, y + rnd.uniform(-2, 2)), (1000, y + rnd.uniform(-2, 2))], 2, (60, 40, 22, 90))
    ic.shade(ic.mask("rectangle", (542, FY, 1012, 806)), (255, 240, 210), 0.25)
    # wooden rake on the beans
    ic.line([(700, 792), (880, 738)], 11, (40, 28, 16, 120))
    ic.line([(696, 786), (876, 732)], 8, (170, 130, 84))
    ic.line([(858, 712), (898, 756)], 11, (124, 90, 56))

    # ---- cacao tree, the hero: pods on trunk and limbs
    X, BASE, FORK = 330, 990, 700
    limbs = ((120, 420, 28), (300, 330, 26), (540, 400, 28))
    pods = [
        (X - 26, 730, 180, 90, 112, YELLOW),
        (X + 24, 790, 186, 92, 70, RED),
        (X - 24, 890, 110, 58, 104, UNRIPE),
        (X + 160, 556, 190, 92, 84, ORANGE),
        (X - 156, 534, 176, 86, 100, RED),
        (X + 222, 490, 130, 64, 78, UNRIPE),
        (X - 40, 596, 150, 74, 96, YELLOW),
        (X + 64, 610, 140, 70, 84, MAROON),
    ]
    cacao_tree(ic, X, BASE, FORK, limbs, (330, 320, 320, 190), pods, leaves=170)
    ic.shade(ic.mask("ellipse", (180, 950, 500, 1004)), alpha=0.45, blur=12)

    # ---- in front: an opened pod with pulp and beans, a picked whole pod
    split_pod(ic, 630, 952, 230, 112, -8, ORANGE)
    ic.shade(ic.mask("ellipse", (770, 950, 960, 998)), alpha=0.45, blur=8)
    pod(ic, (772, 944), 180, 84, -6, YELLOW)

    # ---- dappled light under the banana and the crown
    for _ in range(18):
        x, y = rnd.uniform(60, 1000), rnd.uniform(560, 900)
        r = rnd.uniform(30, 60)
        ic.shade(ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), (12, 16, 6), 0.14, blur=18)
