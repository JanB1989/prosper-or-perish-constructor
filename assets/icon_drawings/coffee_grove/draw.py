"""Coffee Grove: glossy coffee shrubs hung with red cherries under a shade tree, a raised drying bed.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/coffee_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/coffee_grove

Identity: clusters of red cherries on dark glossy coffee shrubs (left) against a raised wooden
drying bed of pale parchment beans and drying red cherries (right), with a small thatched shed
behind the bed and a feathery shade tree over the whole grove; a basket of picked cherries at the
bottom right.

Local helpers: ``gleaf`` (glossy leaf, tone-shaded, gloss sliver, no vein outlines), ``cherries``
(many small shaded berries in one blended layer), ``shrub`` (tiered coffee shrub with nodes of
leaves and cherry clusters), ``canopy`` (blob canopy with leaf dabs and a shaded underside),
``thatch`` (straw roof plane with stroke texture and a cut eave), ``scatter`` (small grains on a
surface in perspective).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 23
REFS = ("fruit_orchard", "fiber_crops_farm", "sugar_plantation", "farming_village")

LEAF = ("#4f7a34", "#14240b")
LEAF_TOP = ("#5c8a3c", "#1a2e10")
TIMBER = (112, 80, 52)

RIPE = ((168, 34, 24), (214, 70, 46), (84, 14, 10))
DEEP = ((128, 20, 22), (176, 48, 44), (64, 10, 12))
DRY = ((104, 34, 20), (146, 62, 38), (52, 18, 10))
UNRIPE = ((196, 120, 40), (228, 170, 80), (110, 60, 20))
GREEN = ((122, 150, 56), (170, 190, 96), (60, 80, 24))


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def gleaf(ic: Icon, base, deg: float, length: float, width: float, colors=LEAF, droop: float = 0.15,
          acc: list | None = None) -> None:
    """Glossy pointed coffee leaf: lit/shadow halves by tone, a pale gloss sliver, faint midrib."""
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
    lower, upper, nu = (s1, s2, -n) if n[1] > 0 else (s2, s1, n)
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (6, 14, 4), 0.30)
    gloss = [tuple(spine[k] + nu * hw[k] * 0.22) for k in range(3, 13)]
    gloss += [tuple(spine[k] + nu * hw[k] * 0.72) for k in range(12, 2, -1)]
    ic.shade(ic.poly_mask(gloss), (226, 240, 206), 0.30, blur=2)
    ic.line([tuple(p) for p in spine[1:-4]], 3, (150, 176, 110, 90))
    ic.outline(pts, 3, (16, 26, 8, 120))
    if acc is not None:
        acc[0] = union(acc[0], m)


def cherries(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Round shaded berries (x, y, r, palette) in one blended layer: dark rim, body, lit side, glint."""

    def paint(dr):
        for x, y, r, (mid, lit, dk) in items:
            dr.ellipse((x - r, y - r, x + r, y + r), fill=dk + (255,))
            dr.ellipse((x - r + 1.5, y - r + 1, x + r - 2.5, y + r - 3), fill=mid + (255,))
            dr.ellipse((x - r * 0.72, y - r * 0.78, x + r * 0.12, y + r * 0.02), fill=lit + (235,))
            g = max(r * 0.22, 1.6)
            gx, gy = x - r * 0.42, y - r * 0.46
            dr.ellipse((gx - g, gy - g, gx + g, gy + g), fill=(252, 226, 206, 210))

    ic.overlay(paint, clip)


def pick(ic: Icon, weights) -> tuple:
    r = ic.random.random()
    for pal, w in weights:
        r -= w
        if r <= 0:
            return pal
    return weights[-1][0]


