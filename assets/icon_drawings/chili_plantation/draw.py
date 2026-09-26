"""Chili Plantation: rows of chili bushes hung with red pods; strings of chilies drying under a thatch.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/chili_plantation/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/chili_plantation

Identity: long red strings of chilies (ristras) hanging in a row from a thatched drying frame, low
bushy chili plants set with red and green pods in front, a woven mat of red pods drying at the
bottom right.

Local helpers: ``gleaf`` (glossy leaf, from coffee_grove), ``pod`` (curved tapering chili with a
calyx), ``ristra`` (string of pods), ``bush`` (chili plant), ``thatch`` (from coffee_grove),
``mat`` (woven mat).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 17
REFS = ("fiber_crops_farm", "fruit_orchard", "tobacco_plantation", "farming_village")

LEAF = ("#56823a", "#14260c")
LEAF_TOP = ("#669444", "#1c3212")

RED = ("#cc2c1c", "#560a08")
CRIMSON = ("#a8201c", "#440808")
SCARLET = ("#d23c24", "#620e08")
ORANGE = ("#d0762a", "#6a300c")
UNRIPE = ("#6e9a34", "#223a0c")
DRIED = ("#8c2418", "#360a06")


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def gleaf(ic: Icon, base, deg: float, length: float, width: float, colors=LEAF, droop: float = 0.15,
          acc: list | None = None) -> None:
    """Glossy pointed leaf: lit/shadow halves by tone, a pale gloss sliver, faint midrib."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 18)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * math.sin(math.pi * t ** 0.8) for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], radial=(min(xs), min(ys), length * 1.15), noise=0.18, chroma=0.14)
    lower, nu = (s1, -n) if n[1] > 0 else (s2, n)
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (6, 14, 4), 0.30)
    gloss = [tuple(spine[k] + nu * hw[k] * 0.22) for k in range(3, 12)]
    gloss += [tuple(spine[k] + nu * hw[k] * 0.72) for k in range(11, 2, -1)]
    ic.shade(ic.poly_mask(gloss), (226, 240, 206), 0.26, blur=2)
    ic.outline(pts, 3, (16, 26, 8, 120))
    if acc is not None:
        acc[0] = union(acc[0], m)


