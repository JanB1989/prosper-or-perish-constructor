"""Managed Cocoa Grove: a planted row of cacao under a planned shade tree, a shingled fermentation
shed with stepped fermentation boxes, a long drying tray of cured beans.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/managed_cocoa_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/managed_cocoa_grove

Identity: the Cocoa Grove's pod-laden cacao tree, now one of an orderly row of three pruned trees
receding to the right (each further back smaller and hazier, with sky between the crowns) under a
tall planned immortelle shade tree (leaning forked trunk, loose crown of four separate lobes tipped
with orange-red blossoms);
on the left an open timber shed, gable end to the viewer, shingle roof, sheltering two stepped
fermentation boxes (the upper one covered with banana leaves, the lower one opened on pale
fermenting beans); in front of the shed a raised drying tray of dark cured beans with jute sacks, a basket of pods.

Local helpers: ``gleaf``, ``pod``, ``split_pod``, ``paddle``, ``cacao_tree``, ``scatter`` (from
cocoa_grove); ``jute`` (from coffee_grove); ``lobe``, ``blossoms``, ``immortelle`` (lobed
shade-tree crown with flower clusters), ``hazed`` (aerial perspective on what was just painted); ``box`` (wooden fermentation box with its
contents), ``grove_tree`` (scaled cacao of the row), ``roof_plane`` (shingled slope of a gable roof
facing the viewer).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 43
REFS = ("fruit_orchard", "sugar_plantation", "tobacco_plantation", "farming_village")

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
               scale: float = 1.0, spread: float = 0.82, leaf_len=(70, 112)) -> Image.Image:
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
        px, py = cx + math.cos(a) * rx * spread * r, cy + math.sin(a) * ry * 0.72 * r - ry * 0.12
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
            L = rnd.uniform(*leaf_len) * s * (0.8 if flush else 1.0)
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


def lobe(ic: Icon, cx: float, cy: float, r: float) -> Image.Image:
    """One rounded leaf lobe of the immortelle crown: overlapping clumps laid top to bottom, each lit
    from the upper left, leaf dabs, a dark underside. Returns its mask."""
    rnd = ic.random
    m = blank()
    blobs = [(cx, cy, r * 0.55)]
    for _ in range(12):
        a, d = rnd.uniform(0, 2 * math.pi), r * rnd.uniform(0.3, 0.6)
        blobs.append((cx + math.cos(a) * d * 1.1, cy + math.sin(a) * d * 0.85, r * rnd.uniform(0.26, 0.4)))
    blobs.sort(key=lambda b: b[1])
    for bx, by, br in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.15, br, 22, 0.1))
        ic.fill(bm, "#76a04a", "#1e3414", radial=(bx - br * 0.8, by - br * 0.9, br * 2.3), noise=0.28, chroma=0.14)
        m = union(m, bm)

    def dabs(dr):
        for _ in range(int(r * 5)):
            x, y = cx + rnd.uniform(-1.2, 1.2) * r, cy + rnd.uniform(-1.1, 1.0) * r
            v = (y - cy) / r
            rr = rnd.uniform(3, 7)
            col = (164, 186, 104, 80) if rnd.random() < 0.5 - 0.6 * v else (22, 34, 12, 80)
            dr.ellipse((x - rr, y - rr * 0.55, x + rr, y + rr * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - r * 1.1, cy + r * 0.05, cx + r * 1.5, cy + r * 1.6))),
             (10, 18, 6), 0.45, blur=16)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - r * 1.3, cy - r * 1.3, cx + r * 0.1, cy))),
             (244, 240, 196), 0.16, blur=18)
    return m


def blossoms(ic: Icon, cx: float, cy: float, r: float, n: int) -> None:
    """Orange-red immortelle flower clusters on the outer tips of a lobe: a spray of claw-shaped
    petals fanning outwards, dark root, bright tips, big enough to survive at 64 px."""
    rnd = ic.random
    items = []
    for k in range(n):
        a = math.radians(-180 + 180 * (k + rnd.uniform(0.25, 0.75)) / n)
        items.append((cx + math.cos(a) * r * 0.8, cy + math.sin(a) * r * 0.72, a, rnd.uniform(18, 24)))

    def paint(dr):
        for x, y, a, s in items:
            dr.ellipse((x - s * 0.7, y - s * 0.3, x + s * 0.7, y + s * 0.6), fill=(90, 26, 10, 200))
            for j in range(7):
                b = a + (j / 6 - 0.5) * 3.0
                tip = (x + math.cos(b) * s, y + math.sin(b) * s)
                dr.line([(x, y), tip], fill=(120, 34, 14, 255), width=int(s * 0.5))
                dr.line([(x, y), tip], fill=(226, 84, 34, 255), width=int(s * 0.32))
                dr.ellipse((tip[0] - 4, tip[1] - 4, tip[0] + 4, tip[1] + 4), fill=(252, 152, 72, 255))
            dr.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(250, 126, 52, 255))

    ic.overlay(paint)


def immortelle(ic: Icon) -> None:
    """Planned shade tree (Erythrina): a slightly leaning trunk forking below a loose, tall rounded
    crown of four separate leaf lobes with sky between them, orange-red blossoms on the outer tips."""
    ic.poly([(752, 870), (768, 640), (786, 470), (796, 400), (840, 400), (840, 470), (828, 640), (824, 870)],
            "#948270", "#3a2e24", span=(770, 830), vertical=False, noise=0.26, edge=3)
    ic.line([(784, 860), (798, 470), (806, 410)], 5, (196, 184, 160, 120))
    for path, w in ((((812, 420), (740, 330), (652, 240)), 22), (((822, 420), (880, 340), (925, 262)), 22),
                    (((872, 350), (838, 230), (805, 140)), 16), (((806, 420), (795, 350), (790, 310)), 14)):
        ic.line(path, w + 6, (40, 30, 22, 200))
        ic.line(path, w, (104, 88, 70))
        ic.line([(p[0] - 3, p[1] - 2) for p in path], max(w // 3, 3), (170, 154, 130, 150))
    lobes = ((800, 118, 110, 3), (638, 222, 94, 3), (926, 244, 84, 3), (790, 318, 66, 2))
    for cx, cy, r, _ in sorted(lobes, key=lambda l: l[1]):
        lobe(ic, cx, cy, r)
    for cx, cy, r, n in lobes:
        blossoms(ic, cx, cy, r, n)


def hazed(ic: Icon, before: Image.Image, alpha: float) -> None:
    """Aerial perspective: lighten and cool everything painted since ``before``."""
    diff = ImageChops.difference(before, ic.image).convert("L").point(lambda v: 255 if v > 0 else 0)
    ic.shade(diff, (200, 212, 200), alpha)


def jute(ic: Icon, cx: float, base: float, w: float, h: float, color) -> None:
    """Filled jute sack (from coffee_grove): lumpy body shaded from the upper left, tied neck, weave."""
    body = ic.jitter(cx, base - h * 0.42, w * 0.5, h * 0.44, 14, 0.06)
    dark = tuple(int(v * 0.45) for v in rgb(color))
    ic.fill(ic.poly_mask(body), color, dark, radial=(cx - w * 0.35, base - h * 0.8, w * 1.2), noise=0.3)
    ic.outline(body, 3, (40, 28, 16, 150))
    ic.poly([(cx - 10, base - h * 0.84), (cx - 16, base - h), (cx + 14, base - h * 1.02), (cx + 9, base - h * 0.84)],
            color, dark, edge=3)
    ic.line([(cx - 13, base - h * 0.86), (cx + 12, base - h * 0.86)], 5, (60, 44, 26))

    def weave(dr):
        for k in range(8):
            y = base - h * (0.15 + 0.08 * k)
            dr.line([(cx - w * 0.4, y), (cx + w * 0.4, y + 3)], fill=(50, 36, 20, 50), width=2)

    ic.overlay(weave, ic.poly_mask(body))


def box(ic: Icon, x0: float, top: float, x1: float, bottom: float, rim: float, fill_cols) -> Image.Image:
    """Wooden fermentation box seen from the raised camera: plank front with grain and a dark joint
    line per board, a lit top rim, and the contents inside the opening. Returns the contents mask."""
    rnd = ic.random
    ic.rect((x0, top, x1, bottom), "#9a7048", "#56381f", noise=0.24, edge=3)
    for k, y in enumerate(np.arange(top + 30, bottom - 5, 30)):
        ic.line([(x0 + 4, y + rnd.uniform(-2, 2)), (x1 - 4, y + rnd.uniform(-2, 2))], 3, (48, 30, 16, 150))
        ic.line([(x0 + 4, y + 4), (x1 - 4, y + 4)], 2, (220, 180, 130, 60))
    for x in (x0 + 12, x1 - 12):
        ic.line([(x, top + 4), (x, bottom - 4)], 12, (74, 50, 30))
    opening = [(x0 + 18, top - rim), (x1 - 18, top - rim), (x1 - 6, top), (x0 + 6, top)]
    om = ic.poly_mask(opening)
    ic.fill(om, fill_cols[0], fill_cols[1], (top - rim, top), noise=0.3)
    ic.line([(x0 + 18, top - rim), (x1 - 18, top - rim)], 10, (132, 98, 64))
    ic.line([(x0, top), (x1, top)], 12, (176, 134, 88))
    ic.line([(x0 + 18, top - rim), (x0, top)], 10, (150, 112, 74))
    ic.line([(x1 - 18, top - rim), (x1, top)], 10, (104, 74, 46))
    ic.shade(ic.mask("rectangle", (x0, top + 6, x1, top + 26)), alpha=0.3, blur=6)
    return om


def grove_tree(ic: Icon, x: float, base: float, s: float, pods, leaves: int, lift: float = 0,
               pod_s: float = 1.0) -> Image.Image:
    """A pruned, compact cacao tree of the planted rows at scale ``s``, its crown raised by ``lift``
    (a longer clear stem, for trees further back); ``pods`` are (dx, dy, L, W, deg, pal) relative to
    the trunk foot in unscaled units, their size times ``pod_s``."""
    top = base - lift
    fork = top - 280 * s
    limbs = ((x - 130 * s, top - 560 * s, 28), (x - 16 * s, top - 650 * s, 26), (x + 130 * s, top - 580 * s, 28))
    crown = (x, top - 660 * s, 190 * s, 168 * s)
    pp = [(x + dx * s * 0.8, top + dy * s, L * s * pod_s, W * s * pod_s, deg, pal) for dx, dy, L, W, deg, pal in pods]
    return cacao_tree(ic, x, base, fork, limbs, crown, pp, leaves=leaves, scale=s, spread=0.56, leaf_len=(62, 94))


POD_SET = [
    (-26, -260, 180, 90, 112, YELLOW),
    (24, -200, 186, 92, 70, RED),
    (-24, -100, 110, 58, 104, UNRIPE),
    (150, -440, 180, 88, 84, ORANGE),
    (-150, -450, 170, 84, 100, RED),
    (-40, -400, 150, 74, 96, YELLOW),
    (60, -380, 140, 70, 84, MAROON),
]


def roof_plane(ic: Icon, peak, eave, D, c1, c2, courses: int = 9) -> Image.Image:
    """One slope of a gable roof facing the viewer, receding by ``D``: wooden shingles laid in
    courses parallel to the eave, each shingle its own tone, each course's butt casting a thin
    shadow down-slope; a lit bargeboard along the front rake. Returns the plane mask."""
    rnd = ic.random
    a, b, D = np.array(peak, float), np.array(eave, float), np.array(D, float)
    pts = [tuple(a), tuple(b), tuple(b + D), tuple(a + D)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.24, chroma=0.06)

    def paint(dr):
        for i in range(courses):
            t0, t1 = i / courses, (i + 1) / courses
            p0, p1 = a + (b - a) * t0, a + (b - a) * t1
            n = 5
            cut = sorted([0.0, 1.0] + [(j + rnd.uniform(-0.25, 0.25) + (0.5 if i % 2 else 0)) / n for j in range(1, n)])
            for u0, u1 in zip(cut[:-1], cut[1:]):
                u0, u1 = max(0.0, u0), min(1.0, u1)
                if u1 - u0 < 0.02:
                    continue
                q = [tuple(p0 + D * u0), tuple(p0 + D * u1), tuple(p1 + D * u1), tuple(p1 + D * u0)]
                t = rnd.uniform(-1, 1)
                dr.polygon(q, fill=(20, 10, 6, int(-t * 70)) if t < 0 else (255, 236, 210, int(t * 50)))
                dr.line([q[1], q[2]], fill=(40, 22, 14, 110), width=3)
            dr.line([tuple(p1 + (b - a) * 0.012), tuple(p1 + D + (b - a) * 0.012)], fill=(18, 8, 4, 120), width=6)
            dr.line([tuple(p1), tuple(p1 + D)], fill=(255, 232, 205, 60), width=3)

    ic.overlay(paint, m)
    ic.outline(pts, 5)
    return m


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.62
    ic.grade["mute"] = 0.84

    # ---- planned shade tree behind the row: leaning forked trunk, lobed crown with immortelle blossoms
    immortelle(ic)

    # ---- ground: a strip at the front, the planted rows receding on the right
    top = [(20, 936)] + [(x, 912 + rnd.uniform(-10, 8)) for x in np.linspace(80, 560, 6)]
    top += [(x, 912 - 100 * ((x - 560) / 450) ** 0.8 + rnd.uniform(-8, 6)) for x in np.linspace(620, 980, 5)]
    top += [(1012, 808)]
    ic.poly(top + [(1012, 996), (520, 1006), (18, 998)], "#735a3a", "#4a3a26", noise=0.32, edge=3)
    ic.shade(ic.mask("rectangle", (560, 780, SIZE, 900)), (200, 212, 200), 0.12, blur=30)

    # ---- the row of cacao receding to the right: each further back smaller and hazier, sky between
    before = ic.image.copy()
    grove_tree(ic, 962, 836, 0.27, POD_SET[:4], 50, lift=120, pod_s=1.1)
    hazed(ic, before, 0.2)
    before = ic.image.copy()
    grove_tree(ic, 806, 884, 0.43, POD_SET[:5], 80, lift=50, pod_s=1.1)
    hazed(ic, before, 0.1)

    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(928, 994)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)), (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)

    # ---- fermentation shed on the left: gable end to the viewer, open below, shingled roof
    ic.rect((24, 470, 392, 820), "#33261a", "#16100a", edge=0)

    def slats(dr):
        for x in np.arange(34, 392, 28):
            dr.line([(x + rnd.uniform(-3, 3), 480), (x, 820)], fill=(90, 70, 50, 60), width=4)

    ic.overlay(slats)
    top_box = box(ic, 44, 610, 234, 704, 34, ("#3c2a1a", "#2a1c10"))
    with ic.clipped(ic.mask("rectangle", (34, 560, 244, 620))):
        for k, (bx, deg) in enumerate(((50, -6), (114, 4), (174, -2))):
            paddle(ic, (bx - 10, 592 + k * 4), deg, 150, 64, 0.1, ("#8cc04a", "#3a6c1c"), tears=3)
    low = box(ic, 150, 704, 372, 806, 38, ("#a26c58", "#6a4636"))
    scatter(ic, low, 666, 704, 160, 362, 15, 7, [((206, 152, 138), (112, 76, 66)), ((186, 128, 112), (98, 62, 52)),
                                                  ((222, 178, 156), (122, 90, 76))])
    ic.line([(320, 676), (276, 580)], 9, (150, 112, 70))  # wooden shovel
    ic.poly([(314, 668), (338, 662), (342, 706), (314, 710)], "#a07a50", "#5e4428", edge=3)
    for x, top_y in ((34, 470), (208, 470), (382, 470)):
        ic.rect((x - 13, top_y, x + 13, 822), "#8a6442", "#4a3220", vertical=False, edge=3)
    ic.shade(ic.mask("rectangle", (24, 470, 392, 560)), alpha=0.5, blur=14)
    # gable wall of upright boards with a vent
    gable = [(208, 300), (14, 476), (402, 476)]
    ic.poly(gable, "#9a7a56", "#6a4c30", noise=0.26, edge=4)

    def boards(dr):
        for x in np.arange(30, 400, 24):
            dr.line([(x + rnd.uniform(-2, 2), 290), (x, 480)], fill=(50, 32, 18, 110), width=3)
            dr.line([(x + 4, 290), (x + 4, 480)], fill=(230, 200, 150, 40), width=2)

    ic.overlay(boards, ic.poly_mask(gable))
    ic.shade(ic.poly_mask([(208, 300), (402, 476), (208, 476)]), alpha=0.25)
    ic.fill(ic.mask("polygon", [(208, 372), (184, 410), (232, 410)]), "#2a1e14", "#16100a")
    ic.rect((10, 468, 406, 488), "#7a5a3a", "#4a3422", edge=3)
    D = (0, -96)
    roof_plane(ic, (208, 290), (-6, 486), D, "#9a7a58", "#6a4e34")
    rr = roof_plane(ic, (208, 290), (424, 486), D, "#7a5e44", "#4a3626")
    ic.shade(rr, alpha=0.22)
    ic.line([(208, 290), (208, 194)], 12, (70, 50, 32))
    ic.line([(-6, 486), (208, 290), (424, 486)], 14, (150, 116, 78))
    ic.line([(-6, 490), (208, 294), (424, 490)], 4, (50, 34, 20, 160))

    # ---- raised drying tray of dark cured beans in front of the shed
    BK, FY = 816, 874
    for x in (40, 250, 470):
        ic.rect((x - 13, FY, x + 13, 950 + rnd.uniform(-4, 4)), "#9a7048", "#4e3420", vertical=False, edge=3)
    ic.shade(ic.mask("ellipse", (10, 930, 520, 966)), alpha=0.35, blur=10)
    surf = [(46, BK), (470, BK), (494, FY), (22, FY)]
    S = ic.poly_mask(surf)
    ic.fill(S, "#4a3020", "#3a2416", (BK, FY), noise=0.3)
    scatter(ic, S, BK, FY, 26, 494, 15, 7.5, BEANS)
    ic.shade(ic.intersect(S, ic.mask("rectangle", (0, BK, SIZE, BK + 14))), alpha=0.35, blur=6)
    ic.line([(46, BK), (470, BK)], 11, (126, 92, 60))
    ic.line([(46, BK), (22, FY)], 11, (140, 104, 68))
    ic.line([(470, BK), (494, FY)], 11, (100, 72, 46))
    ic.rect((16, FY, 500, 906), "#9a7450", "#5e4028", noise=0.2, edge=4)
    ic.line([(28, 890), (488, 891)], 2, (60, 40, 22, 90))
    ic.shade(ic.mask("rectangle", (16, FY, 500, 880)), (255, 240, 210), 0.25)
    jute(ic, 70, 1000, 110, 120, "#9c8054")
    jute(ic, 150, 1002, 84, 96, "#8a7048")

    # ---- front cacao tree of the row, the biggest
    grove_tree(ic, 546, 992, 0.72, POD_SET, 140, pod_s=1.1)
    ic.shade(ic.mask("ellipse", (460, 956, 690, 1004)), alpha=0.45, blur=12)

    # ---- basket of pods, bottom right
    ic.shade(ic.mask("ellipse", (800, 966, 1000, 1002)), alpha=0.45, blur=8)
    ic.fill(ic.mask("ellipse", (822, 874, 988, 916)), "#3a1a10", "#241008")
    for dx, dy, deg, pal in ((-50, 894, -20, YELLOW), (10, 884, 10, RED), (-20, 872, -80, ORANGE), (40, 870, 200, YELLOW)):
        pod(ic, (906 + dx, dy), 100, 50, deg, pal)
    ic.basket(820, 896, 990, 1000)

    # ---- dappled shade
    for _ in range(18):
        x, y = rnd.uniform(60, 1000), rnd.uniform(560, 900)
        r = rnd.uniform(30, 60)
        ic.shade(ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), (12, 16, 6), 0.14, blur=18)
