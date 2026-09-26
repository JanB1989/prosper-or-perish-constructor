"""Saffron Croft: a low fieldstone croft under thatch behind beds of purple crocus; baskets of flowers.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/saffron_croft/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/saffron_croft

Identity: a carpet of lilac-purple crocus goblets with red stigmas in raised beds, a small stone
croft with a thatched roof behind them, a basket heaped with picked flowers and a shallow dish of
red saffron threads at the bottom right. Tier 0 of the saffron chain (Saffron Kiln Croft adds the kiln).

Local helpers: ``crocus`` (goblet flower with grass leaves and red stigmas), ``bed`` (raised crocus
bed in perspective), ``fieldstone`` (rough stone wall), ``thatch`` (from coffee_grove),
``threads`` (red saffron threads in a dish).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 53
REFS = ("fruit_orchard", "fiber_crops_farm", "royal_garden", "free_village")

PETAL = (("#9a5ec8", "#3a1868"), ("#8c52bc", "#34145e"), ("#a46cd0", "#44206e"), ("#8048b0", "#2e1056"))
STIGMA = (196, 40, 24)
THREAD = ((178, 30, 20), (214, 64, 36), (130, 18, 12))


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def petal_pts(base, deg: float, length: float, width: float):
    """Petal outline: narrow at the base, widest past the middle, rounded pointed tip."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 14)
    hw = [width / 2 * math.sin(math.pi * t ** 1.25) ** 0.8 for t in ts]
    s1 = [b + d * length * t + n * w for t, w in zip(ts, hw)]
    s2 = [b + d * length * t - n * w for t, w in zip(ts, hw)]
    return [tuple(p) for p in s1 + s2[::-1]]


LILAC = (np.array((182, 140, 222)), np.array((80, 48, 126)))
VIOLET = (np.array((112, 46, 164)), np.array((34, 10, 66)))


def petal_colors(ic: Icon):
    """A petal palette somewhere between pale lilac and deep violet."""
    t = ic.random.random() ** 0.9
    light = tuple(int(v) for v in LILAC[0] * (1 - t) + VIOLET[0] * t)
    dark = tuple(int(v) for v in LILAC[1] * (1 - t) + VIOLET[1] * t)
    return light, dark


def grass(ic: Icon, x: float, y: float, h: float, n: int = 4, spread: float = 34) -> None:
    """Tuft of thin crocus leaves: dark green blades, each with a pale midstripe."""
    rnd = ic.random
    for _ in range(n):
        ang = -90 + rnd.uniform(-spread, spread)
        L = h * rnd.uniform(0.7, 1.15)
        ex, ey = x + math.cos(math.radians(ang)) * L, y + math.sin(math.radians(ang)) * L
        mx, my = (x + ex) / 2 + rnd.uniform(-5, 5), (y + ey) / 2
        g = rnd.uniform(0.8, 1.15)
        ic.line([(x, y), (mx, my), (ex, ey)], max(3, int(h * 0.07)), tuple(int(v * g) for v in (54, 86, 34)))
        ic.line([(x, y), (mx, my)], 2, (160, 186, 118, 110))


