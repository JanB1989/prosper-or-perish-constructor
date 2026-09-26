"""Pepper Garden: pepper vines climbing rough poles, hung with red and green spikes; peppercorns drying.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pepper_garden/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pepper_garden

Identity: tall columns of dark glossy vine leaves wrapped round crooked poles, hung with long red and
green pepper spikes; a woven mat of black peppercorns in front and a basket of fresh spikes at the
bottom right. No building: tier 0 of the pepper chain (Managed Pepper Garden adds the store).

Local helpers: ``gleaf`` (glossy leaf, from coffee_grove), ``berries`` (small shaded berries in one
layer, from coffee_grove ``cherries``), ``spike`` (hanging pepper catkin), ``vine`` (pole wrapped in a
leafy vine column with spikes), ``mat`` (woven drying mat in perspective), ``scatter`` (grains on a
surface, from coffee_grove).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("fruit_orchard", "fiber_crops_farm", "farming_village", "tobacco_plantation")

LEAF = ("#5a8a38", "#18300e")
LEAF_TOP = ("#6c9c46", "#223a14")

RED = ((164, 36, 26), (212, 76, 50), (78, 14, 10))
DEEP = ((128, 24, 22), (176, 52, 44), (60, 10, 10))
ORANGE = ((190, 104, 36), (226, 156, 76), (104, 52, 18))
GREEN = ((104, 136, 48), (156, 182, 90), (50, 70, 20))
BLACK = ((46, 38, 32), (78, 66, 56), (16, 12, 10))
BROWN = ((84, 52, 34), (126, 88, 62), (36, 22, 14))


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
    ts = np.linspace(0, 1, 20)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    # heart-shaped: broad near the stalk, drawn to a point
    hw = [width / 2 * math.sin(math.pi * t ** 0.62) * (1 + 0.06 * math.sin(11 * t)) for t in ts]
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
    ic.shade(ic.poly_mask(gloss), (226, 240, 206), 0.28, blur=2)
    ic.line([tuple(p) for p in spine[1:-4]], 3, (150, 176, 110, 90))
    ic.outline(pts, 3, (16, 26, 8, 80))
    if acc is not None:
        acc[0] = union(acc[0], m)


def berries(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Round shaded berries (x, y, r, palette) in one blended layer: dark rim, body, lit side, glint."""

    def paint(dr):
        for x, y, r, (mid, lit, dk) in items:
            dr.ellipse((x - r, y - r, x + r, y + r), fill=dk + (255,))
            dr.ellipse((x - r + 1.5, y - r + 1, x + r - 2.5, y + r - 3), fill=mid + (255,))
            dr.ellipse((x - r * 0.72, y - r * 0.78, x + r * 0.12, y + r * 0.02), fill=lit + (235,))
            g = max(r * 0.22, 1.6)
            gx, gy = x - r * 0.42, y - r * 0.46
            dr.ellipse((gx - g, gy - g, gx + g, gy + g), fill=(252, 226, 206, 200))

    ic.overlay(paint, clip)


def spike(ic: Icon, top, length: float, pal, r: float = 9.5, sway: float = 0.0) -> None:
    """Hanging pepper spike: a thin stalk and a tapering chain of berries, swaying slightly."""
    x0, y0 = top
    ic.line([(x0, y0 - 6), (x0 + sway * 0.1, y0 + 10)], 4, (60, 70, 30))
    items = []
    n = max(5, int(length / (r * 0.62)))
    for k in range(n):
        t = k / (n - 1)
        rr = r * (1.0 - 0.3 * t) * ic.random.uniform(0.9, 1.08)
        x = x0 + sway * t * t + ic.random.uniform(-2, 2) + (r * 0.55 if k % 2 else -r * 0.55) * (1 - t * 0.4)
        items.append((x, y0 + 8 + length * t, rr, pal))
    berries(ic, items)


