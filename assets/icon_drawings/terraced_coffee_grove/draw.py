"""Terraced Coffee Grove: coffee shrubs hung with red cherries on curved dry-stone terraces under a shade tree.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/terraced_coffee_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/terraced_coffee_grove

Identity: the tier above the Coffee Grove. A hillside stepped into three curved terraces held by
grey dry-stone walls; each ledge carries a row of dark glossy coffee shrubs dotted with red cherries,
a feathery shade tree crowns the top terrace, and on the lowest ledge a woven drying mat of red
cherries lies beside clay vessels, with a basket of picked cherries in front.

Local helpers: ``gleaf``, ``shrub`` (coffee_grove's shrub with a cherry-size parameter), ``cherries``,
``pick``, ``canopy`` (from coffee_grove),
``drystone`` (curved dry-stone retaining wall with coping and irregular shaded stones), ``jar``
(clay storage vessel), ``mat`` (woven mat of drying cherries).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 29
REFS = ("terraces", "fruit_orchard", "farming_village", "sugar_plantation")

LEAF = ("#3a6428", "#0c1a06")
LEAF_TOP = ("#467432", "#10220a")

RIPE = ((164, 30, 32), (204, 66, 58), (76, 10, 14))
DEEP = ((112, 16, 26), (150, 40, 48), (52, 8, 12))
DRY = ((92, 34, 22), (124, 58, 38), (44, 16, 10))
UNRIPE = ((190, 104, 36), (222, 150, 70), (104, 52, 18))
GREEN = ((110, 138, 50), (156, 178, 88), (52, 72, 22))
BERRIES = ((DEEP, 0.34), (RIPE, 0.36), (UNRIPE, 0.15), (GREEN, 0.15))
HILL = (74, 86, 42)


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def pick(ic: Icon, weights) -> tuple:
    r = ic.random.random()
    for pal, w in weights:
        r -= w
        if r <= 0:
            return pal
    return weights[-1][0]


def cherries(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Round shaded berries (x, y, r, palette) in one blended layer: dark rim, body, lit side, glint."""

    def paint(dr):
        for x, y, r, (mid, lit, dk) in items:
            dr.ellipse((x - r, y - r, x + r, y + r), fill=dk + (255,))
            dr.ellipse((x - r + 1.5, y - r + 1, x + r - 2.5, y + r - 3), fill=mid + (255,))
            dr.ellipse((x - r * 0.72, y - r * 0.78, x + r * 0.12, y + r * 0.02), fill=lit + (235,))
            g = max(r * 0.22, 1.6)
            gx, gy = x - r * 0.42, y - r * 0.46
            dr.ellipse((gx - g, gy - g, gx + g, gy + g), fill=(252, 226, 206, 140))

    ic.overlay(paint, clip)


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
    if ic.random.random() < 0.35:
        ic.shade(ic.poly_mask(gloss), (232, 244, 214), 0.50, blur=1)
    else:
        ic.shade(ic.poly_mask(gloss), (226, 240, 206), 0.10, blur=2)
    ic.line([tuple(p) for p in spine[1:-4]], 3, (150, 176, 110, 90))
    ic.outline(pts, 3, (16, 26, 8, 120))
    if acc is not None:
        acc[0] = union(acc[0], m)


def shrub(ic: Icon, cx: float, base: float, h: float, hw: float, tiers: int, scale: float = 1.0,
          berry: float = 11.0) -> Image.Image:
    """Coffee shrub (as in coffee_grove): stems, dark inner mass, tiers of drooping branches set with
    leaf pairs, cherries hugging the branch. ``berry`` is the cherry radius, kept large on small
    shrubs so the fruit still reads at game size. Returns the shrub mask for lighting."""
    rnd = ic.random
    acc = [blank()]
    for dx, lean in ((-14, -40), (10, 30), (0, 6)):
        ic.line([(cx + dx * scale, base), (cx + dx * 0.4 + lean * 0.3, base - h * 0.85)], int(13 * scale) + 2, (74, 60, 46))
    body = ic.poly_mask(ic.jitter(cx, base - h * 0.42, hw * 0.8, h * 0.38, 18, 0.08))
    ic.fill(body, "#24401a", "#081204", radial=(cx - hw * 0.5, base - h, h * 1.1), noise=0.3)
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
            if t > 0.9 or rnd.random() < 0.75:
                continue
            px, py = at(s)
            for _ in range(rnd.randint(2, 4)):
                pal = pick(ic, BERRIES)
                items.append((px + rnd.uniform(-0.8, 0.8) * berry, py + rnd.uniform(0.1, 1.0) * berry,
                              rnd.uniform(0.85, 1.05) * berry, pal))
        items.sort(key=lambda it: it[1])
        cherries(ic, items)
    return acc[0]


