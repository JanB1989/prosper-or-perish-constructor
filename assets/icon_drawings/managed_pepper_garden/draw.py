"""Managed Pepper Garden: an orderly row of pepper vines on living support trees, a tiled store, drying racks.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/managed_pepper_garden/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/managed_pepper_garden

Identity: tier 1 of the pepper chain. The same leafy vine columns with red and green spikes as the
Pepper Garden, now trained evenly on pruned living support trees, with a timber store under a tiled
roof (sacks at the door) and a raised bamboo rack of black peppercorns in front.

Local helpers: ``gleaf``, ``berries``, ``spike``, ``vine``, ``scatter``, ``mat`` as in pepper_garden;
``crown`` (small pruned tree crown), ``planks`` (board wall), ``jute`` (sack, from coffee_grove).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 43
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
        spike(ic, (px(y) + side * prof(y) * rnd.uniform(0.15, 0.8), y), rnd.uniform(84, 118) * scale, pal,
              12 * scale, sway=side * rnd.uniform(0, 12))
        if rnd.random() < 0.5:
            lit_leaf(y + rnd.uniform(40, 120))
    # tendril at the top of the pole
    tx = px(top)
    ic.line([(tx, top + 10), (tx + 20 * scale, top - 30 * scale), (tx + 6 * scale, top - 52 * scale)], 4, (70, 96, 40))
    gleaf(ic, (tx, top - 4), -70 + rnd.uniform(-15, 15), 56 * scale, 36 * scale, LEAF_TOP, 0.05, acc)
    # shadow side of the column
    m = acc[0]
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x + rx * 0.1, 0, SIZE, SIZE))), (6, 12, 4), 0.28, blur=24)
    return m


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
        for k in range(-40, 60):
            x = k * 18
            dr.line([(x, 0), (x + 700, SIZE)], fill=(70, 50, 24, 70), width=3)
            dr.line([(x + 9, 0), (x + 709, SIZE)], fill=(236, 214, 160, 40), width=2)
        for y in range(0, SIZE, 14):
            dr.line([(0, y), (SIZE, y + rnd.uniform(-1, 1))], fill=(60, 42, 20, 55), width=2)

    ic.overlay(weave, m)
    return m


def crown(ic: Icon, cx: float, cy: float, rx: float, ry: float, trunk_top: float) -> Image.Image:
    """Pollarded crown of a living support tree (Gliricidia/Erythrina): a bare trunk rising out of
    the vine, a few pruned branches fanning out, and a flat umbrella of loose leaf clusters with gaps,
    pale on top and shadowed underneath."""
    rnd = ic.random
    m = blank()
    # bare trunk above the vine and the pruned branches (seen through the gaps)
    tb = cy + ry * 0.35
    ic.poly([(cx - 13, trunk_top), (cx - 10, tb), (cx + 9, tb), (cx + 13, trunk_top)], "#9a8a74", "#4a3c30",
            span=(cx - 13, cx + 13), vertical=False, noise=0.3, edge=3)
    for dx in (-0.78, -0.42, 0.05, 0.46, 0.8):
        ex, ey = cx + dx * rx * 0.9, cy - ry * 0.2 + abs(dx) * ry * 0.4
        ic.line([(cx, tb + 4), ((cx + ex) / 2, (tb + ey) / 2 - 8), (ex, ey)], 9, (40, 30, 22))
        ic.line([(cx, tb + 2), ((cx + ex) / 2, (tb + ey) / 2 - 10), (ex, ey - 2)], 4, (130, 112, 90))
    # clusters along a flat dome, back row first, with gaps between them
    clusters = []
    for k in range(9):
        t = (k + rnd.uniform(-0.25, 0.25)) / 8
        x = cx - rx + 2 * rx * t
        y = cy - ry * 0.75 * math.sin(math.pi * t) + rnd.uniform(-6, 6)
        clusters.append((x, y + (8 if k % 2 else -8), rnd.uniform(0.34, 0.46) * rx * (0.7 + 0.3 * math.sin(math.pi * t))))
    clusters.sort(key=lambda c: c[1])
    for bx, by, br in clusters:
        bm = ic.poly_mask(ic.jitter(bx, by, br, br * 0.66, 16, 0.2))
        ic.fill(bm, "#98ae5c", "#243e16", (by - br * 0.66, by + br * 0.66), noise=0.3, chroma=0.14)
        ic.shade(ic.intersect(bm, ic.mask("ellipse", (bx - br * 1.2, by, bx + br * 1.2, by + br))), (8, 16, 4),
                 0.45, blur=4)
        m = union(m, bm)

    def dabs(dr):
        for _ in range(240):
            x, y = rnd.uniform(cx - rx * 1.2, cx + rx * 1.2), rnd.uniform(cy - ry * 1.1, cy + ry * 0.8)
            r = rnd.uniform(3, 6)
            col = (184, 200, 120, 90) if rnd.random() < 0.55 - 0.5 * (y - cy) / ry else (20, 32, 10, 90)
            dr.ellipse((x - r, y - r * 0.5, x + r, y + r * 0.5), fill=col)

    ic.overlay(dabs, m)
    return m


def planks(ic: Icon, box, c=("#8a6444", "#4c3420"), step: float = 34) -> None:
    """Vertical board wall: boards with their own tone, dark gaps, grain streaks."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    x = x0
    while x < x1:
        w = min(step * rnd.uniform(0.85, 1.15), x1 - x)
        t = rnd.uniform(0.76, 1.16)
        ic.fill(ic.mask("rectangle", (x, y0, x + w, y1)), tuple(int(min(255, v * t)) for v in rgb(c[0])),
                tuple(int(v * t) for v in rgb(c[1])), (y0, y1), noise=0.22)
        ic.line([(x, y0), (x, y1)], 3, (40, 26, 14, 160))
        for _ in range(2):
            gx = x + rnd.uniform(5, w - 5) if w > 10 else x
            ic.line([(gx, y0 + rnd.uniform(0, 30)), (gx + rnd.uniform(-2, 2), y1 - rnd.uniform(0, 30))], 2,
                    (50, 34, 18, 70))
        x += w


