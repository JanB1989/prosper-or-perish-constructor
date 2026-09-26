"""Maize Rotation Farm: a red gambrel barn, the crib behind it, and the rotation of maize, beans and furrows in front.

Identity: the rotation takes the front third: a strip of separate yellow-green bush beans with pale
pods on a line of soil, then fresh furrows running towards the viewer with a wooden plough lying
across them as one diagonal; tall maize with opened golden ears on the left; behind, a barn-red
board barn shown gable end on (gambrel roof with shingled rakes, pale Z-braced doors, loft hatch),
the slatted corn crib of the farmstead tier half hidden behind it.

Local helpers (maize helpers shared by the four maize tiers): ``blade``, ``stalk``, ``tassel``,
``cob``, ``ear``, ``open_ear``, ``maize``, ``hill``; plus ``crib``, ``post``, ``shingles`` (irregular
wooden shingle roof, replaces the kit ``tiles``), ``rake`` (a shingle strip laid along a gable slope),
``boards`` (upright board wall), ``barn_doors``, ``bean_leaf``, ``pod``, ``bean``, ``furrows`` (ridges
running towards the viewer) and ``plough``.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/maize_rotations/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/maize_rotations
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 29
REFS = ('fiber_crops_farm', 'farming_village', 'grain_house', 'sheep_farms')

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


BEAN = ("#c2cc6c", "#5c6e22")  # lighter and yellower than the maize
POD = ("#e6e0a6", "#9a9056")


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
        ic.fill(ic.poly_mask(board), scaled("#9a7a52", tint), scaled("#56402a", tint), (x0, x1), vertical=False,
                noise=0.3)
        ic.shade(ic.poly_mask([board[0], board[1], (board[1][0], y + 5), (board[0][0], y + 5)]), (255, 240, 210), 0.25)
        ic.shade(ic.poly_mask([(board[3][0], yb + 1), (board[2][0], yb + 1), (board[2][0], yb + 7), (board[3][0], yb + 7)]),
                 alpha=0.45, blur=2)
        ic.outline(board, 3, (50, 34, 20, 140))
        y += slat + gap
    ic.outline(wall, 4)


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


def rake(ic: Icon, p0, p1, thick: float, c1, c2, seed: int) -> None:
    """One slope of a gable roof seen end-on: a strip of ``shingles`` laid along the roofline from
    ``p0`` to ``p1`` (left to right), lit outer edge, dark eave line against the wall below."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0
    L = float(np.hypot(*d)) + thick * 0.7
    sub = Icon(seed)
    c = SIZE / 2
    shingles(sub, [(c - L / 2, c - thick / 2), (c + L / 2, c - thick / 2), (c + L / 2, c + thick / 2),
                   (c - L / 2, c + thick / 2)], c1, c2, course=thick / 2.3, span=(14, 30))
    ang = math.degrees(math.atan2(-d[1], d[0]))
    n = np.array([d[1], -d[0]]) / np.hypot(*d)  # outward (up-and-away) normal
    mid = (p0 + p1) / 2 + n * (thick / 2 - 12)
    lay = sub.image.rotate(ang, resample=Image.BICUBIC, center=(c, c), translate=(mid[0] - c, mid[1] - c))
    ic.image.alpha_composite(lay)


def boards(ic: Icon, box, c=("#8a5e3c", "#4e3220"), w: float = 34, gap=(40, 24, 12, 170)) -> None:
    """Wall of upright boards with per-board tone, grain strokes and dark joints."""
    x0, y0, x1, y1 = box
    rnd = ic.random
    x = x0
    while x < x1:
        bw = min(w * rnd.uniform(0.85, 1.15), x1 - x)
        t = rnd.uniform(0.88, 1.1)
        ic.fill(ic.mask("rectangle", (x, y0, x + bw, y1)), scaled(c[0], t), scaled(c[1], t), (y0, y1), noise=0.3)

        def grain(dr, x=x, bw=bw):
            for _ in range(5):
                gx = x + rnd.uniform(4, bw - 4)
                dr.line([(gx, y0 + rnd.uniform(0, 40)), (gx + rnd.uniform(-3, 3), y1 - rnd.uniform(0, 60))],
                        fill=(40, 24, 12, 60), width=2)

        ic.overlay(grain)
        ic.line([(x, y0), (x, y1)], 5, gap)
        x += bw


