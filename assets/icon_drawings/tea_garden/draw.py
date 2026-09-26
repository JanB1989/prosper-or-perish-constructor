"""Tea Garden: a hillside combed with rows of rounded, clipped tea bushes and baskets of plucked leaf.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/tea_garden/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/tea_garden

Identity: a rounded hill whose whole face is ribbed with contour rows of dome-shaped tea bushes,
each row tipped with pale yellow-green new flush and separated by thin red-earth paths; a tall
picker's back-basket and a flat tray heaped with fresh leaf stand at the foot of the slope.

Local helpers: ``hedge`` (a contour row of clipped bushes: merged domes, per-bush light, leaf dabs,
pale flush on top, dark underside), ``leaves`` (small pointed leaf dabs painted in one layer),
``leafpile`` (heap of fresh leaves), ``backbasket`` (tall wicker carrying basket).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("terraces", "fruit_orchard", "farming_village", "tobacco_plantation")

BUSH = ("#78aa64", "#0e2416")
FLUSH = [(172, 200, 84), (156, 190, 72), (186, 206, 96), (140, 176, 66)]
EARTH = ("#8c603c", "#4e3420")


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def leaf_pts(x, y, L, ang, w=0.42):
    """Small pointed leaf (lens) as polygon points."""
    a = math.radians(ang)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array([x, y]) - d * L / 2
    ts = np.linspace(0, 1, 7)
    s1 = [b + d * L * t + n * L * w / 2 * math.sin(math.pi * t) for t in ts]
    s2 = [b + d * L * t - n * L * w / 2 * math.sin(math.pi * t) for t in ts]
    return [tuple(p) for p in s1 + s2[::-1]]


def leaves(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Paint many small leaves (x, y, length, angle, rgba) in one blended layer."""

    def paint(dr):
        for x, y, L, ang, col in items:
            dr.polygon(leaf_pts(x, y, L, ang), fill=col)

    ic.overlay(paint, clip)


def hedge(ic: Icon, base, h: float, step: float = 0.95) -> Image.Image:
    """Row of clipped tea bushes along the baseline ``base`` (list of points, left to right).

    Rounded domes that touch at their shoulders, shaped by a few large soft leaf-mass tones (lit
    upper left, core shadow lower right), sparse leaf dabs, a thin broken edge of yellow-green new
    shoots on the crown and a dark underside. Returns the row mask."""
    rnd = ic.random
    xs = np.array([p[0] for p in base])
    ys = np.array([p[1] for p in base])
    domes = []
    x = xs[0] + h * 0.45
    while x < xs[-1] - h * 0.35:
        y = float(np.interp(x, xs, ys))
        rx = h * rnd.uniform(0.52, 0.64)
        ry = h * rnd.uniform(0.44, 0.56)
        domes.append((x, y - ry * 0.92, rx, ry))
        x += h * step * rnd.uniform(0.86, 1.12)
    m = blank()
    # a low band under the domes keeps the row continuous; notches between domes stay visible
    band = [(xs[0] + h * 0.3, ys[0])] + [(x, y - h * 0.32) for x, y in zip(xs, ys)][3:-3]
    band += [(xs[-1] - h * 0.3, ys[-1])] + [(x, y) for x, y in zip(xs[::-1], ys[::-1])]
    m = union(m, ic.poly_mask(band))
    for cx, cy, rx, ry in domes:
        m = union(m, ic.poly_mask(ic.jitter(cx, cy, rx, ry, 22, 0.04)))
    top = min(ys) - h * 1.1
    ic.fill(m, BUSH[0], BUSH[1], (top, max(ys)), noise=0.3, chroma=0.12)
    for cx, cy, rx, ry in domes:  # soft leaf masses: lit upper left, core shadow lower right
        ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 0.95, cy - ry * 1.0, cx + rx * 0.35, cy + ry * 0.05))),
                 (150, 190, 120), 0.30, blur=h * 0.16)
        ic.shade(ic.intersect(m, ic.mask("ellipse", (cx + rx * 0.05, cy - ry * 0.2, cx + rx * 1.35, cy + ry * 1.3))),
                 (4, 12, 8), 0.46, blur=h * 0.14)
        for _ in range(3):  # a few big clumps of foliage within the bush
            a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.2, 0.6)
            bx, by = cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r
            ic.shade(ic.intersect(m, ic.mask("ellipse", (bx - rx * 0.4, by - ry * 0.3, bx + rx * 0.4, by + ry * 0.3))),
                     (120, 160, 100) if by < cy else (6, 16, 10), 0.18, blur=h * 0.1)
    items = []
    for cx, cy, rx, ry in domes:
        for _ in range(int(22 * h / 100)):
            a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.6
            x, y = cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r
            v = (y - (cy - ry)) / (2 * ry)
            L = h * rnd.uniform(0.11, 0.16)
            col = (110, 150, 96, 60) if rnd.random() < 0.45 - 0.6 * v else (8, 22, 12, 80)
            items.append((x, y, L, rnd.uniform(0, 180), col))
    leaves(ic, items, m)
    flush = []
    for cx, cy, rx, ry in domes:  # thin broken edge of new shoots along the crown
        u = -0.85
        while u < 0.6:
            if rnd.random() < 0.6:
                x = cx + u * rx
                y = cy - ry * math.sqrt(max(0.0, 1 - u * u)) * 0.96 + h * 0.03
                c = rnd.choice(FLUSH)
                a = 245 if u < 0.1 else 170
                flush.append((x, y, h * rnd.uniform(0.08, 0.12), rnd.uniform(-20, 20) + 70 * u, c + (a,)))
            u += rnd.uniform(0.06, 0.14)
    leaves(ic, flush, m)
    ic.shade(ic.intersect(m, ic.poly_mask([(x, y - h * 0.34) for x, y in base] + [(x, y + 5) for x, y in base[::-1]])),
             (4, 10, 6), 0.55, blur=h * 0.1)
    return m


