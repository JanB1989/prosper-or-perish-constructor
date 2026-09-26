"""Maize Model Farm: the largest barn of the chain, stone below and weatherboarded above, with a cupola and hay hood.

Identity: the biggest building of the maize chain, a wide barn with a rubble-stone ground storey and
a wide square-headed cart door of plank leaves under a timber lintel, a vertically weatherboarded
loft with a hay hood, hoist beam, rope and hook over the loft door, and a long shingle roof with a
louvred cupola; right of it the planned corn crib raised on stone piers, big sacks of shelled maize
and husked ears in the yard; tall maize in straight, even rows on the left.

Local helpers (maize helpers shared by the four maize tiers): ``blade``, ``stalk``, ``tassel``,
``cob``, ``ear``, ``open_ear``, ``maize``, ``hill``; plus ``crib``, ``post``, ``rubble`` (coursed
rubble wall), ``cupola``, ``grain_sack`` (open sack of shelled maize), ``shingles`` (irregular wooden
shingle roof, replaces the kit ``tiles``), ``boards`` (weatherboarding), ``cart_door`` and ``hay_hood``.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/maize_model_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/maize_model_farm
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 37
REFS = ('local_estates', 'farming_village', 'granary', 'fiber_crops_farm')

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


def post(ic: Icon, x: float, y0: float, y1: float, w: float = 26) -> None:
    ic.rect((x - w / 2, y0, x + w / 2, y1), "#9a7048", "#4e3420", vertical=False, noise=0.25, edge=4)
    ic.shade(ic.mask("rectangle", (x - w / 2, y0, x + w / 2, y0 + 20)), alpha=0.3, blur=4)


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
        ic.fill(ic.poly_mask(board), scaled("#a0805a", tint), scaled("#5a432c", tint), (x0, x1), vertical=False,
                noise=0.3)
        ic.shade(ic.poly_mask([board[0], board[1], (board[1][0], y + 5), (board[0][0], y + 5)]), (255, 240, 210), 0.25)
        ic.shade(ic.poly_mask([(board[3][0], yb + 1), (board[2][0], yb + 1), (board[2][0], yb + 7), (board[3][0], yb + 7)]),
                 alpha=0.45, blur=2)
        ic.outline(board, 3, (50, 34, 20, 140))
        y += slat + gap
    ic.outline(wall, 4)


def rubble(ic: Icon, box, base="#b0a490", dark="#7c725f") -> None:
    """Coursed rubble stone wall: irregular stones shaded as forms, mortar between them, grime low down."""
    x0, y0, x1, y1 = box
    rnd = ic.random
    ic.rect(box, "#8a8070", "#5e564a", edge=0)
    y = y0 + 4
    while y < y1:
        h = rnd.uniform(30, 44)
        x = x0 - rnd.uniform(0, 40)
        while x < x1:
            w = rnd.uniform(48, 90)
            pts = [(max(x0, min(x1, px)), min(y1, py)) for px, py in
                   ic.jitter(x + w / 2, y + h / 2, w / 2 - 4, h / 2 - 3, 8, 0.1)]
            t = rnd.uniform(0.86, 1.1)
            ic.fill(ic.poly_mask(pts), scaled(base, t), scaled(dark, t), radial=(x, y, w * 1.1), noise=0.25)
            ic.outline(pts, 3, (60, 54, 46, 150))
            x += w
        y += h
    ic.shade(ic.mask("rectangle", (x0, y1 - 60, x1, y1)), (50, 50, 20), 0.35, blur=16)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def cupola(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Louvred ventilation cupola on the barn ridge with a small pyramid roof."""
    ic.rect((cx - w / 2, base - h, cx + w / 2, base), "#3a2819", "#1f150e", edge=0)
    for y in np.arange(base - h + 10, base - 4, 16):
        ic.line([(cx - w / 2 + 8, y), (cx + w / 2 - 8, y + 6)], 9, (170, 140, 104))
    for x in (cx - w / 2 + 6, cx + w / 2 - 6):
        ic.line([(x, base - h), (x, base)], 12, (140, 110, 80))
    ic.outline([(cx - w / 2, base - h), (cx + w / 2, base - h), (cx + w / 2, base), (cx - w / 2, base)])
    ic.poly([(cx - w / 2 - 22, base - h + 4), (cx + w / 2 + 22, base - h + 4), (cx, base - h - h * 0.9)],
            "#a0765a", "#5a3a28")
    ic.shade(ic.poly_mask([(cx, base - h - h * 0.9), (cx + w / 2 + 22, base - h + 4), (cx + 4, base - h + 4)]),
             alpha=0.3)
    ic.line([(cx, base - h - h * 0.9), (cx, base - h - h * 1.25)], 6, (60, 60, 64))


