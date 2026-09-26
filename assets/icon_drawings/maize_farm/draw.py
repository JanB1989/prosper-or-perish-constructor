"""Maize Field: an open field of tall maize on hoed hills, a basket of picked ears and a hoe.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/maize_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/maize_farm

Identity: tall maize stalks with arching ribbon leaves, pale tassels and ears in the husk, each
stand on its own hoed hill of earth (the first tier of the maize chain has no building); a wicker
basket of husked golden ears and a hand hoe at the bottom right.

Local helpers (shared by the four maize tiers): ``blade`` (long arching maize leaf, tone-shaded
fold, pale midrib), ``stalk``, ``tassel``, ``ear`` (ear in the husk with silk, or husked cob with
kernel rows), ``open_ear`` (ripe ear with split husk), ``maize`` (whole plant), ``hill`` (hoed mound).
"""

import math

import numpy as np
from PIL import Image

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 11
REFS = ("fiber_crops_farm", "farming_village", "sugar_plantation", "fruit_orchard")

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


def tassel(ic: Icon, top, size: float, f: float = 1.0) -> None:
    """Pale branched tassel: a central spike and side branches that rise and arch outwards."""
    tx, ty = top
    lit, dk = scaled(TASSEL[0], f), scaled(TASSEL[1], f)
    rnd = ic.random
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
          husked: bool = False) -> None:
    """One maize plant: back leaves, stalk, alternating arching leaves, ears, tassel on top."""
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
    tassel(ic, top, h * 0.16, f)


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


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.56
    ic.grade["mute"] = 0.84

    # hoed ground: a band of loose earth
    top = [(24, 832)] + [(x, 806 + rnd.uniform(-10, 10)) for x in np.linspace(80, 940, 12)] + [(1000, 830)]
    ground = top + [(1010, 980), (520, 996), (16, 982)]
    ic.poly(ground, "#76593a", "#4a3924", noise=0.32, edge=3)
    for _ in range(50):
        x, y = rnd.uniform(40, 990), rnd.uniform(830, 985)
        r = rnd.uniform(6, 14)
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.5, x + r, y + r * 0.5)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.18, blur=2)

    # far row: a dark wall of maize
    for x, h in ((90, 420), (300, 450), (520, 430), (740, 410), (930, 380)):
        maize(ic, x, 800, h, ears=0, lean=rnd.uniform(-20, 20), f=0.62)
    ic.shade(ic.mask("rectangle", (0, 500, 1024, 820)), (8, 16, 4), 0.18, blur=40)
    # back row of hills and plants, darker and smaller
    for x, h in ((200, 470), (420, 520), (640, 480), (850, 430)):
        hill(ic, x, 842, 160, 46)
        maize(ic, x, 834, h, ears=1, lean=rnd.uniform(-20, 20), f=0.8)
    ic.shade(ic.mask("rectangle", (0, 700, 1024, 900)), (8, 16, 4), 0.22, blur=40)

    # front row
    for x, h, ears, husked in ((110, 580, 2, False), (330, 640, 2, True), (555, 590, 1, False)):
        hill(ic, x, 948, 200, 62)
        maize(ic, x, 940, h, ears=ears, lean=rnd.uniform(-25, 25), husked=husked)
        ic.shade(ic.mask("ellipse", (x - 80, 920, x + 120, 960)), alpha=0.3, blur=10)

    # prop, bottom right: a basket of husked ears and a hoe leaning on it
    ic.line([(976, 640), (872, 960)], 18, (70, 48, 28))
    ic.line([(973, 640), (869, 960)], 10, (156, 118, 74))
    ic.poly([(846, 936), (900, 950), (890, 1004), (826, 994)], "#86868a", "#3a3a3e", edge=4)
    ic.shade(ic.mask("ellipse", (660, 964, 1020, 1010)), alpha=0.5, blur=8)
    ic.fill(ic.mask("ellipse", (686, 836, 990, 900)), "#4a3018", "#2a1a0c")
    for p, deg, k in (((700, 870), -24, KERNEL), ((930, 866), 204, KERNEL_RED), ((752, 888), -12, KERNEL),
                      ((962, 890), 188, KERNEL), ((820, 862), -60, KERNEL), ((860, 896), 180, KERNEL)):
        cob(ic, p, deg, 170, 62, kern=k, peel=rnd.random() < 0.5)
    ic.basket(680, 872, 996, 1004)