def vine(ic: Icon, x: float, base: float, top: float, rx: float, scale: float = 1.0, lean: float = 0.0,
         ripe: float = 0.6, spikes: float = 1.0) -> Image.Image:
    """A crooked pole wrapped in a pepper vine: dark inner mass, glossy leaves, hanging spikes."""
    rnd = ic.random
    acc = [blank()]
    # the pole: crooked, tapering, visible above the vine
    ys = np.linspace(base, top - 60 * scale, 9)
    cx = [x + lean * (base - y) / (base - top) + rnd.uniform(-5, 5) for y in ys]
    w = [15 * scale * (1 - 0.35 * i / 8) for i in range(9)]
    pole = [(c - ww, y) for c, ww, y in zip(cx, w, ys)] + [(c + ww, y) for c, ww, y in zip(cx[::-1], w[::-1], ys[::-1])]
    ic.poly(pole, "#9a7a58", "#4a3624", span=(x - 16, x + 16), vertical=False, noise=0.26, edge=3)

    def px(y):
        return float(np.interp(y, ys[::-1], cx[::-1]))

    def prof(y):
        t = (base - y) / (base - top)
        if t > 0.84:  # rounded crown
            return rx * 0.9 * math.sqrt(max(0.05, 1 - ((t - 0.84) / 0.16) ** 2))
        return rx * (0.78 + 0.12 * math.sin(math.pi * t) + 0.06 * math.sin(9 * t + x))

    # dark inner mass
    body = []
    for y in np.linspace(base - 20, top, 14):
        body.append((px(y) - prof(y) * 0.72 + rnd.uniform(-8, 8), y))
    for y in np.linspace(top, base - 20, 14):
        body.append((px(y) + prof(y) * 0.72 + rnd.uniform(-8, 8), y))
    bm = ic.poly_mask(body)
    ic.fill(bm, "#2a4a1a", "#0a1406", radial=(x - rx, top, (base - top) * 0.9), noise=0.3)
    acc[0] = union(acc[0], bm)
    shadowed = tuple(tuple(int(v * 0.52) for v in rgb(c)) for c in LEAF)
    span = base - top
    for _ in range(int(span / 20)):  # leaves deep in the vine, in shadow
        y = rnd.uniform(top + 20, base - 30)
        side = rnd.choice((-1, 1))
        ang = (0 if side > 0 else 180) + side * rnd.uniform(-20, 70)
        gleaf(ic, (px(y) + side * rnd.uniform(0, prof(y) * 0.45), y), ang, rnd.uniform(70, 92) * scale,
              rnd.uniform(46, 58) * scale, shadowed, 0.2, acc)

    def lit_leaf(y):
        t = (base - y) / span
        cols = tuple(tuple(int(min(255, v * rnd.uniform(0.82, 1.08))) for v in rgb(c))
                     for c in (LEAF_TOP if t > 0.6 else LEAF))
        side = rnd.choice((-1, 1))
        bx = px(y) + side * prof(y) * rnd.uniform(0.1, 0.55)
        ang = (0 if side > 0 else 180) + side * rnd.uniform(-25, 65)
        gleaf(ic, (bx, y), ang, rnd.uniform(74, 98) * scale, rnd.uniform(48, 62) * scale, cols,
              rnd.uniform(0.1, 0.3), acc)

    for y in sorted(rnd.uniform(top, base - 50) for _ in range(int(span / 13))):
        lit_leaf(y)
    # spikes hang over the leaves, a few leaves overlap them again
    for y in sorted(rnd.uniform(top + 60, base - 190) for _ in range(int(span / 55 * spikes))):
        side = rnd.choice((-1, 1))
        pal = RED if rnd.random() < ripe else (GREEN if rnd.random() < 0.6 else ORANGE)
        if rnd.random() < 0.2:
            pal = DEEP
        thin = 0.75 if (base - y) / span > 0.5 else 1.0  # slimmer spikes on the upper half
        spike(ic, (px(y) + side * prof(y) * rnd.uniform(0.15, 0.8), y), rnd.uniform(84, 118) * scale, pal,
              12 * scale * thin, sway=side * rnd.uniform(0, 12))
        if rnd.random() < 0.5:
            lit_leaf(y + rnd.uniform(40, 120))
    # tendril at the top of the pole
    tx = px(top)
    ic.line([(tx, top + 10), (tx + 20 * scale, top - 30 * scale), (tx + 6 * scale, top - 52 * scale)], 4, (70, 96, 40))
    gleaf(ic, (tx, top - 4), -70 + rnd.uniform(-15, 15), 56 * scale, 36 * scale, LEAF_TOP, 0.05, acc)
    # shadow side of the column
    m = acc[0]
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x + rx * 0.1, 0, SIZE, SIZE))), (6, 12, 4), 0.28, blur=24)
    tip = stake(ic, px(top) + 4, top + 40, top - 92 * scale, 10 * scale)
    return m, tip