def grain_sack(ic: Icon, cx: float, base: float, w: float, h: float, color) -> None:
    """Open sack of shelled maize: bulging body lit from the upper left, rolled rim, golden grain on top."""
    ts = np.linspace(0, 1, 14)
    left = [(cx - w * 0.5 * (0.82 + 0.18 * math.sin(math.pi * t)), base - h * t) for t in ts]
    right = [(cx + w * 0.5 * (0.82 + 0.18 * math.sin(math.pi * t)), base - h * t) for t in ts[::-1]]
    body = [(x + ic.random.uniform(-3, 3), y) for x, y in left + right]
    dark = tuple(int(v * 0.5) for v in rgb(color))
    ic.fill(ic.poly_mask(body), color, dark, radial=(cx - w * 0.4, base - h, w * 1.3), noise=0.3)
    for k in range(3):  # folds
        x = cx - w * 0.25 + k * w * 0.22
        ic.line([(x, base - h * 0.85), (x + ic.random.uniform(-8, 8), base - h * 0.2)], 4, (60, 40, 20, 90))
    ic.outline(body, 3, (40, 28, 16, 150))
    top = (cx - w * 0.44, base - h - 14, cx + w * 0.44, base - h + 14)
    ic.fill(ic.mask("ellipse", top), "#f2c65a", "#a86c18", (top[1], top[3]), noise=0.45)

    def kernels(dr):
        for _ in range(40):
            x = ic.random.uniform(top[0] + 8, top[2] - 8)
            y = ic.random.uniform(top[1] + 4, top[3] - 4)
            dr.ellipse((x - 4, y - 3, x + 4, y + 3), fill=(120, 70, 14, 150) if ic.random.random() < 0.5 else
                       (255, 226, 130, 170))

    ic.overlay(kernels, ic.mask("ellipse", top))
    ic.overlay(lambda d: d.arc(top, 0, 360, fill=(90, 66, 36, 255), width=8))


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
            joints.append(((x + w + rnd.uniform(-2, 2), prev + (y - prev) * rnd.uniform(0.3, 0.55)), (x + w, yb),
                           rnd.randint(50, 100)))
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


def boards(ic: Icon, box, c=("#8e6c4a", "#523a24"), w: float = 30, gap=(34, 22, 12, 190)) -> None:
    """Vertical weatherboarding: upright boards with per-board tone, grain strokes and dark joints."""
    x0, y0, x1, y1 = box
    rnd = ic.random
    x = x0
    while x < x1:
        bw = min(w * rnd.uniform(0.85, 1.15), x1 - x)
        t = rnd.uniform(0.88, 1.1)
        ic.fill(ic.mask("rectangle", (x, y0, x + bw, y1)), scaled(c[0], t), scaled(c[1], t), (y0, y1), noise=0.3)

        def grain(dr, x=x, bw=bw):
            for _ in range(4):
                gx = x + rnd.uniform(4, bw - 4)
                dr.line([(gx, y0 + rnd.uniform(0, 30)), (gx + rnd.uniform(-3, 3), y1 - rnd.uniform(0, 40))],
                        fill=(40, 24, 12, 60), width=2)

        ic.overlay(grain)
        ic.line([(x, y0), (x, y1)], 5, gap)
        x += bw