def shrub(ic: Icon, cx: float, base: float, h: float, hw: float, tiers: int, scale: float = 1.0) -> Image.Image:
    """Coffee shrub: stems, dark inner mass, tiers of long drooping branches densely set with leaf
    pairs, cherries hugging the branch between leaves. Returns the shrub mask for lighting."""
    rnd = ic.random
    acc = [blank()]
    for dx, lean in ((-14, -40), (10, 30), (0, 6)):
        ic.line([(cx + dx, base), (cx + dx * 0.4 + lean * 0.3, base - h * 0.85)], 13, (74, 60, 46))
    body = ic.poly_mask(ic.jitter(cx, base - h * 0.42, hw * 0.8, h * 0.38, 18, 0.08))
    ic.fill(body, "#2c4a1c", "#0c1606", radial=(cx - hw * 0.5, base - h, h * 1.1), noise=0.3)
    acc[0] = union(acc[0], body)
    shadowed = tuple(tuple(int(v * 0.5) for v in rgb(c)) for c in LEAF)
    for _ in range(tiers * 9):  # leaves deep inside the bush, in shadow
        a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.5
        x, y = cx + math.cos(a) * hw * 0.72 * r, base - h * 0.47 + math.sin(a) * h * 0.4 * r
        ang = (0 if x > cx else 180) + (1 if x > cx else -1) * rnd.uniform(-30, 80)
        gleaf(ic, (x, y), ang, rnd.uniform(50, 80) * scale, rnd.uniform(22, 34) * scale, shadowed, 0.2, acc)
    # branches radiate from the stem at random heights; drawn back to front, the back ones darker
    branches = []
    for _ in range(tiers * 2 + 3):
        t = rnd.uniform(0, 1)
        depth = rnd.random()
        side = rnd.choice((-1, 1))
        prof = math.sqrt(max(0.05, 1 - ((t - 0.3) / 0.75) ** 2))
        reach = 1.0 if depth < 0.6 else rnd.uniform(0.45, 0.9)  # front branches point partly at the viewer
        branches.append((depth, t, side, hw * prof * rnd.uniform(0.6, 1.08) * reach, prof))
    branches.sort()
    for depth, t, side, L, prof in branches:
        y0 = base - h * (0.10 + 0.82 * t) + rnd.uniform(-10, 10)
        x0 = cx + side * rnd.uniform(0, 16)
        f = 0.72 + 0.42 * depth
        cols = tuple(tuple(int(min(255, v * f)) for v in rgb(c)) for c in (LEAF_TOP if t > 0.55 else LEAF))
        droop = rnd.uniform(0.18, 0.34)

        def at(s, L=L, y0=y0, side=side, x0=x0, droop=droop):
            return (x0 + side * L * s, y0 - L * 0.08 * s + L * droop * s * s)

        ic.line([at(s) for s in np.linspace(0, 1, 8)], 6, (48, 40, 28))
        phi = 0 if side > 0 else 180
        size = (56 + 30 * prof) * scale
        nodes = []
        s = rnd.uniform(0.12, 0.22)
        while s < 0.92:
            nodes.append(s)
            s += rnd.uniform(0.15, 0.24)
        for s in nodes:
            p = at(s)
            slope = math.degrees(math.atan2(2 * droop * s - 0.08, 1)) * side
            if rnd.random() < 0.85:
                gleaf(ic, p, phi - side * rnd.uniform(20, 50) + slope, size * rnd.uniform(0.65, 0.95),
                      size * rnd.uniform(0.42, 0.5), cols, 0.10, acc)
            gleaf(ic, p, phi + side * rnd.uniform(45, 80) + slope, size * rnd.uniform(0.85, 1.15),
                  size * rnd.uniform(0.42, 0.5), cols, rnd.uniform(0.15, 0.35), acc)
        gleaf(ic, at(1.0), phi + side * rnd.uniform(10, 35), size * 0.8, size * 0.4, cols, 0.2, acc)
        items = []
        for s in nodes:
            if t > 0.92 or rnd.random() < 0.38:
                continue
            px, py = at(s + 0.05)
            for _ in range(rnd.randint(3, 6)):
                pal = pick(ic, ((RIPE, 0.6), (DEEP, 0.22), (UNRIPE, 0.1), (GREEN, 0.08)))
                items.append((px + rnd.uniform(-14, 14) * scale, py + rnd.uniform(-3, 12) * scale,
                              rnd.uniform(10, 12.5) * scale, pal))
        items.sort(key=lambda it: it[1])
        cherries(ic, items)
    return acc[0]