def pod(ic: Icon, top, deg: float, length: float, width: float, colors=RED, curl: float = 0.18,
        acc: list | None = None) -> None:
    """Chili pod hanging from ``top`` towards ``deg`` (90 = down): shouldered, tapering, curled tip,
    shaded round with a long gloss highlight and a green calyx cap."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(top, float)
    ts = np.linspace(0, 1, 16)
    spine = [b + d * length * t + n * curl * length * t ** 2.2 for t in ts]
    hw = [width / 2 * (0.7 + 0.3 * math.sin(math.pi * min(t * 2.2, 1) / 2)) * (1 - t) ** 0.75 + 1.2 for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], radial=(min(xs), min(ys), length * 1.1), noise=0.12, chroma=0.10)
    lower = s1 if n[0] > 0 else s2  # the side facing right is in shade
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (30, 0, 0), 0.32)
    other = s2 if lower is s1 else s1
    hl = [tuple(spine[k] * 0.45 + other[k] * 0.55) for k in range(2, 11)]
    ic.line(hl, max(3, int(width * 0.2)), (255, 222, 200, 190))
    ic.outline(pts, 3, (50, 10, 6, 150))
    ic.ellipse((top[0] - width * 0.36, top[1] - width * 0.28, top[0] + width * 0.36, top[1] + width * 0.22),
               "#4e6a26", "#1e2e0a", edge=2)
    ic.line([(top[0], top[1] - width * 0.2), (top[0] - width * 0.1, top[1] - width * 0.6)], 3, (60, 80, 30))
    if acc is not None:
        acc[0] = union(acc[0], m)


def ristra(ic: Icon, x: float, y0: float, y1: float, spread: float = 44, colors=(RED, CRIMSON, SCARLET, DRIED)) -> None:
    """String of chilies: a cord with pods tied round it, pointing down and out; back pods darker."""
    rnd = ic.random
    ic.line([(x, y0 - 10), (x + rnd.uniform(-4, 4), y1)], 5, (150, 120, 70))
    for layer in (0, 1):
        y = y0
        while y < y1 - 20:
            t = (y - y0) / (y1 - y0)
            w = spread * (0.75 + 0.25 * math.sin(math.pi * t)) * (1 - 0.35 * t * t)
            for side in (-1, 1):
                if layer == 0:
                    c = rnd.choice(colors)
                    dark = tuple(tuple(int(v * 0.62) for v in rgb(cc)) for cc in c)
                    pod(ic, (x + side * rnd.uniform(0, 6), y), 90 - side * rnd.uniform(25, 55), w * rnd.uniform(1.4, 1.8),
                        w * 0.44, dark, side * 0.1)
                else:
                    pod(ic, (x + side * rnd.uniform(0, 6), y + 8), 90 - side * rnd.uniform(5, 30),
                        w * rnd.uniform(1.3, 1.7), w * 0.46, rnd.choice(colors), -side * rnd.uniform(0, 0.2))
            y += 26 if layer == 0 else 30
        # the bottom tassel
    pod(ic, (x, y1 - 30), 90 + rnd.uniform(-8, 8), spread * 1.4, spread * 0.44, rnd.choice(colors))


def bush(ic: Icon, cx: float, base: float, h: float, hw: float, scale: float = 1.0, ripe: float = 0.7) -> Image.Image:
    """Chili plant: short branching stems, dark leaf mass, lanceolate leaves, pods hanging below them."""
    rnd = ic.random
    acc = [blank()]
    for dx in (-hw * 0.5, -hw * 0.1, hw * 0.3, hw * 0.55):
        ic.line([(cx + dx * 0.2, base), (cx + dx, base - h * 0.6)], 9, (70, 84, 40))
    body = ic.poly_mask(ic.jitter(cx, base - h * 0.5, hw * 0.82, h * 0.42, 18, 0.1))
    ic.fill(body, "#2e4e1c", "#0c1606", radial=(cx - hw * 0.5, base - h, h * 1.2), noise=0.3)
    acc[0] = union(acc[0], body)
    shadowed = tuple(tuple(int(v * 0.52) for v in rgb(c)) for c in LEAF)
    for _ in range(int(28 * scale + 8)):
        a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.5
        x, y = cx + math.cos(a) * hw * 0.7 * r, base - h * 0.52 + math.sin(a) * h * 0.38 * r
        ang = (0 if x > cx else 180) + (1 if x > cx else -1) * rnd.uniform(-30, 60)
        gleaf(ic, (x, y), ang, rnd.uniform(48, 66) * scale, rnd.uniform(20, 26) * scale, shadowed, 0.2, acc)
    spots = sorted(((rnd.uniform(-0.85, 0.85), rnd.uniform(0.08, 0.95)) for _ in range(int(36 * scale + 10))),
                   key=lambda s: -s[1])
    for u, t in spots:
        x = cx + u * hw * math.sqrt(max(0.1, 1 - (t - 0.5) ** 2 * 3))
        y = base - h * t
        if rnd.random() < 0.34 and t < 0.85:
            r = rnd.random()
            col = UNRIPE if r > ripe else rnd.choice((RED, RED, CRIMSON, CRIMSON, SCARLET))
            pod(ic, (x, y), 90 + rnd.uniform(-35, 35), rnd.uniform(78, 96) * scale, rnd.uniform(17, 20) * scale, col,
                rnd.uniform(-0.25, 0.25), acc)
        cols = LEAF_TOP if t > 0.55 else LEAF
        ang = (0 if u > 0 else 180) + (1 if u > 0 else -1) * rnd.uniform(-35, 45)
        gleaf(ic, (x, y), ang, rnd.uniform(52, 72) * scale, rnd.uniform(22, 28) * scale, cols, rnd.uniform(0.1, 0.3), acc)
    m = acc[0]
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx + hw * 0.1, 0, SIZE, SIZE))), (6, 12, 4), 0.25, blur=20)
    return m


def thatch(ic: Icon, ridge, eave, c=("#b8a06a", "#6c5632")) -> None:
    """Thatched roof plane seen from above: straw strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.26, 0.5, 0.75, 1.0]
    for k in reversed(range(len(courses) - 1)):
        f0, f1 = courses[k], courses[k + 1] + (0.05 if k < len(courses) - 2 else 0)
        n = 26
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
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 22) for x, y in low[::-1]])), (30, 20, 8), 0.45, blur=6)
        tint = rnd.uniform(0.92, 1.06)
        ic.fill(band, tuple(int(v * tint) for v in rgb(c[0])), tuple(int(v * tint) for v in rgb(c[1])), (y0 - 10, y1 + 30),
                noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, low=low):
            for _ in range(220):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 24 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 22)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 20, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 7, (150, 128, 84, 170))