def stake(ic: Icon, x: float, y0: float, y1: float, w: float) -> tuple[float, float]:
    """Weathered grey-brown pole top standing out of the vine: lit left edge, grain streaks, slanted cut."""
    rnd = ic.random
    ys = np.linspace(y0, y1, 6)
    cx = [x + rnd.uniform(-2, 2) + (y0 - y) * 0.04 for y in ys]
    ww = [w * (1 - 0.25 * i / 5) for i in range(6)]
    left = [(c - k, y) for c, k, y in zip(cx, ww, ys)]
    right = [(c + k, y) for c, k, y in zip(cx, ww, ys)]
    right[-1] = (right[-1][0], right[-1][1] + 8)  # slanted cut
    pts = left + right[::-1]
    ic.fill(ic.poly_mask(pts), "#a09684", "#463e34", span=(x - w, x + w), vertical=False, noise=0.3)
    ic.line([(cx[0] - w * 0.2, y0), (cx[-1] - w * 0.1, y1 + 12)], 2, (40, 34, 28, 120))
    ic.line([(cx[0] + w * 0.4, y0), (cx[-1] + w * 0.3, y1 + 16)], 2, (40, 34, 28, 90))
    ic.shade(ic.poly_mask([left[-1], right[-1], (right[-1][0], right[-1][1] + 5), (left[-1][0], left[-1][1] + 5)]),
             (230, 220, 200), 0.35)
    ic.outline(pts, 3, (36, 28, 20, 200))
    return cx[-1], y1 + 14


def scatter(ic: Icon, clip: Image.Image, y0: float, y1: float, x0: float, x1: float, step: float,
            size: float, palettes) -> None:
    """Round grains spread over a surface in perspective (smaller towards the back)."""
    rnd = ic.random
    items = []
    y = y0 + 3
    while y < y1:
        s = 0.78 + 0.22 * (y - y0) / (y1 - y0)
        x = x0 + rnd.uniform(0, step)
        while x < x1:
            items.append((x + rnd.uniform(-3, 3), y + rnd.uniform(-2, 2), size * s * rnd.uniform(0.8, 1.1),
                          rnd.choice(palettes)))
            x += step * s * rnd.uniform(0.8, 1.15)
        y += step * 0.62 * s
    berries(ic, items, clip)