def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float) -> Image.Image:
    """Feathery shade-tree crown: irregular blobs lit from the upper left, leaf dabs, dark underside."""
    rnd = ic.random
    m = blank()
    blobs = []
    for _ in range(22):
        u = rnd.uniform(-0.8, 0.8)
        blobs.append((cx + u * rx, cy - ry * 0.32 * (1 - u * u) + rnd.uniform(-ry * 0.28, ry * 0.32),
                      ry * rnd.uniform(0.3, 0.48) * (1.1 - 0.3 * abs(u))))
    for _ in range(26):  # small tufts breaking the upper edge
        u = rnd.uniform(-0.88, 0.88)
        blobs.append((cx + u * rx, cy - ry * 0.75 * math.sqrt(1 - u * u) + rnd.uniform(0, ry * 0.25),
                      ry * rnd.uniform(0.14, 0.24)))
    blobs.sort(key=lambda b: b[1])
    for bx, by, br in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.3, br, 28, 0.07))
        ic.fill(bm, "#668c3c", "#1a2e12", radial=(bx - br * 0.8, by - br * 0.9, br * 2.3), noise=0.28, chroma=0.14)
        m = union(m, bm)
    x0, x1, y0, y1 = cx - rx * 1.05, cx + rx * 1.05, cy - ry * 1.2, cy + ry

    def dabs(dr):
        for _ in range(1800):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            v = (y - cy) / ry
            r = rnd.uniform(3, 7)
            if rnd.random() < 0.5 - 0.5 * v:
                col = (150, 172, 92, 70)
            else:
                col = (22, 34, 12, 70)
            dr.ellipse((x - r, y - r * 0.55, x + r, y + r * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, cy + ry * 0.05, SIZE, SIZE))), (14, 22, 8), 0.40, blur=22)
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

    # overlapping courses of straw bundles, each with a ragged lower edge that shades the one below
    courses = [0.0, 0.22, 0.41, 0.6, 0.79, 1.0]
    for k in reversed(range(len(courses) - 1)):  # laid from the eave up: upper courses overlap lower
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
        if f1 < 1:  # this course's ragged edge shades the course below
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 22) for x, y in low[::-1]])), (30, 20, 8), 0.45, blur=6)
        tint = rnd.uniform(0.92, 1.06)
        ic.fill(band, tuple(int(v * tint) for v in rgb(c[0])), tuple(int(v * tint) for v in rgb(c[1])), (y0 - 10, y1 + 30),
                noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, y1=y1, low=low):
            for _ in range(260):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 26 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 24)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 22, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 8, (150, 128, 84, 170))


def jute(ic: Icon, cx: float, base: float, w: float, h: float, color) -> None:
    """Filled jute sack: lumpy body shaded from the upper left, tied neck, a few weave strokes."""
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