def leafpile(ic: Icon, mask: Image.Image, cx: float, top: float, bottom: float, w: float) -> None:
    """Heap of fresh leaf: bright yellow-green body, lit crown, many small leaf dabs and pale tips."""
    rnd = ic.random
    ic.fill(mask, "#a4c056", "#2c4a16", radial=(cx - w * 0.3, top, w * 0.95), noise=0.3)
    items = []
    for _ in range(int(w * 1.4)):
        x, y = rnd.uniform(cx - w / 2, cx + w / 2), rnd.uniform(top, bottom)
        v = (y - top) / max(bottom - top, 1)
        col = rnd.choice(((168, 196, 88, 220), (132, 170, 70, 210), (84, 124, 42, 210), (208, 220, 120, 210)))
        if rnd.random() < v * 0.5:
            col = (26, 44, 14, 190)
        items.append((x, y, rnd.uniform(14, 24), rnd.uniform(0, 180), col))
    leaves(ic, items, mask)


def backbasket(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Tall wicker back-basket flaring to the mouth, with woven bands and a rolled rim."""
    w = x1 - x0
    body = [(x0, y0), (x1, y0), (x1 - w * 0.16, y1 - 12), (x1 - w * 0.24, y1), (x0 + w * 0.24, y1),
            (x0 + w * 0.16, y1 - 12)]
    m = ic.poly_mask(body)
    ic.fill(m, "#a47a46", "#40280f", (x0, x1), vertical=False, noise=0.28)
    rnd = ic.random

    def weave(dr):
        for k, y in enumerate(np.arange(y0 + 14, y1, 13)):
            dr.line([(x0, y), (x1, y + rnd.uniform(-2, 2))], fill=(70, 46, 22, 150), width=3)
            off = 0 if k % 2 else 9
            for x in np.arange(x0 + off, x1, 18):
                dr.line([(x, y - 11), (x + 2, y)], fill=(230, 200, 140, 70), width=4)
        for x in np.arange(x0 + 20, x1, 26):
            dr.line([(x, y0), (x + (x0 + w / 2 - x) * 0.3, y1)], fill=(60, 40, 20, 90), width=3)

    ic.overlay(weave, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0 + w * 0.55, 0, SIZE, SIZE))), (20, 12, 4), 0.35, blur=14)
    ic.outline(body, 5, (34, 20, 10, 220))
    ic.line([(x0 - 4, y0 + 2), (x1 + 4, y0 + 2)], 18, (92, 62, 32))
    ic.line([(x0 - 2, y0 - 2), (x1 + 2, y0 - 2)], 6, (186, 150, 96, 200))
    # carrying strap looping over the rim
    ic.line([(x0 + w * 0.22, y0 + 4), (x0 + w * 0.12, y0 + (y1 - y0) * 0.55), (x0 + w * 0.3, y1 - 30)], 12, (70, 46, 26))


def chaikin(pts, n: int = 3):
    """Round a polyline by corner cutting (endpoints kept)."""
    for _ in range(n):
        out = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            out += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        out.append(pts[-1])
        pts = out
    return pts


def shadetree(ic: Icon, x: float, base: float, top: float, rx: float, ry: float) -> Image.Image:
    """Small shade tree: slim leaning trunk with two limbs and a flat, feathery crown of soft
    clumps lit from the upper left, dark underside. Returns the crown mask."""
    rnd = ic.random
    trunk = [(x - 24, base), (x - 14, base - 30), (x - 10, top + 40), (x - 2, top), (x + 20, top), (x + 14, top + 40),
             (x + 16, base - 30), (x + 28, base)]
    ic.poly(trunk, "#8a7058", "#3a2a1c", span=(x - 16, x + 20), vertical=False, noise=0.26, edge=3)
    cy = top - ry * 0.35
    for p1, w in (((x - rx * 0.55, cy + ry * 0.1), 11), ((x + rx * 0.6, cy), 10)):
        ic.line([(x + 4, top + 26), p1], w, (84, 64, 46))
    inner = ic.poly_mask(ic.jitter(x + 4, cy + ry * 0.35, rx * 0.6, ry * 0.42, 22, 0.1))
    ic.fill(inner, "#243a1c", "#0c1608", (cy, cy + ry), noise=0.3)
    m = blank()
    blobs = []
    for _ in range(24):
        u = rnd.uniform(-0.85, 0.85)
        blobs.append((x + u * rx, cy - ry * 0.3 * (1 - u * u) + rnd.uniform(-ry * 0.25, ry * 0.3),
                      ry * rnd.uniform(0.38, 0.56) * (1.1 - 0.3 * abs(u))))
    blobs.sort(key=lambda b: b[1])
    for bx, by, br in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.35, br, 24, 0.08))
        ic.fill(bm, "#5e8244", "#14240e", radial=(bx - br * 0.8, by - br * 0.9, br * 2.3), noise=0.28, chroma=0.12)
        m = union(m, bm)

    def dabs(dr):
        for _ in range(360):
            px, py = rnd.uniform(x - rx * 1.1, x + rx * 1.1), rnd.uniform(cy - ry * 1.2, cy + ry)
            v = (py - cy) / ry
            r = rnd.uniform(4, 8)
            col = (140, 170, 100, 60) if rnd.random() < 0.45 - 0.5 * v else (14, 26, 10, 70)
            dr.ellipse((px - r, py - r * 0.55, px + r, py + r * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, cy + ry * 0.1, SIZE, SIZE))), (8, 16, 8), 0.45, blur=12)
    return m


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.84

    # ---- the hill: summit right of centre, a lower shoulder on the left, a long gentle foot
    ctrl = [(14, 982), (50, 952), (100, 884), (150, 780), (192, 636), (236, 548), (290, 512), (360, 504),
            (430, 502), (478, 476), (526, 414), (580, 378), (640, 366), (720, 366), (800, 384), (880, 440), (950, 540),
            (996, 680), (1012, 840), (1012, 1000)]
    crest = chaikin(ctrl, 3)
    crest = [(x, y + rnd.uniform(-3, 3)) for x, y in crest]
    cx_, cy_ = np.array([p[0] for p in crest]), np.array([p[1] for p in crest])

    def crest_y(x):
        return float(np.interp(x, cx_, cy_))

    front = [(x, 1000 + 12 * math.sin(math.pi * (x - 14) / 996)) for x in np.linspace(990, 30, 12)]
    hill = crest + front
    H = ic.poly_mask(hill)
    ic.fill(H, "#80543a", "#3e2616", radial=(360, 300, 900), noise=0.34, chroma=0.12)
    for _ in range(70):
        x, y = rnd.uniform(40, 990), rnd.uniform(320, 990)
        ic.shade(ic.intersect(H, ic.mask("ellipse", (x - 14, y - 5, x + 14, y + 5))),
                 (255, 226, 190) if rnd.random() < 0.4 else (0, 0, 0), 0.16, blur=2)
    # earth lip along the left foot: a lit rim of bare soil just inside the slope's edge
    lip = [(x, crest_y(x)) for x in np.linspace(14, 330, 30)]
    lipm = ic.poly_mask(lip + [(x + 10, y + 34) for x, y in lip[::-1]])
    ic.shade(ic.intersect(H, lipm), (214, 150, 100), 0.30, blur=6)
    ic.line([(x + 8, y + 36) for x, y in lip], 5, (40, 24, 14, 110))

    # ---- shade tree on the summit
    shadetree(ic, 668, 384, 272, 190, 84)

    # ---- contour rows of tea bushes, back to front, tighter towards the top
    rows = [(412, 0.92, 36), (462, 0.88, 42), (518, 0.84, 48), (580, 0.8, 54), (650, 0.76, 60),
            (728, 0.72, 66), (816, 0.68, 72), (914, 0.64, 80), (1016, 0.6, 86)]
    for k, (yc, kf, h) in enumerate(rows):
        lam, ph, amp = rnd.uniform(90, 140), rnd.uniform(0, 6.3), h * 0.07
        segs, cur = [], []
        for x in np.arange(0, SIZE, 8):
            y = yc + kf * (crest_y(x) - 366) + amp * math.sin(x / lam + ph)
            yy = int(min(max(y - h * 0.2, 0), SIZE - 1))
            inside = y < 1010 and H.getpixel((int(x), yy)) and H.getpixel((int(min(x + 30, SIZE - 1)), yy)) and \
                H.getpixel((int(max(x - 30, 0)), yy))
            if inside:
                cur.append((float(x), y))
            elif cur:
                segs.append(cur)
                cur = []
        if cur:
            segs.append(cur)
        for base in segs:
            a, b = rnd.randint(0, 5), rnd.randint(0, 5)  # uneven row ends
            base = base[a:len(base) - b] if len(base) - a - b >= 6 else base
            if len(base) < 6:
                continue
            ic.shade(ic.poly_mask([(x, y - 10) for x, y in base] + [(x, y + h * 0.28) for x, y in base[::-1]]),
                     (20, 10, 4), 0.32, blur=h * 0.12)
            hedge(ic, base, h)

    # ---- flat tray of plucked leaf and the back-basket at the foot of the slope
    ic.shade(ic.mask("ellipse", (540, 944, 1016, 1018)), alpha=0.5, blur=10)
    tray = ic.mask("ellipse", (544, 890, 820, 994))
    ic.fill(tray, "#a07a48", "#4e3620", radial=(560, 890, 290), noise=0.25)
    ic.overlay(lambda d: d.ellipse((544, 890, 820, 994), outline=(50, 32, 16, 220), width=6))
    inner = ic.mask("ellipse", (564, 901, 800, 982))
    leafpile(ic, inner, 682, 897, 984, 236)
    ic.shade(ic.intersect(inner, ic.mask("rectangle", (0, 897, SIZE, 916))), alpha=0.35, blur=6)

    # the basket casts shade on the bushes behind it, so its heap of bright leaf stands clear
    ic.shade(ic.mask("ellipse", (740, 620, 1080, 1000)), (6, 10, 4), 0.55, blur=30)
    pts = ic.jitter(898, 748, 104, 64, 20, 0.08)
    pile = ic.poly_mask(pts)
    leafpile(ic, pile, 898, 690, 800, 200)
    ic.outline(pts, 5, (20, 32, 10, 200))
    backbasket(ic, 808, 760, 990, 1000)
    ic.shade(ic.intersect(pile, ic.mask("rectangle", (0, 740, SIZE, 770))), alpha=0.25, blur=10)

    # ---- afternoon light: lit left flank, shaded right flank
    ic.shade(ic.mask("ellipse", (-200, 200, 560, 900)), (255, 240, 200), 0.08, blur=80)
    ic.shade(ic.mask("ellipse", (760, 280, 1300, 800)), (10, 14, 6), 0.22, blur=80)