def crocus(ic: Icon, x: float, y: float, s: float, pal=PETAL[0], lean: float = 0.0, open_: float = 1.0) -> None:
    """Saffron crocus seen from the raised camera: grass leaves, a goblet of six petals with dark veins
    towards the throat, three long red stigmas over the rim. ``open_`` < 0.5 draws a closed bud."""
    rnd = ic.random
    grass(ic, x, y + s * 0.2, s * 1.7, 3, 38)
    cx, cy = x + lean * s, y - s * 0.55
    ic.line([(x, y + s * 0.2), (cx, cy + s * 0.3)], max(3, int(s * 0.14)), (190, 190, 170))
    light, dark = pal
    o = max(0.2, open_)
    back = [(-90 - 22 * o, 0.95), (-90 + 22 * o, 0.95), (-90, 1.0)]
    front = [(-90 - 38 * o, 0.9), (-90 + 38 * o, 0.9), (-90, 0.86)]
    wide = 0.62 * (0.7 + 0.3 * o)
    for ang, f in back:  # inner petals, seen from inside: darker
        pts = petal_pts((cx, cy + s * 0.12), ang + lean * 10, s * 1.05 * f, s * wide)
        ic.fill(ic.poly_mask(pts), tuple(int(v * 0.8) for v in rgb(light)), dark, (cy - s, cy + s * 0.1), noise=0.14)
        ic.outline(pts, 2, (40, 16, 60, 120))
    if open_ >= 0.5:  # the stigmas: three red threads hanging out over the rim
        for dx, dy in ((-0.34, -0.72), (0.1, -0.86), (0.4, -0.66)):
            ic.line([(cx, cy - s * 0.1), (cx + dx * s * 0.6 * o, cy + dy * s * 0.6), (cx + dx * s * o, cy + dy * s)],
                    max(3, int(s * 0.12)), STIGMA)
        ic.line([(cx - s * 0.08, cy - s * 0.2), (cx - s * 0.14, cy - s * 0.62)], max(2, int(s * 0.08)), (226, 184, 60))
    for ang, f in front:  # outer petals, lit from the upper left
        pts = petal_pts((cx, cy + s * 0.16), ang + lean * 10, s * 0.95 * f * (1.1 - 0.1 * o), s * (wide + 0.02))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        ic.fill(ic.poly_mask(pts), light, dark, radial=(min(xs), min(ys), s * 1.3), noise=0.14)
        vein = [(cx, cy + s * 0.12), (cx + math.cos(math.radians(ang)) * s * 0.5, cy + math.sin(math.radians(ang)) * s * 0.5)]
        ic.line(vein, max(2, int(s * 0.07)), (60, 26, 90, 150))
        ic.outline(pts, 2, (40, 16, 60, 130))
    if open_ >= 0.5:  # a stigma tip over the front petal
        ic.line([(cx + s * 0.02, cy - s * 0.3), (cx + s * 0.1, cy - s * 0.95)], max(3, int(s * 0.12)), STIGMA)


def bed(ic: Icon, pts, rows, x_edges, rng_lean: float = 0.4) -> None:
    """Raised crocus bed: dark tilled earth, then rows of crocus back to front, growing towards the viewer.
    Flowers are jittered, vary in size, tilt and hue, some are closed buds, and leaf tufts fill the gaps."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, "#5a4430", "#3a2a1c", (min(ys), max(ys)), noise=0.32)
    for _ in range(90):
        x, y = rnd.uniform(min(p[0] for p in pts), max(p[0] for p in pts)), rnd.uniform(min(ys), max(ys))
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - 12, y - 5, x + 12, y + 5))),
                 (255, 230, 190) if rnd.random() < 0.4 else (0, 0, 0), 0.18, blur=2)
    for (y, s), (x0, x1) in zip(rows, x_edges):
        x = x0 + rnd.uniform(0, s * 0.6)
        while x < x1:
            fx, fy = x + rnd.uniform(-12, 12), y + rnd.uniform(-12, 12)
            r = rnd.random()
            if r < 0.14:
                grass(ic, fx, fy + s * 0.2, s * rnd.uniform(1.4, 2.0), rnd.randint(4, 6), 40)
            elif r < 0.86:
                op = 1.0 if rnd.random() < 0.72 else rnd.choice((0.3, 0.3, 0.6))
                crocus(ic, fx, fy, s * rnd.uniform(0.75, 1.25), petal_colors(ic), rnd.uniform(-rng_lean, rng_lean), op)
            if rnd.random() < 0.55:  # leaves between the flowers
                grass(ic, x + s * rnd.uniform(0.6, 0.9), y + s * rnd.uniform(0.1, 0.4), s * rnd.uniform(1.1, 1.6),
                      rnd.randint(2, 4), 30)
            x += s * rnd.uniform(1.4, 1.95)


def fieldstone(ic: Icon, box, base=("#a09280", "#6e6456")) -> None:
    """Rough fieldstone wall: dark mortar bed, then irregular rounded stones in uneven courses."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, "#4e443a", "#2e2822", edge=0)
    y = y0 + 4
    while y < y1:
        h = rnd.uniform(34, 50)
        x = x0 - rnd.uniform(0, 40)
        while x < x1:
            w = rnd.uniform(52, 96)
            pts = ic.jitter(x + w / 2, y + h / 2, w / 2 - 3, h / 2 - 3, 10, 0.1)
            t = rnd.uniform(0.82, 1.12)
            c1 = tuple(int(min(255, v * t)) for v in rgb(base[0]))
            c2 = tuple(int(v * t) for v in rgb(base[1]))
            m = ic.intersect(ic.poly_mask(pts), ic.mask("rectangle", box))
            ic.fill(m, c1, c2, radial=(x + w * 0.2, y, w * 0.9), noise=0.24, chroma=0.14)
            x += w
        y += h * 0.92
    ic.shade(ic.mask("rectangle", (x0, y1 - 80, x1, y1)), (40, 50, 24), 0.3, blur=18)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 4)