def scatter(ic: Icon, clip: Image.Image, y0: float, y1: float, x0: float, x1: float, step: float,
            size: float, palettes, round_: bool = False) -> None:
    """Grains spread over a surface in perspective (smaller towards the back)."""
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
    if round_:
        cherries(ic, [(x, yy, size * s * rnd.uniform(0.85, 1.1), pal) for x, yy, s, pal, _ in items], clip)
        return

    def paint(dr):
        for x, yy, s, (mid, dk), r in items:
            w, hh = size * s * (0.9 + 0.3 * r), size * s * 0.62
            dr.ellipse((x - w + 1, yy - hh + 2, x + w + 1, yy + hh + 2), fill=dk + (200,))
            dr.ellipse((x - w, yy - hh, x + w, yy + hh), fill=mid + (255,))
            dr.line([(x - w * 0.5, yy - hh * 0.1), (x + w * 0.5, yy + hh * 0.1)], fill=dk + (150,), width=2)

    ic.overlay(paint, clip)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84

    # ---- shed behind the drying bed: dark interior, sacks, posts, thatched roof
    ic.rect((586, 470, 972, 770), "#35281c", "#17110b", edge=0)

    def slats(dr):
        for x in np.arange(596, 972, 30):
            dr.line([(x + rnd.uniform(-3, 3), 480), (x, 770)], fill=(90, 70, 50, 70), width=4)

    ic.overlay(slats)
    # washing / fermentation vat on the left, jute sacks of dried coffee on the right
    ic.barrel(632, 600, 772, 790)
    ic.fill(ic.mask("ellipse", (640, 588, 764, 616)), "#3a4a4c", "#1e2a2c", noise=0.1)
    ic.shade(ic.mask("ellipse", (646, 590, 720, 604)), (200, 220, 225), 0.25, blur=3)
    jute(ic, 850, 712, 96, 118, "#9c8054")
    jute(ic, 922, 716, 84, 100, "#8a7048")
    jute(ic, 812, 718, 70, 70, "#a8895c")
    for x, top in ((602, 478), (788, 484), (958, 478)):
        ic.rect((x - 12, top, x + 12, 770), "#8a6442", "#4a3220", vertical=False, edge=3)
    ic.shade(ic.mask("rectangle", (586, 470, 972, 560)), alpha=0.45, blur=14)
    ridge = [(624, 352), (780, 344), (936, 350)]
    ex = np.linspace(568, 990, 18)
    eave = [(x, 488 + rnd.uniform(-5, 7)) for x in ex]
    thatch(ic, ridge, eave)
    ic.shade(ic.poly_mask([(800, 300), (1000, 300), (1000, 520), (820, 520)]), alpha=0.20, blur=50)

    # ---- shade tree: trunk and limbs, then the crown
    trunk = [(430, 780), (446, 740), (452, 560), (460, 380), (466, 318), (500, 318), (504, 400), (510, 580), (518, 740), (536, 780)]
    ic.poly(trunk, "#8e7862", "#3a2c22", span=(446, 520), vertical=False, noise=0.26, edge=3)
    for _ in range(14):  # bark mottling and pale lichen
        x, y = rnd.uniform(452, 508), rnd.uniform(340, 760)
        light = rnd.random() < 0.4
        ic.shade(ic.mask("ellipse", (x - 8, y - 16, x + 8, y + 16)), (220, 214, 190) if light else (20, 16, 12),
                 0.18 if light else 0.22, blur=3)
    ic.shade(ic.mask("rectangle", (420, 660, 540, 790)), (40, 52, 24), 0.25, blur=16)
    for x0 in (462, 476, 490):
        ic.line([(x0, 760), (x0 + rnd.uniform(-4, 4), 340)], 3, (40, 32, 24, 90))
    for p0, p1, w in (((472, 400), (330, 250), 22), ((484, 380), (640, 240), 20), ((478, 340), (470, 210), 18),
                      ((360, 280), (230, 220), 12), ((600, 262), (720, 230), 11)):
        ic.line([p0, p1], w, (88, 70, 54))
        ic.line([(p0[0] - 3, p0[1] - 2), (p1[0] - 3, p1[1] - 2)], max(w // 3, 3), (146, 126, 104, 140))
    crown = canopy(ic, 430, 226, 390, 136)

    # ---- ground strip and the dark earth under the bed
    top = [(20, 936)] + [(x, 912 + rnd.uniform(-12, 10)) for x in np.linspace(80, 960, 12)] + [(1010, 930)]
    ground = top + [(1012, 996), (520, 1006), (18, 998)]
    ic.poly(ground, "#735a3a", "#4a3a26", noise=0.32, edge=3)
    ic.rect((432, 780, 1004, 930), "#3a2d20", "#56432c", noise=0.3, edge=0)
    for _ in range(40):  # clods and fallen leaves
        x, y = rnd.uniform(40, 990), rnd.uniform(928, 994)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)), (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)

    # ---- raised drying bed: legs, mat of parchment coffee and drying cherries, front board
    BK, FY = 688, 790
    for x, y1 in ((474, 908), (962, 906)):
        ic.rect((x - 11, FY, x + 11, y1), "#6a4a2e", "#38261a", vertical=False, edge=3)
    ic.rect((470, 876, 966, 892), "#6e4e32", "#3e2a1a", edge=3)
    for x in (446, 712, 982):
        ic.rect((x - 14, FY, x + 14, 940 + rnd.uniform(-4, 4)), "#9a7048", "#4e3420", vertical=False, edge=3)
    ic.shade(ic.mask("ellipse", (410, 918, 1010, 962)), alpha=0.35, blur=10)
    surf = [(456, BK), (986, BK), (1006, FY), (424, FY)]
    S = ic.poly_mask(surf)
    ic.fill(S, "#7a5c3a", "#5c4228", (BK, FY), noise=0.3)
    split = [(742, BK), (760, 712), (738, 738), (766, 764), (752, FY)]
    P = ic.intersect(S, ic.poly_mask([(400, BK - 5)] + split + [(400, FY + 5)]))
    C = ImageChops.subtract(S, P)
    ic.fill(P, "#b0925e", "#86683e", (BK, FY), noise=0.25)
    beans = [((200, 164, 110), (110, 82, 48)), ((182, 146, 96), (100, 74, 42)), ((212, 180, 126), (120, 90, 56)),
             ((164, 128, 82), (92, 66, 38))]
    scatter(ic, P, BK, FY, 440, 770, 17, 8, beans)
    for y in (706, 729, 755, 776):  # raked furrows
        ic.shade(ic.intersect(P, ic.mask("rectangle", (0, y, SIZE, y + 5))), (40, 26, 12), 0.25, blur=3)
    ic.fill(C, "#6a1e14", "#4a120c", (BK, FY), noise=0.25)
    scatter(ic, C, BK, FY, 730, 1010, 18, 9, (RIPE, RIPE, DEEP, DRY, DRY), round_=True)
    ic.shade(ic.intersect(S, ic.mask("rectangle", (0, BK, SIZE, BK + 18))), alpha=0.35, blur=6)
    ic.line([(456, BK), (986, BK)], 12, (126, 92, 60))
    ic.line([(456, BK), (424, FY)], 12, (140, 104, 68))
    ic.line([(986, BK), (1006, FY)], 12, (100, 72, 46))
    # wooden rake lying on the parchment
    ic.line([(548, 774), (722, 716)], 12, (40, 28, 16, 120))
    ic.line([(544, 768), (718, 710)], 9, (164, 124, 78))
    ic.line([(700, 690), (742, 738)], 12, (124, 90, 56))
    # front board with grain
    ic.rect((418, FY, 1012, 830), "#9a7450", "#5e4028", noise=0.2, edge=4)
    for y in (800, 812, 822):
        ic.line([(430, y + rnd.uniform(-2, 2)), (1000, y + rnd.uniform(-2, 2))], 2, (60, 40, 22, 90))
    ic.shade(ic.mask("rectangle", (418, FY, 1012, 796)), (255, 240, 210), 0.25)

    # ---- coffee shrubs, back one first
    shrubA = shrub(ic, 185, 972, 480, 205, 7)
    shrubB = shrub(ic, 395, 994, 380, 165, 6, 0.92)
    for m in (shrubA, shrubB):
        ic.shade(ic.intersect(m, ic.mask("ellipse", (m.getbbox()[0] + 60, m.getbbox()[1] + 80, m.getbbox()[2] + 200,
                                                      m.getbbox()[3] + 200))), (6, 12, 4), 0.30, blur=40)
    ic.shade(ic.intersect(shrubA, ic.mask("rectangle", (0, 470, SIZE, 600))), (10, 18, 6), 0.25, blur=30)
    ic.shade(ic.mask("ellipse", (160, 960, 520, 1010)), alpha=0.40, blur=12)

    # ---- basket of picked cherries, bottom right
    ic.shade(ic.mask("ellipse", (842, 966, 1016, 1000)), alpha=0.45, blur=8)
    ic.fill(ic.mask("ellipse", (858, 858, 1002, 902)), "#3a1a10", "#241008")
    heap = []
    for _ in range(60):
        a, rr = rnd.uniform(math.pi, 2 * math.pi), rnd.random() ** 0.6
        x = 930 + math.cos(a) * 66 * rr
        y = 882 + math.sin(a) * 34 * rr + rnd.uniform(0, 12)
        heap.append((x, y, rnd.uniform(10, 12.5), pick(ic, ((RIPE, 0.7), (DEEP, 0.2), (UNRIPE, 0.1)))))
    heap.sort(key=lambda it: it[1])
    cherries(ic, heap)
    ic.basket(856, 880, 1004, 994)

    # ---- dappled shade from the tree over roof, bed and shrubs
    for _ in range(26):
        x, y = rnd.uniform(60, 1000), rnd.uniform(340, 900)
        r = rnd.uniform(30, 70)
        ic.shade(ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), (12, 16, 6), 0.16, blur=18)
    for _ in range(10):
        x, y = rnd.uniform(60, 1000), rnd.uniform(340, 900)
        r = rnd.uniform(18, 34)
        ic.shade(ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), (255, 238, 190), 0.12, blur=10)
    ic.shade(ic.intersect(crown, ic.mask("ellipse", (0, 60, 520, 260))), (255, 244, 210), 0.14, blur=30)