def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float) -> Image.Image:
    """Feathery shade-tree crown: irregular blobs lit from the upper left, leaf dabs, dark underside."""
    rnd = ic.random
    m = blank()
    blobs = []
    for _ in range(20):
        u = rnd.uniform(-0.8, 0.8)
        blobs.append((cx + u * rx, cy - ry * 0.32 * (1 - u * u) + rnd.uniform(-ry * 0.28, ry * 0.32),
                      ry * rnd.uniform(0.3, 0.48) * (1.1 - 0.3 * abs(u))))
    for _ in range(24):
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
        for _ in range(1400):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            v = (y - cy) / ry
            r = rnd.uniform(3, 7)
            col = (150, 172, 92, 70) if rnd.random() < 0.5 - 0.5 * v else (22, 34, 12, 70)
            dr.ellipse((x - r, y - r * 0.55, x + r, y + r * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, cy + ry * 0.05, SIZE, SIZE))), (14, 22, 8), 0.40, blur=22)
    return m


def smooth(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Terrace:
    """One contour terrace: wall top y = yc - lift * u^2 about ``mc`` (bows towards the viewer), the
    wall face ``h`` high, fading into the slope over ``fade`` px at its left end."""

    def __init__(self, x0, x1, yc, lift, h, back, fade, mc, phase):
        self.x0, self.x1, self.yc, self.lift, self.h, self.back, self.fade, self.mc = x0, x1, yc, lift, h, back, fade, mc
        self.hw = max(mc - x0, x1 - mc)
        self.phase = phase

    def top(self, x):
        u = (x - self.mc) / self.hw
        return self.yc - self.lift * u * u

    def s(self, x):
        return smooth((x - self.x0) / self.fade) * smooth((self.x1 - x) / 36)

    def height(self, x):
        return self.h * self.s(x) * (1 + 0.14 * math.sin(x / 61 + self.phase) + 0.06 * math.sin(x / 17 + 2 * self.phase))


def blend_left(ic: Icon, m: Image.Image, x0: float, fade: float, alpha: float) -> None:
    """Melt the left end of a wall or ledge into the grassy slope."""
    g = ic.mask("rectangle", (x0 - 400, 0, x0 + fade * 0.45, SIZE)).filter(ImageFilter.GaussianBlur(fade * 0.3))
    ic.shade(ic.intersect(m, g), HILL, alpha)


def drystone(ic: Icon, T: Terrace) -> Image.Image:
    """Dry-stone retaining wall of warm brown-grey stones with thin dark joints, a worn coping and a
    damp, mossy footing; its height varies along the wall and it melts into the slope on the left."""
    rnd = ic.random
    xs = np.linspace(T.x0, T.x1, 60)
    face = [(x, T.top(x)) for x in xs] + [(x, T.top(x) + T.height(x)) for x in xs[::-1]]
    m = ic.poly_mask(face)
    ic.fill(m, "#2c241a", "#16110b", (T.yc - T.lift, T.yc + T.h), noise=0.2)
    stones = []
    rows = max(2, int(T.h / 30))
    for r in range(rows):
        f0 = r / rows
        x = T.x0 - rnd.uniform(0, 40)
        while x < T.x1:
            w = rnd.uniform(40, 84)
            cxs = x + w / 2
            hh = T.height(cxs)
            if hh > 10:
                y = T.top(cxs) + hh * (f0 + 0.5 / rows)
                stones.append((cxs, y + rnd.uniform(-2, 2), w * 0.48, hh / rows * 0.47))
            x += w + rnd.uniform(2, 5)
    tones = ((124, 104, 84), (110, 98, 86), (132, 110, 86), (100, 86, 70))

    def paint(dr):
        for sx, sy, rx, ry in stones:
            t = rnd.uniform(0.82, 1.1)
            base = np.array(rnd.choice(tones)) * t
            pts = ic.jitter(sx, sy, rx, ry, 9, 0.1)
            dr.polygon(pts, fill=tuple(int(min(255, v)) for v in base) + (255,))
            dr.polygon([(sx - rx * 0.9, sy - ry * 0.1), (sx - rx * 0.3, sy - ry * 0.9), (sx + rx * 0.6, sy - ry * 0.8),
                        (sx + rx * 0.1, sy - ry * 0.2)], fill=(226, 206, 172, 48))
            dr.polygon([(sx - rx * 0.8, sy + ry * 0.5), (sx + rx * 0.9, sy + ry * 0.2), (sx + rx * 0.7, sy + ry * 0.9),
                        (sx - rx * 0.5, sy + ry * 0.95)], fill=(26, 20, 14, 100))

    ic.overlay(paint, m)
    for _ in range(int((T.x1 - T.x0) / 50)):  # damp streaks and moss low on the wall
        x = rnd.uniform(T.x0, T.x1)
        y = T.top(x) + T.height(x) * rnd.uniform(0.5, 0.9)
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - 30, y - 10, x + 30, y + 14))),
                 (64, 84, 36) if rnd.random() < 0.55 else (20, 16, 10), 0.28, blur=6)
    ic.shade(ic.intersect(m, ic.poly_mask([(x, T.top(x) + T.height(x) * 0.65) for x in xs] +
                                          [(x, T.top(x) + T.height(x) + 2) for x in xs[::-1]])), (10, 8, 4), 0.4, blur=8)
    cx = [x for x in xs if T.s(x) > 0.3]
    ic.line([(x, T.top(x) + 3) for x in cx], 10, (104, 88, 70))
    ic.line([(x, T.top(x) - 1) for x in cx], 3, (168, 148, 118, 100))
    ic.line([(x, T.top(x) + 9) for x in cx], 3, (30, 24, 18, 150))
    blend_left(ic, m, T.x0, T.fade, 0.75)
    return m


