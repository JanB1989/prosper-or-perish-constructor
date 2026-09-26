"""Maize Farmstead: a thatched farmhouse and a slatted corn crib full of golden ears, maize in front.

Identity: the corn crib on the right, a raised, flared box of weathered slats with the stacked
golden ears showing between them under a shingle roof; beside it a timber-framed farmhouse with a
thatched roof, a stand of tall maize with tassels and opened ears in front of the house, and a heap
of husked ears with a basket at the crib's foot.

Local helpers (maize helpers shared by the four maize tiers): ``blade``, ``stalk``, ``tassel``,
``cob``, ``ear``, ``open_ear``, ``maize``, ``hill``; plus ``thatch`` (from coffee_grove, warmed to straw-brown), ``crib``
(slatted crib wall with ears inside), ``post`` and ``shingles`` (irregular wooden shingle roof,
replaces the kit ``tiles``).

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/maize_farmstead/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/maize_farmstead
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 17
REFS = ('farming_village', 'fiber_crops_farm', 'granary', 'free_village')

LEAF = ("#9ab852", "#2c4616")
LEAF_SUN = ("#b0b862", "#4a5424")  # older leaves going yellow
STALK = ((58, 80, 30), (132, 158, 76))
TASSEL = ((214, 190, 120), (120, 94, 46))
KERNEL = ((222, 162, 44), (248, 206, 96), (128, 76, 16))  # mid, lit, dark
KERNEL_RED = ((196, 110, 44), (230, 160, 90), (104, 48, 16))
HUSK_GREEN = ("#a4b862", "#4a5c22")
HUSK_DRY = ("#d8cc98", "#8a7a48")
SILK = (120, 70, 36)


def scaled(c, f: float):
    return tuple(int(max(0, min(255, v * f))) for v in rgb(c))


def blade(ic: Icon, base, deg: float, length: float, width: float, droop: float = 1.0,
          colors=LEAF) -> None:
    """Long maize leaf: leaves the stalk towards ``deg`` and arches over under ``droop``.

    Width follows the tangent, so the ribbon keeps its width through the bend; the side facing
    down is in shade, a pale midrib runs along the lit half.
    """
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 34)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    tang = [d + np.array([0, 2 * droop * t]) for t in ts]
    norms = [np.array([-v[1], v[0]]) / np.hypot(*v) for v in tang]
    hw = [width / 2 * min(1.0, 0.45 + t / 0.12 * 0.55) * (1 - t) ** 0.65 for t in ts]
    s1 = [p + n * w for p, n, w in zip(spine, norms, hw)]
    s2 = [p - n * w for p, n, w in zip(spine, norms, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(ic.poly_mask(pts), colors[0], colors[1],
            radial=(min(xs), min(ys), max(length * 0.9, 1)), noise=0.2, chroma=0.12)
    lower = s1 if norms[0][1] > 0 else s2
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (8, 18, 4), 0.34)
    ic.line([tuple(p) for p in spine[1:-6]], 3, (196, 210, 150, 110))
    ic.outline(pts, 3, (18, 30, 8, 150))


def stalk(ic: Icon, x: float, base: float, h: float, lean: float = 0, f: float = 1.0) -> list:
    """Jointed maize stalk, thick at the foot; returns the top point."""
    top = (x + lean, base - h)
    ts = np.linspace(0, 1, 12)
    spine = [(x + lean * t, base - h * t) for t in ts]
    pts = [(px - 11 * (1 - 0.5 * t), py) for (px, py), t in zip(spine, ts)]
    pts += [(px + 11 * (1 - 0.5 * t), py) for (px, py), t in zip(spine[::-1], ts[::-1])]
    ic.fill(ic.poly_mask(pts), scaled(STALK[1], f), scaled(STALK[0], f * 0.8), radial=(x - 14, base - h, h * 0.08),
            noise=0.2)
    ic.shade(ic.poly_mask([(px + 2, py) for px, py in spine] + [(px + 11 * (1 - 0.5 * t), py) for (px, py), t in
                                                              zip(spine[::-1], ts[::-1])]), (10, 20, 4), 0.35)
    ic.outline(pts, 3, (20, 34, 8, 170))
    for k in range(1, 8):  # nodes
        t = k / 8
        nx, ny = x + lean * t, base - h * t
        ic.line([(nx - 9, ny), (nx + 9, ny + 2)], 4, (40, 54, 20, 170))
    for dx in (-18, 16):  # brace roots
        ic.line([(x, base - 30), (x + dx, base + 4)], 5, scaled(STALK[0], f * 0.85))
    return top


def tassel(ic: Icon, top, size: float, f: float = 1.0, thin: bool = False) -> None:
    """Pale branched tassel: a central spike and side branches that rise and arch outwards."""
    tx, ty = top
    lit, dk = scaled(TASSEL[0], f), scaled(TASSEL[1], f)
    rnd = ic.random
    if thin:  # compact mid-green plume: few, chunky branches so the black silhouette outline stays quiet
        lit, dk = (172, 184, 104), (104, 120, 54)
        for deg, ln, sag, w in ((-90 + rnd.uniform(-5, 5), 0.75, 0.05, 24), (-128 + rnd.uniform(-6, 6), 0.55, 0.7, 18),
                                (-52 + rnd.uniform(-6, 6), 0.55, 0.7, 18)):
            a = math.radians(deg)
            L = size * ln
            pts = [(tx + math.cos(a) * L * t, ty + 8 + math.sin(a) * L * t + sag * L * t * t) for t in np.linspace(0, 1, 9)]
            ic.line(pts, w, dk)
            ic.line([(x - 2, y - 2) for x, y in pts[:-1]], int(w * 0.55), lit)
        return
    branches = [(-90 + rnd.uniform(-6, 6), 0.8, 0.1)]
    for deg in (-150, -125, -55, -30, -100, -75):
        branches.append((deg + rnd.uniform(-8, 8), rnd.uniform(0.6, 0.85), rnd.uniform(0.5, 0.9)))
    for deg, ln, sag in branches:
        a = math.radians(deg)
        L = size * ln
        pts = [(tx + math.cos(a) * L * t, ty + 6 + math.sin(a) * L * t + sag * L * t * t) for t in np.linspace(0, 1, 9)]
        for w, c in ((12, dk), (7, lit)):
            ic.line(pts, w, c)
        for p in pts[2::2]:  # spikelets
            ic.overlay(lambda d, p=p: d.ellipse((p[0] - 6, p[1] - 4, p[0] + 5, p[1] + 5), fill=lit + (230,)))


def cob(ic: Icon, p0, deg: float, length: float, width: float, kern=KERNEL, peel: bool = True,
        husk=HUSK_DRY) -> None:
    """Husked ear from its butt ``p0`` towards ``deg``: rows of shaded kernels, husk folded back."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(p0, float)
    if peel:  # husk leaves folded back past the butt
        for s, k in ((1, 0.9), (-1, 1.0), (0.3, 0.8)):
            tip = b - d * length * 0.55 * k + n * s * width * 0.9
            side = b + n * s * width * 0.25
            pts = [tuple(b - n * width * 0.4), tuple(side + d * width * 0.2), tuple(tip),
                   tuple(b - d * width * 0.2 + n * s * width * 0.1)]
            ic.poly(pts, husk[0], husk[1], edge=3)
    ts = np.linspace(0, 1, 24)
    hw = [width / 2 * (0.82 + 0.18 * math.sin(math.pi * min(1, t * 1.6))) * (1 - t ** 3) ** 0.5 for t in ts]
    s1 = [b + d * length * t + n * w for t, w in zip(ts, hw)]
    s2 = [b + d * length * t - n * w for t, w in zip(ts, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    ic.fill(m, kern[0], kern[2], radial=(min(p[0] for p in pts), min(p[1] for p in pts), length * 1.1),
            noise=0.12)
    kr = width / 9

    def kernels(dr):
        rows = 6
        for i in range(rows):
            u = -0.85 + 1.7 * (i + 0.5) / rows
            lit = u * (1 if n[1] < 0 else -1)  # the upper side of the ear catches the light
            base_c = kern[1] if lit > 0.2 else kern[0] if lit > -0.4 else kern[2]
            for t in np.arange(0.04 + (i % 2) * 0.03, 0.97, kr * 1.9 / length):
                w = hw[min(int(t * 23), 23)]
                c = b + d * length * t + n * u * w * 0.92
                r = kr * (1 - abs(u) * 0.35)
                dr.ellipse((c[0] - r, c[1] - r * 0.9, c[0] + r, c[1] + r * 0.9), fill=base_c + (230,))
                dr.ellipse((c[0] - r * 0.5, c[1] - r * 0.6, c[0] + r * 0.1, c[1] - r * 0.05),
                           fill=(255, 236, 170, 120))

    ic.overlay(kernels, m)
    ic.shade(ic.poly_mask([tuple(p) for p in (s1 if n[1] > 0 else s2)] + [tuple(b + d * length * t) for t in ts[::-1]]),
             (60, 30, 0), 0.30)
    ic.outline(pts, 3, (60, 36, 10, 170))


def ear(ic: Icon, p0, deg: float, length: float, width: float, f: float = 1.0) -> None:
    """Ear still in the green husk on the stalk: spindle of husk leaves with a tuft of dark silk."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(p0, float)
    ts = np.linspace(0, 1, 20)
    hw = [width / 2 * math.sin(math.pi * (0.12 + 0.88 * t) ** 0.8) for t in ts]
    s1 = [b + d * length * t + n * w for t, w in zip(ts, hw)]
    s2 = [b + d * length * t - n * w for t, w in zip(ts, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    ic.fill(ic.poly_mask(pts), scaled(HUSK_GREEN[0], f), scaled(HUSK_GREEN[1], f),
            radial=(min(p[0] for p in pts), min(p[1] for p in pts), length), noise=0.2)
    ic.shade(ic.poly_mask([tuple(p) for p in (s1 if n[1] > 0 else s2)] + [tuple(b + d * length * t) for t in ts[::-1]]),
             (10, 20, 0), 0.3)
    for u in (-0.4, 0.15):  # husk leaf seams
        ic.line([tuple(b + d * length * t + n * u * hw[int(t * 19)]) for t in np.linspace(0.1, 0.9, 6)], 3,
                (50, 70, 20, 130))
    ic.outline(pts, 3, (20, 34, 8, 160))
    tip = b + d * length
    for k in range(5):  # silk
        ang = a + ic.random.uniform(-0.6, 0.6)
        q = tip + np.array([math.cos(ang), math.sin(ang) + 0.6]) * length * 0.22
        ic.line([tuple(tip), tuple(q)], 4, SILK + (220,))


def open_ear(ic: Icon, p0, deg: float, length: float, width: float, f: float = 1.0, kern=KERNEL) -> None:
    """Ripe ear on the stalk with its husk split open: golden cob between two green husk flaps."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(p0, float)
    cob(ic, tuple(b + d * length * 0.08), deg, length * 0.92, width, kern=kern, peel=False)
    for s, reach in ((1, 0.95), (-1, 0.8)):
        pts = [tuple(b - n * s * width * 0.1), tuple(b + d * length * 0.25 + n * s * width * 0.62),
               tuple(b + d * length * reach * 0.75 + n * s * width * 0.95),
               tuple(b + d * length * reach + n * s * width * 1.35),
               tuple(b + d * length * reach * 0.62 + n * s * width * 0.42), tuple(b + d * length * 0.2)]
        ic.poly(pts, scaled(HUSK_GREEN[0], f * (1.08 if s * n[1] < 0 else 0.85)), scaled(HUSK_GREEN[1], f),
                edge=3)


def maize(ic: Icon, x: float, base: float, h: float, ears: int = 1, lean: float = 0, f: float = 1.0,
          husked: bool = False, thin: bool = False) -> None:
    """One maize plant: back leaves, stalk, alternating arching leaves, ears, tassel on top
    (``thin``: a lighter, sparser tassel for plants whose tops make the silhouette's top edge)."""
    rnd = ic.random
    cols = (scaled(LEAF[0], f), scaled(LEAF[1], f))
    sun = (scaled(LEAF_SUN[0], f), scaled(LEAF_SUN[1], f))
    n = 9
    specs = []
    for i in range(n):
        t = 0.1 + 0.8 * i / (n - 1)
        side = 1 if i % 2 == 0 else -1
        side = side if rnd.random() > 0.15 else -side
        ln = h * (0.6 - 0.3 * t) * rnd.uniform(0.85, 1.1)
        deg = -90 + side * rnd.uniform(18 + 10 * (1 - t), 30 + 25 * (1 - t))
        specs.append((t, side, ln, deg, rnd.uniform(0.9, 1.5)))
    # lowest leaves hang behind the stalk
    for t, side, ln, deg, dr in specs[:2]:
        blade(ic, (x + lean * t, base - h * t), deg, ln, ln * 0.15, dr, sun if rnd.random() < 0.6 else cols)
    top = stalk(ic, x, base, h, lean, f)
    ear_ts = [0.42, 0.55][:ears]
    for t, side, ln, deg, dr in specs[2:]:
        blade(ic, (x + lean * t, base - h * t), deg, ln, ln * 0.14, dr * (1.3 - 0.5 * t), cols)
    for k, t in enumerate(ear_ts):
        side = 1 if k % 2 == 0 else -1
        p = (x + lean * t + side * 6, base - h * t)
        if husked or k == 0 and f >= 1:
            open_ear(ic, p, -90 + side * 28, h * 0.23, h * 0.08, f)
        else:
            ear(ic, p, -90 + side * 26, h * 0.17, h * 0.065, f)
    # the top leaf in front
    t, side, ln, deg, dr = specs[-1]
    blade(ic, (x + lean * 0.9, base - h * 0.9), -90 - side * 30, ln * 0.7, ln * 0.09, 1.2, cols)
    tassel(ic, top, h * (0.13 if thin else 0.16), f, thin)


def hill(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Hoed mound of earth, lit from the upper left, with clods."""
    pts = [(cx + w / 2 * math.cos(a) * ic.random.uniform(0.97, 1.03),
            base + h * math.sin(a) * (1 - 0.5 * math.cos(a) ** 2) * ic.random.uniform(0.9, 1.08))
           for a in np.linspace(math.pi, 2 * math.pi, 18)]
    pts += [(cx + w * 0.4, base + 8), (cx - w * 0.4, base + 8)]
    ic.fill(ic.poly_mask(pts), "#8a6c46", "#3c2c1a", radial=(cx - w * 0.3, base - h, w * 0.9), noise=0.35)
    for _ in range(int(w / 12)):
        x, y = cx + ic.random.uniform(-w * 0.4, w * 0.4), base - ic.random.uniform(0, h * 0.8)
        r = ic.random.uniform(5, 10)
        light = ic.random.random() < 0.5
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7)), (255, 230, 190) if light else (0, 0, 0),
                 0.25, blur=1)
    ic.outline(pts, 3, (40, 28, 16, 140))


def thatch(ic: Icon, ridge, eave, c=("#dc9a48", "#7e4a1c")) -> None:
    """Thatched roof plane seen from above, warm straw-brown: straw strokes running down the slope, a
    cut eave lit along its edge, a lit ridge, darker where the hips meet the maize behind."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
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
        ic.fill(band, scaled(c[0], tint), scaled(c[1], tint), (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, y1=y1, low=low):
            for _ in range(260):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (246, 214, 146, 84) if rnd.random() < 0.55 else (72, 44, 16, 84)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 26 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#a47a3e", "#5a3c18", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 24)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([(p[0], p[1] + 3) for p in eave], 7, (240, 204, 136, 150))  # lit edge of the cut eave
    # the hips darken where the roof meets the maize behind; the ridge catches the light
    edge = ic.intersect(m, Image.fromarray(255 - np.asarray(m.filter(ImageFilter.MinFilter(41)))))
    ic.shade(ic.intersect(soft(edge, 8), ic.mask("rectangle", (0, 0, SIZE, max(p[1] for p in eave) - 50))),
             (34, 20, 6), 0.5)
    ic.shade(ic.intersect(m, soft(ic.mask("rectangle", (0, min(ys) - 10, SIZE, min(ys) + 40)), 10)),
             (255, 226, 160), 0.22)
    ic.line([tuple(p) for p in ridge], 24, (112, 76, 36))
    ic.line([tuple(p) for p in ridge], 14, (176, 132, 70))
    ic.line([(p[0], p[1] - 3) for p in ridge], 6, (238, 204, 140, 190))


def crib(ic: Icon, x0: float, x1: float, top: float, floor: float, flare: float = 22, slat: float = 17,
         gap: float = 21) -> None:
    """Slatted corn crib wall, wider at the top: golden ears stacked inside show between the slats."""
    rnd = ic.random
    wall = [(x0 - flare, top), (x1 + flare, top), (x1, floor), (x0, floor)]
    W = ic.poly_mask(wall)
    ic.fill(W, "#5a3a14", "#2a1a08", (top, floor), noise=0.3)
    with ic.clipped(W):  # the stacked ears, butt ends and sides, in rows
        y = top + 10
        while y < floor + 20:
            x = x0 - flare - rnd.uniform(0, 60)
            while x < x1 + flare + 40:
                ln = rnd.uniform(80, 110)
                deg = rnd.choice((0, 180)) + rnd.uniform(-14, 14)
                kern = KERNEL if rnd.random() < 0.8 else KERNEL_RED
                cob(ic, (x, y), deg, ln, rnd.uniform(34, 40), kern=kern, peel=False)
                x += ln * rnd.uniform(0.7, 0.95)
            y += rnd.uniform(26, 32)
    y = top + 4
    while y < floor - 4:  # horizontal slats, weathered grey-brown
        yb = min(y + slat, floor)
        ft, fb = (y - top) / (floor - top), (yb - top) / (floor - top)
        board = [(x0 - flare * (1 - ft) - 4, y), (x1 + flare * (1 - ft) + 4, y), (x1 + flare * (1 - fb) + 4, yb),
                 (x0 - flare * (1 - fb) - 4, yb)]
        tint = rnd.uniform(0.88, 1.08)
        ic.fill(ic.poly_mask(board), scaled("#9a7a52", tint), scaled("#56402a", tint), (x0, x1), vertical=False,
                noise=0.3)
        ic.shade(ic.poly_mask([board[0], board[1], (board[1][0], y + 5), (board[0][0], y + 5)]), (255, 240, 210), 0.25)
        ic.shade(ic.poly_mask([(board[3][0], yb + 1), (board[2][0], yb + 1), (board[2][0], yb + 7), (board[3][0], yb + 7)]),
                 alpha=0.45, blur=2)
        ic.outline(board, 3, (50, 34, 20, 140))
        y += slat + gap
    ic.outline(wall, 4)


def post(ic: Icon, x: float, y0: float, y1: float, w: float = 26) -> None:
    ic.rect((x - w / 2, y0, x + w / 2, y1), "#9a7048", "#4e3420", vertical=False, noise=0.25, edge=4)
    ic.shade(ic.mask("rectangle", (x - w / 2, y0, x + w / 2, y0 + 20)), alpha=0.3, blur=4)


def soft(m, r: float):
    return m.filter(ImageFilter.GaussianBlur(r))


def shingles(ic: Icon, pts, c1, c2, course: float = 30, span=(18, 42)) -> None:
    """Wooden shingle roof plane (replaces the kit's brick-like ``tiles``).

    Courses of irregular height, each shingle its own width and tone, joints that do not line up;
    no light gaps between courses: each course's butt casts a soft shadow onto the one below, so a
    course runs dark under the butt above to lighter at its own butt. Lit towards the ridge, a dark
    shadow line along the eave.
    """
    rnd = ic.random
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    top, bot = min(ys), max(ys)
    ic.fill(m, c1, c2, (top - course * 0.3, bot + course * 0.3), noise=0.24, chroma=0.12)
    rows, y = [], top + course * rnd.uniform(0.55, 0.85)
    while y < bot - course * 0.5:
        rows.append(y)
        y += course * rnd.uniform(0.84, 1.18)
    rows.append(bot + 6)
    tints, joints, butts = [], [], []
    prev = top - 6
    for y in rows:
        x = min(xs) - rnd.uniform(0, span[1])
        edge = []
        while x < max(xs) + 6:
            w = rnd.uniform(*span)
            yb = y + rnd.uniform(-4, 4)
            tints.append(((x, prev, x + w, yb), rnd.uniform(-1, 1)))
            joints.append(((x + w + rnd.uniform(-2, 2), prev + (y - prev) * rnd.uniform(0.3, 0.55)), (x + w, yb), rnd.randint(50, 100)))
            edge += [(x, yb), (x + w, yb)]
            x += w
        butts.append(edge)
        prev = y

    def paint(d):
        for box, t in tints:
            d.rectangle(box, fill=(255, 236, 205, int(t * 18)) if t > 0 else (20, 10, 4, int(-t * 36)))
        for p0, p1, a in joints:
            d.line([p0, p1], fill=(34, 18, 10, a), width=3)

    ic.overlay(paint, m)
    sh = Image.new("L", (SIZE, SIZE), 0)
    sd = ImageDraw.Draw(sh)
    for edge in butts[:-1]:
        sd.polygon(edge + [(x, y + course * 0.42) for x, y in edge[::-1]], fill=255)
    ic.shade(ic.intersect(m, soft(sh, 4)), (24, 12, 4), 0.48)
    ic.overlay(lambda d: [d.line(e, fill=(30, 16, 8, 120), width=3) for e in butts[:-1]], m)
    ic.shade(ic.intersect(m, soft(ic.mask("rectangle", (0, top - 10, SIZE, top + course * 1.1)), 10)),
             (255, 236, 196), 0.18)
    ic.shade(ic.intersect(m, soft(ic.mask("rectangle", (0, bot - course * 0.5, SIZE, bot + 10)), 4)),
             (16, 8, 2), 0.55)
    ic.outline(pts, 7)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84

    # yard ground behind everything
    top = [(30, 820)] + [(x, 806 + rnd.uniform(-8, 8)) for x in np.linspace(90, 940, 10)] + [(1000, 826)]
    ic.poly(top + [(1006, 980), (520, 994), (22, 982)], "#7a5e3e", "#4c3a26", noise=0.32, edge=3)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(830, 985)
        r = rnd.uniform(6, 14)
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.5, x + r, y + r * 0.5)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.18, blur=2)

    # ---- maize field behind the buildings: tassels rise above the roofs
    for x, h in ((260, 560), (440, 620), (620, 520), (800, 580)):
        maize(ic, x, 800, h, ears=1, lean=rnd.uniform(-20, 20), f=0.92, thin=True)
    ic.shade(ic.mask("rectangle", (0, 480, 1024, 820)), (8, 16, 4), 0.16, blur=40)  # darker low, behind the roofs

    # ---- farmhouse, left: daub walls in a timber frame, plank door, thatched roof
    HL, HR, HT, HB = 150, 590, 540, 850
    ic.plaster_frame((HL, HT, HR, HB), posts=(HL + 12, 330, 450, HR - 12), rails=(HT + 14,),
                     braces=(((HL + 12, HB - 10), (330, HT + 30)),), wall="#d2c29e", wall_dark="#a8966e")
    ic.shade(ic.mask("rectangle", (HL, HB - 60, HR, HB)), (60, 50, 20), 0.35, blur=16)  # grime low on the wall
    ic.door(480, 660, 556, HB - 4, arched=False, surround=None)
    ic.window(230, 630, 286, 686)
    ic.window(370, 630, 414, 680)
    thatch(ic, [(200, 360), (390, 352), (550, 362)],
           [(x, 562 + rnd.uniform(-5, 6)) for x in np.linspace(114, 630, 18)])
    ic.shade(ic.mask("rectangle", (HL, HT, HR, HT + 70)), alpha=0.5, blur=14)
    ic.shade(ic.poly_mask([(430, 330), (640, 330), (640, 580), (470, 580)]), alpha=0.1, blur=40)

    # ---- corn crib, right: raised on posts over stone pads, shingle roof
    CL, CR, CT, CB = 690, 950, 470, 800
    ic.shade(ic.mask("ellipse", (640, 856, 1010, 904)), alpha=0.5, blur=12)
    for x in (CL + 16, (CL + CR) / 2, CR - 16):
        ic.rock(ic.jitter(x, 876, 40, 20, 8, 0.1), "#9a9286", "#5e584e", facets=1)
        post(ic, x, CB - 10, 870, 30)
    ic.rect((CL - 10, CB - 8, CR + 10, CB + 14), "#8a6442", "#4a3220", edge=4)  # sill
    crib(ic, CL, CR, CT, CB - 8)
    for x in (CL - 20, CR + 20):  # corner posts follow the flare
        ic.beam((x, CT), (x + (10 if x < CL else -10) * 2.2, CB - 8), 18, (110, 78, 50))
    shingles(ic, [(CL - 60, CT + 10), (CR + 60, CT + 10), (CR + 6, CT - 118), (CL - 6, CT - 118)], "#9c6c4c",
             "#4e3020", course=28)
    ic.rect((CL - 10, CT - 128, CR + 10, CT - 112), "#7a5440", "#4e3428", edge=4)
    ic.shade(ic.mask("rectangle", (CL - 30, CT + 10, CR + 30, CT + 50)), alpha=0.4, blur=10)

    # ---- heap of husked ears and a basket at the crib's foot
    ic.shade(ic.mask("ellipse", (560, 950, 1010, 1000)), alpha=0.45, blur=8)
    for p, deg, k in (((600, 950), -12, KERNEL), ((720, 960), 190, KERNEL), ((660, 930), 8, KERNEL_RED),
                      ((780, 934), 186, KERNEL), ((620, 975), 4, KERNEL), ((730, 984), 176, KERNEL)):
        cob(ic, p, deg, 140, 54, kern=k, peel=rnd.random() < 0.6)
    ic.fill(ic.mask("ellipse", (842, 872, 1000, 908)), "#4a3018", "#2a1a0c")
    for p, deg in (((860, 896), -30), ((960, 890), 210), ((900, 900), -80)):
        cob(ic, p, deg, 110, 44, peel=False)
    ic.basket(840, 890, 1002, 996)

    # ---- maize standing at the left
    for x, h, ears, husked in ((70, 600, 2, True), (230, 540, 1, False)):
        hill(ic, x, 990, 170, 54)
        maize(ic, x, 984, h, ears=ears, lean=rnd.uniform(-20, 20), husked=husked)