def jute(ic: Icon, cx: float, base: float, w: float, h: float, color, lean: float = 0.0) -> None:
    """Upright jute sack: slumped belly wider at the bottom, gathered neck tied with cord and a flared
    tuft, hessian cross-weave, lit from the upper left with a core shadow on the right."""
    rnd = ic.random
    L = lean * w
    body = [(cx - w * 0.5, base), (cx - w * 0.58, base - h * 0.2), (cx - w * 0.52, base - h * 0.5),
            (cx - w * 0.36 + L * 0.5, base - h * 0.72), (cx - w * 0.13 + L, base - h * 0.84),
            (cx + w * 0.13 + L, base - h * 0.84), (cx + w * 0.38 + L * 0.5, base - h * 0.7),
            (cx + w * 0.54, base - h * 0.46), (cx + w * 0.6, base - h * 0.18), (cx + w * 0.52, base)]
    body = [(x + rnd.uniform(-2, 2), y + rnd.uniform(-2, 2)) for x, y in body]
    bm = ic.poly_mask(body)
    dark = tuple(int(v * 0.4) for v in rgb(color))
    ic.fill(bm, color, dark, radial=(cx - w * 0.3 + L, base - h * 0.75, w * 1.15), noise=0.3, chroma=0.12)
    ic.shade(ic.intersect(bm, ic.mask("ellipse", (cx + w * 0.1, base - h * 0.7, cx + w * 0.9, base + h * 0.2))),
             (20, 12, 6), 0.5, blur=10)

    def weave(dr):  # hessian: fine cross-weave
        for y in np.arange(base - h, base, 6):
            dr.line([(cx - w, y), (cx + w, y + 2)], fill=(44, 30, 16, 60), width=2)
        for x in np.arange(cx - w, cx + w, 7):
            dr.line([(x, base - h), (x + 2, base)], fill=(210, 180, 130, 36), width=2)

    ic.overlay(weave, bm)
    # gathered folds running down from the neck
    for f in (-0.28, -0.08, 0.12, 0.3):
        ic.line([(cx + L + f * w * 0.4, base - h * 0.82), (cx + f * w * 0.9 + L * 0.4, base - h * 0.62),
                 (cx + f * w * 1.1, base - h * 0.5)], 3, (36, 24, 12, 130))
    ic.outline(body, 3, (36, 24, 12, 170))
    # flared tuft above the tie
    tx = cx + L
    tuft = [(tx - 10, base - h * 0.84), (tx - w * 0.2, base - h * 0.98), (tx - w * 0.06, base - h * 0.94),
            (tx + w * 0.02, base - h * 1.02), (tx + w * 0.12, base - h * 0.95), (tx + w * 0.2, base - h * 0.99),
            (tx + 10, base - h * 0.84)]
    ic.poly(tuft, tuple(int(min(255, v * 1.08)) for v in rgb(color)), dark, edge=3)
    ic.line([(tx - 14, base - h * 0.85), (tx + 14, base - h * 0.85)], 7, (48, 34, 20))
    ic.line([(tx + 10, base - h * 0.85), (tx + 18, base - h * 0.74)], 4, (60, 42, 24))
    ic.shade(ic.mask("ellipse", (cx - w * 0.6, base - 10, cx + w * 0.75, base + 12)), alpha=0.5, blur=6)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.60
    ic.grade["mute"] = 0.84

    # ---- the store: board walls, dark doorway with sacks, tiled roof
    SL, SR, EAVE, BASE = 640, 968, 500, 800
    ic.poly([(SL + 10, EAVE - 10), (SR - 10, EAVE - 10), (SR - 10, 330), (SL + 10, 330)], "#6a4c32", "#3a2a1c", edge=0)
    planks(ic, (SL, EAVE, SR, BASE))
    # grime and damp towards the foot of the boards
    ic.shade(ic.mask("rectangle", (SL, BASE - 90, SR, BASE)), (26, 18, 10), 0.45, blur=18)
    DL, DR = SL + 124, SL + 268
    ic.rect((DL, EAVE + 60, DR, BASE), "#1a120c", "#080504", edge=4)
    ic.shade(ic.mask("rectangle", (DL, EAVE + 60, DR, EAVE + 130)), alpha=0.6, blur=10)
    # sacks inside the doorway, one outside against the wall
    jute(ic, DL + 88, BASE - 2, 78, 124, "#6c4a28", lean=0.05)
    jute(ic, DL + 44, BASE + 2, 84, 138, "#7a5430", lean=-0.04)
    jute(ic, DR - 30, BASE + 6, 70, 102, "#5e4024", lean=0.08)
    ic.beam((DL - 4, EAVE + 56), (DR + 4, EAVE + 56), 14, (104, 74, 48))
    jute(ic, SL + 62, BASE + 6, 84, 128, "#7a5430", lean=-0.06)
    ic.window(SR - 90, EAVE + 80, SR - 40, EAVE + 136)
    for x in (SL + 8, SR - 8):
        ic.beam((x, EAVE), (x, BASE), 22)
    ic.shade(ic.mask("rectangle", (SL, EAVE, SR, EAVE + 80)), (20, 12, 6), 0.62, blur=14)
    roof = [(SL - 40, EAVE + 14), (SR + 40, EAVE + 14), (SR - 30, 334), (SL + 30, 334)]
    ic.tiles(roof, "#b0704c", "#6a3a24", course=30, stagger=40)
    rm = ic.poly_mask(roof)

    def tile_tone(dr):
        for i, y in enumerate(np.arange(334, EAVE + 14, 30)):
            for x in np.arange(SL - 60 + (0 if i % 2 else 20), SR + 60, 40):
                t = rnd.random()
                col = (236, 180, 140, int(30 + 40 * t)) if t < 0.5 else (40, 18, 10, int(20 + 50 * (t - 0.5)))
                dr.rectangle((x + 2, y + 2, x + 38, y + 27), fill=col)
            dr.line([(SL - 60, y + 3), (SR + 60, y + 3 + rnd.uniform(-2, 2))], fill=(238, 196, 156, 90), width=4)

    ic.overlay(tile_tone, rm)
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (0, EAVE - 30, SIZE, EAVE + 20))), (30, 14, 6), 0.3, blur=10)
    ic.rect((SL + 20, 320, SR - 22, 340), "#8a5a3c", "#5a3622")
    ic.shade(ic.poly_mask([(800, 300), (1024, 300), (1024, 530), (820, 530)]), alpha=0.22, blur=50)

    # ---- ground strip
    top = [(24, 930)] + [(x, 900 + rnd.uniform(-10, 10)) for x in np.linspace(80, 960, 12)] + [(1006, 924)]
    ic.poly(top + [(1010, 990), (520, 1000), (18, 992)], "#76603e", "#4a3a26", noise=0.32, edge=3)
    ic.rect((SL - 20, BASE, SR + 10, 905), "#5a4830", "#6a5436", noise=0.3, edge=0)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(918, 990)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.16, blur=2)

    # ---- living support trees in an even row, each wrapped in a vine and topped by a pruned crown
    for x, b, t in ((510, 900, 260), (310, 950, 230), (110, 986, 210)):
        # bare lower trunk of the support tree below the vine
        ic.poly([(x - 20, b), (x - 14, b - 120), (x + 14, b - 120), (x + 22, b)], "#8e7862", "#3a2c22",
                span=(x - 22, x + 22), vertical=False, noise=0.26, edge=3)
        vine(ic, x, b - 70, t, 60, 0.82, lean=0, ripe=0.62, spikes=1.2)
        crown(ic, x, t - 104, 90, 46, t - 20)
    ic.shade(ic.mask("rectangle", (0, 910, 560, 1024)), (10, 16, 4), 0.35, blur=22)

    # ---- raised bamboo drying rack in front of the store
    TOP, FRONT = 800, 872
    for x in (560, 780, 1000):
        ic.rect((x - 11, FRONT, x + 11, 966 + rnd.uniform(-4, 4)), "#b0985c", "#6a5a30", vertical=False, edge=3)
    ic.shade(ic.mask("ellipse", (520, 950, 1020, 990)), alpha=0.4, blur=10, clip=False)
    quad = [(578, TOP), (992, TOP), (1014, FRONT), (548, FRONT)]
    m = mat(ic, quad, ("#c4aa6c", "#8a6e40"))
    heap = ic.intersect(m, ic.mask("rectangle", (0, 0, 850, SIZE)))
    scatter(ic, heap, TOP, FRONT, 560, 860, 13, 8, (BLACK, BLACK, BLACK, BROWN))
    rest = ic.intersect(m, ic.mask("rectangle", (850, 0, SIZE, SIZE)))
    scatter(ic, rest, TOP, FRONT, 840, 1010, 14, 8, (GREEN, GREEN, RED, BROWN))
    ic.line([(850, TOP), (846, FRONT)], 8, (150, 128, 76))
    # bamboo front pole with nodes
    ic.rect((540, FRONT, 1020, FRONT + 22), "#bca468", "#7a6634", edge=4)
    for x in np.arange(580, 1010, 70):
        ic.line([(x, FRONT), (x, FRONT + 22)], 5, (90, 74, 36))
    ic.line([(578, TOP), (992, TOP)], 10, (150, 128, 76))