def ledge(ic: Icon, T: Terrace) -> Image.Image:
    """Earth surface of a terrace, from its back edge (``back`` above the wall top) to the wall top."""
    rnd = ic.random
    xs = np.linspace(T.x0, T.x1, 40)
    pts = [(x, T.top(x) - T.back * (0.35 + 0.65 * T.s(x))) for x in xs] + [(x, T.top(x) + 4) for x in xs[::-1]]
    m = ic.poly_mask(pts)
    ic.fill(m, "#6a4c30", "#3a2918", (T.yc - T.lift - T.back, T.yc), noise=0.35, chroma=0.12)
    for _ in range(int((T.x1 - T.x0) / 20)):
        x, y = rnd.uniform(T.x0, T.x1), rnd.uniform(T.yc - T.back, T.yc)
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - 12, y - 4, x + 12, y + 4))),
                 (255, 226, 190) if rnd.random() < 0.4 else (0, 0, 0), 0.18, blur=2)
    blend_left(ic, m, T.x0, T.fade, 0.8)
    return m


def hill(ic: Icon, pts) -> Image.Image:
    """Grassy hill mass rising to the upper left: olive turf over brown earth, lit from the upper left."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    ic.fill(m, "#4c5e26", "#191b09", radial=(80, 240, 1100), noise=0.34, chroma=0.14)

    def tufts(dr):
        for _ in range(2600):
            x, y = rnd.uniform(0, SIZE), rnd.uniform(200, SIZE)
            r = rnd.uniform(4, 9)
            k = rnd.random()
            if k < 0.35:
                col = (124, 146, 64, 55)
            elif k < 0.7:
                col = (26, 34, 12, 70)
            else:
                col = (110, 76, 44, 60)
            dr.ellipse((x - r, y - r * 0.5, x + r, y + r * 0.5), fill=col)

    ic.overlay(tufts, m)
    for _ in range(26):  # bare earth patches
        x, y = rnd.uniform(0, SIZE), rnd.uniform(300, 980)
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - 40, y - 12, x + 40, y + 12))), (96, 66, 38), 0.4, blur=10)
    return m


def jar(ic: Icon, cx: float, base: float, w: float, h: float, color="#a86440") -> None:
    """Clay storage vessel: swelling body lit from the upper left, narrow neck and lip."""
    ts = np.linspace(0, 1, 24)
    prof = [w / 2 * (0.55 + 0.45 * math.sin(math.pi * (0.15 + 0.8 * t))) for t in ts]
    left = [(cx - p, base - h * 0.82 * t) for p, t in zip(prof, ts)]
    right = [(cx + p, base - h * 0.82 * t) for p, t in zip(prof[::-1], ts[::-1])]
    pts = left + [(cx - w * 0.2, base - h * 0.9), (cx + w * 0.2, base - h * 0.9)] + right
    dark = tuple(int(v * 0.42) for v in rgb(color))
    ic.fill(ic.poly_mask(pts), color, dark, radial=(cx - w * 0.3, base - h * 0.7, w * 1.1), noise=0.25)
    ic.outline(pts, 4, (40, 22, 12, 200))
    ic.ellipse((cx - w * 0.26, base - h * 0.98, cx + w * 0.26, base - h * 0.86), "#b87650", "#6a3a20", edge=3)
    ic.fill(ic.mask("ellipse", (cx - w * 0.16, base - h * 0.96, cx + w * 0.16, base - h * 0.89)), "#2a1a10")
    ic.line([(cx - w * 0.42, base - h * 0.52), (cx + w * 0.42, base - h * 0.52)], 3, (60, 30, 16, 120))


def mat(ic: Icon, box) -> None:
    """Oval woven drying mat, tan with a lighter bound rim, a sparse scatter of dried cherries."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.shade(ic.mask("ellipse", (x0 - 6, y0 + 10, x1 + 12, y1 + 14)), alpha=0.5, blur=8)
    m = ic.mask("ellipse", box)
    ic.fill(m, "#b8945e", "#7a5a34", radial=(x0 + (x1 - x0) * 0.3, y0, (x1 - x0) * 0.9), noise=0.22)

    def weave(dr):
        for x in np.arange(x0 - 80, x1 + 80, 13):
            dr.line([(x, y0), (x - 36, y1)], fill=(96, 70, 38, 80), width=3)
            dr.line([(x, y0), (x + 36, y1)], fill=(236, 212, 164, 40), width=2)

    ic.overlay(weave, m)
    items = []
    y = y0 + 12
    while y < y1 - 12:
        x = x0 + rnd.uniform(10, 30)
        while x < x1 - 10:
            u, v = (x - (x0 + x1) / 2) / ((x1 - x0) / 2), (y - (y0 + y1) / 2) / ((y1 - y0) / 2)
            if u * u + v * v < 0.66 and rnd.random() < 0.62:
                items.append((x + rnd.uniform(-4, 4), y + rnd.uniform(-2, 2), rnd.uniform(5, 6.5),
                              DRY if rnd.random() < 0.7 else DEEP))
            x += rnd.uniform(13, 18)
        y += 10
    cherries(ic, items, m)
    ic.overlay(lambda d: d.ellipse(box, outline=(222, 198, 150, 230), width=9))
    ic.overlay(lambda d: d.ellipse((x0 + 9, y0 + 6, x1 - 9, y1 - 6), outline=(90, 62, 32, 110), width=3))
    ic.overlay(lambda d: d.ellipse(box, outline=(60, 40, 20, 200), width=3))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.63
    ic.grade["mute"] = 0.84

    # ---- the hillside, rising to the upper left and falling away to the right
    crest = [(0, 440), (14, 360), (60, 300), (150, 262), (280, 250), (420, 272), (560, 318), (700, 390),
             (820, 470), (930, 580), (1010, 700), (1022, 800)]
    crest = [(x + rnd.uniform(-6, 6), y + rnd.uniform(-6, 6)) for x, y in crest]
    foot = [(1022, 900), (700, 912), (300, 918), (60, 920), (0, 906)]
    hill(ic, crest + foot)

    # terraces (x0, x1, wall top at mc, end lift, wall height, ledge depth, left fade, mc, phase):
    # a shallow top step, a deep forward middle step, a long low bottom step
    T3 = Terrace(20, 700, 430, 52, 60, 78, 230, 380, 0.4)
    T2 = Terrace(110, 928, 668, 78, 96, 118, 280, 560, 2.1)
    T1 = Terrace(0, 1012, 872, 44, 76, 92, 210, 600, 4.0)

    # ---- top terrace: shade tree, ledge, shrubs, wall
    ledge(ic, T3)
    trunk = [(334, 440), (352, 396), (360, 256), (364, 188), (404, 188), (410, 256), (420, 396), (440, 440)]
    ic.poly(trunk, "#8e7862", "#3a2c22", span=(340, 440), vertical=False, noise=0.26, edge=3)
    for _ in range(8):  # bark mottling
        x, y = rnd.uniform(362, 406), rnd.uniform(210, 420)
        ic.shade(ic.intersect(ic.poly_mask(trunk), ic.mask("ellipse", (x - 8, y - 14, x + 8, y + 14))),
                 (180, 176, 150) if rnd.random() < 0.4 else (20, 14, 10), 0.3, blur=3)
    # shadowed inner foliage under the crown, behind the limbs
    inner = union(ic.poly_mask(ic.jitter(390, 200, 200, 52, 26, 0.12)), ic.poly_mask(ic.jitter(456, 150, 100, 34, 20, 0.1)))
    ic.fill(inner, "#26381a", "#0e160a", (150, 260), noise=0.3)
    for p0, p1, w in (((378, 270), (220, 170), 22), ((392, 250), (580, 150), 20), ((384, 220), (398, 110), 16)):
        ic.line([p0, p1], w, (88, 70, 54))
        ic.line([(p0[0] - 3, p0[1] - 3), (p1[0] - 3, p1[1] - 3)], max(w // 3, 3), (146, 126, 104, 140))
    crown = canopy(ic, 386, 160, 382, 122)
    with ic.clipped(ic.mask("rectangle", (0, 0, T3.x1 - 14, SIZE))):
        for cx, hh, hwid in ((170, 150, 96), (560, 156, 98)):
            shrub(ic, cx, T3.top(cx) - 6, hh, hwid, 3, 0.42, 7.5)
    drystone(ic, T3)

    # ---- middle terrace
    ledge(ic, T2)
    with ic.clipped(ic.mask("rectangle", (0, 0, T2.x1 - 16, SIZE))):
        for cx, hh, hwid in ((250, 180, 104), (470, 208, 122), (690, 200, 116), (816, 124, 78)):
            shrub(ic, cx + rnd.uniform(-10, 10), T2.top(cx) - 6, hh, hwid, 3, 0.48, 8.5)
    drystone(ic, T2)

    # ---- lowest terrace: shrubs on the left, drying mat and clay vessels on the right
    ledge(ic, T1)
    for cx, hh, hwid in ((110, 214, 124), (350, 230, 132), (560, 214, 120)):
        shrub(ic, cx + rnd.uniform(-10, 10), T1.top(cx) - 6, hh, hwid, 3, 0.54, 9.5)
    ic.shade(ic.mask("ellipse", (820, 770, 1000, 800)), alpha=0.4, blur=10)
    jar(ic, 876, 800, 86, 150, "#a86440")
    jar(ic, 952, 808, 70, 116, "#94583a")
    mat(ic, (626, 784, 906, 866))
    drystone(ic, T1)

    # ---- basket of picked cherries in front of the lowest wall, bottom right
    ic.shade(ic.mask("ellipse", (760, 966, 960, 1010)), alpha=0.5, blur=8)
    ic.fill(ic.mask("ellipse", (784, 872, 936, 916)), "#3a1a10", "#241008")
    heap = []
    for _ in range(60):
        a, rr = rnd.uniform(math.pi, 2 * math.pi), rnd.random() ** 0.6
        heap.append((860 + math.cos(a) * 70 * rr, 896 + math.sin(a) * 34 * rr + rnd.uniform(0, 12),
                     rnd.uniform(10, 12.5), pick(ic, ((RIPE, 0.55), (DEEP, 0.3), (UNRIPE, 0.15)))))
    heap.sort(key=lambda it: it[1])
    cherries(ic, heap)
    ic.basket(782, 894, 938, 1000)

    # ---- dappled shade from the tree and hillside light from the upper left
    for _ in range(16):
        x, y = rnd.uniform(80, 760), rnd.uniform(280, 620)
        r = rnd.uniform(30, 60)
        ic.shade(ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), (12, 16, 6), 0.14, blur=18)
    ic.shade(ic.intersect(crown, ic.mask("ellipse", (0, 20, 450, 190))), (255, 244, 210), 0.14, blur=30)
    ic.shade(ic.mask("ellipse", (-300, 200, 400, 900)), (255, 240, 200), 0.04, blur=80)
    ic.shade(ic.mask("ellipse", (700, 300, 1300, 1000)), (10, 12, 6), 0.12, blur=90)