def mat(ic: Icon, quad, c=("#b89c64", "#7c6038")) -> Image.Image:
    """Woven drying mat lying on the ground, seen from the raised camera; returns its mask."""
    rnd = ic.random
    pts = [tuple(p) for p in quad]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.24)

    def weave(dr):
        for k in range(-40, 60):
            x = k * 18
            dr.line([(x, 0), (x + 700, SIZE)], fill=(70, 50, 24, 70), width=3)
            dr.line([(x + 9, 0), (x + 709, SIZE)], fill=(236, 214, 160, 40), width=2)
        for y in range(0, SIZE, 14):
            dr.line([(0, y), (SIZE, y + rnd.uniform(-1, 1))], fill=(60, 42, 20, 55), width=2)

    ic.overlay(weave, m)
    return m


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.60
    ic.grade["mute"] = 0.82

    # ---- drying frame: dark back, posts, thatched top, strings of chilies
    L, R, BAR = 400, 990, 330
    ic.rect((L + 10, BAR, R - 10, 760), "#3a2a1c", "#1a120c", edge=0)
    for x in np.arange(L + 20, R - 10, 34):
        ic.line([(x + rnd.uniform(-3, 3), BAR + 10), (x, 760)], 4, (96, 74, 52, 70))
    ic.shade(ic.mask("rectangle", (L, BAR, R, BAR + 80)), alpha=0.45, blur=14)
    xs = np.linspace(L + 62, R - 62, 7)
    for i, x in enumerate(xs):
        ristra(ic, x + rnd.uniform(-4, 4), BAR + 26, BAR + 330 + rnd.uniform(-20, 30) - (30 if i % 2 else 0), 40)
    ic.beam((L - 10, BAR + 18), (R + 10, BAR + 18), 16, (104, 74, 48))
    for x in (L + 8, R - 8):
        ic.rect((x - 16, BAR - 10, x + 16, 790), "#9a7250", "#4e3622", vertical=False, edge=3)
    ridge = [(L + 60, 176), ((L + R) / 2, 170), (R - 60, 176)]
    ex = np.linspace(L - 44, R + 30, 16)
    thatch(ic, ridge, [(x, BAR + rnd.uniform(-5, 6)) for x in ex])
    ic.shade(ic.poly_mask([(760, 150), (1024, 150), (1024, 380), (780, 380)]), alpha=0.18, blur=50)

    # ---- ground strip
    top = [(20, 930)] + [(x, 898 + rnd.uniform(-10, 10)) for x in np.linspace(80, 960, 12)] + [(1008, 920)]
    ic.poly(top + [(1012, 992), (520, 1004), (16, 994)], "#78603e", "#4a3a26", noise=0.32, edge=3)
    ic.rect((L, 760, R, 905), "#4a3a28", "#5e4a30", noise=0.3, edge=0)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(920, 992)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.16, blur=2)

    # ---- drying mat of red pods, bottom right
    quad = [(560, 790), (960, 782), (1012, 940), (520, 952)]
    ic.shade(ic.poly_mask([(p[0] + 8, p[1] + 14) for p in quad]), alpha=0.5, blur=10, clip=False)
    m = mat(ic, quad)
    with ic.clipped(m):
        for _ in range(80):
            y = rnd.uniform(784, 944)
            x = rnd.uniform(540 + (y - 790) * -0.25, 1000 + (y - 790) * 0.3)
            pod(ic, (x, y), rnd.uniform(0, 360), rnd.uniform(58, 74), 18, rnd.choice((RED, CRIMSON, DRIED, SCARLET)),
                rnd.uniform(-0.2, 0.2))
    ic.line([p for p in quad] + [quad[0]], 10, (118, 88, 52))

    # ---- rows of chili bushes, left
    bush(ic, 320, 900, 380, 130, 0.9, 0.6)
    bush(ic, 110, 912, 420, 125, 0.95, 0.65)
    bush(ic, 470, 992, 330, 135, 1.0, 0.8)
    bush(ic, 220, 1000, 360, 150, 1.05, 0.75)
    ic.shade(ic.mask("rectangle", (0, 930, 700, 1024)), (10, 16, 4), 0.3, blur=20)

    # ---- basket of picked chilies, bottom right corner
    ic.shade(ic.mask("ellipse", (842, 970, 1020, 1004)), alpha=0.5, blur=8, clip=False)
    ic.fill(ic.mask("ellipse", (858, 860, 1004, 904)), "#2a1a10", "#180e08")
    for _ in range(18):
        x = rnd.uniform(868, 994)
        pod(ic, (x, rnd.uniform(862, 890)), rnd.uniform(0, 360), rnd.uniform(46, 58), 15,
            rnd.choice((RED, RED, SCARLET, CRIMSON)), rnd.uniform(-0.2, 0.2))
    ic.basket(856, 884, 1006, 996)