def cart_door(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Wide square-headed cart door in the stone storey: timber lintel, two plank leaves with dark
    board gaps and iron strap hinges, the right leaf swung a little open on the dark barn floor."""
    mid = (x0 + x1) / 2
    ic.rect((x0, y0, x1, y1), "#1c120a", "#0c0804", edge=0)
    for lx0, lx1, open_ in ((x0, mid - 2, False), (mid + 2 + (x1 - mid) * 0.18, x1, True)):
        boards(ic, (lx0, y0, lx1, y1), c=("#bc9464", "#6c4c2c"), w=26, gap=(30, 18, 8, 230))
        for y in (y0 + 34, y1 - 40):  # strap hinges
            ic.line([(lx0 + 6, y), (lx1 - 6, y)] if not open_ else [(lx1 - 6, y), (lx0 + 6, y)], 10, (44, 42, 44))
        ic.shade(ic.mask("rectangle", (lx0, y0, lx1, y0 + 34)), alpha=0.45, blur=6)
        ic.outline([(lx0, y0), (lx1, y0), (lx1, y1), (lx0, y1)], 5)
    ic.shade(ic.mask("rectangle", (mid + 2 + (x1 - mid) * 0.18, y0, mid + 2 + (x1 - mid) * 0.18 + 24, y1)),
             alpha=0.4, blur=6)
    for x in (x0 - 34, x1):  # dressed stone jambs
        y = y0
        k = 0
        while y < y1:
            h = 44
            w = 34 + (10 if k % 2 else 0)
            bx = (x, y, x + 34, min(y + h, y1)) if x > x0 else (x0 - w, y, x0, min(y + h, y1))
            ic.rect(bx, "#c4b8a2", "#8c8272", edge=4)
            y += h
            k += 1
    ic.rect((x0 - 50, y0 - 36, x1 + 50, y0), "#8a6442", "#4a3220", edge=5)  # timber lintel
    ic.shade(ic.mask("rectangle", (x0 - 50, y0 - 36, x1 + 50, y0 - 26)), (255, 236, 200), 0.25)


def hay_hood(ic: Icon, hx: float, eave: float, door_top: float) -> None:
    """Hay hood over the loft door: a small weatherboarded gable breaking the eave with its own
    shingled rakes; under its apex the hoist beam end, a pulley block, rope and hook."""
    apex = eave - 104
    tri = [(hx - 74, eave + 22), (hx, apex), (hx + 74, eave + 22)]
    T = ic.poly_mask(tri)
    ic.shade(ic.poly_mask([(hx - 60, eave + 10), (hx + 110, eave + 10), (hx + 110, eave + 70), (hx - 60, eave + 70)]),
             alpha=0.35, blur=12)
    with ic.clipped(T):
        boards(ic, (hx - 80, apex, hx + 80, eave + 24), c=("#b49e7e", "#6a5a44"), w=24)
        ic.shade(ic.mask("rectangle", (hx, apex, hx + 80, eave + 24)), alpha=0.18)
    ic.outline(tri, 5)
    for side, col in ((-1, (182, 120, 80)), (1, (130, 80, 54))):
        rake = [(hx + side * 104, eave + 40), (hx + side * 4, apex - 14)]
        ic.line(rake, 40, (40, 22, 12))
        ic.line(rake, 30, col)
        ic.line([(x, y + 12) for x, y in rake], 6, (60, 34, 20, 170))  # shingle course
    ic.poly([(hx - 22, apex - 30), (hx + 22, apex - 30), (hx + 16, apex - 8), (hx - 16, apex - 8)], "#8e5a42",
            "#5e3a2a", edge=4)
    by = eave - 34  # hoist beam end, pulley, rope and hook
    ic.rect((hx - 20, by - 18, hx + 20, by + 18), "#b08458", "#5e4028", edge=5)
    ic.overlay(lambda d: d.ellipse((hx - 11, by - 10, hx + 11, by + 10), outline=(80, 52, 30, 200), width=3))
    ic.rect((hx - 12, by + 22, hx + 12, by + 52), "#8a6a48", "#4a3420", edge=4)
    for dx in (-6, 6):
        ic.line([(hx + dx, by + 52), (hx + dx * 0.5, door_top + 26)], 7, (40, 30, 18))
        ic.line([(hx + dx, by + 52), (hx + dx * 0.5, door_top + 26)], 3, (206, 180, 128))
    ic.overlay(lambda d: d.arc((hx - 14, door_top + 18, hx + 10, door_top + 44), 20, 250, fill=(50, 50, 54, 255),
                               width=7))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.64
    ic.grade["mute"] = 0.84

    # yard
    ic.poly([(170, 846), (1006, 838), (1012, 994), (170, 1000)], "#7e6444", "#50402a", noise=0.3, edge=3)

    # ---- the big barn: rubble-stone ground storey, weatherboarded loft, long roof with a cupola
    BL, BR, ET, ST, BB = 196, 832, 450, 636, 866
    cx = (BL + BR) / 2
    cupola(ic, cx, 262, 100, 80)
    shingles(ic, [(BL - 56, ET + 14), (BR + 56, ET + 14), (BR - 34, 256), (BL + 34, 256)], "#bc6e48", "#62301c",
             course=32)
    ic.rect((BL + 18, 244, BR - 18, 262), "#8e5a42", "#5e3a2a", edge=5)  # ridge
    # loft: vertical weatherboarding between corner posts, loft door and hay hoist
    boards(ic, (BL, ET, BR, ST), c=("#aa9476", "#645240"))
    for x in (BL + 12, BR - 12):
        ic.beam((x, ET), (x, ST), 24)
    ic.shade(ic.mask("rectangle", (BL, ET, BL + 70, ST)), (255, 226, 190), 0.16, blur=12)
    DX = cx + 76  # cart door, loft door and hay hood sit right of centre, clear of the maize
    LD0, LD1 = DX - 50, DX + 50
    ic.rect((LD0 - 8, ET + 70, LD1 + 8, ST - 2), "#6a4a30", "#3a2818", edge=4)
    ic.rect((LD0, ET + 78, LD1, ST - 2), "#22160c", "#0e0804", edge=0)
    boards(ic, (LD0, ET + 78, LD0 + 38, ST - 2), c=("#b08a5e", "#6a4c30"), w=19)
    ic.outline([(LD0, ET + 78), (LD1, ET + 78), (LD1, ST - 2), (LD0, ST - 2)], 5)
    for vx in (BL + 90, BR - 90):  # louvred vents
        ic.rect((vx - 18, 520, vx + 18, 590), "#2e1e10", "#140c06", edge=4)
        for y in (534, 552, 570):
            ic.line([(vx - 14, y), (vx + 14, y + 6)], 7, (140, 110, 80))
    ic.shade(ic.mask("rectangle", (BL - 10, ET, BR + 10, ET + 70)), alpha=0.55, blur=14)  # eave shadow on the loft
    hay_hood(ic, DX, ET + 14, ET + 78)
    rubble(ic, (BL, ST, BR, BB))
    ic.rect((BL - 8, ST - 8, BR + 8, ST + 12), "#8a6442", "#4a3220", edge=4)  # sill beam
    cart_door(ic, DX - 124, 712, DX + 124, BB - 2)
    for vx in (BL + 160, BR - 40):  # slit vents
        ic.rect((vx - 10, 700, vx + 10, 790), "#2e1e10", "#140c06", edge=4)
    ic.shade(ic.poly_mask([(640, 250), (900, 250), (900, 880), (700, 880)]), alpha=0.14, blur=50)

    # ---- the long crib on stone piers, right
    CL, CR, CT, CB = 870, 994, 560, 806
    ic.shade(ic.mask("ellipse", (820, 858, 1016, 900)), alpha=0.5, blur=10)
    for x in (CL + 12, CR - 12):
        rubble(ic, (x - 20, CB - 6, x + 20, 872))
    ic.rect((CL - 12, CB - 10, CR + 12, CB + 10), "#8a6442", "#4a3220", edge=4)
    crib(ic, CL, CR, CT, CB - 8, flare=14)
    for x in (CL - 14, CR + 14):
        ic.beam((x, CT), (x + (10 if x < CL else -10) * 1.4, CB - 8), 16, (110, 78, 50))
    shingles(ic, [(CL - 40, CT + 8), (CR + 26, CT + 8), (CR - 4, CT - 92), (CL, CT - 92)], "#bc6e48", "#62301c",
             course=26)
    ic.shade(ic.mask("rectangle", (CL - 20, CT + 8, CR + 20, CT + 44)), alpha=0.4, blur=10)

    # ---- big sacks of shelled maize and a heap of ears in the yard
    ic.shade(ic.mask("ellipse", (560, 950, 1016, 1008)), alpha=0.45, blur=8)
    for p, deg, k in (((580, 970), -10, KERNEL), ((650, 986), 188, KERNEL), ((610, 950), 6, KERNEL_RED)):
        cob(ic, p, deg, 130, 50, kern=k, peel=True)
    for cx_, base, w, h, col in ((742, 1000, 134, 136, "#c2a068"), (870, 1002, 150, 160, "#c8a46a"),
                                  (980, 1004, 110, 118, "#b89258")):
        grain_sack(ic, cx_, base, w, h, col)
    for _ in range(26):  # spilled kernels
        x, y = rnd.uniform(700, 1000), rnd.uniform(996, 1010)
        ic.fill(ic.mask("ellipse", (x - 6, y - 4, x + 6, y + 4)), "#e8b848", "#8a5a14", noise=0.2)

    # ---- maize in straight, even rows on the left
    for x in (40, 150, 260):
        maize(ic, x, 880, 560, ears=1, lean=rnd.uniform(-8, 8), f=0.88)
    ic.shade(ic.mask("rectangle", (0, 560, 330, 900)), (8, 16, 4), 0.12, blur=40)
    for x, husked in ((80, True), (200, False), (310, True)):
        hill(ic, x, 996, 130, 40)
        maize(ic, x, 990, 600, ears=2, lean=rnd.uniform(-8, 8), husked=husked)