def mat(ic: Icon, quad, c=("#b89c64", "#7c6038")) -> Image.Image:
    """Woven drying mat lying on the ground, seen from the raised camera; returns its mask."""
    rnd = ic.random
    pts = [tuple(p) for p in quad]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.24)

    def weave(dr):
        # twill of palm strips: short lit/dark dashes alternating in a checker, strips running diagonally
        for k in range(-60, 80):
            for j in range(0, 60):
                x, y = k * 20 + j * 12, j * 20
                if (k + j) % 2:
                    dr.line([(x, y), (x + 12, y + 20)], fill=(226, 200, 146, 70), width=6)
                else:
                    dr.line([(x + 4, y), (x - 8, y + 20)], fill=(58, 40, 18, 90), width=5)
        for y in range(0, SIZE, 20):
            dr.line([(0, y), (SIZE, y + rnd.uniform(-1, 1))], fill=(50, 34, 16, 70), width=2)

    ic.overlay(weave, m)
    return m


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.58
    ic.grade["mute"] = 0.84

    # ---- ground strip under the garden
    top = [(24, 930)] + [(x, 900 + rnd.uniform(-10, 10)) for x in np.linspace(80, 960, 12)] + [(1006, 928)]
    ic.poly(top + [(1010, 990), (520, 1000), (18, 992)], "#76603e", "#4a3a26", noise=0.32, edge=3)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(918, 990)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.16, blur=2)

    # ---- vines on poles, back ones first; a sagging tie rope between the pole tops
    _, t3 = vine(ic, 700, 870, 300, 96, 0.9, lean=-10, ripe=0.5)
    _, t1 = vine(ic, 150, 982, 150, 116, 1.0, lean=8, ripe=0.65)
    _, t2 = vine(ic, 432, 996, 200, 110, 1.0, lean=-6, ripe=0.6)
    # dark tie rope sagging between the three pole tops, a lit strand along its top
    for a, b, sag in ((t1, t2, 34), (t2, t3, 30)):
        ts = np.linspace(0, 1, 16)
        pts = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t + sag * 4 * t * (1 - t)) for t in ts]
        ic.line(pts, 12, (44, 30, 20))
        ic.line([(x, y - 3) for x, y in pts[2:-2]], 3, (150, 118, 80, 150))
        for p in (a, b):  # lashing knot
            ic.fill(ic.mask("ellipse", (p[0] - 11, p[1] - 8, p[0] + 11, p[1] + 8)), "#5a4430", "#2a1e14")
    ic.shade(ic.mask("rectangle", (0, 900, SIZE, 1024)), (10, 16, 4), 0.35, blur=22)

    # ---- drying mat of black peppercorns, bottom right (smaller, woven, a dark front lip)
    quad = [(575, 824), (959, 815), (1010, 950), (534, 962)]
    ic.shade(ic.poly_mask([(p[0] + 10, p[1] + 18) for p in quad]), alpha=0.6, blur=10, clip=False)
    m = mat(ic, quad, ("#a88a58", "#6a5030"))
    # cast shadow of the mound on the mat, towards the lower right
    ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(740, 918, 150, 34, 18, 0.06))), (20, 12, 6), 0.55, blur=10)
    # raised mound of black pepper: dome over an elliptic footprint
    mcx, mby, mrx, mh = 712, 916, 136, 96
    dome = [(mcx + math.cos(t) * mrx, mby - math.sin(t) * mh * (0.55 + 0.45 * math.sin(t)) ** 0.8)
            for t in np.linspace(math.pi, 0, 30)]
    foot = [(mcx + math.cos(t) * mrx, mby + math.sin(t) * 22) for t in np.linspace(0, math.pi, 16)]
    pts = [(x + rnd.uniform(-3, 3), y + rnd.uniform(-2, 2)) for x, y in dome + foot]
    heap = ic.poly_mask(pts)
    ic.fill(heap, "#4a2e1a", "#0e0906", radial=(mcx - mrx * 0.4, mby - mh * 0.85, mrx * 1.4), noise=0.3, chroma=0.16)
    PC = ((30, 21, 15), (60, 40, 26), (8, 5, 3))
    PW = ((66, 38, 20), (100, 62, 34), (24, 13, 6))
    scatter(ic, heap, mby - mh - 4, mby + 22, mcx - mrx - 10, mcx + mrx + 10, 13, 7.5, (PC, PC, PC, PW))
    ic.shade(ic.intersect(heap, ic.mask("ellipse", (mcx - 20, mby - mh * 0.6, mcx + mrx * 1.6, mby + 80))),
             (8, 5, 3), 0.62, blur=20)
    ic.shade(ic.intersect(heap, ic.mask("ellipse", (mcx - mrx * 0.85, mby - mh - 10, mcx + 20, mby - 30))),
             (255, 214, 170), 0.22, blur=16)

    def glints(dr):
        for _ in range(34):
            a = rnd.uniform(math.pi * 0.4, math.pi * 0.95)
            rr = rnd.uniform(0.25, 0.85)
            gx, gy = mcx + math.cos(a) * mrx * rr, mby - math.sin(a) * mh * rr - 4
            dr.ellipse((gx - 2.5, gy - 2.5, gx + 2.5, gy + 2.5), fill=(248, 232, 210, 210))

    ic.overlay(glints, heap)
    ic.outline(dome, 3, (20, 14, 10, 160))
    spread = ImageChops.subtract(ic.intersect(m, ic.poly_mask([(850, 800), (980, 800), (1010, 950), (860, 950)])),
                                 heap)
    scatter(ic, spread, 820, 950, 850, 1004, 22, 7, (GREEN, PC, PW, RED))
    # woven edge binding: lit back edge, dark thick front lip with contact shadow
    ic.line([quad[0], quad[1]], 8, (184, 156, 104))
    ic.line([quad[1], quad[2]], 8, (110, 82, 50))
    ic.line([quad[3], quad[0]], 8, (132, 102, 64))
    lip = [quad[3], quad[2], (quad[2][0] + 2, quad[2][1] + 18), (quad[3][0] - 2, quad[3][1] + 18)]
    ic.fill(ic.poly_mask(lip), "#5e4426", "#2e2012", (quad[3][1], quad[3][1] + 18), noise=0.3)
    ic.outline(lip, 3, (30, 20, 10, 200))

    # ---- basket of fresh spikes, bottom right corner
    ic.shade(ic.mask("ellipse", (850, 970, 1020, 1004)), alpha=0.5, blur=8, clip=False)
    ic.fill(ic.mask("ellipse", (864, 858, 1004, 900)), "#2a1a10", "#180e08")
    for k in range(9):
        a = rnd.uniform(-60, 60)
        x = 880 + k * 14 + rnd.uniform(-4, 4)
        pal = (RED, RED, DEEP, GREEN)[k % 4]
        items = []
        for j in range(6):
            items.append((x + j * 9 * math.sin(math.radians(a)), 882 - j * 9 * math.cos(math.radians(a)) * 0.5
                          + rnd.uniform(-2, 2), 9 - j * 0.5, pal))
        berries(ic, items)
    ic.basket(862, 882, 1006, 994)

    # ---- warm light from the upper left over the tops, a little shade low right
    ic.shade(ic.mask("ellipse", (-100, 60, 560, 520)), (255, 240, 200), 0.10, blur=60)