def drystone(ic: Icon, pts) -> None:
    """Low drystone wall (polygon): dark gaps, flat irregular stones in courses, lit tops, cope stones."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    ic.fill(m, "#3e362e", "#221e1a", noise=0.2)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    y = min(ys) - 6
    while y < max(ys):
        h = rnd.uniform(24, 34)
        x = min(xs) - rnd.uniform(0, 30)
        while x < max(xs):
            w = rnd.uniform(44, 84)
            st = ic.jitter(x + w / 2, y + h / 2, w / 2 - 2, h / 2 - 2, 9, 0.12)
            t = rnd.uniform(0.78, 1.14)
            sm = ic.intersect(ic.poly_mask(st), m)
            ic.fill(sm, tuple(int(min(255, v * t)) for v in (168, 156, 136)), tuple(int(v * t) for v in (96, 88, 76)),
                    (y, y + h), noise=0.26, chroma=0.14)
            ic.shade(ic.intersect(sm, ic.mask("rectangle", (x, y, x + w, y + h * 0.3))), (255, 244, 220), 0.18)
            x += w + rnd.uniform(1, 4)
        y += h + rnd.uniform(1, 3)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (min(xs), max(ys) - 26, max(xs), max(ys)))), (30, 34, 16), 0.35,
             blur=8)
    ic.outline(pts, 4)


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


def threads(ic: Icon, clip: Image.Image, box, n: int = 160) -> None:
    """Loose red saffron threads: short curved strokes, dark under light, trumpet ends slightly thicker."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(dr):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            a = rnd.uniform(0, math.pi)
            L = rnd.uniform(16, 28)
            ex, ey = x + math.cos(a) * L, y + math.sin(a) * L * 0.5
            mx, my = (x + ex) / 2 + rnd.uniform(-4, 4), (y + ey) / 2 + rnd.uniform(-3, 3)
            mid, lit, dk = THREAD
            dr.line([(x, y + 2), (mx, my + 2), (ex, ey + 2)], fill=dk + (200,), width=6)
            dr.line([(x, y), (mx, my), (ex, ey)], fill=mid + (255,), width=5)
            dr.line([(x - 1, y - 1), (mx - 1, my - 1)], fill=lit + (200,), width=2)

    ic.overlay(paint, clip)