def barn_doors(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Pair of pale weathered plank doors with dark board gaps and Z braces, the right leaf ajar."""
    mid = (x0 + x1) / 2
    ic.rect((x0 - 14, y0 - 14, x1 + 14, y1), "#2a1a10", "#140c06", edge=0)
    ic.rect((x0, y0, x1, y1), "#1e140c", "#0e0804", edge=0)
    for lx0, lx1 in ((x0, mid - 3), (mid + 3 + (x1 - mid) * 0.22, x1 + 6)):
        boards(ic, (lx0, y0, lx1, y1), c=("#cdbd98", "#8a7a5c"), w=24, gap=(34, 24, 14, 230))
        for p, q in (((lx0 + 6, y0 + 22), (lx1 - 6, y0 + 22)), ((lx0 + 6, y1 - 26), (lx1 - 6, y1 - 26)),
                     ((lx0 + 12, y1 - 34), (lx1 - 12, y0 + 30))):
            ic.line([p, q], 20, (56, 40, 26, 230))
            ic.line([p, q], 12, (196, 180, 146))
        ic.shade(ic.mask("rectangle", (lx0, y0, lx1, y0 + 30)), alpha=0.35, blur=6)
        ic.outline([(lx0, y0), (lx1, y0), (lx1, y1), (lx0, y1)], 5)
    ic.shade(ic.mask("rectangle", (mid + 3 + (x1 - mid) * 0.22, y0, mid + 3 + (x1 - mid) * 0.22 + 26, y1)),
             alpha=0.4, blur=6)  # the open leaf's edge
    ic.beam((x0 - 18, y0 - 10), (x1 + 18, y0 - 10), 18, (120, 84, 54))


def bean_leaf(ic: Icon, base, deg: float, length: float, colors=None) -> None:
    """Broad pointed bean leaflet, lit from the upper left, darker half along the midrib."""
    colors = colors or BEAN
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 16)
    hw = [length * 0.38 * math.sin(math.pi * t ** 0.7) for t in ts]
    s1 = [b + d * length * t + n * w for t, w in zip(ts, hw)]
    s2 = [b + d * length * t - n * w for t, w in zip(ts, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    ic.fill(ic.poly_mask(pts), colors[0], colors[1], radial=(min(p[0] for p in pts), min(p[1] for p in pts),
                                                             length * 1.5), noise=0.22, chroma=0.12)
    ic.shade(ic.poly_mask([tuple(p) for p in (s1 if n[1] > 0 else s2)] + [tuple(b + d * length * t) for t in ts[::-1]]),
             (20, 24, 4), 0.26)
    ic.line([tuple(b + d * length * t) for t in (0.05, 0.8)], 3, (220, 226, 160, 120))
    ic.outline(pts, 3, (30, 40, 10, 150))


def pod(ic: Icon, px: float, py: float, dx: float, ln: float) -> None:
    pts = [(px - 9, py), (px + 9, py), (px + dx + 8, py + ln), (px + dx - 3, py + ln + 8)]
    ic.poly(pts, POD[0], POD[1], edge=4)
    ic.line([(px - 2, py + 4), (px + dx * 0.8 - 1, py + ln * 0.8)], 4, (250, 246, 200, 150))


def bean(ic: Icon, x: float, base: float, s: float) -> None:
    """Bush bean: a separate, rounded mound of yellow-green trifoliate leaves with pale pods."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (x - s * 1.0, base - 14, x + s * 1.0, base + 12)), alpha=0.5, blur=6)
    ic.fill(ic.mask("ellipse", (x - s * 0.8, base - s * 0.95, x + s * 0.8, base + 4)), "#4a5a1c", "#1e2808",
            (base - s, base))
    clusters = sorted([(x + rnd.uniform(-s * 0.55, s * 0.55), base - s * rnd.uniform(0.3, 0.85)) for _ in range(6)],
                      key=lambda p: p[1])
    for cx, cy in clusters:  # leaf clusters of three leaflets, back (high) to front (low)
        a0 = rnd.uniform(-120, -60)
        f = 0.86 + 0.28 * (cx < x)  # the left half faces the light
        cols = (scaled(BEAN[0], f), scaled(BEAN[1], f))
        for da in (-70, 0, 70):
            bean_leaf(ic, (cx, cy), a0 + da + rnd.uniform(-10, 10), s * rnd.uniform(0.5, 0.62), cols)
    for k in range(4):  # short pale pods hanging among the lower leaves
        px = x + s * (-0.5 + 0.33 * k) + rnd.uniform(-8, 8)
        pod(ic, px, base - s * rnd.uniform(0.5, 0.62), (1 if k % 2 else -1) * s * 0.1, s * 0.34)


def furrows(ic: Icon, pts, y0: float, y1: float, vp=(640, 250), step: float = 46) -> None:
    """Ploughed land seen from the front: ridges and furrows running towards the viewer, each ridge
    lit on its left flank, each furrow in deep shadow, clods scattered over them."""
    m = ic.poly_mask(pts)
    ic.fill(m, "#6c4c30", "#4a3220", (y0, y1), noise=0.32)
    k0, k1 = (y0 - vp[1]), (y1 + 20 - vp[1])
    xs = [p[0] for p in pts]

    def at(xt, y):  # x on the line through the top-edge point xt, converging on the vanishing point
        return vp[0] + (xt - vp[0]) * (y - vp[1]) / k0

    lit, dark = Image.new("L", (SIZE, SIZE), 0), Image.new("L", (SIZE, SIZE), 0)
    dl, dd = ImageDraw.Draw(lit), ImageDraw.Draw(dark)
    for xt in np.arange(min(xs) - 120, max(xs) + 120, step):
        q = lambda f, y: at(xt + step * f, y)
        dl.polygon([(q(0.05, y0), y0), (q(0.45, y0), y0), (q(0.45, y1 + 20), y1 + 20), (q(0.05, y1 + 20), y1 + 20)],
                   fill=255)
        dd.polygon([(q(0.55, y0), y0), (q(0.95, y0), y0), (q(0.95, y1 + 20), y1 + 20), (q(0.55, y1 + 20), y1 + 20)],
                   fill=255)
    ic.shade(ic.intersect(m, soft(lit, 3)), (255, 222, 170), 0.42)
    ic.shade(ic.intersect(m, soft(dark, 3)), (14, 6, 0), 0.62)
    ic.shade(ic.intersect(m, soft(ic.mask("rectangle", (0, y0 - 10, SIZE, y0 + 26)), 8)), (10, 6, 0), 0.45)
    for _ in range(46):
        x, yy = ic.random.uniform(min(xs), max(xs)), ic.random.uniform(y0, y1)
        r = ic.random.uniform(5, 11)
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - r, yy - r * 0.6, x + r, yy + r * 0.6))),
                 (255, 230, 190) if ic.random.random() < 0.4 else (0, 0, 0), 0.3)
    ic.outline(pts, 3)