def dish(ic: Icon, cx: float, cy: float, rx: float, ry: float, c=("#b07a4e", "#6a4024")) -> None:
    """Shallow clay dish heaped with saffron threads."""
    ic.shade(ic.mask("ellipse", (cx - rx * 1.05, cy - ry * 0.2, cx + rx * 1.15, cy + ry * 1.6)), alpha=0.5, blur=8,
             clip=False)
    body = [(cx - rx, cy)] + [(cx + math.cos(t) * rx * 0.86, cy + ry * 0.3 + math.sin(t) * ry * 0.95)
                              for t in np.linspace(math.pi, 0, 20)[::-1]][::-1] + [(cx + rx, cy)]
    ic.poly(body, c[0], c[1], span=(cx - rx, cx + rx), vertical=False, edge=3)
    ic.fill(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)), "#8a5a36", "#5a361c", noise=0.2)
    inner = ic.mask("ellipse", (cx - rx * 0.86, cy - ry * 0.78, cx + rx * 0.86, cy + ry * 0.8))
    ic.fill(inner, "#6e1a10", "#3a0c08", noise=0.25)
    threads(ic, inner, (cx - rx * 0.9, cy - ry * 0.9, cx + rx * 0.8, cy + ry * 0.7), int(rx * ry / 40))
    ic.shade(ic.intersect(inner, ic.mask("ellipse", (cx - rx * 0.3, cy - ry * 0.3, cx + rx * 1.2, cy + ry * 1.2))),
             (20, 0, 0), 0.3, blur=10)
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(60, 34, 18, 220), width=5))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.90

    # ---- the croft: fieldstone walls, a plank door, one small window, thatched roof
    HL, HR, EAVE, BASE = 470, 960, 470, 720
    fieldstone(ic, (HL, EAVE, HR, BASE))
    ic.door(HL + 250, EAVE + 70, HL + 340, BASE, arched=False, surround=None)
    ic.window(HL + 90, EAVE + 80, HL + 150, EAVE + 140)
    ic.shade(ic.mask("rectangle", (HL, EAVE, HR, EAVE + 60)), alpha=0.5, blur=12)
    ridge = [(HL + 70, 250), ((HL + HR) / 2, 244), (HR - 70, 252)]
    ex = np.linspace(HL - 50, HR + 40, 16)
    thatch(ic, ridge, [(x, EAVE + 6 + rnd.uniform(-5, 6)) for x in ex])
    ic.shade(ic.poly_mask([(760, 220), (1024, 220), (1024, 500), (780, 500)]), alpha=0.2, blur=50)
    # a stack of empty baskets and a hoe against the wall
    ic.line([(HR - 60, BASE - 8), (HR - 20, EAVE + 30)], 10, (120, 90, 60))
    ic.line([(HR - 38, EAVE + 26), (HR - 4, EAVE + 36)], 14, (90, 90, 96))

    # ---- ground
    top = [(24, 700)] + [(x, 680 + rnd.uniform(-10, 10)) for x in np.linspace(80, 960, 12)] + [(1006, 700)]
    ic.poly(top + [(1010, 990), (520, 1000), (18, 992)], "#7a6444", "#4e3e2a", noise=0.32, edge=3)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(700, 990)
        ic.shade(ic.mask("ellipse", (x - 16, y - 6, x + 16, y + 6)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.14, blur=2)

    # ---- low drystone wall under the croft's right side, stepping down towards the basket
    WL, WR = 648, 1004
    ic.shade(ic.mask("rectangle", (WL, 800, WR + 10, 824)), alpha=0.45, blur=8)
    drystone(ic, [(WL, 812), (WL, 696), (WL + 40, 688), (800, 690), (816, 716), (WR, 724), (WR, 812)])
    for gx in (672, 760, 858, 940):
        grass(ic, gx + rnd.uniform(-10, 10), 818, rnd.uniform(34, 52), rnd.randint(3, 5), 44)

    # ---- crocus beds, back one first, edged with a low stone kerb; the back edge steps unevenly
    back = [(40, 700), (170, 698), (186, 684), (360, 682), (376, 690), (520, 688), (536, 678), (640, 680),
            (660, 780), (26, 780)]
    ic.poly([(26, 776), (240, 778), (250, 772), (664, 774), (664, 800), (26, 800)], "#8a7e6c", "#5a5044", edge=3)
    bed(ic, back, [(700, 28), (730, 32), (760, 34)], [(196, 350), (56, 630), (50, 640)])
    for x, y, s in ((110, 722, 44), (300, 706, 42), (470, 716, 46), (590, 702, 40)):  # a few taller flowers
        crocus(ic, x, y, s, petal_colors(ic), rnd.uniform(-0.3, 0.3))
    front = [(20, 810), (800, 810), (830, 972), (14, 972)]
    bed(ic, front, [(826, 38), (872, 44), (924, 50), (970, 56)], [(34, 790), (30, 800), (26, 810), (40, 790)])
    ic.poly([(10, 968), (836, 968), (840, 994), (8, 994)], "#8a7e6c", "#5a5044", edge=3)

    # ---- picking basket heaped with flowers, dish of red threads
    ic.shade(ic.mask("ellipse", (820, 972, 1020, 1006)), alpha=0.5, blur=8, clip=False)
    ic.fill(ic.mask("ellipse", (838, 822, 1004, 870)), "#2a1a24", "#180e14")
    heap = []
    for _ in range(26):
        a, rr = rnd.uniform(math.pi, 2 * math.pi), rnd.random() ** 0.6
        heap.append((921 + math.cos(a) * 70 * rr, 852 + math.sin(a) * 38 * rr + rnd.uniform(0, 14)))
    heap.sort(key=lambda p: p[1])
    for hx, hy in heap:
        pal = rnd.choice(PETAL)
        pts = ic.jitter(hx, hy, 17, 12, 7, 0.2)
        ic.fill(ic.poly_mask(pts), pal[0], pal[1], radial=(hx - 12, hy - 10, 30), noise=0.2)
        ic.outline(pts, 2, (40, 16, 60, 140))
        ic.line([(hx - 4, hy - 2), (hx + 6, hy - 10)], 3, STIGMA)
    ic.basket(836, 852, 1006, 994)
    dish(ic, 700, 952, 92, 34)