def plough(ic: Icon, share, s: float) -> None:
    """Wooden plough resting in the furrow as one diagonal: the beam slopes down to the front left,
    the handles rise on up to the right; iron share and mouldboard at the foot."""
    sx, sy = share
    wood, rim, glint = (178, 132, 82), (54, 34, 18), (224, 188, 134, 190)
    ic.shade(ic.poly_mask([(sx - s * 0.85, sy + s * 0.16), (sx + s * 0.1, sy + 10), (sx + s * 0.1, sy + 30),
                           (sx - s * 0.85, sy + s * 0.22)]), alpha=0.4, blur=8)
    beam = [(sx - s * 0.85, sy + s * 0.12), (sx + s * 0.08, sy - s * 0.2)]
    ic.line(beam, 34, rim)
    ic.line(beam, 22, wood)
    ic.line([(p[0], p[1] - 6) for p in beam], 7, glint)
    ic.poly([(sx - s * 0.2, sy + 6), (sx + s * 0.1, sy - s * 0.04), (sx + s * 0.24, sy - s * 0.26),
             (sx - s * 0.02, sy - s * 0.3)], "#9a7650", "#4e3620", edge=5)  # mouldboard
    ic.poly([(sx - s * 0.34, sy + 10), (sx - s * 0.1, sy - s * 0.1), (sx - s * 0.02, sy + 10)],
            "#b4b4b8", "#4e4e54", edge=5)  # share
    for dx in (s * 0.16, 0):
        h = [(sx + dx - s * 0.02, sy - s * 0.1), (sx + dx + s * 0.42, sy - s * 0.66)]
        ic.line(h, 30, rim)
        ic.line(h, 19, wood)
        ic.line([(p[0] - 4, p[1] - 3) for p in h], 6, glint)
    ic.line([(sx + s * 0.26, sy - s * 0.46), (sx + s * 0.46, sy - s * 0.46)], 16, rim)
    ic.line([(sx + s * 0.26, sy - s * 0.46), (sx + s * 0.46, sy - s * 0.46)], 9, wood)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.64
    ic.grade["mute"] = 0.84

    # ---- corn crib behind the barn, right: only its slatted upper half and roof show
    CL, CR, CT, CB = 800, 950, 500, 800
    crib(ic, CL, CR, CT, CB, flare=16)
    for x in (CL - 16, CR + 16):
        ic.beam((x, CT), (x + (10 if x < CL else -10) * 1.6, CB), 16, (110, 78, 50))
    shingles(ic, [(CL - 46, CT + 8), (CR + 46, CT + 8), (CR, CT - 92), (CL, CT - 92)], "#9c6c4c", "#4e3020",
             course=26)
    ic.shade(ic.mask("rectangle", (CL - 20, CT + 8, CR + 20, CT + 44)), alpha=0.4, blur=10)

    # ---- the barn: a red board gable end with a gambrel roof, pale doors, loft hatch
    BL, BR, EY, BB = 330, 760, 590, 846
    cx = (BL + BR) / 2
    kl, kr, pk = (BL + 64, 430), (BR - 64, 430), (cx, 318)
    wall = [(BL, BB), (BL, EY), kl, pk, kr, (BR, EY), (BR, BB)]
    W = ic.poly_mask(wall)
    ic.shade(ic.poly_mask([(BR - 40, 460), (1000, 520), (1000, 860), (BR, 860)]), alpha=0.3, blur=30)  # on the crib
    with ic.clipped(W):
        boards(ic, (BL, pk[1] - 10, BR, BB), c=("#b04a30", "#6a2216"), w=32)
        ic.line([(BL - 10, EY + 4), (BR + 10, EY + 4)], 16, (70, 26, 16))  # girt between loft and ground floor
        ic.line([(BL - 10, EY), (BR + 10, EY)], 8, (170, 80, 56))
    for x, lit in ((BL + 13, True), (BR - 13, False)):  # corner boards
        ic.rect((x - 13, EY - 10, x + 13, BB), "#d8c8a6" if lit else "#9a8a6e", "#a8987a" if lit else "#6a5c48",
                edge=4)
    ic.shade(ic.intersect(W, ic.mask("rectangle", (BL, 0, BL + 60, BB))), (255, 224, 190), 0.22, blur=10)  # lit rim
    ic.shade(ic.intersect(W, ic.mask("rectangle", (cx, 0, BR, BB))), alpha=0.12, blur=30)
    # loft hatch in the gable
    ic.rect((cx - 46, 440, cx + 46, 546), "#2a1a10", "#120a06", edge=0)
    boards(ic, (cx - 40, 446, cx + 40, 540), c=("#c4b490", "#86765a"), w=20, gap=(34, 24, 14, 230))
    ic.line([(cx, 446), (cx, 540)], 7, (20, 12, 6))
    ic.line([(cx - 36, 530), (cx + 36, 456)], 16, (56, 40, 26, 230))
    ic.line([(cx - 36, 530), (cx + 36, 456)], 9, (190, 174, 140))
    ic.shade(ic.mask("rectangle", (cx - 40, 446, cx + 40, 470)), alpha=0.4, blur=5)
    ic.outline([(cx - 46, 440), (cx + 46, 440), (cx + 46, 546), (cx - 46, 546)], 5)
    barn_doors(ic, cx - 104, 636, cx + 104, BB - 2)
    ic.shade(ic.intersect(W, ic.mask("rectangle", (BL, BB - 60, BR, BB))), (50, 30, 10), 0.4, blur=14)  # grime
    ic.outline(wall, 6)
    # gambrel roof ends, shingled, with a dark shadow line on the wall under them
    under = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(under).line([(BL - 20, EY + 26), kl, pk, kr, (BR + 20, EY + 26)], fill=255, width=70)
    ic.shade(ic.intersect(W, soft(under, 10)), (20, 6, 2), 0.5)
    lit, dim = ("#aa7a58", "#5a3824"), ("#8a5e44", "#44281a")
    rake(ic, (BL - 40, EY + 34), kl, 64, *lit, seed=5)
    rake(ic, kr, (BR + 40, EY + 34), 64, *dim, seed=6)
    rake(ic, kl, (pk[0] + 10, pk[1] + 8), 64, *lit, seed=7)
    rake(ic, (pk[0] - 10, pk[1] + 8), kr, 64, *dim, seed=8)
    ic.poly([(pk[0] - 34, pk[1] - 40), (pk[0] + 34, pk[1] - 40), (pk[0] + 22, pk[1] - 14), (pk[0] - 22, pk[1] - 14)],
            "#8a5e44", "#4e3222", edge=5)  # ridge cap

    # ---- the rotation in front: separate bush beans on a strip of soil, then fresh furrows
    ic.poly([(290, 836), (1010, 832), (1014, 904), (286, 906)], "#5a4028", "#3a2818", noise=0.3, edge=3)
    for x, s in ((420, 104), (600, 96), (770, 108), (935, 92)):
        bean(ic, x + rnd.uniform(-8, 8), 890, s)
    ic.line([(290, 904), (1012, 900)], 12, (44, 28, 14))  # soil line under the beans
    furrows(ic, [(282, 906), (1014, 902), (1018, 1010), (272, 1012)], 906, 1010)
    plough(ic, (770, 972), 300)

    # ---- maize block on the left, behind and in front
    for x, h in ((80, 540), (210, 590)):
        maize(ic, x, 880, h, ears=1, lean=rnd.uniform(-20, 20), f=0.88)
    ic.shade(ic.mask("rectangle", (0, 500, 330, 900)), (8, 16, 4), 0.14, blur=40)
    for x, h, ears, husked in ((60, 640, 2, True), (200, 600, 2, False), (320, 520, 1, False)):
        hill(ic, x, 996, 150, 46)
        maize(ic, x, 990, h, ears=ears, lean=rnd.uniform(-20, 20), husked=husked)
